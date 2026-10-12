"""`margi status`: a quick overview built from margi/ (no AI)."""

from __future__ import annotations

import json
from pathlib import Path

from . import docs_check
from .config import MARGI_DIR, Config
from .todos_sync import github_sync, todo_items


def load_records(cfg: Config) -> list[dict]:
    out = []
    for p in sorted((cfg.root / MARGI_DIR / "feedback").glob("*.json")):
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
            rec["_file"] = p.name
            out.append(rec)
        except ValueError:
            continue
    return sorted(out, key=lambda r: r.get("provenance", {}).get("timestamp", ""))


MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def _day(ts: str) -> str:
    """'2026-10-05T10:00:00Z' -> '5 Oct', as on the dashboard."""
    return f"{int(ts[8:10])} {MONTHS[int(ts[5:7]) - 1]}" if ts and len(ts) >= 10 else "?"


def _n(n: int) -> str:
    """Thousands grouped with a space, as on the dashboard: 7 180."""
    return f"{n:,}".replace(",", " ")


def _plural(n: int, word: str, many: str | None = None) -> str:
    return f"{n} {word if n == 1 else many or word + 's'}"


def render(cfg: Config) -> str:
    lines: list[str] = []
    from .agent_settings import consent_overrides
    from .save import last_save

    saved = last_save(cfg)
    if saved:
        from datetime import datetime

        # git may print UTC as a trailing "Z", which fromisoformat only accepts from Python 3.11 on
        dt = datetime.fromisoformat(saved.replace("Z", "+00:00"))
        lines.append(f"Last saved     {dt.day} {dt:%b %Y, %H:%M}")
    for rule in consent_overrides(cfg.root):
        lines.append(f"warning: {rule} lets your agent save without asking you; `uv run margi init` removes it")
    report = docs_check.check(cfg.root / MARGI_DIR / "docs")
    threshold = float(cfg["docs"]["min_completeness"])
    flag = "ok" if report.completeness >= threshold else f"below {threshold:.0%} — run /margi propose"
    lines.append(f"Project docs   {report.filled}/{report.required} fields ({report.completeness:.0%}, {flag})")
    for name, fields in report.missing.items():
        lines.append(f"  missing in {name}: {', '.join(fields)}")

    records = load_records(cfg)
    grades: dict[str, dict] = {}
    for r in records:
        if r.get("command") == "grade" and (r.get("readiness") or {}).get("decision") != "not_ready":
            grades[r["scope"]] = r

    from .lifecycle import AWAITING, comments

    tracked = comments(cfg)
    lines.append("")
    lines.append("Latest grades" if grades else "Latest grades  none yet — /margi grade <section>")
    for scope, r in sorted(grades.items()):
        scores = r.get("scores", {})
        parts = [f"{k} {v['score']:g}/{v['max']:g}" for k, v in scores.items()]
        low = " [low confidence]" if r["provenance"].get("docs", {}).get("low_confidence") else ""
        # open comments in this section now (the dashboard's count), not the ones this grade created
        here = [c for c in tracked if c["state"] in AWAITING and c.get("section") == scope]
        n_major = sum(1 for c in here if c.get("severity") == "major")
        lines.append(f"  {scope:<10} {_day(r['provenance']['timestamp']):<7} {', '.join(parts)}  "
                     f"({_plural(len(here), 'open comment')}, {n_major} major){low}")

    if tracked:
        not_closed = [c for c in tracked if c["state"] in AWAITING]
        majors = sum(1 for c in not_closed if c["severity"] == "major")
        waiting = sum(1 for c in not_closed if c["state"] != "open")
        closed = len(tracked) - len(not_closed)
        lines.append(f"Comments       {len(not_closed)} open ({majors} major, {waiting} answered and awaiting a grade), "
                     f"{closed} closed")

    outlines = [r for r in records if r.get("command") == "outline"]
    lines.append("")
    if outlines:
        o = outlines[-1]["payload"]
        top = ", ".join(f"{s['title']} {s['share']:.0%}" for s in o.get("sections", [])[:6])
        prev = outlines[-2]["payload"]["total"] if len(outlines) > 1 else None
        diff = o["total"] - prev if prev is not None else 0
        delta = f" ({'+' if diff >= 0 else '−'}{_n(abs(diff))} since the previous snapshot)" if prev is not None else ""
        lines.append(f"Outline        {_n(o['total'])} {o['unit']}{delta}")
        lines.append(f"  {top}")
    else:
        lines.append("Outline        no snapshot yet — /margi outline")

    lines.append("")
    items = todo_items(cfg)
    count = lambda st: sum(1 for t in items if t["state"] == st)
    waiting = sum(1 for t in items if t["kind"] in ("proposed", "close") and t["status"] != "accepted")
    lines.append(f"Todos          {count('open')} open, {count('done')} done, {waiting} waiting for your review"
                 + (" (mirrored to GitHub)" if github_sync(cfg) else ""))

    lines.append("")
    lines.append("Recent runs" if records else "Recent runs    none yet")
    for r in records[-5:][::-1]:
        scope = "" if r.get("scope") in (None, "all") else r["scope"]
        lines.append(f"  {_day(r['provenance']['timestamp']):<7} /margi {r['command']} {scope}".rstrip())
    return "\n".join(lines)
