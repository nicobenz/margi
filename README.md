# margi

**AI in the margins, never in the text.**

margi is a feedback layer for a thesis that you write 100% by hand. You use it from
[Claude Code](https://claude.com/claude-code) with `/margi` commands. The agent reads your thesis
and writes documentation, grades, literature ratings and todos, but **only inside `margi/`**, and
always in commits that are kept separate from yours. A git hook (and, on GitHub, CI) enforces
this. You don't have to take it on trust, and you don't need to know git: margi keeps the
versions for you.

## Install

```sh
mkdir my-thesis && cd my-thesis && uvx margi init
```

This is the only setup command you run in the terminal. It needs git; if git is missing, `init`
says so and offers to install it (macOS, Windows) or prints the command for your system. It
creates the git repository if there is none and asks for the name your saved versions are
recorded under (Enter keeps "User"; see [Saving your work](#saving-your-work)). In an empty folder it bootstraps a Typst
thesis: `main.typ` with a chapter skeleton in `chapters/`, an empty `refs.bib`, `lit/` for
PDFs, and `PROPOSAL.md`. In an existing Typst project it only adds what is missing
(`PROPOSAL.md` and margi itself) and leaves your files alone. The literature folder gets its own
`.gitignore`: papers stay on your machine and never go into the repository.

At the end, `init` opens the dashboard (`margi/dash.html`) in your browser; pass `--no-open` to
skip that. Until setup is done, the dashboard shows a *Getting started* checklist that ticks
itself off from margi's records: plan saved, project docs, docs complete enough to grade,
submission date, first length snapshot, first grade. Each open step comes with the command to
copy, and margi's reports in Claude Code end with a link to the dashboard until the list is done.

Then:

1. Write your plan into `PROPOSAL.md`: title ideas, research question, data, method, outline,
   constraints. Fragments and loose thoughts are fine.
2. Open Claude Code in the repository and run `/margi propose`. margi first offers to save your
   plan as a version (you approve it), then turns the proposal into structured docs in
   `margi/docs/` and lists what is still unclear in `margi/docs/open-questions.md`.
3. Add to `PROPOSAL.md` and run `/margi propose` again until the docs are complete enough.

margi is installed **per thesis repository**, not globally. `margi init` adds it as a dev
dependency to the repo's `pyproject.toml` (creating a bare one if needed) and locks it in
`uv.lock`, so you, your agent, the commit hook and CI all run the same pinned version from
`.venv/`. Run commands with `uv run margi …` (or activate `.venv`). After cloning on another
machine, run `uv sync` once.

`margi init` also installs the skills (vendored to `.agents/skills/`, symlinked from
`.claude/skills/`) and Claude Code's permissions in `.claude/settings.json`. Finally it writes
`thesis.config.yml` and a `.gitignore`, installs the commit guard (plus a CI workflow when the
repository has a GitHub remote), and creates `margi/`.

margi supports **Claude Code** only for now. Other agents that read `SKILL.md` may run the
commands, but they are untested and the `protect_thesis` permissions and the question before
each save don't apply to them; the commit guard and CI do.

## Commands

All commands run inside Claude Code.

| Command | |
|---|---|
| `/margi propose [--from expose.md]` | Reads your `PROPOSAL.md` (or another file) and documents the research question, dataset, method, field, structure and constraints in `margi/docs/`, with gaps listed in `open-questions.md`. Every other command grades against these docs. |
| `/margi challenge <aspect>` | A devil's-advocate dialogue about any aspect of the project. The refinements you confirm are written back into `margi/docs/`. |
| `/margi grade <section>` | Rubric-based scores per category with comments anchored to file, lines and a verbatim quote. A section that isn't running prose yet (too few words, mostly bullet points, lorem ipsum) is recorded as *not ready to grade* instead of getting scores; `grade.precheck` in `thesis.config.yml` sets whether you can grade it anyway (`ask`, default), never (`strict`) or without the check (`none`). If the docs are incomplete, it asks before grading and marks the result low-confidence. |
| `/margi respond <c17 …>` | Your answer to grade comments: *addressed*, *disputed* or *won't fix*, with an optional reason in your own words. margi records it word for word and commits it under your name. The next `/margi grade` of that section checks every comment that isn't closed and marks it resolved, still open, or (for a dispute it accepts) withdrawn. *Won't fix* closes a comment for good. |
| `/margi outline` | Character counts and their distribution across sections and subsections, compared against targets from `structure.md`. No AI involved. |
| `/margi read [pdf…]` | Rates literature PDFs for relevance to your research question and outline. |
| `/margi todos` | Proposes todos from your open comments and other feedback, and proposes closing todos that look done. You accept, reject or change each one. Accepted todos live in `margi/todos/`; set `github.sync: true` in `thesis.config.yml` to mirror them to GitHub issues. `/margi todos done <id>` marks todos you finished, with an optional note in your own words. |
| `/margi submit-check` | Before submission: checks every direct quotation against its PDF (word for word, showing what differs), the bibliography against your citations and PDFs, the length against your goal, and what is still open. No AI involved; results on the dashboard's Submission tab. |
| `/margi ai-report` | A factual appendix on how margi was used (`margi/ai-use.md`, printable `margi/dash/ai-use.html`): every run and what it produced, and the guard's check of your whole git history. Your declaration and AI statement stay yours to write. |
| `/margi defend [chapter]` | A mock defense: examiner questions over the finished thesis, one at a time. You answer; margi only asks and records which questions to prepare. |
| `/margi status` | Shows docs completeness, latest grades, outline, todos and recent runs. |

`/margi-propose` and `/margi-challenge <aspect>` work as shortcuts too.

## Dashboard

Open `margi/dash.html` in a browser. It shows every section in thesis order with its latest
rubric scores, what changed since it was graded, the anchored comments, how scores developed
over time, project docs, literature, todos and the run log. Each section's comments stay open across grades
until they are closed: the panel opens with how many were resolved since the first grade, shows
your answers and margi's verdicts under each comment, and builds the `/margi respond …` command
from the comments you tick. The header names the thesis commit the page reflects; after you
commit, `/margi status` refreshes it.

Under the status line, a strip shows the days left until submission, the next milestone and any
milestone that was missed. The Timeline tab sets your writing (length snapshots and commits),
grades and answers against the plan, with a table of every milestone and its state. Dates come
from `margi/docs/constraints.md`: tell `/margi propose` or `/margi challenge deadline` your
submission date and milestones such as "chapter 2 drafted by 1 Dec", and margi checks those
against its records (drafted, graded, or settled with no open major comments). The header always shows the next
margi command to run, with a copy button.

In the Literature view, select a paper to see its key passages where they sit in the PDF: the
paper's own section (from the PDF's bookmarks), an image of that part of the page with the quoted
lines highlighted, and a link that opens the PDF at that page. margi finds every quote in the PDF
itself, so a quote that isn't in the paper shows as *passage not found* instead of pointing
somewhere wrong. The page images are rendered into `margi/.cache/` and are never committed;
`margi export` includes them. Those suggestions come from rule-based checks (docs
below the threshold, sections changed since grading, ungraded sections, unrated PDFs, …)
and from your agent, which can add steps based on what you asked for in the session.

The page itself never changes; every margi run only rewrites its data file,
`margi/dash/data.js`, and commits it with the run. To share a snapshot, run

```sh
uv run margi export          # writes margi/dash/export.html, one self-contained offline file
```
 In the background,
the skills call a few hidden `uv run margi …` helpers (`finalize`, `outline`, `status`,
`comments`, `respond`, `extract-pdfs`, `sync-todos`); you never need to run them yourself.

## How the separation works

```
your commits   → everything except margi/      (never prefixed "margi:")
margi commits  → only margi/                   ("margi: grade 2.1", author margi-bot)
```

- **`margi finalize`** runs at the end of every AI command.
  - It aborts if anything outside `margi/` changed.
  - It validates the agent's draft against `skills/margi/schema/feedback.schema.json`.
  - It checks every quoted anchor against `HEAD`.
  - It **injects the provenance itself**: HEAD SHA, file hashes, rubric version and hash,
    docs completeness, model, timestamp.
  - It commits only `margi/`, as the bot.
- **`.githooks/commit-msg`** (`margi guard --staged`) rejects mixed commits, `margi:`
  commits outside `margi/`, unprefixed commits inside it, and any change to an existing
  record in `margi/feedback/` (which is append-only).
- **CI** (`margi guard --range`, written when the repository has a GitHub remote) repeats the
  hook's checks, so `--no-verify` doesn't bypass them.
- **Agent permissions**: `.claude/settings.json` allows `Edit(margi/**)`, the margi helpers and
  read-only `git`/`gh` commands, and always denies edits to margi's own setup (including
  `thesis.config.yml`). `margi save`, `margi author` and `sync-todos` (creates GitHub issues)
  always ask for your permission.
- **`protect_thesis`** in `thesis.config.yml` (default `true`) also denies every agent session
  edits to thesis sources (`.typ`, `.bib`, `.tex`, `.qmd`) and `git commit`/`push`/`reset`/`checkout`,
  whatever you ask it. Set it to `false` if you want your agent's help outside margi, then run
  `uv run margi init`: it rewrites the settings and commits them together with the config change
  (`chore: update margi … (protect_thesis: false)`), so the choice is on record in `git log`.
  If the two ever disagree, the next margi command stops and tells you to run `margi init`.
  margi's own commands follow the human-writing rules either way.

`git log -- margi/` is the complete AI audit trail for your advisors. Besides margi's own records,
`margi/` holds one kind of text by you: your answers to comments (`/margi respond`), committed
under your name, so the log shows who said what.

## Saving your work

margi only gives feedback on a version of your thesis that you saved, so every grade points to
exactly the text it read. You don't save with git yourself (you can, if you like): when a
`/margi` command finds unsaved changes, it pauses and shows what would be saved:

```
Your thesis has changes that aren't saved yet. margi only gives feedback on a saved version.
  chapters/2-method.typ  +1,240 chars
  refs.bib               +3 entries
Saving makes a version under your name (a git commit) that stays on this computer.
```

The agent then runs `uv run margi save`, and Claude Code asks you to approve it. That approval is
your decision; margi never saves your work on its own. Decline, and the command stops without
feedback. The save is tied to what you were shown: if a file changed in between, nothing is saved
and you see the new summary.

- **Your name.** Saves are recorded under `author` in `thesis.config.yml` (default `User`, no
  email). `margi init` asks for it; change it in the file any time, or tell your agent, which
  runs `uv run margi author` (again only after you approve). Later saves use the new value.
- **Where versions go.** Without a remote repository, saves stay on this computer. Once you add
  one (`git remote add origin …`), every save also uploads there; if the upload fails, the
  version is still saved locally and goes up with the next save.
- **On the record.** Saves are commits by you, never by the bot, with a fixed message margi writes
  (`save: 2 files, +1,281 chars`) and a `Margi-Save:` line. The AI-use appendix counts them.
- If "always allow" ever lets your agent save without asking, `/margi status` warns and
  `uv run margi init` removes the rule.

### Without git

margi also works in a folder that isn't a git repository (`margi init` creates one, so this only
happens if you remove it). Every command still runs and still writes provenance-stamped records to
`margi/feedback/`, but everything that needs git is skipped:

