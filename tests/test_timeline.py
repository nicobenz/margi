import json

from margi.finalize import finalize
from margi.lifecycle import respond
from margi.timeline import due, load_plan

FILE = "chapters/prior-work.typ"


def constraints(repo, block: str) -> None:
    path = repo / "margi/docs/constraints.md"
    path.write_text(path.read_text().replace("## Length and format", f"```yaml\n# margi-timeline\n{block}```\n\n## Length and format"))


def dash(repo):
    text = (repo / "margi/dash/data.js").read_text()
    return json.loads(text[text.index("{"):text.rindex("}") + 1])


def grade(repo, cfg, scope="2.1", comments=(), verdicts=None, readiness=None):
    d = {"command": "grade", "scope": scope, "summary": "ok", "files_read": [FILE],
         "scores": {"argument": {"score": 3, "max": 5, "rationale": "fine"}}, "comments": list(comments)}
    if verdicts:
        d["verdicts"] = verdicts
    if readiness:
        d = {"command": "grade", "scope": scope, "summary": "Not ready.", "readiness": readiness}
    staging = repo / "margi/.staging"
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "grade.json").write_text(json.dumps(d))
    finalize(cfg)


MAJOR = {"id": "c1", "category": "argument", "severity": "major", "body": "Claim needs evidence.",
         "anchor": {"file": FILE, "line_start": 5, "line_end": 5, "quote": "Moretti proposed counting instead of reading."}}


def test_plan_parses_and_reports_problems(repo, cfg):
    assert load_plan(cfg) == (None, [])
    constraints(repo, "start: 2026-09-01\ndeadline: 2027-03-31\nlength: 180000\nmilestones:\n"
                      "  - {date: 2027-02-01, label: Advisor meeting}\n"
                      "  - {date: 2026-12-01, sections: [2], state: drafted, label: Prior work drafted}\n"
                      "  - {date: 2026-13-01, sections: ['3'], state: graded}\n"
                      "  - {date: 2027-01-01, sections: ['3'], state: finished}\n")
    plan, problems = load_plan(cfg)
    assert plan["deadline"] == "2027-03-31" and plan["start"] == "2026-09-01" and plan["length"] == 180000
    assert [(m["date"], m["sections"], m["state"]) for m in plan["milestones"]] == [
        ("2026-12-01", ["2"], "drafted"), ("2027-02-01", [], None)]  # sorted, bad ones dropped
    assert any("2026-13-01" in p for p in problems) and any("state must be one of" in p for p in problems)


def test_broken_block_is_a_warning_not_a_crash(repo, cfg):
    constraints(repo, "deadline: [unclosed\n")
    plan, problems = load_plan(cfg)
    assert plan is None and "not valid YAML" in problems[0]
    finalize(cfg, command="noop")
    assert "not valid YAML" in dash(repo)["timeline"]["problem"]


def test_milestones_are_judged_from_records(repo, cfg):
    constraints(repo, "deadline: 2099-03-31\nmilestones:\n"
                      "  - {date: 2099-01-01, sections: ['2.1'], state: graded}\n"
                      "  - {date: 2099-01-02, sections: ['2.1'], state: settled}\n"
                      "  - {date: 2099-01-03, sections: ['2.1', '2.2'], state: graded}\n"
                      "  - {date: 2099-01-04, label: Advisor meeting}\n")
    grade(repo, cfg, comments=[MAJOR])
    t = dash(repo)["timeline"]
    today = t["reference"]
    graded, settled, both, plain = t["milestones"]
    assert graded["met"] == today and settled["met"] is None and both["met"] is None and plain["met"] is None
    assert t["start_source"] == "commit" and t["start"] == t["commits"][0][0]
    respond(cfg, [("c1", "addressed")])
    grade(repo, cfg, verdicts=[{"ref": "c1", "verdict": "resolved", "reason": "Fixed."}])
    t = dash(repo)["timeline"]
    assert t["milestones"][1]["met"] == today  # settled once the major comment is resolved
    kinds = [(e["kind"], e["section"]) for e in t["events"]]
    assert kinds == [("grade", "2.1"), ("respond", "2.1"), ("grade", "2.1")]


def test_chapter_grade_counts_for_its_subsections_and_not_ready_does_not(repo, cfg):
    constraints(repo, "deadline: 2099-03-31\nmilestones:\n  - {date: 2099-01-01, sections: ['2.2'], state: graded}\n")
    grade(repo, cfg, scope="2.2", readiness={"decision": "not_ready", "reasons": ["notes"]})
    assert dash(repo)["timeline"]["milestones"][0]["met"] is None
    grade(repo, cfg, scope="2")
    assert dash(repo)["timeline"]["milestones"][0]["met"] is not None


def test_due_milestone_and_missing_deadline_become_next_steps(repo, cfg):
    constraints(repo, "deadline: 2099-03-31\nmilestones:\n  - {date: 2000-01-01, sections: ['2.2'], state: graded, label: Networks graded}\n")
    finalize(cfg, command="noop")
    steps = dash(repo)["next_steps"]
    step = next(s for s in steps if s["command"] == "/margi grade 2.2")
    assert 'Milestone "Networks graded" is due 1 Jan 2000' in step["reason"]
    assert not any(s["command"] == "/margi challenge deadline" for s in steps)


def test_due_window():
    m = {"date": "2026-10-20", "met": None, "sections": ["2"]}
    assert due(m, "2026-10-11") and not due(m, "2026-10-01")
    assert not due(dict(m, met="2026-10-12"), "2026-10-11") and not due(dict(m, sections=[]), "2026-10-11")
