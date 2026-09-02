# Detecto Backend — Full Documentation

This document explains how the Detecto backend works, how to run it, and the design decisions behind it. Read it top to bottom if you're new to the codebase.

---

## 1. What this backend does

Detecto's backend is a **FastAPI** web service that:

1. Accepts an uploaded image (JPEG/PNG) via HTTP.
2. Runs a **YOLOv8 person detector** on it.
3. Returns the number of people, their bounding boxes, and confidence scores.
4. Draws the boxes on the image and returns an annotated copy.
5. Logs every detection with a timestamp for later analysis.
6. Lets you query that history and clear it.

The core flow: **HTTP request → image → YOLO inference → JSON + annotated image → saved to storage.**

---

## 2. Project layout

```
backend/
├── main.py              # FastAPI app, CORS, env loading, startup
├── requirements.txt     # Python dependencies
├── .env.example         # Template for your private .env (committed)
├── routes/
│   ├── __init__.py
│   ├── detect.py        # POST /api/detect
│   └── history.py       # GET /api/history, DELETE /api/history
├── utils/
│   ├── __init__.py
│   ├── detector.py      # YOLOv8 person detection + annotation
│   └── storage.py       # JSON file storage for detection history
├── tests/
│   ├── __init__.py
│   └── test_detect.py   # pytest tests
└── __init__.py          # makes backend a Python package
```

The `__init__.py` files turn `backend/`, `routes/`, `utils/`, and `tests/` into **Python packages**. Without them, the relative imports inside `routes/` and `utils/` (e.g. `from ..utils.detector import PersonDetector`) would fail.

---

## 3. Dependencies and imports explained

Below is every import used across the backend, what it is, and why it's there. Understanding these will make the code far less opaque.

### 3.1 Standard library (built into Python — no install needed)

| Import | Where used | What it's for |
|--------|-----------|---------------|
| `os` | `main.py` | Reads environment variables (`os.getenv`) — how `.env` config reaches the app. |
| `pathlib.Path` | `main.py`, `storage.py` | Path handling — locating the `.env` file, and constructing the storage file path. |
| `time` | `detector.py` | `time.time()` before/after inference to measure `inference_time`. |
| `base64` | `detector.py` | Encodes the annotated JPEG as a base64 string so it can travel inside JSON. |
| `io` / `io.BytesIO` | `routes/detect.py`, `detector.py` | Treats raw uploaded bytes as an in-memory file so PIL can open them without touching disk. |
| `json` | `storage.py` | Serializes/deserializes detection records to the `detections.json` file. |
| `datetime.datetime` | `storage.py` | Produces the ISO `timestamp` attached to every stored detection. |

### 3.2 Direct third-party imports (from `requirements.txt`)

| Import | Package | What it's for in this project |
|--------|---------|-------------------------------|
| `FastAPI`, `APIRouter`, `File`, `UploadFile`, `HTTPException`, `Query` | `fastapi` | The web framework. Creates the app, splits endpoints into routers, validates multipart file uploads, and raises HTTP errors. |
| `CORSMiddleware` | `fastapi` | Allows the React frontend (configured origin) to call the API from the browser. |
| `JSONResponse` | `fastapi` | Returns explicit JSON payloads from the routes. |
| `load_dotenv` | `python-dotenv` | Loads the private `.env` file into environment variables at startup. |
| `np` (numpy) | `numpy` | Converts PIL images to numeric arrays (the format YOLO expects) and computes the mean confidence. |
| `Image` | `pillow` (PIL) | Decodes uploaded bytes into an image object and normalizes to RGB. |
| `cv2` | `opencv-python` | Draws the green bounding boxes and confidence labels (`annotate_image`) and encodes the result to JPEG. |
| `YOLO` | `ultralytics` | Loads the pretrained YOLOv8n model and runs inference — the core detection engine. |
| `uvicorn` | `uvicorn` | The ASGI server that actually serves the FastAPI app over HTTP. |

### 3.3 Transitive dependencies (pulled in by ultralytics / fastapi)

You don't import these directly in the code, but some are pinned in `requirements.txt` (torch/torchvision) to guarantee version compatibility, and others arrive transitively:

- **`torch` / `torchvision`** — PyTorch, the deep-learning runtime that ultralytics/YOLOv8 runs on. This is the giant install (several GB, includes CUDA libs). Explicitly pinned because ultralytics needs a compatible pairing.
- **`matplotlib`** — ultralytics uses it internally for plotting and training visuals. Not pinned (transitive only).
- **`pandas`, `scipy`, `seaborn`** — ultralytics auxiliary tools (dataset stats, plotting). Not pinned (transitive only).
- **`pydantic`** — fastapi's data validation engine for request/response models. Pinned in `requirements.txt`.

