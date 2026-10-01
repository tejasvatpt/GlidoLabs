import subprocess
import wave
from pathlib import Path

import pytest

from app.media.ingest import ingest
from app.media.probe import MediaError, probe

REPO = Path(__file__).resolve().parents[2]
ECLIPSE = REPO / "samples" / "Eclipse.mp4"


def make_clip(path: Path, audio: bool) -> Path:
    args = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=320x240:r=25:d=1"]
    if audio:
        args += ["-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-shortest"]
    subprocess.run(args + [str(path)], check=True)
    return path


@pytest.mark.skipif(not ECLIPSE.exists(), reason="reference sample missing")
def test_eclipse_metadata_and_audio(tmp_path):
    res = ingest(ECLIPSE, jobs_dir=tmp_path)
    v = res.video
    assert (v.width, v.height, v.fps) == (1080, 1920, 30)
    assert abs(v.duration - 50.2) < 0.1
    assert v.has_audio
    with wave.open(str(res.audio_path)) as w:
        assert w.getframerate() == 16000
        assert w.getnchannels() == 1
        assert abs(w.getnframes() / 16000 - v.duration) < 0.2


def test_rejects_video_without_audio(tmp_path):
    clip = make_clip(tmp_path / "silent.mp4", audio=False)
    assert probe(clip).has_audio is False
    with pytest.raises(MediaError, match="no audio"):
        ingest(clip, jobs_dir=tmp_path / "jobs")


def test_rejects_unsupported_extension(tmp_path):
    bad = tmp_path / "notes.txt"
    bad.write_text("hello")
    with pytest.raises(MediaError, match="Unsupported"):
        ingest(bad, jobs_dir=tmp_path)


def test_rejects_non_video_with_video_extension(tmp_path):
    fake = tmp_path / "fake.mp4"
    fake.write_text("not a video")
    with pytest.raises(MediaError):
        ingest(fake, jobs_dir=tmp_path)


def test_accepts_webm(tmp_path):
    clip = make_clip(tmp_path / "clip.webm", audio=True)
    res = ingest(clip, jobs_dir=tmp_path / "jobs")
    assert res.video.has_audio and res.input_path.suffix == ".webm"
