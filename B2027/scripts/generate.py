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
    content_path,
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


def _has_number(text: str, number: int) -> bool:
    return re.search(rf"(?<!\d){number}(?!\d)", text) is not None


def ensure_ref_timing(
    session: dict[str, Any],
    compiled_ref: dict[str, Any] | None = None,
) -> bool:
    """REF notes and the learner line must state this level's full range."""
    stages = session.get("stages")
    if not isinstance(stages, list):
        return False
    budgets = (compiled_ref or {}).get("budgets") or {}
    lo = int(budgets.get("reflection_seconds_min", 90))
    hi = int(budgets.get("reflection_seconds_max", 120))
    changed = False
    for stage in stages:
        if not isinstance(stage, dict) or stage.get("stage_code") != "REF":
            continue
        notes = str(stage.get("teacher_notes") or "").rstrip()
        if not (_has_number(notes, lo) and _has_number(notes, hi)):
            cue = f"- Stopwatch on. Each student speaks {lo}–{hi} seconds."
            stage["teacher_notes"] = f"{notes}\n{cue}".strip()
            changed = True
        student = str(stage.get("student_content") or "").rstrip()
        if student and student != "HOST_ONLY" and not (
            _has_number(student, lo) and _has_number(student, hi)
        ):
            stage["student_content"] = f"{student} Speak for {lo}–{hi} seconds.".strip()
            changed = True
        return changed
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
    session: dict[str, Any] | None,
    validation_error: str,
    shape: str | None = None,
    lesson_model: str | None = None,
    source_text: str | None = None,
) -> str:
    if lesson_model == "debate":
        task_rules = (
            "- L-IN student_content must contain the word game (a topic game).\n"
            "- Q3 is the debate and must include the first three plan_sheet questions and the word debate or side.\n"
            "- FP is general opinion and must include the word opinion plus the remaining plan_sheet questions.\n"
        )
    else:
        task_rules = (
            "- L-IN is situation questions, not a riddle and not a game.\n"
            "- plan_sheet.questions still has at least 6 items.\n"
            "- Q3 student_content must contain the words role and outcome, and name the situation. "
            "Do not paste plan-sheet questions into Q3.\n"
            "- FP is one or two debrief questions and must include a question mark.\n"
        )
    order = "L-IN, OVW, ART, TL, Q3, FP, REF, FBDC"
    plan_rule = task_rules
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
        "- REF teacher_notes must include a stopwatch cue for this level's reflection range.\n"
        "- REF student_content must state both ends of that range, not one number inside it.\n"
        "- ART = decision vignette (Show Don't Tell); no banned openers "
        "(In today's…, data-driven landscape, Welcome to today's…).\n"
        "- ART reading_passage.body must fall inside the article word range in the validation error. "
        "A count below the minimum means lengthen the vignette. Do not shorten a short article.\n"
        "- ART student_content = one short read-aloud line; body in reading_passage.\n"
        "- TL prefer column_banks; short student prompt.\n"
        f"{plan_rule}"
        "- No materials.tasks / no MCQs.\n"
        "- Return ONLY valid JSON (no markdown fences).\n\n"
        f"Validation errors:\n{validation_error}\n\n"
        "Current JSON:\n"
        + (
            source_text
            if source_text is not None
            else json.dumps(session or {}, indent=2, ensure_ascii=False)
        )
        + "\n"
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
    cefr = str((compiled_ref.get("pipeline_metadata") or {}).get("cefr_level") or "")
    if cefr:
        meta["cefr_level"] = cefr
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
    level: str | None = None,
) -> Path:
    if shape == NEW_SHAPE:
        print("Note: --shape new-shape is retired. Writing the level folder.", file=sys.stderr)
    in_path = compiled_path(session_id, level)
    if not in_path.is_file():
        raise GenerateError(
            f"Compiled reference not found: {in_path}\n"
            f"Run: python scripts/compile.py --session {session_id} --level {level or 'b2'}"
        )

    compiled_ref = load_json(in_path)
    role_id = compiled_ref.get("pipeline_metadata", {}).get("role_id")
    if not isinstance(role_id, str):
        raise GenerateError("Compiled reference missing pipeline_metadata.role_id")

    prompt = build_prompt(load_prompt(role_id), compiled_ref)
    lesson_model = lesson_model_for(session_id)
    destination = out_path or content_path(session_id, level)

    if dry_run:
        print(prompt)
        return destination

    raw = call_gemini(prompt, model_name)
    session: dict[str, Any] | None = None
    parse_error: GenerateError | None = None
    try:
        session = parse_session_response(raw)
    except GenerateError as exc:
        parse_error = exc

    def prepare(current: dict[str, Any], label: str) -> None:
        pin_session_identity(current, session_id, compiled_ref)
        pin_ovw_map(current, compiled_ref)
        title_fixes = scrub_student_title_jargon(current)
        if title_fixes:
            print(
                f"  Scrubbed student_title jargon{label}:\n    "
                + "\n    ".join(title_fixes),
                file=sys.stderr,
            )
        if ensure_ref_timing(current, compiled_ref):
            print(f"  Added REF stopwatch cue{label}", file=sys.stderr)

    if session is not None:
        prepare(session, "")

    if do_validate:
        first_exc = parse_error
        if session is not None and first_exc is None:
            try:
                schema_validate_session(session, shape=shape, lesson_model=lesson_model)
            except GenerateError as exc:
                first_exc = exc
        if first_exc is not None:
            print(
                f"  Validation failed for {session_id}; one repair pass…",
                file=sys.stderr,
            )
            repair_raw = call_gemini(
                build_repair_prompt(
                    session,
                    str(first_exc),
                    shape=shape,
                    lesson_model=lesson_model,
                    source_text=None if session is not None else raw,
                ),
                model_name,
            )
            try:
                session = parse_session_response(repair_raw)
            except GenerateError as repair_parse_exc:
                raise GenerateError(
                    f"Session still invalid after one repair retry:\n{repair_parse_exc}"
                ) from repair_parse_exc
            prepare(session, " after repair")
            try:
                schema_validate_session(session, shape=shape, lesson_model=lesson_model)
                print(f"  Repair PASS for {session_id}", file=sys.stderr)
            except GenerateError as second_exc:
                raise GenerateError(
                    f"Session still invalid after one repair retry:\n{second_exc}"
                ) from second_exc
    elif parse_error is not None:
        raise parse_error

    if session is None:
        raise GenerateError(f"No session produced for {session_id}")

    save_json(destination, session)
    return destination


def main(argv: list[str] | None = None) -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Generate a B2027 Club session")
    parser.add_argument("--session", required=True, help="session_id (c001–c100)")
    parser.add_argument(
        "--level",
        default="b2",
        choices=["b1", "b2", "c1"],
        help="CEFR folder (default b2)",
    )
    parser.add_argument(
        "--shape",
        choices=[NEW_SHAPE],
        help="Retired. The level folder is the path. Accepted so older commands still run.",
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
            level=args.level,
        )
    except GenerateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not args.dry_run:
        print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
