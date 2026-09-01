# detecto

Real-time person detection and counting — temporary README

Purpose
-------
This repository implements a real-time person detection and counting system with a FastAPI backend and a React+Vite frontend. The goal is to accept images or video frames, run person detection, return bounding boxes and confidence scores, and store detection history for analysis.

Directory layout
----------------
- `backend/` — FastAPI app and utilities
- `frontend/` — React + Vite single-page app
- `frontend/public/samples/` — put at least 10 sample images for testing

Quick setup
-----------
Backend (development):

```bash
cd backend
# create a venv and install requirements
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# run the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Frontend (development):

```bash
cd frontend
npm install
npm run dev
```

API endpoints
-------------
- `POST /detect` — accepts an image file (multipart/form-data) and returns JSON with: `count`, `detections` (bbox + confidence), `avg_confidence`. Optionally returns an overlay image (base64).
- `GET /history` — returns recent detection records.
- `POST /reset` — clears stored detection history.

Where to add samples
--------------------
Place at least 10 representative images in `frontend/public/samples/` named like `frame1.jpg` ... `frame10.jpg`. Update `backend/eval/ground_truth.json` with visible-person counts for evaluation.

Evaluation / Metrics (temporary)
--------------------------------
An evaluation script is provided at `backend/eval/evaluate.py` (if present). It reads sample images and `ground_truth.json` and computes:
- Detection Accuracy
- False Positives
- Average Inference Time
- Average Confidence

Fill `backend/eval/ground_truth.json` with a mapping of sample filename → visible person count before running evaluation.

Placeholders and next edits
---------------------------
- This README is temporary and will be updated with measured metrics, screenshots, and detailed instructions once tests are run.
- The detector implementation is a placeholder in `backend/utils/detector.py` — swap in a YOLOv8 or other pretrained model for production accuracy.

Commit & push
-------------
This commit is a temporary documentation update. Use the commit message prefix `chore:` for repository scaffold or `docs:` for README updates.

Contact / Notes
---------------
When you're ready I will update the detector to a selected model, run evaluation (if you provide real sample images), and update this README with results and screenshots.

**Repository Structure**

The current repository layout (top-level files and folders):

```
detecto/
├── backend/
│   ├── .env.example
	│   ├── eval/
│   ├── main.py
	├── requirements.txt
	├── routes/
	│   ├── detect.py
	│   └── history.py
	├── tests/
	│   └── test_detect.py
	└── utils/
		 ├── detector.py
		 └── storage.py
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── public/
│   │   └── samples/
│   │       └── README.md
│   └── src/
│       ├── App.jsx
│       ├── main.jsx
│       ├── styles.css
		 └── pages/
			  ├── Detection.jsx
			  └── History.jsx
├── src/
├── tests/
├── .gitignore
└── README.md
```

