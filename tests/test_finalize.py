import json

import pytest
from conftest import run_git

from margi.finalize import FinalizeError, finalize, verify_anchor

DRAFT = {
    "command": "grade",
    "scope": "2.1",
    "summary": "ok",
    "files_read": ["chapters/prior-work.typ"],
    "scores": {"argument": {"score": 3, "max": 5, "rationale": "fine", "comment_ids": ["c1"]}},
    "comments": [
        {
            "id": "c1",
            "category": "argument",
            "severity": "major",
            "body": "Claim needs evidence.",
            "anchor": {"file": "chapters/prior-work.typ", "line_start": 5, "line_end": 5,
                       "quote": "Moretti proposed counting instead of reading."},
        }
    ],
}


def stage(repo, draft, name="grade.json"):
    d = repo / "margi/.staging"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(json.dumps(draft))


def test_finalize_writes_record_and_bot_commit(repo, cfg):
    stage(repo, DRAFT)
    result = finalize(cfg, model="claude-x", harness="claude", model_source="self-reported")
    assert len(result.records) == 1
    rec = json.loads(result.records[0].read_text())
    prov = rec["provenance"]
    assert prov["head_sha"] and prov["model"] == "claude-x" and prov["model_source"] == "self-reported"
    assert prov["files"][0]["source"] == "HEAD" and len(prov["files"][0]["sha256"]) == 64
    assert prov["rubric"]["id"] == "default" and prov["rubric"]["version"] == "1.0"
    assert prov["docs"]["low_confidence"] is True
    assert rec["comments"][0]["id"].endswith(":c1")
    assert rec["comments"][0]["anchor"]["anchor_status"] == "ok"
    assert rec["scores"]["argument"]["comment_ids"] == [rec["comments"][0]["id"]]
    log = run_git(repo, "log", "-1", "--format=%an|%s|%b").stdout
    assert log.startswith("margi-bot|margi: grade 2.1|Margi-Run:")
    changed = run_git(repo, "show", "--name-only", "--format=", "HEAD").stdout.split()
    assert changed == [result.records[0].relative_to(repo).as_posix()]
    assert not (repo / "margi/.staging/grade.json").exists()


def test_tamper_outside_margi_aborts(repo, cfg):
    stage(repo, DRAFT)
    (repo / "main.typ").write_text("the AI rewrote this\n")
    with pytest.raises(FinalizeError, match="outside margi/"):
        finalize(cfg)
    assert list((repo / "margi/feedback").glob("*.json")) == []


def test_untracked_file_outside_margi_aborts(repo, cfg):
    stage(repo, DRAFT)
    (repo / "notes.txt").write_text("x")
    with pytest.raises(FinalizeError, match="untracked"):
        finalize(cfg)


def test_draft_with_provenance_rejected(repo, cfg):
    stage(repo, {**DRAFT, "provenance": {"model": "fake"}})
    with pytest.raises(FinalizeError, match="must not contain"):
        finalize(cfg)


def test_draft_with_suggested_text_rejected(repo, cfg):
    bad = json.loads(json.dumps(DRAFT))
    bad["comments"][0]["suggested_text"] = "Moretti, in his seminal work, ..."
    stage(repo, bad)
    with pytest.raises(FinalizeError, match="schema"):
        finalize(cfg)


def test_self_reported_model(repo, cfg):
    stage(repo, {**DRAFT, "agent": {"model": "some-model", "harness": "codex"}})
    rec = json.loads(finalize(cfg).records[0].read_text())
    assert rec["provenance"]["model_source"] == "self-reported"
    assert rec["provenance"]["model"] == "some-model"


def test_anchor_relocated_and_unresolved():
    content = b"line one\nthe quick brown\nfox jumps\n"
    a = verify_anchor({"file": "f", "line_start": 1, "line_end": 1, "quote": "brown fox"}, content)
    assert a["anchor_status"] == "relocated" and (a["line_start"], a["line_end"]) == (2, 3)
    a = verify_anchor({"file": "f", "line_start": 1, "line_end": 1, "quote": "not there"}, content)
    assert a["anchor_status"] == "unresolved"
    a = verify_anchor({"file": "f", "line_start": 2, "line_end": 3, "quote": "quick  brown fox"}, content)
    assert a["anchor_status"] == "ok"


def test_docs_only_change_committed_with_subject(repo, cfg):
    (repo / "margi/docs/open-questions.md").write_text("# Open questions\n- scope?\n")
    result = finalize(cfg, command="propose")
    assert result.records == [] and result.commit
    assert run_git(repo, "log", "-1", "--format=%s").stdout.strip() == "margi: propose"
