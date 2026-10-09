# margi

**AI in the margins, never in the text.**

margi is a feedback layer for a thesis that you write 100% by hand. You use it from your AI
agent with `/margi` commands. The agent reads your thesis and writes documentation,
grades, literature ratings and todos, but **only inside `margi/`**, and always in commits that
are kept separate from yours. Git hooks and CI enforce this. You don't have to take it on trust.

## Install

```sh
mkdir my-thesis && cd my-thesis && git init && uvx margi init
```

This is the only setup command you run in the terminal. In an empty folder it bootstraps a Typst
thesis: `main.typ` with a chapter skeleton in `chapters/`, an empty `refs.bib`, `lit/` for
PDFs, and `PROPOSAL.md`. In an existing Typst project it only adds what is missing
(`PROPOSAL.md` and margi itself) and leaves your files alone.

Then:

1. Write your plan into `PROPOSAL.md`: title ideas, research question, data, method, outline,
   constraints. Fragments and loose thoughts are fine.
2. Commit it.
3. Open your agent in the repository and run `/margi propose`. margi turns the proposal into
   structured docs in `margi/docs/` and lists what is still unclear in
   `margi/docs/open-questions.md`.
4. Add to `PROPOSAL.md`, commit, and run `/margi propose` again until the docs are complete
   enough.

margi is installed **per thesis repository**, not globally. `margi init` adds it as a dev
dependency to the repo's `pyproject.toml` (creating a bare one if needed) and locks it in
`uv.lock`, so you, your agent, the commit hook and CI all run the same pinned version from
`.venv/`. Run commands with `uv run margi …` (or activate `.venv`). After cloning on another
machine, run `uv sync` once.

`margi init` also vendors the skills to `.agents/skills/` and symlinks them from `.claude/skills/`, so
Claude Code, Codex, Cursor and other agents that read `SKILL.md` can use them. Finally it
writes `thesis.config.yml`, installs the commit guard and the CI workflow, and creates `margi/`.

## Commands

All commands run inside your agent.

| Command | |
|---|---|
| `/margi propose [--from expose.md]` | Reads your `PROPOSAL.md` (or another file) and documents the research question, dataset, method, field, structure and constraints in `margi/docs/`, with gaps listed in `open-questions.md`. Every other command grades against these docs. |
| `/margi challenge <aspect>` | A devil's-advocate dialogue about any aspect of the project. The refinements you confirm are written back into `margi/docs/`. |
| `/margi grade <section>` | Rubric-based scores per category with comments anchored to file, lines and a verbatim quote. If the docs are incomplete, it asks before grading and marks the result low-confidence. |
| `/margi outline` | Character counts and their distribution across sections and subsections, compared against targets from `structure.md`. No AI involved. |
| `/margi read [pdf…]` | Rates literature PDFs for relevance to your research question and outline. |
| `/margi todos` | Proposes todos as Markdown files and suggests closing issues that look done. You accept, reject or request changes, and only accepted items go to GitHub. |
| `/margi status` | Shows docs completeness, latest grades, outline, todos and recent runs. |

`/margi-propose` and `/margi-challenge <aspect>` work as shortcuts too.

## Dashboard

Open `margi/dash.html` in a browser. It shows every section in thesis order with its latest
rubric scores, what changed since it was graded, the anchored comments, how scores developed
over time, project docs, literature, todos and the run log. The header always shows the next
margi command to run, with a copy button. Those suggestions come from rule-based checks (docs
below the threshold, sections changed since grading, ungraded sections, unrated PDFs, …)
and from your agent, which can add steps based on what you asked for in the session.

The page itself never changes; every margi run only rewrites its data file,
`margi/dash/data.js`, and commits it with the run. To share a snapshot, run

```sh
uv run margi export          # writes margi/dash/export.html, one self-contained offline file
```
 In the background,
the skills call a few hidden `uv run margi …` helpers (`finalize`, `outline`, `status`,
`extract-pdfs`, `sync-todos`); you never need to run them yourself.

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
- **CI** (`margi guard --range`) repeats the hook's checks, so `--no-verify` doesn't bypass them.
- **Agent permissions**: `.claude/settings.json` allows `Edit(margi/**)`, the margi helpers and
  read-only `git`/`gh` commands, and denies edits to thesis sources and git commits.
  `sync-todos` (creates GitHub issues) still asks for your permission.

`git log -- margi/` is the complete AI audit trail for your advisors.

### Without git

margi also works in a folder that isn't a git repository. Every command still runs and still
writes provenance-stamped records to `margi/feedback/`, but everything that needs git is skipped:

- no commits;
- no check that nothing outside `margi/` changed;
- anchors and file hashes come from the working tree, not `HEAD`;
- no commit hook, and `margi guard` refuses to run.

So the separation is not enforced until you add git. Once you run `git init`, run
`uv run margi init` again to install the hook and make the first two commits. From then on,
everything is enforced.

## Layout

```
skills/margi/            SKILL.md, commands/{grade,read,todos}.md, rubrics/default/, schema/
skills/margi-propose/    SKILL.md, templates/ (the margi/docs files)
skills/margi-challenge/  SKILL.md, lenses.md
AGENTS.md                hard rules, merged into the thesis repo's AGENTS.md
templates/               config, PROPOSAL.md, Typst skeleton, commit-msg hook, CI workflow, Claude settings,
                         dash/ (dashboard page and its Libertinus fonts, OFL)
src/margi/               init, export + hidden helpers (finalize, guard, outline, dashboard, adapters/typst, …)
```

The only supported format is Typst; the adapters in `src/margi/adapters/` are the extension
point for LaTeX, Quarto and Markdown. To use your own rubric, put it in
`margi/rubrics/<id>/` in the thesis repo.

## Development

```sh
uv sync && uv run pytest
```
