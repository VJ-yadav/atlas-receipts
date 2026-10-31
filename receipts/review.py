"""receipts review: out/receipts.json → out/review.html, the maintainer console.

One static file, no framework, opens from disk. Home (what this is, where things stand), an entity
grid with a detail panel, the review queue, the refused list, and a form to draft a new entity.
A Before / After switch shows the same views as the Atlas today and with receipts.
Accept / Reject per claim, then "Download decisions.json" for `receipts apply`.
"""
import json
import os
from collections import Counter

from receipts.claims import FIELD_RISK
from receipts.probes import ROOT, load_entries
from receipts.text import highlight_url

# A founder's shortlist (pre-seed, AI infrastructure): funders whose Atlas focus fits.
SHORTLIST = ["glasswing", "venture-guides", "foundersedge", "bcv", "unusual", "milemark", "first-star",
             "two-lanterns", "lama", "companyon", "link-ventures", "techstars"]
STATUS_ORDER = {"contradicted": 0, "refused": 1, "silent": 2, "inferred": 3, "supported": 4}


LOOKED_FOR = {
    "live": "real content, not an error page or a parked domain",
    "place": "the town or street address from the Atlas",
    "deadline": "the deadline date, or wording that applications are rolling, open or closed",
    "fact": "the same amount or number, in a sentence about the program or its checks",
    "link": "the other organization's name, on either organization's own pages",
    "offer": "a sentence about this offer (offers need a reading, so code never verifies them)",
}


def trace(r):
    """The steps behind a status, in order: what was fetched, found, checked, compared, decided."""
    host = r["url"].split("/")[2] if "://" in r["url"] else r["url"]
    when = r["fetched_at"][:16].replace("T", " ") + "Z"
    pages = len(r["searched"] or [r["url"]])
    st, by, quote = r["status"], r["by"], r["quote"]
    steps = []
    if st == "refused" and by == "code":
        steps.append(("stop", "Not fetched", r["reason"]))
        steps.append(("wait", "Nothing to decide", "No page was collected, so there is no evidence either way."))
        return steps
    steps.append(("ok", "Fetched", f"{host} at {when}, {pages} page{'s' if pages != 1 else ''} searched, kept in the local cache"))
    steps.append(("ok", "Looked for", LOOKED_FOR.get(r["field"], "a matching sentence")))
    if by == "model":
        steps.append(("warn", "Suggested by Claude", "Code found no exact match, so Claude was asked to point at one sentence on these pages."))
    if quote:
        if st == "refused":
            steps.append(("stop", "Checked by code", "The suggested sentence is not on the cached page. It is discarded and shown here only as evidence."))
        else:
            steps.append(("ok", "Checked by code", f"Exact text match on the cached page (page hash {(r['sha256'] or '')[:10]})."))
    elif st == "silent":
        steps.append(("warn", "Nothing matched", r["reason"]))
    if st == "supported":
        steps.append(("ok", "Compared", r["reason"]))
    elif st == "contradicted":
        steps.append(("stop", "Compared", r["reason"] + (f" Page: {r['page_value']}." if r["page_value"] else "")))
    elif st == "inferred":
        steps.append(("warn", "Read, not verified", r["reason"].replace("model reading", "Claude's reading", 1)
                      + " A reading is not proof, so this stays inferred."))
    if r["entry_id"].startswith("planted-"):
        steps.append(("stop", "Test data", "Planted test copy. It can never be applied."))
    else:
        steps.append(("wait", "Your decision", "Nothing is written to the Atlas until a maintainer accepts it."))
    return steps


def rows(receipts, entries):
    meta = {e["id"]: e for e in entries}
    out = []
    for r in receipts:
        e = meta.get(r["entry_id"], {})
        v = r["value"]
        if isinstance(v, dict):
            v = " · ".join(str(x) for x in v.values() if x)
        out.append({
            "key": r["key"], "id": r["entry_id"], "name": r["name"], "field": r["field"],
            "value": str(v), "status": r["status"], "quote": r["quote"],
            "reason": r["reason"].replace("model reading", "Claude's reading").replace(" — ", ", "),
            "page_value": r["page_value"], "url": r["url"],
            "link": highlight_url(r["url"], r["quote"]) if r["quote"] else r["url"],
            "fetched": r["fetched_at"][:16].replace("T", " ") + "Z", "searched": r["searched"],
            "by": r["by"], "cat": e.get("cat", ""), "lastVerified": e.get("lastVerified", ""),
            "planted": r["entry_id"].startswith("planted-"),
            "trace": trace(r),
        })
    out.sort(key=lambda x: (x["id"], STATUS_ORDER[x["status"]], FIELD_RISK.get(x["field"], 9)))
    return out



def meta(receipts, entries):
    """Context for the Home page: the database, the pipeline, the measurements."""
    def read(path, default=None):
        p = ROOT / path
        return p.read_text() if p.exists() else default
    atlas = json.loads((ROOT / "data" / "atlas.json").read_text())
    score = json.loads(read("out/planted_score.json", "null") or "null")
    validate = (read("after/validate.txt", "") or "").strip().splitlines()
    clicks = (read("after/clicktest.txt", "") or "").strip().splitlines()
    by_type = Counter(r["field"] for r in receipts)
    sup_type = Counter(r["field"] for r in receipts if r["status"] == "supported")
    cache = ROOT / "cache"
    pages = sum(1 for p in cache.rglob("*.json") if "_model" not in p.parts) if cache.exists() else 0
    calls = len(list((cache / "_model").glob("*.json"))) if (cache / "_model").exists() else 0
    return {
        "atlas_generated": atlas.get("generated", "")[:16].replace("T", " ") + "Z",
        "cats": {k: v["label"] for k, v in atlas.get("cats", {}).items()},
        "june": sum(e["lastVerified"] == "2026-06" for e in entries),
        "by_type": dict(by_type), "sup_type": dict(sup_type),
        "pages": pages, "model_calls": calls, "model": os.environ.get("RECEIPTS_MODEL", "claude-opus-5-5"),
        "validator": validate[-1] if validate else "not run",
        "score": score, "clicks": clicks[-1] if clicks else "",
    }


