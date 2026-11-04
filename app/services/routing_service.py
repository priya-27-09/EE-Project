"""
AI Civic Guardian — Centralized Category-to-Department Routing Service

Single centralized routing authority mapping all 12 canonical civic issues to
responsible municipal departments in PostgreSQL.

Supports:
- Canonical Class IDs (0 to 11, int or string)
- Canonical Class Names (e.g., 'Pothole', 'Garbage Overflow', 'Park/Public Space Damage')
- Canonical Internal Issue Keys (e.g., 'pothole', 'garbage_overflow', 'park_damage')

Strict Guarantees:
- Never assigns a department based only on AI confidence.
- Requires a valid canonical category; missing or invalid categories are rejected safely.
- Dynamically resolves and persists the Department ORM record in PostgreSQL.
"""

from typing import Dict, Any, Optional, Union, Tuple, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.department import Department
from app.complaints.constants import (
    ISSUE_GARBAGE_OVERFLOW,
    ISSUE_ILLEGAL_DUMPING,
    ISSUE_POTHOLE,
    ISSUE_DAMAGED_ROAD,
    ISSUE_WATER_LEAKAGE,
    ISSUE_SEWAGE_OVERFLOW,
    ISSUE_BROKEN_STREET_LIGHT,
    ISSUE_DRAINAGE_PROBLEM,
    ISSUE_TRAFFIC_ISSUE,
    ISSUE_BUILDING_DAMAGE,
    ISSUE_PARK_DAMAGE,
    ISSUE_ENVIRONMENTAL_POLLUTION,
    VALID_ISSUE_TYPES,
)

# Centralized Canonical Routing Table for all 12 civic categories
CANONICAL_ROUTING_TABLE: Dict[int, Dict[str, Any]] = {
    0: {
        "class_id": 0,
        "class_name": "Garbage Overflow",
        "issue_type": ISSUE_GARBAGE_OVERFLOW,
        "department_name": "Solid Waste Management",
        "department_id": 6,
    },
    1: {
        "class_id": 1,
        "class_name": "Illegal Dumping",
        "issue_type": ISSUE_ILLEGAL_DUMPING,
        "department_name": "Solid Waste Management",
        "department_id": 6,
    },
    2: {
        "class_id": 2,
        "class_name": "Pothole",
        "issue_type": ISSUE_POTHOLE,
        "department_name": "Roads & Highways",
        "department_id": 4,
    },
    3: {
        "class_id": 3,
        "class_name": "Damaged Road",
        "issue_type": ISSUE_DAMAGED_ROAD,
        "department_name": "Roads & Highways",
        "department_id": 4,
    },
    4: {
        "class_id": 4,
        "class_name": "Water Leakage",
        "issue_type": ISSUE_WATER_LEAKAGE,
        "department_name": "Water Supply & Sewerage",
        "department_id": 3,
    },
    5: {
        "class_id": 5,
        "class_name": "Sewage Overflow",
        "issue_type": ISSUE_SEWAGE_OVERFLOW,
        "department_name": "Water Supply & Sewerage",
        "department_id": 3,
    },
    6: {
        "class_id": 6,
        "class_name": "Broken Street Light",
        "issue_type": ISSUE_BROKEN_STREET_LIGHT,
        "department_name": "Electricity & Street Lighting",
        "department_id": 5,
    },
    7: {
        "class_id": 7,
        "class_name": "Drainage Problem",
        "issue_type": ISSUE_DRAINAGE_PROBLEM,
        "department_name": "Drainage & Flood Management",
        "department_id": 12,
    },
    8: {
        "class_id": 8,
        "class_name": "Traffic Issue",
        "issue_type": ISSUE_TRAFFIC_ISSUE,
        "department_name": "Traffic & Transportation",
        "department_id": 8,
    },
    9: {
        "class_id": 9,
        "class_name": "Building Damage",
        "issue_type": ISSUE_BUILDING_DAMAGE,
        "department_name": "Building & Construction",
        "department_id": 10,
    },
    10: {
        "class_id": 10,
        "class_name": "Park/Public Space Damage",
        "issue_type": ISSUE_PARK_DAMAGE,
        "department_name": "Parks & Public Spaces",
        "department_id": 7,
    },
    11: {
        "class_id": 11,
        "class_name": "Environmental Pollution",
        "issue_type": ISSUE_ENVIRONMENTAL_POLLUTION,
        "department_name": "Environmental Protection",
        "department_id": 9,
    },
}

