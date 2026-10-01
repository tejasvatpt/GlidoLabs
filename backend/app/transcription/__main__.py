"""python -m app.transcription <video> [script.txt] -> transcript.json in the job folder"""

import sys
from pathlib import Path

from app.media.ingest import ingest
from app.transcription.sources import get_source

video = Path(sys.argv[1])
script = Path(sys.argv[2]).read_text(encoding="utf-8") if len(sys.argv) > 2 else None
job = ingest(video)
transcript = get_source(script).transcribe(job.audio_path, script)
(job.job_dir / "transcript.json").write_text(transcript.model_dump_json(indent=2), encoding="utf-8")
print(job.job_dir)
print(transcript.text)
