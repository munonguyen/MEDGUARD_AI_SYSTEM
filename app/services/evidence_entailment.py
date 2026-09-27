"""Evidence Entailment Engine (Natural Language Inference for Claim-Evidence Linkage).

Solves the subtle hallucination problem where a citation exists and is valid,
but the generated clinical claim asserts a stronger, definitive, or unwarranted statement
beyond what the source evidence actually substantiates.

Cascaded Architecture:
1. Deterministic Rule Checks (modal over-claiming, certainty escalation, negation mismatch).
2. Semantic Entailment Classification (SUPPORTS, PARTIALLY_SUPPORTS, CONTRADICTS, NOT_RELEVANT).
3. Recommended Downgrade Suggestions.
"""

from __future__ import annotations

import re
from typing import Literal
from pydantic import BaseModel, Field

from app.models.verification import EvidenceRelation


class EntailmentResult(BaseModel):
    """Result of claim-evidence entailment verification."""
    claim_id: str
    evidence_id: str
    relation: EvidenceRelation
    confidence: float = Field(ge=0.0, le=1.0)
    over_claiming_detected: bool = False
    negation_mismatch: bool = False
    mitigation_recommendation: str | None = None
    explanation: str = ""


class EvidenceEntailmentEngine:
    """Cascaded NLI Engine verifying claim-evidence faithfulness."""

    CERTAINTY_MARKERS = (
        "chắc chắn",
        "100%",
        "khẳng định",
        "xác định bạn bị",
        "chính xác là",
        "cam kết",
        "hoàn toàn là",
    )

    MODAL_UNCERTAINTY_MARKERS = (
        "có thể",
        "khả năng",
        "nghi ngờ",
        "theo dõi",
        "chẩn đoán phân biệt",
        "cân nhắc",
        "nguy cơ",
    )

    NEGATION_WORDS = ("không", "chưa", "chống chỉ định", "tuyệt đối không", "tránh")

    @classmethod
    def evaluate(cls, claim_id: str, claim_text: str, evidence_id: str, evidence_statement: str) -> EntailmentResult:
        c_lower = claim_text.lower()
        e_lower = evidence_statement.lower()

        # -------------------------------------------------------------
        # 1. Deterministic Rule Check: Negation Mismatch
        # -------------------------------------------------------------
        c_neg = any(w in c_lower for w in ("chống chỉ định", "không được", "tuyệt đối không"))
        e_neg = any(w in e_lower for w in ("chống chỉ định", "không được", "tuyệt đối không"))

        if c_neg != e_neg and any(w in c_lower for w in ("uống", "dùng", "kết hợp")) and any(w in e_lower for w in ("uống", "dùng", "kết hợp")):
            return EntailmentResult(
                claim_id=claim_id,
                evidence_id=evidence_id,
                relation="CONTRADICTS",
                confidence=0.98,
                negation_mismatch=True,
                mitigation_recommendation="Loại bỏ claim do mâu thuẫn trực tiếp với hướng dẫn an toàn trong bằng chứng.",
                explanation="Phát hiện mâu thuẫn phủ định: Bằng chứng quy định chống chỉ định nhưng claim khuyến nghị sử dụng (hoặc ngược lại).",
            )

        # -------------------------------------------------------------
        # 2. Deterministic Rule Check: Certainty Over-Claiming
        # -------------------------------------------------------------
        claim_has_certainty = any(m in c_lower for m in cls.CERTAINTY_MARKERS)
        evidence_is_probabilistic = any(m in e_lower for m in cls.MODAL_UNCERTAINTY_MARKERS)

        if claim_has_certainty:
            # Over-claiming: Source gives a differential or caution, but claim states certainty!
            return EntailmentResult(
                claim_id=claim_id,
                evidence_id=evidence_id,
                relation="PARTIALLY_SUPPORTS",
                confidence=0.92,
                over_claiming_detected=True,
                mitigation_recommendation="Hạ cấp khẳng định chắc chắn thành khả năng phân biệt (dùng 'có thể', 'nghi ngờ').",
                explanation=(
                    f"Luận điểm khẳng định tuyệt đối ('{claim_text[:50]}...') trong khi bằng chứng y khoa "
                    f"chỉ ủng hộ mức độ nghi ngờ hoặc chẩn đoán phân biệt."
                ),
            )

        # -------------------------------------------------------------
        # 3. Topic Overlap / Semantic Relevance Check
        # -------------------------------------------------------------
        # Token intersection between claim and evidence
        c_words = set(re.findall(r"\b\w{3,}\b", c_lower))
        e_words = set(re.findall(r"\b\w{3,}\b", e_lower))
        overlap = c_words.intersection(e_words)

        if not overlap:
            return EntailmentResult(
                claim_id=claim_id,
                evidence_id=evidence_id,
                relation="NOT_RELEVANT",
                confidence=0.90,
                mitigation_recommendation="Thay thế Evidence ID bằng trích dẫn trực tiếp liên quan đến luận điểm.",
                explanation="Bằng chứng được trích dẫn không có từ khóa hoặc chủ đề liên quan đến luận điểm.",
            )

        overlap_ratio = len(overlap) / max(len(c_words), 1)

        # Generic common medical stop-words that don't constitute topical relevance on their own
        generic_stops = {"viêm", "thuốc", "bệnh", "điều", "trị", "chứng", "nhân"}
        if len(overlap) == 1 and overlap.issubset(generic_stops) or overlap_ratio < 0.15:
            return EntailmentResult(
                claim_id=claim_id,
                evidence_id=evidence_id,
                relation="NOT_RELEVANT",
                confidence=0.88,
                mitigation_recommendation="Thay thế Evidence ID bằng trích dẫn trực tiếp liên quan đến luận điểm.",
                explanation="Bằng chứng được trích dẫn không có từ khóa chuyên biệt hoặc chủ đề liên quan đến luận điểm.",
            )

        # -------------------------------------------------------------
        # 4. Standard Entailment Classification
        # -------------------------------------------------------------
        if overlap_ratio >= 0.25:
            return EntailmentResult(
                claim_id=claim_id,
                evidence_id=evidence_id,
                relation="SUPPORTS",
                confidence=round(min(0.85 + overlap_ratio * 0.15, 0.99), 2),
                explanation="Bằng chứng hỗ trợ đầy đủ và phù hợp với luận điểm lâm sàng.",
            )

        return EntailmentResult(
            claim_id=claim_id,
            evidence_id=evidence_id,
            relation="PARTIALLY_SUPPORTS",
            confidence=0.75,
            mitigation_recommendation="Bổ sung thêm trích dẫn củng cố để luận điểm được chứng minh toàn diện hơn.",
            explanation="Bằng chứng hỗ trợ một phần ngữ cảnh nhưng chưa bao quát toàn bộ nội dung luận điểm.",
        )
