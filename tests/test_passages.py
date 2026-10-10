from __future__ import annotations

import json

from conftest import make_pdf, run_git

from margi.dashboard import DASH_DATA, export
from margi.finalize import STAGING, finalize
from margi.passages import CROPS, locate, normalize, trace

P1 = ["Results", "We find that annotators disagree on the boundaries of footnotes",
      "and captions far more often than on paragraphs or section head-",
      "ings, which suggests that layout labels are partly interpretive."]
P2 = ["Discussion", "Interpretive labels call for adjudication rather than majority votes."]
OUTLINE = [("1 Results", 0, 784), ("2 Discussion", 1, 784)]


def paper(tmp_path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(make_pdf([P1, P2], OUTLINE))
    return pdf


def test_normalize():
    assert normalize("“Head-\nings”  are ﬁne") == normalize('"head-ings" are fine') == '"head-ings" are fine'


def test_locate_states(tmp_path):
    pdf = paper(tmp_path)
    ok, moved, lost, visual = locate(pdf, [
        {"page": 1, "quote": "boundaries of footnotes and captions far more often"},
        {"page": 1, "quote": "call for adjudication rather than majority votes"},
        {"page": 1, "quote": "a sentence that is not in the paper"},
        {"page": 2, "quote": "anything", "source": "visual"},
    ])
    assert ok["status"] == "ok" and ok["page"] == 1 and ok["section"] == ["1 Results"]
    crop = ok["crops"][0]
    assert len(crop["lines"]) == 2  # the quote wraps onto a second line
    assert all(crop["box"][0] <= l[0] and l[2] <= crop["box"][2] for l in crop["lines"])
    assert moved["status"] == "relocated" and moved["page"] == 2 and moved["section"] == ["2 Discussion"]
    assert lost == {"status": "unresolved", "page": 1}
    assert visual == {"status": "visual", "page": 2}


def test_locate_joins_hyphenation(tmp_path):
    [a] = locate(paper(tmp_path), [{"page": 1, "quote": "paragraphs or section headings, which suggests"}])
    assert a["status"] == "ok"


def test_trace_overrides_agent_anchors(tmp_path):
    paper(tmp_path)
    out = trace(tmp_path, {"ratings": [{"pdf": "paper.pdf", "key_passages": [
        {"page": 1, "quote": "layout labels are partly interpretive", "anchor": {"status": "ok", "page": 9}}]}]})
    item = out["ratings"][0]
    assert item["pdf_sha256"] and item["key_passages"][0]["anchor"]["page"] == 1


def test_read_record_traces_and_renders(repo, cfg):
    (repo / "lit" / "paper.pdf").write_bytes(make_pdf([P1, P2], OUTLINE))
    staging = repo / STAGING
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "read.json").write_text(json.dumps({
        "command": "read", "scope": "all", "summary": "Rated one PDF.", "files_read": ["lit/paper.pdf"],
        "payload": {"ratings": [{"pdf": "lit/paper.pdf", "relevance": 4, "key_passages": [
            {"page": 1, "quote": "boundaries of footnotes and captions", "why": "w", "source": "text"}]}]}}))
    result = finalize(cfg)
    passage = json.loads(result.records[0].read_text())["payload"]["ratings"][0]["key_passages"][0]
    assert passage["anchor"]["status"] == "ok"

    # the crop lands in the gitignored cache; the committed data only names it
    crops = list((repo / CROPS).glob("*.png"))
    assert len(crops) == 1 and crops[0].read_bytes().startswith(b"\x89PNG")
    data = (repo / DASH_DATA).read_text()
    assert f'.cache/lit/crops/{crops[0].name}' in data and '"href": "../lit/paper.pdf"' in data
    assert "lit/paper.pdf" not in run_git(repo, "ls-files").stdout.split()

    # export inlines the image, so the shared file shows the passage too
    assert "data:image/png;base64," in export(cfg).read_text()
