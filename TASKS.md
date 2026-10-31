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

- [x] **A1 Fetcher** (`receipts/fetch.py`): httpx with a disk cache in `cache/`, robots.txt, about 1 req/s
      per host, and a User-Agent naming the project. Returns url, final_url, status, html, text,
      fetched_at and sha256. Refuses sources whose terms are unverified (meetup.com).
- [x] **A2 Page finder + text** (`receipts/pages.py`, `receipts/text.py`): the home page plus the
      same-site about/contact/apply/portfolio/team/program links (up to 5 pages). Turns HTML into
      sentences. `quote_on_page(quote, text)` is an exact match after normalizing whitespace and case.
- [x] **A3 Rules** (`receipts/rules.py`): live, place, deadline, check size / fact, link, offer.
      Each one takes a claim and its pages and returns a receipt via `make_receipt`.
- [x] **A4 `receipts check [--all|<id>]`** → `out/receipts.json`; `receipts probe` → Probe 8 after,
      the Probe 5 split and status counts.
- [ ] **A5 (code ready, waiting for the API key) Model suggestions** (`receipts/model.py`): Claude suggests a sentence for fuzzy claims
      (offers, program length). Cached by page hash, and the quote is checked by code: not found →
      `refused`; found but not an exact match → `inferred`.
- [x] **A6 `receipts apply out/decisions.json`**: git worktree on the branch `receipts/2026-10-31`
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

## Status 12:35
- Real output exists: `python -m receipts check --all` (75 s cold, about 1 s from cache) writes
  `out/receipts.json` with 1,080 receipts. Probe 8: **0 → 318 / 1,080**. **B1, build against the real
  file now** (run `check --all` once; `out/` is gitignored).
- Statuses today: supported 318 · contradicted 1 (deltav, real) · silent 746 · refused 15.
  Offers are always silent until the model reads them; that's deliberate.
- **B2:** use the real `check` to score: `receipts.check.run(entries=<planted list>, out=<tests/planted/out.json>)`
  takes any entry list. Planted `.invalid` URLs fail DNS → `contradicted` on live.

## Status 12:45: read this first, pjsk02
- **Goals:** `python -m receipts goals` → **12 / 14 met**. The two open goals are P3 (review page)
  and P4 (planted test). See GOALS.md.
- **Change of plan:** Lane A is building **B1 (review page) now**, because it's on the demo's
  critical path. **pjsk02: please take B2 (planted-errors test) now**, on branch `pj/planted`.
  If you already started B1, tell VJ right away so we don't both build it.
- What B2 must produce for goal P4: `python -m receipts test` writes `out/planted_score.json` =
  `{"planted": N, "caught": X, "missed": Y, "false_alarms": Z, "rows": [...]}` and prints the table.
  The target is recall ≥ 0.8 with at most 1 false alarm on the unchanged entries.
- How to run the real checker on your test copy (no network needed for entries already cached):
  `from receipts import check; fresh, _ = check.run(entries=planted_entries, out=ROOT/"out"/"planted_receipts.json")`
  - Planted `https://planted-<id>.invalid` urls fail DNS → `live` comes back `contradicted`.
  - A wrong Check size → `contradicted` only if the page has a check-like sentence with a different
    amount; otherwise `silent`. Pick techstars ($220K, cached) for the wrong-number plant.
  - Duplicates and out-of-scope are not `check` statuses: write `receipts/dedupe.py` as described in B2.
- Pull `main` first: `git pull origin main`. Real numbers: Probe 8 is 0 → 349 / 1,080 verified, 684 with a sentence.

## Status 12:53
- **B1 is done** (Lane A): `python -m receipts review` → `out/review.html`. It has a sidebar of status
  filters, a Probe 8 header, one card per org with problems first, a "How this was checked" step trace
  per claim, Accept/Reject, and a decisions.json download. P3 passes. **13 / 14 goals met.**
- **The only open goal is P4 = B2 (pjsk02).** If you haven't started by 13:30, say so and Lane A
  will build it, so the 14:00 stranger test has the whole product.
- UI copy rule for anything you add: plain, short sentences. No em dashes, no emoji, no "AI magic"
  words. Name things by what they are ("Claude's reading", "checked by code").

