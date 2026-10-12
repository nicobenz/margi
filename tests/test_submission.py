import json

from click.testing import CliRunner
from conftest import human_commit, make_pdf, run_git

from margi import ai_report, submission
from margi.cli import main
from margi.config import load

CHAPTER = """= Results
As Moretti puts it, "distant reading is a condition of knowledge rather than an obstacle" @moretti2013[p. 2].
Da objects that "the quantitative turn has simply never delivered its promise at all" @da2019.
Some claim "this sentence appears nowhere in any of the sources at all" @moretti2013.
A colleague wrote "a quote from a source that has no file anywhere here" @nobody2020.
"An unattributed quotation with enough words to be checked" stands alone.
#quote(attribution: [@da2019])[the quantitative turn has never delivered its promise at all]
"""

BIB = """@book{moretti2013,
  author = {Moretti, Franco}, title = {Distant Reading}, year = {2013}, publisher = {Verso}
}
@article{da2019,
  author = {Da, Nan Z.}, title = {The Computational Case against Computational Literary Studies}
}
@book{unused2000,
  author = {Nobody}, title = {Never Cited}, year = {2000}
}
"""


def setup_thesis(repo):
    (repo / "chapters/results.typ").write_text(CHAPTER)
    main_typ = repo / "main.typ"
    main_typ.write_text(main_typ.read_text() + '\n#include "chapters/results.typ"\n')
    (repo / "refs.bib").write_text(BIB)
    cfg_file = repo / "thesis.config.yml"
    cfg_file.write_text(cfg_file.read_text().replace("bib: null", "bib: refs.bib"))
    lit = repo / "lit"
    lit.mkdir(exist_ok=True)
    (lit / "moretti2013.pdf").write_bytes(make_pdf([["Preface"], ["Distant reading is a condition of knowledge",
                                                                  "rather than an obstacle, he wrote."]]))
    (lit / "da2019.pdf").write_bytes(make_pdf([["The quantitative turn has never delivered its promise at all."]]))
    (lit / "orphan.pdf").write_bytes(make_pdf([["Unrelated."]]))
    human_commit(repo, "results chapter", "chapters", "main.typ", "refs.bib", "thesis.config.yml")
    return load(repo)


def test_quotes_are_checked_against_their_pdfs(repo):
    cfg = setup_thesis(repo)
    p = submission.run(cfg)
    by = {q["quote"][:15]: q for q in p["quotes"] if q["line"] < 7}  # line 7 is the #quote block
    assert by["distant reading"]["status"] == "match" and by["distant reading"]["pdf_page"] == 2
    differs = by["the quantitativ"]
    assert differs["status"] == "differs" and differs["diffs"] == [{"thesis": "simply", "pdf": ""}]
    assert by["this sentence a"]["status"] == "not_found"
    assert by["a quote from a "]["status"] == "no_pdf"
    assert by["An unattributed"]["status"] == "no_citation"
    block = [q for q in p["quotes"] if q["quote"].startswith("the quantitative turn has never")]
    assert block and block[0]["status"] == "match" and block[0]["cite"]["key"] == "da2019"


def test_bibliography_against_citations_and_pdfs(repo):
    cfg = setup_thesis(repo)
    kinds = {(b["kind"], b.get("key")) for b in submission.run(cfg)["bib"]}
    assert ("missing", "nobody2020") in kinds and ("uncited", "unused2000") in kinds
    assert ("incomplete", "da2019") in kinds and ("pdf_without_entry", None) in kinds
    assert ("missing", "moretti2013") not in kinds


def test_cli_records_the_check_and_the_dashboard_shows_it(repo, monkeypatch):
    setup_thesis(repo)
    monkeypatch.chdir(repo)
    out = CliRunner().invoke(main, ["submit-check"])
    assert out.exit_code == 0, out.output
    assert "Quotations   6 checked: 2 match, 1 differ, 1 not found, 1 without a PDF, 1 without a citation nearby" in out.output
    assert run_git(repo, "log", "-1", "--format=%an|%s").stdout.startswith("margi-bot|margi: submit-check")
    text = (repo / "margi/dash/data.js").read_text()
    d = json.loads(text[text.index("{"):text.rindex("}") + 1])
    assert d["submission"]["check"]["counts"]["attention"] == 3  # differs, not found, missing from the bib
    assert d["submission"]["stale"] is False


def test_ai_report_is_factual_and_checks_the_history(repo, monkeypatch):
    setup_thesis(repo)
    monkeypatch.chdir(repo)
    CliRunner().invoke(main, ["submit-check"])
    out = CliRunner().invoke(main, ["ai-report"])
    assert out.exit_code == 0, out.output
    md = (repo / ai_report.MD).read_text()
    assert "margi wrote nothing outside `margi/`" in md and "| submit-check |" in md
    assert "declaration" in md and (repo / ai_report.HTML).read_text().startswith("<!doctype html>")
    tracked = run_git(repo, "ls-files", "margi").stdout
    assert "margi/ai-use.md" in tracked and "ai-use.html" not in tracked


def test_ai_report_admits_a_broken_separation(repo):
    cfg = load(repo)
    (repo / "main.typ").write_text((repo / "main.typ").read_text() + "\nAI wrote this.\n")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-qm", "margi: sneaky", "--no-verify")
    rep = ai_report.build(cfg)
    assert rep["violations"]
    assert "The guard found 1 commit" in ai_report.markdown(cfg, rep)
