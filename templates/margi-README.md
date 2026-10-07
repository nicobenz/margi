# margi/

Everything in this directory is written by [margi](https://github.com/nicobenz/margi), the
AI feedback layer for this thesis. **No thesis text is ever written here or by margi.**

| Path | Content |
|---|---|
| `docs/` | Project documentation (research question, dataset, method, …) from `margi onboard` / `margi challenge`. Every statement cites its source or the interview date. |
| `feedback/` | Append-only JSON records. Provenance (HEAD SHA, file hashes, rubric version, model, timestamp) is injected by scripts, never by the AI. |
| `todos/` | Proposed todos and issue closures awaiting human review, and those synced to GitHub. |

Audit trail: `git log -- margi/` shows every AI contribution. Commits outside `margi/` are
human-only; this is enforced by `.githooks/commit-msg` and the `margi guard` CI workflow.
