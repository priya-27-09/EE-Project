"""
Resolution Evidence Verification Service for AI Civic Guardian (Step 9).
Performs deterministic, measurable visual evidence comparison using classical computer vision
(OpenCV and Pillow) comparing original citizen evidence against officer resolution evidence.

Strict Requirements:
- No fake AI confidence scores or fake YOLO predictions.
- All metrics are mathematically derived from real computer vision algorithms.
- Full auditability with algorithm versioning ("resolution-v1").
- Human review is preserved and never overwrites underlying automated metrics.
"""
from datetime import datetime, timezone
import math
import os
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

import cv2
import numpy as np
from PIL import Image
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.complaint import Complaint
from app.models.evidence import ComplaintEvidence
from app.models.resolution_verification import ResolutionVerification
from app.services.audit_service import record_audit_log

# Storage base directory (same as evidence_service)
UPLOAD_BASE_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "evidence"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Algorithm version
ALGORITHM_VERSION = "resolution-v1"

# Canonical verification states
VERIFICATION_NOT_AVAILABLE = "VERIFICATION_NOT_AVAILABLE"
VERIFICATION_PENDING = "PENDING"
VERIFICATION_AI_VERIFIED = "AI_VERIFIED"
VERIFICATION_NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"
VERIFICATION_FAILED = "VERIFICATION_FAILED"

# Human review decisions
REVIEW_APPROVED = "APPROVED"
REVIEW_REJECTED = "REJECTED"

# Standard image processing dimensions
TARGET_IMAGE_SIZE = (512, 512)

# Supported image extensions
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def select_evidence_pair(
    complaint: Complaint,
    db: Session,
) -> Tuple[Optional[ComplaintEvidence], Optional[ComplaintEvidence], Optional[str]]:
    """
    Deterministically select compatible before (citizen original) and after (officer resolution)
    evidence images for comparison.

    Rules:
    - Before evidence: is_resolution == False, image format, latest uploaded.
    - After evidence: is_resolution == True, image format, latest uploaded.
    - Returns (before_evidence, after_evidence, unavailable_reason).
    """
    evidences = (
        db.query(ComplaintEvidence)
        .filter(ComplaintEvidence.complaint_id == complaint.id)
        .order_by(desc(ComplaintEvidence.created_at))
        .all()
    )

    before_ev: Optional[ComplaintEvidence] = None
    after_ev: Optional[ComplaintEvidence] = None
    has_video_evidence = False

    for ev in evidences:
        file_type = (ev.file_type or "").lower()
        ext = Path(ev.file_path).suffix.lower()

        if file_type.startswith("video/") or ext in {".mp4", ".mov", ".avi", ".webm"}:
            has_video_evidence = True
            continue

        is_image = file_type.startswith("image/") or ext in SUPPORTED_IMAGE_EXTENSIONS
        if not is_image:
            continue

        if ev.is_resolution and after_ev is None:
            after_ev = ev
        elif not ev.is_resolution and before_ev is None:
            before_ev = ev

    if before_ev is None and after_ev is None and has_video_evidence:
        return None, None, "Video resolution verification is not currently available."

    if before_ev is None:
        return None, after_ev, "No compatible original image evidence is available."

    if after_ev is None:
        return before_ev, None, "No resolution image evidence is available."

    return before_ev, after_ev, None


def resolve_and_validate_evidence_path(evidence: ComplaintEvidence) -> Path:
    """
    Safely resolve evidence file path on disk, preventing path traversal.
    Returns absolute Path if file exists, raises ValueError otherwise.
    """
    raw_path = (evidence.file_path or "").strip()
    if not raw_path:
        raise ValueError(f"Evidence ID {evidence.id} has empty file_path.")

    # Prevent path traversal
    normalized = os.path.normpath(raw_path).replace("\\", "/")
    if ".." in normalized.split("/"):
        raise ValueError("Security violation: Path traversal detected in evidence file_path.")

    abs_path = (PROJECT_ROOT / normalized).resolve()

    # Ensure path is inside project root
    try:
        abs_path.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        raise ValueError("Security violation: Evidence file path resides outside authorized project root.")

    if not abs_path.is_file():
        raise FileNotFoundError(f"Evidence file on disk not found: {abs_path}")

    return abs_path


