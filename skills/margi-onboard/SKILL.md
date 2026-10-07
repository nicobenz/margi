---
name: margi-onboard
description: Build the thesis project documentation in margi/docs/ (research question, dataset, method, field, structure, constraints) from the README or an exposé, then interview the user to fill gaps. Use for /margi onboard or /margi-onboard.
---

# margi onboard

Goal: clear, sourced documentation of what the user plans. **Every other margi skill grades
against these documents.** A score is only meaningful if the goals are documented, so
thoroughness here matters more than speed.

You document the user's plans. You do not invent or improve them. Write only to
`margi/docs/` and `margi/.staging/`. Never touch anything outside `margi/`.

## 0. Preflight

Run `margi finalize --check`. Stop if it fails.

## 1. Gather sources

1. If the user passed `--from <file>`, read that file. Otherwise read `onboard.source` from
   `thesis.config.yml` (default `README.md`). For PDFs, run `margi extract-pdfs <file>` and
   read the text file it prints.
2. Also look briefly at: other top-level `*.md` files with exposé/proposal/idea/notes-like
   names, the thesis main file's title and headings, and the bibliography file.
3. Keep a **source log**: every place you checked, and what you found in it, including
   "nothing relevant found". It goes into the draft payload, and its gist goes into the
   "Sources" section of `research-question.md`.

## 2. Draft the docs

Fill the templates in `margi/docs/`. The files already exist with fixed `## ` headings; see
`templates/` in this skill for the originals. **Keep every `## ` heading.** Replace
`_not yet documented_` only where you have real information.

Attribute **every** statement:
- from a file: `(src: README.md:12-18)`
- from the interview: `(user, 2026-10-07)`

Paraphrase faithfully, and quote the user's own formulation of the research question verbatim.

## 3. Interview

For every field that is still empty, vague, or contradicted by another source, ask the user
explicit questions. Ask **2–4 at a time**, grouped by topic, and keep each one concrete. Use
`interview.md` in this skill as the question bank. Rules:

- Ask; don't suggest answers. If the user asks for options, offer a few neutrally and record
  which one they chose and why.
- Push for precision on: the research question (one sentence, answerable, scoped), the corpus
  (what, how much, from where, access/licensing), the method (what exactly, why that one,
  how it will be evaluated) and the expected contribution.
- Contradictions between sources and answers: show both and ask which one holds.
- The user may skip a question. Move it to `open-questions.md` with the date.
- Stop when every field is filled or explicitly deferred, or when the user wants to stop.
  Tell them that `margi onboard` can be run again any time.

Update the docs after each round of answers, so progress is saved even if the session ends.

## 4. Structure targets

If the user has a planned outline, record it in `structure.md` inside the fenced YAML block
marked `# margi-structure`. Include titles and, where the user knows them, target shares
(`target: 15%`). `margi outline` compares the written text against these targets.

## 5. Changelog and draft

1. Append to `margi/docs/CHANGELOG.md`: date, `onboard`, the files changed, and a one-line
   reason. Never edit earlier entries.
2. Write `margi/.staging/onboard.json`:
   - `command`: `onboard`
   - `scope`: `initial` or `update`
   - `summary`: what is now documented and what remains open
   - `files_read`: the sources you used
   - `payload`: `{"sources_checked": [{"path": "...", "found": "short description or 'nothing'"}], "questions_asked": N, "fields_filled": [...], "fields_open": [...]}`
3. Run `margi finalize`, then `margi status`, and show the user the documentation completeness.
