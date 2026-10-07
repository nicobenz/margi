# /margi grade <section>

Grade one section against the rubric **and** against the documented project goals.

## Inputs

1. `margi/docs/*.md`: research question, dataset, method, field, structure, constraints.
   If `margi finalize --check` warns that the docs are below the threshold:
   - **Headless** (the invocation ends in `--headless`): the `margi` CLI already applied the
     gate and the user chose `--force`. Grade, and say in `summary` which docs are missing.
   - **Interactive**: tell the user and recommend `/margi onboard` first. Grade only if
     they confirm, and say in `summary` that the result is low-confidence.
2. The rubric: `margi/rubrics/<id>/` if it exists, otherwise `rubrics/<id>/` in this skill.
   `<id>` is `rubric` in `thesis.config.yml`. Read `rubric.yml` and every category file.
3. The section text. Run `margi outline --no-save` to see section ids, then read the
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

Then run `margi finalize` and show the user a compact table of the scores plus the major
comments with their line numbers.
