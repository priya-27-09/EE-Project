import sys
import hashlib
from pathlib import Path
from datetime import datetime, timezone

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models import (
    User,
    Department,
    Complaint,
    AIPrediction,
    ComplaintEvidence,
    ComplaintStatusHistory,
    DuplicateAnalysis,
    AuditLog,
)


def test_full_model_lifecycle():
    db = SessionLocal()
    try:
        print("[*] Testing full model CRUD and relational constraints...")

        # 1. Create User
        test_email = f"citizen_test_{int(datetime.now(timezone.utc).timestamp())}@example.com"
        user = User(
            name="Priya Sharma",
            email=test_email,
            password_hash="$2b$12$e9XQyF/dummyhashedpasswordstringforverification",
            role="citizen",
            preferred_language="en",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"[OK] Created User: id={user.id}, email={user.email}")

        # 2. Get Department
        dept = db.query(Department).filter(Department.name == "Roads & Highways").first()
        assert dept is not None, "Department not found!"
        print(f"[OK] Fetched Department: id={dept.id}, name={dept.name}")

        # 3. Create Complaint
        cid = f"CMP-{int(datetime.now(timezone.utc).timestamp())}"
        complaint = Complaint(
            complaint_id=cid,
            user_id=user.id,
            department_id=dept.id,
            issue_type="Severe Pothole on Main Road",
            description="Large pothole near junction causing traffic congestion and hazard.",
            original_language="en",
            processed_text="Large pothole near junction causing traffic congestion and hazard.",
            latitude=12.9715987,
            longitude=77.5945627,
            severity="HIGH",
            severity_score=0.88,
            ai_confidence=0.94,
            status="SUBMITTED",
        )
        db.add(complaint)
        db.commit()
        db.refresh(complaint)
        print(f"[OK] Created Complaint: id={complaint.id}, complaint_id={complaint.complaint_id}")

        # 4. Create AI Prediction with JSONB bounding boxes
        prediction = AIPrediction(
            complaint_id=complaint.id,
            model_version="yolov8x-pothole-v1.2",
            detected_class="pothole",
            confidence=0.945,
            bounding_boxes=[
                {"x_min": 120, "y_min": 240, "x_max": 450, "y_max": 510, "label": "pothole", "score": 0.945}
            ],
        )
        db.add(prediction)

        # 5. Create Evidence (secure file path and sha256 hash - NO binary blob)
        sample_path = "storage/secure/evidences/2026/09/22/pothole_evidence_001.jpg"
        sample_hash = hashlib.sha256(b"simulated_image_bytes_for_integrity").hexdigest()
        evidence = ComplaintEvidence(
            complaint_id=complaint.id,
            file_path=sample_path,
            file_type="image/jpeg",
            sha256_hash=sample_hash,
            uploaded_by=user.id,
        )
        db.add(evidence)

        # 6. Create Status History
        history = ComplaintStatusHistory(
            complaint_id=complaint.id,
            old_status=None,
            new_status="SUBMITTED",
            changed_by=user.id,
            remarks="Complaint logged by citizen with initial photo evidence.",
        )
        db.add(history)

        # 7. Create Duplicate Analysis entry (linking to self/reference for test)
        dup = DuplicateAnalysis(
            complaint_id=complaint.id,
            possible_duplicate_id=complaint.id,
            similarity_score=1.0,
        )
        db.add(dup)

        # 8. Create Audit Log
        audit = AuditLog(
            user_id=user.id,
            action="COMPLAINT_CREATED",
            entity_type="Complaint",
            entity_id=str(complaint.id),
            metadata_={"complaint_id": complaint.complaint_id, "channel": "web"},
        )
        db.add(audit)

        db.commit()
        print("[OK] All related entities (AIPrediction, Evidence, StatusHistory, DuplicateAnalysis, AuditLog) saved successfully.")

        # Verify queries and relationships
        db.refresh(complaint)
        assert len(complaint.ai_predictions) == 1
        assert len(complaint.evidences) == 1
        assert complaint.evidences[0].sha256_hash == sample_hash
        assert len(complaint.status_history) == 1
        print("[OK] Relationship traversal and data integrity verified successfully.")

        # Clean up test complaint and test user
        db.delete(complaint)
        db.delete(user)
        db.commit()
        print("[OK] Cascading cleanup test passed successfully.")

    except Exception as e:
        db.rollback()
        print(f"[-] Model lifecycle test failed: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    test_full_model_lifecycle()