# Backward-compatible dictionaries
ISSUE_TO_DEPARTMENT_NAME_MAP: Dict[str, str] = {
    v["issue_type"]: v["department_name"] for v in CANONICAL_ROUTING_TABLE.values()
}

CLASS_ID_TO_DEPARTMENT_NAME_MAP: Dict[int, str] = {
    v["class_id"]: v["department_name"] for v in CANONICAL_ROUTING_TABLE.values()
}

CLASS_NAME_TO_DEPARTMENT_NAME_MAP: Dict[str, str] = {
    v["class_name"]: v["department_name"] for v in CANONICAL_ROUTING_TABLE.values()
}

# Additional lookup aliases for robust parsing
_NORMALIZED_LOOKUP: Dict[str, int] = {}
for cid, info in CANONICAL_ROUTING_TABLE.items():
    _NORMALIZED_LOOKUP[str(cid)] = cid
    _NORMALIZED_LOOKUP[info["issue_type"].lower()] = cid
    _NORMALIZED_LOOKUP[info["class_name"].lower()] = cid
    # Normalized versions stripping punctuation/whitespace
    _NORMALIZED_LOOKUP[info["class_name"].lower().replace("/", " ").replace("-", " ").strip()] = cid
    _NORMALIZED_LOOKUP[info["class_name"].lower().replace("/", "").replace("-", "").strip()] = cid

# Extra specific aliases
_NORMALIZED_LOOKUP["park damage"] = 10
_NORMALIZED_LOOKUP["park / public space"] = 10
_NORMALIZED_LOOKUP["park/public space"] = 10
_NORMALIZED_LOOKUP["park_damage"] = 10


def resolve_canonical_issue(category: Any) -> Tuple[int, str, str, str]:
    """
    Resolve any valid category representation into its canonical tuple:
    (class_id, class_name, issue_type_key, department_name)

    Raises ValueError if category is missing or invalid.
    """
    if category is None:
        raise ValueError("Category is required and cannot be missing or empty.")

    # Integer class ID check (0 - 11)
    if isinstance(category, int):
        if category in CANONICAL_ROUTING_TABLE:
            entry = CANONICAL_ROUTING_TABLE[category]
            return entry["class_id"], entry["class_name"], entry["issue_type"], entry["department_name"]
        raise ValueError(
            f"Invalid canonical class ID '{category}'. Must be an integer between 0 and 11."
        )

    # String normalization
    clean_str = str(category).strip().lower()
    if not clean_str:
        raise ValueError("Category is required and cannot be missing or empty.")

    # Try numeric string (e.g. '2')
    if clean_str.isdigit():
        cid = int(clean_str)
        if cid in CANONICAL_ROUTING_TABLE:
            entry = CANONICAL_ROUTING_TABLE[cid]
            return entry["class_id"], entry["class_name"], entry["issue_type"], entry["department_name"]
        raise ValueError(
            f"Invalid canonical class ID '{category}'. Must be an integer between 0 and 11."
        )

    # Try direct key lookup
    if clean_str in _NORMALIZED_LOOKUP:
        cid = _NORMALIZED_LOOKUP[clean_str]
        entry = CANONICAL_ROUTING_TABLE[cid]
        return entry["class_id"], entry["class_name"], entry["issue_type"], entry["department_name"]

    # Normalized alias lookup
    norm_attempt = clean_str.replace("/", " ").replace("-", " ").replace("_", " ").strip()
    if norm_attempt in _NORMALIZED_LOOKUP:
        cid = _NORMALIZED_LOOKUP[norm_attempt]
        entry = CANONICAL_ROUTING_TABLE[cid]
        return entry["class_id"], entry["class_name"], entry["issue_type"], entry["department_name"]

    raise ValueError(
        f"Invalid issue_type '{category}'. Must be one of: {sorted(list(VALID_ISSUE_TYPES))} or canonical class IDs 0-11."
    )


