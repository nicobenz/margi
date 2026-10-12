import json
import shutil

import pytest
from click.testing import CliRunner
from conftest import FIXTURE, run_git
from test_finalize import DRAFT, stage

from margi import agent_settings
from margi.cli import main
from margi.config import load, set_author
from margi.finalize import FinalizeError, ensure_clean, finalize
from margi.guard import check_range
from margi.init import init
from margi.save import SaveError, counts, label, pending, prompt, save


def edit(repo):
    (repo / "chapters").mkdir(exist_ok=True)
    (repo / "main.typ").write_text((repo / "main.typ").read_text() + "\nA new paragraph, by hand.\n")
    (repo / "refs.bib").write_text("@book{a, title={A}}\n@article{b, title={B}}\n@comment{x}\n")
    (repo / "notes.md").write_text("loose thoughts\n")


def test_prompt_lists_exactly_what_would_be_saved(repo, cfg):
    edit(repo)
    p = pending(cfg)
    text = prompt(cfg, p)
    assert text.startswith("Your thesis has changes that aren't saved yet.")
    assert "main.typ" in text and "+27 chars" in text
    assert "refs.bib" in text and "+2 entries" in text
    assert "notes.md" in text and "new file" in text
    assert "stays on this computer" in text
    assert text.splitlines()[-1] == f"To save, run: uv run margi save --expect {p.digest}"
    assert "Human Writer" not in text  # margi never echoes the name


def test_start_of_run_offers_save_end_of_run_does_not(repo, cfg):
    edit(repo)
    with pytest.raises(FinalizeError, match="aren't saved yet"):
        ensure_clean(cfg)
    stage(repo, DRAFT)
    with pytest.raises(FinalizeError, match="changed during this run") as e:
        finalize(cfg)
    assert "margi save" not in str(e.value)


def test_save_commits_as_the_student_with_trailer(repo, cfg):
    edit(repo)
    result = save(cfg, pending(cfg).digest)
    log = run_git(repo, "log", "-1", "--format=%an|%ae|%cn|%s|%(trailers:key=Margi-Save,valueonly)").stdout.strip()
    assert log.startswith("Human Writer|human@example.org|Human Writer|save: 3 files, +")
    assert result.files == 3 and result.remote is None and not result.pushed
    assert pending(cfg).items == []
    ensure_clean(cfg)
    assert check_range(repo, cfg, "HEAD") == {}
    assert counts(cfg) == (1, 2)  # the save, and the fixture's own first commit


def test_save_refuses_when_files_changed_since_the_summary(repo, cfg):
    edit(repo)
    digest = pending(cfg).digest
    (repo / "notes.md").write_text("changed after the summary\n")
    head = run_git(repo, "rev-parse", "HEAD").stdout
    with pytest.raises(SaveError, match="changed since the summary") as e:
        save(cfg, digest)
    assert "To save, run:" in str(e.value)
    assert run_git(repo, "rev-parse", "HEAD").stdout == head
    assert run_git(repo, "diff", "--cached", "--name-only").stdout == ""


def test_nothing_to_save(repo, cfg):
    with pytest.raises(SaveError, match="nothing to save"):
        save(cfg, "whatever")


def test_save_leaves_margi_files_alone(repo, cfg):
    (repo / "main.typ").write_text("by hand\n")
    (repo / "margi/docs/notes.md").write_text("an uncommitted margi file\n")
    p = pending(cfg)
    assert [i.path for i in p.items] == ["main.typ"]
    save(cfg, p.digest)
    assert run_git(repo, "show", "--name-only", "--format=", "HEAD").stdout.split() == ["main.typ"]
    assert "margi/docs/notes.md" in run_git(repo, "status", "--porcelain").stdout


def test_placeholder_author_and_the_one_hint(repo):
    set_author(repo, None, None)
    run_git(repo, "add", "thesis.config.yml")
    run_git(repo, "commit", "-q", "-m", "author back to the placeholder")
    cfg = load(repo)
    assert cfg.author == ("User", "user@margi.local")
    (repo / "main.typ").write_text("by hand\n")
    assert 'recorded as "User"' in prompt(cfg)
    save(cfg, pending(cfg).digest)
    assert run_git(repo, "log", "-1", "--format=%an <%ae>").stdout.strip() == "User <user@margi.local>"
    (repo / "main.typ").write_text("more, by hand\n")
    assert "recorded as" not in prompt(cfg)  # only until the first save


