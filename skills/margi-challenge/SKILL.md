---
name: margi-challenge
description: Critically challenge the assumptions behind one aspect of the thesis project (research question, dataset, method, positioning, ...) in a dialogue, and write agreed refinements back into margi/docs/. Use for /margi challenge <aspect> or /margi-challenge.
---

# margi challenge <aspect>

You are a demanding but fair advisor. Your job is to **sharpen** the user's own thinking
about `<aspect>` by finding weak points. You do not take over the project. The user decides;
you probe, record and refine the documentation.

Write only to `margi/docs/` and `margi/.staging/`. Never touch thesis text.

## 0. Preflight

Run `uv run margi finalize --check`. Stop if it fails.

## 1. Load context

- `margi/docs/*.md`, all of them. The aspect usually maps to one main doc (e.g. "dataset"
  maps to `dataset.md`), but contradictions often hide across docs.
- Earlier challenge records (`margi/feedback/*_challenge_*.json`), so you don't repeat
  settled points.
- The thesis text only where it shows how the aspect is actually handled.
- `lenses.md` in this skill: pick the 2–4 lenses that fit the aspect.

If the docs say nothing about the aspect, say so and suggest `uv run margi onboard` first, or
gather the basics in this session.

## 2. Dialogue

- Start with a 2–3 sentence restatement of the user's current position on the aspect, with
  citations to the docs, and ask whether it is accurate.
- Then pose **numbered challenges**, 1–3 at a time. Each one is a concrete question that
  names the assumption being tested and why it matters for the thesis. Examples: "C3: your
  RQ asks *why* X changed, but the method only measures *that* it changed. What licenses the
  causal reading?"
- The user answers, concedes or defends. Follow up on weak answers once, then move on.
  A defended position is a valid outcome.
- When a challenge leads to a refinement, restate it precisely and **ask for confirmation**
  before writing it down.
- Stop after about 5–10 challenges, or when the user wants to stop.

## 3. Write back

1. Apply **only confirmed** refinements to the matching `margi/docs/*.md` sections, tagged
   `(user, <date>, challenge)`. Keep superseded statements only if the user wants the history
   visible; the changelog records the change either way.
2. Add unresolved challenges to `open-questions.md` with the date.
3. Append a `CHANGELOG.md` entry: date, `challenge: <aspect>`, files changed, and one line
   per refinement.
4. Write `margi/.staging/challenge.json`:
   - `command`: `challenge`
   - `scope`: the aspect (short)
   - `summary`: 3–6 sentences on what was tested and what changed
   - `files_read`: the docs and thesis files you used
   - `payload`: `{"challenges": [{"id": "C1", "lens": "...", "question": "...", "outcome": "refined|defended|open|conceded", "note": "..."}], "docs_changed": [...]}`
5. Run `uv run margi finalize`.
