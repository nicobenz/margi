---
name: margi-propose
description: Turn the user's free-form PROPOSAL.md into structured, sourced project documentation in margi/docs/ (research question, dataset, method, field, structure, constraints) and list what is still unclear in open-questions.md. Use for /margi propose or /margi-propose.
---

# margi propose

Goal: clear, sourced documentation of what the user plans. **Every other margi skill grades
against these documents.** A score is only meaningful if the goals are documented.

The user writes their plan in `PROPOSAL.md`, in their own words and as unstructured as they
like. You turn it into the docs. You document their plans; you do not invent, complete or
improve them. You do **not** interview the user: gaps become entries in `open-questions.md`,
the user adds to `PROPOSAL.md`, and runs `/margi propose` again.

Write only to `margi/docs/` and `margi/.staging/`. Never touch anything outside `margi/`,
including `PROPOSAL.md`. Talk to the user as described in "Talking to the user" in
`../margi/SKILL.md`.

## 0. Preflight

Run `uv run margi finalize --check`. Stop if it fails.

## 1. Read

1. The source: the file passed with `--from <file>`, otherwise `propose.source` from
   `thesis.config.yml` (default `PROPOSAL.md`). Read it with line numbers. For a PDF, run
   `uv run margi extract-pdfs <file>` and read the text file it prints.
2. If the source has nothing beyond the template's headings and comments, stop and tell the
   user in one line to write their thoughts into it and commit first. No draft, no finalize.
3. On a re-run: the current `margi/docs/*.md` and `CHANGELOG.md`, to see what changed.

## 2. Write the docs

Fill the templates in `margi/docs/`. The files already exist with fixed `## ` headings; see
`templates/` in this skill for the originals. **Keep every `## ` heading.**

- The proposal is unstructured. Map each thought to the doc field it belongs to, regardless
  of which proposal heading it sits under. One thought may feed several fields.
- Attribute **every** statement: `(src: PROPOSAL.md:12-18)`. Statements from earlier
  challenge sessions keep their `(user, <date>, challenge)` tag.
- Paraphrase faithfully. Quote the research question and title ideas verbatim.
- Keep the user's certainty: "maybe", "thinking about" or two alternatives side by side are
  recorded as tentative or undecided, not as decisions.
- Replace `_not yet documented_` only where the proposal says something real. Leave the
  placeholder otherwise.
- Re-run: rewrite fields from the current proposal. Where the proposal now contradicts an
  earlier statement (including a challenge refinement), keep the earlier one, add the new
  one, and raise the contradiction in `open-questions.md`.
- Planned outline: record it in `structure.md` inside the fenced YAML block marked
  `# margi-structure`, with titles and, where the user gives them, target shares
  (`target: 15%`). Titles must match the thesis headings for `uv run margi outline`; if the
  planned chapters differ from the headings in the thesis, record the plan and raise it
  as an open question.

## 3. Open questions

Update `margi/docs/open-questions.md` so it lists what the proposal leaves unclear:

- One bullet per gap: an empty field, a vague statement, an internal contradiction, or a
  claim the rest of the plan depends on but does not support.
- Each bullet is one concrete question, prefixed with the proposal heading where the answer
  belongs and the date it was first raised:
  `- **Method** (2026-10-08): How will you check that the topic model's clusters are meaningful?`
- Ask; never suggest answers or options.
- Be most demanding on: the research question (one sentence, answerable, scoped), the data
  (what, how much, from where, access/licensing, selection), the method (what exactly, why
  that one, how it will be validated) and the expected contribution.
- Remove questions the proposal now answers; keep the date on those still open. Keep
  questions raised in challenge sessions unless the proposal answers them.
- Order by importance. Aim for the 5–12 questions that matter most, not every empty field.

## 4. Changelog and draft

1. Append to `margi/docs/CHANGELOG.md`: date, `propose`, the files changed, and a one-line
   reason. Never edit earlier entries.
2. Write `margi/.staging/propose.json`:
   - `command`: `propose`
   - `scope`: `initial` or `update`
   - `summary`: what is now documented and what remains open
   - `files_read`: the source and the docs you read
   - `payload`: `{"source": "PROPOSAL.md", "fields_filled": [...], "fields_open": [...], "questions_open": N, "questions_resolved": N}`
3. Run `uv run margi finalize`, then `uv run margi status`.

## 5. Report

At most ~5 lines:

- Completeness, e.g. `Docs 24/28 (86%)`, and whether that is below the grading threshold.
- The three most important open questions, each with its proposal heading.
- One line: the full list is in `margi/docs/open-questions.md` (as a link); add to
  `PROPOSAL.md`, commit, and run `/margi propose` again.
