import pytest


@pytest.fixture()
def seeded_storage(fake_storage, client):
    """Populate history with a detection record via the API."""
    from PIL import Image
    import io

    buf = io.BytesIO()
    Image.new("RGB", (320, 240), color=(10, 10, 10)).save(buf, format="PNG")
    client.post("/api/detect", files={"file": ("a.png", buf.getvalue(), "image/png")})
    return fake_storage


def test_history_empty(client, fake_storage):
    response = client.get("/api/history")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["count"] == 0
    assert body["detections"] == []


def test_history_after_detection(client, seeded_storage):
    response = client.get("/api/history")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["detections"][0]["count"] == 2


def test_history_date_filter(client, seeded_storage):
    no_match = client.get("/api/history", params={"date": "1999-01-01"})
    assert no_match.json()["count"] == 0

    match = client.get("/api/history", params={"date": "2026-01-01"})
    assert match.json()["count"] == 1


def test_history_limit(client, seeded_storage):
    response = client.get("/api/history", params={"limit": 0})
    assert response.json()["count"] == 0


def test_reset_history_clears(client, seeded_storage):
    response = client.post("/api/reset")
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert client.get("/api/history").json()["count"] == 0