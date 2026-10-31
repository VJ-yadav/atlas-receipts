"""Find an org's own pages worth reading: home, plus about / contact / apply / program / portfolio."""
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from receipts.fetch import allowed, client, fetch, host_of

MAX_PAGES = 6
# Same-host guesses when the homepage is silent on place / facts / deadlines (capped below).
GUESS_PATHS = ("/contact", "/about", "/faq", "/faqs", "/where", "/locations", "/location",
               "/program", "/programs", "/apply", "/application", "/about-us", "/contact-us",
               "/visit", "/portfolio", "/terms")
WANT = re.compile(r"about|contact|apply|application|program|accelerator|invest|portfolio|"
                  r"terms|faq|where|locations?|visit|deal|fund|who-we-are|mission", re.I)
# Pages that state terms, deadlines and programs come before generic about/contact pages.
STRONG = re.compile(r"terms|invest|deal|apply|application|program|accelerator|fund|faq|location", re.I)
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
            strong = STRONG.search(path) or STRONG.search(label)
            score = path.strip("/").count("/") - (10 if mine else 0) - (5 if strong else 0)
            scored[href] = min(scored.get(href, 99), score)
    return [u for u, _ in sorted(scored.items(), key=lambda kv: kv[1])][: MAX_PAGES - 1]


def _guess_ok(c, url):
    """Respect robots before probing a guessed path."""
    try:
        return allowed(c, url)
    except Exception:
        return True


def pages_for(entry, c=None, refresh=False):
    """The entry's url, then up to 4 same-site pages linked from it. Cached."""
    own = c is None
    c = c or client()
    try:
        home = fetch(entry["url"], c, refresh)
        pages = [home]
        if home["html"]:
            links = candidate_links(home, entry)
            pages += [fetch(u, c, refresh) for u in links]
            # the address usually lives on a contact/about page: try the usual paths too
            root = "/".join(home["final_url"].split("/")[:3])
            seen = {u.rstrip("/") for u in links} | {home["final_url"].rstrip("/")}
            for path in GUESS_PATHS:
                if len(pages) >= MAX_PAGES + 2:
                    break
                url = root + path
                if url.rstrip("/") in seen or any(path.rstrip("/") == urlsplit(u).path.rstrip("/") for u in seen):
                    continue
                if not _guess_ok(c, url):
                    continue
                pg = fetch(url, c, refresh)
                if pg["text"] and (pg["status"] or 0) < 400 and pg["final_url"].rstrip("/") not in seen:
                    pages.append(pg)
                    seen.add(pg["final_url"].rstrip("/"))
        return pages
    finally:
        if own:
            c.close()
