import os
import shutil
from pathlib import Path

import pytest
from conftest import human_commit, run_git

from margi.adapters.typst import TypstAdapter
from margi.config import load
from margi.init import init

REPO = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(not shutil.which("uv"), reason="needs uv")
def test_init_installs_margi_locally(bare_repo, monkeypatch):
    init(bare_repo, spec=str(REPO))
    assert (bare_repo / ".venv/bin/margi").exists()
    assert "margi" in (bare_repo / "pyproject.toml").read_text()
    tracked = run_git(bare_repo, "ls-files").stdout.split()
    assert "pyproject.toml" in tracked and "uv.lock" in tracked
    assert not any(p.startswith(".venv/") for p in tracked)

    # the hook must find the repo-local margi without a global install
    monkeypatch.setenv("PATH", os.pathsep.join(p for p in os.environ["PATH"].split(os.pathsep)
                                               if not (Path(p) / "margi").exists()))
    (bare_repo / "main.typ").write_text("= Changed\n")
    (bare_repo / "margi/docs/field.md").write_text("ai\n")
    proc = human_commit(bare_repo, "mixed", "main.typ", "margi/docs/field.md", check=False)
    assert proc.returncode != 0 and "not installed" not in proc.stderr and "mix" in proc.stderr


def test_init_bootstraps_empty_project(tmp_path):
    root = tmp_path / "fresh"
    root.mkdir()
    run_git(root, "init", "-q", "-b", "main")
    report = init(root, install=False)
    for rel in ("PROPOSAL.md", "main.typ", "chapters/01-introduction.typ", "refs.bib", "lit/.gitignore"):
        assert (root / rel).exists(), rel
    assert "PROPOSAL.md" in report.written
    tracked = run_git(root, "ls-files").stdout.split()
    assert "PROPOSAL.md" in tracked and "chapters/06-conclusion.typ" in tracked
    cfg = load(root)
    assert cfg["main"] == "main.typ" and cfg["literature"]["bib"] == "refs.bib"
    assert cfg["propose"]["source"] == "PROPOSAL.md"
    titles = [s.title for s in TypstAdapter(cfg).tree().children]
    assert titles[0] == "Introduction" and titles[-1] == "Conclusion"


def test_init_existing_project_gets_only_proposal(bare_repo):
    before = set(p.relative_to(bare_repo) for p in bare_repo.rglob("*.typ"))
    init(bare_repo, install=False)
    assert (bare_repo / "PROPOSAL.md").exists()
    assert not (bare_repo / "refs.bib").exists() and not (bare_repo / "chapters/01-introduction.typ").exists()
    assert set(p.relative_to(bare_repo) for p in bare_repo.rglob("*.typ")) == before


def test_reinit_keeps_proposal_and_retires_onboard_skill(repo):
    (repo / "PROPOSAL.md").write_text("# my own thoughts\n")
    old = repo / ".agents/skills/margi-onboard"
    old.mkdir(parents=True)
    (repo / ".claude/skills/margi-onboard").symlink_to(Path("../../.agents/skills/margi-onboard"))
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-q", "-m", "notes")
    init(repo, install=False)
    assert (repo / "PROPOSAL.md").read_text() == "# my own thoughts\n"
    assert not old.exists() and not (repo / ".claude/skills/margi-onboard").is_symlink()
    assert (repo / ".claude/skills/margi-propose/SKILL.md").exists()


def test_legacy_onboard_config_maps_to_propose(repo):
    cfg_file = repo / "thesis.config.yml"
    cfg_file.write_text(cfg_file.read_text().replace("propose:\n  source: PROPOSAL.md", "onboard:\n  source: expose.md"))
    assert load(repo)["propose"]["source"] == "expose.md"


def test_init_writes_no_agents_md(repo):
    assert not (repo / "AGENTS.md").exists()


def test_reinit_removes_legacy_agents_md_section(repo):
    legacy = "<!-- margi:begin -->\n## margi rules\nNever edit.\n<!-- margi:end -->\n"
    (repo / "AGENTS.md").write_text(legacy)
    human_commit(repo, "old margi", "AGENTS.md")
    init(repo, install=False)
    assert not (repo / "AGENTS.md").exists()
    assert "AGENTS.md" not in run_git(repo, "ls-files").stdout.split()

    (repo / "AGENTS.md").write_text("# My own rules\n\nBe concise.\n\n" + legacy)
    human_commit(repo, "own rules plus old margi", "AGENTS.md")
    init(repo, install=False)
    assert (repo / "AGENTS.md").read_text() == "# My own rules\n\nBe concise.\n"
    assert run_git(repo, "status", "--porcelain").stdout == ""


def _deny(root):
    import json
    return json.loads((root / ".claude/settings.json").read_text())["permissions"]["deny"]


def test_protect_thesis_switch_drives_claude_settings(repo):
    from margi.agent_settings import drift

    assert "Edit(**/*.typ)" in _deny(repo) and "Bash(git commit:*)" in _deny(repo)
    assert "(protect_thesis: true)" in run_git(repo, "log", "--format=%s").stdout

    # a human flips the switch and re-runs init: settings follow, and both land in one commit
    cfg = repo / "thesis.config.yml"
    cfg.write_text(cfg.read_text().replace("protect_thesis: true", "protect_thesis: false"))
    init(repo, install=False)
    deny = _deny(repo)
    assert "Edit(**/*.typ)" not in deny and "Bash(git commit:*)" not in deny
    assert "Edit(thesis.config.yml)" in deny and "Edit(.githooks/**)" in deny  # the switch stays human-only
    flip = run_git(repo, "log", "--format=%H %s", "--grep=update margi").stdout.split("\n")[0]
    assert flip.endswith("(protect_thesis: false)")
    files = run_git(repo, "show", "--name-only", "--format=", flip.split()[0]).stdout.split()
    assert "thesis.config.yml" in files and ".claude/settings.json" in files
    assert drift(load(repo)) is None

    # flipping back without re-running init is caught before the next margi run
    cfg.write_text(cfg.read_text().replace("protect_thesis: false", "protect_thesis: true"))
    human_commit(repo, "protect again", "thesis.config.yml")
    assert "protect_thesis: true" in drift(load(repo))


def test_protect_thesis_keeps_user_permissions(repo):
    import json
    path = repo / ".claude/settings.json"
    data = json.loads(path.read_text())
    data["permissions"]["deny"].append("Bash(rm:*)")
    path.write_text(json.dumps(data))
    human_commit(repo, "my own deny", ".claude/settings.json")
    cfg = repo / "thesis.config.yml"
    cfg.write_text(cfg.read_text().replace("protect_thesis: true", "protect_thesis: false"))
    init(repo, install=False)
    assert "Bash(rm:*)" in _deny(repo)