def test_save_pushes_to_a_remote(repo, cfg, tmp_path):
    remote = tmp_path / "remote.git"
    run_git(tmp_path, "init", "-q", "--bare", str(remote))
    run_git(repo, "remote", "add", "origin", str(remote))
    edit(repo)
    assert "and uploads it to" in prompt(cfg)
    result = save(cfg, pending(cfg).digest)
    assert result.pushed and result.push_error is None
    assert run_git(remote, "log", "-1", "--format=%s", "main").stdout.startswith("save: 3 files")


def test_failed_push_keeps_the_local_save(repo, cfg, tmp_path):
    run_git(repo, "remote", "add", "origin", str(tmp_path / "missing.git"))
    edit(repo)
    result = save(cfg, pending(cfg).digest)
    assert not result.pushed and result.push_error
    assert run_git(repo, "log", "-1", "--format=%s").stdout.startswith("save:")


@pytest.mark.parametrize("url, expected", [
    ("https://github.com/user/thesis.git", "github.com/user/thesis"),
    ("git@github.com:user/thesis.git", "github.com/user/thesis"),
    ("ssh://git@gitlab.example.org:2222/group/thesis", "gitlab.example.org/group/thesis"),
    ("https://token@codeberg.org/user/thesis/", "codeberg.org/user/thesis"),
])
def test_remote_label(url, expected):
    assert label(url) == expected


def test_cli_save_and_author(repo, monkeypatch):
    monkeypatch.chdir(repo)
    runner = CliRunner()
    edit(repo)
    digest = pending(load(repo)).digest
    out = runner.invoke(main, ["save", "--expect", digest])
    assert out.exit_code == 0 and out.output.startswith("Saved as yours · ") and "3 files" in out.output
    out = runner.invoke(main, ["author", "--name", "Ada Lovelace"])
    assert out.exit_code == 0 and "Ada" not in out.output
    assert load(repo).author == ("Ada Lovelace", "human@example.org")
    out = runner.invoke(main, ["save", "--expect", "stale"])
    assert out.exit_code != 0 and "changed since the summary" in out.output


def test_init_creates_the_repository_and_records_the_author(tmp_path):
    root = tmp_path / "thesis"
    shutil.copytree(FIXTURE, root)
    report = init(root, install=False, author=("Ada Lovelace", None))
    assert (root / ".git").is_dir() and len(report.commits) == 2 and report.remote is None
    assert load(root).author == ("Ada Lovelace", "user@margi.local")
    assert run_git(root, "log", "--reverse", "--format=%an|%s").stdout.splitlines()[0].startswith(
        "Ada Lovelace|chore: install margi")
    assert ".venv/" in (root / ".gitignore").read_text() and "/main.pdf" in (root / ".gitignore").read_text()
    assert not (root / ".github").exists()
    settings = json.loads((root / ".claude/settings.json").read_text())["permissions"]
    assert "Bash(uv run margi save:*)" in settings["ask"]
    assert not any(agent_settings.skips_consent(a) for a in settings["allow"])


def test_init_writes_the_workflow_only_for_github(tmp_path):
    root = tmp_path / "thesis"
    shutil.copytree(FIXTURE, root)
    run_git(root, "init", "-q", "-b", "main")
    run_git(root, "remote", "add", "origin", "git@github.com:user/thesis.git")
    report = init(root, install=False)
    assert (root / ".github/workflows/margi-guard.yml").exists()
    assert report.remote == "github.com/user/thesis"


def test_init_removes_always_allow_for_saving(repo):
    local = repo / ".claude/settings.local.json"
    local.write_text(json.dumps({"permissions": {"allow": ["Bash(uv run margi save --expect 0123)", "Bash(ls:*)"]}}))
    assert agent_settings.consent_overrides(repo) == [".claude/settings.local.json: Bash(uv run margi save --expect 0123)"]
    init(repo, install=False)
    assert json.loads(local.read_text())["permissions"]["allow"] == ["Bash(ls:*)"]
    assert agent_settings.consent_overrides(repo) == []


@pytest.mark.parametrize("rule, skips", [
    ("Bash(uv run margi save:*)", True),
    ("Bash(uv run margi:*)", True),
    ("Bash(uv run margi author --name x)", True),
    ("Bash(uv run margi finalize:*)", False),
    ("Bash(uv run:*)", False),
    ("Bash", False),
])
def test_skips_consent(rule, skips):
    assert agent_settings.skips_consent(rule) is skips
