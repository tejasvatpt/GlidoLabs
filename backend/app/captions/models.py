from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.media.probe import VideoInfo
from app.transcription.models import Word

Role = Literal["normal", "emphasis", "hook"]


class Weights(BaseModel):
    energy: float
    stretch: float
    pause: float
    lexical: float


class EngineConfig(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    max_words: int
    max_lines_fill: float
    pause_break_s: float
    hold_s: float
    gap_fill_s: float
    hook_min_s: float
    hook_lead_s: float
    min_letters: int
    weights: Weights
    emphasis_threshold: float
    emphasis_min_lexical: float
    hook_threshold: float
    hook_stem_letters: int
    hook_min_lexical: float
    hook_min_gap_s: float
    hooks_per_minute: float


class FeaturedWord(Word):
    energy: float
    stretch: float
    pause_before: float
    lexical: float
    energy_z: float = 0
    stretch_z: float = 0
    pause_z: float = 0


class ScoredWord(FeaturedWord):
    emphasis: float
    role: Role


class CaptionWord(BaseModel):
    text: str
    start: float
    end: float
    role: Role
    emphasis: float
    display: str | None = None  # hook text as shown, e.g. "baarah" -> "12"


class HookPosition(BaseModel):
    """Fractions of the frame: x is the left edge (align "left") or the centre (align "center"); y is the text top."""
    x: float
    y: float
    align: Literal["left", "center"]
    font_size: float


class CaptionGroup(BaseModel):
    id: int
    layer: Literal["normal", "hook"]
    start: float
    end: float
    lines: list[list[int]]
    words: list[CaptionWord]
    position: HookPosition | None = None


class CaptionTrack(BaseModel):
    version: int = 1
    style: str
    source: str
    video: VideoInfo
    groups: list[CaptionGroup]
