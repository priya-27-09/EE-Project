import os
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from web3 import Web3

from app.core.config import settings
from app.models.blockchain_record import (
    BlockchainRecord,
    STATUS_PENDING,
    STATUS_SUBMITTED,
    STATUS_CONFIRMED,
    STATUS_FAILED,
    STATUS_NOT_CONFIGURED,
    EVENT_COMPLAINT_CREATED,
    EVENT_COMPLAINT_STATUS_CHANGED,
    EVENT_RESOLUTION_EVIDENCE_ADDED,
    EVENT_RESOLUTION_VERIFICATION,
    EVENT_HUMAN_RESOLUTION_REVIEW,
)
from app.services.audit_service import record_audit_log

ABI_PATH = Path(__file__).resolve().parent.parent.parent / "blockchain" / "abi" / "CivicGuardianAudit.json"


class BlockchainService:
    """
    Centralized Blockchain Service for AI Civic Guardian.
    Anchors tamper-evident cryptographic hashes on local Ganache Ethereum blockchain.
    PostgreSQL remains the primary database and single source of truth.
    """

    _cached_abi = None

    @classmethod
    def load_abi(cls) -> list:
        """Load contract ABI from compiled artifact."""
        if cls._cached_abi is not None:
            return cls._cached_abi
        if not ABI_PATH.exists():
            return []
        try:
            with open(ABI_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                cls._cached_abi = data.get("abi", [])
                return cls._cached_abi
        except Exception:
            return []

    @classmethod
    def get_web3(cls) -> Web3:
        """Instantiate Web3 provider with configured timeout."""
        rpc_url = settings.BLOCKCHAIN_RPC_URL or "http://127.0.0.1:7545"
        return Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 3}))

    @classmethod
    def is_configured(cls) -> bool:
        """Check if minimum blockchain configuration is present."""
        return bool(
            settings.BLOCKCHAIN_ENABLED
            and settings.BLOCKCHAIN_RPC_URL
            and settings.BLOCKCHAIN_CONTRACT_ADDRESS
            and settings.BLOCKCHAIN_PRIVATE_KEY
        )

    @classmethod
    def is_available(cls) -> Tuple[bool, str]:
        """
        Check whether the local Ganache RPC endpoint is live and responding.
        Returns (is_available, status_message).
        """
        if not settings.BLOCKCHAIN_ENABLED:
            return False, "BLOCKCHAIN_DISABLED"
        if not settings.BLOCKCHAIN_RPC_URL:
            return False, "BLOCKCHAIN_NOT_CONFIGURED"

        try:
            w3 = cls.get_web3()
            if not w3.is_connected():
                return False, "BLOCKCHAIN_UNAVAILABLE"
            return True, "CONNECTED"
        except Exception as exc:
            return False, f"RPC_ERROR: {str(exc)}"

    @classmethod
    def get_network_info(cls) -> Dict[str, Any]:
        """
        Fetch real network and account diagnostics.
        Strictly excludes private keys.
        """
        configured = cls.is_configured()
        available, avail_msg = cls.is_available()

        info = {
            "configured": configured,
            "available": available,
            "status_message": avail_msg,
            "rpc_url": settings.BLOCKCHAIN_RPC_URL,
            "chain_id": settings.BLOCKCHAIN_CHAIN_ID,
            "contract_address": settings.BLOCKCHAIN_CONTRACT_ADDRESS or None,
            "account_address": settings.BLOCKCHAIN_ACCOUNT_ADDRESS or None,
            "latest_block": None,
            "balance_eth": None,
        }

        if available:
            try:
                w3 = cls.get_web3()
                info["chain_id"] = w3.eth.chain_id
                info["latest_block"] = w3.eth.block_number

                # Determine account address
                acct_addr = settings.BLOCKCHAIN_ACCOUNT_ADDRESS
                if not acct_addr and settings.BLOCKCHAIN_PRIVATE_KEY:
                    try:
                        acct_addr = w3.eth.account.from_key(settings.BLOCKCHAIN_PRIVATE_KEY).address
                        info["account_address"] = acct_addr
                    except Exception:
                        pass

                if acct_addr:
                    balance_wei = w3.eth.get_balance(acct_addr)
                    info["balance_eth"] = str(round(float(w3.from_wei(balance_wei, "ether")), 4))
            except Exception as exc:
                info["status_message"] = f"DIAGNOSTIC_FETCH_ERROR: {str(exc)}"

        return info

    @staticmethod
    def canonicalize_payload(payload: dict) -> str:
        """
        Deterministic JSON serialization:
        - Sorted keys
        - Separators (',', ':') with no extra whitespace
        - UTF-8 representation without ascii escaping
        """
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def hash_payload(cls, payload: dict) -> Tuple[str, bytes]:
        """
        Compute deterministic SHA-256 hash of canonical payload.
        Returns:
            - hex_str: 66-character hex string starting with '0x'
            - raw_bytes: 32 raw bytes (bytes32 for Solidity)
        """
        canonical_str = cls.canonicalize_payload(payload)
        canonical_bytes = canonical_str.encode("utf-8")
        hasher = hashlib.sha256(canonical_bytes)
        hex_digest = hasher.hexdigest()
        return f"0x{hex_digest}", hasher.digest()

    @classmethod
    def compute_event_hash(
        cls,
        complaint_reference: str,
        event_type: str,
        unique_key: str,
    ) -> Tuple[str, bytes]:
        """
        Compute unique deterministic 32-byte event hash for an event instance.
        Ensures reproducible identification without storing PII on-chain.
        """
        canonical_tuple = f"{complaint_reference.strip().upper()}:{event_type.strip().upper()}:{unique_key.strip()}"
        hasher = hashlib.sha256(canonical_tuple.encode("utf-8"))
        hex_digest = hasher.hexdigest()
        return f"0x{hex_digest}", hasher.digest()

    @classmethod
    def anchor_event(
        cls,
        complaint_id: int,
        complaint_public_id: str,
        event_type: str,
        payload: dict,
        unique_key: str,
        db: Session,
        user_id: Optional[int] = None,
    ) -> BlockchainRecord:
        """
        Core blockchain anchoring entry point.
        1. Generates deterministic canonical dataHash and eventHash.
        2. Creates BlockchainRecord in PostgreSQL (status=PENDING).
        3. If blockchain unconfigured or unavailable, marks status safely without failing complaint.
        4. Submits Web3 signed transaction to Ganache.
        5. Waits for receipt and updates record to CONFIRMED or FAILED.
        6. Logs audit trail.
        """
        data_hash_hex, data_hash_bytes = cls.hash_payload(payload)
        event_hash_hex, event_hash_bytes = cls.compute_event_hash(
            complaint_reference=complaint_public_id,
            event_type=event_type,
            unique_key=unique_key,
        )

        now = datetime.now(timezone.utc)

        # 1. Create PostgreSQL BlockchainRecord
        record = BlockchainRecord(
            complaint_id=complaint_id,
            event_type=event_type,
            event_hash=event_hash_hex,
            data_hash=data_hash_hex,
            canonical_payload=payload,
            blockchain_network="Ganache",
            chain_id=settings.BLOCKCHAIN_CHAIN_ID,
            contract_address=settings.BLOCKCHAIN_CONTRACT_ADDRESS or None,
            status=STATUS_PENDING,
            created_at=now,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        # 2. Check configuration
        if not cls.is_configured():
            record.status = STATUS_NOT_CONFIGURED
            record.error_message = (
                "BLOCKCHAIN_NOT_CONFIGURED: Missing RPC URL, private key, or contract address."
            )
            db.commit()
            db.refresh(record)
            return record

        # 3. Check node availability
        available, avail_msg = cls.is_available()
        if not available:
            record.status = STATUS_FAILED
            record.error_message = f"BLOCKCHAIN_UNAVAILABLE: {avail_msg}"
            db.commit()
            db.refresh(record)
            record_audit_log(
                action="BLOCKCHAIN_ANCHOR_FAILED",
                entity_type="Complaint",
                entity_id=complaint_public_id,
                user_id=user_id,
                db=db,
                metadata={
                    "record_id": record.id,
                    "event_type": event_type,
                    "error": record.error_message,
                },
            )
            db.commit()
            return record

        # 4. Build and broadcast Web3 transaction
        try:
            w3 = cls.get_web3()
            abi = cls.load_abi()
            if not abi:
                record.status = STATUS_FAILED
                record.error_message = "CONTRACT_ABI_NOT_FOUND: CivicGuardianAudit.json is missing or invalid."
                db.commit()
                return record

            contract = w3.eth.contract(
                address=Web3.to_checksum_address(settings.BLOCKCHAIN_CONTRACT_ADDRESS),
                abi=abi,
            )

            account = w3.eth.account.from_key(settings.BLOCKCHAIN_PRIVATE_KEY)
            sender_address = account.address

            nonce = w3.eth.get_transaction_count(sender_address, "pending")
            chain_id = w3.eth.chain_id

            # Estimate gas safely
            try:
                gas_estimate = contract.functions.recordAudit(
                    data_hash_bytes,
                    event_hash_bytes,
                    event_type,
                    complaint_public_id,
                ).estimate_gas({"from": sender_address})
                gas_limit = int(gas_estimate * 1.25)
            except Exception:
                gas_limit = 350000

            tx_data = contract.functions.recordAudit(
                data_hash_bytes,
                event_hash_bytes,
                event_type,
                complaint_public_id,
            ).build_transaction({
                "from": sender_address,
                "nonce": nonce,
                "gas": gas_limit,
                "gasPrice": w3.eth.gas_price,
                "chainId": chain_id,
            })

            signed_tx = account.sign_transaction(tx_data)
            tx_hash_bytes = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hash_hex = f"0x{tx_hash_bytes.hex()}"

            record.transaction_hash = tx_hash_hex
            record.status = STATUS_SUBMITTED
            db.commit()

            # Record submission audit
            record_audit_log(
                action="BLOCKCHAIN_ANCHOR_SUBMITTED",
                entity_type="Complaint",
                entity_id=complaint_public_id,
                user_id=user_id,
                db=db,
                metadata={
                    "record_id": record.id,
                    "event_type": event_type,
                    "transaction_hash": tx_hash_hex,
                },
            )
            db.commit()

            # Wait for receipt
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash_bytes, timeout=30)
            if receipt.status == 1:
                block = w3.eth.get_block(receipt.blockNumber)
                block_ts = datetime.fromtimestamp(block.timestamp, tz=timezone.utc)

                record.status = STATUS_CONFIRMED
                record.block_number = receipt.blockNumber
                record.blockchain_timestamp = block_ts
                record.confirmed_at = datetime.now(timezone.utc)
                record.error_message = None
                db.commit()
                db.refresh(record)

                record_audit_log(
                    action="BLOCKCHAIN_ANCHOR_CONFIRMED",
                    entity_type="Complaint",
                    entity_id=complaint_public_id,
                    user_id=user_id,
                    db=db,
                    metadata={
                        "record_id": record.id,
                        "event_type": event_type,
                        "transaction_hash": tx_hash_hex,
                        "block_number": receipt.blockNumber,
                    },
                )
                db.commit()
            else:
                record.status = STATUS_FAILED
                record.error_message = "TRANSACTION_REVERTED: Smart contract reverted execution."
                db.commit()
                db.refresh(record)

                record_audit_log(
                    action="BLOCKCHAIN_ANCHOR_FAILED",
                    entity_type="Complaint",
                    entity_id=complaint_public_id,
                    user_id=user_id,
                    db=db,
                    metadata={
                        "record_id": record.id,
                        "event_type": event_type,
                        "error": record.error_message,
                    },
                )
                db.commit()

        except Exception as exc:
            # Catch all blockchain network/signing exceptions cleanly
            safe_error = str(exc)
            # Ensure private key is never leaked in error message
            if settings.BLOCKCHAIN_PRIVATE_KEY and settings.BLOCKCHAIN_PRIVATE_KEY in safe_error:
                safe_error = safe_error.replace(settings.BLOCKCHAIN_PRIVATE_KEY, "[REDACTED]")

            record.status = STATUS_FAILED
            record.error_message = f"TRANSACTION_ERROR: {safe_error}"
            db.commit()
            db.refresh(record)

            record_audit_log(
                action="BLOCKCHAIN_ANCHOR_FAILED",
                entity_type="Complaint",
                entity_id=complaint_public_id,
                user_id=user_id,
                db=db,
                metadata={
                    "record_id": record.id,
                    "event_type": event_type,
                    "error": record.error_message,
                },
            )
            db.commit()

        return record

    @classmethod
    def get_audit_record_from_chain(cls, event_hash: str) -> Optional[Dict[str, Any]]:
        """
        Query CivicGuardianAudit smart contract directly via getAudit(bytes32).
        Returns on-chain record data or None if unavailable/not found.
        """
        if not cls.is_configured():
            return None

        try:
            w3 = cls.get_web3()
            abi = cls.load_abi()
            if not abi or not w3.is_connected():
                return None

            contract = w3.eth.contract(
                address=Web3.to_checksum_address(settings.BLOCKCHAIN_CONTRACT_ADDRESS),
                abi=abi,
            )

            # Ensure event_hash is bytes32
            event_bytes = bytes.fromhex(event_hash[2:] if event_hash.startswith("0x") else event_hash)

            res = contract.functions.getAudit(event_bytes).call()
            # res: (dataHash, recordedEventHash, timestamp, eventType, complaintReference)
            return {
                "data_hash": f"0x{res[0].hex()}",
                "event_hash": f"0x{res[1].hex()}",
                "timestamp": res[2],
                "event_type": res[3],
                "complaint_reference": res[4],
            }
        except Exception:
            return None

    @classmethod
    def verify_record(cls, record_id: int, db: Session, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Comprehensive cryptographic integrity verification of a BlockchainRecord.
        1. Loads PostgreSQL record.
        2. Re-computes SHA-256 of canonical_payload; compares with stored data_hash.
        3. Queries smart contract on Ganache using event_hash.
        4. Calls verifyAudit(event_hash, data_hash) on smart contract.
        5. Returns verified=True only if all checks strictly match.
        """
        record = db.query(BlockchainRecord).filter(BlockchainRecord.id == record_id).first()
        if not record:
            return {
                "verified": False,
                "reason": f"Blockchain record #{record_id} not found in database.",
                "record_id": record_id,
            }

        # Step A: Re-compute local hash
        if not record.canonical_payload:
            return {
                "verified": False,
                "reason": "Canonical payload is missing from database record; cannot re-verify hash.",
                "record_id": record_id,
            }

        recalculated_hex, recalculated_bytes = cls.hash_payload(record.canonical_payload)
        if recalculated_hex.lower() != record.data_hash.lower():
            return {
                "verified": False,
                "reason": "TAMPERING_DETECTED: Recomputed payload hash does not match stored PostgreSQL data_hash.",
                "record_id": record_id,
                "stored_data_hash": record.data_hash,
                "recomputed_data_hash": recalculated_hex,
            }

        # Step B: Check blockchain configuration & availability
        if not cls.is_configured():
            return {
                "verified": False,
                "reason": "BLOCKCHAIN_NOT_CONFIGURED: Cannot query smart contract for on-chain verification.",
                "record_id": record_id,
                "local_hash_valid": True,
            }

        available, avail_msg = cls.is_available()
        if not available:
            return {
                "verified": False,
                "reason": f"BLOCKCHAIN_UNAVAILABLE: {avail_msg}",
                "record_id": record_id,
                "local_hash_valid": True,
            }

        # Step C: Query smart contract
        try:
            w3 = cls.get_web3()
            abi = cls.load_abi()
            contract = w3.eth.contract(
                address=Web3.to_checksum_address(settings.BLOCKCHAIN_CONTRACT_ADDRESS),
                abi=abi,
            )

            event_bytes = bytes.fromhex(record.event_hash[2:] if record.event_hash.startswith("0x") else record.event_hash)
            data_bytes = bytes.fromhex(record.data_hash[2:] if record.data_hash.startswith("0x") else record.data_hash)

            onchain_verified = contract.functions.verifyAudit(event_bytes, data_bytes).call()
            onchain_record = contract.functions.getAudit(event_bytes).call()

            onchain_data_hash = f"0x{onchain_record[0].hex()}"
            onchain_event_hash = f"0x{onchain_record[1].hex()}"
            onchain_ts = onchain_record[2]

            matches_onchain = (
                onchain_verified is True
                and onchain_data_hash.lower() == record.data_hash.lower()
                and onchain_event_hash.lower() == record.event_hash.lower()
            )

            res = {
                "verified": matches_onchain,
                "record_id": record_id,
                "complaint_id": record.complaint_id,
                "event_type": record.event_type,
                "event_hash": record.event_hash,
                "data_hash": record.data_hash,
                "transaction_hash": record.transaction_hash,
                "block_number": record.block_number,
                "onchain_verified": onchain_verified,
                "onchain_data_hash": onchain_data_hash,
                "onchain_timestamp": onchain_ts,
                "reason": (
                    "CRYPTOGRAPHICALLY_VERIFIED: Stored PostgreSQL hash matches canonical recomputation and on-chain smart contract record."
                    if matches_onchain
                    else "HASH_MISMATCH: On-chain hash does not match database record."
                ),
            }

            record_audit_log(
                action="BLOCKCHAIN_VERIFICATION_COMPLETED",
                entity_type="BlockchainRecord",
                entity_id=str(record.id),
                user_id=user_id,
                db=db,
                metadata={
                    "record_id": record.id,
                    "verified": matches_onchain,
                    "event_type": record.event_type,
                    "tx_hash": record.transaction_hash,
                },
            )
            db.commit()

            return res

        except Exception as exc:
            return {
                "verified": False,
                "reason": f"ONCHAIN_QUERY_FAILED: {str(exc)}",
                "record_id": record_id,
                "local_hash_valid": True,
            }

    @classmethod
    def retry_anchor(cls, record_id: int, db: Session, user_id: Optional[int] = None) -> BlockchainRecord:
        """
        Admin-only retry of a failed or unconfigured blockchain record.
        Reuses the EXACT same event_hash and data_hash.
        """
        record = db.query(BlockchainRecord).filter(BlockchainRecord.id == record_id).first()
        if not record:
            raise ValueError(f"Blockchain record #{record_id} not found.")

        if record.status == STATUS_CONFIRMED:
            return record  # Already confirmed, do not resubmit

        if not cls.is_configured():
            record.status = STATUS_NOT_CONFIGURED
            record.error_message = "Blockchain is not configured (missing RPC URL, contract address, or private key)."
            db.commit()
            return record

        available, msg = cls.is_available()
        if not available:
            record.status = STATUS_FAILED
            record.error_message = f"Blockchain network is unavailable: {msg}"
            db.commit()
            return record

        # Re-broadcast using stored hashes and complaint
        w3 = cls.get_web3()
        abi = cls.load_abi()
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(settings.BLOCKCHAIN_CONTRACT_ADDRESS),
            abi=abi,
        )

        account = w3.eth.account.from_key(settings.BLOCKCHAIN_PRIVATE_KEY)
        sender_address = account.address

        event_bytes = bytes.fromhex(record.event_hash[2:] if record.event_hash.startswith("0x") else record.event_hash)
        data_bytes = bytes.fromhex(record.data_hash[2:] if record.data_hash.startswith("0x") else record.data_hash)

        # Check if already anchored on chain
        try:
            if contract.functions.verifyAudit(event_bytes, data_bytes).call():
                record.status = STATUS_CONFIRMED
                record.error_message = None
                record.confirmed_at = datetime.now(timezone.utc)
                db.commit()
                return record
        except Exception:
            pass

        nonce = w3.eth.get_transaction_count(sender_address, "pending")
        chain_id = w3.eth.chain_id

        complaint_ref = record.complaint.complaint_id if record.complaint else f"CMP-{record.complaint_id}"

        tx_data = contract.functions.recordAudit(
            data_bytes,
            event_bytes,
            record.event_type,
            complaint_ref,
        ).build_transaction({
            "from": sender_address,
            "nonce": nonce,
            "gas": 350000,
            "gasPrice": w3.eth.gas_price,
            "chainId": chain_id,
        })

        signed_tx = account.sign_transaction(tx_data)
        tx_hash_bytes = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_hash_hex = f"0x{tx_hash_bytes.hex()}"

        record.transaction_hash = tx_hash_hex
        record.status = STATUS_SUBMITTED
        db.commit()

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash_bytes, timeout=30)
        if receipt.status == 1:
            block = w3.eth.get_block(receipt.blockNumber)
            record.status = STATUS_CONFIRMED
            record.block_number = receipt.blockNumber
            record.blockchain_timestamp = datetime.fromtimestamp(block.timestamp, tz=timezone.utc)
            record.confirmed_at = datetime.now(timezone.utc)
            record.error_message = None
            db.commit()

            record_audit_log(
                action="BLOCKCHAIN_ANCHOR_CONFIRMED",
                entity_type="Complaint",
                entity_id=complaint_ref,
                user_id=user_id,
                db=db,
                metadata={
                    "record_id": record.id,
                    "event_type": record.event_type,
                    "transaction_hash": tx_hash_hex,
                    "is_retry": True,
                },
            )
            db.commit()
        else:
            record.status = STATUS_FAILED
            record.error_message = "TRANSACTION_REVERTED: Retry transaction reverted on chain."
            db.commit()

        return record
