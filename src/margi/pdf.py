"""Extract literature PDFs to a plain-text cache the agent can read (margi/.cache/lit/).

The text layer is a cheap first pass. Pages it can't serve well are flagged so the agent reads
those pages from the PDF itself instead: no-text (scans, figure-only pages), garbled (unmapped or
control glyphs) and not-prose (too few vowels: tables, formulas or a font with a broken mapping).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .config import MARGI_DIR, Config
from .gitutil import sha256

CACHE = f"{MARGI_DIR}/.cache/lit"
EXTRACTOR = "pdfium-1"  # bump when extraction or cleanup changes, so cached text is redone

LIGATURES = str.maketrans({"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi",
                           "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"})
JUNK = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f�-]|\(cid:\d+\)")
LATIN = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]")
VOWELS = re.compile(r"[AEIOUYaeiouyÀ-ÆÈ-ÏÒ-ÖØ-Ýà-æè-ïò-öø-ýÿ]")
MIN_CHARS = 50       # fewer non-space characters: no usable text layer
MIN_LETTERS = 200    # too few Latin letters to judge the vowel share
MIN_VOWELS = 0.25    # natural Latin-script prose sits around 0.35-0.45
MAX_JUNK = 0.05      # share of control, private-use or unmapped glyphs


def clean(text: str) -> str:
    """Normalise pdfium's raw page text: LF line ends, rejoined hyphenation, plain ligatures."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\x02\n?", "", text)  # pdfium marks a line-end hyphenation with \x02
    return text.translate(LIGATURES).strip()


def flag(text: str) -> str | None:
    """Why a page's extracted text shouldn't be trusted, or None if it looks fine."""
    chars = len(re.sub(r"\s", "", text))
    if chars < MIN_CHARS:
        return "no-text"
    if len(JUNK.findall(text)) / chars > MAX_JUNK:
        return "garbled"
    letters = len(LATIN.findall(text))
    if letters >= MIN_LETTERS and len(VOWELS.findall(text)) / letters < MIN_VOWELS:
        return "not-prose"
    return None


def find_pdfs(cfg: Config, only: list[str] | None = None) -> list[Path]:
    if only:
        return [(cfg.root / p).resolve() for p in only]
    lit = cfg.root / cfg["literature"]["dir"]
    return sorted(lit.rglob("*.pdf")) if lit.is_dir() else []


def _pages(pdf: Path) -> list[str]:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(pdf)
    try:
        return [clean(doc[i].get_textpage().get_text_bounded()) for i in range(len(doc))]
    finally:
        doc.close()


def extract(cfg: Config, only: list[str] | None = None) -> dict[str, dict]:
    """Extract each PDF once per content hash and extractor version. Returns {pdf path: entry}.

    Each entry has the text file, the page count and `flags`: {page number: reason from `flag`},
    or {"all": "failed"} when the file couldn't be opened.
    """
    cache = cfg.root / CACHE
    cache.mkdir(parents=True, exist_ok=True)
    index_path = cache / "index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {}
    done = []
    for pdf in find_pdfs(cfg, only):
        if not pdf.is_file():
            raise FileNotFoundError(f"PDF not found: {pdf}")
        digest = sha256(pdf.read_bytes())
        rel = pdf.relative_to(cfg.root.resolve()).as_posix()
        done.append(rel)
        old = index.get(rel, {})
        txt = cache / f"{digest[:16]}.{EXTRACTOR}.txt"
        if txt.exists() and old.get("sha256") == digest and old.get("extractor") == EXTRACTOR:
            continue
        try:
            pages = _pages(pdf)
            txt.write_text("\n\n".join(f"--- page {i} ---\n{p}" for i, p in enumerate(pages, 1)), encoding="utf-8")
            flags = {str(i): f for i, p in enumerate(pages, 1) if (f := flag(p))}
        except Exception as e:  # pdfium raises on encrypted or broken files
            pages, flags = [], {"all": "failed"}
            txt.write_text(f"--- extraction failed: {e} ---", encoding="utf-8")
        index[rel] = {"sha256": digest, "extractor": EXTRACTOR, "text": txt.relative_to(cfg.root).as_posix(),
                      "pages": len(pages), "flags": flags}
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
    return {rel: index[rel] for rel in done}
