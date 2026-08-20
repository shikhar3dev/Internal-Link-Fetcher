from pathlib import Path
import pytest
from pydantic import HttpUrl

from app.db.repository import Repository
from app.models.schemas import AnalyzeRequest
from app.services.gemini_service import GeminiService
from app.services.opportunity_service import OpportunityService


@pytest.fixture
def test_env(tmp_path):
    db_file = tmp_path / "test_opp.db"
    repo = Repository(str(db_file))
    schema_path = Path(__file__).resolve().parents[1] / "app" / "db" / "schema.sql"
    repo.init_schema(schema_path.read_text(encoding="utf-8"))
    gemini = GeminiService(api_key="")
    service = OpportunityService(repo=repo, gemini=gemini)
    return repo, service


@pytest.mark.asyncio
async def test_opportunity_service_pipeline(test_env):
    repo, service = test_env
    
    # 1. Insert an article on example.com with exact unlinked anchor
    repo.upsert_article({
        "domain": "example.com",
        "is_demo": 1,
        "url_raw": "https://example.com/blog/marathon-prep",
        "url_normalized": "https://example.com/blog/marathon-prep",
        "title": "Marathon Preparation Guide",
        "content_text": "To prepare for a marathon, having comfortable footwear is key. Finding the best running shoes reduces fatigue during long distance races.",
        "paragraphs": [
            "To prepare for a marathon, having comfortable footwear is key.",
            "Finding the best running shoes reduces fatigue during long distance races."
        ],
        "headings": [{"level": "h1", "text": "Marathon Prep"}],
        "word_count": 22,
        "links": []
    })
    
    # 2. Insert an article on example.com that ALREADY links to the target destination
    repo.upsert_article({
        "domain": "example.com",
        "is_demo": 1,
        "url_raw": "https://example.com/blog/already-linked-post",
        "url_normalized": "https://example.com/blog/already-linked-post",
        "title": "Old Shoe Reviews",
        "content_text": "We already linked to best running shoes in our previous post.",
        "paragraphs": ["We already linked to best running shoes in our previous post."],
        "headings": [],
        "word_count": 11,
        "links": [
            {
                "href_raw": "https://example.com/best-running-shoes",
                "href_resolved": "https://example.com/best-running-shoes",
                "href_normalized": "https://example.com/best-running-shoes",
                "anchor_text": "best running shoes",
                "is_internal": True,
                "rel_nofollow": False
            }
        ]
    })

    # 3. Insert an article on DIFFERENT domain (runnersworld.com)
    repo.upsert_article({
        "domain": "runnersworld.com",
        "is_demo": 0,
        "url_raw": "https://www.runnersworld.com/gear/shoes-article",
        "url_normalized": "https://runnersworld.com/gear/shoes-article",
        "title": "Runners World Shoe Guide",
        "content_text": "Here are the best running shoes for marathon runners in 2026.",
        "paragraphs": ["Here are the best running shoes for marathon runners in 2026."],
        "headings": [],
        "word_count": 12,
        "links": []
    })
    
    # Target URL is on example.com
    request = AnalyzeRequest(
        sitemap_url=HttpUrl("https://example.com/blog-sitemap.xml"),
        destination_url=HttpUrl("https://example.com/best-running-shoes"),
        anchor_text="best running shoes",
        max_results=10
    )
    
    response = await service.analyze(request, active_domain_override="example.com", is_demo_mode=True)
    
    # Verify deterministic exclusion of already linked article
    assert response.excluded_already_linking == 1
    assert len(response.excluded_articles_log) >= 1
    assert response.excluded_articles_log[0].reason_code == "ALREADY_LINKED"
    
    # Verify top opportunity is strictly from example.com (Domain Scoped)
    assert response.total_opportunities >= 1
    opp = response.opportunities[0]
    assert opp.source_article.domain == "example.com"
    assert opp.target_page.domain == "example.com"
    assert opp.anchor_status == "EXACT_UNLINKED_ANCHOR"
    assert opp.scores.overall_score >= 70.0
    assert "[best running shoes](https://example.com/best-running-shoes)" in opp.placement.ready_to_paste_markdown
    assert '<a href="https://example.com/best-running-shoes">best running shoes</a>' in opp.placement.ready_to_paste_html
