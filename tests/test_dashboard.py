import json

from conftest import human_commit, run_git

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
    assert d["next_steps"][0] == {**d["next_steps"][0], "command": "/margi grade 2", "source": "session"}

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
    assert [s["command"] for s in data(repo)["next_steps"] if s["source"] == "session"] == ["/margi grade 2", "/margi outline"]

    stage(repo, {**DRAFT, "scope": "2"})
    finalize(cfg)
    assert [s["command"] for s in data(repo)["next_steps"] if s["source"] == "session"] == ["/margi outline"]


def test_export_is_self_contained(repo, cfg, tmp_path):
    out = export(cfg, tmp_path / "export.html")
    html = out.read_text()
    assert DATA_TAG not in html and "window.MARGI_DASH = {" in html
    assert "src=\"" not in html.replace('src:url(data:', '')  # no external scripts, images or fonts
    assert "</script>" in html and html.count("<script") == 2


def test_next_steps_reject_prose(repo, cfg):
    import pytest
    from margi.finalize import FinalizeError

    stage(repo, {**DRAFT, "next_steps": [{"command": "Rewrite the intro as follows", "reason": "x"}]})
    with pytest.raises(FinalizeError, match="schema"):
        finalize(cfg)
