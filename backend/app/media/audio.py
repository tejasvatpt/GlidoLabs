"""Loudness envelope of the 16 kHz WAV and where speech actually is (Silero VAD, robust to music/noise)."""

from functools import cache
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


@cache
def vad_model():
    from silero_vad import load_silero_vad
    return load_silero_vad()


def speech_regions(wav: Path) -> list[tuple[float, float]]:
    import torch
    from silero_vad import get_speech_timestamps

    audio, _ = sf.read(wav, dtype="float32")
    regions = get_speech_timestamps(torch.from_numpy(audio), vad_model(), sampling_rate=SAMPLE_RATE,
                                    threshold=0.5, speech_pad_ms=60, return_seconds=True)
    return [(r["start"], r["end"]) for r in regions]
