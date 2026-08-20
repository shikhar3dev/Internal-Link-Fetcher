import os
import sqlite3
from pathlib import Path
import pytest
from app.db.repository import Repository
from app.core.url_utils import normalize_url


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test.db"
    repo = Repository(str(db_file))
    
    schema_path = Path(__file__).resolve().parents[1] / "app" / "db" / "schema.sql"
    repo.init_schema(schema_path.read_text(encoding="utf-8"))
    return repo


def test_repository_upsert_and_fetch(temp_db):
    payload = {
        "domain": "example.com",
        "url_raw": "https://example.com/blog/running-tips",
        "url_normalized": "https://example.com/blog/running-tips",
        "canonical_url": "https://example.com/blog/running-tips",
        "title": "Essential Running Tips",
        "content_text": "Running requires great shoes and dedication.",
        "paragraphs": ["Running requires great shoes and dedication."],
        "headings": [{"level": "h1", "text": "Essential Running Tips"}],
        "word_count": 6,
        "language": "en",
        "content_hash": "hash123",
        "last_crawled_at": "2026-08-20T12:00:00Z",
        "crawl_status": "SAVED",
        "http_status": 200,
        "crawl_error": None,
        "links": [
            {
                "href_raw": "/gear/shoes",
                "href_resolved": "https://example.com/gear/shoes",
                "href_normalized": "https://example.com/gear/shoes",
                "anchor_text": "gear shoes",
                "is_internal": True,
                "rel_nofollow": False
            }
        ]
    }

    art_id = temp_db.upsert_article(payload)
    assert art_id > 0

    articles = temp_db.fetch_articles(domain="example.com")
    assert len(articles) == 1
    assert articles[0]["title"] == "Essential Running Tips"
    assert articles[0]["domain"] == "example.com"

    links = temp_db.fetch_article_links(art_id)
    assert len(links) == 1
    assert links[0] == "https://example.com/gear/shoes"

    # Domain summary check
    summary = temp_db.fetch_domains_summary()
    assert len(summary) == 1
    assert summary[0]["domain"] == "example.com"
    assert summary[0]["count"] == 1