def route_issue_to_department(
    category: Any = None,
    db: Optional[Session] = None,
    *,
    issue_type: Optional[str] = None,
    issue_class: Optional[int] = None,
) -> Department:
    """
    Deterministically route any canonical civic issue (class ID, name, or key)
    to its responsible Department record in PostgreSQL.

    Guarantees:
    - Never routes based only on AI confidence.
    - If category is missing or invalid, raises HTTPException(400) with clear detail.
    - Queries the live PostgreSQL departments table dynamically by name.
    """
    raw_cat = category
    if raw_cat is None and issue_type is not None:
        raw_cat = issue_type
    if raw_cat is None and issue_class is not None:
        raw_cat = issue_class

    if raw_cat is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category is required for department routing and cannot be missing or empty.",
        )

    try:
        class_id, class_name, issue_key, dept_name = resolve_canonical_issue(raw_cat)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    # If db session is not passed, create a temporary session
    close_db = False
    if db is None:
        from app.db.session import SessionLocal
        db = SessionLocal()
        close_db = True

    try:
        department = (
            db.query(Department)
            .filter(Department.name == dept_name, Department.active.is_(True))
            .first()
        )

        # Fallback to department_id if name query didn't match
        if not department:
            target_id = CANONICAL_ROUTING_TABLE[class_id]["department_id"]
            department = (
                db.query(Department)
                .filter(Department.id == target_id, Department.active.is_(True))
                .first()
            )

        if not department:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Target department '{dept_name}' not found or is currently inactive in the database.",
            )

        return department
    finally:
        if close_db and db is not None:
            db.close()


# ==============================================================================
# Centralized Description-Based Classification Service (English, Tamil, Tanglish)
# ==============================================================================

import re

