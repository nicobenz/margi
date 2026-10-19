"""margi command-line interface.

The user-facing commands are `init`, `update` and `export`. Everything else happens in the agent (`/margi ...`);
the remaining commands are hidden plumbing that the skills, the commit hook and CI call.
"""

from __future__ import annotations

import os
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


def _clean_or_exit(cfg: Config) -> None:
    """Start-of-run check. Unsaved work prints margi's save summary as is (no "Error:"), exit 1."""
    try:
        ensure_clean(cfg)
    except FinalizeError as e:
        if str(e).startswith("Your thesis has changes"):
            click.echo(str(e))
            sys.exit(1)
        raise click.ClickException(str(e)) from e


def _cfg() -> Config:
    return load(project_root(Path.cwd(), CONFIG_NAME))


def _report(result: FinalizeResult, cfg: Config | None = None) -> None:
    for rec in result.records:
        click.echo(f"  wrote {rec.relative_to(rec.parents[2]).as_posix()}")
    if not result.has_git:
        click.echo(f"  not committed ({NO_GIT})")
    elif result.commit:
        click.echo(f"  committed {result.commit[:7]}  {result.message}")
    elif not result.records:
        click.echo("  nothing to finalize")
    if cfg is not None:
        _handover(cfg)


def _handover(cfg: Config) -> None:
    from .dashboard import handover

    for line in handover(cfg):
        click.echo(line)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="margi")
def main() -> None:
    """margi: AI in the margins, never in the text.

    Run `uvx margi init` once in your thesis repository. After that, use margi from
    your agent: /margi propose, /margi grade 2.1, /margi read, /margi todos, ...
    `uv run margi update` moves the repository to the latest margi.
    """


# ----------------------------------------------------------------- setup


@main.command()
@click.option("--no-commit", is_flag=True, help="Scaffold files without committing.")
@click.option("--no-claude-settings", is_flag=True, help="Do not write .claude/settings.json permissions.")
@click.option("--force-config", is_flag=True, help="Overwrite an existing thesis.config.yml.")
@click.option("--no-install", is_flag=True, help="Do not add margi to the repo's pyproject.toml (uv).")
@click.option("--spec", help="Requirement passed to `uv add --dev` (default: margi==<this version>; a path works too).")
@click.option("--no-open", is_flag=True, help="Do not open the dashboard in a browser.")
@click.option("-v", "--verbose", is_flag=True, help="List every file written or kept.")
def init(
    no_commit: bool,
    no_claude_settings: bool,
    force_config: bool,
    no_install: bool,
    spec: str | None,
    no_open: bool,
    verbose: bool,
) -> None:
    """Bootstrap a Typst thesis with margi, or add margi to an existing one."""
    from .init import GitMissing, InitError, init as run_init

    root = project_root(Path.cwd(), CONFIG_NAME)
    interactive = sys.stdin.isatty() and sys.stdout.isatty() and not os.environ.get("CI")
    import shutil

    if not shutil.which("git"):  # before asking anything: without git there is nothing to set up
        offer_git_install("margi needs git to keep versions of your thesis, and git is not installed", interactive)
        sys.exit(1)
    author = None
    if interactive and (force_config or not (root / CONFIG_NAME).exists()):
        author = ask_author()
    try:
        report = run_init(root, commit=not no_commit, claude_settings=not no_claude_settings, force_config=force_config,
                         install=not no_install, spec=spec, author=author)
    except GitMissing as e:
        offer_git_install(str(e), interactive)
        sys.exit(1)
    except InitError as e:
        raise click.ClickException(str(e)) from e
    if verbose:
        for w in report.written:
            click.echo(f"  wrote {w}")
        for k in report.kept:
            click.echo(f"  kept  {k}")
        for c in report.commits:
            click.echo(f"  commit {c}")
    for s in report.skipped:
        click.echo(f"  skipped {s}")
    from .dashboard import DASH_HTML, open_page

    dash = (root / DASH_HTML).resolve()
    opened = False
    if should_open_dashboard(report.first, no_open, sys.stdout.isatty(), os.environ):
        opened = open_page(root, only_if_changed=False) == "opened"
    click.echo("\nmargi is ready." + ("" if verbose else
                                       f" Set up {_plural(len(report.written), 'file')}"
                                       + (f", kept {len(report.kept)} existing" if report.kept else "")
                                       + " (--verbose lists them).") + "\n")
    click.echo(f"  Dashboard  {dash.as_uri()}   ({'opened in your browser' if opened else 'open it in a browser'})")
    click.echo("  Versions   " + (f"saves upload to {report.remote}" if report.remote else
                                 "saves stay on this computer until you add a remote repository"))
    click.echo("  Next       write your plan into PROPOSAL.md, then run /margi propose in Claude Code")
    click.echo("             (start Claude Code in this folder: type `claude` here, or open the folder in the app)")
    click.echo("  Lost?      run /margi help in Claude Code: where you stand, what to run next, every command")


