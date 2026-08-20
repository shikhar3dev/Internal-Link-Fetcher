import pytest
from pathlib import Path
from pydantic import HttpUrl

from app.core.url_utils import classify_link_type, destination_in_links, normalize_domain, normalize_url
from app.core.anchor_scanner import scan_anchor_occurrences
from app.core.context_evaluator import is_weak_context_sentence, evaluate_sentence_context_quality, calculate_content_quality
from app.core.scoring import compute_comprehensive_score
from app.db.repository import Repository
from app.models.schemas import (
    AnalyzeRequest,
    OpportunityResult,
    SourceArticleModel,
    TargetPageModel,
    ScoreBreakdownModel,
    PlacementAnalysis,
    LocationRef,
)
from app.services.gemini_service import GeminiService, build_link_formats
from app.services.opportunity_service import OpportunityService, validate_opportunity_hard_gate


@pytest.fixture
def repo_and_service(tmp_path):
    db_file = tmp_path / "comprehensive_test.db"
    repo = Repository(str(db_file))
    schema_path = Path(__file__).resolve().parents[1] / "app" / "db" / "schema.sql"
    repo.init_schema(schema_path.read_text(encoding="utf-8"))
    gemini = GeminiService(api_key="")
    service = OpportunityService(repo=repo, gemini=gemini)
    return repo, service


# ==========================================
# 1. DOMAIN NORMALIZATION & MATCHING TESTS
# ==========================================

def test_same_domain_classification():
    src = "https://www.example.com/blog/how-to-run"
    tgt = "https://example.com/best-running-shoes"
    assert normalize_domain(src) == "example.com"
    assert normalize_domain(tgt) == "example.com"
    assert classify_link_type(src, tgt) == "INTERNAL"


def test_different_domain_classification():
    src = "https://example.com/blog/how-to-run"
    tgt = "https://www.runnersworld.com/gear/shoes"
    assert normalize_domain(src) == "example.com"
    assert normalize_domain(tgt) == "runnersworld.com"
    assert classify_link_type(src, tgt) == "EXTERNAL"


def test_www_and_casing_domain_normalization():
    d1 = normalize_domain("http://www.EXAMPLE.COM/path/")
    d2 = normalize_domain("https://example.com:443/another-path")
    d3 = normalize_domain("OUTDOORGEARLAB.COM")
    d4 = normalize_domain("https://www.outdoorgearlab.com/")
    assert d1 == "example.com"
    assert d2 == "example.com"
    assert d3 == "outdoorgearlab.com"
    assert d4 == "outdoorgearlab.com"
    assert d1 == d2
    assert d3 == d4


def test_trailing_slash_normalization():
    u1 = normalize_url("https://example.com/blog/running-shoes/")
    u2 = normalize_url("https://example.com/blog/running-shoes")
    assert u1 == u2


# ==========================================
# 2. EXISTING LINK DETECTION TESTS
# ==========================================

def test_exact_target_link_detection():
    source_url = "https://example.com/blog/review"
    existing_links = ["https://example.com/best-running-shoes", "https://example.com/gear"]
    target = "https://example.com/best-running-shoes"
    assert destination_in_links(source_url, existing_links, target) is True


def test_relative_target_link_detection():
    source_url = "https://example.com/blog/review"
    existing_links = ["/best-running-shoes", "/gear"]
    target = "https://example.com/best-running-shoes"
    assert destination_in_links(source_url, existing_links, target) is True


def test_query_parameter_target_link_detection():
    source_url = "https://example.com/blog/review"
    existing_links = ["https://example.com/best-running-shoes"]
    target_with_utm = "https://example.com/best-running-shoes?utm_source=newsletter&utm_medium=email"
    assert destination_in_links(source_url, existing_links, target_with_utm) is True


def test_raw_url_mention_in_text_detection():
    source_url = "https://example.com/blog/review"
    body = "Check out https://example.com/best-running-shoes for our shoe guide."
    target = "https://example.com/best-running-shoes"
    assert destination_in_links(source_url, [], target, raw_article_text=body) is True


# ==========================================
# 3. ANCHOR DETECTION & MULTI-OCCURRENCE TESTS
# ==========================================

def test_exact_anchor_detection():
    paragraphs = [
        "Finding the best running shoes involves understanding your gait cycle and pronation."
    ]
    occurrences = scan_anchor_occurrences(
        paragraphs, "best running shoes", [], "https://example.com/best-running-shoes"
    )
    assert len(occurrences) == 1
    occ = occurrences[0]
    assert occ["status"] == "EXACT_UNLINKED_ANCHOR"
    assert occ["sentence_char_start"] == 12
    assert occ["sentence_char_end"] == 30
    assert occ["is_weak_context"] is False


