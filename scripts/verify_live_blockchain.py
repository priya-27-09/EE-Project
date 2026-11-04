import os
import sys
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

from web3 import Web3

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.complaint import Complaint
from app.models.blockchain_record import BlockchainRecord, STATUS_CONFIRMED
from app.services.blockchain_service import BlockchainService


def verify_live_blockchain():
    print("=" * 70)
    print("AI CIVIC GUARDIAN — LIVE GANACHE BLOCKCHAIN VERIFICATION")
    print("=" * 70)

    db = SessionLocal()
    try:
        # 1. Check Ganache RPC
        print("\n[STEP 1] Checking Ganache RPC...")
        rpc_url = settings.BLOCKCHAIN_RPC_URL or "http://127.0.0.1:7545"
        w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 10}))
        assert w3.is_connected(), f"Failed to connect to Ganache RPC at {rpc_url}"
        print(f" -> Connected to Ganache at: {rpc_url}")

        # 2. Get Chain ID
        print("\n[STEP 2] Retrieving Chain ID...")
        chain_id = w3.eth.chain_id
        print(f" -> Chain ID: {chain_id}")
        assert chain_id in (1337, 5777), f"Unexpected chain ID: {chain_id}"

        # 3. Get Configured Account
        print("\n[STEP 3] Loading Configured Account...")
        acct_addr = settings.BLOCKCHAIN_ACCOUNT_ADDRESS
        if not acct_addr and settings.BLOCKCHAIN_PRIVATE_KEY:
            acct_addr = w3.eth.account.from_key(settings.BLOCKCHAIN_PRIVATE_KEY).address
        print(f" -> Writer Account Address: {acct_addr}")
        assert acct_addr and Web3.is_address(acct_addr), f"Invalid account address: {acct_addr}"

        # 4. Check Account Balance
        print("\n[STEP 4] Checking Account Balance...")
        balance_wei = w3.eth.get_balance(acct_addr)
        balance_eth = w3.from_wei(balance_wei, "ether")
        print(f" -> Balance: {balance_eth} ETH")
        assert balance_eth > 0, "Account has 0 ETH balance"

        # 5. Contract Address & Deployment Check
        print("\n[STEP 5 & 6] Checking Smart Contract Deployment...")
        contract_addr = settings.BLOCKCHAIN_CONTRACT_ADDRESS
        print(f" -> Contract Address: {contract_addr}")
        assert contract_addr and Web3.is_address(contract_addr), "No contract address configured"

        # 7. Connect Contract Instance
        print("\n[STEP 7] Loading Contract ABI and Instance...")
        abi = BlockchainService.load_abi()
        assert abi, "CivicGuardianAudit.json ABI is empty or missing"
        contract = w3.eth.contract(address=Web3.to_checksum_address(contract_addr), abi=abi)
        owner = contract.functions.owner().call()
        authorized_writer = contract.functions.authorizedWriter().call()
        print(f" -> Contract Owner: {owner}")
        print(f" -> Contract Authorized Writer: {authorized_writer}")

        # 8. Create Deterministic Test Payload
        print("\n[STEP 8] Creating Deterministic Payload...")
        now_iso = datetime.now(timezone.utc).isoformat()
        test_payload = {
            "complaint_id": "CG-LIVE-VERIFY-001",
            "event_type": "COMPLAINT_CREATED",
            "issue_type": "damaged_road",
            "timestamp": now_iso,
        }
        canonical_str = BlockchainService.canonicalize_payload(test_payload)
        print(f" -> Canonical Payload: {canonical_str}")

        # 9. Calculate SHA-256
        print("\n[STEP 9] Calculating SHA-256 Hashes...")
        data_hash_hex, data_hash_bytes = BlockchainService.hash_payload(test_payload)
        event_hash_hex, event_hash_bytes = BlockchainService.compute_event_hash(
            complaint_reference="CG-LIVE-VERIFY-001",
            event_type="COMPLAINT_CREATED",
            unique_key=f"live_test_{now_iso}",
        )
        print(f" -> Data Hash:  {data_hash_hex}")
        print(f" -> Event Hash: {event_hash_hex}")

        # 10. Submit Real Transaction
        print("\n[STEP 10 & 11] Broadcasting Signed Raw Transaction to Ganache...")
        account = w3.eth.account.from_key(settings.BLOCKCHAIN_PRIVATE_KEY)
        nonce = w3.eth.get_transaction_count(account.address, "pending")

        tx = contract.functions.recordAudit(
            data_hash_bytes,
            event_hash_bytes,
            "COMPLAINT_CREATED",
            "CG-LIVE-VERIFY-001",
        ).build_transaction({
            "from": account.address,
            "nonce": nonce,
            "gas": 300000,
            "gasPrice": w3.eth.gas_price,
            "chainId": chain_id,
        })

        signed_tx = account.sign_transaction(tx)
        tx_hash_bytes = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_hash_hex = f"0x{tx_hash_bytes.hex()}"
        print(f" -> Transaction Broadcast! Tx Hash: {tx_hash_hex}")

        # 12. Read Transaction Receipt
        print("\n[STEP 12] Awaiting Receipt Confirmation...")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash_bytes, timeout=30)
        assert receipt.status == 1, "Transaction reverted on Ganache"
        print(f" -> [RECEIPT CONFIRMED] Block Number: #{receipt.blockNumber}, Gas Used: {receipt.gasUsed}")

        # 13 & 14. Read Smart Contract Record
        print("\n[STEP 13 & 14] Querying Contract On-Chain State...")
        onchain_rec = contract.functions.getAudit(event_hash_bytes).call()
        onchain_data_hash = f"0x{onchain_rec[0].hex()}"
        onchain_event_hash = f"0x{onchain_rec[1].hex()}"
        onchain_ts = onchain_rec[2]
        onchain_type = onchain_rec[3]
        onchain_ref = onchain_rec[4]

        print(f" -> On-Chain Data Hash:  {onchain_data_hash}")
        print(f" -> On-Chain Event Hash: {onchain_event_hash}")
        print(f" -> On-Chain Timestamp:  {onchain_ts}")
        print(f" -> On-Chain Event Type: {onchain_type}")
        print(f" -> On-Chain Reference:  {onchain_ref}")

        assert onchain_data_hash.lower() == data_hash_hex.lower(), "Data hash mismatch on-chain"
        assert onchain_event_hash.lower() == event_hash_hex.lower(), "Event hash mismatch on-chain"

        # 15. Verify Mismatched Hash Returns False
        print("\n[STEP 15] Verifying Mismatched Hash Returns False...")
        fake_data_bytes = bytes.fromhex("11" * 32)
        match_true = contract.functions.verifyAudit(event_hash_bytes, data_hash_bytes).call()
        match_false = contract.functions.verifyAudit(event_hash_bytes, fake_data_bytes).call()
        print(f" -> verifyAudit(matching):   {match_true}")
        print(f" -> verifyAudit(mismatched): {match_false}")
        assert match_true is True, "verifyAudit matching failed"
        assert match_false is False, "verifyAudit mismatched returned true"

        # 16. Store Record in PostgreSQL
        print("\n[STEP 16] Persisting BlockchainRecord in PostgreSQL 17...")
        # Find or create reference complaint
        c = db.query(Complaint).first()
        assert c, "No complaints found in database"

        pg_record = BlockchainRecord(
            complaint_id=c.id,
            event_type="COMPLAINT_CREATED",
            event_hash=event_hash_hex,
            data_hash=data_hash_hex,
            canonical_payload=test_payload,
            blockchain_network="Ganache",
            chain_id=chain_id,
            contract_address=contract_addr,
            transaction_hash=tx_hash_hex,
            block_number=receipt.blockNumber,
            blockchain_timestamp=datetime.fromtimestamp(onchain_ts, tz=timezone.utc),
            status=STATUS_CONFIRMED,
            created_at=datetime.now(timezone.utc),
            confirmed_at=datetime.now(timezone.utc),
        )
        db.add(pg_record)
        db.commit()
        db.refresh(pg_record)
        print(f" -> Stored in PostgreSQL with ID: #{pg_record.id}")

        # 17 & 18. Query PostgreSQL and Verify Hash Equality
        print("\n[STEP 17 & 18] Querying PostgreSQL & Running Cryptographic Verification...")
        queried = db.query(BlockchainRecord).filter(BlockchainRecord.id == pg_record.id).first()
        assert queried.data_hash.lower() == onchain_data_hash.lower(), "PostgreSQL hash != on-chain hash"
        verif_result = BlockchainService.verify_record(record_id=pg_record.id, db=db)
        print(f" -> Cryptographic Verification Result: {verif_result['verified']}")
        print(f" -> Reason: {verif_result['reason']}")
        assert verif_result["verified"] is True, "Cryptographic verification failed"

        # 19, 20, 21. Summary Print
        print("\n" + "=" * 70)
        print("LIVE BLOCKCHAIN TRANSACTION DETAILS:")
        print(f"Transaction Hash: {tx_hash_hex}")
        print(f"Block Number:     #{receipt.blockNumber}")
        print(f"Contract Address: {contract_addr}")
        print(f"Gas Used:         {receipt.gasUsed}")
        print(f"PostgreSQL ID:    #{pg_record.id}")
        print("=" * 70)

        # 22. Clean up test record
        db.delete(pg_record)
        db.commit()
        print("\n[STEP 22] Test records cleaned up successfully.")

        print("\n>>> LIVE GANACHE BLOCKCHAIN VERIFICATION COMPLETED: 100% SUCCESS <<<")
        return True

    finally:
        db.close()


if __name__ == "__main__":
    ok = verify_live_blockchain()
    sys.exit(0 if ok else 1)
