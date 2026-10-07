from margi import outline
from margi.adapters import get_adapter


def test_counts_and_tree(cfg):
    tree, rows = outline.compute(cfg)
    ids = {s.id: s for s in tree.walk()}
    assert ids["1"].own_chars == 46
    assert ids["2.1"].own_chars == 112  # math, comments, raw block excluded; footnote kept
    assert ids["2.2"].own_chars == 26  # figure call excluded
    assert ids["3"].total_chars == 0
    assert ids["2"].total_chars == ids["2"].own_chars + 112 + 26
    assert tree.total_chars == sum(r.chars for r in rows)


def test_resolve_section(cfg):
    ad = get_adapter(cfg)
    assert ad.resolve("2.1").title == "Distant Reading"
    assert ad.resolve("network analysis").id == "2.2"
    assert ad.resolve("Network").id == "2.2"
    assert ad.resolve("nope") is None


def test_planned_targets(cfg, repo):
    (repo / "margi/docs/structure.md").write_text(
        "# Structure\n\n## Planned outline\n```yaml\n# margi-structure\n"
        "- title: Introduction\n  target: 10%\n- title: Prior Work\n  target: 50%\n"
        "- title: Conclusion\n  target: 10%\n```\n"
    )
    tree, rows = outline.compute(cfg)
    by_title = {r.title: r for r in rows}
    assert by_title["Introduction"].target == "target 10%"
    assert by_title["Conclusion"].planned_only and by_title["Conclusion"].chars == 0
    text = outline.render(tree, rows, "chars")
    assert "Conclusion" in text and "planned" in text


def test_template_example_is_not_a_plan(cfg):
    assert outline.load_plan(cfg) == []
