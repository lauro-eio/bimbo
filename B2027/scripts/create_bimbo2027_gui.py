#!/usr/bin/env python3
"""Local operator GUI — B2027 Club factory (validate / compile / generate / render).

  cd special-projects/Bimbo/B2027
  ./create_bimbo2027_gui.sh
  # or: .venv/bin/python scripts/create_bimbo2027_gui.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
SEEDS = ROOT / "Seeds"
CONTENT = ROOT / "content"
PREVIEW = ROOT / "preview"
INDEX = SEEDS / "session_index.json"

VALIDATE = SCRIPTS / "validate.py"
COMPILE = SCRIPTS / "compile.py"
GENERATE = SCRIPTS / "generate.py"
RENDER = SCRIPTS / "render.py"

VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
PYTHON = str(VENV_PYTHON if VENV_PYTHON.is_file() else Path(sys.executable))


def load_sessions() -> list[dict[str, str]]:
    if not INDEX.is_file():
        return []
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    rows: list[dict[str, str]] = []
    for row in data.get("sessions", []):
        sid = str(row.get("session_id") or "").strip()
        topic = str(row.get("unit_title") or row.get("topic") or "").strip()
        if not sid:
            continue
        rows.append({"session_id": sid, "topic": topic})
    return rows


def session_label(row: dict[str, str]) -> str:
    topic = row.get("topic") or ""
    short = topic if len(topic) <= 72 else topic[:71] + "…"
    return f"{row['session_id']}  —  {short}" if short else row["session_id"]


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("B2027 — Club factory")
        self.geometry("820x620")
        self.minsize(700, 500)

        self.sessions = load_sessions()
        self._labels = [session_label(r) for r in self.sessions]
        self._by_label = {session_label(r): r for r in self.sessions}

        default = ""
        if self.sessions:
            prefer = next(
                (session_label(r) for r in self.sessions if r["session_id"] == "c001"),
                self._labels[0],
            )
            default = prefer

        self.session_label_var = tk.StringVar(value=default)
        self.level_var = tk.StringVar(value="b2")
        self.filter_var = tk.StringVar(value="")
        self.dry_run = tk.BooleanVar(value=False)
        self.no_validate = tk.BooleanVar(value=False)
        self._proc: subprocess.Popen[str] | None = None

        self._build()
        self.filter_var.trace_add("write", lambda *_: self._apply_filter())

    def _build(self) -> None:
        form = ttk.LabelFrame(self, text="Session", padding=10)
        form.pack(fill=tk.X, padx=10, pady=10)
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Filter").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(form, textvariable=self.filter_var).grid(
            row=0, column=1, sticky=tk.EW, padx=6
        )

        ttk.Label(form, text="Session").grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        self.session_cb = ttk.Combobox(
            form,
            textvariable=self.session_label_var,
            values=self._labels,
            state="readonly",
        )
        self.session_cb.grid(row=1, column=1, sticky=tk.EW, padx=6, pady=(8, 0))

        ttk.Label(form, text="Level").grid(row=2, column=0, sticky=tk.W, pady=(8, 0))
        ttk.Combobox(
            form,
            textvariable=self.level_var,
            values=("b1", "b2", "c1"),
            state="readonly",
        ).grid(row=2, column=1, sticky=tk.W, padx=6, pady=(8, 0))

        opts = ttk.Frame(form)
        opts.grid(row=3, column=1, sticky=tk.W, padx=6, pady=(8, 0))
        ttk.Checkbutton(opts, text="Generate dry-run (prompt only)", variable=self.dry_run).pack(
            side=tk.LEFT
        )
        ttk.Checkbutton(
            opts, text="Skip validate on generate", variable=self.no_validate
        ).pack(side=tk.LEFT, padx=(12, 0))

        topic_frame = ttk.LabelFrame(self, text="Unit title (topic)", padding=8)
        topic_frame.pack(fill=tk.X, padx=10)
        self.topic_label = ttk.Label(topic_frame, text=self._current_topic(), wraplength=760)
        self.topic_label.pack(anchor=tk.W)
        self.session_cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_topic())

        btns = ttk.Frame(self)
        btns.pack(fill=tk.X, padx=10, pady=(10, 0))
        ttk.Button(btns, text="Validate seeds", command=self.validate_seeds).pack(
            side=tk.LEFT
        )
        ttk.Button(btns, text="Compile", command=self.compile_session).pack(
            side=tk.LEFT, padx=6
        )
        ttk.Button(btns, text="Generate", command=self.generate_session).pack(side=tk.LEFT)
        ttk.Button(btns, text="Validate content", command=self.validate_content).pack(
            side=tk.LEFT, padx=6
        )
        ttk.Button(btns, text="Render", command=self.render_session).pack(side=tk.LEFT)

        btns2 = ttk.Frame(self)
        btns2.pack(fill=tk.X, padx=10, pady=(6, 0))
        ttk.Button(btns2, text="Run pipeline", command=self.run_pipeline).pack(side=tk.LEFT)
        ttk.Button(btns2, text="Open host preview", command=self.open_host).pack(
            side=tk.LEFT, padx=6
        )
        ttk.Button(btns2, text="Open learner preview", command=self.open_learner).pack(
            side=tk.LEFT
        )
        ttk.Button(btns2, text="Stop", command=self.stop_proc).pack(side=tk.LEFT, padx=6)

        hint = ttk.Label(
            self,
            text=(
                "Pipeline: validate seeds → compile → generate → validate content → render. "
                "Upload converter deferred. GEMINI_API_KEY from B2027/.env or ../.env."
            ),
            foreground="#555555",
            wraplength=780,
        )
        hint.pack(anchor=tk.W, padx=12, pady=(8, 0))

        log_frame = ttk.LabelFrame(self, text="Log", padding=6)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.log = scrolledtext.ScrolledText(log_frame, height=18, wrap=tk.WORD)
        self.log.pack(fill=tk.BOTH, expand=True)

        if not self.sessions:
            self.append_log(
                f"[warn] No sessions in {INDEX}. Rebuild session_index from source.\n"
            )

    def _apply_filter(self) -> None:
        needle = self.filter_var.get().strip().lower()
        if not needle:
            values = self._labels
        else:
            values = [
                session_label(r)
                for r in self.sessions
                if needle in r["session_id"].lower() or needle in r["topic"].lower()
            ]
        self.session_cb["values"] = values
        if values and self.session_label_var.get() not in values:
            self.session_label_var.set(values[0])
            self._refresh_topic()

    def _current_row(self) -> dict[str, str] | None:
        return self._by_label.get(self.session_label_var.get())

    def _current_session_id(self) -> str | None:
        row = self._current_row()
        return row["session_id"] if row else None

    def _current_topic(self) -> str:
        row = self._current_row()
        return row["topic"] if row else "(no session selected)"

    def _refresh_topic(self) -> None:
        self.topic_label.configure(text=self._current_topic())

    def append_log(self, text: str) -> None:
        self.log.insert(tk.END, text)
        self.log.see(tk.END)

    def _level(self) -> str:
        return self.level_var.get().strip().lower() or "b2"

    def _require_session(self) -> str | None:
        sid = self._current_session_id()
        if not sid:
            messagebox.showerror("No session", "Pick a session from the list.")
            return None
        return sid

    def validate_seeds(self) -> None:
        self._run([PYTHON, str(VALIDATE)])

    def compile_session(self) -> None:
        sid = self._require_session()
        if not sid:
            return
        self._run([PYTHON, str(COMPILE), "--session", sid, "--level", self._level()])

    def generate_session(self) -> None:
        sid = self._require_session()
        if not sid:
            return
        if not self.dry_run.get() and not messagebox.askokcancel(
            "Generate",
            f"Call Gemini for session {sid} at {self._level()}?\n"
            f"Writes content/{self._level()}/{sid}.json\n"
            f"Topic: {self._current_topic()}",
        ):
            return
        argv = [PYTHON, str(GENERATE), "--session", sid, "--level", self._level()]
        if self.dry_run.get():
            argv.append("--dry-run")
        if self.no_validate.get():
            argv.append("--no-validate")
        self._run(argv)

    def validate_content(self) -> None:
        sid = self._require_session()
        if not sid:
            return
        self._run(
            [PYTHON, str(VALIDATE), "--content", "--session", sid, "--level", self._level()]
        )

    def render_session(self) -> None:
        sid = self._require_session()
        if not sid:
            return
        self._run([PYTHON, str(RENDER), "--session", sid, "--level", self._level()])

    def run_pipeline(self) -> None:
        sid = self._require_session()
        if not sid:
            return
        if self.dry_run.get():
            messagebox.showinfo(
                "Dry-run",
                "Uncheck dry-run for full pipeline (generate would not write content).",
            )
            return
        if not messagebox.askokcancel(
            "Run pipeline",
            f"Validate seeds → compile → generate → validate content → render\n"
            f"session: {sid}\n"
            f"level: {self._level()}\n"
            f"Calls Gemini.",
        ):
            return
        level = self._level()
        steps = [
            [PYTHON, str(VALIDATE)],
            [PYTHON, str(COMPILE), "--session", sid, "--level", level],
            [PYTHON, str(GENERATE), "--session", sid, "--level", level],
            [PYTHON, str(VALIDATE), "--content", "--session", sid, "--level", level],
            [PYTHON, str(RENDER), "--session", sid, "--level", level],
        ]
        if self.no_validate.get():
            steps[2] = [
                PYTHON, str(GENERATE), "--session", sid, "--level", level, "--no-validate"
            ]
        self._run_sequence(steps)

    def open_host(self) -> None:
        self._open_preview("host")

    def open_learner(self) -> None:
        self._open_preview("learner")

    def _open_preview(self, kind: str) -> None:
        sid = self._require_session()
        if not sid:
            return
        path = PREVIEW / self._level() / f"{sid}_{kind}.html"
        if not path.is_file():
            messagebox.showerror("Missing preview", f"Not found:\n{path}\nRender first.")
            return
        webbrowser.open(path.resolve().as_uri())

    def stop_proc(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            self.append_log("\n[stop] sent terminate\n")

    def _busy(self) -> bool:
        if self._proc and self._proc.poll() is None:
            messagebox.showwarning("Busy", "A command is already running.")
            return True
        return False

    def _run(self, argv: list[str]) -> None:
        if self._busy():
            return
        self._run_sequence([argv])

    def _run_sequence(self, steps: list[list[str]]) -> None:
        if self._busy():
            return

        def worker() -> None:
            env = os.environ.copy()
            for argv in steps:
                self.after(0, self.append_log, f"\n$ {' '.join(argv)}\n")
                try:
                    self._proc = subprocess.Popen(
                        argv,
                        cwd=str(ROOT),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        env=env,
                    )
                    assert self._proc.stdout is not None
                    for line in self._proc.stdout:
                        self.after(0, self.append_log, line)
                    code = self._proc.wait()
                    self.after(0, self.append_log, f"\n[exit {code}]\n")
                    if code != 0:
                        self.after(
                            0,
                            self.append_log,
                            "[pipeline stopped — previous step failed]\n",
                        )
                        return
                except Exception as exc:  # noqa: BLE001 — GUI log
                    self.after(0, self.append_log, f"\n[error] {exc}\n")
                    return

        threading.Thread(target=worker, daemon=True).start()


def main() -> int:
    missing = [p for p in (VALIDATE, COMPILE, GENERATE, RENDER) if not p.is_file()]
    if missing:
        print("missing scripts:\n" + "\n".join(str(p) for p in missing), file=sys.stderr)
        return 1
    App().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
