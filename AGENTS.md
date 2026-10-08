## margi rules (AI feedback layer for this thesis)

This repository contains a thesis written **entirely by a human**. AI agents working here
through margi skills give feedback in the margins; they never write the text.

1. **Never edit anything outside `margi/`.** No thesis source (`*.typ`, `*.bib`, figures, …),
   no config, no README. Read anything; write only to `margi/docs/`, `margi/todos/` and
   `margi/.staging/`.
2. **Never write thesis prose.** Comments name the problem and why it matters ("the argument
   in §2.1 assumes X without evidence"). They never contain replacement sentences,
   rewritten paragraphs, or "you could write: …".
3. **Never write provenance.** Do not add timestamps, SHAs, hashes or model ids to drafts.
   `margi finalize` injects them.
4. **`margi/feedback/` is append-only.** Never modify or delete existing records.
5. **Never commit, push, reset or checkout.** `margi finalize` commits margi/ as the margi
   bot. Human work and margi work are never mixed in one commit.
6. **Don't invent facts about the project.** Everything in `margi/docs/` cites a source file
   and line range or the date the user said it in an interview. Unknown → `open-questions.md`.
7. **Start every run with `uv run margi finalize --check`** and stop if it fails. End every run with
   `uv run margi finalize`.
