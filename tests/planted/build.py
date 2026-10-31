"""Build tests/planted/entries.json + expected.json from data/atlas.json."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from receipts.claims import enumerate_claims  # noqa: E402
from receipts.probes import load_entries  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
N_REAL = 30


def pick_real(atlas: list[dict]) -> list[dict]:
    """30 real entries: always techstars + Check size / applyBy, then fill."""
    by_id = {e["id"]: e for e in atlas}
    chosen = []
    seen = set()

    def add(eid):
        if eid in by_id and eid not in seen:
            chosen.append(copy.deepcopy(by_id[eid]))
            seen.add(eid)

    add("techstars")
    for e in atlas:
        facts = e.get("facts") or []
        if any(f[0] == "Check size" for f in facts) or e.get("applyBy"):
            add(e["id"])
        if len(chosen) >= N_REAL:
            break
    for e in atlas:
        if len(chosen) >= N_REAL:
            break
        add(e["id"])
    return chosen[:N_REAL]


def fact_index(entry: dict, label: str) -> int:
    for i, (lab, _) in enumerate(entry.get("facts") or []):
        if lab == label:
            return i
    raise KeyError(label)


def plant(real: list[dict], atlas: list[dict]) -> tuple[list[dict], list[dict]]:
    """Return (all entries including planted copies, expected rows)."""
    by_id = {e["id"]: e for e in atlas}
    planted = []
    expected = []

    def add_planted(src_id: str, mutator, expect_rows):
        src = by_id[src_id]
        e = copy.deepcopy(src)
        e["id"] = f"planted-{src_id}"
        mutator(e)
        planted.append(e)
        for row in expect_rows(e):
            expected.append(row)

    # 1) wrong number — techstars Check size $220K → $500K
    def wrong_number(e):
        i = fact_index(e, "Check size")
        e["facts"][i] = ["Check size", "$500K"]

    def wrong_number_expect(e):
        i = fact_index(e, "Check size")
        return [{"key": f"{e['id']}:fact:{i}", "expect": "contradicted", "type": "wrong_number"}]

    add_planted("techstars", wrong_number, wrong_number_expect)

    # 2) wrong place — Boston loc → Worcester
    place_src = next(e for e in real if e.get("loc") == "Boston" and e["id"] != "techstars")
    add_planted(
        place_src["id"],
        lambda e: e.__setitem__("loc", "Worcester"),
        lambda e: [{"key": f"{e['id']}:place:0", "expect": "contradicted", "type": "wrong_place"}],
    )

    # 3) dead url → .invalid (expect contradicted on live)
    dead_src = next(e for e in real if e["id"] not in ("techstars", place_src["id"]))
    add_planted(
        dead_src["id"],
        lambda e: e.__setitem__("url", f"https://planted-{e['id'].removeprefix('planted-')}.invalid"),
        lambda e: [{"key": f"{e['id']}:live:0", "expect": "contradicted", "type": "dead"}],
    )

    # 4) duplicate — same host / near name under planted- id
    dup_src = by_id["techstars"]

    def make_dup(e):
        e["id"] = "planted-dup-techstars"
        e["name"] = "Techstars Boston Accelerator"
        # keep url host identical so find_duplicate matches

    e_dup = copy.deepcopy(dup_src)
    make_dup(e_dup)
    planted.append(e_dup)
    expected.append({
        "key": f"{e_dup['id']}:live:0",
        "expect": "duplicate:techstars",
        "type": "duplicate",
    })

    # 5) out of scope — Providence, RI
    oos_src = next(e for e in real if e["id"] not in (place_src["id"], dead_src["id"], "techstars"))

    def make_oos(e):
        e["loc"] = "Providence, RI"
        e["lat"] = 41.824
        e["lng"] = -71.4128

    add_planted(
        oos_src["id"],
        make_oos,
        lambda e: [{"key": f"{e['id']}:place:0", "expect": "out_of_scope", "type": "out_of_scope"}],
    )

    # 6) unsourced fact — Check size on an entry that has none (site won't support it)
    unsourced_id = next(
        e["id"] for e in atlas
        if not any(f[0] == "Check size" for f in (e.get("facts") or []))
        and e["id"] in {x["id"] for x in real}
    )

    def make_unsourced(e):
        facts = list(e.get("facts") or [])
        facts.append(["Check size", "$999K"])
        e["facts"] = facts

    def unsourced_expect(e):
        i = fact_index(e, "Check size")
        return [{"key": f"{e['id']}:fact:{i}", "expect": "silent", "type": "unsourced_fact"}]

    add_planted(unsourced_id, make_unsourced, unsourced_expect)

    all_entries = real + planted
    # sanity: every expected key that is a claim status should exist in enumerate_claims
    claim_keys = {c["key"] for c in enumerate_claims(planted)}
    for row in expected:
        if row["expect"] in ("supported", "contradicted", "silent", "inferred", "refused"):
            assert row["key"] in claim_keys, row
    return all_entries, expected


def main():
    atlas = load_entries()
    real = pick_real(atlas)
    assert any(e["id"] == "techstars" for e in real)
    assert any(any(f[0] == "Check size" for f in (e.get("facts") or [])) for e in real)
    assert any(e.get("applyBy") for e in real)

    entries, expected = plant(real, atlas)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "entries.json").write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "expected.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    n_planted = sum(1 for e in entries if str(e["id"]).startswith("planted-"))
    print(f"wrote {OUT_DIR / 'entries.json'}: {len(real)} real + {n_planted} planted = {len(entries)}")
    print(f"wrote {OUT_DIR / 'expected.json'}: {len(expected)} expectations")
    for row in expected:
        print(f"  {row['type']}: {row['key']} -> {row['expect']}")


if __name__ == "__main__":
    main()