def load_and_preprocess_image(evidence: ComplaintEvidence) -> Tuple[np.ndarray, np.ndarray]:
    """
    Safely load image from disk, validate it can be decoded, and preprocess it.
    Returns:
        (color_image_bgr_512x512, grayscale_image_512x512)
    Raises ValueError on decode failure or corrupted file.
    """
    abs_path = resolve_and_validate_evidence_path(evidence)

    # Check file size > 0
    if abs_path.stat().st_size == 0:
        raise ValueError(f"Evidence file is empty (0 bytes): {abs_path.name}")

    # Read image using OpenCV with unicode-safe buffer
    img_bgr = None
    try:
        with open(abs_path, "rb") as f:
            file_bytes = np.frombuffer(f.read(), dtype=np.uint8)
            img_bgr = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    except Exception as exc:
        img_bgr = None

    # Fallback to Pillow if OpenCV imdecode failed
    if img_bgr is None or img_bgr.size == 0:
        try:
            with Image.open(abs_path) as pil_img:
                pil_img = pil_img.convert("RGB")
                img_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        except Exception as exc:
            raise ValueError(f"Corrupted or undecodable image file: {abs_path.name} ({str(exc)})")

    if img_bgr is None or img_bgr.size == 0:
        raise ValueError(f"Failed to decode image from evidence: {abs_path.name}")

    # Resize to standard TARGET_IMAGE_SIZE (512, 512)
    resized_bgr = cv2.resize(img_bgr, TARGET_IMAGE_SIZE, interpolation=cv2.INTER_AREA)
    resized_gray = cv2.cvtColor(resized_bgr, cv2.COLOR_BGR2GRAY)

    return resized_bgr, resized_gray


def attempt_feature_alignment(
    img1_gray: np.ndarray,
    img2_gray: np.ndarray,
    img2_bgr: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, str]:
    """
    Attempt perspective alignment using ORB keypoint detection, BFMatcher,
    and RANSAC Homography warp perspective.

    Returns:
        (aligned_img2_gray, aligned_img2_bgr, alignment_status)
    Where alignment_status is 'ALIGNED' or 'NOT_AVAILABLE'.
    Never fabricates alignment if matching is insufficient.
    """
    try:
        orb = cv2.ORB_create(nfeatures=1000)
        kp1, des1 = orb.detectAndCompute(img1_gray, None)
        kp2, des2 = orb.detectAndCompute(img2_gray, None)

        if des1 is None or des2 is None or len(kp1) < 15 or len(kp2) < 15:
            return img2_gray, img2_bgr, "NOT_AVAILABLE"

        # BFMatcher with Hamming distance
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        matches = matcher.knnMatch(des1, des2, k=2)

        # Lowe's ratio test (0.75)
        good_matches = []
        for m_pair in matches:
            if len(m_pair) == 2:
                m, n = m_pair
                if m.distance < 0.75 * n.distance:
                    good_matches.append(m)

        if len(good_matches) < 10:
            return img2_gray, img2_bgr, "NOT_AVAILABLE"

        src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

        # Find homography mapping img2 onto img1
        H, inliers = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 5.0)

        if H is None or inliers is None:
            return img2_gray, img2_bgr, "NOT_AVAILABLE"

        inlier_count = int(np.sum(inliers))
        if inlier_count < 8:
            return img2_gray, img2_bgr, "NOT_AVAILABLE"

        # Check determinant to avoid degenerate or inverted warps
        det = np.linalg.det(H[:2, :2])
        if det < 0.1 or det > 10.0:
            return img2_gray, img2_bgr, "NOT_AVAILABLE"

        aligned_gray = cv2.warpPerspective(img2_gray, H, TARGET_IMAGE_SIZE, flags=cv2.INTER_LINEAR)
        aligned_bgr = cv2.warpPerspective(img2_bgr, H, TARGET_IMAGE_SIZE, flags=cv2.INTER_LINEAR)

        return aligned_gray, aligned_bgr, "ALIGNED"
    except Exception:
        return img2_gray, img2_bgr, "NOT_AVAILABLE"


