"""Duplicate and out-of-scope checks for planted tests and proposed new orgs.

`python -m receipts dedupe` writes a report-only `out/duplicates.json` — it never edits the Atlas.
"""
from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from urllib.parse import urlparse

from receipts.probes import ROOT, load_entries

# Rough Massachusetts bounding box (includes Boston / Worcester / Berkshires).
MA_LAT = (41.20, 42.95)
MA_LNG = (-73.55, -69.85)

# US state names / abbreviations that are not Massachusetts.
NON_MA_STATES = {
    "al", "alabama", "ak", "alaska", "az", "arizona", "ar", "arkansas", "ca", "california",
    "co", "colorado", "ct", "connecticut", "dc", "de", "delaware", "fl", "florida", "ga",
    "georgia", "hi", "hawaii", "id", "idaho", "il", "illinois", "in", "indiana", "ia", "iowa",
    "ks", "kansas", "ky", "kentucky", "la", "louisiana", "me", "maine", "md", "maryland",
    "mi", "michigan", "mn", "minnesota", "ms", "mississippi", "mo", "missouri", "mt", "montana",
    "ne", "nebraska", "nv", "nevada", "nh", "new hampshire", "nj", "new jersey", "nm",
    "new mexico", "ny", "new york", "nc", "north carolina", "nd", "north dakota", "oh", "ohio",
    "ok", "oklahoma", "or", "oregon", "pa", "pennsylvania", "ri", "rhode island", "sc",
    "south carolina", "sd", "south dakota", "tn", "tennessee", "tx", "texas", "ut", "utah",
    "vt", "vermont", "va", "virginia", "wa", "washington", "wv", "west virginia", "wi",
    "wisconsin", "wy", "wyoming",
}
MA_TOKENS = {"ma", "mass", "massachusetts"}


def norm_name(name: str) -> str:
    s = (name or "").lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\b(the|inc|llc|ltd|corp|corporation|co)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def host_of(url: str) -> str:
    try:
        host = urlparse(url or "").hostname or ""
    except ValueError:
        return ""
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def find_duplicate(entry: dict, entries: list[dict], threshold: float = 0.85):
    """Return the matching entry id if name similarity ≥ threshold or same url host, else None."""
    name = norm_name(entry.get("name", ""))
    host = host_of(entry.get("url", ""))
    eid = entry.get("id")
    best = None
    best_score = -1.0
    for other in entries:
        oid = other.get("id")
        if not oid or oid == eid:
            continue
        score = SequenceMatcher(None, name, norm_name(other.get("name", ""))).ratio() if name else 0.0
        same_host = bool(host) and host == host_of(other.get("url", ""))
        if not same_host and score < threshold:
            continue
        effective = max(score, 1.0 if same_host else 0.0)
        if effective > best_score:
            best = oid
            best_score = effective
    return best


def _loc_tokens(loc: str) -> set[str]:
    parts = re.split(r"[,;/|·]+", (loc or "").lower())
    tokens = set()
    for p in parts:
        p = p.strip()
        if not p:
            continue
        tokens.add(p)
        tokens.update(p.split())
    return tokens


def out_of_scope(entry: dict) -> bool:
    """True if loc names a non-MA state, or lat/lng falls outside Massachusetts."""
    tokens = _loc_tokens(entry.get("loc", ""))
    if tokens & NON_MA_STATES and not (tokens & MA_TOKENS):
        return True
    lat, lng = entry.get("lat"), entry.get("lng")
    if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
        if not (MA_LAT[0] <= lat <= MA_LAT[1] and MA_LNG[0] <= lng <= MA_LNG[1]):
            return True
    return False


def report(out_path=None):
    """Scan the Atlas for near-duplicate pairs; write out/duplicates.json (report only)."""
    entries = load_entries()
    pairs = []
    seen = set()
    for e in entries:
        other = find_duplicate(e, entries)
        if not other:
            continue
        a, b = sorted([e["id"], other])
        if (a, b) in seen:
            continue
        seen.add((a, b))
        left = next(x for x in entries if x["id"] == a)
        right = next(x for x in entries if x["id"] == b)
        pairs.append({
            "a": a, "b": b,
            "a_name": left.get("name"), "b_name": right.get("name"),
            "a_host": host_of(left.get("url", "")), "b_host": host_of(right.get("url", "")),
            "name_ratio": round(SequenceMatcher(None, norm_name(left.get("name", "")),
                                                norm_name(right.get("name", ""))).ratio(), 3),
            "same_host": host_of(left.get("url", "")) == host_of(right.get("url", "")),
        })
    out_path = out_path or (ROOT / "out" / "duplicates.json")
    out_path.parent.mkdir(exist_ok=True)
    payload = {"count": len(pairs), "pairs": pairs}
    out_path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"duplicates: {len(pairs)} pair(s) -> {out_path}")
    return payload
