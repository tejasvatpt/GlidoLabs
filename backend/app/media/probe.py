"""Video inspection and audio extraction via ffprobe/ffmpeg."""

import json
import subprocess
from fractions import Fraction
from pathlib import Path

from pydantic import BaseModel


class MediaError(Exception):
    """Raised when a file is not a usable video. Message is safe to show users."""


class VideoInfo(BaseModel):
    width: int
    height: int
    fps: float
    duration: float
    has_audio: bool
    rotation: int = 0
    video_codec: str
    audio_codec: str | None = None


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")


def probe(path: Path) -> VideoInfo:
    result = _run([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_streams", "-show_format", str(path),
    ])
    if result.returncode != 0:
        raise MediaError("File could not be read as a video.")

    data = json.loads(result.stdout or "{}")
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if video is None:
        raise MediaError("File has no video stream.")

    rate = video.get("avg_frame_rate", "0/0")
    fps = float(Fraction(rate if rate != "0/0" else video.get("r_frame_rate", "30/1")))
    duration = float(data.get("format", {}).get("duration") or video.get("duration") or 0)
    if duration <= 0:
        raise MediaError("Could not determine video duration.")

    # phone videos store portrait as landscape + rotation metadata
    side_rotation = next((s["rotation"] for s in video.get("side_data_list", []) if "rotation" in s), 0)
    rotation = int(side_rotation or video.get("tags", {}).get("rotate", 0)) % 360
    width, height = int(video["width"]), int(video["height"])
    if rotation in (90, 270):
        width, height = height, width

    return VideoInfo(
        width=width,
        height=height,
        fps=round(fps, 3),
        duration=round(duration, 3),
        has_audio=audio is not None,
        rotation=rotation,
        video_codec=video.get("codec_name", "unknown"),
        audio_codec=audio.get("codec_name") if audio else None,
    )


def extract_audio(video: Path, wav: Path) -> Path:
    """Write 16 kHz mono PCM WAV, the input format for ASR and alignment."""
    wav.parent.mkdir(parents=True, exist_ok=True)
    result = _run([
        "ffmpeg", "-y", "-v", "error", "-i", str(video),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav),
    ])
    if result.returncode != 0 or not wav.exists():
        raise MediaError("Audio could not be extracted from the video.")
    return wav
