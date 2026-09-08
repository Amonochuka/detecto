from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from ..models.record import HistoryResponse, ErrorResponse

router = APIRouter(prefix="/api", tags=["history"])

@router.get("/history", response_model=HistoryResponse, responses={400: {"model": ErrorResponse}})
async def get_history(request: Request, date: str = Query(None), limit: int = Query(100)):
    """
    Retrieve detection history.
    Args:
        date: Optional filter by date (YYYY-MM-DD)
        limit: Maximum number of records to return
    """
    storage = request.app.state.storage

    if date:
        detections = storage.get_by_date(date)
    else:
        detections = storage.get_all(limit=limit)
    
    return JSONResponse({
        "success": True,
        "count": len(detections),
        "detections": detections
    })

@router.post("/reset")
async def reset_history(request: Request):
    """Clear all detection history."""
    storage = request.app.state.storage
    storage.clear()
    
    return JSONResponse({
        "success": True,
        "message": "Detection history cleared"
    })
