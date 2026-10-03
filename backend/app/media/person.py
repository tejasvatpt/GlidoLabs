"""Speaker segmentation (MediaPipe selfie segmenter): a mask video to put hooks behind the person, and where the head is."""

import subprocess
import urllib.request
from functools import cache
from pathlib import Path

import numpy as np

from app.config import settings

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/image_segmenter/"
             "selfie_segmenter/float16/latest/selfie_segmenter.tflite")
MASK_WIDTH = 270  # masks are upscaled (and softened) by FFmpeg when compositing


@cache
def segmenter():
    from mediapipe.tasks.python import BaseOptions, vision

    model = settings.jobs_dir.parent / "models" / "selfie_segmenter.tflite"
    if not model.exists():
        model.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(MODEL_URL, model)
    options = vision.ImageSegmenterOptions(base_options=BaseOptions(model_asset_path=str(model)), output_confidence_masks=True)
    return vision.ImageSegmenter.create_from_options(options)


def person_mask(rgb: np.ndarray) -> np.ndarray:
    import mediapipe as mp

    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
    return segmenter().segment(image).confidence_masks[0].numpy_view().squeeze()


def head_position(mask: np.ndarray) -> tuple[float, float] | None:
    """(top of head, head centre x) as fractions of the frame, or None if nobody is visible."""
    rows = np.flatnonzero((mask > 0.5).mean(axis=1) > 0.02)
    if not rows.size:
        return None
    band = mask[rows[0]:rows[0] + max(1, len(mask) // 10)] > 0.5
    cols = np.flatnonzero(band.any(axis=0))
    return rows[0] / len(mask), (cols.mean() / mask.shape[1]) if cols.size else 0.5


def frames(video: Path, width: int, height: int, seconds: float | None = None, crop: tuple | None = None):
    vf = (f"crop={crop[0]}:{crop[1]}:{crop[2]}:{crop[3]}," if crop else "") + f"scale={width}:{height}"
    args = ["ffmpeg", "-v", "error", "-i", str(video), *(["-t", str(seconds)] if seconds else []),
            "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    with subprocess.Popen(args, stdout=subprocess.PIPE) as proc:
        while len(buf := proc.stdout.read(width * height * 3)) == width * height * 3:
            yield np.frombuffer(buf, np.uint8).reshape(height, width, 3)


def mask_video(video: Path, width: int, height: int, fps: float, out: Path) -> list[tuple[float, float] | None]:
    """Writes a grayscale person-mask video (temporally smoothed) and returns the head position per frame."""
    w, h = MASK_WIDTH, round(MASK_WIDTH * height / width / 2) * 2
    encoder = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{w}x{h}",
                                "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
                                "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
    heads, previous = [], None
    for rgb in frames(video, w, h):
        mask = person_mask(rgb)
        mask = mask if previous is None else 0.6 * mask + 0.4 * previous  # damp edge flicker
        previous = mask
        encoder.stdin.write((np.clip(mask, 0, 1) * 255).astype(np.uint8).tobytes())
        heads.append(head_position(mask))
    encoder.stdin.close()
    if encoder.wait() != 0:
        raise RuntimeError("Could not write the person mask video.")
    return heads
