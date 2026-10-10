"""Is a section ready to be graded? A deterministic check run before every grade.

A peer reviewer asked to comment on bullet points or placeholder text would say "write it first".
margi does the same: a section needs enough running prose, not mostly list items and no
placeholder text before a grade means anything. To-do markers are reported but don't block.

`grade.precheck` in thesis.config.yml decides what happens when a section isn't ready:
strict records it as not ready, ask lets the student grade it anyway (on record), none grades
without asking. The check itself always runs and is stored with every grade.
"""

from __future__ import annotations

from .adapters import get_adapter
from .adapters.base import Section
from .config import Config

MODES = ("strict", "ask", "none")


class ReadinessError(ValueError):
    pass


def mode(cfg: Config) -> str:
    m = str(cfg["grade"].get("precheck", "ask")).lower()
    if m not in MODES:
        raise ReadinessError(f"grade.precheck in thesis.config.yml must be one of {', '.join(MODES)}, not {m!r}")
    return m


def assess(section: Section, cfg: Config) -> dict:
    g = cfg["grade"]
    min_words, max_list = int(g.get("min_words", 150)), float(g.get("max_list_share", 0.5))
    secs = list(section.walk())
    words = sum(s.own_words for s in secs)
    lines = sum(s.own_lines for s in secs)
    share = round(sum(s.own_list_lines for s in secs) / lines, 2) if lines else 0.0
    placeholder = any(s.own_placeholder for s in secs)
    markers = list(dict.fromkeys(m for s in secs for m in s.own_markers))
    reasons = []
    if placeholder:
        reasons.append("contains placeholder text (lorem ipsum)")
    if words < min_words:
        reasons.append(f"{words} words of running prose (needs {min_words})")
    if share > max_list:
        reasons.append(f"{share:.0%} of its lines are list items (at most {max_list:.0%})")
    return {"ready": not reasons, "words": words, "list_share": share, "placeholder": placeholder,
            "markers": markers, "reasons": reasons}


def for_scope(cfg: Config, scope: str) -> tuple[Section | None, dict | None]:
    """The section a grade scope names and its readiness, or (None, None) if it can't be resolved."""
    try:
        section = get_adapter(cfg).resolve(scope)
    except (FileNotFoundError, ValueError, OSError, UnicodeDecodeError):
        return None, None
    return (section, assess(section, cfg)) if section else (None, None)
