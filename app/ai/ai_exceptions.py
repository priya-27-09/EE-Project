"""
Custom exceptions for the AI Inference Service.
"""

class AIInferenceException(Exception):
    """Base exception for all AI inference-related errors."""
    def __init__(self, message: str, error_code: str = "AI_INFERENCE_ERROR"):
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class AIModelNotAvailableException(AIInferenceException):
    """Raised when no trained YOLO model is currently active in PostgreSQL."""
    def __init__(
        self,
        message: str = "No trained AI model is currently active. Please complete dataset preparation and YOLO training.",
    ):
        super().__init__(message, error_code="AI_MODEL_NOT_AVAILABLE")


class AINoDetectionException(AIInferenceException):
    """Raised when YOLO inference produces no detections meeting confidence threshold."""
    def __init__(
        self,
        message: str = "No civic issue detected in the provided image with sufficient confidence.",
    ):
        super().__init__(message, error_code="AI_NO_DETECTION")


class InvalidImageException(AIInferenceException):
    """Raised when uploaded file is not an image or fails validation constraints."""
    def __init__(self, message: str = "Uploaded file failed image validation."):
        super().__init__(message, error_code="INVALID_IMAGE")


class CorruptedImageException(AIInferenceException):
    """Raised when uploaded image cannot be parsed or verified by Pillow/OpenCV."""
    def __init__(self, message: str = "Uploaded image file is corrupted or unreadable."):
        super().__init__(message, error_code="CORRUPTED_IMAGE")


class InferenceFailedException(AIInferenceException):
    """Raised when Ultralytics YOLO execution fails unexpectedly."""
    def __init__(self, message: str = "YOLO inference execution failed."):
        super().__init__(message, error_code="INFERENCE_FAILED")
