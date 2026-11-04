import re
import math
import unicodedata
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.models.complaint import Complaint
from app.complaints.constants import ISSUE_DISPLAY_NAMES

# Configurable Deterministic Thresholds
TEXT_SIMILARITY_THRESHOLD = 0.70
GPS_DISTANCE_THRESHOLD_METERS = 100.0
RECENT_DAYS = 30
DUPLICATE_FLAG_SCORE_THRESHOLD = 0.60
MAX_CANDIDATES = 10

# Earth radius in meters for Haversine calculation
EARTH_RADIUS_METERS = 6371000.0


def normalize_complaint_text(text: Optional[str]) -> str:
    """
    Normalize complaint description strictly for duplicate comparison.
    - Converts ASCII letters to lowercase
    - Strips Unicode punctuation and symbols, preserving letters, combining marks/matras, and numbers
    - Collapses multiple whitespace characters to a single space
    - Strips leading/trailing whitespace

    The original text in PostgreSQL remains 100% unaltered.
    """
    if not text:
        return ""
    clean = text.lower()
    cleaned_chars = []
    for char in clean:
        cat = unicodedata.category(char)
        if cat.startswith(("P", "S")):
            cleaned_chars.append(" ")
        else:
            cleaned_chars.append(char)
    clean = "".join(cleaned_chars)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def haversine_distance_meters(
    lat1: Optional[float],
    lon1: Optional[float],
    lat2: Optional[float],
    lon2: Optional[float],
) -> Optional[float]:
    """
    Compute great-circle distance between two geographic coordinates using Haversine formula.
    Returns distance in meters.
    If either point lacks latitude or longitude, returns None without fabricating coordinates.
    """
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return None

    try:
        lat1_f = float(lat1)
        lon1_f = float(lon1)
        lat2_f = float(lat2)
        lon2_f = float(lon2)
    except (ValueError, TypeError):
        return None

    # Validate coordinate boundaries (-90..90, -180..180)
    if not (-90.0 <= lat1_f <= 90.0 and -90.0 <= lat2_f <= 90.0):
        return None
    if not (-180.0 <= lon1_f <= 180.0 and -180.0 <= lon2_f <= 180.0):
        return None

    # Convert degrees to radians
    phi1 = math.radians(lat1_f)
    phi2 = math.radians(lat2_f)
    delta_phi = math.radians(lat2_f - lat1_f)
    delta_lambda = math.radians(lon2_f - lon1_f)

    # Haversine formula
    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    distance = EARTH_RADIUS_METERS * c

    return round(distance, 1)


def compute_text_similarity(
    target_text: str,
    candidate_texts: List[str],
) -> List[float]:
    """
    Calculate real cosine similarity between target_text and a list of candidate_texts
    using TF-IDF vectorization from scikit-learn.
    Returns actual floating-point scores between 0.0 and 1.0 (no fake confidence).
    """
    norm_target = normalize_complaint_text(target_text)
    norm_candidates = [normalize_complaint_text(t) for t in candidate_texts]

    # If target is completely empty, all similarities are 0.0
    if not norm_target:
        return [0.0] * len(candidate_texts)

    # Filter out empty candidates early
    results: List[float] = [0.0] * len(candidate_texts)
    valid_indices = [i for i, c in enumerate(norm_candidates) if c]

    if not valid_indices:
        return results

    corpus = [norm_target] + [norm_candidates[i] for i in valid_indices]

    try:
        vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            token_pattern=r"(?u)\S+",
            stop_words="english",
            min_df=1,
            sublinear_tf=True,
        )
        tfidf_matrix = vectorizer.fit_transform(corpus)
        sim_scores = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()

        for idx, orig_pos in enumerate(valid_indices):
            score = float(sim_scores[idx])
            # Clamp between 0.0 and 1.0
            results[orig_pos] = round(max(0.0, min(1.0, score)), 4)
    except Exception:
        # Fallback to word overlap Jaccard if TF-IDF fails on strange characters
        target_words = set(norm_target.split())
        for idx in valid_indices:
            cand_words = set(norm_candidates[idx].split())
            if not target_words or not cand_words:
                results[idx] = 0.0
            else:
                intersection = len(target_words & cand_words)
                union = len(target_words | cand_words)
                results[idx] = round(intersection / union, 4) if union > 0 else 0.0

    return results


