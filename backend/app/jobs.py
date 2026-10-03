"""Job state on disk plus one background worker (one GPU/CPU-heavy job at a time)."""

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
from app.media.audio import vad_model
from app.media.person import mask_video, segmenter
from app.media.probe import MediaError
from app.rendering import bundle_renderer, render_video
from app.transcription.sources import apex_pipeline, transcribe

Status = Literal["queued", "preparing", "transcribing", "captioning", "rendering", "done", "error"]
log = logging.getLogger("glido")
worker = ThreadPoolExecutor(max_workers=1)
warming = []


def warm_up():
    """Load every model and the renderer bundle in parallel at startup; jobs wait for them instead of loading serially."""
    loader = ThreadPoolExecutor(max_workers=4)
    warming.extend(loader.submit(load) for load in (apex_pipeline, vad_model, segmenter, bundle_renderer))


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
    try:
        return Job.model_validate_json(path.read_text(encoding="utf-8")) if job_id.isalnum() and path.exists() else None
    except ValueError:  # job saved by an older version of the app
        return None


def run_step(job: Job, fn):
    try:
        fn()
    except MediaError as e:
        save(job, status="error", error=str(e))
    except Exception as e:
        log.exception("job %s failed", job.id)
        save(job, status="error", error=f"Processing failed: {type(e).__name__}")


def process(job: Job, upload: Path):
    """Upload -> vertical UGC video -> words -> speaker mask -> captions.json -> final MP4."""
    def steps():
        for ready in warming:
            ready.result()
        save(job, status="preparing", progress=0.05)
        media = ingest(upload, job_id=job.id)
        upload.unlink(missing_ok=True)
        save(job, status="transcribing", progress=0.2)
        v, mask = media.video, media.job_dir / "mask.mp4"
        with ThreadPoolExecutor(max_workers=1) as side:  # speaker cut-out (CPU) runs while the ASR uses the GPU
            cutout = side.submit(mask_video, media.input_path, v.width, v.height, v.fps, mask)
            transcript = transcribe(media.audio_path, job.script)
            if not transcript.words:
                raise MediaError("No speech was detected in this video.")
            (media.job_dir / "transcript.json").write_text(transcript.model_dump_json(indent=2), encoding="utf-8")
            save(job, status="captioning", progress=0.35)
            heads = cutout.result()
        track = build_captions(transcript, media.audio_path, v, job.style, job.force_hooks, heads)
        (media.job_dir / "captions.json").write_text(track.model_dump_json(indent=2), encoding="utf-8")
        media.audio_path.unlink(missing_ok=True)
        save(job, status="rendering", progress=0.5)
        props = {"captions": track.model_dump(), "style": load_style(job.style)}
        render_video(props, media.input_path, mask, media.job_dir / "output.mp4",
                     lambda p: save(job, progress=round(0.5 + 0.5 * p, 2)))
        mask.unlink(missing_ok=True)
        save(job, status="done", progress=1)

    run_step(job, steps)


def sweep_old_jobs(max_age_h: float = 24):
    cutoff = time.time() - max_age_h * 3600
    for folder in settings.jobs_dir.glob("*"):
        if folder.is_dir() and (folder.stat().st_mtime < cutoff or not load(folder.name)):
            shutil.rmtree(folder, ignore_errors=True)
        elif (job := load(folder.name)) and job.status not in ("done", "error"):
            save(job, status="error", error="Interrupted by a server restart. Please upload again.")