def test_multiple_anchor_occurrences():
    paragraphs = [
        "Finding the best running shoes involves understanding your gait cycle and pronation.",
        "Later in the guide we mention best running shoes again."
    ]
    occurrences = scan_anchor_occurrences(
        paragraphs, "best running shoes", [], "https://example.com/best-running-shoes"
    )
    assert len(occurrences) == 2
    assert occurrences[0]["paragraph_index"] == 0
    assert occurrences[1]["paragraph_index"] == 1


def test_exact_anchor_already_linked():
    paragraphs = [
        'We already linked to <a href="https://example.com/best-running-shoes">best running shoes</a> here.'
    ]
    occurrences = scan_anchor_occurrences(
        paragraphs, "best running shoes", ["https://example.com/best-running-shoes"], "https://example.com/best-running-shoes"
    )
    assert len(occurrences) == 1
    assert occurrences[0]["status"] == "EXACT_ALREADY_TARGET_LINKED"


# ==========================================
# 4. WEAK CONTEXT & QUALITY EVALUATION TESTS
# ==========================================

def test_weak_context_rejection():
    weak_sentences = [
        "We have already reviewed the best running shoes on our dedicated page.",
        "Click here for best running shoes details.",
        "Visit this page to see our best running shoes guide.",
        "As mentioned above, best running shoes are important.",
    ]
    for s in weak_sentences:
        is_weak, reason = is_weak_context_sentence(s)
        assert is_weak is True, f"Failed for sentence: {s}"

        score, acceptable, _ = evaluate_sentence_context_quality(s, "best running shoes", s)
        assert acceptable is False
        assert score <= 40.0


def test_strong_context_acceptance():
    strong_sentence = "Finding the best running shoes involves understanding your gait cycle and pronation."
    is_weak, _ = is_weak_context_sentence(strong_sentence)
    assert is_weak is False

    score, acceptable, _ = evaluate_sentence_context_quality(
        strong_sentence, "best running shoes", strong_sentence
    )
    assert acceptable is True
    assert score >= 75.0


def test_content_quality_calculation():
    score_rich = calculate_content_quality(word_count=1200, headings_count=4, paragraphs_count=6)
    score_thin = calculate_content_quality(word_count=50, headings_count=0, paragraphs_count=1)
    assert score_rich >= 90.0
    assert score_thin <= 40.0


# ==========================================
# 5. CODE-DRIVEN MARKDOWN & HTML GENERATION
# ==========================================

def test_deterministic_markdown_and_html_generation():
    sentence = "Finding the best running shoes involves understanding your gait cycle and pronation."
    anchor = "best running shoes"
    target = "https://example.com/best-running-shoes"

    bold, md, html_code, start, end = build_link_formats(sentence, anchor, target)
    assert bold == "Finding the **best running shoes** involves understanding your gait cycle and pronation."
    assert md == "Finding the [best running shoes](https://example.com/best-running-shoes) involves understanding your gait cycle and pronation."
    assert html_code == 'Finding the <a href="https://example.com/best-running-shoes">best running shoes</a> involves understanding your gait cycle and pronation.'
    assert start == 12
    assert end == 30


def test_html_escaping_in_link_generation():
    sentence = "Finding the best running shoes & gear involves research."
    anchor = "best running shoes & gear"
    target = "https://example.com/shoes?brand=nike&model=alpha"

    _, _, html_code, _, _ = build_link_formats(sentence, anchor, target)
    assert "&amp;" in html_code or "&quot;" in html_code or 'href="https://example.com/shoes?brand=nike&amp;model=alpha"' in html_code or 'href="https://example.com/shoes?brand=nike&model=alpha"' in html_code


# ==========================================
# 6. HARD GATE VALIDATION TESTS
# ==========================================

