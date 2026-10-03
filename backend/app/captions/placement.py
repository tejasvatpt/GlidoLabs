"""Places each hook around the speaker's head, as in the Eclipse reference: long words centred above the head,
short words on the left at head height, always low enough that the head covers part of the word."""

from app.captions.layout import font
from app.captions.models import CaptionGroup, HookPosition
from app.config import STYLES_DIR
from app.transcription.cleanup import core

NUMBERS = {"das": "10", "gyarah": "11", "barah": "12", "baarah": "12", "terah": "13", "chaudah": "14", "pandrah": "15",
           "solah": "16", "satrah": "17", "atharah": "18", "unnis": "19", "bees": "20", "tees": "30", "chalis": "40",
           "pachas": "50", "pachaas": "50", "sau": "100", "hazaar": "1000", "hazar": "1000", "lakh": "1 LAKH",
           "ten": "10", "eleven": "11", "twelve": "12", "twenty": "20", "fifty": "50", "hundred": "100", "thousand": "1000"}


def hook_text(word: str) -> str:
    return NUMBERS.get(core(word), word).upper()


def head_at(heads: list, t: float, fps: float) -> tuple[float, float]:
    """Head position near time t (falls back to a typical talking-head framing)."""
    i = min(int(t * fps), len(heads) - 1) if heads else -1
    nearby = [h for h in heads[max(0, i - 5):i + 6] if h] if heads else []
    return nearby[len(nearby) // 2] if nearby else (0.28, 0.5)


def place_hooks(groups: list[CaptionGroup], heads: list, fps: float, style: dict, width: int, height: int) -> None:
    h, spec = style["hook"], style["fonts"]["hook"]
    path = str(STYLES_DIR / style["name"] / spec["file"])
    for g in (g for g in groups if g.layer == "hook"):
        word = g.words[0]
        word.display = hook_text(word.text)
        unit = font(path, 100, spec["weight"]).getbbox(word.display)
        size = min(h["fontSize"] * width, h["maxWidth"] * width * 100 / (unit[2] - unit[0]))
        text_w, text_h = (unit[2] - unit[0]) * size / 100 / width, (unit[3] - unit[1]) * size / 100 / height
        head_top, head_x = head_at(heads, word.start, fps)
        top = max(h["minTopY"], head_top - (1 - h["headOverlap"]) * text_h)
        if text_w < h["shortWordWidth"]:  # short word: left of the head, at head height
            g.position = HookPosition(x=h["sideMarginX"], y=top + h["shortWordDrop"] * text_h, align="left", font_size=size / width)
        else:
            g.position = HookPosition(x=min(max(head_x, text_w / 2 + 0.02), 1 - text_w / 2 - 0.02), y=top,
                                      align="center", font_size=size / width)
