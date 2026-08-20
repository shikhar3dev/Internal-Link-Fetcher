from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class AnalyzeRequest(BaseModel):
    destination_url: HttpUrl
    anchor_text: str = Field(min_length=2, max_length=120)
    sitemap_url: HttpUrl | None = None
    max_results: int = Field(default=20, ge=1, le=100)
    active_domain_override: str | None = None
    target_domain_override: str | None = None  # Legacy compatibility alias
    allow_external_links: bool = False  # Preferred semantic name: True allows cross-domain linking
    allow_external: bool = False  # Legacy compatibility alias
    is_demo: bool | None = None

    @property
    def is_external_allowed(self) -> bool:
        return bool(self.allow_external_links or self.allow_external)

    @property
    def domain_override(self) -> str | None:
        return self.active_domain_override or self.target_domain_override


class IndexRequest(BaseModel):
    sitemap_url: HttpUrl
    max_urls: int = Field(default=5000, ge=1, le=100000)
    is_demo: bool = False


class LocationRef(BaseModel):
    paragraph_index: int
    sentence_index: int
    sentence_char_start: int
    sentence_char_end: int
    paragraph_char_start: int = 0
    paragraph_char_end: int = 0
    paragraph_total_sentences: int = 1


class ScoreBreakdownModel(BaseModel):
    overall_score: float
    semantic_relevance: float
    anchor_match_quality: float
    context_quality: float
    linkability_score: float
    content_quality: float
    opportunity_value: float
    existing_link_penalty: float = 0.0


class SourceArticleModel(BaseModel):
    id: int
    title: str
    url: str
    domain: str
    word_count: int = 0
    total_paragraphs: int = 0
    is_demo: bool = False


class TargetPageModel(BaseModel):
    title: str
    url: str
    domain: str
    target_anchor: str
    primary_topic: str = ""
    search_intent: str = "informational"
    link_type: Literal["INTERNAL", "EXTERNAL"] = "INTERNAL"


class DestinationSummary(BaseModel):
    primary_topic: str
    search_intent: Literal[
        "informational", "commercial", "transactional", "navigational", "mixed"
    ]
    important_entities: list[str] = Field(default_factory=list)
    related_concepts: list[str] = Field(default_factory=list)
    suitable_reference_contexts: list[str] = Field(default_factory=list)
    anchor_semantic_meaning: str
    insufficient_evidence: bool = False


class RelevanceAnalysis(BaseModel):
    relevance_score: float = Field(ge=0, le=100)
    reader_value: Literal["high", "medium", "low"]
    linking_recommended: bool
    reason: str
    evidence_spans: list[dict[str, str]] = Field(default_factory=list)
    insufficient_evidence: bool = False


class PlacementAnalysis(BaseModel):
    decision: Literal["ACCEPT", "REJECT"] = "ACCEPT"
    anchor_status: Literal["EXACT_UNLINKED_ANCHOR", "SEMANTIC_ANCHOR_CANDIDATE", "NONE"]
    can_insert_naturally: bool
    recommended_location: LocationRef | None = None
    original_sentence: str
    suggested_sentence_edit: str
    ready_to_paste_markdown: str
    ready_to_paste_html: str
    suggested_link_span: str
    placement_reason: str
    context_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    linking_recommended: bool
    insufficient_evidence: bool = False


class ExcludedArticle(BaseModel):
    title: str
    url: str
    candidate_anchor: str = ""
    reason_code: Literal[
        "ALREADY_LINKED",
        "WRONG_DOMAIN",
        "LOW_RELEVANCE",
        "LOW_CONTEXT_QUALITY",
        "NO_NATURAL_FIT",
        "THIN_CONTENT",
        "INVALID_LOCATION",
        "MISSING_SENTENCE",
    ]
    explanation: str


class TargetValidation(BaseModel):
    target_url: str
    target_domain: str
    active_partition_domain: str
    link_type: Literal["INTERNAL", "EXTERNAL"]
    is_eligible_for_internal: bool
    validation_message: str


class OpportunityResult(BaseModel):
    schema_version: str = "3.0"
    source_article: SourceArticleModel
    target_page: TargetPageModel
    link_type: Literal["INTERNAL", "EXTERNAL"] = "INTERNAL"
    status: Literal[
        "ACCEPTED", "REJECTED", "ALREADY_LINKED", "WRONG_DOMAIN", "LOW_CONTEXT"
    ] = "ACCEPTED"
    scores: ScoreBreakdownModel
    anchor_status: Literal["EXACT_UNLINKED_ANCHOR", "SEMANTIC_ANCHOR_CANDIDATE", "NONE"]
    placement: PlacementAnalysis
    reason: str
    evidence_quotes: list[str] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    job_id: str
    created_at: datetime
    active_domain: str
    target_validation: TargetValidation
    discovered_urls: int
    analyzed_articles: int
    excluded_already_linking: int
    excluded_irrelevant: int
    excluded_wrong_domain: int = 0
    total_opportunities: int
    opportunities: list[OpportunityResult] = Field(default_factory=list)
    excluded_articles_log: list[ExcludedArticle] = Field(default_factory=list)


class IndexResponse(BaseModel):
    discovered_urls: int
    crawled_urls: int
    inserted_articles: int
    updated_articles: int
    skipped_articles: int
    errors: list[str] = Field(default_factory=list)
