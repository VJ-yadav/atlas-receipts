# Atlas Receipts

Every checkable claim in the Mass AI Atlas, with the sentence on the organization's own live page
that proves it.

## Track

Track A, "The Survey" (backend). TOA "Chart the Common Wealth" hackathon, 31 Oct 2026.

## The gap

The Atlas makes **1,080 checkable claims** about 197 organizations: each org is live (197), its
location (197), its offers (318), its facts rows such as check size and equity (177), its links to
other orgs (170) and its deadlines (21). **None of them links to the page that says it.** "Verified"
is one month stamp for a whole entry, so a founder can't tell whether *this* check size still holds,
and the maintainer re-checks entries blind, 10–15 minutes each.

Atlas Receipts gives each claim a **receipt**: the URL, the exact sentence on the org's own page,
when it was fetched and the page hash. Then "verified" means *a live page still says it*, per claim.

**The model may suggest, code checks, a person decides.**

| Status | Meaning |
|---|---|
| `supported` | code found the sentence on the cached page and it matches the Atlas value (numbers, dates, names, places) |
| `contradicted` | the org's own page says something else; both values are shown |
| `silent` | nothing found: needs review, with what was searched and why |
| `inferred` | a model reading of a sentence that code confirmed is on the page. **Never shown as verified** |
| `refused` | the source's terms or robots.txt forbid collection, or the model offered a sentence that is not on the page |

## Declared sources

- **The organizations' own websites** (the `url` of each Atlas entry, plus up to 7 same-site pages:
  about, contact, apply, program, portfolio). Fetched with robots.txt respected, about 1 request a
  second per host, a User-Agent naming this project, and every fetch cached to disk.
  - **Refused:** meetup.com (its terms could not be verified to allow automated collection) and any
    page robots.txt disallows (e.g. a LinkedIn company page).
  - **Respected:** sites that block bots (HTTP 401/403/429) are reported as `silent`, not dead, and
    not worked around.
- **The Mass AI Atlas dataset:** https://the-open-accelerator.com/ecosystem/atlas.json (pulled
  31 Oct 2026), and the Atlas repo github.com/holzerjm/mass-ai-atlas for `validate.js`.
- **Claude API** (`claude-opus-5-5`): only *suggests* a sentence for fuzzy claims (offers,
  descriptive facts). Code checks every suggested quote against the cached page, and a model reading
  is never `supported`. Calls are cached by page hash.
- **No people:** organizations only. Sentences about a person, and any email or phone number, are
  never used as receipts or shown.

## Probe line

**Probe 8 (new): claims with a receipt, 0 → 349 of 1,080 verified by code**, and 684 of 1,080 carrying
a sentence from the org's own page (the extra 335 are model readings, labelled `inferred`).

```
supported 349 · contradicted 1 · silent 380 · inferred 335 · refused 15      (31 Oct, 12:55)
```

- Before: `before/probes.txt` (probes 1–8 on the fresh atlas.json). After: `after/probes.txt`.
- One real contradiction: **deltav**. The Atlas says "Up to $20K plus living stipend"; MIT delta v's
  own page says "$75K equity-free funding".

Validator output on the branch `receipts/2026-10-31` of the Atlas (from upstream `7f8f377`),
`after/validate.txt`:

```
Mass AI Atlas — validating 197 entries, 11 categories

PASSED: data/ is valid.
```

## How to run

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
git clone https://github.com/holzerjm/mass-ai-atlas ../mass-ai-atlas && (cd ../mass-ai-atlas && npm ci)
echo "ANTHROPIC_API_KEY=..." > .env          # optional: without it, fuzzy claims stay silent

python -m receipts check techstars            # one entry, about 10 s cold, 1 s cached
python -m receipts check --all --model        # all 197 entries, about 75 s cold
python -m receipts probe                      # probes 1-8
python -m receipts review                     # out/review.html: the maintainer's queue
python -m receipts apply out/decisions.json   # accepted rows only → Atlas branch + validate.js
python -m receipts test                       # planted-errors test copy: caught / missed / false alarms
python -m receipts changes                    # re-check: only claims whose sentence changed come back
python -m receipts goals                      # every goal in GOALS.md, checked by code
```

`apply` is the only path to `data/entities.yml`. It takes only the rows a person accepted in the
review page, edits only those lines on a branch in a git worktree of the Atlas (never its `main`),
bumps `lastVerified` on the touched entries, runs `node scripts/validate.js`, and refuses any
`planted-` test id.

## Attribution

Data: Mass AI Atlas, The Open Accelerator, CC BY 4.0.
