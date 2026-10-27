# B2027 — locked decisions

Status: **locked** (updated 2026-10-26). Change only with an explicit unlock note here.

Canonical client sources: [`source/bimbo-2027-program.md`](source/bimbo-2027-program.md), [`source/Club Session Roadmap - Club Session Roadmap.pdf`](source/Club%20Session%20Roadmap%20-%20Club%20Session%20Roadmap.pdf).

Pattern reference only (do not import machinery): `global-opportunities` SK-PROD speaking / `_OUTPUT_TYPE_RULES.md` / `file-layout.md`.

Working notes: [`notes/2026-09-29-locks.md`](notes/2026-09-29-locks.md), [`notes/2026-09-29-note.md`](notes/2026-09-29-note.md).

---

## 1. Identity

| Field | Locked value |
| --- | --- |
| Project code | **B2027** |
| Commercial name | **Bimbo · 100** |
| Client hub | `special-projects/Bimbo/` |
| Engagement path | `special-projects/Bimbo/B2027/` |
| Product family | English Club (bespoke) — **not** GO2 catalog, **not** GL workshop packages |
| Package naming | Does **not** use `{program}-t{n}-m{nn}`. The commercial name is not a package spine. |

**Bimbo · 100** is the program title in the UI (host and learner preview, and later the platform program name). Canonical copy lives in `Seeds/configuration.json` as `commercial_name`.

It does not rename the factory. Keep **B2027** for `project_code`, paths, filenames, session ids, and the operator GUI. `unit_title` stays the class topic.

The title is not a live class count. The catalog may grow or shrink. A participant may complete only part of the program. Do not rename it when either happens.

---

## 2. Club stage map

Single session type for every calendar entry. Stage codes are the factory contract; labels are host-facing.

| # | Code | Host label | Job |
| :---: | --- | --- | --- |
| 1 | `L-IN` | Welcome to Class | Icebreaker; high energy |
| 2 | `OVW` | Overview | Expectations + session map (facilitation; light generation) |
| 3 | `TL` | Target Language | Introduce **3–5** idioms / vocabulary items |
| 4 | `Q3` | 3 questions | First three plan-sheet questions (controlled activation) |
| 5 | `ART` | Article Reading | Short article read aloud for shared context |
| 6 | `FP` | The Rest of the Questions | Remaining plan-sheet questions; debate / opinion |
| 7a | `REF` | Wrap — student reflection | Timed **1.5–2.0 min** per participant summary |
| 7b | `FBDC` | Wrap — host delivery & upgrades | Anonymous delayed correction + expressive upgrades |

**Pedagogy frame:** tweaked CELTA **SK-PROD** (productive speaking). Article (`ART`) is the model input (not a listening dialogue). Grammar PPP/TTT stages are out of scope.

**Timer doctrine:** keep an on-screen stopwatch for each student speaking turn (especially `REF`).

---

## 3. Topic-only index + upload titles

**Unlocked:** five weekday tracks (`case` / `metrics` / `reporting` / `delivery` / `people`) are **not** generation locks.

| Field | Locked value |
| --- | --- |
| Spine | **Topic** from [`source/bimbo-2027-program.md`](source/bimbo-2027-program.md) |
| Session index | `session_id` + `topic` (+ optional schedule `date` / `weekday` for calendar only) |
| Upload / unit title | **`unit_title` = topic string** (exact list title) |
| `session_title` | Same as `unit_title` / topic (required on generated session metadata) |
| Paths | `content/{session_id}.json`, `preview/{session_id}_{host\|learner}.html` |

Generation guardrail is the topic + `situational_brief` auto-from-topic — not weekday taxonomy.

---

## 4. CEFR / budgets

| Field | Locked value |
| --- | --- |
| Operating CEFR | **B2** |
| Lexis stretch | C1 allowed in `TL` and host **expressive upgrades** only |
| Article (`ART`) | **120–220 words** (quick aloud paragraphs) |
| Target language | **3–5** items per session |
| Plan sheet | ≥ **6** questions total: first **3** → `Q3`; remainder → `FP` |
| Reflection | **90–120 seconds** per student |

No A0–C2 book ladder. No per-book `max_text_word_count` matrix from GO2.

---

## 5. Single-role factory pipeline

