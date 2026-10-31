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


def rows(receipts, entries):
    meta = {e["id"]: e for e in entries}
    out = []
    for r in receipts:
        e = meta.get(r["entry_id"], {})
        v = r["value"]
        if isinstance(v, dict):
            v = " — ".join(str(x) for x in v.values() if x)
        out.append({
            "key": r["key"], "id": r["entry_id"], "name": r["name"], "field": r["field"],
            "value": str(v), "status": r["status"], "quote": r["quote"], "reason": r["reason"],
            "page_value": r["page_value"], "url": r["url"],
            "link": highlight_url(r["url"], r["quote"]) if r["quote"] else r["url"],
            "fetched": r["fetched_at"][:16].replace("T", " ") + "Z", "searched": r["searched"],
            "by": r["by"], "cat": e.get("cat", ""), "lastVerified": e.get("lastVerified", ""),
            "planted": r["entry_id"].startswith("planted-"),
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
:root{--bg:#fafaf8;--card:#fff;--ink:#1c1c1a;--mute:#6b6a65;--line:#e4e2dc;--ok:#1f7a4d;--okbg:#e8f4ec;
--bad:#b42318;--badbg:#fdecea;--sil:#5f5e5a;--silbg:#efeee9;--inf:#9a5b00;--infbg:#fdf3e1;--ref:#2b2b2b;--refbg:#e2e1dd;
--acc:#1d4ed8;--test:#7c2d12;--testbg:#ffedd5}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#151514;--card:#1e1e1c;--ink:#ecebe6;--mute:#a3a29c;--line:#34332f;
--ok:#6fcf97;--okbg:#17301f;--bad:#ff8a80;--badbg:#3a1714;--sil:#b8b7b0;--silbg:#2a2a27;--inf:#f5b54a;--infbg:#3a2a0d;
--ref:#e2e1dd;--refbg:#3a3a36;--acc:#8ab4ff;--test:#fdba74;--testbg:#431407}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
header{position:sticky;top:0;z-index:2;background:var(--bg);border-bottom:1px solid var(--line);padding:14px 16px 10px}
.wrap{max-width:1040px;margin:0 auto}
h1{font-size:20px;margin:0 0 2px}h1 small{font-weight:400;color:var(--mute);font-size:13px;margin-left:8px}
.probe{font-size:15px;margin:6px 0}.probe b{font-size:22px}.probe .arrow{color:var(--mute);margin:0 6px}
.counts{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}
.chip{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:999px;padding:3px 10px;font-size:13px;cursor:pointer}
.chip[aria-pressed=true]{border-color:var(--ink);font-weight:600}
.tools{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
input[type=search]{flex:1;min-width:180px;padding:7px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink);font-size:14px}
button{font:inherit;font-size:13px;border-radius:7px;border:1px solid var(--line);background:var(--card);color:var(--ink);padding:5px 10px;cursor:pointer}
button.primary{background:var(--acc);border-color:var(--acc);color:#fff}
.legend{font-size:12.5px;color:var(--mute);margin-top:6px}
main{padding:12px 16px 60px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;margin:12px 0;overflow:hidden}
.card h2{font-size:16px;margin:0;padding:10px 14px;display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;border-bottom:1px solid var(--line)}
.card h2 .meta{font-weight:400;font-size:12.5px;color:var(--mute)}
.test{background:var(--testbg);color:var(--test);font-weight:700;padding:6px 14px;font-size:13px}
.row{display:grid;grid-template-columns:180px 1fr auto;gap:10px;padding:9px 14px;border-top:1px solid var(--line)}
.row:first-of-type{border-top:0}
.badge{display:inline-block;font-size:12px;font-weight:600;border-radius:6px;padding:2px 7px;white-space:nowrap}
.s-supported{color:var(--ok);background:var(--okbg)}.s-contradicted{color:var(--bad);background:var(--badbg)}
.s-silent{color:var(--sil);background:var(--silbg)}.s-inferred{color:var(--inf);background:var(--infbg)}
.s-refused{color:var(--ref);background:var(--refbg)}
.field{font-size:12px;color:var(--mute);text-transform:uppercase;letter-spacing:.04em}
.val{font-weight:600}
.quote{margin:4px 0 2px;padding-left:10px;border-left:3px solid var(--line)}
.quote a{color:var(--acc);text-decoration:none;margin-left:4px;white-space:nowrap}
.why{font-size:13px;color:var(--mute)}.pv{color:var(--bad);font-weight:600}
.searched{font-size:12px;color:var(--mute);word-break:break-all}
.act{display:flex;gap:6px;align-items:flex-start;flex-wrap:wrap;justify-content:flex-end}
.act input{width:150px;padding:4px 6px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--ink);font-size:13px}
.row.accepted{box-shadow:inset 4px 0 var(--ok)}.row.rejected{box-shadow:inset 4px 0 var(--bad);opacity:.7}
button.on{border-color:var(--ink);font-weight:700}
.quiet{padding:8px 14px;font-size:13px;color:var(--ok);border-top:1px solid var(--line);cursor:pointer}
.quiet .row{cursor:auto}
#refused h2{font-size:17px;margin:28px 0 6px}
.reason-group{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:8px 0}
.empty{color:var(--mute);padding:30px 0;text-align:center}
@media (max-width:640px){.row{grid-template-columns:1fr}.act{justify-content:flex-start}}
</style></head><body>
<header><div class="wrap">
<h1>Atlas Receipts <small id="gen"></small></h1>
<div class="probe">Probe 8, claims with a receipt (verified by code): <b>0</b><span class="arrow">→</span><b id="p8"></b> / <span id="tot"></span>
 · <span id="p8b"></span> carry a sentence from the org's own page</div>
<div class="counts" id="counts"></div>
<div class="tools"><input type="search" id="q" placeholder="Find an organization or id (e.g. techstars)">
<button id="dl" class="primary">Download decisions.json (<span id="nd">0</span>)</button></div>
<div class="legend"><b>supported</b> = code found the sentence on the org's page ·
<b>contradicted</b> = the page says something else ·
<b>silent</b> = nothing found, needs review ·
<b>inferred</b> = a model's reading, not verified ·
<b>refused</b> = not allowed to collect, or the model's sentence is not on the page.
↗ opens the page with the sentence highlighted.</div>
</div></header>
<main><div class="wrap"><div id="list"></div><section id="refused"></section></div></main>
<script id="data" type="application/json">/*DATA*/</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ORDER=['contradicted','refused','silent','inferred','supported'];
const LABEL={supported:'● supported',contradicted:'▲ contradicted',silent:'○ silent',inferred:'◐ inferred — not verified',refused:'■ refused'};
let filter='problems',q='';
let dec={};try{dec=JSON.parse(localStorage.getItem('receipts-decisions')||'{}')}catch(e){}
const save=()=>{try{localStorage.setItem('receipts-decisions',JSON.stringify(dec))}catch(e){};document.getElementById('nd').textContent=Object.keys(dec).length};
const c=D.head.counts;
document.getElementById('p8').textContent=(c.supported||0).toLocaleString();
document.getElementById('p8b').textContent=((c.supported||0)+(c.inferred||0)).toLocaleString();
document.getElementById('tot').textContent=D.head.total.toLocaleString();
document.getElementById('gen').textContent='pages fetched up to '+D.head.generated;
const chips=[['problems','Needs review',D.head.total-(c.supported||0)],...ORDER.map(s=>[s,s,c[s]||0]),['all','all',D.head.total]];
document.getElementById('counts').innerHTML=chips.map(([k,l,n])=>`<button class="chip" data-f="${k}" aria-pressed="${k===filter}">${esc(l)} ${n.toLocaleString()}</button>`).join('');
document.getElementById('counts').onclick=e=>{const b=e.target.closest('.chip');if(!b)return;filter=b.dataset.f;
  document.querySelectorAll('.chip').forEach(x=>x.setAttribute('aria-pressed',x===b));render()};
document.getElementById('q').oninput=e=>{q=e.target.value.trim().toLowerCase();render()};
function rowHtml(r){
  const d=dec[r.key]||{};
  let body=`<div><span class="field">${esc(r.field)}</span> <span class="val">${esc(r.value)}</span></div>`;
  if(r.quote&&r.status!=='refused')body+=`<div class="quote">“${esc(r.quote)}” <a href="${esc(r.link)}" target="_blank" rel="noopener" title="Open the page with this sentence highlighted">↗ ${esc(r.fetched)}</a></div>`;
  if(r.status==='refused'&&r.quote)body+=`<div class="quote">model offered: “${esc(r.quote)}” <span class="why">(not on <a href="${esc(r.url)}" target="_blank" rel="noopener">the page</a>)</span></div>`;
  if(r.page_value&&r.status==='contradicted')body+=`<div>Atlas: <b>${esc(r.value)}</b> · page: <span class="pv">${esc(r.page_value)}</span></div>`;
  body+=`<div class="why">${esc(r.reason)}${r.status!=='supported'&&!r.quote?` · <a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.fetched)}</a>`:''}</div>`;
  if(r.status==='silent'&&r.searched&&r.searched.length)body+=`<div class="searched">searched: ${r.searched.map(u=>`<a href="${esc(u)}" target="_blank" rel="noopener">${esc(u.replace(/^https?:\/\//,''))}</a>`).join(' · ')}</div>`;
  const editable=['contradicted','silent','inferred'].includes(r.status)&&['deadline','place','live','fact'].includes(r.field);
  const act=r.planted?'<span class="why">test data: cannot be applied</span>':
    r.status==='refused'?'<span class="why">nothing collected, nothing to decide</span>':
    `${editable?`<input placeholder="new value (optional)" data-k="${esc(r.key)}" value="${esc(d.new_value||'')}">`:''}
     <button data-k="${esc(r.key)}" data-d="accept" class="${d.decision==='accept'?'on':''}">${r.status==='supported'?'Confirm':'Accept'}</button>
     <button data-k="${esc(r.key)}" data-d="reject" class="${d.decision==='reject'?'on':''}">Reject</button>`;
  return `<div class="row ${d.decision?d.decision+'ed':''}"><div><span class="badge s-${r.status}">${LABEL[r.status]}</span><div class="why">${r.by==='model'?'model reading':''}</div></div><div>${body}</div><div class="act">${act}</div></div>`;
}
function render(){
  const by={};
  for(const r of D.rows){
    if(q&&!(r.id.toLowerCase().includes(q)||r.name.toLowerCase().includes(q)))continue;
    (by[r.id]=by[r.id]||[]).push(r);
  }
  const worst=rs=>Math.min(...rs.map(r=>ORDER.indexOf(r.status)));
  const ids=Object.keys(by).sort((a,b)=>worst(by[a])-worst(by[b])||a.localeCompare(b));
  let html='',shown=0;
  for(const id of ids){
    const rs=by[id];
    const vis=rs.filter(r=>filter==='all'?true:filter==='problems'?r.status!=='supported':r.status===filter);
    if(!vis.length)continue;shown++;
    const r0=rs[0],sup=rs.filter(r=>r.status==='supported');
    const loud=filter==='problems'?vis:vis.filter(r=>r.status!=='supported'||filter==='supported');
    const quiet=filter==='all'?sup:[];
    html+=`<article class="card">${r0.planted?'<div class="test">TEST — planted (a test copy with deliberate errors; never the real data)</div>':''}
      <h2>${esc(r0.name)} <span class="meta">${esc(id)} · ${esc(r0.cat)} · last verified by a person: ${esc(r0.lastVerified||'–')} · ${sup.length} of ${rs.length} claims verified</span></h2>
      ${loud.filter(r=>filter==='all'?r.status!=='supported':true).map(rowHtml).join('')}
      ${quiet.length?`<details class="quiet"><summary>● ${quiet.length} supported, with receipts</summary>${quiet.map(rowHtml).join('')}</details>`:''}</article>`;
    if(shown>=400)break;
  }
  document.getElementById('list').innerHTML=html||'<div class="empty">Nothing here.</div>';
}
document.getElementById('list').onclick=e=>{const b=e.target.closest('button[data-d]');if(!b)return;
  const k=b.dataset.k,cur=dec[k]||{};
  if(cur.decision===b.dataset.d)delete dec[k];else dec[k]={...cur,key:k,decision:b.dataset.d};
  save();render()};
document.getElementById('list').oninput=e=>{const i=e.target.closest('input[data-k]');if(!i)return;
  const k=i.dataset.k;dec[k]={...(dec[k]||{key:k,decision:'accept'}),new_value:i.value};if(!i.value)delete dec[k].new_value;save()};
document.getElementById('dl').onclick=()=>{
  const out=Object.values(dec).filter(d=>!d.key.startsWith('planted-')).map(d=>({key:d.key,decision:d.decision,...(d.new_value?{new_value:d.new_value}:{})}));
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(out,null,1)],{type:'application/json'}));
  a.download='decisions.json';a.click()};
// refused, grouped by reason
const ref={};for(const r of D.rows.filter(r=>r.status==='refused'))(ref[r.reason]=ref[r.reason]||[]).push(r);
document.getElementById('refused').innerHTML=Object.keys(ref).length?`<h2>Refused (${D.rows.filter(r=>r.status==='refused').length}): what it would not do, and why</h2>`+
  Object.entries(ref).sort((a,b)=>b[1].length-a[1].length).map(([why,rs])=>`<div class="reason-group"><b>${rs.length}</b> · ${esc(why)}<div class="why">${[...new Set(rs.map(r=>r.id))].map(esc).join(', ')}</div></div>`).join(''):'';
save();render();
</script></body></html>
"""
