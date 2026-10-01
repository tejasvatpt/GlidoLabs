"""Transcript + audio + style -> captions.json, the contract consumed by the renderer."""

import json
from pathlib import Path

from app.captions.emphasis import score_words
from app.captions.features import word_features
from app.captions.models import CaptionTrack, EngineConfig
from app.captions.segmenter import segment
from app.config import REPO_ROOT
from app.media.probe import VideoInfo
from app.transcription.models import Transcript

STYLES_DIR = REPO_ROOT / "styles"


def load_style(name: str) -> dict:
    return json.loads((STYLES_DIR / name / "style.json").read_text(encoding="utf-8"))


def build_captions(transcript: Transcript, wav: Path, video: VideoInfo, style: str = "eclipse",
                   force_hooks: list[str] = ()) -> CaptionTrack:
    cfg = EngineConfig(**load_style(style)["engine"])
    words = [w for w in transcript.words if w.start is not None]
    featured = word_features(words, wav, cfg.min_letters)
    scored = score_words(featured, cfg, video.duration, force_hooks)
    return CaptionTrack(style=style, source=transcript.source, video=video, groups=segment(scored, cfg))