### 3.4 Dev / test dependencies

| Import | Package | What it's for |
|--------|---------|---------------|
| `pytest` | `pytest` | Test runner for `backend/tests/`. |
| `httpx` | `httpx` | Async HTTP client used by FastAPI's `TestClient` to call endpoints in tests. |

### 3.5 Why opencv and PIL both touch the image?

They fill different roles:
- **PIL** (`Image`) only *decodes* and normalizes the upload (bytes → RGB image → numpy array).
- **OpenCV** (`cv2`) both *annotates* (rectangles/labels) and *encodes* (numpy → JPEG bytes).

---

## 4. How to run it

### Prerequisites
- Python 3.12+
- A machine capable of running the PyTorch CPU/GPU model (a few GB of RAM/disk).

### First-time setup (only once)

```bash
# from the repo root (detecto/)
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

This installs all backend dependencies (FastAPI, YOLOv8/ultralytics, OpenCV, PyTorch — the last one is several GB).

### Start the server

Run from the **repo root**:

```bash
.venv/bin/uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

> **Important:** Always run from the **repo root**, never `cd backend`. The code uses `backend.routes.*` and `backend.utils.*` imports, which only resolve when `backend` is a package visible on the Python path (i.e. your current directory is the repo root).

On first start the YOLO model loads and `yolov8n.pt` (~6 MB) is auto-downloaded, so the server takes a few extra seconds to become ready.

### Verify it's running

| Check | URL | Expected |
|-------|-----|----------|
| Health | http://localhost:8000/health | `{"status":"healthy"}` |
| Root | http://localhost:8000/ | `{"message":"Detecto API running"}` |
| Interactive API docs (Swagger UI) | http://localhost:8000/docs | clickable interface — safest way to test uploads |

### Test detection with curl

```bash
curl -X POST http://localhost:8000/api/detect -F "file=@/path/to/image.jpg"
```

Returns JSON with `count`, `detections` (bounding boxes + confidence), `inference_time`, and an `annotated_image` (base64). For a zero-dependency way to view the annotated image, open the Swagger UI at `/docs`, expand the `POST /api/detect` endpoint, and upload a file — the response there is easy to browse.

### Reference: verified smoke test (this repo's environment)

The following was verified end-to-end on a CPU machine with the default setup:

| Check | Result |
|-------|--------|
| Server starts and stays up | ✅ |
| `GET /health`, `GET /` | ✅ 200 OK |
| `POST /api/detect` (upload → JSON) | ✅ |
| Detection history recorded per run | ✅ |
| Steady-state inference time | ~1.6 s on CPU with the synthetic test image |

> **Note on performance:** measured steady-state inference is ~1.6 s — slightly above the assignment's ≤1.5 s target on plain CPU. Expect much faster on GPU (`yolov8n` is small and CPU-friendly; try `yolov8s/yolov8m` for accuracy if GPU is available). Benchmark with your real 10+ sample images and record the numbers in the README as required.

---

## 5. Why `.env` and the secrets question

You asked a great question: *"why expose .env variables in main.py yet .env should be private?"*

The key idea is a **separation between the template and the real values**:

| File | Committed? | Purpose |
|------|-----------|---------|
| `.env.example` | ✅ Yes | Documents which config variables exist, with placeholder values. Safe to share. |
| `.env` | ❌ No (gitignored) | Your private real values. **Never commit this.** |
| `main.py` | ✅ Yes | *Reads* the values at runtime via `os.getenv()`. Never contains real secrets itself. |

So `main.py` does not "expose" secrets to the public. It reads private values from `.env` (which stays on your machine) and uses them at runtime. Because `.env` is gitignored, the secrets never reach the repository.

```python
# main.py reads the value; the value itself lives in YOUR private .env
BACKEND_PORT = int(os.getenv("BACKEND_PORT", 8000))   # default only if unset
```

**Honest caveat — the defaults are not secrets.** You'll notice `0.0.0.0`, port `8000`, and `localhost:5173` are also written right in `main.py` as fallback defaults. Those are not sensitive; nothing is being hidden there. The indirection earns its keep only once the app has *real* secrets (an API key, a DB password, a model license). Those go **only** in `.env` and never in code. If you hardcode a secret in code, it gets committed and leaked. The pattern keeps all config flowing through one mechanism so sensitive values are trivially kept out of the repo while non-sensitive defaults stay readable.

