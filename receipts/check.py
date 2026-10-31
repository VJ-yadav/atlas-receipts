"""receipts check [--all|<id>...] [--refresh]: one receipt per claim → out/receipts.json."""
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from receipts import model
from receipts.claims import enumerate_claims
from receipts.fetch import client
from receipts.pages import pages_for
from receipts.probes import ROOT, load_entries
from receipts.rules import check_entry

OUT = ROOT / "out" / "receipts.json"


def check_one(entry, claims, by_id, refresh=False, use_model=False):
    with client() as c:
        pages = pages_for(entry, c, refresh)
    receipts = check_entry(entry, claims, pages, by_id)
    if use_model:
        try:
            receipts = model.upgrade(receipts, pages)
        except Exception as e:  # the model is optional: claims stay silent, with the reason logged
            print(f"  model skipped for {entry['id']}: {type(e).__name__}: {str(e)[:120]}")
    return receipts


def run(ids=None, refresh=False, entries=None, out=OUT, workers=16, use_model=False):
    entries = entries or load_entries()
    by_id = {e["id"]: e for e in entries}
    todo = [by_id[i] for i in ids] if ids else entries
    claims = enumerate_claims(todo)
    per = {}
    for c in claims:
        per.setdefault(c["entry_id"], []).append(c)
    with ThreadPoolExecutor(workers) as pool:
        results = list(pool.map(lambda e: check_one(e, per[e["id"]], by_id, refresh, use_model), todo))
    fresh = [r for rs in results for r in rs]
    keep = []
    if ids and out.exists():
        done = set(ids)
        keep = [r for r in json.loads(out.read_text()) if r["entry_id"] not in done]
    allr = keep + fresh
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(allr, indent=1))
    return fresh, allr


def summary(receipts):
    n = Counter(r["status"] for r in receipts)
    return " · ".join(f"{s} {n[s]}" for s in ("supported", "contradicted", "silent", "inferred", "refused"))


def print_entry(receipts):
    for r in receipts:
        v = r["value"] if not isinstance(r["value"], dict) else " ".join(str(x) for x in r["value"].values())
        q = f'"{r["quote"][:90]}"' if r["quote"] else r["reason"][:90]
        print(f"  {r['status']:<12} {r['field']:<8} {str(v)[:34]:<34} {q}")
