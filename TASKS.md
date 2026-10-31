# Atlas Receipts: tasks and prompts (31 Oct, from 12:20)

Two lanes that touch different files, so merges don't conflict.
- **Lane A** (VJ-yadav + Claude, consolidation): fetching, claim rules, `check`, `apply`. Commits to `main`.
- **Lane B** (pjsk02): the review page and the planted-errors test. Work on branches `pj/<task>`,
  open a PR to `main`, and Lane A merges.

## Ground rules (both lanes, no exceptions)
- **Organizations only.** No people's names, emails, phones or handles in any output, cache or fixture.
- **The model suggests, code checks, a person decides.** Only code can mark a claim `supported`.
  A model reading is `inferred` at most.
- **Every receipt is built with `receipts.claims.make_receipt()`**, which refuses a receipt with no
  URL, fetch time or reason. Never hand-build receipt dicts in product code.
- **Nothing writes `data/entities.yml`** except `receipts apply` on accepted decisions, on a branch
  of the Atlas clone, followed by `node scripts/validate.js`.
- **Planted test data** lives only in `tests/planted/`, every id starts with `planted-`, the screen
  says **TEST — planted**, and `apply` refuses `planted-` ids.
- Fetch politely: robots.txt, about 1 request a second per host, cache everything in `cache/`.
- Python 3.12: `python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt`, then `python -m receipts <cmd>`. Do not commit `.env`.

## The contract (read before you start)
- Claims: `receipts/claims.py` → `enumerate_claims(entries)` gives 1,080 claims
  (live 197, place 197, offer 318, link 170, fact 177, deadline 21).
- Receipt record: everything in the claim, plus `status, url, quote, fetched_at, sha256, reason,
  page_value, searched, by`.
  Statuses: `supported | contradicted | silent | inferred | refused`.
- Output: `out/receipts.json`, a list of receipts. Until the real run exists, build against
  `tests/fixtures/receipts.sample.json`, which has one of each status and ids prefixed `fixture-`.
- Decisions: `out/decisions.json` = `[{"key": "<receipt key>", "decision": "accept"|"reject",
  "new_value": <optional>}]`.

## Timeline
| Time | Phase |
|---|---|
| 12:20–13:20 | **Build** (the tasks below) |
| 13:20–13:50 | **Test**: full run on the 197, `receipts test`, SELFCHECK #2 |
| 13:50–14:30 | **Improve**; stranger test at 14:00; SELFCHECK #3 at 14:30 |
| 14:30–15:15 | README, brief, final run, after numbers |
| 15:15–15:25 | Video; judging form submitted by 15:25 |

---

## Lane A: VJ-yadav + Claude

- [ ] **A1 Fetcher** (`receipts/fetch.py`): httpx with a disk cache in `cache/`, robots.txt, about 1 req/s
      per host, and a User-Agent naming the project. Returns url, final_url, status, html, text,
      fetched_at and sha256. Refuses sources whose terms are unverified (meetup.com).
- [ ] **A2 Page finder + text** (`receipts/pages.py`, `receipts/text.py`): the home page plus the
      same-site about/contact/apply/portfolio/team/program links (up to 5 pages). Turns HTML into
      sentences. `quote_on_page(quote, text)` is an exact match after normalizing whitespace and case.
- [ ] **A3 Rules** (`receipts/rules.py`): live, place, deadline, check size / fact, link, offer.
      Each one takes a claim and its pages and returns a receipt via `make_receipt`.
- [ ] **A4 `receipts check [--all|<id>]`** → `out/receipts.json`; `receipts probe` → Probe 8 after,
      the Probe 5 split and status counts.
- [ ] **A5 Model suggestions** (`receipts/model.py`): Claude suggests a sentence for fuzzy claims
      (offers, program length). Cached by page hash, and the quote is checked by code: not found →
      `refused`; found but not an exact match → `inferred`.
- [ ] **A6 `receipts apply out/decisions.json`**: git worktree on the branch `receipts/2026-10-31`
      in `../mass-ai-atlas`, line-level edits to `entities.yml` (no YAML re-dump), `lastVerified` bumped
      on accepted entries, then `node scripts/validate.js` saved to `after/validate.txt`. Refuses `planted-`.