def compute_ssim(img1_gray: np.ndarray, img2_gray: np.ndarray) -> float:
    """
    Compute Structural Similarity Index (SSIM) between two grayscale images using
    Gaussian-filtered local luminance, contrast, and structure equations.
    Formula:
        SSIM(x, y) = [(2*mu_x*mu_y + C1)*(2*sigma_xy + C2)] / [(mu_x^2 + mu_y^2 + C1)*(sigma_x^2 + sigma_y^2 + C2)]
    Returns float in range [0.0, 1.0].
    """
    C1 = (0.01 * 255.0) ** 2
    C2 = (0.03 * 255.0) ** 2

    img1 = img1_gray.astype(np.float64)
    img2 = img2_gray.astype(np.float64)

    kernel = (11, 11)
    sigma = 1.5

    mu1 = cv2.GaussianBlur(img1, kernel, sigma)
    mu2 = cv2.GaussianBlur(img2, kernel, sigma)

    mu1_sq = mu1 * mu1
    mu2_sq = mu2 * mu2
    mu1_mu2 = mu1 * mu2

    sigma1_sq = cv2.GaussianBlur(img1 * img1, kernel, sigma) - mu1_sq
    sigma2_sq = cv2.GaussianBlur(img2 * img2, kernel, sigma) - mu2_sq
    sigma12 = cv2.GaussianBlur(img1 * img2, kernel, sigma) - mu1_mu2

    numerator = (2.0 * mu1_mu2 + C1) * (2.0 * sigma12 + C2)
    denominator = (mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2)

    ssim_map = numerator / (denominator + 1e-10)
    score = float(np.mean(ssim_map))
    return max(0.0, min(1.0, score))


def compute_pixel_difference(img1_gray: np.ndarray, img2_gray: np.ndarray) -> float:
    """
    Compute normalized Mean Absolute Difference (MAD) between two grayscale images.
    Returns float in range [0.0, 1.0].
    """
    diff = np.abs(img1_gray.astype(np.float64) - img2_gray.astype(np.float64))
    mad = float(np.mean(diff) / 255.0)
    return max(0.0, min(1.0, mad))


def compute_edge_similarity(img1_gray: np.ndarray, img2_gray: np.ndarray) -> float:
    """
    Compute Canny edge similarity using the Dice similarity coefficient:
        Dice = 2 * |Edges1 ∩ Edges2| / (|Edges1| + |Edges2|)
    Returns float in range [0.0, 1.0].
    """
    edges1 = cv2.Canny(img1_gray, 50, 150) > 0
    edges2 = cv2.Canny(img2_gray, 50, 150) > 0

    count1 = int(np.sum(edges1))
    count2 = int(np.sum(edges2))

    if count1 == 0 and count2 == 0:
        return 1.0
    if count1 == 0 or count2 == 0:
        return 0.0

    intersection = int(np.sum(np.logical_and(edges1, edges2)))
    dice = (2.0 * intersection) / float(count1 + count2)
    return max(0.0, min(1.0, float(dice)))


