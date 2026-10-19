# /margi help

Also what a bare `/margi` does. Tell the student where their project stands and what to run
next. Read-only: no preflight, no draft, no `margi finalize`, nothing written or committed.

1. Run `uv run margi next`. It prints the getting-started checklist (while setup is open), the
   ranked next steps (rule-based checks plus the steps from the latest session), and an
   inventory of the project: plan, project docs, submission date, sections, comments, length,
   literature, todos and the submit check.
2. If the student asked something with the command (`/margi help grading`, "what should I do
   about the literature?"), answer that from the output and the Commands table in `SKILL.md`,
   reading `margi/docs/` or a command file if you need to. Otherwise go on.
3. Report:
   - **Where things stand**: one or two sentences naming what is done and what is missing,
     from the inventory. While setup is open, say which step of how many they are on.
   - **Next**: the one to three commands that matter most, each with its reason in one line,
     in the order `margi next` gave them. Weigh in what the student said earlier in this
     conversation (a chapter they want to focus on, a deadline they mentioned), but don't
     reorder past a docs shortfall: `/margi propose` comes first while docs are below the
     threshold, since grades are low-confidence until then. A step "on hold" is named with
     its reason, never recommended. If nothing is pending, say so.
   - **Commands**: a compact list of every command from the Commands table in `SKILL.md`,
     one line each (`/margi help` itself excluded), so the student has the cheat sheet.
   - Run `uv run margi open` and close with its dashboard line as a link, naming its Guide tab.

Don't invent steps that aren't backed by the output or the conversation, and don't propose
thesis text. Keep everything but the command list to about eight lines.
