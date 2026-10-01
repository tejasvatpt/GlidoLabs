"""Per-word features: local loudness contrast, stretch, pause before, and lexical salience."""

from functools import cache
from pathlib import Path

import numpy as np
from wordfreq import zipf_frequency

from app.captions.models import FeaturedWord
from app.media.audio import FRAME_S, energy_db
from app.transcription.cleanup import core
from app.transcription.models import Word


@cache
def stopwords() -> frozenset[str]:
    return frozenset((Path(__file__).parent / "stopwords.txt").read_text(encoding="utf-8").split())


def lexical(word: str, min_letters: int) -> float:
    """Long and rare words carry the content (OBSIDIAN, PISCES); common words don't.
    Words barely attested in English (mostly romanised Hindi) get a neutral rarity instead of looking rare."""
    if word in stopwords():
        return 0.0
    length = min(1.0, max(0, len(word) - min_letters + 1) / 6)
    zipf = zipf_frequency(word, "en")
    rarity = 0.4 if zipf < 2.5 else min(1.0, (6.5 - zipf) / 3.5)
    return round(0.5 * length + 0.5 * rarity, 3)


def robust_z(values: list[float]) -> np.ndarray:
    v = np.asarray(values, dtype=float)
    median = np.median(v)
    spread = 1.4826 * np.median(np.abs(v - median)) or v.std() or 1.0
    return np.clip((v - median) / spread, -3, 3)


def word_features(words: list[Word], wav: Path, min_letters: int = 4) -> list[FeaturedWord]:
    if not words:
        return []
    db = energy_db(wav)
    frame = lambda t: min(int(t / FRAME_S), len(db) - 1)
    out = [FeaturedWord(
        **w.model_dump(),
        energy=float(db[frame(w.start):frame(w.end) + 1].mean()),
        stretch=(w.end - w.start) / max(1, len(core(w.text))),
        pause_before=max(0.0, w.start - words[i - 1].end) if i else 0.0,
        lexical=lexical(core(w.text), min_letters),
    ) for i, w in enumerate(words)]
    # loudness counts relative to nearby words: emphasis is local contrast, not overall volume
    energy = [w.energy - float(np.median([x.energy for x in out[max(0, i - 4):i + 5]])) for i, w in enumerate(out)]
    for name, values in (("energy", energy), ("stretch", [w.stretch for w in out]), ("pause", [w.pause_before for w in out])):
        for w, z in zip(out, robust_z(values)):
            setattr(w, f"{name}_z", round(float(z), 3))
    return out
