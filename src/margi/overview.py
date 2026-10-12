"""`margi next`: what is there, what is missing, and what to run next (no AI).

Read-only input for `/margi help`: the setup checklist, the dashboard's ranked next steps, and
an inventory of the project. The agent explains it; nothing is written or committed.
"""

from __future__ import annotations

import datetime as dt

from .config import Config
from .dashboard import DASH_HTML, _date, _plan_written, collect
from .lifecycle import AWAITING


def render(cfg: Config) -> str:
    data = collect(cfg)
    lines: list[str] = []

    setup = data["setup"]
    if setup["done"] < setup["total"]:
        lines.append(f"Getting started  {setup['done']} of {setup['total']} done")
        current = next(s for s in setup["steps"] if not s["done"])
        for s in setup["steps"]:
            mark = "x" if s["done"] else ">" if s is current else " "
            cmd = f"  ({s['command']})" if s is current and s["command"] else ""
            lines.append(f"  [{mark}] {s['title']}{cmd}")
        lines.append("")

    lines.append("Next steps" if data["next_steps"] else "Next steps     nothing pending")
    for s in data["next_steps"]:
        src = "your session" if s["source"] == "session" else "checks"
        held = f" On hold: {s['held']}" if s.get("held") else ""
        lines.append(f"  {s['command']:<28} {s['reason']}{held}  [{src}]")

    lines.append("")
    lines.append("Project")
    proposal = str((cfg.get("propose") or {}).get("source") or "PROPOSAL.md")
    lines.append(f"  Plan          {proposal} " + ("written and saved" if _plan_written(cfg)
                                                  else "still the template, or not saved yet"))
    d = data["docs"]
    lines.append(f"  Project docs  {d['filled']}/{d['required']} fields ({d['completeness']:.0%}, "
                 f"grading needs {d['threshold']:.0%}), {len(d['open_questions'])} open questions")
    for name, fields in (d["missing"] if d["filled"] else {}).items():  # with nothing documented, all of it
        lines.append(f"    missing in {name}: {', '.join(fields)}")

    tl = data["timeline"]
    if tl.get("deadline"):
        left = (dt.date.fromisoformat(tl["deadline"]) - dt.date.today()).days
        lines.append(f"  Submission    {_date(tl['deadline'])} ({left} days left), "
                     f"{len(tl['milestones'])} milestones")
    else:
        lines.append("  Submission    no date documented")

    sections = [s for s in data["sections"] if not s.get("orphan")]
    written = [s for s in sections if s["chars"] > 0]
    graded = [s for s in sections if s["id"] in data["grades"]]
    changed = [s["id"] for s in graded if data["grades"][s["id"]][-1]["changed"]]
    lines.append(f"  Sections      {len(sections)} in the outline, {len(written)} with text, {len(graded)} graded"
                 + (f", changed since grading: {', '.join(changed)}" if changed else ""))
    open_c = [c for c in data["comments"] if c["state"] in AWAITING]
    majors = sum(1 for c in open_c if c.get("severity") == "major")
    lines.append(f"  Comments      {len(open_c)} open ({majors} major)")
    lines.append(f"  Length        " + (f"{data['outline']['total']} {data['outline']['unit']}, "
                                         f"{len(data['outline']['history'])} snapshots" if data["outline"]["history"]
                                         else "no snapshot yet"))
    lit = data["literature"]
    lines.append(f"  Literature    {len(lit['rated']) + len(lit['unrated'])} PDFs, {len(lit['unrated'])} not rated")
    todos = data["todos"]
    lines.append(f"  Todos         {sum(1 for t in todos if t['state'] == 'open')} open")
    sub = data["submission"]
    lines.append("  Submit check  " + ("not run yet" if not sub["check"] else
                                      "outdated, the text changed since" if sub["stale"] else "up to date"))

    lines.append("")
    lines.append(f"Dashboard  {(cfg.root / DASH_HTML).resolve().as_uri()}  (all commands are in its Guide tab)")
    return "\n".join(lines)
