from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
import numpy as np


class Repository:
    def __init__(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON;")
        return con

    def init_schema(self, schema_sql: str) -> None:
        with self.connect() as con:
            # Check if articles table exists; ensure all columns exist before running index scripts
            cur = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='articles';")
            table_exists = bool(cur.fetchone())
            if table_exists:
                cur_cols = con.execute("PRAGMA table_info(articles);")
                cols = {row["name"] for row in cur_cols.fetchall()}
                if "domain" not in cols:
                    con.execute("ALTER TABLE articles ADD COLUMN domain TEXT DEFAULT '';")
                if "is_demo" not in cols:
                    con.execute("ALTER TABLE articles ADD COLUMN is_demo INTEGER DEFAULT 0;")
                if "crawl_error" not in cols:
                    con.execute("ALTER TABLE articles ADD COLUMN crawl_error TEXT;")
                if "indexed_at" not in cols:
                    con.execute("ALTER TABLE articles ADD COLUMN indexed_at TEXT;")
                if "published_at" not in cols:
                    con.execute("ALTER TABLE articles ADD COLUMN published_at TEXT;")

            cur_l = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='article_links';")
            if bool(cur_l.fetchone()):
                cur_links = con.execute("PRAGMA table_info(article_links);")
                cols_l = {row["name"] for row in cur_links.fetchall()}
                if "is_internal" not in cols_l:
                    con.execute("ALTER TABLE article_links ADD COLUMN is_internal INTEGER DEFAULT 1;")
                if "paragraph_index" not in cols_l:
                    con.execute("ALTER TABLE article_links ADD COLUMN paragraph_index INTEGER DEFAULT 0;")

            con.executescript(schema_sql)

    def clear_all_articles(self) -> None:
        """Deletes all indexed articles, links, and embeddings."""
        with self.connect() as con:
            con.execute("DELETE FROM articles;")
            con.execute("DELETE FROM article_links;")
            con.execute("DELETE FROM article_embeddings;")
            con.execute("DELETE FROM opportunities;")

    def delete_domain(self, domain: str) -> int:
        """Deletes all indexed articles belonging to a specific domain."""
        with self.connect() as con:
            cur = con.execute("DELETE FROM articles WHERE domain = ?", (domain,))
            return cur.rowcount

    def fetch_domains_summary(self) -> list[dict[str, Any]]:
        """Returns distinct domains with article counts and demo status."""
        with self.connect() as con:
            rows = con.execute(
                """
                SELECT domain, is_demo, COUNT(*) as count, MAX(indexed_at) as last_indexed
                FROM articles
                WHERE crawl_status = 'SAVED' AND domain != ''
                GROUP BY domain, is_demo
                ORDER BY count DESC
                """
            ).fetchall()
            return [
                {
                    "domain": r["domain"],
                    "is_demo": bool(r["is_demo"]),
                    "count": int(r["count"]),
                    "last_indexed": r["last_indexed"]
                }
                for r in rows
            ]

    def upsert_article(self, payload: dict[str, Any]) -> int:
        with self.connect() as con:
            domain = payload.get("domain", "")
            is_demo = 1 if payload.get("is_demo") else 0
            cur = con.execute(
                """
                INSERT INTO articles (
                    domain, url_raw, url_normalized, canonical_url, title, meta_description,
                    content_text, headings_json, paragraphs_json, word_count,
                    language, content_hash, is_demo, last_crawled_at, crawl_status, http_status, crawl_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url_normalized) DO UPDATE SET
                    domain=excluded.domain,
                    canonical_url=excluded.canonical_url,
                    title=excluded.title,
                    meta_description=excluded.meta_description,
                    content_text=excluded.content_text,
                    headings_json=excluded.headings_json,
                    paragraphs_json=excluded.paragraphs_json,
                    word_count=excluded.word_count,
                    language=excluded.language,
                    content_hash=excluded.content_hash,
                    is_demo=excluded.is_demo,
                    last_crawled_at=excluded.last_crawled_at,
                    crawl_status=excluded.crawl_status,
                    http_status=excluded.http_status,
                    crawl_error=excluded.crawl_error
                """,
                (
                    domain,
                    payload["url_raw"],
                    payload["url_normalized"],
                    payload.get("canonical_url"),
                    payload.get("title"),
                    payload.get("meta_description"),
                    payload.get("content_text"),
                    json.dumps(payload.get("headings", [])),
                    json.dumps(payload.get("paragraphs", [])),
                    payload.get("word_count", 0),
                    payload.get("language", "en"),
                    payload.get("content_hash"),
                    is_demo,
                    payload.get("last_crawled_at"),
                    payload.get("crawl_status", "SAVED"),
                    payload.get("http_status", 200),
                    payload.get("crawl_error"),
                ),
            )
            article_id = cur.lastrowid

            if not article_id:
                existing = con.execute(
                    "SELECT id FROM articles WHERE url_normalized = ?",
                    (payload["url_normalized"],),
                ).fetchone()
                if not existing:
                    raise RuntimeError("Failed to resolve upserted article id")
                article_id = int(existing["id"])

            con.execute("DELETE FROM article_links WHERE article_id = ?", (article_id,))
            for link in payload.get("links", []):
                con.execute(
                    """
                    INSERT INTO article_links (
                        article_id, href_raw, href_resolved, href_normalized, anchor_text, is_internal, rel_nofollow
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        article_id,
                        link["href_raw"],
                        link["href_resolved"],
                        link["href_normalized"],
                        link.get("anchor_text"),
                        1 if link.get("is_internal", True) else 0,
                        1 if link.get("rel_nofollow") else 0,
                    ),
                )
            return int(article_id)

    def save_embedding(self, article_id: int, embedding: list[float], model_version: str = "text-embedding-004") -> None:
        blob = np.array(embedding, dtype=np.float32).tobytes()
        with self.connect() as con:
            con.execute(
                """
                INSERT INTO article_embeddings (article_id, embedding_blob, model_version)
                VALUES (?, ?, ?)
                ON CONFLICT(article_id) DO UPDATE SET
                    embedding_blob=excluded.embedding_blob,
                    model_version=excluded.model_version
                """,
                (article_id, blob, model_version),
            )

    def fetch_articles(self, domain: str | None = None, is_demo: bool | None = None) -> list[sqlite3.Row]:
        with self.connect() as con:
            query = "SELECT id, domain, title, url_normalized, canonical_url, content_text, paragraphs_json, is_demo FROM articles WHERE crawl_status = 'SAVED'"
            params = []
            if domain is not None:
                query += " AND domain = ?"
                params.append(domain)
            if is_demo is not None:
                query += " AND is_demo = ?"
                params.append(1 if is_demo else 0)
            return con.execute(query, params).fetchall()

    def fetch_articles_with_embeddings(self, domain: str | None = None, is_demo: bool | None = None) -> list[dict[str, Any]]:
        with self.connect() as con:
            query = """
                SELECT a.id, a.domain, a.title, a.url_normalized, a.canonical_url, a.content_text, a.paragraphs_json, a.word_count, a.headings_json, a.is_demo, e.embedding_blob
                FROM articles a
                LEFT JOIN article_embeddings e ON a.id = e.article_id
                WHERE a.crawl_status = 'SAVED'
            """
            params = []
            if domain is not None:
                query += " AND a.domain = ?"
                params.append(domain)
            if is_demo is not None:
                query += " AND a.is_demo = ?"
                params.append(1 if is_demo else 0)

            rows = con.execute(query, params).fetchall()
            results = []
            for r in rows:
                emb = None
                if r["embedding_blob"]:
                    emb = np.frombuffer(r["embedding_blob"], dtype=np.float32).tolist()
                results.append({
                    "id": int(r["id"]),
                    "domain": r["domain"],
                    "title": r["title"],
                    "url_normalized": r["url_normalized"],
                    "canonical_url": r["canonical_url"],
                    "content_text": r["content_text"],
                    "paragraphs_json": r["paragraphs_json"],
                    "headings_json": r["headings_json"],
                    "word_count": int(r["word_count"] or 0),
                    "is_demo": bool(r["is_demo"]),
                    "embedding": emb,
                })
            return results

    def fetch_article_links(self, article_id: int) -> list[str]:
        with self.connect() as con:
            rows = con.execute(
                "SELECT href_normalized FROM article_links WHERE article_id = ?",
                (article_id,),
            ).fetchall()
            return [str(r["href_normalized"]) for r in rows]
