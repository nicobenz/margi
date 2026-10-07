from __future__ import annotations

from ..config import Config
from .base import Adapter, Section
from .typst import TypstAdapter

ADAPTERS = {"typst": TypstAdapter}


def get_adapter(cfg: Config) -> Adapter:
    fmt = cfg["format"]
    if fmt not in ADAPTERS:
        raise ValueError(f"unsupported format {fmt!r} (supported: {', '.join(ADAPTERS)})")
    return ADAPTERS[fmt](cfg)


__all__ = ["Adapter", "Section", "get_adapter"]
