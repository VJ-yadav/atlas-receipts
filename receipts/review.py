"""receipts review: out/receipts.json → out/review.html, the maintainer console.

One static file, no framework, opens from disk. Home (what this is, where things stand), an entity
grid with a detail panel, the review queue, the refused list, and a form to draft a new entity.
A Before / After switch shows the same views as the Atlas today and with receipts.
Accept / Reject per claim, then "Download decisions.json" for `receipts apply`.
"""
import json
import os
from collections import Counter

from receipts import metrics
from receipts.claims import FIELD_RISK, no_contact
from receipts.probes import ROOT, load_entries
from receipts.text import highlight_url

# A founder's shortlist (pre-seed, AI infrastructure): funders whose Atlas focus fits.
from receipts.metrics import SHORTLIST  # noqa: E402  (one list, used everywhere)
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



def meta(m):
    """Home page context, all from receipts.metrics (the single source of numbers)."""
    atlas = json.loads((ROOT / "data" / "atlas.json").read_text())
    clicks = m["clicks"]
    return {
        "atlas_generated": m["atlas_generated"],
        "cats": {k: v["label"] for k, v in atlas.get("cats", {}).items()},
        "june": m["june"]["entries"], "pages": m["pages_read"],
        "model": m["model"]["name"], "model_calls": m["model"]["calls"], "run_cost": m["model"]["usd"],
        "validator": m["validator"], "score": m["planted"], "decisions": m["decisions"],
        "clicks": f"{clicks['found']} / {clicks['of']}" if clicks else "",
        "all": m["all"], "probes": m["probes"],
    }


