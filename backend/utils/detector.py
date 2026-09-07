import cv2
import numpy as np
from ultralytics import YOLO
from pathlib import Path
import time
import base64
from io import BytesIO
from PIL import Image
from .preprocessing import preprocess_pipeline, pil_to_numpy

class PersonDetector:
    def __init__(self, model_name="yolov8n.pt"):
        self.model = YOLO(model_name)
        self.conf_threshold = 0.15
    
    def detect(self, image_source):
        """
        Detect people in an image.
        Args:
            image_source: numpy array, file path, or PIL Image
        
        Returns:
            dict with detections, count, and inference time
        """
        # Preprocess image
        if isinstance(image_source, str):
            img = cv2.imread(image_source)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        elif isinstance(image_source, Image.Image):
            img = pil_to_numpy(image_source)
        else:
            img = image_source.copy()
        
        img = preprocess_pipeline(img, max_dim=1280, enhance=True, normalize=False)
        
        start_time = time.time()
        
        # Run inference
        results = self.model(img, conf=self.conf_threshold, iou=0.4)
        inference_time = time.time() - start_time
        
        detections = []
        count = 0
        confidences = []
        
        for result in results:
            for box in result.boxes:
                class_id = int(box.cls)
                # Class 0 is 'person' in COCO dataset
                if class_id == 0:
                    count += 1
                    conf = float(box.conf)
                    confidences.append(conf)
                    
                    # Get box coordinates
                    x1, y1, x2, y2 = box.xyxy[0]
                    detections.append({
                        "x1": float(x1),
                        "y1": float(y1),
                        "x2": float(x2),
                        "y2": float(y2),
                        "confidence": conf,
                        "class": "person"
                    })
        
        avg_confidence = np.mean(confidences) if confidences else 0.0
        
        return {
            "count": count,
            "detections": detections,
            "average_confidence": float(avg_confidence),
            "inference_time": inference_time
        }
    
    def annotate_image(self, image_source, detections):
        """Add bounding boxes to image"""
        if isinstance(image_source, str):
            img = cv2.imread(image_source)
        elif isinstance(image_source, np.ndarray):
            img = image_source.copy()
        else:
            img = np.array(image_source)
        
        for det in detections:
            x1, y1 = int(det["x1"]), int(det["y1"])
            x2, y2 = int(det["x2"]), int(det["y2"])
            conf = det["confidence"]
            
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(img, f"{conf:.2f}", (x1, y1 - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        return img
    
    def image_to_base64(self, image_array):
        """Convert image array to base64"""
        _, buffer = cv2.imencode('.jpg', image_array)
        return base64.b64encode(buffer).decode('utf-8')
