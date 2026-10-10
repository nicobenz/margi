# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

The product is a Python CLI (`click`, `pyyaml`, `jsonschema`, `pypdf`; `pyproject.toml`) plus agent
skills in `skills/`. The planned dashboard is a **single self-contained HTML file** (user, 2026-10-09).

Confirmed by the user on 2026-10-09:
- The dashboard is **`margi/dash.html`**. `uvx margi init` creates it with no data in it yet.
- Ideally `margi/` holds `dash.html` at the top and everything else in subfolders (`docs/`,
  `feedback/`, `todos/`, …), so the folder reads as dashboard first, sources below. Files that
  `init` writes deterministically, such as `margi/README.md` and `margi/.gitignore`, may stay at
  the top level.
- The boundary is about AI text, not files: margi never puts AI-written text outside `margi/`.
  Files created deterministically are fine.
- Every grading step or other data change refreshes the dashboard, so it always shows current data.
- **`margi export`** writes **`export.html`**: a single self-contained file that works offline.
  The everyday `dash.html` does not have to meet that bar.

Data loading (delegated to the build, 2026-10-09): the user does not want to restrict how data gets
into `dash.html` and asked for the approach that keeps the most options open. Chosen: `dash.html`
stays a fixed page, and refreshes only rewrite data files in a subfolder. The page loads those files
with relative `<script src>` tags, which work when the file is opened straight from disk and also
when served. Because the page is fixed, `margi export` only has to inline the data to build
`export.html`, and the data files can be read by other tools.

Open: where `export.html` is written; the exact name and location of the data files.

## Users

- **Primary: thesis students** who write their thesis entirely by hand in Typst and run margi from
  a coding agent (`/margi …` commands) to get feedback, grades, literature ratings and todos
  without AI-written text (README.md).
- **Digital humanities is a deliberate focus.** The default rubric is "for humanities / digital
  humanities theses" (`skills/margi/rubrics/default/rubric.yml`), scale anchored to an MSc thesis.

Advisors read `git log -- margi/` as an audit trail (README.md), but the user did not name them as
a primary audience for design work.

## Product Purpose

margi is a feedback layer for a human-written thesis: the agent reads the thesis and writes
documentation, rubric grades, literature ratings and todos, only inside `margi/`, in commits kept
separate from the student's. Success is a student who keeps writing every word themselves while
knowing where the thesis stands and what to do next.

The first visual surface is a **dashboard** in one self-contained HTML file that shows:
- scores (rubric grades per section and category),
- next steps,
- suggested next margi commands,
- how scores develop over time.

## Positioning

"AI in the margins, never in the text." margi grades and supports; it never writes thesis prose.
The separation is enforced mechanically (`margi finalize`, commit hook, CI guard) rather than taken
on trust (README.md). The user calls this separation the main identity but not a rigid commitment
yet (2026-10-09).

## Operating Context

- The student works in a git repository with `main.typ`, `chapters/`, `refs.bib`, `lit/` and
  `PROPOSAL.md`; margi lives in `margi/` (README.md).
- Workflow: write `PROPOSAL.md` → `/margi propose` → `/margi challenge`, `/margi grade <section>`,
  `/margi outline`, `/margi read`, `/margi todos`, `/margi status`.
- Records are append-only JSON in `margi/feedback/`, each with command, scope, summary, scores,
  comments and provenance (timestamp, HEAD SHA, model, docs completeness, low-confidence flag)
  (`skills/margi/schema/feedback.schema.json`, `src/margi/status.py`).
- `margi status` today is plain text: docs completeness against a threshold, latest grade per
  scope, outline snapshot with delta, todo counts, the five most recent runs (`src/margi/status.py`).

## Capabilities and Constraints

- Scores: 1–5 per rubric category (alignment, argument, evidence, scholarship, method, structure,
  style); categories may be omitted when they don't apply to a section (`rubric.yml`). Only the
  bundled default rubric is supported for now; custom rubrics may come later with bounded
  scales (1–5 now; 1–10 or percentages possible) and floor/ceiling descriptions (user, 2026-10-10).
- Comments carry severity `major | minor | note` and an optional anchor (file, lines, verbatim
  quote, anchor status `ok | relocated | unresolved`).
- A grade can be marked low-confidence when the project docs are incomplete.
- Outline snapshots hold character counts and shares per section, compared to targets in
  `structure.md`.
- Todos have states: proposed, accepted (not synced), closure proposals, synced to GitHub.
- Typst is the only supported thesis format; adapters are the extension point.
- Status: alpha, version 0.3.0 (`pyproject.toml`).
- Next steps come from both sources (user, 2026-10-09): deterministic checks (e.g. docs
  completeness, missing grades, stale outline) are passed to the agent as input. The agent combines
  them with chat context, such as a focus the student already asked for. The dashboard should make
  clear that a suggestion can rest on either source.
- The dashboard has an empty state: the freshly initialised file before any record exists.

## Brand Commitments

Name "margi" and the tagline "AI in the margins, never in the text." exist (README.md). The user
made none of them binding for now (2026-10-09).

## Evidence on Hand

- Real schemas and rubric: `skills/margi/schema/feedback.schema.json`,
  `skills/margi/rubrics/default/`.
- No real thesis data, users, testimonials or institutions are in this repository. Design work must
  use clearly synthetic sample records and must not invent adoption or endorsement.

## Product Principles

1. **The thesis is the student's.** Anything margi shows names problems and directions; it never
   offers replacement prose.
2. **Show where the work stands, then what to do next.** Scores are only useful next to the next
   step and the command that takes it.
3. **Every number is traceable.** Scores, comments and trends point back to a record, a section and
   a date, and say when confidence is low.
4. **Progress over verdicts.** Development over time matters as much as the latest score.

## Accessibility & Inclusion

No product-specific requirement stated.
