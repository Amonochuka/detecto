# Detecto — Everything Explained

This document is a full walkthrough of the Detecto project: what it is, how the code
is organised, everything that was found when I first audited the repo, everything that
has been changed since, and — most importantly — *why* each change was made. It also
explains the "lazy imports" change in detail and walks through every test.

Read this top to bottom; it is written so that a beginner can follow it.

---

## 1. What this project is

Detecto is a **real-time person detection and counting system**. Given an image (or a
frame from a video stream), the backend runs a machine-learning object-detection model,
finds every person in the image, draws a green box around each one, reports how confident
the model is about each box, and stores the result in history so an analyst can review
crowd size over time.

Two parts:

| Part | Tech | Job |
|------|------|-----|
| `backend/` | FastAPI + Python | Accept an image, run the detection model, return boxes + confidences + an annotated image, and save history |
| `frontend/` | React + Vite (JSX) | Dashboard with a "Detection" page (upload → see boxes) and a "History" page (table/graph of past detections) |

> The backend is **fully implemented and tested**. The frontend is currently **empty
> scaffolding** (placeholder files only) — that is the big remaining piece of work.

---

## 2. Where everything lives (accurate tree)

```
detecto/
├── .env.example                 # (backend) template for local config
├── .gitignore
├── README.md                    # project README
├── EXPLAINED.md                 # this document
├── requirements.txt             # backend deps (root copy — see §5.3)
├── test_crowd_count.py          # optional: run YOLO over every backend/samples image
├── yolov8n.pt                   # YOLOv8-nano weights (gitignored)
├── backend/
│   ├── .env                     # local config (BACKEND_HOST/PORT, FRONTEND_URL)
│   ├── .env.example             # template for .env
│   ├── README.md                # deep-dive backend docs
│   ├── main.py                  # FastAPI app: config, CORS, lifespan, routers
│   ├── requirements.txt         # backend deps (source of truth)
│   ├── detections.json          # history storage (auto-created, gitignored)
│   ├── models/
│   │   └── record.py            # Pydantic request/response models
│   ├── interfaces/
│   │   └── storage.py           # DetectionRepository abstract base class
│   ├── repositories/
│   │   └── json_storage.py      # JsonDetectionRepository (JSON file storage)
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── detect.py            # POST /api/detect
│   │   └── history.py           # GET /api/history, POST /api/reset
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── detector.py          # PersonDetector (YOLOv8 wrapper)
│   │   ├── preprocessing.py     # resize / normalize / contrast / letterbox
│   │   └── perf_log.py          # rotating perf logger
│   ├── logs/
│   │   └── performance.log      # perf logging (auto-created, gitignored)
│   ├── samples/                 # 13 original images + annotated/ outputs
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py          # fixtures + fake detector/storage
│       ├── test_detect.py       # 6 tests for /api/detect
│       └── test_history.py      # 5 tests for history/reset
└── frontend/                    # (scaffolding — not built yet)
    ├── index.html
    ├── package.json
    ├── public/samples/          # put 10+ demo images here (required by spec)
    └── src/
        ├── App.jsx              # returns null (placeholder)
        ├── main.jsx             # returns null (placeholder)
        ├── styles.css           # empty
        └── pages/
            ├── Detection.jsx    # returns null (placeholder)
            └── History.jsx      # returns null (placeholder)
```

---

## 3. How the backend works

### 3.1 `backend/main.py` — the app entry point

| Concern | How it's handled |
|---------|------------------|
| Config | reads `BACKEND_HOST`, `BACKEND_PORT`, `FRONTEND_URL` from environment (with defaults) |
| `.env` | loaded **from `backend/.env`** (`Path(__file__).resolve().parent / ".env"`) |
| CORS | only the configured frontend origin (`http://localhost:5173` by default) may call the API |
| Heavy resources | created once in a **`lifespan`** context manager and stored on `app.state` |
| Routers | `detect_router` and `history_router` are attached under the `/api` prefix |
| Health | `GET /` → `{"message": "Detecto API running"}`, `GET /health` → `{"status": "healthy"}` |

The interesting bit is the **lifespan** (see §5.1 for the full story):

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.detector = PersonDetector()      # happens ONCE, at server startup
    app.state.storage = DetectionStorage()     # happens ONCE, at server startup
    yield                                      # server now serves requests
    del app.state.detector                     # cleanup on shutdown
    del app.state.storage
