"""Typst adapter.

Follows ``#include "..."`` from the main file, builds the heading tree (``=``, ``==``, ...)
with default hierarchical numbering, and counts prose characters per section.

Prose extraction is a heuristic: comments, raw blocks, math, code lines (``#set``, ``#show``,
``#let``, ``#import``, multi-line function calls) and function arguments are dropped; content
blocks (``#emph[...]``) are kept; labels, references and markup characters are removed.
Heading lines themselves are not counted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .base import Adapter, Section, Segment, count

HEADING = re.compile(r"^\s*(=+)\s+(.*?)\s*(<[\w:.-]+>)?\s*$")
INCLUDE = re.compile(r'^\s*#include\s+"([^"]+)"\s*$')
CODE_LINE = re.compile(r"^\s*#(set|show|import|let|include|pagebreak|outline|bibliography|v|h|align|place)\b")
LABEL = re.compile(r"<[\w:.-]+>")
REF = re.compile(r"@[\w:.-]+")
LINE_COMMENT = re.compile(r"(?<![:/])//.*$")


@dataclass
class Line:
    file: str
    lineno: int
    text: str


class TypstAdapter(Adapter):
    def lines(self) -> list[Line]:
        main = self.root / self.cfg["main"]
        if not main.exists():
            raise FileNotFoundError(f"main file not found: {self.cfg['main']} (set `main` in thesis.config.yml)")
        out: list[Line] = []
        self._expand(main, out, seen=set())
        return out

    def _expand(self, path: Path, out: list[Line], seen: set[Path]) -> None:
        path = path.resolve()
        if path in seen:
            return
        seen = seen | {path}
        rel = path.relative_to(self.root.resolve()).as_posix()
        for i, text in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            m = INCLUDE.match(text)
            if m:
                out.append(Line(rel, i, ""))
                target = (path.parent / m.group(1))
                if target.exists():
                    self._expand(target, out, seen)
                continue
            out.append(Line(rel, i, text))

    def tree(self) -> Section:
        root = Section(id="", title="Thesis", level=0)
        stack: list[Section] = [root]
        counters: list[int] = []
        mode = self.cfg.get("count", "chars")
        state = _ProseState()

        for line in self.lines():
            if state.in_raw or state.in_block_comment or state.code_depth or state.in_math:
                prose = state.consume(line.text)
            else:
                m = HEADING.match(line.text)
                if m:
                    level = len(m.group(1))
                    counters = (counters + [0] * level)[:level]
                    counters[level - 1] += 1
                    sec = Section(
                        id=".".join(str(n) for n in counters),
                        title=m.group(2).strip(),
                        level=level,
                    )
                    while stack[-1].level >= level:
                        stack.pop()
                    stack[-1].children.append(sec)
                    stack.append(sec)
                    _add_line(sec, line)
                    continue
                prose = state.consume(line.text)
            current = stack[-1]
            _add_line(current, line)
            if prose.strip():
                current.own_chars += count(prose, mode) + (1 if mode == "chars" else 0)
        return root


def _add_line(sec: Section, line: Line) -> None:
    if sec.segments and sec.segments[-1].file == line.file and sec.segments[-1].line_end == line.lineno - 1:
        sec.segments[-1].line_end = line.lineno
    else:
        sec.segments.append(Segment(line.file, line.lineno, line.lineno))


class _ProseState:
    """Line-by-line prose extractor that tracks multi-line constructs."""

    def __init__(self) -> None:
        self.in_raw = False
        self.in_block_comment = False
        self.in_math = False
        self.code_depth = 0

    def consume(self, text: str) -> str:
        if text.strip().startswith("```"):
            self.in_raw = not self.in_raw
            return ""
        if self.in_raw:
            return ""
        text = self._strip_block_comments(text)
        if self.code_depth:
            self.code_depth = _depth_after(text, self.code_depth)
            return ""
        text = LINE_COMMENT.sub("", text)
        if CODE_LINE.match(text):
            self.code_depth = _depth_after(text, 0)
            return ""
        text = self._strip_math(text)
        text = self._strip_calls(text)
        text = LABEL.sub("", text)
        text = REF.sub("", text)
        text = re.sub(r"^\s*([-+]|/\s*[^:]*:)\s+", "", text)  # list / term markers
        text = re.sub(r"[*_`\\\[\]]", "", text)
        return text

    def _strip_block_comments(self, text: str) -> str:
        out = []
        i = 0
        while i < len(text):
            if self.in_block_comment:
                end = text.find("*/", i)
                if end < 0:
                    return "".join(out)
                self.in_block_comment = False
                i = end + 2
            else:
                start = text.find("/*", i)
                if start < 0:
                    out.append(text[i:])
                    break
                out.append(text[i:start])
                self.in_block_comment = True
                i = start + 2
        return "".join(out)

    def _strip_math(self, text: str) -> str:
        parts = re.split(r"(?<!\\)\$", text)
        out = [part for i, part in enumerate(parts) if not (self.in_math ^ (i % 2 == 1))]
        if (len(parts) - 1) % 2:
            self.in_math = not self.in_math
        return " ".join(out)

    def _strip_calls(self, text: str) -> str:
        """Drop `#fn` names and `(...)` args; keep `[...]` content."""
        out = []
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == "#" and i + 1 < len(text) and (text[i + 1].isalpha() or text[i + 1] == "_"):
                j = i + 1
                while j < len(text) and (text[j].isalnum() or text[j] in "_-."):
                    j += 1
                while j < len(text) and text[j] == "(":
                    depth = 0
                    k = j
                    while k < len(text):
                        if text[k] == "(":
                            depth += 1
                        elif text[k] == ")":
                            depth -= 1
                            if depth == 0:
                                break
                        k += 1
                    if depth:
                        self.code_depth = depth
                        return "".join(out)
                    j = k + 1
                i = j
                continue
            out.append(ch)
            i += 1
        return "".join(out)


def _depth_after(text: str, depth: int) -> int:
    for ch in text:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
    return depth
