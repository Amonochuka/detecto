import json
from datetime import datetime
from pathlib import Path

class DetectionStorage:
    def __init__(self, storage_file="detections.json"):
        self.storage_file = Path(storage_file)
        self.init_storage()
    
    def init_storage(self):
        """Initialize storage file if it doesn't exist"""
        if not self.storage_file.exists():
            self.storage_file.write_text(json.dumps([]))
    
    def save_detection(self, detection_result):
        """Save detection result with timestamp"""
        detections = self.load_all()
        
        record = {
            "timestamp": datetime.now().isoformat(),
            "count": detection_result["count"],
            "average_confidence": detection_result["average_confidence"],
            "inference_time": detection_result["inference_time"],
            "detections": detection_result["detections"]
        }
        
        detections.append(record)
        self.storage_file.write_text(json.dumps(detections, indent=2))
        
        return record
    
    def load_all(self):
        """Load all detection records"""
        if self.storage_file.exists():
            return json.loads(self.storage_file.read_text())
        return []
    
    def load_by_date(self, date_str):
        """Load detections for a specific date (YYYY-MM-DD)"""
        all_detections = self.load_all()
        return [d for d in all_detections if d["timestamp"].startswith(date_str)]
    
    def reset(self):
        """Clear all detection history"""
        self.storage_file.write_text(json.dumps([]))
