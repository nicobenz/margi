# /margi todos

Curate a todo list **with** the human. Nothing becomes a todo, and nothing is closed, without
explicit acceptance. Todos live in `margi/todos/`; GitHub issues mirror them only when
`github.sync` is `true` in `thesis.config.yml`.

`/margi todos done <id> [<id>…]` is different: the student marks todos done. Skip to
*Done by the student* below.

## 1. Gather

- The open comments: `uv run margi comments` (major and minor comments that aren't closed, with
  their numbers, e.g. `c17`).
- The latest records in `margi/feedback/` for read, outline and challenge.
- `margi/docs/open-questions.md` and `structure.md` (planned vs. written, via the latest outline record).
- Existing todos: `margi/todos/proposed/`, `margi/todos/open/` (and legacy `margi/todos/synced/`),
  and closure proposals in `margi/todos/close/`.
- With `github.sync: true` only: open GitHub issues,
  `gh issue list --label margi --state open --json number,title,body`. If `gh` is unavailable,
  skip the GitHub parts and say so.

## 2. Propose todos

Write **one file per todo** to `margi/todos/proposed/<id>-<slug>.md`, where `<id>` is `t` plus
the date plus a counter, e.g. `t20261007-01`. Do not duplicate open todos or existing proposals.

```markdown
---
id: t20261007-01
title: Engage with Moretti's critics in 2.1
status: proposed
section: "2.1"
comments: [c17, c18]
labels: [margi, literature]
---
What needs to happen and why, in task form (2–6 sentences). Name the evidence.
Never draft thesis text.
```

`comments` lists the comment numbers a todo comes from, if any. Keep todos actionable, specific
and few: 3–8 per run, prioritised.

## 3. Check completion of open todos

For each open todo, look for evidence that it is done: the current thesis text (quote file and
lines), newer grades that resolved its comments (the dashboard data marks a todo whose comments
are all closed), updated docs, or outline changes. If you find evidence, write
`margi/todos/close/<todo-id>.md`:

```markdown
---
todo: t20261007-01
title: <todo title>
status: proposed
---
Evidence: ... (file:lines, record names, comment numbers)
```

## 4. Review with the human

Ask about each item through the structured question tool, up to 4 items per call: new todos
first, then proposed closures. Question text: the title plus one line of why (or the
evidence, for closures). Options:

- **Accept** → set `status: accepted` in the file
- **Reject** → delete the file
- **Change** → revise the file as instructed (free-text/notes), then ask about it again

Repeat until every item is accepted or rejected. Never mark anything accepted on your own.

## 5. Apply and record

1. Run `uv run margi sync-todos`. It moves accepted proposals to `margi/todos/open/` and finishes
   the todos whose closure was accepted. With `github.sync: true` it also creates and closes
   issues through `gh`, and finishes todos whose issue was closed on GitHub.
2. Write `margi/.staging/todos.json` with `command: todos`, `scope: review`, a `summary`, and
   `payload: {"accepted": [...ids], "rejected": [...ids], "closed": [...todo ids]}`.
3. Run `uv run margi finalize`.

## Done by the student

`/margi todos done t20261007-01 t20261007-02`

1. Check the ids against `margi/todos/open/` (and legacy `synced/`). Refuse unknown ones in one line.
2. Ask through the question tool whether to add a note in their own words (answer via Other),
   with the options "No note" and "Skip for now".
3. Run `uv run margi todo-done <ids…> [--note "<their words>"]`. Pass the note **verbatim**:
   never edit, shorten, translate or paraphrase it. The helper commits under the student's name;
   don't run `margi finalize`.
4. Report in one line what was marked done.
