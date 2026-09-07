import base64
import io
import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from backend.main import app


class FakeDetector:
    """Stand-in for PersonDetector that returns fixed results without a model."""

    def detect(self, image_array):
        return {
            "count": 2,
            "detections": [
                {"x1": 10, "y1": 10, "x2": 50, "y2": 80, "confidence": 0.95, "class": "person"},
                {"x1": 60, "y1": 20, "x2": 90, "y2": 70, "confidence": 0.81, "class": "person"},
            ],
            "average_confidence": 0.88,
            "inference_time": 0.05,
        }

    def annotate_image(self, image_array, detections):
        if isinstance(image_array, np.ndarray):
            return image_array.copy()
        return np.array(image_array)

    def image_to_base64(self, image_array):
        buf = io.BytesIO()
        Image.fromarray(image_array).save(buf, format="JPEG")
        return base64.b64encode(buf.getvalue()).decode()


class FakeStorage:
    """In-memory stand-in for DetectionStorage."""

    def __init__(self):
        self.records = []

    def save_detection(self, detection_result):
        record = dict(detection_result)
        record["timestamp"] = "2026-01-01T12:00:00"
        self.records.append(record)
        return record

    def load_all(self):
        return self.records

    def load_by_date(self, date_str):
        return [r for r in self.records if r["timestamp"].startswith(date_str)]

    def reset(self):
        self.records = []


@pytest.fixture()
def fake_detector(monkeypatch):
    detector = FakeDetector()
    monkeypatch.setattr("backend.main.PersonDetector", lambda: detector)
    return detector


@pytest.fixture()
def fake_storage(monkeypatch):
    storage = FakeStorage()
    monkeypatch.setattr("backend.main.DetectionStorage", lambda: storage)
    return storage


@pytest.fixture()
def client(fake_detector, fake_storage):
    # TestClient triggers the lifespan (startup/shutdown), which reads the
    # patched PersonDetector/DetectionStorage factories set above. Depending on
    # the fakes here guarantees the patches are in place before startup runs.
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def sample_image():
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), color=(60, 60, 60)).save(buf, format="PNG")
    buf.seek(0)
    return buf


@pytest.fixture()
def jpeg_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (320, 240), color=(128, 128, 128)).save(buf, format="JPEG")
    return buf.getvalue()