"""Pause-aware grouping of scored words into caption groups with timing and line breaks."""

from app.captions.models import CaptionGroup, CaptionWord, EngineConfig, ScoredWord


def joined_len(words) -> int:
    return len(" ".join(w.text for w in words))


def should_break(group: list[ScoredWord], word: ScoredWord, cfg: EngineConfig) -> bool:
    last = group[-1]
    return (word.start - last.end >= cfg.pause_break_s
            or last.text[-1] in ".?!"
            or (last.text[-1] == "," and len(group) >= 2)
            or len(group) >= cfg.max_words
            or joined_len(group + [word]) > cfg.max_chars)


def split_groups(words: list[ScoredWord], cfg: EngineConfig) -> list[tuple[str, list[ScoredWord]]]:
    groups, current = [], []
    for w in words:
        if w.role == "hook" or (current and should_break(current, w, cfg)):
            if current:
                groups.append(("normal", current))
            current = []
        if w.role == "hook":
            groups.append(("hook", [w]))
        else:
            current.append(w)
    if current:
        groups.append(("normal", current))
    return groups


def merge_orphans(groups, cfg: EngineConfig):
    def can_join(a, b):
        return (a[0] == b[0] == "normal" and len(a[1]) + len(b[1]) <= cfg.max_words + 1
                and b[1][0].start - a[1][-1].end < 0.2 and a[1][-1].text[-1] not in ".?!")

    out = []
    for g in groups:
        if out and g[0] == "normal" and (len(g[1]) == 1 or len(out[-1][1]) == 1) and can_join(out[-1], g):
            out[-1] = ("normal", out[-1][1] + g[1])
        else:
            out.append(g)
    return out


def break_lines(words, max_chars: int) -> list[list[int]]:
    n = len(words)
    if n < 2 or joined_len(words) <= max_chars:
        return [list(range(n))]
    k = min(range(1, n), key=lambda k: abs(joined_len(words[:k]) - joined_len(words[k:])))
    return [list(range(k)), list(range(k, n))]


def segment(words: list[ScoredWord], cfg: EngineConfig) -> list[CaptionGroup]:
    groups = [CaptionGroup(
        id=i, layer=layer, start=ws[0].start, end=ws[-1].end + cfg.hold_s,
        lines=break_lines(ws, cfg.line_max_chars),
        words=[CaptionWord(**w.model_dump(include={"text", "start", "end", "role", "emphasis"})) for w in ws],
    ) for i, (layer, ws) in enumerate(merge_orphans(split_groups(words, cfg), cfg), 1)]

    for layer in ("normal", "hook"):
        same = [g for g in groups if g.layer == layer]
        for g, nxt in zip(same, same[1:] + [None]):
            if layer == "hook":
                g.end = max(g.end, g.start + cfg.hook_min_s)
            if nxt:
                g.end = nxt.start if nxt.start - g.end < cfg.gap_fill_s else min(g.end, nxt.start)
            g.end = round(g.end, 3)
    return groups