def build(receipts, out_path, entries=None, title="Atlas Receipts"):
    entries = entries if entries is not None else load_entries()
    data = rows(receipts, entries)
    n = Counter(r["status"] for r in receipts)
    sl = [r for r in receipts if r["entry_id"] in SHORTLIST]
    head = {"total": len(receipts), "counts": dict(n), "title": title, "shortlist": SHORTLIST,
            "sl_total": len(sl), "sl_supported": sum(r["status"] == "supported" for r in sl),
            "sl_sentence": sum(r["status"] in ("supported", "inferred") for r in sl),
            "generated": max((r["fetched_at"] for r in receipts), default="")[:16].replace("T", " ") + "Z"}
    ents = [{k: e.get(k) for k in ("id", "name", "cat", "loc", "url", "lastVerified", "added", "approx",
                                    "offers", "links", "applyBy", "desc")} for e in entries]
    blob = json.dumps({"head": head, "meta": meta(receipts, entries), "entities": ents, "rows": data})
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(PAGE.replace("/*DATA*/", blob.replace("</", "<\\/")))
    return out_path


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Atlas Receipts</title>
<style>
:root{--bg:#fff;--side:#f9f9fa;--muted:#f4f5f7;--ink:#1c1d21;--mute:#5d6270;--faint:#6e7380;--line:#e3e5e9;--hair:#eceef1;
--acc:#16a34a;--acc-strong:#15803d;--acc-soft:#e8f7ee;--warn:#a35200;--warn-soft:#fff4e0;--bad:#c62828;--bad-soft:#fdecec;
--info:#1f5fbf;--info-soft:#eaf2ff;--test:#b4410c;--test-soft:#fdf0e8;
--sans:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;--mono:"JetBrains Mono","SF Mono",Menlo,monospace;
--shadow:0 1px 2px 0 rgb(16 17 20/.05),0 1px 1px 0 rgb(16 17 20/.03);--shadow-lg:0 12px 32px -8px rgb(16 17 20/.18),0 2px 6px rgb(16 17 20/.06)}
:root[data-theme=dark]{--bg:#131417;--side:#16171a;--muted:#212227;--ink:#ececef;--mute:#a6abb6;--faint:#8e939e;--line:#2c2e34;--hair:#24262b;
--acc:#4ade80;--acc-strong:#22c55e;--acc-soft:#15291d;--warn:#fbbf24;--warn-soft:#2e2410;--bad:#f87171;--bad-soft:#331616;
--info:#8fb8ff;--info-soft:#16223a;--test:#fb923c;--test-soft:#331a0c}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.55 var(--sans);-webkit-font-smoothing:antialiased}
a{color:var(--info);text-decoration:none}a:hover{text-decoration:underline}
button{font:inherit;color:inherit}
.mono{font-family:var(--mono);font-size:12px}
/* top bar */
.bar{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--bg) 94%,transparent);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.bar-in{max-width:1240px;margin:0 auto;padding:10px 24px;display:flex;align-items:center;gap:18px;flex-wrap:wrap}
.brand{font-weight:650;font-size:15px;display:flex;gap:8px;align-items:center;white-space:nowrap}
.brand i{width:9px;height:9px;border-radius:50%;background:var(--acc)}
.admin{font-size:11.5px;font-weight:600;color:var(--warn);background:var(--warn-soft);border-radius:999px;padding:2px 9px;white-space:nowrap}
nav.tabs{display:flex;gap:2px;flex-wrap:wrap}
nav.tabs a{color:var(--mute);padding:6px 11px;border-radius:8px;font-weight:500}
nav.tabs a:hover{background:var(--muted);color:var(--ink);text-decoration:none}
nav.tabs a.on{color:var(--ink);background:var(--muted);font-weight:600}
.grow{flex:1}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:9px;padding:2px;background:var(--muted)}
.seg button{border:0;background:none;padding:5px 12px;border-radius:7px;cursor:pointer;color:var(--mute);font-size:13px;font-weight:500}
.seg button.on{background:var(--bg);color:var(--ink);box-shadow:var(--shadow);font-weight:600}
.iconbtn{border:1px solid var(--line);background:var(--bg);border-radius:8px;padding:5px 9px;cursor:pointer;font-size:12.5px;color:var(--mute)}
.wrap{max-width:1240px;margin:0 auto;padding:24px}
section.view{display:none}section.view.on{display:block}
h1{font-size:28px;line-height:1.2;margin:8px 0 10px;letter-spacing:-.01em}
h2{font-size:18px;margin:34px 0 12px}h3{font-size:15px;margin:0 0 6px}
.lead{font-size:16px;color:var(--mute);max-width:760px;margin:0 0 18px}
.note{font-size:12.5px;color:var(--faint)}
.mode-note{display:flex;gap:10px;align-items:center;border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:0 0 18px;background:var(--side);font-size:13px;color:var(--mute)}
.mode-note b{color:var(--ink)}
/* tiles */
.tiles{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.tile{border:1px solid var(--line);border-radius:12px;padding:14px 16px;box-shadow:var(--shadow);background:var(--bg)}
.tile .k{font-size:12.5px;color:var(--mute)}.tile .v{font-size:28px;font-weight:650;font-variant-numeric:tabular-nums;line-height:1.25}
.tile .v small{font-size:13px;color:var(--faint);font-weight:400}.tile .s{font-size:12.5px;color:var(--faint);margin-top:2px}
.tile.big .v{color:var(--acc-strong)}.tile.before .v{color:var(--ink)}
/* flow */
.flow{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;counter-reset:s}
.step{border:1px solid var(--line);border-radius:12px;padding:14px 16px;position:relative;background:var(--bg)}
.step .n{font:600 12px var(--mono);color:var(--bg);background:var(--ink);border-radius:6px;padding:1px 7px;display:inline-block;margin-bottom:8px}
.step p{margin:0;color:var(--mute);font-size:13.5px}.step .who{margin-top:8px;font-size:12px;font-weight:600}
.who.code{color:var(--acc-strong)}.who.model{color:var(--warn)}.who.person{color:var(--info)}
.cols{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.panel{border:1px solid var(--line);border-radius:12px;padding:14px 16px;background:var(--bg)}
.kv{display:grid;grid-template-columns:auto 1fr;gap:6px 16px;font-size:13.5px}.kv dt{color:var(--mute)}.kv dd{margin:0;font-weight:500}
.stat-list{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}
.sdef{border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.sdef p{margin:6px 0 0;font-size:13px;color:var(--mute)}
.barrow{display:grid;grid-template-columns:120px 1fr 90px;gap:10px;align-items:center;font-size:13px;margin:6px 0}
.stack{height:10px;border-radius:5px;background:var(--muted);overflow:hidden;display:flex}
.stack span{display:block;height:100%}
.b-supported{background:var(--acc)}.b-inferred{background:var(--warn)}.b-silent{background:var(--line)}.b-contradicted{background:var(--bad)}.b-refused{background:var(--ink)}
.start{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.start .panel{cursor:pointer}.start .panel:hover{box-shadow:var(--shadow-lg)}
/* pills, dots */
.pill{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:600;border-radius:999px;padding:2px 9px;white-space:nowrap}
.p-supported{color:var(--acc-strong);background:var(--acc-soft)}.p-contradicted{color:var(--bad);background:var(--bad-soft)}
.p-silent{color:var(--mute);background:var(--muted)}.p-inferred{color:var(--warn);background:var(--warn-soft)}.p-refused{color:var(--bg);background:var(--ink)}
.p-nosource{color:var(--mute);background:var(--muted)}
.chip{border:1px solid var(--line);background:var(--bg);border-radius:999px;padding:4px 11px;font-size:12.5px;cursor:pointer;color:var(--mute)}
.chip.on{border-color:var(--ink);color:var(--ink);font-weight:600}
/* entity grid */
.toolbar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:12px}
input[type=search],input[type=text],input[type=url],select,textarea{padding:8px 11px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink);font:inherit}
input[type=search]{flex:1;min-width:220px}
input:focus,select:focus,textarea:focus{outline:2px solid var(--acc);outline-offset:-1px}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
.ecard{border:1px solid var(--line);border-radius:12px;padding:14px;background:var(--bg);box-shadow:var(--shadow);cursor:pointer;display:flex;flex-direction:column;gap:8px;text-align:left}
.ecard:hover{box-shadow:var(--shadow-lg);border-color:var(--faint)}
.ecard .top{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}
.ecard h3{margin:0;font-size:14.5px;line-height:1.3}
.ecard .loc{font-size:12.5px;color:var(--mute)}
.ecard .foot{display:flex;justify-content:space-between;font-size:12px;color:var(--faint);align-items:center}
.cat{font-size:11px;color:var(--mute);background:var(--muted);border-radius:6px;padding:1px 7px;white-space:nowrap}
.flag{font-size:11.5px;font-weight:600;color:var(--bad)}
.count{font:12px var(--mono);color:var(--faint)}
/* drawer */
.scrim{position:fixed;inset:0;background:rgb(15 23 42/.35);z-index:9;display:none}.scrim.on{display:block}
.drawer{position:fixed;top:0;right:0;bottom:0;width:min(760px,100%);background:var(--bg);z-index:10;box-shadow:var(--shadow-lg);
transform:translateX(100%);transition:transform .18s ease;display:flex;flex-direction:column}
.drawer.on{transform:none}
.dh{padding:16px 20px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:12px;align-items:flex-start}
.dh h2{margin:0 0 4px;font-size:18px}.db{overflow:auto;padding:4px 20px 40px;flex:1}
.row{display:grid;grid-template-columns:150px minmax(0,1fr);gap:12px;padding:12px 0;border-top:1px solid var(--hair)}
.row:first-child{border-top:0}
.field{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--faint);margin-right:6px}
.val{font-weight:600}
.quote{margin:6px 0 4px;padding:8px 12px;background:var(--muted);border-radius:8px}
.quote .src{display:block;margin-top:4px;font:12px var(--mono)}
.why{font-size:13px;color:var(--mute)}.pv{color:var(--bad);font-weight:600}
details.trace{margin-top:6px}details.trace summary{cursor:pointer;font-size:12.5px;color:var(--mute);list-style:none}
details.trace summary::before{content:"▸ ";font-size:10px}details.trace[open] summary::before{content:"▾ "}
ol.steps{list-style:none;margin:8px 0 2px;padding:0 0 0 4px}
ol.steps li{position:relative;padding:0 0 10px 22px;font-size:13px;color:var(--mute)}
ol.steps li::before{content:"";position:absolute;left:4px;top:7px;width:8px;height:8px;border-radius:50%;background:var(--line)}
ol.steps li::after{content:"";position:absolute;left:7.5px;top:17px;bottom:-2px;width:1px;background:var(--hair)}
ol.steps li:last-child::after{display:none}ol.steps li b{color:var(--ink);font-weight:600;margin-right:6px}
ol.steps li.ok::before{background:var(--acc)}ol.steps li.warn::before{background:var(--warn)}
ol.steps li.stop::before{background:var(--bad)}ol.steps li.wait::before{background:var(--bg);outline:1.5px solid var(--faint)}
.act{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;align-items:center}
.act input{width:170px;padding:5px 8px;font-size:13px}
.btn{font-size:13px;border-radius:8px;border:1px solid var(--line);background:var(--bg);padding:6px 12px;cursor:pointer}
.btn:hover{background:var(--muted)}.btn.primary{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.btn.on-accept{background:var(--acc-soft);border-color:var(--acc);color:var(--acc-strong);font-weight:600}
.btn.on-reject{background:var(--bad-soft);border-color:var(--bad);color:var(--bad);font-weight:600}
.before-box{border:1px dashed var(--line);border-radius:10px;padding:10px 12px;color:var(--mute);font-size:13px;margin-top:6px}
/* queue */
.qrow{border:1px solid var(--line);border-radius:12px;padding:4px 16px;margin:10px 0;background:var(--bg)}
.qrow .who{font-size:12.5px;color:var(--mute);padding-top:10px}
.test{background:var(--test-soft);color:var(--test);font-weight:600;padding:7px 12px;border-radius:8px;font-size:12.5px}
/* add */
.form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 16px;max-width:860px}
.form label{display:flex;flex-direction:column;gap:5px;font-size:13px;font-weight:600}
.form label span{font-weight:400;color:var(--faint);font-size:12px}
.form .full{grid-column:1/-1}
.checks{display:flex;flex-direction:column;gap:6px;margin:14px 0;max-width:860px}
.ck{display:flex;gap:8px;font-size:13.5px}.ck.ok{color:var(--acc-strong)}.ck.bad{color:var(--bad)}.ck.wait{color:var(--mute)}
pre.code{background:var(--muted);border-radius:10px;padding:12px 14px;font:12px/1.5 var(--mono);overflow:auto;max-width:860px}
.empty{color:var(--mute);padding:40px 0;text-align:center}
@media (max-width:900px){.tiles,.flow,.stat-list,.start{grid-template-columns:repeat(2,minmax(0,1fr))}.cols,.form{grid-template-columns:1fr}}
@media (max-width:560px){.tiles,.flow,.stat-list,.start{grid-template-columns:1fr}.row{grid-template-columns:1fr}.bar-in,.wrap{padding-left:16px;padding-right:16px}}
</style></head><body>
<div class="bar"><div class="bar-in">
  <div class="brand"><i></i>Atlas Receipts</div>
  <span class="admin" title="There is no login yet. This console is meant for the Atlas maintainer and admins, not the public.">Maintainer console · admin only</span>
  <nav class="tabs" id="tabs">
    <a href="#home" data-v="home">Home</a><a href="#entities" data-v="entities">Entities</a>
    <a href="#queue" data-v="queue">Review queue</a><a href="#refused" data-v="refused">Refused</a><a href="#add" data-v="add">Add an entity</a>
  </nav>
  <div class="grow"></div>
  <div class="seg" id="mode" title="Before: what the Atlas shows today. After: with receipts."><button data-m="before">Before</button><button data-m="after">After</button></div>
  <button class="iconbtn" id="theme">Dark</button>
</div></div>

<section class="view" id="v-home"><div class="wrap">
  <div class="note">Mass AI Atlas · maintainer console (proposed) · data pulled <span id="h-gen"></span></div>
  <h1>Every claim in the Atlas, checked against the organization's own page.</h1>
  <p class="lead">The Atlas lists 197 organizations and makes <b id="h-total"></b> checkable claims about them: that each is live,
  where it is, what it offers, its check size and terms, who it works with, and its deadlines. Atlas Receipts finds the exact
  sentence on each organization's own website that backs each claim, so the maintainer reviews only what changed or what
  no page supports.</p>
  <div class="mode-note" id="h-mode"></div>
  <div class="tiles" id="h-tiles"></div>

  <h2>How it works</h2>
  <div class="flow">
    <div class="step"><span class="n">1</span><h3>Fetch</h3><p>Read each organization's own pages: home, about, contact, apply, program. Respect robots.txt, one request a second per site, keep a copy of every page.</p><div class="who code">Done by code</div></div>
    <div class="step"><span class="n">2</span><h3>Find</h3><p>Search the saved pages for the sentence behind each claim: the amount, the date, the address, the other organization's name. For wording like "offers mentorship", Claude may point at a sentence.</p><div class="who model">Code, with suggestions from Claude</div></div>
    <div class="step"><span class="n">3</span><h3>Check</h3><p>Code confirms the exact sentence is on the saved page and compares it with the Atlas value. Claude's suggestions can never be marked verified, only "inferred".</p><div class="who code">Done by code</div></div>
    <div class="step"><span class="n">4</span><h3>Decide</h3><p>The maintainer accepts or rejects each finding. Accepted changes go to a branch of the Atlas, then the Atlas's own validator runs. Nothing is published without that.</p><div class="who person">Done by a person</div></div>
  </div>

  <h2>What each status means</h2>
  <div class="stat-list">
    <div class="sdef"><span class="pill p-supported">Supported</span><p>Code found the sentence on the organization's own page, and it matches.</p></div>
    <div class="sdef"><span class="pill p-contradicted">Contradicted</span><p>The organization's page says something different. Both values are shown.</p></div>
    <div class="sdef"><span class="pill p-silent">Silent</span><p>No page says it. Needs review, with the pages that were searched.</p></div>
    <div class="sdef"><span class="pill p-inferred">Inferred</span><p>Claude's reading of a real sentence. Useful, but not verified.</p></div>
    <div class="sdef"><span class="pill p-refused">Refused</span><p>Not collected: the site's rules forbid it, or a suggested sentence was not on the page.</p></div>
  </div>

  <h2>Start here</h2>
  <div class="start" id="h-start"></div>

  <h2>The data and the system</h2>
  <div class="cols">
    <div class="panel"><h3>Claims by type</h3><div id="h-types"></div><div class="note" style="margin-top:8px">Green: verified by code · amber: Claude's reading · grey: nothing found · red: contradicted · black: refused</div></div>
    <div class="panel"><h3>System status</h3><dl class="kv" id="h-sys"></dl></div>
  </div>
  <p class="note" style="margin-top:28px">Data: Mass AI Atlas, The Open Accelerator, CC BY 4.0. Organizations only: no people and no contact details are collected or shown.
  This console is a proposal for the Atlas maintainer; it is not part of the public Atlas.</p>
</div></section>

<section class="view" id="v-entities"><div class="wrap">
  <div class="mode-note" id="e-mode"></div>
  <div class="toolbar"><input type="search" id="e-q" placeholder="Search 197 organizations by name, id or town">
    <select id="e-sort"><option value="problems">Most to review first</option><option value="name">Name A–Z</option><option value="verified">Least verified first</option><option value="oldest">Oldest check first</option></select>
    <select id="e-show"><option value="all">All entities</option><option value="contradicted">With a contradiction</option><option value="review">With claims to review</option><option value="clean">Fully verified</option><option value="shortlist">Founder shortlist (12)</option></select></div>
  <div class="chips" id="e-cats"></div>
  <div class="note" id="e-count" style="margin-bottom:10px"></div>
  <div class="grid" id="e-grid"></div>
</div></section>

<section class="view" id="v-queue"><div class="wrap">
  <div class="toolbar"><div><h2 style="margin:0">Review queue</h2><div class="note">Riskiest first: contradictions, then deadlines and check sizes. Verified claims are not here. <span id="q-n"></span></div></div>
    <div class="grow"></div><select id="q-f"><option value="contradicted">Contradicted</option><option value="silent">Silent</option><option value="inferred">Inferred</option><option value="all" selected>All to review</option></select>
    <button class="btn primary" id="dl">Download decisions.json (<span id="nd">0</span>)</button></div>
  <div id="q-list"></div><div style="text-align:center;margin:16px"><button class="btn" id="q-more">Show 40 more</button></div>
</div></section>

<section class="view" id="v-refused"><div class="wrap">
  <h2 style="margin-top:0">Refused: what it would not do, and why</h2>
  <p class="lead">Holding back is part of being accurate. These were not collected, or a suggested sentence was rejected because it was not on the page.</p>
  <div id="r-list"></div>
</div></section>

<section class="view" id="v-add"><div class="wrap">
  <h2 style="margin-top:0">Add an entity</h2>
  <p class="lead">A new organization goes through the same checks before it reaches the Atlas: no duplicate of the 197, in Massachusetts,
  an https site that answers, and receipts for its claims. This form drafts the entry; the command below checks it and puts it in the
  review queue. Nothing is written to the Atlas until the maintainer accepts it.</p>
  <div class="form">
    <label>Name<input type="text" id="a-name" placeholder="Organization name"></label>
    <label>Id<span>lowercase, kebab-case, unique</span><input type="text" id="a-id" placeholder="auto from name"></label>
    <label>Category<select id="a-cat"></select></label>
    <label>Location<span>address or neighborhood, town</span><input type="text" id="a-loc" placeholder="e.g. 1 Broadway, Cambridge"></label>
    <label class="full">Website<span>the organization's own page; https only</span><input type="url" id="a-url" placeholder="https://"></label>
    <label class="full">Description<textarea id="a-desc" rows="2" placeholder="One sentence, in the Atlas's style"></textarea></label>
  </div>
  <div class="checks" id="a-checks"></div>
  <div class="toolbar"><button class="btn primary" id="a-dl">Download new-entry.json</button></div>
  <pre class="code">python -m receipts propose new-entry.json
# checks: duplicate of the 197? in Massachusetts? site answers? then fetches its pages and writes receipts
# for its claims to out/proposed/&lt;id&gt;.json for review. It never edits entities.yml.</pre>
  <p class="note">The Atlas's own issue form and suggestion bot can feed this step too: a suggested entry gets receipts before a person reads it.</p>
</div></section>

<div class="scrim" id="scrim"></div>
<aside class="drawer" id="drawer"><div class="dh"><div id="d-h"></div><button class="iconbtn" id="d-x">Close</button></div><div class="db" id="d-b"></div></aside>

<script id="data" type="application/json">/*DATA*/</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=n=>(n||0).toLocaleString();
const $=id=>document.getElementById(id);
const ORDER=['contradicted','refused','silent','inferred','supported'];
const LABEL={supported:'Supported',contradicted:'Contradicted',silent:'Silent',inferred:'Inferred, not verified',refused:'Refused'};
const RISK={deadline:0,fact:1,live:2,place:3,link:4,offer:5};
const store={get(k,d){try{return JSON.parse(localStorage.getItem(k))??d}catch(e){return d}},set(k,v){try{localStorage.setItem(k,JSON.stringify(v))}catch(e){}}};
let mode=store.get('receipts-mode','after'),dec=store.get('receipts-decisions',{});
const C=D.head.counts,T=D.head.total,M=D.meta;
const byEnt={};for(const r of D.rows)(byEnt[r.id]=byEnt[r.id]||[]).push(r);
const SL=new Set(D.head.shortlist);
const ents=D.entities.map(e=>{const rs=byEnt[e.id]||[];const n={};rs.forEach(r=>n[r.status]=(n[r.status]||0)+1);
  return {...e,rs,n,total:rs.length,sup:n.supported||0,worst:rs.length?Math.min(...rs.map(r=>ORDER.indexOf(r.status))):9}});
const saveDec=()=>{store.set('receipts-decisions',dec);$('nd').textContent=Object.keys(dec).length};

/* ---------- mode ---------- */
function setMode(m){mode=m;store.set('receipts-mode',m);document.querySelectorAll('#mode button').forEach(b=>b.classList.toggle('on',b.dataset.m===m));renderAll()}
$('mode').onclick=e=>{const b=e.target.closest('button');if(b)setMode(b.dataset.m)};
const modeNote=()=>mode==='before'
 ?`<b>Before:</b> what the Atlas shows today. Each entry has one "last verified" month for all its claims, and no claim links to a source.`
 :`<b>After:</b> each claim carries a receipt, the sentence on the organization's own page that backs it, or a status saying why not.`;

/* ---------- home ---------- */
function renderHome(){
  $('h-gen').textContent=M.atlas_generated;$('h-total').textContent=fmt(T);$('h-mode').innerHTML=modeNote();
  const sent=(C.supported||0)+(C.inferred||0);
  const tiles=mode==='before'?[
    ['Claims with a source','0',`of ${fmt(T)}`,'Probe 8, before',''],
    ['How "verified" is shown','1 date','per entry','e.g. "2026-06" covers every claim',''],
    ['Entries last checked in June',fmt(M.june),'of 197','a date, not evidence',''],
    ['Time to re-check one entry','10–15','min','by hand, every claim',''],
  ]:[
    ['Claims verified by code',fmt(C.supported),`of ${fmt(T)}`,'Probe 8: was 0 this morning','big'],
    ['Carry a sentence from the org',fmt(sent),`of ${fmt(T)}`,`includes ${fmt(C.inferred)} labelled inferred`,''],
    ['Contradicted by the org itself',fmt(C.contradicted),'claims','both values shown',''],
    ['Need a person',fmt(T-(C.supported||0)-(C.refused||0)),'claims','silent, inferred or contradicted',''],
  ];
  $('h-tiles').innerHTML=tiles.map(([k,v,u,s,c])=>`<div class="tile ${c}"><div class="k">${esc(k)}</div><div class="v">${esc(v)} <small>${esc(u)}</small></div><div class="s">${esc(s)}</div></div>`).join('');
  const contra=ents.filter(e=>e.n.contradicted).slice(0,3);
  $('h-start').innerHTML=contra.map(e=>{const r=e.rs.find(r=>r.status==='contradicted');
    return `<div class="panel" data-open="${esc(e.id)}"><span class="pill p-contradicted">Contradicted</span><h3 style="margin-top:8px">${esc(e.name)}</h3>
    <div class="why">Atlas: <b>${esc(r.value)}</b><br>Their page: <span class="pv">${esc(r.page_value)}</span></div></div>`}).join('')
    ||'<div class="note">No contradictions in this run.</div>';
  const types=[['live','Is live'],['place','Location'],['offer','Offers'],['fact','Facts (check size, terms…)'],['link','Links to other orgs'],['deadline','Deadlines']];
  $('h-types').innerHTML=types.map(([t,l])=>{const rs=D.rows.filter(r=>r.field===t),n=rs.length;
    if(mode==='before')return `<div class="barrow"><span>${l}</span><div class="stack"></div><span class="count">0 / ${n}</span></div>`;
    const seg=ORDER.slice().reverse().map(s=>{const k=rs.filter(r=>r.status===s).length;return k?`<span class="b-${s}" style="width:${100*k/n}%" title="${s} ${k}"></span>`:''}).join('');
    return `<div class="barrow"><span>${l}</span><div class="stack">${seg}</div><span class="count">${rs.filter(r=>r.status==='supported').length} / ${n}</span></div>`}).join('');
  const s=M.score;
  const sys=[['Atlas data',`197 entries · pulled ${M.atlas_generated}`],['Pages read',`${fmt(M.pages)} saved pages from the orgs' own sites`],
    ['Last check',D.head.generated],['Claude',`${M.model} · ${fmt(M.model_calls)} cached readings`],
    ['Validator',M.validator],['Planted test',s?`${s.planted} planted errors: ${s.caught} caught, ${s.missed} missed, ${s.false_alarms} false alarm`:'not run'],
    ['Link click test',M.clicks||'not run'],['Writes to the Atlas','only accepted decisions, on a branch, then the validator']];
  $('h-sys').innerHTML=sys.map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('');
}
$('h-start').onclick=e=>{const p=e.target.closest('[data-open]');if(p)openEntity(p.dataset.open)};

/* ---------- entities grid ---------- */
let cat='all';
$('e-cats').innerHTML=[['all','All',197],...Object.entries(M.cats).map(([k,l])=>[k,l,ents.filter(e=>e.cat===k).length])]
  .map(([k,l,n])=>`<button class="chip ${k==='all'?'on':''}" data-c="${k}">${esc(l)} <span class="count">${n}</span></button>`).join('');
$('e-cats').onclick=e=>{const b=e.target.closest('.chip');if(!b)return;cat=b.dataset.c;$('e-cats').querySelectorAll('.chip').forEach(x=>x.classList.toggle('on',x===b));renderGrid()};
['e-q','e-sort','e-show'].forEach(id=>$(id).oninput=renderGrid);
function renderGrid(){
  $('e-mode').innerHTML=modeNote();
  const q=$('e-q').value.trim().toLowerCase(),sort=$('e-sort').value,show=$('e-show').value;
  let list=ents.filter(e=>(cat==='all'||e.cat===cat)&&(!q||(e.name+' '+e.id+' '+e.loc).toLowerCase().includes(q)));
  if(mode==='after'){
    if(show==='contradicted')list=list.filter(e=>e.n.contradicted);
    if(show==='review')list=list.filter(e=>e.sup<e.total);
    if(show==='clean')list=list.filter(e=>e.total&&e.sup===e.total);
  }
  if(show==='shortlist')list=list.filter(e=>SL.has(e.id));
  const key={problems:e=>[mode==='after'?e.worst:0,e.name],name:e=>[e.name],verified:e=>[mode==='after'?e.sup/(e.total||1):0,e.name],oldest:e=>[e.lastVerified,e.name]}[sort];
  list.sort((a,b)=>{const x=key(a),y=key(b);return x[0]<y[0]?-1:x[0]>y[0]?1:String(x[1]).localeCompare(y[1])});
  $('e-count').textContent=`${list.length} of 197 organizations`+(show==='shortlist'&&mode==='after'?` · shortlist: ${D.head.sl_supported} of ${D.head.sl_total} claims verified, ${D.head.sl_sentence} carry a sentence (this morning: 0)`:'');
  $('e-grid').innerHTML=list.map(e=>{
    const body=mode==='before'
      ?`<div class="stack"></div><div class="foot"><span>verified ${esc(e.lastVerified)} · whole entry</span><span class="count">0 / ${e.total} sourced</span></div>`
      :`<div class="stack">${ORDER.slice().reverse().map(s=>e.n[s]?`<span class="b-${s}" style="width:${100*e.n[s]/e.total}%"></span>`:'').join('')}</div>
        <div class="foot"><span>${e.n.contradicted?`<span class="flag">▲ ${e.n.contradicted} contradicted</span>`:e.n.refused?'refused':e.sup===e.total?'all verified':`${e.total-e.sup} to review`}</span><span class="count">${e.sup} / ${e.total} verified</span></div>`;
    return `<button class="ecard" data-open="${esc(e.id)}"><div class="top"><h3>${esc(e.name)}</h3><span class="cat">${esc(M.cats[e.cat]||e.cat)}</span></div>
      <div class="loc">${esc(e.loc)}${e.approx?' · approximate pin':''}</div>${body}</button>`}).join('')||'<div class="empty">No organizations match.</div>';
}
$('e-grid').onclick=e=>{const c=e.target.closest('[data-open]');if(c)openEntity(c.dataset.open)};

/* ---------- claim rows ---------- */
function rowHtml(r,withName){
  const d=dec[r.key]||{};
  let b=`<div><span class="field">${esc(r.field)}</span><span class="val">${esc(r.value)}</span></div>`;
  if(mode==='before'){
    return `<div class="row"><div><span class="pill p-nosource">No source</span></div><div>${b}<div class="before-box">The Atlas shows this claim with no link to where it came from. The only check is "last verified ${esc((ents.find(e=>e.id===r.id)||{}).lastVerified)}" for the whole entry.</div></div></div>`;
  }
  if(r.quote&&r.status!=='refused')b+=`<div class="quote">“${esc(r.quote)}”<a class="src" href="${esc(r.link)}" target="_blank" rel="noopener" title="Open the page with this sentence highlighted">↗ ${esc(r.url.replace(/^https?:\/\//,''))} · ${esc(r.fetched)}</a></div>`;
  if(r.status==='refused'&&r.quote)b+=`<div class="quote">Suggested, not on the page: “${esc(r.quote)}”</div>`;
  b+=r.status==='contradicted'&&r.page_value?`<div class="why">Atlas: <b>${esc(r.value)}</b> · their page: <span class="pv">${esc(r.page_value)}</span></div>`:`<div class="why">${esc(r.reason)}</div>`;
  b+=`<details class="trace"><summary>How this was checked</summary><ol class="steps">${r.trace.map(([s,t,x])=>`<li class="${s}"><b>${esc(t)}</b>${esc(x)}${t==='Fetched'&&r.searched&&r.searched.length>1?'<br>'+r.searched.map(u=>`<a class="mono" href="${esc(u)}" target="_blank" rel="noopener">${esc(u.replace(/^https?:\/\//,''))}</a>`).join(' · '):''}</li>`).join('')}</ol></details>`;
  const editable=['contradicted','silent','inferred'].includes(r.status)&&['deadline','place','live','fact'].includes(r.field);
  if(r.planted)b+='<div class="test">TEST: planted copy with deliberate errors. Can never be applied.</div>';
  else if(r.status!=='refused')b+=`<div class="act">${editable?`<input type="text" placeholder="Corrected value (optional)" data-k="${esc(r.key)}" value="${esc(d.new_value||'')}">`:''}
    <button class="btn ${d.decision==='accept'?'on-accept':''}" data-k="${esc(r.key)}" data-d="accept">${r.status==='supported'?'Confirm':'Accept'}</button>
    <button class="btn ${d.decision==='reject'?'on-reject':''}" data-k="${esc(r.key)}" data-d="reject">Reject</button></div>`;
  return `<div class="row"><div><span class="pill p-${r.status}">${LABEL[r.status]}</span>${withName?`<div class="who"><a href="#" data-open="${esc(r.id)}">${esc(r.name)}</a></div>`:''}</div><div>${b}</div></div>`;
}
function onRowClick(e,rerender){
  const o=e.target.closest('[data-open]');if(o){e.preventDefault();openEntity(o.dataset.open);return}
  const b=e.target.closest('button[data-d]');if(!b)return;const k=b.dataset.k,cur=dec[k]||{};
  if(cur.decision===b.dataset.d)delete dec[k];else dec[k]={...cur,key:k,decision:b.dataset.d};saveDec();rerender()}
function onRowInput(e){const i=e.target.closest('input[data-k]');if(!i)return;const k=i.dataset.k;
  dec[k]={...(dec[k]||{key:k,decision:'accept'}),new_value:i.value};if(!i.value)delete dec[k].new_value;saveDec()}

/* ---------- drawer ---------- */
let openId=null;
function openEntity(id){openId=id;renderDrawer();$('drawer').classList.add('on');$('scrim').classList.add('on')}
function closeDrawer(){openId=null;$('drawer').classList.remove('on');$('scrim').classList.remove('on')}
$('d-x').onclick=closeDrawer;$('scrim').onclick=closeDrawer;document.addEventListener('keydown',e=>{if(e.key==='Escape')closeDrawer()});
function renderDrawer(){
  if(!openId)return;const e=ents.find(x=>x.id===openId);if(!e)return;
  const rs=e.rs.slice().sort((a,b)=>ORDER.indexOf(a.status)-ORDER.indexOf(b.status)||(RISK[a.field]??9)-(RISK[b.field]??9));
  $('d-h').innerHTML=`<h2>${esc(e.name)}</h2><div class="note"><span class="mono">${esc(e.id)}</span> · ${esc(M.cats[e.cat]||e.cat)} · ${esc(e.loc)} ·
    <a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.url.replace(/^https?:\/\//,''))}</a></div>
    <div class="note">${mode==='before'?`Last verified ${esc(e.lastVerified)}, one date for all ${e.total} claims. 0 claims have a source.`:`${e.sup} of ${e.total} claims verified by code · last checked by a person ${esc(e.lastVerified)}`}</div>`;
  $('d-b').innerHTML=(e.desc?`<p class="why" style="margin:12px 0">${esc(e.desc)}</p>`:'')+rs.map(r=>rowHtml(r,false)).join('');
}
$('d-b').onclick=e=>onRowClick(e,renderDrawer);$('d-b').oninput=onRowInput;

/* ---------- queue ---------- */
let qn=40;$('q-more').onclick=()=>{qn+=40;renderQueue()};$('q-f').oninput=()=>{qn=40;renderQueue()};
function renderQueue(){
  const f=$('q-f').value;
  let q=D.rows.filter(r=>!['supported','refused'].includes(r.status)&&(f==='all'||r.status===f));
  q.sort((a,b)=>ORDER.indexOf(a.status)-ORDER.indexOf(b.status)||(RISK[a.field]??9)-(RISK[b.field]??9)||a.id.localeCompare(b.id));
  $('q-n').textContent=`${fmt(q.length)} claims.`;
  $('q-list').innerHTML=mode==='before'?`<div class="mode-note">${modeNote()} There is no queue: the maintainer re-checks entries on a calendar, about 17 a month, 10–15 minutes each.</div>`
    :q.slice(0,qn).map(r=>`<div class="qrow">${rowHtml(r,true)}</div>`).join('');
  $('q-more').style.display=mode==='after'&&q.length>qn?'':'none';
}
$('q-list').onclick=e=>onRowClick(e,renderQueue);$('q-list').oninput=onRowInput;
$('dl').onclick=()=>{
  const out=Object.values(dec).filter(d=>!d.key.startsWith('planted-')).map(d=>({key:d.key,decision:d.decision,...(d.new_value?{new_value:d.new_value}:{})}));
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(out,null,1)],{type:'application/json'}));a.download='decisions.json';a.click()};

