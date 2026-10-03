"""Pause-aware grouping of scored words into caption groups, with pixel-width line breaks."""

from app.captions.layout import TextMeasure
from app.captions.models import CaptionGroup, CaptionWord, EngineConfig, ScoredWord


def should_break(group: list[ScoredWord], word: ScoredWord, cfg: EngineConfig, measure: TextMeasure) -> bool:
    last = group[-1]
    return (word.start - last.end >= cfg.pause_break_s
            or last.text[-1] in ".?!"
            or (last.text[-1] == "," and len(group) >= 2)
            or len(group) >= cfg.max_words
            or measure.width(group + [word]) > cfg.max_lines_fill * measure.line_width)


def split_groups(words: list[ScoredWord], cfg: EngineConfig, measure: TextMeasure):
    groups, current = [], []
    for w in words:
        if current and (w.role == "hook" or should_break(current, w, cfg, measure)):
            groups.append(("normal", current))
            current = []
        if w.role == "hook":
            groups.append(("hook", [w]))
        else:
            current.append(w)
    return groups + ([("normal", current)] if current else [])


def merge_orphans(groups, cfg: EngineConfig, measure: TextMeasure):
    out = []
    for layer, ws in groups:
        prev = out[-1][1] if out and out[-1][0] == layer == "normal" else None
        if (prev and 1 in (len(ws), len(prev)) and len(prev) + len(ws) <= cfg.max_words + 1
                and ws[0].start - prev[-1].end < 0.2 and prev[-1].text[-1] not in ".?!"
                and measure.width(prev + ws) <= cfg.max_lines_fill * measure.line_width):
            out[-1] = ("normal", prev + ws)
        else:
            out.append((layer, ws))
    return out


def break_lines(words: list[ScoredWord], measure: TextMeasure) -> list[list[int]]:
    """One line if it fits the caption width, else the split with the most even line widths."""
    n = len(words)
    if n < 2 or measure.width(words) <= measure.line_width:
        return [list(range(n))]
    k = min(range(1, n), key=lambda k: abs(measure.width(words[:k]) - measure.width(words[k:])))
    return [list(range(k)), list(range(k, n))]


def segment(words: list[ScoredWord], cfg: EngineConfig, measure: TextMeasure) -> list[CaptionGroup]:
    groups = [CaptionGroup(
        id=i, layer=layer, start=ws[0].start, end=ws[-1].end + cfg.hold_s,
        lines=break_lines(ws, measure) if layer == "normal" else [[0]],
        words=[CaptionWord(**w.model_dump(include={"text", "start", "end", "role", "emphasis"})) for w in ws],
    ) for i, (layer, ws) in enumerate(merge_orphans(split_groups(words, cfg, measure), cfg, measure), 1)]

    for layer in ("normal", "hook"):
        same = [g for g in groups if g.layer == layer]
        for g, nxt in zip(same, same[1:] + [None]):
            if layer == "hook":  # rises exactly when its word is spoken, readable for hookMinS, never beyond the speech after it
                speech_end = max(w.end for w in words if w.start < g.words[0].start + cfg.hook_min_s)
                g.end = min(max(g.end, g.words[0].start + cfg.hook_min_s), speech_end)
            if nxt:
                g.end = nxt.start if nxt.start - g.end < cfg.gap_fill_s else min(g.end, nxt.start)
            g.end = round(g.end, 3)
    return groups
