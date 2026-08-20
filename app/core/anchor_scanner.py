from __future__ import annotations

import re
from typing import Any

from app.core.context_evaluator import is_weak_context_sentence

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_HTML_LINK_RE = re.compile(r"<a\s+(?:[^>]*?\s+)?href=([\"'])(.*?)\1[^>]*>(.*?)</a>", re.IGNORECASE)


def extract_all_existing_links_from_text(text: str) -> list[dict[str, Any]]:
    """Extracts HTML <a> tags and Markdown [text](url) links with character spans."""
    links = []
    for match in _HTML_LINK_RE.finditer(text):
        links.append({
            "type": "html",
            "href": match.group(2).strip(),
            "anchor": match.group(3).strip(),
            "start": match.start(),
            "end": match.end(),
        })
    for match in _MARKDOWN_LINK_RE.finditer(text):
        links.append({
            "type": "markdown",
            "href": match.group(2).strip(),
            "anchor": match.group(1).strip(),
            "start": match.start(),
            "end": match.end(),
        })
    return links


def scan_anchor_occurrences(
    paragraphs: list[str],
    anchor_text: str,
    existing_outbound_links: list[str],
    destination_norm: str,
) -> list[dict[str, Any]]:
    """
    Deterministically scans paragraphs for exact word-boundary occurrences of anchor_text.
    Calculates precise character offsets within both paragraph and sentence boundaries.
    Classifies each occurrence into:
    - EXACT_UNLINKED_ANCHOR
    - EXACT_ALREADY_TARGET_LINKED
    - EXACT_OTHER_LINKED
    """
    occurrences = []
    anchor_clean = anchor_text.strip()
    if not anchor_clean:
        return occurrences

    pattern = re.compile(r"\b" + re.escape(anchor_clean) + r"\b", re.IGNORECASE)

    for p_idx, paragraph in enumerate(paragraphs):
        p_clean = paragraph.strip()
        if not p_clean:
            continue

        sentences = [s.strip() for s in _SENTENCE_SPLIT.split(p_clean) if s.strip()]
        existing_links_in_p = extract_all_existing_links_from_text(p_clean)

        for match in pattern.finditer(p_clean):
            p_char_start = match.start()
            p_char_end = match.end()
            exact_snippet = p_clean[p_char_start:p_char_end]

            # Determine sentence index and sentence-relative character offsets
            sentence_index = 0
            sentence_text = ""
            s_char_start = -1
            s_char_end = -1

            consumed = 0
            for s_idx, s in enumerate(sentences):
                # Search for match in this specific sentence
                s_match = pattern.search(s)
                if s_match and p_char_start >= consumed and p_char_end <= consumed + len(s) + 5:
                    sentence_index = s_idx
                    sentence_text = s
                    s_char_start = s_match.start()
                    s_char_end = s_match.end()
                    break
                consumed += len(s) + 1

            if not sentence_text and sentences:
                sentence_text = sentences[0]
                s_m = pattern.search(sentence_text)
                if s_m:
                    s_char_start = s_m.start()
                    s_char_end = s_m.end()

            # If anchor was not found in sentence, skip
            if s_char_start == -1 or s_char_end <= s_char_start:
                continue

            # Check if this exact character span is already inside an existing HTML/MD link
            is_inside_link = False
            linked_href = ""
            for l in existing_links_in_p:
                if l["start"] <= p_char_start and p_char_end <= l["end"]:
                    is_inside_link = True
                    linked_href = l["href"]
                    break

            status = "EXACT_UNLINKED_ANCHOR"
            if is_inside_link:
                from app.core.url_utils import normalize_url
                norm_link = normalize_url(linked_href)
                if norm_link == destination_norm:
                    status = "EXACT_ALREADY_TARGET_LINKED"
                else:
                    status = "EXACT_OTHER_LINKED"

            # Check for weak editorial patterns
            is_weak, weak_reason = is_weak_context_sentence(sentence_text)

            occurrences.append({
                "paragraph_index": p_idx,
                "sentence_index": sentence_index,
                "paragraph_char_start": p_char_start,
                "paragraph_char_end": p_char_end,
                "sentence_char_start": s_char_start,
                "sentence_char_end": s_char_end,
                "anchor_text": exact_snippet,
                "sentence_text": sentence_text,
                "paragraph_text": p_clean,
                "status": status,
                "is_weak_context": is_weak,
                "weak_context_reason": weak_reason,
                "linked_href": linked_href,
                "paragraph_total_sentences": len(sentences),
            })

    return occurrences
