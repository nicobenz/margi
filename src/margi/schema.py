"""Validate drafts and records against the bundled JSON schema."""

from __future__ import annotations

import json
from functools import lru_cache

from jsonschema import Draft202012Validator

from .resources import schema_path


@lru_cache(maxsize=None)
def _validator(kind: str) -> Draft202012Validator:
    full = json.loads(schema_path().read_text(encoding="utf-8"))
    return Draft202012Validator({**full, "$ref": f"#/$defs/{kind}"})


def errors(obj: object, kind: str) -> list[str]:
    """Return human-readable validation errors (empty list = valid). kind: draft | record."""
    out = []
    for err in sorted(_validator(kind).iter_errors(obj), key=lambda e: list(e.absolute_path)):
        where = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{where}: {err.message}")
    return out
