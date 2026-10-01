import re
import subprocess
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from app.transcription.cleanup import align_script, clean_words, respell
from app.transcription.models import Word
from app.transcription.sources import transcribe, words_from_text

DATA = Path(__file__).parent / "data"
ECLIPSE = Path(__file__).resolve().parents[2] / "samples" / "Eclipse.mp4"


def test_script_alignment_keeps_script_text_and_borrows_timing():
    heard = [Word(text=t, start=i * 0.5, end=i * 0.5 + 0.4) for i, t in enumerate(["bhai", "yeh", "bahut", "acha", "hai"])]
    words = align_script(words_from_text("Bhai ye bahut accha product hai."), heard)
    assert [w.text for w in words] == ["Bhai", "ye", "bahut", "accha", "product", "hai."]
    assert words[0].start == 0 and words[2].start == 1.0 and words[-1].end == 2.4
    assert all(a.start <= b.start for a, b in zip(words, words[1:]))


def test_respell_keeps_case_and_punctuation():
    assert [respell(t) for t in ["Mainne", "lie.", "pahli", "crystals,"]] == ["Maine", "liye.", "pehli", "crystals,"]


def test_words_snap_to_speech_after_leading_silence(tmp_path):
    sr = 16000
    audio = np.concatenate([np.zeros(sr * 3), 0.3 * np.sin(2 * np.pi * 220 * np.arange(sr * 2) / sr)])
    sf.write(tmp_path / "late.wav", audio, sr)
    words = clean_words([Word(text="bhai", start=0.0, end=3.6), Word(text="hai", start=3.6, end=4.9)],
                        tmp_path / "late.wav", duration=5.0)
    assert 2.95 <= words[0].start <= 3.05 and words[1].start == 3.6
    assert clean_words([Word(text="hai", start=1.0, end=1.2), Word(text=".", start=1.2, end=1.25)],
                       tmp_path / "late.wav", 5.0)[0].text == "hai."


@pytest.mark.slow
@pytest.mark.skipif(not ECLIPSE.exists(), reason="reference sample missing")
def test_apex_on_eclipse_first_20s(tmp_path):
    jiwer = pytest.importorskip("jiwer")
    wav = tmp_path / "first20.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(ECLIPSE), "-t", "20",
                    "-ac", "1", "-ar", "16000", str(wav)], check=True)
    t = transcribe(wav)
    clean = lambda s: " ".join(re.sub(r"[^a-z' ]", " ", s.lower()).split())
    wer = jiwer.wer(clean((DATA / "eclipse_first_20s.txt").read_text()), clean(t.text))
    print(f"\nAPEX: {t.text}\nWER: {wer:.3f}")
    assert not re.search(r"[ऀ-ॿ]", t.text), "output must be Roman script"
    assert wer < 0.3
