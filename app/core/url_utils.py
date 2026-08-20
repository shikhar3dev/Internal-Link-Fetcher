from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

# Universal tracking & analytics parameters to strip
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_name", "gclid", "fbclid", "msclkid", "mc_cid", "mc_eid",
    "ref", "source", "_ga", "_gl", "yclid", "zanpid", "dclid"
}

DEFAULT_FILES_PATTERN = re.compile(r"/index\.(html|htm|php|asp|aspx)$", re.IGNORECASE)
RAW_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)


def normalize_domain(url_or_domain: str) -> str:
    """
    Normalizes a domain or URL to a clean lowercase domain string for strict partition comparison.
    - Strips protocol (http://, https://)
    - Strips 'www.' prefix
    - Strips default ports (:80, :443)
    - Strips trailing slashes, dots, path segments, and query strings
    - Converts to lowercase
    Example: 'https://www.example.com/blog/' -> 'example.com'
    """
    if not url_or_domain:
        return ""

    raw = url_or_domain.strip().lower()
    # Add protocol if missing so urlparse parses netloc correctly
    if not raw.startswith(("http://", "https://", "//")):
        raw = "https://" + raw

    try:
        parsed = urlparse(raw)
        netloc = parsed.netloc or parsed.path
        
        # Strip path if netloc was not parsed properly
        if "/" in netloc:
            netloc = netloc.split("/")[0]

        # Strip port numbers
        if ":" in netloc:
            host, port = netloc.split(":", 1)
            if port in ("80", "443", ""):
                netloc = host
            else:
                netloc = f"{host}:{port}"

        # Strip www.
        if netloc.startswith("www."):
            netloc = netloc[4:]

        # Strip trailing dot
        netloc = netloc.rstrip(".")

        return netloc
    except Exception:
        return ""


def get_domain(url: str) -> str:
    """Alias for normalize_domain for backwards compatibility."""
    return normalize_domain(url)


def classify_link_type(source_url: str, target_url: str) -> str:
    """
    Classifies link relationship as 'INTERNAL' (same domain) or 'EXTERNAL' (cross domain).
    """
    source_dom = normalize_domain(source_url)
    target_dom = normalize_domain(target_url)
    if source_dom and target_dom and source_dom == target_dom:
        return "INTERNAL"
    return "EXTERNAL"


def normalize_url(raw_url: str, base_url: str | None = None, keep_params: set[str] | None = None) -> str:
    """
    Normalizes a URL to a standard canonical format for reliable deterministic comparison.
    Forces HTTPS, normalizes domain casing, removes default ports (80/443), removes 'www.',
    strips tracking parameters, removes default index files, and cleans trailing slashes.
    """
    if not raw_url or raw_url.strip().startswith(("javascript:", "mailto:", "tel:", "#")):
        return ""

    absolute = urljoin(base_url, raw_url.strip()) if base_url else raw_url.strip()
    parsed = urlparse(absolute)

    raw_scheme = (parsed.scheme or "https").lower()
    if raw_scheme not in ("http", "https"):
        return ""

    scheme = "https"
    netloc = normalize_domain(parsed.netloc or "")
    if not netloc:
        return ""

    # Path normalization: strip default index files, collapse consecutive slashes
    path = parsed.path or "/"
    path = DEFAULT_FILES_PATTERN.sub("", path)
    path = re.sub(r"/+", "/", path)

    # Strip trailing slash (unless it is root '/')
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    elif not path:
        path = "/"

    # Clean query parameters: remove tracking params, sort remainder
    keep_params = {k.lower() for k in keep_params} if keep_params else set()
    cleaned_query_params: list[tuple[str, str]] = []
    
    if parsed.query:
        for k, v in parse_qsl(parsed.query, keep_blank_values=True):
            lk = k.lower()
            if lk in keep_params:
                cleaned_query_params.append((k, v))
            elif lk in TRACKING_PARAMS or any(lk.startswith(pfx) for pfx in ("utm_", "ga_")):
                continue
            else:
                cleaned_query_params.append((k, v))

        cleaned_query_params.sort(key=lambda x: x[0].lower())

    new_query = urlencode(cleaned_query_params, doseq=True)

    return urlunparse((scheme, netloc, path, "", new_query, ""))


def destination_in_links(
    article_url: str,
    hrefs: list[str],
    destination_url: str,
    raw_article_text: str = ""
) -> bool:
    """
    Checks if destination_url is present in the list of outbound hrefs OR raw article text.
    Handles HTML hrefs, Markdown links, and raw URL mentions.
    """
    destination_norm = normalize_url(destination_url)
    if not destination_norm:
        return False

    # 1. Check extracted structured outbound links
    for href in hrefs:
        try:
            link_norm = normalize_url(href, base_url=article_url)
            if link_norm == destination_norm:
                return True
        except Exception:
            continue

    # 2. Check for raw URL mentions in article body
    if raw_article_text:
        for match in RAW_URL_PATTERN.finditer(raw_article_text):
            found_norm = normalize_url(match.group(0), base_url=article_url)
            if found_norm == destination_norm:
                return True

    return False
