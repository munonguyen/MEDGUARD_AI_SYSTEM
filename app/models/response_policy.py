"""Response Policy & Contract Data Models for MedGuard AI System.

Implements the SOTA Clinical UX Architecture:
Clinical State + Safety Result + User Intent + Uncertainty + Evidence
    -> Response Policy Engine -> Response Contract -> Adaptive Clinical Response.

Separation of Concerns:
- Safety Kernel: WHAT MUST NOT BE VIOLATED (hard boundary)
- Response Policy: HOW SHOULD WE RESPOND (profile, severity, need, contract)
- Jev Context Planner: WHAT CONTEXT / DEPTH / TONE IS USEFUL
- Final Synthesis: FINAL PATIENT-FACING ANSWER adhering to ResponseContract
- Clinical Output Guard: CAN IT BE RELEASED?
- Response Quality Check: UX, empathy, actionability, non-repetition audit
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field


class ResponseProfile(str, Enum):
    """Core communicative archetype for the patient response."""
    CONVERSATIONAL = "conversational"
    SELF_CARE = "self_care"
    CLARIFY_FIRST = "clarify_first"
    CLINICAL_EXPLANATION = "clinical_explanation"
    MEDICATION_SAFETY = "medication_safety"
    URGENT_GUIDANCE = "urgent_guidance"
    EMERGENCY_ACTION = "emergency_action"


class ClinicalSeverity(str, Enum):
    """Clinical severity dimension independent of response need."""
    S0_BENIGN = "S0"          # Benign, informational, normal physiology
    S1_MILD = "S1"            # Mild symptoms, stable, routine self-care
    S2_UNCERTAIN = "S2"       # Ambiguous symptoms, requires clarification / safety net
    S3_CONCERNING = "S3"      # Significant symptoms, potential complication, requires prompt evaluation
    S4_EMERGENCY = "S4"       # Life-threatening red flag, emergency lock engaged


class ResponseNeed(str, Enum):
    """Response need dimension determining the patient-facing goal."""
    R0_SIMPLE_ANSWER = "R0"       # 1-2 sentence direct educational answer
    R1_EDUCATION = "R1"           # Health literacy explanation of concepts
    R2_SELF_CARE = "R2"           # Safe, actionable home care in 1-2 days
    R3_CLARIFICATION = "R3"       # High-information-gain clinical clarifying questions
    R4_MEDICATION_SAFETY = "R4"   # Interaction, contraindication, or dosage audit
    R5_URGENT_ACTION = "R5"       # Immediate emergency actions and emergency services escalation


class ResponseRichness(str, Enum):
    """4-level response richness budget."""
    LEVEL_0 = "LEVEL_0"  # 1-2 sentences for simple factual queries
    LEVEL_1 = "LEVEL_1"  # Short explanation + single primary action
    LEVEL_2 = "LEVEL_2"  # Explanation + differentials + self-care + red flags + follow-up
    LEVEL_3 = "LEVEL_3"  # Full structured clinical answer + drug review + monitoring + next steps


class ResponseContract(BaseModel):
    """Immutable contract governing what Final Synthesis must and must not produce."""
    profile: ResponseProfile
    severity: ClinicalSeverity
    response_need: ResponseNeed
    richness_level: ResponseRichness = ResponseRichness.LEVEL_2
    required_sections: list[str] = Field(default_factory=list)
    max_length: int = 650
    tone: str = "calm_reassuring"
    medical_depth: str = "moderate"
    must_not_include: list[str] = Field(
        default_factory=lambda: [
            "internal_gateway_status",
            "Jev",
            "FHIR",
            "jury",
            "evidence_id",
            "source_approval",
            "ESI 4",
            "ESI 5",
            "ESI 3",
            "ROUTINE",
            "trace_id",
        ]
    )
    adaptive_quick_replies: list[dict[str, str]] = Field(default_factory=list)


class ClinicalResponseContext(BaseModel):
    """Jev Context Planner output specifying tone, depth, and clinical context."""
    tone: str = "calm_reassuring"
    depth: str = "moderate"
    primary_goal: str = "self_care_and_clarification"
    explain: list[str] = Field(default_factory=list)
    highlight_red_flags: list[str] = Field(default_factory=list)
    ask_next: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(
        default_factory=lambda: [
            "definitive diagnosis",
            "unnecessary emergency language",
            "internal jargon",
            "repetitive 115 warnings",
        ]
    )
    adaptive_quick_replies: list[dict[str, str]] = Field(default_factory=list)