def build(receipts, out_path, entries=None, title="Atlas Receipts"):
    entries = entries if entries is not None else load_entries()
    data = rows(receipts, entries)
    m = metrics.compute(receipts)
    a, sl = m["all"], m["shortlist"]
    head = {"total": a["claims"], "counts": {k: a[k] for k in metrics.STATUSES}, "title": title,
            "shortlist": sl["ids"], "sl_total": sl["claims"], "sl_supported": sl["supported"],
            "sl_sentence": sl["with_sentence"], "generated": m["checked_at"]}
    ents = [{k: e.get(k) for k in ("id", "name", "cat", "loc", "url", "lastVerified", "added", "approx",
                                    "offers", "links", "applyBy")} | {"desc": no_contact(e.get("desc", ""))}
            for e in entries]
    blob = json.dumps({"head": head, "meta": meta(m), "entities": ents, "rows": data})
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(PAGE.replace("/*DATA*/", blob.replace("</", "<\\/")), encoding="utf-8")
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
.data3{display:grid;grid-template-columns:1fr 1.25fr 1fr;gap:12px;align-items:start}
.dcard{border:1px solid var(--line);border-radius:14px;padding:16px;background:var(--bg)}
.dk{font-size:14px;color:var(--mute)}.dk b{font-size:26px;color:var(--ink);font-weight:650;margin-right:4px;font-variant-numeric:tabular-nums}
.dp{font-size:13px;color:var(--mute);margin:6px 0 12px}.dp b{color:var(--ink)}
.cr{display:grid;grid-template-columns:1fr 70px 28px;gap:8px;align-items:center;font-size:12.5px;margin:4px 0}
.cb{height:6px;background:var(--muted);border-radius:3px;overflow:hidden}.cb i{display:block;height:100%;background:var(--faint)}
.ct .t-ic{color:var(--mute);width:18px;height:18px}
.ct{display:grid;grid-template-columns:20px 1fr 44px;gap:10px;align-items:start;padding:7px 0;border-top:1px solid var(--hair)}
.ctl{display:flex;justify-content:space-between;gap:8px;font-size:13px}.ctm{font-size:12px;color:var(--faint);margin:1px 0 4px}
.ct .stack{height:6px}.ct .stack span{display:block;height:100%}.ctv{text-align:right;color:var(--acc-strong)}
.sum{font:12.5px var(--mono);color:var(--mute);border-top:1px solid var(--line);padding-top:8px;margin:6px 0}
.rc{background:var(--side)}.anat{border:1px solid var(--line);border-radius:10px;background:var(--bg);overflow:hidden;margin-bottom:8px}
.anat.off{opacity:.75}.ar{display:grid;grid-template-columns:82px 1fr;gap:8px;padding:7px 10px;border-top:1px solid var(--hair);font-size:12.5px}
.ar:first-child{border-top:0}.ar>span{color:var(--faint);font-size:11px;text-transform:uppercase;letter-spacing:.05em;padding-top:2px}.ar b{font-weight:500}.aq{font-style:italic}
@media (max-width:1100px){.data3{grid-template-columns:1fr}}
.statgrid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}
.sg{border:1px solid var(--line);border-radius:12px;padding:12px 14px;display:grid;grid-template-columns:12px 1fr;gap:2px 8px;align-items:baseline;background:var(--bg)}
.sg i{width:10px;height:10px;border-radius:3px;grid-row:1}.sg b{font-size:22px;font-variant-numeric:tabular-nums}
.sg span,.sg em,.sg small{grid-column:2}.sg span{font-weight:600}.sg em{font-style:normal;font-size:12px;color:var(--faint)}
.sg small{font-size:12px;color:var(--mute);margin-top:4px}.sg.go-q{cursor:pointer}.sg.go-q:hover{box-shadow:var(--shadow-lg)}.sg.go-q small{color:var(--info)}
details.about{margin-top:34px;border-top:1px solid var(--line);padding-top:6px}
details.about>summary{list-style:none;cursor:pointer;display:flex;align-items:baseline;gap:12px;margin:18px 0 12px}
details.about>summary h2{margin:0}details.about>summary::before{content:"▸";color:var(--faint)}details.about[open]>summary::before{content:"▾"}
.origin{margin-top:12px;font-size:13px;color:var(--mute);background:var(--side)}.origin b{color:var(--ink)}
@media (max-width:980px){.statgrid{grid-template-columns:repeat(2,minmax(0,1fr))}}
.pw-rows{border:1px solid var(--line);border-radius:14px;overflow:hidden}
.pw{display:grid;grid-template-columns:28px 230px 110px 1fr;gap:10px;align-items:baseline;padding:8px 14px;border-top:1px solid var(--hair);font-size:13px}
.pw:first-child{border-top:0}.pw .pn{font:600 11px var(--mono);color:var(--faint)}.pw em{font-style:normal;color:var(--mute);font-size:12.5px}
.pw.p8{background:var(--acc-soft)}.pw.p8 b,.pw.p8 .count{color:var(--acc-strong);font-weight:650}
.pw-why{font-size:13.5px;color:var(--mute);max-width:900px;margin:12px 0 0}.pw-why b{color:var(--ink)}
@media (max-width:760px){.pw{grid-template-columns:24px 1fr auto}.pw em{grid-column:2/-1}}
.probes{display:grid;grid-template-columns:repeat(8,minmax(0,1fr));gap:8px}
.pr{border:1px solid var(--line);border-radius:12px;padding:10px 12px;display:flex;flex-direction:column;gap:2px;background:var(--bg)}
.pr .pn{font:600 11px var(--mono);color:var(--faint)}.pr b{font-size:16px;font-variant-numeric:tabular-nums}.pr span:last-child{font-size:12px;color:var(--mute)}
.pr.p8{border:1.5px solid var(--acc);background:var(--acc-soft)}.pr.p8 b{color:var(--acc-strong)}.pr em{font-style:normal;font-size:10.5px;font-weight:700;color:var(--bg);background:var(--acc);border-radius:5px;padding:0 5px;margin-left:4px}
.p8-note{font-size:13px;color:var(--mute);max-width:860px;margin:10px 0 0}.p8-note b{color:var(--ink)}
.tip{position:relative;display:inline-grid;place-items:center;width:15px;height:15px;border-radius:50%;border:1px solid var(--line);font:600 10px var(--sans);color:var(--faint);cursor:help;vertical-align:middle;margin-left:4px;font-style:normal}
.tip:hover::after,.tip:focus::after{content:attr(data-tip);position:absolute;left:50%;bottom:130%;transform:translateX(-50%);width:240px;background:var(--ink);color:var(--bg);font:400 12px/1.45 var(--sans);padding:8px 10px;border-radius:8px;z-index:20;text-align:left;box-shadow:var(--shadow-lg)}
@media (max-width:980px){.probes{grid-template-columns:repeat(4,minmax(0,1fr))}}
.hero{display:grid;grid-template-columns:minmax(0,1fr) 380px;gap:28px;align-items:center}
.kpis{display:flex;gap:28px;flex-wrap:wrap;margin-top:6px}.kpi{max-width:300px}.kpi b{display:block;font-size:24px;font-weight:650;font-variant-numeric:tabular-nums}.kpi span{font-size:12.5px;color:var(--mute)}
.donut-wrap{display:flex;flex-direction:column;align-items:center;gap:8px;border:1px solid var(--line);border-radius:16px;padding:16px;background:var(--side)}
.d-big{font:700 30px var(--sans);fill:var(--ink)}.d-sub{font:12px var(--sans);fill:var(--mute)}
.probe8{font-size:13px;color:var(--mute);border-bottom:1px solid var(--line);padding-bottom:8px;width:100%;text-align:center}
ul.legend{list-style:none;margin:0;padding:0;width:100%;display:flex;flex-direction:column;gap:5px}
ul.legend li{display:grid;grid-template-columns:12px auto 1fr;gap:4px 8px;align-items:baseline;font-size:13px}
ul.legend i{width:10px;height:10px;border-radius:3px;display:inline-block}ul.legend b{font-variant-numeric:tabular-nums}
ul.legend span{grid-column:2/-1;font-size:11.5px;color:var(--faint);margin-top:-3px}
.sec-h{display:flex;align-items:baseline;gap:12px;margin:34px 0 12px}.sec-h h2{margin:0}
.ic{width:20px;height:20px;flex:none}
.pipe{display:flex;align-items:stretch;gap:0;overflow-x:auto;padding-bottom:4px}
.node{flex:1;min-width:150px;border:1px solid var(--line);border-radius:14px;padding:14px;background:var(--bg);display:flex;flex-direction:column;gap:3px}
.node.off{opacity:.55}.n-ic{width:36px;height:36px;border-radius:10px;background:var(--muted);display:grid;place-items:center;margin-bottom:6px}
.n-t{font-weight:650}.n-n{font-size:18px;font-weight:650;font-variant-numeric:tabular-nums}.n-d{font-size:12px;color:var(--mute)}
.who-code,.who-person,.who-code\+{font-size:11px;font-weight:600;margin-top:auto;padding-top:6px}
.who-code{color:var(--acc-strong)}.who-person{color:var(--info)}
.link{display:grid;place-items:center;color:var(--faint);padding:0 4px}
.gauges{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.gauge{border:1px solid var(--line);border-radius:14px;padding:14px 12px 12px;text-align:center;position:relative;background:var(--bg)}
.g-ic{position:absolute;top:12px;left:12px;color:var(--faint);width:18px;height:18px}
.g-v{font-size:22px;font-weight:650;margin-top:-30px;font-variant-numeric:tabular-nums}.g-k{font-size:13px;font-weight:600;margin-top:8px}.g-s{font-size:12px;color:var(--faint)}
.two{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr);gap:28px}
ul.todo{list-style:none;margin:0;padding:0;border:1px solid var(--line);border-radius:14px;overflow:hidden}
ul.todo li{display:grid;grid-template-columns:24px 1fr auto;gap:10px;align-items:center;padding:12px 14px;border-top:1px solid var(--hair);cursor:pointer}
ul.todo li:first-child{border-top:0}ul.todo li.plain{display:block;cursor:default}ul.todo li:hover{background:var(--side)}
.t-ic{color:var(--bad)}.types .t-ic{color:var(--mute);width:18px;height:18px}
.go{font-size:12.5px;color:var(--info);display:flex;gap:4px;align-items:center}.go .ic{width:15px;height:15px}
.trow{display:grid;grid-template-columns:20px 80px 1fr 78px;gap:10px;align-items:center;margin:9px 0;font-size:13px}
.trow .stack{height:10px}.trow .count{white-space:nowrap;text-align:right}.trow .stack span{display:block;height:100%}
@media (max-width:980px){.hero,.two{grid-template-columns:1fr}.gauges{grid-template-columns:repeat(2,minmax(0,1fr))}.pipe{flex-direction:column}.link{transform:rotate(90deg)}}
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
  <div class="hero">
    <div class="hero-l">
      <div class="note">Mass AI Atlas · maintainer console (proposed) · data pulled <span id="h-gen"></span></div>
      <h1>Every claim in the Atlas, checked against the organization's own page.</h1>
      <p class="lead">Each claim gets a receipt: the sentence on the organization's own website that backs it. You review only
      what no page supports, or what a page contradicts.</p>
      <div class="mode-note" id="h-mode"></div>
      <div class="kpis" id="h-kpis"></div>
    </div>
    <div class="hero-r"><div class="donut-wrap"><svg id="h-donut" viewBox="0 0 200 200" width="190" height="190" role="img"></svg>
      <div class="probe8" id="h-p8"></div></div></div>
  </div>

  <div class="sec-h"><h2>Your queue</h2><span class="note">what needs a decision, by status</span></div>
  <div class="statgrid" id="h-legend"></div>

  <div class="sec-h"><h2>Start here</h2><span class="note">the organization's own site disagrees with the Atlas</span></div>
  <ul class="todo" id="h-start"></ul>

  <div class="sec-h"><h2>The probes</h2><span class="note">how the Atlas is measured</span></div>
  <div class="probes" id="h-probes"></div>
  <p class="p8-note"><b>Probe 8 is new.</b> The organizers' probes 1–7 count gaps in the Atlas. Probe 8 counts what
  none of them can: how many of the Atlas's claims carry a source you can click, a sentence on the organization's own
  page that code confirmed is there. This morning it was 0. It is the number this project moves.</p>

  <div class="sec-h"><h2>How a claim gets its receipt</h2><span class="note">live numbers from the last run</span></div>
  <div class="pipe" id="h-pipe"></div>

  <div class="sec-h"><h2>Is it working?</h2><span class="note">measured, not assumed</span></div>
  <div class="gauges" id="h-gauges"></div>

  <details class="about" id="h-about"><summary><h2>What's in the data</h2><span class="note">197 organizations · 1,080 claims · what a receipt is · where claims come from</span></summary>
  <div class="data3"><div class="dcard" id="h-orgs"></div><div class="dcard" id="h-claims"></div><div class="dcard rc" id="h-receipt"></div></div>
  <div class="dcard origin"><b>Where the claims come from.</b> Every claim is a value someone typed into the Atlas's data file,
  <span class="mono">data/entities.yml</span>: the maintainer's own research, or a suggestion through the Atlas's "suggest an
  organization" issue form (website, address, what it offers…), which a bot drafts into an entry for the maintainer to merge.
  Facts like check size and links to other organizations are added by hand. None of it records which page it came from, and the
  only proof today is one "last verified" month per entry. Atlas Receipts goes back to the organization's own site for each value.</div>
  </details>

  <div class="sec-h"><h2>Why a Probe 8</h2><span class="note">the organizers' seven probes, and the one we added</span></div>
  <div class="pwhy" id="h-pwhy"></div>
  <p class="note" style="margin-top:34px">Data: Mass AI Atlas, The Open Accelerator, CC BY 4.0. Organizations only: no people and no contact details are
  collected or shown. A proposal for the Atlas maintainer; not part of the public Atlas. <a href="atlas.html">Open the public view →</a></p>
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
const ICON={
 globe:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
 search:'<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
 shield:'<path d="M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6z"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
 user:'<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/>',
 branch:'<circle cx="6" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="7" r="2"/><path d="M6 7v10M18 9c0 5-6 4-12 8"/>',
 alert:'<path d="M12 4 2.5 20h19z"/><path d="M12 10v4M12 17.5v.01"/>',
 pin:'<path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
 gift:'<rect x="3" y="8" width="18" height="5" rx="1"/><path d="M5 13v8h14v-8M12 8v13M12 8C10 4 6 4 7.5 7M12 8c2-4 6-4 4.5-1"/>',
 chart:'<path d="M4 20V10M10 20V4M16 20v-7M2 20h20"/>',
 link:'<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
 cal:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
 coin:'<circle cx="12" cy="12" r="9"/><path d="M15 9.5c-.5-1-1.6-1.5-3-1.5-1.7 0-3 .8-3 2s1.3 1.7 3 2 3 .8 3 2-1.3 2-3 2c-1.4 0-2.5-.5-3-1.5M12 6.5v11"/>',
 target:'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
 click:'<path d="M9 9l11 4-5 1.5L13.5 20z"/><path d="M5 3v3M3 5h3M8.5 4.5l-1 1"/>',
 arrow:'<path d="M5 12h14M13 6l6 6-6 6"/>'};
