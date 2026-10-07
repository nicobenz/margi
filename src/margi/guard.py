"""Enforce the separation between human commits and margi commits.

Rules (path-based):
  * a commit touches either only ``margi/**`` or nothing under ``margi/`` -- never both
  * commits touching ``margi/**`` must have a message starting with ``margi:``
  * commits outside ``margi/`` must not start with ``margi:`` and must not be authored by the bot
  * files in ``margi/feedback/`` are append-only: never modified, deleted or renamed
  * every new ``margi/feedback/*.json`` must be a valid record
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from . import schema
from .config import MARGI_DIR, Config
from .gitutil import Change, git, git_bytes, parse_name_status, staged_changes

PREFIX = "margi:"
FEEDBACK = f"{MARGI_DIR}/feedback/"


def in_margi(path: str) -> bool:
    return path == MARGI_DIR or path.startswith(MARGI_DIR + "/")


@dataclass
class CommitInfo:
    label: str
    message: str
    author_name: str
    author_email: str
    changes: list[Change]


def check_commit(info: CommitInfo, cfg: Config, read_blob) -> list[str]:
    """Return a list of violations. ``read_blob(path) -> bytes`` reads the new version of a file."""
    problems: list[str] = []
    paths = [c.path for c in info.changes] + [c.orig_path for c in info.changes if c.orig_path]
    inside = [p for p in paths if in_margi(p)]
    outside = [p for p in paths if not in_margi(p)]
    is_margi_msg = info.message.lstrip().startswith(PREFIX)
    is_bot = info.author_email == cfg.bot_email or info.author_name == cfg.bot_name

    if inside and outside:
        problems.append(
            "commit mixes margi/ files with other files; commit them separately.\n"
            f"    margi/: {', '.join(sorted(inside)[:5])}\n"
            f"    other : {', '.join(sorted(outside)[:5])}"
        )
    if inside and not is_margi_msg:
        problems.append(f"commit touches margi/ but the message does not start with '{PREFIX}'")
    if outside and is_margi_msg:
        problems.append(f"'{PREFIX}' commits may only touch margi/, found: {', '.join(sorted(outside)[:5])}")
    if outside and is_bot:
        problems.append(f"the margi bot ({cfg.bot_name}) may only commit inside margi/")

    for c in info.changes:
        touched = [c.path] + ([c.orig_path] if c.orig_path else [])
        if c.status != "A" and any(p.startswith(FEEDBACK) for p in touched):
            problems.append(f"margi/feedback is append-only: {c.status} {c.orig_path or c.path}")
        elif c.status == "A" and c.path.startswith(FEEDBACK) and c.path.endswith(".json"):
            try:
                record = json.loads(read_blob(c.path))
            except (ValueError, UnicodeDecodeError) as e:
                problems.append(f"{c.path}: not valid JSON ({e})")
                continue
            for err in schema.errors(record, "record"):
                problems.append(f"{c.path}: {err}")
    return problems


def _author_ident(root: Path) -> tuple[str, str]:
    ident = git("var", "GIT_AUTHOR_IDENT", cwd=root).strip()
    # "Name <email> 1700000000 +0100"
    name, _, rest = ident.partition(" <")
    email = rest.split(">", 1)[0]
    return name, email


def check_staged(root: Path, cfg: Config, message: str) -> list[str]:
    name, email = _author_ident(root)
    info = CommitInfo("staged", message, name, email, staged_changes(root))
    return check_commit(info, cfg, lambda p: git_bytes("show", f":{p}", cwd=root))


def check_range(root: Path, cfg: Config, rev_range: str) -> dict[str, list[str]]:
    shas = git("rev-list", "--no-merges", "--reverse", rev_range, cwd=root).split()
    results: dict[str, list[str]] = {}
    for sha in shas:
        fmt = git("show", "-s", "--format=%an%x00%ae%x00%B", sha, cwd=root)
        name, email, message = fmt.split("\0", 2)
        diff = git("diff-tree", "--root", "--no-commit-id", "-r", "-M", "--name-status", "-z", sha, cwd=root)
        info = CommitInfo(sha[:10], message, name, email, parse_name_status(diff))
        problems = check_commit(info, cfg, lambda p, s=sha: git_bytes("show", f"{s}:{p}", cwd=root))
        if problems:
            results[sha] = problems
    return results


def commit_msg_from_file(path: str | os.PathLike) -> str:
    lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(line for line in lines if not line.startswith("#"))
