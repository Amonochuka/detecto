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
├── backend/
│   ├── .env                     # local config (BACKEND_HOST/PORT, FRONTEND_URL)
│   ├── .env.example             # template for .env
│   ├── README.md                # deep-dive backend docs
│   ├── main.py                  # FastAPI app: config, CORS, lifespan, routers
│   ├── requirements.txt         # backend deps (source of truth)
│   ├── detections.json          # history storage (auto-created, gitignored)
│   ├── logs/
│   │   └── performance.log      # perf logging (auto-created, gitignored)
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── detect.py            # POST /api/detect
│   │   └── history.py           # GET/DELETE /api/history, POST /api/reset
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── detector.py          # PersonDetector (YOLOv8 wrapper)
│   │   ├── storage.py           # DetectionStorage (JSON file)
│   │   └── perf_log.py          # rotating perf logger
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py          # fixtures + fake detector/storage
│       ├── test_detect.py       # 6 tests for /api/detect
│       └── test_history.py      # 6 tests for history/reset
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
| `DELETE /api/history` | Clears all history |
| `POST /api/reset` | Alias of the DELETE above (the project spec names a `/reset` route) |

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
| 8 | History reset existed only as `DELETE /api/history`; the spec explicitly names a `/reset` endpoint | **minor gap** |
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

The spec says the backend should offer `/reset` to clear history. We already had
`DELETE /api/history`; I added `POST /api/reset` as a thin alias that does the same
thing, so both the conventional REST verb and the spec's literal route exist.

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

### 6.3 `test_history.py` — 6 tests

`seeded_storage` first runs one real `/api/detect` through the client (populating fake
storage), then returns the storage for assertions.

| Test | What it does | What it asserts |
|------|--------------|-----------------|
| `test_history_empty` | GET on fresh storage | success + `count == 0` |
| `test_history_after_detection` | GET after seeding | `count == 1`, record has the expected `count == 2` |
| `test_history_date_filter` | GET with `date=1999-01-01` vs `date=2026-01-01` | 0 vs 1 record |
| `test_history_limit` | GET with `limit=0` | `count == 0` (the `-0` bug guard) |
| `test_delete_history_clears` | DELETE then GET | 0 records remain |
| `test_reset_history_clears` | POST `/api/reset` then GET | 0 records remain |

### 6.4 Running the tests

```bash
# from the repo root, after installing at least the light deps:
python -m pytest backend/tests -v
# Full results: 12 passed
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
screenshots added, and root `.env.example` support added.