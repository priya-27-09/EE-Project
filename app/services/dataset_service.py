import os
import io
import re
import json
import shutil
import zipfile
import tarfile
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Tuple, Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.config import settings
from app.models.dataset import DatasetVersion, DatasetStatus
from app.services.dataset_validator import YOLODatasetValidator, YOLOValidationResult

DATASET_ROOT = settings.BASE_DIR / "dataset"
DATASET_VERSIONS_DIR = DATASET_ROOT / "versions"
DATASET_VERSIONS_DIR.mkdir(parents=True, exist_ok=True)

MAX_DATASET_UPLOAD_SIZE = 500 * 1024 * 1024  # 500 MB

DANGEROUS_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".sh", ".ps1", ".vbs", ".dll", ".so", ".com", ".msi", ".jar", ".bin"
}


def generate_dataset_version_id(db: Session) -> str:
    """
    Generate unique dataset version identifier in the format:
    DS-YYYY-XXXXXX (e.g. DS-2026-000001)
    """
    current_year = datetime.now(timezone.utc).year
    prefix = f"DS-{current_year}-"

    latest = (
        db.query(DatasetVersion)
        .filter(DatasetVersion.dataset_version.like(f"{prefix}%"))
        .order_by(desc(DatasetVersion.id))
        .first()
    )

    if latest and latest.dataset_version.startswith(prefix):
        try:
            current_seq = int(latest.dataset_version.split("-")[-1])
            new_seq = current_seq + 1
        except ValueError:
            new_seq = 1
    else:
        new_seq = 1

    # Ensure sequence doesn't collide with existing directory on disk
    while (DATASET_VERSIONS_DIR / f"{prefix}{new_seq:06d}").exists():
        new_seq += 1

    return f"{prefix}{new_seq:06d}"


def compute_bytes_sha256(data: bytes) -> str:
    """Compute SHA-256 hash of raw bytes."""
    return hashlib.sha256(data).hexdigest()


