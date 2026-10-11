import json
import os
import stat

from margi.config import load
from margi.todos_sync import read_md, sync_accepted, write_md

FAKE_GH = """#!/bin/sh
echo "$@" >> "$GH_LOG"
case "$1 $2" in
  "issue list") cat "$GH_ISSUES" ;;
  "issue create") echo "https://github.com/o/r/issues/42" ;;
esac
"""


def setup_gh(tmp_path, monkeypatch, issues):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(FAKE_GH)
    gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
    (tmp_path / "issues.json").write_text(json.dumps(issues))
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("GH_LOG", str(tmp_path / "gh.log"))
    monkeypatch.setenv("GH_ISSUES", str(tmp_path / "issues.json"))
    return tmp_path / "gh.log"


def sync_on(repo):
    path = repo / "thesis.config.yml"
    path.write_text(path.read_text().replace("sync: false", "sync: true"))
    return load(repo)


def test_only_accepted_items_sync(repo, tmp_path, monkeypatch):
    cfg = sync_on(repo)
    log = setup_gh(tmp_path, monkeypatch, [{"number": 7, "body": "x <!-- margi-id: t2 -->", "state": "OPEN"}])
    todos = repo / "margi/todos"
    write_md(todos / "proposed/t1-a.md", {"id": "t1", "title": "Do A", "status": "accepted"}, "Body A")
    write_md(todos / "proposed/t2-b.md", {"id": "t2", "title": "Do B", "status": "accepted"}, "Body B")
    write_md(todos / "proposed/t3-c.md", {"id": "t3", "title": "Do C", "status": "proposed"}, "Body C")
    write_md(todos / "close/9.md", {"issue": 9, "status": "accepted"}, "Evidence: done")
    write_md(todos / "close/10.md", {"issue": 10, "status": "proposed"}, "Evidence: maybe")

    report = sync_accepted(cfg)
    assert report.created == [("t1", 42)]
    assert report.reused == [("t2", 7)]  # deduplicated via margi-id marker
    assert report.closed == [9]
    assert (todos / "proposed/t3-c.md").exists() and (todos / "close/10.md").exists()
    meta, _ = read_md(todos / "open/t1-a.md")
    assert meta["issue"] == 42 and meta["status"] == "open"
    calls = log.read_text()
    assert "issue close 9" in calls and "issue close 10" not in calls
    assert calls.count("issue create") == 1


def test_nothing_accepted_means_no_gh_calls(repo, cfg, tmp_path, monkeypatch):
    log = setup_gh(tmp_path, monkeypatch, [])
    write_md(repo / "margi/todos/proposed/t1-a.md", {"id": "t1", "status": "proposed"}, "Body")
    report = sync_accepted(cfg)
    assert not report.created and not log.exists()


def test_issue_closed_on_github_finishes_its_todo(repo, tmp_path, monkeypatch):
    cfg = sync_on(repo)
    setup_gh(tmp_path, monkeypatch, [{"number": 5, "body": "x", "state": "CLOSED"}])
    write_md(repo / "margi/todos/open/t1-a.md", {"id": "t1", "title": "A", "status": "open", "issue": 5}, "Body")
    report = sync_accepted(cfg)
    assert report.done == ["t1"]
    meta, _ = read_md(repo / "margi/todos/done/t1-a.md")
    assert meta["done_by"] == "github"
