# Todos without GitHub (design draft)

Status: implemented (`src/margi/todos_sync.py`, `/margi todos`, the dashboard's Todos tab).

Accepted todos used to go to GitHub issues and nowhere else. Without `gh` they stayed "not on
GitHub yet" for good, nothing could be marked done, and a todo lost its link to the comment it came
from. Todos now live inside margi; GitHub is an optional mirror.

## Where todos live

`thesis.config.yml`: `github: {sync: false, label: margi}`. New projects start with `sync: false`.
A project without the key that already has files in `margi/todos/synced/` counts as `sync: true`,
so nobody loses their GitHub sync silently.

| Folder | State |
|---|---|
| `margi/todos/proposed/` | margi's suggestions waiting for review (`status: proposed`, or `accepted` until applied) |
| `margi/todos/open/` | accepted |
| `margi/todos/done/` | finished |
| `margi/todos/close/` | margi's proposals to close an open todo, with evidence |
| `margi/todos/synced/` | legacy: read as open (or done for `closed-*.md`) |

Front matter adds `comments: [c17, c18]` (source comments by number), `section`, `issue` (only when
synced), and on done: `done_at`, `done_by` (`student`, `margi` for an accepted closure, `github`
for an issue closed there) and an optional `note` in the student's own words.

## How a todo gets done

- By the student: `/margi todos done t20261007-01 [t…]`. The agent passes the ids, and a note word
  for word, to `uv run margi todo-done`, which moves the files to `done/` and commits under the
  student's name (`margi: todo done t…`). With sync on it also closes the issue through `gh`.
- By margi, with consent: `/margi todos` looks for evidence that open todos are finished and writes
  `close/<todo-id>.md`. Accepted closures move the todo to `done/` with the evidence.
- With sync on, `uv run margi sync-todos` (run by `/margi todos`) also reads issue states back: a
  todo whose issue was closed on GitHub moves to `done/`. Only during a margi run, never during a
  page refresh, which stays offline and deterministic.

## The link to comments

A todo shows its source comments with their states ("from c17 resolved, c18 open"); a comment shows
"→ todo …". When all of a todo's comments are closed (resolved, withdrawn, won't fix) the todo is
marked "its comments are closed", a next step suggests `/margi todos`, and the next run proposes
closing it. Nothing closes on its own.

## Dashboard

The Todos tab has three groups: Open (title, section, source comments, `#12` when synced, an
"Done" checkbox that builds `/margi todos done t1 t2` in a sticky bar), Waiting for your review
(proposals and closure proposals, with `/margi todos`), and Done (collapsed, with date and who
closed it). The "not on GitHub yet" next step applies only with sync on.

## Non-goals

Due dates on todos (milestones cover deadlines), priorities beyond the order, two-way editing of
issue text. Todo bodies stay task descriptions, never thesis prose.
