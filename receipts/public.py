"""receipts public: the founder-facing view → out/atlas.html, plus the enriched dataset
after/atlas-with-receipts.json (every Atlas entry with a receipt per claim).

The Atlas data is shown as it is; receipts say what the organization's own site backs today.
Nothing is corrected here: a contradiction is shown as "their site says otherwise", with both values.
"""
import json

from receipts.probes import ROOT, load_entries
from receipts.review import SHORTLIST
from receipts.text import highlight_url

FIELDS = ("key", "field", "value", "status", "quote", "url", "fetched_at", "sha256", "reason", "page_value", "by")


def dataset(receipts, entries):
    by = {}
    for r in receipts:
        by.setdefault(r["entry_id"], []).append({k: r[k] for k in FIELDS})
    out = []
    for e in entries:
        claims = by.get(e["id"], [])
        out.append({**e, "receipts": claims,
                    "proven": sum(c["status"] == "supported" for c in claims), "claims": len(claims)})
    return out


def build(receipts, entries=None):
    entries = entries if entries is not None else load_entries()
    data = dataset(receipts, entries)
    (ROOT / "after").mkdir(exist_ok=True)
    (ROOT / "after" / "atlas-with-receipts.json").write_text(json.dumps(
        {"source": "Mass AI Atlas, The Open Accelerator, CC BY 4.0", "entries": data}, indent=1))
    cats = json.loads((ROOT / "data" / "atlas.json").read_text()).get("cats", {})
    slim = []
    for e in data:
        cl = []
        for c in e["receipts"]:
            v = c["value"]
            if isinstance(v, dict):
                v = {"label": v.get("label"), "value": v.get("value")} if "label" in v else \
                    {"label": "Apply by", "value": v["applyBy"] + (f" ({v['applyNote']})" if v.get("applyNote") else "")}
            cl.append({"f": c["field"], "v": v, "s": c["status"], "q": c["quote"] if c["status"] != "refused" else None,
                       "u": highlight_url(c["url"], c["quote"]) if c["quote"] else c["url"],
                       "t": c["fetched_at"][:10], "p": c["page_value"]})
        slim.append({k: e.get(k) for k in ("id", "name", "cat", "loc", "url", "desc", "why", "offers",
                                            "links", "lastVerified", "approx")} | {"c": cl, "proven": e["proven"]})
    blob = json.dumps({"entries": slim, "cats": {k: v["label"] for k, v in cats.items()},
                       "shortlist": SHORTLIST}).replace("</", "<\\/")
    out = ROOT / "out" / "atlas.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(PAGE.replace("/*DATA*/", blob))
    return out


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mass AI Atlas, with receipts</title>
<style>
:root{--bg:#fff;--soft:#f9f9fa;--muted:#f4f5f7;--ink:#1c1d21;--mute:#5d6270;--faint:#6e7380;--line:#e3e5e9;--hair:#eceef1;
--acc:#16a34a;--acc-strong:#15803d;--acc-soft:#e8f7ee;--warn:#a35200;--warn-soft:#fff4e0;--bad:#c62828;--bad-soft:#fdecec;--info:#1f5fbf;
--sans:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;--mono:"JetBrains Mono","SF Mono",Menlo,monospace;
--shadow:0 1px 2px 0 rgb(16 17 20/.05),0 1px 1px 0 rgb(16 17 20/.03);--shadow-lg:0 12px 32px -8px rgb(16 17 20/.18),0 2px 6px rgb(16 17 20/.06)}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.55 var(--sans);-webkit-font-smoothing:antialiased}
a{color:var(--info);text-decoration:none}a:hover{text-decoration:underline}button{font:inherit;color:inherit}
.bar{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--bg) 94%,transparent);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.bar-in{max-width:1240px;margin:0 auto;padding:10px 24px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
.brand{font-weight:650;font-size:15px}.brand small{font-weight:400;color:var(--mute);margin-left:6px}
.pub{font-size:11.5px;font-weight:600;color:var(--acc-strong);background:var(--acc-soft);border-radius:999px;padding:2px 9px}
.grow{flex:1}.admin-link{font-size:12.5px;color:var(--mute)}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:9px;padding:2px;background:var(--muted)}
.seg button{border:0;background:none;padding:5px 12px;border-radius:7px;cursor:pointer;color:var(--mute);font-size:13px;font-weight:500}
.seg button.on{background:var(--bg);color:var(--ink);box-shadow:var(--shadow);font-weight:600}
.wrap{max-width:1240px;margin:0 auto;padding:22px 24px 120px}
h1{font-size:30px;line-height:1.2;margin:6px 0 8px;letter-spacing:-.01em}
.lead{font-size:16px;color:var(--mute);max-width:720px;margin:0 0 14px}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:13px;color:var(--mute);margin:0 0 18px}
.mode-note{border:1px solid var(--line);border-radius:10px;padding:9px 14px;background:var(--soft);font-size:13px;color:var(--mute);margin-bottom:14px}
.mode-note b{color:var(--ink)}
.need{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:10px}
.need .lbl{font-weight:600;margin-right:4px}
.chip{border:1px solid var(--line);background:var(--bg);border-radius:999px;padding:5px 12px;font-size:13px;cursor:pointer;color:var(--mute)}
.chip.on{background:var(--ink);border-color:var(--ink);color:var(--bg);font-weight:600}
.toolbar{display:flex;gap:10px;flex-wrap:wrap;margin:6px 0 14px}
input[type=search],select{padding:8px 11px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink);font:inherit}
input[type=search]{flex:1;min-width:220px}input:focus,select:focus{outline:2px solid var(--acc);outline-offset:-1px}
.count{font-size:12.5px;color:var(--faint);margin-bottom:10px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:14px}
.card{border:1px solid var(--line);border-radius:14px;background:var(--bg);box-shadow:var(--shadow);display:flex;flex-direction:column;overflow:hidden}
.card:hover{box-shadow:var(--shadow-lg)}
.c-main{padding:14px 16px 10px;cursor:pointer;flex:1}
.c-top{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}
.c-top h3{margin:0;font-size:15px;line-height:1.3}
.cat{font-size:11px;color:var(--mute);background:var(--muted);border-radius:6px;padding:1px 7px;white-space:nowrap}
.loc{font-size:12.5px;color:var(--mute);margin:2px 0 6px}
.desc{font-size:13px;color:var(--mute);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;margin:0 0 8px}
.facts{display:flex;flex-direction:column;gap:4px;font-size:13px}
.fact{display:flex;gap:6px;align-items:baseline}.fact .k{color:var(--faint);min-width:78px}
.m{font-weight:700;font-size:12px;width:14px;display:inline-block;text-align:center}
.m-supported{color:var(--acc)}.m-contradicted{color:var(--bad)}.m-inferred{color:var(--warn)}.m-silent,.m-refused,.m-none{color:var(--faint)}
.offers{display:flex;gap:4px;flex-wrap:wrap;margin-top:8px}
.of{font-size:11.5px;border-radius:6px;padding:1px 7px;background:var(--muted);color:var(--mute)}
.of.ok{background:var(--acc-soft);color:var(--acc-strong)}.of.mid{background:var(--warn-soft);color:var(--warn)}
.c-foot{display:flex;justify-content:space-between;align-items:center;padding:9px 16px;border-top:1px solid var(--hair);font-size:12.5px;color:var(--mute);background:var(--soft)}
.meter{display:flex;gap:8px;align-items:center}.meter .bar2{width:70px;height:6px;background:var(--line);border-radius:3px;overflow:hidden}
.meter .bar2 span{display:block;height:100%;background:var(--acc)}
.flag{color:var(--bad);font-weight:600}
.cmp{display:flex;gap:6px;align-items:center;cursor:pointer;user-select:none}
/* drawer */
.scrim{position:fixed;inset:0;background:rgb(15 23 42/.35);z-index:9;display:none}.scrim.on{display:block}
.drawer{position:fixed;top:0;right:0;bottom:0;width:min(640px,100%);background:var(--bg);z-index:10;box-shadow:var(--shadow-lg);transform:translateX(100%);transition:transform .18s;display:flex;flex-direction:column}
.drawer.on{transform:none}.dh{padding:18px 22px;border-bottom:1px solid var(--line)}.dh h2{margin:0 0 4px;font-size:20px}
.db{overflow:auto;padding:6px 22px 40px}
.claim{padding:12px 0;border-top:1px solid var(--hair)}.claim:first-child{border-top:0}
.claim .h{display:flex;gap:8px;align-items:baseline}.claim .k{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--faint)}
.tag{font-size:12px;font-weight:600;border-radius:999px;padding:1px 8px;white-space:nowrap}
.t-supported{color:var(--acc-strong);background:var(--acc-soft)}.t-contradicted{color:var(--bad);background:var(--bad-soft)}
.t-inferred{color:var(--warn);background:var(--warn-soft)}.t-silent,.t-refused,.t-none{color:var(--mute);background:var(--muted)}
.q{margin:6px 0 2px;padding:8px 12px;background:var(--muted);border-radius:8px;font-size:13.5px}
.q a{display:block;font:12px var(--mono);margin-top:4px}
.btn{border:1px solid var(--line);background:var(--bg);border-radius:8px;padding:6px 12px;cursor:pointer;font-size:13px}
.btn.primary{background:var(--ink);color:var(--bg);border-color:var(--ink)}
/* compare */
.tray{position:fixed;left:0;right:0;bottom:0;z-index:6;background:var(--bg);border-top:1px solid var(--line);box-shadow:0 -8px 24px -12px rgb(16 17 20/.2);display:none}
.tray.on{display:block}.tray-in{max-width:1240px;margin:0 auto;padding:10px 24px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.cmpview{position:fixed;inset:5vh 4vw;z-index:11;background:var(--bg);border-radius:16px;box-shadow:var(--shadow-lg);display:none;flex-direction:column}
.cmpview.on{display:flex}.cmpview .db{padding:10px 24px 30px}
table.c{width:100%;border-collapse:collapse;font-size:13.5px}table.c th,table.c td{border-bottom:1px solid var(--hair);padding:9px 10px;text-align:left;vertical-align:top}
table.c th{font-size:12px;color:var(--faint);font-weight:600;width:150px}table.c thead td{font-weight:650;font-size:15px}
.verdict{border-radius:10px;background:var(--soft);border:1px solid var(--line);padding:10px 14px;margin:10px 0 4px;font-size:14px}
.empty{color:var(--mute);padding:40px;text-align:center}
@media (max-width:560px){.bar-in,.wrap{padding-left:16px;padding-right:16px}h1{font-size:24px}}
</style></head><body>
<div class="bar"><div class="bar-in">
  <div class="brand">Mass AI Atlas <small>with receipts</small></div><span class="pub">Public view</span>
  <div class="grow"></div>
  <a class="admin-link" href="review.html" title="For the Atlas maintainer">Maintainer console (admin) →</a>
  <div class="seg" id="mode"><button data-m="before">Before</button><button data-m="after">After</button></div>
</div></div>
<div class="wrap">
  <h1>Find who can help, and see what's proven.</h1>
  <p class="lead">197 Massachusetts AI organizations. For each check size, deadline, address and offer, we show whether the
  organization's own website says it today, with the sentence one click away.</p>
  <div class="legend"><span><span class="m m-supported">✓</span> Proven by their own site</span><span><span class="m m-contradicted">▲</span> Their site says otherwise</span>
  <span><span class="m m-inferred">◐</span> Mentioned on their site, not word for word</span><span><span class="m m-silent">–</span> No source found</span></div>
  <div class="mode-note" id="note"></div>
  <div class="need" id="need"><span class="lbl">I need</span></div>
  <div class="toolbar"><input type="search" id="q" placeholder="Search by name or town">
    <select id="cat"><option value="">All kinds</option></select>
    <select id="sort"><option value="proven">Most proven first</option><option value="name">Name A–Z</option></select>
    <select id="list"><option value="">Everyone</option><option value="shortlist">A founder's shortlist (12 funders)</option><option value="flag">Where their site disagrees</option></select></div>
  <div class="count" id="count"></div>
  <div class="grid" id="grid"></div>
  <p class="count" style="margin-top:30px">Data: Mass AI Atlas, The Open Accelerator, CC BY 4.0. Receipts by Atlas Receipts: each sentence was found on the organization's
  own site and checked by code; a person reviews disagreements. Organizations only. <a href="../after/atlas-with-receipts.json">Download the data with receipts</a></p>
</div>
<div class="tray" id="tray"><div class="tray-in"><b>Compare</b><span id="tray-names" class="count" style="margin:0"></span><div class="grow"></div>
  <button class="btn" id="tray-clear">Clear</button><button class="btn primary" id="tray-go">Compare side by side</button></div></div>
<div class="scrim" id="scrim"></div>
<aside class="drawer" id="drawer"><div class="dh" id="d-h"></div><div class="db" id="d-b"></div></aside>
<div class="cmpview" id="cmpv"><div class="dh" style="display:flex;justify-content:space-between"><h2 style="margin:0">Side by side</h2><button class="btn" id="cmp-x">Close</button></div><div class="db" id="cmp-b"></div></div>
<script id="data" type="application/json">/*DATA*/</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent),$=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const store={get(k,d){try{return JSON.parse(localStorage.getItem(k))??d}catch(e){return d}},set(k,v){try{localStorage.setItem(k,JSON.stringify(v))}catch(e){}}};
let mode=store.get('atlas-mode','after'),need=null,picked=[];
const MARK={supported:'✓',contradicted:'▲',inferred:'◐',silent:'–',refused:'–',none:'–'};
const TAG={supported:'Proven by their site',contradicted:'Their site says otherwise',inferred:'Mentioned on their site',silent:'No source found',refused:'Not checked (site does not allow it)',none:'No source'};
const OFFERS=['funding','mentorship','grants','community','space','talent','customers','compute'];
const st=c=>mode==='before'?'none':c.s;
const val=c=>typeof c.v==='object'&&c.v?c.v.value:c.v;
const lab=c=>({live:'Website',place:'Location',offer:'Offers',link:'Works with',deadline:'Apply by'}[c.f]||(c.v&&c.v.label)||c.f);
const name=id=>(D.entries.find(e=>e.id===id)||{}).name||id;
$('need').innerHTML+=OFFERS.map(o=>`<button class="chip" data-o="${o}">${o}</button>`).join('');
$('cat').innerHTML+=Object.entries(D.cats).map(([k,l])=>`<option value="${k}">${esc(l)}</option>`).join('');
$('need').onclick=e=>{const b=e.target.closest('[data-o]');if(!b)return;need=need===b.dataset.o?null:b.dataset.o;$('need').querySelectorAll('.chip').forEach(x=>x.classList.toggle('on',x.dataset.o===need));render()};
['q','cat','sort','list'].forEach(id=>$(id).oninput=render);
function setMode(m){mode=m;store.set('atlas-mode',m);$('mode').querySelectorAll('button').forEach(b=>b.classList.toggle('on',b.dataset.m===m));
  $('note').innerHTML=m==='before'?'<b>Before:</b> the Atlas today. Each organization has one "last verified" month, and no claim says where it came from.'
  :'<b>After:</b> each claim is marked by what the organization\'s own website says today. Click a card to see the sentence.';render();renderDrawer()}
