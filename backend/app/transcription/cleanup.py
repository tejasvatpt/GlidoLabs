"""Make raw words safe to render, and map a known script onto heard word timings."""

import re
from difflib import SequenceMatcher

from app.transcription.models import Word

MIN_WORD_S = 0.08
PUNCT_ONLY = re.compile(r"^[^\w]+$")


def core(text: str) -> str:
    return re.sub(r"[^\w']", "", text.lower())


def clean_words(words: list[Word], duration: float) -> list[Word]:
    out: list[Word] = []
    for w in words:
        text = w.text.strip()
        if not text:
            continue
        if PUNCT_ONLY.match(text) and out:
            out[-1].text += text
            continue
        out.append(w.model_copy(update={"text": text}))

    prev_end = 0.0
    for w in out:
        if w.start is None:
            continue
        start = min(max(w.start, prev_end), duration)
        end = w.end if w.end is not None else start + 0.3
        end = min(max(end, start + MIN_WORD_S), duration)
        w.start, w.end, prev_end = round(start, 3), round(end, 3), end
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
        left = script[i - 1].end if i else 0.0
        right = script[j].start if j < len(script) else left + 0.3 * (j - i)
        spread(script[i:j], left, right)
        i = j
    return script


def to_srt(words: list[Word]) -> str:
    stamp = lambda s: f"{int(s // 3600):02}:{int(s % 3600 // 60):02}:{int(s % 60):02},{int(s % 1 * 1000):03}"
    return "\n".join(f"{i}\n{stamp(w.start)} --> {stamp(w.end)}\n{w.text}\n"
                     for i, w in enumerate((w for w in words if w.start is not None), 1))
