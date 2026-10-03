"""UGC layout: every video becomes full-screen vertical 1080x1920, letterbox removed, crop centred on the speaker."""

import re
import subprocess
from pathlib import Path

import numpy as np

from app.media.person import frames, head_position, person_mask
from app.media.probe import MediaError, VideoInfo

WIDTH, HEIGHT = 1080, 1920


def content_box(video: Path, info: VideoInfo) -> tuple[int, int, int, int]:
    """Visible picture inside any black bars, as (w, h, x, y)."""
    log = subprocess.run(["ffmpeg", "-v", "info", "-t", "8", "-i", str(video), "-vf", "cropdetect=24:2:0", "-f", "null", "-"],
                         capture_output=True, text=True, errors="replace").stderr
    found = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", log)
    w, h, x, y = map(int, found[-1]) if found else (info.width, info.height, 0, 0)
    return (w, h, x, y) if w > info.width * 0.3 and h > info.height * 0.3 else (info.width, info.height, 0, 0)


def speaker_x(video: Path, box: tuple[int, int, int, int]) -> float:
    """Median horizontal position of the head (0-1 of the content box) over a few seconds."""
    w, h, x, y = box
    small = (256, round(256 * h / w / 2) * 2)
    xs = []
    for i, rgb in enumerate(frames(video, *small, seconds=6, crop=box)):
        if i % 15 == 0 and (head := head_position(person_mask(rgb))):
            xs.append(head[1])
    return float(np.median(xs)) if xs else 0.5


def to_vertical(video: Path, info: VideoInfo, out: Path) -> Path:
    w, h, x, y = box = content_box(video, info)
    crop_w, crop_h = (round(h * 9 / 16), h) if w / h > 9 / 16 else (w, round(w * 16 / 9))
    left = x + min(max(round(speaker_x(video, box) * w - crop_w / 2), 0), w - crop_w)
    top = y + (h - crop_h) // 2
    vf = f"crop={crop_w}:{crop_h}:{left}:{top},scale={WIDTH}:{HEIGHT}:flags=lanczos,setsar=1"
    result = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vf", vf, "-c:v", "libx264", "-preset", "veryfast",
                             "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(out)], capture_output=True)
    if result.returncode != 0:
        raise MediaError("The video could not be converted to the vertical UGC layout.")
    return out
