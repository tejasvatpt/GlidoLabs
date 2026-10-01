"""HTTP API: upload -> captions (preview) -> export -> download."""

import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import jobs
from app.config import REPO_ROOT, load_style, settings, style_names
from app.media.ingest import ALLOWED_EXTENSIONS
from app.transcription.sources import apex_pipeline

FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"
CHUNK = 1024 * 1024


@asynccontextmanager
async def lifespan(_):
    settings.jobs_dir.mkdir(parents=True, exist_ok=True)
    jobs.sweep_old_jobs()
    jobs.worker.submit(apex_pipeline)  # load the model now so the first upload doesn't wait for it
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
    if get_job(job_id).status not in ("ready", "rendering", "done"):
        raise HTTPException(409, "Captions are not ready yet.")
    return jobs.captions(job_id)


@app.post("/api/jobs/{job_id}/export")
def export_job(job_id: str):
    job = get_job(job_id)
    if job.status not in ("ready", "done", "error") or not (jobs.job_dir(job_id) / "captions.json").exists():
        raise HTTPException(409, "Job is not ready for export.")
    jobs.worker.submit(jobs.export, jobs.save(job, status="rendering", progress=0, error=None))
    return {"status": "rendering"}


@app.get("/api/jobs/{job_id}/download")
def download(job_id: str):
    job, output = get_job(job_id), jobs.job_dir(job_id) / "output.mp4"
    if job.status != "done" or not output.exists():
        raise HTTPException(409, "The video has not been exported yet.")
    return FileResponse(output, media_type="video/mp4", filename=f"{Path(job.input_name).stem}_captioned.mp4")


@app.get("/media/{job_id}/input")
def media_input(job_id: str):
    path = jobs.input_file(job_id) if job_id.isalnum() else None
    if not path:
        raise HTTPException(404, "Video not found.")
    return FileResponse(path)


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