ISSUE_KEYWORDS: Dict[str, Dict[str, Any]] = {
    ISSUE_GARBAGE_OVERFLOW: {
        "phrases": [
            "garbage overflow", "garbage overflowing", "waste overflow", "overflowing trash",
            "overflowing bin", "dustbin overflowing", "garbage heap", "trash pile",
            "waste dump", "garbage not cleared", "rubbish accumulation", "waste bin overflow",
            "kuppai thotti", "kuppai erukkudhu", "garbage bin", "trash can full", "garbage pile"
        ],
        "strong": ["garbage", "trash", "rubbish", "dustbin", "kuppai", "kuppa", "dumpster", "wastebin"],
        "tamil": ["குப்பை", "குப்பைத்தொட்டி", "கழிவு", "குப்பைக் கூளம்"],
        "secondary": ["waste", "smell", "rotten", "stench", "litter", "clearing"],
    },
    ISSUE_ILLEGAL_DUMPING: {
        "phrases": [
            "illegal dumping", "unauthorized dumping", "debris dumped", "construction waste",
            "construction debris", "debris dumping", "waste thrown on road", "dumped waste",
            "dumping debris", "building debris", "roadside dumping", "commercial dumping",
            "unauthorized garbage disposal", "dumping rubbish", "dumped illegally", "illegally dumped",
            "waste dumped", "dumping waste"
        ],
        "strong": ["debris", "dumping", "dumped", "unauthorized", "rubble", "discarded"],
        "tamil": ["கட்டிட கழிவு", "குப்பை கொட்டுதல்", "கொட்டப்படுகிறது", "முறையற்ற குப்பை"],
        "secondary": ["construction", "bricks", "cement", "unlawful", "roadside", "truck"],
    },
    ISSUE_POTHOLE: {
        "phrases": [
            "deep pothole", "pothole on road", "road pothole", "large pothole", "dangerous pothole",
            "crater on road", "pit on road", "tar road hole", "kuzhi on road", "potholes everywhere",
            "big pothole", "huge pothole", "road pit", "pothole causing accident"
        ],
        "strong": ["pothole", "potholes", "crater", "craters", "roadpit", "kuzhi", "kuli", "pallam"],
        "tamil": ["குழி", "பள்ளம்", "ரோடு குழி", "சாலை குழி"],
        "secondary": ["hole", "cavity", "cratered", "two-wheeler", "bike skid", "road crater"],
    },
    ISSUE_DAMAGED_ROAD: {
        "phrases": [
            "damaged road", "broken road", "road damaged", "uneven road", "cracked road",
            "tar road broken", "asphalt cracked", "road collapsed", "bad road condition",
            "salai sedham", "broken pavement", "road eroded", "road worn out", "pavement damaged"
        ],
        "strong": ["salai", "saalai", "sedham", "tar road", "uneven road", "pavement crack", "asphalt damage"],
        "tamil": ["சேதமடைந்த சாலை", "சாலை சேதம்", "சாலை உடைவு", "சாலை"],
        "secondary": ["road", "asphalt", "pavement", "bumpy", "erosion", "rough", "surface"],
    },
    ISSUE_WATER_LEAKAGE: {
        "phrases": [
            "water leakage", "water leak", "broken water pipe", "pipe leak", "pipeline burst",
            "pipe burst", "drinking water leak", "water pipe broken", "clean water wasted",
            "pipeline leakage", "thanneer kasivu", "kudineer kuzhai", "drinking water wasting",
            "water gushing from pipe", "underground pipe leak"
        ],
        "strong": ["pipeline", "leakage", "waterpipe", "pipeburst", "kudineer", "thanneer", "kasivu"],
        "tamil": ["தண்ணீர் கசிவு", "குடிநீர்", "குழாய் உடைப்பு", "கசிவு", "குடிநீர் வீணாகிறது"],
        "secondary": ["water", "pipe", "leak", "gushing", "meter", "supply", "drinking water"],
    },
    ISSUE_SEWAGE_OVERFLOW: {
        "phrases": [
            "sewage overflow", "sewer overflow", "manhole overflow", "sewage water",
            "gutter overflowing", "septic overflow", "foul smell sewage", "black water overflow",
            "saakadai thanneer", "manhole open", "drainage stink", "sewage leak", "sewer line burst"
        ],
        "strong": ["sewage", "sewer", "manhole", "gutter", "septic", "saakadai", "malini"],
        "tamil": ["சாக்கடை", "கழிவுநீர்", "கழிவு நீர்", "சாக்கடை நீர்", "சாக்கடை வழிதல்"],
        "secondary": ["foul smell", "stink", "overflow", "black water", "contaminated", "choked sewer"],
    },
    ISSUE_BROKEN_STREET_LIGHT: {
        "phrases": [
            "broken street light", "street light not working", "dark street", "light pole broken",
            "lamp post broken", "no street light", "streetlights off", "light not glowing",
            "theruvilakku eriyala", "street light dark", "street lamp broken", "flickering street light",
            "street lights not burning", "dark road at night"
        ],
        "strong": ["streetlight", "streetlights", "lamppost", "theruvilakku", "vilakku"],
        "tamil": ["தெருவிளக்கு", "விளக்கு", "மின்விளக்கு", "விளக்கு எரியவில்லை"],
        "secondary": ["street light", "lamp", "pole", "dark", "darkness", "bulb", "lighting", "night"],
    },
    ISSUE_DRAINAGE_PROBLEM: {
        "phrases": [
            "drainage problem", "drain blocked", "clogged drain", "drainage clogged",
            "storm drain blocked", "rainwater stagnant", "blocked drain", "water stagnant on street",
            "drainage choking", "vaadikkaal adaipu", "rain water logging", "water logging",
            "monsoon drain blocked", "rainwater accumulation"
        ],
        "strong": ["drainage", "waterlogging", "waterlogged", "vaadikkaal", "adaipu", "stormdrain"],
        "tamil": ["வடிகால்", "வடிகால் அடைப்பு", "மழைநீர்", "மழைநீர் தேக்கம்", "நீர் தேக்கம்"],
        "secondary": ["drain", "clogged", "blocked", "stagnant", "rainwater", "choked", "flooding"],
    },
    ISSUE_TRAFFIC_ISSUE: {
        "phrases": [
            "traffic issue", "traffic jam", "traffic congestion", "traffic signal not working",
            "signal not working", "traffic lights not working", "signal broken", "illegal parking",
            "heavy traffic", "pokkuvarathu jam", "signal failure", "junction traffic block",
            "road block traffic", "traffic bottleneck"
        ],
        "strong": ["congestion", "gridlock", "pokkuvarathu", "bottleneck"],
        "tamil": ["போக்குவரத்து", "சிக்னல்", "போக்குவரத்து நெரிசல்", "சிக்னல் பழுது"],
        "secondary": ["traffic", "signal", "jam", "junction", "vehicles", "crossing", "parking"],
    },
    ISSUE_BUILDING_DAMAGE: {
        "phrases": [
            "building damage", "wall crack", "dilapidated building", "unsafe building",
            "wall collapsing", "cracked ceiling", "ceiling collapse", "broken wall",
            "dilapidated structure", "kattida sedham", "crumbling wall", "building collapse risk",
            "old building falling", "plaster falling"
        ],
        "strong": ["dilapidated", "kattidam", "kattida", "crumbling", "structural crack"],
        "tamil": ["கட்டிடம்", "கட்டிட சேதம்", "சுவர் விரிசல்", "இடிந்து", "இடியும் நிலை"],
        "secondary": ["building", "wall", "ceiling", "collapse", "crack", "cracked", "structure", "pillars"],
    },
    ISSUE_PARK_DAMAGE: {
        "phrases": [
            "park damage", "park bench broken", "playground broken", "swing broken",
            "children park damaged", "park walking track", "garden damaged", "public park maintenance",
            "poonga sedham", "park lights broken", "broken swing", "damaged bench in park",
            "see saw broken", "park fence broken"
        ],
        "strong": ["playground", "poonga", "seesaw", "walking track", "park bench"],
        "tamil": ["பூங்கா", "விளையாட்டு மைதானம்", "பூங்கா சேதம்", "ஊஞ்சல்"],
        "secondary": ["park", "garden", "bench", "swing", "recreation", "grass", "plants"],
    },
    ISSUE_ENVIRONMENTAL_POLLUTION: {
        "phrases": [
            "environmental pollution", "air pollution", "factory smoke", "industrial smoke",
            "chemical fumes", "toxic smell", "chemical odor", "smoke emission", "river pollution",
            "burning garbage plastic", "kaatru maasu", "industrial pollution", "toxic waste river",
            "black smoke from factory", "chemical pollution"
        ],
        "strong": ["pollution", "smog", "toxic fumes", "chemical smell", "factory smoke", "maasu"],
        "tamil": ["சுற்றுச்சூழல்", "சுற்றுச்சூழல் மாசு", "காற்று மாசு", "புகை", "நச்சு புகை"],
        "secondary": ["chemical", "fumes", "toxic", "smoke", "odor", "emission", "polluted", "river"],
    },
}