$('mode').onclick=e=>{const b=e.target.closest('button');if(b)setMode(b.dataset.m)};
function keyFacts(e){
  const pick=[];const cs=e.c.find(c=>c.f==='fact'&&c.v&&c.v.label==='Check size');if(cs)pick.push(cs);
  const dl=e.c.find(c=>c.f==='deadline');if(dl)pick.push(dl);
  const pl=e.c.find(c=>c.f==='place');if(pl)pick.push(pl);
  for(const c of e.c.filter(c=>c.f==='fact'&&c.v&&!['Check size'].includes(c.v.label)))if(pick.length<3)pick.push(c);
  return pick.slice(0,3)}
function card(e){
  const flags=e.c.filter(c=>c.s==='contradicted').length,on=picked.includes(e.id);
  const offers=e.c.filter(c=>c.f==='offer').map(c=>`<span class="of ${mode==='after'?(c.s==='supported'?'ok':c.s==='inferred'?'mid':''):''}">${esc(c.v)}</span>`).join('');
  return `<div class="card"><div class="c-main" data-open="${esc(e.id)}"><div class="c-top"><h3>${esc(e.name)}</h3><span class="cat">${esc(D.cats[e.cat]||e.cat)}</span></div>
    <div class="loc">${esc(e.loc)}</div><p class="desc">${esc(e.desc)}</p>
    <div class="facts">${keyFacts(e).map(c=>`<div class="fact"><span class="m m-${st(c)}" title="${esc(TAG[st(c)])}">${MARK[st(c)]}</span><span class="k">${esc(lab(c))}</span><span>${esc(val(c))}</span></div>`).join('')}</div>
    <div class="offers">${offers}</div></div>
    <div class="c-foot">${mode==='before'?`<span>Last verified ${esc(e.lastVerified)}</span><span>0 of ${e.c.length} sourced</span>`
      :`<span class="meter"><span class="bar2"><span style="width:${100*e.proven/Math.max(1,e.c.length)}%"></span></span>${e.proven} of ${e.c.length} proven${flags?` · <span class="flag">▲ ${flags}</span>`:''}</span>`}
      <label class="cmp"><input type="checkbox" data-pick="${esc(e.id)}" ${on?'checked':''}> Compare</label></div></div>`}
