from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from margi.config import load
from margi.init import init

FIXTURE = Path(__file__).parent / "fixtures" / "typst-thesis"


def run_git(root: Path, *args: str, env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, env=env, check=check)


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    # the commit-msg hook calls `margi`; make the venv's entry point visible
    monkeypatch.setenv("PATH", f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Human Writer")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "human@example.org")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Human Writer")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "human@example.org")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("MARGI_MODEL", raising=False)
    monkeypatch.delenv("MARGI_HARNESS", raising=False)
    (tmp_path / "home").mkdir()


@pytest.fixture
def bare_repo(tmp_path) -> Path:
    root = tmp_path / "thesis"
    shutil.copytree(FIXTURE, root)
    run_git(root, "init", "-q", "-b", "main")
    run_git(root, "add", "-A")
    run_git(root, "commit", "-q", "-m", "initial draft")
    return root


@pytest.fixture
def repo(bare_repo) -> Path:
    init(bare_repo)
    return bare_repo


@pytest.fixture
def cfg(repo):
    return load(repo)


def human_commit(root: Path, message: str, *paths: str, check: bool = True) -> subprocess.CompletedProcess:
    run_git(root, "add", "-A", "--", *paths)
    return run_git(root, "commit", "-q", "-m", message, check=check)
