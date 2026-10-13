# margi/

Everything in this directory is written by [margi](https://github.com/nicobenz/margi), the
AI feedback layer for this thesis. **No thesis text is ever written here or by margi.**

| Path | Content |
|---|---|
| `dash.html` | The dashboard. Open it in a browser: section scores, comments, history and the next margi command. Refreshed by every margi run. |
| `dash/` | The dashboard's data (`data.js`), generated from the folders below. `margi export` writes a self-contained `export.html` here (not committed). |
| `docs/` | Project documentation (research question, dataset, method, …) from `/margi propose` / `/margi challenge`. Every statement cites its source or the date the user said it. |
| `feedback/` | Append-only JSON records. Provenance (HEAD SHA, file hashes, rubric version, model, timestamp) is injected by scripts, never by the AI. |
| `todos/` | Proposed todos and issue closures awaiting human review, and those synced to GitHub. |

Audit trail: `git log -- margi/` shows every AI contribution. Commits outside `margi/` are
human-only; this is enforced by `.githooks/commit-msg` and the `margi guard` CI workflow.
