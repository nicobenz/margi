import json

from conftest import human_commit, run_git

from margi.config import load
from margi.guard import check_range


def test_init_creates_two_separate_commits(repo):
    log = run_git(repo, "log", "--format=%an|%s").stdout.splitlines()
    assert log[0] == "margi-bot|margi: init"
    assert log[1].startswith("Human Writer|chore: install margi")
    assert check_range(repo, load(repo), "HEAD~2..HEAD") == {}


def test_human_commit_of_thesis_text_is_accepted(repo):
    (repo / "main.typ").write_text((repo / "main.typ").read_text() + "\nMore text.\n")
    assert human_commit(repo, "write intro", "main.typ").returncode == 0


def test_mixed_commit_rejected(repo):
    (repo / "main.typ").write_text("changed\n")
    (repo / "margi/docs/open-questions.md").write_text("changed\n")
    proc = human_commit(repo, "margi: sneaky", "main.typ", "margi", check=False)
    assert proc.returncode != 0
    assert "mixes margi/" in proc.stderr


def test_margi_prefix_outside_margi_rejected(repo):
    (repo / "main.typ").write_text("changed\n")
    proc = human_commit(repo, "margi: rewrite intro", "main.typ", check=False)
    assert proc.returncode != 0
    assert "may only touch margi/" in proc.stderr


def test_human_commit_inside_margi_without_prefix_rejected(repo):
    (repo / "margi/docs/open-questions.md").write_text("# Open questions\n- x\n")
    proc = human_commit(repo, "notes", "margi", check=False)
    assert proc.returncode != 0
    assert "does not start with 'margi:'" in proc.stderr


def test_human_may_edit_docs_in_margi_commit(repo):
    (repo / "margi/docs/open-questions.md").write_text("# Open questions\n- x\n")
    assert human_commit(repo, "margi: fix docs by hand", "margi").returncode == 0


def test_bot_outside_margi_rejected(repo, monkeypatch):
    monkeypatch.setenv("GIT_AUTHOR_NAME", "margi-bot")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "margi-bot@users.noreply.github.com")
    (repo / "main.typ").write_text("bot was here\n")
    proc = human_commit(repo, "fix typo", "main.typ", check=False)
    assert proc.returncode != 0
    assert "bot" in proc.stderr


def _valid_record(cfg):
    from margi.finalize import build_record
    from datetime import datetime, timezone

    return build_record(cfg, {"command": "grade", "scope": "1"}, "r1", datetime.now(timezone.utc),
                        model=None, harness=None, model_source=None)


def test_feedback_append_only(repo, cfg):
    path = repo / "margi/feedback/20260101T000000Z_grade_1.json"
    path.write_text(json.dumps(_valid_record(cfg)))
    assert human_commit(repo, "margi: add record", "margi").returncode == 0

    path.write_text(json.dumps({**_valid_record(cfg), "summary": "tampered"}))
    proc = human_commit(repo, "margi: edit record", "margi", check=False)
    assert proc.returncode != 0 and "append-only" in proc.stderr

    run_git(repo, "checkout", "--", "margi")
    path.unlink()
    proc = human_commit(repo, "margi: delete record", "margi", check=False)
    assert proc.returncode != 0 and "append-only" in proc.stderr


def test_invalid_record_rejected(repo):
    (repo / "margi/feedback/bad.json").write_text(json.dumps({"command": "grade", "scope": "1"}))
    proc = human_commit(repo, "margi: bad", "margi", check=False)
    assert proc.returncode != 0 and "required property" in proc.stderr


def test_range_check_catches_no_verify(repo, cfg):
    (repo / "main.typ").write_text("x\n")
    (repo / "margi/docs/open-questions.md").write_text("y\n")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-q", "--no-verify", "-m", "mixed")
    problems = check_range(repo, cfg, "HEAD~1..HEAD")
    assert len(problems) == 1
