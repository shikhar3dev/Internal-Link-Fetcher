from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import numpy as np
from rank_bm25 import BM25Okapi

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Tokenizes text into lowercase alphanumeric tokens."""
    return TOKEN_RE.findall((text or "").lower())


@dataclass
class Candidate:
    article_id: int
    score: float


def cosine_similarity_matrix(target_vec: np.ndarray, candidate_matrix: np.ndarray) -> np.ndarray:
    """Computes cosine similarity between target vector and matrix of candidate embeddings."""
    dot_products = np.dot(candidate_matrix, target_vec)
    norm_a = np.linalg.norm(target_vec)
    norms_b = np.linalg.norm(candidate_matrix, axis=1)
    return dot_products / (norm_a * norms_b + 1e-10)


class HybridRetriever:
    def __init__(self, articles: list[dict[str, Any]]) -> None:
        self.articles = articles
        self.corpus_tokens = [tokenize(f"{a.get('title', '')} {a.get('content_text', '')}") for a in articles]
        self.bm25 = BM25Okapi(self.corpus_tokens) if articles else None

    def bm25_top(self, query: str, top_n: int = 300) -> list[Candidate]:
        """Ranks articles using BM25 keyword/concept scoring."""
        if not self.bm25 or not self.articles:
            return []
        tokens = tokenize(query)
        if not tokens:
            return [Candidate(article_id=int(a["id"]), score=1.0) for a in self.articles[:top_n]]
            
        scores = self.bm25.get_scores(tokens)
        ranked_idx = np.argsort(scores)[::-1][:top_n]
        out = []
        for i in ranked_idx:
            out.append(Candidate(article_id=int(self.articles[int(i)]["id"]), score=float(scores[int(i)])))
        return out

    def vector_top(self, target_embedding: list[float], top_n: int = 300) -> list[Candidate]:
        """Ranks articles using vector cosine similarity on pre-computed embeddings."""
        if not self.articles or not target_embedding:
            return []
            
        valid_indices = []
        vectors = []
        for idx, a in enumerate(self.articles):
            if a.get("embedding"):
                valid_indices.append(idx)
                vectors.append(a["embedding"])
                
        if not vectors:
            return []
            
        target_vec = np.array(target_embedding, dtype=np.float32)
        matrix = np.array(vectors, dtype=np.float32)
        
        sims = cosine_similarity_matrix(target_vec, matrix)
        ranked_order = np.argsort(sims)[::-1][:top_n]
        
        out = []
        for rank in ranked_order:
            actual_article_idx = valid_indices[int(rank)]
            article_id = int(self.articles[actual_article_idx]["id"])
            out.append(Candidate(article_id=article_id, score=float(sims[rank]) * 100.0))
        return out

    def merge_scores(
        self, bm25_candidates: list[Candidate], vector_candidates: list[Candidate], top_n: int = 120
    ) -> list[Candidate]:
        """Combines BM25 and Vector scores using Reciprocal Rank Fusion / normalized weighted sum."""
        merged: dict[int, float] = {}

        # Normalize BM25 scores (0-50 scale)
        if bm25_candidates:
            max_bm25 = max(c.score for c in bm25_candidates) or 1.0
            for c in bm25_candidates:
                merged[c.article_id] = merged.get(c.article_id, 0.0) + (c.score / max_bm25) * 45.0

        # Vector scores (0-55 scale)
        if vector_candidates:
            max_vec = max(c.score for c in vector_candidates) or 1.0
            for c in vector_candidates:
                merged[c.article_id] = merged.get(c.article_id, 0.0) + (c.score / max_vec) * 55.0

        ranked = sorted(
            (Candidate(article_id=k, score=v) for k, v in merged.items()),
            key=lambda x: x.score,
            reverse=True,
        )
        return ranked[:top_n]


def parse_paragraphs(paragraphs_json: str) -> list[str]:
    try:
        data = json.loads(paragraphs_json or "[]")
        if isinstance(data, list):
            return [str(x) for x in data if str(x).strip()]
    except Exception:
        pass
    return []
