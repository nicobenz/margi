"""Comment lifecycle: every major and minor grade comment keeps a state until it is closed.

Records in margi/feedback/ are append-only, so a state is never stored on the comment. It is
derived from later records, in time order:

* the grade that creates a comment opens it and gives it a thesis-wide number (``c17``);
* a ``respond`` record holds the student's answer: addressed, disputed or won't fix, with an
  optional reason in their own words (see ``respond`` below);
* a later grade of the same section gives a verdict on every comment that isn't closed:
  resolved, still open, or withdrawn (only for a disputed comment). Finalize refuses a grade
  that leaves one out.

Won't fix closes a comment for good: the thesis is the student's. Whether the quoted passage is
still in the text is shown as a signal only; it never changes a state.
"""

from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import MARGI_DIR, Config
from .gitutil import GitError, git
from .guard import FEEDBACK, PREFIX

LIFECYCLE = ("major", "minor")  # notes are strengths and have no lifecycle
RESPONSES = ("addressed", "disputed", "wont_fix")
VERDICTS = ("resolved", "open", "withdrawn")
AWAITING = ("open", "addressed", "disputed")  # need a verdict at the next grade
CLOSED = ("resolved", "withdrawn", "wont_fix")
MAX_REASON = 600
REF = re.compile(r"^c[1-9][0-9]*$")


class LifecycleError(RuntimeError):
    pass


# --------------------------------------------------------------------------- records


def load_records(cfg: Config) -> list[dict]:
    """Every record in margi/feedback/, oldest first, with its file name in ``_file``."""
    out = []
    for p in sorted((cfg.root / FEEDBACK).glob("*.json")):
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if isinstance(rec, dict) and "provenance" in rec:
            rec["_file"] = p.name
            out.append(rec)
    return sorted(out, key=lambda r: (r["provenance"].get("timestamp", ""), r["_file"]))


