"""Completeness of the project documentation in margi/docs/.

Required fields are the ``## `` headings of the docs templates. A field counts as
filled when its body contains real text (not just the placeholder or HTML comments).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from .resources import skills_dir

PLACEHOLDER = "_not yet documented_"
SCORED_DOCS = ["research-question.md", "dataset.md", "method.md", "field.md", "structure.md", "constraints.md"]
ALL_DOCS = SCORED_DOCS + ["open-questions.md", "CHANGELOG.md"]

_COMMENT = re.compile(r"<!--.*?-->", re.S)


def templates_dir() -> Path:
    return skills_dir() / "margi-propose" / "templates"


def split_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current = None
    buf: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(buf)
            current = line[3:].strip()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf)
    return sections


def is_filled(body: str) -> bool:
    body = _COMMENT.sub("", body).replace(PLACEHOLDER, "")
    return bool(body.strip())


@dataclass
class DocsReport:
    filled: int = 0
    required: int = 0
    missing: dict[str, list[str]] = field(default_factory=dict)

    @property
    def completeness(self) -> float:
        return round(self.filled / self.required, 3) if self.required else 0.0


def check(docs_dir: Path) -> DocsReport:
    report = DocsReport()
    for name in SCORED_DOCS:
        template = templates_dir() / name
        required = list(split_sections(template.read_text(encoding="utf-8")))
        path = docs_dir / name
        actual = split_sections(path.read_text(encoding="utf-8")) if path.exists() else {}
        for heading in required:
            report.required += 1
            if is_filled(actual.get(heading, "")):
                report.filled += 1
            else:
                report.missing.setdefault(name, []).append(heading)
    return report


def docs_hash(docs_dir: Path) -> str | None:
    if not docs_dir.is_dir():
        return None
    h = hashlib.sha256()
    for path in sorted(docs_dir.glob("*.md")):
        h.update(path.name.encode() + b"\0" + path.read_bytes() + b"\0")
    return h.hexdigest()
