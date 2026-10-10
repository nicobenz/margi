"""Locate bundled skills and templates (installed wheel or source checkout)."""

from __future__ import annotations

from pathlib import Path

_PKG = Path(__file__).resolve().parent


def bundled_root() -> Path:
    installed = _PKG / "_bundled"
    if installed.is_dir():
        return installed
    # source checkout / editable install: repo root is two levels up from src/margi
    return _PKG.parent.parent


def skills_dir() -> Path:
    return bundled_root() / "skills"


def templates_dir() -> Path:
    return bundled_root() / "templates"


def schema_path() -> Path:
    return skills_dir() / "margi" / "schema" / "feedback.schema.json"
