---
name: margi
description: Feedback for a human-written thesis, set out as a critical apparatus beside the student's own text.
colors:
  red: "#a3301b"
  red-ink: "#8e2716"
  red-tint: "#f2dcd4"
  wash: "#f0cfc3"
  ground: "#e6e3dd"
  page: "#f7f6f2"
  sel: "#ebe7df"
  ink: "#1c1a18"
  ink-2: "#47423d"
  ink-3: "#6a645d"
  rule: "#d2cdc4"
  rule-soft: "#e3dfd8"
  chart: "#1c1a18"
  chart-grid: "#ddd8cf"
typography:
  headline:
    fontFamily: "Libertinus Serif, Iowan Old Style, Palatino Linotype, Palatino, Georgia, serif"
    fontSize: "26px"
    fontWeight: 600
    lineHeight: 1.15
  body:
    fontFamily: "Libertinus Serif, Iowan Old Style, Palatino Linotype, Palatino, Georgia, serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "tnum, lnum, kern"
  body-small:
    fontFamily: "Libertinus Serif, Iowan Old Style, Palatino Linotype, Palatino, Georgia, serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.4
  label:
    fontFamily: "Libertinus Sans, Gill Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    letterSpacing: "0.09em"
  control:
    fontFamily: "Libertinus Sans, Gill Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
  wordmark:
    fontFamily: "Libertinus Sans, Gill Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 700
    letterSpacing: "0.02em"
  mono:
    fontFamily: "Libertinus Mono, ui-monospace, SF Mono, Menlo, Consolas, monospace"
    fontSize: "13px"
    fontWeight: 400
rounded:
  none: "0"
  hairline: "2px"
spacing:
  s1: "4px"
  s2: "8px"
  s3: "12px"
  s4: "16px"
  s5: "24px"
  s6: "32px"
  s7: "48px"
  head-h: "44px"
components:
  sheet:
    backgroundColor: "{colors.page}"
    rounded: "{rounded.none}"
  command-chip:
    backgroundColor: "{colors.page}"
    textColor: "{colors.ink}"
    typography: "{typography.mono}"
    rounded: "{rounded.hairline}"
    padding: "2px 4px 2px 8px"
  copy-button:
    textColor: "{colors.ink-3}"
    rounded: "{rounded.hairline}"
    width: "28px"
    height: "26px"
  copy-button-hover:
    backgroundColor: "{colors.sel}"
    textColor: "{colors.ink}"
  copy-button-done:
    textColor: "{colors.red}"
  tab:
    textColor: "{colors.ink-3}"
    typography: "{typography.control}"
    padding: "8px 0"
  tab-selected:
    textColor: "{colors.ink}"
  segment:
    backgroundColor: "{colors.page}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.hairline}"
    padding: "3px 9px"
  segment-pressed:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.page}"
  select:
    backgroundColor: "{colors.page}"
    rounded: "{rounded.hairline}"
    padding: "3px 6px"
  grid-row-selected:
    backgroundColor: "{colors.sel}"
  score-low:
    textColor: "{colors.red}"
  tooltip:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.page}"
    rounded: "{rounded.hairline}"
    padding: "3px 6px"
---

# Design System: margi

## Overview

**Creative North Star: "The Critical Apparatus"**

margi's dashboard is set like the apparatus of a scholarly edition: the student's own section list is the text, and every grade, comment and next step is an annotation ranged around it in the margin. It reads as a printed sheet laid on a warm grey desk: a lighter page plane, near-black ink, hairline rules, and a single rubricator red that a scribe would use to mark what needs attention. Nothing is decorated; hierarchy comes from weight, size, letter-spaced capitals and rules.

Density is high and deliberate. The Sections view puts every section, in thesis order, with all rubric scores on one table; the apparatus panel beside it opens one section's scores, history and anchored comments. Comments are set as apparatus entries: line locator, the quoted lemma closed by a bracket, then severity, category and the note. Numbers are tabular everywhere so columns align like a printed table.

The system refuses the dashboard category default: no KPI cards, no hero numbers, no filled colour badges, no green-good/red-bad pairing. The status line states figures in running prose; flags are letter-spaced words, not pills.

**Key Characteristics:**
- Warm grey ground, lighter page sheets, near-black ink; light and dark modes with the same roles.
- One accent, rubricator red, reserved for attention and the active mark.
- Libertinus throughout: Serif for content, Sans for controls and labels, Mono only for commands, paths and line locators.
- Structure by 1px hairline rules and a double rule under the running head; flat, square sheets.
- Tabular lining figures on every number.

