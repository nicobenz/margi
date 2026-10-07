from margi import docs_check


def test_templates_are_empty(repo):
    r = docs_check.check(repo / "margi/docs")
    assert r.filled == 0 and r.required > 20


def test_filling_fields_raises_completeness(repo):
    p = repo / "margi/docs/research-question.md"
    text = p.read_text().replace("## Research question\n_not yet documented_",
                                 "## Research question\nHow did X change Y? (user, 2026-10-07)", 1)
    p.write_text(text)
    r = docs_check.check(repo / "margi/docs")
    assert r.filled == 1
    assert "Research question" not in r.missing["research-question.md"]
