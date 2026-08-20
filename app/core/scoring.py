from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScoreBreakdown:
    overall_score: float
    semantic_relevance: float  # 0-100 (Weight: 35%)
    anchor_match_quality: float  # 0-100 (Weight: 20%)
    context_quality: float  # 0-100 (Weight: 15%)
    linkability_score: float  # 0-100 (Weight: 10%)
    content_quality: float  # 0-100 (Weight: 10%)
    opportunity_value: float  # 0-100 (Weight: 10%)
    existing_link_penalty: float = 0.0


def compute_comprehensive_score(
    semantic_relevance: float,
    anchor_status: str,  # "EXACT_UNLINKED_ANCHOR", "SEMANTIC_ANCHOR_CANDIDATE", "NONE"
    context_quality: float,
    paragraph_index: int,
    total_paragraphs: int,
    content_quality: float,
    has_existing_link_to_target: bool = False,
    is_weak_context: bool = False,
) -> ScoreBreakdown:
    """
    Computes a dynamic composite opportunity score:
    Overall = (Semantic * 0.35) + (Anchor * 0.20) + (Context * 0.15) + (Linkability * 0.10) + (ContentQuality * 0.10) + (OpportunityValue * 0.10)
    """
    if has_existing_link_to_target:
        return ScoreBreakdown(
            overall_score=0.0,
            semantic_relevance=round(semantic_relevance, 1),
            anchor_match_quality=0.0,
            context_quality=0.0,
            linkability_score=0.0,
            content_quality=round(content_quality, 1),
            opportunity_value=0.0,
            existing_link_penalty=100.0,
        )

    # 1. Semantic Relevance (0-100)
    sem_score = max(0.0, min(100.0, float(semantic_relevance)))

    # 2. Anchor Match Quality (0-100)
    if anchor_status == "EXACT_UNLINKED_ANCHOR":
        anchor_score = 100.0
    elif anchor_status == "SEMANTIC_ANCHOR_CANDIDATE":
        anchor_score = 75.0
    else:
        anchor_score = 40.0

    # 3. Context Quality (0-100)
    ctx_score = max(0.0, min(100.0, float(context_quality)))
    if is_weak_context:
        ctx_score = min(ctx_score, 35.0)

    # 4. Linkability Score (0-100) based on location in article
    if total_paragraphs > 0:
        pos_ratio = paragraph_index / max(1, total_paragraphs)
        if pos_ratio <= 0.4:
            linkability_score = 95.0
        elif pos_ratio <= 0.75:
            linkability_score = 82.0
        else:
            linkability_score = 65.0
    else:
        linkability_score = 80.0

    # 5. Content Quality (0-100)
    cont_score = max(0.0, min(100.0, float(content_quality)))

    # 6. Opportunity Value / Freshness (0-100)
    opp_val = round((sem_score * 0.5) + (ctx_score * 0.5), 1)

    # Weighted Composite Score
    raw_composite = (
        0.35 * sem_score
        + 0.20 * anchor_score
        + 0.15 * ctx_score
        + 0.10 * linkability_score
        + 0.10 * cont_score
        + 0.10 * opp_val
    )

    final_score = round(max(0.0, min(100.0, raw_composite)), 1)

    return ScoreBreakdown(
        overall_score=final_score,
        semantic_relevance=round(sem_score, 1),
        anchor_match_quality=round(anchor_score, 1),
        context_quality=round(ctx_score, 1),
        linkability_score=round(linkability_score, 1),
        content_quality=round(cont_score, 1),
        opportunity_value=round(opp_val, 1),
        existing_link_penalty=0.0,
    )
