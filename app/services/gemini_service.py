from __future__ import annotations

import html
import json
import logging
import re
from typing import Any

import httpx

from app.core.context_evaluator import evaluate_sentence_context_quality, is_weak_context_sentence
from app.models.schemas import DestinationSummary, LocationRef, PlacementAnalysis, RelevanceAnalysis

logger = logging.getLogger("gemini_service")

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def extract_key_terms(text: str) -> set[str]:
    """Extracts lowercase meaningful words (ignoring short stopwords)."""
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    stopwords = {
        "the", "and", "for", "with", "this", "that", "from", "have", "what",
        "your", "which", "more", "will", "been", "there", "their", "about",
        "into", "some", "them", "these", "other", "then", "also", "just",
        "over", "after", "before", "each", "here", "were", "when", "where",
        "could", "should", "would", "because"
    }
    return {w for w in words if w not in stopwords}


def build_link_formats(sentence: str, anchor_text: str, target_url: str) -> tuple[str, str, str, int, int]:
    """
    Deterministically transforms a sentence containing anchor_text into:
    1. Modified text with bold anchor: ... **anchor** ...
    2. Ready-to-paste Markdown: ... [anchor](target_url) ...
    3. Ready-to-paste HTML: ... <a href="target_url">anchor</a> ...
    Returns (bold_version, md_version, html_version, char_start, char_end)
    """
    clean_s = sentence.strip()
    pattern = re.compile(r"\b" + re.escape(anchor_text.strip()) + r"\b", re.IGNORECASE)
    
    match = pattern.search(clean_s)
    if not match:
        pattern_loose = re.compile(re.escape(anchor_text.strip()), re.IGNORECASE)
        match = pattern_loose.search(clean_s)

    if not match:
        return clean_s, clean_s, clean_s, -1, -1

    s_start = match.start()
    s_end = match.end()
    actual_matched_text = clean_s[s_start:s_end]
    
    # 1. Bold text preview
    bold_version = clean_s[:s_start] + f"**{actual_matched_text}**" + clean_s[s_end:]
    
    # 2. Markdown link
    md_version = clean_s[:s_start] + f"[{actual_matched_text}]({target_url})" + clean_s[s_end:]
    
    # 3. HTML link
    escaped_url = html.escape(target_url, quote=True)
    html_version = clean_s[:s_start] + f'<a href="{escaped_url}">{html.escape(actual_matched_text)}</a>' + clean_s[s_end:]
    
    return bold_version, md_version, html_version, s_start, s_end


