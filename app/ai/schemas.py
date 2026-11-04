from typing import List, Optional
from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x1: float = Field(..., description="Top-left X coordinate in pixels")
    y1: float = Field(..., description="Top-left Y coordinate in pixels")
    x2: float = Field(..., description="Bottom-right X coordinate in pixels")
    y2: float = Field(..., description="Bottom-right Y coordinate in pixels")


class DetectionItem(BaseModel):
    class_id: int = Field(..., description="Zero-indexed canonical YOLO class ID")
    class_name: str = Field(..., description="Canonical class name")
    confidence: float = Field(..., description="Model prediction confidence score [0.0 - 1.0]")
    bbox: BoundingBox = Field(..., description="Bounding box pixel coordinates")


class IssueDetection(BaseModel):
    class_id: int = Field(..., description="Selected primary civic issue class ID")
    class_name: str = Field(..., description="Selected primary canonical class name")
    confidence: float = Field(..., description="Confidence of primary detection")
    bbox: Optional[BoundingBox] = Field(default=None, description="Primary bounding box")
    issue_type: Optional[str] = Field(default=None, description="Internal complaint issue identifier")


class SeverityInfo(BaseModel):
    level: str = Field(..., description="Determined severity: LOW, MEDIUM, HIGH, or CRITICAL")
    score: Optional[float] = Field(default=None, description="Deterministic severity score if available")
    reason: Optional[str] = Field(default=None, description="Reasoning for the assigned severity")


class DepartmentInfo(BaseModel):
    id: Optional[int] = Field(default=None, description="Database ID of routed department")
    name: str = Field(..., description="Official name of routed department")


class AIInferenceSuccessResponse(BaseModel):
    success: bool = True
    model_version: str
    issue: IssueDetection
    severity: SeverityInfo
    department: DepartmentInfo
    detections: List[DetectionItem] = []


class AIInferenceErrorResponse(BaseModel):
    success: bool = False
    error_code: str
    message: str
    model_version: Optional[str] = None
    detections: List[DetectionItem] = []


class AIDemoInferenceSuccessResponse(BaseModel):
    success: bool = True
    is_demo: bool = True
    is_experimental: bool = True
    is_production_ready: bool = False
    model_version: str
    weights_path: str
    issue: IssueDetection
    severity: SeverityInfo
    department: DepartmentInfo
    detections: List[DetectionItem] = []
    is_unvalidated_class: bool = False
    warning: Optional[str] = None
    note: str = "Experimental baseline demo inference only. Not validated for production."


class AIDemoInferenceErrorResponse(BaseModel):
    success: bool = False
    is_demo: bool = True
    error_code: str
    message: str
    model_version: Optional[str] = None
    detections: List[DetectionItem] = []

