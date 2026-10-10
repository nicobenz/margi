"""Load thesis.config.yml with defaults."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .gitutil import is_repo

CONFIG_NAME = "thesis.config.yml"
MARGI_DIR = "margi"

DEFAULTS: dict[str, Any] = {
    "format": "typst",
    "protect_thesis": True,
    "main": "main.typ",
    "sections": {},
    "count": "chars",  # chars | chars_no_spaces | words
    "propose": {"source": "PROPOSAL.md"},
    "literature": {"dir": "lit", "bib": None},
    "rubric": "default",
    "docs": {"min_completeness": 0.7},
    "ai_identity": {"name": "margi-bot", "email": "margi-bot@users.noreply.github.com"},
    "github": {"label": "margi"},
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


def load(root: Path) -> Config:
    path = root / CONFIG_NAME
    raw: dict = {}
    if path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if "onboard" in raw and "propose" not in raw:  # configs written before the rename
        raw["propose"] = raw.pop("onboard")
    return Config(root=root, data=_merge(DEFAULTS, raw), has_git=is_repo(root))
