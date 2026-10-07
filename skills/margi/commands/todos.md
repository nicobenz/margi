# /margi todos

Curate a todo list **with** the human. Nothing goes to GitHub without explicit acceptance.

## 1. Gather

- The latest records in `margi/feedback/` for grade, read, outline and challenge, and their open `major` comments.
- `margi/docs/open-questions.md` and `structure.md` (planned vs. written, via the latest outline record).
- Existing proposals in `margi/todos/proposed/` and synced todos in `margi/todos/synced/`.
- Open GitHub issues: `gh issue list --label margi --state open --json number,title,body`.
  If `gh` is unavailable, skip the GitHub parts and say so.

## 2. Propose todos

Write **one file per todo** to `margi/todos/proposed/<id>-<slug>.md`, where `<id>` is `t` plus
the date plus a counter, e.g. `t20261007-01`. Do not duplicate open issues or existing
proposals.

```markdown
---
id: t20261007-01
title: Engage with Moretti's critics in 2.1
status: proposed
section: "2.1"
labels: [margi, literature]
source: [<record file name>:<comment id>, ...]
---
What needs to happen and why, in task form (2–6 sentences). Name the evidence.
Never draft thesis text.
```

Keep todos actionable, specific and few: 3–8 per run, prioritised.

## 3. Check completion of open issues

For each open `margi`-labelled issue, look for evidence that it is done. Evidence can be the
current thesis text (quote file and lines), newer grade records without the problem, updated
docs, or outline changes. If you find evidence, write `margi/todos/close/<issue-number>.md`:

```markdown
---
issue: 12
title: <issue title>
status: proposed
---
Evidence: ... (file:lines, record names)
```

## 4. Review with the human

Show both lists compactly: new todos, then proposed closures. Ask the human for each item
(they may answer in bulk):

- **accept** → set `status: accepted` in the file
- **reject** → delete the file
- **change** → revise the file as instructed, then show it again

Repeat until every item is accepted or rejected. Never mark anything accepted on your own.

## 5. Sync and record

1. If anything is accepted, run `margi todos --sync-accepted`. It creates issues and closes
   issues through `gh`, then moves the files to `margi/todos/synced/`.
2. Write `margi/.staging/todos.json` with `command: todos`, `scope: review`, a `summary`, and
   `payload: {"accepted": [...ids], "rejected": [...ids], "closed": [...issue numbers]}`.
3. Run `margi finalize`.