## Status 12:56: 14 / 14 goals met. Thanks pjsk02, B2 is merged (`4d78858`)
- `python -m receipts test` → planted 6 · caught 5 · missed 1 · false alarm 1 · precision 0.83 · recall 0.83.
  - The miss: wrong town (Boston → Worcester) on founder-institute stays `silent`, because their
    global site names no town. Honest, and a good thing to show.
  - The "false alarm" is **deltav** in the real data ($75K on their page vs "Up to $20K" in the
    Atlas). It is probably a real discrepancy, but it counts as an alarm until a person confirms it.
- Your `review.py` was superseded by Lane A's version (sidebar, step trace). It's in your branch history.
- **Pull main before you start anything new:** `git checkout Je-Branch && git merge origin/main`
  (or branch fresh from main).

## Next round (12:56–13:45): improvements

### Lane B (pjsk02)
- [ ] **B4 De-duplication against the 197** (a Track A rubric item). Run `receipts.dedupe.find_duplicate`
      over all 197 real entries, pairwise, and write `out/duplicates.json` plus a short printed list.
      Report only: never merge or delete. Wire it as `python -m receipts dedupe`. Expect a few
      near-duplicates like `deltav` / `deltav-demo`. Say which ones are the same org and which are
      related but distinct.
- [ ] **B5 More plants**: add 2 more of each failure type (12–18 plants total) so the score isn't
      based on 6. Prefer cached entries so the test stays fast. Keep every id `planted-`.
- [ ] **B6 Stranger test at 14:00**: open `out/review.html` and give it to someone who hasn't seen it:
      "Review these three claims." Write down what confused them in `notes/stranger.md`.

### Lane A (VJ-yadav + Claude)
- [x] Wrong-town rule: a page with a Massachusetts street address in a different town → `contradicted`.
- [x] Click test (5/5, after/clicktest.txt): 5 random receipt links open on the highlighted sentence (SELFCHECK Truth).
- [x] Founder view (24 verified, 67 with a sentence, of 83): a filter in review.html for VJ's 12-funder shortlist (0 → N of 83).
- [ ] One accepted decision end to end (needs VJ to click Accept: the human gate): review.html → decisions.json → `apply` → branch + validator.

