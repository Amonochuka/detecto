from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class DetectionBox(BaseModel):
    x1: float = Field(..., description="Left coordinate")
    y1: float = Field(..., description="Top coordinate")
    x2: float = Field(..., description="Right coordinate")
    y2: float = Field(..., description="Bottom coordinate")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    class_name: str = Field(default="person", description="Object class")


class DetectRequest(BaseModel):
    image_base64: Optional[str] = Field(None, description="Base64 encoded image")


class DetectResponse(BaseModel):
    success: bool
    count: int
    average_confidence: float
    inference_time: float
    detections: List[DetectionBox]
    annotated_image: Optional[str] = Field(None, description="Base64 encoded annotated image")


class HistoryRecord(BaseModel):
    timestamp: datetime
    count: int
    average_confidence: float
    inference_time: float
    detections: List[DetectionBox]


class HistoryResponse(BaseModel):
    success: bool
    count: int
    detections: List[HistoryRecord]


class ResetResponse(BaseModel):
    success: bool
    message: str


class ErrorResponse(BaseModel):
    success: bool = False
    detail: str