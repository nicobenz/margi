# End of thesis (design draft)

Status: implemented (`src/margi/submission.py`, `src/margi/ai_report.py`, `commands/defend.md`, the
dashboard's Submission tab).

Three commands for the last weeks. Proofreading, formatting, front matter and the declaration text
stay out of scope by decision.

## `/margi submit-check` (no AI)

`uv run margi submit-check` records a `submit-check` record and commits it as the bot.

| Check | How | Findings |
|---|---|---|
| Quotations | Direct quotes (Typst `"…"`/`“…”` of 6+ words, `#quote[…]`) paired with the citation that follows on the same line (or starts the next line when the quote ends its line), or a `#quote` attribution. The PDF comes from the bib `file` field, a `read` rating's `cite_key`, or a file named like the key. Words are compared normalised and without surrounding punctuation; failing an exact match, the closest passage by words (≥ 80 % similar) is reported with the differing words side by side. | matches · differs · not found in the PDF · no PDF · no citation near the quote |
| Bibliography | `literature.bib` against the `@key`s in the thesis (labels and `fig:`/`tab:`/… refs excluded) and the PDFs in the literature folder | cited but not in the bibliography · never cited · lacks author/title/year · duplicate key · duplicate DOI · PDF without an entry |
| Length | total against `length` in the timeline block | over the goal |
| Sections | sections with text | changed since graded · never graded · not ready |
| Open items | comment lifecycle, todos | open major comments, open todos |

"Need attention" (red): quotes that differ or aren't found, citations missing from the
bibliography, length over the goal. PDF page numbers are reported as PDF pages; they often differ
from printed page numbers, so a page mismatch is not a finding.

## `/margi ai-report` (no AI)

Writes `margi/ai-use.md` (committed) and a printable `margi/dash/ai-use.html` (ignored, like the
export): period, runs per command, models, every run with what it produced, how separation is
enforced, and the guard's verdict over the whole history. If the guard finds violating commits the
report says so and lists them instead of claiming separation. It never drafts the declaration or
an AI statement.

## `/margi defend [chapter]`

The agent asks examiner questions one at a time over the finished thesis (targets: open or disputed
majors, low scores, contested literature, the challenge lenses). The student answers, marks "I'd
struggle here" or skips. The `defend` record keeps questions with targets and outcomes, the
student's answers verbatim only if they agree, and weak spots named as problems. No model answers,
nothing written into `margi/docs/`.

## Dashboard

Submission tab: the latest check (date, commit, findings, a warning when the thesis changed since),
quotations with both versions side by side for differing words, bibliography findings, what is
still open with grade commands, questions marked "I'd struggle here", and the AI-use and defense
commands. Within 21 days of the deadline (or after it), a next step suggests `/margi submit-check`
when no check matches the current thesis commit.