- `load_dotenv(...)` loads the `.env` file into environment variables at startup.
- `os.getenv("NAME", default)` returns the value, or `default` if missing.
- If you deploy to a server, you'd set these same variables in the server's environment instead of a file — the code works either way.

This is the universal pattern for keeping credentials out of source control: **code reads config from the environment; secrets live in the environment (or a gitignored file).**

---

## 6. Configuration variables

Defined in `.env` (root of repo):

| Variable        | Default             | Purpose                                    |
|-----------------|---------------------|--------------------------------------------|
| `FASTAPI_ENV`   | `development`       | Runtime environment flag                    |
| `BACKEND_HOST`  | `0.0.0.0`           | Interface the server binds to (all)         |
| `BACKEND_PORT`  | `8000`              | Port the server listens on                  |
| `FRONTEND_URL`  | `http://localhost:5173` | Allowed CORS origin (the React app)     |

---

## 7. The endpoints

### `GET /`
Welcome message. Returns `{"message": "Detecto API running"}`.

### `GET /health`
Health check for monitoring. Returns `{"status": "healthy"}`.

### `POST /api/detect`
Accepts an image file via `multipart/form-data` (field name `file`).

**Request:**
```
curl -X POST http://localhost:8000/api/detect \
  -F "file=@/path/to/image.jpg"
```

**Response (JSON):**
```json
{
  "success": true,
  "count": 2,
  "average_confidence": 0.873,
  "inference_time": 0.184,
  "detections": [
    { "x1": 50, "y1": 60, "x2": 120, "y2": 200, "confidence": 0.91, "class": "person" },
    { "x1": 180, "y1": 90, "x2": 250, "y2": 210, "confidence": 0.83, "class": "person" }
  ],
  "annotated_image": "<base64-encoded JPEG>"
}
```

- `count` — number of detected people.
- `detections` — each person's bounding box (`x1,y1,x2,y2`), confidence, and class.
- `average_confidence` — mean confidence across detections.
- `inference_time` — seconds spent running inference (not network/encoding).
- `annotated_image` — the input image with green boxes + confidence labels, base64-encoded for easy embedding in a web page.

### `GET /api/history?date=YYYY-MM-DD&limit=100`
Returns past detection records from storage.

- `date` (optional) — only records on that day (`timestamp.startswith(date)`).
- `limit` (optional, default 100) — returns the most recent N records.

**Response:**
```json
{
  "success": true,
  "count": 2,
  "detections": [
    { "timestamp": "2026-09-02T12:00:00.123456", "count": 1, "average_confidence": 0.9, "inference_time": 0.18, "detections": [ ... ] }
  ]
}
```

### `DELETE /api/history`
Clears all stored detection history. Returns `{"success": true, "message": "Detection history cleared"}`.

---

## 8. How detection works (`utils/detector.py`)

The `PersonDetector` class wraps the **YOLOv8** model (Ultralytics), the default being `yolov8n.pt` (the small "nano" variant — good speed/accuracy balance for CPU).

```python
class PersonDetector:
    def __init__(self, model_name="yolov8n.pt"):
        self.model = YOLO(model_name)      # loads the pretrained weights
        self.conf_threshold = 0.5          # only keep boxes with confidence >= 0.5
```

Key methods:

- **`detect(image_source)`** — runs the model on a numpy array / file path / PIL image.
  1. Times inference with `time.time()`.
  2. Runs `self.model(image_source, conf=self.conf_threshold)`.
  3. Loops over detected boxes, keeps only **class 0** (person in the COCO dataset).
  4. Collects each box's coordinates and confidence.
  5. Returns a dict: `count`, `detections`, `average_confidence`, `inference_time`.

- **`annotate_image(image_source, detections)`** — draws a green rectangle around each person and writes the confidence score above the box, using OpenCV.

- **`image_to_base64(image_array)`** — encodes the annotated image as a JPEG, then base64, so it can travel inside JSON.

The first time you run it, Ultralytics downloads `yolov8n.pt` (~6 MB) automatically.

### 8.1 What the bounding boxes are and why they matter

A bounding box (bbox) is a **rectangle that locates every detected person in the image**, stored as four pixel coordinates in `(x1, y1)` (top-left corner) and `(x2, y2)` (bottom-right corner):

```
(x1, y1) ┌─────────────┐
         │             │
         │    PERSON   │
         │             │
         └─────────────┘ (x2, y2)
```

An example from the `/api/detect` response:

```json
{ "x1": 50, "y1": 60, "x2": 120, "y2": 200, "confidence": 0.91, "class": "person" }
```

A detection is **not** "a number of people" — it's *this list of boxes*. The `count` is just derived from `len(detections)`. The bounding boxes play several distinct roles:

