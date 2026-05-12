"""
PDF → Word Converter — Backend API
FastAPI + SQLite + pdf2docx
"""

import os
import uuid
import shutil
import asyncio
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from database import SessionLocal, engine, Base
from converter import convert_pdf_to_docx
import models

# ──────────────────────────────────────────
# Directories
# ──────────────────────────────────────────
UPLOAD_DIR  = Path("uploads")
OUTPUT_DIR  = Path("outputs")
STATIC_DIR  = Path("../")          # sert le frontend

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# ──────────────────────────────────────────
# App lifecycle
# ──────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)   # create tables
    yield
    # cleanup on shutdown (optionnel)

app = FastAPI(
    title="PDF→Word Converter API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend statically
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ──────────────────────────────────────────
# Helper
# ──────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _db():
    """Synchronous DB session for background tasks."""
    return SessionLocal()


# ──────────────────────────────────────────
# Background conversion worker
# ──────────────────────────────────────────
def run_conversion(job_id: str, pdf_path: Path, output_path: Path):
    db = _db()
    try:
        job = db.query(models.Conversion).filter(models.Conversion.id == job_id).first()
        if not job:
            return

        job.status = "processing"
        db.commit()

        success, error = convert_pdf_to_docx(pdf_path, output_path)

        if success:
            job.status        = "done"
            job.output_path   = str(output_path)
            job.completed_at  = datetime.utcnow()
            job.file_size_out = output_path.stat().st_size if output_path.exists() else 0
        else:
            job.status       = "error"
            job.error_message = error
            job.completed_at  = datetime.utcnow()

        db.commit()
    except Exception as exc:
        job = db.query(models.Conversion).filter(models.Conversion.id == job_id).first()
        if job:
            job.status        = "error"
            job.error_message = str(exc)
            job.completed_at  = datetime.utcnow()
            db.commit()
    finally:
        db.close()
        # Remove uploaded PDF after conversion
        if pdf_path.exists():
            pdf_path.unlink()


# ──────────────────────────────────────────
# Routes
# ──────────────────────────────────────────

@app.get("/")
async def root():
    return {"message": "PDF→Word Converter API", "version": "1.0.0"}


# ── 1. Upload & start conversion ──
@app.post("/api/convert", status_code=202)
async def start_conversion(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    # Validate
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > 50:
        raise HTTPException(status_code=413, detail="File exceeds 50 MB limit.")

    # Persist PDF
    job_id   = str(uuid.uuid4())
    pdf_path = UPLOAD_DIR / f"{job_id}.pdf"
    pdf_path.write_bytes(content)

    out_name    = Path(file.filename).stem + ".docx"
    output_path = OUTPUT_DIR / f"{job_id}.docx"

    # DB record
    db  = _db()
    job = models.Conversion(
        id               = job_id,
        original_filename= file.filename,
        output_filename  = out_name,
        file_size_in     = len(content),
        status           = "queued",
    )
    db.add(job)
    db.commit()
    db.close()

    # Schedule background conversion
    background_tasks.add_task(run_conversion, job_id, pdf_path, output_path)

    return {
        "job_id":   job_id,
        "filename": out_name,
        "status":   "queued",
    }


# ── 2. Poll status ──
@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    db  = _db()
    job = db.query(models.Conversion).filter(models.Conversion.id == job_id).first()
    db.close()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    return {
        "job_id":            job.id,
        "status":            job.status,          # queued | processing | done | error
        "original_filename": job.original_filename,
        "output_filename":   job.output_filename,
        "file_size_in":      job.file_size_in,
        "file_size_out":     job.file_size_out,
        "created_at":        job.created_at.isoformat(),
        "completed_at":      job.completed_at.isoformat() if job.completed_at else None,
        "error":             job.error_message,
    }


# ── 3. Download converted file ──
@app.get("/api/download/{job_id}")
async def download_file(job_id: str):
    db  = _db()
    job = db.query(models.Conversion).filter(models.Conversion.id == job_id).first()
    db.close()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status != "done":
        raise HTTPException(status_code=409, detail=f"Job is not ready (status: {job.status}).")

    output_path = Path(job.output_path)
    if not output_path.exists():
        raise HTTPException(status_code=410, detail="File has been deleted.")

    return FileResponse(
        path        = str(output_path),
        filename    = job.output_filename,
        media_type  = "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


# ── 4. Statistics dashboard ──
@app.get("/api/stats")
async def get_stats():
    db    = _db()
    total = db.query(models.Conversion).count()
    done  = db.query(models.Conversion).filter(models.Conversion.status == "done").count()
    error = db.query(models.Conversion).filter(models.Conversion.status == "error").count()
    queue = db.query(models.Conversion).filter(models.Conversion.status.in_(["queued","processing"])).count()

    recent = (
        db.query(models.Conversion)
        .order_by(models.Conversion.created_at.desc())
        .limit(10)
        .all()
    )
    db.close()

    return {
        "total":      total,
        "done":       done,
        "error":      error,
        "in_progress":queue,
        "success_rate": round(done / total * 100, 1) if total else 0,
        "recent": [
            {
                "job_id":   r.id,
                "filename": r.original_filename,
                "status":   r.status,
                "created":  r.created_at.isoformat(),
            }
            for r in recent
        ],
    }


# ── 5. Delete job & file ──
@app.delete("/api/job/{job_id}")
async def delete_job(job_id: str):
    db  = _db()
    job = db.query(models.Conversion).filter(models.Conversion.id == job_id).first()
    if not job:
        db.close()
        raise HTTPException(status_code=404, detail="Job not found.")

    # Remove output file if it exists
    if job.output_path:
        p = Path(job.output_path)
        if p.exists():
            p.unlink()

    db.delete(job)
    db.commit()
    db.close()
    return {"deleted": job_id}


# ──────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)