"""Deadline, milestones and the events the dashboard's timeline shows (no AI, no wall clock).

The plan lives in a fenced YAML block in margi/docs/constraints.md, written by `/margi propose`
and `/margi challenge` from what the student says:

    ```yaml
    # margi-timeline
    start: 2026-09-01          # optional; else the first thesis commit
    deadline: 2027-03-31
    length: 180000             # optional goal, in the unit of `count` in thesis.config.yml
    milestones:
      - {date: 2026-12-01, sections: ["2"], state: drafted, label: Prior work drafted}
      - {date: 2027-02-01, label: Advisor meeting}   # no sections: a plain date, never judged
    ```

A milestone with sections is judged from the records only:

* ``drafted``: the section passes the readiness check; met on the first grade whose stored
  check says ready, or, if the section is ready now and was never checked, on the date of the
  latest thesis commit;
* ``graded``: the section (or a chapter containing it) has a real grade; met on that grade;
* ``settled``: graded, and no open major comments; met on the record that closed the last one.

The data carries dates only. "Today", days left, "due soon" and "missed" are the page's job, so
an unchanged project produces an unchanged data file.
"""

from __future__ import annotations

import datetime as dt
import re

import yaml

from .config import MARGI_DIR, Config
from .gitutil import GitError, git

STATES = ("drafted", "graded", "settled")
BLOCK = "margi-timeline"
DUE_SOON_DAYS = 14


class _Loader(yaml.SafeLoader):
    """SafeLoader that leaves dates as text, so one bad date is reported instead of failing the block."""


_Loader.yaml_implicit_resolvers = {
    k: [r for r in v if r[0] != "tag:yaml.org,2002:timestamp"] for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


# --------------------------------------------------------------------------- plan


def _date(value, field: str, problems: list[str]) -> str | None:
    if isinstance(value, dt.datetime):
        value = value.date()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
        try:
            return dt.date.fromisoformat(value.strip()).isoformat()
        except ValueError:
            pass
    problems.append(f"{field}: {value!r} is not a date (write YYYY-MM-DD)")
    return None


def load_plan(cfg: Config) -> tuple[dict | None, list[str]]:
    """The timeline block from constraints.md, normalised, and what was wrong with it."""
    path = cfg.root / MARGI_DIR / "docs" / "constraints.md"
    if not path.exists():
        return None, []
    text = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.S)
    block = next((b for b in re.findall(r"```ya?ml\n(.*?)```", text, re.S) if BLOCK in b), None)
    if block is None:
        return None, []
    try:
        raw = yaml.load(block, Loader=_Loader)  # a SafeLoader subclass
    except yaml.YAMLError as e:
        return None, [f"the {BLOCK} block is not valid YAML ({str(e).splitlines()[0]})"]
    if not isinstance(raw, dict):
        return None, [f"the {BLOCK} block must be a mapping with at least a deadline"]
    problems: list[str] = []
    plan: dict = {"start": None, "deadline": None, "length": None, "milestones": []}
    if "deadline" in raw:
        plan["deadline"] = _date(raw["deadline"], "deadline", problems)
    else:
        problems.append("no deadline")
    if raw.get("start") is not None:
        plan["start"] = _date(raw["start"], "start", problems)
    if raw.get("length") is not None:
        n = raw["length"]
        if isinstance(n, int) and not isinstance(n, bool) and n > 0:
            plan["length"] = n
        else:
            problems.append(f"length: {n!r} is not a positive whole number")
    items = raw.get("milestones") or []
    if not isinstance(items, list):
        problems.append("milestones must be a list")
        items = []
    for i, m in enumerate(items, 1):
        where = f"milestone {i}"
        if not isinstance(m, dict):
            problems.append(f"{where} is not a mapping")
            continue
        date = _date(m.get("date"), f"{where} date", problems)
        sections = m.get("sections") or []
        if isinstance(sections, (str, int, float)):
            sections = [sections]
        sections = [str(s) for s in sections]
        state = m.get("state")
        if sections and state not in STATES:
            problems.append(f"{where}: state must be one of {', '.join(STATES)}")
            continue
        if date is None:
            continue
        label = str(m.get("label") or "").strip() or None
        plan["milestones"].append({"date": date, "label": label, "sections": sections,
                                   "state": state if sections else None})
    plan["milestones"].sort(key=lambda m: m["date"])
    if plan["start"] and plan["deadline"] and plan["start"] >= plan["deadline"]:
        problems.append("start is not before the deadline")
        plan["start"] = None
    return plan, problems


# --------------------------------------------------------------------------- git


def commit_days(cfg: Config) -> list[list]:
    """[[day, commits], …] for thesis commits (anything outside margi/), oldest first."""
    if not cfg.has_git:
        return []
    try:
        out = git("log", "--format=%cs", "--", ".", f":(exclude){MARGI_DIR}", cwd=cfg.root)
    except GitError:
        return []
    counts: dict[str, int] = {}
    for day in out.split():
        counts[day] = counts.get(day, 0) + 1
    return [[d, counts[d]] for d in sorted(counts)]


# --------------------------------------------------------------------------- milestones


def _within(sid: str, scope_key: str) -> bool:
    """Does a record for ``scope_key`` speak for section ``sid`` (the section or a chapter containing it)?"""
    return sid == scope_key or sid.startswith(scope_key + ".")


def _day(ts: str | None) -> str | None:
    return ts[:10] if ts else None


def met_on(state: str, sid: str, grades: list[dict], comments: list[dict], ready_now: bool | None,
           observed: str | None) -> str | None:
    """The day ``sid`` reached ``state``, or None. ``grades`` are grade records with a ``key``
    (their section) and ``readiness``; ``comments`` come from lifecycle."""
    mine = [g for g in grades if _within(sid, g["key"])]
    if state == "drafted":
        for g in mine:
            check = (g.get("readiness") or {}).get("check") or {}
            if check.get("ready"):
                return _day(g["timestamp"])
        return observed if ready_now else None
    real = [g for g in mine if (g.get("readiness") or {}).get("decision") != "not_ready"]
    if not real:
        return None
    graded = _day(real[0]["timestamp"])
    if state == "graded":
        return graded
    majors = [c for c in comments if c["severity"] == "major" and c["section"] is not None
              and (c["section"] == sid or c["section"].startswith(sid + "."))]
    if any(c["state"] in ("open", "addressed", "disputed") for c in majors):
        return None
    closed = [h["timestamp"] for c in majors for h in c["history"]]
    return max([graded] + [_day(t) for t in closed if t])


def evaluate(plan: dict, grades: list[dict], comments: list[dict], ready: dict[str, bool],
             observed: str | None) -> list[dict]:
    """Milestones with ``met`` (a day, or None while unmet). Several sections: met when all are."""
    out = []
    for m in plan["milestones"]:
        m = dict(m, met=None)
        if m["sections"]:
            days = [met_on(m["state"], s, grades, comments, ready.get(s), observed) for s in m["sections"]]
            m["met"] = max(days) if all(days) else None
        out.append(m)
    return out


def due(milestone: dict, reference: str | None, window: int = DUE_SOON_DAYS) -> bool:
    """Unmet and due within ``window`` days of ``reference`` (or already past it)."""
    if milestone["met"] or not milestone["sections"] or not reference:
        return False
    return dt.date.fromisoformat(milestone["date"]) - dt.date.fromisoformat(reference) <= dt.timedelta(days=window)