const ic=(n,c='')=>`<svg class="ic ${c}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${ICON[n]}</svg>`;
const SCOL={supported:'var(--acc)',inferred:'var(--warn)',contradicted:'var(--bad)',silent:'var(--line)',refused:'var(--ink)'};
const SDESC={supported:'code found the sentence on their own page',inferred:"Claude's reading of a real sentence, not verified",
  contradicted:'their own page says something else',silent:'no page says it: needs a look',refused:'not allowed to collect, so not checked'};
function donut(){
  const segs=mode==='before'?[['none',T]]:['supported','inferred','contradicted','silent','refused'].map(s=>[s,C[s]||0]);
  const R=78,L=2*Math.PI*R;let off=0;
  const arcs=segs.map(([s,n])=>{const len=L*n/T,gap=n&&segs.length>1?1.5:0;
    const el=`<circle cx="100" cy="100" r="${R}" fill="none" stroke="${s==='none'?'var(--line)':SCOL[s]}" stroke-width="22" stroke-dasharray="${Math.max(0,len-gap)} ${L}" stroke-dashoffset="${-off}" transform="rotate(-90 100 100)"><title>${s} ${n}</title></circle>`;off+=len;return el}).join('');
  const big=mode==='before'?'0':fmt(C.supported),sub=mode==='before'?'claims with a source':'verified by code';
  $('h-donut').innerHTML=arcs+`<text x="100" y="98" text-anchor="middle" class="d-big">${big}</text><text x="100" y="118" text-anchor="middle" class="d-sub">${sub}</text><text x="100" y="134" text-anchor="middle" class="d-sub">of ${fmt(T)}</text>`;
  $('h-p8').innerHTML=tip(TIPS.donut)+` <b>Probe 8</b>, claims with a receipt: 0 → <b>${mode==='before'?0:fmt(C.supported)}</b> of ${fmt(T)}`;
  const ACT={supported:['','nothing to do'],inferred:['inferred','confirm or reject Claude\'s reading'],contradicted:['contradicted','decide which value is right'],
    silent:['silent','look for a source, or mark unsourced'],refused:['','nothing collected']};
  $('h-legend').innerHTML=mode==='before'?`<div class="sg"><i style="background:var(--line)"></i><b>${fmt(T)}</b><span>no source</span><em>one "last verified" month per entry; no queue</em></div>`
    :['contradicted','silent','inferred','supported','refused'].map(s=>{const [f,a]=ACT[s];
      return `<div class="sg ${f?'go-q':''}" ${f?`data-q="${f}"`:''}><i style="background:${SCOL[s]}"></i><b>${fmt(C[s])}</b><span>${LABEL[s].split(',')[0]}</span><em>${SDESC[s]}</em><small>${f?`${a} →`:a}</small></div>`}).join('');
}
function gauge(pct,label,val,sub,icon,tone,tipkey){
  const R=52,L=Math.PI*R,f=Math.max(0,Math.min(1,pct));
  return `<div class="gauge">${ic(icon,'g-ic')}<svg viewBox="0 0 130 74" width="150"><path d="M13 66a52 52 0 0 1 104 0" fill="none" stroke="var(--muted)" stroke-width="11" stroke-linecap="round"/>
    <path d="M13 66a52 52 0 0 1 104 0" fill="none" stroke="${tone}" stroke-width="11" stroke-linecap="round" stroke-dasharray="${L*f} ${L}"/></svg>
    <div class="g-v">${val}</div><div class="g-k">${label} ${tip(TIPS[tipkey])}</div><div class="g-s">${sub}</div></div>`}
