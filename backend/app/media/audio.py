"""Loudness envelope of the 16 kHz WAV and where speech actually is."""

from pathlib import Path

import numpy as np
import soundfile as sf

SAMPLE_RATE, FRAME, HOP = 16000, 400, 160  # 25 ms frames every 10 ms
FRAME_S = HOP / SAMPLE_RATE


def energy_db(wav: Path) -> np.ndarray:
    audio, _ = sf.read(wav, dtype="float32")
    audio = audio.mean(axis=1) if audio.ndim > 1 else audio
    count = max(1, 1 + (len(audio) - FRAME) // HOP)
    index = np.minimum(np.arange(FRAME) + HOP * np.arange(count)[:, None], len(audio) - 1)
    return 20 * np.log10(np.sqrt((audio[index] ** 2).mean(axis=1)) + 1e-9)


def voiced(db: np.ndarray) -> np.ndarray:
    """Frames well above the noise floor and within 40 dB of the loudest speech."""
    return db > max(np.percentile(db, 10) + 12, np.percentile(db, 99) - 40)
