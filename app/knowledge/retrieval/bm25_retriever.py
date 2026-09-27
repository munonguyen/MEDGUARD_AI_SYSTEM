"""In-process BM25 Retrieval Engine for Exact Term & Clinical Identifier Matching.

Zero cloud cost, zero external dependencies. Highly optimized for:
- Exact drug active ingredients (warfarin, amoxicillin, paracetamol)
- Guideline decision codes (QĐ 361, TT 51)
- Standardized medical acronyms (DVT, ACS, INR, FAST, ECG)
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from typing import Any

from app.knowledge.ingestion.normalizer import NormalizedEvidence
from app.knowledge.ingestion.version_manager import KnowledgeSnapshot


def _tokenize(text: str) -> list[str]:
    """Cleans, normalizes, and splits text into search tokens."""
    text = text.lower().replace("đ", "d").replace("Đ", "d")
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    tokens = re.findall(r"\b[a-z0-9_]+\b", stripped)
    return tokens


class BM25Retriever:
    """In-process BM25 search index over NormalizedEvidence objects."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.corpus: list[NormalizedEvidence] = []
        self.doc_tokens: list[list[str]] = []
        self.doc_lengths: list[int] = []
        self.avg_doc_len: float = 0.0
        self.inverted_index: dict[str, list[int]] = {}
        self.idf: dict[str, float] = {}

    def index_snapshot(self, snapshot: KnowledgeSnapshot) -> None:
        """Indexes all NormalizedEvidence items contained within a snapshot."""
        self.corpus = list(snapshot.evidence_items.values())
        self.doc_tokens = []
        self.doc_lengths = []
        self.inverted_index = {}

        total_docs = len(self.corpus)
        if total_docs == 0:
            self.avg_doc_len = 0.0
            return

        for doc_idx, item in enumerate(self.corpus):
            full_text = f"{item.concept} {item.statement} {item.source_id} {item.section}"
            tokens = _tokenize(full_text)
            self.doc_tokens.append(tokens)
            self.doc_lengths.append(len(tokens))

            unique_tokens = set(tokens)
            for token in unique_tokens:
                self.inverted_index.setdefault(token, []).append(doc_idx)

        self.avg_doc_len = sum(self.doc_lengths) / total_docs

        # Calculate IDF for each token: ln((N - n + 0.5) / (n + 0.5) + 1)
        self.idf = {}
        for token, doc_list in self.inverted_index.items():
            n = len(doc_list)
            self.idf[token] = math.log(((total_docs - n + 0.5) / (n + 0.5)) + 1.0)

    def search(self, query: str, top_k: int = 10) -> list[tuple[NormalizedEvidence, float]]:
        """Executes BM25 scoring for a search query, returning top-k scored documents."""
        query_tokens = _tokenize(query)
        if not query_tokens or not self.corpus:
            return []

        scores = [0.0] * len(self.corpus)

        for q_token in query_tokens:
            if q_token not in self.idf:
                continue

            q_idf = self.idf[q_token]
            matching_docs = self.inverted_index.get(q_token, [])

            for doc_idx in matching_docs:
                freq = self.doc_tokens[doc_idx].count(q_token)
                doc_len = self.doc_lengths[doc_idx]
                numerator = freq * (self.k1 + 1.0)
                denominator = freq + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avg_doc_len))
                scores[doc_idx] += q_idf * (numerator / denominator)

        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        results = [
            (self.corpus[idx], scores[idx])
            for idx in ranked_indices
            if scores[idx] > 0.0
        ]
        return results[:top_k]
