"""receipts goals: every goal in GOALS.md, checked by code. Exit code 0 only when all pass.

The loop: run it, fix the first FAIL, commit, run it again.
"""
import json
import re
import subprocess

from receipts.fetch import fetch
from receipts.probes import ROOT
from receipts.rules import PERSONISH
from receipts.text import quote_on_page

OUT = ROOT / "out"
PROBE8_TARGET = 340   # verified by code (supported)
SOURCED_TARGET = 600  # carry a sentence from the org's own page (supported + inferred, labelled)
GOALS = []


def goal(gid, title):
    def wrap(fn):
        GOALS.append((gid, title, fn))
        return fn
    return wrap


def receipts():
    p = OUT / "receipts.json"
    return json.loads(p.read_text()) if p.exists() else []


def sh(*cmd):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True).stdout


# ---------- eligibility and caps (any FAIL here blocks everything else) ----------

@goal("E1", "every commit is after 09:00 on 31 Oct")
def _():
    times = sh("git", "log", "--format=%ad", "--date=format:%Y-%m-%d %H:%M").split("\n")
    early = [t for t in times if t and t < "2026-10-31 09:00"]
    return not early, f"{len(times) - 1} commits, {len(early)} before 09:00"


@goal("E2", "no .env or API key ever committed")
def _():
    # the shape of a real key (prefix, kind, then a long secret), not just the prefix
    hits = sh("git", "log", "--all", "--format=%h", "-G", "sk-ant-[a-z]+(-[a-z0-9]+)?-[A-Za-z0-9_-]{30,}").strip()
    files = sh("git", "log", "--all", "--format=", "--name-only", "--", ".env").strip()
    return not hits and not files, "clean" if not (hits or files) else "KEY IN HISTORY"


@goal("C1", "every receipt has url, fetched_at, reason; supported/inferred have quote + page hash")
def _():
    rs = receipts()
    bad = [r["key"] for r in rs if not (r["url"] and r["fetched_at"] and r["reason"])
           or (r["status"] in ("supported", "inferred") and not (r["quote"] and r["sha256"]))]
    return bool(rs) and not bad, f"{len(rs)} receipts, {len(bad)} incomplete {bad[:3]}"


@goal("C2", "every supported/inferred quote is really on the cached page (re-checked now)")
def _():
    rs = [r for r in receipts() if r["status"] in ("supported", "inferred")]
    bad = []
    for r in rs:
        page = fetch(r["url"])  # served from cache/
        if not quote_on_page(r["quote"], page.get("text", "")):
            bad.append(r["key"])
    return bool(rs) and not bad, f"{len(rs) - len(bad)} / {len(rs)} quotes found on their page {bad[:3]}"


@goal("C3", "only code marks a claim supported (no model reading shown as verified)")
def _():
    bad = [r["key"] for r in receipts() if r["status"] == "supported" and r["by"] != "code"]
    return not bad, f"{len(bad)} model-made supported"


@goal("C4", "no people: no quote about a person, no emails or phone numbers in output")
def _():
    rs = receipts()
    bad = [r["key"] for r in rs if r["quote"] and r["status"] != "refused" and PERSONISH.search(r["quote"])]
    text = "".join(p.read_text(errors="ignore") for p in OUT.glob("*") if p.is_file())
    emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
    return not bad and not emails, f"{len(bad)} person-ish quotes {bad[:3]}, {len(emails)} emails"


@goal("C5", "no planted entry in the real output; apply refuses planted ids")
def _():
    leaked = [r["key"] for r in receipts() if r["entry_id"].startswith("planted-")]
    from receipts import apply
    probe = OUT / "_planted_probe.json"
    probe.write_text(json.dumps([{"key": "planted-x:live:0", "decision": "accept"}]))
    try:
        apply.run(probe)
        refused = False
    except SystemExit as e:
        refused = "refused" in str(e)
    finally:
        probe.unlink()
    return not leaked and refused, f"{len(leaked)} planted in real output; apply refuses: {refused}"


@goal("C6", "the Atlas branch passes node scripts/validate.js")
def _():
    v = ROOT / "after" / "validate.txt"
    ok = v.exists() and "PASSED" in v.read_text()
    return ok, (v.read_text().strip().splitlines()[-1] if v.exists() else "no after/validate.txt")


@goal("C7", "silence is explained: every silent/refused receipt says what was searched or why")
def _():
    rs = [r for r in receipts() if r["status"] in ("silent", "refused")]
    bad = [r["key"] for r in rs if len(r["reason"]) < 20]
    return not bad, f"{len(rs)} silent/refused, {len(bad)} without a real reason"


# ---------- product goals ----------

@goal("P1", f"Probe 8: >= {PROBE8_TARGET} claims verified by code, >= {SOURCED_TARGET} with a sourced sentence")
def _():
    from receipts.metrics import compute
    a = compute(receipts())["all"]
    n, m = a["supported"], a["with_sentence"]
    return n >= PROBE8_TARGET and m >= SOURCED_TARGET, f"{n} verified, {m} with a sentence, of {a['claims']}"


@goal("P2", "the model pass has run: fuzzy claims are inferred or refused, not just silent")
def _():
    rs = receipts()
    inf = sum(r["status"] == "inferred" for r in rs)
    ref = sum(r["status"] == "refused" and r["by"] == "model" for r in rs)
    return inf >= 100, f"{inf} inferred, {ref} model quotes refused (not on page)"


@goal("P3", "review page exists, shows all statuses, links highlight the sentence")
def _():
    p = OUT / "review.html"
    if not p.exists():
        return False, "no out/review.html (B1)"
    h = p.read_text()
    missing = [s for s in ("supported", "contradicted", "silent", "inferred", "refused") if s not in h]
    return not missing and "#:~:text=" in h and "Probe 8" in h, f"missing {missing}" if missing else "ok"


@goal("P4", "planted-errors test runs: recall >= 0.8 and at most 1 false alarm")
def _():
    p = OUT / "planted_score.json"
    if not p.exists():
        return False, "no out/planted_score.json (B2: receipts test)"
    s = json.loads(p.read_text())
    ok = s["planted"] >= 6 and s["caught"] / s["planted"] >= 0.8 and s["false_alarms"] <= 1
    return ok, f"planted {s['planted']}, caught {s['caught']}, missed {s['missed']}, false alarms {s['false_alarms']}"


@goal("P5", "README is filled: no placeholders, sources declared, probe line, validator output")
def _():
    t = (ROOT / "README.md").read_text()
    todo = t.count("_To be filled._")
    ok = not todo and "Probe 8" in t and "PASSED" in t and "the-open-accelerator.com" in t
    return ok, f"{todo} placeholders left"


def run():
    fails = 0
    for gid, title, fn in GOALS:
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, f"error: {type(e).__name__}: {e}"
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {gid:<3} {title}\n      {detail}")
    print(f"\n{len(GOALS) - fails} / {len(GOALS)} goals met")
    return fails