function render(){
  const q=$('q').value.trim().toLowerCase(),cat=$('cat').value,list=$('list').value,SL=new Set(D.shortlist);
  let es=D.entries.filter(e=>(!q||(e.name+' '+e.loc).toLowerCase().includes(q))&&(!cat||e.cat===cat)&&(!need||(e.offers||[]).includes(need))
    &&(list!=='shortlist'||SL.has(e.id))&&(list!=='flag'||e.c.some(c=>c.s==='contradicted')));
  es.sort($('sort').value==='name'||mode==='before'?(a,b)=>a.name.localeCompare(b.name):(a,b)=>b.proven-a.proven||b.proven/Math.max(1,b.c.length)-a.proven/Math.max(1,a.c.length)||a.name.localeCompare(b.name));
  const cl=es.flatMap(e=>e.c),pr=cl.filter(c=>c.s==='supported').length;
  $('count').textContent=`${es.length} organizations · `+(mode==='before'?`0 of ${cl.length} claims have a source`:`${pr} of ${cl.length} claims proven by the organization's own site`);
  $('grid').innerHTML=es.map(card).join('')||'<div class="empty">No organizations match.</div>'}
$('grid').onclick=e=>{const p=e.target.closest('[data-pick]');if(p){togglePick(p.dataset.pick,p.checked);return}const o=e.target.closest('[data-open]');if(o)openE(o.dataset.open)};
/* drawer */
let openId=null;
function openE(id){openId=id;renderDrawer();$('drawer').classList.add('on');$('scrim').classList.add('on')}
function closeAll(){openId=null;['drawer','scrim','cmpv'].forEach(i=>$(i).classList.remove('on'))}
$('scrim').onclick=closeAll;$('cmp-x').onclick=closeAll;document.addEventListener('keydown',e=>{if(e.key==='Escape')closeAll()});
const ORD={contradicted:0,supported:1,inferred:2,silent:3,refused:4};
function claimHtml(c){const s=st(c);
  let h=`<div class="claim"><div class="h"><span class="k">${esc(lab(c))}</span><b>${esc(c.f==='link'?name(val(c)):val(c))}</b></div>
    <div style="margin-top:4px"><span class="tag t-${s}">${MARK[s]} ${TAG[s]}</span></div>`;
  if(mode==='after'&&c.q)h+=`<div class="q">“${esc(c.q)}”<a href="${esc(c.u)}" target="_blank" rel="noopener">See it on their site ↗ · checked ${esc(c.t)}</a></div>`;
  if(mode==='after'&&c.s==='contradicted'&&c.p)h+=`<div class="count" style="margin:4px 0 0">The Atlas says <b>${esc(val(c))}</b>; their site says <b style="color:var(--bad)">${esc(c.p)}</b>. Under review.</div>`;
  return h+'</div>'}
