import json

import pytest
from click.testing import CliRunner
from conftest import run_git

from margi import lifecycle
from margi.cli import main
from margi.finalize import FinalizeError, finalize
from margi.guard import check_range
from margi.lifecycle import LifecycleError, respond

FILE = "chapters/prior-work.typ"


def comment(cid, severity="major", line=5, quote="Moretti proposed counting instead of reading."):
    c = {"id": cid, "category": "argument", "severity": severity, "body": f"Problem {cid}."}
    if quote:
        c["anchor"] = {"file": FILE, "line_start": line, "line_end": line, "quote": quote}
    return c


def grade(scope="2.1", comments=(), verdicts=None, **extra):
    d = {"command": "grade", "scope": scope, "summary": "ok", "files_read": [FILE],
         "scores": {"argument": {"score": 3, "max": 5, "rationale": "fine"}}, "comments": list(comments)}
    if verdicts is not None:
        d["verdicts"] = verdicts
    d.update(extra)
    return d


def run(repo, cfg, draft):
    d = repo / "margi/.staging"
    d.mkdir(parents=True, exist_ok=True)
    (d / "grade.json").write_text(json.dumps(draft))
    try:
        result = finalize(cfg)
    except FinalizeError:
        (d / "grade.json").unlink()
        raise
    return json.loads(result.records[0].read_text())


def states(cfg):
    return {c["ref"]: c["state"] for c in lifecycle.comments(cfg)}


def first_grade(repo, cfg):
    return run(repo, cfg, grade(comments=[
        comment("c1"),
        comment("c2", "minor", line=7, quote="strongly."),
        comment("c3", "note", quote=None),
    ]))


def test_finalize_numbers_major_and_minor_comments(repo, cfg):
    rec = first_grade(repo, cfg)
    assert [c.get("ref") for c in rec["comments"]] == ["c1", "c2", None]
    rec2 = run(repo, cfg, grade(scope="2.2", comments=[comment("c1", line=15, quote="Networks model relations.")]))
    assert rec2["comments"][0]["ref"] == "c3"  # thesis-wide, never reused
    assert states(cfg) == {"c1": "open", "c2": "open", "c3": "open"}


def test_regrade_must_judge_every_open_comment(repo, cfg):
    first_grade(repo, cfg)
    with pytest.raises(FinalizeError, match="no verdict for c1, c2"):
        run(repo, cfg, grade())
    with pytest.raises(FinalizeError, match="no such comment"):
        run(repo, cfg, grade(verdicts=[{"ref": "c9", "verdict": "open", "reason": "x"}]))
    rec = run(repo, cfg, grade(verdicts=[
        {"ref": "c1", "verdict": "resolved", "reason": "Now cited (prior-work.typ:5)."},
        {"ref": "c2", "verdict": "open", "reason": "Passage unchanged."},
    ]))
    assert len(rec["verdicts"]) == 2
    assert states(cfg) == {"c1": "resolved", "c2": "open"}
    with pytest.raises(FinalizeError, match="already closed"):
        run(repo, cfg, grade(verdicts=[{"ref": "c1", "verdict": "open", "reason": "x"},
                                       {"ref": "c2", "verdict": "open", "reason": "x"}]))


def test_parent_grade_covers_subsections_and_others_are_out_of_scope(repo, cfg):
    first_grade(repo, cfg)
    sid, due = lifecycle.pending(cfg, "2")
    assert sid == "2" and [c["ref"] for c in due] == ["c1", "c2"]
    assert lifecycle.pending(cfg, "Distant Reading")[1] == due  # titles resolve too
    assert lifecycle.pending(cfg, "2.2")[1] == []
    with pytest.raises(FinalizeError, match="doesn't cover"):
        run(repo, cfg, grade(scope="2.2", verdicts=[{"ref": "c1", "verdict": "open", "reason": "x"}]))


def test_not_ready_grade_gives_no_verdicts(repo, cfg):
    first_grade(repo, cfg)
    draft = {"command": "grade", "scope": "2.1", "summary": "Not ready.", "readiness": {"decision": "not_ready"}}
    run(repo, cfg, draft)  # no verdicts needed
    with pytest.raises(FinalizeError, match="gives no verdicts"):
        run(repo, cfg, {**draft, "verdicts": [{"ref": "c1", "verdict": "resolved", "reason": "x"}]})
    assert states(cfg) == {"c1": "open", "c2": "open"}


