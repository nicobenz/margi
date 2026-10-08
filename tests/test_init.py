import os
import shutil
from pathlib import Path

import pytest
from conftest import human_commit, run_git

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
