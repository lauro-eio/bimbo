# B2027 output type rules (Club speaking)

Match `Seeds/session_output_schema.json`. Do not invent extra keys.

## Session identity (upload titles)

| Field | Rule |
| :--- | :--- |
| `session_id` | Compiled class id (`c001`–`c100`) |
| `topic` | Exact topic from compiled `session_context` |
| `unit_title` | **Equals** `topic` (platform upload / unit title) |
| `session_title` | **Equals** `topic` |
| `date`, `weekday`, `track` | **Forbidden** |

## Dual titles (every stage)

| Field | Audience | Rule |
| :--- | :--- | :--- |
| `title` | Host | Club / academic stage name OK |
| `student_title` | Learner | Short thematic worksheet heading; **must differ** from `title` |

**Forbidden in `student_title`:** lead-in, overview, target language, Q3, article, freer practice, reflection, FBDC, wrap-up, stage codes (`L-IN`, `OVW`, `TL`, `ART`, `FP`, `REF`, …).

**Safe `student_title` examples (use this pattern):**

| Stage | Host `title` OK | Learner `student_title` |
| :--- | :--- | :--- |
| L-IN | Welcome / Lead-in | Opening questions |
| OVW | Overview | Session map |
| TL | Target Language | Phrases to use |
| Q3 | 3 questions | First three |
| ART | Article Reading | Shared story |
| FP | Freer practice | Keep talking |
| REF | Reflection | Your takeaways |
| FBDC | Feedback / upgrades | Stronger wording |

Never put the word **reflection**, **article**, **overview**, or stage codes in `student_title`.

## Channels (GO2 discipline)

| Field | Rule |
| :--- | :--- |
| `teacher_notes` | Short procedure bullets only. No answer keys. No long spoken scripts. |
| `student_content` | Learner tasks/questions only. No ceremony. No session agenda maps. |
| `OVW.student_content` | Exact string `HOST_ONLY` |
| `materials` | Allowed keys only: `reading_passage`, `vocabulary_items`, `column_banks`. **No** `tasks`. |

## ART

- Body = decision vignette (Show Don't Tell).
- Respect word budget from compiled `budgets`.
- Never use banned phrases from compiled `editorial.banned_phrases`.
- Full text only in `materials.reading_passage`; learner prompt is one short line.

## Rich text

- `**phrase**` allowed in `reading_passage.body` and light learner prose.
- Forbidden in titles, `teacher_notes`, and plan-sheet questions.
- No backticks, single-asterisk emphasis, or raw HTML.

## Plan sheet

- `plan_sheet.questions` ≥ 6.
- First 3 appear in `Q3` `student_content`; remainder in `FP`.

## Speaking only

No quizzes, `items[]` soup, or MCQs for open discussion.