const tip=t=>`<span class="tip" tabindex="0" data-tip="${esc(t)}">i</span>`;
const TIPS={
 sentence:"Claims where the organization's own page has a sentence about it: verified, Claude's reading, or contradicting.",
 contra:"Claims where the organization's own page says something different from the Atlas. Both values are shown; a person decides.",
 need:"Contradicted, silent and inferred claims: the ones a person should look at. Verified and refused ones need no decision.",
 donut:"All 1,080 claims by status. Green is verified by code: Probe 8.",
 fetch:"Pages read from the organizations' own sites that returned text. Saved to disk; robots.txt respected.",
 find:"Every checkable claim in the Atlas: live, location, offers, facts, links, deadlines.",
 check:"Sentences code confirmed are on the saved page, word for word.",
 decide:"Claims a person accepted or rejected in this console.",
 branch:"Accepted changes are written to a branch of the Atlas, then the Atlas's own validator runs.",
 g1:"Probe 8 as a share: claims verified by code out of all claims.",
 g2:"We planted known errors in a test copy (never the real data) and count how many the checks catch.",
 g3:"Random receipts opened in a real browser: does the quoted sentence appear on the page?",
 g4:"What the model cost to read all 197 organizations once. Code does the verifying, so this stays small."};
const PMEAN={1:"map pins placed at a rough spot, not the real address",2:"organizations linked to no other organization",
 3:"entries not placed on the founder journey",4:"funders that don't say how much they invest",5:"entries not re-checked in 4+ months: stale by date",
 6:"coverage outside Boston and Cambridge",7:"what one manual re-check costs the maintainer"};
