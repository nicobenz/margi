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
2. The rubric: `margi/rubrics/<id>/` if it exists, otherwise `rubrics/<id>/` in this skill.
   `<id>` is `rubric` in `thesis.config.yml`. Read `rubric.yml` and every category file.
3. The section text. Run `uv run margi outline --no-save` to see section ids, then read the
   section's file(s) **with line numbers**. A section spans from its heading to the next
   heading of the same or higher level, possibly across `#include`d files.
4. Recent records for this section in `margi/feedback/*_grade_<section>*.json`, if any.
   Note what improved since then.

## Procedure

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
  "payload": {"section_title": "Prior Work", "previous_record": "<file name or null>"}
}
```

Then run `uv run margi finalize` and show the user a compact table of the scores plus the major
comments as one line each with a file:line link. Nothing else.
