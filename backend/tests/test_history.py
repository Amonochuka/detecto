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


def test_export_history_csv(client, seeded_storage):
    response = client.get("/api/export", params={"format": "csv"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]

    text = response.text
    lines = text.strip().splitlines()
    assert lines[0].startswith("timestamp,count,average_confidence,inference_time")
    assert len(lines) == 3  # 1 header + 1 record x 2 boxes
    assert "2026-01-01T12:00:00" in lines[1]
    assert lines[1].endswith("person")


def test_export_history_csv_empty(client, fake_storage):
    response = client.get("/api/export")
    assert response.status_code == 200
    lines = response.text.strip().splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("timestamp,count")


def test_export_history_unsupported_format(client, seeded_storage):
    response = client.get("/api/export", params={"format": "json"})
    assert response.status_code == 400
    assert response.json()["success"] is False