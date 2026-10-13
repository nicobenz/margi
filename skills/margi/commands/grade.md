# /margi grade <section>

Grade one section against the rubric **and** against the documented project goals.

## Readiness first

A grade only helps once the section is running prose. Think of a peer asked to review bullet
points, to-dos or lorem ipsum: they would say "write it first". Before anything else, run
`uv run margi precheck <section>`. It reports whether the section is ready and why not (too little
running prose, mostly list items, placeholder text), and prints `grade.precheck`:

- **strict**: if it is not ready, do not grade. Record it as not ready (draft below) and tell the
  user in one line why, in margi's terms. Don't suggest what to write.
- **ask**: if it is not ready, say why in one line and ask through the question tool: "Grade
  anyway" or "Not yet". Grade anyway → grade normally and set `"readiness": {"decision":
  "override"}`. Not yet → record it as not ready.
- **none**: grade normally; the check is still stored with the grade.

Even when the precheck says ready, you may judge that the text is not yet a draft (notes to
self, loose quotes, an outline in sentences). Then treat it as not ready under strict and ask
(asking first under ask), with your reasons in `readiness.reasons`.

A not-ready record has no scores and no comments:

```json
{"command": "grade", "scope": "2.1", "summary": "Not ready to grade yet.",
 "readiness": {"decision": "not_ready", "reasons": ["mostly bullet points"]}}
```

Reasons are short and in margi's own words; they never propose text.

## Inputs

1. `margi/docs/*.md`: research question, dataset, method, field, structure, constraints.
   If `uv run margi finalize --check` warns that the docs are below the threshold, ask
   through the question tool whether to run `/margi propose` first or grade anyway. Grade
   only if they choose to, and say in
   `summary` that the result is low-confidence and which docs are missing.
2. The rubric: `rubrics/default/` in this skill. Read `rubric.yml` and every category file.
3. The section text. Run `uv run margi outline --no-save` to see section ids, then read the
   section's file(s) **with line numbers**. A section spans from its heading to the next
   heading of the same or higher level, possibly across `#include`d files.
4. Recent records for this section in `margi/feedback/*_grade_<section>*.json`, if any.
   Note what improved since then.
5. The earlier comments you must judge: `uv run margi comments <section>`. It lists every major
   and minor comment in this section and its subsections that isn't closed, with its number
   (`c17`), state (open, addressed, disputed), the quoted passage, whether that passage is
   still in the text (*passage unchanged / moved / changed*), and the student's answers.

## Procedure

0. **Judge the earlier comments first.** For each comment from `uv run margi comments
   <section>`, read the passage where it is now and decide:
   - `resolved`: the problem is gone. The reason names the evidence: file and lines.
   - `open`: the problem is still there. The reason says why, in one or two sentences.
     A changed passage alone doesn't resolve a comment; a disputed comment you don't accept
     stays `open`, and the reason answers the student's argument.
   - `withdrawn`: only for a *disputed* comment whose dispute you accept. The reason says why.
   Take the student's reason seriously; it is their thesis. Never propose text in a reason.
   Don't repeat a comment that stays open as a new comment: it keeps its number.

1. For each rubric category, decide a score on the rubric's scale using its descriptors.
   Always judge against what the docs say this thesis is trying to do (its research question,
   method and audience), not against a generic ideal.
2. Write 1–3 sentences of rationale per category, referencing comment ids.
3. Write anchored comments: 3–12 in total. Prioritise `major` problems such as the argument,
   evidence, alignment with the research question, or method transparency over `minor` ones
   (clarity, terminology, citation form). Use `note` for strengths worth keeping.
4. Every comment must point to a concrete passage (anchor with a verbatim quote) unless it is
   about something missing. Missing things go without an anchor and say where the gap is.
5. **Never propose wording.** Say "this claim needs a source" or "the transition hides a
   jump from X to Y". Do not say "replace with: …".

## Draft

`margi/.staging/grade.json`:

```json
{
  "command": "grade",
  "scope": "2.1",
  "summary": "...",
  "files_read": ["chapters/02-prior-work.typ", "margi/docs/research-question.md", "..."],
  "scores": {
    "argument": {"score": 3, "max": 5, "rationale": "...", "comment_ids": ["c1", "c4"]}
  },
  "comments": [
    {"id": "c1", "category": "argument", "severity": "major",
     "body": "...", "anchor": {"file": "chapters/02-prior-work.typ", "line_start": 41,
     "line_end": 43, "quote": "verbatim text from those lines"}}
  ],
  "verdicts": [
    {"ref": "c12", "verdict": "resolved", "reason": "The claim now cites Underwood 2019 (chapters/02-prior-work.typ:41-44)."},
    {"ref": "c13", "verdict": "open", "reason": "The jump from corpus to genre is still unexplained."}
  ],
  "payload": {"section_title": "Prior Work", "previous_record": "<file name or null>"}
}
```

`verdicts` holds exactly one entry for every comment `uv run margi comments <section>` lists, and
nothing else; finalize refuses the draft otherwise. Leave it out when the list is empty, and in a
not-ready record (those judge nothing). Never give the new comments a `ref`: finalize numbers them.

Then run `uv run margi finalize` and report, in this order:

1. The verdicts in one line, if there were any: `Since 3 Oct: c12, c14 resolved · c13 still open ·
   your dispute of c15 accepted`.
2. A compact table of the scores.
3. The new major comments as one line each with their number and a file:line link.
4. **Only on the first grade of this section** (no earlier record in step 4 of Inputs): one line
   that puts the scores in the rubric's own terms, quoting the anchor of the median score from
   `scale.anchors` in `rubric.yml`, e.g. `First grade. A 3 is "adequate: meets expectations with clear room to
   improve"; the next grade shows what changed.` Plain and factual: no praise, no consolation.
5. The `next` and `dashboard` lines from finalize (see "Talking to the user").

Nothing else.