## Lane B: pjsk02

Paste each prompt into your coding assistant inside the repo. One branch and PR per task.

### B1 Review page: `receipts review` → `out/review.html` (branch `pj/review`)
> In this repo (Python 3.12, no new dependencies), create `receipts/review.py` with a function
> `build(receipts: list[dict], out_path)` that writes ONE static HTML file, with no framework and
> inline CSS and JS, from the receipts list described in TASKS.md "The contract". Test it with
> `tests/fixtures/receipts.sample.json`. Layout:
> (1) A header: "Atlas Receipts". "Probe 8: claims with a receipt 0 → N / total", where N = the
> number with status `supported`, and counts per status.
> (2) One card per entry, entries with problems (contradicted, silent, refused, inferred) first, and
> within a card the claims sorted by field risk: deadline, fact, live, place, link, offer. Each claim
> row shows a status badge (supported = calm green, contradicted = red ▲, silent = grey ○,
> inferred = amber, explicitly labelled "inferred — not verified", refused = dark), the Atlas value,
> the quote in quotation marks, the page value when contradicted, the reason, the fetch date, and a
> ↗ link to `url + "#:~:text=" + encodeURIComponent(first ~8 words of the quote)` that opens in a new
> tab. Silent rows list the `searched` URLs. Supported rows stay compact.
> (3) Accept / Reject buttons on every non-supported row. The choices are kept in memory, plus a
> "Download decisions.json" button that saves `[{"key", "decision"}]`.
> (4) At the bottom, a "Refused" section grouped by reason, with counts.
> Any entry whose id starts with `planted-` must show a "TEST — planted" banner.
> Escape all text (quotes come from the web). Show no people's names or contact details.
> Wire it into `receipts/__main__.py` as the command `review` (reads `out/receipts.json`, or `--fixture`).

### B2 Planted test copy (branch `pj/planted`)
> Create `tests/planted/build.py`, which reads `data/atlas.json`, takes 30 real entries (include
> techstars and entries with a Check size or applyBy), and writes `tests/planted/entries.json`:
> the 30 entries unchanged, plus planted copies whose ids are prefixed `planted-`. Change ONLY the
> Atlas side, never a website. Plant at least one of each:
> wrong number (techstars Check size $220K → $500K; expected `contradicted`); wrong place (a Boston
> `loc` → "Worcester"; expected `contradicted`); dead (url → `https://planted-<id>.invalid`;
> expected `contradicted` on live); duplicate (an existing entry under a slightly different name;
> expected `duplicate:<id>`); out of scope (loc "Providence, RI"; expected `out_of_scope`); unsourced
> fact (a Check size on an entry whose site gives none; expected `silent`). Also write
> `tests/planted/expected.json` = `[{"key": "<claim key>", "expect": "<status>", "type": "<failure type>"}]`.
> Then create `receipts/plantedtest.py` with `score(receipts, expected)`, which prints a table:
> planted N, caught X, missed Y, plus false alarms on the 30 unchanged entries (any `contradicted`
> there). Precision and recall. Use `receipts.claims.enumerate_claims` for keys.
> Duplicate and out-of-scope detection: add `receipts/dedupe.py`, with `find_duplicate(entry, entries)`
> (normalized-name similarity ≥ 0.85 against the 197, or the same url host) and
> `out_of_scope(entry)` (a loc naming a non-MA state, or lat/lng outside MA). It runs on planted
> entries and on any proposed new org.

### B3 Brief + demo assets (no code, from 14:30)
> Using DEMO.md (in the parent folder; ask VJ), draft `BRIEF.md`, one page:
> problem · what "verified" means here · how it works · numbers (filled from `receipts probe`) ·
> what it refuses · Monday for the maintainer · sources · attribution
> "Mass AI Atlas, The Open Accelerator, CC BY 4.0".

## Merge order
`A1/A2/A3` → `B1` (review on real output) → `A4/A5` → `B2` (test on the real check) → `A6`.
Lane A pulls each PR, runs `../.venv/bin/python -m receipts check techstars && … review`, and merges.
