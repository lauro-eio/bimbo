# B2027 Seeds

Factory contracts for Club sessions. Policy: [`../LOCKS.md`](../LOCKS.md).

| File | Role |
| --- | --- |
| `configuration.json` | Stages, budgets, role, `commercial_name`, v1 defaults (`unit_title: topic`) |
| `configuration_schema.json` | Schema for configuration |
| `audience.json` | MANDATORY audience guardrails |
| `audience_schema.json` | Schema for audience |
| `session_index.json` | Topic index (`session_id` → topic / unit_title) |
| `session_index_schema.json` | Schema for session index |
| `ovw_template.md` | Fixed OVW host blurb; `{{STAGE_ROSTER}}` filled at compile |
| `editorial.json` | Show Don't Tell, ART vignette form, banned phrases, channel discipline |
| `editorial_schema.json` | Schema for editorial |
| `compiled_session_reference_schema.json` | Compile → LLM payload contract |
| `session_output_schema.json` | Generated session JSON contract (DoD shape) |

No grammar registry. No GO2 book ladder. No weekday tracks.

**Pipeline:** `scripts/compile.py` → `compiled/` · `scripts/generate.py` → `content/` · `scripts/validate.py` · `scripts/render.py` → `preview/`. See [`../AUTHORING.md`](../AUTHORING.md).

**Pipeline contracts:** compile emits JSON matching `compiled_session_reference_schema.json`; generate emits JSON matching `session_output_schema.json` (`plan_sheet` ≥6 questions; 8 Club stages in order; ART `reading_passage` + `passage_id`; TL vocab/column banks; no `tasks[]` / fake MCQs; `unit_title` = `session_title` = topic).

## Rebuild `session_index.json`

Parse dated lines from [`../source/bimbo-2027-program.md`](../source/bimbo-2027-program.md):

- `unit_title` = topic (exact list title)
- Optional `date` / `weekday` for calendar only — **not** generation tracks
- Year: Oct–Dec → **2026**; Jan–May → **2027**
- Do **not** store `situational_brief` here (auto from topic at compile)

Validate seeds with `python scripts/validate.py`.
