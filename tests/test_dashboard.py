import json
import re

from conftest import human_commit, run_git

from margi import dashboard
from margi.config import load
from margi.dashboard import DATA_TAG, collect, export
from margi.finalize import finalize
from test_finalize import DRAFT, stage


def data(repo) -> dict:
    text = (repo / "margi/dash/data.js").read_text()
    return json.loads(text[text.index("{"): text.rindex("}") + 1])


def test_init_writes_dashboard_in_bot_commit(repo):
    assert (repo / "margi/dash.html").is_file()
    page = (repo / "margi/dash.html").read_text()
    assert DATA_TAG in page and "@font-face" in page and "MARGI_DASH = {" not in page
    files = run_git(repo, "show", "--name-only", "--format=", "HEAD").stdout.split()
    assert "margi/dash.html" in files and "margi/dash/data.js" in files
    d = data(repo)
    assert d["project"]["title"] == "Reading Machines"
    assert [s["id"] for s in d["sections"]][:2] == ["1", "2"]
    assert d["next_steps"][0]["command"] == "/margi propose"


def test_refresh_is_deterministic(repo, cfg):
    before = (repo / "margi/dash/data.js").read_text()
    result = finalize(cfg, command="noop")
    assert result.commit is None
    assert (repo / "margi/dash/data.js").read_text() == before


def test_grade_shows_up_and_goes_stale(repo, cfg):
    stage(repo, {**DRAFT, "next_steps": [{"command": "/margi grade 2", "reason": "You asked to focus on chapter 2."}]})
    finalize(cfg)
    d = data(repo)
    run = d["grades"]["2.1"][-1]
    assert run["scores"]["argument"]["score"] == 3 and run["changed"] == []
    # the docs are incomplete, so their shortfall leads and the asked-for grade waits, saying why
    assert d["next_steps"][0]["command"] == "/margi propose"
    asked = next(s for s in d["next_steps"] if s["source"] == "session")
    assert asked["command"] == "/margi grade 2" and "below 70%" in asked["held"]

    path = repo / "chapters/prior-work.typ"
    path.write_text(path.read_text() + "\nA new paragraph.\n")
    human_commit(repo, "write more", "chapters/prior-work.typ")
    fresh = collect(load(repo))
    assert fresh["grades"]["2.1"][-1]["changed"] == ["chapters/prior-work.typ"]
    assert any(s["command"] == "/margi grade 2.1" and s["source"] == "check" for s in fresh["next_steps"])


def test_session_step_drops_once_carried_out(repo, cfg):
    stage(repo, {**DRAFT, "next_steps": [{"command": "/margi grade 2", "reason": "Focus on chapter 2."},
                                         {"command": "/margi outline", "reason": "Check lengths."}]})
    finalize(cfg)
    assert [s["command"] for s in data(repo)["next_steps"] if s["source"] == "session"] == ["/margi outline", "/margi grade 2"]

    # a grade of chapter 2 judges the earlier comment on 2.1
    stage(repo, {**DRAFT, "scope": "2", "verdicts": [{"ref": "c1", "verdict": "open", "reason": "Still there."}]})
    finalize(cfg)
    assert [s["command"] for s in data(repo)["next_steps"] if s["source"] == "session"] == ["/margi outline"]


def test_export_is_self_contained(repo, cfg, tmp_path):
    out = export(cfg, tmp_path / "export.html")
    html = out.read_text()
    assert DATA_TAG not in html and "window.MARGI_DASH = {" in html
    # no external scripts, images or fonts (the page's own code builds `src="' + …` for inlined crops)
    assert not re.search(r'src="(?!data:)[^\']', html) and "src:url(data:" in html
    assert "</script>" in html and html.count("<script") == 2


def test_next_steps_reject_prose(repo, cfg):
    import pytest
    from margi.finalize import FinalizeError

    stage(repo, {**DRAFT, "next_steps": [{"command": "Rewrite the intro as follows", "reason": "x"}]})
    with pytest.raises(FinalizeError, match="schema"):
        finalize(cfg)


def _data(completeness=1.0, ready=True, questions=(), session=()):
    sec = {"id": "2", "title": "Prior Work", "level": 1, "chars": 500,
           "readiness": {"ready": ready, "reasons": [] if ready else ["mostly bullet points"]}}
    d = {"docs": {"completeness": completeness, "threshold": 0.7, "open_questions": list(questions)},
         "sections": [sec], "grades": {}, "comments": [], "timeline": {"deadline": "2099-01-01", "milestones": []},
         "grade_precheck": "ask", "outline": {"history": [{}], "changed": []}, "literature": {"unrated": []}, "todos": []}
    d["docs"]["challenge_aspect"] = dashboard._challenge_aspect(d["docs"]["open_questions"])
    records = [{"next_steps": [{"command": c, "reason": "You asked."} for c in session], "provenance": {"timestamp": "t"}}]
    return d, records


def test_asked_for_steps_lead_unless_held():
    d, recs = _data(session=["/margi read"])
    steps = dashboard.next_steps(d, recs)
    assert steps[0]["command"] == "/margi read" and steps[0]["source"] == "session"
    d, recs = _data(ready=False, session=["/margi grade 2", "/margi read"])
    steps = dashboard.next_steps(d, recs)
    assert [s["command"] for s in steps] == ["/margi read", "/margi grade 2"]
    assert "isn't ready to grade yet (mostly bullet points)" in steps[1]["held"]


def test_steps_are_capped_and_challenge_names_an_aspect():
    qs = ["**Method** (2026-10-01): How?", "**Dataset** (2026-10-01): Which?", "**Method** (2026-10-02): Why?"]
    d, recs = _data(questions=qs, session=[f"/margi grade 2.{i}" for i in range(1, 6)])
    steps = dashboard.next_steps(d, recs)
    assert len(steps) == dashboard.MAX_STEPS
    d, recs = _data(questions=qs)
    challenge = next(s for s in dashboard.next_steps(d, recs) if s["command"].startswith("/margi challenge"))
    assert challenge["command"] == "/margi challenge method" and "most of them about method" in challenge["reason"]
