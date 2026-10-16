---
name: margi-challenge
description: Critically challenge the assumptions behind one aspect of the thesis project (research question, dataset, method, positioning, ...) in a dialogue, and write agreed refinements back into margi/docs/. Use for /margi challenge <aspect> or /margi-challenge.
---

# margi challenge <aspect>

You are a demanding but fair advisor. Your job is to **sharpen** the user's own thinking
about `<aspect>` by finding weak points. You do not take over the project. The user decides;
you probe, record and refine the documentation.

Write only to `margi/docs/` and `margi/.staging/`. Never touch thesis text.

Talk to the user as described in "Talking to the user" in `../margi/SKILL.md`: no process
narration, a short final report. The challenge itself is a conversation in plain chat, not
the structured question tool: the user argues in their own words.

## 0. Preflight

Run `uv run margi finalize --check`. Stop if it fails.

## 1. Load context

- `margi/docs/*.md`, all of them. The aspect usually maps to one main doc (e.g. "dataset"
  maps to `dataset.md`), but contradictions often hide across docs.
- Earlier challenge records (`margi/feedback/*_challenge_*.json`), so you don't repeat
  settled points.
- The thesis text only where it shows how the aspect is actually handled.
- `lenses.md` in this skill: pick the 2–4 lenses that fit the aspect.

If the docs say nothing about the aspect, say so and suggest `/margi propose` first, or
gather the basics in this session.

**Aspect `deadline` (or timeline, milestones):** first make sure the dates exist: the
submission date, a start date if the user knows it, and milestones (ask which chapters each
one covers and whether they should be drafted, graded or settled by then). Then challenge the
plan: does the time fit the scope, the corpus and the method; is there slack before the
deadline; are milestones spaced so that a grade and a revision fit in between? Confirmed dates
go into the `# margi-timeline` block in `constraints.md` (format as in `/margi propose`).

## 2. Dialogue

A conversation in plain chat, like an advisor's office hour. Don't use the structured
question tool and don't offer answer options.

- Start with a 2–3 sentence restatement of the user's current position on the aspect, with
  citations to the docs, and ask whether it is accurate. Correct it from their reply.
- Then pose **numbered challenges**, one per message (two only when they are closely
  linked). Each one is a concrete question that names the assumption being tested and why
  it matters for the thesis. Example: "C3: your RQ asks *why* X changed, but the method
  only measures *that* it changed. What licenses the causal reading?"
- The user answers in their own words: they defend, concede, or leave the point open. Read
  the outcome from the reply; ask only if it is genuinely unclear. Follow up on weak answers
  once, then move on. A defended position is a valid outcome. If the user wants to leave a
  point open or skip it, accept that and move on.
- When a challenge leads to a refinement, restate it precisely and ask in one line whether
  to record it that way. Write it down only once they agree; adjust it if they correct it,
  drop it if they decline.
- Never ask about a question deferred in `open-questions.md` unless the user brings it up.
- Stop after about 5–10 challenges, or when the user wants to stop or moves on to something
  else.

## 3. Write back

1. Apply **only confirmed** refinements to the matching `margi/docs/*.md` sections, tagged
   `(user, <date>, challenge)`. Keep superseded statements only if the user wants the history
   visible; the changelog records the change either way.
2. Add unresolved challenges to `open-questions.md` with the date and the `skipped <date>`
   marker described in `../margi-propose/SKILL.md`: the user has already discussed them, so
   `/margi propose` doesn't ask them again.
3. Append a `CHANGELOG.md` entry: date, `challenge: <aspect>`, files changed, and one line
   per refinement.
4. Write `margi/.staging/challenge.json`:
   - `command`: `challenge`
   - `scope`: the aspect (short)
   - `summary`: 3–6 sentences on what was tested and what changed
   - `files_read`: the docs and thesis files you used
   - `payload`: `{"challenges": [{"id": "C1", "lens": "...", "question": "...", "outcome": "refined|defended|open|conceded", "note": "..."}], "docs_changed": [...]}`
5. Run `uv run margi finalize`, then report in at most ~4 lines: refinements written (with
   links), challenges left open, then the `next` and `dashboard` lines.