def after_latest(records: list[dict], now: datetime) -> datetime:
    """``now``, or one second after the newest record if that isn't later. Records are ordered by
    their timestamp, which has one-second resolution, so two runs in the same second would
    otherwise be ordered by file name, not by time."""
    latest = max((r["provenance"].get("timestamp", "") for r in records), default="")
    try:
        last = datetime.strptime(latest, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return now
    return now if now > last else last + timedelta(seconds=1)


def _tracked(records: list[dict]):
    for rec in records:
        if rec.get("command") != "grade":
            continue
        for c in rec.get("comments", []):
            if c.get("severity") in LIFECYCLE:
                yield rec, c


def numbers(records: list[dict]) -> dict[str, str]:
    """Comment id -> its number. Comments from before numbers existed are numbered in record order,
    ahead of every stored number, so their numbers never change either."""
    out, n = {}, 0
    for _, c in _tracked(records):
        if "ref" not in c:
            n += 1
            out[c["id"]] = f"c{n}"
    for _, c in _tracked(records):
        if "ref" in c:
            out[c["id"]] = c["ref"]
    return out


def next_number(records: list[dict]) -> int:
    return max((int(r[1:]) for r in numbers(records).values()), default=0) + 1


# --------------------------------------------------------------------------- sections


class _Sections:
    """Where comments sit in the thesis now. Tolerates a thesis that can't be parsed."""

    def __init__(self, cfg: Config):
        from .adapters import get_adapter

        self.cfg = cfg
        self.lines: dict[tuple[str, int], str] = {}
        self.sections = []
        try:
            self.adapter = get_adapter(cfg)
            root = self.adapter.tree()
        except (FileNotFoundError, ValueError, OSError, UnicodeDecodeError):
            self.adapter = None
            return
        for s in root.walk():
            if s.level == 0:
                continue
            self.sections.append(s)
            for seg in s.segments:
                for line in range(seg.line_start, seg.line_end + 1):
                    self.lines[(seg.file, line)] = s.id
        self._resolved: dict[str, str | None] = {}

    def at(self, file: str, line: int) -> str | None:
        return self.lines.get((file, line))

    def resolve(self, scope: str) -> str | None:
        if self.adapter is None:
            return None
        if scope not in self._resolved:
            try:
                s = self.adapter.resolve(scope)
            except (FileNotFoundError, ValueError, OSError, UnicodeDecodeError):
                s = None
            self._resolved[scope] = s.id if s else None
        return self._resolved[scope]

    def title(self, sid: str) -> str | None:
        return next((s.title for s in self.sections if s.id == sid), None)


def covers(scope_id: str, section: str | None) -> bool:
    """Does a grade of ``scope_id`` cover a comment in ``section`` (the section or a subsection)?"""
    if scope_id == "all":
        return True
    return section is not None and (section == scope_id or section.startswith(scope_id + "."))


# --------------------------------------------------------------------------- state


SIGNALS = {"ok": "unchanged", "relocated": "moved", "unresolved": "changed"}


def _apply(state: str, by: str, value: str) -> str:
    if state not in AWAITING:
        return state
    if by == "student" and value in RESPONSES:
        return value
    if by == "margi":
        if value == "withdrawn":
            return "withdrawn" if state == "disputed" else state
        if value in ("resolved", "open"):
            return value
    return state


def comments(cfg: Config, records: list[dict] | None = None) -> list[dict]:
    """Every tracked comment with its number, section, state, history and passage signal."""
    from .finalize import _read_source, verify_anchor

    records = load_records(cfg) if records is None else records
    refs = numbers(records)
    where = _Sections(cfg)
    sources: dict[str, bytes | None] = {}
    out: dict[str, dict] = {}
    for rec in records:
        ts = rec["provenance"].get("timestamp")
        cmd = rec.get("command")
        if cmd == "grade":
            for c in rec.get("comments", []):
                if c.get("severity") not in LIFECYCLE:
                    continue
                ref = refs[c["id"]]
                entry = {"ref": ref, "id": c["id"], "record": rec["_file"], "created": ts,
                         "scope": rec.get("scope"), "severity": c["severity"], "category": c.get("category"),
                         "body": c.get("body"), "anchor": c.get("anchor"), "state": "open", "history": [],
                         "signal": None}
                section = None
                if c.get("anchor"):
                    a = c["anchor"]
                    if a["file"] not in sources:
                        sources[a["file"]] = _read_source(cfg, a["file"])[0]
                    now = verify_anchor(a, sources[a["file"]])
                    entry["signal"] = SIGNALS[now["anchor_status"]]
                    entry["now"] = {"line_start": now["line_start"], "line_end": now["line_end"]}
                    if now["anchor_status"] != "unresolved":
                        section = where.at(a["file"], now["line_start"])
                entry["section"] = section or where.resolve(rec.get("scope", "")) or rec.get("scope")
                out[ref] = entry
            for v in rec.get("verdicts", []):
                if v["ref"] in out:
                    e = out[v["ref"]]
                    e["state"] = _apply(e["state"], "margi", v["verdict"])
                    e["history"].append({"by": "margi", "value": v["verdict"], "reason": v.get("reason"),
                                         "timestamp": ts, "record": rec["_file"]})
        elif cmd == "respond":
            author = rec["provenance"].get("author") or {}
            for r in (rec.get("payload") or {}).get("responses", []):
                if r.get("ref") in out:
                    e = out[r["ref"]]
                    e["state"] = _apply(e["state"], "student", r["status"])
                    e["history"].append({"by": "student", "value": r["status"], "reason": r.get("reason"),
                                         "timestamp": ts, "record": rec["_file"], "author": author.get("name")})
    for e in out.values():
        e["title"] = where.title(e["section"]) if e["section"] else None
    return list(out.values())


def pending(cfg: Config, scope: str, records: list[dict] | None = None) -> tuple[str, list[dict]]:
    """The section id a grade scope names, and the comments that grade must give a verdict on."""
    where = _Sections(cfg)
    sid = "all" if scope == "all" else (where.resolve(scope) or scope)
    return sid, [c for c in comments(cfg, records) if c["state"] in AWAITING and covers(sid, c["section"])]


def check_verdicts(cfg: Config, draft: dict, records: list[dict]) -> list[str]:
    """Problems with a draft's verdicts. A grade with scores must judge every comment it covers."""
    verdicts = draft.get("verdicts", [])
    if draft.get("command") != "grade":
        return ["only a grade gives verdicts on earlier comments"] if verdicts else []
    if (draft.get("readiness") or {}).get("decision") == "not_ready" or not (draft.get("scores") or draft.get("comments")):
        return ["a grade without scores gives no verdicts; the comments stay as they are"] if verdicts else []
    sid, due = pending(cfg, draft["scope"], records)
    by_ref = {c["ref"]: c for c in comments(cfg, records)}
    problems, seen = [], set()
    for v in verdicts:
        ref = v["ref"]
        if ref in seen:
            problems.append(f"{ref}: more than one verdict")
        seen.add(ref)
        c = by_ref.get(ref)
        if c is None:
            problems.append(f"{ref}: no such comment")
        elif c["state"] in CLOSED:
            problems.append(f"{ref}: already closed ({c['state'].replace('_', ' ')})")
        elif not covers(sid, c["section"]):
            problems.append(f"{ref}: belongs to section {c['section']}, which this grade of {sid} doesn't cover")
        elif v["verdict"] == "withdrawn" and c["state"] != "disputed":
            problems.append(f"{ref}: only a disputed comment can be withdrawn")
    missing = [c["ref"] for c in due if c["ref"] not in seen]
    if missing:
        problems.append(f"no verdict for {', '.join(missing)}; a grade of {sid} must judge every comment in it "
                        f"that isn't closed (see `uv run margi comments {draft['scope']}`)")
    return problems


# --------------------------------------------------------------------------- respond


def _identity(cfg: Config) -> dict:
    if not cfg.has_git:
        return {"name": None, "email": None}
    from .guard import _author_ident

    try:
        name, email = _author_ident(cfg.root)
    except GitError as e:
        raise LifecycleError("git doesn't know who you are; set user.name and user.email so your answer is "
                             "committed under your name") from e
    return {"name": name or None, "email": email or None}


def respond(cfg: Config, answers: list[tuple[str, str]], reasons: dict[str, str] | None = None,
            *, commit: bool = True) -> tuple[Path, str | None]:
    """Record the student's answers to comments and commit them under the student's name.

    ``answers`` is ``[(ref, status), …]``; ``reasons`` maps a ref to the student's own words,
    stored verbatim. Returns the record path and the commit SHA (None without git).
    """
    from . import schema
    from .finalize import FinalizeError, _slug, build_record, ensure_clean

    reasons = dict(reasons or {})
    try:
        ensure_clean(cfg)
    except FinalizeError as e:
        raise LifecycleError(str(e)) from e
    if not answers:
        raise LifecycleError("name at least one comment, e.g. c17=addressed")
    records = load_records(cfg)
    by_ref = {c["ref"]: c for c in comments(cfg, records)}
    problems, seen, responses = [], set(), []
    for ref, status in answers:
        c = by_ref.get(ref)
        if ref in seen:
            problems.append(f"{ref}: named twice")
        elif status not in RESPONSES:
            problems.append(f"{ref}: {status!r} is not one of {', '.join(RESPONSES)}")
        elif c is None:
            problems.append(f"{ref}: no such comment")
        elif c["state"] in CLOSED:
            problems.append(f"{ref}: already closed ({c['state'].replace('_', ' ')})")
        seen.add(ref)
        item = {"ref": ref, "status": status}
        reason = reasons.pop(ref, None)
        if reason is not None and reason.strip():
            if len(reason) > MAX_REASON:
                problems.append(f"{ref}: the reason has {len(reason)} characters (at most {MAX_REASON})")
            item["reason"] = reason
        responses.append(item)
    for ref in reasons:
        problems.append(f"{ref}: a reason for a comment that isn't answered")
    if problems:
        raise LifecycleError("\n  ".join(["cannot record the answers:"] + problems))

    sections = sorted({by_ref[r]["section"] for r, _ in answers if by_ref[r]["section"]})
    scope = "+".join(sections)[:120] or "comments"
    now = after_latest(records, datetime.now(timezone.utc).replace(microsecond=0))
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{stamp}-{secrets.token_hex(3)}"
    draft = {"command": "respond", "scope": scope, "payload": {"responses": responses}}
    record = build_record(cfg, draft, run_id, now, model=None, harness=None, model_source="none")
    record["provenance"]["author"] = _identity(cfg)
    errs = schema.errors(record, "record")
    if errs:
        raise LifecycleError("internal error, record does not match schema:\n  " + "\n  ".join(errs))

    feedback = cfg.root / FEEDBACK
    feedback.mkdir(parents=True, exist_ok=True)
    out = feedback / f"{stamp}_respond_{_slug(scope)}.json"
    n = 2
    while out.exists():
        out = feedback / f"{stamp}_respond_{_slug(scope)}-{n}.json"
        n += 1
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    from .dashboard import refresh

    refresh(cfg)
    if not (commit and cfg.has_git):
        return out, None
    subject = f"{PREFIX} respond {' '.join(r for r, _ in answers)}"
    try:
        git("add", "-A", "--", MARGI_DIR, cwd=cfg.root)
        git("commit", "-q", "-m", subject, "-m", f"Margi-Run: {run_id}", cwd=cfg.root)
    except GitError as e:
        raise LifecycleError(f"{out.name} was written but not committed:\n  {e}") from e
    return out, git("rev-parse", "HEAD", cwd=cfg.root).strip()


# --------------------------------------------------------------------------- text


STATE_LABEL = {"open": "open", "addressed": "addressed", "disputed": "disputed", "wont_fix": "won't fix",
               "resolved": "resolved", "withdrawn": "withdrawn"}


def render(entries: list[dict]) -> str:
    lines = []
    for c in entries:
        where = f"{c['anchor']['file']}:{(c.get('now') or c['anchor'])['line_start']}" if c.get("anchor") else "no anchor"
        signal = f"passage {c['signal']}" if c.get("signal") else ""
        lines.append(f"{c['ref']:<5} {c['severity']:<5} {STATE_LABEL[c['state']]:<10} {c['section'] or '?':<6} "
                     f"{where}  {signal}".rstrip())
        lines.append(f"      {c['body']}")
        if c.get("anchor"):
            lines.append(f"      quote: \"{c['anchor']['quote']}\"")
        for h in c["history"]:
            who = "student" if h["by"] == "student" else "margi"
            reason = f": {h['reason']}" if h.get("reason") else ""
            lines.append(f"      {who}, {(h['timestamp'] or '')[:10]}: {STATE_LABEL.get(h['value'], h['value'])}{reason}")
    return "\n".join(lines)