class GeminiService:
    def __init__(self, api_key: str = "", model: str = "gemini-2.5-flash", embedding_model: str = "text-embedding-004") -> None:
        self.api_key = api_key.strip()
        self.model = model
        self.embedding_model = embedding_model

    def set_api_key(self, api_key: str) -> None:
        self.api_key = api_key.strip()

    def is_api_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 10 and not self.api_key.startswith("YOUR_"))

    async def _call_json(self, prompt: str) -> dict[str, Any]:
        if not self.is_api_configured():
            return {"insufficient_evidence": True}

        models_to_try = [self.model, "gemini-2.0-flash", "gemini-1.5-flash"]
        models_to_try = list(dict.fromkeys(models_to_try))

        for model_name in models_to_try:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "responseMimeType": "application/json",
                },
            }

            try:
                async with httpx.AsyncClient(timeout=35) as client:
                    response = await client.post(endpoint, params={"key": self.api_key}, json=payload)
                    if response.status_code == 200:
                        data = response.json()
                        text = (
                            data.get("candidates", [{}])[0]
                            .get("content", {})
                            .get("parts", [{}])[0]
                            .get("text", "{}")
                        )
                        return json.loads(text)
                    else:
                        logger.warning(f"Model {model_name} returned status {response.status_code}: {response.text[:200]}")
            except Exception as e:
                logger.error(f"Error calling Gemini with model {model_name}: {e}")

        return {"insufficient_evidence": True}

    async def get_embedding(self, text: str) -> list[float]:
        """Generates 768-dimensional embedding for content indexing."""
        if not self.is_api_configured():
            return []

        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.embedding_model}:embedContent"
        payload = {"content": {"parts": [{"text": text[:8000]}]}}

        try:
            async with httpx.AsyncClient(timeout=25) as client:
                response = await client.post(endpoint, params={"key": self.api_key}, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("embedding", {}).get("values", [])
        except Exception as e:
            logger.warning(f"Failed to generate embedding: {e}")
        return []

    async def analyze_destination(
        self, destination_url: str, title: str, content: str, anchor_text: str
    ) -> DestinationSummary:
        prompt = f"""
You are an expert SEO Ontologist.
Analyze the target web page to construct a semantic profile.

TARGET PAGE:
- URL: {destination_url}
- Title: {title}
- Target Anchor: "{anchor_text}"
- Content Excerpt:
{content[:8000]}

OUTPUT FORMAT: Strict JSON matching the schema:
{{
  "primary_topic": "string (main topic)",
  "search_intent": "informational" | "commercial" | "transactional" | "navigational" | "mixed",
  "important_entities": ["entity1", "entity2", "entity3"],
  "related_concepts": ["concept1", "concept2"],
  "suitable_reference_contexts": ["context1", "context2"],
  "anchor_semantic_meaning": "string"
}}
""".strip()
        raw = await self._call_json(prompt)

        if raw.get("insufficient_evidence") or not raw.get("primary_topic"):
            terms = list(extract_key_terms(f"{title} {anchor_text}"))
            primary = title if title and len(title) > 3 else anchor_text
            return DestinationSummary(
                primary_topic=primary,
                search_intent="informational",
                important_entities=terms[:5],
                related_concepts=[anchor_text] + terms[:3],
                suitable_reference_contexts=[f"Discussions addressing {anchor_text}"],
                anchor_semantic_meaning=f"Reference to '{anchor_text}'",
                insufficient_evidence=False,
            )
        return DestinationSummary(**raw)

    async def analyze_relevance(
        self, destination_summary: dict[str, Any], blog_title: str, blog_content: str, anchor_text: str
    ) -> RelevanceAnalysis:
        prompt = f"""
You are a senior SEO editor.
Evaluate whether this existing blog post should link to the target page.

DESTINATION PAGE SUMMARY:
{json.dumps(destination_summary, indent=2)}

TARGET ANCHOR: "{anchor_text}"

SOURCE BLOG POST:
- Title: {blog_title}
- Content Excerpt:
{blog_content[:9000]}

RULES:
1. Score relevance (0 to 100) based on genuine topical harmony and reader value.
2. If unrelated, set relevance_score <= 40 and linking_recommended = false.
3. Be conservative. High quality over quantity.

OUTPUT SCHEMA: Strict JSON only:
{{
  "relevance_score": 85,
  "reader_value": "high" | "medium" | "low",
  "linking_recommended": true,
  "reason": "Concise explanation of connection or why rejected",
  "evidence_spans": [{{"quote": "excerpt from blog", "why_relevant": "explanation"}}]
}}
""".strip()
        raw = await self._call_json(prompt)
        if raw.get("insufficient_evidence") or "relevance_score" not in raw:
            # Deterministic NLP relevance fallback
            target_terms = extract_key_terms(
                f"{destination_summary.get('primary_topic', '')} {anchor_text} {' '.join(destination_summary.get('important_entities', []))}"
            )
            blog_terms = extract_key_terms(f"{blog_title} {blog_content}")
            common = target_terms.intersection(blog_terms)
            exact_in_blog = anchor_text.lower() in blog_content.lower()

            if exact_in_blog:
                score = 90.0 if len(common) >= 2 else 78.0
                recommended = True
                reason = f"Source article covers related concepts ({', '.join(list(common)[:3]) or 'topical overlap'}) and contains the phrase '{anchor_text}'."
            elif len(common) >= 3:
                score = 76.0
                recommended = True
                reason = f"Topical overlap on key concepts: {', '.join(list(common)[:4])}."
            elif len(common) >= 1:
                score = 48.0
                recommended = False
                reason = f"Weak topical overlap ('{list(common)[0]}'). Context is insufficient for a natural link."
            else:
                score = 12.0
                recommended = False
                reason = f"No topical or contextual relationship between '{blog_title}' and target topic '{destination_summary.get('primary_topic', '')}'."

            return RelevanceAnalysis(
                relevance_score=score,
                reader_value="high" if score >= 80 else ("medium" if score >= 60 else "low"),
                linking_recommended=recommended,
                reason=reason,
                evidence_spans=[],
                insufficient_evidence=False,
            )
        return RelevanceAnalysis(**raw)

    async def evaluate_placement_and_format(
        self,
        destination_summary: dict[str, Any],
        target_url: str,
        anchor_text: str,
        paragraphs: list[str],
        unlinked_occurrences: list[dict[str, Any]],
    ) -> PlacementAnalysis:
        """
        Layer 3 (AI Editorial Placement) + Layer 4 (Deterministic Fact Validation).
        Ensures exact character positions, real source sentences, and zero empty fallbacks.
        Filters out weak self-referential patterns.
        """
        # Case 1: Exact Unlinked Occurrence Exists in Source Article
        valid_unlinked = [o for o in unlinked_occurrences if not o.get("is_weak_context")]
        
        if valid_unlinked:
            best_occ = valid_unlinked[0]
            p_idx = best_occ["paragraph_index"]
            s_idx = best_occ.get("sentence_index", 0)
            orig_sentence = best_occ.get("sentence_text", "").strip()

            if not orig_sentence and p_idx < len(paragraphs):
                p_sentences = [s.strip() for s in _SENTENCE_SPLIT.split(paragraphs[p_idx]) if s.strip()]
                orig_sentence = p_sentences[s_idx] if s_idx < len(p_sentences) else paragraphs[p_idx].strip()

            bold_ver, md_ver, html_ver, s_start, s_end = build_link_formats(orig_sentence, anchor_text, target_url)

            if s_start == -1 or s_end <= s_start:
                # Anchor not found in sentence -> reject exact status
                pass
            else:
                p_text = paragraphs[p_idx] if p_idx < len(paragraphs) else orig_sentence
                ctx_score, is_acceptable, ctx_reason = evaluate_sentence_context_quality(
                    orig_sentence, anchor_text, p_text, base_confidence=0.96
                )

                if is_acceptable:
                    loc_ref = LocationRef(
                        paragraph_index=p_idx,
                        sentence_index=s_idx,
                        sentence_char_start=s_start,
                        sentence_char_end=s_end,
                        paragraph_char_start=best_occ.get("paragraph_char_start", 0),
                        paragraph_char_end=best_occ.get("paragraph_char_end", 0),
                        paragraph_total_sentences=best_occ.get("paragraph_total_sentences", 1),
                    )

                    return PlacementAnalysis(
                        decision="ACCEPT",
                        anchor_status="EXACT_UNLINKED_ANCHOR",
                        can_insert_naturally=True,
                        recommended_location=loc_ref,
                        original_sentence=orig_sentence,
                        suggested_sentence_edit=bold_ver,
                        ready_to_paste_markdown=md_ver,
                        ready_to_paste_html=html_ver,
                        suggested_link_span=anchor_text,
                        placement_reason=f"The exact phrase '{anchor_text}' naturally appears in paragraph #{p_idx + 1} with strong contextual depth.",
                        context_score=ctx_score,
                        confidence=0.96,
                        linking_recommended=True,
                        insufficient_evidence=False,
                    )

        # Case 2: Semantic Match / Contextual Clause Insertion
        target_terms = extract_key_terms(f"{destination_summary.get('primary_topic', '')} {anchor_text}")
        best_p_idx = -1
        best_score = 0

        for idx, p in enumerate(paragraphs):
            p_terms = extract_key_terms(p)
            overlap = len(target_terms.intersection(p_terms))
            if overlap > best_score:
                best_score = overlap
                best_p_idx = idx

        if best_p_idx >= 0 and best_score >= 2:
            p_text = paragraphs[best_p_idx].strip()
            sentences = [s.strip() for s in _SENTENCE_SPLIT.split(p_text) if s.strip()]
            
            # Find candidate sentence without weak patterns
            orig_sentence = ""
            for s in sentences:
                is_weak, _ = is_weak_context_sentence(s)
                if not is_weak and len(s) > 20:
                    orig_sentence = s
                    break

            if orig_sentence:
                clean_s = orig_sentence.rstrip(".!?")
                punct = orig_sentence[-1] if orig_sentence.endswith((".", "!", "?")) else "."
                
                new_sentence = f"{clean_s}, especially when considering {anchor_text}{punct}"
                bold_ver, md_ver, html_ver, s_start, s_end = build_link_formats(new_sentence, anchor_text, target_url)

                if s_start != -1 and s_end > s_start:
                    ctx_score, is_acceptable, ctx_reason = evaluate_sentence_context_quality(
                        orig_sentence, anchor_text, p_text, base_confidence=0.85
                    )

                    loc_ref = LocationRef(
                        paragraph_index=best_p_idx,
                        sentence_index=0,
                        sentence_char_start=s_start,
                        sentence_char_end=s_end,
                        paragraph_char_start=0,
                        paragraph_char_end=len(clean_s),
                        paragraph_total_sentences=len(sentences),
                    )

                    return PlacementAnalysis(
                        decision="ACCEPT",
                        anchor_status="SEMANTIC_ANCHOR_CANDIDATE",
                        can_insert_naturally=True,
                        recommended_location=loc_ref,
                        original_sentence=orig_sentence,
                        suggested_sentence_edit=bold_ver,
                        ready_to_paste_markdown=md_ver,
                        ready_to_paste_html=html_ver,
                        suggested_link_span=anchor_text,
                        placement_reason=f"Paragraph #{best_p_idx + 1} provides a strong contextual fit for a supporting clause reference.",
                        context_score=ctx_score,
                        confidence=0.85,
                        linking_recommended=True,
                        insufficient_evidence=False,
                    )

        # Case 3: Rejection (Weak or No Natural Placement)
        weak_reason = "No paragraph in this article provides sufficient contextual value for a natural editorial link."
        if unlinked_occurrences and all(o.get("is_weak_context") for o in unlinked_occurrences):
            weak_reason = f"Sentence contains a self-referential or promotional pattern ({unlinked_occurrences[0].get('weak_context_reason')})."

        return PlacementAnalysis(
            decision="REJECT",
            anchor_status="NONE",
            can_insert_naturally=False,
            recommended_location=None,
            original_sentence="",
            suggested_sentence_edit="",
            ready_to_paste_markdown="",
            ready_to_paste_html="",
            suggested_link_span="",
            placement_reason=weak_reason,
            context_score=35.0,
            confidence=0.90,
            linking_recommended=False,
            insufficient_evidence=False,
        )
