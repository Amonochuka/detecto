import os
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.detect import router as detect_router
from backend.routes.history import router as history_router
from backend.utils.detector import PersonDetector
from backend.repositories.json_storage import JsonDetectionRepository

# Load environment variables. The spec's structure puts .env at the repo root,
# so check there first; backend/.env is kept as a fallback for dev setups.
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

# Read config from the environment. Defaults fall back only when a value is
# absent, so a developer who skips creating .env still gets a working server.
BACKEND_HOST = os.getenv("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", 8000))
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize heavy resources (YOLO model) once at startup
    # rather than at module import time.
    app.state.detector = PersonDetector()
    app.state.storage = JsonDetectionRepository()
    yield
    # Cleanup resources on shutdown
    del app.state.detector
    del app.state.storage

app = FastAPI(title="Detecto API", version="1.0.0", lifespan=lifespan)

# CORS middleware - allow the configured frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(detect_router)
app.include_router(history_router)

@app.get("/")
async def root():
    return {"message": "Detecto API running"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=BACKEND_HOST, port=BACKEND_PORT, reload=True)