def compute_histogram_similarity(img1_bgr: np.ndarray, img2_bgr: np.ndarray) -> float:
    """
    Compute 3D BGR color histogram correlation normalized to [0.0, 1.0].
    """
    # 8 bins per channel (8x8x8 = 512 bins)
    hist1 = cv2.calcHist([img1_bgr], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
    hist2 = cv2.calcHist([img2_bgr], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])

    cv2.normalize(hist1, hist1, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
    cv2.normalize(hist2, hist2, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)

    correl = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
    # Correlation is in [-1.0, 1.0], map to [0.0, 1.0]
    normalized_correl = max(0.0, min(1.0, (float(correl) + 1.0) / 2.0))
    return normalized_correl


def compute_phash_hamming_distance(img1_gray: np.ndarray, img2_gray: np.ndarray) -> int:
    """
    Compute 64-bit DCT Perceptual Hash (pHash) Hamming distance.
    Steps:
    1. Resize to 32x32.
    2. Compute 2D DCT.
    3. Take 8x8 low frequency coefficients (excluding DC component).
    4. Compute median.
    5. Generate 64-bit hash (1 if > median, else 0).
    6. Return Hamming distance in [0, 64].
    """
    def _phash(gray: np.ndarray) -> np.ndarray:
        resized = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA)
        f_val = np.float32(resized)
        dct = cv2.dct(f_val)
        # 8x8 low frequencies
        dct_low = dct[:8, :8]
        # Exclude DC term at [0, 0] when calculating median
        ac_coeffs = dct_low.flatten()[1:]
        med = float(np.median(ac_coeffs))
        return dct_low > med

    hash1 = _phash(img1_gray)
    hash2 = _phash(img2_gray)
    hamming_dist = int(np.count_nonzero(hash1 != hash2))
    return max(0, min(64, hamming_dist))


def evaluate_verification_decision(
    structural_similarity: float,
    pixel_difference: float,
    edge_similarity: float,
    histogram_similarity: float,
    perceptual_hash_distance: int,
    alignment_status: str,
    issue_type: Optional[str] = None,
) -> Tuple[str, float, bool, str]:
    """
    Evaluate deterministic verification decision and scoring formula.
    Returns:
        (verification_status, verification_score, human_review_required, verification_reason)

    Rules:
    1. Anti-Spoofing Identical Evidence Check:
       If pixel_difference < 0.01 and SSIM > 0.98 and pHash_dist <= 2:
       Images are visually identical, indicating same image uploaded twice without actual repair.
       -> VERIFICATION_FAILED (score = 0.0, human_review_required = True).

    2. Dissimilar Scene Check:
       If pHash_dist > 35 and histogram_similarity < 0.25 and SSIM < 0.20:
       Scenes differ significantly in composition/location.
       -> NEEDS_HUMAN_REVIEW (human_review_required = True).

    3. Composite Score Calculation:
       - Scene consistency: S_scene = 0.5 * hist_sim + 0.5 * (1.0 - pHash_dist / 64.0)
       - Structural consistency: S_struct = structural_similarity
       - Edge similarity: S_edge = edge_similarity
       - Alignment factor: A = 1.0 if alignment_status == 'ALIGNED' else 0.6
       Score = 0.35 * S_scene + 0.30 * S_struct + 0.20 * S_edge + 0.15 * A

    4. Decision Thresholds:
       - Score >= 0.70 AND S_scene >= 0.50 AND pixel_difference >= 0.02:
         -> AI_VERIFIED (human_review_required = False)
       - 0.40 <= Score < 0.70:
         -> NEEDS_HUMAN_REVIEW (human_review_required = True)
       - Score < 0.40:
         -> VERIFICATION_FAILED (human_review_required = True)
    """
    # 1. Anti-Spoofing: Identical Images Check
    if pixel_difference < 0.01 and structural_similarity > 0.98 and perceptual_hash_distance <= 2:
        return (
            VERIFICATION_FAILED,
            0.0,
            True,
            "Before and after evidence images appear identical; no measurable repair change detected.",
        )

    # 2. Scene Dissimilarity Check
    if perceptual_hash_distance > 35 and histogram_similarity < 0.25 and structural_similarity < 0.20:
        # Calculate raw score for transparency
        s_scene = 0.5 * histogram_similarity + 0.5 * (1.0 - (perceptual_hash_distance / 64.0))
        s_struct = structural_similarity
        s_edge = edge_similarity
        a_factor = 1.0 if alignment_status == "ALIGNED" else 0.6
        raw_score = round(0.35 * s_scene + 0.30 * s_struct + 0.20 * s_edge + 0.15 * a_factor, 4)
        return (
            VERIFICATION_NEEDS_HUMAN_REVIEW,
            raw_score,
            True,
            "Before and after evidence scenes differ significantly in perspective, composition, or environment. Manual officer inspection required.",
        )

    # 3. Composite Score Calculation
    s_scene = 0.5 * histogram_similarity + 0.5 * (1.0 - (perceptual_hash_distance / 64.0))
    s_struct = structural_similarity
    s_edge = edge_similarity
    a_factor = 1.0 if alignment_status == "ALIGNED" else 0.6

    score = round(0.35 * s_scene + 0.30 * s_struct + 0.20 * s_edge + 0.15 * a_factor, 4)
    score = max(0.0, min(1.0, score))

    # 4. Decision Thresholds
    if score >= 0.70 and s_scene >= 0.50 and pixel_difference >= 0.02:
        return (
            VERIFICATION_AI_VERIFIED,
            score,
            False,
            "The available before/after visual evidence satisfies the configured measurable verification criteria.",
        )
    elif score >= 0.40:
        return (
            VERIFICATION_NEEDS_HUMAN_REVIEW,
            score,
            True,
            "Visual evidence is inconclusive or shows partial change. Manual officer review recommended.",
        )
    else:
        return (
            VERIFICATION_FAILED,
            score,
            True,
            "Visual evidence failed measurable verification criteria; insufficient evidence of repair.",
        )