def classify_issue_from_description(
    text: Optional[str],
    language: Optional[str] = "en",
) -> Tuple[Optional[str], float, List[str]]:
    """
    Intelligently infer civic issue category from complaint description
    using multi-lingual keyword and phrase matching (English, Tamil, Tanglish).

    Returns:
    (canonical_issue_key, confidence, matched_keywords)
    If classification is uncertain, returns (None, 0.0, []).
    """
    if not text or not text.strip():
        return None, 0.0, []

    clean_text = text.lower()
    scores: Dict[str, float] = {}
    matched_words_map: Dict[str, List[str]] = {}

    for issue_key, data in ISSUE_KEYWORDS.items():
        score = 0.0
        matched = []

        # 1. Exact phrase matches (High weight: 3.5)
        for phrase in data.get("phrases", []):
            if phrase.isascii():
                pattern = rf"\b{re.escape(phrase)}\b"
                if re.search(pattern, clean_text):
                    score += 3.5
                    matched.append(phrase)
            else:
                if phrase in clean_text:
                    score += 3.5
                    matched.append(phrase)

        # 2. Tamil keyword matches (Weight: 2.5)
        for t_word in data.get("tamil", []):
            if t_word in clean_text:
                score += 2.5
                matched.append(t_word)

        # 3. Strong keyword matches (Weight: 2.0)
        for word in data.get("strong", []):
            pattern = rf"\b{re.escape(word)}\b"
            if re.search(pattern, clean_text):
                score += 2.0
                matched.append(word)

        # 4. Secondary keywords (Weight: 0.8, only counted if score >= 1.5 or multiple secondaries match)
        secondary_hits = []
        for word in data.get("secondary", []):
            pattern = rf"\b{re.escape(word)}\b"
            if re.search(pattern, clean_text):
                secondary_hits.append(word)

        if score > 0 or len(secondary_hits) >= 2:
            score += len(secondary_hits) * 0.8
            matched.extend(secondary_hits)

        if score > 0:
            scores[issue_key] = score
            matched_words_map[issue_key] = list(set(matched))

    if not scores:
        return None, 0.0, []

    sorted_issues = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_issue, top_score = sorted_issues[0]
    second_score = sorted_issues[1][1] if len(sorted_issues) > 1 else 0.0

    # Ensure significant confidence margin to prevent ambiguous routing
    if top_score < 1.6:
        # Score too low -> Uncertain
        return None, 0.0, []

    if len(sorted_issues) > 1 and second_score > 0:
        ratio = top_score / second_score
        diff = top_score - second_score
        if ratio < 1.25 and diff < 1.4:
            # Ambiguous conflict between two categories -> Uncertain
            return None, 0.0, []

    confidence = min(0.96, 0.55 + (top_score * 0.08))
    return best_issue, round(confidence, 2), matched_words_map.get(best_issue, [])



def get_routing_for_issue(issue_key_or_id: Any) -> Dict[str, Any]:
    """
    Returns complete metadata for a given issue (class_id, class_name, issue_type, department_id, department_name).
    """
    class_id, class_name, issue_key, dept_name = resolve_canonical_issue(issue_key_or_id)
    entry = CANONICAL_ROUTING_TABLE[class_id]
    return {
        "class_id": class_id,
        "class_name": class_name,
        "issue_type": issue_key,
        "department_id": entry["department_id"],
        "department_name": dept_name,
    }