## Colors

A warm, paper-and-ink neutral range with a single red; dark mode inverts the same roles onto warm charcoal (values in `.impeccable/design.json`).

### Primary
- **Rubricator Red** (red): marks only what needs attention: major-severity labels, scores at or below the low cut (2 on the 1-5 scale), the "changed since grading" flag, a nonzero major-comment count, the selected section's number, and the "needs N%" docs shortfall. It also carries the interaction marks: focus ring, text caret, link-hover underline, the copy-confirmed tick, and the border of the missing-data banner.
- **Deep Rubric** (red-ink): red for running warning text (low confidence, text changed since grade, anchor "moved" / "passage not found"), slightly darker than Rubricator Red so sentences stay comfortable to read.
- **Rubric Wash** (red-tint): the text-selection highlight only.
- **Passage Wash** (wash): the quoted lines on a page image in the Literature view, multiplied over the paper-white crop. It marks a quoted selection, not attention, and stays the same in dark mode because the crop stays paper-white.

### Neutral
- **Desk Grey** (ground): the page background, the running head, the scrollbar track.
- **Sheet** (page): every content plane (section table, apparatus panel, secondary-view sheets), control fills (command chip, select, segment), and the inverted text of the tooltip and pressed segment.
- **Pencil Shade** (sel): selected table row, hovered/open controls; at 60% mixed with transparent for row hover.
- **Ink** (ink): primary text, the strong rules (head double rule, table header bottom, block heading rule, legend top rule, popover border), the pressed segment and tooltip fill, the selected-tab underline.
- **Second Ink** (ink-2): secondary text: status line, rationales, lower outline levels, length-bar fill, minor severity, "down" deltas.
- **Faded Ink** (ink-3): labels and metadata: capitals, meta lines, section numbers, unselected tabs, the note severity, axis labels.
- **Hairline** (rule): sheet borders, control borders, link underlines at rest.
- **Soft Hairline** (rule-soft): row dividers within tables and lists, the length-bar track.
- **Chart Ink** (chart) and **Chart Grid** (chart-grid): score-history lines and dots; min/max grid lines and the dashed midline.

### Named Rules
**The Rubricator Rule.** Red means "look here". It is never used for a brand mark, a positive state, a target, or a delta; the wordmark, length targets and score changes stay in ink.

**The No Verdict Hue Rule.** There is no "good" colour. Rising and falling deltas are ink and second ink; a high literature relevance is ink, a low one faded ink. Only attention earns a hue.

## Typography

**Display Font:** none; the largest type is the apparatus headline.
**Body Font:** Libertinus Serif (with Iowan Old Style, Palatino, Georgia)
**Label/Mono Font:** Libertinus Sans for controls and capitals; Libertinus Mono for commands, paths and line locators.

**Character:** Typst's own Libertinus family, so the dashboard shares the face of the thesis it annotates. The serif carries reading; the sans is the quieter voice of the instrument; mono appears only where text is literally typed or a file is named.

Fonts ship as woff2 and are inlined as data URIs at render time: Serif 400, 400 italic, 600; Sans 400, 700; Mono 400. Use no other weights.

### Hierarchy
- **Headline** (Serif 600, 26px, 1.15, balanced wrap): the apparatus panel title ("2.1 Genre theory of the Novelle", "Needs attention"), with the section number in regular weight, faded ink.
- **Body** (Serif 400, 17px, 1.45; 16px under 720px): section titles in the table, summaries (max 68ch). Top-level sections set in 600.
- **Body small** (Serif 400, 15-16px): comment notes (16px, max 66ch), rationales, "why" lines, category names; the lemma is italic in curly quotes.
- **Label** (Sans 400, 12px, 0.08-0.09em, uppercase, faded ink): table column heads, block headings in the apparatus (set in ink there), severity words, the "Next" field label, small-multiple captions. Flags such as CHANGED use 11px.
- **Control** (Sans 400, 13-15px): tabs 15px, header strip 14px, meta lines, filters and legend 13px.
- **Wordmark** (Sans 700, 15px, 0.02em): "margi", in ink.
- **Mono** (Mono 400, 0.86em; 13px in the command chip, 12px for line locators).

### Named Rules
**The Three Voices Rule.** Serif is what the student reads, Sans is what the student operates, Mono is what the student types or opens. Never set content in Sans or controls in Serif.

**The Tabular Rule.** Every figure is tabular and lining (`font-variant-numeric: tabular-nums lining-nums` on body); thousands are grouped with a space ("11 777").

## Layout

