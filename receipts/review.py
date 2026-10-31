"""receipts review: out/receipts.json → out/review.html, the maintainer's queue.

One static file, no framework, opens from disk. Problems first; supported claims stay quiet.
Accept / Reject per claim, then "Download decisions.json" for `receipts apply`.
"""
import json
from collections import Counter

from receipts.claims import FIELD_RISK
from receipts.probes import ROOT, load_entries
from receipts.text import highlight_url

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


def build(receipts, out_path, entries=None, title="Atlas Receipts"):
    entries = entries if entries is not None else load_entries()
    data = rows(receipts, entries)
    n = Counter(r["status"] for r in receipts)
    head = {"total": len(receipts), "counts": dict(n), "title": title,
            "generated": max((r["fetched_at"] for r in receipts), default="")[:16].replace("T", " ") + "Z"}
    blob = json.dumps({"head": head, "rows": data}).replace("</", "<\\/")
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(PAGE.replace("/*DATA*/", blob))
    return out_path


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Atlas Receipts</title>
<style>
:root{--bg:#fff;--side:#f9f9fa;--muted:#f4f5f7;--ink:#1c1d21;--mute:#5d6270;--faint:#6e7380;--line:#e3e5e9;--hair:#eceef1;
--acc:#16a34a;--acc-strong:#15803d;--acc-soft:#e8f7ee;--warn:#a35200;--warn-soft:#fff4e0;--bad:#c62828;--bad-soft:#fdecec;
--info:#1f5fbf;--info-soft:#eaf2ff;--test:#b4410c;--test-soft:#fdf0e8;
--sans:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;--mono:"JetBrains Mono","SF Mono",Menlo,monospace;
--r:10px;--shadow:0 1px 2px 0 rgb(16 17 20/.05),0 1px 1px 0 rgb(16 17 20/.03)}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#131417;--side:#16171a;--muted:#212227;--ink:#ececef;--mute:#a6abb6;
--faint:#8e939e;--line:#2c2e34;--hair:#24262b;--acc:#4ade80;--acc-strong:#22c55e;--acc-soft:#15291d;--warn:#fbbf24;--warn-soft:#2e2410;
--bad:#f87171;--bad-soft:#331616;--info:#8fb8ff;--info-soft:#16223a;--test:#fb923c;--test-soft:#331a0c}}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.55 var(--sans);-webkit-font-smoothing:antialiased}
a{color:var(--info);text-decoration:none}a:hover{text-decoration:underline}
.app{display:grid;grid-template-columns:248px 1fr;min-height:100vh}
aside{background:var(--side);border-right:1px solid var(--line);padding:20px 14px;position:sticky;top:0;height:100vh;overflow:auto}
.brand{font-weight:650;font-size:15px;display:flex;gap:8px;align-items:center;margin:0 6px 18px}
.brand i{width:9px;height:9px;border-radius:50%;background:var(--acc);display:inline-block}
.nav{display:flex;flex-direction:column;gap:2px}
.nav button{all:unset;cursor:pointer;display:flex;justify-content:space-between;align-items:center;padding:7px 10px;border-radius:8px;color:var(--mute)}
.nav button:hover{background:var(--muted);color:var(--ink)}
.nav button[aria-pressed=true]{background:var(--bg);color:var(--ink);font-weight:600;box-shadow:var(--shadow);outline:1px solid var(--line)}
.nav .n{font:12px var(--mono);color:var(--faint)}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:8px}
.d-supported{background:var(--acc)}.d-contradicted{background:var(--bad)}.d-silent{background:var(--faint)}.d-inferred{background:var(--warn)}.d-refused{background:var(--ink)}.d-problems{background:var(--info)}.d-all{background:var(--line)}
.side-h{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--faint);margin:20px 10px 6px}
.side-p{font-size:12.5px;color:var(--mute);margin:0 10px;line-height:1.5}
main{min-width:0}
.top{position:sticky;top:0;z-index:2;background:color-mix(in srgb,var(--bg) 92%,transparent);backdrop-filter:blur(8px);border-bottom:1px solid var(--hair);padding:16px 28px}
.stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:12px}
.stat{border:1px solid var(--line);border-radius:var(--r);padding:10px 14px;box-shadow:var(--shadow);background:var(--bg)}
.stat .k{font-size:12px;color:var(--mute)}.stat .v{font:600 22px/1.3 var(--sans);font-variant-numeric:tabular-nums}
.stat .v small{font-size:13px;color:var(--faint);font-weight:400}.stat .v .from{color:var(--faint);font-weight:400}
.tools{display:flex;gap:10px}
input[type=search]{flex:1;min-width:0;padding:8px 12px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink);font:inherit}
input[type=search]:focus,.act input:focus{outline:2px solid var(--acc);outline-offset:-1px}
.btn{font:inherit;font-size:13px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--ink);padding:6px 12px;cursor:pointer}
.btn:hover{background:var(--muted)}.btn.primary{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.btn.on-accept{background:var(--acc-soft);border-color:var(--acc);color:var(--acc-strong);font-weight:600}
.btn.on-reject{background:var(--bad-soft);border-color:var(--bad);color:var(--bad);font-weight:600}
.list{padding:8px 28px 80px;max-width:1100px}
.card{border:1px solid var(--line);border-radius:12px;margin:16px 0;background:var(--bg);box-shadow:var(--shadow);overflow:hidden}
.card-h{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:baseline;padding:12px 16px;border-bottom:1px solid var(--hair)}
.card-h h2{font-size:15px;margin:0;font-weight:650}
.meta{font-size:12.5px;color:var(--mute)}.mono{font-family:var(--mono);font-size:12px}
.bar{height:4px;border-radius:2px;background:var(--muted);width:120px;display:inline-block;vertical-align:middle;margin-left:8px;overflow:hidden}
.bar span{display:block;height:100%;background:var(--acc)}
.test{background:var(--test-soft);color:var(--test);font-weight:600;padding:7px 16px;font-size:12.5px}
.row{display:grid;grid-template-columns:150px minmax(0,1fr) auto;gap:14px;padding:12px 16px;border-top:1px solid var(--hair)}
.row:first-child{border-top:0}
.pill{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:600;border-radius:999px;padding:2px 9px;white-space:nowrap}
.p-supported{color:var(--acc-strong);background:var(--acc-soft)}.p-contradicted{color:var(--bad);background:var(--bad-soft)}
.p-silent{color:var(--mute);background:var(--muted)}.p-inferred{color:var(--warn);background:var(--warn-soft)}.p-refused{color:var(--bg);background:var(--ink)}
.field{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--faint);margin-right:6px}
.val{font-weight:600}
.quote{margin:6px 0 4px;padding:8px 12px;background:var(--muted);border-radius:8px;color:var(--ink)}
.quote .src{display:block;margin-top:4px;font:12px var(--mono)}
.why{font-size:13px;color:var(--mute)}.pv{color:var(--bad);font-weight:600}
details.trace{margin-top:6px}details.trace summary{cursor:pointer;font-size:12.5px;color:var(--mute);list-style:none}
details.trace summary::before{content:"▸ ";font-size:10px}details.trace[open] summary::before{content:"▾ "}
ol.steps{list-style:none;margin:8px 0 2px;padding:0 0 0 4px;position:relative}
ol.steps li{position:relative;padding:0 0 10px 22px;font-size:13px;color:var(--mute)}
ol.steps li::before{content:"";position:absolute;left:4px;top:7px;width:8px;height:8px;border-radius:50%;background:var(--line)}
ol.steps li::after{content:"";position:absolute;left:7.5px;top:17px;bottom:-2px;width:1px;background:var(--hair)}
ol.steps li:last-child::after{display:none}
ol.steps li b{color:var(--ink);font-weight:600;margin-right:6px}
ol.steps li.ok::before{background:var(--acc)}ol.steps li.warn::before{background:var(--warn)}
ol.steps li.stop::before{background:var(--bad)}ol.steps li.wait::before{background:var(--bg);outline:1.5px solid var(--faint)}
.act{display:flex;gap:6px;align-items:flex-start;flex-wrap:wrap;justify-content:flex-end;max-width:300px}
.act input{width:150px;padding:5px 8px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink);font:inherit;font-size:13px}
.row.accept{box-shadow:inset 3px 0 var(--acc)}.row.reject{box-shadow:inset 3px 0 var(--bad)}
details.quiet>summary{padding:10px 16px;border-top:1px solid var(--hair);cursor:pointer;color:var(--acc-strong);font-size:13px;list-style:none}
#refused h3{font-size:15px;margin:32px 0 8px}
.rg{border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:8px 0;box-shadow:var(--shadow)}
.empty{color:var(--mute);padding:40px 0;text-align:center}
@media (max-width:860px){.app{grid-template-columns:1fr}aside{position:static;height:auto}.stats{grid-template-columns:1fr}
.row{grid-template-columns:1fr}.act{justify-content:flex-start;max-width:none}.top,.list{padding-left:16px;padding-right:16px}}
</style></head><body>
<div class="app">
<aside>
  <div class="brand"><i></i>Atlas Receipts</div>
  <div class="nav" id="nav"></div>
  <div class="side-h">What the statuses mean</div>
  <p class="side-p"><span class="dot d-supported"></span>Supported: code found the sentence on the org's own page.<br>
  <span class="dot d-contradicted"></span>Contradicted: the page says something else.<br>
  <span class="dot d-silent"></span>Silent: nothing found. Needs review.<br>
  <span class="dot d-inferred"></span>Inferred: Claude's reading of a sentence. Not verified.<br>
  <span class="dot d-refused"></span>Refused: not allowed to collect, or the suggested sentence is not on the page.</p>
  <div class="side-h">How it decides</div>
  <p class="side-p">Claude may suggest. Code checks every quote against the saved page. A person decides. Nothing is written to the Atlas without Accept.</p>
  <div class="side-h">Data</div>
  <p class="side-p">Mass AI Atlas, The Open Accelerator, CC BY 4.0. <span id="gen"></span></p>
