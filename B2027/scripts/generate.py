#!/usr/bin/env python3
"""Generate B2027 Club session JSON from a compiled reference via Gemini."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from jsonschema import Draft202012Validator

from common import (
    NEW_SHAPE,
    PROMPTS,
    ROOT,
    SEEDS,
    compiled_path,
    compiled_shape_path,
    content_path,
    content_shape_path,
    lesson_model_for,
    load_json,
    save_json,
)

PLACEHOLDER = "{{COMPILED_SESSION_REFERENCE}}"

# Keep in sync with validate.JARGON — learner titles must stay thematic.
_STUDENT_TITLE_JARGON = re.compile(
    r"\b(lead[- ]?in|overview|target language|freer practice|reflection|"
    r"wrap[- ]?up|fbdc|l-in|ovw|q3|art)\b",
    re.I,
)
_SAFE_STUDENT_TITLES: dict[str, str] = {
    "L-IN": "Opening questions",
    "OVW": "Session map",
    "TL": "Phrases to use",
    "Q3": "First three",
    "ART": "Shared story",
    "FP": "Keep talking",
    "REF": "Your takeaways",
    "FBDC": "Stronger wording",
}


class GenerateError(Exception):
    pass


def scrub_student_title_jargon(session: dict[str, Any]) -> list[str]:
    """Replace learner titles that trip Club jargon DoD (deterministic)."""
    fixes: list[str] = []
    stages = session.get("stages")
    if not isinstance(stages, list):
        return fixes
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        code = str(stage.get("stage_code") or "")
        student_title = str(stage.get("student_title") or "")
        host_title = str(stage.get("title") or "")
        if not _STUDENT_TITLE_JARGON.search(student_title):
            continue
        replacement = _SAFE_STUDENT_TITLES.get(code, "Speaking task")
        if replacement.strip() == host_title.strip():
            replacement = f"{replacement} now"
        stage["student_title"] = replacement
        fixes.append(f"{code}: {student_title!r} → {replacement!r}")
    return fixes


_REF_TIMING = re.compile(
    r"(90|120|1\.5|2(\.0)?)\s*(s|sec|secs|second|seconds|min|mins|minute|minutes)"
    r"|timed\s+reflection|stopwatch",
    re.I,
)


def ensure_ref_timing(session: dict[str, Any]) -> bool:
    """REF host notes must carry the locked 90–120s cue."""
    stages = session.get("stages")
    if not isinstance(stages, list):
        return False
    for stage in stages:
        if not isinstance(stage, dict) or stage.get("stage_code") != "REF":
            continue
        notes = str(stage.get("teacher_notes") or "").rstrip()
        if _REF_TIMING.search(notes):
            return False
        cue = "- Stopwatch on. Each student speaks 90–120 seconds."
        stage["teacher_notes"] = f"{notes}\n{cue}".strip()
        return True
    return False


def load_env() -> None:
    for candidate in (ROOT / ".env", ROOT.parent / ".env"):
        if candidate.is_file():
            load_dotenv(candidate, override=False)


def load_prompt(role_id: str) -> str:
    prompt_path = PROMPTS / f"{role_id}.md"
    if not prompt_path.is_file():
        raise GenerateError(f"Prompt template not found: {prompt_path}")
    parts = [prompt_path.read_text(encoding="utf-8")]
    rules = PROMPTS / "_OUTPUT_TYPE_RULES.md"
    if rules.is_file():
        parts.append("\n\n---\n\n")
        parts.append(rules.read_text(encoding="utf-8"))
    return "".join(parts)


def build_prompt(template: str, compiled_ref: dict[str, Any]) -> str:
    if PLACEHOLDER not in template:
        raise GenerateError(f"Prompt template missing {PLACEHOLDER}")
    return template.replace(
        PLACEHOLDER, json.dumps(compiled_ref, indent=2, ensure_ascii=False)
    )


def extract_json_text(raw: str) -> str:
    text = raw.strip()
    fence = re.match(
        r"^```(?:json)?\s*\n?(.*?)\n?```\s*$",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if fence:
        text = fence.group(1).strip()
    return text


def call_gemini(prompt: str, model_name: str) -> str:
    try:
        from google import genai
    except ImportError as exc:
        raise GenerateError(
            "google-genai is not installed; run: pip install -r requirements.txt"
        ) from exc

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise GenerateError(
            "GEMINI_API_KEY is not set; copy special-projects/Bimbo/.env.example to .env"
        )

    client = genai.Client(api_key=api_key)
    # One-shot JSON. AFC is for tool loops; leaving it on logs a warning.
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "automatic_function_calling": {"disable": True},
        },
    )
    if not response.text:
        raise GenerateError("Gemini returned an empty response")
    return response.text


def parse_session_response(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(extract_json_text(raw))
    except json.JSONDecodeError as exc:
        raise GenerateError(f"Gemini response is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise GenerateError("Gemini response must be a JSON object")
    return payload


def schema_validate_session(
    session: dict[str, Any],
    shape: str | None = None,
    lesson_model: str | None = None,
) -> None:
    from validate import validate_session_dod

    if shape != NEW_SHAPE:
        schema = load_json(SEEDS / "session_output_schema.json")
        errors = sorted(
            Draft202012Validator(schema).iter_errors(session),
            key=lambda e: list(e.path),
        )
        if errors:
            messages = "\n".join(
                f"  - {'/'.join(str(p) for p in err.path) or '(root)'}: {err.message}"
                for err in errors
            )
            raise GenerateError(f"Session failed schema validation:\n{messages}")

    config = load_json(SEEDS / "configuration.json")
    editorial = load_json(SEEDS / "editorial.json")
    dod = validate_session_dod(
        session, config, editorial, shape=shape, lesson_model=lesson_model
    )
    if dod:
        raise GenerateError("Session failed Club DoD:\n" + "\n".join(dod))


def build_repair_prompt(
    session: dict[str, Any],
    validation_error: str,
    shape: str | None = None,
    lesson_model: str | None = None,
) -> str:
    if shape == NEW_SHAPE:
        if lesson_model == "roleplay":
            task_rules = (
                "- L-IN is situation questions, not a riddle and not a game.\n"
                "- plan_sheet.questions still has at least 6 items.\n"
                "- Q3 is the role-play: name the roles, the situation, and the outcome. "
                "Do not paste plan-sheet questions into Q3.\n"
                "- FP is one or two debrief questions and must include a question mark.\n"
            )
        else:
            task_rules = (
                "- L-IN student_content must contain the word game (a topic game).\n"
                "- Q3 is the debate and must include the first three plan_sheet questions and the word debate or side.\n"
                "- FP is general opinion and must include the word opinion plus the remaining plan_sheet questions.\n"
            )
        order = "L-IN, OVW, ART, TL, Q3, FP, REF, FBDC"
        plan_rule = task_rules
    else:
        order = "L-IN, OVW, TL, Q3, ART, FP, REF, FBDC"
        plan_rule = "- plan_sheet.questions ≥ 6; first 3 in Q3, rest in FP.\n"
    return (
        "You are fixing a B2027 Club session JSON so it passes schema + Club DoD. "
        "Keep pedagogy and topic.\n\n"
        "Rules:\n"
        f"- Exactly 8 stages: {order}.\n"
        "- session_metadata.session_id is the class id (c001–c100).\n"
        "- session_metadata.unit_title and session_title must equal topic.\n"
        "- Omit date, weekday, and track.\n"
        "- OVW.student_content must be exactly HOST_ONLY; put the roadmap only in teacher_notes.\n"
        "- student_content = task prompts/questions only — no Welcome/agenda ceremony.\n"
        "- teacher_notes = short bullets, not long host scripts.\n"
        "- student_title must DIFFER from title and must NOT contain: reflection, "
        "overview, article, target language, lead-in, freer practice, wrap-up, "
        "Q3, FBDC, L-IN, OVW, ART, REF.\n"
        "- REF student_title example: Your takeaways (never Reflection).\n"
        "- REF teacher_notes must include a 90–120 seconds stopwatch cue.\n"
        "- ART = decision vignette (Show Don't Tell); no banned openers "
        "(In today's…, data-driven landscape, Welcome to today's…).\n"
        "- ART student_content = one short read-aloud line; body in reading_passage.\n"
        "- TL prefer column_banks; short student prompt.\n"
        f"{plan_rule}"
        "- No materials.tasks / no MCQs.\n"
        "- Return ONLY valid JSON (no markdown fences).\n\n"
        f"Validation errors:\n{validation_error}\n\n"
        f"Current JSON:\n{json.dumps(session, indent=2, ensure_ascii=False)}\n"
    )


def pin_session_identity(
    session: dict[str, Any],
    session_id: str,
    compiled_ref: dict[str, Any],
) -> None:
    """Force class id and topic titles; drop calendar fields the index no longer has."""
    meta = session.get("session_metadata")
    if not isinstance(meta, dict):
        meta = {}
        session["session_metadata"] = meta
    context = compiled_ref.get("session_context") or {}
    topic = str(context.get("topic") or meta.get("topic") or "").strip()
    meta["session_id"] = session_id
    if topic:
        meta["topic"] = topic
        meta["unit_title"] = topic
        meta["session_title"] = topic
    meta.pop("date", None)
    meta.pop("weekday", None)
    meta.pop("track", None)
    meta.pop("track_focus", None)


def pin_ovw_map(session: dict[str, Any], compiled_ref: dict[str, Any]) -> None:
    """Keep the host map in the compiled stage order."""
    host_map = compiled_ref.get("ovw_host_content")
    if not isinstance(host_map, str) or not host_map.strip():
        return
    for stage in session.get("stages") or []:
        if isinstance(stage, dict) and stage.get("stage_code") == "OVW":
            stage["teacher_notes"] = host_map
            stage["student_content"] = "HOST_ONLY"
            return


def generate_one(
    session_id: str,
    model_name: str,
    dry_run: bool,
    do_validate: bool,
    out_path: Path | None,
    shape: str | None = None,
) -> Path:
    in_path = compiled_shape_path(session_id) if shape == NEW_SHAPE else compiled_path(session_id)
    if not in_path.is_file():
        raise GenerateError(
            f"Compiled reference not found: {in_path}\n"
            f"Run: python scripts/compile.py --session {session_id}"
            + (" --shape new-shape" if shape == NEW_SHAPE else "")
        )

    compiled_ref = load_json(in_path)
    role_id = compiled_ref.get("pipeline_metadata", {}).get("role_id")
    if not isinstance(role_id, str):
        raise GenerateError("Compiled reference missing pipeline_metadata.role_id")

    prompt = build_prompt(load_prompt(role_id), compiled_ref)
    lesson_model = lesson_model_for(session_id) if shape == NEW_SHAPE else None
    destination = out_path or (
        content_shape_path(session_id) if shape == NEW_SHAPE else content_path(session_id)
    )

    if dry_run:
        print(prompt)
        return destination

    raw = call_gemini(prompt, model_name)
    session = parse_session_response(raw)
    pin_session_identity(session, session_id, compiled_ref)
    if shape == NEW_SHAPE:
        pin_ovw_map(session, compiled_ref)
    title_fixes = scrub_student_title_jargon(session)
    if title_fixes:
        print(
            "  Scrubbed student_title jargon:\n    "
            + "\n    ".join(title_fixes),
            file=sys.stderr,
        )
    if ensure_ref_timing(session):
        print("  Added REF 90–120s timing cue", file=sys.stderr)

    if do_validate:
        try:
            schema_validate_session(session, shape=shape, lesson_model=lesson_model)
        except GenerateError as first_exc:
            print(
                f"  Validation failed for {session_id}; one repair pass…",
                file=sys.stderr,
            )
            repair_raw = call_gemini(
                build_repair_prompt(
                    session, str(first_exc), shape=shape, lesson_model=lesson_model
                ),
                model_name,
            )
            session = parse_session_response(repair_raw)
            pin_session_identity(session, session_id, compiled_ref)
            if shape == NEW_SHAPE:
                pin_ovw_map(session, compiled_ref)
            title_fixes = scrub_student_title_jargon(session)
            if title_fixes:
                print(
                    "  Scrubbed student_title jargon after repair:\n    "
                    + "\n    ".join(title_fixes),
                    file=sys.stderr,
                )
            if ensure_ref_timing(session):
                print("  Added REF 90–120s timing cue after repair", file=sys.stderr)
            try:
                schema_validate_session(session, shape=shape, lesson_model=lesson_model)
                print(f"  Repair PASS for {session_id}", file=sys.stderr)
            except GenerateError as second_exc:
                raise GenerateError(
                    f"Session still invalid after one repair retry:\n{second_exc}"
                ) from second_exc

    save_json(destination, session)
    return destination


def main(argv: list[str] | None = None) -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Generate a B2027 Club session")
    parser.add_argument("--session", required=True, help="session_id (c001–c100)")
    parser.add_argument(
        "--shape",
        choices=[NEW_SHAPE],
        help="Read compiled/{session}_new-shape.json and write content/{session}_new-shape.json",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        help="Gemini model id",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print prompt only; no API call",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip schema validate + repair on write",
    )
    parser.add_argument("-o", "--output", type=Path, help="Override content path")
    args = parser.parse_args(argv)

    try:
        out = generate_one(
            session_id=args.session,
            model_name=args.model,
            dry_run=args.dry_run,
            do_validate=not args.no_validate,
            out_path=args.output,
            shape=args.shape,
        )
    except GenerateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not args.dry_run:
        print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
