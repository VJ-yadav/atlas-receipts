"""Probes 1-7 (the organizers') and Probe 8 (ours: claims that carry a receipt)."""
import json
from pathlib import Path

from receipts.claims import enumerate_claims

ROOT = Path(__file__).resolve().parent.parent
WORCESTER_LNG = -71.80


def load_entries(path=ROOT / "data" / "atlas.json"):
    return json.loads(Path(path).read_text())["data"]


def run(entries, receipts=None):
    n = len(entries)
    ids = {e["id"] for e in entries}
    edges = {(e["id"], t) for e in entries for t in e.get("links", []) if t in ids}
    both = sum(1 for a, b in edges if (b, a) in edges) // 2
    funders = [e for e in entries if "funding" in e.get("offers", [])]
    claims = enumerate_claims(entries)
    with_receipt = with_sentence = 0
    if receipts:
        with_receipt = sum(1 for r in receipts if r["status"] == "supported")
        with_sentence = with_receipt + sum(1 for r in receipts if r["status"] == "inferred")
    lines = [
        f"Probe 1 approximate pins          {sum(bool(e.get('approx')) for e in entries)} / {n}",
        f"Probe 2 entries with no links     {sum(not e.get('links') for e in entries)} / {n}"
        f"  ({len(edges)} edges: {len(edges) - 2 * both} one-way, {2 * both} both ways)",
        f"Probe 3 no stages                 {sum(not e.get('stages') for e in entries)} / {n}",
        f"Probe 4 funders with a Check size {sum(any(f[0] == 'Check size' for f in e.get('facts') or []) for e in funders)}"
        f" of {len(funders)}  (applyBy on {sum(bool(e.get('applyBy')) for e in funders)} funders)",
        f"Probe 5 lastVerified 2026-06      {sum(e['lastVerified'] == '2026-06' for e in entries)} / {n}",
        f"Probe 6 west of Worcester         {sum(e['lng'] < WORCESTER_LNG - 0.05 for e in entries)} / {n}",
        "Probe 7 hand time per entry       10-15 min (maintainer's estimate)",
        f"Probe 8 claims with a receipt     {with_receipt} / {len(claims)}  (verified by code)",
        f"        with a sourced sentence   {with_sentence} / {len(claims)}  (adds {with_sentence - with_receipt} model readings, labelled inferred)",
    ]
    by_field = {}
    for c in claims:
        by_field[c["field"]] = by_field.get(c["field"], 0) + 1
    lines.append("        claims by type: " + ", ".join(f"{k} {v}" for k, v in by_field.items()))
    return "\n".join(lines)