## Status 13:26: pull main, read README.md first
- PR #1 is in. BRIEF.md is kept. The place-rule change was measured on the real 197 and reverted:
  it raised 12 place contradictions, most false ("East Coast - United States Boston", "Do I have
  to be in Boston?"), and supported claims on words like "main" and "the". Its two real finds,
  **matrix** and **accomplice**, are now caught by a wider address pattern. Good catch, credited in the commit messages.
- **The README is now the single guide**: what it is, who it's for, how to run, and the status checklist.
- `out/review.html` is now a **maintainer console**: Home, Entities (grid of 197 + detail panel),
  Review queue, Refused, Add an entity, and a Before/After switch. Run `python -m receipts review`
  after `check --all` (see README "How to run"). `.env` is optional for you: without a key the fuzzy
  claims stay silent.
- Please **don't run `check --all --model` with a key** unless asked: it costs API credits for pages not cached.
- Your open items: **B4** (`receipts dedupe` across the 197), **B6** (stranger test with the console
  at 14:00). B5 (more plants) only if time allows.

## pjsk02: test plan and next tasks (13:40)

### T1 Full test from a clean pull (about 10 min). Report any line that differs.
```bash
git checkout main && git pull
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m receipts check techstars
#  expect: 9 claims; "this run: supported 5 · contradicted 0 · silent 4 · inferred 0 · refused 0"
#  expect quotes: deadline "Nov 18 2026 Final Deadline"; Equity "...will be 5% of the company..."
.venv/bin/python -m receipts check --all
#  about 75 s the first time (polite fetching), then about 2 s from cache/
#  expect (no API key): "supported 351 · contradicted 3 · silent 711 · inferred 0 · refused 15 (1080 claims)"
#  ±3 is fine (sites change). With VJ's key the 711 silent split into 377 silent + 334 inferred.
.venv/bin/python -m receipts probe
#  expect: "Probe 8 claims with a receipt     351 / 1080  (verified by code)"
.venv/bin/python -m receipts review && open out/review.html
#  expect: maintainer console. Click through Home, Entities, Review queue, Refused, Add an entity, and Before/After.
#  On Home, "Start here" shows 3 contradictions: Matrix (Waltham vs Cambridge), Accomplice
#  (Cambridge vs Boston), MIT delta v ($20K vs $75K).
.venv/bin/python -m receipts review --fixture && open out/review-fixture.html
#  expect: the 5-row fixture, in its own file (it no longer overwrites review.html)
.venv/bin/python -m receipts test --check
#  expect: planted 6 · caught 5 · missed 1 (planted-founder-institute:place:0) · false alarm 1 (deltav:fact:0)
.venv/bin/python -m receipts changes
#  expect: "0 changed, 0 new" when run right after another check
echo '{"id":"techstars-copy","name":"Techstars Boston Accelerator","cat":"accel","loc":"Boston","url":"https://www.techstars.com"}' > /tmp/dup.json
.venv/bin/python -m receipts propose /tmp/dup.json
#  expect: "✕ possible duplicate of techstars" and "stopped: fix the above before fetching anything"
.venv/bin/python -m receipts goals
#  expect without a key: P2 (model pass) FAILs; everything else passes once check --all and test have run
```
Also check, by eye: (a) open 3 random ↗ links in the console. Each should open the org's page with
the sentence highlighted. (b) No person's name, email or phone appears anywhere in the console.

### T2 B4 de-duplication across the 197 (about 20 min)
`python -m receipts dedupe` → `out/duplicates.json` and a printed list of candidate pairs among the
real 197 (name similarity or same host). Report only, never merge. For each pair, say "same org" or
"related but distinct" (e.g. deltav / deltav-demo). It feeds the Home page later.

### T3 Stranger test at 14:00, now on the **public view** (Lane A is building `out/atlas.html`)
Ask someone who hasn't seen it: "Here are two funders. Which one's information would you trust
less, and why?" Don't help them. Write down the time it took, their answer, and what confused them
in `notes/stranger.md`. That is the Track B test.

Rules unchanged: organizations only, no `.env` in git, no Co-authored-by trailers, no `--model` runs.

## 13:55: pjsk02 owns two tracks now; Lane A owns consolidation and the data infrastructure

Reference builds are committed: `docs/public-view.html` (public view) and `docs/maintainer-console.html`
(console). Open them straight from the repo. They are snapshots; regenerate them with
`python -m receipts public` / `review`.

### P-UI Public view (branch `pj/public`)
- **You own `receipts/public.py`.** Lane A won't edit it, so there are no conflicts. Build on the current
  version: "I need…" filter, a proof mark per claim, Compare two, Before/After.
- Track B test: a stranger, unaided, says which of two entries to trust less, and why. Optimize for that.
- Keep these: plain copy (no em dashes, no "AI" wording), organizations only, contradictions shown as
  "their site says otherwise" with both values (never as corrected data), and the Before/After switch.
- Ideas: a map or town filter, "proven" badges on the founder's shortlist, a mobile layout, keyboard compare.

### P-CLAIMS Raise Probe 8 from 351 toward 600–700 verified (branch `pj/claims`)
**The bar (non-negotiable; this is the Truth score):** "supported" still means *code* found an exact
sentence on the org's own page that matches the Atlas value. A model reading never counts. A keyword
hit alone never counts.
Methods that are allowed and likely to pay off:
1. **More of the org's own pages**: read `sitemap.xml` (if robots.txt allows) to find the
   about/contact/apply/portfolio/terms pages the homepage doesn't link. That is the biggest lever for place, facts and links.
2. **JavaScript-only sites**: render with Playwright (installed in `../mass-ai-atlas`) **only** when
   robots.txt allows. Never to get around a 403/429 block: that is a "no".
3. **Links**: name aliases (e.g. "MIT CSAIL" ↔ "CSAIL"), with both orgs' own pages already in cache.
4. **Place**: a zip code or town on the contact page; St/Street-style matching already exists (`place_pattern`).
5. **Facts**: number + unit variants ("12-week", "three months" is NOT 13 weeks).
How to submit, so Lane A can merge:
- Your PR description has to show `receipts goals` 14/14, `receipts test` (no new false alarms),
  and the before/after of `receipts probe`.
- Attach **20 random newly supported receipts** (key + quote) so we can check them by eye.
  If more than 1 of 20 is wrong, the rule doesn't merge.
- Don't run `--model` (it costs credits). Code-only gains are what count for Probe 8.

### Lane A (VJ-yadav + Claude), in parallel
- Data infrastructure: an evidence sidecar for the Atlas PR, a monthly re-check workflow, and `make check`.
- Consolidation: we merge P-UI and P-CLAIMS after checking them against the bar above.
