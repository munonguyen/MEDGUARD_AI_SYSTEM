"""Jev Micro-Judge for MedGuard AI System.

Phase 3.4 Architecture Invariant:
1. Deprecation of Dictatorial Triage: Jev NEVER issues global triage recommendations
   (ROUTINE, URGENT, EMERGENCY) and NEVER decides `allow_home_monitoring`.
2. Atomic Epistemic Evaluation: Evaluates specific, measurable probabilities and scores:
   - unsupported_claim_probability
   - overtriage_probability
   - undertriage_probability
   - context_alignment_score
   - redflag_coverage_score
   - evidence_grounding_score
3. Grounding & Calibration: Provides quantitative epistemic grounding to feed the
   Deterministic Arbitration Policy.
"""

from __future__ import annotations

from typing import Any
from app.models.evidence import ClinicalEvidencePacket
from app.models.intake import CompiledClinicalIntake
from app.models.safety import SafetyKernelResult
from app.models.synthesis import (
    CriticReport,
    JevMicroJudgment,
    ReasoningDraft,
)


class JevMicroJudge:
    """Gate 3 Jev: Micro-judgment engine evaluating atomic epistemic dimensions."""

    @classmethod
    def judge(
        cls,
        intake: CompiledClinicalIntake,
        evidence_packet: ClinicalEvidencePacket,
        safety_kernel: SafetyKernelResult,
        draft: ReasoningDraft,
        critic: CriticReport,
    ) -> JevMicroJudgment:
        advisory_notes: list[str] = []

        # 1. Unsupported Claim Probability
        # Derived from critic rejected claims, ungrounded claims, and definitive diagnosis violations
        total_claims = max(1, len(draft.claims))
        rejected_count = len(critic.rejected_claims)
        unsupported_violations = sum(1 for v in critic.violations if v.code == "UNSUPPORTED_DIAGNOSIS")

        unsupported_prob = min(
            1.0,
            (rejected_count / total_claims * 0.6) + (unsupported_violations * 0.4),
        )
        if unsupported_prob > 0.4:
            advisory_notes.append(f"High risk of unsupported assertions: prob={unsupported_prob:.2f}")

        # 2. Over-Triage Probability
        # Checks if draft triggered emergency/urgent without real safety flags
        is_routine_case = (
            safety_kernel.minimum_triage == "ROUTINE"
            and not safety_kernel.emergency_lock
            and not intake.red_flag_mentions
        )
        if is_routine_case and draft.urgency == "EMERGENCY":
            overtriage_prob = 0.95
            advisory_notes.append("Severe over-triage detected on confirmed benign case")
        elif is_routine_case and draft.urgency == "URGENT":
            overtriage_prob = 0.35
        else:
            overtriage_prob = 0.05

        # 3. Under-Triage Probability
        # Checks if safety kernel has emergency lock but draft missed it
        if safety_kernel.emergency_lock and draft.urgency != "EMERGENCY":
            undertriage_prob = 0.99
            advisory_notes.append("CRITICAL: Severe under-triage: Safety Kernel emergency disregarded")
        elif safety_kernel.emergency_lock and not any(k in draft.draft_answer.lower() for k in ["115", "cấp cứu"]):
            undertriage_prob = 0.80
            advisory_notes.append("Emergency urgency present but lacking emergency call-to-action")
        else:
            undertriage_prob = 0.02

        # 4. Context Alignment Score
        # Checks if draft hallucinates unmentioned context (e.g. assuming gym when user didn't mention it)
        draft_lower = draft.draft_answer.lower()
        raw_lower = intake.raw_query.lower()
        context_score = 0.95

        assumed_gym = ("tập gym" in draft_lower or "tập tạ" in draft_lower or "thể hình" in draft_lower)
        user_mentioned_gym = ("gym" in raw_lower or "tập tạ" in raw_lower or "thể hình" in raw_lower or "vận động" in raw_lower)
        if assumed_gym and not user_mentioned_gym:
            context_score -= 0.30
            advisory_notes.append("Hallucinated context: Assumed gym/weightlifting without user mention")

        context_score = max(0.2, min(1.0, context_score))

        # 5. Red Flag Coverage Score
        # How well draft covers mandatory warning signs
        if draft.red_flags:
            rf_score = 0.95
        else:
            rf_score = 0.40
            advisory_notes.append("Missing necessary clinical red flags in advisory")

        # 6. Evidence Grounding Score
        grounded_claims = sum(1 for c in draft.claims if c.evidence_ids and c.approved)
        grounding_score = min(1.0, grounded_claims / total_claims)
        if draft.sources:
            gov_sources = sum(1 for s in draft.sources if s.get("authority_tier") == "government_health")
            if gov_sources > 0:
                grounding_score = min(1.0, grounding_score + 0.1)

        return JevMicroJudgment(
            unsupported_claim_probability=round(unsupported_prob, 3),
            overtriage_probability=round(overtriage_prob, 3),
            undertriage_probability=round(undertriage_prob, 3),
            context_alignment_score=round(context_score, 3),
            redflag_coverage_score=round(rf_score, 3),
            evidence_grounding_score=round(grounding_score, 3),
            advisory_notes=advisory_notes,
        )
