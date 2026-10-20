from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import cv2
from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.analyzer import (
    VideoAnalyzer,
    generate_heatmap_overlay,
    normalize_roi_polygon,
)
from src.db import EventDatabase
from src.query import QueryEngine
from src.reporter import IncidentReporter

app = FastAPI(title="CCTV Event Monitor API")

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path("data")
UPLOAD_DIR = DATA_DIR / "uploads"
HEATMAP_DIR = DATA_DIR / "heatmaps"
DB_PATH = DATA_DIR / "events.db"
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "500"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
HEATMAP_DIR.mkdir(parents=True, exist_ok=True)

database = EventDatabase(str(DB_PATH))


def _get_database_counts() -> dict[str, int]:
    total_videos = len(database.list_videos())
    total_events = database.total_event_count()
    return {"videos": total_videos, "events": total_events}

# Mount static files for video and heatmaps
app.mount("/videos", StaticFiles(directory=UPLOAD_DIR), name="videos")
app.mount("/heatmaps", StaticFiles(directory=HEATMAP_DIR), name="heatmaps")


def compute_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


@app.get("/api/health")
async def get_health():
    counts = _get_database_counts()
    active_jobs = sum(1 for status in ANALYSIS_JOBS.values() if status.get("status") in {"pending", "running"})
    return {
        "status": "ok",
        "service": "cctv-event-monitor",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": {
            "path": str(DB_PATH),
            "exists": DB_PATH.exists(),
            **counts,
        },
        "uploads": {
            "directory": str(UPLOAD_DIR),
            "exists": UPLOAD_DIR.exists(),
            "file_count": len(list(UPLOAD_DIR.glob("*"))) if UPLOAD_DIR.exists() else 0,
        },
        "jobs": {
            "active": active_jobs,
            "total": len(ANALYSIS_JOBS),
        },
    }


@app.get("/api/jobs")
async def list_jobs():
    return {"jobs": {job_id: state for job_id, state in ANALYSIS_JOBS.items()}}


@app.get("/api/stats/{video_id}")
async def get_stats(video_id: int):
    video = database.get_video(video_id)
    if not video:
        raise HTTPException(404, "Video not found")
    stats = database.event_summary(video_id)
    all_events = database.list_events(video_id)

    loitering_count = sum(1 for e in all_events if e["event_type"] == "loitering")
    breach_count = sum(1 for e in all_events if e["event_type"] in ["zone_breach", "zone_entry"])
    stats["loitering"] = loitering_count
    stats["breaches"] = breach_count
    return stats


@app.get("/api/videos")
async def list_videos():
    return database.list_videos()


@app.get("/api/videos/{video_id}")
async def get_video(video_id: int):
    video = database.get_video(video_id)
    if not video:
        raise HTTPException(404, "Video not found")
    return dict(video)


@app.delete("/api/videos/{video_id}")
async def delete_video(video_id: int):
    deleted = database.delete_video(video_id)
    if not deleted:
        raise HTTPException(404, "Video not found")
    return {"deleted": True, "video_id": video_id}


@app.get("/api/events/{video_id}")
async def list_events(video_id: int, search: str = ""):
    return database.list_events(video_id, search=search)


@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        supported = ", ".join(sorted(ALLOWED_VIDEO_EXTENSIONS))
        raise HTTPException(400, f"Unsupported file type '{ext or 'unknown'}'. Supported video formats: {supported}")

    # Stream upload with size limit to avoid loading entire file into RAM
    chunks: list[bytes] = []
    total_size = 0
    while chunk := await file.read(1024 * 1024):  # Read 1MB at a time
        total_size += len(chunk)
        if total_size > MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                413, f"File too large. Maximum upload size is {MAX_UPLOAD_SIZE_MB}MB."
            )
        chunks.append(chunk)

    file_bytes = b"".join(chunks)
    if not file_bytes:
        raise HTTPException(400, "Uploaded file is empty.")

    video_hash = compute_hash(file_bytes)

    video_path = UPLOAD_DIR / f"{video_hash}{ext}"
    if not video_path.exists():
        video_path.write_bytes(file_bytes)

    return {
        "filename": file.filename,
        "video_hash": video_hash,
        "path": str(video_path),
        "cached": database.get_video_by_hash(video_hash) is not None,
    }


class AnalysisRequest(BaseModel):
    video_path: str
    video_hash: str
    filename: str
    model_name: str = "yolo11s.pt"
    tracker: str = "botsort.yaml"
    unattended_secs: float = 8.0
    proximity_ratio: float = 0.75
    loitering_secs: float = 15.0
    sample_every: int = 1
    confidence_threshold: float = 0.45
    scene_profile: Literal["balanced", "crowded", "low_light", "outdoor"] = "balanced"
    roi_polygon: list[tuple[float, float]] | None = None


# Global state tracking jobs
ANALYSIS_JOBS: dict[str, dict] = {}
JOB_TTL_SECONDS = 3600  # Auto-evict completed/failed jobs after 1 hour


