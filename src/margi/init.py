"""`margi init`: bootstrap a Typst thesis with margi, or add margi to an existing one.

Only missing files are created: PROPOSAL.md always, the Typst skeleton (main.typ, chapters/,
refs.bib, lit/) only when there is no main file yet.

Produces two commits so human and margi files never mix:
  1. "chore: install margi"  (your identity)  — PROPOSAL.md, Typst skeleton, skills, config, hooks,
                                                CI, agent settings, and margi pinned as a dev
                                                dependency (pyproject.toml, uv.lock)
  2. "margi: init"           (margi bot)      — the margi/ directory with doc templates

Without git, the files are scaffolded but the hook setup and both commits are skipped;
run `git init` and `margi init` again to enable them.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import __version__
from .config import CONFIG_NAME, MARGI_DIR, load
from .dashboard import refresh
from .docs_check import ALL_DOCS, templates_dir
from .finalize import bot_commit
from .gitutil import git, is_repo, staged_changes
from . import agent_settings
from .resources import skills_dir, templates_dir as tool_templates

SKILLS = ["margi", "margi-propose", "margi-challenge"]
RETIRED_SKILLS = ["margi-onboard"]  # removed on re-init
BEGIN, END = "<!-- margi:begin -->", "<!-- margi:end -->"  # AGENTS.md section of earlier versions


class InitError(RuntimeError):
    pass


@dataclass
class InitReport:
    written: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    commits: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def detect_main(root: Path) -> str:
    for name in ("main.typ", "thesis.typ"):
        if (root / name).exists():
            return name
    top = sorted(p.name for p in root.glob("*.typ"))
    return top[0] if len(top) == 1 else "main.typ"


def _write(root: Path, rel: str, content: str, report: InitReport, *, overwrite: bool) -> None:
    path = root / rel
    if path.exists() and not overwrite:
        report.kept.append(rel)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    report.written.append(rel)


def _vendor_skills(root: Path, report: InitReport) -> None:
    for name in RETIRED_SKILLS:
        for old in (root / ".agents" / "skills" / name, root / ".claude" / "skills" / name):
            if old.is_symlink() or old.is_file():
                old.unlink()
            elif old.is_dir():
                shutil.rmtree(old)
    for name in SKILLS:
        dest = root / ".agents" / "skills" / name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(skills_dir() / name, dest, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))
        (dest / "VERSION").write_text(__version__ + "\n", encoding="utf-8")
        report.written.append(f".agents/skills/{name}/")

        link = root / ".claude" / "skills" / name
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink() or link.exists():
            if link.is_dir() and not link.is_symlink():
                shutil.rmtree(link)
            else:
                link.unlink()
        os.symlink(Path("..") / ".." / ".agents" / "skills" / name, link)
        report.written.append(f".claude/skills/{name} -> ../../.agents/skills/{name}")


def _retire_agents_md(root: Path, report: InitReport) -> None:
    """Earlier versions merged a margi section into AGENTS.md; remove it, keep everything else."""
    path = root / "AGENTS.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    if BEGIN not in text or END not in text:
        return
    pre, _, rest = text.partition(BEGIN)
    _, _, post = rest.partition(END)
    text = (pre.rstrip() + "\n\n" + post.lstrip()).strip()
    if text:
        path.write_text(text + "\n", encoding="utf-8")
    else:
        path.unlink()
    report.written.append("AGENTS.md (margi section removed)")


def _claude_settings(root: Path, report: InitReport) -> None:
    agent_settings.write(root, bool(load(root)["protect_thesis"]))
    report.written.append(agent_settings.SETTINGS)


def _hook(root: Path, report: InitReport, *, has_git: bool) -> None:
    hook = root / ".githooks" / "commit-msg"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text((tool_templates() / "commit-msg").read_text(encoding="utf-8"), encoding="utf-8")
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    report.written.append(".githooks/commit-msg")
    if not has_git:
        report.skipped.append("core.hooksPath (no git repository; run `git init` and `margi init` again)")
        return
    current = git("config", "--get", "core.hooksPath", cwd=root, check=False).strip()
    if current and current != ".githooks":
        raise InitError(f"core.hooksPath is already set to {current!r}; add .githooks/commit-msg there manually")
    git("config", "core.hooksPath", ".githooks", cwd=root)


def _install(root: Path, spec: str, report: InitReport) -> None:
    """Pin margi in the thesis repo's own uv project so `uv run margi` and the hook use a local copy."""
    uv = shutil.which("uv")
    if not uv:
        raise InitError("`uv` not found on PATH; margi is installed per repository with uv (https://docs.astral.sh/uv/)")
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}

    def run(*args: str) -> None:
        proc = subprocess.run([uv, *args], cwd=root, env=env, capture_output=True, text=True)
        if proc.returncode != 0:
            raise InitError(f"`uv {' '.join(args)}` failed:\n{proc.stderr.strip()}")

    if not (root / "pyproject.toml").exists():
        run("init", "--bare", "--no-workspace")
        report.written.append("pyproject.toml")
    run("add", "--dev", spec)
    report.written.append(f"pyproject.toml: dev dependency {spec}")
    report.written.append("uv.lock")