| Field | Locked value |
| --- | --- |
| Roles | **One:** `CLUB_SK_PROD_SPEAKING` |
| Frameworks | **One:** Club stage map above |
| Lifecycle | One Club session per **topic** (upload unit) — **not** 7-class book units |
| Pipeline | `seeds → compile → generate → validate → render` (upload converter later) |
| Seeds (minimal) | `configuration` · `session_index` (topic + unit_title) · audience · editorial |
| Contracts | **One** shared output schema + **one** role prompt that lists stage → required materials |
| LLM input | One **compiled session reference** per session (never a whole-program blob) |
| Outputs (per session) | Plan sheet · article · TL bank · host upgrade notes · facilitation cues; **unit_title** for upload |

Dropped from GO2: grammar registry · 15 class roles · unit exams · `angles[7]` book logic · multi-framework PPP/TTT/TBLF/SK-REC · quiz-heavy SK-REC · publishing into `go-preview` as catalog.

---

## 6. Dual titles + channel split

Inspired by GO2 `_OUTPUT_TYPE_RULES.md`. Every stage requires both titles; channels never mix.

| Field | Audience | Rule |
| --- | --- | --- |
| `title` | Host | Academic / Club stage name OK |
| `student_title` | Learner | Short thematic worksheet heading; **must differ** from `title`; no stage jargon (`L-IN`, `FBDC`, “target language”, etc.) |
| `teacher_notes` | Host | Procedure only (timing, grouping, facilitation) — **not** answer keys |
| `student_content` | Learner | Instructions / prompts only — no full article body when it belongs in materials |

Host deck vs learner plan sheet are different channels of the same session JSON.

---

## 7. Audience guardrails

Mandatory seed (GO2 `target_audience` pattern). Honored on every generate call (`constraint_level: MANDATORY`).

| Field | Locked value |
| --- | --- |
| Profile | Adult corporate professionals (managers / ICs in workplace English Club) |
| Register | Professional, practical, dignity-preserving |
| Avoid | Childish or school-homework tone; pure academic linguistics drills |
| Context | Workplace-relevant; LatAm / Mexico corporate sensitivity when scenarios are local |

Exact copy of the guardrails blob lives in seeds when authored; this table is the policy lock.

---

## 8. Artifact tiers + git policy

Inspired by GO2 `file-layout.md`.

| Tier | Git | Typical path |
| --- | :---: | --- |
| Contracts / docs / client source | Tracked | `LOCKS.md`, `AUTHORING.md`, `Seeds/`, schemas, prompts, `source/`, `notes/` |
| Intermediate (compiled refs) | Ignored | `compiled/` |
| Product (generated sessions) | Ignored | `content/` |
| Preview HTML | Ignored | `preview/` |
| Media binaries / plans | Ignored | `media/` |

**Rule:** regenerable from seeds + scripts does **not** belong in git. Do not keep parallel calendars at repo root.

---

## 9. Factory ≠ delivery

| Lane | Owns | Does not own |
| --- | --- | --- |
| **Factory (B2027)** | Session JSON, seeds, compile/generate/validate/render | API clients, platform upload, Editor.js conversion |
| **Delivery** | Upload (`egregor-api-demo`) and/or Club HTML/PDF preview | Authoring schemas or LLM prompts |

Do not mix delivery code into the factory. Delivery surface (HTML vs PDF host deck vs platform) remains choosable later; the split itself is locked.

---

## 10. Materials shape (speaking)

SK-PROD remapped to Club stages. Learning text lives in materials, not only in `student_content`.

| Stage | Required / preferred materials |
| --- | --- |
| `ART` | `materials.reading_passage` with `passage_id`, content-only `title`, `body` |
| `TL` | `vocabulary_items` and/or `column_banks` (2–4 titled columns) |
| `Q3` / `FP` | Production briefs / discussion questions in `student_content` — **no fake MCQs** for open speaking |
| `FBDC` | Host upgrades in `teacher_notes` (anonymous delayed correction + expressive paraphrases) |
| `REF` | Timing cues (90–120s) in `teacher_notes`; learner prompt in `student_content` |

---

## 11. Situational brief + L-IN fidelity

