# Snowballing (design draft)

Status: draft, not implemented. Command: `/margi snowball <paper>`.

Starting from one seed paper, margi follows its references (and, two levels down, the references
of the best of those), screens every candidate against the thesis docs, and passes only the
survivors on. Full text is read only at the very end.

## Pipeline

```
seed ──resolve──▶ level 1: references of seed
                    │  screen (abstract) ─▶ keep score ≥ threshold, at most max_per_paper
                    ▼
                  level 2: references of each kept level-1 paper
                    │  screen (abstract) ─▶ same rule
                    ▼
                  final selection (all kept papers, ranked)
                    │  full text: open-access PDF fetched, or the student adds it to lit/
                    ▼
                  /margi read on those PDFs (existing full-text rating, 0–5)
```

### Stage 0: resolve the seed

`<paper>` may be a DOI, a cite key from `refs.bib`, a PDF in `lit/` (DOI from the first pages)
or a title (OpenAlex search, the student confirms the match). The resolved OpenAlex ID is recorded.
If the seed is a book (see *Books* below), margi says so and stops: there is nothing to snowball
from.

### Stage 1: fetch (deterministic, `margi snowball fetch`)

- OpenAlex `referenced_works` of the parent, then the works themselves in batches of 50 with
  `select=id,doi,title,publication_year,type,primary_location,abstract_inverted_index,cited_by_count,referenced_works,best_oa_location`.
  Title and abstract arrive in the same response, so fetching the abstract costs no extra calls.
- Missing abstract → try Semantic Scholar by DOI. Still missing → the candidate is marked
  `basis: title` (see below).
- Every response is cached under `margi/.cache/openalex/`, so reruns and level 2 are cheap and a
  run can be reproduced.
- Deterministic signals per candidate, given to the agent as input, never as the score itself:
  - `in_bib` / `in_lit`: already known to the student;
  - `co_cited`: how many kept papers in the run reference it (computed after each level);
  - `year`, `type`, `cited_by_count`.
- Duplicates across parents are screened once; the candidate keeps a list of all its parents.

### Stage 2: screen (agent, abstract-based)

The agent scores each candidate 0–1 for relevance to the research question, using
`margi/docs/*.md`. Batches of ~25 candidates per prompt keep the scores consistent with each other.
Each score comes with a one-line reason and the doc it relates to.

Anchors, so that 0.7 means the same thing across runs:

| Score | Meaning |
|---|---|
| 0.9–1.0 | Addresses the research question, method or corpus directly |
| 0.7–0.8 | Clearly useful for a named section (theory, method, related work) |
| 0.4–0.6 | Same field, but the link to this thesis is indirect |
| 0.1–0.3 | Shares a keyword, little else |
| 0.0 | Unrelated |

Selection per parent: drop candidates below `threshold`, sort the rest by score (ties broken by
`co_cited`, then year), keep at most `max_per_paper`. Only kept papers are expanded at the next
level.

Already-known papers (`in_bib`, `in_lit`) are scored and expanded like any other but are not
proposed as new finds. They often lead to the best level-2 candidates.

### Books

margi does not snowball off books (OpenAlex `type` `book`, `book-chapter`, `edited-book`,
`monograph`, `reference-book`). A book found as a candidate is **ranked but never expanded**: it
is scored from whatever metadata OpenAlex has (abstract or description if present, otherwise
title, venue or publisher, year and topics) and can pass the threshold and reach the final
selection. It is a leaf in the tree. Its references are not fetched, and it does not count
against the run's expansion budget. margi focuses on digital humanities, where the core
literature is mostly articles and proceedings, so stopping at books costs little.

### Stage 3: full text (only for the final selection)

For each paper in the final selection:
- open access (`best_oa_location.pdf_url`): margi downloads it to `lit/snowball/` (a
  deterministic file, not AI text);
- otherwise it is listed for the student to obtain and drop into `lit/`.

Then `/margi read` rates the PDFs as usual (0–5, key passages, role, sections). An optional
`fulltext_threshold` can drop papers whose full-text relevance falls short of what the abstract
suggested.

Two scales on purpose, for now: screening scores 0–1 (from an abstract), `/margi read` rates
0–5 (from the full text). They judge different evidence, so they stay separate in v1. They may be
unified later (decided 2026-10-10).

## Why abstracts first, not titles

The first pass scores the abstract, not just the title:

1. **Same API cost.** OpenAlex returns the abstract with the title. Only LLM tokens differ:
   roughly 300 tokens per candidate instead of 30. For the worst case below (~450 candidates)
   that is ~135k input tokens, which is acceptable for a command run a few times per thesis.
