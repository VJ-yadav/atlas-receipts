"""receipts changes: what a re-check sends back to the maintainer.

Compares the previous run (out/receipts.prev.json, saved by every `check`) with the current one.
A claim whose sentence is still on its page needs nobody. Only claims whose sentence vanished, whose
status changed, or that are new come back for review.
"""
import json

from receipts.probes import ROOT

PREV = ROOT / "out" / "receipts.prev.json"
CUR = ROOT / "out" / "receipts.json"


def compare(prev, cur):
    before = {r["key"]: r for r in prev}
    held, back, new = [], [], []
    for r in cur:
        p = before.get(r["key"])
        if not p:
            new.append(r)
        elif p["status"] == r["status"] and p["quote"] == r["quote"]:
            held.append(r)
        else:
            back.append((p, r))
    return held, back, new


def report(prev=None, cur=None):
    prev = prev if prev is not None else json.loads(PREV.read_text())
    cur = cur if cur is not None else json.loads(CUR.read_text())
    held, back, new = compare(prev, cur)
    still = sum(r["status"] == "supported" for r in held)
    print(f"Re-check: {len(cur)} claims. {len(held)} unchanged ({still} still verified by their sentence: nobody needed).")
    print(f"Back to the maintainer: {len(back)} changed, {len(new)} new.")
    for p, r in back[:25]:
        print(f"  {r['key']:<34} {p['status']} → {r['status']}")
        if p["quote"] and p["quote"] != r["quote"]:
            print(f"      was: \"{p['quote'][:90]}\"")
            print(f"      now: " + (f"\"{r['quote'][:90]}\"" if r["quote"] else f"(gone) {r['reason'][:80]}"))
    return held, back, new
