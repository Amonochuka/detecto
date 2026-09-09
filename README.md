# Detecto

Real-time person detection and counting system. A FastAPI backend runs YOLOv8 person
detection on uploaded images, returns bounding boxes with confidence scores plus an
annotated image, and stores every detection with a timestamp for later analysis. A
React + Vite frontend provides a two-page dashboard: a **Detection view** to upload
images or pick from 13 bundled samples and watch results render, and a **History view**
to review past detections with date filters and one-click reset.

## Architecture

```
┌─────────────┐  POST /api/detect   ┌──────────────────────────────┐
│  React/Vite │ ───────────────────→│  FastAPI backend             │
│  dashboard  │ ←───────────────────│  - validation                │
└─────────────┘  JSON + base64 img  │  - YOLOv8 person detection   │
                                    │  - perf logging + history    │
                                    └──────────────┬───────────────┘
                                                   │
                                          detections.json
                                          logs/performance.log
```

- `backend/` — FastAPI app: `/api/detect`, `/api/history`, `/api/reset`; YOLOv8
  (`utils/detector.py`), JSON-file history (`repositories/json_storage.py` with the
  repository pattern in `interfaces/storage.py`), perf logging (`utils/perf_log.py`).
- `frontend/` — React + Vite SPA (`react-router-dom` for navigation:
  `/` → Detection, `/history` → History). Dev server proxies `/api/*` to the backend
  on port 8000, so no CORS fiddling is needed in development.
  - Detection view: drag-and-drop or file-picker upload (JPEG/PNG, ≤ 15 MB), a grid
    of sample images, and a live results panel with per-person boxes, bounding-box
    coordinates, confidence scores, count, average confidence, and processing time
    (auto-scaled ms/s).
  - History view: table of timestamped detections (people count, avg confidence badge,
    inference time), a date filter (YYYY-MM-DD), a result limit (default 50), refresh,
    download-to-CSV export, a guarded Clear History button backed by `POST /api/reset`,
    and a **bonus** hourly statistics panel (average crowd size per hour as a bar chart
    computed from the loaded records).

See [EXPLAINED.md](EXPLAINED.md) for a full walkthrough of the code, the changes, why
they were made, and an explanation of every test.

## Setup

Backend requirements are in `requirements.txt` (root, identical to
`backend/requirements.txt`).

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# config (optional; sensible defaults exist)
cp backend/.env.example backend/.env

# run the server (from the repo root)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Quick check: `curl http://localhost:8000/health` → `{"status":"healthy"}`.
Interactive API docs: http://localhost:8000/docs.

Frontend (dev, from a second terminal):

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

Open http://localhost:5173 — the Detection view loads immediately. Upload an image or
click any sample card; results (annotated image, count, confidence, timing) appear in a
stats row plus a side panel listing each detection. The History tab shows every saved
detection recorded so far.

Previews of the sample set:

| Terse name | Sample image |
|---|---|
| Yabelo street | `busy-street-scene-in-yabelo-ethiopia-2011-jpg.jpg` |
| Dhaka street | `busy-street-with-pedestrians-in-dhaka-bangladesh-jpg.jpg` |
| Winchester market | `christmas-market-crowd-winchester-geograph-org-uk-42887.jpg` |
| Brooklyn snow | `church-ave-people-walking-in-snow-chicken-restaurant-jan-2026-brooklyn-jpg.jpg` |
| Kenting night market | `crowd-at-the-kenting-night-market-20100925-jpg.jpg` |
| London stadium | `london-stadium-crowd-control-jpg.jpg` |
| Crosswalk | `pedestrians-crossing-the-a-busy-street-jpg.jpg` |
| High Line NYC | `people-walking-north-on-the-high-line-jpg.jpg` |
| Dufferin Terrace | `people-walking-on-the-dufferin-terrace-in-winter-jpg.jpg` |
| Quebec pedestrian | `person-in-winter-clothing-in-quebec-city-jpg.jpg` |
| Mall queue | `queue-of-people-outside-a-mall-jpg.jpg` |
| Shibuya crossing | `tokyo-shibuya-scramble-crossing-2018-10-09-jpg.jpg` |
| Jerusalem walkers | `walking-jewish-people-jerusalem-jpg.jpg` |

## API endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Welcome message |
| `GET /health` | Health check |
| `POST /api/detect` | Upload an image (`file` field, JPEG/PNG, ≤ 15 MB). Returns `count`, `detections` (bbox + confidence), `average_confidence`, `inference_time`, `annotated_image` (base64) |
| `GET /api/history?date=YYYY-MM-DD&limit=100` | Past detections, optional date filter, most recent `limit` |
| `GET /api/export?format=csv&date=YYYY-MM-DD&limit=100` | Download detection history as Excel-compatible CSV (`format=csv` or `format=excel`) |
| `POST /api/reset` | Clear detection history |

Example detect call:

```bash
curl -X POST http://localhost:8000/api/detect -F "file=@sample.jpg"
```

Error handling: unreadable/missing files, empty uploads, oversized images (413),
unsupported types (415), and corrupt payloads (400) are all rejected explicitly.

## Testing

