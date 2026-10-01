"""Measures caption words in pixels with the style's real fonts, mirroring the renderer's spacing."""

from functools import cache

from PIL import ImageFont

from app.config import STYLES_DIR


@cache
def font(path: str, size: int, weight: int) -> ImageFont.FreeTypeFont:
    face = ImageFont.truetype(path, size)
    try:
        face.set_variation_by_axes([weight])  # variable fonts (Montserrat); static fonts raise
    except OSError:
        pass
    return face


class TextMeasure:
    def __init__(self, style: dict, video_width: int):
        c, folder = style["caption"], STYLES_DIR / style["name"]
        self.size, self.emphasis = round(c["fontSize"] * video_width), c["emphasis"]
        self.line_width = c["maxWidth"] * video_width
        self.gap = (c["wordGap"] + 0.28) * self.size  # word margin + active pill padding, as in CaptionedVideo.tsx
        self.fonts = {k: (str(folder / f["file"]), f["weight"]) for k, f in style["fonts"].items()}

    def word(self, text: str, role: str) -> float:
        if role == "normal":
            path, weight = self.fonts["caption"]
            return font(path, self.size, weight).getlength(text) + self.gap
        path, weight = self.fonts["emphasis"]
        text = text.upper() if self.emphasis["uppercase"] else text
        return font(path, round(self.size * self.emphasis["scale"]), weight).getlength(text) + self.gap

    def width(self, words) -> float:
        return sum(self.word(w.text, w.role) for w in words)