def run_resolution_verification(
    complaint: Complaint,
    officer_user_id: int,
    db: Session,
) -> ResolutionVerification:
    """
    Run full end-to-end resolution evidence verification for a complaint.
    1. Deterministically selects before/after evidence pair.
    2. Safely loads and preprocesses images.
    3. Attempts feature alignment.
    4. Computes 5 measurable computer vision metrics.
    5. Applies deterministic scoring and decision logic.
    6. Persists new ResolutionVerification record in PostgreSQL.
    7. Records audit log with metadata.
    """
    # 1. Select evidence pair
    before_ev, after_ev, unavailable_reason = select_evidence_pair(complaint, db)

    if unavailable_reason is not None:
        verification = ResolutionVerification(
            complaint_id=complaint.id,
            before_evidence_id=before_ev.id if before_ev else None,
            after_evidence_id=after_ev.id if after_ev else None,
            verification_status=VERIFICATION_NOT_AVAILABLE,
            verification_score=None,
            human_review_required=True,
            verification_reason=unavailable_reason,
            alignment_status="NOT_AVAILABLE",
            algorithm_version=ALGORITHM_VERSION,
        )
        db.add(verification)
        db.commit()
        db.refresh(verification)

        record_audit_log(
            action="RESOLUTION_VERIFICATION_COMPLETED",
            entity_type="Complaint",
            entity_id=complaint.complaint_id,
            user_id=officer_user_id,
            db=db,
            metadata={
                "verification_id": verification.id,
                "verification_status": VERIFICATION_NOT_AVAILABLE,
                "reason": unavailable_reason,
                "algorithm_version": ALGORITHM_VERSION,
            },
        )
        db.commit()
        return verification

    # 2. Load and preprocess images
    try:
        before_bgr, before_gray = load_and_preprocess_image(before_ev)
    except Exception as exc:
        verification = ResolutionVerification(
            complaint_id=complaint.id,
            before_evidence_id=before_ev.id,
            after_evidence_id=after_ev.id,
            verification_status=VERIFICATION_FAILED,
            verification_score=0.0,
            human_review_required=True,
            verification_reason=f"Failed to load original citizen evidence: {str(exc)}",
            alignment_status="NOT_AVAILABLE",
            algorithm_version=ALGORITHM_VERSION,
        )
        db.add(verification)
        db.commit()
        db.refresh(verification)
        return verification

    try:
        after_bgr, after_gray = load_and_preprocess_image(after_ev)
    except Exception as exc:
        verification = ResolutionVerification(
            complaint_id=complaint.id,
            before_evidence_id=before_ev.id,
            after_evidence_id=after_ev.id,
            verification_status=VERIFICATION_FAILED,
            verification_score=0.0,
            human_review_required=True,
            verification_reason=f"Failed to load officer resolution evidence: {str(exc)}",
            alignment_status="NOT_AVAILABLE",
            algorithm_version=ALGORITHM_VERSION,
        )
        db.add(verification)
        db.commit()
        db.refresh(verification)
        return verification

    # 3. Attempt feature alignment
    aligned_after_gray, aligned_after_bgr, alignment_status = attempt_feature_alignment(
        img1_gray=before_gray,
        img2_gray=after_gray,
        img2_bgr=after_bgr,
    )

    # 4. Compute 5 real computer vision metrics
    eval_gray = aligned_after_gray if alignment_status == "ALIGNED" else after_gray
    eval_bgr = aligned_after_bgr if alignment_status == "ALIGNED" else after_bgr

    ssim_val = round(compute_ssim(before_gray, eval_gray), 4)
    pixel_diff_val = round(compute_pixel_difference(before_gray, eval_gray), 4)
    edge_sim_val = round(compute_edge_similarity(before_gray, eval_gray), 4)
    hist_sim_val = round(compute_histogram_similarity(before_bgr, eval_bgr), 4)
    phash_dist_val = compute_phash_hamming_distance(before_gray, eval_gray)

    # 5. Evaluate deterministic verification decision
    status_val, score_val, review_req, reason_val = evaluate_verification_decision(
        structural_similarity=ssim_val,
        pixel_difference=pixel_diff_val,
        edge_similarity=edge_sim_val,
        histogram_similarity=hist_sim_val,
        perceptual_hash_distance=phash_dist_val,
        alignment_status=alignment_status,
        issue_type=complaint.issue_type,
    )

    # 6. Persist record in PostgreSQL
    verification = ResolutionVerification(
        complaint_id=complaint.id,
        before_evidence_id=before_ev.id,
        after_evidence_id=after_ev.id,
        verification_status=status_val,
        verification_score=score_val,
        human_review_required=review_req,
        verification_reason=reason_val,
        structural_similarity=ssim_val,
        pixel_difference=pixel_diff_val,
        edge_similarity=edge_sim_val,
        histogram_similarity=hist_sim_val,
        perceptual_hash_distance=phash_dist_val,
        alignment_status=alignment_status,
        algorithm_version=ALGORITHM_VERSION,
    )
    db.add(verification)
    db.commit()
    db.refresh(verification)

    # 7. Record audit log
    record_audit_log(
        action="RESOLUTION_VERIFICATION_COMPLETED",
        entity_type="Complaint",
        entity_id=complaint.complaint_id,
        user_id=officer_user_id,
        db=db,
        metadata={
            "verification_id": verification.id,
            "complaint_id": complaint.complaint_id,
            "before_evidence_id": before_ev.id,
            "after_evidence_id": after_ev.id,
            "verification_status": status_val,
            "verification_score": score_val,
            "human_review_required": review_req,
            "alignment_status": alignment_status,
            "metrics": {
                "structural_similarity": ssim_val,
                "pixel_difference": pixel_diff_val,
                "edge_similarity": edge_sim_val,
                "histogram_similarity": hist_sim_val,
                "perceptual_hash_distance": phash_dist_val,
            },
            "algorithm_version": ALGORITHM_VERSION,
        },
    )
    db.commit()

    # Blockchain Integrity Anchoring (Step 10)
    # Anchors tamper-evident verification event on Ganache
    try:
        from app.services.blockchain_service import BlockchainService
        from app.models.blockchain_record import EVENT_RESOLUTION_VERIFICATION

        verif_payload = {
            "complaint_id": complaint.complaint_id,
            "event_type": EVENT_RESOLUTION_VERIFICATION,
            "verification_id": verification.id,
            "verification_status": verification.verification_status,
            "verification_score": str(verification.verification_score) if verification.verification_score is not None else "0.0",
            "algorithm_version": verification.algorithm_version,
            "created_at": verification.created_at.isoformat(),
        }

        BlockchainService.anchor_event(
            complaint_id=complaint.id,
            complaint_public_id=complaint.complaint_id,
            event_type=EVENT_RESOLUTION_VERIFICATION,
            payload=verif_payload,
            unique_key=f"verif_{verification.id}",
            db=db,
            user_id=officer_user_id,
        )
    except Exception:
        # Resilient design: Blockchain errors must NEVER fail verification recording
        pass

    return verification


