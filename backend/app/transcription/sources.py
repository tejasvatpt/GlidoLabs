"""Replaceable transcript sources. Every source returns the same Transcript shape."""

from functools import cache
from pathlib import Path

import soundfile as sf

from app.config import settings
from app.transcription.cleanup import align_script, clean_words, respell
from app.transcription.models import Transcript, Word

APEX_MODEL = "Oriserve/Whisper-Hindi2Hinglish-Apex"
TURBO_ALIGNMENT_HEADS = [[2, 4], [2, 11], [3, 3], [3, 6], [3, 11], [3, 14]]


def words_from_text(text: str) -> list[Word]:
    return [Word(text=t) for t in text.split()]


@cache
def apex_pipeline():
    import torch
    from transformers import pipeline

    use_gpu = settings.asr_device == "cuda" and torch.cuda.is_available()
    pipe = pipeline("automatic-speech-recognition", model=APEX_MODEL, device="cuda:0" if use_gpu else "cpu",
                    dtype=torch.float16 if use_gpu else torch.float32,
                    generate_kwargs={"task": "transcribe", "language": "en"})
    # Apex ships without word-timing heads; it shares large-v3-turbo's architecture, so reuse its heads
    pipe.model.generation_config.alignment_heads = TURBO_ALIGNMENT_HEADS
    # word timing only needs decoder cross-attention; encoder attention maps would cost ~3 GB of VRAM
    encoder = pipe.model.model.encoder
    forward = encoder.forward
    encoder.forward = lambda *args, **kwargs: forward(*args, **{**kwargs, "output_attentions": False})
    return pipe


def heard_words(wav: Path) -> list[Word]:
    result = apex_pipeline()(str(wav), chunk_length_s=30, batch_size=1, return_timestamps="word")
    return [Word(text=c["text"], start=c["timestamp"][0], end=c["timestamp"][1]) for c in result["chunks"]]


def transcribe(wav: Path, script: str | None = None) -> Transcript:
    """No script: Apex ASR (uploaded videos). Script: exact script text, audio only supplies timing."""
    heard = heard_words(wav)
    if script:
        words, source = align_script(words_from_text(script), heard) if heard else [], "script"
    else:
        words, source = [w.model_copy(update={"text": respell(w.text)}) for w in heard], "apex"
    return Transcript(language="hinglish", source=source, words=clean_words(words, wav, sf.info(wav).duration))
