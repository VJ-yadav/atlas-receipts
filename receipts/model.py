"""The model suggests a sentence for fuzzy claims; code decides what that suggestion is worth.

- the suggested quote is not on the cached page  → refused (the model's text is kept as evidence)
- the quote is on the page                      → inferred (a reading, never "supported")
One call per entry, only for its silent offer/fact claims, cached on disk by page hashes.
"""
import hashlib
import json
import os

from receipts.claims import make_receipt
from receipts.fetch import CACHE
from receipts.text import quote_on_page

MODEL = os.environ.get("RECEIPTS_MODEL", "claude-opus-5-5")
FUZZY = ("offer", "fact")
SYSTEM = (
    "You help verify claims a public directory makes about an organization, using only the "
    "organization's own web pages given to you. For each claim, copy ONE sentence verbatim from "
    "the pages that bears on it, character for character, or return an empty quote if no "
    "sentence does. Never paraphrase or combine sentences: your quote is checked by exact string "
    "match and rejected if it is not on the page. Say whether the sentence supports the claim, "
    "contradicts it, or is only related. Ignore people's names and contact details."
)
SCHEMA = {
    "type": "object",
    "properties": {"answers": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "key": {"type": "string"},
            "page": {"type": "integer"},
            "quote": {"type": "string"},
            "reading": {"type": "string", "enum": ["supports", "contradicts", "related", "none"]},
            "why": {"type": "string"},
        },
        "required": ["key", "page", "quote", "reading", "why"],
        "additionalProperties": False,
    }}},
    "required": ["answers"],
    "additionalProperties": False,
}


def available():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _ask(claims, pages):
    import anthropic
    docs = "\n\n".join(f"<page index=\"{i}\" url=\"{p['final_url']}\">\n{p['text']}\n</page>"
                       for i, p in enumerate(pages))
    asks = "\n".join(f"- key={c['key']}: {c['field']} = {json.dumps(c['value'])}" for c in claims)
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": f"{docs}\n\nClaims about {claims[0]['name']}:\n{asks}"}],
    )
    if resp.stop_reason == "refusal":
        return []
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text)["answers"]


def suggest(claims, pages):
    """Model answers for these claims, cached by the page hashes and claim keys."""
    sig = hashlib.sha256(json.dumps([[p["sha256"] for p in pages], [c["key"] for c in claims],
                                     MODEL]).encode()).hexdigest()[:20]
    path = CACHE / "_model" / f"{sig}.json"
    if path.exists():
        return json.loads(path.read_text())
    answers = _ask(claims, pages)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(answers))
    return answers


def upgrade(receipts, pages):
    """Replace silent offer/fact receipts with model-suggested, code-checked ones."""
    todo = [r for r in receipts if r["status"] == "silent" and r["field"] in FUZZY]
    pages = [p for p in pages if p.get("text")]
    if not todo or not pages or not available():
        return receipts
    by_key = {a["key"]: a for a in suggest(todo, pages)}
    out = []
    for r in receipts:
        a = by_key.get(r["key"])
        if r not in todo or not a or a["reading"] == "none" or not a["quote"].strip():
            out.append(r)
            continue
        claim = {k: r[k] for k in ("key", "entry_id", "name", "field", "value")}
        page = pages[a["page"]] if 0 <= a["page"] < len(pages) else pages[0]
        if not quote_on_page(a["quote"], page["text"]):
            out.append(make_receipt(claim, "refused", url=page["final_url"], fetched_at=page["fetched_at"],
                                    quote=a["quote"], by="model",
                                    reason="the model offered a sentence that is not on the page"))
        else:
            out.append(make_receipt(claim, "inferred", url=page["final_url"], fetched_at=page["fetched_at"],
                                    quote=a["quote"], sha256=page["sha256"], by="model",
                                    page_value=a["reading"],
                                    reason=f"model reading ({a['reading']}): {a['why'][:200]}"))
    return out
