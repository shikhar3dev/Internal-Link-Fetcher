import pytest
from app.core.anchor_scanner import scan_anchor_occurrences
from app.core.scoring import compute_comprehensive_score
from app.core.context_evaluator import calculate_content_quality


def test_composite_scoring_logic():
    # 1. High-value unlinked exact anchor match
    content_qual = calculate_content_quality(word_count=850, headings_count=3, paragraphs_count=5)
    breakdown = compute_comprehensive_score(
        semantic_relevance=90.0,
        anchor_status="EXACT_UNLINKED_ANCHOR",
        context_quality=95.0,
        paragraph_index=2,
        total_paragraphs=5,
        content_quality=content_qual,
        has_existing_link_to_target=False,
    )
    assert breakdown.overall_score >= 80.0
    assert breakdown.anchor_match_quality == 100.0
    assert breakdown.existing_link_penalty == 0.0

    # 2. Already linked article should receive a zero score
    breakdown_linked = compute_comprehensive_score(
        semantic_relevance=90.0,
        anchor_status="EXACT_UNLINKED_ANCHOR",
        context_quality=95.0,
        paragraph_index=2,
        total_paragraphs=5,
        content_quality=content_qual,
        has_existing_link_to_target=True,
    )
    assert breakdown_linked.overall_score == 0.0
    assert breakdown_linked.existing_link_penalty == 100.0


def test_scan_anchor_occurrences_classification():
    paragraphs = [
        "Welcome to our running blog where we discuss training tips.",
        "Choosing the best running shoes is essential for injury prevention.",
        'We already linked to <a href="https://example.com/target">best running shoes</a> in this sentence.'
    ]
    anchor = "best running shoes"
    dest_norm = "https://example.com/target"

    occurrences = scan_anchor_occurrences(paragraphs, anchor, ["https://example.com/target"], dest_norm)
    assert len(occurrences) == 2

    # Paragraph 1 occurrence should be EXACT_UNLINKED_ANCHOR
    assert occurrences[0]["paragraph_index"] == 1
    assert occurrences[0]["status"] == "EXACT_UNLINKED_ANCHOR"
    assert occurrences[0]["sentence_char_start"] == 13
    assert occurrences[0]["sentence_char_end"] == 31

    # Paragraph 2 occurrence should be EXACT_ALREADY_TARGET_LINKED
    assert occurrences[1]["paragraph_index"] == 2
    assert occurrences[1]["status"] == "EXACT_ALREADY_TARGET_LINKED"