def _evict_stale_jobs() -> None:
    """Remove completed/failed jobs older than JOB_TTL_SECONDS."""
    now = time.monotonic()
    stale = [
        jid for jid, state in ANALYSIS_JOBS.items()
        if state["status"] in {"completed", "failed"}
        and now - state.get("finished_at", now) > JOB_TTL_SECONDS
    ]
    for jid in stale:
        del ANALYSIS_JOBS[jid]


@app.post("/api/analyze")
async def analyze_video(req: AnalysisRequest, background_tasks: BackgroundTasks):
    # Path traversal protection: ensure video_path is inside UPLOAD_DIR
    resolved_path = Path(req.video_path).resolve()
    upload_dir_resolved = UPLOAD_DIR.resolve()
    if not str(resolved_path).startswith(str(upload_dir_resolved)):
        raise HTTPException(400, "Invalid video path: must be within the uploads directory.")
    if not resolved_path.exists():
        raise HTTPException(404, "Video file not found.")

    cached_video = database.get_video_by_hash(req.video_hash)
    if cached_video and req.roi_polygon is None:
        return {"status": "cached", "video_id": cached_video["id"]}

    _evict_stale_jobs()

    job_id = req.video_hash
    if job_id in ANALYSIS_JOBS and ANALYSIS_JOBS[job_id]["status"] == "running":
        return {"status": "running", "job_id": job_id}

    ANALYSIS_JOBS[job_id] = {
        "status": "pending",
        "progress": 0.0,
        "metrics": {},
        "result": None,
        "error": None,
        "finished_at": None,
    }

    background_tasks.add_task(asyncio.to_thread, run_analysis_task, job_id, req)
    return {"status": "started", "job_id": job_id}


def run_analysis_task(job_id: str, req: AnalysisRequest):
    ANALYSIS_JOBS[job_id]["status"] = "running"
    try:
        analyzer = VideoAnalyzer(
            model_name=req.model_name,
            tracker=req.tracker,
            unattended_after_seconds=req.unattended_secs,
            proximity_ratio=req.proximity_ratio,
            loitering_threshold_seconds=req.loitering_secs,
            roi_polygon=req.roi_polygon,
            confidence_threshold=req.confidence_threshold,
            scene_profile=req.scene_profile,
        )

        def progress_cb(frac: float, metrics: dict):
            if job_id in ANALYSIS_JOBS:
                ANALYSIS_JOBS[job_id]["progress"] = frac
                ANALYSIS_JOBS[job_id]["metrics"] = metrics

        result = analyzer.analyze(
            req.video_path,
            progress=progress_cb,
            sample_every_n_frames=req.sample_every,
            export_path=None,
        )

        # Save to DB
        video_id = database.create_video(
            req.filename, req.video_path, result.fps, result.frame_count, req.video_hash
        )
        database.add_events(video_id, (e.as_dict() for e in result.events))

        # Heatmap
        if result.first_frame is not None and result.heatmap_points:
            w, h = result.video_dimensions
            pixel_roi = normalize_roi_polygon(req.roi_polygon, w, h) if req.roi_polygon else None
            heatmap_img = generate_heatmap_overlay(
                result.first_frame, result.heatmap_points, roi_polygon=pixel_roi
            )
            heatmap_file = HEATMAP_DIR / f"heatmap_video_{video_id}.png"
            cv2.imwrite(str(heatmap_file), heatmap_img)
            database.update_video_meta(
                video_id,
                heatmap_path=str(heatmap_file),
                roi_coords=json.dumps(req.roi_polygon) if req.roi_polygon else None,
            )

        ANALYSIS_JOBS[job_id]["status"] = "completed"
        ANALYSIS_JOBS[job_id]["video_id"] = video_id
        ANALYSIS_JOBS[job_id]["finished_at"] = time.monotonic()
    except Exception as e:
        ANALYSIS_JOBS[job_id]["status"] = "failed"
        ANALYSIS_JOBS[job_id]["error"] = str(e)
        ANALYSIS_JOBS[job_id]["finished_at"] = time.monotonic()


@app.websocket("/ws/progress/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await websocket.accept()
    try:
        while True:
            if job_id not in ANALYSIS_JOBS:
                await websocket.send_json({"type": "not_found"})
                break

            state = ANALYSIS_JOBS[job_id]
            await websocket.send_json(
                {
                    "type": "progress",
                    "status": state["status"],
                    "progress": state["progress"],
                    "metrics": state["metrics"],
                    "error": state["error"],
                    "video_id": state.get("video_id"),
                }
            )

            if state["status"] in ["completed", "failed"]:
                # Send the final state and wait for client to disconnect or close
                pass

            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass


class QueryRequest(BaseModel):
    video_id: int
    question: str


@app.post("/api/query")
async def query_events(req: QueryRequest):
    all_events = database.list_events(req.video_id)
    engine = QueryEngine(all_events)
    answer = engine.query(req.question)
    return {"answer": answer}


class ReportRequest(BaseModel):
    video_id: int


@app.post("/api/report")
async def generate_report(req: ReportRequest):
    video_meta = database.get_video(req.video_id)
    if not video_meta:
        raise HTTPException(404, "Video not found")

    all_events = database.list_events(req.video_id)
    reporter = IncidentReporter()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    report_content = reporter.generate_report(
        video_meta, all_events, api_key=api_key
    )
    return {"report": report_content}
