"""The dashboard: `margi/dash.html` plus its data file `margi/dash/data.js` (no AI).

`dash.html` is a fixed page rendered from the bundled template; it never contains data. Every
refresh (`margi init`, every `margi finalize`) only rewrites `dash/data.js`, which the page loads
with a relative `<script src>`, so it works straight from disk. `margi export` inlines the same
data into one self-contained `export.html`.

The data is deterministic: no wall-clock time, so an unchanged project produces an unchanged file
and finalize has nothing to commit.
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import yaml

from . import __version__, docs_check, readiness
from .adapters import get_adapter
from .adapters.base import slug
from .config import MARGI_DIR, Config
from .gitutil import GitError, file_at_head, git, sha256
from .resources import templates_dir
from .todos_sync import list_items

DASH_HTML = f"{MARGI_DIR}/dash.html"
DASH_DATA = f"{MARGI_DIR}/dash/data.js"
EXPORT_HTML = f"{MARGI_DIR}/dash/export.html"
DATA_TAG = '<script src="dash/data.js"></script>'
FONTS_MARK = "/*@margi-fonts@*/"

FONTS = [  # (family, weight, style, file)
    ("Libertinus Serif", 400, "normal", "libertinus-serif-latin-400-normal.woff2"),
    ("Libertinus Serif", 400, "italic", "libertinus-serif-latin-400-italic.woff2"),
    ("Libertinus Serif", 600, "normal", "libertinus-serif-latin-600-normal.woff2"),
    ("Libertinus Sans", 400, "normal", "libertinus-sans-latin-400-normal.woff2"),
    ("Libertinus Sans", 700, "normal", "libertinus-sans-latin-700-normal.woff2"),
    ("Libertinus Mono", 400, "normal", "libertinus-mono-latin-400-normal.woff2"),
]

MAX_STEPS = 5
MAX_RUNS = 40


# --------------------------------------------------------------------------- page


def render_page() -> str:
    """The fixed page: template plus the bundled fonts as data URIs (so export stays offline)."""
    base = templates_dir() / "dash"
    html = (base / "dash.html").read_text(encoding="utf-8")
    faces = []
    for family, weight, style, name in FONTS:
        data = base64.b64encode((base / "fonts" / name).read_bytes()).decode("ascii")
        faces.append(
            f"@font-face{{font-family:'{family}';font-weight:{weight};font-style:{style};font-display:swap;"
            f"src:url(data:font/woff2;base64,{data}) format('woff2')}}"
        )
    return html.replace(FONTS_MARK, "\n".join(faces))


# --------------------------------------------------------------------------- helpers


def _load_records(cfg: Config) -> list[dict]:
    from .lifecycle import load_records

    return load_records(cfg)


def _current_sha(cfg: Config, path: str) -> str | None:
    if cfg.has_git and not path.startswith(f"{MARGI_DIR}/"):
        data = file_at_head(cfg.root, path)
    else:
        p = cfg.root / path
        data = p.read_bytes() if p.is_file() else None
    return sha256(data) if data is not None else None


def _changed_files(cfg: Config, rec: dict, only: set[str] | None = None) -> list[str]:
    """Thesis files whose content differs from what the record was based on."""
    changed = []
    for f in rec["provenance"].get("files", []):
        path = f.get("path", "")
        if path.startswith(f"{MARGI_DIR}/") or (only is not None and path not in only):
            continue
        if f.get("sha256") and _current_sha(cfg, path) != f["sha256"]:
            changed.append(path)
    return changed


def _title(cfg: Config) -> str:
    main = cfg.root / cfg["main"]
    if main.is_file():
        m = re.search(r'#set\s+document\([^)]*title:\s*"([^"]+)"', main.read_text(encoding="utf-8"))
        if m:
            return m.group(1)
    return cfg.root.name


def _rubric(cfg: Config) -> dict:
    from .finalize import RUBRIC, resolve_rubric

    info = resolve_rubric(cfg)
    if not info:
        return {"id": RUBRIC, "version": None, "min": 1, "max": 5, "categories": [], "anchors": {}}
    path = cfg.root / info["path"] if not info["path"].startswith("<bundled>") else None
    if path is None:
        from .resources import skills_dir

        path = skills_dir() / "margi" / "rubrics" / RUBRIC
    data = yaml.safe_load((path / "rubric.yml").read_text(encoding="utf-8")) or {}
    scale = data.get("scale") or {}
    return {
        "id": info["id"],
        "version": info["version"],
        "title": data.get("title"),
        "min": scale.get("min", 1),
        "max": scale.get("max", 5),
        "anchors": {str(k): str(v) for k, v in (scale.get("anchors") or {}).items()},
        "categories": [{"id": str(c["id"]), "title": str(c.get("title", c["id"]))} for c in data.get("categories", [])],
    }


def _sections(cfg: Config, records: list[dict]) -> tuple[list[dict], str | None]:
    """Section tree in thesis order: from the thesis itself, else from the latest outline snapshot."""
    try:
        tree = get_adapter(cfg).tree()
    except (FileNotFoundError, ValueError, OSError, UnicodeDecodeError) as e:
        tree, problem = None, str(e)
    else:
        problem = None
    out: list[dict] = []
    if tree is not None:
        total = tree.total_chars or 1
        for s in tree.walk():
            if s.level == 0:
                continue
            files = sorted({seg.file for sec in s.walk() for seg in sec.segments})
            out.append({"id": s.id, "title": s.title, "level": s.level, "chars": s.total_chars,
                        "share": round(s.total_chars / total, 4), "files": files,
                        "range": [{"file": g.file, "start": g.line_start, "end": g.line_end} for g in s.full_range()],
                        "readiness": readiness.assess(s, cfg)})
        return out, problem
    outlines = [r for r in records if r.get("command") == "outline"]
    if outlines:
        def walk(rows: list[dict], level: int) -> None:
            for r in rows:
                if r.get("planned_only"):
                    continue
                out.append({"id": r.get("id", ""), "title": r.get("title", ""), "level": level, "chars": r.get("chars", 0),
                            "share": r.get("share", 0), "files": [], "range": []})
                walk(r.get("children") or [], level + 1)

        walk(outlines[-1].get("payload", {}).get("sections", []), 1)
    return out, problem


def _section_key(scope: str, sections: list[dict], payload: dict) -> str:
    ids = {s["id"] for s in sections}
    if scope in ids:
        return scope
    for s in sections:
        if slug(s["title"]) == slug(scope) or (payload.get("section_title") and slug(s["title"]) == slug(payload["section_title"])):
            return s["id"]
    return scope


def _targets(records: list[dict]) -> dict[str, str]:
    outlines = [r for r in records if r.get("command") == "outline"]
    found: dict[str, str] = {}

    def walk(rows: list[dict]) -> None:
        for r in rows:
            if r.get("id") and r.get("target"):
                found[r["id"]] = r["target"]
            walk(r.get("children") or [])

    if outlines:
        walk(outlines[-1].get("payload", {}).get("sections", []))
    return found


def _open_questions(cfg: Config) -> list[str]:
    path = cfg.root / MARGI_DIR / "docs" / "open-questions.md"
    if not path.is_file():
        return []
    text = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.S)
    items = []
    for line in text.splitlines():
        m = re.match(r"^\s*(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s+)?(.+?)\s*$", line)
        if m and docs_check.PLACEHOLDER not in m.group(1):
            items.append(m.group(1))
    return items


def _challenge_aspect(questions: list[str]) -> str | None:
    """The doc heading most open questions belong to ("- **Method** (date): …" -> "method")."""
    counts: dict[str, int] = {}
    for q in questions:
        m = re.match(r"\*\*(.+?)\*\*", q)
        if m:
            key = slug(m.group(1))
            counts[key] = counts.get(key, 0) + 1
    return max(counts, key=lambda k: (counts[k], -list(counts).index(k))) if counts else None


# --------------------------------------------------------------------------- data


def collect(cfg: Config) -> dict:
    records = _load_records(cfg)
    rubric = _rubric(cfg)
    sections, section_problem = _sections(cfg, records)
    targets = _targets(records)
    for s in sections:
        if s["id"] in targets:
            s["target"] = targets[s["id"]]

    # grades, per section, oldest first; prechecks: the latest "not ready to grade" record per section
    grades: dict[str, list[dict]] = {}
    prechecks: dict[str, dict] = {}
    for r in records:
        if r.get("command") != "grade":
            continue
        key = _section_key(r["scope"], sections, r.get("payload") or {})
        prov = r["provenance"]
        ready = r.get("readiness") or {}
        if ready.get("decision") == "not_ready":
            prechecks[key] = {"timestamp": prov.get("timestamp"), "file": r["_file"], "mode": ready.get("mode"),
                              "check_reasons": (ready.get("check") or {}).get("reasons") or [],
                              "reasons": ready.get("reasons") or []}
            continue
        files = {f["path"] for f in prov.get("files", [])}
        section_files = next((set(s["files"]) for s in sections if s["id"] == key), None)
        grades.setdefault(key, []).append({
            "run": r["run"]["id"],
            "file": r["_file"],
            "timestamp": prov.get("timestamp"),
            "scope": r["scope"],
            "summary": r.get("summary", ""),
            "scores": {k: {"score": v["score"], "max": v["max"], "rationale": v.get("rationale", ""),
                           "comment_ids": v.get("comment_ids", [])} for k, v in (r.get("scores") or {}).items()},
            "comments": r.get("comments", []),
            "low_confidence": bool(prov.get("docs", {}).get("low_confidence")),
            "model": prov.get("model"),
            "rubric": (prov.get("rubric") or {}).get("version"),
            "changed": _changed_files(cfg, r, (section_files & files) if section_files else None),
            "override": ready.get("decision") == "override",
            "readiness_reasons": (ready.get("check") or {}).get("reasons") or [],
        })
    known = {s["id"] for s in sections}
    for key in list(grades) + list(prechecks):
        if key not in known:
            known.add(key)
            sections.append({"id": key, "title": key, "level": 1, "chars": 0, "share": 0, "files": [], "range": [],
                             "orphan": True})

    # categories: rubric order first, then anything graded that the rubric doesn't list
    cats = list(rubric["categories"])
    seen = {c["id"] for c in cats}
    for runs in grades.values():
        for run in runs:
            for k in run["scores"]:
                if k not in seen:
                    cats.append({"id": k, "title": k})
                    seen.add(k)
    rubric["categories"] = cats

    report = docs_check.check(cfg.root / MARGI_DIR / "docs")
    threshold = float(cfg["docs"]["min_completeness"])
    docs = {
        "filled": report.filled,
        "required": report.required,
        "completeness": report.completeness,
        "threshold": threshold,
        "missing": report.missing,
        "open_questions": _open_questions(cfg),
    }
    docs["challenge_aspect"] = _challenge_aspect(docs["open_questions"])

    outlines = [r for r in records if r.get("command") == "outline"]
    outline = {
        "unit": cfg.get("count", "chars"),
        "total": sum(s["chars"] for s in sections if s["level"] == 1),
        "history": [{"timestamp": r["provenance"]["timestamp"], "total": r.get("payload", {}).get("total", 0)}
                    for r in outlines],
        "changed": _changed_files(cfg, outlines[-1]) if outlines else [],
    }

    literature = _literature(cfg, records)
    todos = _todos(cfg)
    comments = _comments(cfg, records, sections)

    runs = [{"timestamp": r["provenance"].get("timestamp"), "command": r.get("command"), "scope": r.get("scope"),
             "summary": r.get("summary", ""), "model": r["provenance"].get("model"), "file": r["_file"]}
            for r in records[-MAX_RUNS:][::-1]]

    data = {
        "schema": "margi/dash@1",
        "margi_version": __version__,
        "project": {"title": _title(cfg), "main": cfg["main"], "format": cfg["format"], "git": cfg.has_git,
                    "section_problem": section_problem},
        "updated": records[-1]["provenance"].get("timestamp") if records else None,
        "thesis_commit": _thesis_commit(cfg),
        "rubric": rubric,
        "sections": sections,
        "grades": grades,
        "prechecks": prechecks,
        "comments": comments,
        "grade_precheck": _precheck_mode(cfg),
        "docs": docs,
        "outline": outline,
        "literature": literature,
        "todos": todos,
        "runs": runs,
    }
    data["timeline"] = _timeline(cfg, records, sections, comments, data["thesis_commit"], outline["unit"])
    data["next_steps"] = next_steps(data, records)
    return data


def _timeline(cfg: Config, records: list[dict], sections: list[dict], comments: list[dict],
              thesis_commit: dict | None, unit: str) -> dict:
    """Deadline, milestones and dated events for the timeline (see timeline.py)."""
    from . import timeline as tl

    plan, problems = tl.load_plan(cfg)
    commits = tl.commit_days(cfg)
    observed = (thesis_commit or {}).get("date", "")[:10] or None
    grades, events = [], []
    for r in records:
        ts = r["provenance"].get("timestamp")
        if r.get("command") == "grade":
            key = _section_key(r["scope"], sections, r.get("payload") or {})
            ready = r.get("readiness") or {}
            grades.append({"key": key, "timestamp": ts, "readiness": ready})
            events.append({"timestamp": ts, "kind": "not_ready" if ready.get("decision") == "not_ready" else "grade",
                           "section": key, "file": r["_file"],
                           "low_confidence": bool(r["provenance"].get("docs", {}).get("low_confidence"))})
        elif r.get("command") == "respond":
            refs = {x.get("ref") for x in (r.get("payload") or {}).get("responses", [])}
            for sec in sorted({c["section"] for c in comments if c["ref"] in refs and c["section"]}):
                events.append({"timestamp": ts, "kind": "respond", "section": sec, "file": r["_file"]})
    ready = {s["id"]: bool((s.get("readiness") or {}).get("ready")) for s in sections if s.get("readiness")}
    plan = plan or {"start": None, "deadline": None, "length": None, "milestones": []}
    first_record = (records[0]["provenance"].get("timestamp") or "")[:10] if records else None
    start, source = plan["start"], "doc"
    if not start:
        start, source = (commits[0][0], "commit") if commits else (first_record, "record") if first_record else (None, None)
    return {
        "start": start,
        "start_source": source,
        "deadline": plan["deadline"],
        "length": plan["length"],
        "unit": unit,
        "milestones": tl.evaluate(plan, grades, comments, ready, observed),
        "problem": "; ".join(problems) or None,
        "reference": observed,
        "commits": commits,
        "events": events,
    }


def _comments(cfg: Config, records: list[dict], sections: list[dict]) -> list[dict]:
    """Every major and minor grade comment with its state and history (see lifecycle.py)."""
    from .lifecycle import comments

    known = {s["id"] for s in sections}
    out = []
    for c in comments(cfg, records):
        section = c["section"] if c["section"] in known else _section_key(c["scope"] or "", sections, {})
        out.append({"ref": c["ref"], "id": c["id"], "section": section, "severity": c["severity"],
                    "category": c["category"], "body": c["body"], "anchor": c["anchor"], "now": c.get("now"),
                    "signal": c["signal"], "state": c["state"], "created": c["created"], "history": c["history"]})
    return out


def _thesis_commit(cfg: Config) -> dict | None:
    """The newest commit that touched the thesis (anything outside margi/): what the data reflects."""
    if not cfg.has_git:
        return None
    try:
        out = git("log", "-1", "--format=%H%x00%cI", "--", ".", f":(exclude){MARGI_DIR}", cwd=cfg.root).strip()
    except GitError:
        return None
    if not out:
        return None
    sha, date = out.split("\0")
    return {"sha": sha, "date": date}


def _precheck_mode(cfg: Config) -> str:
    try:
        return readiness.mode(cfg)
    except readiness.ReadinessError:
        return "ask"


def _literature(cfg: Config, records: list[dict]) -> dict:
    ratings: dict[str, dict] = {}
    for r in records:
        if r.get("command") != "read":
            continue
        for item in (r.get("payload") or {}).get("ratings", []):
            if isinstance(item, dict) and item.get("pdf"):
                ratings[item["pdf"]] = dict(item, timestamp=r["provenance"].get("timestamp"))
    lit_dir = cfg.root / (cfg.get("literature", {}) or {}).get("dir", "lit")
    pdfs = sorted(p.relative_to(cfg.root).as_posix() for p in lit_dir.rglob("*.pdf")) if lit_dir.is_dir() else []
    for item in ratings.values():
        _passage_links(item)
    return {
        "rated": sorted(ratings.values(), key=lambda x: (-(x.get("relevance") or 0), x["pdf"])),
        "unrated": [p for p in pdfs if p not in ratings],
    }


def _passage_links(item: dict) -> None:
    """Add what the page needs to show a passage: its PDF link and crop images (paths from dash.html).

    Paths only, never whether the files exist here: the data stays the same on every machine and
    the page falls back to text when a crop image doesn't load.
    """
    from .passages import CROPS, crop_name

    item["href"] = "../" + item["pdf"]
    for p in item.get("key_passages") or []:
        anchor = p.get("anchor") or {}
        for c in anchor.get("crops") or []:
            if item.get("pdf_sha256"):
                c["src"] = CROPS.removeprefix(f"{MARGI_DIR}/") + "/" + crop_name(item["pdf_sha256"], anchor["page"], c["box"])


def render_crops(cfg: Config, data: dict) -> None:
    """Render missing passage crops into the gitignored cache (local only, never committed)."""
    from .passages import crop_jobs, render

    for pdf, jobs in crop_jobs(cfg.root, data["literature"]["rated"]).items():
        try:
            render(pdf, jobs)
        except Exception:  # a PDF pdfium can't render keeps its text fallback
            continue


def _inline_crops(cfg: Config, data: dict) -> None:
    for item in data["literature"]["rated"]:
        for p in item.get("key_passages") or []:
            for c in (p.get("anchor") or {}).get("crops") or []:
                path = cfg.root / MARGI_DIR / c.get("src", "")
                if c.get("src") and path.is_file():
                    c["src"] = "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")
                else:
                    c.pop("src", None)


def _todos(cfg: Config) -> list[dict]:
    out = []
    for kind in ("proposed", "close", "synced"):
        for path, meta, _body in list_items(cfg, kind):
            out.append({
                "kind": kind,
                "id": str(meta.get("id") or path.stem),
                "title": str(meta.get("title") or path.stem),
                "status": str(meta.get("status") or kind),
                "issue": meta.get("issue"),
                "file": path.relative_to(cfg.root).as_posix(),
            })
    return out


# --------------------------------------------------------------------------- next steps

MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def _date(ts: str | None) -> str:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", ts or "")
    return f"{int(m.group(3))} {MONTHS[int(m.group(2)) - 1]} {m.group(1)}" if m else (ts or "")


def _common_parent(ids: list[str]) -> str:
    """The deepest section containing all ``ids`` ("2.1", "2.3" -> "2"), or the first id."""
    parts = [i.split(".") for i in ids]
    common = []
    for level in zip(*parts):
        if len(set(level)) != 1:
            break
        common.append(level[0])
    return ".".join(common) or ids[0]


def _carried_out(command: str, later: list[dict]) -> bool:
    """A session step is done once a later run used the same command (and scope, if it names one)."""
    m = re.match(r"/margi[ -]([a-z-]+)\s*(\S*)", command)
    if not m:
        return False
    name, scope = m.groups()
    return any(r.get("command") == name and (not scope or r.get("scope") == scope) for r in later)


def next_steps(data: dict, records: list[dict]) -> list[dict]:
    """Rule-based checks first, then the latest steps the agent left in a draft (`next_steps`)."""
    steps: list[dict] = []

    def add(command: str, reason: str, source: str = "check", **extra) -> None:
        if not any(s["command"] == command for s in steps):
            steps.append({"command": command, "reason": reason, "source": source, **extra})

    docs = data["docs"]
    if docs["completeness"] < docs["threshold"]:
        add("/margi propose", f"Project docs are {docs['completeness']:.0%} complete (needs {docs['threshold']:.0%}); "
                              "until then every grade is low-confidence.")
    sections = [s for s in data["sections"] if not s.get("orphan")]
    awaiting: dict[str, int] = {}
    for c in data.get("comments", []):
        if c["state"] in ("addressed", "disputed"):
            awaiting[c["section"]] = awaiting.get(c["section"], 0) + 1
    for s in sections:
        n = awaiting.get(s["id"])
        if n:
            add(f"/margi grade {s['id']}", f"{n} answered comment{'s' if n != 1 else ''} in {s['title']} "
                                           f"{'await' if n != 1 else 'awaits'} checking.")
    from .timeline import due

    timeline = data.get("timeline") or {}
    for m in timeline.get("milestones", []):
        if m["state"] in ("graded", "settled") and due(m, timeline.get("reference")):
            names = m["label"] or f"{', '.join(m['sections'])} {m['state']}"
            target = m["sections"][0] if len(m["sections"]) == 1 else _common_parent(m["sections"])
            add(f"/margi grade {target}", f"Milestone \"{names}\" is due {_date(m['date'])}.")
    if not timeline.get("deadline") and docs["completeness"] >= docs["threshold"]:
        add("/margi challenge deadline", "No submission date documented yet.")
    gated = data.get("grade_precheck") != "none"
    ready = lambda s: not gated or (s.get("readiness") or {}).get("ready", True)
    for s in sections:
        runs = data["grades"].get(s["id"])
        if runs and runs[-1]["changed"] and ready(s):
            add(f"/margi grade {s['id']}", f"{s['title']} changed since it was graded on {_date(runs[-1]['timestamp'])}.")
    ungraded = sorted((s for s in sections if s["id"] not in data["grades"] and s["chars"] > 0 and ready(s)),
                      key=lambda s: (-s["chars"]))
    top_level_graded = any(k for k in data["grades"])
    for s in ungraded[:1]:
        add(f"/margi grade {s['id']}", f"{s['title']} has text but no grade yet."
            + ("" if top_level_graded else " Nothing has been graded so far."))
    if sections and (not data["outline"]["history"] or data["outline"]["changed"]):
        add("/margi outline", "No length snapshot yet." if not data["outline"]["history"]
            else "The text changed since the last length snapshot.")
    if data["literature"]["unrated"]:
        n = len(data["literature"]["unrated"])
        add("/margi read", f"{n} PDF{'s' if n != 1 else ''} in the literature folder not rated yet.")
    accepted = [t for t in data["todos"] if t["status"] == "accepted"]
    if accepted:
        add("/margi todos", f"{len(accepted)} accepted todo{'s' if len(accepted) != 1 else ''} not on GitHub yet.")
    if docs["open_questions"] and docs["completeness"] >= docs["threshold"]:
        n, aspect = len(docs["open_questions"]), docs.get("challenge_aspect")
        add(f"/margi challenge {aspect}" if aspect else "/margi challenge",
            f"{n} open question{'s' if n != 1 else ''} in the project docs"
            + (f", most of them about {aspect.replace('-', ' ')}." if aspect else "."))

    at = next((i for i in range(len(records) - 1, -1, -1) if records[i].get("next_steps")), None)
    session, held = [], []
    if at is not None:
        agent, later = records[at], records[at + 1:]
        for s in agent["next_steps"][:MAX_STEPS]:
            if _carried_out(s["command"], later):
                continue
            step = {"command": s["command"], "reason": s.get("reason", ""), "source": "session",
                    "timestamp": agent["provenance"].get("timestamp")}
            why = _held(step["command"], docs, sections, gated, ready)
            if why:
                held.append(dict(step, held=why))
            else:
                session.append(step)
    # a docs shortfall blocks everything else, so it leads; then what the student asked for, then the
    # checks; asked-for steps that the docs or the readiness check would refuse come last, saying why
    lead = [c for c in steps if c["command"] == "/margi propose"]
    rest = [c for c in steps if c["command"] != "/margi propose"]
    def unique(items: list[dict], taken: list[dict]) -> list[dict]:
        out: list[dict] = []
        for step in items:
            if not any(t["command"] == step["command"] for t in taken + out):
                out.append(step)
        return out

    # what the student asked for always stays visible; the checks fill the remaining places
    kept = unique(lead + session + held, [])[:MAX_STEPS]
    checks = unique(rest, kept)[:MAX_STEPS - len(kept)]
    first = [k for k in kept if k not in held]
    return first + checks + [k for k in kept if k in held]


def _held(command: str, docs: dict, sections: list[dict], gated: bool, ready) -> str | None:
    """Why a step the agent suggested can't run usefully right now, or None."""
    m = re.match(r"/margi[ -](grade|read)\b\s*(.*)$", command.strip())
    if not m:
        return None
    if docs["completeness"] < docs["threshold"]:
        return f"Project docs are below {docs['threshold']:.0%}, so the result would be low-confidence."
    name, scope = m.groups()
    if name == "grade" and scope and gated:
        target = next((s for s in sections if s["id"] == scope or slug(s["title"]) == slug(scope)), None)
        if target and not ready(target):
            reasons = (target.get("readiness") or {}).get("reasons") or []
            return f"{target['title']} isn't ready to grade yet" + (f" ({'; '.join(reasons)})." if reasons else ".")
    return None


# --------------------------------------------------------------------------- write


def to_js(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=False).replace("</", "<\\/")
    return f"/* margi dashboard data. Generated by margi; do not edit. */\nwindow.MARGI_DASH = {payload};\n"


def _write_if_changed(path: Path, text: str) -> bool:
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def refresh(cfg: Config) -> list[str]:
    """Rewrite dash.html (only when the template changed) and dash/data.js. Returns the paths written."""
    written = []
    if _write_if_changed(cfg.root / DASH_HTML, render_page()):
        written.append(DASH_HTML)
    data = collect(cfg)
    render_crops(cfg, data)
    if _write_if_changed(cfg.root / DASH_DATA, to_js(data)):
        written.append(DASH_DATA)
    return written


def export(cfg: Config, out: Path | None = None) -> Path:
    """One self-contained, offline HTML file with the data inlined."""
    page = render_page()
    data = collect(cfg)
    render_crops(cfg, data)
    _inline_crops(cfg, data)
    inline = "<script>\n" + to_js(data) + "</script>"
    if DATA_TAG not in page:
        raise RuntimeError("dashboard template is missing its data tag")
    path = out or cfg.root / EXPORT_HTML
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page.replace(DATA_TAG, inline), encoding="utf-8")
    return path
