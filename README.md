# Atlas Receipts

Every checkable claim in the Mass AI Atlas, with the sentence on the organization's own live page
that proves it.

**Track A, "The Survey" (backend).** TOA "Chart the Common Wealth" hackathon, 31 Oct 2026.
Team: VJ-yadav, pjsk02.

## The gap

The [Mass AI Atlas](https://the-open-accelerator.com/ecosystem/) lists 197 Massachusetts AI
organizations and makes **1,080 checkable claims** about them:

| Claim | Count |
|---|---|
| The org is live | 197 |
| Its location | 197 |
| What it offers | 318 |
| Facts rows (check size, equity, program length…) | 177 |
| Links to other orgs | 170 |
| Deadlines | 21 |

**None of these claims links to the page that says it.** "Verified" is a single month stamp for the
whole entry. So:
- a founder can't tell whether *this* check size still holds;
- the one maintainer re-checks whole entries blind, on a calendar, at 10–15 minutes each.

## What it does

Atlas Receipts gives every claim a **receipt**: the URL, the exact sentence on the organization's own
page, when the page was fetched and the page's hash. **"Verified" then means a live page still says
it, per claim.** Next month only the claims whose sentence changed go back to a person.

**The model may suggest, code checks, a person decides.**

| Step | Done by | What happens |
|---|---|---|
| 1 Fetch | code | Reads each org's own pages (home, about, contact, apply, program). Respects robots.txt, sends about 1 request a second per site, caches every page. |
| 2 Find | code, with suggestions from Claude | Searches the saved pages for the amount, date, address or org name. For fuzzy wording ("offers mentorship"), Claude may point at one sentence. |
| 3 Check | code | Confirms the exact sentence is on the saved page and compares it with the Atlas value. A Claude reading is never "supported", only "inferred". |
| 4 Decide | the maintainer | Accepts or rejects in the console. `apply` writes only accepted rows to a branch of the Atlas, then runs the Atlas's own `validate.js`. |

| Status | Meaning |
|---|---|
| `supported` | code found the sentence on the org's own page and it matches |
| `contradicted` | the org's own page says something else; both values shown |
| `silent` | no page says it: needs review, with the pages searched |
| `inferred` | Claude's reading of a real sentence; **not verified** |
| `refused` | not collected (site terms or robots.txt), or a suggested sentence was not on the page |

## Who it is for

- **The Atlas maintainer.** The maintainer console shows the review queue riskiest first, every claim
  with its sentence and a link that opens the page with that sentence highlighted, and Accept / Reject.
  A re-check sends back only claims whose sentence changed, not 17 random entries a month.
- **Founders using the Atlas.** They can see which claims (a check size, a deadline) are backed by the
  funder's own page today. For one founder's 12-funder shortlist, see the numbers block below.
- **New entries.** A proposed organization is checked for duplicates and scope, and gets receipts,
  before anyone reads it.

## Probe line

<!-- metrics:start -->
**Probe 8: claims with a receipt, 0 → 380 of 1,080 verified by code.** 667 carry a sentence from the org's own page (283 of them are Claude's readings, labelled inferred; 4 are sentences that contradict the Atlas).

```
supported 380 · contradicted 4 · silent 398 · inferred 283 · refused 15      (checked 2026-10-31 18:30Z)
```

| Number | Value |
|---|---|
| Probe 8: claims verified by code | 0 → **380 / 1,080** |
| Claims carrying a sentence from the org's own page | 667 |
| Claims that need a person (contradicted, silent, inferred) | 685 |
| Real contradictions | 4: salesforce-bos, matrix, accomplice, deltav |
| Probe 5: the 52 entries last checked in June | 39 confirmed live by their own site; 2 with a contradiction; 92 of 256 claims verified |
| Links with a receipt | 75 / 170 |
| A founder's 12-funder shortlist | 0 → 26 / 83 verified (67 with a sentence) |
| Planted errors: caught / missed / false alarms | 6 / 0 / 1 of 6 |
| Click test, random receipts | 5 / 5 land on their sentence |
| Pages read from the orgs' own sites | 3,171 |
| Sites that block bots (respected) | 0 |
| Model (claude-haiku-5-5): cost of reading all 197 | $0.04 over 154 calls |
| Validator on the Atlas branch | PASSED: data/ is valid. |
<!-- metrics:end -->
All numbers in this block come from `after/metrics.json` (`python -m receipts metrics`), the same
source the console and the probes read.

