from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.core.anchor_scanner import scan_anchor_occurrences
from app.core.context_evaluator import calculate_content_quality, is_weak_context_sentence
from app.core.scoring import compute_comprehensive_score
from app.core.url_utils import classify_link_type, destination_in_links, normalize_domain, normalize_url
from app.db.repository import Repository
from app.models.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ExcludedArticle,
    OpportunityResult,
    ScoreBreakdownModel,
    SourceArticleModel,
    TargetPageModel,
    TargetValidation,
)
from app.services.crawl_service import extract_title_and_meta
from app.services.gemini_service import GeminiService
from app.services.retrieval_service import HybridRetriever, parse_paragraphs


def slug_to_title(url: str) -> str:
    """Extracts human-readable words from a URL slug as fallback title."""
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    parts = path.split("/")
    slug = parts[-1] if parts else ""
    if slug.endswith((".html", ".htm", ".php", ".asp", ".aspx")):
        slug = slug.rsplit(".", 1)[0]
    words = re.findall(r"[a-zA-Z0-9]+", slug)
    clean = " ".join(words)
    return clean.title() if len(clean) > 3 else "Target Destination Page"


def validate_opportunity_hard_gate(
    opp: OpportunityResult,
    target_norm_url: str,
    active_domain: str,
    allow_external: bool = False,
) -> tuple[bool, str]:
    """
    Layer 4 Production Hard Gate:
    Strictly verifies all 17 quality and fact checkpoints before an opportunity can be recommended.
    """
    # 1. Source and Target URLs must be valid
    if not opp.source_article.url or not opp.target_page.url:
        return False, "Invalid source or target URL."

    # 2. Source and Target must not be the identical URL
    if opp.source_article.url == opp.target_page.url:
        return False, "Source and destination are the same page."

    # 3. Domain Matching / Internal Link Check
    source_dom = normalize_domain(opp.source_article.domain or opp.source_article.url)
    target_dom = normalize_domain(opp.target_page.domain or opp.target_page.url)

    if not allow_external and source_dom != target_dom:
        return False, f"Domain mismatch: source ({source_dom}) and target ({target_dom}) are different domains."

    if not allow_external and source_dom != active_domain:
        return False, f"Source domain ({source_dom}) does not match active partition ({active_domain})."

    # 4. Original sentence must be non-empty and non-fallback
    orig = opp.placement.original_sentence.strip()
    if not orig or orig in ("Original context", "No change suggested", "Original sentence", ""):
        return False, "Missing or fallback original sentence."

    # 5. Anchor must be present and non-empty
    anchor = opp.target_page.target_anchor.strip()
    if not anchor:
        return False, "Empty target anchor."

    # 6. Weak promotional pattern check
    is_weak, weak_reason = is_weak_context_sentence(orig)
    if is_weak and opp.placement.anchor_status == "EXACT_UNLINKED_ANCHOR":
        return False, f"Weak context pattern: {weak_reason}"

    # 7. Ready-to-paste links must contain the exact target URL
    if target_norm_url not in opp.placement.ready_to_paste_markdown:
        return False, "Markdown link formatting failed to bind target URL."
    if target_norm_url not in opp.placement.ready_to_paste_html:
        return False, "HTML link formatting failed to bind target URL."

    # 8. Location offsets must be valid positive integers
    loc = opp.placement.recommended_location
    if not loc or loc.paragraph_index < 0 or loc.sentence_index < 0:
        return False, "Invalid paragraph or sentence index."
    if loc.sentence_char_start < 0 or loc.sentence_char_end <= loc.sentence_char_start:
        return False, f"Invalid character offsets ({loc.sentence_char_start}–{loc.sentence_char_end})."

    # 9. AI decision must be ACCEPT
    if opp.placement.decision != "ACCEPT":
        return False, f"Editorial placement rejected: {opp.placement.placement_reason}"

    # 10. Quality thresholds
    if opp.scores.semantic_relevance < 55.0:
        return False, f"Semantic relevance ({opp.scores.semantic_relevance:.1f}) is below minimum threshold 55."
    if opp.placement.context_score < 65.0:
        return False, f"Context quality ({opp.placement.context_score:.1f}) is below minimum threshold 65."
    if opp.scores.overall_score < 70.0:
        return False, f"Overall score ({opp.scores.overall_score:.1f}) is below conservative threshold 70."

    return True, "Valid"


