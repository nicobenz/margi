import json

import pytest
from click.testing import CliRunner
from conftest import human_commit

from margi.cli import main
from margi.config import load
from margi.finalize import FinalizeError, finalize
from margi.readiness import for_scope
from test_dashboard import data
from test_finalize import DRAFT, stage

PROSE = " ".join(["Distant reading counts what close reading interprets."] * 30)


def set_mode(repo, mode):
    path = repo / "thesis.config.yml"
    path.write_text(path.read_text().replace("precheck: none", f"precheck: {mode} "))
    human_commit(repo, f"precheck {mode}", "thesis.config.yml")
    return load(repo)


def write_chapter(repo, body):
    (repo / "chapters/prior-work.typ").write_text("= Prior Work\n\n== Distant Reading\n" + body + "\n")
    human_commit(repo, "write", "chapters/prior-work.typ")


def test_assess_prose_bullets_and_placeholders(repo):
    cfg = load(repo)
    write_chapter(repo, PROSE + "\n// TODO not counted, it is a comment\nTODO add Da 2019.")
    check = for_scope(cfg, "2.1")[1]
    assert check["ready"] and check["words"] >= 150 and check["markers"] == ["TODO"]

    write_chapter(repo, "- counting\n- reading\n- machines\nSome text.")
    check = for_scope(cfg, "2.1")[1]
    assert not check["ready"] and check["list_share"] == 0.75
    assert any("list items" in r for r in check["reasons"]) and any("words of running prose" in r for r in check["reasons"])

    write_chapter(repo, PROSE + "\n#lorem(80)")
    check = for_scope(cfg, "2.1")[1]
    assert not check["ready"] and check["placeholder"] and check["reasons"] == ["contains placeholder text (lorem ipsum)"]


def test_ask_requires_a_decision(repo):
    cfg = set_mode(repo, "ask")
    stage(repo, DRAFT)
    with pytest.raises(FinalizeError, match="not ready to grade .*Ask the user"):
        finalize(cfg)

    stage(repo, {**DRAFT, "readiness": {"decision": "override"}})
    rec = json.loads(finalize(cfg).records[0].read_text())
    assert rec["readiness"]["decision"] == "override" and rec["readiness"]["mode"] == "ask"
    assert rec["readiness"]["check"]["ready"] is False and rec["scores"]
    run = data(repo)["grades"]["2.1"][-1]
    assert run["override"] and run["readiness_reasons"]


def test_not_ready_is_recorded_without_scores(repo):
    cfg = set_mode(repo, "ask")
    stage(repo, {"command": "grade", "scope": "2.1", "summary": "Not ready yet.",
                 "readiness": {"decision": "not_ready", "reasons": ["notes, not yet prose"]}})
    rec = json.loads(finalize(cfg).records[0].read_text())
    assert rec["readiness"]["decision"] == "not_ready" and "scores" not in rec
    d = data(repo)
    assert "2.1" not in d["grades"] and d["prechecks"]["2.1"]["reasons"] == ["notes, not yet prose"]
    assert d["prechecks"]["2.1"]["check_reasons"]
    # nothing in the fixture is ready, so no grade is suggested
    assert not any(s["command"].startswith("/margi grade") for s in d["next_steps"])

    stage(repo, {**DRAFT, "readiness": {"decision": "not_ready"}})
    with pytest.raises(FinalizeError, match="no scores or comments"):
        finalize(cfg)


def test_strict_refuses_override(repo):
    cfg = set_mode(repo, "strict")
    stage(repo, {**DRAFT, "readiness": {"decision": "override"}})
    with pytest.raises(FinalizeError, match="strict"):
        finalize(cfg)


def test_ready_section_grades_in_strict_mode(repo):
    cfg = set_mode(repo, "strict")
    write_chapter(repo, PROSE + "\nMoretti proposed counting instead of reading.")
    stage(repo, {**DRAFT, "comments": [dict(DRAFT["comments"][0], anchor=dict(DRAFT["comments"][0]["anchor"], line_start=4, line_end=4))]})
    rec = json.loads(finalize(cfg).records[0].read_text())
    assert rec["readiness"]["decision"] == "graded" and rec["readiness"]["check"]["ready"]


def test_none_grades_and_keeps_the_check(repo, cfg):
    stage(repo, DRAFT)
    rec = json.loads(finalize(cfg).records[0].read_text())
    assert rec["readiness"]["mode"] == "none" and rec["readiness"]["decision"] == "graded"
    assert rec["readiness"]["check"]["ready"] is False


def test_precheck_command(repo, monkeypatch):
    set_mode(repo, "ask")
    monkeypatch.chdir(repo)
    out = CliRunner().invoke(main, ["precheck", "2.1"])
    assert out.exit_code == 0 and "not ready to grade (grade.precheck: ask)" in out.output
    assert CliRunner().invoke(main, ["precheck", "9.9"]).exit_code != 0
