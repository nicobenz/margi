import io
import json
import shutil

import pytest
from click.testing import CliRunner
from conftest import run_git

from margi import __version__, update as update_mod
from margi.cli import main
from margi.update import UpdateError, installed_version, is_newer, latest_version, update


@pytest.fixture
def no_install(monkeypatch):
    """Run the real init without `uv add` (tests have no package index)."""
    real_init = update_mod.init
    monkeypatch.setattr(update_mod, "init", lambda root, **kw: real_init(root, install=False, **kw))


def _offline(*args, **kw):
    raise UpdateError("no network")


def _head(root):
    return run_git(root, "rev-parse", "HEAD").stdout.strip()


def _set_installed(root, version):
    (root / ".agents/skills/margi/VERSION").write_text(version + "\n")
    run_git(root, "add", "-A")
    run_git(root, "commit", "-q", "-m", "older margi", "--no-verify")


def test_update_installs_running_version(repo, monkeypatch, no_install):
    monkeypatch.setattr(update_mod, "latest_version", lambda: __version__)
    _set_installed(repo, "0.1.0")
    result = update(repo)
    assert result.installed == "0.1.0" and result.changed
    assert installed_version(repo) == __version__
    subjects = run_git(repo, "log", "-2", "--format=%s").stdout.splitlines()
    assert subjects[1].startswith(f"chore: update margi {__version__}") and subjects[0] == "margi: init"


def test_up_to_date_commits_nothing(repo, monkeypatch, no_install):
    monkeypatch.setattr(update_mod, "latest_version", lambda: __version__)
    before = _head(repo)
    assert not update(repo).changed and _head(repo) == before


def test_restores_deleted_skill(repo, monkeypatch, no_install):
    monkeypatch.setattr(update_mod, "latest_version", lambda: __version__)
    shutil.rmtree(repo / ".agents/skills/margi-challenge")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-q", "-m", "oops", "--no-verify")
    assert update(repo).changed and (repo / ".agents/skills/margi-challenge/SKILL.md").exists()


def test_outdated_copy_names_the_command(repo, monkeypatch, no_install):
    monkeypatch.setattr(update_mod, "latest_version", lambda: "99.0.0")
    before = _head(repo)
    with pytest.raises(UpdateError, match="uvx margi@latest update"):
        update(repo)
    assert _head(repo) == before


def test_offline_updates_to_running_version(repo, monkeypatch, no_install):
    monkeypatch.setattr(update_mod, "latest_version", _offline)
    _set_installed(repo, "0.1.0")
    assert update(repo).changed and installed_version(repo) == __version__


def test_check_changes_nothing(repo, monkeypatch):
    monkeypatch.setattr(update_mod, "latest_version", lambda: "99.0.0")
    before = _head(repo)
    result = update(repo, check=True)
    assert result.latest == "99.0.0" and result.installed == __version__ and not result.changed
    assert _head(repo) == before


def test_needs_margi_set_up(bare_repo):
    with pytest.raises(UpdateError, match="uvx margi init"):
        update(bare_repo)


def test_latest_version_reads_pypi(monkeypatch):
    body = io.BytesIO(json.dumps({"info": {"version": "1.2.3"}}).encode())
    monkeypatch.setattr(update_mod.urllib.request, "urlopen", lambda url, timeout: body)
    assert latest_version() == "1.2.3"

    def offline(url, timeout):
        raise OSError("no network")

    monkeypatch.setattr(update_mod.urllib.request, "urlopen", offline)
    with pytest.raises(UpdateError, match="PyPI"):
        latest_version()


def test_is_newer():
    assert is_newer("0.10.0", "0.9.1") and not is_newer("0.4.1", "0.4.1") and not is_newer("0.4.0", "0.4.1")
    assert is_newer("1.0.0", "0.0.0+unknown") and is_newer("1.0.0rc1", "0.4.1")


def test_cli_check(repo, monkeypatch):
    monkeypatch.chdir(repo)
    monkeypatch.setattr(update_mod, "latest_version", lambda: "99.0.0")
    out = CliRunner().invoke(main, ["update", "--check"])
    assert out.exit_code == 0 and "99.0.0 is available" in out.output and "uvx margi@latest update" in out.output


def test_cli_update_reports_versions(repo, monkeypatch, no_install):
    monkeypatch.chdir(repo)
    monkeypatch.setattr(update_mod, "latest_version", lambda: __version__)
    _set_installed(repo, "0.1.0")
    out = CliRunner().invoke(main, ["update"])
    assert out.exit_code == 0 and f"updated from 0.1.0 to {__version__}" in out.output
