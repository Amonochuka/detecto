from pathlib import Path
from typing import List, Dict, Any
import json
from datetime import datetime

from backend.interfaces.storage import DetectionRepository


class JsonDetectionRepository(DetectionRepository):
    """JSON file implementation of DetectionRepository."""

    def __init__(self, storage_file: Path = None):
        if storage_file is None:
            storage_file = Path(__file__).resolve().parent.parent.parent / "detections.json"
        self.storage_file = Path(storage_file)
        self._init_storage()

    def _init_storage(self):
        if not self.storage_file.exists():
            self.storage_file.write_text(json.dumps([]))

    def save(self, record: Dict[str, Any]) -> Dict[str, Any]:
        detections = self.get_all(limit=10**9)  # load all

        record_with_timestamp = {
            "timestamp": datetime.now().isoformat(),
            "count": record["count"],
            "average_confidence": record["average_confidence"],
            "inference_time": record["inference_time"],
            "detections": record["detections"],
        }

        detections.append(record_with_timestamp)
        self.storage_file.write_text(json.dumps(detections, indent=2))
        return record_with_timestamp

    def get_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        if self.storage_file.exists():
            detections = json.loads(self.storage_file.read_text())
            return detections[-limit:] if limit > 0 else []
        return []

    def get_by_date(self, date: str) -> List[Dict[str, Any]]:
        all_detections = self.get_all(limit=10**9)
        return [d for d in all_detections if d["timestamp"].startswith(date)]

    def clear(self) -> None:
        self.storage_file.write_text(json.dumps([]))