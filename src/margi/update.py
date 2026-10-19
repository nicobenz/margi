"""`margi update`: move a thesis repository to a newer margi.

Updating is `margi init` run by the new version: it re-pins the dev dependency, re-copies the
skills, rewrites the hook, CI workflow and agent settings, and commits "chore: update margi X".
The skills and templates must come from the new version, so when this process is older than the
target, it hands over to `uv tool run --from margi==<target> margi init` instead of running the
old init. When this process already is the target (`uvx margi@latest update`), init runs in-process.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .config import CONFIG_NAME
from .init import InitError, InitReport, init

PYPI = "https://pypi.org/pypi/margi/json"


class UpdateError(RuntimeError):
    pass


@dataclass
class UpdateResult:
    current: str
    target: str
    report: InitReport | None = None  # set when init ran in this process
    delegated: bool = False  # the target version's init ran in a subprocess

    @property
    def changed(self) -> bool:
        return self.delegated or bool(self.report and self.report.commits)


def latest_version(timeout: float = 10) -> str:
    """The newest release on PyPI (prereleases excluded, as PyPI's `info.version` does)."""
    try:
        with urllib.request.urlopen(PYPI, timeout=timeout) as resp:
            return json.load(resp)["info"]["version"]
    except (OSError, ValueError, KeyError) as e:
        raise UpdateError(f"could not look up the latest margi on PyPI ({e}); pass --to <version> to choose one") from e


def _key(v: str) -> tuple[int, ...] | None:
    parts = v.split("+")[0].split(".")
    return tuple(int(p) for p in parts) if all(p.isdigit() for p in parts) else None


def is_newer(target: str, current: str) -> bool:
    """True when ``target`` is a later release than ``current``; unparsable versions compare by inequality."""
    t, c = _key(target), _key(current)
    if t is None or c is None:
        return target != current
    return t > c


def _delegate(root: Path, target: str, *, commit: bool) -> None:
    uv = shutil.which("uv")
    if not uv:
        raise UpdateError("`uv` not found on PATH; margi is installed per repository with uv (https://docs.astral.sh/uv/)")
    cmd = [uv, "tool", "run", "--from", f"margi=={target}", "margi", "init", "--no-open"]
    if not commit:
        cmd.append("--no-commit")
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    if subprocess.run(cmd, cwd=root, env=env).returncode != 0:
        raise UpdateError(f"margi {target} could not finish the update (see above); your repository is unchanged "
                          "except for what it reported")


def update(root: Path, *, to: str | None = None, commit: bool = True, check: bool = False) -> UpdateResult:
    """Update margi in ``root`` to ``to`` (default: the latest release). ``check`` only compares versions."""
    if not (root / CONFIG_NAME).exists():
        raise UpdateError(f"no {CONFIG_NAME} here; margi is not set up in this folder yet (run `uvx margi init`)")
    target = to or latest_version()
    result = UpdateResult(current=__version__, target=target)
    if check:
        return result
    if target == __version__:
        try:
            result.report = init(root, commit=commit)
        except InitError as e:
            raise UpdateError(str(e)) from e
        return result
    if to is None and not is_newer(target, __version__):
        return result  # this copy is ahead of PyPI (a dev or path install): nothing to update to
    _delegate(root, target, commit=commit)
    result.delegated = True
    return result
