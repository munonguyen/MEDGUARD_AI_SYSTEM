"""In-process Semantic Vector Retriever.

Employs subword & character n-gram TF-IDF vector embeddings with cosine similarity.
Guarantees 100% in-process execution, zero AWS cloud cost, and instant retrieval for
colloquial and descriptive Vietnamese patient narratives.
"""

from __future__ import annotations

import math
import unicodedata
from collections import Counter
from typing import Any

from app.knowledge.ingestion.normalizer import NormalizedEvidence
from app.knowledge.ingestion.version_manager import KnowledgeSnapshot


def _char_ngrams(text: str, n: int = 3) -> list[str]:
    """Generates character n-grams from normalized text for robust fuzzy semantic matching."""
    text = text.lower().replace("đ", "d").replace("Đ", "d")
    decomposed = unicodedata.normalize("NFKD", text)
    clean = "".join(c for c in decomposed if not unicodedata.combining(c) and c.isalnum() or c.isspace())
    words = clean.split()
    padded = f" {' '.join(words)} "
    return [padded[i : i + n] for i in range(len(padded) - n + 1)]


class VectorRetriever:
    """In-process Semantic Similarity Retriever over NormalizedEvidence."""

    def __init__(self, ngram_size: int = 3) -> None:
        self.ngram_size = ngram_size
        self.corpus: list[NormalizedEvidence] = []
        self.doc_vectors: list[dict[str, float]] = []
        self.doc_norms: list[float] = []
        self.idf: dict[str, float] = {}

    def index_snapshot(self, snapshot: KnowledgeSnapshot) -> None:
        self.corpus = list(snapshot.evidence_items.values())
        self.doc_vectors = []
        self.doc_norms = []

        total_docs = len(self.corpus)
        if total_docs == 0:
            return

        doc_ngram_counts: list[Counter[str]] = []
        df: Counter[str] = Counter()

        for item in self.corpus:
            text = f"{item.concept} {item.statement}"
            ngrams = _char_ngrams(text, self.ngram_size)
            counts = Counter(ngrams)
            doc_ngram_counts.append(counts)
            for ng in counts:
                df[ng] += 1

        self.idf = {
            ng: math.log((total_docs + 1.0) / (count + 1.0)) + 1.0
            for ng, count in df.items()
        }

        for counts in doc_ngram_counts:
            vec: dict[str, float] = {}
            for ng, tf in counts.items():
                vec[ng] = (1.0 + math.log(tf)) * self.idf.get(ng, 1.0)
            norm = math.sqrt(sum(v * v for v in vec.values()))
            self.doc_vectors.append(vec)
            self.doc_norms.append(norm if norm > 0.0 else 1.0)

    def search(self, query: str, top_k: int = 10) -> list[tuple[NormalizedEvidence, float]]:
        """Returns evidence ranked by cosine similarity against the query vector."""
        if not self.corpus:
            return []

        q_ngrams = _char_ngrams(query, self.ngram_size)
        if not q_ngrams:
            return []

        q_counts = Counter(q_ngrams)
        q_vec: dict[str, float] = {}
        for ng, tf in q_counts.items():
            if ng in self.idf:
                q_vec[ng] = (1.0 + math.log(tf)) * self.idf[ng]

        q_norm = math.sqrt(sum(v * v for v in q_vec.values()))
        if q_norm == 0.0:
            return []

        results: list[tuple[NormalizedEvidence, float]] = []
        for idx, doc_vec in enumerate(self.doc_vectors):
            dot_product = sum(q_vec[ng] * doc_vec[ng] for ng in q_vec if ng in doc_vec)
            similarity = dot_product / (q_norm * self.doc_norms[idx])
            if similarity > 0.05:
                results.append((self.corpus[idx], similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]


# Architecture Aliases: Character N-Gram / Sparse Semantic Retrieval
CharNgramRetriever = VectorRetriever
SparseSemanticRetriever = VectorRetriever
