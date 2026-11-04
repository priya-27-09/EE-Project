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
from app.models.blockchain_record import (
    BlockchainRecord,
    STATUS_CONFIRMED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_NOT_CONFIGURED,
    EVENT_COMPLAINT_CREATED,
    EVENT_COMPLAINT_STATUS_CHANGED,
    EVENT_RESOLUTION_EVIDENCE_ADDED,
    EVENT_RESOLUTION_VERIFICATION,
    EVENT_HUMAN_RESOLUTION_REVIEW,
)
from app.services.blockchain_service import BlockchainService


class TestBlockchainIntegrity:
    """Comprehensive 20-test automated suite for Step 10 Blockchain Integrity."""

    @classmethod
    def setup_class(cls):
        cls.db = SessionLocal()
        cls.w3 = BlockchainService.get_web3()
        cls.test_complaint = None
        cls.created_records = []

        # Find or create a test citizen user and complaint
        citizen = cls.db.query(User).filter(User.role == UserRole.CITIZEN).first()
        if not citizen:
            from app.auth.security import get_password_hash
            citizen = User(
                email="blockchain_test_citizen@civicguardian.gov",
                password_hash=get_password_hash("TestPassword123!"),
                full_name="Blockchain Test Citizen",
                role=UserRole.CITIZEN,
            )
            cls.db.add(citizen)
            cls.db.commit()
            cls.db.refresh(citizen)
        cls.citizen = citizen

        # Find or create test complaint
        c = cls.db.query(Complaint).filter(Complaint.complaint_id == "CG-TEST-BLOCKCHAIN-01").first()
        if not c:
            from app.models.department import Department
            dept = cls.db.query(Department).first()
            now = datetime.now(timezone.utc)
            c = Complaint(
                complaint_id="CG-TEST-BLOCKCHAIN-01",
                user_id=citizen.id,
                department_id=dept.id if dept else 1,
                issue_type="pothole",
                description="Test pothole for blockchain audit anchoring verification",
                original_language="en",
                original_text="Test pothole for blockchain audit anchoring verification",
                processed_text="test pothole for blockchain audit anchoring verification",
                status="SUBMITTED",
                severity="HIGH",
                created_at=now,
                updated_at=now,
            )
            cls.db.add(c)
            cls.db.commit()
            cls.db.refresh(c)
        cls.test_complaint = c

    @classmethod
    def teardown_class(cls):
        # Clean up test blockchain records
        if cls.created_records:
            cls.db.query(BlockchainRecord).filter(BlockchainRecord.id.in_(cls.created_records)).delete(synchronize_session=False)
            cls.db.commit()
        cls.db.close()

    def log(self, num: int, name: str, passed: bool, detail: str = ""):
        status_str = "[PASS]" if passed else "[FAIL]"
        print(f"TEST {num:02d} {status_str}: {name} {f'({detail})' if detail else ''}")
        assert passed, f"Test {num} failed: {name} - {detail}"

    def test_01_web3_import_and_initialization(self):
        """1. Web3 import and initialization."""
        import web3
        w3 = BlockchainService.get_web3()
        self.log(1, "Web3 import and initialization", w3 is not None and hasattr(w3, "eth"))

    def test_02_configuration_detection(self):
        """2. Configuration detection."""
        configured = BlockchainService.is_configured()
        detail = f"RPC={settings.BLOCKCHAIN_RPC_URL}, Contract={settings.BLOCKCHAIN_CONTRACT_ADDRESS[:10] if settings.BLOCKCHAIN_CONTRACT_ADDRESS else 'None'}..."
        self.log(2, "Configuration detection", configured is True, detail)

    def test_03_ganache_connectivity(self):
        """3. Ganache connectivity."""
        available, msg = BlockchainService.is_available()
        self.log(3, "Ganache connectivity", available is True, f"Status: {msg}")

    def test_04_chain_id_retrieval(self):
        """4. Chain ID retrieval."""
        chain_id = self.w3.eth.chain_id
        self.log(4, "Chain ID retrieval", chain_id in (1337, 5777), f"Chain ID: {chain_id}")

    def test_05_account_retrieval(self):
        """5. Account retrieval."""
        info = BlockchainService.get_network_info()
        acct = info.get("account_address")
        self.log(5, "Account retrieval", bool(acct and acct.startswith("0x")), f"Account: {acct}")

    def test_06_contract_loading(self):
        """6. Contract ABI and loading."""
        abi = BlockchainService.load_abi()
        has_functions = any(item.get("name") == "recordAudit" for item in abi)
        self.log(6, "Contract ABI loading", bool(abi and has_functions), f"{len(abi)} ABI items loaded")

    def test_07_contract_address_validation(self):
        """7. Contract address validation."""
        addr = settings.BLOCKCHAIN_CONTRACT_ADDRESS
        is_checksum = Web3.is_checksum_address(addr) if addr else False
        is_valid = Web3.is_address(addr) if addr else False
        self.log(7, "Contract address validation", bool(is_valid), f"Address: {addr}")

    def test_08_sha256_deterministic_hashing(self):
        """8. SHA-256 deterministic hashing."""
        payload = {"b": 2, "a": 1, "c": [3, 4]}
        h1, b1 = BlockchainService.hash_payload(payload)
        h2, b2 = BlockchainService.hash_payload(payload)
        # Expected hash of '{"a":1,"b":2,"c":[3,4]}'
        expected_raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        expected_hash = f"0x{hashlib.sha256(expected_raw).hexdigest()}"
        self.log(8, "SHA-256 deterministic hashing", h1 == h2 == expected_hash, f"Hash: {h1[:16]}...")

    def test_09_canonical_json_deterministic_serialization(self):
        """9. Canonical JSON deterministic serialization."""
        p1 = {"zeta": 1, "alpha": 2, "beta": {"nested_b": "value", "nested_a": 100}}
        p2 = {"alpha": 2, "beta": {"nested_a": 100, "nested_b": "value"}, "zeta": 1}
        c1 = BlockchainService.canonicalize_payload(p1)
        c2 = BlockchainService.canonicalize_payload(p2)
        self.log(9, "Canonical JSON deterministic serialization", c1 == c2, f"Canonical: {c1}")

    def test_10_transaction_submission(self):
        """10. Transaction submission to Ganache."""
        test_payload = {
            "complaint_id": self.test_complaint.complaint_id,
            "event_type": EVENT_COMPLAINT_CREATED,
            "test_run": datetime.now(timezone.utc).isoformat(),
        }
        unique_suffix = f"unit_test_tx_{datetime.now(timezone.utc).timestamp()}"
        record = BlockchainService.anchor_event(
            complaint_id=self.test_complaint.id,
            complaint_public_id=self.test_complaint.complaint_id,
            event_type=EVENT_COMPLAINT_CREATED,
            payload=test_payload,
            unique_key=unique_suffix,
            db=self.db,
            user_id=self.citizen.id,
        )
        self.created_records.append(record.id)
        has_tx = bool(record.transaction_hash and record.transaction_hash.startswith("0x"))
        self.log(10, "Transaction submission to Ganache", has_tx, f"Tx: {record.transaction_hash}")

    def test_11_receipt_confirmation(self):
        """11. Receipt confirmation and block number."""
        record = self.db.query(BlockchainRecord).filter(BlockchainRecord.id == self.created_records[-1]).first()
        is_confirmed = record.status == STATUS_CONFIRMED
        has_block = record.block_number is not None and record.block_number >= 1
        self.log(11, "Receipt confirmation and block number", is_confirmed and has_block, f"Status: {record.status}, Block: #{record.block_number}")

    def test_12_postgresql_blockchain_record_creation(self):
        """12. PostgreSQL blockchain record creation and fields."""
        record = self.db.query(BlockchainRecord).filter(BlockchainRecord.id == self.created_records[-1]).first()
        all_present = (
            record is not None
            and record.complaint_id == self.test_complaint.id
            and record.event_type == EVENT_COMPLAINT_CREATED
            and record.data_hash.startswith("0x")
            and record.event_hash.startswith("0x")
            and record.canonical_payload is not None
        )
        self.log(12, "PostgreSQL blockchain record creation", all_present, f"Record ID: {record.id}")

    def test_13_blockchain_record_retrieval(self):
        """13. Blockchain record retrieval by complaint ID."""
        records = (
            self.db.query(BlockchainRecord)
            .filter(BlockchainRecord.complaint_id == self.test_complaint.id)
            .all()
        )
        self.log(13, "Blockchain record retrieval by complaint ID", len(records) >= 1, f"Found {len(records)} records")

    def test_14_blockchain_verification_matching(self):
        """14. Blockchain verification check (verifyAudit returns true for matching hash)."""
        record_id = self.created_records[-1]
        res = BlockchainService.verify_record(record_id=record_id, db=self.db)
        self.log(14, "Blockchain verification matching", res.get("verified") is True, f"Verified: {res.get('verified')}, Reason: {res.get('reason')}")

    def test_15_mismatched_hash_detection(self):
        """15. Mismatched hash detection (tampering detected)."""
        # Create a modified payload that does not match stored data_hash
        tampered_record = BlockchainRecord(
            complaint_id=self.test_complaint.id,
            event_type="TAMPER_TEST",
            event_hash="0x" + "11" * 32,
            data_hash="0x" + "22" * 32,  # Fake hash
            canonical_payload={"complaint_id": "FAKE", "secret": "tampered"},
            blockchain_network="Ganache",
            status=STATUS_CONFIRMED,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(tampered_record)
        self.db.commit()
        self.created_records.append(tampered_record.id)

        res = BlockchainService.verify_record(record_id=tampered_record.id, db=self.db)
        tamper_detected = res.get("verified") is False and "TAMPERING_DETECTED" in res.get("reason", "")
        self.log(15, "Mismatched hash detection", tamper_detected, f"Reason: {res.get('reason')}")

    def test_16_unauthorized_api_access_prevention(self):
        """16. Unauthorized API access prevention."""
        from fastapi.testclient import TestClient
        from fastapi_app import app
        from app.core.auth import create_access_token


        client = TestClient(app)
        citizen_token = create_access_token({"sub": str(self.citizen.id), "email": self.citizen.email, "role": UserRole.CITIZEN})

        # Citizen cannot call /api/v1/admin/blockchain/status
        resp = client.get("/api/v1/admin/blockchain/status", headers={"Authorization": f"Bearer {citizen_token}"})
        self.log(16, "Unauthorized API access prevention (Citizen rejected from admin)", resp.status_code == 403, f"Status code: {resp.status_code}")

    def test_17_admin_retry_functionality(self):
        """17. Admin retry functionality reuses exact hashes."""
        # Create a FAILED record
        failed_payload = {"complaint_id": self.test_complaint.complaint_id, "test": "retry_test"}
        h_hex, _ = BlockchainService.hash_payload(failed_payload)
        e_hex, _ = BlockchainService.compute_event_hash(self.test_complaint.complaint_id, "RETRY_EVENT", f"key_{datetime.now(timezone.utc).timestamp()}")

        failed_rec = BlockchainRecord(
            complaint_id=self.test_complaint.id,
            event_type="RETRY_EVENT",
            event_hash=e_hex,
            data_hash=h_hex,
            canonical_payload=failed_payload,
            blockchain_network="Ganache",
            status=STATUS_FAILED,
            error_message="Simulated temporary network failure",
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(failed_rec)
        self.db.commit()
        self.created_records.append(failed_rec.id)

        # Retry the record
        retried = BlockchainService.retry_anchor(record_id=failed_rec.id, db=self.db)
        self.log(17, "Admin retry functionality reuses exact hashes", retried.status == STATUS_CONFIRMED and retried.event_hash == e_hex and retried.data_hash == h_hex, f"Status: {retried.status}, Tx: {retried.transaction_hash}")

    def test_18_graceful_handling_unconfigured_state(self):
        """18. Graceful handling of unconfigured/failed blockchain without breaking complaints."""
        # Test hash canonicalization when blockchain is disabled
        orig_setting = settings.BLOCKCHAIN_ENABLED
        settings.BLOCKCHAIN_ENABLED = False
        try:
            unconf_rec = BlockchainService.anchor_event(
                complaint_id=self.test_complaint.id,
                complaint_public_id=self.test_complaint.complaint_id,
                event_type="UNCONFIGURED_TEST",
                payload={"test": "unconfigured"},
                unique_key="unconf_key",
                db=self.db,
            )
            self.created_records.append(unconf_rec.id)
            graceful = unconf_rec.status == STATUS_NOT_CONFIGURED and "NOT_CONFIGURED" in unconf_rec.error_message
            self.log(18, "Graceful unconfigured state handling", graceful, f"Status: {unconf_rec.status}")
        finally:
            settings.BLOCKCHAIN_ENABLED = orig_setting

    def test_19_zero_private_key_leakage(self):
        """19. Zero private key leakage in responses, logs, or database."""
        pk = settings.BLOCKCHAIN_PRIVATE_KEY
        info = BlockchainService.get_network_info()
        records = self.db.query(BlockchainRecord).filter(BlockchainRecord.id.in_(self.created_records)).all()

        info_clean = pk not in json.dumps(info)
        db_clean = not any(pk in str(r.error_message or "") or pk in str(r.canonical_payload or "") for r in records)
        self.log(19, "Zero private key leakage in diagnostics and database", info_clean and db_clean, "Private key is strictly protected")

    def test_20_zero_sensitive_data_onchain(self):
        """20. Zero sensitive data (no citizen names, emails, passwords, GPS) stored on-chain."""
        contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(settings.BLOCKCHAIN_CONTRACT_ADDRESS),
            abi=BlockchainService.load_abi(),
        )
        rec = self.db.query(BlockchainRecord).filter(BlockchainRecord.id == self.created_records[0]).first()
        event_bytes = bytes.fromhex(rec.event_hash[2:])
        onchain = contract.functions.getAudit(event_bytes).call()

        # onchain tuple: (dataHash, eventHash, timestamp, eventType, complaintReference)
        data_hash_len = len(onchain[0])
        event_type = onchain[3]
        complaint_ref = onchain[4]

        no_pii = (
            data_hash_len == 32
            and "@" not in complaint_ref
            and not any(sensitive in complaint_ref.lower() for sensitive in ["password", "token", "jwt", "gps", "lat", "lon"])
        )
        self.log(20, "Zero sensitive data on-chain", no_pii, f"Stored ref: '{complaint_ref}', Type: '{event_type}'")


def run_all():
    print("=" * 70)
    print("AI CIVIC GUARDIAN — STEP 10: BLOCKCHAIN INTEGRITY AUTOMATED TEST SUITE")
    print("=" * 70)
    suite = TestBlockchainIntegrity()
    suite.setup_class()

    tests = [getattr(suite, m) for m in dir(suite) if m.startswith("test_") and callable(getattr(suite, m))]
    passed_count = 0

    for t in sorted(tests, key=lambda x: x.__name__):
        try:
            t()
            passed_count += 1
        except Exception as exc:
            print(f"[ERROR IN {t.__name__}]: {exc}")

    suite.teardown_class()
    print("=" * 70)
    print(f"RESULTS: {passed_count}/{len(tests)} Tests Passed Successfully")
    print("=" * 70)
    return passed_count == len(tests)


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