A full-width frame (max 1520px, 24px side padding, 48px bottom) under a sticky running head 44px tall. The head carries wordmark, thesis title (ellipsised), a flexible spacer, the next-step strip and the refresh date. Below it: one status line in running prose, then a tab row underlined by a hairline.

The Sections view is a two-column split: the section table takes the remaining width, the apparatus panel at least 340px and 0.62fr; 24px gap. The panel is sticky under the head and scrolls internally. Secondary views use auto-fit columns of at least 320px.

Spacing runs on a 4px base scale: 4, 8, 12, 16, 24, 32, 48. Table cells use 7-8px vertical and 8px horizontal padding with 16px at the row ends; apparatus blocks are 32px apart.

Responsive: under 1360px the Graded date column drops; under 1080px the split collapses to one column, the panel becomes static and the next-step reason hides; under 720px the head wraps (head height becomes auto), body drops to 16px, the per-category score columns collapse to one "Scores" summary column ("2 low" / "ok"), the legend hides, and tabs wrap. Print hides tabs, filters, copy controls and the steps disclosure.

## Elevation & Depth

Flat. Depth is a change of plane, not a shadow: Desk Grey ground, Sheet planes on top, each bordered by a 1px hairline. The running head separates itself with a double ink rule (1px border plus a second 1px rule 4px below). The one shadow in the system belongs to the floating "next steps" popover, which overlaps content.

### Shadow Vocabulary
- **Popover lift** (`box-shadow: 0 10px 28px -12px rgb(0 0 0 / 0.35)`): the next-steps disclosure panel only, together with a 1px ink border.

### Named Rules
**The Flat Sheet Rule.** Content sheets never carry a shadow; only an element that floats over content may lift, and it still keeps its ink border.

## Shapes

Rectangular. Sheets, tables, the banner and the popover have square corners. Small controls (command chip, copy button, select, segmented control, tooltip, steps summary) take a barely-there 2px radius. Borders are always 1px; the only 2px line is the selected-tab underline and the focus ring. Length bars are 3px hairline tracks with a 1px ink tick for the target.

## Components

### Command chip
The signature action: a typed command you can copy.
- **Shape:** 1px hairline border, Sheet fill, 2px radius, inline.
- **Content:** the command in Mono 13px, followed by a 28 x 26px copy button with a 14px stroked copy icon in faded ink.
- **Hover / Done:** the copy button fills Pencil Shade with ink icon on hover; after copying it swaps to a check in Rubricator Red for 1.4s.

### Buttons (segmented filter)
- **Shape:** joined 1px-bordered segments in a 2px-radius frame; Sans 13px, 3px 9px padding.
- **Rest:** Sheet fill, second ink. **Pressed:** ink fill, Sheet text.

### Tabs
- **Style:** Sans 15px, faded ink, no fill; count in faded ink after the label.
- **Hover:** ink text. **Selected:** ink text with a 2px ink underline sitting on the tab row's hairline. Arrow keys move between tabs.

### Inputs / Fields (select)
- **Style:** native select, 1px hairline border, Sheet fill, 2px radius, Sans 13px.
- **Focus:** the global focus ring: 2px Rubricator Red outline, 2px offset.

### Cards / Containers (sheet)
- **Corner Style:** square.
- **Background:** Sheet on Desk Grey.
- **Shadow Strategy:** none (see Elevation).
- **Border:** 1px hairline.
- **Internal Padding:** 24px for padded sheets; tables run edge to edge with 16px row-end padding.

### Navigation (running head)
- **Style:** sticky, Desk Grey, double ink rule below. Wordmark, title, then the next-step strip: a "Next" capitals label, the first command chip, its reason in faded ink, and a "N steps" disclosure (Sans 14px, Pencil Shade on hover and when open) that opens the popover listing every step with its source ("from checks" / "from your session"). At most five steps, in this order: a docs shortfall, the steps the student asked for in the session, the checks, then asked-for steps that the docs or the readiness check would refuse, each with a faded note saying why (an "on hold" flag if one leads the strip).
- **Mobile:** wraps to two lines; the next-step strip spans the full width; date and spacer hide.

### Section table (signature)
- Header row of 12px capitals over a 1px ink rule, sticky under the head. Rows divided by Soft Hairlines; outline levels indent 14px / 28px, level 1 in 600, levels 3-4 in second ink.
- Category scores are centred figures; low scores in Rubricator Red 600; missing scores a faint centred dot; low-confidence grades italic.
- Length column: figure over a 3px bar (second-ink fill on Soft Hairline track) with a 1px ink target tick.
- Row hover: Pencil Shade at 60%. Selected row: Pencil Shade with the section number in red.
- Under the table, a legend line in Sans 13px over a 1px ink rule spells out the abbreviations.

