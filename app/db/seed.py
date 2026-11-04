import sys
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.department import Department

# Exactly 12 core civic departments requested for AI Civic Guardian
DEPARTMENTS: List[Dict[str, Any]] = [
    {
        "name": "Public Health & Sanitation",
        "description": "Vector-borne disease control, sanitization, public toilets, and prevention of water stagnation.",
        "active": True,
    },
    {
        "name": "Urban Planning & Municipal Services",
        "description": "City zoning, encroachment prevention, municipal property services, and civic infrastructure planning.",
        "active": True,
    },
    {
        "name": "Water Supply & Sewerage",
        "description": "Potable drinking water supply, pipeline leakages, water contamination, and sewage system maintenance.",
        "active": True,
    },
    {
        "name": "Roads & Highways",
        "description": "Maintenance of highways, city arterial roads, pothole repairs, bridges, and pedestrian walkways.",
        "active": True,
    },
    {
        "name": "Electricity & Street Lighting",
        "description": "Streetlights, high-mast illumination, exposed cables, transformer safety, and civic electrical fixtures.",
        "active": True,
    },
    {
        "name": "Solid Waste Management",
        "description": "Garbage collection, street sweeping, municipal waste processing, and elimination of open dumping spots.",
        "active": True,
    },
    {
        "name": "Parks & Public Spaces",
        "description": "Maintenance of civic gardens, community parks, urban forestry, playground safety, and tree pruning.",
        "active": True,
    },
    {
        "name": "Traffic & Transportation",
        "description": "Traffic signals, road signage, public transit infrastructure, speed calming, and parking enforcement.",
        "active": True,
    },
    {
        "name": "Environmental Protection",
        "description": "Air quality monitoring, industrial effluent control, open waste burning prevention, and noise regulation.",
        "active": True,
    },
    {
        "name": "Building & Construction",
        "description": "Structural safety compliance, illegal building construction, demolition hazards, and permit enforcement.",
        "active": True,
    },
    {
        "name": "Public Safety",
        "description": "Emergency hazard mitigation, open manholes, disaster response coordination, and civic physical safety.",
        "active": True,
    },
    {
        "name": "Drainage & Flood Management",
        "description": "Stormwater drain desilting, monsoon waterlogging mitigation, canal clearing, and floodwater diversion.",
        "active": True,
    },
]


def seed_departments(db: Session = None) -> List[Department]:
    """
    Seed the database with all 12 core civic departments for AI Civic Guardian.
    Idempotent operation: creates missing departments or updates existing active status.
    Ensures exactly the 12 required departments exist without duplicates.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        print(f"[*] Seeding {len(DEPARTMENTS)} municipal departments for AI Civic Guardian...")
        seeded_records = []
        created_count = 0
        updated_count = 0

        for dept_data in DEPARTMENTS:
            dept = db.query(Department).filter(Department.name == dept_data["name"]).first()
            if not dept:
                dept = Department(
                    name=dept_data["name"],
                    description=dept_data["description"],
                    active=dept_data["active"],
                )
                db.add(dept)
                created_count += 1
            else:
                dept.description = dept_data["description"]
                dept.active = dept_data["active"]
                updated_count += 1
            seeded_records.append(dept)

        db.commit()

        print(f"[+] Seeding complete! Created: {created_count}, Updated/Existing: {updated_count}")
        print("\n" + "=" * 80)
        print(f"{'ID':<4} | {'Department Name':<38} | {'Active':<7} | {'Description'[:25]}")
        print("-" * 80)
        
        all_depts = db.query(Department).order_by(Department.id).all()
        for d in all_depts:
            desc_preview = (d.description[:25] + "...") if d.description and len(d.description) > 25 else (d.description or "")
            print(f"{d.id:<4} | {d.name:<38} | {str(d.active):<7} | {desc_preview}")
        print("=" * 80 + "\n")

        return all_depts
    except Exception as e:
        db.rollback()
        print(f"[-] Error seeding departments: {e}", file=sys.stderr)
        raise
    finally:
        if close_db:
            db.close()


if __name__ == "__main__":
    seed_departments()