class SafeArchiveExtractor:
    """
    Extracts ZIP/TAR archives while preventing:
    - Path traversal (Zip Slip / relative paths / absolute paths)
    - Executable files
    - Overwriting target directory
    """

    @staticmethod
    def extract_zip(archive_bytes: bytes, target_dir: Path) -> List[str]:
        target_dir = target_dir.resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        extracted_files = []

        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
            for member in zf.infolist():
                filename = member.filename
                # Path traversal checks
                if ".." in filename or filename.startswith("/") or filename.startswith("\\"):
                    raise ValueError(f"Unsafe path traversal attempt detected in archive member: '{filename}'")

                # Disallow drive letters
                if re.match(r"^[a-zA-Z]:", filename):
                    raise ValueError(f"Unsafe absolute path detected in archive member: '{filename}'")

                member_path = Path(filename)
                ext = member_path.suffix.lower()
                if ext in DANGEROUS_EXTENSIONS:
                    raise ValueError(f"Unsupported/executable file type rejected in archive: '{filename}'")

                # Resolve and verify destination is within target_dir
                destination = (target_dir / member_path).resolve()
                if not destination.is_relative_to(target_dir):
                    raise ValueError(f"Extracted path points outside dataset directory: '{filename}'")

                if member.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src, open(destination, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    extracted_files.append(str(destination))

        SafeArchiveExtractor._normalize_root(target_dir)
        return extracted_files

    @staticmethod
    def _normalize_root(target_dir: Path):
        """
        If the archive was packed inside a single top-level folder (e.g. my_dataset/data.yaml),
        promote contents to target_dir if data.yaml is not at the target_dir root.
        """
        yaml_at_root = (target_dir / "data.yaml").exists()
        if yaml_at_root:
            return

        subdirs = [p for p in target_dir.iterdir() if p.is_dir()]
        if len(subdirs) == 1:
            nested_dir = subdirs[0]
            if (nested_dir / "data.yaml").exists():
                # Move all contents of nested_dir to target_dir
                for item in nested_dir.iterdir():
                    shutil.move(str(item), str(target_dir / item.name))
                nested_dir.rmdir()


class DatasetService:
    """
    High-level service managing dataset versions in disk storage and PostgreSQL.
    """

    @staticmethod
    def create_dataset_from_upload(
        db: Session,
        archive_bytes: bytes,
        archive_filename: str,
        dataset_name: str,
        description: Optional[str],
        user_id: int,
        auto_validate: bool = True,
    ) -> Tuple[DatasetVersion, Dict[str, Any]]:
        if len(archive_bytes) > MAX_DATASET_UPLOAD_SIZE:
            raise ValueError(f"Dataset archive exceeds maximum allowed size of {MAX_DATASET_UPLOAD_SIZE // (1024*1024)} MB.")

        if not archive_filename.lower().endswith((".zip", ".tar", ".tar.gz", ".tgz")):
            raise ValueError("Unsupported archive format. Please upload a .zip or .tar archive.")

        # Compute archive SHA-256
        archive_sha256 = compute_bytes_sha256(archive_bytes)

        # Generate unique dataset version ID
        dataset_version = generate_dataset_version_id(db)
        version_dir = DATASET_VERSIONS_DIR / dataset_version

        if version_dir.exists():
            raise ValueError(f"Dataset version directory already exists: {version_dir}")

        version_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Safe archive extraction
            if archive_filename.lower().endswith(".zip"):
                SafeArchiveExtractor.extract_zip(archive_bytes, version_dir)
            else:
                # tarfile support
                with tarfile.open(fileobj=io.BytesIO(archive_bytes)) as tar:
                    for member in tar.getmembers():
                        if ".." in member.name or member.name.startswith("/") or member.name.startswith("\\"):
                            raise ValueError(f"Unsafe path detected in tar member: {member.name}")
                        ext = Path(member.name).suffix.lower()
                        if ext in DANGEROUS_EXTENSIONS:
                            raise ValueError(f"Unsupported executable in tar member: {member.name}")
                    tar.extractall(path=version_dir)
                SafeArchiveExtractor._normalize_root(version_dir)

            # Record initial metadata on disk
            metadata = {
                "dataset_version": dataset_version,
                "dataset_name": dataset_name,
                "description": description or "",
                "uploaded_by": user_id,
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "dataset_sha256": archive_sha256,
                "original_filename": archive_filename,
                "storage_path": str(version_dir),
            }
            with open(version_dir / "metadata.json", "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)

            # Create PostgreSQL record
            dataset_record = DatasetVersion(
                dataset_version=dataset_version,
                dataset_name=dataset_name,
                description=description,
                uploaded_by=user_id,
                storage_path=str(version_dir),
                dataset_sha256=archive_sha256,
                status=DatasetStatus.UPLOADED,
            )
            db.add(dataset_record)
            db.commit()
            db.refresh(dataset_record)

            # Run validation if requested
            validation_data = {}
            if auto_validate:
                validation_data = DatasetService.validate_dataset(db, dataset_version)

            return dataset_record, validation_data

        except Exception as exc:
            # Clean up on failure
            if version_dir.exists():
                shutil.rmtree(version_dir, ignore_errors=True)
            db.rollback()
            raise exc

    @staticmethod
    def validate_dataset(db: Session, dataset_version: str) -> Dict[str, Any]:
        """
        Validate dataset version on disk and update database record.
        """
        dataset = db.query(DatasetVersion).filter(DatasetVersion.dataset_version == dataset_version).first()
        if not dataset:
            raise ValueError(f"Dataset version '{dataset_version}' not found.")

        dataset_dir = Path(dataset.storage_path)
        if not dataset_dir.exists():
            dataset.status = DatasetStatus.INVALID
            db.commit()
            raise ValueError(f"Dataset directory '{dataset_dir}' does not exist on disk.")

        # Update status to VALIDATING
        dataset.status = DatasetStatus.VALIDATING
        db.commit()

        # Run validation engine
        validator = YOLODatasetValidator(dataset_dir, dataset_version)
        result = validator.validate()
        report_dict = result.to_dict()

        # Write validation_report.json to disk
        report_path = dataset_dir / "validation_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, indent=2)

        # Update PostgreSQL dataset record with exact statistics
        dataset.status = result.status
        dataset.train_image_count = result.summary["train_images"]
        dataset.val_image_count = result.summary["val_images"]
        dataset.test_image_count = result.summary["test_images"]
        dataset.total_image_count = result.summary["total_images"]
        dataset.total_object_count = result.summary["total_objects"]
        dataset.class_count = result.summary["class_count"]
        dataset.validation_summary = report_dict
        dataset.validation_report_path = str(report_path)
        dataset.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(dataset)
        return report_dict

    @staticmethod
    def get_validation_report(db: Session, dataset_version: str) -> Dict[str, Any]:
        """Fetch validation report from database or disk."""
        dataset = db.query(DatasetVersion).filter(DatasetVersion.dataset_version == dataset_version).first()
        if not dataset:
            raise ValueError(f"Dataset version '{dataset_version}' not found.")

        if dataset.validation_summary:
            return dataset.validation_summary

        report_path = Path(dataset.storage_path) / "validation_report.json"
        if report_path.exists():
            with open(report_path, "r", encoding="utf-8") as f:
                return json.load(f)

        return {"error": "Validation report not yet generated."}