- Before: `before/probes.txt`. After: `after/probes.txt`.
- **Real contradictions** (each needs a person to confirm):

  | Entry | The Atlas says | The org's own page says |
  |---|---|---|
  | deltav | Check size "Up to $20K plus living stipend" | "$75K equity-free funding" |
  | matrix | "Bay Colony, Waltham" | "101 Main Street, 17th Floor Cambridge, MA 02142" |
  | accomplice | "Cambridge" | "56 Wareham Street, Fl 3 Boston, MA 02118" |

- **Measured verifier** (`receipts test`, a test copy with planted errors; never the real data):
  6 planted, 5 caught, 1 missed, 1 false alarm. Precision 0.83, recall 0.83.
  - The miss: a wrong town on a global site that names no town.
  - The "false alarm" is the real deltav discrepancy, counted conservatively.
- **Click test:** 5 of 5 random receipts open on their sentence in a real browser
  (`after/clicktest.txt`).
- **Validator** on the Atlas branch `receipts/2026-10-31`, after applying a maintainer's 5 accepted
  decisions (`after/validate.txt`):
  ```
  Mass AI Atlas — validating 197 entries, 11 categories

  PASSED: data/ is valid.
  ```

## Declared sources

- **The organizations' own websites:** each Atlas entry's `url` plus up to 7 same-site pages.
  robots.txt is respected, about 1 request a second per host, the User-Agent names this project, and
  every fetch is cached in `cache/`.
  - **Refused:** meetup.com (its terms could not be verified to allow automated collection) and pages
    robots.txt disallows (e.g. a LinkedIn company page).
  - **Respected, not worked around:** sites that block bots (HTTP 401/403/429) show as `silent`, not dead.
- **Mass AI Atlas dataset:** https://the-open-accelerator.com/ecosystem/atlas.json (pulled
  31 Oct 2026). The Atlas repo github.com/holzerjm/mass-ai-atlas is used for `validate.js`.
- **Claude API** (`claude-opus-5-5`): suggests a sentence for fuzzy claims only. Every quote is checked
  by code, and readings are cached by page hash.
- **Organizations only.** Sentences about a person, emails and phone numbers are never used or shown.

## How to run (for teammates too)

```bash
git clone https://github.com/VJ-yadav/atlas-receipts && cd atlas-receipts
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
git clone https://github.com/holzerjm/mass-ai-atlas ../mass-ai-atlas && (cd ../mass-ai-atlas && npm ci)
echo "ANTHROPIC_API_KEY=..." > .env       # optional; without it fuzzy claims stay silent. Never commit .env

.venv/bin/python -m receipts check --all            # fetch + check all 197 (about 75 s the first time)
.venv/bin/python -m receipts check --all --model    # plus Claude's suggestions (costs credits once, then cached)
.venv/bin/python -m receipts review                 # build the maintainer console → out/review.html
open out/review.html
```

| Command | What it does |
|---|---|
| `check [--all\|<id>…] [--model] [--refresh]` | one receipt per claim → `out/receipts.json` |
| `review` | the maintainer console → `out/review.html` (Home, Entities grid, Review queue, Refused, Add an entity; Before/After switch) |
| `public` | the founder-facing public view → `out/atlas.html` (I need…, proof marks per claim, compare two, Before/After) and the enriched dataset `after/atlas-with-receipts.json` |
| `apply out/decisions.json` | accepted rows only → Atlas branch `receipts/2026-10-31` + `validate.js`; refuses `planted-` ids |
| `evidence` | the sidecar `after/evidence.yml`: per entry, each claim's sentence, URL, fetch time and page hash. `apply` puts it on the Atlas branch as `data/evidence.yml`, which the Atlas loader ignores, so the entry schema is untouched |
| `changes` | a re-check: only claims whose sentence changed come back |
| `propose new-entry.json` | a new organization: duplicate, scope and https checks, then receipts → `out/proposed/` |
| `test` | the planted-errors test copy: caught / missed / false alarms |
| `probe` | probes 1–8 |
| `goals` | every goal in GOALS.md, checked by code (exit 0 only when all pass) |

