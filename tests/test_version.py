import tomllib
from pathlib import Path

from margi import __version__


def test_version_matches_pyproject():
    pyproject = tomllib.loads((Path(__file__).resolve().parent.parent / "pyproject.toml").read_text())
    assert __version__ == pyproject["project"]["version"]
