from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from ..utils.storage import DetectionStorage
from ..models.record import HistoryResponse, ResetResponse, ErrorResponse

router = APIRouter(prefix="/api", tags=["history"])

@router.get("/history", response_model=HistoryResponse, responses={400: {"model": ErrorResponse}})
async def get_history(date: str = Query(None), limit: int = Query(100)):
    """
    Retrieve detection history.
    Args:
        date: Optional filter by date (YYYY-MM-DD)
        limit: Maximum number of records to return
    """
    storage = request.app.state.storage

    if date:
        detections = storage.load_by_date(date)
    else:
        detections = storage.load_all()
    
    # Apply limit (limit <= 0 returns no records)
    detections = detections[-limit:] if limit > 0 else []
    
    return JSONResponse({
        "success": True,
        "count": len(detections),
        "detections": detections
    })

@router.delete("/history", response_model=ResetResponse, responses={400: {"model": ErrorResponse}})
async def reset_history():
    """Clear all detection history"""
    storage = request.app.state.storage
    storage.reset()
    
    return JSONResponse({
        "success": True,
        "message": "Detection history cleared"
    })
