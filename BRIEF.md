# Atlas Receipts — brief

Team: Vijay Yadav (VJ-yadav), pjsk02 · Track A (backend), with a founder-facing public view (Track B) · github.com/VJ-yadav/atlas-receipts · Probe 8, claims with a receipt: 0 → 373 of 1,080

## Problem
The Mass AI Atlas lists ~197 Massachusetts AI organizations with checkable facts (URLs, places, offers, fund sizes, deadlines, links). Hand-checking each entry takes 10–15 minutes. Stale or wrong values sneak in; “looks live” is not the same as proven.

## What “verified” means here
A claim is **verified** only when code finds an exact quote on the organization’s own live pages and builds a receipt via `make_receipt()` (URL, fetch time, reason required). Statuses: `supported` (code-proven), `contradicted` (page disagrees), `silent` (searched, nothing found), `inferred` (model suggested; not verified), `refused` (we will not fetch or assert). **Only code can mark `supported`. A person accepts or rejects before anything writes the Atlas.**

## How it works
1. Enumerate ~1,080 claims from `data/atlas.json`.
2. Fetch home + a few same-site pages (robots.txt, ~1 req/s/host, disk cache).
3. Rule checkers (live, place, offer, link, fact, deadline) emit receipts → `out/receipts.json`.
4. `receipts review` → `out/review.html`: a person Accept/Rejects; downloads `decisions.json`.
5. `receipts apply` edits `entities.yml` on a dated branch and runs the Atlas validator.
6. `receipts test --check` scores planted errors (wrong number/place/dead URL/duplicate/out-of-scope/unsourced).

## Numbers (`python -m receipts probe`, after `check --all`)
| Probe | Result |
|---|---|
| 1 approximate pins | 87 / 197 |
| 2 entries with no links | 104 / 197 (170 edges) |
| 3 no stages | 35 / 197 |
| 4 funders with Check size | 13 of 61 (applyBy on 3) |
| 5 lastVerified 2026-06 | 52 / 197 |
| 6 west of Worcester | 5 / 197 |
| 7 hand time per entry | 10–15 min (maintainer estimate) |

Probe 8 and every number of the run (generated from `after/metrics.json` by `python -m receipts metrics`; don't edit by hand):

<!-- metrics:start -->
**Probe 8: claims with a receipt, 0 → 373 of 1,080 verified by code.** 665 carry a sentence from the org's own page (288 of them are Claude's readings, labelled inferred; 4 are sentences that contradict the Atlas).

```
supported 373 · contradicted 4 · silent 400 · inferred 288 · refused 15      (checked 2026-10-31 18:47Z)
```

| Number | Value |
|---|---|
| Probe 8: claims verified by code | 0 → **373 / 1,080** |
| Claims carrying a sentence from the org's own page | 665 |
| Claims that need a person (contradicted, silent, inferred) | 692 |
| Real contradictions | 4: salesforce-bos, matrix, accomplice, deltav |
| Probe 5: the 52 entries last checked in June | 39 confirmed live by their own site; 2 with a contradiction; 92 of 256 claims verified |
| Links with a receipt | 69 / 170 |
| A founder's 12-funder shortlist | 0 → 25 / 83 verified (70 with a sentence) |
| Planted errors: caught / missed / false alarms | 6 / 0 / 1 of 6 |
| Click test, random receipts | 5 / 5 land on their sentence |
| Pages read from the orgs' own sites | 962 |
| Sites that block bots (respected) | 28 |
| Model (claude-haiku-5-5): cost of reading all 197 | $0.05 over 199 calls |
| Validator on the Atlas branch | PASSED: data/ is valid. |
<!-- metrics:end -->

## What it refuses
- People’s names, emails, phones, or handles in outputs, cache, or fixtures.
- Sources with unverified terms (e.g. meetup.com) → `refused`, not “dead.”
- Hand-built receipt dicts; `apply` on `planted-` ids; model marking `supported`.
- Treating HTTP 403 / JS-only pages as proof the org is dead.

## Monday for the maintainer
1. `python -m receipts check --all` (cold ~1–2 min; ~1 s from `cache/`).
2. Open `out/review.html`; Accept/Reject; Download `decisions.json`.
3. `python -m receipts apply out/decisions.json` on Atlas branch `receipts/YYYY-MM-DD`; read `after/validate.txt`.
4. `python -m receipts test --check` after rule changes (planted pack under `tests/planted/`).
5. Re-run `probe` and keep Probe 8 as the public scoreboard.

## Sources
Mass AI Atlas `entities.yml` / `data/atlas.json`; organization websites fetched under robots.txt with a project User-Agent. Demo fixture: `tests/fixtures/receipts.sample.json` (`receipts review --fixture`).

## Attribution
Mass AI Atlas, The Open Accelerator, CC BY 4.0.
