"""`margi finalize`: turn staged agent drafts into provenance-stamped records and commit them.

The agent never writes provenance. This module is the only place that does.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import __version__, docs_check, schema
from .config import MARGI_DIR, Config
from .gitutil import file_at_head, git, head_sha, sha256, worktree_changes
from .guard import FEEDBACK, PREFIX, in_margi
from .resources import skills_dir

STAGING = f"{MARGI_DIR}/.staging"


class FinalizeError(RuntimeError):
    pass


@dataclass
class FinalizeResult:
    records: list[Path] = field(default_factory=list)
    commit: str | None = None
    message: str | None = None
    has_git: bool = True


# --------------------------------------------------------------------------- preflight


def preflight(cfg: Config) -> list[str]:
    """Violations that block a run: changes outside margi/, or edits to existing feedback.

    Without git there is no baseline to compare against, so nothing is checked.
    """
    problems = []
    if not cfg.has_git:
        return problems
    for c in worktree_changes(cfg.root):
        paths = [c.path] + ([c.orig_path] if c.orig_path else [])
        if any(not in_margi(p) for p in paths):
            label = "untracked" if c.status == "?" else c.status
            problems.append(f"outside margi/ ({label}): {c.path}")
        elif c.status not in ("?", "A") and any(p.startswith(FEEDBACK) for p in paths):
            problems.append(f"existing feedback record changed ({c.status}): {c.path}")
    return problems


def ensure_clean(cfg: Config) -> None:
    problems = preflight(cfg)
    if problems:
        raise FinalizeError(
            "working tree is not clean outside margi/ — commit or stash your own changes first.\n  "
            + "\n  ".join(problems)
        )


# --------------------------------------------------------------------------- helpers


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _read_source(cfg: Config, path: str) -> tuple[bytes | None, str]:
    """Committed content for thesis files, worktree content for margi/ files (and everything without git)."""
    if in_margi(path) or not cfg.has_git:
        p = cfg.root / path
        return (p.read_bytes(), "worktree") if p.is_file() else (None, "missing")
    data = file_at_head(cfg.root, path)
    return (data, "HEAD") if data is not None else (None, "missing")


def verify_anchor(anchor: dict, content: bytes | None) -> dict:
    anchor = dict(anchor)
    if content is None:
        anchor["anchor_status"] = "unresolved"
        return anchor
    lines = content.decode("utf-8", errors="replace").splitlines()
    quote = _norm(anchor["quote"])
    start, end = anchor["line_start"], max(anchor["line_end"], anchor["line_start"])
    window = _norm(" ".join(lines[start - 1 : end]))
    if quote and quote in window:
        anchor["anchor_status"] = "ok"
        return anchor
    # search the whole file; relocate if the quote occurs exactly once
    normed = [_norm(line) for line in lines]
    offsets, pos = [], 0
    for n in normed:
        offsets.append(pos)
        pos += len(n) + 1
    full = " ".join(normed)
    hits = [m.start() for m in re.finditer(re.escape(quote), full)] if quote else []
    if len(hits) == 1:
        s, e = hits[0], hits[0] + len(quote) - 1
        first = max(i for i, o in enumerate(offsets) if o <= s)
        last = max(i for i, o in enumerate(offsets) if o <= e)
        anchor.update(line_start=first + 1, line_end=last + 1, anchor_status="relocated")
    else:
        anchor["anchor_status"] = "unresolved"
    return anchor


RUBRIC = "default"  # custom rubrics are not supported yet (see README, "Rubrics")


def resolve_rubric(cfg: Config) -> dict | None:
    """The bundled rubric: the repo's vendored copy of the skill if present, else the package's."""
    rid = RUBRIC
    candidates = [
        cfg.root / ".agents" / "skills" / "margi" / "rubrics" / rid,
        skills_dir() / "margi" / "rubrics" / rid,
    ]
    for d in candidates:
        meta = d / "rubric.yml"
        if meta.is_file():
            h = hashlib.sha256()
            for f in sorted(p for p in d.rglob("*") if p.is_file()):
                h.update(f.relative_to(d).as_posix().encode() + b"\0" + f.read_bytes() + b"\0")
            data = yaml.safe_load(meta.read_text(encoding="utf-8")) or {}
            try:
                shown = d.relative_to(cfg.root).as_posix()
            except ValueError:
                shown = f"<bundled>/{rid}"
            return {"id": str(data.get("id", rid)), "version": str(data.get("version", "0")), "sha256": h.hexdigest(), "path": shown}
    return None


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9.]+", "-", text).strip("-")[:60] or "all"


# --------------------------------------------------------------------------- readiness


def grade_readiness(cfg: Config, draft: dict) -> dict:
    """Run the precheck for a grade draft and decide, per grade.precheck, whether it may be recorded."""
    from .readiness import ReadinessError, for_scope, mode

    try:
        m = mode(cfg)
    except ReadinessError as e:
        raise FinalizeError(str(e)) from e
    _, check = for_scope(cfg, draft["scope"])
    asked = draft.get("readiness", {})
    graded = bool(draft.get("scores") or draft.get("comments"))
    out = {"mode": m, "decision": "graded", "check": check}
    if asked.get("reasons"):
        out["reasons"] = asked["reasons"]
    if asked.get("decision") == "not_ready":
        if graded:
            raise FinalizeError(f"grade {draft['scope']}: a not_ready grade carries no scores or comments")
        out["decision"] = "not_ready"
        return out
    if not graded or check is None or check["ready"] or m == "none":
        return out
    why = "; ".join(check["reasons"])
    if m == "strict":
        raise FinalizeError(f"grade {draft['scope']}: the section is not ready to grade ({why}) and grade.precheck is "
                            "strict. Record it as not ready (readiness.decision: not_ready, no scores); to grade it "
                            "anyway, the user changes grade.precheck in thesis.config.yml.")
    if asked.get("decision") != "override":
        raise FinalizeError(f"grade {draft['scope']}: the section is not ready to grade ({why}). Ask the user: if they "
                            "want it graded anyway, set readiness.decision to override; otherwise record it as not "
                            "ready (readiness.decision: not_ready, no scores).")
    out["decision"] = "override"
    return out


# --------------------------------------------------------------------------- build


def load_drafts(cfg: Config) -> list[tuple[Path, dict]]:
    staging = cfg.root / STAGING
    drafts = []
    for path in sorted(staging.glob("*.json")) if staging.is_dir() else []:
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as e:
            raise FinalizeError(f"{path.name}: invalid JSON ({e})") from e
        if isinstance(obj, dict) and ({"provenance", "run", "schema"} & obj.keys()):
            raise FinalizeError(f"{path.name}: drafts must not contain run/provenance/schema — margi injects those")
        errs = schema.errors(obj, "draft")
        if errs:
            raise FinalizeError(f"{path.name}: draft does not match schema:\n  " + "\n  ".join(errs))
        drafts.append((path, obj))
    return drafts


def build_record(
    cfg: Config,
    draft: dict,
    run_id: str,
    now: datetime,
    *,
    model: str | None,
    harness: str | None,
    model_source: str | None,
) -> dict:
    record = {"schema": "margi/record@1", "run": {"id": run_id}}
    record.update(draft)
    if draft["command"] == "grade":
        record["readiness"] = grade_readiness(cfg, draft)
    else:
        record.pop("readiness", None)

    comments = []
    for c in draft.get("comments", []):
        c = dict(c, id=f"{run_id}:{c['id']}")
        if "anchor" in c:
            content, _ = _read_source(cfg, c["anchor"]["file"])
            c["anchor"] = verify_anchor(c["anchor"], content)
        comments.append(c)
    if comments:
        record["comments"] = comments
    if "scores" in draft:
        record["scores"] = {
            k: dict(v, comment_ids=[f"{run_id}:{i}" for i in v.get("comment_ids", [])])
            for k, v in draft["scores"].items()
        }

    paths = list(dict.fromkeys(draft.get("files_read", []) + [c["anchor"]["file"] for c in comments if "anchor" in c]))
    files = []
    for p in paths:
        content, source = _read_source(cfg, p)
        files.append({"path": p, "sha256": sha256(content) if content is not None else None, "source": source})

    report = docs_check.check(cfg.root / MARGI_DIR / "docs")
    agent = draft.get("agent", {})
    if model_source in ("wrapper", "self-reported") and model:
        m, src, h = model, model_source, harness
    elif agent.get("model"):
        m, src, h = agent["model"], "self-reported", agent.get("harness")
    else:
        m, src, h = None, "none", harness or agent.get("harness")

    record["provenance"] = {
        "head_sha": head_sha(cfg.root) if cfg.has_git else None,
        "files": files,
        "rubric": resolve_rubric(cfg) if draft["command"] == "grade" else None,
        "docs": {
            "sha256": docs_check.docs_hash(cfg.root / MARGI_DIR / "docs"),
            "completeness": report.completeness,
            "low_confidence": report.completeness < float(cfg["docs"]["min_completeness"]),
        },
        "model": m,
        "model_source": src,
        "harness": h,
        "margi_version": __version__,
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    errs = schema.errors(record, "record")
    if errs:
        raise FinalizeError("internal error, record does not match schema:\n  " + "\n  ".join(errs))
    return record


# --------------------------------------------------------------------------- main entry


def finalize(
    cfg: Config,
    *,
    model: str | None = None,
    harness: str | None = None,
    model_source: str | None = None,
    command: str | None = None,
    commit: bool = True,
) -> FinalizeResult:
    ensure_clean(cfg)
    drafts = load_drafts(cfg)  # validates all drafts before anything is written

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{stamp}-{secrets.token_hex(3)}"
    feedback = cfg.root / FEEDBACK
    feedback.mkdir(parents=True, exist_ok=True)

    result = FinalizeResult(has_git=cfg.has_git)
    records = [build_record(cfg, draft, run_id if len(drafts) == 1 else f"{run_id}-{i + 1}", now,
                            model=model, harness=harness, model_source=model_source)
               for i, (_, draft) in enumerate(drafts)]  # every draft must pass before anything is written
    for (path, draft), record in zip(drafts, records):
        out = feedback / f"{stamp}_{draft['command']}_{_slug(draft['scope'])}.json"
        n = 2
        while out.exists():
            out = feedback / f"{stamp}_{draft['command']}_{_slug(draft['scope'])}-{n}.json"
            n += 1
        out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        result.records.append(out)
        path.unlink()

    from .dashboard import refresh

    refresh(cfg)

    if not commit:
        return result

    if drafts:
        subject = ", ".join(f"{d['command']} {d['scope']}" for _, d in drafts)
    else:
        subject = command or "update"
    result.commit = bot_commit(cfg, subject, run_id)
    if result.commit:
        result.message = f"{PREFIX} {subject}"
    return result


def bot_commit(cfg: Config, subject: str, run_id: str | None = None) -> str | None:
    """Stage everything under margi/ and commit it as the margi bot. Returns the SHA or None."""
    if not cfg.has_git:
        return None
    git("add", "-A", "--", MARGI_DIR, cwd=cfg.root)
    if not git("diff", "--cached", "--name-only", cwd=cfg.root).split():
        return None
    message = f"{PREFIX} {subject}\n"
    if run_id:
        message += f"\nMargi-Run: {run_id}\n"
    env = dict(
        os.environ,
        GIT_AUTHOR_NAME=cfg.bot_name,
        GIT_AUTHOR_EMAIL=cfg.bot_email,
        GIT_COMMITTER_NAME=cfg.bot_name,
        GIT_COMMITTER_EMAIL=cfg.bot_email,
    )
    proc = subprocess.run(["git", "commit", "-q", "-F", "-"], cwd=cfg.root, input=message.encode(), env=env, capture_output=True)
    if proc.returncode != 0:
        raise FinalizeError("git commit failed:\n" + (proc.stderr or proc.stdout).decode(errors="replace"))
    return git("rev-parse", "HEAD", cwd=cfg.root).strip()