class OpportunityService:
    def __init__(self, repo: Repository, gemini: GeminiService) -> None:
        self.repo = repo
        self.gemini = gemini
        self.jobs: dict[str, AnalyzeResponse] = {}

    async def analyze(
        self,
        request: AnalyzeRequest,
        active_domain_override: str | None = None,
        target_domain_override: str | None = None,
        allow_external_links: bool | None = None,
        allow_external: bool | None = None,
        is_demo_mode: bool | None = None,
    ) -> AnalyzeResponse:
        """
        Main entry point for finding linking opportunities.
        Parameters:
        - request: AnalyzeRequest containing destination_url, anchor_text, max_results, etc.
        - active_domain_override: The active website partition to query source articles from.
        - target_domain_override: Legacy alias for active_domain_override.
        - allow_external_links / allow_external: When True, enables cross-domain linking analysis.
        - is_demo_mode: When True, queries demo articles (is_demo = 1); when False, queries production articles.
        """
        target_raw_url = str(request.destination_url).strip()
        target_norm_url = normalize_url(target_raw_url)
        target_anchor = request.anchor_text.strip()
        target_domain = normalize_domain(target_norm_url)

        # Resolve active source domain partition
        active_domain_candidate = (
            active_domain_override
            or request.active_domain_override
            or target_domain_override
            or request.target_domain_override
            or target_domain
        )
        active_domain = normalize_domain(active_domain_candidate)

        # Resolve allow external setting
        is_ext_allowed = (
            allow_external_links
            if allow_external_links is not None
            else (
                allow_external
                if allow_external is not None
                else request.is_external_allowed
            )
        )

        # Resolve is_demo mode
        demo_flag = is_demo_mode if is_demo_mode is not None else request.is_demo

        link_type = classify_link_type(active_domain, target_domain)
        is_internal_eligible = (link_type == "INTERNAL")

        target_validation = TargetValidation(
            target_url=target_norm_url,
            target_domain=target_domain,
            active_partition_domain=active_domain,
            link_type=link_type,
            is_eligible_for_internal=is_internal_eligible,
            validation_message=(
                f"Target belongs to active domain partition ({active_domain}). Eligible for internal linking."
                if is_internal_eligible
                else f"External destination detected. Target ({target_domain}) does not match active partition ({active_domain}). In strict internal mode, zero cross-domain opportunities will be generated."
            ),
        )

        job_id = str(uuid.uuid4())

        # ==========================================
        # PRE-VALIDATION CHECK: Cross-Domain in Strict Internal Mode
        # ==========================================
        if not is_internal_eligible and not is_ext_allowed:
            response = AnalyzeResponse(
                job_id=job_id,
                created_at=datetime.now(timezone.utc),
                active_domain=active_domain,
                target_validation=target_validation,
                discovered_urls=0,
                analyzed_articles=0,
                excluded_already_linking=0,
                excluded_irrelevant=0,
                excluded_wrong_domain=1,
                total_opportunities=0,
                opportunities=[],
                excluded_articles_log=[
                    ExcludedArticle(
                        title="External Target Destination",
                        url=target_norm_url,
                        candidate_anchor=target_anchor,
                        reason_code="WRONG_DOMAIN",
                        explanation=f"Target page ({target_domain}) does not belong to active partition ({active_domain}). Internal linking requires source and destination to share the same domain.",
                    )
                ],
            )
            self.jobs[job_id] = response
            return response

        # ==========================================
        # LAYER 1: Target Page Semantic Extraction
        # ==========================================
        target_title = ""
        target_content = ""
        
        headers = {"User-Agent": settings.user_agent}
        try:
            async with httpx.AsyncClient(headers=headers, timeout=min(5, settings.request_timeout_seconds), follow_redirects=True) as client:
                resp = await client.get(target_raw_url)
                if resp.status_code == 200:
                    html_text = resp.text
                    t, _, _ = extract_title_and_meta(html_text)
                    target_title = t or ""
                    target_content = re.sub(r"\s+", " ", html_text)
        except Exception:
            pass

        if not target_title:
            target_title = slug_to_title(target_raw_url)
            target_content = f"{target_title}. Primary target anchor: {target_anchor}"

        target_summary = await self.gemini.analyze_destination(
            destination_url=target_raw_url,
            title=target_title,
            content=target_content,
            anchor_text=target_anchor,
        )

        target_model = TargetPageModel(
            title=target_title,
            url=target_norm_url,
            domain=target_domain,
            target_anchor=target_anchor,
            primary_topic=target_summary.primary_topic,
            search_intent=target_summary.search_intent,
            link_type=link_type,
        )

        # ==========================================
        # LAYER 2: Domain-Scoped Retrieval & Shortlisting
        # ==========================================
        # Query articles strictly belonging to active_domain partition
        articles = self.repo.fetch_articles_with_embeddings(
            domain=active_domain, is_demo=demo_flag
        )

        if not articles:
            response = AnalyzeResponse(
                job_id=job_id,
                created_at=datetime.now(timezone.utc),
                active_domain=active_domain,
                target_validation=target_validation,
                discovered_urls=0,
                analyzed_articles=0,
                excluded_already_linking=0,
                excluded_irrelevant=0,
                excluded_wrong_domain=0,
                total_opportunities=0,
                opportunities=[],
                excluded_articles_log=[
                    ExcludedArticle(
                        title="No Articles in Domain Partition",
                        url=target_norm_url,
                        candidate_anchor=target_anchor,
                        reason_code="NO_NATURAL_FIT",
                        explanation=f"No indexed articles found for domain '{active_domain}'. Please crawl this website's sitemap first.",
                    )
                ],
            )
            self.jobs[job_id] = response
            return response

        retriever = HybridRetriever(articles)
        target_emb = await self.gemini.get_embedding(
            f"{target_title} {target_summary.primary_topic} {target_anchor}"
        )

        query = " ".join(
            [target_anchor, target_summary.primary_topic] + target_summary.related_concepts[:4]
        ).strip()

        bm25_top = retriever.bm25_top(query=query, top_n=80)
        vector_top = retriever.vector_top(target_emb, top_n=80) if target_emb else []
        
        # Merge and shortlist top 10 candidates for LLM evaluation (Cost & Speed optimization)
        merged_candidates = retriever.merge_scores(bm25_top, vector_top, top_n=10)

        # ==========================================
        # LAYER 3 & 4: Deterministic Filtering, Placement & Validation
        # ==========================================
        excluded_already_linking = 0
        excluded_irrelevant = 0
        excluded_log: list[ExcludedArticle] = []
        opportunities: list[OpportunityResult] = []
        by_id = {int(a["id"]): a for a in articles}

        for candidate in merged_candidates:
            article = by_id.get(candidate.article_id)
            if not article:
                continue

            art_title = article.get("title") or "Untitled Article"
            art_url = str(article["url_normalized"])
            source_domain = normalize_domain(article.get("domain") or art_url)
            paragraphs = parse_paragraphs(article.get("paragraphs_json") or "[]")
            content_text = article.get("content_text") or ""
            word_count = len(content_text.split())

            # 1. Strict Domain Check
            if source_domain != active_domain:
                excluded_log.append(ExcludedArticle(
                    title=art_title,
                    url=art_url,
                    candidate_anchor=target_anchor,
                    reason_code="WRONG_DOMAIN",
                    explanation=f"Source article domain ({source_domain}) does not match active partition ({active_domain}).",
                ))
                continue

            # 2. Hard Deterministic Existing-Link Exclusion
            hrefs = self.repo.fetch_article_links(candidate.article_id)
            if destination_in_links(art_url, hrefs, target_norm_url, raw_article_text=content_text):
                excluded_already_linking += 1
                excluded_log.append(ExcludedArticle(
                    title=art_title,
                    url=art_url,
                    candidate_anchor=target_anchor,
                    reason_code="ALREADY_LINKED",
                    explanation=f"Source article already contains an existing link to destination '{target_norm_url}'.",
                ))
                continue

            # 3. Content Quality Filter (Reject thin articles <6 words)
            if word_count < 6:
                excluded_log.append(ExcludedArticle(
                    title=art_title,
                    url=art_url,
                    candidate_anchor=target_anchor,
                    reason_code="THIN_CONTENT",
                    explanation="Article body is too short (<6 words) for natural internal linking.",
                ))
                continue

            # 4. Deterministic Exact Anchor Scanner
            anchor_occurrences = scan_anchor_occurrences(
                paragraphs=paragraphs,
                anchor_text=target_anchor,
                existing_outbound_links=hrefs,
                destination_norm=target_norm_url,
            )

            unlinked_occurrences = [o for o in anchor_occurrences if o["status"] == "EXACT_UNLINKED_ANCHOR"]
            already_target_linked = [o for o in anchor_occurrences if o["status"] == "EXACT_ALREADY_TARGET_LINKED"]

            if already_target_linked:
                excluded_already_linking += 1
                excluded_log.append(ExcludedArticle(
                    title=art_title,
                    url=art_url,
                    candidate_anchor=target_anchor,
                    reason_code="ALREADY_LINKED",
                    explanation=f"Exact anchor '{target_anchor}' is already hyperlinked to destination in paragraph #{already_target_linked[0]['paragraph_index'] + 1}.",
                ))
                continue

            # 5. Semantic Relevance Evaluation
            relevance = await self.gemini.analyze_relevance(
                destination_summary=target_summary.model_dump(),
                blog_title=art_title,
                blog_content=content_text,
                anchor_text=target_anchor,
            )

            if not relevance.linking_recommended or relevance.relevance_score < 55:
                excluded_irrelevant += 1
                excluded_log.append(ExcludedArticle(
                    title=art_title,
                    url=art_url,
                    candidate_anchor=target_anchor,
                    reason_code="LOW_RELEVANCE",
                    explanation=f"Semantic relevance score is {relevance.relevance_score:.0f}/100. {relevance.reason}",
                ))
                continue

            # 6. Editorial Placement & Link Formats Generator
            placement = await self.gemini.evaluate_placement_and_format(
                destination_summary=target_summary.model_dump(),
                target_url=target_norm_url,
                anchor_text=target_anchor,
                paragraphs=paragraphs,
                unlinked_occurrences=unlinked_occurrences,
            )

            if not placement.linking_recommended or placement.decision == "REJECT" or placement.context_score < 60:
                excluded_irrelevant += 1
                reason_code = "LOW_CONTEXT_QUALITY" if "self-referential" in placement.placement_reason.lower() or "weak" in placement.placement_reason.lower() else "NO_NATURAL_FIT"
                excluded_log.append(ExcludedArticle(
                    title=art_title,
                    url=art_url,
                    candidate_anchor=target_anchor,
                    reason_code=reason_code,
                    explanation=placement.placement_reason,
                ))
                continue

            # 7. Composite Multi-Factor Scoring
            p_idx = placement.recommended_location.paragraph_index if placement.recommended_location else 0
            content_qual = calculate_content_quality(
                word_count=word_count,
                headings_count=len(json.loads(article.get("headings_json") or "[]")),
                paragraphs_count=len(paragraphs),
            )

            score_obj = compute_comprehensive_score(
                semantic_relevance=relevance.relevance_score,
                anchor_status=placement.anchor_status,
                context_quality=placement.context_score,
                paragraph_index=p_idx,
                total_paragraphs=len(paragraphs),
                content_quality=content_qual,
                has_existing_link_to_target=False,
                is_weak_context=False,
            )

            source_model = SourceArticleModel(
                id=int(article["id"]),
                title=art_title,
                url=art_url,
                domain=source_domain,
                word_count=word_count,
                total_paragraphs=len(paragraphs),
                is_demo=bool(article.get("is_demo")),
            )

            score_model = ScoreBreakdownModel(
                overall_score=score_obj.overall_score,
                semantic_relevance=score_obj.semantic_relevance,
                anchor_match_quality=score_obj.anchor_match_quality,
                context_quality=score_obj.context_quality,
                linkability_score=score_obj.linkability_score,
                content_quality=score_obj.content_quality,
                opportunity_value=score_obj.opportunity_value,
                existing_link_penalty=score_obj.existing_link_penalty,
            )

            candidate_opp = OpportunityResult(
                source_article=source_model,
                target_page=target_model,
                link_type=link_type,
                status="ACCEPTED",
                scores=score_model,
                anchor_status=placement.anchor_status,
                placement=placement,
                reason=relevance.reason,
                evidence_quotes=[e["quote"] for e in relevance.evidence_spans if e.get("quote")],
            )

            # 8. LAYER 4: HARD GATE VALIDATION
            is_valid, reject_msg = validate_opportunity_hard_gate(
                candidate_opp,
                target_norm_url=target_norm_url,
                active_domain=active_domain,
                allow_external=is_ext_allowed,
            )

            if not is_valid:
                excluded_irrelevant += 1
                excluded_log.append(ExcludedArticle(
                    title=art_title,
                    url=art_url,
                    candidate_anchor=target_anchor,
                    reason_code="LOW_CONTEXT_QUALITY" if "weak" in reject_msg.lower() else "NO_NATURAL_FIT",
                    explanation=f"Validation Gate: {reject_msg}",
                ))
                continue

            opportunities.append(candidate_opp)

        # Sort top opportunities by composite score
        opportunities = sorted(
            opportunities,
            key=lambda x: x.scores.overall_score,
            reverse=True,
        )[: request.max_results]

        response = AnalyzeResponse(
            job_id=job_id,
            created_at=datetime.now(timezone.utc),
            active_domain=active_domain,
            target_validation=target_validation,
            discovered_urls=len(articles),
            analyzed_articles=len(merged_candidates),
            excluded_already_linking=excluded_already_linking,
            excluded_irrelevant=excluded_irrelevant,
            excluded_wrong_domain=0,
            total_opportunities=len(opportunities),
            opportunities=opportunities,
            excluded_articles_log=excluded_log,
        )
        self.jobs[job_id] = response
        return response

    def get_job(self, job_id: str) -> AnalyzeResponse | None:
        return self.jobs.get(job_id)
