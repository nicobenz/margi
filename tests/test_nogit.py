import json
import shutil

import pytest
from click.testing import CliRunner
from conftest import FIXTURE, run_git
from test_finalize import DRAFT, stage

from margi.cli import main
from margi.config import load
from margi.finalize import finalize
from margi.init import init


@pytest.fixture
def plain_dir(tmp_path):
    root = tmp_path / "thesis"
    shutil.copytree(FIXTURE, root)
    return root


@pytest.fixture
def plain(plain_dir):
    init(plain_dir, install=False)
    return plain_dir


def test_init_without_git_scaffolds_and_skips_commits(plain_dir):
    report = init(plain_dir, install=False)
    assert (plain_dir / "thesis.config.yml").exists() and (plain_dir / "margi/docs").is_dir()
    assert report.commits == []
    assert any("hooksPath" in s for s in report.skipped) and any("commits" in s for s in report.skipped)
    assert not (plain_dir / ".git").exists()


def test_finalize_without_git_writes_record_without_commit(plain):
    cfg = load(plain)
    assert not cfg.has_git
    (plain / "main.typ").write_text("edited by the human, not committed anywhere\n")
    stage(plain, DRAFT)
    result = finalize(cfg, model="claude-x", model_source="self-reported")
    assert result.commit is None and len(result.records) == 1
    prov = json.loads(result.records[0].read_text())["provenance"]
    assert prov["head_sha"] is None
    assert prov["files"][0]["source"] == "worktree" and len(prov["files"][0]["sha256"]) == 64


def test_cli_without_git(plain, monkeypatch):
    monkeypatch.chdir(plain / "chapters")
    runner = CliRunner()
    check = runner.invoke(main, ["finalize", "--check"])
    assert check.exit_code == 0 and "no git repository" in check.output
    out = runner.invoke(main, ["outline"])
    assert out.exit_code == 0 and "not committed" in out.output
    assert any("outline" in p.name for p in (plain / "margi/feedback").glob("*.json"))
    guard = runner.invoke(main, ["guard", "--range", "HEAD"])
    assert guard.exit_code != 0 and "needs a git repository" in guard.output


def test_git_features_resume_after_git_init(plain):
    run_git(plain, "init", "-q", "-b", "main")
    report = init(plain, install=False)
    assert report.skipped == [] and len(report.commits) == 2
    assert run_git(plain, "config", "--get", "core.hooksPath").stdout.strip() == ".githooks"
    assert load(plain).has_git
