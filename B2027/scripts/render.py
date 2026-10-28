#!/usr/bin/env python3
"""Render B2027 Club session JSON to local host + learner HTML previews."""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path
from typing import Any

from common import (
    CONTENT,
    NEW_SHAPE,
    ROOT,
    SEEDS,
    content_path,
    content_shape_path,
    find_session,
    load_json,
    shape_stem,
)

PREVIEW = ROOT / "preview"


class RenderError(Exception):
    pass


def escape(text: str) -> str:
    return html.escape(text, quote=True)


def format_inline(text: str) -> str:
    """Escape HTML then apply **bold** spans."""
    parts: list[str] = []
    last = 0
    for match in re.finditer(r"\*\*(.+?)\*\*", text):
        parts.append(escape(text[last : match.start()]))
        parts.append(f"<strong>{escape(match.group(1))}</strong>")
        last = match.end()
    parts.append(escape(text[last:]))
    return "".join(parts)


def format_block(text: str) -> str:
    lines = text.splitlines() or [""]
    chunks: list[str] = []
    buf: list[str] = []

    def flush_para() -> None:
        nonlocal buf
        if not buf:
            return
        body = "<br>\n".join(format_inline(line) for line in buf)
        chunks.append(f"<p>{body}</p>")
        buf = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_para()
            continue
        if re.match(r"^[-*]\s+", stripped):
            flush_para()
            item = re.sub(r"^[-*]\s+", "", stripped)
            chunks.append(f"<li>{format_inline(item)}</li>")
            continue
        if re.match(r"^\d+[.)]\s+", stripped):
            flush_para()
            item = re.sub(r"^\d+[.)]\s+", "", stripped)
            chunks.append(f"<li>{format_inline(item)}</li>")
            continue
        buf.append(line)
    flush_para()

    # Wrap consecutive <li> into <ul>
    out: list[str] = []
    list_buf: list[str] = []
    for chunk in chunks:
        if chunk.startswith("<li>"):
            list_buf.append(chunk)
        else:
            if list_buf:
                out.append("<ul>" + "".join(list_buf) + "</ul>")
                list_buf = []
            out.append(chunk)
    if list_buf:
        out.append("<ul>" + "".join(list_buf) + "</ul>")
    return "\n".join(out) if out else "<p></p>"


def render_materials(materials: dict[str, Any]) -> str:
    parts: list[str] = []
    passage = materials.get("reading_passage")
    if isinstance(passage, dict):
        title = str(passage.get("title") or "").strip()
        body = str(passage.get("body") or "")
        pid = str(passage.get("passage_id") or "")
        parts.append('<div class="passage">')
        if title:
            parts.append(f"<h4>{escape(title)}</h4>")
        if pid:
            parts.append(f'<p class="meta">passage_id: {escape(pid)}</p>')
        parts.append(format_block(body))
        parts.append("</div>")

    vocab = materials.get("vocabulary_items")
    if isinstance(vocab, list) and vocab:
        items = "".join(f"<li>{escape(str(w))}</li>" for w in vocab)
        parts.append(f'<div class="vocab"><h4>Target language</h4><ul>{items}</ul></div>')

    banks = materials.get("column_banks")
    if isinstance(banks, list) and banks:
        parts.append('<div class="column-banks">')
        for bank in banks:
            if not isinstance(bank, dict):
                continue
            title = str(bank.get("title") or "").strip() or "Bank"
            items = bank.get("items") or []
            lis = "".join(f"<li>{escape(str(i))}</li>" for i in items)
            parts.append(f"<h4>{escape(title)}</h4><ul>{lis}</ul>")
        parts.append("</div>")

    return "\n".join(parts)


