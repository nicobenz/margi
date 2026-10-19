import json

from click.testing import CliRunner
from conftest import human_commit, run_git

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


def test_finalize_ends_with_next_step_and_dashboard(repo, monkeypatch):
    monkeypatch.chdir(repo)
    out = CliRunner().invoke(main, ["finalize", "--message", "noop"])
    assert out.exit_code == 0, out.output
    tail = out.output.rstrip().splitlines()[-2:]
    assert tail[0].startswith("  next       /margi propose  Write your plan into PROPOSAL.md first")
    assert tail[1].startswith("  dashboard  file://") and "margi/dash.html  (reload it if it is open; setup 0 of 6)" in tail[1]


def test_propose_reason_follows_the_plan(repo, cfg):
    from margi.dashboard import collect

    first = collect(cfg)["next_steps"][0]
    assert first["command"] == "/margi propose" and "Write your plan" in first["reason"]
    (repo / "PROPOSAL.md").write_text((repo / "PROPOSAL.md").read_text() + "\nMy research question.\n")
    human_commit(repo, "plan", "PROPOSAL.md")
    first = collect(cfg)["next_steps"][0]
    assert first["command"] == "/margi propose" and "grading needs" in first["reason"]


def test_status_ends_with_the_handover_and_hides_plumbing(repo, monkeypatch):
    monkeypatch.chdir(repo)
    out = CliRunner().invoke(main, ["status"])
    assert out.exit_code == 0, out.output
    assert "self-reported" not in out.output and "(none)" not in out.output
    assert out.output.rstrip().splitlines()[-1].startswith("  dashboard  file://")


def test_init_names_the_dashboard(bare_repo, monkeypatch):
    monkeypatch.chdir(bare_repo)
    out = CliRunner().invoke(main, ["init", "--no-install"])
    assert out.exit_code == 0, out.output
    assert "Dashboard  file://" in out.output and "margi/dash.html   (open it in a browser)" in out.output
    assert "Next       write your plan" in out.output and "type `claude` here" in out.output
    assert "  wrote " not in out.output and "--verbose lists them" in out.output
    assert init(bare_repo, install=False, commit=False).first is False  # margi is there now


def test_browser_opens_only_on_first_run_at_a_terminal():
    assert should_open_dashboard(True, False, True, {})
    assert not should_open_dashboard(False, False, True, {})  # re-run
    assert not should_open_dashboard(True, True, True, {})  # --no-open
    assert not should_open_dashboard(True, False, False, {})  # piped, or an agent ran it
    assert not should_open_dashboard(True, False, True, {"CI": "true"})


def test_next_shows_setup_steps_and_inventory_without_writing(repo, monkeypatch):
    monkeypatch.chdir(repo)
    before = run_git(repo, "status", "--porcelain").stdout
    out = CliRunner().invoke(main, ["next"])
    assert out.exit_code == 0, out.output
    assert "Getting started  0 of 6 done" in out.output
    assert "[>] Write your plan into PROPOSAL.md and save it" in out.output
    assert "/margi propose" in out.output.split("Next steps", 1)[1]
    assert "Plan          PROPOSAL.md still the template" in out.output
    assert "Submission    no date documented" in out.output
    assert "Guide tab" in out.output
    assert run_git(repo, "status", "--porcelain").stdout == before  # read-only


def test_help_is_routed_and_allowed():
    from margi.resources import skills_dir, templates_dir

    skill = (skills_dir() / "margi" / "SKILL.md").read_text()
    assert "`/margi help`, or `/margi` alone" in skill and (skills_dir() / "margi/commands/help.md").is_file()
    assert "Bash(uv run margi next:*)" in json.loads((templates_dir() / "claude-settings.json").read_text())["permissions"]["allow"]


def test_finalize_without_draft_warns_when_it_commits(repo, monkeypatch):
    monkeypatch.chdir(repo)
    (repo / "margi/docs/method.md").write_text("# Method\n\nChanged by hand.\n")
    out = CliRunner().invoke(main, ["finalize"])
    assert out.exit_code == 0, out.output
    assert "no draft in margi/.staging/" in out.output
    quiet = CliRunner().invoke(main, ["finalize", "--message", "noop"])
    assert "no draft" not in quiet.output


def test_open_opens_the_dashboard_only_when_it_changed(repo, cfg, monkeypatch):
    import webbrowser

    opened = []
    monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url) or True)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.chdir(repo)
    run = lambda *a: CliRunner().invoke(main, ["open", *a]).output.strip()  # noqa: E731
    assert run().endswith("margi/dash.html  (opened in your browser; setup 0 of 6)")
    assert opened == [(repo / "margi/dash.html").resolve().as_uri()]
    assert not run_git(repo, "status", "--porcelain").stdout  # the stamp is gitignored
    assert run().endswith("(unchanged since it was last opened; setup 0 of 6)") and len(opened) == 1
    assert "opened in your browser" in run("--always") and len(opened) == 2
    (repo / "PROPOSAL.md").write_text((repo / "PROPOSAL.md").read_text() + "\nMy research question.\n")
    human_commit(repo, "plan", "PROPOSAL.md")
    refresh(cfg)
    assert "opened in your browser; setup 1 of 6" in run() and len(opened) == 3


def test_open_never_opens_in_ci(repo, monkeypatch):
    import webbrowser

    monkeypatch.setattr(webbrowser, "open", lambda url: (_ for _ in ()).throw(AssertionError(url)))
    monkeypatch.setenv("CI", "true")
    monkeypatch.chdir(repo)
    out = CliRunner().invoke(main, ["open"])
    assert out.exit_code == 0 and out.output.rstrip().endswith("(open it in a browser; setup 0 of 6)")
