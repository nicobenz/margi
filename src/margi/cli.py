"""margi command-line interface.

The user-facing commands are `init` and `export`. Everything else happens in the agent (`/margi ...`);
the remaining commands are hidden plumbing that the skills, the commit hook and CI call.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from . import __version__
from . import outline as outline_mod
from . import status as status_mod
from .config import CONFIG_NAME, Config, load
from .finalize import FinalizeError, FinalizeResult, ensure_clean, finalize as run_finalize, preflight
from .gitutil import project_root
from .guard import check_range, check_staged, commit_msg_from_file


NO_GIT = "no git repository: margi works, but commits, the clean-tree check and the guard are skipped"


def _cfg() -> Config:
    return load(project_root(Path.cwd(), CONFIG_NAME))


def _report(result: FinalizeResult) -> None:
    for rec in result.records:
        click.echo(f"  wrote {rec.relative_to(rec.parents[2]).as_posix()}")
    if not result.has_git:
        click.echo(f"  not committed ({NO_GIT})")
    elif result.commit:
        click.echo(f"  committed {result.commit[:7]}  {result.message}")
    elif not result.records:
        click.echo("  nothing to finalize")


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="margi")
def main() -> None:
    """margi: AI in the margins, never in the text.

    Run `uvx margi init` once in your thesis repository. After that, use margi from
    your agent: /margi propose, /margi grade 2.1, /margi read, /margi todos, ...
    """


# ----------------------------------------------------------------- setup


@main.command()
@click.option("--no-commit", is_flag=True, help="Scaffold files without committing.")
@click.option("--no-claude-settings", is_flag=True, help="Do not write .claude/settings.json permissions.")
@click.option("--force-config", is_flag=True, help="Overwrite an existing thesis.config.yml.")
@click.option("--no-install", is_flag=True, help="Do not add margi to the repo's pyproject.toml (uv).")
@click.option("--spec", help="Requirement passed to `uv add --dev` (default: margi==<this version>; a path works too).")
def init(
    no_commit: bool,
    no_claude_settings: bool,
    force_config: bool,
    no_install: bool,
    spec: str | None,
) -> None:
    """Bootstrap a Typst thesis with margi, or add margi to an existing one."""
    from .init import InitError, init as run_init

    try:
        root = project_root(Path.cwd(), CONFIG_NAME)
        report = run_init(root, commit=not no_commit, claude_settings=not no_claude_settings, force_config=force_config,
                         install=not no_install, spec=spec)
    except InitError as e:
        raise click.ClickException(str(e)) from e
    for w in report.written:
        click.echo(f"  wrote {w}")
    for k in report.kept:
        click.echo(f"  kept  {k}")
    for c in report.commits:
        click.echo(f"  commit {c}")
    for s in report.skipped:
        click.echo(f"  skip  {s}")
    click.echo("\nmargi is ready. Write your plan into PROPOSAL.md, commit it, then run /margi propose "
               "in your agent.")


@main.command()
@click.option("--out", type=click.Path(dir_okay=False, path_type=Path),
              help="Where to write the file (default: margi/dash/export.html).")
def export(out: Path | None) -> None:
    """Write the dashboard as one self-contained HTML file that works offline."""
    from .dashboard import export as run_export

    cfg = _cfg()
    path = run_export(cfg, out.resolve() if out else None)
    try:
        shown = path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        shown = str(path)
    click.echo(f"  wrote {shown}")


# ----------------------------------------------------------------- plumbing (hidden, called by skills, hook and CI)


@main.command(hidden=True)
@click.option("--no-save", is_flag=True, help="Only print; do not commit a snapshot.")
def outline(no_save: bool) -> None:
    """[plumbing] Character distribution across sections and subsections."""
    cfg = _cfg()
    try:
        tree, rows = outline_mod.compute(cfg)
    except FileNotFoundError as e:
        raise click.ClickException(str(e)) from e
    unit = cfg.get("count", "chars")
    click.echo(outline_mod.render(tree, rows, unit))
    if no_save:
        return
    if preflight(cfg):
        click.echo("\n(snapshot not saved: uncommitted changes outside margi/ — commit first so counts match HEAD)")
        return
    outline_mod.write_snapshot(cfg, outline_mod.snapshot_draft(tree, rows, unit))
    try:
        result = run_finalize(cfg, model_source="none")
    except FinalizeError as e:
        raise click.ClickException(str(e)) from e
    click.echo("")
    _report(result)


@main.command(hidden=True)
@click.argument("section")
def precheck(section: str) -> None:
    """[plumbing] Is a section ready to grade? Run before `/margi grade`."""
    from .readiness import ReadinessError, for_scope, mode

    cfg = _cfg()
    try:
        m = mode(cfg)
    except ReadinessError as e:
        raise click.ClickException(str(e)) from e
    sec, check = for_scope(cfg, section)
    if check is None:
        raise click.ClickException(f"no section {section!r} in the thesis (see `uv run margi outline --no-save`)")
    click.echo(f"{sec.id} {sec.title}: {'ready' if check['ready'] else 'not ready'} to grade (grade.precheck: {m})")
    for r in check["reasons"]:
        click.echo(f"  - {r}")
    click.echo(f"  {check['words']} words of running prose, {check['list_share']:.0%} list items"
               + (f", markers: {', '.join(check['markers'])}" if check["markers"] else ""))


@main.command(hidden=True)
def status() -> None:
    """[plumbing] Overview: docs completeness, latest grades, outline, todos, recent runs."""
    click.echo(status_mod.render(_cfg()))


@main.command(name="sync-todos", hidden=True)
def sync_todos() -> None:
    """[plumbing] Push accepted todos/closures to GitHub (no AI)."""
    from .todos_sync import SyncError, sync_accepted

    cfg = _cfg()
    try:
        report = sync_accepted(cfg)
    except SyncError as e:
        raise click.ClickException(str(e)) from e
    for tid, n in report.created:
        click.echo(f"  created #{n}  {tid}")
    for tid, n in report.reused:
        click.echo(f"  exists  #{n}  {tid}")
    for n in report.closed:
        click.echo(f"  closed  #{n}")
    if not (report.created or report.reused or report.closed):
        click.echo("  no accepted todos or closures to sync")


@main.command(hidden=True)
@click.option("--check", is_flag=True, help="Only run the preflight check (use at the start of a run).")
@click.option("--model", help="Self-reported model id.")
@click.option("--harness", help="Self-reported harness name.")
@click.option("--message", "subject", help="Commit subject when there is no draft (e.g. 'todos review').")
def finalize(check: bool, model: str | None, harness: str | None, subject: str | None) -> None:
    """[plumbing] Stamp staged drafts with provenance and commit margi/ as the bot."""
    from . import docs_check
    from .config import MARGI_DIR

    cfg = _cfg()
    if check:
        try:
            ensure_clean(cfg)
        except FinalizeError as e:
            raise click.ClickException(str(e)) from e
        from .agent_settings import drift

        mismatch = drift(cfg)
        if mismatch:
            raise click.ClickException(f"{mismatch}. Run `uv run margi init` to apply the setting.")
        report = docs_check.check(cfg.root / MARGI_DIR / "docs")
        threshold = float(cfg["docs"]["min_completeness"])
        tree = "tree clean outside margi/" if cfg.has_git else NO_GIT
        click.echo(f"ok: {tree}; project docs {report.completeness:.0%} complete")
        if report.completeness < threshold:
            click.echo(f"warning: project docs below {threshold:.0%} — grade/read results will be low-confidence; "
                       "suggest /margi propose")
        return
    try:
        result = run_finalize(cfg, command=subject, harness=harness, model=model,
                              model_source="self-reported" if model else None)
    except FinalizeError as e:
        raise click.ClickException(str(e)) from e
    _report(result)


@main.command(hidden=True)
@click.option("--staged", "msg_file", type=click.Path(exists=True), help="Check the staged commit; pass the commit-msg file.")
@click.option("--range", "rev_range", help="Check every commit in a revision range (CI).")
def guard(msg_file: str | None, rev_range: str | None) -> None:
    """[plumbing] Enforce separation of human and margi commits."""
    cfg = _cfg()
    if not cfg.has_git:
        raise click.ClickException("margi guard needs a git repository")
    if msg_file:
        problems = check_staged(cfg.root, cfg, commit_msg_from_file(msg_file))
        if problems:
            click.echo("margi guard: commit rejected", err=True)
            for p in problems:
                click.echo(f"  - {p}", err=True)
            sys.exit(1)
        return
    if rev_range:
        results = check_range(cfg.root, cfg, rev_range)
        for sha, problems in results.items():
            click.echo(f"{sha[:10]}:", err=True)
            for p in problems:
                click.echo(f"  - {p}", err=True)
        if results:
            sys.exit(1)
        click.echo("margi guard: all commits ok")
        return
    raise click.UsageError("pass --staged <msg-file> or --range <rev-range>")


@main.command(name="extract-pdfs", hidden=True)
@click.argument("pdfs", nargs=-1)
def extract_pdfs(pdfs: tuple[str, ...]) -> None:
    """[plumbing] Extract literature PDFs to margi/.cache/lit/."""
    from .pdf import extract

    for path, entry in extract(_cfg(), list(pdfs) or None).items():
        click.echo(f"{path}\t{entry['text']}")


if __name__ == "__main__":
    main()
