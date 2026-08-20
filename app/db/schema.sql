PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS articles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  domain TEXT NOT NULL,
  url_raw TEXT NOT NULL,
  url_normalized TEXT NOT NULL UNIQUE,
  canonical_url TEXT,
  title TEXT,
  meta_description TEXT,
  content_text TEXT,
  headings_json TEXT,
  paragraphs_json TEXT,
  word_count INTEGER DEFAULT 0,
  language TEXT DEFAULT 'en',
  content_hash TEXT,
  is_demo INTEGER DEFAULT 0, -- 1 for demo articles, 0 for real crawled production articles
  published_at TEXT,
  indexed_at TEXT DEFAULT CURRENT_TIMESTAMP,
  last_crawled_at TEXT,
  crawl_status TEXT DEFAULT 'SAVED', -- 'SAVED', 'FAILED', 'BLOCKED', 'DUPLICATE', 'NO_CONTENT'
  http_status INTEGER DEFAULT 200,
  crawl_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_articles_domain ON articles(domain);
CREATE INDEX IF NOT EXISTS idx_articles_canonical ON articles(canonical_url);
CREATE INDEX IF NOT EXISTS idx_articles_content_hash ON articles(content_hash);
CREATE INDEX IF NOT EXISTS idx_articles_is_demo ON articles(is_demo);

CREATE TABLE IF NOT EXISTS article_links (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  article_id INTEGER NOT NULL,
  href_raw TEXT NOT NULL,
  href_resolved TEXT NOT NULL,
  href_normalized TEXT NOT NULL,
  anchor_text TEXT,
  is_internal INTEGER DEFAULT 1,
  rel_nofollow INTEGER DEFAULT 0,
  paragraph_index INTEGER DEFAULT 0,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_links_article_id ON article_links(article_id);
CREATE INDEX IF NOT EXISTS idx_links_href_norm ON article_links(href_normalized);

CREATE TABLE IF NOT EXISTS article_embeddings (
  article_id INTEGER PRIMARY KEY,
  embedding_blob BLOB NOT NULL,
  model_version TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS destination_pages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  domain TEXT NOT NULL,
  url_raw TEXT NOT NULL,
  url_normalized TEXT NOT NULL UNIQUE,
  title TEXT,
  content_text TEXT,
  summary_json TEXT,
  analyzed_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS opportunities (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  destination_id INTEGER NOT NULL,
  article_id INTEGER NOT NULL,
  link_type TEXT DEFAULT 'INTERNAL', -- 'INTERNAL' or 'EXTERNAL'
  overall_score REAL,
  semantic_relevance REAL,
  anchor_match_quality REAL,
  context_quality REAL,
  linkability_score REAL,
  content_quality REAL,
  opportunity_value REAL,
  anchor_status TEXT, -- 'EXACT_UNLINKED_ANCHOR' or 'SEMANTIC_ANCHOR_CANDIDATE'
  status TEXT DEFAULT 'ACCEPTED', -- 'ACCEPTED', 'REJECTED', 'ALREADY_LINKED', 'WRONG_DOMAIN', 'LOW_CONTEXT'
  reason TEXT,
  paragraph_index INTEGER,
  sentence_index INTEGER,
  char_start INTEGER,
  char_end INTEGER,
  original_sentence TEXT,
  suggested_sentence TEXT,
  markdown_link TEXT,
  html_link TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(destination_id) REFERENCES destination_pages(id) ON DELETE CASCADE,
  FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE
);