1. **They are the actual model output.** YOLO (and most object detectors) don't return "yes there are 3 people". They return *candidate rectangles* classified by objectness. Each box is how the model asserts "there is a person covering this region of the image." Confidence is how sure it is.

2. **They make counting unambiguous.** Each box represents exactly one person, so counting is simply counting boxes. Without boxes, overlapping/occluded people would be impossible to separate — two people side by side are two boxes, not one blob.

3. **They enable the visual overlay.** `annotate_image()` draws the green rectangle + confidence label using exactly these coordinates. The `annotated_image` you get back is the proof-of-detection UI, and the boxes are the data behind it.

4. **They contain spatial information beyond the count.** From the coordinates you can compute:
   - **Position** — e.g. *is this person in the doorway, the checkout, the restricted zone?* (basis for the "region-based alerts" bonus feature)
   - **Size / apparent height** — useful for heuristics, e.g. filtering tiny far-away boxes, or flagging someone too close to a fence
   - **Coverage / crowd density** — what fraction of the frame is occupied

5. **They are stored for later analysis.** Storage keeps the full `detections` array (boxes + confidence) per timestamp, so you can replay *where* people were, not just *how many* — the difference between a table of numbers and a reconstruction of what happened.

6. **They are the input for quality metrics.** The assignment's *False Positive* metric counts "boxes that don't contain a person"; *Accuracy* compares correct boxes to manually counted people. So the requirement `≥ 85% accuracy` and `≤ 10% false positives` are evaluated box-by-box, using these coordinates.

In short: the count is the headline, but **the boxes are the substance** — they're the model's raw answer, the driver of the visual overlay, and the data that powers every spatial feature and metric in the project.

---

## 9. How storage works (`utils/storage.py`)

The `DetectionStorage` class persists detection records to a **local JSON file** (`detections.json`) — simple and dependency-free, good enough for this project's scale.

- `init_storage()` — creates the file as `[]` if it doesn't exist.
- `save_detection(result)` — appends a record with an ISO `timestamp` plus count/confidence/time/boxes.
- `load_all()` — reads the whole file.
- `load_by_date(date_str)` — filters records by `YYYY-MM-DD`.
- `reset()` — overwrites the file with `[]`.

`detections.json` is created in the current working directory when the server runs; it's listed in `.gitignore` so it never gets committed.

---

## 10. How a request flows through the code

1. `main.py` starts FastAPI and registers both routers.
2. A client hits `POST /api/detect`.
3. `routes/detect.py` reads the uploaded file bytes.
4. It opens the bytes as a PIL image and converts to a numpy array.
5. It calls `detector.detect(...)` → gets people/boxes/confidence/time.
6. It calls `storage.save_detection(...)` to log it.
7. It annotates the image and base64-encodes it.
8. It returns the full JSON payload.

---

## 11. Testing

The tests live in `backend/tests/test_detect.py` using **pytest** with **httpx** (FastAPI's test client).

Run from the repo root:

```bash
.venv/bin/pytest backend/tests -v
```

Tests cover: loading the detector, running detection on a synthetic image, the `/api/detect`, `/api/history`, and `DELETE /api/history` endpoints, plus error handling for missing/invalid uploads.

---

## 12. Common issues

| Symptom | Cause / Fix |
|---------|-------------|
| `ModuleNotFoundError: backend` | You're running from inside `backend/`. Run from the **repo root**. |
| Imports not found | Missing `__init__.py` files — ensure they exist in every package dir. |
| Slow first request | YOLO downloads `yolov8n.pt` on first model load. |
| Model still loads on CPU | It will; this project runs CPU inference by default. |
| `detections.json` appears in git | It's gitignored now, but if you created one before adding `.gitignore`, `git rm --cached detections.json` then re-commit. |
| Port already in use | Change `BACKEND_PORT` in `.env`. |

---

## 13. Design notes / trade-offs

- **Flat-file JSON storage** — intentionally simple. A real production system would use SQLite/PostgreSQL with concurrency control. Good for this assignment; note it's not safe for heavy concurrent writes.
- **CPU inference** — `yolov8n.pt` (nano) is chosen so it runs reasonably on CPU. For GPU, swap to a larger model and install the CUDA build of torch.
- **Confidence threshold 0.5** — can be tuned down to find more (often occluded) people, at the risk of more false positives.
- **CORS restricted** — only the configured frontend origin is allowed, not `*` (hardcoded). This is safer than the original wildcard config.
- **Detection stats** — `inference_time` and `average_confidence` are logged per record precisely so you can compute the metrics required by the assignment (accuracy, inference time, confidence) across your 10+ test images.
