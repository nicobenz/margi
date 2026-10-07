"""Sync human-accepted todo files to GitHub issues via the `gh` CLI.

  margi/todos/proposed/<id>-<slug>.md   status: proposed | accepted
  margi/todos/close/<issue>.md          status: proposed | accepted   (closure proposals)
  margi/todos/synced/                   files that reached GitHub

Only files with ``status: accepted`` are touched. Acceptance is the human's decision.
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
    created: list[tuple[str, int]] = field(default_factory=list)
    reused: list[tuple[str, int]] = field(default_factory=list)
    closed: list[int] = field(default_factory=list)


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


def sync_accepted(cfg: Config) -> SyncReport:
    label = cfg["github"]["label"]
    report = SyncReport()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    proposed = [(p, m, b) for p, m, b in list_items(cfg, "proposed") if m.get("status") == "accepted"]
    closures = [(p, m, b) for p, m, b in list_items(cfg, "close") if m.get("status") == "accepted"]
    if not proposed and not closures:
        return report

    subprocess.run(["gh", "label", "create", label, "--color", "8B5CF6", "--description", "margi todo", "--force"],
                   capture_output=True)
    existing = json.loads(_gh("issue", "list", "--label", label, "--state", "all", "--limit", "500",
                              "--json", "number,body") or "[]")

    for path, meta, body in proposed:
        tid = str(meta.get("id") or path.stem)
        number = next((i["number"] for i in existing if marker(tid) in (i.get("body") or "")), None)
        if number is None:
            sources = ", ".join(meta.get("source") or []) if isinstance(meta.get("source"), list) else meta.get("source")
            issue_body = body.strip() + f"\n\n---\n_Proposed by margi" + (f" from {sources}" if sources else "") + f"_\n{marker(tid)}\n"
            labels = [label] + [str(lbl) for lbl in meta.get("labels") or [] if str(lbl) != label]
            args = ["issue", "create", "--title", str(meta.get("title") or tid), "--body", issue_body]
            for lbl in labels:
                args += ["--label", lbl]
            url = _gh(*args).strip().splitlines()[-1]
            number = int(url.rstrip("/").rsplit("/", 1)[-1])
            report.created.append((tid, number))
        else:
            report.reused.append((tid, number))
        meta.update(status="synced", issue=number, synced_at=now)
        write_md(cfg.root / TODOS / "synced" / path.name, meta, body)
        path.unlink()

    for path, meta, body in closures:
        number = int(meta.get("issue") or path.stem)
        _gh("issue", "close", str(number), "--comment", body.strip() + "\n\n_Closed after human review via margi._")
        meta.update(status="closed", closed_at=now)
        write_md(cfg.root / TODOS / "synced" / f"closed-{number}.md", meta, body)
        path.unlink()
        report.closed.append(number)
    return report
