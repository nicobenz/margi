from __future__ import annotations

import json

from click.testing import CliRunner

from conftest import make_pdf

from margi.cli import main
from margi.pdf import CACHE, clean, extract, flag

PROSE = ("The quick brown fox jumps over the lazy dog while the committee reviews "
         "another chapter of the thesis about reading practices in early modern Europe.")
SHIFTED = "7KHUH ZDV D FKDQJH WR WKH PLQLPXPV IRU FLUFOLQJ DSSURDFKHV"  # Caesar-shifted font


def test_clean_normalises_pdfium_output():
    assert clean("com\x02\r\npact rep\x02resentation\r\nof ﬁgures\r\n") == "compact representation\nof figures"


def test_flag():
    assert flag(PROSE * 3) is None
    assert flag("Figure 3") == "no-text"
    assert flag(SHIFTED * 5) == "not-prose"
    assert flag(PROSE + "\x08\x0c�" * 20) == "garbled"


def test_extract_flags_pages_and_caches(cfg, monkeypatch):
    lit = cfg.root / "lit"
    lit.mkdir(exist_ok=True)
    (lit / "paper.pdf").write_bytes(make_pdf([[PROSE] * 3, [], [SHIFTED] * 5]))
    entry = extract(cfg)["lit/paper.pdf"]
    assert entry["pages"] == 3 and entry["flags"] == {"2": "no-text", "3": "not-prose"}
    text = (cfg.root / entry["text"]).read_text()
    assert text.startswith("--- page 1 ---\nThe quick brown fox") and "--- page 3 ---" in text

    # unchanged PDFs are not extracted again; a new extractor version redoes them
    monkeypatch.setattr("margi.pdf._pages", lambda pdf: (_ for _ in ()).throw(AssertionError("re-extracted")))
    assert extract(cfg)["lit/paper.pdf"] == entry
    index = cfg.root / CACHE / "index.json"
    index.write_text(json.dumps({"lit/paper.pdf": dict(entry, extractor="pypdf")}))
    monkeypatch.setattr("margi.pdf._pages", lambda pdf: ["redone"])
    assert extract(cfg)["lit/paper.pdf"]["flags"] == {"1": "no-text"}


def test_extract_broken_pdf(cfg):
    (cfg.root / "lit").mkdir(exist_ok=True)
    (cfg.root / "lit" / "broken.pdf").write_bytes(b"%PDF-1.4 not really")
    entry = extract(cfg)["lit/broken.pdf"]
    assert entry["flags"] == {"all": "failed"}
    assert "extraction failed" in (cfg.root / entry["text"]).read_text()


def test_extract_command_prints_flags(cfg, monkeypatch):
    (cfg.root / "lit").mkdir(exist_ok=True)
    (cfg.root / "lit" / "a.pdf").write_bytes(make_pdf([[PROSE] * 3]))
    (cfg.root / "lit" / "b.pdf").write_bytes(make_pdf([[PROSE] * 3, []]))
    monkeypatch.chdir(cfg.root)
    out = CliRunner().invoke(main, ["extract-pdfs"])
    assert out.exit_code == 0, out.output
    rows = [line.split("\t") for line in out.output.splitlines()]
    assert [(r[0], r[2]) for r in rows] == [("lit/a.pdf", "-"), ("lit/b.pdf", "2:no-text")]
