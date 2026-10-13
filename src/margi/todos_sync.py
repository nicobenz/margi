"""Todos: accepted work items that live in margi/, optionally mirrored to GitHub issues.

  margi/todos/proposed/<id>-<slug>.md   status: proposed | accepted   (margi's suggestions)
  margi/todos/open/<id>-<slug>.md       accepted todos
  margi/todos/done/<id>-<slug>.md       finished: done_at, done_by (student | margi | github), note
  margi/todos/close/<todo-id>.md        status: proposed | accepted   (margi's closure proposals)
  margi/todos/synced/                   legacy: todos that reached GitHub before todos were local

Only files with ``status: accepted`` are applied. Acceptance is the human's decision. GitHub is
used only when ``github.sync`` is on (see ``github_sync``).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .config import MARGI_DIR, Config

TODOS = f"{MARGI_DIR}/todos"


class SyncError(RuntimeError):
    pass


@dataclass
class SyncReport:
    opened: list[str] = field(default_factory=list)
    created: list[tuple[str, int]] = field(default_factory=list)
    reused: list[tuple[str, int]] = field(default_factory=list)
    closed: list[int] = field(default_factory=list)  # issues closed on GitHub by margi
    done: list[str] = field(default_factory=list)  # todos moved to done/


def read_md(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


def write_md(path: Path, meta: dict, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    front = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    path.write_text(f"---\n{front}\n---\n{body.lstrip()}", encoding="utf-8")


def _gh(*args: str) -> str:
    if not shutil.which("gh"):
        raise SyncError("the GitHub CLI `gh` is not installed or not on PATH (https://cli.github.com)")
    proc = subprocess.run(["gh", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise SyncError(f"gh {' '.join(args[:2])} failed: {proc.stderr.strip()}")
    return proc.stdout


def marker(todo_id: str) -> str:
    return f"<!-- margi-id: {todo_id} -->"


def list_items(cfg: Config, kind: str) -> list[tuple[Path, dict, str]]:
    d = cfg.root / TODOS / kind
    return [(p, *read_md(p)) for p in sorted(d.glob("*.md"))] if d.is_dir() else []


def github_sync(cfg: Config) -> bool:
    """``github.sync`` from the config; without the key, on only if todos already went to GitHub."""
    gh = cfg.get("github") or {}
    if "sync" in gh:
        return bool(gh["sync"])
    synced = cfg.root / TODOS / "synced"
    return synced.is_dir() and any(synced.glob("*.md"))


def todo_items(cfg: Config) -> list[dict]:
    """Every todo with its state: proposed, open or done (closure proposals as kind "close")."""
    out = []
    for kind in ("proposed", "open", "synced", "done", "close"):
        for path, meta, body in list_items(cfg, kind):
            state = {"proposed": "proposed", "open": "open", "done": "done", "close": "close"}.get(kind)
            if kind == "synced":
                state = "done" if meta.get("status") == "closed" or path.name.startswith("closed-") else "open"
            comments = meta.get("comments") or []
            out.append({
                "kind": kind, "state": state, "path": path, "body": body,
                "id": str(meta.get("id") or meta.get("todo") or path.stem),
                "title": str(meta.get("title") or path.stem),
                "status": str(meta.get("status") or state),
                "section": str(meta["section"]) if meta.get("section") is not None else None,
                "comments": [str(c) for c in (comments if isinstance(comments, list) else [comments])],
                "issue": meta.get("issue"),
                "todo": str(meta["todo"]) if meta.get("todo") else None,
                "done_at": meta.get("done_at") or meta.get("closed_at"),
                "done_by": meta.get("done_by") or ("github" if kind == "synced" and state == "done" else None),
                "note": meta.get("note"),
                "file": path.relative_to(cfg.root).as_posix(),
            })
    return out


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _finish(cfg: Config, path: Path, meta: dict, body: str, by: str, now: str, **extra) -> None:
    meta.update(status="done", done_at=now, done_by=by, **{k: v for k, v in extra.items() if v})
    write_md(cfg.root / TODOS / "done" / path.name, meta, body)
    path.unlink()


def sync_accepted(cfg: Config) -> SyncReport:
    """Apply what the student accepted: proposals become open todos (and issues, with sync on),
    accepted closures finish their todo; with sync on, todos whose issue was closed on GitHub finish."""
    report = SyncReport()
    sync = github_sync(cfg)
    label = cfg["github"]["label"]
    now = _now()
    proposed = [(p, m, b) for p, m, b in list_items(cfg, "proposed") if m.get("status") == "accepted"]
    closures = [(p, m, b) for p, m, b in list_items(cfg, "close") if m.get("status") == "accepted"]
    open_items = list_items(cfg, "open") + [x for x in list_items(cfg, "synced") if x[1].get("status") != "closed"
                                            and not x[0].name.startswith("closed-")]
    if not proposed and not closures and not (sync and any(m.get("issue") for _, m, _ in open_items)):
        return report

    existing = []
    if sync:
        subprocess.run(["gh", "label", "create", label, "--color", "8B5CF6", "--description", "margi todo", "--force"],
                       capture_output=True)
        existing = json.loads(_gh("issue", "list", "--label", label, "--state", "all", "--limit", "500",
                                  "--json", "number,body,state") or "[]")

    for path, meta, body in proposed:
        tid = str(meta.get("id") or path.stem)
        if sync:
            number = next((i["number"] for i in existing if marker(tid) in (i.get("body") or "")), None)
            if number is None:
                sources = ", ".join(meta.get("comments") or meta.get("source") or []) \
                    if isinstance(meta.get("comments") or meta.get("source"), list) else meta.get("source")
                issue_body = body.strip() + "\n\n---\n_Proposed by margi" + (f" from {sources}" if sources else "") + f"_\n{marker(tid)}\n"
                labels = [label] + [str(lbl) for lbl in meta.get("labels") or [] if str(lbl) != label]
                args = ["issue", "create", "--title", str(meta.get("title") or tid), "--body", issue_body]
                for lbl in labels:
                    args += ["--label", lbl]
                url = _gh(*args).strip().splitlines()[-1]
                number = int(url.rstrip("/").rsplit("/", 1)[-1])
                report.created.append((tid, number))
            else:
                report.reused.append((tid, number))
            meta.update(issue=number, synced_at=now)
        meta.update(status="open", accepted_at=now)
        write_md(cfg.root / TODOS / "open" / path.name, meta, body)
        path.unlink()
        report.opened.append(tid)

    by_id = {str(m.get("id") or p.stem): (p, m, b) for p, m, b in list_items(cfg, "open") + open_items}
    by_issue = {m.get("issue"): (p, m, b) for p, m, b in by_id.values() if m.get("issue")}
    for path, meta, body in closures:
        target = by_id.get(str(meta["todo"])) if meta.get("todo") else by_issue.get(int(meta.get("issue") or path.stem))
        number = (target[1].get("issue") if target else None) or (meta.get("issue") if not meta.get("todo") else None)
        if sync and number:
            _gh("issue", "close", str(number), "--comment", body.strip() + "\n\n_Closed after human review via margi._")
            report.closed.append(int(number))
        if target:
            tpath, tmeta, tbody = target
            if tpath.exists():
                _finish(cfg, tpath, tmeta, tbody, "margi", now, evidence=body.strip())
                report.done.append(str(tmeta.get("id") or tpath.stem))
        path.unlink()

    if sync:
        closed = {i["number"] for i in existing if str(i.get("state", "")).upper() == "CLOSED"}
        for tid, (path, meta, body) in list(by_id.items()):
            if path.exists() and meta.get("issue") in closed:
                _finish(cfg, path, meta, body, "github", now)
                report.done.append(tid)
    return report


def todo_done(cfg: Config, ids: list[str], note: str | None = None, *, commit: bool = True) -> tuple[list[Path], str | None]:
    """The student marks open todos done. The note is their own words, stored verbatim."""
    from .finalize import FinalizeError, ensure_clean
    from .gitutil import GitError, git
    from .guard import PREFIX

    try:
        ensure_clean(cfg)
    except FinalizeError as e:
        raise SyncError(str(e)) from e
    if not ids:
        raise SyncError("name at least one todo, e.g. t20261007-01")
    items = {t["id"]: t for t in todo_items(cfg) if t["state"] == "open"}
    unknown = [i for i in ids if i not in items]
    if unknown:
        raise SyncError(f"no open todo {', '.join(unknown)} (see the Todos tab or margi/todos/open/)")
    if note and len(note) > 600:
        raise SyncError(f"the note has {len(note)} characters (at most 600)")
    sync = github_sync(cfg)
    now = _now()
    moved = []
    for tid in dict.fromkeys(ids):
        t = items[tid]
        meta, body = read_md(t["path"])
        if sync and meta.get("issue"):
            _gh("issue", "close", str(meta["issue"]), "--comment", "_Marked done by the student via margi._")
        _finish(cfg, t["path"], meta, body, "student", now, note=note)
        moved.append(cfg.root / TODOS / "done" / t["path"].name)

    from .dashboard import refresh

    refresh(cfg)
    if not (commit and cfg.has_git):
        return moved, None
    try:
        git("add", "-A", "--", MARGI_DIR, cwd=cfg.root)
        git("commit", "-q", "-m", f"{PREFIX} todo done {' '.join(dict.fromkeys(ids))}", cwd=cfg.root,
            env=cfg.author_env())
    except GitError as e:
        raise SyncError(f"the todos were moved but not committed:\n  {e}") from e
    return moved, git("rev-parse", "HEAD", cwd=cfg.root).strip()
