"""receipts metrics: every number we show, computed once, in one place.

compute() reads out/receipts.json and the measured results (planted test, click test, validator,
model usage, page cache) and returns one dict. The console, the public view, `probe`, the goals and
the README/DEMO number blocks all read it; none of them counts on their own.
Written to after/metrics.json (committed) so the numbers in the repo match the pages.
"""
import json
import re
from collections import Counter

from receipts.probes import ROOT, load_entries

STATUSES = ("supported", "contradicted", "silent", "inferred", "refused")
WITH_SENTENCE = ("supported", "inferred", "contradicted")
FIELDS = ("live", "place", "offer", "fact", "link", "deadline")
SHORTLIST = ["glasswing", "venture-guides", "foundersedge", "bcv", "unusual", "milemark", "first-star",
             "two-lanterns", "lama", "companyon", "link-ventures", "techstars"]
OUT = ROOT / "after" / "metrics.json"


def _read(rel, default=""):
    p = ROOT / rel
    return p.read_text() if p.exists() else default


def _counts(rs):
    n = Counter(r["status"] for r in rs)
    return {s: n.get(s, 0) for s in STATUSES}


def _block(rs):
    c = _counts(rs)
    # a sentence from the org's own page that code confirmed is on the saved page
    with_sentence = sum(1 for r in rs if r["status"] in WITH_SENTENCE and r.get("quote"))
    return {"claims": len(rs), **c, "with_sentence": with_sentence,
            "needs_person": c["contradicted"] + c["silent"] + c["inferred"]}


def compute(receipts=None):
    receipts = receipts if receipts is not None else json.loads(_read("out/receipts.json", "[]"))
    entries = load_entries()
    atlas = json.loads(_read("data/atlas.json", "{}") or "{}")
    june = {e["id"] for e in entries if e["lastVerified"] == "2026-06"}
    jr = [r for r in receipts if r["entry_id"] in june]
    cache = ROOT / "cache"
    pages = [json.loads(p.read_text()) for p in cache.glob("*/*.json") if p.parent.name != "_model"] \
        if cache.exists() else []
    from receipts.model import MODEL, usage_report
    usage = usage_report()
    clicks = re.findall(r"^(\d+) / (\d+)$", _read("after/clicktest.txt"), re.M)
    validate = _read("after/validate.txt").strip().splitlines()
    decisions = json.loads(_read("out/decisions.json", "[]") or "[]")
    planted = json.loads(_read("out/planted_score.json", "null") or "null")
    m = {
        "atlas_generated": atlas.get("generated", "")[:16].replace("T", " ") + "Z",
        "checked_at": max((r["fetched_at"] for r in receipts), default="")[:16].replace("T", " ") + "Z",
        "entities": len(entries),
        "all": _block(receipts),
        "by_type": {f: _block([r for r in receipts if r["field"] == f]) for f in FIELDS},
        "contradictions": [{"id": r["entry_id"], "name": r["name"], "field": r["field"], "value": r["value"],
                            "page_value": r["page_value"], "url": r["url"]}
                           for r in receipts if r["status"] == "contradicted"],
        "shortlist": {"ids": SHORTLIST, **_block([r for r in receipts if r["entry_id"] in SHORTLIST])},
        "june": {"entries": len(june), **_block(jr),
                 "live_verified": len({r["entry_id"] for r in jr if r["field"] == "live" and r["status"] == "supported"}),
                 "with_contradiction": len({r["entry_id"] for r in jr if r["status"] == "contradicted"})},
        "blocked_sites": sum(1 for r in receipts if r["field"] == "live" and "blocks automated" in r["reason"]),
        "refused_reasons": dict(Counter(r["reason"] for r in receipts if r["status"] == "refused")),
        "pages_read": sum(1 for p in pages if p.get("text")),
        "model": {"name": MODEL, "calls": usage.get(MODEL, {}).get("calls", 0),
                  "usd": round(usage.get(MODEL, {}).get("usd", 0.0), 3),
                  "usd_all_models": round(sum(v["usd"] for v in usage.values()), 3)},
        "planted": planted,
        "clicks": {"found": int(clicks[-1][0]), "of": int(clicks[-1][1])} if clicks else None,
        "validator": validate[-1] if validate else "not run",
        "decisions": len(decisions),
    }
    return m


def block_text(m):
    """The numbers block shared by README.md and DEMO.md (between the metrics markers)."""
    a, s, j, p = m["all"], m["shortlist"], m["june"], m["planted"] or {}
    return "\n".join([
        f"**Probe 8: claims with a receipt, 0 → {a['supported']} of {a['claims']:,} verified by code.** "
        f"{a['with_sentence']} carry a sentence from the org's own page ({a['inferred']} of them are Claude's "
        f"readings, labelled inferred; {a['contradicted']} are sentences that contradict the Atlas).",
        "",
        "```",
        f"supported {a['supported']} · contradicted {a['contradicted']} · silent {a['silent']} · "
        f"inferred {a['inferred']} · refused {a['refused']}      (checked {m['checked_at']})",
        "```",
        "",
        "| Number | Value |",
        "|---|---|",
        f"| Probe 8: claims verified by code | 0 → **{a['supported']} / {a['claims']:,}** |",
        f"| Claims carrying a sentence from the org's own page | {a['with_sentence']} |",
        f"| Claims that need a person (contradicted, silent, inferred) | {a['needs_person']} |",
        f"| Real contradictions | {a['contradicted']}: " + ", ".join(c["id"] for c in m["contradictions"]) + " |",
        f"| Probe 5: the {j['entries']} entries last checked in June | {j['live_verified']} confirmed live by their own site; "
        f"{j['with_contradiction']} with a contradiction; {j['supported']} of {j['claims']} claims verified |",
        f"| Links with a receipt | {m['by_type']['link']['supported']} / {m['by_type']['link']['claims']} |",
        f"| A founder's 12-funder shortlist | 0 → {s['supported']} / {s['claims']} verified ({s['with_sentence']} with a sentence) |",
        f"| Planted errors: caught / missed / false alarms | {p.get('caught', '–')} / {p.get('missed', '–')} / {p.get('false_alarms', '–')} of {p.get('planted', '–')} |",
        f"| Click test, random receipts | " + (f"{m['clicks']['found']} / {m['clicks']['of']} land on their sentence" if m["clicks"] else "not run") + " |",
        f"| Pages read from the orgs' own sites | {m['pages_read']:,} |",
        f"| Sites that block bots (respected) | {m['blocked_sites']} |",
        f"| Model ({m['model']['name']}): cost of reading all 197 | ${m['model']['usd']:.2f} over {m['model']['calls']} calls |",
        f"| Validator on the Atlas branch | {m['validator']} |",
    ])


def replace_block(path, text):
    if not path.exists():
        return False
    s = path.read_text()
    a, b = "<!-- metrics:start -->", "<!-- metrics:end -->"
    if a not in s or b not in s:
        return False
    path.write_text(s[:s.index(a) + len(a)] + "\n" + text + "\n" + s[s.index(b):])
    return True


def run():
    m = compute()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(m, indent=1))
    text = block_text(m)
    done = [p.name for p in (ROOT / "README.md", ROOT.parent / "DEMO.md") if replace_block(p, text)]
    print(f"wrote {OUT.relative_to(ROOT)}; updated blocks in: {', '.join(done) or 'none'}")
    return m


def load():
    """The last computed metrics (compute fresh if none)."""
    return json.loads(OUT.read_text()) if OUT.exists() else compute()
