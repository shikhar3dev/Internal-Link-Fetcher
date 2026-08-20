# API Contracts

## POST /api/index/sitemap

Request:

```json
{
  "sitemap_url": "https://example.com/blog-sitemap.xml",
  "max_urls": 5000
}
```

Response:

```json
{
  "discovered_urls": 5284,
  "crawled_urls": 5284,
  "inserted_articles": 5100,
  "updated_articles": 0,
  "skipped_articles": 184,
  "errors": ["Failed: https://example.com/..."]
}
```

## POST /api/opportunities/analyze

Request:

```json
{
  "sitemap_url": "https://example.com/blog-sitemap.xml",
  "destination_url": "https://example.com/best-running-shoes",
  "anchor_text": "best running shoes",
  "max_results": 25
}
```

Response (shape):

```json
{
  "job_id": "uuid",
  "created_at": "2026-08-17T10:00:00Z",
  "discovered_urls": 5284,
  "analyzed_articles": 40,
  "excluded_already_linking": 412,
  "excluded_irrelevant": 22,
  "total_opportunities": 18,
  "opportunities": [
    {
      "schema_version": "1.0",
      "destination": {},
      "article": {},
      "scores": {},
      "decision": {},
      "anchor_analysis": {},
      "placement": {},
      "evidence": {}
    }
  ]
}
```

## GET /api/opportunities/{job_id}

Returns previously computed response for the job.
