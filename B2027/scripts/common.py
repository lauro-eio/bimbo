#!/usr/bin/env python3
"""Shared paths and JSON helpers for B2027 Club factory scripts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SEEDS = ROOT / "Seeds"
PROMPTS = ROOT / "prompts"
COMPILED = ROOT / "compiled"
CONTENT = ROOT / "content"

STAGE_HOST_LABELS: list[tuple[str, str]] = [
    ("L-IN", "Welcome to Class"),
    ("OVW", "Overview"),
    ("TL", "Target Language"),
    ("Q3", "3 questions"),
    ("ART", "Article Reading"),
    ("FP", "The Rest of the Questions"),
    ("REF", "Wrap — student reflection"),
    ("FBDC", "Wrap — host delivery & upgrades"),
]


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def compiled_path(session_id: str) -> Path:
    return COMPILED / f"{session_id}.json"


def content_path(session_id: str) -> Path:
    return CONTENT / f"{session_id}.json"


def find_session(index: dict[str, Any], session_id: str) -> dict[str, Any]:
    for row in index.get("sessions", []):
        if row.get("session_id") == session_id:
            return row
    raise KeyError(f"session_id not in session_index: {session_id}")


def stage_roster_markdown() -> str:
    lines = [
        f"{i}. **{code}** — {label}"
        for i, (code, label) in enumerate(STAGE_HOST_LABELS, start=1)
    ]
    return "\n".join(lines)


def fill_ovw_template(template: str) -> str:
    return template.replace("{{STAGE_ROSTER}}", stage_roster_markdown())


def auto_situational_brief(topic: str) -> str:
    topic = topic.strip()
    return (
        f"Open with a quick workplace hook, then speak to this session topic: {topic}"
    )


def linguistic_label_from_topic(topic: str, max_len: int = 96) -> str:
    """Short lexis focus label derived from the topic (no weekday track)."""
    topic = topic.strip()
    if len(topic) <= max_len:
        return topic
    cut = topic[: max_len - 1].rsplit(" ", 1)[0]
    return (cut or topic[: max_len - 1]) + "…"