@main.command()
@click.option("--to", "to", metavar="VERSION", help="Update to this version instead of the latest release.")
@click.option("--check", is_flag=True, help="Only show whether a newer margi is available.")
@click.option("--no-commit", is_flag=True, help="Update files without committing.")
def update(to: str | None, check: bool, no_commit: bool) -> None:
    """Update margi in this thesis repository to the latest release."""
    from .update import UpdateError, update as run_update

    root = project_root(Path.cwd(), CONFIG_NAME)
    try:
        result = run_update(root, to=to, commit=not no_commit, check=check)
    except UpdateError as e:
        raise click.ClickException(str(e)) from e
    if check:
        if result.target == result.current:
            click.echo(f"margi {result.current} is up to date.")
        else:
            click.echo(f"margi {result.current} is installed; {result.target} is available. Run `uv run margi update`.")
        return
    if result.delegated:
        click.echo(f"\nmargi updated from {result.current} to {result.target}.")
    elif result.changed:
        click.echo(f"\nmargi {result.current} is up to date; restored its files ({', '.join(result.report.commits)}).")
    else:
        click.echo(f"margi {result.current} is up to date.")


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def ask_author() -> tuple[str | None, str | None]:
    """Ask who saves are recorded as; Enter keeps the placeholder. Runs in the terminal, before any AI."""
    from .config import PLACEHOLDER

    click.echo("Your saved versions are recorded under a name.")
    name = click.prompt("  Name", default=PLACEHOLDER[0], show_default=True).strip()
    email = click.prompt("  Email (optional)", default="", show_default=False).strip()
    click.echo("  You can change this later in thesis.config.yml, or ask your agent to do it.\n")
    return (name if name and name != PLACEHOLDER[0] else None), (email or None)


def git_install_command() -> tuple[list[str] | None, str]:
    """(command margi may run without admin rights, or None; the instruction to show)."""
    if sys.platform == "darwin":
        return ["xcode-select", "--install"], "xcode-select --install"
    if sys.platform == "win32":
        return ["winget", "install", "--id", "Git.Git", "-e"], "winget install --id Git.Git -e"
    return None, "install it with your package manager, e.g. `sudo apt install git` or `sudo dnf install git`"


def offer_git_install(message: str, interactive: bool) -> None:
    import shutil
    import subprocess

    cmd, hint = git_install_command()
    click.echo(f"{message}.", err=True)
    if cmd and interactive and shutil.which(cmd[0]) and click.confirm("Install it now?", default=True):
        subprocess.run(cmd)
        click.echo("When the installation has finished, open a new terminal and run `uvx margi init` again.")
        return
    click.echo(f"To install git: {hint}. Then run `uvx margi init` again.", err=True)


def should_open_dashboard(first: bool, no_open: bool, interactive: bool, env) -> bool:
    """Open the dashboard only when margi was just added, by a person at a terminal, outside CI."""
    return first and not no_open and interactive and not env.get("CI")


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
        click.echo("\n(snapshot not recorded: the thesis has unsaved changes, and margi records counts only for a "
                   "saved version)")
        return
    outline_mod.write_snapshot(cfg, outline_mod.snapshot_draft(tree, rows, unit))
    try:
        result = run_finalize(cfg, model_source="none")
    except FinalizeError as e:
        raise click.ClickException(str(e)) from e
    click.echo("")
    _report(result, cfg)


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
    """[plumbing] Overview: docs completeness, latest grades, outline, todos, recent runs.

    Also refreshes the dashboard data, so it reflects commits made since the last margi run.
    """
    from .dashboard import refresh

    cfg = _cfg()
    refresh(cfg)
    click.echo(status_mod.render(cfg))
    click.echo("")
    _handover(cfg)


@main.command(name="open", hidden=True)
@click.option("--always", is_flag=True, help="Open it even if nothing changed since it was last opened.")
def open_(always: bool) -> None:
    """[plumbing] Open the dashboard in the browser if it changed since it was last opened.

    The agent runs this last, before its report; the printed line replaces finalize's dashboard line.
    """
    from .dashboard import dashboard_line, open_page

    cfg = _cfg()
    state = open_page(cfg.root, only_if_changed=not always)
    click.echo(dashboard_line(cfg, {"opened": "opened in your browser",
                                    "unchanged": "unchanged since it was last opened",
                                    "failed": "open it in a browser"}[state]))


