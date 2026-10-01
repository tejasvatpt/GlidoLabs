import numpy as np
import soundfile as sf

from app.captions.build import load_style
from app.captions.emphasis import score_words
from app.captions.features import word_features
from app.captions.models import EngineConfig, FeaturedWord, ScoredWord
from app.captions.segmenter import segment
from app.transcription.cleanup import clean_words
from app.transcription.models import Word

CFG = EngineConfig(**load_style("eclipse")["engine"])


def scored(spec):
    """spec: list of (text, start, end, role)"""
    return [ScoredWord(text=t, start=s, end=e, role=r, emphasis=0, energy=0, stretch=0, pause_before=0, lexical=1)
            for t, s, e, r in spec]


def flat(texts, step=0.3, start=0.0):
    return scored([(t, start + i * step, start + i * step + step - 0.02, "normal") for i, t in enumerate(texts)])


def test_pause_breaks_group():
    words = flat(["bhai", "ye", "kitna"]) + flat(["pyara", "hai"], start=1.5)
    assert [len(g.words) for g in segment(words, CFG)] == [3, 2]


def test_max_words_splits():
    groups = segment(flat(["ek", "do", "teen", "char", "paanch", "chhe", "saat", "aath"]), CFG)
    assert all(len(g.words) <= CFG.max_words for g in groups) and len(groups) == 2


def test_sentence_punctuation_breaks():
    groups = segment(flat(["store", "se.", "Aur", "maine"]), CFG)
    assert [g.words[-1].text for g in groups] == ["se.", "maine"]


def test_hook_is_own_layer_and_min_duration():
    words = scored([("black", 0, 0.3, "normal"), ("obsidian", 0.32, 0.6, "hook"), ("aur", 0.62, 0.8, "normal")])
    groups = segment(words, CFG)
    hook = next(g for g in groups if g.layer == "hook")
    assert hook.words[0].text == "obsidian" and hook.end - hook.start >= CFG.hook_min_s


def test_no_flicker_between_close_groups():
    a, b = segment(flat(["bhai", "ye", "kitna", "pyara", "lag", "raha"]), CFG)
    assert a.end == b.start


def test_long_group_breaks_into_two_lines():
    g = segment(flat(["mangwaya", "tha", "apne", "liye."]), CFG)[0]
    assert len(g.lines) == 2 and sum(map(len, g.lines)) == 4


def test_hooks_are_spaced_and_budgeted():
    words = [FeaturedWord(text=f"keyword{i}", start=i * 1.0, end=i * 1.0 + 0.5, energy=0, stretch=0,
                          pause_before=0, lexical=1, energy_z=3, stretch_z=3, pause_z=3) for i in range(20)]
    hooks = [w for w in score_words(words, CFG, duration=20) if w.role == "hook"]
    assert 1 <= len(hooks) <= round(CFG.hooks_per_minute * 20 / 60)
    assert all(b.start - a.start >= CFG.hook_min_gap_s for a, b in zip(hooks, hooks[1:]))


def test_force_hooks_and_stopwords_never_hooks():
    words = [FeaturedWord(text=t, start=i, end=i + 0.4, energy=0, stretch=0, pause_before=0, lexical=lex,
                          energy_z=z, stretch_z=z, pause_z=z) for i, (t, lex, z) in
             enumerate([("hai", 0, 3), ("pisces.", 1, 0), ("normal", 1, 0)])]
    roles = {w.text: w.role for w in score_words(words, CFG, duration=3, force_hooks=["Pisces"])}
    assert roles == {"hai": "normal", "pisces.": "hook", "normal": "normal"}


def test_loud_slow_word_scores_higher(tmp_path):
    sr = 16000
    t = np.arange(sr * 2) / sr
    audio = 0.05 * np.sin(2 * np.pi * 200 * t)
    audio[sr:] *= 8
    sf.write(tmp_path / "a.wav", audio, sr)
    words = [Word(text="quiet", start=0.2, end=0.5), Word(text="normal", start=0.5, end=0.8),
             Word(text="loud", start=1.2, end=1.9)]
    f = word_features(words, tmp_path / "a.wav")
    assert f[2].energy > f[0].energy + 15 and f[2].energy_z > 0 and f[2].stretch_z > 0


def test_cleanup_orders_and_attaches_punctuation():
    words = clean_words([Word(text="hai", start=1.0, end=1.2), Word(text=".", start=1.2, end=1.25),
                         Word(text="yaar", start=1.1, end=None)], duration=1.3)
    assert [w.text for w in words] == ["hai.", "yaar"]
    assert words[1].start >= words[0].end and words[1].end <= 1.3
