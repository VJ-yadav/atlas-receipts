"""receipts propose <new-entry.json>: check a proposed new organization before anyone reads it.

Duplicate of the 197? In Massachusetts? Site answers? Then fetch its own pages and write receipts for
its claims to out/proposed/<id>.json. Never edits entities.yml: a new entry still goes through the
maintainer, as a pull request.
"""
import json

from receipts import check
from receipts.dedupe import find_duplicate, out_of_scope
from receipts.probes import ROOT, load_entries


def run(path):
    e = json.loads(open(path).read())
    e = {"offers": [], "links": [], "facts": [], "stages": [], "tags": [], "lastVerified": "", **e}
    if e["id"].startswith("planted-"):
        raise SystemExit("refused: planted- ids are test data")
    entries = load_entries()
    taken = e["id"] in {x["id"] for x in entries}
    dup = find_duplicate(e, entries)
    oos = out_of_scope(e) if e.get("lat") is not None else False
    https = e["url"].startswith("https://")
    print(f"{e['name']} ({e['id']})")
    print(f"  {'✕' if taken else '✓'} id {'is already taken' if taken else 'is free'}")
    print(f"  {'✕ possible duplicate of ' + dup if dup else '✓ no duplicate among the 197'}")
    print(f"  {'✕ out of scope (not Massachusetts)' if oos else '✓ location reads as in scope'}")
    print(f"  {'✓' if https else '✕'} website {'uses https' if https else 'must use https'}")
    if taken or dup or oos or not https:
        print("  stopped: fix the above before fetching anything")
        return
    out = ROOT / "out" / "proposed" / f"{e['id']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    fresh, _ = check.run(entries=entries + [e], ids=[e["id"]], out=out)
    check.print_entry(fresh)
    print(f"  receipts: {check.summary(fresh)} → {out.relative_to(ROOT)}")
