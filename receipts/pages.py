"""Find an org's own pages worth reading: home, plus about / contact / apply / program / portfolio."""
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from receipts.fetch import client, fetch, host_of

MAX_PAGES = 6
WANT = re.compile(r"about|contact|apply|application|program|accelerator|invest|portfolio|"
                  r"terms|faq|location|visit|deal|fund|who-we-are|mission", re.I)
# People pages are skipped: we collect organizations only.
SKIP = re.compile(r"team|people|staff|leadership|partners/|bio|login|signin|privacy|cookie|"
                  r"careers|jobs|blog/|news/|\.pdf$|mailto:|tel:", re.I)


def own_words(entry):
    """Words that point at this entry's page on a multi-city site, e.g. "boston"."""
    words = re.findall(r"[a-z]{4,}", (entry["loc"] + " " + entry["name"]).lower())
    return [w for w in words if w not in {"street", "avenue", "suite", "floor", "center", "ventures",
                                          "capital", "partners", "group", "fund"}]


def candidate_links(home, entry=None):
    soup = BeautifulSoup(home["html"], "lxml")
    base = home["final_url"]
    site = host_of(base)
    words = [w for w in own_words(entry or {"loc": "", "name": ""}) if w not in site]
    scored = {}
    for a in soup.find_all("a", href=True):
        href = urljoin(base, a["href"]).split("#")[0]
        if host_of(href) != site or not href.startswith("https://") or SKIP.search(href):
            continue
        label = a.get_text(" ", strip=True)[:60]
        path = urlsplit(href).path
        mine = any(w in path.lower() or w in label.lower() for w in words)
        hit = WANT.search(path) or WANT.search(label)
        if (hit or mine) and href.rstrip("/") != base.rstrip("/"):
            score = path.strip("/").count("/") - (10 if mine else 0)
            scored[href] = min(scored.get(href, 99), score)
    return [u for u, _ in sorted(scored.items(), key=lambda kv: kv[1])][: MAX_PAGES - 1]


def pages_for(entry, c=None, refresh=False):
    """The entry's url, then up to 4 same-site pages linked from it. Cached."""
    own = c is None
    c = c or client()
    try:
        home = fetch(entry["url"], c, refresh)
        pages = [home]
        if home["html"]:
            pages += [fetch(u, c, refresh) for u in candidate_links(home, entry)]
        return pages
    finally:
        if own:
            c.close()
