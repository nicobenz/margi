# /margi read [pdf…]

Rate literature PDFs for their relevance to **this** thesis.

## Inputs

1. `margi/docs/*.md`, especially `research-question.md`, `field.md`, `method.md` and `structure.md`.
   Below the docs threshold, apply the same rule as in `grade.md`.
2. Extracted text: run `uv run margi extract-pdfs [pdf…]`. It prints `pdf<TAB>text-file`. Read the
   text files, which contain `--- page N ---` markers. With no arguments, all PDFs in the
   configured literature directory are processed.
3. The bibliography (`literature.bib` in the config), if any, to match PDFs to cite keys.
4. Previous `margi/feedback/*_read_*.json` records. Don't re-rate unchanged PDFs unless asked.

## Per PDF

- `relevance`: 0–5. 5 = central to the research question or method, 0 = unrelated.
- `why`: 1–3 sentences tied to a specific part of the docs.
- `sections`: the outline section(s) where it matters (ids or titles from `structure.md`).
- `role`: one of `theory | method | data | related-work | counterposition | background`.
- `key_passages`: up to 5 entries of `{page, quote (verbatim, ≤ 300 chars), why}`.
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
