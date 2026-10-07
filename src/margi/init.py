"""`margi init`: scaffold margi into a thesis repository.

Produces two commits so human and margi files never mix:
  1. "chore: install margi"  (your identity)  — skills, config, hooks, CI, agent settings
  2. "margi: init"           (margi bot)      — the margi/ directory with doc templates
"""

from __future__ import annotations

import json
import os
import shutil
import stat
from dataclasses import dataclass, field
from pathlib import Path

from . import __version__
from .config import CONFIG_NAME, MARGI_DIR, load
from .docs_check import ALL_DOCS, templates_dir
from .finalize import bot_commit
from .gitutil import git, staged_changes
from .resources import agents_md, skills_dir, templates_dir as tool_templates

SKILLS = ["margi", "margi-onboard", "margi-challenge"]
BEGIN, END = "<!-- margi:begin -->", "<!-- margi:end -->"


class InitError(RuntimeError):
    pass


@dataclass
class InitReport:
    written: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    commits: list[str] = field(default_factory=list)


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


def _agents_md(root: Path, report: InitReport) -> None:
    section = f"{BEGIN}\n{agents_md().read_text(encoding='utf-8').strip()}\n{END}\n"
    path = root / "AGENTS.md"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if BEGIN in text and END in text:
        pre, _, rest = text.partition(BEGIN)
        _, _, post = rest.partition(END)
        text = pre + section.rstrip("\n") + post
    else:
        text = (text.rstrip() + "\n\n" if text.strip() else "") + section
    path.write_text(text, encoding="utf-8")
    report.written.append("AGENTS.md")


def _claude_settings(root: Path, report: InitReport) -> None:
    path = root / ".claude" / "settings.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    template = json.loads((tool_templates() / "claude-settings.json").read_text(encoding="utf-8"))
    perms = data.setdefault("permissions", {})
    for key in ("allow", "deny"):
        merged = list(dict.fromkeys(perms.get(key, []) + template["permissions"][key]))
        perms[key] = merged
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    report.written.append(".claude/settings.json")


def _hook(root: Path, report: InitReport) -> None:
    hook = root / ".githooks" / "commit-msg"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text((tool_templates() / "commit-msg").read_text(encoding="utf-8"), encoding="utf-8")
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    report.written.append(".githooks/commit-msg")
    current = git("config", "--get", "core.hooksPath", cwd=root, check=False).strip()
    if current and current != ".githooks":
        raise InitError(f"core.hooksPath is already set to {current!r}; add .githooks/commit-msg there manually")
    git("config", "core.hooksPath", ".githooks", cwd=root)


def _margi_dir(root: Path, report: InitReport) -> None:
    m = root / MARGI_DIR
    for sub in ("feedback", "todos/proposed", "todos/close", "todos/synced", "docs"):
        (m / sub).mkdir(parents=True, exist_ok=True)
    for sub in ("feedback", "todos/proposed", "todos/close", "todos/synced"):
        keep = m / sub / ".gitkeep"
        if not keep.exists():
            keep.write_text("", encoding="utf-8")
    _write(root, f"{MARGI_DIR}/.gitignore", ".staging/\n.cache/\n", report, overwrite=True)
    for name in ALL_DOCS:
        _write(root, f"{MARGI_DIR}/docs/{name}", (templates_dir() / name).read_text(encoding="utf-8"), report, overwrite=False)
    _write(root, f"{MARGI_DIR}/README.md", (tool_templates() / "margi-README.md").read_text(encoding="utf-8"), report, overwrite=True)


def init(root: Path, *, commit: bool = True, claude_settings: bool = True, force_config: bool = False) -> InitReport:
    if staged_changes(root):
        raise InitError("you have staged changes; commit or unstage them before running `margi init`")
    report = InitReport()

    config = (tool_templates() / "thesis.config.yml").read_text(encoding="utf-8").replace("{{main}}", detect_main(root))
    _write(root, CONFIG_NAME, config, report, overwrite=force_config)
    _vendor_skills(root, report)
    _agents_md(root, report)
    _hook(root, report)
    _write(root, ".github/workflows/margi-guard.yml", (tool_templates() / "margi-guard.yml").read_text(encoding="utf-8"),
           report, overwrite=True)
    if claude_settings:
        _claude_settings(root, report)
    _margi_dir(root, report)

    if not commit:
        return report

    human_paths = [CONFIG_NAME, ".agents/skills", ".claude", "AGENTS.md", ".githooks", ".github/workflows/margi-guard.yml"]
    git("add", "-A", "--", *[p for p in human_paths if (root / p).exists() or (root / p).is_symlink()], cwd=root)
    if git("diff", "--cached", "--name-only", cwd=root).split():
        git("commit", "-q", "-m", f"chore: install margi {__version__}", cwd=root)
        report.commits.append(git("rev-parse", "--short", "HEAD", cwd=root).strip())
    sha = bot_commit(load(root), "init")
    if sha:
        report.commits.append(sha[:7])
    return report
