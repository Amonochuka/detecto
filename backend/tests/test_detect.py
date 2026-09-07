from fastapi.testclient import TestClient


def test_detect_valid_image(client, sample_image, fake_storage):
    response = client.post(
        "/api/detect",
        files={"file": ("person.png", sample_image.getvalue(), "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["count"] == 2
    assert len(body["detections"]) == 2
    assert body["average_confidence"] == 0.88
    assert body["inference_time"] == 0.05
    assert body["annotated_image"]
    # Detection should be persisted
    assert len(fake_storage.records) == 1


def test_detect_unsupported_content_type(client, sample_image):
    response = client.post(
        "/api/detect",
        files={"file": ("doc.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 415
    assert "Unsupported file type" in response.json()["detail"]


def test_detect_empty_upload(client):
    response = client.post(
        "/api/detect",
        files={"file": ("empty.png", b"", "image/png")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_detect_corrupt_image(client):
    response = client.post(
        "/api/detect",
        files={"file": ("fake.png", b"definitely not a real image", "image/png")},
    )
    assert response.status_code == 400


def test_detect_missing_file(client):
    response = client.post("/api/detect")
    assert response.status_code == 422


def test_detect_oversized_image(client, monkeypatch):
    # Simulate a payload over the 15 MB limit
    import backend.routes.detect as detect_module

    monkeypatch.setattr(detect_module, "MAX_FILE_SIZE", 1024)
    oversized = b"\x00" * 2048
    response = client.post(
        "/api/detect",
        files={"file": ("big.png", oversized, "image/png")},
    )
    assert response.status_code == 413