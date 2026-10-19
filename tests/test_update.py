import io
import json
import shutil
import subprocess

import pytest
from click.testing import CliRunner
from conftest import run_git

from margi import __version__, update as update_mod
from margi.cli import main
from margi.update import UpdateError, is_newer, latest_version, update


@pytest.fixture
def delegated(monkeypatch):
    """Records the hand-over to `uv tool run` instead of running it; everything else runs as usual."""
    calls = []
    which, run = shutil.which, subprocess.run
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/uv" if name == "uv" else which(name))
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: (calls.append((cmd, kw)) or
                                                              subprocess.CompletedProcess(cmd, 0))
                        if cmd[0] == "/usr/bin/uv" else run(cmd, **kw))
    return calls


def _head(root):
    return run_git(root, "rev-parse", "HEAD").stdout.strip()


def test_newer_release_hands_over_to_its_init(repo, monkeypatch, delegated):
    monkeypatch.setattr(update_mod, "latest_version", lambda: "99.0.0")
    result = update(repo)
    assert result.delegated and result.changed and result.target == "99.0.0"
    (cmd, kw), = delegated
    assert cmd == ["/usr/bin/uv", "tool", "run", "--from", "margi==99.0.0", "margi", "init", "--no-open"]
    assert kw["cwd"] == repo and "VIRTUAL_ENV" not in kw["env"]


def test_no_commit_is_passed_on(repo, delegated):
    update(repo, to="99.0.0", commit=False)
    assert delegated[0][0][-1] == "--no-commit"


def test_failed_handover_is_an_error(repo, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1))
    with pytest.raises(UpdateError, match="could not finish"):
        update(repo, to="99.0.0")


def test_same_version_reruns_init_in_process(repo, monkeypatch, delegated):
    monkeypatch.setattr(update_mod, "latest_version", lambda: __version__)
    monkeypatch.setattr(update_mod, "init", lambda root, **kw: update_mod.InitReport())  # no uv in the tests
    before = _head(repo)
    result = update(repo)
    assert not result.delegated and not result.changed and not delegated
    assert _head(repo) == before


def test_same_version_restores_deleted_skill(repo, monkeypatch):
    monkeypatch.setattr(update_mod, "latest_version", lambda: __version__)
    real_init = update_mod.init
    monkeypatch.setattr(update_mod, "init", lambda root, **kw: real_init(root, install=False, **kw))
    shutil.rmtree(repo / ".agents/skills/margi-challenge")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-q", "-m", "oops", "--no-verify")
    result = update(repo)
    assert result.changed and (repo / ".agents/skills/margi-challenge/SKILL.md").exists()
    assert run_git(repo, "log", "-2", "--format=%s").stdout.splitlines()[1].startswith(f"chore: update margi {__version__}")


def test_older_latest_does_not_downgrade(repo, monkeypatch, delegated):
    monkeypatch.setattr(update_mod, "__version__", "99.0.0")
    monkeypatch.setattr(update_mod, "latest_version", lambda: "1.0.0")
    assert not update(repo).changed and not delegated
    update(repo, to="1.0.0")  # but an explicit --to does
    assert delegated[0][0][4] == "margi==1.0.0"


def test_check_changes_nothing(repo, monkeypatch, delegated):
    monkeypatch.setattr(update_mod, "latest_version", lambda: "99.0.0")
    before = _head(repo)
    result = update(repo, check=True)
    assert result.target == "99.0.0" and not result.changed and not delegated and _head(repo) == before


def test_needs_margi_set_up(bare_repo):
    with pytest.raises(UpdateError, match="uvx margi init"):
        update(bare_repo, to="99.0.0")


def test_latest_version_reads_pypi(monkeypatch):
    body = io.BytesIO(json.dumps({"info": {"version": "1.2.3"}}).encode())
    monkeypatch.setattr(update_mod.urllib.request, "urlopen", lambda url, timeout: body)
    assert latest_version() == "1.2.3"

    def offline(url, timeout):
        raise OSError("no network")

    monkeypatch.setattr(update_mod.urllib.request, "urlopen", offline)
    with pytest.raises(UpdateError, match="--to"):
        latest_version()


def test_is_newer():
    assert is_newer("0.10.0", "0.9.1") and not is_newer("0.4.1", "0.4.1") and not is_newer("0.4.0", "0.4.1")
    assert is_newer("1.0.0", "0.0.0+unknown") and is_newer("1.0.0rc1", "0.4.1")


def test_cli_check(repo, monkeypatch):
    monkeypatch.chdir(repo)
    monkeypatch.setattr(update_mod, "latest_version", lambda: "99.0.0")
    out = CliRunner().invoke(main, ["update", "--check"])
    assert out.exit_code == 0 and "99.0.0 is available" in out.output