Backend tests run against fake detector/storage, so **no ML stack is required** to run
them (only fastapi, pillow, numpy, python-multipart, pytest, httpx).

```bash
python -m pytest backend/tests -v    # 18 tests
```

Covered: valid detection flow and response shape, unsupported type, empty upload,
corrupt image, missing file, oversized image, empty history, history after a detection,
date filter, limit, and `POST /api/reset`.

## Evaluation & metrics

The project requires measuring model performance on ≥ 10 sample images. Place samples in
`frontend/public/samples/` (e.g. `frame1.jpg` … `frame10.jpg`), run detection on each,
then record:

| Metric | Formula / description | Target |
|--------|----------------------|--------|
| Detection Accuracy | Correct detections ÷ total visible persons | ≥ 85 % |
| False Positives | Non-person detections | ≤ 10 % |
| Average Inference Time | Mean processing time per image | ≤ 1.5 s |
| Average Confidence | Mean confidence of valid detections | ≥ 0.7 |
| System Reliability | All test images processed without errors | 100 % |

_raw numbers accumulate automatically in `backend/logs/performance.log`._

### Real benchmark (conf threshold 0.5, CPU, `yolov8n.pt`)

13 sample images run through `POST /api/detect` (originals in `backend/samples/`,
annotated copies in `backend/samples/annotated/`):

| # | Image | Detected | Avg conf | Infer (s) |
|---|-------|---------:|---------:|----------:|
| 1 | Busy street, Yabelo (Ethiopia) | 9 | 0.777 | *2.754 (warm-up)* |
| 2 | Busy street, Dhaka | 1 | 0.573 | 0.456 |
| 3 | Christmas market crowd, Winchester | 10 | 0.598 | 0.469 |
| 4 | Snowy street, Brooklyn | 2 | 0.857 | 0.388 |
| 5 | Night market, Kenting (low light) | 5 | 0.717 | 0.285 |
| 6 | London Stadium crowd control | 0 | — | 0.250 |
| 7 | Pedestrian crosswalk | 9 | 0.744 | 0.419 |
| 8 | High Line, NYC | 4 | 0.759 | 0.326 |
| 9 | Dufferin Terrace winter crowd | 14 | 0.751 | 0.443 |
| 10 | Single pedestrian, Quebec City | 1 | 0.510 | 0.435 |
| 11 | Queue outside a mall | 5 | 0.725 | 0.263 |
| 12 | Shibuya scramble crossing, Tokyo | 7 | 0.708 | 0.456 |
| 13 | Pedestrians, Jerusalem | 7 | 0.780 | 0.267 |

**Measured:** 74 persons across 13 images · mean confidence **0.708** (≥ 0.7 ✅) ·
mean inference **0.56 s** (≤ 1.5 s ✅; ~0.38 s excluding the first-call warm-up) ·
**13/13 images processed without errors (100 % ✅)**.

> The table above was measured at conf ≥ 0.5. The current default in
> `utils/detector.py` is **0.20** (with `max_det=300`, `min_size_ratio=0.005`), which
> raises the same run from 74 to 97 detected persons by recovering distant/occluded
> people the 0.5 cut missed — at some cost to average confidence.

**Known limitation (logged failure):** the London Stadium crowd detected **0** persons
at conf ≥ 0.5 with the default 640px inference resolution — a distant, heavily occluded
crowd. Testing showed the real culprit was the input resolution: at `imgsz=1280` the same
scene yields **35** people at the 0.20 default. The `PersonDetector` now picks an
inference resolution of up to 1280px from the image size, which is what recovered the
crowd (this under-counting is the classic "occlusion/partial visibility" failure the
project asks to document — some truly distant/tiny people remain below the confidence
floor even at full resolution). Single, clear subjects (image 10) still score 1/1.

**Manual step:** Detection Accuracy and False-Positive % are computed against your own
manual count of visible persons per image — open any `backend/samples/annotated/*.jpg`,
count the people, and fill the `visible_persons` column to finalise the percentages.

### Screenshots

Video/dashboard screenshots captured from the running app (Detection view idle, a
successful crosswalk detection with 13 people boxed, and the History view):

![Detection view](./docs/screenshots/detection-home.jpg)
![Crosswalk detection result](./docs/screenshots/detection-crosswalk.jpg)
![History view](./docs/screenshots/history.jpg)

## Current status

- ✅ Backend implemented and tested (18/18): detect + history + export + reset, upload
  validation, perf logging, deterministic storage path, lifespan-managed model.
- ✅ Frontend implemented: Vite + React SPA with React Router; Detection view
  (drag-and-drop upload, sample gallery, annotated-image results with count /
  confidence / timing, per-detection list); History view (timestamped table, date
  filter, result limit, refresh, CSV export, clear). Dev proxy wires `/api/*` to the backend.
- ✅ Bonus features: detection-history CSV export (`/api/export`) with a Download CSV
  button, and an hourly average-crowd-size bar chart on the History page.
- ✅ 13 real-world sample images (crowds, crosswalks, night market, snow) in
  `backend/samples/` and `frontend/public/samples/`; benchmark run and README table
  populated. (Sample photos are from Wikimedia Commons under their respective CC
  licenses.)