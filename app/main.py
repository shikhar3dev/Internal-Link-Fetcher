from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException

from app.config import settings
from app.db.repository import Repository
from app.models.schemas import AnalyzeRequest, AnalyzeResponse, IndexRequest, IndexResponse
from app.services.crawl_service import crawl_article
from app.services.gemini_service import GeminiService
from app.services.opportunity_service import OpportunityService
from app.services.sitemap_service import chunked, get_sitemap_urls

app = FastAPI(
    title="Internal Linking Opportunity Finder API",
    version="1.0.0",
    description="Deterministic link exclusion + Gemini semantic placement for high-precision internal link building."
)

repo = Repository(settings.database_path)
schema_path = Path(__file__).resolve().parent / "db" / "schema.sql"
repo.init_schema(schema_path.read_text(encoding="utf-8"))

gemini = GeminiService(api_key=settings.gemini_api_key, model=settings.gemini_model)
opportunity_service = OpportunityService(repo=repo, gemini=gemini)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "internal-link-finder"}


@app.get("/api/domains")
def get_indexed_domains() -> dict:
    """Returns distinct indexed domains with article counts and demo status."""
    summaries = repo.fetch_domains_summary()
    return {
        "total_articles": sum(d["count"] for d in summaries),
        "domains": summaries,
    }


@app.post("/api/index/sitemap", response_model=IndexResponse)
async def index_sitemap(request: IndexRequest) -> IndexResponse:
    discovered = 0
    crawled = 0
    inserted_or_updated = 0
    skipped = 0
    errors: list[str] = []

    headers = {"User-Agent": settings.user_agent}
    async with httpx.AsyncClient(headers=headers, timeout=settings.request_timeout_seconds, follow_redirects=True) as client:
        urls = await get_sitemap_urls(str(request.sitemap_url), client, request.max_urls)
        discovered = len(urls)

        for batch in chunked(urls, 10):
            tasks = [crawl_article(url, client) for url in batch]
            results = await asyncio.gather(*tasks)
            for payload in results:
                crawled += 1
                if payload["crawl_status"] != "ok":
                    skipped += 1
                    errors.append(f"Failed ({payload.get('crawl_status')}): {payload['url_raw']}")
                    continue
                
                article_id = repo.upsert_article(payload)
                # Generate and save embedding if API key is active
                if settings.gemini_api_key:
                    emb = await gemini.get_embedding(f"{payload.get('title', '')}: {payload.get('content_text', '')[:2000]}")
                    if emb:
                        repo.save_embedding(article_id, emb)

                inserted_or_updated += 1

    return IndexResponse(
        discovered_urls=discovered,
        crawled_urls=crawled,
        inserted_articles=inserted_or_updated,
        updated_articles=0,
        skipped_articles=skipped,
        errors=errors[:50],
    )


@app.post("/api/opportunities/analyze", response_model=AnalyzeResponse)
async def analyze_opportunities(request: AnalyzeRequest) -> AnalyzeResponse:
    return await opportunity_service.analyze(request)


@app.get("/api/opportunities/{job_id}", response_model=AnalyzeResponse)
def get_analysis_job(job_id: str) -> AnalyzeResponse:
    data = opportunity_service.get_job(job_id)
    if not data:
        raise HTTPException(status_code=404, detail="Job not found")
    return data
