import json
import stat

import pytest
import yaml
from conftest import run_git

from margi.config import load
from margi.wrapper import WrapperError, harness_command, run

FAKE_AGENT = """#!/bin/sh
# pretend to be an agent: write a draft, then finalize like the skill says
mkdir -p margi/.staging
cat > margi/.staging/grade.json <<'JSON'
{"command": "grade", "scope": "2.1", "summary": "fake",
 "scores": {"argument": {"score": 4, "max": 5, "rationale": "ok"}}}
JSON
margi finalize
"""

EVIL_AGENT = """#!/bin/sh
echo "AI text" >> main.typ
mkdir -p margi/.staging
echo '{"command": "grade", "scope": "2.1"}' > margi/.staging/grade.json
"""


def configure(repo, tmp_path, script, model="test-model"):
    agent = tmp_path / "agent.sh"
    agent.write_text(script)
    agent.chmod(agent.stat().st_mode | stat.S_IXUSR)
    path = repo / "thesis.config.yml"
    data = yaml.safe_load(path.read_text())
    data["harness"] = {"kind": "claude", "model": model, "bin": str(agent)}
    path.write_text(yaml.safe_dump(data))
    run_git(repo, "commit", "-qam", "configure harness")
    return load(repo)


def test_docs_gate_blocks_grade(repo, tmp_path):
    cfg = configure(repo, tmp_path, FAKE_AGENT)
    with pytest.raises(WrapperError, match="project docs"):
        run(cfg, "grade", ["2.1"])


def test_wrapper_end_to_end_with_force(repo, tmp_path):
    cfg = configure(repo, tmp_path, FAKE_AGENT)
    run(cfg, "grade", ["2.1"], force=True)
    recs = list((repo / "margi/feedback").glob("*_grade_2.1.json"))
    assert len(recs) == 1
    prov = json.loads(recs[0].read_text())["provenance"]
    assert prov["model"] == "test-model" and prov["model_source"] == "wrapper"
    assert prov["docs"]["low_confidence"] is True
    assert run_git(repo, "log", "-1", "--format=%an").stdout.strip() == "margi-bot"


def test_agent_editing_thesis_is_caught(repo, tmp_path):
    cfg = configure(repo, tmp_path, EVIL_AGENT)
    with pytest.raises(Exception, match="outside margi/"):
        run(cfg, "grade", ["2.1"], force=True)
    assert list((repo / "margi/feedback").glob("*.json")) == []


def test_harness_command_restricts_tools(repo, cfg):
    cmd = harness_command(cfg, "grade", ["2.1"])
    assert cmd[:3] == ["claude", "-p", "/margi grade 2.1 --headless"]
    tools = cmd[cmd.index("--allowedTools") + 1]
    assert "Edit(margi/**)" in tools and "Bash(git commit" not in tools
    assert "-p" not in harness_command(cfg, "onboard", [])
    assert harness_command(cfg, "challenge", ["research question"])[1] == "/margi-challenge research question"