### Apparatus entry (signature)
- Two-column grid: a 3.2em locator column in Mono 12px with bare line numbers ("12" / "3–5"; a prefix like "l." reads as "1." in Mono), then the lemma line: italic quoted passage, a faded closing bracket, and an anchor-state note in Deep Rubric if moved or unresolved.
- Below, the note: severity in 12px capitals (major: Rubricator Red 700; minor: second ink; note: faded ink), then category, comment id and file in faded ink, an em dash, and the comment body in Serif 16px.
- Entries divided by Soft Hairlines.

### Getting started (checklist)
- Shown only while setup is incomplete. With nothing graded it is the Sections view's panel ("Getting started" headline, "N of 6 done" meta); otherwise a block under "Needs attention"; on the empty-project screen a padded sheet. Under 1080px the panel moves above the section table so the first screen leads with what to do.
- An ordered list divided by Soft Hairlines: a 22px marker column (step number in Sans 13px faded ink, or a drawn 14px second-ink tick when done), the step in Serif 16px. Done steps: second ink, with their date in Sans 12px. The first open step: ink, 600, followed by its command chip and a Sans 13px hint. Later open steps: faded ink, no chip, so there is one next action.
- During setup the status line's docs figure reads "· needed for grading: 70%" in faded ink instead of the low-confidence warning, and the strip's "No submission date documented" stays hidden (step 4 asks for it).

### Todos tab
- A split: *Open* (and a collapsed *Done*) on the left sheet, *Waiting for your review* on the right. Open todos are apparatus entries: the short id as locator (Mono), the title in Serif 16px, a Sans 13px meta line (section link · "from c17 resolved" · "#12" when mirrored to GitHub), and a state line with "Its comments are closed" in capitals when all source comments are closed, and a "Done" checkbox.
- Ticking builds `/margi todos done t… t…` in the same sticky command bar as comment answers. Done todos show date and who closed them ("by you", "on margi's evidence", "closed on GitHub"); the student's note is set like their other words (italic, curly quotes).
- A comment with an open todo ends its note with "→ todo: <title>" in Sans 13px second ink, linking to the tab.

