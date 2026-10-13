# /margi read [pdf…]

Rate literature PDFs for their relevance to **this** thesis.

## Inputs

1. `margi/docs/*.md`, especially `research-question.md`, `field.md`, `method.md` and `structure.md`.
   Below the docs threshold, apply the same rule as in `grade.md`.
2. Extracted text: run `uv run margi extract-pdfs [pdf…]`. It prints `pdf<TAB>text-file<TAB>flags`.
   Read the text files, which contain `--- page N ---` markers. With no arguments, all PDFs in the
   configured literature directory are processed. `flags` is `-` or a list like `5:no-text,10:not-prose`
   naming pages whose text layer can't be trusted; see *Reading the PDF itself* below.
3. The bibliography (`literature.bib` in the config), if any, to match PDFs to cite keys.
4. Previous `margi/feedback/*_read_*.json` records. Don't re-rate unchanged PDFs unless asked.

## Reading the PDF itself

The text cache is the cheap first pass. Read pages straight from the PDF (the Read tool with
`pages`, at most 20 pages per call) only where the text fails you:

- a flagged page: `no-text` (a scan or a figure-only page), `garbled` (unmapped glyphs) or
  `not-prose` (a table, formulas, or a font whose letters came out wrong), when that page matters
  for the rating;
- `all:failed`, when the file couldn't be extracted at all; read the first pages (abstract,
  introduction, conclusion) instead of the whole file;
- a passage you need that looks wrong in the text even though its page isn't flagged, e.g.
  letter salad inside a figure, or a table or equation you need to understand.

Don't read whole PDFs visually when the text is fine: it costs far more and gives the same words.

## Per PDF

- `relevance`: 0–5. 5 = central to the research question or method, 0 = unrelated.
- `why`: 1–3 sentences tied to a specific part of the docs.
- `sections`: the outline section(s) where it matters (ids or titles from `structure.md`).
- `role`: one of `theory | method | data | related-work | counterposition | background`.
- `key_passages`: up to 5 entries of `{page, quote (verbatim, ≤ 300 chars), why, source}`. Copy
  quotes from the text file where you can (`source: "text"`); `source: "visual"` marks a quote you
  read from the page image because the text layer failed there. `page` is the `--- page N ---`
  marker the quote sits under. Finalize finds each quote in the PDF and records its page, the
  paper's section and the region to show in the dashboard; the student uses that to check you.
  So copy the words exactly, one contiguous run within one column, and don't stitch sentences
  together or quote figure text. Don't write an `anchor` yourself.
- `cite_key`: the bib key if one matches, else null.
- `cited_in_thesis`: true or false (grep the thesis sources for the cite key).
- `caveats`: limits, date, or a disputed status.

High-relevance PDFs that are not yet cited should appear first in `summary`.

## Draft

`margi/.staging/read.json`:
- `command`: `read`
- `scope`: `all` or a short list of file names
- `files_read`: the PDFs, the text cache files and the docs you used
- `payload`: `{"ratings": [{"pdf": "lit/foo.pdf", ...fields above}]}`
- `comments`: optional. Use them only to point at places in the thesis where a rated source
  should be engaged with, anchored as usual.

Then run `uv run margi finalize`.
