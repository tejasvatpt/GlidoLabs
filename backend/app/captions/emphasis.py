"""Weighted emphasis score per word, then role: hook (budgeted, spaced), emphasis or normal."""

from app.captions.models import EngineConfig, FeaturedWord, ScoredWord
from app.transcription.cleanup import core


def score_words(words: list[FeaturedWord], cfg: EngineConfig, duration: float,
                force_hooks: list[str] = ()) -> list[ScoredWord]:
    w = cfg.weights
    scores = [w.energy * f.energy_z + w.stretch * f.stretch_z + w.pause * f.pause_z + w.lexical * f.lexical
              for f in words]
    forced = {core(h) for h in force_hooks}
    hooks = [i for i, f in enumerate(words) if core(f.text) in forced]
    budget = max(len(hooks), round(cfg.hooks_per_minute * duration / 60))

    spaced = lambda i: all(abs(words[i].start - words[j].start) >= cfg.hook_min_gap_s for j in hooks)
    for i in sorted(range(len(words)), key=lambda i: -scores[i]):
        if len(hooks) >= budget or scores[i] < cfg.hook_threshold:
            break
        if words[i].lexical and i not in hooks and spaced(i):
            hooks.append(i)

    role = lambda i: "hook" if i in hooks else (
        "emphasis" if words[i].lexical and scores[i] >= cfg.emphasis_threshold else "normal")
    return [ScoredWord(**f.model_dump(), emphasis=round(scores[i], 3), role=role(i)) for i, f in enumerate(words)]
