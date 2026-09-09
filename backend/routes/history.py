from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, Response
import csv
import io
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

@router.get("/export")
async def export_history(
    request: Request,
    format: str = Query("csv", description="Export format: 'csv' (Excel-compatible)"),
    date: str = Query(None),
    limit: int = Query(100),
):
    """Export detection history as CSV (bonus feature)."""
    allowed = {"csv", "excel"}
    if format not in allowed:
        return JSONResponse(
            {"success": False, "detail": f"Unsupported format '{format}'. Supported: {', '.join(sorted(allowed))}."},
            status_code=400,
        )

    storage = request.app.state.storage
    if date:
        detections = storage.get_by_date(date)
    else:
        detections = storage.get_all(limit=limit)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "timestamp", "count", "average_confidence", "inference_time",
        "x1", "y1", "x2", "y2", "confidence", "class",
    ])

    for record in detections:
        base = [
            record["timestamp"],
            record["count"],
            record["average_confidence"],
            record["inference_time"],
        ]
        boxes = record.get("detections") or []
        if boxes:
            for box in boxes:
                writer.writerow(base + [
                    box.get("x1", ""), box.get("y1", ""),
                    box.get("x2", ""), box.get("y2", ""),
                    box.get("confidence", ""),
                    box.get("class", "person"),
                ])
        else:
            writer.writerow(base + ["", "", "", "", "", ""])

    filename = "detections.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
