"""Claims and receipts: the shared contract.

A claim is one checkable statement in an Atlas entry. A receipt is the result of checking it.
make_receipt() refuses to build a receipt without its provenance, so a source is attached from
the moment a result exists.
"""
from datetime import datetime, timezone

STATUSES = ("supported", "contradicted", "silent", "inferred", "refused")
# Statuses that assert something about the page must carry the exact sentence.
NEEDS_QUOTE = ("supported", "contradicted", "inferred")
# Review order: riskiest first.
FIELD_RISK = {"deadline": 0, "fact": 1, "live": 2, "place": 3, "link": 4, "offer": 5}


def enumerate_claims(entries):
    """Every checkable claim: live, place, offer, fact rows, links, deadline."""
    claims = []
    for e in entries:
        eid = e["id"]

        def add(field, value, i=0):
            claims.append({"key": f"{eid}:{field}:{i}", "entry_id": eid, "name": e["name"],
                           "field": field, "value": value})

        add("live", e["url"])
        add("place", e["loc"])
        for i, o in enumerate(e.get("offers", [])):
            add("offer", o, i)
        for i, (label, val) in enumerate(e.get("facts") or []):
            add("fact", {"label": label, "value": val}, i)
        for i, t in enumerate(e.get("links", [])):
            add("link", t, i)
        if e.get("applyBy"):
            add("deadline", {"applyBy": e["applyBy"], "applyNote": e.get("applyNote", "")})
    return claims


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_receipt(claim, status, *, url, fetched_at, reason, quote=None, sha256=None,
                 page_value=None, searched=None, by="code"):
    """Build a receipt. Raises if provenance is missing.

    url         the page checked (or attempted)
    fetched_at  when that page was fetched (UTC ISO)
    quote       the exact sentence found on the cached page (required for supported,
                contradicted, inferred)
    sha256      hash of the cached page text the quote was checked against
    page_value  what the page says, when it differs (contradicted)
    searched    the URLs looked at, for silent
    by          "code" or "model": a model reading can never be "supported"
    """
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}")
    if not url or not fetched_at:
        raise ValueError(f"{claim['key']}: a receipt needs url and fetched_at")
    if not reason:
        raise ValueError(f"{claim['key']}: a receipt needs a reason")
    if status in NEEDS_QUOTE and not (quote and sha256):
        raise ValueError(f"{claim['key']}: {status} needs a quote and the page sha256")
    if status == "supported" and by != "code":
        raise ValueError(f"{claim['key']}: only code can mark a claim supported")
    return {**claim, "status": status, "url": url, "quote": quote, "fetched_at": fetched_at,
            "sha256": sha256, "reason": reason, "page_value": page_value,
            "searched": searched or [url], "by": by}
