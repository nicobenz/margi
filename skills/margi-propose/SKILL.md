---
name: margi-propose
description: Turn the user's free-form PROPOSAL.md into structured, sourced project documentation in margi/docs/ (research question, dataset, method, field, structure, constraints), record what is still unclear in open-questions.md and ask the user those questions in chat. Use for /margi propose or /margi-propose.
---

# margi propose

Goal: clear, sourced documentation of what the user plans. **Every other margi skill grades
against these documents.** A score is only meaningful if the goals are documented.

The user writes their plan in `PROPOSAL.md`, in their own words and as unstructured as they
like. You turn it into the docs. You document their plans; you do not invent, complete or
improve them. Gaps become entries in `open-questions.md` (the written record, kept in git
history). After the docs are written, you and the user talk through those questions in
plain chat; their answers go into the docs. The user never has to answer inside
`open-questions.md`.

Write only to `margi/docs/` and `margi/.staging/`. Never touch anything outside `margi/`,
including `PROPOSAL.md`. Talk to the user as described in "Talking to the user" in
`../margi/SKILL.md`.

With `--review`, or when the user asks to go through their open questions again, also ask
the questions they deferred earlier (see "Deferred questions" below).

## 0. Preflight

Run `uv run margi finalize --check`. Stop if it fails.

## 1. Read

1. The source: the file passed with `--from <file>`, otherwise `propose.source` from
   `thesis.config.yml` (default `PROPOSAL.md`). Read it with line numbers. For a PDF, run
   `uv run margi extract-pdfs <file>` and read the text file it prints. If it flags pages
   (third column, e.g. `3:no-text`), read those pages from the PDF itself.
2. If the source has nothing beyond the template's headings and comments, stop and tell the
   user in one line to write their thoughts into it (fragments are fine) and run `/margi propose`
   again; margi offers to save it then. No draft, no finalize.
3. On a re-run: the current `margi/docs/*.md` (including `open-questions.md`) and
   `CHANGELOG.md`, to see what changed and which questions the user already deferred.

## 2. Write the docs

Fill the templates in `margi/docs/`. The files already exist with fixed `## ` headings; see
`templates/` in this skill for the originals. **Keep every `## ` heading.**

- The proposal is unstructured. Map each thought to the doc field it belongs to, regardless
  of which proposal heading it sits under. One thought may feed several fields.
- Attribute **every** statement: `(src: PROPOSAL.md:12-18)`. Statements the user gave in
  chat keep their `(user, <date>, propose)` or `(user, <date>, challenge)` tag; a re-run
  never drops them just because the proposal doesn't repeat them.
- Paraphrase faithfully. Quote the research question and title ideas verbatim.
- Keep the user's certainty: "maybe", "thinking about" or two alternatives side by side are
  recorded as tentative or undecided, not as decisions.
- Replace `_not yet documented_` only where the proposal says something real. Leave the
  placeholder otherwise.
- Re-run: rewrite fields from the current proposal. Where the proposal now contradicts an
  earlier statement (including a chat answer or a challenge refinement), keep the earlier
  one, add the new one, and raise the contradiction in `open-questions.md`.
- Planned outline: record it in `structure.md` inside the fenced YAML block marked
  `# margi-structure`, with titles and, where the user gives them, target shares
  (`target: 15%`). Titles must match the thesis headings for `uv run margi outline`; if the
  planned chapters differ from the headings in the thesis, record the plan and raise it
  as an open question.
- Dates: record the submission date, a start date and milestones in `constraints.md` inside
  the fenced YAML block marked `# margi-timeline` (see the commented example in the template),
  next to the prose and its citation. Only dates the user actually gives, as `YYYY-MM-DD`; a
  vague date ("end of March") stays in the prose and becomes an open question. A milestone
  gets `sections` and a `state` (`drafted`, `graded` or `settled`) only when the user ties it
  to chapters ("chapter 2 drafted by December"); otherwise it is a plain date with a `label`.
  `length` is the overall length limit or goal, in the unit of `count` in
  `thesis.config.yml`, only if the user gives one in that unit.

## 3. Open questions

Update `margi/docs/open-questions.md` so it lists what the docs still leave unclear:

- One bullet per gap: an empty field, a vague statement, an internal contradiction, or a
  claim the rest of the plan depends on but does not support.
- Each bullet is one concrete question, prefixed with the proposal heading where the answer
  belongs and the date it was first raised:
  `- **Method** (2026-10-08): How will you check that the topic model's clusters are meaningful?`
- Ask; never suggest answers or options.
- Be most demanding on: the research question (one sentence, answerable, scoped), the data
  (what, how much, from where, access/licensing, selection), the method (what exactly, why
  that one, how it will be validated) and the expected contribution.
