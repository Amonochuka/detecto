from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import numpy as np
from PIL import Image
import io
from ..utils.detector import PersonDetector
from ..utils.storage import DetectionStorage
from ..models.record import DetectResponse, ErrorResponse

router = APIRouter(prefix="/api", tags=["detection"])

detector = PersonDetector("yolov8s.pt")
storage = DetectionStorage()

@router.post("/detect", response_model=DetectResponse, responses={400: {"model": ErrorResponse}})
async def detect_people(file: UploadFile = File(...)):
    """
    Detect people in an uploaded image.
    Returns: count, bounding boxes, confidence scores, and annotated image.
    """
    try:
        # Read uploaded file
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        image_array = np.array(image)
        
        # Run detection
        result = detector.detect(image_array)
        
        # Save to storage
        storage.save_detection(result)
        
        # Annotate image
        annotated = detector.annotate_image(image_array, result["detections"])
        annotated_base64 = detector.image_to_base64(annotated)
        
        return JSONResponse({
            "success": True,
            "count": result["count"],
            "average_confidence": result["average_confidence"],
            "inference_time": result["inference_time"],
            "detections": result["detections"],
            "annotated_image": annotated_base64
        })
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
