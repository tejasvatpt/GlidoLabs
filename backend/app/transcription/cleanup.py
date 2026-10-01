"""Make raw words render-safe: spelling, punctuation, order, and timings snapped to actual speech."""

import json
import re
from difflib import SequenceMatcher
from functools import cache
from pathlib import Path

import numpy as np

from app.media.audio import FRAME_S, energy_db, voiced
from app.transcription.models import Word

MIN_WORD_S = 0.08
PUNCT_ONLY = re.compile(r"^[^\w]+$")
WORD_PARTS = re.compile(r"^(\W*)([\w']+)(\W*)$")


def core(text: str) -> str:
    return re.sub(r"[^\w']", "", text.lower())


@cache
def spellings() -> dict[str, str]:
    return json.loads((Path(__file__).parent / "spelling.json").read_text(encoding="utf-8"))


def respell(text: str) -> str:
    """ASR spellings -> common social-media Hinglish ('mainne' -> 'maine'), keeping case and punctuation."""
    if not (parts := WORD_PARTS.match(text)) or not (fix := spellings().get(parts[2].lower())):
        return text
    return parts[1] + (fix.capitalize() if parts[2][0].isupper() else fix) + parts[3]


def snap_to_speech(words: list[Word], wav: Path) -> None:
    """Move each word's start forward and end back onto voiced audio, so captions never show over silence."""
    speech = np.flatnonzero(voiced(energy_db(wav)))
    for w in words:
        inside = speech[(speech >= int(w.start / FRAME_S)) & (speech < int(w.end / FRAME_S) + 1)]
        if inside.size:
            w.start, w.end = max(w.start, float(inside[0] * FRAME_S)), min(w.end, float((inside[-1] + 1) * FRAME_S))


def clean_words(words: list[Word], wav: Path, duration: float) -> list[Word]:
    out: list[Word] = []
    for w in words:
        text = w.text.strip()
        if PUNCT_ONLY.match(text or "x") and out:
            out[-1].text += text
        elif text:
            out.append(w.model_copy(update={"text": text}))

    prev_end = 0.0
    for w in out:
        start = min(max(w.start, prev_end), duration)
        w.start, w.end = start, min(max(w.end if w.end is not None else start + 0.3, start + MIN_WORD_S), duration)
        prev_end = w.end
    snap_to_speech(out, wav)
    for w in out:
        w.start, w.end = round(w.start, 3), round(max(w.end, w.start + MIN_WORD_S), 3)
    return out


def spread(words: list[Word], start: float, end: float) -> None:
    step = (end - start) / max(1, len(words))
    for i, w in enumerate(words):
        w.start, w.end = start + i * step, start + (i + 1) * step


def align_script(script: list[Word], heard: list[Word]) -> list[Word]:
    """Exact script text, timings borrowed from matching heard words; gaps are interpolated."""
    a, b = [core(w.text) for w in script], [core(w.text) for w in heard]
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                script[i1 + k].start, script[i1 + k].end = heard[j1 + k].start, heard[j1 + k].end
        elif tag == "replace":
            spread(script[i1:i2], heard[j1].start, heard[j2 - 1].end)

    i = 0
    while i < len(script):
        if script[i].start is not None:
            i += 1
            continue
        j = next((k for k in range(i, len(script)) if script[k].start is not None), len(script))
        left = script[i - 1].end if i else heard[0].start
        right = script[j].start if j < len(script) else left + 0.3 * (j - i)
        spread(script[i:j], left, right)
        i = j
    return script
