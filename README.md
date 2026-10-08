# margi

**AI in the margins, never in the text.**

margi is a feedback layer for a thesis that you write 100% by hand. Short terminal commands
launch an AI agent with a specific skill. The agent reads your thesis and writes documentation,
grades, literature ratings and todos, but **only inside `margi/`**, and always in commits that
are kept separate from yours. Git hooks and CI enforce this. You don't have to take it on trust.

## Install

```sh
cd my-thesis && uvx margi init
```

margi is installed **per thesis repository**, not globally. `margi init` adds it as a dev
dependency to the repo's `pyproject.toml` (creating a bare one if needed) and locks it in
`uv.lock`, so you, your agent, the commit hook and CI all run the same pinned version from
`.venv/`. Run commands with `uv run margi …` (or activate `.venv`). After cloning on another
machine, run `uv sync` once.

It also vendors the skills to `.agents/skills/` and symlinks them from `.claude/skills/`, so
Claude Code, Codex, Cursor and other agents that read `SKILL.md` can use them. Finally it
writes `thesis.config.yml`, installs the commit guard and the CI workflow, creates `margi/`,
and starts onboarding.

## Commands

| Command | |
|---|---|
| `margi onboard [--from expose.md]` | Reads your README or exposé, then **interviews you** to document the research question, dataset, method, field, structure and constraints in `margi/docs/`. Every other command grades against these docs. |
| `margi challenge <aspect>` | A devil's-advocate dialogue about any aspect of the project. The refinements you confirm are written back into `margi/docs/`. |
| `margi grade <section>` | Rubric-based scores per category with comments anchored to file, lines and a verbatim quote. Refuses to run while the docs are incomplete (override with `--force`). |
| `margi outline` | Character counts and their distribution across sections and subsections, compared against targets from `structure.md`. No AI involved. |
| `margi read [pdf…]` | Rates literature PDFs for relevance to your research question and outline. |
| `margi todos` | Proposes todos as Markdown files and suggests closing issues that look done. You accept, reject or request changes, and only accepted items go to GitHub. |
| `margi status` | Shows docs completeness, latest grades, outline, todos and recent runs. |

Run each command as `uv run margi <command>`. Inside an agent session you can use the same
commands as `/margi grade 2.1`, `/margi-onboard` and `/margi-challenge research question`.

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
- **Agent permissions**: the wrapper only allows reads, `Edit(margi/**)` and a handful of
  `margi`/`git status` commands, and `.claude/settings.json` denies edits to thesis sources.

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
skills/margi-onboard/    SKILL.md, interview.md, templates/ (the margi/docs files)
skills/margi-challenge/  SKILL.md, lenses.md
AGENTS.md                hard rules, merged into the thesis repo's AGENTS.md
templates/               config, commit-msg hook, CI workflow, Claude settings
src/margi/               CLI (finalize, guard, outline, adapters/typst, wrapper, init, …)
```

The only supported format is Typst; the adapters in `src/margi/adapters/` are the extension
point for LaTeX, Quarto and Markdown. To use your own rubric, put it in
`margi/rubrics/<id>/` in the thesis repo.

## Development

```sh
uv sync && uv run pytest
```
