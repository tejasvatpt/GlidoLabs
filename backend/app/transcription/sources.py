"""Replaceable transcript sources. Every source returns the same Transcript shape."""

from functools import cache
from pathlib import Path

import soundfile as sf

from app.config import settings
from app.transcription.cleanup import align_script, clean_words
from app.transcription.models import Transcript, Word

APEX_MODEL = "Oriserve/Whisper-Hindi2Hinglish-Apex"
TURBO_ALIGNMENT_HEADS = [[2, 4], [2, 11], [3, 3], [3, 6], [3, 11], [3, 14]]


def words_from_text(text: str) -> list[Word]:
    return [Word(text=t) for t in text.split()]


class ApexSource:
    """Uploaded videos: Roman-Hinglish ASR with word timestamps."""

    name = "apex"

    @staticmethod
    @cache
    def pipeline():
        import torch
        from transformers import pipeline

        use_gpu = settings.asr_device == "cuda" and torch.cuda.is_available()
        pipe = pipeline(
            "automatic-speech-recognition",
            model=APEX_MODEL,
            dtype=torch.float16 if use_gpu else torch.float32,
            device="cuda:0" if use_gpu else "cpu",
            generate_kwargs={"task": "transcribe", "language": "en"},
        )
        # Apex ships without word-timing heads; it shares large-v3-turbo's architecture, so reuse its heads
        pipe.model.generation_config.alignment_heads = TURBO_ALIGNMENT_HEADS
        return pipe

    def transcribe(self, wav: Path, script: str | None = None) -> Transcript:
        result = self.pipeline()(str(wav), chunk_length_s=30, batch_size=1, return_timestamps="word")
        words = [Word(text=c["text"], start=c["timestamp"][0], end=c["timestamp"][1]) for c in result["chunks"]]
        return Transcript(language="hinglish", source=self.name, words=clean_words(words, sf.info(wav).duration))


class ScriptSource:
    """Glido-generated videos: the script is the text; audio only supplies timing."""

    name = "script"

    def transcribe(self, wav: Path, script: str) -> Transcript:
        heard = ApexSource().transcribe(wav).words
        words = align_script(words_from_text(script), heard) if heard else words_from_text(script)
        return Transcript(language="hinglish", source=self.name, words=clean_words(words, sf.info(wav).duration))


def get_source(script: str | None = None):
    return ScriptSource() if script else ApexSource()