def _bootstrap(root: Path, main: str, report: InitReport) -> list[str]:
    """Create PROPOSAL.md and, for a new project, the Typst skeleton. Returns the paths created."""
    created: list[str] = []

    def add(rel: str, content: str) -> None:
        if (root / rel).exists():
            report.kept.append(rel)
            return
        _write(root, rel, content, report, overwrite=False)
        created.append(rel)

    add("PROPOSAL.md", (tool_templates() / "PROPOSAL.md").read_text(encoding="utf-8"))
    if (root / main).exists() or any(root.glob("*.typ")) or any(root.glob("*/*.typ")):
        return created
    skeleton = tool_templates() / "typst"
    for src in sorted(p for p in skeleton.rglob("*") if p.is_file()):
        add(src.relative_to(skeleton).as_posix(), src.read_text(encoding="utf-8"))
    add("lit/.gitkeep", "")
    return created


def _margi_dir(root: Path, report: InitReport) -> None:
    m = root / MARGI_DIR
    for sub in ("feedback", "todos/proposed", "todos/close", "todos/synced", "docs"):
        (m / sub).mkdir(parents=True, exist_ok=True)
    for sub in ("feedback", "todos/proposed", "todos/close", "todos/synced"):
        keep = m / sub / ".gitkeep"
        if not keep.exists():
            keep.write_text("", encoding="utf-8")
    _write(root, f"{MARGI_DIR}/.gitignore", ".staging/\n.cache/\ndash/export.html\n", report, overwrite=True)
    for name in ALL_DOCS:
        _write(root, f"{MARGI_DIR}/docs/{name}", (templates_dir() / name).read_text(encoding="utf-8"), report, overwrite=False)
    _write(root, f"{MARGI_DIR}/README.md", (tool_templates() / "margi-README.md").read_text(encoding="utf-8"), report, overwrite=True)
    report.written += refresh(load(root))


def init(
    root: Path,
    *,
    commit: bool = True,
    claude_settings: bool = True,
    force_config: bool = False,
    install: bool = True,
    spec: str | None = None,
) -> InitReport:
    has_git = is_repo(root)
    if has_git and staged_changes(root):
        raise InitError("you have staged changes; commit or unstage them before running `margi init`")
    report = InitReport()
    installed = has_git and bool(git("ls-files", "--", CONFIG_NAME, cwd=root).strip())

    main = load(root)["main"] if (root / CONFIG_NAME).exists() else detect_main(root)
    created = _bootstrap(root, main, report)
    bib = "refs.bib" if (root / "refs.bib").exists() else "null"
    config = (tool_templates() / "thesis.config.yml").read_text(encoding="utf-8")
    config = config.replace("{{main}}", main).replace("{{bib}}", bib)
    _write(root, CONFIG_NAME, config, report, overwrite=force_config)
    _vendor_skills(root, report)
    _retire_agents_md(root, report)
    _hook(root, report, has_git=has_git)
    _write(root, ".github/workflows/margi-guard.yml", (tool_templates() / "margi-guard.yml").read_text(encoding="utf-8"),
           report, overwrite=True)
    if claude_settings:
        _claude_settings(root, report)
    if install:
        _install(root, spec or f"margi=={__version__}", report)
    _margi_dir(root, report)

    if not commit:
        return report
    if not has_git:
        report.skipped.append("commits (no git repository)")
        return report

    human_paths = [CONFIG_NAME, ".agents/skills", ".claude", ".githooks", ".github/workflows/margi-guard.yml",
                   "pyproject.toml", "uv.lock", *created]
    paths = [p for p in human_paths if (root / p).exists() or (root / p).is_symlink()]
    if "AGENTS.md (margi section removed)" in report.written and git("ls-files", "--", "AGENTS.md", cwd=root).strip():
        paths.append("AGENTS.md")  # stages the edit, or the deletion when nothing else was in it
    git("add", "-A", "--", *paths, cwd=root)
    if git("diff", "--cached", "--name-only", cwd=root).split():
        subject = f"chore: update margi {__version__}" if installed else f"chore: install margi {__version__}"
        if claude_settings:
            subject += f" (protect_thesis: {str(bool(load(root)['protect_thesis'])).lower()})"
        git("commit", "-q", "-m", subject, cwd=root)
        report.commits.append(git("rev-parse", "--short", "HEAD", cwd=root).strip())
    sha = bot_commit(load(root), "init")
    if sha:
        report.commits.append(sha[:7])
    return report
