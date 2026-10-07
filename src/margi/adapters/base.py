"""Format adapter interface: map a thesis to a section tree with file/line ranges."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..config import Config


@dataclass
class Segment:
    file: str  # repo-relative
    line_start: int  # 1-based, inclusive
    line_end: int  # inclusive


@dataclass
class Section:
    id: str  # "2.1"
    title: str
    level: int
    segments: list[Segment] = field(default_factory=list)  # own text incl. heading line, excl. children
    own_chars: int = 0
    children: list["Section"] = field(default_factory=list)

    @property
    def total_chars(self) -> int:
        return self.own_chars + sum(c.total_chars for c in self.children)

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def full_range(self) -> list[Segment]:
        """Segments of this section and all descendants, merged per file."""
        segs = [s for sec in self.walk() for s in sec.segments]
        merged: list[Segment] = []
        for s in segs:
            if merged and merged[-1].file == s.file and s.line_start <= merged[-1].line_end + 1:
                merged[-1].line_end = max(merged[-1].line_end, s.line_end)
            else:
                merged.append(Segment(s.file, s.line_start, s.line_end))
        return merged


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def count(text: str, mode: str) -> int:
    if mode == "words":
        return len(text.split())
    if mode == "chars_no_spaces":
        return len(re.sub(r"\s+", "", text))
    return len(re.sub(r"\s+", " ", text).strip())


class Adapter:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.root: Path = cfg.root

    def tree(self) -> Section:
        """Root pseudo-section (id "", level 0) holding the document tree."""
        raise NotImplementedError

    def resolve(self, query: str) -> Section | None:
        """Find a section by number ("2.1"), configured alias, or (partial) title."""
        root = self.tree()
        sections = [s for s in root.walk() if s.level > 0]
        alias = self.cfg.get("sections", {}).get(query)
        if isinstance(alias, dict) and alias.get("heading"):
            query = alias["heading"]
        for s in sections:
            if s.id == query:
                return s
        q = slug(query)
        for s in sections:
            if slug(s.title) == q:
                return s
        partial = [s for s in sections if q and q in slug(s.title)]
        return partial[0] if len(partial) == 1 else None
