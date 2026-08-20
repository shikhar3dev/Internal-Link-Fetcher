from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup

from app.core.url_utils import get_domain, normalize_url

logger = logging.getLogger("crawl_service")

__all__ = [
    "crawl_article",
    "get_domain",
    "extract_title_and_meta",
    "extract_headings_and_paragraphs",
    "extract_links",
    "fetch_with_retry",
]


def extract_title_and_meta(html_text: str) -> tuple[str | None, str | None, str | None]:
    """Extracts title, meta description, and canonical URL from raw HTML."""
    soup = BeautifulSoup(html_text, "html.parser")

    # Title
    title = None
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)

    # Meta Description
    meta_desc = None
    meta_tag = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta", attrs={"property": "og:description"}
    )
    if meta_tag and meta_tag.get("content"):
        meta_desc = str(meta_tag["content"]).strip()

    # Canonical URL
    canonical_url = None
    canon_tag = soup.find("link", attrs={"rel": "canonical"})
    if canon_tag and canon_tag.get("href"):
        canonical_url = str(canon_tag["href"]).strip()

    return title, meta_desc, canonical_url


def extract_headings_and_paragraphs(html_text: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Extracts clean headings and main body paragraphs."""
    soup = BeautifulSoup(html_text, "html.parser")
    
    # Remove boilerplate elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "svg"]):
        tag.decompose()

    headings: list[dict[str, Any]] = []
    for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        text = h.get_text(strip=True)
        if text:
            headings.append({"level": h.name.lower(), "text": text})

    paragraphs: list[str] = []
    for p in soup.find_all("p"):
        text = p.get_text(" ", strip=True)
        # Keep meaningful paragraphs (> 20 chars and > 4 words)
        if len(text) > 20 and len(text.split()) >= 4:
            paragraphs.append(text)

    return headings, paragraphs


def extract_links(html_text: str, base_url: str) -> list[dict[str, Any]]:
    """Extracts all outbound links with resolve, normalized targets, and is_internal flag."""
    soup = BeautifulSoup(html_text, "html.parser")
    source_domain = get_domain(base_url)
    links: list[dict[str, Any]] = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue

        resolved = urljoin(base_url, href)
        normalized = normalize_url(resolved, base_url=base_url)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)

        target_domain = get_domain(normalized)
        is_internal = (target_domain == source_domain) if (target_domain and source_domain) else True

        anchor_text = a.get_text(" ", strip=True)
        rel_vals = [r.lower() for r in a.get("rel", [])] if isinstance(a.get("rel"), list) else [str(a.get("rel", "")).lower()]
        rel_nofollow = "nofollow" in rel_vals or "sponsored" in rel_vals

        links.append({
            "href_raw": href,
            "href_resolved": resolved,
            "href_normalized": normalized,
            "anchor_text": anchor_text,
            "is_internal": is_internal,
            "rel_nofollow": rel_nofollow,
        })

    return links


async def fetch_with_retry(
    url: str,
    client: httpx.AsyncClient,
    max_attempts: int = 3,
) -> tuple[int, str, str, str]:
    """
    Performs HTTP GET with exponential backoff retries.
    Returns: (http_status, html_content, crawl_status, error_message)
    """
    crawl_status = "FAILED"
    error_msg = ""
    status_code = 0
    html_text = ""

    for attempt in range(1, max_attempts + 1):
        try:
            resp = await client.get(url, follow_redirects=True, timeout=18)
            status_code = resp.status_code

            if status_code == 200:
                html_text = resp.text
                crawl_status = "FETCHED"
                error_msg = ""
                break
            elif status_code == 429:
                crawl_status = "BLOCKED"
                error_msg = f"HTTP 429 Rate Limited (Attempt {attempt}/{max_attempts}). Server requested backoff."
                if attempt < max_attempts:
                    await asyncio.sleep(2.0 * attempt)
            elif status_code in (401, 403):
                crawl_status = "BLOCKED"
                error_msg = f"HTTP {status_code} Access Denied (Attempt {attempt}/{max_attempts}). Bot/WAF protected."
                # Do not retry on 403
                break
            elif 500 <= status_code < 600:
                crawl_status = "FAILED"
                error_msg = f"HTTP {status_code} Server Error (Attempt {attempt}/{max_attempts})."
                if attempt < max_attempts:
                    await asyncio.sleep(1.5 * attempt)
            else:
                crawl_status = "FAILED"
                error_msg = f"HTTP {status_code} Error (Attempt {attempt}/{max_attempts})."
                break

        except httpx.TimeoutException:
            crawl_status = "FAILED"
            error_msg = f"Request timed out after 18s (Attempt {attempt}/{max_attempts})."
            if attempt < max_attempts:
                await asyncio.sleep(1.0 * attempt)

        except httpx.NetworkError as ne:
            crawl_status = "FAILED"
            error_msg = f"Connection error: {str(ne) or 'Server disconnected without sending a response'} (Attempt {attempt}/{max_attempts})."
            if attempt < max_attempts:
                await asyncio.sleep(1.5 * attempt)

        except Exception as e:
            crawl_status = "FAILED"
            error_msg = f"Fetch error: {str(e)} (Attempt {attempt}/{max_attempts})."
            if attempt < max_attempts:
                await asyncio.sleep(1.0 * attempt)

    return status_code, html_text, crawl_status, error_msg


async def crawl_article(url: str, client: httpx.AsyncClient) -> dict[str, Any]:
    """
    Crawls and extracts clean article content with full canonical resolution and failure diagnosis.
    """
    url_norm = normalize_url(url)
    domain = get_domain(url_norm or url)
    now_iso = datetime.now(timezone.utc).isoformat()

    status_code, html_text, crawl_status, error_msg = await fetch_with_retry(url, client, max_attempts=3)

    if crawl_status != "FETCHED" or not html_text:
        return {
            "domain": domain,
            "url_raw": url,
            "url_normalized": url_norm or url,
            "canonical_url": None,
            "title": "",
            "meta_description": "",
            "content_text": "",
            "headings": [],
            "paragraphs": [],
            "links": [],
            "word_count": 0,
            "language": "en",
            "content_hash": "",
            "last_crawled_at": now_iso,
            "crawl_status": crawl_status,
            "http_status": status_code,
            "crawl_error": error_msg,
        }

    # Extract metadata & canonical
    title, meta_desc, raw_canonical = extract_title_and_meta(html_text)
    canonical_url = normalize_url(raw_canonical, base_url=url) if raw_canonical else url_norm

    # Extract main text via Trafilatura
    extracted_text = trafilatura.extract(
        html_text,
        url=url,
        include_links=True,
        include_formatting=False,
        output_format="txt",
    )

    headings, paragraphs = extract_headings_and_paragraphs(html_text)

    # Fallback text if Trafilatura fails
    if not extracted_text:
        extracted_text = " ".join(paragraphs)

    clean_content = (extracted_text or "").strip()
    word_count = len(clean_content.split())

    if word_count < 15:
        return {
            "domain": domain,
            "url_raw": url,
            "url_normalized": url_norm,
            "canonical_url": canonical_url,
            "title": title or "",
            "meta_description": meta_desc or "",
            "content_text": clean_content,
            "headings": headings,
            "paragraphs": paragraphs,
            "links": [],
            "word_count": word_count,
            "language": "en",
            "content_hash": "",
            "last_crawled_at": now_iso,
            "crawl_status": "NO_CONTENT",
            "http_status": status_code,
            "crawl_error": "Extracted text is too short (<15 words). Likely a category/index page or empty.",
        }

    # Content Hash (SHA-256)
    content_hash = hashlib.sha256(clean_content.encode("utf-8")).hexdigest()

    # Outbound links
    links = extract_links(html_text, base_url=url)

    return {
        "domain": domain,
        "url_raw": url,
        "url_normalized": url_norm,
        "canonical_url": canonical_url,
        "title": title or "Untitled Article",
        "meta_description": meta_desc or "",
        "content_text": clean_content,
        "headings": headings,
        "paragraphs": paragraphs,
        "links": links,
        "word_count": word_count,
        "language": "en",
        "content_hash": content_hash,
        "last_crawled_at": now_iso,
        "crawl_status": "SAVED",
        "http_status": status_code,
        "crawl_error": None,
    }
