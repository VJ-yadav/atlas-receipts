"""Score receipts against planted expectations (Lane B)."""
from __future__ import annotations

import json
from pathlib import Path

from receipts.dedupe import find_duplicate, out_of_scope
from receipts.probes import ROOT, load_entries

PLANTED = ROOT / "tests" / "planted"


def _status_caught(receipts_by_key: dict, item: dict) -> bool:
    expect = item["expect"]
    key = item["key"]
    if expect.startswith("duplicate:"):
        return False  # handled via dedupe path
    if expect == "out_of_scope":
        return False
    r = receipts_by_key.get(key)
    return bool(r) and r.get("status") == expect


def score(receipts: list[dict], expected: list[dict], entries: list[dict] | None = None) -> dict:
    """Print planted / caught / missed / false-alarm table; return the numbers."""
    entries = entries or load_entries()
    by_id = {e["id"]: e for e in entries}
    receipts_by_key = {r["key"]: r for r in receipts}

    # expected.json lists only the planted failure cases we care about catching.
    planted_items = list(expected)
    planted_n = len(planted_items)

    # Real (unchanged) entry ids among the planted pack: those without planted- prefix in entries.json
    real_ids = {e["id"] for e in entries if not str(e["id"]).startswith("planted-")}

    caught = []
    missed = []
    for item in planted_items:
        expect = item["expect"]
        key = item["key"]
        eid = key.split(":", 1)[0]
        entry = by_id.get(eid)

        ok = False
        if expect.startswith("duplicate:"):
            want = expect.split(":", 1)[1]
            got = find_duplicate(entry, [e for e in entries if not str(e["id"]).startswith("planted-")]) if entry else None
            # also allow matching against full atlas baseline
            if got is None and entry:
                got = find_duplicate(entry, load_entries())
            ok = got == want or (got is not None and f"duplicate:{got}" == expect)
        elif expect == "out_of_scope":
            ok = bool(entry) and out_of_scope(entry)
        else:
            ok = _status_caught(receipts_by_key, item)

        (caught if ok else missed).append(item)

    false_alarms = [
        r for r in receipts
        if r.get("entry_id") in real_ids and r.get("status") == "contradicted"
        and not str(r.get("entry_id", "")).startswith("planted-")
    ]

    x, y = len(caught), len(missed)
    # precision: caught / (caught + false alarms); recall: caught / planted
    denom_p = x + len(false_alarms)
    precision = (x / denom_p) if denom_p else 0.0
    recall = (x / planted_n) if planted_n else 0.0

    print("planted test score")
    print(f"  planted     {planted_n}")
    print(f"  caught      {x}")
    print(f"  missed      {y}")
    print(f"  false alarm {len(false_alarms)}")
    print(f"  precision   {precision:.3f}")
    print(f"  recall      {recall:.3f}")
    if missed:
        print("  missed detail:")
        for m in missed:
            print(f"    {m['key']} expect={m['expect']} type={m.get('type')}")
    if false_alarms:
        print("  false alarms:")
        for r in false_alarms[:20]:
            print(f"    {r['key']} {r.get('reason', '')[:80]}")

    return {
        "planted": planted_n,
        "caught": x,
        "missed": y,
        "false_alarms": len(false_alarms),
        "precision": precision,
        "recall": recall,
    }


def run(check: bool = False) -> dict:
    """Load planted pack; optionally run receipts.check, then score."""
    entries_path = PLANTED / "entries.json"
    expected_path = PLANTED / "expected.json"
    if not entries_path.exists() or not expected_path.exists():
        raise SystemExit("missing tests/planted/entries.json or expected.json; run: python tests/planted/build.py")

    entries = json.loads(entries_path.read_text(encoding="utf-8"))
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    out = PLANTED / "out.json"

    if check:
        from receipts import check as check_mod
        print("running check on planted entries…")
        fresh, _ = check_mod.run(entries=entries, out=out, workers=8)
        receipts = fresh
    elif out.exists():
        receipts = json.loads(out.read_text(encoding="utf-8"))
        print(f"using cached {out} ({len(receipts)} receipts)")
    else:
        receipts = []
        print(f"no {out.name}; scoring structural checks only "
              f"(duplicate / out_of_scope). Pass --check for full run.")

    return score(receipts, expected, entries=entries)
