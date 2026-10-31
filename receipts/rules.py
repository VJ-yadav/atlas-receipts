"""Claim rules: one function per claim type. Each finds a sentence on the org's own cached pages
and returns a receipt. Code does every check here; the model is not involved."""
import re
from datetime import date

from receipts.claims import make_receipt
from receipts.text import normalize, quote_on_page, sentences

TODAY = date(2026, 10, 31)
THIN = 200  # fewer characters than this: probably a JavaScript-only page
PARKED = re.compile(r"domain (is |may be )?for sale|buy this domain|parked (free|domain)|"
                    r"this domain has expired|domain name is available", re.I)
OFFER_WORDS = {
    "funding": r"invest|funding|capital|seed|pre-seed|check|portfolio",
    "mentorship": r"mentor|coach|advis",
    "grants": r"grant|non-dilutive|prize|award|stipend",
    "community": r"community|network|members|meetup|events?",
    "space": r"co-?working|office space|lab space|workspace|desk|facility|facilities",
    "talent": r"talent|hiring|careers?|recruit|students|graduates|interns?",
    "customers": r"customers?|pilots?|partners?hips?|corporate partners|procurement",
    "compute": r"compute|gpus?|cloud credits|computing|supercomput|hpc",
}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]


# ---------- shared helpers ----------

def usable(pages):
    return [p for p in pages if p.get("text") and not p.get("error") and (p.get("status") or 0) < 400]


def units(page):
    """Sentences, plus runs of short adjacent lines (labels and values sit in separate tags)."""
    lines = page["text"].split("\n")
    out = []
    for i, line in enumerate(lines):
        out += sentences(line)
        # runs of 2-3 short lines: "Nov 18" / "2026" / "Final Deadline"
        for n in (2, 3):
            run = lines[i:i + n]
            if len(run) == n and all(len(x) < 40 for x in run[:-1]) and len(run[-1]) < 60:
                out.append(" ".join(run))
    return out


def full_sentence(s):
    return len(s.split()) >= 8


def find(pages, test, prefer=full_sentence):
    """(page, sentence) where test(sentence) is true, preferring one where prefer(sentence) is
    also true. The sentence is re-checked against the cached page by code."""
    first = (None, None)
    for p in usable(pages):
        for s in units(p):
            if test(s) and quote_on_page(s, p["text"]):
                if prefer(s):
                    return p, s[:400]
                first = first if first[0] else (p, s[:400])
    return first


def supported(claim, page, quote, reason):
    return make_receipt(claim, "supported", url=page["final_url"], fetched_at=page["fetched_at"],
                        quote=quote, sha256=page["sha256"], reason=reason)


def contradicted(claim, page, quote, page_value, reason):
    return make_receipt(claim, "contradicted", url=page["final_url"], fetched_at=page["fetched_at"],
                        quote=quote, sha256=page.get("sha256"), page_value=page_value, reason=reason)


def silent(claim, pages, reason):
    home = pages[0]
    return make_receipt(claim, "silent", url=home["final_url"], fetched_at=home["fetched_at"],
                        reason=reason, searched=[p["final_url"] for p in pages])


def word(term):
    return re.compile(r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])")


# ---------- money ----------

_MONEY = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)\s*(k|m|mm|b|thousand|million|billion)?\b", re.I)
_MULT = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mm": 1e6, "million": 1e6, "b": 1e9, "billion": 1e9}


def amounts(s):
    out = []
    for num, unit in _MONEY.findall(s):
        v = float(num.replace(",", "")) * _MULT.get((unit or "").lower(), 1)
        out.append(round(v))
    return out


# ---------- rules ----------