2. **Titles can't carry a 0.7 threshold.** A hard cut-off needs a score that is roughly
   calibrated. Title-only scores are mostly noise, and digital-humanities titles are often
   metaphorical ("Reading Machines", "Distant Horizons"). A paper wrongly dropped
   at level 1 also loses its whole level-2 subtree, so a false negative costs more here than at
   any later stage.
3. **A title pre-filter isn't worth the complexity yet.** It would only pay off if a level
   became much larger than ~50 candidates per parent. If that happens, add a lenient title pass
   that drops only clear misses (< 0.2) before the abstract pass.

Candidates without an abstract (`basis: title`) are scored from the title, venue, type and
OpenAlex topics. They are **neither dropped nor expanded automatically**. Instead they appear in
a "needs a look" list, where the student decides. Books follow their own rule (see *Books*).

## Parameters

In `thesis.config.yml` under `snowball:`. Each can be overridden per run as a CLI flag.

| Key | Default | Meaning |
|---|---|---|
| `threshold` | `0.7` | Minimum screening score to be kept and expanded |
| `max_per_paper` | `10` | At most this many kept candidates per parent |
| `depth` | `2` | Levels below the seed (1 = references only) |
| `direction` | `backward` | `backward` (references); later `forward` / `both` (citing papers) |
| `max_screened` | `600` | Run-wide limit on candidates screened; the run stops and reports when it is hit |
| `fulltext_threshold` | `null` | Optional cut-off on the 0–5 full-text rating from `/margi read` |
| `mailto` | `null` | Contact address for the OpenAlex polite pool (and an API key if OpenAlex requires one) |

Worst case with the defaults, assuming ~40 references per paper: level 1 screens 40 and keeps 10.
Level 2 screens ≤ 400 (fewer after deduplication) and keeps ≤ 100. Up to ~110 papers can reach the
final selection. A large list is fine: how wide to cast the net is the student's choice, made
through `threshold`, `max_per_paper` and `depth`. The final list is ranked, so the strongest
papers come first either way. The defaults may be tuned once there is real usage.

## Output

- `margi/snowball/<run-id>.json`: the whole tree (seed, parameters, every candidate with
  parents, level, signals, score, reason, `basis`, kept or dropped and why). This is the audit
  trail. A dropped paper can always be traced to the score and rule that dropped it.
- A feedback record (`command: snowball`) via `margi finalize`, with the ranked final selection
  in its payload. The dashboard gets a reading-list panel from it.
- Nothing is written to `refs.bib` automatically. Adding BibTeX for papers the student accepts
  is a possible later opt-in.

## Known gaps

- **Missing reference lists.** Some articles and proceedings have no `referenced_works` in
  OpenAlex. Such a paper is ranked but cannot be expanded, and the run file says so. A possible
  later fallback: if its PDF is in `lit/`, extract the bibliography with pypdfium2 and resolve
  each entry through OpenAlex search or Crossref `query.bibliographic`.
- **Missing abstracts** for some publishers in OpenAlex; partly covered by the Semantic Scholar
  fallback.
- **Rate limits and keys.** Check OpenAlex's current policy before shipping; the cache keeps
  repeated runs cheap.

## Later: inclusion criteria (not in v1)

Hard yes/no criteria in addition to the relevance score. Two kinds behave very differently:

1. **Metadata criteria**, checked deterministically and for free, ideally as OpenAlex filters
   during the fetch:
   - year range (`publication_year`);
   - language;
   - document type (`article`, `book`, `book-chapter`, `preprint`, …);
   - peer review or venue type;
   - open access only.
2. **Content criteria**, judged by the agent:
   - "uses method X";
   - "works with corpus or period Y";
   - "empirical, not a position paper".

   These should be **tri-state** (`yes | no | unknown`), not boolean. Abstracts often don't say
   which method was used, so at screening time most answers are `unknown`. Rules:
   - at the abstract stage, only an explicit `no` excludes; `unknown` passes;
   - at the full-text stage, the criterion is decided for good, and `unknown` is resolved or
     reported.

Possible config shape:

```yaml
snowball:
  criteria:
    - id: method-topic-modelling
      kind: content
      text: "Uses topic modelling or another quantitative text-analysis method"
      required: true        # false = only boosts the rank
    - id: recent
      kind: metadata
      filter: "publication_year:>2010"
```

Every criterion's verdict and reason goes into the run file next to the score, so an exclusion
stays traceable.
