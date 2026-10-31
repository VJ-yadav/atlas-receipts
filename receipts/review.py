"""receipts review: one static HTML page for a person to accept or reject claims."""
from __future__ import annotations

import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from receipts.claims import FIELD_RISK
from receipts.text import highlight_url

PROBLEM = ("contradicted", "silent", "refused", "inferred")
CONTACT = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    r"|\+?\d[\d\s().-]{8,}\d"
    r"|@[A-Za-z0-9_]{2,}"
)


def esc(s) -> str:
    if s is None:
        return ""
    return html.escape(CONTACT.sub("[redacted]", str(s)), quote=True)


def fmt_value(value) -> str:
    if isinstance(value, dict):
        if "label" in value and "value" in value:
            return f"{value['label']}: {value['value']}"
        if "applyBy" in value:
            note = value.get("applyNote") or ""
            return f"{value['applyBy']}" + (f" — {note}" if note else "")
        return ", ".join(f"{k}: {v}" for k, v in value.items())
    return str(value)


def badge(status: str) -> str:
    labels = {
        "supported": ("badge-ok", "supported"),
        "contradicted": ("badge-bad", "contradicted ▲"),
        "silent": ("badge-silent", "silent ○"),
        "inferred": ("badge-inf", "inferred — not verified"),
        "refused": ("badge-ref", "refused"),
    }
    cls, label = labels.get(status, ("badge-silent", status))
    return f'<span class="badge {cls}">{esc(label)}</span>'


def entry_has_problem(recs: list[dict]) -> bool:
    return any(r["status"] in PROBLEM for r in recs)


def sort_receipts(recs: list[dict]) -> list[dict]:
    return sorted(recs, key=lambda r: (FIELD_RISK.get(r.get("field"), 99), r.get("key", "")))


def claim_row(r: dict) -> str:
    status = r.get("status", "")
    compact = status == "supported"
    value = esc(fmt_value(r.get("value")))
    quote = r.get("quote")
    reason = esc(r.get("reason"))
    fetched = esc((r.get("fetched_at") or "")[:10])
    page_value = r.get("page_value")
    url = r.get("url") or ""
    link = ""
    if url and quote:
        href = esc(highlight_url(url, quote))
        link = f'<a class="jump" href="{href}" target="_blank" rel="noopener">↗</a>'
    elif url:
        link = f'<a class="jump" href="{esc(url)}" target="_blank" rel="noopener">↗</a>'

    parts = [
        f'<div class="claim {"compact" if compact else ""}" data-key="{esc(r["key"])}" data-status="{esc(status)}">',
        f'<div class="claim-head">{badge(status)}'
        f'<span class="field">{esc(r.get("field", ""))}</span>'
        f'<span class="value">{value}</span>{link}</div>',
    ]
    if not compact:
        if quote:
            parts.append(f'<div class="quote">“{esc(quote)}”</div>')
        if status == "contradicted" and page_value is not None:
            parts.append(f'<div class="page-value">page: {esc(page_value)}</div>')
        if reason:
            parts.append(f'<div class="reason">{reason}</div>')
        if fetched:
            parts.append(f'<div class="meta">fetched {fetched}</div>')
        if status == "silent":
            searched = r.get("searched") or []
            if searched:
                items = "".join(f"<li>{esc(u)}</li>" for u in searched)
                parts.append(f'<ul class="searched">{items}</ul>')
        if status != "supported":
            parts.append(
                '<div class="decide">'
                f'<button type="button" data-decision="accept" data-key="{esc(r["key"])}">Accept</button>'
                f'<button type="button" data-decision="reject" data-key="{esc(r["key"])}">Reject</button>'
                '<span class="choice"></span></div>'
            )
    parts.append("</div>")
    return "\n".join(parts)


def entry_card(entry_id: str, name: str, recs: list[dict]) -> str:
    planted = entry_id.startswith("planted-")
    banner = '<div class="planted">TEST — planted</div>' if planted else ""
    rows = "\n".join(claim_row(r) for r in sort_receipts(recs))
    return (
        f'<section class="card" data-entry="{esc(entry_id)}">'
        f"{banner}"
        f'<h2>{esc(name)} <span class="eid">{esc(entry_id)}</span></h2>'
        f"{rows}</section>"
    )


