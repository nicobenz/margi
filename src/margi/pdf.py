"""Extract literature PDFs to a plain-text cache the agent can read (margi/.cache/lit/)."""

from __future__ import annotations

import json
from pathlib import Path

from .config import MARGI_DIR, Config
from .gitutil import sha256

CACHE = f"{MARGI_DIR}/.cache/lit"


def find_pdfs(cfg: Config, only: list[str] | None = None) -> list[Path]:
    if only:
        return [(cfg.root / p).resolve() for p in only]
    lit = cfg.root / cfg["literature"]["dir"]
    return sorted(lit.rglob("*.pdf")) if lit.is_dir() else []


def extract(cfg: Config, only: list[str] | None = None) -> dict[str, dict]:
    """Extract each PDF once (keyed by content hash). Returns the index {pdf path: entry}."""
    from pypdf import PdfReader

    cache = cfg.root / CACHE
    cache.mkdir(parents=True, exist_ok=True)
    index_path = cache / "index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {}
    for pdf in find_pdfs(cfg, only):
        if not pdf.is_file():
            raise FileNotFoundError(f"PDF not found: {pdf}")
        data = pdf.read_bytes()
        digest = sha256(data)
        rel = pdf.relative_to(cfg.root.resolve()).as_posix()
        txt = cache / f"{digest[:16]}.txt"
        if not txt.exists():
            try:
                reader = PdfReader(pdf)
                pages = [f"--- page {i} ---\n{(p.extract_text() or '').strip()}" for i, p in enumerate(reader.pages, 1)]
                txt.write_text("\n\n".join(pages), encoding="utf-8")
            except Exception as e:  # pypdf raises many types on broken files
                txt.write_text(f"--- extraction failed: {e} ---", encoding="utf-8")
        index[rel] = {"sha256": digest, "text": txt.relative_to(cfg.root).as_posix()}
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
    return index
