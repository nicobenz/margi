"""`margi status`: a quick overview built from margi/ (no AI)."""

from __future__ import annotations

import json
from pathlib import Path

from . import docs_check
from .config import MARGI_DIR, Config
from .todos_sync import list_items


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


def render(cfg: Config) -> str:
    lines: list[str] = []
    report = docs_check.check(cfg.root / MARGI_DIR / "docs")
    threshold = float(cfg["docs"]["min_completeness"])
    flag = "ok" if report.completeness >= threshold else f"below {threshold:.0%} — run `margi onboard`"
    lines.append(f"Project docs   {report.filled}/{report.required} fields ({report.completeness:.0%}, {flag})")
    for name, fields in report.missing.items():
        lines.append(f"  missing in {name}: {', '.join(fields)}")

    records = load_records(cfg)
    grades: dict[str, dict] = {}
    for r in records:
        if r.get("command") == "grade":
            grades[r["scope"]] = r
    lines.append("")
    lines.append("Latest grades" if grades else "Latest grades  none yet — `margi grade <section>`")
    for scope, r in sorted(grades.items()):
        scores = r.get("scores", {})
        parts = [f"{k} {v['score']:g}/{v['max']:g}" for k, v in scores.items()]
        date = r["provenance"]["timestamp"][:10]
        low = " [low confidence]" if r["provenance"].get("docs", {}).get("low_confidence") else ""
        n_major = sum(1 for c in r.get("comments", []) if c.get("severity") == "major")
        lines.append(f"  {scope:<10} {date}  {', '.join(parts)}  ({len(r.get('comments', []))} comments, {n_major} major){low}")

    outlines = [r for r in records if r.get("command") == "outline"]
    lines.append("")
    if outlines:
        o = outlines[-1]["payload"]
        top = ", ".join(f"{s['title']} {s['share']:.0%}" for s in o.get("sections", [])[:6])
        prev = outlines[-2]["payload"]["total"] if len(outlines) > 1 else None
        delta = f" ({o['total'] - prev:+d} since previous snapshot)" if prev is not None else ""
        lines.append(f"Outline        {o['total']} {o['unit']}{delta}")
        lines.append(f"  {top}")
    else:
        lines.append("Outline        no snapshot yet — `margi outline`")

    lines.append("")
    proposed = list_items(cfg, "proposed")
    close = list_items(cfg, "close")
    synced = list_items(cfg, "synced")
    accepted = sum(1 for _, m, _ in proposed if m.get("status") == "accepted")
    lines.append(f"Todos          {len(proposed)} proposed ({accepted} accepted, not synced), "
                 f"{len(close)} closure proposals, {len(synced)} synced")

    lines.append("")
    lines.append("Recent runs")
    for r in records[-5:][::-1]:
        p = r["provenance"]
        lines.append(f"  {p['timestamp']}  {r['command']:<9} {r['scope']:<16} {p.get('model') or '-'} ({p['model_source']})")
    if not records:
        lines.append("  none")
    return "\n".join(lines)