def render_stage_host(stage: dict[str, Any]) -> str:
    code = escape(str(stage.get("stage_code") or ""))
    title = escape(str(stage.get("title") or ""))
    student_title = escape(str(stage.get("student_title") or ""))
    teacher = str(stage.get("teacher_notes") or "")
    student = str(stage.get("student_content") or "")
    materials = stage.get("materials") if isinstance(stage.get("materials"), dict) else {}

    parts = [
        f'<article class="stage" id="stage-{code}">',
        f'<header class="stage-header"><span class="stage-code">{code}</span>'
        f"<h2>{title}</h2></header>",
        '<section class="teacher"><h3>Host notes</h3>',
        format_block(teacher) if teacher else "<p><em>No host notes.</em></p>",
        "</section>",
        '<section class="handout"><h3>Learner view</h3>',
        f'<h4 class="handout-title">{student_title}</h4>',
        format_block(student) if student else "<p><em>No learner content.</em></p>",
    ]
    if materials:
        parts.append(render_materials(materials))
    parts.extend(["</section>", "</article>"])
    return "\n".join(parts)


def render_stage_learner(stage: dict[str, Any]) -> str:
    student_title = escape(str(stage.get("student_title") or stage.get("title") or ""))
    student = str(stage.get("student_content") or "")
    materials = stage.get("materials") if isinstance(stage.get("materials"), dict) else {}
    code = escape(str(stage.get("stage_code") or ""))

    parts = [
        f'<article class="stage" id="stage-{code}">',
        f'<header class="stage-header"><h2>{student_title}</h2></header>',
        '<section class="handout">',
        format_block(student) if student else "<p><em>No learner content.</em></p>",
    ]
    if materials:
        parts.append(render_materials(materials))
    parts.extend(["</section>", "</article>"])
    return "\n".join(parts)


def page_shell(title: str, body: str, view: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      --text: #1a1a1a;
      --muted: #555;
      --border: #ddd;
      --host: #2c5282;
      --learner: #276749;
      --teacher-bg: #f3f6f9;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      font-family: Georgia, "Times New Roman", serif;
      line-height: 1.55;
      color: var(--text);
      max-width: 46rem;
      margin: 0 auto;
      padding: 1.5rem 1.25rem 3rem;
      background: #fff;
    }}
    body.view-host {{ border-top: 4px solid var(--host); }}
    body.view-learner {{ border-top: 4px solid var(--learner); }}
    h1 {{ font-size: 1.45rem; margin: 0 0 0.35rem; }}
    h2 {{ font-size: 1.1rem; margin: 0; }}
    h3 {{
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--muted);
      margin: 0 0 0.5rem;
    }}
    h4 {{ font-size: 0.95rem; margin: 0.75rem 0 0.35rem; }}
    .meta {{ color: var(--muted); font-size: 0.9rem; margin: 0 0 1.25rem; }}
    .plan-sheet {{
      border: 1px solid var(--border);
      padding: 0.85rem 1rem;
      margin: 0 0 1.5rem;
      background: #fafafa;
    }}
    .plan-sheet ol {{ margin: 0.35rem 0 0; padding-left: 1.25rem; }}
    .stage {{
      border-top: 1px solid var(--border);
      padding: 1.25rem 0;
      margin: 0;
    }}
    .stage-header {{
      display: flex;
      gap: 0.65rem;
      align-items: baseline;
      margin-bottom: 0.75rem;
    }}
    .stage-code {{
      font-family: ui-monospace, monospace;
      font-size: 0.75rem;
      color: var(--host);
      background: var(--teacher-bg);
      padding: 0.15rem 0.4rem;
      border-radius: 3px;
    }}
    body.view-learner .stage-code {{ display: none; }}
    .teacher {{
      background: var(--teacher-bg);
      padding: 0.75rem 0.9rem;
      margin-bottom: 0.85rem;
      border-radius: 4px;
    }}
    .handout-title {{ margin-top: 0; }}
    .passage {{
      border-left: 3px solid var(--border);
      padding-left: 0.85rem;
      margin: 0.75rem 0;
    }}
    ul {{ margin: 0.35rem 0 0.75rem; padding-left: 1.25rem; }}
    p {{ margin: 0 0 0.65rem; }}
    a {{ color: var(--host); }}
  </style>
