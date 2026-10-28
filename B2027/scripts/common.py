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

NEW_SHAPE = "new-shape"
NEW_SHAPE_ORDER = ["L-IN", "OVW", "ART", "TL", "Q3", "FP", "REF", "FBDC"]
NEW_SHAPE_LABELS: dict[str, list[tuple[str, str]]] = {
    "roleplay": [
        ("L-IN", "Situation hook"),
        ("OVW", "Overview"),
        ("ART", "Article Reading"),
        ("TL", "Target Language"),
        ("Q3", "Role-play"),
        ("FP", "Role-play debrief"),
        ("REF", "Wrap — student reflection"),
        ("FBDC", "Wrap — host delivery & upgrades"),
    ],
    "debate": [
        ("L-IN", "Topic game"),
        ("OVW", "Overview"),
        ("ART", "Article Reading"),
        ("TL", "Target Language"),
        ("Q3", "Debate"),
        ("FP", "General opinion"),
        ("REF", "Wrap — student reflection"),
        ("FBDC", "Wrap — host delivery & upgrades"),
    ],
}


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


def class_number(session_id: str) -> int:
    return int(session_id[1:])


def lesson_model_for(session_id: str) -> str:
    """Odd class = role-play. Even class = game then debate."""
    return "roleplay" if class_number(session_id) % 2 == 1 else "debate"


def shape_stem(session_id: str) -> str:
    return f"{session_id}_{NEW_SHAPE}"


def compiled_shape_path(session_id: str) -> Path:
    return COMPILED / f"{shape_stem(session_id)}.json"


def content_shape_path(session_id: str) -> Path:
    return CONTENT / f"{shape_stem(session_id)}.json"


def find_session(index: dict[str, Any], session_id: str) -> dict[str, Any]:
    for row in index.get("sessions", []):
        if row.get("session_id") == session_id:
            return row
    raise KeyError(f"session_id not in session_index: {session_id}")


def stage_roster_markdown(
    labels: list[tuple[str, str]] | None = None,
) -> str:
    rows = labels if labels is not None else STAGE_HOST_LABELS
    lines = [
        f"{i}. **{code}** — {label}"
        for i, (code, label) in enumerate(rows, start=1)
    ]
    return "\n".join(lines)


def fill_ovw_template(
    template: str,
    labels: list[tuple[str, str]] | None = None,
) -> str:
    return template.replace("{{STAGE_ROSTER}}", stage_roster_markdown(labels))


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
