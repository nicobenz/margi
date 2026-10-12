"""`margi save`: commit the student's own work, on their behalf and with their consent.

margi never saves the thesis on its own. When a run finds unsaved changes outside margi/, it
prints a summary of exactly what would be saved, with a hash of that state. The agent then runs
`uv run margi save --expect <hash>`, which Claude Code asks the student to approve (it is on the
`ask` list in .claude/settings.json). Approving is the consent. If anything changed between the
summary and the approval, the hash no longer matches and nothing is saved.

Saves are committed under the identity in thesis.config.yml (`author`), never as the bot, with a
fixed message margi generates and a `Margi-Save:` trailer. With a remote, the save is pushed; a
failed push leaves the local save in place.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass, field

from .config import PLACEHOLDER, Config
from .gitutil import GitError, file_at_head, git, git_bytes, staged_changes, worktree_changes
from .guard import CommitInfo, check_commit, in_margi

TRAILER = "Margi-Save"
MAX_LISTED = 8
# Files `margi init` writes outside margi/: grouped as one line instead of listed one by one.
SETUP = (".agents/", ".claude/", ".githooks/", ".github/workflows/margi-guard.yml", "pyproject.toml", "uv.lock",
         ".gitignore")
BIB_ENTRY = re.compile(r"^\s*@(?!comment|string|preamble)\w+\s*[{(]", re.I | re.M)


class SaveError(RuntimeError):
    pass


@dataclass
class Item:
    path: str
    kind: str  # new | changed | deleted | renamed
    orig: str | None = None
    chars: int | None = None  # change in characters, text files only
    entries: int | None = None  # change in bibliography entries, .bib only


@dataclass
class Pending:
    items: list[Item] = field(default_factory=list)
    digest: str = ""

    @property
    def paths(self) -> list[str]:
        return [p for i in self.items for p in (i.path, i.orig) if p]

    @property
    def chars(self) -> int:
        return sum(i.chars or 0 for i in self.items)


@dataclass
class SaveResult:
    sha: str
    files: int
    remote: str | None = None
    pushed: bool = False
    push_error: str | None = None


def _text(data: bytes | None) -> str | None:
    if data is None or b"\0" in data[:8000]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _read(cfg: Config, path: str) -> bytes | None:
    p = cfg.root / path
    return p.read_bytes() if p.is_file() else None


def pending(cfg: Config) -> Pending:
    """Unsaved changes outside margi/, and a digest of exactly that state."""
    out = Pending()
    h = hashlib.sha256()
    for c in sorted(worktree_changes(cfg.root), key=lambda c: c.path):
        if in_margi(c.path) and not (c.orig_path and not in_margi(c.orig_path)):
            continue
        now = None if c.status == "D" else _read(cfg, c.path)
        before = file_at_head(cfg.root, c.orig_path or c.path)
        kind = ("new" if c.status in ("?", "A") else "deleted" if c.status == "D"
                else "renamed" if c.status in ("R", "C") else "changed")
        item = Item(c.path, kind, c.orig_path if kind == "renamed" else None)
        new_t, old_t = _text(now), _text(before)
        if kind != "deleted" and new_t is not None and (old_t is not None or before is None):
            item.chars = len(new_t) - len(old_t or "")
            if c.path.endswith(".bib"):
                item.entries = len(BIB_ENTRY.findall(new_t)) - len(BIB_ENTRY.findall(old_t or ""))
        out.items.append(item)
        for p in (c.path, c.orig_path):
            if p:
                data = _read(cfg, p) if p == c.path and c.status != "D" else None
                h.update(f"{p}\0{hashlib.sha256(data).hexdigest() if data is not None else '-'}\n".encode())
    out.digest = h.hexdigest()[:16] if out.items else ""
    return out


def _n(n: int, word: str, plural: str | None = None) -> str:
    return f"{n:,} {word if n == 1 else plural or word + 's'}"


def _signed(n: int, word: str, plural: str | None = None) -> str:
    return f"{'+' if n >= 0 else '−'}{_n(abs(n), word, plural)}"


def _detail(i: Item) -> str:
    if i.kind == "deleted":
        return "deleted"
    if i.entries:
        return _signed(i.entries, "entry", "entries")
    if i.kind == "new":
        return "new file"
    tail = f"renamed from {i.orig}" if i.kind == "renamed" else ""
    if i.chars:
        return f"{_signed(i.chars, 'char')}{' · ' + tail if tail else ''}"
    return tail or "changed"


def _is_setup(path: str) -> bool:
    return any(path == s or path.startswith(s) for s in SETUP)


def remote(cfg: Config) -> tuple[str, str] | None:
    """(remote name, short label such as github.com/user/thesis) of the remote saves go to, or None."""
    if not cfg.has_git:
        return None
    names = git("remote", cwd=cfg.root, check=False).split()
    if not names:
        return None
    upstream = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", cwd=cfg.root, check=False).strip()
    name = upstream.split("/", 1)[0] if upstream and upstream.split("/", 1)[0] in names else (
        "origin" if "origin" in names else names[0])
    url = git("remote", "get-url", name, cwd=cfg.root, check=False).strip()
    return name, label(url) or name


def label(url: str) -> str:
    """github.com/user/thesis for https, ssh and scp-style URLs; credentials and .git dropped."""
    m = re.match(r"^(?:[a-z+]+://)?(?:[^@/]+@)?([^/:]+)(?::\d+)?[:/](.+?)(?:\.git)?/?$", url.strip())
    return f"{m.group(1)}/{m.group(2)}" if m else ""


def prompt(cfg: Config, p: Pending | None = None) -> str:
    """The fixed text the agent shows when a run needs a save. Written by margi, never by the agent."""
    p = p or pending(cfg)
    listed = [i for i in p.items if not _is_setup(i.path)]
    setup = [i for i in p.items if _is_setup(i.path)]
    width = max([len(i.path) for i in listed[:MAX_LISTED]] + [len("margi setup")])
    lines = ["Your thesis has changes that aren't saved yet. margi only gives feedback on a saved version."]
    lines += [f"  {i.path:<{width}}  {_detail(i)}" for i in listed[:MAX_LISTED]]
    if len(listed) > MAX_LISTED:
        lines.append(f"  + {len(listed) - MAX_LISTED} more")
    if setup:
        lines.append(f"  {'margi setup':<{width}}  {_n(len(setup), 'file')}")
    r = remote(cfg)
    lines.append("Saving makes a version under your name (a git commit) "
                 + (f"and uploads it to {r[1]}." if r else "that stays on this computer."))
    if cfg.author[0] == PLACEHOLDER[0] and counts(cfg)[0] == 0:
        lines.append(f'Your saves are recorded as "{PLACEHOLDER[0]}". To use your name, tell your agent, or write it '
                     "into thesis.config.yml under author: yourself.")
    lines.append(f"To save, run: uv run margi save --expect {p.digest}")
    return "\n".join(lines)


def subject(p: Pending) -> str:
    chars = p.chars
    return f"save: {_n(len(p.items), 'file')}" + (f", {_signed(chars, 'char')}" if chars else "")


def save(cfg: Config, expect: str, *, push: bool = True) -> SaveResult:
    """Commit exactly the state the summary showed, as the student; push when there is a remote."""
    if not cfg.has_git:
        raise SaveError("this project is not a git repository; run `uv run margi init` first")
    p = pending(cfg)
    if not p.items:
        raise SaveError("nothing to save: the thesis has no unsaved changes")
    if p.digest != expect:
        raise SaveError("the files changed since the summary, so nothing was saved. Here is what would be saved now:\n\n"
                        + prompt(cfg, p))
    already = [c.path for c in staged_changes(cfg.root)]
    git("add", "-A", "--", *p.paths, cwd=cfg.root)
    message = f"{subject(p)}\n\n{TRAILER}: {p.digest}\n"
    name, email = cfg.author
    info = CommitInfo("save", message, name, email, staged_changes(cfg.root))
    problems = check_commit(info, cfg, lambda path: git_bytes("show", f":{path}", cwd=cfg.root))
    if problems:
        git("reset", "-q", "--", *[x for x in p.paths if x not in already], cwd=cfg.root, check=False)
        raise SaveError("cannot save:\n  " + "\n  ".join(problems))
    try:
        git("commit", "-q", "-F", "-", cwd=cfg.root, input=message.encode(), env=cfg.author_env())
    except GitError as e:
        raise SaveError(f"git could not save:\n  {e}") from e
    result = SaveResult(sha=git("rev-parse", "HEAD", cwd=cfg.root).strip(), files=len(p.items))
    r = remote(cfg)
    if r and push:
        result.remote = r[1]
        result.push_error = _push(cfg, r[0])
        result.pushed = result.push_error is None
    return result


def _push(cfg: Config, name: str) -> str | None:
    """Push the current branch; the reason on failure. Never waits for a password or passphrase."""
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
    has_upstream = git("rev-parse", "--abbrev-ref", "@{u}", cwd=cfg.root, check=False).strip()
    args = ["push", "-q"] if has_upstream else ["push", "-q", "-u", name, "HEAD"]
    try:
        proc = subprocess.run(["git", *args], cwd=cfg.root, env=env, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        return "no answer from the remote within 90 seconds"
    if proc.returncode == 0:
        return None
    lines = [ln.strip() for ln in proc.stderr.splitlines() if ln.strip() and not ln.startswith("hint:")]
    return (lines[0].removeprefix("fatal: ").removeprefix("error: ") if lines else "git push failed")[:200]


def last_save(cfg: Config) -> str | None:
    """ISO date of the newest commit outside margi/ (a save, or a commit the student made themselves)."""
    if not cfg.has_git:
        return None
    out = git("log", "-1", "--format=%cI", "--", ".", ":(exclude)margi", cwd=cfg.root, check=False).strip()
    return out or None


def counts(cfg: Config) -> tuple[int, int]:
    """(versions saved through margi, all versions of the thesis): commits outside margi/, without
    the setup commits `margi init` makes ("chore: install/update margi …")."""
    if not cfg.has_git or not git("rev-parse", "--verify", "-q", "HEAD", cwd=cfg.root, check=False).strip():
        return 0, 0
    out = git("log", "--no-merges", f"--format=%s%x1f%(trailers:key={TRAILER},valueonly)%x00", "--", ".",
              ":(exclude)margi", cwd=cfg.root, check=False)
    entries = [e.lstrip("\n").split("\x1f", 1) for e in out.split("\0")[:-1]]
    entries = [e for e in entries if not re.match(r"chore: (install|update) margi ", e[0])]
    return sum(1 for e in entries if len(e) > 1 and e[1].strip()), len(entries)
