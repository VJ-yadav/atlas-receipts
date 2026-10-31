"""Polite, cached fetching: robots.txt, ~1 request a second per host, every fetch kept on disk."""
import hashlib
import json
import threading
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from receipts.claims import now_iso
from receipts.text import page_text

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache"
UA = "AtlasReceipts/0.1 (+https://github.com/VJ-yadav/atlas-receipts; TOA hackathon verifier)"
MIN_GAP = 1.0
# Hosts whose terms we could not verify allow automated collection: never fetched.
REFUSED_HOSTS = {"meetup.com": "meetup.com terms could not be verified to allow automated collection"}

_last_hit = {}
_host_locks = {}
_robots = {}
_lock = threading.Lock()


def host_of(url):
    h = urlsplit(url).hostname or ""
    return h[4:] if h.startswith("www.") else h


def refused_reason(url):
    h = host_of(url)
    for bad, why in REFUSED_HOSTS.items():
        if h == bad or h.endswith("." + bad):
            return why
    return None


def _cache_path(url):
    return CACHE / host_of(url) / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".json")


def _wait(host):
    with _lock:
        lk = _host_locks.setdefault(host, threading.Lock())
    lk.acquire()
    gap = time.monotonic() - _last_hit.get(host, 0)
    if gap < MIN_GAP:
        time.sleep(MIN_GAP - gap)
    return lk


def _get(client, url):
    host = host_of(url)
    lk = _wait(host)
    try:
        return client.get(url)
    finally:
        _last_hit[host] = time.monotonic()
        lk.release()


def allowed(client, url):
    parts = urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}"
    if base not in _robots:
        rp = RobotFileParser()
        try:
            r = _get(client, base + "/robots.txt")
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except httpx.HTTPError:
            rp.parse([])
        _robots[base] = rp
    return _robots[base].can_fetch(UA, url)


def client():
    return httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=20)


def fetch(url, c=None, refresh=False):
    """Return a page dict: url, final_url, status, html, text, sha256, fetched_at, error.

    Served from cache/ unless refresh=True. Never raises for network problems.
    """
    path = _cache_path(url)
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    page = {"url": url, "final_url": url, "status": None, "html": "", "text": "",
            "sha256": None, "fetched_at": now_iso(), "error": None}
    why = refused_reason(url)
    if why:
        page["error"] = "refused: " + why
        return page  # not cached: nothing was fetched
    own = c is None
    c = c or client()
    try:
        if not allowed(c, url):
            page["error"] = "refused: robots.txt disallows this page"
        else:
            r = _get(c, url)
            page.update(final_url=str(r.url), status=r.status_code, fetched_at=now_iso())
            if "html" in r.headers.get("content-type", "html"):
                page["html"] = r.text
                page["text"] = page_text(r.text)
                page["sha256"] = hashlib.sha256(page["text"].encode()).hexdigest()
    except httpx.HTTPError as e:
        page["error"] = f"unreachable: {type(e).__name__}"
    finally:
        if own:
            c.close()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(page))
    return page