@main.command(name="next", hidden=True)
def next_() -> None:
    """[plumbing] Setup progress, next steps and what is there or missing, for /margi help. Read-only."""
    from .overview import render

    click.echo(render(_cfg()))


@main.command(hidden=True)
@click.argument("scope", required=False)
@click.option("--all", "show_all", is_flag=True, help="Also list closed comments.")
def comments(scope: str | None, show_all: bool) -> None:
    """[plumbing] Comments that aren't closed; with SCOPE, those a grade of SCOPE must give a verdict on."""
    from . import lifecycle

    cfg = _cfg()
    if scope:
        sid, entries = lifecycle.pending(cfg, scope)
        if not entries:
            click.echo(f"no open comments in {sid}; the grade gives no verdicts")
            return
        click.echo(f"{len(entries)} comment{'s' if len(entries) != 1 else ''} in {sid} need a verdict in this grade:\n")
    else:
        entries = [c for c in lifecycle.comments(cfg) if show_all or c["state"] in lifecycle.AWAITING]
        if not entries:
            click.echo("no open comments")
            return
    click.echo(lifecycle.render(entries))


@main.command(hidden=True)
@click.argument("answers", nargs=-1, required=True)
@click.option("--reason", "reasons", nargs=2, multiple=True, metavar="REF TEXT",
              help="The student's own words for one comment, stored verbatim. Repeat per comment.")
def respond(answers: tuple[str, ...], reasons: tuple[tuple[str, str], ...]) -> None:
    """[plumbing] Record the student's answers, e.g. `c17=addressed c18=disputed --reason c18 "..."`.

    Statuses: addressed, disputed, wont_fix. The record is committed under the student's name (`author` in thesis.config.yml).
    """
    from .lifecycle import LifecycleError
    from .lifecycle import respond as run_respond

    pairs = []
    for a in answers:
        ref, sep, status = a.partition("=")
        if not sep:
            raise click.ClickException(f"{a!r}: write REF=STATUS, e.g. c17=addressed")
        pairs.append((ref.strip(), status.strip().replace("-", "_").replace("won't_fix", "wont_fix")))
    given: dict[str, str] = {}
    for ref, text in reasons:
        if ref in given:
            raise click.ClickException(f"{ref}: more than one --reason")
        given[ref] = text
    cfg = _cfg()
    try:
        path, sha = run_respond(cfg, pairs, given)
    except LifecycleError as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"  wrote {path.relative_to(cfg.root).as_posix()}")
    if sha:
        click.echo(f"  committed {sha[:7]}  margi: respond {' '.join(r for r, _ in pairs)}")
    elif not cfg.has_git:
        click.echo(f"  not committed ({NO_GIT})")
    _handover(cfg)


@main.command(name="submit-check", hidden=True)
def submit_check() -> None:
    """[plumbing] Check quotations, bibliography, length, grades and open items before submission (no AI)."""
    import json as _json

    from . import submission
    from .finalize import STAGING

    cfg = _cfg()
    _clean_or_exit(cfg)
    payload = submission.run(cfg)
    lines = submission.summary(payload)
    for line in lines:
        click.echo(line)
    c = payload["counts"]
    draft = {"command": "submit-check", "scope": "all",
             "summary": f"{c['findings']} findings, {c['attention']} need attention. " + " ".join(lines)[:2800],
             "payload": payload}
    staging = cfg.root / STAGING
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "submit-check.json").write_text(_json.dumps(draft, ensure_ascii=False), encoding="utf-8")
    try:
        result = run_finalize(cfg, model_source="none")
    except FinalizeError as e:
        raise click.ClickException(str(e)) from e
    click.echo("")
    _report(result, cfg)


@main.command(name="ai-report", hidden=True)
def ai_report() -> None:
    """[plumbing] Write the AI-use appendix (margi/ai-use.md, printable margi/dash/ai-use.html) and commit it."""
    from . import ai_report as report_mod

    cfg = _cfg()
    _clean_or_exit(cfg)
    _, rep = report_mod.write(cfg)
    click.echo(f"  wrote {report_mod.MD} ({len(rep['rows'])} runs) and {report_mod.HTML} (printable, not committed)")
    if rep["violations"]:
        click.echo(f"  the guard found {len(rep['violations'])} commit(s) that break the separation; see the report")
    try:
        result = run_finalize(cfg, command="ai-report", model_source="none")
    except FinalizeError as e:
        raise click.ClickException(str(e)) from e
    _report(result, cfg)