def test_validation_hard_gate_acceptance():
    src_model = SourceArticleModel(
        id=1, title="Shoes Guide", url="https://example.com/shoes", domain="example.com"
    )
    tgt_model = TargetPageModel(
        title="Best Shoes", url="https://example.com/best-shoes", domain="example.com", target_anchor="best shoes"
    )
    scores = ScoreBreakdownModel(
        overall_score=85.0, semantic_relevance=90.0, anchor_match_quality=100.0,
        context_quality=90.0, linkability_score=90.0, content_quality=80.0, opportunity_value=85.0
    )
    placement = PlacementAnalysis(
        decision="ACCEPT",
        anchor_status="EXACT_UNLINKED_ANCHOR",
        can_insert_naturally=True,
        recommended_location=LocationRef(
            paragraph_index=1, sentence_index=0, sentence_char_start=5, sentence_char_end=15
        ),
        original_sentence="These best shoes are durable.",
        suggested_sentence_edit="These **best shoes** are durable.",
        ready_to_paste_markdown="These [best shoes](https://example.com/best-shoes) are durable.",
        ready_to_paste_html='These <a href="https://example.com/best-shoes">best shoes</a> are durable.',
        suggested_link_span="best shoes",
        placement_reason="Good fit",
        context_score=90.0,
        confidence=0.95,
        linking_recommended=True,
    )
    valid_opp = OpportunityResult(
        source_article=src_model,
        target_page=tgt_model,
        link_type="INTERNAL",
        scores=scores,
        anchor_status="EXACT_UNLINKED_ANCHOR",
        placement=placement,
        reason="Relevant",
    )

    is_valid, msg = validate_opportunity_hard_gate(
        valid_opp, target_norm_url="https://example.com/best-shoes", active_domain="example.com"
    )
    assert is_valid is True
    assert msg == "Valid"


def test_validation_hard_gate_missing_sentence_rejection():
    src_model = SourceArticleModel(
        id=1, title="Shoes Guide", url="https://example.com/shoes", domain="example.com"
    )
    tgt_model = TargetPageModel(
        title="Best Shoes", url="https://example.com/best-shoes", domain="example.com", target_anchor="best shoes"
    )
    scores = ScoreBreakdownModel(
        overall_score=85.0, semantic_relevance=90.0, anchor_match_quality=100.0,
        context_quality=90.0, linkability_score=90.0, content_quality=80.0, opportunity_value=85.0
    )
    placement = PlacementAnalysis(
        decision="ACCEPT",
        anchor_status="EXACT_UNLINKED_ANCHOR",
        can_insert_naturally=True,
        recommended_location=LocationRef(
            paragraph_index=1, sentence_index=0, sentence_char_start=5, sentence_char_end=15
        ),
        original_sentence="",  # Missing!
        suggested_sentence_edit="",
        ready_to_paste_markdown="",
        ready_to_paste_html="",
        suggested_link_span="best shoes",
        placement_reason="Good fit",
        context_score=90.0,
        confidence=0.95,
        linking_recommended=True,
    )
    invalid_opp = OpportunityResult(
        source_article=src_model,
        target_page=tgt_model,
        link_type="INTERNAL",
        scores=scores,
        anchor_status="EXACT_UNLINKED_ANCHOR",
        placement=placement,
        reason="Relevant",
    )

    is_valid, msg = validate_opportunity_hard_gate(
        invalid_opp, target_norm_url="https://example.com/best-shoes", active_domain="example.com"
    )
    assert is_valid is False
    assert "Missing" in msg


# ==========================================
# 7. SERVICE PIPELINE & REGRESSION TESTS
# ==========================================

@pytest.mark.asyncio
async def test_cross_domain_pre_validation_strict_mode(repo_and_service):
    repo, service = repo_and_service

    repo.upsert_article({
        "domain": "example.com",
        "url_raw": "https://example.com/blog/shoes",
        "url_normalized": "https://example.com/blog/shoes",
        "title": "Shoes",
        "content_text": "Finding the best running shoes involves understanding your gait cycle and pronation.",
        "paragraphs": ["Finding the best running shoes involves understanding your gait cycle and pronation."],
        "word_count": 20,
        "is_demo": 1,
    })

    req = AnalyzeRequest(
        destination_url=HttpUrl("https://www.runnersworld.com/gear/a19663621/best-running-shoes/"),
        anchor_text="best running shoes",
        active_domain_override="example.com",
        allow_external_links=False,
    )

    # Must return a controlled response without throwing any exception
    res = await service.analyze(req, active_domain_override="example.com", allow_external_links=False)
    assert res.target_validation.is_eligible_for_internal is False
    assert res.target_validation.link_type == "EXTERNAL"
    assert res.total_opportunities == 0
    assert len(res.excluded_articles_log) >= 1
    assert res.excluded_articles_log[0].reason_code == "WRONG_DOMAIN"


