import re
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.complaint import Complaint


def generate_complaint_id(db: Session) -> str:
    """
    Generate a unique, human-readable complaint identifier in the format:
    CG-YYYY-XXXXXX (e.g., CG-2026-000001).
    Queries the database for the highest sequence number in the current year.
    """
    current_year = datetime.now(timezone.utc).year
    prefix = f"CG-{current_year}-"

    # Query all complaint IDs for current year
    complaints = (
        db.query(Complaint.complaint_id)
        .filter(Complaint.complaint_id.like(f"{prefix}%"))
        .all()
    )

    max_seq = 0
    pattern = re.compile(rf"^CG-{current_year}-(\d+)$")
    for (cid,) in complaints:
        m = pattern.match(cid or "")
        if m:
            try:
                seq = int(m.group(1))
                # Only consider standard sequences (ignore large unix timestamps)
                if seq < 1_000_000_000 and seq > max_seq:
                    max_seq = seq
            except ValueError:
                pass

    next_seq = max_seq + 1

    # Guarantee collision prevention
    while True:
        candidate = f"{prefix}{next_seq:06d}"
        exists = db.query(Complaint.id).filter(Complaint.complaint_id == candidate).first()
        if not exists:
            return candidate
        next_seq += 1

