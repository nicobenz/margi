"""`margi update`: move a thesis repository to the margi that is running.

Run it as `uvx margi@latest update`. Updating is `margi init` run by the new version: it re-pins the
dev dependency, re-copies the skills, rewrites the hook, CI workflow and agent settings, and commits
"chore: update margi X". The skills and templates must come from the new version, so an older copy
(`uv run margi update` from the repository's own .venv) stops and names the command instead of
installing its own, outdated files. `uvx` runs outside .venv, so `uv add` can replace the repository's
copy on every platform.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .config import CONFIG_NAME
from .init import InitError, InitReport, init

PYPI = "https://pypi.org/pypi/margi/json"
COMMAND = "uvx margi@latest update"


class UpdateError(RuntimeError):
    pass


def installed_version(root: Path) -> str | None:
    """The margi this repository was last set up with (init writes it next to the skills)."""
    path = root / ".agents" / "skills" / "margi" / "VERSION"
    return (path.read_text(encoding="utf-8").strip() or None) if path.is_file() else None


@dataclass
class UpdateResult:
    installed: str | None  # the repository's margi before this run
    current: str  # the margi running now
    latest: str | None  # None when PyPI could not be reached
    report: InitReport | None = None

    @property
    def changed(self) -> bool:
        return bool(self.report and self.report.commits)

    @property
    def outdated(self) -> bool:
        """A newer release exists than the margi running now."""
        return self.latest is not None and is_newer(self.latest, self.current)


def latest_version(timeout: float = 10) -> str:
    """The newest release on PyPI (prereleases excluded, as PyPI's `info.version` does)."""
    try:
        with urllib.request.urlopen(PYPI, timeout=timeout) as resp:
            return json.load(resp)["info"]["version"]
    except (OSError, ValueError, KeyError) as e:
        raise UpdateError(f"could not look up the latest margi on PyPI ({e})") from e


def _key(v: str) -> tuple[int, ...] | None:
    parts = v.split("+")[0].split(".")
    return tuple(int(p) for p in parts) if all(p.isdigit() for p in parts) else None


def is_newer(target: str, current: str) -> bool:
    """True when ``target`` is a later release than ``current``; unparsable versions compare by inequality."""
    t, c = _key(target), _key(current)
    if t is None or c is None:
        return target != current
    return t > c


def update(root: Path, *, commit: bool = True, check: bool = False) -> UpdateResult:
    """Install this margi's files and pin in ``root``. ``check`` only compares versions."""
    if not (root / CONFIG_NAME).exists():
        raise UpdateError(f"no {CONFIG_NAME} here; margi is not set up in this folder yet (run `uvx margi init`)")
    if check:
        return UpdateResult(installed_version(root), __version__, latest_version())
    try:
        latest = latest_version()
    except UpdateError:
        latest = None  # offline: uvx already chose the version, so update to this one
    result = UpdateResult(installed_version(root), __version__, latest)
    if result.outdated:
        raise UpdateError(f"this is margi {__version__}, but {latest} is available; run `{COMMAND}` "
                          "so the new version installs its own files")
    try:
        result.report = init(root, commit=commit)
    except InitError as e:
        raise UpdateError(str(e)) from e
    return result