function renderPwhy(){
  $('h-pwhy').innerHTML=`<div class="pw-rows">${M.probes.map(p=>`<div class="pw"><span class="pn">${p.n}</span><b>${esc(p.name)}</b><span class="count">${esc(p.value)}</span><em>${PMEAN[p.n]||''}</em></div>`).join('')}
    <div class="pw p8"><span class="pn">8</span><b>claims with a receipt</b><span class="count">${mode==='before'?0:fmt(C.supported)} / ${fmt(T)}</span><em>claims backed by a sentence on the organization's own page that code confirmed</em></div></div>
    <p class="pw-why"><b>Probes 1–7 count gaps in the Atlas. Probe 8 counts something none of them can: how many claims carry a source you can click.</b>
    It went from 0 this morning to ${fmt(C.supported)}. It also gives two of the others evidence: Probe 5 becomes "still holds on their own site" instead of a date,
    and Probe 7 shrinks to the claims that need a person, each with its sentence one click away.</p>`}
function renderHome(){
  $('h-gen').textContent=M.atlas_generated;$('h-mode').innerHTML=modeNote();
  const sent=M.all.with_sentence,need=M.all.needs_person;
  $('h-kpis').innerHTML=(mode==='before'
    ?[['1 date','per entry, for every claim in it'],['10–15 min','to re-check one entry by hand'],[fmt(M.june),'entries last checked in June']]
    :[[fmt(sent),`have a sentence from the org: ${fmt(C.supported)} verified + ${fmt(C.inferred)} Claude's reading + ${fmt(C.contradicted)} contradicting`],[fmt(C.contradicted),'contradicted by the org itself'],[fmt(need),'need a person']])
    .map(([v,k],i)=>`<div class="kpi"><b>${v}${mode==='after'?tip(TIPS[['sentence','contra','need'][i]]):''}</b><span>${k}</span></div>`).join('');
  donut();renderPwhy();
  $('h-probes').innerHTML=M.probes.map(p=>`<div class="pr"><span class="pn">${p.n}</span><b>${esc(p.value)}</b><span>${esc(p.name)}</span></div>`).join('')
    +`<div class="pr p8"><span class="pn">8</span><b>${mode==='before'?'0':fmt(C.supported)} / ${fmt(T)}</b><span>claims with a receipt <em>new</em></span></div>`;
  const before=mode==='before';
  const steps=[['globe','Fetch','code',before?'—':`${fmt(M.pages)} pages`,'their own site, robots.txt, 1 req/s'],
    ['search','Find','code + Claude',before?'—':`${fmt(T)} claims`,'amounts, dates, places, names'],
    ['shield','Check','code',before?'—':`${fmt(sent)} sentences`,'exact text on the saved page'],
    ['user','Decide','person',before?'by hand':`${fmt(M.decisions)} decided`,'accept or reject each finding'],
    ['branch','Atlas branch','code',before?'—':M.validator.startsWith('PASSED')?'validator passed':M.validator,'only accepted rows, then validate.js']];
  $('h-pipe').innerHTML=steps.map(([i,t,who,n,d],k)=>`<div class="node ${before?'off':''}"><div class="n-ic">${ic(i)}</div><div class="n-t">${t} ${tip(TIPS[['fetch','find','check','decide','branch'][k]])}</div><div class="n-n">${n}</div><div class="n-d">${d}</div><div class="who-${who.split(' ')[0]}">${who}</div></div>${k<steps.length-1?`<div class="link">${ic('arrow')}</div>`:''}`).join('');
  const s=M.score||{planted:0,caught:0,false_alarms:0},clk=(M.clicks.match(/(\d+) \/ (\d+)/)||[0,0,1]);
  $('h-gauges').innerHTML=before
    ?`<div class="note" style="grid-column:1/-1">Nothing is measured before: there is no source to check, no test, no queue.</div>`
    :gauge((C.supported||0)/T,'claims verified by code',`${Math.round(100*(C.supported||0)/T)}%`,`${fmt(C.supported)} of ${fmt(T)}`,'target','var(--acc)','g1')
    +gauge(s.planted?s.caught/s.planted:0,'planted errors caught',`${s.caught} / ${s.planted}`,`${s.false_alarms} false alarm on real data`,'alert','var(--info)','g2')
    +gauge(clk[2]?clk[1]/clk[2]:0,'random receipts land on the sentence',`${clk[1]} / ${clk[2]}`,'opened in a real browser','click','var(--acc)','g3')
    +gauge(Math.min(1,(M.run_cost||0)/0.10),'model cost of a full run',`$${(M.run_cost||0).toFixed(2)}`,`${M.model}; code does the verifying`,'coin','var(--warn)','g4');
  const contra=ents.filter(e=>e.n.contradicted);
  $('h-start').innerHTML=before?'<li class="plain note">No way to know: nothing is compared with the organizations\' own pages.</li>'
    :contra.map(e=>{const r=e.rs.find(r=>r.status==='contradicted');
    return `<li data-open="${esc(e.id)}">${ic('alert','t-ic')}<div><b>${esc(e.name)}</b> <span class="note">${esc(r.field)}</span><div class="why">Atlas: ${esc(r.value)} · their site: <span class="pv">${esc(r.page_value)}</span></div></div><span class="go">Review ${ic('arrow')}</span></li>`}).join('');
  const CT=[['live','globe','Is live','the website is real and answers','one per organization'],
    ['place','pin','Location','where the organization is','one per organization'],
    ['offer','gift','Offers','what it offers founders: funding, mentorship, space, talent…','1–3 each'],
    ['fact','chart','Facts','check size, equity, program length, stage, focus…','for funders and programs'],
    ['link','link','Links','another Atlas organization it works with','where the Atlas lists one'],
    ['deadline','cal','Deadlines','when applications close, or "rolling"','for programs that take applications']];
  const bt=t=>D.rows.filter(r=>r.field===t);
  $('h-claims').innerHTML=`<div class="dk"><b>${fmt(T)}</b> claims</div><p class="dp">A <b>claim</b> is one statement in an entry that a founder could act on and the organization's own page can confirm. About ${(T/D.entities.length).toFixed(1)} per organization.</p>
    ${CT.map(([t,i,l,m,w])=>{const rs=bt(t),n=rs.length,v=rs.filter(r=>r.status==='supported').length;
      const seg=before?'':['supported','inferred','contradicted','silent','refused'].map(s=>{const k=rs.filter(r=>r.status===s).length;return k?`<span style="width:${100*k/n}%;background:${SCOL[s]}"></span>`:''}).join('');
      return `<div class="ct">${ic(i,'t-ic')}<div><div class="ctl"><b>${l}</b><span class="count">${fmt(n)}</span></div><div class="ctm">${m}</div><div class="stack">${seg}</div></div><span class="count ctv" title="verified by code">${before?0:v} ✓</span></div>`}).join('')}
    <div class="sum">${CT.map(([t])=>fmt(bt(t).length)).join(' + ')} = <b>${fmt(T)}</b></div>
    <div class="note">Not counted: the description and stages. Those are the Atlas's own wording, not facts an organization's page states.</div>`;
  const byCat={};D.entities.forEach(e=>byCat[e.cat]=(byCat[e.cat]||0)+1);const cmax=Math.max(...Object.values(byCat));
  $('h-orgs').innerHTML=`<div class="dk"><b>${D.entities.length}</b> organizations</div><p class="dp">An <b>organization</b> is one entry in the Atlas, a Massachusetts AI fund, startup, lab, accelerator, community or program, with its website, place, offers and facts.</p>
    ${Object.entries(byCat).sort((a,b)=>b[1]-a[1]).map(([k,n])=>`<div class="cr"><span>${esc(M.cats[k]||k)}</span><div class="cb"><i style="width:${100*n/cmax}%"></i></div><span class="count">${n}</span></div>`).join('')}`;
  const ex=D.rows.find(r=>r.id==='techstars'&&r.field==='deadline')||D.rows.find(r=>r.status==='supported');
  $('h-receipt').innerHTML=`<div class="dk"><b>1</b> receipt per claim</div><p class="dp"><b>Atlas Receipts</b> gives every claim a <b>receipt</b>: proof from the organization's own page, kept with the claim, re-checked when the page changes.</p>
    ${before?`<div class="anat off"><div class="ar"><span>claim</span><b>${esc(ex.name)} · apply by ${esc(ex.value.split(' · ')[0])}</b></div><div class="ar"><span>proof today</span><b>"last verified ${esc((ents.find(e=>e.id===ex.id)||{}).lastVerified)}" for the whole entry. No link, no sentence.</b></div></div>`
    :`<div class="anat"><div class="ar"><span>claim</span><b>${esc(ex.name)} · ${esc(ex.field)} · ${esc(ex.value)}</b></div>
      <div class="ar"><span>sentence</span><b class="aq">“${esc(ex.quote)}”</b></div>
      <div class="ar"><span>where</span><a href="${esc(ex.link)}" target="_blank" rel="noopener">${esc(ex.url.replace(/^https?:\/\//,''))} ↗</a></div>
      <div class="ar"><span>read at</span><b class="mono">${esc(ex.fetched)}</b></div>
      <div class="ar"><span>fingerprint</span><b class="mono">${esc((ex.trace.find(t=>t[1]==='Checked by code')||['','',''])[2].match(/hash (\w+)/)?.[1]||'')}… of the saved page</b></div>
      <div class="ar"><span>status</span><b><span class="pill p-${ex.status}">${LABEL[ex.status]}</span> checked by code</b></div></div>
      <div class="note">Next month the page is read again. If the sentence is still there, nothing to do. If it changed, the claim comes back to you.</div>`}`;
}
$('h-legend').onclick=e=>{const g=e.target.closest('[data-q]');if(!g)return;$('q-f').value=g.dataset.q;qn=40;location.hash='queue';renderQueue()};
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
setTheme(store.get('receipts-theme','light'));
if(!store.get('receipts-seen-about',false)){$('h-about').open=true;store.set('receipts-seen-about',true)}saveDec();renderChecks();
show(location.hash.slice(1));setMode(mode);
</script></body></html>
"""
