from __future__ import annotations

import re

# Weak / promotional self-referential patterns that produce poor editorial links
WEAK_CONTEXT_PATTERNS = [
    (re.compile(r"\b(already\s+reviewed|already\s+covered|already\s+discussed)\b", re.IGNORECASE), "References prior review/coverage rather than presenting contextual substance"),
    (re.compile(r"\b(our\s+dedicated\s+page|on\s+our\s+dedicated\s+page|dedicated\s+article)\b", re.IGNORECASE), "Meta-reference to dedicated page rather than editorial context"),
    (re.compile(r"\b(click\s+here|click\s+this\s+link|tap\s+here)\b", re.IGNORECASE), "Low-quality generic anchor context ('click here')"),
    (re.compile(r"\b(read\s+more\s+at|learn\s+more\s+at|see\s+more\s+at)\b", re.IGNORECASE), "Promotional CTA pattern"),
    (re.compile(r"\b(visit\s+this\s+page|check\s+out\s+this\s+page)\b", re.IGNORECASE), "Generic navigational instruction"),
    (re.compile(r"\b(as\s+mentioned\s+above|as\s+discussed\s+earlier|as\s+stated\s+previously)\b", re.IGNORECASE), "Self-referential document pointer"),
]


def is_weak_context_sentence(sentence: str) -> tuple[bool, str]:
    """
    Checks if a sentence contains weak/promotional self-referential phrases that make it poor for editorial internal links.
    Returns (is_weak, reason)
    """
    if not sentence or len(sentence.strip()) < 15:
        return True, "Sentence is too short to provide contextual depth"

    for pattern, reason in WEAK_CONTEXT_PATTERNS:
        if pattern.search(sentence):
            return True, f"Weak editorial pattern detected: {reason}"

    return False, ""


def evaluate_sentence_context_quality(
    sentence: str,
    anchor_text: str,
    paragraph_text: str,
    base_confidence: float = 0.9,
) -> tuple[float, bool, str]:
    """
    Evaluates the editorial and grammatical suitability of placing an anchor in a sentence.
    Returns (context_score: float, is_acceptable: bool, reason: str)
    """
    clean_s = sentence.strip()
    words = clean_s.split()
    word_count = len(words)

    # 1. Check for weak self-referential patterns
    is_weak, weak_reason = is_weak_context_sentence(clean_s)
    if is_weak:
        return 35.0, False, weak_reason

    # 2. Minimum length requirements
    if word_count < 6:
        return 40.0, False, "Sentence is too brief (<6 words) for natural contextual linking"

    # 3. Informational density check
    score = 75.0

    # Strong topical indicators (+10 to +20)
    anchor_low = anchor_text.lower()
    if anchor_low in clean_s.lower():
        score += 15.0
    
    # Substantive sentence structure (+5 to +10)
    if 10 <= word_count <= 35:
        score += 10.0
    elif word_count > 35:
        score += 5.0

    # Surrounding paragraph depth
    p_words = len(paragraph_text.split())
    if p_words >= 30:
        score += 5.0

    final_score = round(min(100.0, max(0.0, score * (base_confidence or 0.9))), 1)
    is_acceptable = final_score >= 70.0
    
    reason = (
        "Strong editorial context directly connecting topical concepts to the target"
        if is_acceptable
        else "Context quality score is below the minimum threshold (70)"
    )

    return final_score, is_acceptable, reason


def calculate_content_quality(
    word_count: int,
    headings_count: int = 1,
    paragraphs_count: int = 1,
) -> float:
    """
    Computes deterministic Content Quality Score (0-100) based on verified article depth signals.
    """
    score = 50.0

    # Word count scale
    if word_count >= 1000:
        score += 35.0
    elif word_count >= 500:
        score += 25.0
    elif word_count >= 250:
        score += 15.0
    elif word_count >= 100:
        score += 5.0
    else:
        score -= 15.0

    # Structural richness (headings & paragraphs)
    if headings_count >= 3:
        score += 10.0
    elif headings_count >= 1:
        score += 5.0

    if paragraphs_count >= 4:
        score += 5.0

    return round(max(20.0, min(100.0, score)), 1)
