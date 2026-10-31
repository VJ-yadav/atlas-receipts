# Atlas Receipts — brief

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
| **8 claims with a receipt** | **328 / 1080** |

Claims by type: live 197 · place 197 · offer 318 · link 170 · fact 177 · deadline 21.  
This run: supported 328 · contradicted 13 · silent 724 · inferred 0 · refused 15.  
Planted harness: 6 planted, 6 caught, 0 missed, 1 false alarm (real deltav check-size mismatch).

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
