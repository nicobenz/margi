"""`margi submit-check`: deterministic checks before submission (no AI).

* quotations: every direct quote in the thesis (Typst "…"/“…” of six or more words, and
  ``#quote[…]``) is paired with the nearest citation and looked up in that source's PDF;
* bibliography: refs.bib against the citations in the thesis and the PDFs in the literature folder;
* length against the goal in the timeline block; sections changed since graded, never graded, or not
  ready; open major comments and open todos.

Findings name a problem and show both sides; they never suggest a correction.
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path

from .config import Config

QUOTE = re.compile(r'"([^"\n]{12,})"|“([^”\n]{12,})”')
QUOTE_BLOCK = re.compile(r"#quote(?:\([^)]*\))?\[")
CITE = re.compile(r"@([\w:.-]+)(?:\[([^\]]*)\])?")
LABEL = re.compile(r"<([\w:.-]+)>")
COMMENT = re.compile(r"(?<![:/])//.*$")
BIB_ENTRY = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,(.*?)(?=\n@\w+\s*\{|\Z)", re.S)
BIB_FIELD = re.compile(r"(\w+)\s*=\s*(\{(?:[^{}]|\{[^{}]*\})*\}|\"[^\"]*\"|\d+)", re.S)
MIN_WORDS = 6
NEAR = 0.8  # word-level similarity for "differs"


# --------------------------------------------------------------------------- thesis


def _source_lines(cfg: Config):
    from .adapters import get_adapter

    for line in get_adapter(cfg).lines():
        text = COMMENT.sub("", line.text)
        if text.strip().startswith(("=", "#set", "#show", "#let", "#import")):
            yield line, ""
            continue
        yield line, text


def thesis_quotes(cfg: Config) -> list[dict]:
    """Direct quotes with their location and the citation nearest after them (same or next line)."""
    lines = list(_source_lines(cfg))
    out = []
    for i, (line, text) in enumerate(lines):
        found = [(m.start(), m.end(), m.group(1) or m.group(2), None) for m in QUOTE.finditer(text)]
        for m in QUOTE_BLOCK.finditer(text):  # #quote(attribution: [@key])[...] on one or more lines
            depth, buf, j, k = 1, "", i, m.end()
            while j < len(lines) and depth:
                t = lines[j][1][k:] if j == i else lines[j][1]
                for ch in t:
                    depth += ch == "["
                    depth -= ch == "]"
                    if not depth:
                        break
                    buf += ch
                buf += " "
                j, k = j + 1, 0
            found.append((m.start(), len(text), CITE.sub("", buf).strip(), CITE.search(m.group(0))))
        for start, end, quote, attributed in found:
            words = quote.split()
            if len(words) < MIN_WORDS:
                continue
            # the citation belongs to the quote if it follows on the same line, or on the next line when
            # the quote ends its line; a citation further away belongs to something else
            rest = text[end:]
            c = attributed or CITE.search(rest[:200])
            if c is None and not rest.strip() and i + 1 < len(lines):
                c = CITE.match(lines[i + 1][1].lstrip())
            cite = None
            if c:
                page = re.search(r"\d+", c.group(2) or "")
                cite = {"key": c.group(1).rstrip(".:"), "page": int(page.group()) if page else None, "supplement": c.group(2)}
            out.append({"file": line.file, "line": line.lineno, "quote": re.sub(r"\s+", " ", quote).strip(), "cite": cite})
    return out


def thesis_citations(cfg: Config) -> dict[str, list[dict]]:
    """Citation keys used in the thesis (labels excluded) -> where."""
    lines = list(_source_lines(cfg))
    labels = {m.group(1) for _, t in lines for m in LABEL.finditer(t)}
    out: dict[str, list[dict]] = {}
    for line, text in lines:
        for m in CITE.finditer(text):
            key = m.group(1).rstrip(".:")
            if key in labels or ":" in key and key.split(":")[0] in ("fig", "tab", "eq", "sec", "lst"):
                continue
            out.setdefault(key, []).append({"file": line.file, "line": line.lineno})
    return out


# --------------------------------------------------------------------------- bibliography


def parse_bib(path: Path) -> dict[str, dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    out: dict[str, dict] = {}
    for m in BIB_ENTRY.finditer(text):
        kind, key, body = m.group(1).lower(), m.group(2), m.group(3)
        if kind in ("comment", "preamble", "string"):
            continue
        fields = {f.group(1).lower(): f.group(2).strip("{}\"").strip() for f in BIB_FIELD.finditer(body)}
        line = text[:m.start()].count("\n") + 1
        out.setdefault(key, {"type": kind, "fields": fields, "line": line, "dupes": 0})
        if out[key]["line"] != line:
            out[key]["dupes"] += 1
    return out


def _bib_path(cfg: Config) -> Path | None:
    bib = (cfg.get("literature") or {}).get("bib")
    if not bib:
        return None
    path = cfg.root / str(bib)
    return path if path.is_file() else None


def pdf_for(key: str, bib: dict, ratings: dict[str, str], pdfs: list[Path], root: Path) -> Path | None:
    """The PDF for a cite key: the bib ``file`` field, a rating's cite_key, or a file named like the key."""
    entry = bib.get(key)
    if entry and entry["fields"].get("file"):
        for part in re.split(r"[;:]", entry["fields"]["file"]):
            if part.lower().endswith(".pdf"):
                p = (root / part).resolve() if not Path(part).is_absolute() else Path(part)
                if p.is_file():
                    return p
                hit = next((q for q in pdfs if q.name == Path(part).name), None)
                if hit:
                    return hit
    if key in ratings and (root / ratings[key]).is_file():
        return root / ratings[key]
    return next((p for p in pdfs if p.stem.lower() == key.lower()), None)


