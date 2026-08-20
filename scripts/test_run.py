from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.db.repository import Repository
from app.models.schemas import AnalyzeRequest
from app.services.gemini_service import GeminiService
from app.services.opportunity_service import OpportunityService
from scripts.seed_demo_data import seed
from pydantic import HttpUrl


async def run_test():
    repo = Repository(settings.database_path)
    schema_path = Path(__file__).resolve().parents[1] / "app" / "db" / "schema.sql"
    repo.init_schema(schema_path.read_text(encoding="utf-8"))
    
    # Re-seed demo data to ensure domain and is_demo columns are populated
    seed()
    
    gemini = GeminiService(api_key=settings.gemini_api_key, model=settings.gemini_model)
    service = OpportunityService(repo=repo, gemini=gemini)
    
    print("\n--- Test 1: Internal Linking on same domain (example.com -> example.com) ---")
    request_internal = AnalyzeRequest(
        sitemap_url=HttpUrl("https://example.com/blog-sitemap.xml"),
        destination_url=HttpUrl("https://example.com/best-running-shoes"),
        anchor_text="best running shoes",
        max_results=5,
        allow_external=False
    )
    
    res = await service.analyze(request_internal, active_domain_override="example.com", is_demo_mode=True)
    
    print(f"\n================ ANALYSIS RESULTS ================")
    print(f"Target Validation: {res.target_validation.validation_message}")
    print(f"Total Indexed Posts (Scoped to Domain): {res.discovered_urls}")
    print(f"Excluded (Already Linking): {res.excluded_already_linking}")
    print(f"Excluded (Irrelevant / Weak Context): {res.excluded_irrelevant}")
    print(f"Recommended Opportunities: {res.total_opportunities}")
    print("==================================================\n")
    
    for idx, opp in enumerate(res.opportunities, start=1):
        print(f"[{idx}] {opp.source_article.title}")
        print(f"    Source URL: {opp.source_article.url}")
        print(f"    Target URL: {opp.target_page.url}")
        print(f"    Domain: {opp.source_article.domain}")
        print(f"    Link Type: {opp.link_type}")
        print(f"    Anchor Status: {opp.anchor_status}")
        print(f"    Composite Score: {opp.scores.overall_score}/100")
        print(f"      - Semantic: {opp.scores.semantic_relevance}")
        print(f"      - Anchor Match: {opp.scores.anchor_match_quality}")
        print(f"      - Context: {opp.scores.context_quality}")
        print(f"      - Linkability: {opp.scores.linkability_score}")
        print(f"      - Content Quality: {opp.scores.content_quality}")
        print(f"      - Opportunity Value: {opp.scores.opportunity_value}")
        print(f"    Reason: {opp.reason}")
        loc = opp.placement.recommended_location
        if loc:
            print(f"    Location: Paragraph #{loc.paragraph_index + 1} -> Sentence #{loc.sentence_index + 1} (Offsets: {loc.sentence_char_start}–{loc.sentence_char_end})")
        print(f"    Original Sentence:\n    --> {opp.placement.original_sentence}")
        print(f"    Ready-to-Paste Markdown:\n    --> {opp.placement.ready_to_paste_markdown}")
        print(f"    Ready-to-Paste HTML:\n    --> {opp.placement.ready_to_paste_html}\n")

    if res.excluded_articles_log:
        print("=== EXCLUSION AUDIT LOG ===")
        for ex in res.excluded_articles_log:
            print(f"- [{ex.reason_code}] {ex.title}: {ex.explanation}")

    print("\n\n--- Test 2: Cross-Domain Target (example.com -> runnersworld.com) in strict Internal Mode ---")
    request_cross = AnalyzeRequest(
        sitemap_url=HttpUrl("https://example.com/blog-sitemap.xml"),
        destination_url=HttpUrl("https://www.runnersworld.com/gear/a19663621/best-running-shoes/"),
        anchor_text="best running shoes",
        max_results=5,
        allow_external=False
    )
    res_cross = await service.analyze(request_cross, active_domain_override="example.com", is_demo_mode=True)
    print(f"Link Type: {res_cross.target_validation.link_type}")
    print(f"Eligible for Internal: {res_cross.target_validation.is_eligible_for_internal}")
    print(f"Validation Message: {res_cross.target_validation.validation_message}")
    print(f"Total Opportunities Returned: {res_cross.total_opportunities}")
    print(f"Audit Log Code: {res_cross.excluded_articles_log[0].reason_code}")


if __name__ == "__main__":
    asyncio.run(run_test())
