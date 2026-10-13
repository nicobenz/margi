"""Claude Code permissions for the thesis repo, driven by `protect_thesis` in thesis.config.yml.

The template's `ask` list (`margi save`, `margi author`) makes Claude Code ask the student before
the agent saves their work or changes who it is saved as; an allow rule that would skip that
question (such as "always allow" in settings.local.json) is removed by `margi init`.

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
LOCAL = ".claude/settings.local.json"
CONSENT = ("uv run margi save", "uv run margi author")  # commands that must stay behind a question


def _template() -> dict:
    return json.loads((templates_dir() / "claude-settings.json").read_text(encoding="utf-8"))


def write(root: Path, protect: bool) -> None:
    """Merge margi's permissions into .claude/settings.json, keeping entries the user added."""
    path = root / SETTINGS
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    t = _template()["permissions"]
    perms = data.setdefault("permissions", {})
    perms["allow"] = [a for a in dict.fromkeys(perms.get("allow", []) + t["allow"]) if not skips_consent(a)]
    perms["ask"] = list(dict.fromkeys(perms.get("ask", []) + t["ask"]))
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


def skips_consent(rule: str) -> bool:
    """Is this an allow rule for `margi save`/`margi author` (or all of margi) that would skip the question?

    Broader rules (`Bash`, `Bash(uv run:*)`) are the user's own business; Claude Code checks `ask`
    rules before `allow` rules, so they don't silence the question.
    """
    rule = rule.strip()
    if not (rule.startswith("Bash(") and rule.endswith(")")):
        return False
    pattern = rule[5:-1].strip()
    prefix = pattern[:-2] if pattern.endswith(":*") else pattern[:-1] if pattern.endswith("*") else None
    if prefix is None:
        return pattern.startswith(CONSENT)
    prefix = prefix.rstrip()
    return prefix.startswith("uv run margi") and any(cmd.startswith(prefix) or prefix.startswith(cmd) for cmd in CONSENT)


def consent_overrides(root: Path) -> list[str]:
    """Allow rules in the settings files that skip the question before a save, as "file: rule"."""
    out = []
    for rel in (SETTINGS, LOCAL):
        path = root / rel
        try:
            allow = json.loads(path.read_text(encoding="utf-8")).get("permissions", {}).get("allow", []) if path.is_file() else []
        except ValueError:
            continue
        out += [f"{rel}: {a}" for a in allow if isinstance(a, str) and skips_consent(a)]
    return out


def remove_consent_overrides(root: Path) -> list[str]:
    """Drop those rules from settings.local.json (write() already keeps them out of settings.json)."""
    path = root / LOCAL
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return []
    allow = data.get("permissions", {}).get("allow", [])
    dropped = [a for a in allow if isinstance(a, str) and skips_consent(a)]
    if dropped:
        data["permissions"]["allow"] = [a for a in allow if a not in dropped]
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return dropped
