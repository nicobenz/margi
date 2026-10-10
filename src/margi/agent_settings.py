"""Claude Code permissions for the thesis repo, driven by `protect_thesis` in thesis.config.yml.

The template's `deny` list always applies: it keeps agents off margi's own plumbing, including
thesis.config.yml, so only a human can flip the switch. `deny_protect_thesis` (thesis sources and
git history commands) is added only while `protect_thesis` is true. The switch lives in a
committed file, so every change to it shows up in `git log -- thesis.config.yml`.
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import Config
from .resources import templates_dir

SETTINGS = ".claude/settings.json"


def _template() -> dict:
    return json.loads((templates_dir() / "claude-settings.json").read_text(encoding="utf-8"))


def write(root: Path, protect: bool) -> None:
    """Merge margi's permissions into .claude/settings.json, keeping entries the user added."""
    path = root / SETTINGS
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    t = _template()["permissions"]
    perms = data.setdefault("permissions", {})
    perms["allow"] = list(dict.fromkeys(perms.get("allow", []) + t["allow"]))
    managed = set(t["deny_protect_thesis"])
    deny = [d for d in perms.get("deny", []) if d not in managed] + t["deny"]
    if protect:
        deny += t["deny_protect_thesis"]
    perms["deny"] = list(dict.fromkeys(deny))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def drift(cfg: Config) -> str | None:
    """Why .claude/settings.json doesn't match `protect_thesis`, or None. No settings file: nothing to check."""
    path = cfg.root / SETTINGS
    if not path.is_file():
        return None
    try:
        deny = set(json.loads(path.read_text(encoding="utf-8")).get("permissions", {}).get("deny", []))
    except ValueError:
        return f"{SETTINGS} is not valid JSON"
    managed = set(_template()["permissions"]["deny_protect_thesis"])
    protect = bool(cfg["protect_thesis"])
    if protect and not managed <= deny:
        return f"thesis.config.yml sets protect_thesis: true, but {SETTINGS} lets agents edit the thesis"
    if not protect and managed & deny:
        return f"thesis.config.yml sets protect_thesis: false, but {SETTINGS} still blocks thesis edits"
    return None
