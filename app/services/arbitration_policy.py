"""Deterministic Arbitration Policy for MedGuard AI System.

Phase 3.5 Architecture Invariant:
1. Pure Deterministic Logic: Code rules decide the action, NOT an LLM, NOT Jev.
2. Zero Hallucination Overhead: Resolves conflicts objectively based on Safety Kernel,
   Critic violations, and Jev micro-judgment probabilities.
3. Strict Safety Routing:
   - ACCEPT_A: All safety, evidence, and clinical invariants are satisfied.
   - REPAIR_A: Minor or isolated violation; targeted surgical repair required.
   - REGENERATE: Structural reasoning failure requiring fresh synthesis.
   - SAFE_FALLBACK: Multiple severe violations or critical safety breach.
"""

from __future__ import annotations

from typing import Any
from app.models.safety import SafetyKernelResult
from app.models.synthesis import (
    ArbitrationDecision,
    CriticReport,
    JevMicroJudgment,
    ReasoningDraft,
)


class ArbitrationPolicy:
    """Deterministic policy arbiter that decides pipeline execution route."""

    @classmethod
    def arbitrate(
        cls,
        safety_kernel: SafetyKernelResult,
        critic: CriticReport,
        jev: JevMicroJudgment,
        draft: ReasoningDraft,
    ) -> ArbitrationDecision:
        reasons: list[str] = []
        claims_to_repair: list[str] = list(critic.rejected_claims)
        mandatory_emergency = safety_kernel.emergency_lock
        fallback_policy: str | None = None

        # 1. Critical Safety Floor Breach
        if safety_kernel.emergency_lock and draft.urgency != "EMERGENCY":
            reasons.append("Safety Kernel emergency floor violated by Draft A.")
            if len(critic.violations) >= 2:
                return ArbitrationDecision(
                    action="SAFE_FALLBACK",
                    reasons=reasons,
                    mandatory_emergency=True,
                    fallback_policy="SAFE_EMERGENCY",
                )
            return ArbitrationDecision(
                action="REPAIR_A",
                reasons=reasons,
                claims_to_repair=claims_to_repair,
                mandatory_emergency=True,
                fallback_policy="SAFE_EMERGENCY",
            )

        # 2. Critical Number of High Severity Violations
        critical_violations = [v for v in critic.violations if v.severity == "CRITICAL"]
        high_violations = [v for v in critic.violations if v.severity == "HIGH"]
        if len(critical_violations) > 0 or len(high_violations) >= 2 or jev.unsupported_claim_probability > 0.85:
            reasons.append(f"Multiple high severity violations ({len(high_violations)} high, {len(critical_violations)} critical).")
            fallback_type = "SAFE_EMERGENCY" if mandatory_emergency else (
                "SAFE_URGENT" if draft.urgency == "URGENT" else "SAFE_GENERAL"
            )
            return ArbitrationDecision(
                action="SAFE_FALLBACK",
                reasons=reasons,
                mandatory_emergency=mandatory_emergency,
                fallback_policy=fallback_type,
            )

        # 3. Targeted Repair Required
        requires_repair = False
        if len(high_violations) == 1:
            reasons.append(f"High severity violation requiring repair: {high_violations[0].code}")
            requires_repair = True

        if critic.rejected_claims:
            reasons.append(f"Rejected claims requiring removal or repair: {', '.join(critic.rejected_claims)}")
            requires_repair = True

        if jev.overtriage_probability > 0.80:
            reasons.append("High over-triage probability detected on benign case.")
            requires_repair = True

        if jev.redflag_coverage_score < 0.60 or any(m.type == "red_flag" for m in critic.missing_points):
            reasons.append("Mandatory red flags missing in draft.")
            requires_repair = True

        if requires_repair:
            return ArbitrationDecision(
                action="REPAIR_A",
                reasons=reasons,
                claims_to_repair=claims_to_repair,
                mandatory_emergency=mandatory_emergency,
            )

        # 4. Clean Pass: Accept A
        reasons.append("Draft A passed all critic audits and Jev micro-judgment thresholds.")
        return ArbitrationDecision(
            action="ACCEPT_A",
            reasons=reasons,
            claims_to_repair=[],
            mandatory_emergency=mandatory_emergency,
        )