</aside>
<main>
  <div class="top">
    <div class="stats">
      <div class="stat"><div class="k">Probe 8: claims with a receipt, verified by code</div><div class="v"><span class="from">0 → </span><span id="p8"></span> <small>/ <span id="tot"></span></small></div></div>
      <div class="stat"><div class="k">Carry a sentence from the org's own page</div><div class="v"><span id="p8b"></span> <small>incl. inferred</small></div></div>
      <div class="stat"><div class="k">Needs a person</div><div class="v"><span id="nr"></span> <small><span id="nd">0</span> decided</small></div></div>
    </div>
    <div class="tools"><input type="search" id="q" placeholder="Find an organization or id, for example techstars">
      <button id="dl" class="btn primary">Download decisions.json</button></div>
  </div>
  <div class="list"><div id="list"></div><section id="refused"></section></div>
</main>
</div>
<script id="data" type="application/json">/*DATA*/</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ORDER=['contradicted','refused','silent','inferred','supported'];
const LABEL={supported:'Supported',contradicted:'Contradicted',silent:'Silent',inferred:'Inferred, not verified',refused:'Refused'};
let filter='problems',q='';
let dec={};try{dec=JSON.parse(localStorage.getItem('receipts-decisions')||'{}')}catch(e){}
const c=D.head.counts,T=D.head.total,fmt=n=>(n||0).toLocaleString();
const save=()=>{try{localStorage.setItem('receipts-decisions',JSON.stringify(dec))}catch(e){};document.getElementById('nd').textContent=Object.keys(dec).length};
document.getElementById('p8').textContent=fmt(c.supported);
document.getElementById('p8b').textContent=fmt((c.supported||0)+(c.inferred||0));
document.getElementById('tot').textContent=fmt(T);
document.getElementById('nr').textContent=fmt(T-(c.supported||0)-(c.refused||0));
document.getElementById('gen').textContent='Pages fetched up to '+D.head.generated+'.';
const NAV=[['problems','Needs review',T-(c.supported||0)],...ORDER.map(s=>[s,LABEL[s].split(',')[0],c[s]||0]),['all','All claims',T]];
const nav=document.getElementById('nav');
nav.innerHTML=NAV.map(([k,l,n])=>`<button data-f="${k}" aria-pressed="${k===filter}"><span><span class="dot d-${k}"></span>${esc(l)}</span><span class="n">${fmt(n)}</span></button>`).join('');
nav.onclick=e=>{const b=e.target.closest('button');if(!b)return;filter=b.dataset.f;nav.querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',x===b));render()};
document.getElementById('q').oninput=e=>{q=e.target.value.trim().toLowerCase();render()};
function rowHtml(r){
  const d=dec[r.key]||{};
  let b=`<div><span class="field">${esc(r.field)}</span><span class="val">${esc(r.value)}</span></div>`;
  if(r.quote&&r.status!=='refused')b+=`<div class="quote">“${esc(r.quote)}”<a class="src" href="${esc(r.link)}" target="_blank" rel="noopener" title="Open the page with this sentence highlighted">↗ ${esc(r.url.replace(/^https?:\/\//,''))} · ${esc(r.fetched)}</a></div>`;
  if(r.status==='refused'&&r.quote)b+=`<div class="quote">Suggested, not on the page: “${esc(r.quote)}”</div>`;
  if(r.status==='contradicted'&&r.page_value)b+=`<div class="why">Atlas: <b>${esc(r.value)}</b> · page: <span class="pv">${esc(r.page_value)}</span></div>`;
  else b+=`<div class="why">${esc(r.reason)}</div>`;
  b+=`<details class="trace"><summary>How this was checked</summary><ol class="steps">${r.trace.map(([s,t,x])=>`<li class="${s}"><b>${esc(t)}</b>${esc(x)}${t==='Fetched'&&r.searched&&r.searched.length>1?'<br>'+r.searched.map(u=>`<a class="mono" href="${esc(u)}" target="_blank" rel="noopener">${esc(u.replace(/^https?:\/\//,''))}</a>`).join(' · '):''}</li>`).join('')}</ol></details>`;
  const editable=['contradicted','silent','inferred'].includes(r.status)&&['deadline','place','live','fact'].includes(r.field);
  const act=r.planted?'<span class="why">Test data, cannot be applied</span>':r.status==='refused'?'<span class="why">Nothing to decide</span>':
    `${editable?`<input placeholder="Corrected value" data-k="${esc(r.key)}" value="${esc(d.new_value||'')}">`:''}
     <button class="btn ${d.decision==='accept'?'on-accept':''}" data-k="${esc(r.key)}" data-d="accept">${r.status==='supported'?'Confirm':'Accept'}</button>
     <button class="btn ${d.decision==='reject'?'on-reject':''}" data-k="${esc(r.key)}" data-d="reject">Reject</button>`;
  return `<div class="row ${d.decision||''}"><div><span class="pill p-${r.status}">${LABEL[r.status]}</span></div><div>${b}</div><div class="act">${act}</div></div>`;
}
function render(){
  const by={};
  for(const r of D.rows){if(q&&!(r.id.toLowerCase().includes(q)||r.name.toLowerCase().includes(q)))continue;(by[r.id]=by[r.id]||[]).push(r)}
  const worst=rs=>Math.min(...rs.map(r=>ORDER.indexOf(r.status)));
  const ids=Object.keys(by).sort((a,b)=>worst(by[a])-worst(by[b])||a.localeCompare(b));
  let html='',shown=0;
  for(const id of ids){
    const rs=by[id],sup=rs.filter(r=>r.status==='supported');
    const loud=rs.filter(r=>filter==='all'?r.status!=='supported':filter==='problems'?r.status!=='supported':r.status===filter);
    const quiet=filter==='all'?sup:[];
    if(!loud.length&&!quiet.length)continue;if(++shown>400)break;
    const r0=rs[0],pct=Math.round(100*sup.length/rs.length);
    html+=`<article class="card">${r0.planted?'<div class="test">TEST: planted copy with deliberate errors. Never the real data.</div>':''}
      <div class="card-h"><h2>${esc(r0.name)}</h2><span class="meta"><span class="mono">${esc(id)}</span> · ${esc(r0.cat)} · last checked by a person ${esc(r0.lastVerified||'never')} · ${sup.length} of ${rs.length} verified<span class="bar"><span style="width:${pct}%"></span></span></span></div>
      ${loud.map(rowHtml).join('')}
      ${quiet.length?`<details class="quiet"><summary>${quiet.length} supported, with receipts</summary>${quiet.map(rowHtml).join('')}</details>`:''}</article>`;
  }
  document.getElementById('list').innerHTML=html||'<div class="empty">Nothing here.</div>';
}
document.getElementById('list').onclick=e=>{const b=e.target.closest('button[data-d]');if(!b)return;
  const k=b.dataset.k,cur=dec[k]||{};if(cur.decision===b.dataset.d)delete dec[k];else dec[k]={...cur,key:k,decision:b.dataset.d};save();render()};
document.getElementById('list').oninput=e=>{const i=e.target.closest('input[data-k]');if(!i)return;const k=i.dataset.k;
  dec[k]={...(dec[k]||{key:k,decision:'accept'}),new_value:i.value};if(!i.value)delete dec[k].new_value;save()};
document.getElementById('dl').onclick=()=>{
  const out=Object.values(dec).filter(d=>!d.key.startsWith('planted-')).map(d=>({key:d.key,decision:d.decision,...(d.new_value?{new_value:d.new_value}:{})}));
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(out,null,1)],{type:'application/json'}));a.download='decisions.json';a.click()};
const ref={};for(const r of D.rows.filter(r=>r.status==='refused'))(ref[r.reason]=ref[r.reason]||[]).push(r);
const nref=D.rows.filter(r=>r.status==='refused').length;
document.getElementById('refused').innerHTML=nref?`<h3>Refused (${nref}): what it would not do, and why</h3>`+Object.entries(ref).sort((a,b)=>b[1].length-a[1].length)
  .map(([w,rs])=>`<div class="rg"><b>${rs.length}</b> · ${esc(w)}<div class="why mono">${[...new Set(rs.map(r=>r.id))].map(esc).join(', ')}</div></div>`).join(''):'';
save();render();
</script></body></html>
"""