def record_human_review(
    complaint: Complaint,
    officer_user_id: int,
    decision: str,
    notes: str,
    db: Session,
) -> ResolutionVerification:
    """
    Record officer human review decision (APPROVED or REJECTED) with mandatory notes.
    Preserves all automated CV metrics and records an audit log.
    """
    clean_decision = (decision or "").strip().upper()
    if clean_decision not in {REVIEW_APPROVED, REVIEW_REJECTED}:
        raise ValueError(f"Invalid review decision '{decision}'. Must be APPROVED or REJECTED.")

    clean_notes = (notes or "").strip()
    if len(clean_notes) < 5:
        raise ValueError("Review notes must contain at least 5 characters.")

    latest_ver = (
        db.query(ResolutionVerification)
        .filter(ResolutionVerification.complaint_id == complaint.id)
        .order_by(desc(ResolutionVerification.created_at))
        .first()
    )

    if not latest_ver:
        # If no verification exists yet, create one in NEEDS_HUMAN_REVIEW state
        latest_ver = ResolutionVerification(
            complaint_id=complaint.id,
            verification_status=VERIFICATION_NEEDS_HUMAN_REVIEW,
            verification_score=None,
            human_review_required=True,
            verification_reason="Manual officer review conducted directly.",
            alignment_status="NOT_AVAILABLE",
            algorithm_version=ALGORITHM_VERSION,
        )
        db.add(latest_ver)
        db.flush()

    now = datetime.now(timezone.utc)
    latest_ver.reviewed_by_id = officer_user_id
    latest_ver.reviewed_at = now
    latest_ver.review_decision = clean_decision
    latest_ver.review_notes = clean_notes
    latest_ver.updated_at = now

    record_audit_log(
        action="RESOLUTION_REVIEW_RECORDED",
        entity_type="Complaint",
        entity_id=complaint.complaint_id,
        user_id=officer_user_id,
        db=db,
        metadata={
            "verification_id": latest_ver.id,
            "review_decision": clean_decision,
            "reviewed_by_id": officer_user_id,
            "notes_length": len(clean_notes),
        },
    )

    db.commit()
    db.refresh(latest_ver)

    # Blockchain Integrity Anchoring (Step 10)
    # Anchors tamper-evident human review decision on Ganache without storing reviewer PII
    try:
        from app.services.blockchain_service import BlockchainService
        from app.models.blockchain_record import EVENT_HUMAN_RESOLUTION_REVIEW

        review_payload = {
            "complaint_id": complaint.complaint_id,
            "event_type": EVENT_HUMAN_RESOLUTION_REVIEW,
            "verification_id": latest_ver.id,
            "decision": clean_decision,
            "review_timestamp": latest_ver.reviewed_at.isoformat() if latest_ver.reviewed_at else now.isoformat(),
        }

        BlockchainService.anchor_event(
            complaint_id=complaint.id,
            complaint_public_id=complaint.complaint_id,
            event_type=EVENT_HUMAN_RESOLUTION_REVIEW,
            payload=review_payload,
            unique_key=f"human_review_{latest_ver.id}_{int(latest_ver.reviewed_at.timestamp() if latest_ver.reviewed_at else 0)}",
            db=db,
            user_id=officer_user_id,
        )
    except Exception:
        # Resilient design: Blockchain errors must NEVER fail human review recording
        pass

    return latest_ver

