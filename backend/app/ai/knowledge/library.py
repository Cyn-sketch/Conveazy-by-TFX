"""Condition trigger words and calming exercises (static, reviewed data files)."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).resolve().parent


@lru_cache
def triggers() -> dict:
    return json.loads((_DIR / "triggers.json").read_text())["conditions"]


@lru_cache
def exercises() -> dict[str, dict]:
    return {e["id"]: e for e in json.loads((_DIR / "exercises.json").read_text())["exercises"]}


def conditions_in(text: str) -> list[str]:
    """Conditions the person chose to name in their own words (never inferred)."""
    return [k for k, c in triggers().items() if re.search(c["detect"], text or "", re.I)]


def hurt_points_text(disclosed: list[str]) -> str:
    t = triggers()
    return "\n".join(f"{t[k]['label']}: " + "; ".join(f"{i['phrase']} ({i['why']})" for i in t[k]["items"])
                     for k in disclosed if k in t)


def condition_lexicon(disclosed: list[str]) -> list[tuple[str, str, str, str | None]]:
    """Entries in the mock softener's (pattern, category, how_it_lands, replacement) format."""
    t = triggers()
    return [(i["pattern"], "trigger", f"{i['why']} This is a common hurt point for people who live with {t[k]['label']}.",
             i["instead"]) for k in disclosed if k in t for i in t[k]["items"]]


def exercise_menu() -> str:
    return "\n".join(f"- {e['id']}: {e['name']} ({e['good']})" for e in exercises().values())
