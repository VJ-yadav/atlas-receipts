"""receipts apply <decisions.json>: the only path to entities.yml, and only for rows a person accepted.

Writes to a git worktree on a branch of the Atlas clone (never its main), editing only the lines
that change so the diff stays reviewable, then runs the Atlas's own validator.
"""
import json
import re
import subprocess

from receipts.probes import ROOT

ATLAS = ROOT.parent / "mass-ai-atlas"
BRANCH = "receipts/2026-10-31"
WORKTREE = ROOT / "atlas-branch"
STAMP = "2026-10"
# Which Atlas line a corrected value goes to.
FIELD_LINE = {"deadline": "applyBy", "place": "loc", "live": "url"}


def scalar(v):
    v = str(v)
    if re.fullmatch(r"[A-Za-z0-9][^:#'\"\[\]{},&*!|>%@`]*", v) and not re.fullmatch(r"[\d-]+", v):
        return v
    return "'" + v.replace("'", "''") + "'"


def entry_span(lines, eid):
    start = next(i for i, l in enumerate(lines) if l.rstrip() == f"- id: {eid}")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("- id: ")), len(lines))
    return start, end


def set_field(lines, eid, field, value):
    s, e = entry_span(lines, eid)
    for i in range(s, e):
        if lines[i].startswith(f"  {field}:"):
            lines[i] = f"  {field}: {scalar(value)}\n"
            return
    raise KeyError(f"{eid} has no {field} line")


def set_fact(lines, eid, label, old, new):
    s, e = entry_span(lines, eid)
    for i in range(s, e):
        if lines[i].startswith("  facts:") and f"[{label}, {old}]" in lines[i]:
            lines[i] = lines[i].replace(f"[{label}, {old}]", f"[{label}, {new}]")
            return
    raise KeyError(f"{eid}: fact {label} = {old} not found")


def git(*args, cwd=ATLAS):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


def run(decisions_path):
    decisions = json.loads(open(decisions_path).read())
    receipts = {r["key"]: r for r in json.loads((ROOT / "out" / "receipts.json").read_text())}
    planted = [d["key"] for d in decisions if d["key"].startswith("planted-")]
    if planted:
        raise SystemExit(f"refused: {len(planted)} planted test ids can never be applied ({planted[0]} …)")
    accepted = [d for d in decisions if d.get("decision") == "accept"]
    if not accepted:
        print("nothing accepted: entities.yml untouched")
        return
    if not WORKTREE.exists():
        git("worktree", "add", "-B", BRANCH, str(WORKTREE), "main")
        (WORKTREE / "node_modules").symlink_to(ATLAS / "node_modules")
    path = WORKTREE / "data" / "entities.yml"
    lines = path.read_text().splitlines(keepends=True)
    touched = set()
    for d in accepted:
        r = receipts[d["key"]]
        if "new_value" in d:
            if r["field"] == "fact":
                set_fact(lines, r["entry_id"], r["value"]["label"], r["value"]["value"], d["new_value"])
            elif r["field"] in FIELD_LINE:
                set_field(lines, r["entry_id"], FIELD_LINE[r["field"]], d["new_value"])
            else:
                print(f"skip {d['key']}: {r['field']} edits are proposed in the PR text, not written")
                continue
        touched.add(r["entry_id"])
    for eid in touched:  # a person checked these entries today
        set_field(lines, eid, "lastVerified", STAMP)
    path.write_text("".join(lines))
    v = subprocess.run(["node", "scripts/validate.js"], cwd=WORKTREE, capture_output=True, text=True)
    report = (v.stdout + v.stderr).strip()
    (ROOT / "after").mkdir(exist_ok=True)
    (ROOT / "after" / "validate.txt").write_text(report + "\n")
    print(git("diff", "--stat", cwd=WORKTREE).strip())
    print(report.splitlines()[-1] if report else "validator printed nothing")
    if v.returncode == 0:
        git("commit", "-qam", f"Receipts: {len(accepted)} accepted claims on {len(touched)} entries",
            cwd=WORKTREE)
        print(f"committed on branch {BRANCH} in {WORKTREE.name}/ (not pushed; open a PR by hand)")
    else:
        print("validator FAILED: nothing committed; see after/validate.txt")