</head>
<body class="view-{escape(view)}">
{body}
</body>
</html>
"""


def program_title() -> str:
    config = load_json(SEEDS / "configuration.json")
    return str(config.get("commercial_name") or "B2027")


def session_heading(meta: dict[str, Any]) -> str:
    topic = str(meta.get("unit_title") or meta.get("topic") or "")
    sid = str(meta.get("session_id") or "")
    return f"{sid} — {topic}" if topic else sid


def render_plan_sheet(session: dict[str, Any]) -> str:
    questions = (session.get("plan_sheet") or {}).get("questions") or []
    if not isinstance(questions, list) or not questions:
        return ""
    items = "".join(f"<li>{escape(str(q))}</li>" for q in questions)
    return (
        '<section class="plan-sheet"><h3>Plan sheet</h3>'
        f"<ol>{items}</ol></section>"
    )


def render_host_page(session: dict[str, Any]) -> str:
    meta = session.get("session_metadata") or {}
    title = session_heading(meta)
    program = program_title()
    stages = session.get("stages") or []
    body_parts = [
        f"<h1>{escape(title)}</h1>",
        (
            f'<p class="meta">{escape(program)} · host · '
            f'{escape(str(meta.get("unit_title") or meta.get("topic") or ""))} · '
            f'CEFR {escape(str(meta.get("cefr_level") or ""))} · '
            f'{escape(str(meta.get("role_id") or ""))}</p>'
        ),
        render_plan_sheet(session),
    ]
    for stage in stages:
        if isinstance(stage, dict):
            body_parts.append(render_stage_host(stage))
    return page_shell(f"{program} · Host · {title}", "\n".join(body_parts), "host")


def render_learner_page(session: dict[str, Any]) -> str:
    meta = session.get("session_metadata") or {}
    title = session_heading(meta)
    program = program_title()
    stages = session.get("stages") or []
    body_parts = [
        f"<h1>{escape(title)}</h1>",
        (
            f'<p class="meta">{escape(program)} · learner · '
            f'{escape(str(meta.get("unit_title") or meta.get("topic") or ""))}</p>'
        ),
        render_plan_sheet(session),
    ]
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        # Host-only stages (e.g. OVW) stay off the learner pack
        if str(stage.get("student_content") or "").strip() == "HOST_ONLY":
            continue
        body_parts.append(render_stage_learner(stage))
    return page_shell(f"{program} · Learner · {title}", "\n".join(body_parts), "learner")


def resolve_content_file(
    session_id: str | None,
    path: Path | None,
    shape: str | None = None,
) -> Path:
    if path:
        return path
    if not session_id:
        raise RenderError("pass --session or --file")
    index = load_json(SEEDS / "session_index.json")
    find_session(index, session_id)
    preferred = (
        content_shape_path(session_id) if shape == NEW_SHAPE else content_path(session_id)
    )
    if preferred.is_file():
        return preferred
    legacy = sorted(CONTENT.glob(f"{session_id}_*.json"))
    if legacy:
        return legacy[0]
    raise RenderError(f"Content not found: {preferred}. Generate first.")


def preview_paths(
    session: dict[str, Any],
    session_id: str,
    shape: str | None = None,
) -> tuple[Path, Path]:
    stem = shape_stem(session_id) if shape == NEW_SHAPE else session_id
    return (
        PREVIEW / f"{stem}_host.html",
        PREVIEW / f"{stem}_learner.html",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render B2027 host + learner HTML")
    parser.add_argument("--session", help="session_id (c001–c100)")
    parser.add_argument("--file", type=Path, help="Explicit content JSON path")
    parser.add_argument(
        "--shape",
        choices=[NEW_SHAPE],
        help="Render preview/{session}_new-shape_{host,learner}.html",
    )
    args = parser.parse_args(argv)

    try:
        content_file = resolve_content_file(args.session, args.file, args.shape)
    except (RenderError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    session = load_json(content_file)
    if not isinstance(session, dict):
        print("ERROR: content must be a JSON object", file=sys.stderr)
        return 1

    meta = session.get("session_metadata") or {}
    session_id = str(meta.get("session_id") or args.session or content_file.stem)
    host_path, learner_path = preview_paths(session, session_id, args.shape)

    write_text(host_path, render_host_page(session))
    write_text(learner_path, render_learner_page(session))

    print(f"Wrote {host_path.relative_to(ROOT)}")
    print(f"Wrote {learner_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