- no saves and no commits;
- no check that nothing outside `margi/` changed;
- anchors and file hashes come from the working tree, not `HEAD`;
- no commit hook, and `margi guard` refuses to run.

So the separation is not enforced without git. Run `uv run margi init` again to set it up.

## Layout

```
skills/margi/            SKILL.md, commands/{grade,read,respond,todos}.md, rubrics/default/, schema/
skills/margi-propose/    SKILL.md, templates/ (the margi/docs files)
skills/margi-challenge/  SKILL.md, lenses.md
templates/               config, PROPOSAL.md, Typst skeleton, commit-msg hook, CI workflow, Claude settings,
                         dash/ (dashboard page and its Libertinus fonts, OFL)
src/margi/               init, export + hidden helpers (finalize, guard, outline, dashboard, adapters/typst, …)
```

The only supported format is Typst; the adapters in `src/margi/adapters/` are the extension
point for LaTeX, Quarto and Markdown.

### Rubrics

Every grade uses the bundled rubric in `skills/margi/rubrics/default/` (seven categories, scored
1–5). Custom rubrics are not supported yet. They may come later in a constrained form, where
each category has:

- a description of what is graded;
- a bounded scale: 1–5 for now, possibly 1–10, percentages or other bounded scales later;
- descriptions of the floor and ceiling values (what the lowest and highest score mean).

Open-ended scoring without such anchors will not be supported. Custom rubrics are written by
people, so they would live outside `margi/`, which holds only what margi writes.

## Development

```sh
uv sync && uv run pytest
```