def test_respond_records_student_words_under_their_name(repo, cfg):
    first_grade(repo, cfg)
    path, _ = respond(cfg, [("c1", "addressed"), ("c2", "disputed")], {"c2": "The term is defined in 1.2."})
    rec = json.loads(path.read_text())
    assert rec["command"] == "respond" and rec["scope"] == "2.1"
    assert rec["payload"]["responses"][1] == {"ref": "c2", "status": "disputed", "reason": "The term is defined in 1.2."}
    assert rec["provenance"]["author"] == {"name": "Human Writer", "email": "human@example.org"}
    assert rec["provenance"]["model"] is None
    log = run_git(repo, "log", "-1", "--format=%an|%s").stdout.strip()
    assert log == "Human Writer|margi: respond c1 c2"
    assert check_range(repo, cfg, "HEAD~1..HEAD") == {}
    assert states(cfg) == {"c1": "addressed", "c2": "disputed"}


def test_dispute_withdrawn_or_kept_and_wont_fix_is_final(repo, cfg):
    first_grade(repo, cfg)
    respond(cfg, [("c1", "disputed"), ("c2", "wont_fix")], {"c2": "Out of scope for this thesis."})
    assert lifecycle.pending(cfg, "2.1")[1][0]["ref"] == "c1"  # won't fix needs no verdict
    with pytest.raises(FinalizeError, match="already closed"):
        run(repo, cfg, grade(verdicts=[{"ref": "c1", "verdict": "open", "reason": "x"},
                                       {"ref": "c2", "verdict": "open", "reason": "x"}]))
    run(repo, cfg, grade(verdicts=[{"ref": "c1", "verdict": "open", "reason": "The jump is still there."}]))
    assert states(cfg) == {"c1": "open", "c2": "wont_fix"}  # dispute rejected: open again
    with pytest.raises(FinalizeError, match="only a disputed comment can be withdrawn"):
        run(repo, cfg, grade(verdicts=[{"ref": "c1", "verdict": "withdrawn", "reason": "x"}]))
    respond(cfg, [("c1", "disputed")])  # a student may dispute again
    run(repo, cfg, grade(verdicts=[{"ref": "c1", "verdict": "withdrawn", "reason": "Accepted."}]))
    assert states(cfg) == {"c1": "withdrawn", "c2": "wont_fix"}
    history = next(c for c in lifecycle.comments(cfg) if c["ref"] == "c1")["history"]
    assert [(h["by"], h["value"]) for h in history] == [
        ("student", "disputed"), ("margi", "open"), ("student", "disputed"), ("margi", "withdrawn")]


def test_respond_refuses_bad_answers(repo, cfg):
    first_grade(repo, cfg)
    with pytest.raises(LifecycleError, match="no such comment"):
        respond(cfg, [("c9", "addressed")])
    with pytest.raises(LifecycleError, match="not one of"):
        respond(cfg, [("c1", "fixed")])
    with pytest.raises(LifecycleError, match="at most 600"):
        respond(cfg, [("c1", "disputed")], {"c1": "x" * 601})
    with pytest.raises(LifecycleError, match="isn't answered"):
        respond(cfg, [("c1", "disputed")], {"c2": "why"})
    (repo / "main.typ").write_text("uncommitted\n")
    with pytest.raises(LifecycleError, match="not clean"):
        respond(cfg, [("c1", "addressed")])


def test_agent_cannot_write_answers_or_numbers(repo, cfg):
    first_grade(repo, cfg)
    with pytest.raises(FinalizeError, match="margi respond"):
        run(repo, cfg, {"command": "respond", "scope": "2.1", "payload": {"responses": []}})
    with pytest.raises(FinalizeError, match="must not carry a ref"):
        run(repo, cfg, grade(comments=[{**comment("c1"), "ref": "c99"}],
                             verdicts=[{"ref": "c1", "verdict": "open", "reason": "x"},
                                       {"ref": "c2", "verdict": "open", "reason": "x"}]))


