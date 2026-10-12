# Whole-thesis grade (design draft)

Status: confirmed brief, 2026-10-12. Not implemented. Command: `/margi grade thesis`.

`/margi grade` judges one section at a time. Examiners judge the thesis as a whole, and its most
common failures only show across chapters: the introduction promises what the conclusion never
delivers, the research question is not answered, the abstract describes a different thesis, a
concept shifts meaning between chapters. No section grade can see these. This draft adds a grade
of the whole thesis on its own lenses, with comments that can point at two passages at once.

Goal: the student can name the one or two places where the argument breaks between chapters, see
both passages of each break, and answer it with `/margi respond` like any other comment. It is
useful mid-thesis as a red-thread check, not only before submission. The advisor sees the same
records in `export.html`.

## The command

`/margi grade thesis` reuses the grade command with the reserved scope `thesis`. There is no new
verb. Section ids are numbers, so `thesis` cannot collide with one.

The procedure is the grade procedure (judge earlier comments first, then score, then comment),
with the thesis lenses instead of the rubric categories. "Never propose wording" holds with extra
force: a comment says *the conclusion leaves sub-question 2 unanswered*, never what to write.

## The lenses

A separate set, on the same 1–5 scale and the same `scale.anchors` as the section rubric. They do
not repeat the section categories: a lens is only about what is visible across sections.

| Lens | Judges | Needs |
|---|---|---|
| `question` | the conclusion answers the research question in `research-question.md`, including its sub-questions | conclusion |
| `promise` | what the introduction announces (aims, contributions, chapter overview) is delivered | introduction, conclusion |
| `method-results` | the analysis does what the method chapter says it will, with the data `dataset.md` names | method, results |
| `terms` | key concepts are defined once and used in the same sense throughout | two or more drafted sections |
| `thread` | each chapter's role in the argument is clear and it builds on the ones before | two or more drafted chapters |
| `abstract` | the abstract matches what the thesis does and finds | abstract, conclusion |

They live in the bundled rubric as `skills/margi/rubrics/default/thesis.yml` plus one file per
lens, with descriptors written like the category files.

## Readiness, per lens

The grade runs at any time on whatever exists. Each lens is judged only when every section it
needs passes the existing precheck (`grade.precheck` applies per lens as it does per section:
`strict` skips, `ask` asks once for all unready lenses, `none` judges anyway). A lens that is not
judged is recorded as not judgeable, naming what it needs:

```json
"lenses_pending": {"abstract": {"needs": ["abstract"], "reason": "no abstract section"},
                   "promise": {"needs": ["6"], "reason": "6 Conclusion is not drafted"}}
```

If no lens can be judged, the record is a not-ready record, as for sections.

## Section roles

Lenses need to know which section is the introduction, the method, the results, the conclusion and
the abstract. `structure.md`'s outline gets an optional `role` per entry:

```yaml
# margi-structure
- title: Abstract
  role: abstract
- title: Introduction
  role: introduction
  target: 10%
- title: Method
  role: method
```

Roles: `abstract`, `introduction`, `method`, `results`, `conclusion`. `/margi propose` fills them
from the plan and cites the source like every other doc; the student corrects them through
`/margi challenge structure` or by telling `propose`. Without a role, the grade does not guess
from headings: the lens is pending with the reason *no section has the role "conclusion"*, and
`help` suggests adding it.

## Paired anchors

A cross-chapter problem has two places. A comment may carry up to two anchors, each with a role
label from a fixed set:

```json
{"id": "c1", "category": "promise", "severity": "major",
 "body": "The introduction announces a comparison with the 1850s corpus; the conclusion never returns to it.",
 "anchors": [
   {"role": "promised", "file": "chapters/01-intro.typ", "line_start": 14, "line_end": 15, "quote": "…"},
   {"role": "not-delivered", "file": "chapters/06-conclusion.typ", "line_start": 3, "line_end": 9, "quote": "…"}
 ]}
```

- Labels: `promised` / `not-delivered`, `defined` / `used-differently`, `announced` / `done`,
  `claimed` / `contradicted`. A pair uses two labels of one row.
- `anchor` (one) stays valid; `anchors` (two) is the new form. A comment has one or the other.
- Something missing still goes without a quote: one anchor where it was promised, and the body
  names where it should be.
- `finalize` checks both quotes against `HEAD` and sets `anchor_status` on each. The comment's
  passage signal (*unchanged / moved / changed*) is the worse of the two.
- Paired anchors are allowed only in thesis grades. Section grades keep one anchor.

## Comments and their lifecycle

- Thesis comments continue margi's global numbering (`c41`, `c42`, …), so `/margi respond` works
  unchanged.
- **Scope must not clash.** `lifecycle.covers("all", …)` matches every comment today
  (`src/margi/lifecycle.py:143`). `thesis` is its own scope: a thesis grade judges only comments
  from thesis grades, and a section grade never judges them, even when one of the anchors lies in
  that section. `uv run margi comments thesis` lists them.
- 0–12 comments per grade. Most are `major`, because a lens only catches structural problems.
  `note` marks a thread that holds and should be kept.

## The dashboard

The thesis row is the first row of the section list, above 1, 2, 3…. It keeps the section rows'
height and rhythm; it is the whole above its parts, not a banner.

- **Row:** "Whole thesis", the lens scores where sections show category scores, and per pending
  lens a quiet *not yet* with what it needs (*needs 6 Conclusion drafted*).
- **Never graded:** "not graded yet" and the copyable `/margi grade thesis`.
- **Changed since grading:** when any section's file changed since the graded thesis commit. There
  is no text diff, which is per section.
- **Low confidence:** as for sections.
- **Panel:** the section panel's structure: lens scores with their rationale, comments with
  verdicts and answers, the respond picker, history.
- **Paired quotes:** the two passages read as one finding, joined, each with its label and its own
  link: *promised · 1.2 l.14* and *not delivered · 6.1 l.3*. At phone width they stack and keep
  their labels.
- **History:** one line per lens. A lens that was pending in a grade leaves a gap, never a zero.

## Next steps and help

- Suggest `/margi grade thesis` once two or more chapters are graded and the thesis has never been
  graded, or when sections changed since the last thesis grade.
- Suggest adding roles when a lens is pending only for a missing role.
- `/margi help` lists the command with the grade commands.

## Out of scope

- An overall score or average across lenses. Each lens stands alone.
- Judging section-level problems again (argument within a chapter, citation form, style).
- Custom lenses; they follow whatever custom rubrics become.