- Remove questions the proposal or the docs now answer; keep the date on those still open.
  Keep questions raised in challenge sessions unless they are answered.
- Never re-raise a deferred question as a new bullet, and never reword one to ask it again.
  Keep its bullet, date and marker as they are (see below). A field the user recorded as
  undecided is covered by its deferred question, not a new gap.
- Order by importance. Aim for the 5–12 questions that matter most, not every empty field.

### Deferred questions

A question the user says they can't answer yet ("don't know yet", "not decided") or want to
leave for later ("skip", "later", "not now") stays in `open-questions.md`, still open, with a
marker after the date:

- `- **Method** (2026-10-08; not decided yet 2026-10-09): …`: the user doesn't know yet.
  The matching doc field also records it as undecided, tagged `(user, <date>, propose)`.
- `- **Data** (2026-10-08; skipped 2026-10-09): …`: the user chose not to answer now.

Deferred questions are **not asked again**, in this run or later ones, unless the user runs
`/margi propose --review` or asks to review their open questions. They still count as open.
Remove one only when the proposal or a later answer settles it. In a review, a question the
user defers again keeps its first date and gets the new marker date.

## 4. Changelog and draft

1. Append to `margi/docs/CHANGELOG.md`: date, `propose`, the files changed, and a one-line
   reason. Never edit earlier entries.
2. Write `margi/.staging/propose.json`:
   - `command`: `propose`
   - `scope`: `initial` or `update` (`chat` for the conversation in step 6)
   - `summary`: what is now documented and what remains open (`scope: chat`: what the user
     answered or deferred)
   - `files_read`: the source and the docs you read
   - Write it with an absolute path or from the project root (do not rely on a `cd`), and
     check `margi finalize` printed `wrote margi/feedback/...`. If it did not, the draft is
     missing: fix that and finalize again.
   - `fields_filled` lists only fields with real content; a plan without calendar dates
     does not fill `constraints.deadline`.
   - `payload`: `{"source": "PROPOSAL.md", "fields_filled": [...], "fields_open": [...], "questions_open": N, "questions_resolved": N, "questions_deferred": N}`.
     `questions_open` counts deferred questions too; `questions_deferred` is how many of them
     are deferred after this run.
3. Run `uv run margi finalize`, then `uv run margi status`.

## 5. Report

At most ~5 lines:

- Completeness, e.g. `Docs 24/28 (86%)`, and whether that is below the grading threshold.
- How many questions are open and how many of them are deferred, with a link to
  `margi/docs/open-questions.md`.
- If a question is open and not deferred (with `--review`: any open question): the most
  important one, which starts the conversation below. Leave out the `next` and `dashboard`
  lines; they close the conversation instead.
- Otherwise: the `next` and `dashboard` lines, as in every report.

## 6. Talk through the open questions

This is a conversation, not a form. Ask in plain chat, **not** with the structured question
tool: these questions have no options to offer, and the user answers in their own words.

- Ask one question at a time, two only when they are closely linked, most important first.
  Name the heading it belongs to and why it matters for the thesis in one short clause. Never
  suggest answers or options.
- Only ask questions that are in `open-questions.md` and not deferred (with `--review` or
  when the user asks to review their open questions: deferred ones too). Never ask a
  deferred question again on your own, and don't argue when the user defers one.
- Read each reply for what it settles:
  - **An answer**: write it into the matching doc field, paraphrased faithfully and in the
    user's certainty, tagged `(user, <date>, propose)`, and remove the question from
    `open-questions.md`. If the answer is too vague to settle the gap, ask one narrower
    follow-up; otherwise move on. If it raises a new gap, add it to `open-questions.md`.
  - **Can't answer yet / skip**: mark the question as deferred (see above). If the field is
    undecided, record that in the doc too.
  - **Something else**: the user may correct an earlier statement, answer several questions
    at once, or answer one you haven't asked yet. Record all of it the same way.
- After each reply that changed `margi/docs/`, append a `CHANGELOG.md` entry (date,
  `propose: chat`, files changed, one line per question answered or deferred), write
  `margi/.staging/propose.json` with `scope: chat` and the same payload fields as above, and
  run `uv run margi finalize`. Don't mention any of this, and leave out the `next` and
  `dashboard` lines in these replies: just acknowledge briefly what you recorded and ask
  the next question.
- When no undeferred question is left, or the user wants to stop or moves on to something
  else, close with one line: how many questions are still open (deferred ones included),
  and that `/margi propose --review` goes through the deferred ones. Then the `next` and
  `dashboard` lines from the last finalize.
