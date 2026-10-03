"""Transcript + audio + style (+ where the speaker's head is) -> captions.json, the contract consumed by the renderer."""

from pathlib import Path

from app.captions.emphasis import score_words
from app.captions.features import word_features
from app.captions.layout import TextMeasure
from app.captions.models import CaptionTrack, EngineConfig
from app.captions.placement import place_hooks
from app.captions.segmenter import segment
from app.config import load_style
from app.media.probe import VideoInfo
from app.transcription.models import Transcript


def build_captions(transcript: Transcript, wav: Path, video: VideoInfo, style: str = "eclipse",
                   force_hooks: list[str] = (), heads: list | None = None) -> CaptionTrack:
    spec = load_style(style)
    cfg = EngineConfig(**spec["engine"])
    scored = score_words(word_features(transcript.words, wav, cfg.min_letters), cfg, video.duration, force_hooks)
    groups = segment(scored, cfg, TextMeasure(spec, video.width))
    place_hooks(groups, heads or [], video.fps, spec, video.width, video.height)
    return CaptionTrack(style=style, source=transcript.source, video=video, groups=groups)
