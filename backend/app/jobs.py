"""Job state on disk plus one background worker (one GPU/CPU-heavy job at a time)."""

import json
import logging
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.captions.build import build_captions
from app.config import load_style, settings
from app.media.ingest import ingest
from app.media.probe import MediaError
from app.rendering import render_video
from app.transcription.sources import transcribe

Status = Literal["queued", "extracting", "transcribing", "captioning", "ready", "rendering", "done", "error"]
log = logging.getLogger("glido")
worker = ThreadPoolExecutor(max_workers=1)


class Job(BaseModel):
    id: str
    status: Status = "queued"
    progress: float = 0
    error: str | None = None
    style: str = "eclipse"
    script: str | None = None
    force_hooks: list[str] = []
    input_name: str = ""


def job_dir(job_id: str) -> Path:
    return settings.jobs_dir / job_id


def save(job: Job, **changes) -> Job:
    for key, value in changes.items():
        setattr(job, key, value)
    job_dir(job.id).mkdir(parents=True, exist_ok=True)
    tmp = job_dir(job.id) / "job.json.tmp"
    tmp.write_text(job.model_dump_json(indent=2), encoding="utf-8")
    for _ in range(20):  # atomic swap; Windows refuses it while a status poll has the file open
        try:
            tmp.replace(job_dir(job.id) / "job.json")
            break
        except PermissionError:
            time.sleep(0.05)
    return job


def load(job_id: str) -> Job | None:
    path = job_dir(job_id) / "job.json"
    return Job.model_validate_json(path.read_text(encoding="utf-8")) if job_id.isalnum() and path.exists() else None


def run_step(job: Job, fn):
    try:
        fn()
    except MediaError as e:
        save(job, status="error", error=str(e))
    except Exception as e:
        log.exception("job %s failed", job.id)
        save(job, status="error", error=f"Processing failed: {type(e).__name__}")


def process(job: Job, upload: Path):
    def steps():
        save(job, status="extracting", progress=0.05)
        media = ingest(upload, job_id=job.id)
        upload.unlink(missing_ok=True)
        save(job, status="transcribing", progress=0.2)
        transcript = transcribe(media.audio_path, job.script)
        if not transcript.words:
            raise MediaError("No speech was detected in this video.")
        (media.job_dir / "transcript.json").write_text(transcript.model_dump_json(indent=2), encoding="utf-8")
        save(job, status="captioning", progress=0.85)
        track = build_captions(transcript, media.audio_path, media.video, job.style, job.force_hooks)
        (media.job_dir / "captions.json").write_text(track.model_dump_json(indent=2), encoding="utf-8")
        media.audio_path.unlink(missing_ok=True)
        save(job, status="ready", progress=1)

    run_step(job, steps)


def export(job: Job):
    def steps():
        save(job, status="rendering", progress=0)
        props = {"captions": captions(job.id), "style": load_style(job.style)}
        render_video(props, input_file(job.id), job_dir(job.id) / "output.mp4", lambda p: save(job, progress=p))
        save(job, status="done", progress=1)

    run_step(job, steps)


def captions(job_id: str) -> dict:
    return json.loads((job_dir(job_id) / "captions.json").read_text(encoding="utf-8"))


def input_file(job_id: str) -> Path | None:
    return next(job_dir(job_id).glob("input.*"), None)


def sweep_old_jobs(max_age_h: float = 24):
    cutoff = time.time() - max_age_h * 3600
    for folder in settings.jobs_dir.glob("*"):
        if folder.is_dir() and folder.stat().st_mtime < cutoff:
            shutil.rmtree(folder, ignore_errors=True)
        elif (job := load(folder.name)) and job.status not in ("ready", "done", "error"):
            save(job, status="error", error="Interrupted by a server restart. Please upload again.")
