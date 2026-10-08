"""Shell entry point for AI commands: preflight → launch the agent harness → finalize.

The agent is restricted to reading anything and writing only inside margi/.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass

from . import docs_check, pdf
from .config import MARGI_DIR, Config
from .finalize import FinalizeResult, ensure_clean, finalize, load_drafts
from .gitutil import worktree_changes


class WrapperError(RuntimeError):
    pass


@dataclass(frozen=True)
class Spec:
    skill: str
    interactive: bool
    needs_docs: bool


COMMANDS = {
    "onboard": Spec("margi-onboard", interactive=True, needs_docs=False),
    "challenge": Spec("margi-challenge", interactive=True, needs_docs=False),
    "grade": Spec("margi", interactive=False, needs_docs=True),
    "read": Spec("margi", interactive=False, needs_docs=True),
    "todos": Spec("margi", interactive=True, needs_docs=False),
}

ALLOWED_TOOLS = [
    "Read",
    "Glob",
    "Grep",
    f"Edit({MARGI_DIR}/**)",
    "Bash(uv run margi finalize:*)",
    "Bash(uv run margi outline:*)",
    "Bash(uv run margi status:*)",
    "Bash(uv run margi extract-pdfs:*)",
    "Bash(uv run margi todos --sync-accepted:*)",
    "Bash(git status:*)",
    "Bash(git log:*)",
    "Bash(git diff:*)",
    "Bash(gh issue list:*)",
    "Bash(gh issue view:*)",
]


def prompt_for(command: str, args: list[str]) -> str:
    spec = COMMANDS[command]
    rest = " ".join(args + ([] if spec.interactive else ["--headless"]))
    if spec.skill == "margi":
        return f"/margi {command} {rest}".strip()
    return f"/{spec.skill} {rest}".strip()


def harness_command(cfg: Config, command: str, args: list[str]) -> list[str]:
    harness = cfg["harness"]
    kind = harness.get("kind", "claude")
    spec = COMMANDS[command]
    prompt = prompt_for(command, args)
    if kind == "claude":
        exe = harness.get("bin") or "claude"
        # the prompt goes first: --allowedTools is variadic and would swallow it
        cmd = [exe, "-p", prompt] if not spec.interactive else [exe, prompt]
        if harness.get("model"):
            cmd += ["--model", harness["model"]]
        cmd += ["--allowedTools", ",".join(ALLOWED_TOOLS)]
        return cmd
    raise WrapperError(f"harness kind {kind!r} is not supported yet (supported: claude)")


def run(cfg: Config, command: str, args: list[str], *, force: bool = False) -> FinalizeResult:
    spec = COMMANDS[command]
    ensure_clean(cfg)

    if spec.needs_docs:
        report = docs_check.check(cfg.root / MARGI_DIR / "docs")
        threshold = float(cfg["docs"]["min_completeness"])
        if report.completeness < threshold and not force:
            missing = "; ".join(f"{k}: {', '.join(v)}" for k, v in report.missing.items())
            raise WrapperError(
                f"project docs are {report.completeness:.0%} complete (need {threshold:.0%}). "
                f"Scores are only meaningful against documented goals.\n"
                f"  Missing: {missing}\n"
                f"  Run `uv run margi onboard` (or pass --force to get a low-confidence result)."
            )

    if command == "read":
        pdf.extract(cfg, args or None)

    cmd = harness_command(cfg, command, args)
    exe = cmd[0]
    if not shutil.which(exe):
        raise WrapperError(f"agent harness `{exe}` not found on PATH")

    env = dict(os.environ, MARGI_WRAPPED="1")
    model = cfg["harness"].get("model")
    harness = cfg["harness"].get("kind")
    if model:
        env["MARGI_MODEL"] = model
    env["MARGI_HARNESS"] = harness or ""
    stdin = None if spec.interactive else subprocess.DEVNULL
    proc = subprocess.run(cmd, cwd=cfg.root, env=env, stdin=stdin)
    if proc.returncode != 0:
        raise WrapperError(f"agent exited with status {proc.returncode}; nothing was committed")

    # The skill normally finalizes itself; finalize anything left over.
    pending = load_drafts(cfg) or (cfg.has_git and any(c.path.startswith(MARGI_DIR + "/") for c in worktree_changes(cfg.root)))
    if not pending:
        return FinalizeResult(has_git=cfg.has_git)
    return finalize(
        cfg,
        model=model,
        harness=harness,
        model_source="wrapper" if model else None,
        command=f"{command} {' '.join(args)}".strip(),
    )