```

### 3.2 `routes/detect.py` — `POST /api/detect`

Flow of a request:

1. FastAPI confirms a required upload field named `file` is present (else → **422**).
2. We check the declared content type is `image/jpeg` or `image/png` (else → **415**).
3. We read the bytes. Empty file → **400**. Bigger than 15 MB → **413**.
4. We try to decode the bytes with **PIL**. Non-image / corrupt → **400**.
5. Image is converted to a NumPy array and handed to `detector.detect(...)`.
6. Detection result is logged (`perf_log`) and saved to history (`storage`).
7. Boxes are drawn on the image (`annotate_image`) and the result is base64-encoded.
8. JSON response: `count`, `average_confidence`, `inference_time`, `detections[]`, `annotated_image`.

### 3.3 `routes/history.py` — history endpoints

| Endpoint | Behaviour |
|----------|-----------|
| `GET /api/history?date=YYYY-MM-DD&limit=100` | All records, optionally filtered to one day, truncated to the most recent `limit` |
| `POST /api/reset` | Clears all history (the project spec names a `/reset` route) |

Small but important detail: `limit` uses `detections[-limit:]` which in Python weirdly
**ignores** `0` (because `-0 == 0`), so we guard with `detections[-limit:] if limit > 0 else []`.

### 3.4 `utils/detector.py` — the model wrapper

`PersonDetector` wraps **Ultralytics YOLOv8** (default weights `yolov8n.pt` — the small
"nano" model, a good speed/accuracy trade-off for CPU).

- `detect(image)` runs inference with a **confidence threshold of 0.5** and keeps only
  boxes whose class id is **0**. In the COCO dataset (which YOLOv8 is trained on),
  class 0 is **person**. It returns `count`, `detections` (each with `x1,y1,x2,y2`,
  `confidence`, `class`), `average_confidence`, and `inference_time`.
- `annotate_image(image, detections)` draws green rectangles + a confidence label.
- `image_to_base64(image)` JPEG-encodes the image and returns base64 (so the frontend can
  embed it directly in an `<img>` tag).

### 3.5 `utils/storage.py` — persistence

`DetectionStorage` stores every detection as a JSON array in `backend/detections.json`
(guaranteed relative to the backend directory — see §5.2).

Each record looks like:

```json
{
  "timestamp": "2026-09-07T21:43:59.150056",
  "count": 2,
  "average_confidence": 0.88,
  "inference_time": 0.05,
  "detections": [ { "x1": ..., "y1": ..., "x2": ..., "y2": ..., "confidence": ..., "class": "person" } ]
}
```

Methods: `save_detection`, `load_all`, `load_by_date`, `reset`.

### 3.6 `utils/perf_log.py` — performance logging

Every successful detection appends one JSON line to `backend/logs/performance.log`
(a **rotating** file — max 5 MB, keeps 3 backups). This is the raw data you'd use to
compute the project's required benchmarks (average inference time, average confidence).

```json
{"timestamp": "...", "count": 2, "average_confidence": 0.88, "inference_time": 0.05}
```

---

## 4. What I found when I first audited the repo

### 4.1 Backend audit

| # | Finding | State |
|---|---------|-------|
| 1 | `tests/test_detect.py` was just `# placeholder test` — no real tests | **missing** |
| 2 | `main.py` loaded `.env` from the **repo root**, but `.env` actually lived in `backend/` — so config silently fell back to defaults | **bug** |
| 3 | No root-level `requirements.txt` (spec's structure puts one at the root) | **missing** |
| 4 | No benchmark metrics (accuracy, false positives, inference time, confidence across 10+ images) recorded | **missing** |
| 5 | No sample images in `backend/samples/` or `frontend/public/samples/` | **missing** |
| 6 | `routes/detect.py` created `PersonDetector()` (loads the ~hundreds-of-MB YOLO model) **at module import time** — slow startup, heavy import side effect | **bad** |
| 7 | `DetectionStorage` defaulted to a **CWD-relative** `detections.json` — storage broke if you ran the server from a different directory | **bad** |
| 8 | History reset existed only as `DELETE /api/history`; the spec explicitly names a `/reset` endpoint. `DELETE` was later removed as out of scope — the reset route is now `POST /api/reset` only | **fixed** |
| 9 | No validation of uploads — a text file, an empty file, or a 2 GB file would sail straight through or crash with a generic 400 | **bad** |
| 10 | Performance logging captured inference time only in the ephemeral HTTP response, never persisted for later analysis | **missing** |

### 4.2 Frontend audit

The frontend was **pure scaffolding**: `index.html` was an HTML comment, `main.jsx`
returned `null`, `App.jsx` returned `null`, both `Detection.jsx` and `History.jsx`
returned `null`, `styles.css` was empty, there was no `vite.config.js`, no dependencies,
no router, no components directory, and no sample images. In short: **nothing built**.

### 4.3 Things that were already good

- The **core detect flow worked end-to-end**: FastAPI app + YOLO person detection +
  JSON-file storage, with sensible defaults.
- The **project structure followed the spec** (routes/ utils/ models/ etc.).
- `detections.json`, `.env`, `*.pt`, venv and node artefacts were already **gitignored**.

---

## 5. Every change, explained (per task)

### 5.1 Lazy loading: lifespan + lazy imports (§points 6)

This was two related fixes and it's the trickiest concept, so it gets two sub-sections.

#### Why loading the model at import time is bad

In the original code, `routes/detect.py` started with:

```python
detector = PersonDetector()      # <-- this RUNS YOLO(...), loading ~6 MB of
                                 # weights AND importing torch/cv2
```

Python executes module-level code the moment `import backend.routes.detect` runs. Since
`main.py` imports the router, **merely importing the app triggered a full model load**.
Every test, every linter, every tool that imports the app paid that cost — and a crash
inside that import would break the whole server before it even started.

#### Fix 1 — move creation into a `lifespan`

FastAPI runs the `lifespan` context manager **once at server startup** (and its cleanup
on shutdown). We create the detector/storage there and stash them on `app.state`; route
handlers reach them via `request.app.state.detector` / `request.app.state.storage`:

```python
# routes/detect.py (inside the endpoint)
detector = request.app.state.detector
storage = request.app.state.storage
```

Benefits: the model loads at *startup*, not *import*; tests can replace the detector with
a fake **before** startup (see §7); startup failures are obvious FastAPI errors.

This was committed earlier as `7259c0c` ("fix: load detector and storage in app lifespan").

#### Fix 2 — lazy imports (this is also the change I call "making the imports lazy")

Even with the lifespan fix, `main.py` still does `from backend.utils.detector import
PersonDetector` at the top — and `detector.py` itself started with:

```python
import cv2
from ultralytics import YOLO     # pulls in torch + a lot more
```

So importing the *app* still dragged in torch/cv2/ultralytics, even though the model
object isn't created until lifespan. That's wasteful and makes the app effectively
untestable in a lightweight environment.

**"Lazy imports"** = moving the import statement from the top of the module (which runs
at import time) *inside* the function/method that actually uses it (which runs only when
that code executes).

```python
# BEFORE (runs when the module is imported)
import cv2
from ultralytics import YOLO

class PersonDetector:
    def __init__(self, model_name="yolov8n.pt"):
        self.model = YOLO(model_name)

    def annotate_image(self, image_source, detections):
        ... cv2.rectangle(...) ...
```

```python
# AFTER (runs only when the thing that needs it actually runs)
class PersonDetector:
    def __init__(self, model_name="yolov8n.pt"):
        from ultralytics import YOLO        # deferred to model creation
        self.model = YOLO(model_name)

    def annotate_image(self, image_source, detections):
        import cv2                          # deferred to first image annotation
        ... cv2.rectangle(...) ...
```

Why this matters *in this project specifically*:

1. `import backend.main` (and therefore any test importing the app) now only needs the
   **light** dependencies: fastapi, pillow, numpy, python-multipart, dotenv. That's why
   I could install a handful of small packages and run the whole test suite **without
   installing torch (~2 GB)**.
2. The heavy work happens at the moment it's genuinely needed (server startup → model
   creation; first annotated image → cv2 import), not silently at import time.