def rule_live(claim, pages):
    home = pages[0]
    if home["error"]:
        if home["error"].startswith("refused"):
            return None  # handled for the whole entry
        return contradicted(claim, home, None, home["error"], "the site did not answer: " + home["error"])
    if home["status"] >= 400:
        return contradicted(claim, home, None, f"HTTP {home['status']}", f"the site answers HTTP {home['status']}")
    p, s = find([home], lambda s: PARKED.search(s))
    if p:
        return contradicted(claim, p, s, "parked or for-sale domain", "the page is a parked or for-sale domain")
    if len(home["text"]) < THIN:
        return silent(claim, pages, f"the page has almost no text ({len(home['text'])} chars): "
                                    "probably JavaScript-only; needs a browser fetch or review")
    name = [w for w in re.findall(r"[a-z]{4,}", claim["name"].lower())]
    p, s = find([home], lambda s: len(s) > 25 and any(w in s.lower() for w in name))
    if not p:
        p, s = find([home], lambda s: len(s) > 40)
    reason = f"the site answers HTTP {home['status']} with {len(home['text'])} characters of content"
    if home["final_url"].split("/")[2].removeprefix("www.") != claim["value"].split("/")[2].removeprefix("www."):
        reason += f"; it redirects to {home['final_url']} (check it is the same organization)"
        return make_receipt(claim, "silent", url=home["final_url"], fetched_at=home["fetched_at"],
                            reason=reason, quote=s, sha256=home["sha256"])
    return supported(claim, p, s, reason)


US_STATES = r"(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)"
_OTHER_STATE_ADDR = re.compile(r"\b[A-Z][a-z]+,\s*" + US_STATES + r"\s+\d{5}\b")
_MA_ADDR = re.compile(r"\b(MA|Massachusetts)\b\s*0[12]\d{3}\b")


def rule_place(claim, pages):
    parts = sorted({p.strip() for p in re.split(r"[,/·]| near ", claim["value"]) if len(p.strip()) > 2},
                   key=len, reverse=True)
    for part in parts:
        pat = word(part)
        p, s = find(pages, lambda s: pat.search(s.lower()))
        if p:
            return supported(claim, p, s, f"the page names '{part}' from the Atlas location")
    p, s = find(pages, lambda s: _OTHER_STATE_ADDR.search(s))
    if p and not _MA_ADDR.search(p["text"]):
        return contradicted(claim, p, s, _OTHER_STATE_ADDR.search(s).group(0),
                            "the page gives an address outside Massachusetts and none inside it")
    return silent(claim, pages, f"none of {parts} appears on {len(usable(pages))} pages")


def _date_patterns(d):
    m = MONTHS[d.month - 1]
    return [f"{m} {d.day}, {d.year}", f"{m} {d.day} {d.year}", f"{m[:3]} {d.day}, {d.year}",
            f"{m[:3]} {d.day} {d.year}", f"{d.day} {m} {d.year}", f"{d.month}/{d.day}/{d.year}",
            d.isoformat(), f"{m} {d.day}", f"{m[:3]} {d.day}"]


CLOSED = re.compile(r"applications? (are |is )?(now )?closed|no longer accepting|not currently accepting", re.I)
ROLLING = re.compile(r"rolling|apply (now|anytime|any time|today)|applications? (are |is )?(now )?open|"
                     r"accepting applications|year-round|year round|ongoing basis", re.I)


def rule_deadline(claim, pages):
    v = claim["value"]["applyBy"]
    p, s = find(pages, lambda s: CLOSED.search(s))
    closed = (p, s)
    if v == "rolling":
        p, s = find(pages, lambda s: ROLLING.search(s))
        if p:
            return supported(claim, p, s, "the page says applications are open or rolling")
        if closed[0]:
            return contradicted(claim, *closed, "applications closed", "Atlas says rolling; the page says closed")
        return silent(claim, pages, "no sentence says rolling, open or closed on "
                                    f"{len(usable(pages))} pages")
    d = date.fromisoformat(v)
    pats = [normalize(x) for x in _date_patterns(d)]
    p, s = find(pages, lambda s: any(x in normalize(s) for x in pats),
                prefer=lambda s: re.search(r"deadline|due|apply by|close", s, re.I))
    if p:
        if d < TODAY:
            return contradicted(claim, p, s, f"{v} has passed", f"the page gives {v}, which has passed")
        return supported(claim, p, s, f"the page gives the deadline {v}")
    if closed[0]:
        return contradicted(claim, *closed, "applications closed", f"Atlas says apply by {v}; the page says closed")
    return silent(claim, pages, f"the date {v} does not appear on {len(usable(pages))} pages "
                                f"(searched as {', '.join(_date_patterns(d)[:3])} …)")


