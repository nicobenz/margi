import json

from click.testing import CliRunner
from conftest import run_git

from margi.cli import main
from margi.config import load
from margi.finalize import finalize
from margi.lifecycle import respond
from margi.todos_sync import github_sync, sync_accepted, todo_done, todo_items, write_md

TODOS = "margi/todos"


def dash(repo):
    text = (repo / "margi/dash/data.js").read_text()
    return json.loads(text[text.index("{"):text.rindex("}") + 1])


def commit_margi(repo, msg="margi: todos"):
    run_git(repo, "add", "-A", "margi")
    run_git(repo, "commit", "-qm", msg)


def test_local_by_default_and_legacy_synced_keeps_github(repo, cfg):
    assert github_sync(cfg) is False
    path = repo / "thesis.config.yml"
    path.write_text(path.read_text().replace("  sync: false", ""))
    assert github_sync(load(repo)) is False
    write_md(repo / TODOS / "synced/t0-x.md", {"id": "t0", "title": "Old", "status": "synced", "issue": 3}, "b")
    assert github_sync(load(repo)) is True
    assert [(t["id"], t["state"]) for t in todo_items(load(repo))] == [("t0", "open")]


def test_accepting_opens_locally_without_gh(repo, cfg, monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")  # no gh anywhere
    write_md(repo / TODOS / "proposed/t1-a.md", {"id": "t1", "title": "Do A", "status": "accepted", "comments": ["c1"]}, "Body")
    write_md(repo / TODOS / "proposed/t2-b.md", {"id": "t2", "title": "Do B", "status": "proposed"}, "Body")
    report = sync_accepted(cfg)
    assert report.opened == ["t1"] and not report.created
    states = {t["id"]: t["state"] for t in todo_items(cfg)}
    assert states == {"t1": "open", "t2": "proposed"}
    write_md(repo / TODOS / "close/t1.md", {"todo": "t1", "status": "accepted"}, "Evidence: chapters/x.typ:4")
    report = sync_accepted(cfg)
    assert report.done == ["t1"]
    done = next(t for t in todo_items(cfg) if t["id"] == "t1")
    assert done["state"] == "done" and done["done_by"] == "margi"


def test_student_marks_done_with_a_note(repo, cfg):
    write_md(repo / TODOS / "open/t1-a.md", {"id": "t1", "title": "Do A", "status": "open"}, "Body")
    commit_margi(repo)
    moved, sha = todo_done(cfg, ["t1"], "Rewrote the paragraph myself.")
    assert moved[0].name == "t1-a.md" and sha
    t = next(t for t in todo_items(cfg) if t["id"] == "t1")
    assert (t["state"], t["done_by"], t["note"]) == ("done", "student", "Rewrote the paragraph myself.")
    assert run_git(repo, "log", "-1", "--format=%an|%s").stdout.strip() == "Human Writer|margi: todo done t1"


def test_cli_refuses_unknown_todo(repo, monkeypatch):
    monkeypatch.chdir(repo)
    out = CliRunner().invoke(main, ["todo-done", "t9"])
    assert out.exit_code != 0 and "no open todo t9" in out.output


def test_closed_comments_mark_a_todo_as_looking_done(repo, cfg):
    staging = repo / "margi/.staging"
    staging.mkdir(parents=True, exist_ok=True)
    comment = {"id": "c1", "category": "argument", "severity": "major", "body": "Needs evidence.",
               "anchor": {"file": "chapters/prior-work.typ", "line_start": 5, "line_end": 5,
                          "quote": "Moretti proposed counting instead of reading."}}
    (staging / "grade.json").write_text(json.dumps({"command": "grade", "scope": "2.1", "summary": "ok",
                                                    "scores": {"argument": {"score": 3, "max": 5, "rationale": "r"}},
                                                    "comments": [comment]}))
    finalize(cfg)
    write_md(repo / TODOS / "open/t1-a.md", {"id": "t1", "title": "Add evidence", "status": "open", "comments": ["c1"]}, "Body")
    commit_margi(repo)
    respond(cfg, [("c1", "wont_fix")])
    d = dash(repo)
    todo = next(t for t in d["todos"] if t["id"] == "t1")
    assert todo["comments"] == [{"ref": "c1", "state": "wont_fix"}] and todo["comments_closed"]
    assert any(s["command"] == "/margi todos" and "look" in s["reason"] for s in d["next_steps"])