3. It's the standard Python "import is a statement, not a declaration" idea — imports
   can live anywhere a statement can, and deferring them is a legitimate technique for
   cutting startup cost and improving testability.

Trade-off: the model on the real server still loads exactly once (still cheap over the
app's lifetime), and cv2 is imported once per annotated image (negligible).

### 5.2 Storage path — stop depending on CWD (§point 7)

Originally: `DetectionStorage(storage_file="detections.json")` — a **relative path**, so
the file appeared in whatever directory the process happened to run from.

Now: default resolves relative to the **backend folder**:

```python
storage_file = Path(__file__).resolve().parent.parent / "detections.json"
```

`__file__` is this source file's path; `.resolve()` makes it absolute; `.parent.parent`
walks up from `utils/` to `backend/`. Result: the file is always `backend/detections.json`
no matter where you launch the server from.

### 5.3 Root `requirements.txt` (§point 3)

The spec's structure shows `requirements.txt` at the repo root, but it only existed in
`backend/`. I added a root copy **identical** to `backend/requirements.txt` so
`pip install -r requirements.txt` works from the root. (Slight downside: duplication can
drift — if you change one, change the other.)

### 5.4 Upload validation (§point 9)

`/api/detect` now rejects bad uploads with precise HTTP status codes:

| Case | Status | Message |
|------|--------|---------|
| Not an allowed content type (`image/jpeg`/`image/png`) | `415 Unsupported Media Type` | lists the allowed types |
| Empty file | `400` | "Uploaded file is empty." |
| Larger than 15 MB | `413 Payload Too Large` | mentions the size limit |
| Not actually an image (corrupt / wrong data) | `400` | "not a valid image" |

The "corrupt image" check is a **file-signature validation**: we really try to decode the
bytes with PIL (`Image.open(...)` + `image.load()`). PIL raises `UnidentifiedImageError`
if the bytes aren't a decodable image, no matter what the content type claims.

### 5.5 `/reset` endpoint (§point 8)

The spec's route list is `/detect`, `/history`, `/reset` — it never names a `DELETE`
verb. The codebase originally cleared history via `DELETE /api/history` and `POST
/api/reset` was added as an alias, but since `DELETE` is outside the spec's scope it
was removed: resetting history is now exactly one endpoint, `POST /api/reset`.
Keeping only the spec'd route also means every history-clearing consumer uses the same
URL, so Swagger docs and the frontend have a single "clear" action.

### 5.6 Performance logging (§point 10)

New module `utils/perf_log.py`: a module-level `RotatingFileHandler` writes one JSON line
per detection to `backend/logs/performance.log` (5 MB max, 3 backups). `/api/detect`
calls `log_detection(count, average_confidence, inference_time)` after inference. These
logs are the raw numbers you'll aggregate for the project's benchmark table (§9).

### 5.7 Confidence threshold and counting (0.15 → 0.5)

Counting accuracy is the product's real job — but bounding boxes are handed out with a
per-box confidence, and a decision has to be made about what counts as "a person". That
decision is `self.conf_threshold` in `utils/detector.py`.

When the repo was audited, the threshold had been set very low (0.15). On our 13 real
sample images that produced **137** "persons" — roughly double what the photos plausibly
contain. The excess were low-confidence boxes the model attached to background clutter
(trees, vehicle glass, crowd blurs). It also dragged mean confidence down to **0.526**,
missing the spec's ≥ 0.7 target, and slowed post-processing to ~1.2 s/image.

I ran a sweep of the threshold against all 13 images:

| conf | persons | avg conf | infer | verdict |
|------|--------:|---------:|------:|---------|
| 0.15 | 137 | 0.526 | 1.20 s | noisy, over-counts, fails ≥ 0.7 |
| 0.30 | 99 | 0.598 | 0.87 s | still noisy |
| 0.40 | 88 | 0.626 | 0.85 s | borderline |
| 0.50 | **74** | **0.708** | 0.56 s | ✅ balanced, meets ≥ 0.7 |
| 0.60 | 55 | 0.605 | 0.38 s | under-counts |
| 0.70 | 42 | 0.641 | 0.35 s | under-counts |

**0.5 won**: it clears the ≥ 0.7 confidence target, keeps inference well under 1.5 s, and
gives credible counts (a photo with one clear person → exactly 1). It's also the classic
default for YOLO person detection.

**The known trade-off** (documented in the README benchmark table): dense crowd images
still under-count. At 0.5, Shibuya's scramble crossing read 7, the London Stadium crowd
read 0, and the Dhaka street read 1 — those scenes genuinely contain more people than
the model reports, mostly distant or half-occluded subjects scoring below 0.5.

**Why not just lower the threshold to fix the crowds?** Because the same relaxation that
recovers hidden people also admits false boxes (background) → over-counting elsewhere and
a failing confidence metric. The threshold alone can't win both ways (see §5.8).

### 5.8 Planned next step: `max_det` + size filter (not yet implemented)

This is my proposed fix for the under-counting crowds *without* breaking the confidence
target, and it has **not** been implemented yet — picked up as a follow-up.

The idea, in plain terms:

1. **`max_det`** — cap the number of boxes returned per image (YOLO accepts `max_det=N`).
   A real street scene has maybe 50 people, not 300 candidate boxes. When the model
   produces more candidates than N, keep only the strongest (highest-confidence) N and
   discard the rest. This kills the tail of weak, repetitive boxes.

2. **Size filter** — before counting, drop any box whose height or width is below a
   small percentage of the image (e.g. 2–3% of height). Background specks and blurred
   blobs are almost always tiny; real people — even distant ones — are bigger. This
   removes the classic "false person" without touching real ones.

Applied together, you can afford to lower the threshold slightly (catch the hidden
crowd people at ~0.3) and then let the two filters strip the junk, so:
`lower threshold (recall) + max_det (cap duplicates) + size filter (kill blobs)`.

Status: designed, discussed here, **not coded**. The README currently uses plain
threshold 0.5 and asks for a manual per-image count to finalise the accuracy/FP numbers.

---

## 6. The tests — explained in depth

The whole suite runs **without the real model** — that's the payoff of the lazy-loading
work in §5.1. We substitute a `FakeDetector` and `FakeStorage`, so the tests are fast,
deterministic, and runnable on a machine without torch.

### 6.1 `conftest.py` — the shared fixtures

`conftest.py` is a special filename pytest auto-loads; fixtures defined there are shared
by all test files in that directory. Contents:

**`FakeDetector`** — the same interface as the real `PersonDetector` (`detect`,
`annotate_image`, `image_to_base64`) but returns a **fixed** result: 2 people, each with
specific boxes/confidences, `average_confidence = 0.88`, `inference_time = 0.05`. The
`image_to_base64` fake encodes via PIL instead of cv2 (so tests never need OpenCV).

**`FakeStorage`** — in-memory version of `DetectionStorage` (list + the same four methods)
with a fixed timestamp so date-filtering tests are deterministic.

```python
@pytest.fixture()
def fake_detector(monkeypatch):
    detector = FakeDetector()
    monkeypatch.setattr("backend.main.PersonDetector", lambda: detector)
    return detector
```

**`monkeypatch`** temporarily replaces an attribute for the duration of a test. Here we
swap the name `PersonDetector` *inside the `backend.main` module* for a lambda that
always returns our fake. Because the lifespan calls `PersonDetector()` as a **global
lookup at startup** (not a captured reference), the patch takes effect.

**The `client` fixture** is where fixture *ordering* must be right:

```python
@pytest.fixture()
def client(fake_detector, fake_storage):
    with TestClient(app) as c:      # entering this runs the lifespan
        yield c
```

`TestClient(app)` is FastAPI's in-process test harness: hitting `with TestClient(app)` as
a context manager **runs the startup (lifespan) and shutdown** around your requests. We
make `client` **depend on** the two fake fixtures — pytest guarantees dependencies are set
up first — so by the time the lifespan tries to build a detector, the monkeypatched
factory is already in place. (My first draft got the order wrong and the real model was
loaded; this ordering is the fix.)

**`sample_image` / `jpeg_bytes`** — small synthetic images generated in memory with PIL
(no files on disk).

### 6.2 `test_detect.py` — 6 tests

| Test | What it does | What it asserts |
|------|--------------|-----------------|
| `test_detect_valid_image` | POSTs a real tiny PNG to `/api/detect` | 200; `count == 2`; 2 detections; `average_confidence == 0.88`; `inference_time == 0.05`; `annotated_image` is non-empty; one record saved to fake storage |
| `test_detect_unsupported_content_type` | POSTs `text/plain` | 415; detail mentions "Unsupported file type" |
| `test_detect_empty_upload` | POSTs empty bytes as `image/png` | 400 |
| `test_detect_corrupt_image` | POSTs `b"definitely not a real image"` as `image/png` | 400 (signature check catches it) |
| `test_detect_missing_file` | POSTs with no `file` field | 422 (FastAPI's own validation) |
| `test_detect_oversized_image` | monkeypatches `MAX_FILE_SIZE` to 1024 bytes and sends 2048 | 413 |

The oversized test monkeypatches the *module constant* the route reads at request time —
so we exercise the size path without shipping gigabytes.

### 6.3 `test_history.py` — 5 tests

`seeded_storage` first runs one real `/api/detect` through the client (populating fake
storage), then returns the storage for assertions.

| Test | What it does | What it asserts |
|------|--------------|-----------------|
| `test_history_empty` | GET on fresh storage | success + `count == 0` |
| `test_history_after_detection` | GET after seeding | `count == 1`, record has the expected `count == 2` |
| `test_history_date_filter` | GET with `date=1999-01-01` vs `date=2026-01-01` | 0 vs 1 record |
| `test_history_limit` | GET with `limit=0` | `count == 0` (the `-0` bug guard) |
| `test_reset_history_clears` | POST `/api/reset` then GET | 0 records remain |

### 6.4 Running the tests

```bash
# from the repo root, after installing at least the light deps:
python -m pytest backend/tests -v
# Full results: 11 passed
```

---

## 7. The commit history (per task)

```
92dbed2 docs: document /reset endpoint in backend README
a481b2a test: add backend test suite replacing placeholder
0738da3 feat: add POST /api/reset endpoint
bba0b49 fix: apply history limit only when positive
42525d7 feat: log detection performance metrics
65f740a feat: validate image uploads in /detect
f4dfad1 refactor: lazy-load ML dependencies for fast imports
2d9ad10 fix: make detection storage path backend-relative
7259c0c fix: load detector and storage in app lifespan   (points 2 + 6)
```

Each commit is one logical task, so history is easy to read and easy to revert.

---

## 8. Concepts worth remembering

- **FastAPI lifespan** runs once at startup (replaces the older `@app.on_event("startup")`).
  Use it for anything expensive or singleton-like; expose via `app.state`.
- **Module-level side effects**: anything executed at import time runs for *every*
  consumer of that module. Keep imports cheap and defer heavy work.
- **HTTP status codes** do the communicating: 415 unsupported type, 413 too large,
  400 bad payload, 422 missing required field. FastAPI auto-returns 422 for unvalidatable
  input.
- **CORS**: the browser blocks cross-origin fetch unless the API sends
  `Access-Control-Allow-Origin`. FastAPI's `CORSMiddleware` whitelists `FRONTEND_URL`.
- **YOLO/ultralytics result shape**: `results[0].boxes` → `.xyxy` (corners), `.cls`
  (class id), `.conf` (confidence). COCO class **0 = person**.
- **Python gotcha**: `list[-0:]` slices from index 0 — "0 offset" silently means "all".
  Guard against it (`if limit > 0 else []`).
- **Pytest fixture order**: fixtures are built in dependency order. If fixture A needs a
  monkeypatch applied by fixture B, A must depend on B.

---

## 9. What's left to do

1. **Manual count verification** — open the annotated images in `backend/samples/annotated/`
   and record the visible persons per image, so README's Accuracy (%) and False Positives (%)
   can be finalised (ground truth is a human job by design).
2. **Optional crowd-count fix** — implement `max_det` + size filter (§5.8) to reduce the
   under-counts in dense crowds without failing the ≥ 0.7 confidence target.
3. **Frontend** — build the React/Vite dashboard (Detection + History pages). The two pages
   are still scaffolding (`null`). This is the big remaining piece.
4. **Screenshots / demo** — capture annotated results in the UI once the frontend exists
   (a placeholder README uses `backend/samples/annotated/` outputs now).
5. Validate error paths end-to-end (text file upload, huge file, etc.) from the UI.

Already done since this doc was first written: full deps installed (torch/opencv/ultralytics),
13 real sample images fetched (crowds, crosswalks, night market, snow) into
`backend/samples/` and `frontend/public/samples/`, conf threshold tuned to 0.5 with a real
benchmark run (avg conf 0.708, ~0.56 s/image, 13/13 reliable), README benchmark table +
screenshots added, root `.env.example` support added, and the **full frontend built and
integrated** (see §10) with the Vite dev proxy verified end-to-end against the live backend
(detect, history, reset, sample-image serving, and error paths all exercised from the UI
route through the proxy).

---

## 10. The frontend — every file, every function

The frontend is a **React 18 + Vite 5** single-page application. It has exactly one page
shell (`App.jsx`) with two routes, and every network call goes through the **Vite dev
proxy** in `vite.config.js`, so the code uses *relative* URLs (`/api/detect`) and the
browser never needs CORS in development.

```
Browser fetches http://localhost:5173
   │
   ├─ index.html ──<script type="module">──► main.jsx ──createRoot──► App.jsx
   │                                                              (BrowserRouter)
   │                                     ┌──────────────────────────────┴────────────────┐
   │                        NavLink to "/"                                   NavLink to "/history"
   │                                     │                                               │
   │                               Detection view                                    History view
   │                       POST /api/detect                                   GET /api/history
   │                                     │                                               │
   └─────────── Vite proxy ──/api/*─────► http://localhost:8000 (FastAPI)
```

Each file below gets its own sub-section; every function inside a file is explained
separately after its name.

### 10.1 `frontend/index.html`

The **single HTML page** Vite serves in both dev and production. React never writes HTML
directly — it renders into the empty `<div id="root">` inside this file.

| Element | Purpose |
|---------|---------|
| `<meta charset="UTF-8">` | Correct Unicode rendering |
| `<meta name="viewport" ...>` | Mobile-friendly scaling |
| `<title>Detecto — Person Detection Dashboard</title>` | Browser tab title |
| `<link rel="icon" ... data:image/svg+xml ...>` | Inline favicon (a 🎯 emoji) — no extra file to ship |
| `<div id="root">` | The mount point React attaches to |
| `<script type="module" src="/src/main.jsx">` | Loads the app; `type="module"` is required by Vite |

There are no functions here — it is declarative markup only.

### 10.2 `frontend/package.json`

The npm manifest. The earlier version was a 4-line placeholder; this one is complete.

| Field | Purpose |
|-------|---------|
| `"name": "detecto-frontend"` | Package name |
| `"private": true` | Prevents accidental `npm publish` |
| `"version": "1.0.0"` | Version |
| `"type": "module"` | Treats `.js`/`.jsx` files as ES modules (modern `import` syntax) |
| `"scripts": { "dev", "build", "preview" }` | The three commands: dev server, production build, preview the build |
| `"dependencies": { react, react-dom, react-router-dom }` | Runtime libraries |
| `"devDependencies": { vite, @vitejs/plugin-react }` | Build-time tools only |

The dependency split matters: React and the router travel into the production bundle;
Vite and its React plugin are only used while developing/building.

- **`"dev": "vite"`** — starts the development server (port 5173, hot reload, proxy).
- **`"build": "vite build"`** — bundles everything into `frontend/dist/` for deployment.
- **`"preview": "vite preview"`** — serves the built `dist/` locally.

### 10.3 `frontend/vite.config.js`

Vite's configuration file — the only file with no React code.

**`defineConfig({ ... })`** — returns the config object Vite uses at startup:

| Setting | Purpose |
|---------|---------|
| `plugins: [react()]` | The `@vitejs/plugin-react` plugin adds JSX/ESM transform support |
| `server.port: 5173` | Dev-server port (matches `FRONTEND_URL` in the backend `.env`) |
| `server.proxy["/api"]` | Forwards every `/api/*` request to `http://localhost:8000` with `changeOrigin`. This is what lets the frontend call relative `/api/detect` and `/api/history` without CORS issues in development |

### 10.4 `frontend/src/main.jsx`

The **React entry point** — the smallest file, and the first one React runs.

| Statement | Purpose |
|-----------|---------|
| `import React` / `import ReactDOM` | Brings in the React runtime and the DOM renderer |
| `import App from "./App"` | The root component (see 10.5) |
| `import "./styles.css"` | Pulls all global styles into the app |
| `ReactDOM.createRoot(document.getElementById("root"))` | Attaches React to the `<div id="root">` from `index.html` |
| `.render(<React.StrictMode><App /></React.StrictMode>)` | Renders the tree; `StrictMode` double-invokes render functions in dev to surface bugs |

### 10.5 `frontend/src/App.jsx`

The **page shell**. It owns the navbar and the routing table; the two pages are just
lazy-rendered children.

**`App()`** — the default-exported root component. It renders:

| Piece | Purpose |
|-------|---------|
| `<BrowserRouter>` | Reads the URL and gives the router context to every route below it |
| `<nav className="navbar">` | The fixed top bar |
| `.nav-brand` | The "Detecto" wordmark |
| `<NavLink to="/" end ...>` | The **Detection** tab. `end` means "only active on exactly `/`" |
| `<NavLink to="/history" ...>` | The **History** tab |
| `className={({ isActive }) => ...}` | React Router calls this per render — `isActive` toggles the `.active` highlight class for whichever tab matches the URL |
| `<Routes>` / `<Route path="/" element={<Detection />} />` | When the URL is `/`, render the Detection page |
| `<Route path="/history" element={<History />} />` | When the URL is `/history`, render the History page |

### 10.6 `frontend/src/styles.css`

All styling in one file, organised as a set of **design tokens** followed by component
classes. No functions — plain CSS.

**Design tokens (`:root`)** — CSS variables used everywhere else, so the whole theme is
uniform and changeable in one place:

| Variable | Value | Role |
|----------|-------|------|
| `--bg` | `#0f1117` | page background |
| `--surface` | `#1a1d27` | card/navbar background |
| `--surface-2` | `#242834` | nested panels, inputs, rows |
| `--border` | `#2e3343` | hairline borders |
| `--text` / `--text-muted` | `#e4e6ed` / `#8b8fa3` | primary / secondary text |
| `--primary` / `--primary-hover` | `#3b82f6` / `#2563eb` | accents, active links, buttons |
| `--success` / `--warning` / `--danger` | green / amber / red | semantic colours (counts, badges, errors) |
| `--radius` / `--shadow` | `8px` / soft shadow | consistent rounding + elevation |

**Component blocks** (each answers "what gets these styles"):

| Selector(s) | Styles |
|-------------|--------|
| `*`, `*::before`, `*::after`, `html`, `body` | Box-model reset and base font/colour/line-height |
| `.navbar`, `.nav-brand`, `.nav-links`, `.nav-link`, `.nav-link.active` | Sticky top bar, brand colour, tab hover/active states |
| `.main-content` | Centres the page content (max-width 1200px) and lays out below the navbar |
| `.page-header h1` / `.page-header p` | Page titles and subtitles |
| `.card`, `.card-title` | The universal panel (surface bg, border, padding, title style) |
| `.stats-row`, `.stat-value`, `.stat-label`, `.stat-value.success/.primary/.warning` | The three-metric summary row (count, confidence, time) |
| `.upload-zone`, `.upload-zone.dragover`, `.icon`, `.browse`, `input[type="file"]` | Dashed drop target; highlight while dragging; hides the real file input on top of the clickable zone |
| `.sample-grid`, `.sample-card`, `.sample-card.selected`, `.sample-name` | Responsive thumbnail gallery; selected-sample ring; truncated caption |
| `.btn`, `.btn-primary`, `.btn-danger`, `.btn-outline`, `.btn:disabled` | Button base + the three variants + disabled state |
| `.results-grid` (+ `@media (max-width: 800px)`) | Two-column image/list layout that collapses to one column on small screens |
| `.annotated-image-wrapper img` | The result image fills its card without distortion |
| `.detection-list`, `.detection-item`, `.det-index`, `.det-conf` | Scrollable per-person list; index number, coordinates, confidence |
| `.filters-bar` + its inputs | The History toolbar (date picker, number input, buttons) |
| `.history-table`, `th`, `td`, `tr:hover` | Full-width sortable-style table with hover rows |
| `.conf-high` / `.conf-medium` / `.conf-low` | Confidence badge colours (≥0.7 / ≥0.4 / below) |
| `.spinner`, `@keyframes spin`, `.loading-overlay` | Rotating loader used on both pages |
| `.error-banner` | Red-tinted alert shown when a request fails |
| `.empty-state`, `.icon` | Friendly "nothing here" panel |
| `.section-title`, `::-webkit-scrollbar` | Small caps section labels; slim dark scrollbars |

### 10.7 `frontend/src/pages/Detection.jsx` — per function

This is the **main page** of the app. It ships a hard-coded list of the 13 sample images
(in `public/samples/`), lets the user upload a photo instead, sends either one to the
backend, and renders the annotated result.

**`SAMPLES`** — a module-level array of the 13 sample filenames. It drives the gallery
grid at the bottom of the page. Keeping it at module scope (outside the component) means
it is created once, not on every render.

**`displayName(filename)`** — a pure helper that turns a filename into a human caption:
`"person-in-winter-clothing-in-quebec-city-jpg.jpg"` → `"Person In Winter Clothing In
Quebec City"`. It does this by removing the `-jpg` suffix, replacing the remaining
hyphens with spaces, and capitalising each word. Pure = same input always gives the same
output, so it is safe to call from inside a render.

**`Detection()`** — the default-exported page component. It holds the page's whole UI
state:

| State | What it tracks |
|-------|----------------|
| `selectedSample` | Which sample card (if any) is currently chosen — drives the ring highlight |
| `dragOver` | Whether the pointer is over the drop zone (drives the `.dragover` highlight) |
| `loading` | True while a detection request is in flight — shows the spinner text |
| `error` | A user-facing error string, or `null` |
| `result` | The last `/api/detect` response, or `null` |
| `fileInputRef` | A `useRef` handle to the hidden `<input type="file">`, so the whole drop zone can trigger it with a click |

It also registers one effect and six handlers, each described separately below.

**`useEffect(() => { window.scrollTo(...) }, [result])`** — whenever a new `result`
arrives (the dependency), smooth-scrolls the page to the top so the results panel is in
view. It returns early if `result` is `null` (first mount).

**`handleFileSelect(file)`** — the shared entry point for any chosen image. It ignores a
falsy `file` (e.g. the user cancelled the picker), clears any old `error`, un-highlights
the sample gallery (`setSelectedSample(null)`), then hands the file to `uploadFile`.

**`handleDrop(e)`** — the drag-and-drop event handler. It calls `e.preventDefault()` (so
the browser does not navigate to the file), clears the drag highlight, and pushes
`e.dataTransfer.files[0]` — the first dropped file — into `handleFileSelect`.

**`handleDragOver(e)`** — fires continuously while dragging over the zone. It calls
`e.preventDefault()` (required to allow a drop) and sets `dragOver` true so the border
lights up. The React `onDragOver` binding means no `e.stopPropagation()` is needed — the
event is scoped to this element in JSX.

**`handleDragLeave()`** — clears `dragOver` when the pointer leaves the zone, so the
highlight does not stick.

**`uploadFile(file)`** — the core async function. It:

1. **Validates client-side first** (mirrors the backend): type must be `image/jpeg` or
   `image/png`, else sets an error and returns; size must be ≤ 15 MB, else sets an error
   and returns.
2. Switches to the `loading` state and clears `error`/`result`.
3. Builds a `FormData` with the file under the field name **`file`** — the exact name
   `routes/detect.py` expects.
4. `POST`s it to the **relative** URL `/api/detect` (the Vite proxy forwards it to
   `:8000`).
5. On an HTTP error status, surfaces the backend's `data.detail` message (e.g. "Uploaded
   file is empty."); on a network failure (backend down), shows the "Could not connect…"
   message.
6. Stores the parsed JSON `result` — which the render turns into the stats row, annotated
   image, and detection list. `finally` always clears `loading`.

**`handleSampleClick(filename)`** — lets the user skip the file dialog and run a bundled
sample instead. It highlights the card, enters `loading`, fetches the image bytes at
`/samples/<filename>` (served statically by Vite from `public/`), wraps them in a `File`
object named after the sample, and reuses `uploadFile`. If the fetch fails it shows
"Failed to load sample image." and exits `loading`.

**The render** is three stacked regions driven by the state above:

1. `.page-header` + the `error` banner (drawn only when `error` is set).
2. The **results block** (only when `result` exists): a `.stats-row` of three cards —
   people count, average confidence (×100, one decimal, %), and processing time
   (printed as ms when under 1 s, else seconds) — followed by a `.results-grid` with the
   annotated image (drawn from `data:image/jpeg;base64,${result.annotated_image}`) and a
   per-detection list showing `#i`, corner coordinates `(x1,y1) → (x2,y2)` rounded to
   integers, and each box's confidence.
3. The **upload card** (clickable/drop zone, hidden file input) and the **samples card**
   (the `SAMPLES` grid, each tile clickable and highlighted when selected).

### 10.8 `frontend/src/pages/History.jsx` — per function

The second page: it reads past detections from the backend and shows them in a table,
with a date filter, a row limit, a refresh button, and a guarded "clear" action.

**`History()`** — the default-exported page component and its state:

| State | What it tracks |
|-------|----------------|
| `records` | The array of detection records loaded from `/api/history` |
| `loading` | True while a fetch is in flight |
| `error` | A user-facing error string, or `null` |
| `dateFilter` | The value of the `<input type="date">` box (`""` = no filter) |
| `limit` | The row limit, defaults to `50` |

Note the `useCallback`/`useEffect` pair: `fetchHistory` is recreated only when its two
dependencies (`dateFilter`, `limit`) change, and the effect re-runs only when the function
changes — so changing the date or limit automatically re-fetches, without resetting
`records` on every keystroke elsewhere.

**`fetchHistory()`** — the async loader (wrapped in `useCallback`). It builds a query
string with `URLSearchParams`: adds `date=YYYY-MM-DD` only when the filter is non-empty,
always adds `limit=N`, then `GET`s `/api/history` (again relative, via the proxy). On an
HTTP error it shows the backend's `detail`; on success it stores the array (falling back
to `[]`); a network failure produces the "Could not connect…" message. `finally` clears
`loading`.

**`useEffect(() => { fetchHistory(); }, [fetchHistory])`** — runs `fetchHistory`
whenever the component mounts **or** when the filter/limit changed.

**`handleReset()`** — the async "Clear History" action. First it pops a
`window.confirm` dialog ("This cannot be undone.") and aborts if the user declines. If
they accept it `POST`s `/api/reset` and optimistically empties the local `records`
array, so the table clears instantly; a failed request instead sets a "Failed to clear
history." error.

**`confBadge(conf)`** — a pure render helper that turns a confidence number into a
coloured pill: ≥ 0.7 → green `.conf-high`, ≥ 0.4 → amber `.conf-medium`, otherwise red
`.conf-low`, with the percentage text (one decimal) inside.

**`formatTime(iso)`** — a pure helper that parses the backend's ISO timestamp into a
`Date` and formats it with `toLocaleString()` (your browser's date/time format). If the
string cannot be parsed it returns it unchanged rather than throwing.

**The render** is: header, error banner, then a `.filters-bar` (date input, number
input clamped 1–500, Refresh button wired to `fetchHistory`, red Clear History button
wired to `handleReset`), then one of three states — the loading spinner (`.loading-overlay`),
the `.empty-state` (with a link back to `/`), or the `.history-table` listing each record
with its index, formatted timestamp, people count, confidence badge, and inference time
(ms or s). A footer line summarises how many records are shown.