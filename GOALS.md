# Goals: we work until all of these pass

Run `python -m receipts goals`. Every goal is checked by code, not by eye. The loop:

1. Run `goals`.
2. Take the first FAIL. E and C goals come before P goals: an E or C failure caps the score.
3. Fix it in the smallest change, commit, push.
4. Repeat until it prints `14 / 14 goals met`.

Owners: **A** = VJ-yadav + Claude, **B** = pjsk02. Merges to `main` go through Lane A.

| Id | Goal | Why it matters (rubric) | Owner |
|---|---|---|---|
| E1 | Every commit is after 09:00 on 31 Oct | eligibility | all |
| E2 | No `.env` or API key ever committed | safety | all |
| C1 | Every receipt has url, fetched_at, reason; supported/inferred carry a quote and page hash | Truth: "a field with no source" caps at 2 | A |
| C2 | Every quote shown is really on the cached page, re-checked | Truth 4: "the source actually supports it" | A |
| C3 | Only code marks a claim supported | Truth: "inference shown as verified" caps at 2 | A |
| C4 | No people: no person-sentences, emails or phones in output | event rule: organizations only | A |
| C5 | No planted entry in real output; `apply` refuses `planted-` ids | Truth: a fabricated org caps at 1 | A + B |
| C6 | The Atlas branch passes `node scripts/validate.js` | Track: "fails the validator" caps at 2 | A |
| C7 | Every silent/refused receipt says what was searched or why | Truth: "refusing everything" caps at 2 | A |
| P1 | Probe 8: ≥ 340 / 1,080 verified by code, and ≥ 650 carrying a sentence from the org's own page (inferred ones labelled) | Track: a measured before/after | A |
| P2 | Model pass ran: fuzzy claims are `inferred`/`refused`, never `supported` | calibrated confidence | A |
| P3 | `out/review.html`: all statuses, highlight links, Probe 8 header | Track: a review queue usable unassisted | **B (B1)** |
| P4 | `receipts test` on the planted set: recall ≥ 0.8, at most 1 false alarm | Innovation: a measured verifier | **B (B2)** |
| P5 | README filled: sources, probe line, validator output, how to run | submission checklist | A |

After 14/14: improvements (more claim types, a second independent source, re-check on change),
then the demo assets.

**Note on P1 (12:52):** the first target, 450 verified, was set before measuring. The measured ceiling
for code-only verification is about 350: 318 offers are fuzzy by design (code never verifies them),
28 sites block bots (HTTP 403/429, which we respect), and many pages simply don't say the claim. We
did not loosen what "supported" means; we report both numbers.
