#!/usr/bin/env python3
"""Compile one B2027 Club session reference from Seeds."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from common import (
    NEW_SHAPE,
    NEW_SHAPE_LABELS,
    NEW_SHAPE_ORDER,
    SEEDS,
    auto_situational_brief,
    compiled_path,
    fill_ovw_template,
    find_session,
    lesson_model_for,
    linguistic_label_from_topic,
    load_json,
    normalize_level,
    save_json,
)


class CompileError(Exception):
    pass


def validate_against_schema(instance: dict[str, Any], schema_path: Path) -> None:
    schema = load_json(schema_path)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(instance),
        key=lambda e: list(e.path),
    )
    if errors:
        messages = "\n".join(
            f"  - {'/'.join(str(p) for p in err.path) or '(root)'}: {err.message}"
            for err in errors
        )
        raise CompileError(f"Compiled reference failed schema:\n{messages}")


def compile_session(session_id: str, level: str | None = None) -> dict[str, Any]:
    config = load_json(SEEDS / "configuration.json")
    audience = load_json(SEEDS / "audience.json")
    editorial = load_json(SEEDS / "editorial.json")
    index = load_json(SEEDS / "session_index.json")
    ovw_template = (SEEDS / "ovw_template.md").read_text(encoding="utf-8")

    row = find_session(index, session_id)
    topic = str(row["topic"]).strip()
    unit_title = str(row.get("unit_title") or topic).strip()
    if unit_title != topic:
        raise CompileError(
            f"unit_title must equal topic for {session_id}: "
            f"unit_title={unit_title!r} topic={topic!r}"
        )

    cefr_level = normalize_level(level or config["default_cefr_level"])
    level_spec = config["levels"][cefr_level]
    budgets = level_spec["budgets"]
    guardrails = audience["target_audience"]
    lesson_model = lesson_model_for(session_id)
    stage_order = list(config["framework"]["ordered_stages"])
    if stage_order != NEW_SHAPE_ORDER:
        raise CompileError(f"locked stage order must be {NEW_SHAPE_ORDER}")
    ovw_labels = NEW_SHAPE_LABELS[lesson_model]

    session_context: dict[str, Any] = {
        "topic": topic,
        "unit_title": unit_title,
        "situational_brief": auto_situational_brief(topic),
        "level_demand": str(level_spec["demand"]),
    }

    payload: dict[str, Any] = {
        "pipeline_metadata": {
            "project_code": config["project_code"],
            "session_id": session_id,
            "cefr_level": cefr_level,
            "role_id": config["role_id"],
            "framework_name": config["framework"]["name"],
        },
        "target_audience_guardrails": {
            "profile": guardrails["profile"],
            "description": guardrails["description"],
            "constraint_level": guardrails["constraint_level"],
            "prefer": list(guardrails.get("prefer", [])),
            "avoid": list(guardrails.get("avoid", [])),
        },
        "session_context": session_context,
        "compiled_linguistic_targets": [
            {
                "label": linguistic_label_from_topic(topic),
                "tags": ["lexis"],
            }
        ],
        "framework_runtime": {
            "framework_name": config["framework"]["name"],
            "ordered_stages": stage_order,
            "lesson_model": lesson_model,
        },
        "budgets": {
            "article_word_min": budgets["article_word_min"],
            "article_word_max": budgets["article_word_max"],
            "tl_item_min": budgets["tl_item_min"],
            "tl_item_max": budgets["tl_item_max"],
            "plan_sheet_question_min": budgets["plan_sheet_question_min"],
            "q3_count": budgets["q3_count"],
            "reflection_seconds_min": budgets["reflection_seconds_min"],
            "reflection_seconds_max": budgets["reflection_seconds_max"],
        },
        "ovw_host_content": fill_ovw_template(ovw_template, ovw_labels),
        "editorial": {
            "show_dont_tell": editorial["show_dont_tell"],
            "art_form": editorial["art_form"],
            "art_form_description": editorial["art_form_description"],
            "banned_phrases": list(editorial["banned_phrases"]),
            "ovw_learner": editorial["channel_discipline"]["ovw_learner"],
        },
    }

    if payload["framework_runtime"]["lesson_model"] not in NEW_SHAPE_LABELS:
        raise CompileError(f"unknown lesson_model for {session_id}")
    validate_against_schema(
        payload, SEEDS / "compiled_session_reference_schema.json"
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile a B2027 Club session reference")
    parser.add_argument(
        "--session",
        required=True,
        help="session_id (c001–c100), e.g. c001",
    )
    parser.add_argument(
        "--level",
        default="b2",
        choices=["b1", "b2", "c1"],
        help="CEFR folder (default b2). Writes compiled/{level}/{session}.json",
    )
    parser.add_argument(
        "--shape",
        choices=[NEW_SHAPE],
        help="Retired. The level folder is the path. Accepted so older commands still run.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Override output path (default compiled/{session_id}.json)",
    )
    args = parser.parse_args(argv)

    try:
        payload = compile_session(args.session, level=args.level)
    except KeyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except CompileError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.shape == NEW_SHAPE:
        print("Note: --shape new-shape is retired. Writing the level folder.", file=sys.stderr)
    if args.output:
        out = args.output
    else:
        out = compiled_path(args.session, args.level)
    save_json(out, payload)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