INVEST_CTX = re.compile(r"invest|check|fund|capital|seed|round|safe|equity|award|grant|prize|stipend", re.I)


def rule_fact(claim, pages):
    label, val = claim["value"]["label"], claim["value"]["value"]
    if label in ("Check size", "Terms") and amounts(val):
        want = amounts(val.split("(")[0]) or amounts(val)
        p, s = find(pages, lambda s: set(want) <= set(amounts(s)))
        if p:
            return supported(claim, p, s, f"the page gives {', '.join(f'${a:,}' for a in want)}")
        p1, s1 = find(pages, lambda s: set(want) & set(amounts(s)))
        p2, s2 = find(pages, lambda s: amounts(s) and INVEST_CTX.search(s) and not set(want) & set(amounts(s)))
        if p1:
            return silent(claim, pages, f"the page gives part of the range: \"{s1[:120]}\"; needs review")
        if p2 and label == "Check size":
            return contradicted(claim, p2, s2, ", ".join(f"${a:,}" for a in amounts(s2)),
                                f"Atlas says {val}; the page gives a different amount")
        return silent(claim, pages, f"no amount matching {val} on {len(usable(pages))} pages")
    # a number together with its unit: "13 weeks" must not match a stray "13"
    tokens = re.findall(r"\d+(?:\.\d+)?%|\d+(?:\.\d+)?(?:[\s-]+[a-z]+)?", val)
    if tokens:
        pats = [re.compile(r"(?<![\d.])" + re.escape(t.lower()).replace(r"\ ", r"[\s-]+").rstrip("s") + r"s?\b"
                           if re.search(r"[a-z]", t) else word(t)) for t in tokens]
        p, s = find(pages, lambda s: all(x.search(s.lower()) for x in pats))
        if p:
            return supported(claim, p, s, f"the page gives {' '.join(tokens)}")
        return silent(claim, pages, f"{' '.join(tokens)} not found on {len(usable(pages))} pages "
                                    "(different wording? needs review)")
    return silent(claim, pages, f"'{label}: {val}' is a description, not a number: needs a reading")


def rule_link(claim, pages, entries_by_id):
    target = entries_by_id.get(claim["value"])
    if not target:
        return silent(claim, pages, f"link target id {claim['value']!r} is not in the Atlas")
    full = re.sub(r"\s*\(.*?\)", "", target["name"]).strip()
    names = {full, re.sub(r"\b(Boston|Inc\.?|LLC)\b", "", full).strip()}
    pats = [word(n) for n in names if len(n) > 3]
    p, s = find(pages, lambda s: any(x.search(s.lower()) for x in pats))
    if p:
        return supported(claim, p, s, f"the page names {target['name']} ({target['id']})")
    return silent(claim, pages, f"{target['name']} is not named on {len(usable(pages))} pages")


def rule_offer(claim, pages):
    pat = re.compile(r"\b(" + OFFER_WORDS.get(claim["value"], re.escape(claim["value"])) + r")", re.I)
    p, s = find(pages, lambda s: 20 < len(s) < 300 and pat.search(s))
    if p:
        return supported(claim, p, s, f"the sentence mentions '{pat.search(s).group(0)}' for {claim['value']}")
    return silent(claim, pages, f"no sentence about {claim['value']} on {len(usable(pages))} pages")


def check_entry(entry, claims, pages, entries_by_id):
    """One receipt per claim of this entry."""
    home = pages[0]
    out = []
    for c in claims:
        if home["error"] and home["error"].startswith("refused"):
            out.append(make_receipt(c, "refused", url=home["url"], fetched_at=home["fetched_at"],
                                    reason=home["error"].removeprefix("refused: ")))
            continue
        if c["field"] != "live" and not usable(pages):
            out.append(silent(c, pages, "the org's site gave no readable page: " +
                              (home["error"] or f"HTTP {home['status']}")))
            continue
        f = c["field"]
        r = (rule_live(c, pages) if f == "live" else rule_place(c, pages) if f == "place" else
             rule_deadline(c, pages) if f == "deadline" else rule_fact(c, pages) if f == "fact" else
             rule_link(c, pages, entries_by_id) if f == "link" else rule_offer(c, pages))
        out.append(r)
    return out