| Field | Locked value |
| --- | --- |
| Per session | Short `situational_brief` derived from the **topic** |
| `L-IN` | Must realize that brief (situation, stakes) — not a generic Club opener |
| Validate | Flag near-duplicate openers across nearby sessions |

Adapted from GO2 `lead_in_brief` / angle fidelity (no generic interchangeable warm-ups).

---

## 12. Session Definition of Done

Do not treat a session as shippable without a green Club validate. Minimum gates:

- All Club stage codes present in order
- Dual titles on every stage
- TL count **3–5** (prefer `column_banks` of usable phrases)
- Article word count in **120–220**; form = decision vignette; no banned openers
- Plan-sheet split: first **3** → `Q3`; remainder → `FP` (≥6 total)
- `REF` timing cues present (90–120s)
- Audience guardrails honored
- Materials shape respected (`ART` passage, no fake speaking MCQs)
- Channel discipline: `OVW` learner = `HOST_ONLY`; no agenda maps / ceremony in learner copy
- No hits from `Seeds/editorial.json` `banned_phrases` in ART body or learner openers

Inspired by GO2 `validate.py --content` DoD + GL editorial bans — Club-specific checklist.

---

## 13. V1 scaffolding defaults

Locked for factory MVP (revisit after first green session if needed).

| Field | Locked value |
| --- | --- |
| Article provenance | **Generate from topic** (LLM). Curated bank / Mon case IP review later if needed. |
| `situational_brief` | **Auto** from calendar topic string at compile |
| `OVW` depth | **Template** on **host channel only** — not LLM-authored; learner `student_content` = `HOST_ONLY` |
| Render target | **Local host + learner HTML** only; skip Egregor upload/convertibility for now |
| Upload / unit title | **`unit_title` = topic** (see §3) |

---

## 14. Channel discipline (GO2-style)

Borrowed from GO2 SK-PROD speaking; Club stages unchanged.

| Channel | Rule |
| --- | --- |
| `student_content` | Task prompts and questions only. No ceremony (“Welcome to today’s…”), no stage agenda maps, no “we will spend our time…” |
| `teacher_notes` | Short procedure bullets (grouping, timing, what to listen for). Not a spoken host script or minute-by-minute monologue |
| `OVW` | Host-only: `teacher_notes` = filled OVW template; `student_content` = exact string `HOST_ONLY` |
| `L-IN` | 2–3 sharp situation questions from `situational_brief` — no lesson welcome |
| `TL` | Prefer `column_banks` of usable phrases; avoid dictionary-definition paragraphs in `student_content` |
| `ART` learner line | One short read-aloud prompt; full text only in `materials.reading_passage` |
| `Q3` / `FP` | Questions (+ optional one-line stem). No coaching essays |

Learner HTML may omit stages whose `student_content` is `HOST_ONLY`.

---

## 15. Editorial voice (GL-style)

Borrowed from Global Leadership `docs/locks/editorial.md` + gl-factory `banned_phrases` — not the full GL asset pack.

| Field | Locked value |
| --- | --- |
| Show, Don't Tell | **Required** for `ART` |
| `ART` form | **decision_vignette** — workplace scene/decision that forces opinion; not a textbook explainer |
| Banned openers / slop | Canonical list in [`Seeds/editorial.json`](Seeds/editorial.json); validate fails on hits in ART body and L-IN/learner openers |
| Invented statistics | Prohibited unless explicitly illustrative (prefer qualitative) |
| Out of scope from GL | T1–T4 Bloom forks, 6-asset packs, SJQs, framework templates |

---

## Deferred (after first green session)

Do not block scaffolding on these; lock when generation batch starts:

- Session identity / metatext first page (session_id, unit_title, CEFR, CONTENT ORDER roster)
- Rich-text lexis: `**phrase**` only in article / student prose; never in titles
- Offline preflight before batch (prompts, schema holes, index coverage)
- Create compose stop-on-red (no render after failed validate)
- Egregor upload converter (unit title = topic)

---

## Explicitly unlocked / out of scope

- Whether pre–Oct 1 topics re-enter the index
- Media slots (21:9 banner, article narration, silence pads)
- Voice pack / TTS
- Full convertibility → Egregor platform (deferred past local HTML)
- Curated article bank / Mon case IP review (past v1 generate-from-topic)
- Exams
- GL pedagogy tiers / full workshop asset suites
