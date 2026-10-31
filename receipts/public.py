"""receipts public: the founder-facing view → out/atlas.html, plus the enriched dataset
after/atlas-with-receipts.json (every Atlas entry with a receipt per claim).

The Atlas data is shown as it is; receipts say what the organization's own site backs today.
Nothing is corrected here: a contradiction is shown as "their site says otherwise", with both values.
"""
import json
import subprocess
import sys

from receipts.claims import no_contact
from receipts.probes import ROOT, load_entries
from receipts.review import SHORTLIST
from receipts.text import highlight_url

FIELDS = ("key", "field", "value", "status", "quote", "url", "fetched_at", "sha256", "reason", "page_value", "by")

# Worst claim status for the map pin (lower = worse trust).
TRUST_RANK = {"contradicted": 0, "inferred": 1, "silent": 2, "refused": 2, "none": 2, "supported": 3}


def dataset(receipts, entries):
    by = {}
    for r in receipts:
        by.setdefault(r["entry_id"], []).append({k: r[k] for k in FIELDS})
    out = []
    for e in entries:
        claims = by.get(e["id"], [])
        e = {**e, "desc": no_contact(e.get("desc", "")), "why": no_contact(e.get("why", "")),
             "applyNote": no_contact(e.get("applyNote", ""))}
        out.append({**e, "receipts": claims,
                    "proven": sum(c["status"] == "supported" for c in claims), "claims": len(claims)})
    return out


def _label(c):
    v = c["value"]
    if c["field"] == "live":
        return "Website"
    if c["field"] == "place":
        return "Location"
    if c["field"] == "offer":
        return "Offers"
    if c["field"] == "link":
        return "Works with"
    if c["field"] == "deadline":
        return "Apply by"
    if isinstance(v, dict) and v.get("label"):
        return v["label"]
    return c["field"]


def _val(c):
    v = c["value"]
    if isinstance(v, dict):
        if "label" in v:
            return v.get("value")
        if "applyBy" in v:
            return v["applyBy"] + (f" ({v['applyNote']})" if v.get("applyNote") else "")
    return v


def _trust(statuses):
    if not statuses:
        return "silent"
    worst = min(statuses, key=lambda s: TRUST_RANK.get(s, 2))
    return "silent" if worst in ("refused", "none") else worst


def _metrics(n_entries):
    path = ROOT / "after" / "metrics.json"
    if not path.exists():
        subprocess.run([sys.executable, "-m", "receipts", "metrics"], check=False, cwd=ROOT)
    if not path.exists():
        return {"verified": 0, "with_sentence": 0, "needs_person": 0, "entities": n_entries}
    m = json.loads(path.read_text(encoding="utf-8"))
    all_ = m.get("all") or {}
    return {
        "verified": all_.get("supported", 0),
        "with_sentence": all_.get("with_sentence", 0),
        "needs_person": all_.get("needs_person", 0),
        "entities": m.get("entities", n_entries),
    }


