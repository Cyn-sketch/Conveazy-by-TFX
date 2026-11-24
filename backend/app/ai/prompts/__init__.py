"""Version-controlled prompts. Each file has front matter with a stable `version` id that
is stored alongside every AI response for auditability."""
from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).parent


@lru_cache
def load_prompt(name: str) -> tuple[str, str]:
    raw = (_DIR / f"{name}.v1.md").read_text()
    _, front, body = raw.split("---", 2)
    meta = dict(line.split(": ", 1) for line in front.strip().splitlines())
    return meta["version"], body.strip()
