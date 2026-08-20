import pytest
from app.core.url_utils import normalize_url, destination_in_links


def test_url_normalization_standardization():
    # Lowercase domain, force https, strip port
    assert normalize_url("http://EXAMPLE.com:80/blog/post") == "https://example.com/blog/post"
    assert normalize_url("https://example.com:443/blog/post/") == "https://example.com/blog/post"
    assert normalize_url("https://www.example.com/blog/post") == "https://example.com/blog/post"


def test_url_normalization_tracking_parameters():
    # Strips UTM params, gclid, fbclid, ref, and fragments
    raw = "https://example.com/blog/shoes?utm_source=twitter&utm_medium=social&gclid=12345#reviews"
    assert normalize_url(raw) == "https://example.com/blog/shoes"


def test_url_normalization_default_files():
    # Strips index.html, index.php
    assert normalize_url("https://example.com/category/shoes/index.html") == "https://example.com/category/shoes"
    assert normalize_url("https://example.com/index.php") == "https://example.com/"


def test_relative_url_resolution():
    base = "https://example.com/blog/running-tips"
    assert normalize_url("../best-shoes", base_url=base) == "https://example.com/best-shoes"
    assert normalize_url("/gear/shoes", base_url=base) == "https://example.com/gear/shoes"


def test_destination_in_links():
    article_url = "https://example.com/blog/marathon-prep"
    outbound_links = [
        "https://example.com/about",
        "https://example.com/best-running-shoes?utm_source=blog",
        "https://external.com/product"
    ]
    
    # Matches even with UTM params and trailing slash differences
    assert destination_in_links(article_url, outbound_links, "https://example.com/best-running-shoes") is True
    assert destination_in_links(article_url, outbound_links, "https://www.example.com/best-running-shoes/") is True
    
    # Correctly identifies unlinked page
    assert destination_in_links(article_url, outbound_links, "https://example.com/trail-running-shoes") is False