# --------------------------------------------------------------------------- matching


def _tokens(text: str) -> list[str]:
    """Words without surrounding punctuation: a quote may drop a sentence's full stop or a comma."""
    return [t for t in (re.sub(r"^\W+|\W+$", "", w) for w in text.split()) if t]


def _pdf_words(pdf: Path) -> tuple[list[str], list[int]]:
    from .passages import normalize
    from .pdf import _pages

    words, pages = [], []
    for n, text in enumerate(_pages(pdf), start=1):
        for w in _tokens(normalize(text)):
            words.append(w)
            pages.append(n)
    return words, pages


def match_quote(quote: str, words: list[str], pages: list[int]) -> dict:
    """Exact (normalised) match, else the closest passage by words, else not found."""
    from .passages import normalize

    q = _tokens(normalize(quote))
    n = len(q)
    if not n or not words:
        return {"status": "not_found"}
    text = " ".join(words)
    pos = text.find(" ".join(q))
    if pos >= 0:
        idx = text[:pos].count(" ")
        return {"status": "match", "pdf_page": pages[idx]}
    starts = set()
    index: dict[tuple, list[int]] = {}
    for i in range(len(words) - 2):
        index.setdefault(tuple(words[i:i + 3]), []).append(i)
    for k in range(max(1, n - 2)):
        for i in index.get(tuple(q[k:k + 3]), []):
            starts.add(max(0, i - k))
    best, best_at = 0.0, None
    for s in starts:
        window = words[s:s + n + 2]
        r = difflib.SequenceMatcher(None, q, window, autojunk=False).ratio()
        if r > best:
            best, best_at = r, s
    if best_at is None or best < NEAR:
        return {"status": "not_found"}
    window = words[best_at:best_at + n + 2]
    sm = difflib.SequenceMatcher(None, q, window, autojunk=False)
    blocks = sm.get_matching_blocks()
    end = max((b.b + b.size for b in blocks if b.size), default=len(window))
    window = window[:end]
    sm = difflib.SequenceMatcher(None, q, window, autojunk=False)
    diffs = [{"thesis": " ".join(q[a1:a2]), "pdf": " ".join(window[b1:b2])}
             for op, a1, a2, b1, b2 in sm.get_opcodes() if op != "equal"]
    if not diffs:
        return {"status": "match", "pdf_page": pages[best_at]}
    return {"status": "differs", "pdf_page": pages[best_at], "pdf_text": " ".join(window), "diffs": diffs}


# --------------------------------------------------------------------------- check


