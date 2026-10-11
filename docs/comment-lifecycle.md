# Comment lifecycle (design draft)

Status: records and commands implemented (`src/margi/lifecycle.py`); dashboard not yet. New
command: `/margi respond <ids…>`.

Today a grade comment lives in exactly one record. A regrade numbers its comments from `c1` again,
so nobody can see whether last week's major comments were fixed. This draft gives every grade
comment a state from the grade that creates it until it is closed, and keeps every state change
as an append-only record.

Goal: the student comes back to a section after revising it and sees *"Since 3 Oct: 4 of 6
major comments resolved"*, with evidence they can check. The advisor reads the same states in
`git log -- margi/` and `export.html`.

## Scope

- Only `major` and `minor` comments from `grade` records. `note` comments (strengths) and
  comments from `read` have no lifecycle.
- Nothing in `margi/feedback/` is ever changed. States come from later records.
- The dashboard stays static and read-only. Any action on it means copying a command.
- Not in scope: todos, writing from the browser, auto-closing.

## Comment numbers

`finalize` gives each new comment a thesis-wide number (`c17`) that is never reused. Drafts keep
their local `c1…` ids; finalize remaps them, along with each score's `comment_ids`. A carried-over
comment keeps its number across regrades.

Legacy records without stored numbers are numbered at collect time, in record order, before any
stored number.

## States

| State | Set by | Closed? |
|---|---|---|
| Open | the grade that created it | no |
| Addressed (awaiting check) | the student | no, waits for the next grade |
| Disputed (awaiting check) | the student, reason optional | no, waits for the next grade |
| Won't fix | the student, reason optional | **yes**, the student's decision; the next grade does not judge it again |
| Resolved | the next grade, with evidence (file:lines) | yes |
| Withdrawn | the next grade accepts a dispute | yes |

If the next grade rejects a dispute, the comment goes back to **Open** with margi's answer
attached. The answer names the problem, like a comment body, and never contains replacement
prose. A student may dispute the same comment again; each rejection gets its own answer.

A won't-fix is never reopened. The thesis is the student's.

## Signals (deterministic, never a state)

At every dashboard refresh, `verify_anchor` (`src/margi/finalize.py`) runs against HEAD for each
comment that isn't closed:

- *passage unchanged*: the quote is still at its lines;
- *passage moved*: the quote is unchanged but elsewhere in the file;
- *passage changed or removed*: the quote is no longer in the file.

Comments without an anchor (something missing) show *section changed since* when the section's
files differ from the grade's SHA.

These are evidence only. Deleting a sentence doesn't prove the problem is solved, so a signal
never closes a comment.

Signals are only as fresh as the last refresh, so this ships together with a
"data as of commit … · N commits since" line on the page.

## Regrade

A grade of section S must give a verdict on every Open, Addressed and Disputed comment in S and
its subsections. Comments follow their anchors, so a renamed or renumbered section keeps them.

The draft gets a top-level `verdicts` list:

```json
"verdicts": [
  {"ref": "c17", "verdict": "resolved", "reason": "The claim now cites Underwood 2019 (ch02.typ:41–44)."},
  {"ref": "c18", "verdict": "open", "reason": "Passage unchanged; the jump from corpus to genre is still unexplained."},
  {"ref": "c21", "verdict": "withdrawn", "reason": "Accepted: the term is defined in 1.2, as the student says."}
]
```

- `verdict`: `resolved | open | withdrawn`. `withdrawn` only for a disputed comment.
- `reason`: ≤ 600 chars. For `resolved`, it cites file and lines. It never proposes text.
- `finalize` rejects a draft that leaves a comment out or names one that isn't Open, Addressed or
  Disputed. Completeness is enforced mechanically, not trusted.
- New problems become new comments. A problem that is still there stays under its old number.
- A *not ready to grade* record makes no verdicts. The comments stay as they are.

The chat report after a regrade opens with the verdicts, then scores, then new major comments:

```
Since 3 Oct: c3, c5 resolved · c4 still open · your dispute of c6 accepted
```

## /margi respond

`/margi respond c17 c18`, usually copied from the dashboard.

1. Preflight as for every command: the working tree must be clean outside `margi/`.
2. The agent asks for each comment's state through the question tool (Addressed, Disputed,
   Won't fix) and for an optional reason through "Other".
3. It shows the exact text it will record and passes the student's words **verbatim** to the
   deterministic helper `uv run margi respond`. The agent never edits, shortens or paraphrases a
   reason.
4. The helper writes `margi/feedback/<timestamp>_respond_<scope>.json` and commits it as
   `margi: respond c17 c18` under the **student's** git identity, not the bot's.

Record payload:

```json
{"command": "respond", "scope": "2.1",
 "payload": {"responses": [
   {"ref": "c17", "status": "addressed"},
   {"ref": "c18", "status": "disputed", "reason": "The term is defined in 1.2."}
 ]}}
```

- `status`: `addressed | disputed | wont_fix`. `reason`: optional, ≤ 600 chars.
- The helper refuses refs that are closed or unknown.
- Provenance is injected as usual and marks the text as written by the student.

## Guard

No change. The guard already accepts `margi:` commits inside `margi/` from people as well as the
bot (fixing docs by hand is allowed), so a `respond` commit under the student's name passes as it
is. Who wrote an answer is recorded twice: as the commit author and as `provenance.author` in the
record. `git log -- margi/` shows who said what.

## Dashboard

- **Apparatus panel** opens on a progress line, e.g. *Since 3 Oct: 4 of 6 major comments
  resolved · 1 disputed · 1 open*.
- **Two lists:** *Open* (Open, Addressed, Disputed) shown by default, ordered by severity, then
  age, keeping the lemma `]` notation; *Closed* (Resolved, Withdrawn, Won't fix) collapsed, with a
  count.
- **Each comment** has a small-caps state line: `C17 · OPEN SINCE 3 OCT · passage changed`.
- **The student's voice is visibly theirs:** an indented "You, 5 Oct:" line with the reason, set
  apart from margi's text by a hairline rule. margi's verdict follows as
  "margi, 10 Oct: resolved (`ch02.typ:41–44`)". Red stays reserved for open major comments.
- **Selection:** each open comment has a checkbox. Once one is ticked, a sticky bar at the foot of
  the panel shows `/margi respond c17 c18` with the existing copy chip. On mobile the bar sits at
  the bottom of the viewport.
- **Sections table:** MAJ. counts open major comments across all grades, not only the latest.
- **Status line:** "N open major comments · M awaiting check".
- **Next steps:**
  - Addressed or Disputed comments in a section → `/margi grade 2.1`, "2 comments await checking".
  - Open major comments whose passage changed → the same suggestion, ranked lower.

## Ordering

Records are ordered by their timestamp, which has one-second resolution. Finalize and respond
stamp a new record at least one second after the newest existing one, so a respond and a grade
in the same second can't swap places.

## Ranges

- Typical section: 3–12 comments per grade, 1–4 grades.
- Worst case: about 40 comments in a section's history, 0–15 of them not closed.

## Wording changes

- README and PRODUCT.md: "`margi/` holds only what margi writes" becomes "…plus the student's
  answers to it, committed under their name".
- `skills/margi/commands/grade.md`: read the open comments of the section and its subsections,
  give a verdict on each, report verdicts first.

## Known gaps

- `read` comments and todos stay outside the lifecycle.
- A comment whose anchor spans two sections belongs to the section of its first line.