`make all` runs the whole pipeline from the cache; `make check` is the mechanical self-check (goals and the Atlas validator).
`.github/workflows/recheck.yml` re-checks every claim on demand (monthly once enabled), code only, and reports what changed in the job summary.
Built pages for reference: [docs/public-view.html](docs/public-view.html), [docs/maintainer-console.html](docs/maintainer-console.html).

Lanes and tasks are in [TASKS.md](TASKS.md); goals in [GOALS.md](GOALS.md); the one-page brief is
[BRIEF.md](BRIEF.md).

## Status checklist (updated as we go)

**Self-check: `python -m receipts goals` → 14 / 14 met** (eligibility, every scoring cap, Probe 8,
review console, planted test, README).

| | Item | Status |
|---|---|---|
| ✅ | Public repo, every commit after 09:00 | done |
| ✅ | Fresh atlas.json, before probes saved | `before/probes.txt` |
| ✅ | Fetcher: cache, robots.txt, ~1 req/s/host, project User-Agent | done |
| ✅ | Claim rules: live, place, deadline, check size / facts, links, offers | done |
| ✅ | Every receipt has url + quote + fetch time + page hash; quotes re-checked by code | goals C1, C2 |
| ✅ | Model pass: Claude suggests, code checks, never "supported" | count in the numbers block |
| ✅ | Maintainer console with Before/After, grid, queue, refused, add-entity | `out/review.html` |
| ✅ | Human gate: decisions.json → `apply` → Atlas branch → validator PASSED | Atlas branch commit `6e1ab9d` |
| ✅ | Planted-errors test (pjsk02) | 5 / 6 caught |
| ✅ | Click test, 5 random receipts | 5 / 5 |
| ✅ | Re-check ("next month"): only changed sentences come back | `receipts changes` |
| ✅ | README: gap, sources, probe line, validator output, how to run | this file |
| ⬜ | Before screenshots of the live Atlas (Directory, Techstars drawer, Galaxy, Kendall pins) | VJ |
| ⬜ | Stranger test on the console (14:00) | pjsk02 (B6) |
| ✅ | Evidence sidecar on the Atlas branch (`data/evidence.yml`, 649 claims) + validator PASSED | Atlas branch `8730e32` |
| ✅ | Re-check workflow (on demand; monthly once enabled) and `make check` | `.github/workflows/recheck.yml` |
| ✅ | Cost: model step on Claude Haiku 5.5 with code-chosen sentences; full run $0.04 (was ~$12) | `cache/_usage.jsonl` |
| ✅ | Public view for founders (Track B direction) | `docs/public-view.html` |
| ⬜ | Public view, next version | pjsk02 (P-UI) |
| ⬜ | Probe 8 from 351 toward 600–700, code-verified | pjsk02 (P-CLAIMS) |
| ⬜ | De-duplication across the 197 (`receipts dedupe`) | pjsk02 (B4) |
| ⬜ | BRIEF.md numbers updated to the final run | 14:30 |
| ⬜ | DEMO.md and PREP.md numbers, SELFCHECK log | end of day |
| ⬜ | 2-minute video, uploaded Public | 15:15 |
| ⬜ | Judging form by 15:25 (repo, video, brief, Track A, sources, validator, probe line) | VJ |

## Attribution

Data: Mass AI Atlas, The Open Accelerator, CC BY 4.0. This is a proposed tool for the Atlas
maintainer; it is not part of the public Atlas.
