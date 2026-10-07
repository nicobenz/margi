"""`margi outline`: character distribution across sections and subsections.

Targets come from an optional ```yaml block in margi/docs/structure.md:

    ```yaml
    # margi-structure
    - title: Introduction
      target: 10%          # share of total, or an absolute count like 6000
    - title: Prior Work
      target: 25%
      children:
        - title: Distant Reading
    ```
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .adapters import Section, get_adapter
from .adapters.base import slug
from .config import MARGI_DIR, Config


@dataclass
class Row:
    depth: int
    id: str
    title: str
    chars: int
    share: float
    target: str | None = None
    planned_only: bool = False
    children: list["Row"] = field(default_factory=list)


def load_plan(cfg: Config) -> list[dict]:
    path = cfg.root / MARGI_DIR / "docs" / "structure.md"
    if not path.exists():
        return []
    text = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.S)
    for block in re.findall(r"```ya?ml\n(.*?)```", text, re.S):
        if "margi-structure" in block:
            data = yaml.safe_load(block) or []
            return data if isinstance(data, list) else []
    return []


def _target_str(target, total: int) -> str | None:
    if target is None:
        return None
    if isinstance(target, str) and target.strip().endswith("%"):
        return f"target {target.strip()}"
    try:
        return f"target {int(target):,}".replace(",", " ")
    except (TypeError, ValueError):
        return f"target {target}"


def build_rows(section: Section, plan: list[dict], total: int, depth: int = 0) -> list[Row]:
    rows: list[Row] = []
    remaining = list(plan)
    for child in section.children:
        match = next((p for p in remaining if slug(str(p.get("title", ""))) == slug(child.title)), None)
        if match:
            remaining.remove(match)
        row = Row(
            depth=depth,
            id=child.id,
            title=child.title,
            chars=child.total_chars,
            share=child.total_chars / total if total else 0.0,
            target=_target_str((match or {}).get("target"), total),
        )
        row.children = build_rows(child, (match or {}).get("children") or [], total, depth + 1)
        rows.append(row)
    for p in remaining:
        row = Row(depth, "", str(p.get("title", "?")), 0, 0.0, _target_str(p.get("target"), total), planned_only=True)
        row.children = [
            Row(depth + 1, "", str(c.get("title", "?")), 0, 0.0, _target_str(c.get("target"), total), True)
            for c in p.get("children") or []
        ]
        rows.append(row)
    return rows


def compute(cfg: Config) -> tuple[Section, list[Row]]:
    tree = get_adapter(cfg).tree()
    rows = build_rows(tree, load_plan(cfg), tree.total_chars)
    return tree, rows


def render(tree: Section, rows: list[Row], unit: str, width: int = 20) -> str:
    flat: list[tuple[str, Row]] = []

    def walk(rs: list[Row], prefix: str) -> None:
        for i, r in enumerate(rs):
            last = i == len(rs) - 1
            flat.append((prefix + ("└ " if last else "├ "), r))
            walk(r.children, prefix + ("  " if last else "│ "))

    walk(rows, "")
    labels = [f"{p}{(r.id + ' ') if r.id else ''}{r.title}" for p, r in flat]
    lw = max([len("Thesis")] + [len(lbl) for lbl in labels]) + 2
    fmt_n = lambda n: f"{n:,}".replace(",", " ")  # noqa: E731
    nw = max(len(fmt_n(tree.total_chars)), 5)
    lines = [f"{'Thesis'.ljust(lw)}{fmt_n(tree.total_chars).rjust(nw)}  100%   ({unit})"]
    if tree.own_chars:
        lines.append(f"{'(front matter)'.ljust(lw)}{fmt_n(tree.own_chars).rjust(nw)}")
    for label, (_, r) in zip(labels, flat):
        bar = "█" * round(r.share * width)
        note = " (planned)" if r.planned_only else ""
        if r.target:
            note = f"  ({r.target}){note}" if not r.planned_only else f"  ({r.target}, planned)"
        pct = f"{round(r.share * 100):>3}%"
        lines.append(f"{label.ljust(lw)}{fmt_n(r.chars).rjust(nw)}  {pct} {bar.ljust(width)}{note}".rstrip())
    return "\n".join(lines)


def snapshot_draft(tree: Section, rows: list[Row], unit: str) -> dict:
    def ser(rs: list[Row]) -> list[dict]:
        return [
            {
                "id": r.id,
                "title": r.title,
                "chars": r.chars,
                "share": round(r.share, 4),
                **({"target": r.target} if r.target else {}),
                **({"planned_only": True} if r.planned_only else {}),
                **({"children": ser(r.children)} if r.children else {}),
            }
            for r in rs
        ]

    files = sorted({seg.file for s in tree.walk() for seg in s.segments})
    return {
        "command": "outline",
        "scope": "all",
        "summary": f"{tree.total_chars} {unit} across {sum(1 for s in tree.walk() if s.level)} sections",
        "files_read": files,
        "payload": {"unit": unit, "total": tree.total_chars, "front_matter": tree.own_chars, "sections": ser(rows)},
    }


def write_snapshot(cfg: Config, draft: dict) -> Path:
    staging = cfg.root / MARGI_DIR / ".staging"
    staging.mkdir(parents=True, exist_ok=True)
    path = staging / "outline.json"
    path.write_text(json.dumps(draft, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
