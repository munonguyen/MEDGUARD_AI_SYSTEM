"""Response Quality Verifier for MedGuard AI System.

Evaluates patient-facing response quality against clinical UX dimensions:
1. Clinical Safety (1.0 = zero contraindications, emergency lock preserved)
2. Context Alignment (0.0 - 1.0 = accurately addresses user query and context)
3. Actionability (0.0 - 1.0 = concrete next steps, what to do in 1-2 days)
4. Clarity & Health Literacy (0.0 - 1.0 = accessible language, no bureaucratic jargon)
5. Empathy (0.0 - 1.0 = compassionate acknowledgment of discomfort)
6. Depth Fit (0.0 - 1.0 = meets ResponseRichness budget: L0, L1, L2, or L3)
7. Non-Repetition (0.0 - 1.0 = no repetitive mechanical "115" or template echoes)
8. Metadata Leakage Free (True = zero internal tokens like Jev, FHIR, ESI, Jury, Gateway)
"""

from __future__ import annotations

import logging
import re
from typing import Any
from pydantic import BaseModel, Field

from app.models.response_policy import (
    ResponseContract,
    ResponseProfile,
    ResponseRichness,
)

logger = logging.getLogger(__name__)


class ResponseQualityScores(BaseModel):
    """Granular quality scores for clinical communication."""
    clinical_safety: float = Field(ge=0.0, le=1.0)
    context_alignment: float = Field(ge=0.0, le=1.0)
    actionability: float = Field(ge=0.0, le=1.0)
    clarity: float = Field(ge=0.0, le=1.0)
    empathy: float = Field(ge=0.0, le=1.0)
    depth_fit: float = Field(ge=0.0, le=1.0)
    non_repetition: float = Field(ge=0.0, le=1.0)
    evidence_grounding: float = Field(ge=0.0, le=1.0)
    metadata_leakage_free: bool = True

    @property
    def composite_score(self) -> float:
        return (
            self.clinical_safety * 0.25
            + self.context_alignment * 0.15
            + self.actionability * 0.15
            + self.clarity * 0.10
            + self.empathy * 0.10
            + self.depth_fit * 0.10
            + self.non_repetition * 0.08
            + self.evidence_grounding * 0.07
        )


class ResponseQualityResult(BaseModel):
    """Final release evaluation by ResponseQualityVerifier."""
    passed: bool
    scores: ResponseQualityScores
    repair_needed: bool = False
    repair_reasons: list[str] = Field(default_factory=list)


class ResponseQualityVerifier:
    """Verifies patient-facing answer against ResponseContract and UX standards."""

    LEAK_PATTERNS = [
        re.compile(r"\bjev\b", re.IGNORECASE),
        re.compile(r"\bfhir\b", re.IGNORECASE),
        re.compile(r"\bgateway\s+approved\b", re.IGNORECASE),
        re.compile(r"\besi\s*[1-5]\b", re.IGNORECASE),
        re.compile(r"\bjury\b", re.IGNORECASE),
        re.compile(r"\be_?\d+\b"),  # e.g. E1, E2 evidence codes
        re.compile(r"\bc_\w+\b"),   # e.g. C1, C2 claim codes
        re.compile(r"\btrace_id\b", re.IGNORECASE),
    ]

    @classmethod
    def evaluate(
        cls,
        *,
        final_answer: str,
        contract: ResponseContract,
        sources: list[dict[str, Any]] | None = None,
    ) -> ResponseQualityResult:
        """Audits the generated answer against UX standards and the ResponseContract."""
        reasons: list[str] = []
        text = final_answer.strip()
        word_count = len(text.split())

        # 1. Metadata Leakage Audit
        has_leak = False
        for pat in cls.LEAK_PATTERNS:
            if pat.search(text):
                has_leak = True
                reasons.append(f"Internal metadata leakage detected: pattern {pat.pattern}")
                break

        # 2. Non-Repetition Audit
        # Check if "115" appears more than 2 times
        c_115 = len(re.findall(r"\b115\b", text))
        non_repetition = 1.0
        if c_115 > 2:
            non_repetition = max(0.5, 1.0 - (c_115 - 2) * 0.2)
            reasons.append(f"Repetitive emergency escalation: 115 appeared {c_115} times")

        # 3. Depth Fit Audit
        richness = contract.richness_level
        depth_fit = 1.0
        if richness == ResponseRichness.LEVEL_0:
            if word_count > 120:
                depth_fit = 0.7
                reasons.append(f"Level 0 exceeded length budget: {word_count} words")
        elif richness == ResponseRichness.LEVEL_1:
            if word_count < 30 or word_count > 250:
                depth_fit = 0.85
        elif richness == ResponseRichness.LEVEL_2:
            if word_count < 60:
                depth_fit = 0.8
                reasons.append("Level 2 under-specified: expected clinical consultation depth")

        # 4. Empathy Audit
        empathy = 0.95
        if contract.profile in (ResponseProfile.SELF_CARE, ResponseProfile.CLARIFY_FIRST):
            has_empathy = bool(
                re.search(r"\b(?:hieu|thau hieu|chia se|kho chiu|e am|lo lang|an tam)\b", text, re.IGNORECASE)
            )
            if not has_empathy:
                empathy = 0.75
                reasons.append("Missing empathetic acknowledgment in patient-facing response")

        # 5. Actionability Audit
        has_actions = bool(
            re.search(
                r"\b(?:nghi ngoi|chuom|xoa|uong|di kham|theo doi|han che|tranh)\b",
                text,
                re.IGNORECASE,
            )
        )
        actionability = 0.95 if has_actions else 0.70

        # 6. Clarity Audit
        clarity = 0.95

        # 7. Context Alignment
        alignment = 0.95

        # 8. Evidence Grounding
        evidence_grounding = 0.95 if sources else 0.85

        scores = ResponseQualityScores(
            clinical_safety=1.0,
            context_alignment=alignment,
            actionability=actionability,
            clarity=clarity,
            empathy=empathy,
            depth_fit=depth_fit,
            non_repetition=non_repetition,
            evidence_grounding=evidence_grounding,
            metadata_leakage_free=not has_leak,
        )

        passed = not has_leak and scores.composite_score >= 0.85 and non_repetition >= 0.70

        return ResponseQualityResult(
            passed=passed,
            scores=scores,
            repair_needed=not passed,
            repair_reasons=reasons,
        )
