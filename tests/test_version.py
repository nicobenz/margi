import re
from pathlib import Path

from margi import __version__


def test_version_matches_pyproject():
    pyproject = (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text()
    assert __version__ == re.search(r'^version = "(.+)"$', pyproject, re.M).group(1)
