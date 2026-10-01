import json
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
STYLES_DIR = REPO_ROOT / "styles"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    storage_dir: Path = REPO_ROOT / "storage"
    max_upload_mb: int = 500
    max_duration_s: float = 600
    asr_device: str = "cuda"

    @property
    def jobs_dir(self) -> Path:
        path = self.storage_dir if self.storage_dir.is_absolute() else REPO_ROOT / self.storage_dir
        return path / "jobs"


def style_names() -> list[str]:
    return sorted(p.parent.name for p in STYLES_DIR.glob("*/style.json"))


def load_style(name: str) -> dict:
    return json.loads((STYLES_DIR / name / "style.json").read_text(encoding="utf-8"))


settings = Settings()
