import os
import uuid
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.evidence import ComplaintEvidence

# Storage directory configuration
UPLOAD_BASE_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "evidence"

# File limits and specifications
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024   # 10 MB
MAX_AUDIO_SIZE_BYTES = 20 * 1024 * 1024   # 20 MB
MAX_VIDEO_SIZE_BYTES = 50 * 1024 * 1024   # 50 MB

ALLOWED_EXTENSIONS = {
    # Images
    "jpg": ("image/jpeg", "image", MAX_IMAGE_SIZE_BYTES),
    "jpeg": ("image/jpeg", "image", MAX_IMAGE_SIZE_BYTES),
    "png": ("image/png", "image", MAX_IMAGE_SIZE_BYTES),
    "webp": ("image/webp", "image", MAX_IMAGE_SIZE_BYTES),
    # Audio
    "wav": ("audio/wav", "audio", MAX_AUDIO_SIZE_BYTES),
    "mp3": ("audio/mpeg", "audio", MAX_AUDIO_SIZE_BYTES),
    "m4a": ("audio/x-m4a", "audio", MAX_AUDIO_SIZE_BYTES),
    # Video & WebM
    "mp4": ("video/mp4", "video", MAX_VIDEO_SIZE_BYTES),
    "mov": ("video/quicktime", "video", MAX_VIDEO_SIZE_BYTES),
    "avi": ("video/x-msvideo", "video", MAX_VIDEO_SIZE_BYTES),
    "webm": ("video/webm", "video", MAX_VIDEO_SIZE_BYTES),
}

ALLOWED_MIME_PREFIXES = ("image/", "video/", "audio/")


def get_upload_dir() -> Path:
    """Ensure and return the dated upload directory structure YYYY/MM."""
    now = datetime.now(timezone.utc)
    target_dir = UPLOAD_BASE_DIR / str(now.year) / f"{now.month:02d}"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def sanitize_and_validate_file(file: UploadFile) -> Tuple[str, str, int]:
    """
    Validate file extension, MIME type, and return normalized (extension, mime_type, max_size).
    Raises HTTPException(400) on unsupported file type.
    """
    original_name = file.filename or ""
    if not original_name or "." not in original_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must include a valid extension.",
        )

    ext = original_name.rsplit(".", 1)[-1].lower().strip()
    if ext not in ALLOWED_EXTENSIONS:
        supported = sorted(list(ALLOWED_EXTENSIONS.keys()))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '.{ext}'. Supported extensions are: {', '.join(supported)}",
        )

    expected_mime, media_category, max_size = ALLOWED_EXTENSIONS[ext]
    detected_mime = (file.content_type or "").lower().strip()

    # If MIME type is supplied, verify it matches the general media type
    if detected_mime and not any(detected_mime.startswith(prefix) for prefix in ALLOWED_MIME_PREFIXES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid MIME type '{detected_mime}'. Only image, video, and audio files are supported.",
        )

    final_mime = detected_mime if detected_mime else expected_mime
    return ext, final_mime, max_size


def save_evidence_file(
    file: UploadFile,
    complaint_id: int,
    uploaded_by: int,
    db: Session,
) -> ComplaintEvidence:
    """
    Securely stream and save uploaded evidence to disk.
    - Validates extension, MIME type, and size limit.
    - Generates safe UUID server-side filename (prevents path traversal).
    - Calculates SHA-256 hash.
    - Persists file path and SHA-256 hash in ComplaintEvidence table.
    - Strict requirement: NEVER stores binary data in PostgreSQL.
    """
    ext, mime_type, max_size = sanitize_and_validate_file(file)

    upload_dir = get_upload_dir()
    safe_filename = f"{uuid.uuid4().hex}.{ext}"
    destination_path = upload_dir / safe_filename

    # Prevent path traversal: ensure destination is inside UPLOAD_BASE_DIR
    try:
        destination_path.resolve().relative_to(UPLOAD_BASE_DIR.resolve())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Security violation: Path traversal detected.",
        )

    sha256 = hashlib.sha256()
    total_bytes = 0
    first_chunk = True

    # Stream file to disk and compute SHA-256 simultaneously
    try:
        with open(destination_path, "wb") as buffer:
            while chunk := file.file.read(64 * 1024):  # 64 KB chunks
                if first_chunk:
                    first_chunk = False
                    # 1. Reject executables and dangerous scripts regardless of extension/MIME
                    if chunk.startswith(b"MZ") or chunk.startswith(b"\x7fELF"):
                        buffer.close()
                        if destination_path.exists():
                            destination_path.unlink()
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Disallowed executable binary file format detected.",
                        )
                    if chunk.startswith((b"<?php", b"<!DOCTYPE", b"<script", b"#!")):
                        buffer.close()
                        if destination_path.exists():
                            destination_path.unlink()
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Disallowed script or markup file content detected.",
                        )

                    # 2. If claiming to be an image, verify image magic bytes
                    if ext in ("jpg", "jpeg", "png", "webp"):
                        is_jpeg = chunk.startswith(b"\xff\xd8")
                        is_png = chunk.startswith(b"\x89PNG\r\n\x1a\n")
                        is_webp = chunk.startswith(b"RIFF") and b"WEBP" in chunk[:16]
                        if not (is_jpeg or is_png or is_webp):
                            buffer.close()
                            if destination_path.exists():
                                destination_path.unlink()
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Invalid image binary signature. The uploaded file is not a valid image.",
                            )

                total_bytes += len(chunk)
                if total_bytes > max_size:
                    buffer.close()
                    if destination_path.exists():
                        destination_path.unlink()
                    limit_mb = max_size // (1024 * 1024)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"File exceeds maximum allowed size of {limit_mb} MB.",
                    )
                sha256.update(chunk)
                buffer.write(chunk)

        # 3. Reject empty files
        if total_bytes == 0:
            if destination_path.exists():
                destination_path.unlink()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty (0 bytes).",
            )
    except HTTPException:
        raise
    except Exception as exc:
        if destination_path.exists():
            destination_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to securely save evidence file: {str(exc)}",
        )

    # Relative path from project root for portability (never expose raw absolute server filesystem roots)
    project_root = Path(__file__).resolve().parent.parent.parent
    rel_path = str(destination_path.relative_to(project_root)).replace("\\", "/")
    sha256_hex = sha256.hexdigest()

    # Create database record storing path and SHA-256 hash only
    evidence = ComplaintEvidence(
        complaint_id=complaint_id,
        file_path=rel_path,
        file_type=mime_type,
        sha256_hash=sha256_hex,
        uploaded_by=uploaded_by,
        created_at=datetime.now(timezone.utc),
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    return evidence
