from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from margi.config import load
from margi.init import init
from margi.resources import templates_dir

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
    # the fixture thesis is a few lines per section; tests not about the precheck grade it anyway
    template = (templates_dir() / "thesis.config.yml").read_text()
    (bare_repo / "thesis.config.yml").write_text(
        template.replace("{{main}}", "main.typ").replace("{{bib}}", "null").replace("precheck: ask ", "precheck: none"))
    init(bare_repo, install=False)
    return bare_repo


@pytest.fixture
def cfg(repo):
    return load(repo)


def human_commit(root: Path, message: str, *paths: str, check: bool = True) -> subprocess.CompletedProcess:
    run_git(root, "add", "-A", "--", *paths)
    return run_git(root, "commit", "-q", "-m", message, check=check)


def make_pdf(pages: list[list[str]], outline: list[tuple[str, int, int]] | None = None) -> bytes:
    """A minimal valid PDF, one Helvetica text line per string (line i sits at y = 780 - 14 i).

    `outline` adds top-level bookmarks as (title, page index, y).
    """
    objs = ["<< /Type /Catalog /Pages 2 0 R%s >>", None,
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"]
    kids = []
    for lines in pages:
        ops = "".join(f"BT /F1 9 Tf 40 {780 - 14 * i} Td ({line}) Tj ET\n" for i, line in enumerate(lines))
        objs.append(f"<< /Length {len(ops)} >>\nstream\n{ops}endstream")
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                    f"/Resources << /Font << /F1 3 0 R >> >> /Contents {len(objs)} 0 R >>")
        kids.append(f"{len(objs)} 0 R")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    if outline:
        root = len(objs) + 1
        first = root + 1
        objs.append(f"<< /Type /Outlines /First {first} 0 R /Last {first + len(outline) - 1} 0 R /Count {len(outline)} >>")
        for i, (title, page, y) in enumerate(outline):
            n = first + i
            links = (f" /Prev {n - 1} 0 R" if i else "") + (f" /Next {n + 1} 0 R" if i < len(outline) - 1 else "")
            objs.append(f"<< /Title ({title}) /Parent {root} 0 R{links} /Dest [{kids[page]} /XYZ 40 {y} 0] >>")
        objs[0] = objs[0] % f" /Outlines {root} 0 R"
    else:
        objs[0] = objs[0] % ""
    out, offsets = b"%PDF-1.4\n", []
    for n, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    return out + f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