class DuplicateService:
    """
    Deterministic Duplicate Complaint Detection Service.
    Combines text similarity, geographic distance, and canonical issue matching.
    """

    @staticmethod
    def get_recent_eligible_complaints(
        db: Session,
        recent_days: int = RECENT_DAYS,
        exclude_complaint_id: Optional[str] = None,
        exclude_db_id: Optional[int] = None,
    ) -> List[Complaint]:
        """
        Query eligible historical complaints for duplicate comparison.
        - Restricted to the configured sliding window (default: last 30 days).
        - Excludes REJECTED complaints if desired.
        - Excludes the complaint currently being evaluated.
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=recent_days)

        query = (
            db.query(Complaint)
            .filter(Complaint.created_at >= cutoff_date)
            .filter(Complaint.status != "REJECTED")
            .order_by(desc(Complaint.created_at))
        )

        if exclude_complaint_id:
            query = query.filter(Complaint.complaint_id != exclude_complaint_id.strip())
        if exclude_db_id:
            query = query.filter(Complaint.id != exclude_db_id)

        # Cap search candidates to prevent unbounded memory consumption
        return query.limit(300).all()

    @staticmethod
    def evaluate_candidates(
        target_issue_type: str,
        target_description: Optional[str],
        target_lat: Optional[float],
        target_lon: Optional[float],
        candidates: List[Complaint],
    ) -> List[Dict[str, Any]]:
        """
        Evaluate candidate complaints and compute deterministic similarity scores.
        """
        if not candidates:
            return []

        clean_issue = (target_issue_type or "").strip().lower()
        candidate_texts = [c.processed_text or c.description or "" for c in candidates]
        text_similarities = compute_text_similarity(target_description or "", candidate_texts)

        results = []

        for idx, candidate in enumerate(candidates):
            cand_issue = (candidate.issue_type or "").strip().lower()
            issue_match = (clean_issue == cand_issue)

            text_sim = text_similarities[idx]
            distance = haversine_distance_meters(
                target_lat,
                target_lon,
                float(candidate.latitude) if candidate.latitude is not None else None,
                float(candidate.longitude) if candidate.longitude is not None else None,
            )

            # Deterministic Duplicate Score Calculation
            if not issue_match:
                duplicate_score = 0.0
                reason = "Different civic issue category"
                is_flagged = False
            else:
                # Same issue type
                if distance is not None:
                    if distance <= GPS_DISTANCE_THRESHOLD_METERS:
                        # Nearby location
                        dist_factor = max(0.0, 1.0 - (distance / GPS_DISTANCE_THRESHOLD_METERS))
                        # Combine text and proximity
                        if text_sim > 0.1:
                            duplicate_score = round(0.50 * text_sim + 0.50 * dist_factor, 4)
                        else:
                            # Minimal text description provided
                            duplicate_score = round(0.50 * dist_factor, 4)

                        is_flagged = (
                            duplicate_score >= DUPLICATE_FLAG_SCORE_THRESHOLD
                            or distance <= 30.0
                            or (distance <= 100.0 and text_sim >= 0.40)
                        )
                        if text_sim >= 0.40:
                            reason = f"Same issue type, high text similarity ({text_sim:.2f}), and nearby GPS location ({distance:.1f} m)"
                        else:
                            reason = f"Same issue type and nearby GPS location ({distance:.1f} m)"
                    else:
                        # Far location: distance penalty
                        decay = max(0.0, 1.0 - ((distance - GPS_DISTANCE_THRESHOLD_METERS) / 900.0))
                        duplicate_score = round(text_sim * 0.70 * decay, 4)
                        is_flagged = duplicate_score >= DUPLICATE_FLAG_SCORE_THRESHOLD
                        reason = f"Same issue type, but location is {distance:.1f} m away"
                else:
                    # Missing GPS coordinates: rely strictly on text similarity + issue match
                    duplicate_score = round(text_sim, 4)
                    is_flagged = text_sim >= TEXT_SIMILARITY_THRESHOLD
                    reason = f"Same issue type and high text similarity ({text_sim:.2f}) (GPS coordinates not provided)"

            if is_flagged:
                results.append({
                    "complaint_id": candidate.complaint_id,
                    "db_id": candidate.id,
                    "issue_type": candidate.issue_type,
                    "issue_type_display": ISSUE_DISPLAY_NAMES.get(candidate.issue_type, candidate.issue_type),
                    "issue_match": issue_match,
                    "text_similarity": text_sim,
                    "distance_meters": distance,
                    "duplicate_score": duplicate_score,
                    "reason": reason,
                    "status": candidate.status,
                    "created_at": candidate.created_at,
                })

        # Sort flagged candidates by duplicate_score descending
        results.sort(key=lambda x: x["duplicate_score"], reverse=True)
        return results[:MAX_CANDIDATES]

    @classmethod
    def check_for_duplicates(
        cls,
        db: Session,
        issue_type: str,
        description: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        exclude_complaint_id: Optional[str] = None,
        exclude_db_id: Optional[int] = None,
        recent_days: int = RECENT_DAYS,
    ) -> Dict[str, Any]:
        """
        Public duplicate check method returning structured candidate information.
        Guarantees zero exposure of private citizen details.
        """
        candidates = cls.get_recent_eligible_complaints(
            db=db,
            recent_days=recent_days,
            exclude_complaint_id=exclude_complaint_id,
            exclude_db_id=exclude_db_id,
        )

        flagged = cls.evaluate_candidates(
            target_issue_type=issue_type,
            target_description=description,
            target_lat=latitude,
            target_lon=longitude,
            candidates=candidates,
        )

        # Sanitize candidate dictionaries for public/citizen consumption (no user_id or internal DB ID)
        sanitized_candidates = [
            {
                "complaint_id": item["complaint_id"],
                "issue_type": item["issue_type"],
                "issue_type_display": item["issue_type_display"],
                "issue_match": item["issue_match"],
                "text_similarity": item["text_similarity"],
                "distance_meters": item["distance_meters"],
                "duplicate_score": item["duplicate_score"],
                "reason": item["reason"],
                "status": item["status"],
                "created_at": item["created_at"],
            }
            for item in flagged
        ]

        return {
            "has_possible_duplicate": len(sanitized_candidates) > 0,
            "candidates": sanitized_candidates,
            "raw_candidates_with_db_id": flagged,  # internal reference for DB association
        }