/* ---------- refused ---------- */
function renderRefused(){
  const ref={};for(const r of D.rows.filter(r=>r.status==='refused'))(ref[r.reason]=ref[r.reason]||[]).push(r);
  $('r-list').innerHTML=Object.entries(ref).sort((a,b)=>b[1].length-a[1].length).map(([w,rs])=>`<div class="panel" style="margin:10px 0"><b>${rs.length} claims</b> · ${esc(w)}
    <div class="note" style="margin-top:4px">${[...new Set(rs.map(r=>r.id))].map(id=>`<a href="#" data-open="${esc(id)}">${esc((ents.find(e=>e.id===id)||{}).name||id)}</a>`).join(' · ')}</div></div>`).join('')
    +`<div class="panel" style="margin:10px 0"><b>${fmt(ents.filter(e=>(e.rs.find(r=>r.field==='live')||{}).reason?.includes('blocks automated')).length)} sites</b> · block automated fetches (HTTP 403/429). We respect that: their claims show as silent, not dead.</div>`;
}
$('r-list').onclick=e=>{const o=e.target.closest('[data-open]');if(o){e.preventDefault();openEntity(o.dataset.open)}};

/* ---------- add an entity ---------- */
$('a-cat').innerHTML=Object.entries(M.cats).map(([k,l])=>`<option value="${k}">${esc(l)}</option>`).join('');
const norm=s=>s.toLowerCase().replace(/\b(inc|llc|the|boston|ventures?|capital|partners)\b/g,'').replace(/[^a-z0-9]/g,'');
const sim=(a,b)=>{if(!a||!b)return 0;if(a===b)return 1;const bg=s=>{const m=new Map();for(let i=0;i<s.length-1;i++){const g=s.slice(i,i+2);m.set(g,(m.get(g)||0)+1)}return m};
  const A=bg(a),B=bg(b);let o=0;for(const [g,n] of A)o+=Math.min(n,B.get(g)||0);return 2*o/((a.length-1)+(b.length-1))};
