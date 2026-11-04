"""
AI Inference Package for AI Civic Guardian.
Provides real Ultralytics YOLO object detection, model caching,
canonical civic issue mapping, severity assessment, and department routing.
"""

from app.ai.ai_exceptions import (
    AIInferenceException,
    AIModelNotAvailableException,
    AINoDetectionException,
    InvalidImageException,
    CorruptedImageException,
    InferenceFailedException,
)
from app.ai.model_loader import ModelLoader
from app.ai.detection_service import DetectionService
from app.ai.inference_service import AIInferenceService
from app.ai.schemas import (
    AIInferenceSuccessResponse,
    AIInferenceErrorResponse,
    DetectionItem,
    IssueDetection,
)

__all__ = [
    "AIInferenceException",
    "AIModelNotAvailableException",
    "AINoDetectionException",
    "InvalidImageException",
    "CorruptedImageException",
    "InferenceFailedException",
    "ModelLoader",
    "DetectionService",
    "AIInferenceService",
    "AIInferenceSuccessResponse",
    "AIInferenceErrorResponse",
    "DetectionItem",
    "IssueDetection",
]
