"""Thin wrappers around the git CLI."""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path


class GitError(RuntimeError):
    pass


def git(*args: str, cwd: Path | str | None = None, check: bool = True, input: bytes | None = None) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, input=input)
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {proc.stderr.decode(errors='replace').strip()}")
    return proc.stdout.decode(errors="replace")


def git_bytes(*args: str, cwd: Path | str | None = None) -> bytes:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True)
    if proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {proc.stderr.decode(errors='replace').strip()}")
    return proc.stdout


def repo_root(start: Path | str | None = None) -> Path:
    try:
        return Path(git("rev-parse", "--show-toplevel", cwd=start).strip())
    except (GitError, FileNotFoundError) as e:
        raise GitError("not inside a git repository") from e


def is_repo(path: Path | str) -> bool:
    """True if ``path`` is the top level of a git work tree (and git is installed)."""
    try:
        return repo_root(path).resolve() == Path(path).resolve()
    except GitError:
        return False


def project_root(start: Path, marker: str) -> Path:
    """The git top level; without git, the nearest directory containing ``marker``, else ``start``."""
    try:
        return repo_root(start)
    except GitError:
        pass
    for d in (start, *start.parents):
        if (d / marker).exists():
            return d
    return start


def head_sha(root: Path) -> str | None:
    out = git("rev-parse", "--verify", "-q", "HEAD", cwd=root, check=False).strip()
    return out or None


def file_at_head(root: Path, path: str) -> bytes | None:
    proc = subprocess.run(["git", "show", f"HEAD:{path}"], cwd=root, capture_output=True)
    return proc.stdout if proc.returncode == 0 else None


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class Change:
    status: str  # first letter: A, M, D, R, C, T, ? (untracked)
    path: str
    orig_path: str | None = None


def worktree_changes(root: Path) -> list[Change]:
    """All staged, unstaged and untracked (non-ignored) changes."""
    out = git("status", "--porcelain=v1", "-z", "--untracked-files=all", cwd=root)
    entries = out.split("\0")
    changes: list[Change] = []
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if not entry:
            continue
        xy, path = entry[:2], entry[3:]
        orig = None
        if "R" in xy or "C" in xy:
            orig = entries[i]
            i += 1
        if xy == "??":
            status = "?"
        else:
            # prefer the more significant of index / worktree status
            status = next((c for c in xy if c in "DRCAMT"), xy.strip()[:1] or "M")
        changes.append(Change(status, path, orig))
    return changes


def parse_name_status(out: str) -> list[Change]:
    """Parse `git diff --name-status -z` output."""
    parts = out.split("\0")
    changes: list[Change] = []
    i = 0
    while i < len(parts):
        code = parts[i]
        i += 1
        if not code:
            continue
        letter = code[0]
        if letter in "RC":
            orig, path = parts[i], parts[i + 1]
            i += 2
            changes.append(Change(letter, path, orig))
        else:
            changes.append(Change(letter, parts[i]))
            i += 1
    return changes


def staged_changes(root: Path) -> list[Change]:
    return parse_name_status(git("diff", "--cached", "--name-status", "-z", "-M", cwd=root))
