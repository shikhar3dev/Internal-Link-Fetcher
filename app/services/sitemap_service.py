from __future__ import annotations

import gzip
import re
from typing import Iterable
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import httpx

_LOC_REGEX = re.compile(r"<loc>\s*(https?://[^<\s]+)\s*</loc>", re.IGNORECASE)

MEDIA_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".ico",
    ".pdf", ".mp4", ".mp3", ".avi", ".mov", ".zip", ".tar", ".gz",
    ".xml", ".xml.gz"
)


def is_html_article_url(url: str) -> bool:
    """Checks if a URL is likely an HTML article rather than media asset."""
    p = urlparse(url)
    path = p.path.lower()
    return not path.endswith(MEDIA_EXTENSIONS)


def _extract_locs(content_bytes: bytes) -> list[str]:
    """
    Extracts <loc> URLs from XML bytes or gzipped XML bytes.
    Tries ElementTree first, with a regex fallback for unescaped characters or malformed tokens.
    """
    if content_bytes.startswith(b"\x1f\x8b"):
        try:
            content_bytes = gzip.decompress(content_bytes)
        except Exception:
            pass

    text = content_bytes.decode("utf-8", errors="replace").strip()
    locs: list[str] = []

    try:
        root = ElementTree.fromstring(text)
        for loc in root.findall(".//{*}loc"):
            if loc.text and loc.text.strip():
                locs.append(loc.text.strip())
        if locs:
            return locs
    except Exception:
        pass

    for match in _LOC_REGEX.finditer(text):
        url = match.group(1).strip()
        if url:
            locs.append(url)

    return locs


async def discover_sitemaps_from_robots(base_url: str, client: httpx.AsyncClient) -> list[str]:
    """Discovers sitemap URLs by inspecting the site's /robots.txt."""
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme or 'https'}://{parsed.netloc}"
    robots_url = urljoin(origin, "/robots.txt")

    sitemaps = []
    try:
        resp = await client.get(robots_url, timeout=12)
        if resp.status_code == 200:
            for line in resp.text.splitlines():
                if line.strip().lower().startswith("sitemap:"):
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        sm = parts[1].strip()
                        if sm.startswith("http"):
                            sitemaps.append(sm)
    except Exception:
        pass

    if not sitemaps:
        sitemaps.append(urljoin(origin, "/sitemap.xml"))
        sitemaps.append(urljoin(origin, "/sitemap_index.xml"))

    return sitemaps


async def get_sitemap_urls(
    input_url: str, client: httpx.AsyncClient, max_urls: int = 5000
) -> list[str]:
    """
    Fetches and parses URLs from XML sitemaps, sitemap indexes, or auto-discovers from HTML pages.
    """
    input_clean = input_url.strip()
    if not input_clean.startswith("http"):
        input_clean = "https://" + input_clean

    pending = [input_clean]
    seen = set()
    out: list[str] = []

    while pending and len(out) < max_urls:
        current = pending.pop(0)
        if current in seen:
            continue
        seen.add(current)

        try:
            resp = await client.get(current, follow_redirects=True, timeout=20)
            if resp.status_code != 200:
                continue

            content_type = resp.headers.get("content-type", "").lower()
            raw_body = resp.content

            is_html = (
                "text/html" in content_type
                or b"<!doctype html" in raw_body[:200].lower()
                or b"<html" in raw_body[:200].lower()
            )

            if is_html:
                if current == input_clean:
                    discovered_sitemaps = await discover_sitemaps_from_robots(current, client)
                    if is_html_article_url(current):
                        out.append(current)
                    for sm in discovered_sitemaps:
                        if sm not in seen:
                            pending.append(sm)
                    continue
                else:
                    if is_html_article_url(current):
                        out.append(current)
                    continue

            locs = _extract_locs(raw_body)
            xml_text = raw_body.decode("utf-8", errors="replace")
            is_index = "<sitemapindex" in xml_text.lower() or "<sitemap>" in xml_text.lower()

            if is_index and locs:
                pending.extend(locs[:50])
            else:
                out.extend([l for l in locs if is_html_article_url(l)])

        except Exception:
            continue

    # Deduplicate while preserving order
    deduped: list[str] = []
    seen_urls: set[str] = set()
    for url in out:
        if url not in seen_urls and is_html_article_url(url):
            seen_urls.add(url)
            deduped.append(url)

    return deduped[:max_urls]


def chunked(items: list[str], size: int) -> Iterable[list[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]
