import subprocess

from fastapi.testclient import TestClient

from app import jobs
from app.main import app
from app.transcription.models import Transcript, Word

client = TestClient(app)


def fake_transcribe(wav, script=None):
    words = [Word(text=t, start=0.1 + i * 0.3, end=0.35 + i * 0.3) for i, t in enumerate("bhai ye kitna pyara hai".split())]
    return Transcript(language="hinglish", source="fake", words=words)


def test_upload_to_ready_and_captions(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs.settings, "storage_dir", tmp_path)
    monkeypatch.setattr(jobs, "transcribe", fake_transcribe)
    monkeypatch.setattr(jobs.worker, "submit", lambda fn, *a: fn(*a))
    clip = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=320x240:r=25:d=2",
                    "-f", "lavfi", "-i", "sine=duration=2", "-shortest", str(clip)], check=True)

    job_id = client.post("/api/jobs", files={"file": ("clip.mp4", clip.read_bytes(), "video/mp4")}).json()["job_id"]
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "ready"
    captions = client.get(f"/api/jobs/{job_id}/captions").json()
    assert captions["video"]["width"] == 320 and sum(len(g["words"]) for g in captions["groups"]) == 5
    assert client.get(f"/media/{job_id}/input", headers={"Range": "bytes=0-99"}).status_code == 206
    assert client.get(f"/api/jobs/{job_id}/download").status_code == 409


def test_rejects_bad_type_and_unknown_job():
    assert client.post("/api/jobs", files={"file": ("a.txt", b"x", "text/plain")}).status_code == 400
    assert client.get("/api/jobs/doesnotexist").status_code == 404
    assert client.get("/api/styles").json() == ["eclipse"]