def build(receipts, entries=None):
    entries = entries if entries is not None else load_entries()
    data = dataset(receipts, entries)
    (ROOT / "after").mkdir(exist_ok=True)
    (ROOT / "after" / "atlas-with-receipts.json").write_text(json.dumps(
        {"source": "Mass AI Atlas, The Open Accelerator, CC BY 4.0", "entries": data}, indent=1))
    cats = json.loads((ROOT / "data" / "atlas.json").read_text(encoding="utf-8")).get("cats", {})
    slim = []
    for e in data:
        cl = []
        for c in e["receipts"]:
            s = c["status"]
            pin_s = "silent" if s in ("refused", "none") else s
            cl.append({
                "k": _label(c),
                "v": _val(c),
                "s": pin_s,
                "q": c["quote"] if s != "refused" else None,
                "u": highlight_url(c["url"], c["quote"]) if c.get("quote") else c["url"],
                "t": (c.get("fetched_at") or "")[:10],
                "p": c.get("page_value"),
                "raw": s,
            })
        trust = _trust([c["s"] for c in cl] or ["silent"])
        row = {
            "id": e["id"], "name": e["name"], "cat": e.get("cat"), "loc": e.get("loc"),
            "lat": e.get("lat"), "lng": e.get("lng"), "url": e.get("url"),
            "desc": no_contact(e.get("desc") or ""), "offers": e.get("offers") or [],
            "tags": e.get("tags") or [], "approx": bool(e.get("approx")),
            "trust": trust, "proven": e["proven"], "total": len(cl), "claims": cl,
        }
        if row["lat"] is None or row["lng"] is None:
            continue
        slim.append(row)
    offers = sorted({o for e in slim for o in e["offers"]})
    blob = json.dumps({
        "entries": slim,
        "cats": {k: v["label"] for k, v in cats.items()},
        "shortlist": SHORTLIST,
        "offers": offers,
        "metrics": _metrics(len(slim)),
    }).replace("</", "<\\/")
    out = ROOT / "out" / "atlas.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(PAGE.replace("/*DATA*/", blob), encoding="utf-8")
    return out


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mass AI Atlas, with receipts</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&family=Syne:wght@600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
:root {
  --ink: #1a2330;
  --ink-soft: #3d4a5c;
  --mute: #5c6b7e;
  --faint: #8a96a6;
  --line: #d5dde6;
  --panel: rgba(248, 250, 252, 0.92);
  --panel-solid: #f7f9fb;
  --water: #c9d9e6;
  --acc: #1f7a4c;
  --acc-soft: #e4f3ea;
  --warn: #9a6700;
  --bad: #b42318;
  --silent: #7a8696;
  --brand: #0f3d5c;
  --shadow: 0 10px 40px rgba(26, 35, 48, 0.12);
  --sans: "Instrument Sans", ui-sans-serif, sans-serif;
  --display: "Syne", ui-sans-serif, sans-serif;
  --ease: cubic-bezier(0.22, 1, 0.36, 1);
  --dur: 260ms;
}
* { box-sizing: border-box; }
html, body { height: 100%; margin: 0; }
body {
  color: var(--ink);
  font: 15px/1.5 var(--sans);
  background:
    radial-gradient(1200px 700px at 18% 12%, #dfeaf2 0%, transparent 55%),
    radial-gradient(900px 600px at 88% 78%, #e4ebe3 0%, transparent 50%),
    linear-gradient(165deg, #edf2f6 0%, #e6ece8 48%, #e9eef3 100%);
  -webkit-font-smoothing: antialiased;
  overflow: hidden;
}
a { color: var(--brand); }
button { font: inherit; color: inherit; }

.app {
  position: relative;
  height: 100%;
  width: 100%;
}
#map {
  position: absolute;
  inset: 0;
  z-index: 0;
  background: var(--water);
}

.vignette {
  pointer-events: none;
  position: absolute;
  inset: 0;
  z-index: 1;
  background:
    linear-gradient(90deg, rgba(237,242,246,0.88) 0%, rgba(237,242,246,0.55) 220px, rgba(237,242,246,0) 420px),
    linear-gradient(180deg, rgba(237,242,246,0.55) 0%, transparent 90px);
}

.chrome {
  position: absolute;
  z-index: 2;
  top: 20px;
  left: 20px;
  width: min(360px, calc(100vw - 40px));
  padding: 22px 22px 18px;
  background: var(--panel);
  backdrop-filter: blur(14px);
  border: 1px solid rgba(213, 221, 230, 0.9);
  border-radius: 4px;
  box-shadow: var(--shadow);
  animation: chrome-in 480ms var(--ease) both;
}
@keyframes chrome-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: none; }
}
.brand {
  font-family: var(--display);
  font-weight: 800;
  font-size: 28px;
  letter-spacing: -0.03em;
  line-height: 1.05;
  color: var(--brand);
  margin: 0 0 6px;
}
.brand span {
  display: block;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--mute);
  margin-top: 8px;
  font-family: var(--sans);
}
.lede {
  margin: 10px 0 0;
  color: var(--ink-soft);
  font-size: 14.5px;
  max-width: 32ch;
}
.filter {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--line);
}
.filter label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--faint);
  margin-bottom: 8px;
}
.filter select {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 3px;
  background: #fff;
  color: var(--ink);
  font: inherit;
}
.legend {
  margin-top: 14px;
  display: grid;
  gap: 7px;
  font-size: 12.5px;
  color: var(--mute);
  opacity: 0;
  transform: translateY(6px);
  animation: legend-in 420ms var(--ease) 180ms forwards;
}
@keyframes legend-in {
  to { opacity: 1; transform: none; }
}
.legend i {
  display: inline-block;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  margin-right: 8px;
  vertical-align: middle;
  border: 1.5px solid transparent;
}
.legend .proven i { background: var(--acc); }
.legend .inferred i { background: #e8b84a; border-color: #c9921a; }
.legend .disagree i { background: var(--bad); }
.legend .silent i { background: #c5ced8; border-color: var(--silent); }
.hint {
  margin-top: 12px;
  font-size: 12px;
  color: var(--faint);
}
.map-stack {
  margin-top: 10px;
  font-size: 11.5px;
  color: var(--faint);
  line-height: 1.4;
}

.trust-note {
  position: absolute;
  z-index: 2;
  bottom: 24px;
  left: 20px;
  max-width: 340px;
  font-size: 12px;
  color: var(--mute);
  background: rgba(247,249,251,0.85);
  backdrop-filter: blur(8px);
  padding: 10px 12px;
  border-left: 3px solid var(--brand);
  animation: chrome-in 480ms var(--ease) 120ms both;
}
.trust-note b { color: var(--ink); font-weight: 600; }

.pin {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid #fff;
  box-shadow: 0 1px 4px rgba(26,35,48,0.35);
  cursor: pointer;
  transition: transform var(--dur) var(--ease), box-shadow var(--dur) var(--ease), opacity var(--dur) ease;
}
.pin:hover, .pin.on {
  transform: scale(1.4);
  box-shadow: 0 0 0 4px rgba(15, 61, 92, 0.18), 0 1px 4px rgba(26,35,48,0.35);
}
.pin.supported { background: var(--acc); }
.pin.inferred { background: #e8b84a; }
.pin.contradicted { background: var(--bad); }
.pin.silent { background: #b7c0cb; }
.pin.approx { outline: 1px dashed rgba(26,35,48,0.35); outline-offset: 2px; }
.pin.dim { opacity: 0.28; transform: scale(0.92); }

.scrim {
  position: fixed;
  inset: 0;
  z-index: 8;
  background: rgba(26, 35, 48, 0.22);
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transition: opacity var(--dur) ease, visibility var(--dur) ease;
}
.scrim.on {
  opacity: 1;
  visibility: visible;
  pointer-events: auto;
}
.drawer {
  position: fixed;
  top: 0; right: 0; bottom: 0;
  width: min(420px, 100%);
  z-index: 9;
  background: var(--panel-solid);
  border-left: 1px solid var(--line);
  box-shadow: -12px 0 40px rgba(26,35,48,0.1);
  transform: translateX(100%);
  opacity: 0;
  transition: transform var(--dur) var(--ease), opacity var(--dur) ease;
  display: flex;
  flex-direction: column;
  pointer-events: none;
}
.drawer.on {
  transform: none;
  opacity: 1;
  pointer-events: auto;
}
.dh {
  padding: 22px 22px 14px;
  border-bottom: 1px solid var(--line);
}
.dh h2 {
  font-family: var(--display);
  font-size: 22px;
  letter-spacing: -0.02em;
  margin: 0 0 4px;
  line-height: 1.2;
}
.meta { font-size: 13px; color: var(--mute); }
.db { overflow: auto; padding: 8px 22px 32px; flex: 1; }
.claim {
  padding: 14px 0;
  border-top: 1px solid #e8edf2;
}
.claim:first-child { border-top: 0; }
.claim .k {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--faint);
  margin-bottom: 2px;
}
.claim .v { font-weight: 600; font-size: 15px; }
.status {
  display: inline-block;
  margin-top: 6px;
  font-size: 12px;
  font-weight: 600;
  padding: 2px 0;
}
.status.supported { color: var(--acc); }
.status.inferred { color: var(--warn); }
.status.contradicted { color: var(--bad); }
.status.silent { color: var(--silent); }
.quote {
  margin: 8px 0 0;
  padding: 10px 12px;
  background: #eef3f7;
  border-left: 3px solid var(--brand);
  font-size: 13.5px;
  color: var(--ink-soft);
  font-style: italic;
}
.quote a {
  display: block;
  margin-top: 6px;
  font-style: normal;
  font-size: 12px;
  font-weight: 500;
}
.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}
.tag {
  font-size: 11.5px;
  color: var(--mute);
  border: 1px solid var(--line);
  background: #fff;
  padding: 2px 8px;
  border-radius: 3px;
}
.suggest {
  margin-top: 14px;
  padding: 12px 12px 10px;
  background: #eef3f7;
  border: 1px solid var(--line);
  border-radius: 3px;
}
.suggest .lbl {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--faint);
  margin-bottom: 8px;
}
.suggest .row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.suggest button.linkish {
  border: 0;
  background: none;
  padding: 0;
  color: var(--brand);
  font-weight: 600;
  font-size: 13.5px;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 3px;
}
.suggest .why {
  margin-top: 6px;
  font-size: 12px;
  color: var(--faint);
}
.actions {
  display: flex;
  gap: 10px;
  margin-top: 14px;
  flex-wrap: wrap;
}
.btn {
  border: 1px solid var(--line);
  background: #fff;
  padding: 8px 12px;
  border-radius: 3px;
  cursor: pointer;
  font-size: 13px;
  transition: background 160ms ease, transform 160ms ease;
}
.btn:hover { background: #f0f4f8; }
.btn.primary {
  background: var(--brand);
  color: #fff;
  border-color: var(--brand);
}
.btn.primary:hover { background: #0c324b; }
.btn:disabled { opacity: 0.45; cursor: not-allowed; }

.tray {
  position: absolute;
  z-index: 3;
  left: 50%;
  bottom: 20px;
  width: min(560px, calc(100vw - 40px));
  padding: 12px 14px;
  background: var(--panel);
  backdrop-filter: blur(12px);
  border: 1px solid var(--line);
  border-radius: 4px;
  box-shadow: var(--shadow);
  display: flex;
  align-items: center;
  gap: 12px;
  transform: translate(-50%, 120%);
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transition: transform var(--dur) var(--ease), opacity var(--dur) ease, visibility var(--dur) ease;
}
.tray.on {
  transform: translate(-50%, 0);
  opacity: 1;
  visibility: visible;
  pointer-events: auto;
}
.tray b { font-size: 13px; }
.tray .names { flex: 1; font-size: 13px; color: var(--mute); }

.cmpview {
  position: fixed;
  inset: 8vh 8vw;
  z-index: 10;
  background: var(--panel-solid);
  border: 1px solid var(--line);
  border-radius: 4px;
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  opacity: 0;
  visibility: hidden;
  transform: translateY(16px);
  pointer-events: none;
  transition: opacity var(--dur) ease, transform var(--dur) var(--ease), visibility var(--dur) ease;
}
.cmpview.on {
  opacity: 1;
  visibility: visible;
  transform: none;
  pointer-events: auto;
}
.cmpview .dh { display: flex; justify-content: space-between; align-items: center; }
.cmpview .db { padding: 16px 22px 28px; }
table.c { width: 100%; border-collapse: collapse; font-size: 13.5px; }
table.c th, table.c td {
  border-bottom: 1px solid #e8edf2;
  padding: 10px 8px;
  text-align: left;
  vertical-align: top;
}
table.c th { color: var(--faint); font-weight: 600; width: 28%; font-size: 12px; }
.header-links {
  position: absolute;
  top: 20px;
  right: 16px;
  z-index: 4;
  text-align: right;
}
.header-links a {
  font-size: 12px;
  font-weight: 500;
  color: var(--mute);
  text-decoration: none;
  background: rgba(247,249,251,0.9);
  padding: 6px 10px;
  border: 1px solid var(--line);
  border-radius: 3px;
  transition: color var(--dur) ease, border-color var(--dur) ease;
}
.header-links a:hover {
  color: var(--brand);
  border-color: #b8c5d2;
}
.metrics-strip {
  margin-top: 14px;
  padding: 10px 12px;
  background: #eef3f7;
  border: 1px solid var(--line);
  border-radius: 3px;
}
.metrics-strip .from {
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: var(--faint);
  margin-bottom: 8px;
}
.metrics-strip .nums {
  display: flex;
  flex-wrap: wrap;
  gap: 14px 18px;
}
.metrics-strip .n {
  min-width: 4.5ch;
}
.metrics-strip .n strong {
  display: block;
  font-family: var(--display);
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.1;
  color: var(--brand);
}
.metrics-strip .n span {
  font-size: 11.5px;
  color: var(--mute);
}
@media (max-width: 720px) {
  .chrome { top: 12px; left: 12px; width: calc(100vw - 24px); padding: 16px; }
  .brand { font-size: 24px; }
  .trust-note { display: none; }
  .tray { bottom: 12px; }
  .header-links { top: auto; bottom: 12px; right: 12px; left: 12px; text-align: left; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
</style>
</head>
<body>
<div class="app">
  <div id="map" aria-label="Massachusetts AI organizations map"></div>
  <div class="vignette" aria-hidden="true"></div>
  <div class="header-links">
    <a href="review.html">Maintainer console (admin) →</a>
  </div>

  <aside class="chrome">
    <h1 class="brand">Mass AI Atlas<span>with receipts</span></h1>
    <p class="lede">Find who can help across Massachusetts — and see what each organization’s own site backs today.</p>
    <div class="metrics-strip" aria-label="Summary from metrics">
      <div class="from">from metrics</div>
      <div class="nums" id="metrics-nums"></div>
    </div>
    <div class="filter">
      <label for="need">I need</label>
      <select id="need">
        <option value="">Everything on the map</option>
      </select>
    </div>
    <div class="legend" aria-label="Trust legend">
      <div class="proven"><i></i>Proven by their site</div>
      <div class="inferred"><i></i>Mentioned on their site, not verified</div>
      <div class="disagree"><i></i>Their site says otherwise</div>
      <div class="silent"><i></i>No source found</div>
    </div>
    <p class="hint">Click a pin for the receipt. Similar organizations suggest a compare. Shift-click a second pin anytime.</p>
    <p class="map-stack">Organizations only. OpenStreetMap tiles · Leaflet.</p>
  </aside>

  <p class="trust-note"><b>Verified</b> means their own site backs the claim today — checked by code. Mentioned-but-not-exact stays labelled; it is never called verified.</p>

  <div class="tray" id="tray">
    <b>Compare</b>
    <span class="names" id="tray-names"></span>
    <button class="btn" id="tray-clear" type="button">Clear</button>
    <button class="btn primary" id="tray-go" type="button" disabled>Side by side</button>
  </div>
</div>

<div class="scrim" id="scrim"></div>
<aside class="drawer" id="drawer" aria-live="polite">
  <div class="dh" id="d-h"></div>
  <div class="db" id="d-b"></div>
</aside>
<div class="cmpview" id="cmpv">
  <div class="dh">
    <h2 style="margin:0;font-family:var(--display);font-size:20px">Side by side</h2>
    <button class="btn" id="cmp-x" type="button">Close</button>
  </div>
  <div class="db" id="cmp-b"></div>
</div>

<script id="data" type="application/json">/*DATA*/</script>
<script>
const D = JSON.parse(document.getElementById("data").textContent);
const ORGS = D.entries;
const CATS = D.cats || {};
const TAG = {
  supported: "Proven by their site",
  contradicted: "Their site says otherwise",
  inferred: "Mentioned on their site, not verified",
  silent: "No source found"
};
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
const $ = id => document.getElementById(id);
const catLabel = o => CATS[o.cat] || o.cat;
const offerLabel = o => o.charAt(0).toUpperCase() + o.slice(1);

const M = D.metrics || {};
$("metrics-nums").innerHTML = `
  <div class="n"><strong>${esc(M.verified ?? 0)}</strong><span>verified</span></div>
  <div class="n"><strong>${esc(M.with_sentence ?? 0)}</strong><span>with sentence</span></div>
  <div class="n"><strong>${esc(M.needs_person ?? 0)}</strong><span>needs person</span></div>`;

$("need").innerHTML += (D.offers || []).map(o =>
  `<option value="${esc(o)}">${esc(offerLabel(o))}</option>`).join("");

const MA_BOUNDS = L.latLngBounds([41.2, -73.5], [42.9, -69.9]);
const map = L.map("map", {
  zoomControl: false,
  attributionControl: true,
  minZoom: 8,
  maxZoom: 16,
  maxBounds: MA_BOUNDS.pad(0.08),
  maxBoundsViscosity: 1.0
});
L.control.zoom({ position: "bottomright" }).addTo(map);
map.fitBounds(MA_BOUNDS, { padding: [24, 24], animate: false });
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · Mass AI Atlas with receipts',
  maxZoom: 19,
  bounds: MA_BOUNDS.pad(0.2)
}).addTo(map);

let need = "";
let picked = [];
let openId = null;
const markers = {};

function pinIcon(o, on, dim) {
  const cls = `pin ${o.trust}${o.approx ? " approx" : ""}${on ? " on" : ""}${dim ? " dim" : ""}`;
  return L.divIcon({
    className: "",
    html: `<div class="${cls}" title="${esc(o.name)}"></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7]
  });
}

function visible() {
  return ORGS.filter(o => !need || (o.offers || []).includes(need));
}

function overlapBits(a, b) {
  const sharedTags = (a.tags || []).filter(t => (b.tags || []).includes(t));
  const sharedOffers = (a.offers || []).filter(t => (b.offers || []).includes(t));
  const sameCat = a.cat === b.cat;
  let score = 0;
  if (sameCat) score += 2;
  score += sharedTags.length;
  score += sharedOffers.length * 0.5;
  return { score, sharedTags, sharedOffers, sameCat };
}

function similarTo(o, limit = 3) {
  return ORGS
    .filter(x => x.id !== o.id)
    .map(x => ({ org: x, ...overlapBits(o, x) }))
    .filter(r => r.sameCat && (r.sharedTags.length > 0 || r.sharedOffers.length > 0) && r.score >= 2.5)
    .sort((a, b) => b.score - a.score || a.org.name.localeCompare(b.org.name))
    .slice(0, limit);
}

function renderPins() {
  const show = new Set(visible().map(o => o.id));
  const focus = new Set([openId, ...picked].filter(Boolean));
  ORGS.forEach(o => {
    const m = markers[o.id];
    if (!m) return;
    if (show.has(o.id)) {
      if (!map.hasLayer(m)) m.addTo(map);
      const on = focus.has(o.id);
      const dim = focus.size > 0 && !on;
      m.setIcon(pinIcon(o, on, dim));
      m.setOpacity(1);
    } else if (map.hasLayer(m)) {
      map.removeLayer(m);
    }
  });
}

ORGS.forEach(o => {
  const m = L.marker([o.lat, o.lng], { icon: pinIcon(o, false, false), riseOnHover: true });
  m.on("click", e => {
    if (e.originalEvent.shiftKey) togglePick(o.id);
    else openOrg(o.id);
  });
  m.addTo(map);
  markers[o.id] = m;
});

$("need").onchange = e => {
  need = e.target.value;
  document.querySelectorAll(".pin").forEach(p => { p.style.opacity = "0.2"; });
  requestAnimationFrame(() => {
    renderPins();
    setTimeout(() => document.querySelectorAll(".pin").forEach(p => { p.style.opacity = ""; }), 40);
  });
};

function enterCompare(aId, bId) {
  picked = [aId, bId];
  renderTray();
  renderPins();
  openCompare();
}

function openOrg(id) {
  openId = id;
  const o = ORGS.find(x => x.id === id);
  const sims = similarTo(o);
  const site = (o.url || "").replace(/^https?:\/\//, "");
  $("d-h").innerHTML = `
    <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start">
      <div>
        <h2>${esc(o.name)}</h2>
        <div class="meta">${esc(catLabel(o))} · ${esc(o.loc)}${o.approx ? " · approximate pin" : ""}</div>
        ${o.url ? `<div class="meta" style="margin-top:4px"><a href="${esc(o.url)}" target="_blank" rel="noopener">${esc(site)}</a></div>` : ""}
      </div>
      <button class="btn" type="button" id="d-close">Close</button>
    </div>
    <p class="meta" style="margin:10px 0 0">${o.proven} of ${o.total} claims proven by their own site</p>
    <div class="tags">${(o.tags || []).map(t => `<span class="tag">${esc(t)}</span>`).join("")}</div>
    <div class="actions">
      <button class="btn" type="button" id="d-cmp">${picked.includes(id) ? "Remove from compare" : "Add to compare"}</button>
    </div>`;

  let body = (o.claims || []).map(c => {
    let extra = "";
    if (c.q) extra += `<blockquote class="quote">“${esc(c.q)}”<a href="${esc(c.u)}" target="_blank" rel="noopener">See it on their site ↗${c.t ? ` · checked ${esc(c.t)}` : ""}</a></blockquote>`;
    if (c.s === "contradicted" && c.p != null) extra += `<p class="meta" style="margin:8px 0 0">The Atlas says <b>${esc(c.v)}</b>; their site says <b style="color:var(--bad)">${esc(c.p)}</b>. Under review.</p>`;
    if (c.s === "inferred") extra += `<p class="meta" style="margin:6px 0 0">Mentioned on their site, not word for word — not verified.</p>`;
    if (c.s === "silent") extra += `<p class="meta" style="margin:6px 0 0">No matching sentence found on fetched pages.</p>`;
    return `<div class="claim"><div class="k">${esc(c.k)}</div><div class="v">${esc(c.v)}</div>
      <div class="status ${c.s}">${TAG[c.s] || TAG.silent}</div>${extra}</div>`;
  }).join("");

  if (sims.length) {
    const bits = sims.map(s => {
      const why = [
        s.sameCat ? "same category" : null,
        s.sharedTags.length ? `tags: ${s.sharedTags.join(", ")}` : null,
        s.sharedOffers.length ? `offers: ${s.sharedOffers.join(", ")}` : null
      ].filter(Boolean).join(" · ");
      return { id: s.org.id, name: s.org.name, why };
    });
    body = `<div class="suggest">
      <div class="lbl">Similar</div>
      <div class="row">Compare with ${bits.map((b, i) =>
        `<button type="button" class="linkish" data-cmp="${esc(b.id)}">${esc(b.name)}</button>${i < bits.length - 1 ? "," : ""}`
      ).join(" ")}</div>
      <div class="why">${esc(bits[0].why)}</div>
    </div>` + body;
  }

  $("d-b").innerHTML = body;
  $("drawer").classList.add("on");
  $("scrim").classList.add("on");
  $("d-close").onclick = closeDrawer;
  $("d-cmp").onclick = () => { togglePick(id); openOrg(id); };
  $("d-b").querySelectorAll("[data-cmp]").forEach(btn => {
    btn.onclick = () => enterCompare(id, btn.getAttribute("data-cmp"));
  });

  const m = markers[id];
  if (m) map.panTo(m.getLatLng(), { animate: true, duration: 0.35 });
  renderPins();
}

function closeDrawer() {
  openId = null;
  $("drawer").classList.remove("on");
  if (!$("cmpv").classList.contains("on")) $("scrim").classList.remove("on");
  renderPins();
}

function closeAll() {
  openId = null;
  picked = [];
  ["drawer", "scrim", "cmpv", "tray"].forEach(i => $(i).classList.remove("on"));
  renderTray();
  renderPins();
}
$("scrim").onclick = () => {
  if ($("cmpv").classList.contains("on")) {
    $("cmpv").classList.remove("on");
    $("scrim").classList.toggle("on", !!openId);
  } else closeDrawer();
};
$("cmp-x").onclick = () => {
  $("cmpv").classList.remove("on");
  $("scrim").classList.toggle("on", !!openId);
};
document.addEventListener("keydown", e => {
  if (e.key !== "Escape") return;
  if ($("cmpv").classList.contains("on")) {
    $("cmpv").classList.remove("on");
    $("scrim").classList.toggle("on", !!openId);
  } else if (openId) closeDrawer();
  else closeAll();
});

function togglePick(id) {
  if (picked.includes(id)) picked = picked.filter(x => x !== id);
  else { picked.push(id); if (picked.length > 2) picked = picked.slice(-2); }
  renderTray();
  renderPins();
}
function renderTray() {
  $("tray").classList.toggle("on", picked.length > 0);
  const names = picked.map(id => (ORGS.find(o => o.id === id) || {}).name || id);
  $("tray-names").textContent = names.join(" · ") + (picked.length < 2 ? "  (pick one more, or use a Similar link)" : "");
  $("tray-go").disabled = picked.length < 2;
}
function openCompare() {
  if (picked.length < 2) return;
  const [a, b] = picked.map(id => ORGS.find(o => o.id === id));
  const ov = overlapBits(a, b);
  const claimKeys = [...new Set([...(a.claims || []), ...(b.claims || [])].map(c => c.k))];
  const rows = [
    ["Category", o => catLabel(o)],
    ["Tags", o => (o.tags || []).join(", ") || "—"],
    ["Offers", o => (o.offers || []).join(", ") || "—"],
    ["Proven", o => `${o.proven} of ${o.total}`],
    ["Trust pin", o => TAG[o.trust] || o.trust],
    ...claimKeys.map(k => [
      k, o => {
        const c = (o.claims || []).find(x => x.k === k);
        return c ? `${c.v} · ${TAG[c.s] || c.s}` : "—";
      }
    ])
  ];
  const shared = [
    ov.sharedTags.length ? `shared tags: ${ov.sharedTags.join(", ")}` : null,
    ov.sharedOffers.length ? `shared offers: ${ov.sharedOffers.join(", ")}` : null
  ].filter(Boolean).join("; ");
  const less = (a.claims || []).some(c => c.s === "contradicted") !== (b.claims || []).some(c => c.s === "contradicted")
    ? ((a.claims || []).some(c => c.s === "contradicted") ? a : b)
    : (a.proven / Math.max(1, a.total) <= b.proven / Math.max(1, b.total) ? a : b);
  $("cmp-b").innerHTML = `
    <p class="meta" style="margin:0 0 12px">Trust <b>${esc(less.name)}</b>’s listing less when fewer claims are proven — or when their site says otherwise — until a maintainer reviews.${shared ? ` Overlap — ${esc(shared)}.` : ""}</p>
    <table class="c"><thead><tr><th></th><td><b>${esc(a.name)}</b></td><td><b>${esc(b.name)}</b></td></tr></thead>
    <tbody>${rows.map(([l, f]) => `<tr><th>${esc(l)}</th><td>${esc(f(a))}</td><td>${esc(f(b))}</td></tr>`).join("")}</tbody></table>`;
  $("drawer").classList.remove("on");
  openId = null;
  $("cmpv").classList.add("on");
  $("scrim").classList.add("on");
  renderPins();
}
$("tray-clear").onclick = () => { picked = []; renderTray(); renderPins(); };
$("tray-go").onclick = openCompare;

renderPins();
</script>
</body>
</html>
"""