@main.command(name="sync-todos", hidden=True)
def sync_todos() -> None:
    """[plumbing] Apply accepted todos and closures; with github.sync, mirror them to issues (no AI)."""
    from .todos_sync import SyncError, sync_accepted

    cfg = _cfg()
    try:
        report = sync_accepted(cfg)
    except SyncError as e:
        raise click.ClickException(str(e)) from e
    for tid in report.opened:
        click.echo(f"  open    {tid}")
    for tid, n in report.created:
        click.echo(f"  created #{n}  {tid}")
    for tid, n in report.reused:
        click.echo(f"  exists  #{n}  {tid}")
    for n in report.closed:
        click.echo(f"  closed  #{n}")
    for tid in report.done:
        click.echo(f"  done    {tid}")
    if not (report.opened or report.closed or report.done):
        click.echo("  nothing accepted to apply")


@main.command(name="todo-done", hidden=True)
@click.argument("ids", nargs=-1, required=True)
@click.option("--note", help="The student's own words, stored verbatim (at most 600 characters).")
def todo_done(ids: tuple[str, ...], note: str | None) -> None:
    """[plumbing] The student marks open todos done; committed under their name."""
    from .todos_sync import SyncError, todo_done as run_done

    cfg = _cfg()
    try:
        moved, sha = run_done(cfg, list(ids), note)
    except SyncError as e:
        raise click.ClickException(str(e)) from e
    for p in moved:
        click.echo(f"  done    {p.relative_to(cfg.root).as_posix()}")
    if sha:
        click.echo(f"  committed {sha[:7]}  margi: todo done {' '.join(dict.fromkeys(ids))}")
    elif not cfg.has_git:
        click.echo(f"  not committed ({NO_GIT})")


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
        _clean_or_exit(cfg)
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
    _report(result, cfg)
    if result.commit and not result.records and not subject:
        click.echo("warning: no draft in margi/.staging/, so this commit has no run record. If you ran a command, "
                   "the draft write failed (check the path); write it and run `uv run margi finalize` again.", err=True)


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


@main.command(hidden=True)
@click.option("--expect", required=True, metavar="HASH",
              help="The hash from the summary margi printed; nothing is saved if the files changed since.")
def save(expect: str) -> None:
    """[plumbing] Save the student's work as a version under their name, after they approved it.

    The agent runs this only with the hash from margi's own summary; Claude Code asks the student
    first (`ask` in .claude/settings.json). Never prints the student's name.
    """
    from .save import SaveError, save as run_save

    cfg = _cfg()
    try:
        result = run_save(cfg, expect.strip())
    except SaveError as e:
        raise click.ClickException(str(e)) from e
    from datetime import datetime

    line = f"Saved as yours · {datetime.now().strftime('%H:%M')} · {result.files} file{'s' if result.files != 1 else ''}"
    if result.pushed:
        line += f" · uploaded to {result.remote}"
    click.echo(line)
    if result.push_error:
        click.echo(f"Saved on this computer; upload to {result.remote} failed: {result.push_error}. "
                   "It will go up with the next save.")
    from .dashboard import refresh

    refresh(cfg)


@main.command(hidden=True)
@click.option("--name", help="Your name as it appears on your saved versions.")
@click.option("--email", help="Optional email for your saved versions.")
def author(name: str | None, email: str | None) -> None:
    """[plumbing] Set who saves are recorded as (`author` in thesis.config.yml). Never echoes it."""
    from .config import set_author

    if name is None and email is None:
        raise click.UsageError("pass --name and/or --email")
    cfg = _cfg()
    current = cfg.get("author") or {}
    set_author(cfg.root, name if name is not None else current.get("name"),
               email if email is not None else current.get("email"))
    click.echo(f"  updated author in {CONFIG_NAME}; later saves use it (earlier saves keep theirs)")


@main.command(name="extract-pdfs", hidden=True)
@click.argument("pdfs", nargs=-1)
def extract_pdfs(pdfs: tuple[str, ...]) -> None:
    """[plumbing] Extract literature PDFs to margi/.cache/lit/. Prints pdf, text file and flagged pages."""
    from .pdf import extract

    for path, entry in extract(_cfg(), list(pdfs) or None).items():
        flags = ",".join(f"{page}:{why}" for page, why in entry["flags"].items()) or "-"
        click.echo(f"{path}\t{entry['text']}\t{flags}")


if __name__ == "__main__":
    main()