def run(cfg: Config) -> dict:
    """All checks as one payload for a submit-check record."""
    from .dashboard import collect

    data = collect(cfg)
    bib_path = _bib_path(cfg)
    bib = parse_bib(bib_path) if bib_path else {}
    ratings = {}
    for item in data["literature"]["rated"]:
        if item.get("cite_key"):
            ratings[item["cite_key"]] = item["pdf"]
    from .pdf import find_pdfs

    pdfs = find_pdfs(cfg)
    cache: dict[Path, tuple] = {}

    quotes = []
    for q in thesis_quotes(cfg):
        entry = {"file": q["file"], "line": q["line"], "quote": q["quote"], "cite": q["cite"]}
        if not q["cite"]:
            entry["status"] = "no_citation"
        else:
            pdf = pdf_for(q["cite"]["key"], bib, ratings, pdfs, cfg.root)
            if pdf is None:
                entry["status"] = "no_pdf"
            else:
                if pdf not in cache:
                    try:
                        cache[pdf] = _pdf_words(pdf)
                    except Exception:  # unreadable PDF: say so rather than fail the check
                        cache[pdf] = ([], [])
                entry.update(match_quote(q["quote"], *cache[pdf]))
                entry["pdf"] = pdf.relative_to(cfg.root).as_posix() if pdf.is_relative_to(cfg.root) else str(pdf)
        quotes.append(entry)

    cited = thesis_citations(cfg)
    bib_findings = []
    if bib_path is None:
        bib_findings.append({"kind": "no_bib", "detail": "no bibliography file configured or found (literature.bib)"})
    else:
        rel = bib_path.relative_to(cfg.root).as_posix()
        for key, where in sorted(cited.items()):
            if key not in bib:
                bib_findings.append({"kind": "missing", "key": key, "file": where[0]["file"], "line": where[0]["line"],
                                     "count": len(where)})
        for key, e in sorted(bib.items(), key=lambda kv: kv[1]["line"]):
            if key not in cited:
                bib_findings.append({"kind": "uncited", "key": key, "file": rel, "line": e["line"]})
            f = e["fields"]
            lacking = [x for x in ("author", "title") if not f.get(x) and not (x == "author" and f.get("editor"))]
            if not (f.get("year") or f.get("date")):
                lacking.append("year")
            if lacking:
                bib_findings.append({"kind": "incomplete", "key": key, "file": rel, "line": e["line"], "fields": lacking})
            if e["dupes"]:
                bib_findings.append({"kind": "duplicate_key", "key": key, "file": rel, "line": e["line"]})
        dois: dict[str, list[str]] = {}
        for key, e in bib.items():
            doi = e["fields"].get("doi", "").lower().strip()
            if doi:
                dois.setdefault(doi, []).append(key)
        for doi, keys in sorted(dois.items()):
            if len(keys) > 1:
                bib_findings.append({"kind": "duplicate_doi", "key": ", ".join(keys), "detail": doi, "file": rel})
        mapped = {pdf_for(k, bib, ratings, pdfs, cfg.root) for k in bib}
        for p in pdfs:
            if p not in mapped:
                bib_findings.append({"kind": "pdf_without_entry", "file": p.relative_to(cfg.root).as_posix()})

    timeline = data.get("timeline") or {}
    total = data["outline"]["total"]
    length = {"total": total, "unit": data["outline"]["unit"], "goal": timeline.get("length")}

    sections = []
    for s in data["sections"]:
        if s.get("orphan") or not s["chars"]:
            continue
        runs = data["grades"].get(s["id"])
        if not runs:
            state = "not_ready" if not (s.get("readiness") or {}).get("ready", True) else "ungraded"
        elif runs[-1]["changed"]:
            state = "changed"
        else:
            continue
        sections.append({"id": s["id"], "title": s["title"], "state": state,
                         "graded": runs[-1]["timestamp"] if runs else None})

    open_majors = [{"ref": c["ref"], "section": c["section"], "body": c["body"]} for c in data["comments"]
                   if c["state"] in ("open", "addressed", "disputed") and c["severity"] == "major"]
    open_todos = [{"id": t["id"], "title": t["title"]} for t in data["todos"] if t["state"] == "open"]
    return {
        "commit": (data.get("thesis_commit") or {}).get("sha"),
        "quotes": quotes,
        "bib": bib_findings,
        "length": length,
        "sections": sections,
        "majors": open_majors,
        "todos": open_todos,
        "counts": counts({"quotes": quotes, "bib": bib_findings, "length": length, "sections": sections,
                          "majors": open_majors, "todos": open_todos}),
    }


ATTENTION_QUOTES = ("not_found", "differs")


def counts(p: dict) -> dict:
    over = bool(p["length"]["goal"] and p["length"]["total"] > p["length"]["goal"])
    attention = (sum(1 for q in p["quotes"] if q.get("status") in ATTENTION_QUOTES)
                 + sum(1 for b in p["bib"] if b["kind"] == "missing") + int(over))
    findings = (sum(1 for q in p["quotes"] if q.get("status") != "match") + len(p["bib"]) + int(over)
                + len(p["sections"]) + len(p["majors"]) + len(p["todos"]))
    return {"findings": findings, "attention": attention, "quotes": len(p["quotes"]),
            "quotes_ok": sum(1 for q in p["quotes"] if q.get("status") == "match")}


def summary(p: dict) -> list[str]:
    """Short lines for the terminal and the record summary."""
    q = p["quotes"]
    by = lambda s: sum(1 for x in q if x.get("status") == s)
    lines = [(f"Quotations   {len(q)} checked: {by('match')} match, {by('differs')} differ, {by('not_found')} not found, "
              f"{by('no_pdf')} without a PDF, {by('no_citation')} without a citation nearby")]
    kinds = {}
    for b in p["bib"]:
        kinds[b["kind"]] = kinds.get(b["kind"], 0) + 1
    labels = {"missing": "cited but not in the bibliography", "uncited": "never cited", "incomplete": "incomplete",
              "duplicate_key": "duplicate keys", "duplicate_doi": "duplicate DOIs", "pdf_without_entry": "PDFs without an entry",
              "no_bib": "no bibliography file"}
    lines.append("Bibliography " + (", ".join(f"{n} {labels.get(k, k)}" for k, n in kinds.items()) or "no findings"))
    L = p["length"]
    if L["goal"]:
        lines.append(f"Length       {L['total']} of {L['goal']} {L['unit']}" + (" (over the goal)" if L["total"] > L["goal"] else ""))
    lines.append(f"Sections     {len(p['sections'])} changed since graded, never graded or not ready")
    lines.append(f"Open         {len(p['majors'])} major comments, {len(p['todos'])} todos")
    return lines
