from pydantic import BaseModel


class Word(BaseModel):
    text: str
    start: float | None = None
    end: float | None = None
    confidence: float | None = None


class Transcript(BaseModel):
    language: str
    source: str
    words: list[Word]

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)
