---
version: 1
slug: "templates-dash-dash-html"
primary_target: "templates/dash/dash.html"
related_targets: []
---

# Surface: margi/dash.html (template: templates/dash/dash.html)

Mode: Operate. A thesis student opens it between writing sessions or right after a margi run to see
where each section stands, why, and which /margi command to run next.

Scope: production dash.html (fixed page, data via margi/dash/data.js), empty state, `margi export`
→ self-contained export.html. Overview of sections with drill-in; secondary views for docs,
literature, todos and the run log. Next steps in a quiet sticky header.

## Direction contract

THESIS: The dashboard is the critical apparatus of the student's own edition: feedback is set out as
annotation around the text, never as replacement. It refuses the category default of KPI cards,
hero numbers and coloured badges.

OWN-WORLD: Warm grey ground with a lighter page plane; near-black ink; one rubricator red that marks
only what needs attention (major comments, scores of 2 or below, sections whose text changed since
their grade, the active selection mark). Amended after finish review: a stale grade is a cause for
regrading, i.e. attention, so "changed" stays red; everything else (targets, deltas, wordmark) is ink.
Libertinus Serif (Typst's own face) for content with tabular figures, letter-spaced capitals for
category labels, Libertinus Sans for controls, Libertinus Mono only for paths and commands. Hairline
rules, no shadows on content, no rounded cards.

STORY: The student sees every section in thesis order with its rubric scores, sees what is rubricated
red, opens a section, reads the apparatus entries anchored to file, lines and quote, and copies the
next command from the header.

FIRST VIEWPORT: Sticky running head (44px plus a 4px double rule): wordmark, thesis title, next-step strip with the first
command and copy control plus a disclosure for the rest, each tagged check or session; refresh
date. Below: one status line (docs %, sections graded, open majors, length). Then tabs; Sections tab
fills the viewport: section table left (~60%), apparatus panel right (~40%) for the selected section.

FORM: Critical apparatus, position 1 on the ordered list (chosen as the pick over assigned
candidate 6, Survey map); seed key eea10d6a; roll degraded (no challengers). Signature move: comments
rendered as apparatus entries `file lines ] "lemma" ] severity · category` followed by the note.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Open decisions
- Rule set for deterministic next steps may grow; agent steps come via draft field `next_steps`.
