import io
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image

from app.services.dataset_validator import CANONICAL_CLASSES
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
)
from app.ai.ai_exceptions import (
    InvalidImageException,
    CorruptedImageException,
    AINoDetectionException,
    InferenceFailedException,
)
from app.ai.schemas import BoundingBox, DetectionItem, IssueDetection

# Maximum allowed image upload size: 10 MB
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
SUPPORTED_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/bmp",
}

# Strict 1-to-1 mapping from zero-indexed canonical class ID to internal issue type key
CLASS_ID_TO_INTERNAL_ISSUE: Dict[int, str] = {
    0: ISSUE_GARBAGE_OVERFLOW,
    1: ISSUE_ILLEGAL_DUMPING,
    2: ISSUE_POTHOLE,
    3: ISSUE_DAMAGED_ROAD,
    4: ISSUE_WATER_LEAKAGE,
    5: ISSUE_SEWAGE_OVERFLOW,
    6: ISSUE_BROKEN_STREET_LIGHT,
    7: ISSUE_DRAINAGE_PROBLEM,
    8: ISSUE_TRAFFIC_ISSUE,
    9: ISSUE_BUILDING_DAMAGE,
    10: ISSUE_PARK_DAMAGE,
    11: ISSUE_ENVIRONMENTAL_POLLUTION,
}


class DetectionService:
    """
    Handles image validation, Ultralytics YOLO inference execution,
    and deterministic resolution from raw detections to canonical civic issue.
    """

    @staticmethod
    def validate_and_open_image(
        image_bytes: bytes,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> Image.Image:
        """
        Securely validate uploaded image file:
        - Checks size limits (<= 10MB)
        - Rejects zero-byte streams
        - Checks safe filename and extension (prevents path traversal)
        - Validates MIME type if provided
        - Verifies stream integrity via Pillow img.verify()
        - Decodes safely into an RGB PIL Image

        Never executes uploaded files or stores raw binary in PostgreSQL.
        """
        if not image_bytes or len(image_bytes) == 0:
            raise InvalidImageException("Uploaded image file is empty (0 bytes).")

        if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
            raise InvalidImageException(
                f"Image size exceeds the maximum allowed limit of {MAX_IMAGE_SIZE_BYTES // (1024 * 1024)} MB."
            )

        if filename:
            # Prevent path traversal in filename
            clean_name = os.path.basename(filename)
            if ".." in filename or "/" in filename or "\\" in filename:
                clean_name = os.path.basename(clean_name)
            ext = Path(clean_name).suffix.lower()
            if ext not in SUPPORTED_IMAGE_EXTENSIONS:
                raise InvalidImageException(
                    f"Unsupported image extension '{ext}'. Supported extensions: {sorted(list(SUPPORTED_IMAGE_EXTENSIONS))}"
                )

        if content_type:
            clean_mime = content_type.strip().lower()
            if clean_mime not in SUPPORTED_MIME_TYPES and not clean_mime.startswith("image/"):
                raise InvalidImageException(
                    f"Unsupported image MIME type '{content_type}'. Must be one of: {sorted(list(SUPPORTED_MIME_TYPES))}"
                )

        # 1. Verify file header & structure with Pillow
        try:
            stream = io.BytesIO(image_bytes)
            with Image.open(stream) as probe:
                probe.verify()
        except Exception as exc:
            raise CorruptedImageException(
                f"Image verification failed: file is corrupted or not a valid image ({str(exc)})."
            )

        # 2. Decode and convert to standard RGB raster for Ultralytics
        try:
            stream = io.BytesIO(image_bytes)
            img = Image.open(stream)
            fmt = (img.format or "").upper()
            if fmt not in ["JPEG", "PNG", "WEBP", "BMP"]:
                raise InvalidImageException(f"Unsupported image format: '{fmt}'.")

            # Safely convert RGBA, Grayscale, or CMYK to RGB
            img_rgb = img.convert("RGB")
            # Force raster load into memory so stream can close
            img_rgb.load()
            return img_rgb
        except (InvalidImageException, CorruptedImageException):
            raise
        except Exception as exc:
            raise CorruptedImageException(f"Failed to decode image data into raster: {str(exc)}")

    @staticmethod
    def run_inference(
        model: Any,
        image: Image.Image,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        img_size: int = 640,
    ) -> List[DetectionItem]:
        """
        Run real Ultralytics YOLO inference on the validated PIL Image.
        Returns all detections meeting the confidence threshold.
        """
        if not (0.01 <= conf_threshold <= 1.0):
            conf_threshold = 0.25
        if not (0.01 <= iou_threshold <= 1.0):
            iou_threshold = 0.45

        try:
            results = model.predict(
                source=image,
                conf=conf_threshold,
                iou=iou_threshold,
                imgsz=img_size,
                verbose=False,
            )

            detections: List[DetectionItem] = []
            for r in results:
                boxes = r.boxes
                if boxes is None:
                    continue
                for box in boxes:
                    c_id = int(box.cls[0].item())
                    conf = float(box.conf[0].item())
                    xyxy = [float(x) for x in box.xyxy[0].tolist()]

                    # Use canonical 12 civic classes mapping exactly
                    class_name = CANONICAL_CLASSES.get(c_id, f"Class_{c_id}")

                    detections.append(
                        DetectionItem(
                            class_id=c_id,
                            class_name=class_name,
                            confidence=round(conf, 4),
                            bbox=BoundingBox(
                                x1=round(xyxy[0], 2),
                                y1=round(xyxy[1], 2),
                                x2=round(xyxy[2], 2),
                                y2=round(xyxy[3], 2),
                            ),
                        )
                    )

            return detections
        except Exception as exc:
            raise InferenceFailedException(f"Ultralytics inference failed: {str(exc)}")

    @staticmethod
    def resolve_primary_issue(
        detections: List[DetectionItem],
        model_version: str,
    ) -> IssueDetection:
        """
        Deterministically convert YOLO detections into the primary complaint issue.
        Rules:
        - If no detection passes threshold: raise AINoDetectionException (AI_NO_DETECTION)
        - If one valid detection: use that detection
        - If multiple valid detections: select the highest-confidence valid detection
        """
        if not detections:
            raise AINoDetectionException(
                "No civic issue detected in the provided image with sufficient confidence."
            )

        # Filter only detections that map to canonical classes
        valid_detections = [
            d for d in detections if d.class_id in CANONICAL_CLASSES
        ]

        if not valid_detections:
            raise AINoDetectionException(
                "No recognized civic issue category detected in the provided image."
            )

        # Select highest-confidence detection
        primary = max(valid_detections, key=lambda d: d.confidence)

        internal_issue = CLASS_ID_TO_INTERNAL_ISSUE.get(primary.class_id, "unknown")

        return IssueDetection(
            class_id=primary.class_id,
            class_name=primary.class_name,
            confidence=primary.confidence,
            bbox=primary.bbox,
            issue_type=internal_issue,
        )