### Comment lifecycle (apparatus)
- The section panel opens with a progress line in running prose under the meta line: "Since 3 Oct: **1 of 3** major comments resolved · 1 withdrawn · 1 open" (Serif 17px, second ink, figures in ink 600). No hue: progress is good news (The No Verdict Hue Rule).
- *Open comments* lists every major and minor comment of the section and its subsections that isn't closed, across all grades, by severity, then age. Each apparatus entry adds, under the note, a thread and a state line.
- Thread: a 1px hairline rule on the left, 15px second ink; each line starts with an 11px capitals speaker label ("You, 5 Oct" / "margi, 10 Oct"). The student's own words are set like the lemma (italic in curly quotes) because both are the student's text; margi's verdict reasons stay roman.
- State line: 11px capitals ("Open since 3 Oct", "Addressed · awaiting a grade", "Still open · checked 10 Oct"), then the passage signal in Sans 12px ("passage changed" in Deep Rubric, "unchanged" / "moved" in faded ink), and on the right an "Answer" checkbox (ink accent). A ticked entry takes Pencil Shade at 55%.
- Ticking one or more comments shows a bar at the foot of the panel: hint text, the `/margi respond c3 c5` command chip and a "Clear" text button. It sticks to the bottom of the panel (of the viewport on phones), with an ink rule above it and no shadow.
- *Noted strengths* lists the note comments of the selected grade. *Closed* (resolved, withdrawn, won't fix) is a collapsed disclosure under an ink rule; its entries are second ink and a closed major is no longer red.

### Timeline strip (every view)
- Under the status line: one prose line in Serif 16px ("**171 days** left until submission on 31 Mar 2027 · next: *Method drafted*, 1 Dec · 2 milestones missed" with the missed count in Rubricator Red, then a "Timeline" link), over a 14px axis: a hairline from start to end, the elapsed part as a 1px ink rule, milestone ticks 7px tall (met: ink, open: faded ink, missed: 2px red, plain dates: hairline), today as a 1px ink rule, the deadline as a 10px ink tick (red once passed). Start date, "Today" and "Submission <date>" sit beneath in Sans 13px faded ink.
- Under 720px only the prose line remains. Without a deadline: "No submission date documented." and a command chip.

### Timeline chart
- One sheet; the SVG is drawn at the panel's pixel width (720px minimum, so phones scroll it sideways inside the sheet, opened at today). A 200px label column on the left; month labels in Sans 11px faded ink with Chart Grid month rules through all rows.
- Rows: *Length* (snapshot totals as a 1.6px Chart Ink line with 3.2px dots, a dotted run to the current length as an open dot, the goal as a dashed faded-ink rule labelled "goal 9 000"), then one row per section down to level 2 (deeper sections fold into their parent; labels Serif 15px, level 1 in 600), then *Commits* (one faded-ink tick per day, 4-16px tall by count). Ink rules separate the three bands; Soft Hairlines separate section rows.
- Marks: grade = 4px filled Chart Ink dot; not ready = open faded-ink circle; the student's answers = a short second-ink tick below the row centre; a milestone = a 1px staff with a small pennant (ink when met, faded ink when open, red and 1.6px when missed); a plain date = a dotted hairline through the section rows.
- Today runs through every row as a 1px ink rule labelled TODAY; the deadline as a 1.6px ink rule labelled SUBMISSION (red once passed). Every mark has a hover tooltip (the score-history tooltip style); grade marks and row labels open the section.
- A legend line under the chart (Sans 13px, drawn glyphs), then the milestone table (`plain` table: date, milestone, sections as links, state: "met 8 Oct", "met late, 8 Oct", "due in 9 days", "missed" in red).

### Passage entry (Literature apparatus)
- The Literature view uses the Sections split: the rated-literature table left (selected row: Pencil Shade, relevance figure in red), the apparatus panel right for one paper: name as headline, a meta line (relevance, role, thesis sections, cited or not, rating date), the PDF path with an "open the PDF" link, the rating's why as summary, caveats as an italic-led note.
- Each key passage is an apparatus entry: locator `p. N` in Mono 12px; the paper's own section path in Sans 13px faded ink with › separators; the page crop; the lemma line (italic quote, faded bracket, anchor state in Deep Rubric: "found on p. N, not p. M", "passage not found in the PDF"; "read from the page image" in faded ink); the passage's why as the note; "Open p. N in the PDF" in Sans 13px with a drawn 11px external-link icon.
- The crop: a greyscale page image on white inside a 1px hairline, square, no shadow; top and bottom fade out over 10px so it reads as an excerpt (no fade in print). Width fills the panel up to 1.5x print size and never drops below print size; on a phone it scrolls sideways inside its frame. Quoted lines carry the Passage Wash as an overlay, not baked into the image. Dark mode dims the crop to 88% brightness.
- A crop that doesn't load (PDF not on this machine, changed, or not rendered yet) is replaced by a Sans 13px faded note saying how to get it back, and the page link hides.

### Score history (small multiples)
- Grid of 140px-minimum figures, one per category: caption in capitals with the latest score in Serif 600; a 200 x 72 line chart with min/max grid lines, a dashed midline, a 1.6px Chart Ink line and 3.2px dots (red when low) ringed in Sheet; start and end dates beneath.
- Hover shows an ink tooltip with Sheet text, 2px radius, fading in over 80ms.

### Motion
Opening a section staggers the apparatus children in: 220ms `cubic-bezier(0.16, 1, 0.3, 1)`, 6px rise, 30ms steps up to 90ms. Disabled under `prefers-reduced-motion`.

## Do's and Don'ts

### Do:
- **Do** set feedback as annotation beside the student's text: locator, lemma, bracket, severity, note.
- **Do** keep red to attention (major, low scores, changed since grading, warnings) and to the active mark and focus ring.
- **Do** separate regions with 1px rules: ink for headings and table heads, hairline for sheet borders, soft hairline between rows.
- **Do** use tabular lining figures and space-grouped thousands for every number.
- **Do** write labels as 12px letter-spaced Sans capitals that name a column, block or field directly.
- **Do** give every command a copyable command chip.
- **Do** define every colour for both light and dark modes through the same role names.

### Don't:
- **Don't** use KPI cards, hero numbers or filled colour badges; put figures in the status line's prose and flags in letter-spaced text.
- **Don't** colour good news: no green, no red for falling deltas, no red wordmark or targets.
- **Don't** round or shadow content sheets; only the floating popover lifts.
- **Don't** set content in Sans or Mono; Mono is for commands, paths and line locators only.
- **Don't** add weights beyond the inlined set (Serif 400/400i/600, Sans 400/700, Mono 400).
- **Don't** set a capitals label above a heading as an eyebrow; capitals are the label itself.
