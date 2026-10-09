# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Students who write a thesis entirely by hand and use margi from their AI coding agent
(Claude Code, Codex, Cursor) for feedback. The dashboard (`margi dash`) is for the student
alone: a private check-in between writing sessions. It is not built for advisors.

## Product Purpose

margi is a feedback layer that keeps AI "in the margins, never in the text". The agent reads
the thesis and writes documentation, rubric grades, literature ratings and todos, but only
inside `margi/`, in commits separate from the human's. The dashboard turns that append-only
record into one view whose first job is to answer "what should I do next?", with progress over
time underneath.

## Positioning

Every number margi shows carries provenance injected by scripts, not by the AI: HEAD SHA, file
hashes, rubric version, model, docs completeness, timestamp. The dashboard can therefore show
*why* a score may not be comparable (rubric or model changed, low-confidence docs) instead of
drawing smooth trend lines that imply it is.

## Operating Context

- The student runs `margi dash` in the thesis repo; it builds a self-contained HTML snapshot
  from `margi/` (and `gh` issue state when available) and opens it in a browser.
- Real work happens in the agent: the dashboard suggests `/margi …` commands to copy and paste;
  it never runs them.
- Todos become GitHub issues after human acceptance; closing happens on GitHub or via
  `/margi todos`.

## Capabilities and Constraints

- Read-only view. No write-back, no server, no buttons that execute commands.
- Fully offline single file: no CDN scripts, no web fonts. English UI; thesis titles and
  comments are shown as written.
- Generated on demand into a gitignored location; never committed, never written by `finalize`.
- Built with the Python standard library (margi's runtime deps are click, pyyaml, jsonschema,
  pypdf).
- Must work without git and without `gh` (degraded, stated plainly).

## Brand Commitments

- Name: margi (lowercase). Tagline: "AI in the margins, never in the text."
- The dashboard must never contain or suggest thesis prose.

## Evidence on Hand

- Record format: `skills/margi/schema/feedback.schema.json`; reader: `src/margi/status.py`.
- Rubric categories: `skills/margi/rubrics/default/` (alignment, argument, evidence, method,
  scholarship, structure, style).
- No real thesis data ships with the repo; demos must use clearly synthetic data.

## Product Principles

1. Next step before score: guidance outranks grades.
2. Show comparability breaks; never imply precision the data doesn't have.
3. The human decides; margi proposes.
4. The repository is the source of truth; the dashboard is a disposable view.