@pytest.mark.asyncio
async def test_cross_domain_external_mode(repo_and_service):
    repo, service = repo_and_service

    repo.upsert_article({
        "domain": "example.com",
        "url_raw": "https://example.com/blog/shoes",
        "url_normalized": "https://example.com/blog/shoes",
        "title": "How to Choose Running Shoes",
        "content_text": "Finding the best running shoes involves understanding your gait cycle and pronation.",
        "paragraphs": ["Finding the best running shoes involves understanding your gait cycle and pronation."],
        "word_count": 25,
        "is_demo": 1,
    })

    req = AnalyzeRequest(
        destination_url=HttpUrl("https://www.outdoorgearlab.com/topics/shoes-and-boots/best-running-shoes"),
        anchor_text="best running shoes",
        active_domain_override="example.com",
        allow_external_links=True,
    )

    res = await service.analyze(req, active_domain_override="example.com", allow_external_links=True)
    assert res.target_validation.link_type == "EXTERNAL"
    assert res.total_opportunities >= 1
    assert res.opportunities[0].link_type == "EXTERNAL"
    assert res.opportunities[0].source_article.domain == "example.com"
    assert res.opportunities[0].target_page.domain == "outdoorgearlab.com"


@pytest.mark.asyncio
async def test_active_partition_source_scoping(repo_and_service):
    repo, service = repo_and_service

    # Insert article on example.com
    repo.upsert_article({
        "domain": "example.com",
        "url_raw": "https://example.com/blog/post1",
        "url_normalized": "https://example.com/blog/post1",
        "title": "Example Post",
        "content_text": "Finding the best running shoes involves understanding your gait cycle and pronation.",
        "paragraphs": ["Finding the best running shoes involves understanding your gait cycle and pronation."],
        "word_count": 20,
    })

    # Insert article on outdoorgearlab.com
    repo.upsert_article({
        "domain": "outdoorgearlab.com",
        "url_raw": "https://www.outdoorgearlab.com/blog/gear-guide",
        "url_normalized": "https://outdoorgearlab.com/blog/gear-guide",
        "title": "Outdoor Gear Guide",
        "content_text": "Finding the best running shoes involves understanding your gait cycle and pronation.",
        "paragraphs": ["Finding the best running shoes involves understanding your gait cycle and pronation."],
        "word_count": 25,
    })

    req = AnalyzeRequest(
        destination_url=HttpUrl("https://www.outdoorgearlab.com/topics/shoes/best-running-shoes"),
        anchor_text="best running shoes",
        active_domain_override="outdoorgearlab.com",
    )

    res = await service.analyze(req, active_domain_override="outdoorgearlab.com")
    assert res.total_opportunities == 1
    assert res.opportunities[0].source_article.domain == "outdoorgearlab.com"
    assert res.opportunities[0].source_article.title == "Outdoor Gear Guide"


@pytest.mark.asyncio
async def test_demo_data_isolation(repo_and_service):
    repo, service = repo_and_service

    # Demo article
    repo.upsert_article({
        "domain": "example.com",
        "is_demo": 1,
        "url_raw": "https://example.com/blog/demo-post",
        "url_normalized": "https://example.com/blog/demo-post",
        "title": "Demo Post",
        "content_text": "Finding the best running shoes involves understanding your gait cycle and pronation.",
        "paragraphs": ["Finding the best running shoes involves understanding your gait cycle and pronation."],
        "word_count": 20,
    })

    # Query with is_demo_mode = False
    req = AnalyzeRequest(
        destination_url=HttpUrl("https://example.com/best-running-shoes"),
        anchor_text="best running shoes",
        active_domain_override="example.com",
        is_demo=False,
    )
    res = await service.analyze(req, active_domain_override="example.com", is_demo_mode=False)
    assert res.total_opportunities == 0  # No production articles exist


@pytest.mark.asyncio
async def test_legacy_target_domain_override_alias(repo_and_service):
    repo, service = repo_and_service

    repo.upsert_article({
        "domain": "example.com",
        "url_raw": "https://example.com/blog/post",
        "url_normalized": "https://example.com/blog/post",
        "title": "Post",
        "content_text": "Finding the best running shoes involves understanding your gait cycle and pronation.",
        "paragraphs": ["Finding the best running shoes involves understanding your gait cycle and pronation."],
        "word_count": 20,
    })

    req = AnalyzeRequest(
        destination_url=HttpUrl("https://example.com/best-running-shoes"),
        anchor_text="best running shoes",
        target_domain_override="example.com",
        allow_external=False,
    )

    res = await service.analyze(req, target_domain_override="example.com", allow_external=False)
    assert res.active_domain == "example.com"
    assert res.total_opportunities >= 1
