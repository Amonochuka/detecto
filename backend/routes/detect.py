from fastapi import APIRouter, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse
import numpy as np
from PIL import Image, UnidentifiedImageError
import io
from ..utils.detector import PersonDetector
from ..utils.storage import DetectionStorage
from ..models.record import DetectResponse, ErrorResponse

from ..utils.perf_log import log_detection

router = APIRouter(prefix="/api", tags=["detection"])

detector = PersonDetector("yolov8s.pt")
storage = DetectionStorage()

@router.post("/detect", response_model=DetectResponse, responses={400: {"model": ErrorResponse}})
async def detect_people(file: UploadFile = File(...)):
    """
    Detect people in an uploaded image.
    Returns: count, bounding boxes, confidence scores, and annotated image.
    """
    detector = request.app.state.detector
    storage = request.app.state.storage

    # Reject unsupported content types before reading the file
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.content_type}'. "
                   f"Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}."
        )

    # Reject empty uploads
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Reject oversized images
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Image exceeds the 15 MB size limit.")

    # Reject corrupt / non-image payloads (file signature validation)
    try:
        image = Image.open(io.BytesIO(contents))
        image.load()
        image = image.convert("RGB")
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image.")
    except Exception:
        raise HTTPException(status_code=400, detail="Uploaded file could not be decoded as an image.")

    image_array = np.array(image)

    # Run detection
    result = detector.detect(image_array)

    # Log performance metrics
    log_detection(result["count"], result["average_confidence"], result["inference_time"])

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
