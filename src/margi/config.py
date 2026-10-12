"""Load thesis.config.yml with defaults."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .gitutil import git, is_repo

CONFIG_NAME = "thesis.config.yml"
MARGI_DIR = "margi"
PLACEHOLDER = ("User", "user@margi.local")  # who saves are recorded as when the student names nobody

DEFAULTS: dict[str, Any] = {
    "format": "typst",
    "protect_thesis": True,
    "main": "main.typ",
    "sections": {},
    "count": "chars",  # chars | chars_no_spaces | words
    "propose": {"source": "PROPOSAL.md"},
    "literature": {"dir": "lit", "bib": None},
    "docs": {"min_completeness": 0.7},
    "grade": {"precheck": "ask", "min_words": 150, "max_list_share": 0.5},
    "author": {"name": None, "email": None},  # unset: the student's git identity, else PLACEHOLDER
    "ai_identity": {"name": "margi-bot", "email": "margi-bot@users.noreply.github.com"},
    "github": {"label": "margi"},  # "sync" absent: see todos_sync.github_sync
}


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


@dataclass
class Config:
    root: Path
    data: dict = field(default_factory=dict)
    # Without git, margi still works but skips commits, the clean-tree check and the guard.
    has_git: bool = True

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    @property
    def margi_dir(self) -> Path:
        return self.root / MARGI_DIR

    @property
    def bot_name(self) -> str:
        return self.data["ai_identity"]["name"]

    @property
    def bot_email(self) -> str:
        return self.data["ai_identity"]["email"]

    @property
    def author(self) -> tuple[str, str]:
        """Who the student's saves (and their own margi records) are committed as.

        ``author`` in thesis.config.yml wins. A config without it (written before margi saved for
        the student) falls back to git's user.name/user.email, then to the placeholder.
        """
        a = self.data.get("author") or {}
        name, email = (a.get("name") or "").strip(), (a.get("email") or "").strip()
        if not name and self.has_git:
            name = git("config", "user.name", cwd=self.root, check=False).strip()
            email = email or git("config", "user.email", cwd=self.root, check=False).strip()
        return name or PLACEHOLDER[0], email or PLACEHOLDER[1]

    def author_env(self) -> dict[str, str]:
        """Environment for a git commit made on the student's behalf (author and committer)."""
        name, email = self.author
        return {"GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email,
                "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email}


def load(root: Path) -> Config:
    path = root / CONFIG_NAME
    raw: dict = {}
    if path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if "onboard" in raw and "propose" not in raw:  # configs written before the rename
        raw["propose"] = raw.pop("onboard")
    return Config(root=root, data=_merge(DEFAULTS, raw), has_git=is_repo(root))


AUTHOR_BLOCK = re.compile(r"^author:[^\n]*\n(?:[ \t]+\S[^\n]*\n?)*", re.M)
AUTHOR_COMMENT = ("# Who your saved versions are recorded as. Stays in this project; change it here any time\n"
                  "# (later saves use the new value) or ask your agent to.\n")


def author_block(name: str | None, email: str | None) -> str:
    q = lambda v: json.dumps(v, ensure_ascii=False) if v else "null"  # JSON strings are valid YAML
    return (f"author:\n"
            f"  name: {q(name or PLACEHOLDER[0])}\n"
            f"  email: {q(email)}\n")


def set_author(root: Path, name: str | None, email: str | None) -> None:
    """Rewrite the `author` block of thesis.config.yml, keeping everything else (comments included)."""
    path = root / CONFIG_NAME
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    block = author_block(name, email)
    if AUTHOR_BLOCK.search(text):
        text = AUTHOR_BLOCK.sub(lambda _: block, text, count=1)
    else:
        text = text.rstrip("\n") + ("\n\n" if text else "") + AUTHOR_COMMENT + block
    path.write_text(text, encoding="utf-8")
