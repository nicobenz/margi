# Introducing the dashboard (design draft)

Status: implemented (`margi init`, `dashboard._setup`, the dashboard's Getting started panel).

After `uvx margi init` the dashboard is never mentioned, and its first screen reads as a list of
shortfalls ("Docs 0%", "low-confidence", rows of "no text yet"). This draft makes `init` open the
dashboard, gives the page a setup checklist for the first visits, and has margi point at the page
until setup is done.

Goal: the student finds the page and sees it as their guide to setting up margi, not as a report
card. Once setup is done the checklist disappears and the page is the normal dashboard.

## The terminal (`margi init`)

Closing message:

```
margi is ready.

  Dashboard  file:///…/margi/dash.html   (opened in your browser)
  Versions   saves stay on this computer until you add a remote repository
  Next       write your plan into PROPOSAL.md, then run /margi propose in Claude Code
```

- `init` opens `margi/dash.html` with Python's `webbrowser`, only when stdout is an interactive
  terminal, `CI` is not set and `--no-open` is not given. If no browser opens (a remote session),
  the line says "(open it in a browser)".
- Re-running `init` (updates, a settings change) never opens the browser again; the link is still
  printed.

## The checklist (on the page)

Six steps, each judged from the data, never by the agent:

| # | Step | Done when | Command |
|---|---|---|---|
| 1 | Write your plan | `PROPOSAL.md` at HEAD differs from the template | — (edit; `/margi propose` offers to save it) |
| 2 | Turn it into project docs | a `propose` record exists | `/margi propose` |
| 3 | Docs complete enough to grade | completeness ≥ the threshold | `/margi propose`, or `/margi challenge <aspect>` |
| 4 | Set the submission date | the timeline has a deadline | `/margi challenge deadline` |
| 5 | Take a length snapshot | an outline record exists | `/margi outline` |
| 6 | Grade a first section | any real grade | `/margi grade <first section with text>` |

- Where: it replaces "Nothing graded yet" in the Sections view's panel when no section is
  selected, and the static three-step list on the empty-project screen.
- Look: an ordered list in the apparatus style. Done steps get a drawn tick, their date (where a
  record gives one) and second-ink text. The first open step is in ink with its command chip;
  later open steps are faded, without chips. Heading: "Getting started · 2 of 6".
- When all six are done, it disappears for good. A later regression (docs dropping below the
  threshold) is the next-step list's job.
- During setup the status line's "Docs 0% (grades are low-confidence until 70%)" becomes the
  neutral "Docs 0% · needed for grading: 70%". Nothing is red before anything is graded.

## Later runs

While setup is incomplete, `margi finalize` prints one more line:
`dashboard  margi/dash.html  (setup 3 of 6)`. The skill tells the agent to end its report with
that line whenever finalize prints it. When setup is done the line stops.

## Decided while building

- Under 1080px the checklist moves above the section table, so a phone's first screen is the list,
  not rows of "no text yet".
- During setup the timeline strip's "No submission date documented" stays hidden; step 4 asks for
  it.
- Whether to open the browser is one small function (`should_open_dashboard`) so it can be tested.

## Constraints

- The page reads only `data.js`; no wall clock, no browser storage. The checklist data
  (`setup`: steps with done flags, dates and commands) is built in `dashboard.collect()`.
- DESIGN.md holds: red only for attention, no green ticks, no KPI boxes, every command copyable.
- Out of scope: a tour or modal, remembering dismissed steps, changing what `init` scaffolds.
