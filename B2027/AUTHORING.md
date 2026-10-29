# Authoring — B2027

Read [`LOCKS.md`](LOCKS.md) first. Do not invent a second session format.

## Sources

| Path | Use |
| --- | --- |
| `source/bimbo-2027-program.md` | Canonical calendar (date → topic) |
| `source/Club Session Roadmap - Club Session Roadmap.pdf` | Host stage map / timer doctrine |
| [`Seeds/`](Seeds/) | `configuration`, `audience`, `session_index`, `ovw_template` — see [`Seeds/README.md`](Seeds/README.md) |

## Session shape

Every session uses the locked Club stage codes (`L-IN` → `OVW` → `ART` → `TL` → `Q3` → `FP` → `REF` → `FBDC`). Odd classes are role-play. Even classes are a topic game, then a debate, then opinion. The same class is written three times, under `b1/`, `b2/`, and `c1/`. Spine is **topic only**; upload / unit title = topic string. Week and slot are calendar metadata only (not a generation track).

## Factory

From `B2027/` (use a venv with `pip install -r requirements.txt`):

**GUI (recommended):**

```bash
./create_bimbo2027_gui.sh
```

Double-click from the file manager works the same way (detaches; logs under `var/logs/`). Needs system Tk (`python3-tkinter` on Fedora).

**CLI:**

```bash
python scripts/validate.py
python scripts/compile.py --session c001 --level b2
python scripts/generate.py --session c001 --level b2 --dry-run
python scripts/generate.py --session c001 --level b1
python scripts/validate.py --content --session c001 --level b2
python scripts/render.py --session c001 --level b2
```

`GEMINI_API_KEY` loads from `B2027/.env` or hub `special-projects/Bimbo/.env`.

1. Resolve the session from `Seeds/session_index.json` (`session_id`, `topic`, `unit_title`).
2. Compile one session reference (`compiled/{session_id}.json`) — auto `situational_brief`, OVW from template.
3. Generate with role prompt `prompts/CLUB_SK_PROD_SPEAKING.md` → `content/{session_id}.json`.
4. Validate Club DoD (`scripts/validate.py --content`) — stop on red before render.
5. Render local host + learner HTML → `preview/{session_id}_host.html` and `_learner.html`.

V1 defaults: article generated from topic; `situational_brief` auto; `OVW` from template; `unit_title` = topic.

## Do not

- Add PPP / TTT / multi-class book lifecycles
- Reintroduce weekday tracks (`case` / `metrics` / `reporting` / `delivery` / `people`) as generation locks
- Publish into `go-preview` or GL catalog previews
- Keep parallel calendars at repo root (`bimbo-2027-program.md`, `Untitled`)
- Change stage codes without updating `LOCKS.md`
