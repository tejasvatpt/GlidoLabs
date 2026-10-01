"""Per-word prosody features from the 16 kHz WAV: loudness, stretch, pause, lexical weight."""

from functools import cache
from pathlib import Path

import numpy as np
import soundfile as sf

from app.captions.models import FeaturedWord
from app.transcription.cleanup import core
from app.transcription.models import Word

SAMPLE_RATE, FRAME, HOP = 16000, 400, 160  # 25 ms frames every 10 ms


@cache
def stopwords() -> frozenset[str]:
    return frozenset((Path(__file__).parent / "stopwords.txt").read_text(encoding="utf-8").split())


def energy_db(wav: Path) -> np.ndarray:
    audio, _ = sf.read(wav, dtype="float32")
    audio = audio.mean(axis=1) if audio.ndim > 1 else audio
    count = max(1, 1 + (len(audio) - FRAME) // HOP)
    index = np.minimum(np.arange(FRAME) + HOP * np.arange(count)[:, None], len(audio) - 1)
    return 20 * np.log10(np.sqrt((audio[index] ** 2).mean(axis=1)) + 1e-9)


def robust_z(values: list[float]) -> np.ndarray:
    v = np.asarray(values, dtype=float)
    median = np.median(v)
    spread = 1.4826 * np.median(np.abs(v - median)) or v.std() or 1.0
    return np.clip((v - median) / spread, -3, 3)


def local_contrast(values: list[float], radius: int = 4) -> list[float]:
    return [v - float(np.median(values[max(0, i - radius):i + radius + 1])) for i, v in enumerate(values)]


def word_features(words: list[Word], wav: Path, min_letters: int = 4) -> list[FeaturedWord]:
    if not words:
        return []
    db = energy_db(wav)
    frame = lambda t: min(int(t * SAMPLE_RATE / HOP), len(db) - 1)
    out = []
    for i, w in enumerate(words):
        word = core(w.text)
        out.append(FeaturedWord(
            **w.model_dump(),
            energy=float(db[frame(w.start):frame(w.end) + 1].mean()),
            stretch=(w.end - w.start) / max(1, len(word)),
            pause_before=max(0.0, w.start - words[i - 1].end) if i else 0.0,
            lexical=0.0 if word in stopwords() else round(min(1.0, max(0, len(word) - min_letters + 1) / 6), 3),
        ))
    # loudness counts relative to nearby words: emphasis is local contrast, not overall volume
    energy = local_contrast([w.energy for w in out])
    for name, values in (("energy", energy), ("stretch", [w.stretch for w in out]), ("pause", [w.pause_before for w in out])):
        for w, z in zip(out, robust_z(values)):
            setattr(w, f"{name}_z", round(float(z), 3))
    return out
