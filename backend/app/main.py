"""HTTP API: upload -> processing (captions + render) -> preview -> download."""

import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import jobs
from app.config import REPO_ROOT, load_style, settings, style_names
from app.media.ingest import ALLOWED_EXTENSIONS
from app.media.audio import vad_model
from app.transcription.sources import apex_pipeline

FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"
CHUNK = 1024 * 1024


@asynccontextmanager
async def lifespan(_):
    settings.jobs_dir.mkdir(parents=True, exist_ok=True)
    jobs.sweep_old_jobs()
    for load in (vad_model, apex_pipeline):  # load and warm models now so the first upload doesn't wait
        jobs.worker.submit(load)
    yield


app = FastAPI(title="Glido Labs", lifespan=lifespan)


def get_job(job_id: str) -> jobs.Job:
    job = jobs.load(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    return job


@app.post("/api/jobs")
async def create_job(file: UploadFile = File(...), script: str = Form(""), force_hooks: str = Form(""),
                     style: str = Form("eclipse")):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Unsupported file type. Use MP4, MOV, WebM or MKV.")
    if style not in style_names():
        raise HTTPException(400, f"Unknown style '{style}'.")

    job = jobs.Job(id=uuid.uuid4().hex, style=style, script=script.strip() or None, input_name=file.filename,
                   force_hooks=[h.strip() for h in force_hooks.split(",") if h.strip()])
    upload = jobs.job_dir(job.id) / f"upload{ext}"
    upload.parent.mkdir(parents=True)
    size, limit = 0, settings.max_upload_mb * CHUNK
    with upload.open("wb") as out:
        while chunk := await file.read(CHUNK):
            size += len(chunk)
            if size > limit:
                out.close()
                upload.unlink()
                raise HTTPException(413, f"File is larger than {settings.max_upload_mb} MB.")
            out.write(chunk)
    jobs.save(job)
    jobs.worker.submit(jobs.process, job, upload)
    return {"job_id": job.id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    return get_job(job_id)


@app.get("/api/jobs/{job_id}/captions")
def job_captions(job_id: str):
    path = jobs.job_dir(get_job(job_id).id) / "captions.json"
    if not path.exists():
        raise HTTPException(409, "Captions are not ready yet.")
    return FileResponse(path, media_type="application/json")


def output_file(job_id: str) -> Path:
    job, output = get_job(job_id), jobs.job_dir(job_id) / "output.mp4"
    if job.status != "done" or not output.exists():
        raise HTTPException(409, "The video is not ready yet.")
    return output


@app.get("/api/jobs/{job_id}/video")
def preview(job_id: str):
    return FileResponse(output_file(job_id), media_type="video/mp4")


@app.get("/api/jobs/{job_id}/download")
def download(job_id: str):
    name = Path(get_job(job_id).input_name).stem
    return FileResponse(output_file(job_id), media_type="video/mp4", filename=f"{name}_captioned.mp4")


@app.get("/api/styles")
def styles():
    return style_names()


@app.get("/api/styles/{name}")
def style(name: str):
    if name not in style_names():
        raise HTTPException(404, "Style not found.")
    return load_style(name)


if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
