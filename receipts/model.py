"""The model reads a few candidate sentences for fuzzy claims; code decides what the reading is worth.

Cost-efficient by design:
- Code picks the candidate sentences (keyword overlap with the claim), so the model sees about
  30 short sentences per organization, not whole pages.
- The model answers with a sentence number, never with text, so it cannot invent a quote.
- A small model (Claude Haiku 5.5) by default. RECEIPTS_MODEL overrides it.
- One call per organization, only for its silent offer/fact claims, cached on disk by the candidate
  sentences; every call's tokens and cost are logged to cache/_usage.jsonl.

A reading is "inferred" (never "supported"); the sentence is still re-checked on the cached page.
"""
import hashlib
import json
import os
import re

from receipts.claims import make_receipt, now_iso
from receipts.fetch import CACHE
from receipts.rules import OFFER_WORDS, PERSONISH, units, usable
from receipts.text import quote_on_page

MODEL = os.environ.get("RECEIPTS_MODEL", "claude-haiku-5-5")
PRICE = {"claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.0, 10.0), "claude-opus-5-5": (4.0, 20.0)}
FUZZY = ("offer", "fact")
PER_CLAIM, PER_ENTRY = 6, 40
STOP = {"with", "from", "that", "this", "their", "about", "plus", "into", "through", "only", "most"}
SYSTEM = (
    "You help check claims a public directory makes about an organization. You get numbered sentences "
    "taken from the organization's own website, and a list of claims. For each claim, give the number of "
    "the ONE sentence that bears on it most directly, or 0 if none does, and say whether that sentence "
    "supports the claim, contradicts it, or is only related. Keep 'why' under 20 words. Ignore people's "
    "names and contact details."
)
SCHEMA = {
    "type": "object",
    "properties": {"answers": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "key": {"type": "string"},
            "sentence": {"type": "integer"},
            "reading": {"type": "string", "enum": ["supports", "contradicts", "related", "none"]},
            "why": {"type": "string"},
        },
        "required": ["key", "sentence", "reading", "why"],
        "additionalProperties": False,
    }}},
    "required": ["answers"],
    "additionalProperties": False,
}


def available():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def claim_terms(c):
    if c["field"] == "offer":
        return re.compile(r"\b(" + OFFER_WORDS.get(c["value"], re.escape(c["value"])) + r")", re.I)
    v = c["value"]
    words = [w for w in re.findall(r"[a-z0-9$%]{4,}", f"{v['label']} {v['value']}".lower()) if w not in STOP]
    return re.compile(r"\b(" + "|".join(map(re.escape, words or [v["label"].lower()])) + r")", re.I)


def candidates(claims, pages):
    """The few sentences on the org's own pages that could bear on these claims, numbered from 1."""
    pool = []
    for i, p in enumerate(pages):
        for s in units(p):
            if 20 < len(s) < 320 and not PERSONISH.search(s) and (i, s) not in pool:
                pool.append((i, s))
    chosen = []
    for c in claims:
        pat = claim_terms(c)
        hits = sorted((-len(pat.findall(s)), len(s), (i, s)) for i, s in pool if pat.search(s))
        for _, _, item in hits[:PER_CLAIM]:
            if item not in chosen:
                chosen.append(item)
    return chosen[:PER_ENTRY]


def log_usage(resp, n_claims):
    u = resp.usage
    pin, pout = PRICE.get(MODEL, (0, 0))
    cost = (u.input_tokens * pin + u.output_tokens * pout) / 1e6
    with open(CACHE / "_usage.jsonl", "a") as f:
        f.write(json.dumps({"at": now_iso(), "model": MODEL, "in": u.input_tokens, "out": u.output_tokens,
                            "claims": n_claims, "usd": round(cost, 5)}) + "\n")


def _ask(claims, sents):
    import anthropic
    listing = "\n".join(f"[{n}] {s}" for n, (_, s) in enumerate(sents, 1))
    asks = "\n".join(f"- key={c['key']}: {c['field']} = {json.dumps(c['value'])}" for c in claims)
    resp = anthropic.Anthropic().messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": f"Sentences from {claims[0]['name']}'s own website:\n{listing}"
                                              f"\n\nClaims:\n{asks}"}],
    )
    log_usage(resp, len(claims))
    if resp.stop_reason == "refusal":
        return []
    return json.loads(next(b.text for b in resp.content if b.type == "text"))["answers"]


def suggest(claims, sents):
    sig = hashlib.sha256(json.dumps([sents, [c["key"] for c in claims], MODEL]).encode()).hexdigest()[:20]
    path = CACHE / "_model" / f"{sig}.json"
    if path.exists():
        return json.loads(path.read_text())
    answers = _ask(claims, sents)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(answers))
    return answers


def upgrade(receipts, pages):
    """Replace silent offer/fact receipts with a model reading of a code-chosen, code-checked sentence."""
    todo = [r for r in receipts if r["status"] == "silent" and r["field"] in FUZZY]
    pages = usable(pages)
    if not todo or not pages or not available():
        return receipts
    sents = candidates(todo, pages)
    if not sents:
        return receipts
    by_key = {a["key"]: a for a in suggest(todo, sents)}
    out = []
    for r in receipts:
        a = by_key.get(r["key"])
        n = a["sentence"] if a else 0
        if r not in todo or not a or a["reading"] == "none" or not 1 <= n <= len(sents):
            out.append(r)
            continue
        i, quote = sents[n - 1]
        page = pages[i]
        claim = {k: r[k] for k in ("key", "entry_id", "name", "field", "value")}
        if not quote_on_page(quote, page["text"]):  # cannot happen by construction; checked anyway
            out.append(make_receipt(claim, "refused", url=page["final_url"], fetched_at=page["fetched_at"],
                                    quote=quote, by="model", reason="the chosen sentence is not on the page"))
            continue
        out.append(make_receipt(claim, "inferred", url=page["final_url"], fetched_at=page["fetched_at"],
                                quote=quote, sha256=page["sha256"], by="model", page_value=a["reading"],
                                reason=f"model reading ({a['reading']}): " + re.sub(r"\b[Ss]entence \d+\s*", "The sentence ", a["why"])[:200]))
    return out


def usage_report():
    p = CACHE / "_usage.jsonl"
    rows = [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []
    by = {}
    for r in rows:
        m = by.setdefault(r["model"], {"calls": 0, "in": 0, "out": 0, "usd": 0.0, "claims": 0})
        for k in ("in", "out", "usd", "claims"):
            m[k] += r[k]
        m["calls"] += 1
    return by
