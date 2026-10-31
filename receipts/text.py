"""HTML to sentences, and the code check that a quote is really on the page."""
import re
import unicodedata

from bs4 import BeautifulSoup

DROP = ("script", "style", "noscript", "svg", "template", "iframe")
_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"“$])|\n+")


def page_text(html):
    """Visible text, one block per line."""
    soup = BeautifulSoup(html, "lxml")
    for t in soup(DROP):
        t.decompose()
    lines = (re.sub(r"\s+", " ", s).strip() for s in soup.get_text("\n").split("\n"))
    return "\n".join(s for s in lines if s)


def sentences(text):
    return [s.strip() for s in _SPLIT.split(text) if len(s.strip()) > 2]


def normalize(s):
    s = unicodedata.normalize("NFKC", s)
    s = s.translate(str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-",
                                   " ": " "}))
    return re.sub(r"\s+", " ", s).strip().lower()


def quote_on_page(quote, text):
    """Exact match after normalizing whitespace, case and typographic punctuation."""
    q = normalize(quote or "")
    return bool(q) and q in normalize(text)


def highlight_url(url, quote):
    """A link that opens the page with the sentence highlighted (#:~:text=)."""
    from urllib.parse import quote as q
    words = (quote or "").split()
    if not words:
        return url
    if len(words) > 8:
        start, end = " ".join(words[:4]), " ".join(words[-4:])
        return f"{url.split('#')[0]}#:~:text={q(start, safe='')},{q(end, safe='')}"
    frag = " ".join(words)
    return f"{url.split('#')[0]}#:~:text={q(frag, safe='')}"