def refused_section(receipts: list[dict]) -> str:
    refused = [r for r in receipts if r.get("status") == "refused"]
    by_reason: dict[str, list] = defaultdict(list)
    for r in refused:
        by_reason[r.get("reason") or "(no reason)"].append(r)
    if not by_reason:
        return '<section class="refused"><h2>Refused</h2><p>None.</p></section>'
    blocks = []
    for reason, rows in sorted(by_reason.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        keys = "".join(f"<li>{esc(r['key'])}</li>" for r in rows)
        blocks.append(
            f'<div class="refuse-group"><h3>{esc(reason)}'
            f' <span class="count">({len(rows)})</span></h3><ul>{keys}</ul></div>'
        )
    return '<section class="refused"><h2>Refused</h2>' + "".join(blocks) + "</section>"


CSS = """
:root {
  --bg: #f6f3ec; --ink: #1c1a16; --muted: #6b655a; --line: #d9d2c4;
  --ok: #2f6b4f; --ok-bg: #e4f0e8; --inf: #8a5a12; --inf-bg: #f7edd8;
  --silent-bg: #ece8e0; --ref-bg: #e2e0db; --planted: #7a2e2e; --planted-bg: #f3d9d6;
}
* { box-sizing: border-box; }
body {
  margin: 0; font: 15px/1.45 "Source Serif 4", "Iowan Old Style", Georgia, serif;
  color: var(--ink); background:
    radial-gradient(1200px 500px at 10% -10%, #efe6d4 0%, transparent 60%),
    linear-gradient(180deg, #fbf8f1, var(--bg));
}
header {
  padding: 1.5rem 1.5rem 1rem; border-bottom: 1px solid var(--line);
  background: rgba(255,255,255,0.55); backdrop-filter: blur(6px);
  position: sticky; top: 0; z-index: 5;
}
header h1 { margin: 0 0 .35rem; font-size: 1.65rem; letter-spacing: -.02em; }
.probe { margin: 0; color: var(--muted); }
.counts { margin: .55rem 0 0; display: flex; flex-wrap: wrap; gap: .4rem .75rem; }
.counts span { font-size: .92rem; color: var(--muted); }
.toolbar { margin-top: .75rem; }
.toolbar button {
  font: inherit; padding: .45rem .85rem; border: 1px solid var(--ink);
  background: var(--ink); color: #fff; cursor: pointer;
}
main { max-width: 920px; margin: 0 auto; padding: 1.25rem 1rem 3rem; }
.card {
  margin: 0 0 1.25rem; padding: 1rem 1rem .4rem;
  border-top: 2px solid var(--ink);
}
.card h2 { margin: 0 0 .75rem; font-size: 1.2rem; }
.eid { color: var(--muted); font-weight: 400; font-size: .85rem; }
.planted {
  display: inline-block; margin: 0 0 .6rem; padding: .2rem .55rem;
  background: var(--planted-bg); color: var(--planted);
  font-size: .8rem; letter-spacing: .04em; text-transform: uppercase;
}
.claim { margin: 0 0 .85rem; padding: .55rem 0; border-bottom: 1px solid var(--line); }
.claim.compact { padding: .3rem 0; opacity: .85; }
.claim-head { display: flex; flex-wrap: wrap; gap: .35rem .55rem; align-items: baseline; }
.field { color: var(--muted); font-size: .85rem; text-transform: uppercase; letter-spacing: .04em; }
.value { font-weight: 600; }
.quote { margin: .35rem 0; font-style: italic; }
.page-value, .reason, .meta { color: var(--muted); font-size: .92rem; }
.searched { margin: .3rem 0 0 1.1rem; color: var(--muted); font-size: .88rem; }
.jump { margin-left: .35rem; text-decoration: none; color: var(--ink); }
.badge { display: inline-block; padding: .1rem .45rem; font-size: .78rem; border-radius: 2px; }
.badge-ok { background: var(--ok-bg); color: var(--ok); }
.badge-bad { background: #f8e6e3; color: #9b2f24; }
.badge-silent { background: var(--silent-bg); color: var(--muted); }
.badge-inf { background: var(--inf-bg); color: var(--inf); }
.badge-ref { background: var(--ref-bg); color: #2a2a2a; }
.decide { margin-top: .45rem; display: flex; gap: .4rem; align-items: center; }
.decide button {
  font: inherit; font-size: .85rem; padding: .25rem .55rem;
  border: 1px solid var(--line); background: #fff; cursor: pointer;
}
.decide button.active-accept { background: var(--ok-bg); border-color: var(--ok); color: var(--ok); }
.decide button.active-reject { background: #f8e6e3; border-color: #9b2f24; color: #9b2f24; }
.choice { font-size: .85rem; color: var(--muted); }
.refused { margin-top: 2rem; padding-top: 1rem; border-top: 2px solid var(--ink); }
.refused h2 { margin: 0 0 .75rem; }
.refuse-group { margin: 0 0 1rem; }
.refuse-group h3 { margin: 0 0 .35rem; font-size: 1rem; }
.refuse-group .count { color: var(--muted); font-weight: 400; }
.refuse-group ul { margin: 0; padding-left: 1.1rem; color: var(--muted); font-size: .9rem; }
"""

JS = """
(function () {
  const decisions = {};
  function sync(key) {
    const row = document.querySelector('.claim[data-key="' + CSS.escape(key) + '"]');
    if (!row) return;
    const choice = row.querySelector('.choice');
    const d = decisions[key];
    row.querySelectorAll('button[data-decision]').forEach(function (b) {
      b.classList.toggle('active-accept', d === 'accept' && b.dataset.decision === 'accept');
      b.classList.toggle('active-reject', d === 'reject' && b.dataset.decision === 'reject');
    });
    if (choice) choice.textContent = d ? d : '';
  }
  document.addEventListener('click', function (ev) {
    const btn = ev.target.closest('button[data-decision]');
    if (!btn) return;
    const key = btn.dataset.key;
    const decision = btn.dataset.decision;
    if (decisions[key] === decision) delete decisions[key];
    else decisions[key] = decision;
    sync(key);
  });
  document.getElementById('download').addEventListener('click', function () {
    const payload = Object.keys(decisions).sort().map(function (key) {
      return { key: key, decision: decisions[key] };
    });
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'decisions.json';
    a.click();
    URL.revokeObjectURL(a.href);
  });
})();
"""


def build(receipts: list[dict], out_path) -> Path:
    out_path = Path(out_path)
    by_entry: dict[str, list] = defaultdict(list)
    names: dict[str, str] = {}
    for r in receipts:
        eid = r["entry_id"]
        by_entry[eid].append(r)
        names[eid] = r.get("name") or eid

    order = sorted(by_entry.keys(), key=lambda eid: (0 if entry_has_problem(by_entry[eid]) else 1, names[eid], eid))
    cards = "\n".join(entry_card(eid, names[eid], by_entry[eid]) for eid in order)

    n = Counter(r.get("status") for r in receipts)
    supported = n.get("supported", 0)
    total = len(receipts)
    counts = " · ".join(
        f'<span>{esc(s)} {n.get(s, 0)}</span>'
        for s in ("supported", "contradicted", "silent", "inferred", "refused")
    )

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Atlas Receipts — review</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>Atlas Receipts</h1>
  <p class="probe">Probe 8: claims with a receipt 0 → {supported} / {total}</p>
  <div class="counts">{counts}</div>
  <div class="toolbar"><button type="button" id="download">Download decisions.json</button></div>
</header>
<main>
{cards}
{refused_section(receipts)}
</main>
<script>{JS}</script>
</body>
</html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc, encoding="utf-8")
    return out_path


def run(fixture: bool = False) -> Path:
    from receipts.probes import ROOT

    src = ROOT / "tests" / "fixtures" / "receipts.sample.json" if fixture else ROOT / "out" / "receipts.json"
    if not src.exists():
        raise SystemExit(f"missing {src}; run receipts check --all or pass --fixture")
    receipts = json.loads(src.read_text(encoding="utf-8"))
    out = ROOT / "out" / "review.html"
    build(receipts, out)
    print(f"wrote {out} ({len(receipts)} receipts)")
    return out