def test_signal_follows_the_passage_but_never_changes_state(repo, cfg):
    first_grade(repo, cfg)
    text = (repo / FILE).read_text().replace("Moretti proposed counting instead of reading.", "Moretti counted.")
    (repo / FILE).write_text(text)
    run_git(repo, "commit", "-qam", "revise 2.1")
    by_ref = {c["ref"]: c for c in lifecycle.comments(cfg)}
    assert by_ref["c1"]["signal"] == "changed" and by_ref["c1"]["state"] == "open"
    assert by_ref["c1"]["section"] == "2.1"  # falls back to the graded scope
    assert by_ref["c2"]["signal"] == "unchanged"


def test_legacy_comments_are_numbered_before_stored_ones(repo, cfg):
    rec = first_grade(repo, cfg)
    legacy = dict(rec, comments=[{k: v for k, v in c.items() if k != "ref"} for c in rec["comments"]])
    legacy["provenance"] = dict(rec["provenance"], timestamp="2020-01-01T00:00:00Z")
    legacy["run"] = {"id": "legacy"}
    legacy["comments"] = [dict(c, id=c["id"].replace(rec["run"]["id"], "legacy")) for c in legacy["comments"]]
    (repo / "margi/feedback/20200101T000000Z_grade_2.1.json").write_text(json.dumps(legacy))
    refs = lifecycle.numbers(lifecycle.load_records(cfg))
    assert refs["legacy:c1"] == "c1" and refs["legacy:c2"] == "c2"
    assert refs[rec["comments"][0]["id"]] == "c1"  # stored refs win; old ones keep their numbers
    assert lifecycle.next_number(lifecycle.load_records(cfg)) == 3


def test_cli_comments_and_respond(repo, cfg, monkeypatch):
    first_grade(repo, cfg)
    monkeypatch.chdir(repo)
    out = CliRunner().invoke(main, ["comments", "2.1"])
    assert out.exit_code == 0, out.output
    assert "2 comments in 2.1 need a verdict" in out.output and "passage unchanged" in out.output
    out = CliRunner().invoke(main, ["respond", "c1=addressed", "c2=wont-fix", "--reason", "c2", "Kept on purpose."])
    assert out.exit_code == 0, out.output
    assert "margi: respond c1 c2" in out.output
    out = CliRunner().invoke(main, ["comments", "--all"])
    assert "student" in out.output and "won't fix: Kept on purpose." in out.output
    out = CliRunner().invoke(main, ["respond", "c1"])
    assert out.exit_code != 0 and "REF=STATUS" in out.output


def dash(repo):
    text = (repo / "margi/dash/data.js").read_text()
    return json.loads(text[text.index("{"):text.rindex("}") + 1])


def test_dashboard_carries_states_and_suggests_a_regrade(repo, cfg):
    first_grade(repo, cfg)
    respond(cfg, [("c1", "disputed")], {"c1": "The term is defined in 1.2."})
    d = dash(repo)
    by_ref = {c["ref"]: c for c in d["comments"]}
    assert by_ref["c1"]["state"] == "disputed" and by_ref["c1"]["section"] == "2.1"
    assert by_ref["c1"]["history"][0]["reason"] == "The term is defined in 1.2."
    assert by_ref["c2"]["state"] == "open" and by_ref["c2"]["signal"] == "unchanged"
    step = next(s for s in d["next_steps"] if s["command"] == "/margi grade 2.1")
    assert "1 answered comment" in step["reason"]
    head = run_git(repo, "log", "-1", "--format=%H", "--", ".", ":(exclude)margi").stdout.strip()
    assert d["thesis_commit"]["sha"] == head


def test_status_refreshes_the_dashboard(repo, cfg, monkeypatch):
    first_grade(repo, cfg)
    (repo / FILE).write_text((repo / FILE).read_text() + "\nMore text.\n")
    run_git(repo, "commit", "-qam", "write more")
    monkeypatch.chdir(repo)
    out = CliRunner().invoke(main, ["status"])
    assert out.exit_code == 0, out.output
    assert "Comments       2 open (1 major, 0 answered" in out.output
    d = dash(repo)
    assert d["thesis_commit"]["sha"] == run_git(repo, "rev-parse", "HEAD").stdout.strip()
    assert d["grades"]["2.1"][-1]["changed"] == [FILE]
