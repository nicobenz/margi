import json

from click.testing import CliRunner
from conftest import human_commit

from margi.cli import main, should_open_dashboard
from margi.config import load
from margi.dashboard import refresh, setup_progress
from margi.finalize import finalize
from margi.init import init


def steps(repo):
    return {s["id"]: s for s in setup_progress(load(repo))["steps"]}


def test_checklist_ticks_itself_off(repo, cfg):
    s = steps(repo)
    assert [k for k, v in s.items() if v["done"]] == []
    assert s["grade"]["command"].startswith("/margi grade ")
    (repo / "PROPOSAL.md").write_text((repo / "PROPOSAL.md").read_text() + "\nMy research question.\n")
    human_commit(repo, "plan", "PROPOSAL.md")
    staging = repo / "margi/.staging"
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "propose.json").write_text(json.dumps({"command": "propose", "scope": "all", "summary": "Docs."}))
    finalize(cfg)
    s = steps(repo)
    assert s["plan"]["done"] and s["propose"]["done"] and s["propose"]["date"]
    assert not s["docs"]["done"] and setup_progress(cfg)["done"] == 2


def test_uncommitted_plan_does_not_count(repo, cfg):
    (repo / "PROPOSAL.md").write_text("A plan that isn't committed yet.\n")
    refresh(cfg)
    assert not steps(repo)["plan"]["done"]


def test_finalize_names_the_dashboard_until_setup_is_done(repo, monkeypatch):
    monkeypatch.chdir(repo)
    out = CliRunner().invoke(main, ["finalize", "--message", "noop"])
    assert out.exit_code == 0, out.output
    assert "dashboard  margi/dash.html  (setup 0 of 6)" in out.output


def test_init_names_the_dashboard(bare_repo, monkeypatch):
    monkeypatch.chdir(bare_repo)
    out = CliRunner().invoke(main, ["init", "--no-install"])
    assert out.exit_code == 0, out.output
    assert "Dashboard  file://" in out.output and "margi/dash.html   (open it in a browser)" in out.output
    assert "Next       write your plan" in out.output
    assert init(bare_repo, install=False, commit=False).first is False  # margi is there now


def test_browser_opens_only_on_first_run_at_a_terminal():
    assert should_open_dashboard(True, False, True, {})
    assert not should_open_dashboard(False, False, True, {})  # re-run
    assert not should_open_dashboard(True, True, True, {})  # --no-open
    assert not should_open_dashboard(True, False, False, {})  # piped, or an agent ran it
    assert not should_open_dashboard(True, False, True, {"CI": "true"})
