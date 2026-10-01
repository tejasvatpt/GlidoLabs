"""Bridge to the Remotion renderer: writes props.json and runs render.mjs, reporting progress."""

import json
import subprocess
from collections import deque
from pathlib import Path
from typing import Callable

from app.config import REPO_ROOT

RENDERER_DIR = REPO_ROOT / "renderer"


def render_video(props: dict, props_path: Path, output: Path, on_progress: Callable[[float], None]) -> Path:
    props_path.write_text(json.dumps(props), encoding="utf-8")
    proc = subprocess.Popen(["node", "render.mjs", str(props_path), str(output)], cwd=RENDERER_DIR,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            errors="replace", shell=False)
    tail = deque(maxlen=15)
    for line in proc.stdout:
        tail.append(line.rstrip())
        if line.startswith('{"progress"'):
            on_progress(json.loads(line)["progress"])
    if proc.wait() != 0 or not output.exists():
        raise RuntimeError("Render failed:\n" + "\n".join(tail))
    return output