const hostOf=u=>{try{return new URL(u).hostname.replace(/^www\./,'')}catch(e){return ''}};
const OTHER=/\b(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b/;
function draft(){const name=$('a-name').value.trim();
  return {id:$('a-id').value.trim()||name.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,''),name,cat:$('a-cat').value,
    loc:$('a-loc').value.trim(),url:$('a-url').value.trim(),desc:$('a-desc').value.trim()}}
function renderChecks(){
  const d=draft(),cks=[];
  if(!d.name){$('a-checks').innerHTML='<div class="ck wait">○ Fill in a name and website to run the checks.</div>';return}
  const best=ents.map(e=>[e,sim(norm(e.name),norm(d.name))]).sort((a,b)=>b[1]-a[1])[0];
  const sameHost=d.url&&ents.find(e=>hostOf(e.url)===hostOf(d.url));
  cks.push(sameHost?['bad',`Possible duplicate: same website as ${sameHost.name} (${sameHost.id})`]:best&&best[1]>=0.85?['bad',`Possible duplicate: very close to ${best[0].name} (${best[0].id})`]:['ok',`No duplicate among the 197 (closest: ${best?best[0].name:'none'})`]);
  cks.push(ents.some(e=>e.id===d.id)?['bad',`Id "${d.id}" is already taken`]:['ok',`Id "${d.id}" is free`]);
  cks.push(!d.url?['wait','Website not given yet']:/^https:\/\//.test(d.url)?['ok','Website uses https']:['bad','Website must start with https://']);
  cks.push(!d.loc?['wait','Location not given yet']:OTHER.test(d.loc)?['bad','Location names another state: out of scope for a Massachusetts atlas']:['ok','Location reads as Massachusetts (confirmed when the site is checked)']);
  cks.push(['wait','Receipts for its claims: run the command below']);
  $('a-checks').innerHTML=cks.map(([s,t])=>`<div class="ck ${s}">${s==='ok'?'✓':s==='bad'?'✕':'○'} ${esc(t)}</div>`).join('');
}
['a-name','a-id','a-cat','a-loc','a-url','a-desc'].forEach(id=>$(id).oninput=renderChecks);
$('a-dl').onclick=()=>{const d=draft();if(!d.name||!d.url)return renderChecks();
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(d,null,1)],{type:'application/json'}));a.download='new-entry.json';a.click()};

/* ---------- routing, theme ---------- */
function show(v){v=['home','entities','queue','refused','add'].includes(v)?v:'home';
  document.querySelectorAll('section.view').forEach(s=>s.classList.toggle('on',s.id==='v-'+v));
  document.querySelectorAll('#tabs a').forEach(a=>a.classList.toggle('on',a.dataset.v===v));window.scrollTo(0,0)}
window.addEventListener('hashchange',()=>show(location.hash.slice(1)));
const setTheme=t=>{document.documentElement.dataset.theme=t;$('theme').textContent=t==='dark'?'Light':'Dark';store.set('receipts-theme',t)};
$('theme').onclick=()=>setTheme(document.documentElement.dataset.theme==='dark'?'light':'dark');
function renderAll(){renderHome();renderGrid();renderQueue();renderRefused();renderDrawer()}
setTheme(store.get('receipts-theme','light'));saveDec();renderChecks();
show(location.hash.slice(1));setMode(mode);
</script></body></html>
"""
