# Timeline and deadline (design draft)

Status: draft, not implemented.

The dashboard has no sense of time beyond one section's score history. This draft adds a
submission date, milestones and a timeline: a slim strip on every view and a Timeline tab. It
shows only what margi can show from its own records and git. It makes no predictions.

Goal: on every visit the student sees how much time is left, what the next milestone is, and
whether one was missed. The Timeline tab shows what happened when (grades, writing, answers to
comments), set against the plan. The advisor sees the same in `export.html`.

## Where the dates live

A fenced YAML block in `margi/docs/constraints.md`, the same pattern `structure.md` uses for its
outline:

```yaml
# margi-timeline
start: 2026-09-01          # optional; else the first thesis commit
deadline: 2027-03-31
length: 180000             # optional goal, in the unit set by `count` in thesis.config.yml
milestones:
  - {date: 2026-12-01, sections: ["2"], state: drafted, label: Prior work drafted}
  - {date: 2027-01-15, sections: ["2", "3"], state: graded}
  - {date: 2027-02-01, label: Advisor meeting}     # no sections: a plain tick, never judged
```

- `/margi propose` and `/margi challenge` write it from what the student says, citing the source
  like every other doc. The prose section "Deadline and milestones" stays as it is.
- A malformed block shows a warning on the page, like the existing section-list warning.

## Milestone states

Judged from records, never by the agent:

| State | Met when | Date counted as met |
|---|---|---|
| `drafted` | the section passes the readiness check | the first grade whose stored check says ready |
| `graded` | the section has a real grade (not "not ready") | that grade's date |
| `settled` | graded, and no open major comments | the date of the record that closed the last one |

A milestone with several sections is met when all of them are; its date is the latest of theirs.

Each milestone shows as **met** (on time or late), **missed**, **due soon** (14 days or less) or
**upcoming**. A milestone without sections is a plain date and is never judged.

## No wall clock in the data

The data file stays deterministic: an unchanged project produces an unchanged file. The data
carries dates and met-dates only. The browser computes "today", days left, "due soon" and
"missed". Next-step rules, which are computed in Python, use the date of the latest thesis commit
instead of today.

## The strip (every view, under the status line)

- One full-width hairline axis from start to deadline:
  - the elapsed part in ink, the rest as hairline;
  - "Today" as a 1px ink rule with its label: "Today · 171 days left";
  - milestone ticks above the axis: missed in red, met in ink, upcoming in faded ink;
  - the deadline at the right end: "Submission 31 Mar 2027".
- It is a time axis in thin rules, not a progress bar or a KPI.
- Narrow screens: one line, "171 days left · next: Prior work drafted, 1 Dec".
- No deadline yet: "No submission date documented" with `/margi challenge deadline` to copy.
  Once the docs are complete, this is also a next step.
- Deadline passed: "Submission was 31 Mar", and the axis extends to today.

## The Timeline tab

One shared time axis, from start to the later of deadline and today, with today and the deadline
as vertical rules through every row:

- **Length:** outline snapshot totals as a line, plus the current length. A dashed horizontal line
  at the goal if one is documented. No projection.
- **One row per section, in thesis order:** grades as dots (low-confidence ones marked as such in
  the tooltip), "not ready" checks as open circles, answers to comments as small marks below, and
  that section's milestones as flags.
- **Commits:** faint ticks along the bottom, one per day with commits, showing the writing rhythm.
- **Milestone table** below the chart: date, milestone, sections, state ("met 28 Nov", "missed",
  "due in 12 days").

Interaction: hover shows tooltips like the existing score charts. Clicking a grade dot or a
section name opens that section in the Sections tab. On narrow screens the chart keeps its width
and scrolls sideways inside its frame, like the page images in Literature; the milestone table
stays readable.

## Ranges and empty states

- Typical thesis: 3–9 months, 5–30 sections, 0–8 milestones, 0–40 grades, 50–500 commits.
- No records: only the axis, with today.
- No outline snapshots: the length row says how to get one (`/margi outline`).
- Very long section lists: sections at level 3 and below fold into their parent row.

## Next steps

- No deadline documented, docs above the threshold → `/margi challenge deadline`.
- An unmet `graded` or `settled` milestone due within 14 days of the latest thesis commit →
  `/margi grade <section>`.
- `drafted` milestones suggest nothing: writing is the student's job.

## Constraints

- The page stays static; the data is built in `dashboard.collect()`. `export.html` includes the
  timeline.
- DESIGN.md holds: Libertinus type, red only for missed milestones and a passed deadline, no
  green, no new shadows, tabular figures. The visual language extends the score history charts.

## Open

- Whether the strip appears in print.
- The "due soon" window: 14 days unless decided otherwise.