function renderDrawer(){if(!openId)return;const e=D.entries.find(x=>x.id===openId);
  $('d-h').innerHTML=`<div style="display:flex;justify-content:space-between;gap:10px"><div><h2>${esc(e.name)}</h2><div class="count" style="margin:0">${esc(D.cats[e.cat]||e.cat)} · ${esc(e.loc)} · <a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.url.replace(/^https?:\/\//,''))}</a></div></div><button class="btn" onclick="closeAll()">Close</button></div>
    <p class="desc" style="-webkit-line-clamp:unset;margin:10px 0 0">${esc(e.desc)}</p>
    <div class="count" style="margin:8px 0 0">${mode==='before'?`Last verified ${esc(e.lastVerified)} for the whole entry. No claim has a source.`:`${e.proven} of ${e.c.length} claims proven by their own site.`}</div>`;
  $('d-b').innerHTML=e.c.slice().sort((a,b)=>mode==='before'?0:ORD[a.s]-ORD[b.s]).map(claimHtml).join('')}
/* compare */
function togglePick(id,on){picked=picked.filter(x=>x!==id);if(on)picked.push(id);if(picked.length>2)picked=picked.slice(-2);renderTray();render()}
function renderTray(){$('tray').classList.toggle('on',picked.length>0);$('tray-names').textContent=picked.map(name).join(' and ')+(picked.length<2?'  (pick one more)':'');$('tray-go').disabled=picked.length<2}
$('tray-clear').onclick=()=>{picked=[];renderTray();render()};
$('tray-go').onclick=()=>{if(picked.length<2)return;renderCompare();$('cmpv').classList.add('on');$('scrim').classList.add('on')};
function renderCompare(){
  const [a,b]=picked.map(id=>D.entries.find(e=>e.id===id));
  const rows=[['Website',e=>e.c.find(c=>c.f==='live')],['Location',e=>e.c.find(c=>c.f==='place')],
    ...['Check size','Equity','Terms','Stage','Program length','Focus'].map(l=>[l,e=>e.c.find(c=>c.f==='fact'&&c.v&&c.v.label===l)]),
    ['Apply by',e=>e.c.find(c=>c.f==='deadline')]].filter(([l,f])=>f(a)||f(b));
  const cell=c=>c?`<span class="m m-${st(c)}">${MARK[st(c)]}</span> ${esc(val(c))}${mode==='after'&&c.q?`<div class="count" style="margin:3px 0 0">“${esc(c.q.slice(0,120))}${c.q.length>120?'…':''}” <a href="${esc(c.u)}" target="_blank" rel="noopener">↗</a></div>`:''}${mode==='after'&&c.s==='contradicted'?`<div class="count flag" style="margin:3px 0 0">Their site says ${esc(c.p)}</div>`:''}`:'<span class="count">not listed</span>';
  const sc=e=>({p:e.proven,n:e.c.length,x:e.c.filter(c=>c.s==='contradicted').length});const A=sc(a),B=sc(b);
  const less=mode==='before'?null:(A.x!==B.x?(A.x>B.x?a:b):(A.p/A.n<B.p/B.n?a:b));
  $('cmp-b').innerHTML=`${mode==='before'?`<div class="verdict">Before: both show only a "last verified" month (${esc(a.lastVerified)} and ${esc(b.lastVerified)}). There is no way to tell which claims still hold.</div>`
    :`<div class="verdict"><b>${esc(a.name)}</b>: ${A.p} of ${A.n} claims proven${A.x?`, ${A.x} where their site says otherwise`:''}. <b>${esc(b.name)}</b>: ${B.p} of ${B.n} proven${B.x?`, ${B.x} where their site says otherwise`:''}.
      ${less?` Trust <b>${esc(less.name)}</b>'s listing less: ${less===a?(A.x>B.x?'its own site disagrees with it':'fewer of its claims are backed by its own site'):(B.x>A.x?'its own site disagrees with it':'fewer of its claims are backed by its own site')}.`:''}</div>`}
    <table class="c"><thead><tr><th></th><td>${esc(a.name)}</td><td>${esc(b.name)}</td></tr></thead><tbody>${rows.map(([l,f])=>`<tr><th>${l}</th><td>${cell(f(a))}</td><td>${cell(f(b))}</td></tr>`).join('')}</tbody></table>`}
setMode(mode);renderTray();
</script></body></html>
"""
