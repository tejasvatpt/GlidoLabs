"""Accept a video: validate it, create the job folder, extract 16 kHz audio."""

import shutil
import uuid
from pathlib import Path

from pydantic import BaseModel

from app.config import settings
from app.media.probe import MediaError, VideoInfo, extract_audio, probe

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv"}


class IngestResult(BaseModel):
    job_id: str
    job_dir: Path
    input_path: Path
    audio_path: Path
    video: VideoInfo


def validate_file(path: Path) -> None:
    if not path.is_file():
        raise MediaError("File not found.")
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise MediaError(f"Unsupported file type '{path.suffix}'. Use MP4, MOV, WebM or MKV.")
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > settings.max_upload_mb:
        raise MediaError(f"File is {size_mb:.0f} MB; the limit is {settings.max_upload_mb} MB.")


def ingest(source: Path, jobs_dir: Path | None = None, job_id: str | None = None) -> IngestResult:
    validate_file(source)
    info = probe(source)
    if not info.has_audio:
        raise MediaError("Video has no audio track, so there is nothing to caption.")
    if info.duration > settings.max_duration_s:
        raise MediaError(f"Video is {info.duration:.0f} s; the limit is {settings.max_duration_s:.0f} s.")

    job_id = job_id or uuid.uuid4().hex
    job_dir = (jobs_dir or settings.jobs_dir) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    # Never reuse the user's file name in paths.
    input_path = job_dir / f"input{source.suffix.lower()}"
    shutil.copyfile(source, input_path)
    audio_path = extract_audio(input_path, job_dir / "audio.wav")

    (job_dir / "video.json").write_text(info.model_dump_json(indent=2), encoding="utf-8")
    return IngestResult(job_id=job_id, job_dir=job_dir, input_path=input_path, audio_path=audio_path, video=info)

