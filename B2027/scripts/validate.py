#!/usr/bin/env python3
"""Validate B2027 Seeds and optional generated session content (Club DoD)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from common import (
    NEW_SHAPE,
    SEEDS,
    content_path,
    find_session,
    lesson_model_for,
    load_json,
    normalize_level,
)

SEED_VALIDATIONS: list[tuple[Path, Path]] = [
    (SEEDS / "configuration.json", SEEDS / "configuration_schema.json"),
    (SEEDS / "audience.json", SEEDS / "audience_schema.json"),
    (SEEDS / "session_index.json", SEEDS / "session_index_schema.json"),
    (SEEDS / "editorial.json", SEEDS / "editorial_schema.json"),
]

STAGE_ORDER = ["L-IN", "OVW", "ART", "TL", "Q3", "FP", "REF", "FBDC"]
HOST_ONLY = "HOST_ONLY"

JARGON = re.compile(
    r"\b(lead[- ]?in|overview|target language|freer practice|reflection|"
    r"wrap[- ]?up|fbdc|l-in|ovw|q3|art)\b",
    re.I,
)
TIMING = re.compile(
    r"(90|120|1\.5|2(\.0)?)\s*(s|sec|secs|second|seconds|min|mins|minute|minutes)"
    r"|timed\s+reflection|stopwatch",
    re.I,
)
CEREMONY = re.compile(
    r"welcome to (today|our|this)|here's how we('ll| will) spend|"
    r"our goal today|speaking club!|map the session|session map",
    re.I,
)
AGENDA_MAP = re.compile(
    r"(^|\n)\s*\d+\.\s+\*?\*?Welcome|\bL-IN\b.*\bOVW\b|\bTarget Language\b.*\bArticle\b",
    re.I,
)
SCRIPT_Y = re.compile(
    r"allocate\s+\d+|divide participants into|facilitate a brief|"
    r"open the session by greeting",
    re.I,
)


def validate_pair(instance_path: Path, schema_path: Path) -> tuple[bool, list[str]]:
    instance = load_json(instance_path)
    schema = load_json(schema_path)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(instance),
        key=lambda e: list(e.path),
    )
    messages = [
        f"  - {'/'.join(str(p) for p in error.path) or '(root)'}: {error.message}"
        for error in errors
    ]
    return len(errors) == 0, messages


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def stage_by_code(session: dict[str, Any], code: str) -> dict[str, Any] | None:
    for stage in session.get("stages", []):
        if isinstance(stage, dict) and stage.get("stage_code") == code:
            return stage
    return None


def find_banned(text: str, phrases: list[str]) -> list[str]:
    lower = text.lower()
    hits = []
    for phrase in phrases:
        if phrase.lower() in lower:
            hits.append(phrase)
    return hits


def budgets_for(config: dict[str, Any], session: dict[str, Any]) -> dict[str, Any]:
    level = str((session.get("session_metadata") or {}).get("cefr_level") or "")
    spec = (config.get("levels") or {}).get(level) or {}
    budgets = spec.get("budgets")
    if isinstance(budgets, dict):
        return budgets
    raise KeyError(f"no budgets for cefr_level {level!r}")


def validate_session_dod(
    session: dict[str, Any],
    config: dict[str, Any],
    editorial: dict[str, Any],
    shape: str | None = None,
    lesson_model: str | None = None,
) -> list[str]:
    messages: list[str] = []
    try:
        budgets = budgets_for(config, session)
    except KeyError as exc:
        return [f"  - {exc}"]
    banned = list(editorial.get("banned_phrases") or [])

    schema = load_json(SEEDS / "session_output_schema.json")
    errors = sorted(
        Draft202012Validator(schema).iter_errors(session),
        key=lambda e: list(e.path),
    )
    if errors:
        messages.extend(
            f"  - schema {'/'.join(str(p) for p in e.path) or '(root)'}: {e.message}"
            for e in errors
        )

    meta = session.get("session_metadata") or {}
    topic = str(meta.get("topic") or "").strip()
    unit_title = str(meta.get("unit_title") or "").strip()
    session_title = str(meta.get("session_title") or "").strip()
    if topic and unit_title and unit_title != topic:
        messages.append(
            f"  - session_metadata.unit_title must equal topic "
            f"(got {unit_title!r} vs {topic!r})"
        )
    if topic and session_title and session_title != topic:
        messages.append(
            f"  - session_metadata.session_title must equal topic "
            f"(got {session_title!r} vs {topic!r})"
        )
    if "track" in meta:
        messages.append(
            "  - session_metadata.track is unlocked; omit track — use unit_title"
        )

    stages = session.get("stages", [])
    if not isinstance(stages, list) or len(stages) != 8:
        messages.append("  - stages: expected exactly 8 stage objects")
    else:
        codes = [s.get("stage_code") for s in stages if isinstance(s, dict)]
        expected = STAGE_ORDER
        if codes != expected:
            messages.append(f"  - stages: order must be {expected}; got {codes}")

    for i, stage in enumerate(stages if isinstance(stages, list) else []):
        if not isinstance(stage, dict):
            continue
        title = str(stage.get("title") or "")
        student_title = str(stage.get("student_title") or "")
        code = stage.get("stage_code")
        student = str(stage.get("student_content") or "")
        teacher = str(stage.get("teacher_notes") or "")
        if title.strip() == student_title.strip():
            messages.append(
                f"  - stages[{i}] ({code}): title and student_title must differ"
            )
        if JARGON.search(student_title):
            messages.append(
                f"  - stages[{i}] ({code}): student_title has stage jargon"
            )
        materials = stage.get("materials") or {}
        if isinstance(materials, dict) and "tasks" in materials:
            messages.append(
                f"  - stages[{i}] ({code}): materials.tasks not allowed for Club speaking"
            )
        if code != "OVW" and student.strip() != HOST_ONLY:
            if CEREMONY.search(student) or AGENDA_MAP.search(student):
                messages.append(
                    f"  - stages[{i}] ({code}): student_content looks like ceremony/agenda "
                    "(channel discipline)"
                )
            hits = find_banned(student, banned)
            if hits:
                messages.append(
                    f"  - stages[{i}] ({code}): banned phrase(s) in student_content: {hits}"
                )
        if SCRIPT_Y.search(teacher) and len(teacher) > 420:
            messages.append(
                f"  - stages[{i}] ({code}): teacher_notes look like a long host script"
            )

    ovw = stage_by_code(session, "OVW")
    if ovw:
        sc = str(ovw.get("student_content") or "").strip()
        if sc != HOST_ONLY:
            messages.append(
                f"  - OVW student_content must be exactly {HOST_ONLY!r} (got {sc!r})"
            )

    lin = stage_by_code(session, "L-IN")
    if lin:
        sc = str(lin.get("student_content") or "")
        if CEREMONY.search(sc) or sc.strip().lower().startswith("welcome"):
            messages.append("  - L-IN: avoid welcome/ceremony; use situation questions")

    questions = (session.get("plan_sheet") or {}).get("questions") or []
    if not isinstance(questions, list) or len(questions) < budgets["plan_sheet_question_min"]:
        messages.append(
            f"  - plan_sheet.questions: need ≥ {budgets['plan_sheet_question_min']}"
        )

    tl = stage_by_code(session, "TL")
    if tl:
        materials = tl.get("materials") or {}
        items = materials.get("vocabulary_items") if isinstance(materials, dict) else None
        banks = materials.get("column_banks") if isinstance(materials, dict) else None
        if isinstance(items, list) and not (
            budgets["tl_item_min"] <= len(items) <= budgets["tl_item_max"]
        ):
            messages.append(
                f"  - TL vocabulary_items: need "
                f"{budgets['tl_item_min']}–{budgets['tl_item_max']}, got {len(items)}"
            )
        elif not isinstance(items, list) and not isinstance(banks, list):
            messages.append("  - TL: need vocabulary_items and/or column_banks")
        tl_student = str(tl.get("student_content") or "")
        if len(tl_student) > 280:
            messages.append(
                "  - TL student_content too long — keep a short use-these-phrases prompt"
            )

    art = stage_by_code(session, "ART")
    if art:
        materials = art.get("materials") or {}
        passage = materials.get("reading_passage") if isinstance(materials, dict) else None
        if not isinstance(passage, dict):
            messages.append("  - ART: missing materials.reading_passage")
        else:
            if not passage.get("passage_id"):
                messages.append("  - ART: reading_passage.passage_id required")
            body = str(passage.get("body") or "")
            wc = word_count(body)
            lo, hi = budgets["article_word_min"], budgets["article_word_max"]
            if wc < lo or wc > hi:
                messages.append(f"  - ART body word count {wc} outside {lo}–{hi}")
            hits = find_banned(body, banned)
            if hits:
                messages.append(f"  - ART body banned phrase(s): {hits}")
            student = str(art.get("student_content") or "")
            if body and body.strip() and body.strip() in student:
                messages.append(
                    "  - ART: full article body must not appear in student_content"
                )
            if len(student) > 220:
                messages.append(
                    "  - ART student_content too long — one short read-aloud prompt only"
                )

    ref = stage_by_code(session, "REF")
    if ref:
        notes = str(ref.get("teacher_notes") or "")
        if not TIMING.search(notes):
            messages.append(
                "  - REF teacher_notes: missing 90–120s / timer timing cues"
            )

    q3 = stage_by_code(session, "Q3")
    fp = stage_by_code(session, "FP")
    q3_text = str((q3 or {}).get("student_content") or "")
    fp_text = str((fp or {}).get("student_content") or "")
    lin_text = str((lin.get("student_content") if lin else "") or "")
    if not lesson_model:
        sid = str((session.get("session_metadata") or {}).get("session_id") or "")
        if sid.startswith("c"):
            lesson_model = lesson_model_for(sid)
    if lesson_model == "roleplay":
        if "riddle" in lin_text.lower():
            messages.append("  - L-IN: riddle is not used")
        lower_q3 = q3_text.lower()
        if "role" not in lower_q3 or "outcome" not in lower_q3:
            messages.append(
                "  - Q3 role-play must name the roles and the outcome"
            )
        if "?" not in fp_text:
            messages.append("  - FP role-play debrief needs a question")
    elif lesson_model == "debate":
        if "game" not in lin_text.lower():
            messages.append("  - L-IN must be a topic game")
        if "debate" not in q3_text.lower() and "side" not in q3_text.lower():
            messages.append("  - Q3 must be a debate with sides")
        if "opinion" not in fp_text.lower():
            messages.append("  - FP must be general opinion")
        if isinstance(questions, list) and len(questions) >= 3 and q3 and fp:
            missing_q3 = [q for q in questions[:3] if q not in q3_text]
            missing_fp = [q for q in questions[3:] if q not in fp_text]
            if missing_q3:
                messages.append(
                    f"  - Q3 student_content missing plan_sheet questions: {missing_q3!r}"
                )
            if missing_fp:
                messages.append(
                    f"  - FP student_content missing plan_sheet questions: {missing_fp!r}"
                )
    else:
        messages.append("  - lesson_model must be roleplay or debate")

    return messages


def resolve_content_file(
    session_id: str | None,
    path: Path | None,
    shape: str | None = None,
    level: str | None = None,
) -> Path:
    if path:
        return path
    if not session_id:
        raise ValueError("pass --session or --file")
    # Confirm session exists in index
    index = load_json(SEEDS / "session_index.json")
    find_session(index, session_id)
    if shape == NEW_SHAPE:
        print("Note: --shape new-shape is retired. Reading the level folder.", file=sys.stderr)
    return content_path(session_id, level)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate B2027 seeds / session content")
    parser.add_argument(
        "--content",
        action="store_true",
        help="Also validate a generated session (Club DoD)",
    )
    parser.add_argument("--session", help="session_id for --content")
    parser.add_argument(
        "--level",
        default="b2",
        choices=["b1", "b2", "c1"],
        help="CEFR folder for --content (default b2)",
    )
    parser.add_argument(
        "--shape",
        choices=[NEW_SHAPE],
        help="Validate content/{session}_new-shape.json instead of the default file",
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Explicit content JSON path for --content",
    )
    args = parser.parse_args(argv)

    failed = False

    print("Seeds")
    for instance_path, schema_path in SEED_VALIDATIONS:
        ok, messages = validate_pair(instance_path, schema_path)
        label = instance_path.name
        if ok:
            print(f"  PASS {label}")
        else:
            failed = True
            print(f"  FAIL {label}")
            print("\n".join(messages))

    # Budget sanity (mins ≤ maxes) not fully expressible in schema alone
    config = load_json(SEEDS / "configuration.json")
    editorial = load_json(SEEDS / "editorial.json")
    budget_ok = True
    for spec in (config.get("levels") or {}).values():
        b = spec.get("budgets") or {}
        if not (
            b.get("article_word_min", 1) <= b.get("article_word_max", 0)
            and b.get("tl_item_min", 1) <= b.get("tl_item_max", 0)
            and b.get("reflection_seconds_min", 1) <= b.get("reflection_seconds_max", 0)
        ):
            budget_ok = False
    if budget_ok:
        print("  PASS configuration budgets (min ≤ max)")
    else:
        failed = True
        print("  FAIL configuration budgets (min ≤ max)")

    if args.content:
        print("Content")
        try:
            content_file = resolve_content_file(
                args.session, args.file, args.shape, args.level
            )
        except (KeyError, ValueError) as exc:
            print(f"  FAIL {exc}")
            return 1
        if not content_file.is_file():
            print(f"  FAIL missing file: {content_file}")
            return 1
        session = load_json(content_file)
        expected = normalize_level(args.level)
        got = str((session.get("session_metadata") or {}).get("cefr_level") or "")
        if got != expected:
            print(f"  FAIL {content_file.name} is {got or 'missing a level'}, expected {expected}")
            return 1
        sid = str((session.get("session_metadata") or {}).get("session_id") or args.session or "")
        lesson_model = lesson_model_for(sid) if sid.startswith("c") else None
        messages = validate_session_dod(
            session,
            config,
            editorial,
            shape=args.shape,
            lesson_model=lesson_model,
        )
        if not messages:
            print(f"  PASS {content_file.name}")
        else:
            failed = True
            print(f"  FAIL {content_file.name}")
            print("\n".join(messages))

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
