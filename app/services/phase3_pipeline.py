"""Phase 3 Master Clinical Pipeline for MedGuard AI System.

Architectural Progression:
Understand -> Retrieve -> Reason -> Critique -> Judge -> Synthesize -> Verify -> Release

1. Clinical Intake Compiler (Dual Representation)
2. Adaptive Complexity Router (C0 - C4)
3. Safety Kernel (Deterministic Hard Emergency Floor & Contraindications)
4. Multi-Domain Clinical Evidence Retriever (Typed ClinicalEvidencePacket with Provenance)
5. Agent A: Clinical Reasoner (Structured Draft with Atomic Claims & Evidence Links)
6. Agent B: Evidence & Safety Critic (Independent Critic, Audits Violations & Rejects Claims)
7. Gate 3: Jev Micro-Judge (Atomic Epistemic Probabilities: Unsupported, Over-triage, Under-triage)
8. Deterministic Arbitration Policy (ACCEPT_A, REPAIR_A, REGENERATE, SAFE_FALLBACK)
9. Final Synthesis Agent (Surgical Merging & Structuring of Approved Claims)
10. Clinical Output Guard (Independent Deterministic + Clinical Safety Release Gate)
11. Evidence & Citation Verifier (Authenticity & Grounding Audit)
12. Targeted Repair Engine (Max 1 surgical retry) with Safe Fallback protection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from time import perf_counter
from typing import Any

from app.models.evidence import ClinicalEvidencePacket
from app.models.intake import CompiledClinicalIntake
from app.models.safety import ClinicalOutputGuardResult, SafetyKernelResult
from app.models.synthesis import (
    ArbitrationDecision,
    CriticReport,
    FinalSynthesisResult,
    JevMicroJudgment,
    ReasoningDraft,
)
from app.models.response_policy import ClinicalResponseContext, ResponseContract
from app.models.verification import EvidenceVerificationResult
from app.services.arbitration_policy import ArbitrationPolicy
from app.services.clinical_intake_compiler import ClinicalIntakeCompiler
from app.services.clinical_output_guard import ClinicalOutputGuard
from app.services.clinical_reasoner_agent import ClinicalReasonerAgent
from app.services.complexity_router import ComplexityRouter, PipelineRoute
from app.services.evidence_critic_agent import EvidenceCriticAgent
from app.services.evidence_verifier import EvidenceVerifier
from app.services.final_synthesis_agent import FinalSynthesisAgent
from app.services.jev_context_planner import JevContextPlanner
from app.services.jev_micro_judge import JevMicroJudge
from app.services.multi_domain_retriever import MultiDomainRetriever
from app.services.response_policy_engine import ResponsePolicyEngine
from app.services.response_quality_check import ResponseQualityResult, ResponseQualityVerifier
from app.services.safe_fallback import SafeFallbackGenerator
from app.services.safety_kernel import SafetyKernel
from app.services.targeted_repair import TargetedRepairEngine

logger = logging.getLogger(__name__)


@dataclass
class Phase3PipelineResult:
    """Comprehensive trace and output of Phase 3 clinical pipeline."""
    final_synthesis: FinalSynthesisResult
    intake: CompiledClinicalIntake
    complexity_route: PipelineRoute
    safety_kernel: SafetyKernelResult
    evidence_packet: ClinicalEvidencePacket
    reasoner_draft: ReasoningDraft
    critic_report: CriticReport
    jev_judgment: JevMicroJudgment
    arbitration: ArbitrationDecision
    output_guard: ClinicalOutputGuardResult
    evidence_verification: EvidenceVerificationResult
    response_contract: ResponseContract | None = None
    quality_result: ResponseQualityResult | None = None
    repaired: bool = False
    pipeline_latency_ms: float = 0.0


class Phase3ClinicalPipeline:
    """Orchestrates Phase 3 Understand -> Reason -> Critique -> Judge -> Synthesize -> Verify."""

    @classmethod
    def execute(
        cls,
        query: str,
        patient_context: dict[str, Any] | None = None,
    ) -> Phase3PipelineResult:
        t0 = perf_counter()

        # Step 1: Clinical Intake Compiler (Dual Representation)
        intake = ClinicalIntakeCompiler.compile(query)

        # Step 2: Adaptive Complexity Router (C0 - C4)
        complexity_route = ComplexityRouter.route(intake)

        # Step 3: Safety Kernel (Independent & Deterministic)
        safety_kernel = SafetyKernel.evaluate(intake, patient_context)

        # Step 3.5: Response Policy Engine (How should we respond?)
        response_contract = ResponsePolicyEngine.evaluate(
            query=query,
            safety_kernel=safety_kernel,
            complexity_level=complexity_route.level,
            user_intent="triage",
        )

        # Step 4: Multi-Domain Evidence Retrieval (Typed Packet)
        evidence_packet = MultiDomainRetriever.retrieve_typed_packet(intake)

        # Step 4.5: Jev Context Planner (What context / depth / tone is useful?)
        context_plan = JevContextPlanner.plan(
            contract=response_contract,
            intake=intake,
            safety_kernel=safety_kernel,
            evidence_packet=evidence_packet,
        )

        # Step 5: Agent A - Clinical Reasoner
        reasoner_draft = ClinicalReasonerAgent.generate_draft(
            intake=intake,
            evidence_packet=evidence_packet,
            safety_kernel=safety_kernel,
            patient_context=patient_context,
        )

        # Step 6: Agent B - Evidence & Safety Critic
        critic_report = EvidenceCriticAgent.audit_draft(
            intake=intake,
            evidence_packet=evidence_packet,
            safety_kernel=safety_kernel,
            draft=reasoner_draft,
        )

        # Step 7: Gate 3 - Jev Micro-Judge
        jev_judgment = JevMicroJudge.judge(
            intake=intake,
            evidence_packet=evidence_packet,
            safety_kernel=safety_kernel,
            draft=reasoner_draft,
            critic=critic_report,
        )

        # Step 8: Deterministic Arbitration Policy
        arbitration = ArbitrationPolicy.arbitrate(
            safety_kernel=safety_kernel,
            critic=critic_report,
            jev=jev_judgment,
            draft=reasoner_draft,
        )

        # Step 9: Final Synthesis Agent (Guided by ResponseContract & ContextPlan)
        synthesis = FinalSynthesisAgent.synthesize(
            intake=intake,
            evidence_packet=evidence_packet,
            safety_kernel=safety_kernel,
            draft=reasoner_draft,
            critic=critic_report,
            jev=jev_judgment,
            arbitration=arbitration,
            contract=response_contract,
            context_plan=context_plan,
        )

        # Step 10: Clinical Output Guard
        output_guard = ClinicalOutputGuard.evaluate_output(
            intake=intake,
            safety_kernel=safety_kernel,
            synthesis=synthesis,
        )

        # Step 11: Evidence & Citation Verifier
        evidence_verification = EvidenceVerifier.verify(
            evidence_packet=evidence_packet,
            synthesis=synthesis,
        )

        # Step 11.5: Response Quality Verifier (Clinical UX Audit)
        quality_result = ResponseQualityVerifier.evaluate(
            final_answer=synthesis.final_answer,
            contract=response_contract,
            sources=synthesis.sources,
        )

        # Step 12: Targeted Repair if needed (MAX_REPAIR = 1)
        repaired = False
        if not output_guard.safe or not evidence_verification.verified or not quality_result.passed:
            if output_guard.action == "SAFE_FALLBACK":
                synthesis = SafeFallbackGenerator.generate(
                    tier="SAFE_EMERGENCY" if safety_kernel.emergency_lock else "SAFE_GENERAL",
                    intake=intake,
                    safety_kernel=safety_kernel,
                    specialty_code=synthesis.specialty_code,
                    specialty_label=synthesis.specialty_label,
                    sources=synthesis.sources,
                )
            else:
                synthesis = TargetedRepairEngine.repair(
                    intake=intake,
                    safety_kernel=safety_kernel,
                    synthesis=synthesis,
                    guard_result=output_guard,
                    verifier_result=evidence_verification,
                )
                repaired = True

                # Re-check Guard once after repair
                re_guard = ClinicalOutputGuard.evaluate_output(
                    intake=intake,
                    safety_kernel=safety_kernel,
                    synthesis=synthesis,
                )
                if not re_guard.safe:
                    # If still fails second time, delegate to Safe Fallback
                    synthesis = SafeFallbackGenerator.generate(
                        tier="SAFE_EMERGENCY" if safety_kernel.emergency_lock else "SAFE_GENERAL",
                        intake=intake,
                        safety_kernel=safety_kernel,
                        specialty_code=synthesis.specialty_code,
                        specialty_label=synthesis.specialty_label,
                        sources=synthesis.sources,
                    )
                output_guard = re_guard

        elapsed_ms = (perf_counter() - t0) * 1000.0

        return Phase3PipelineResult(
            final_synthesis=synthesis,
            intake=intake,
            complexity_route=complexity_route,
            safety_kernel=safety_kernel,
            evidence_packet=evidence_packet,
            reasoner_draft=reasoner_draft,
            critic_report=critic_report,
            jev_judgment=jev_judgment,
            arbitration=arbitration,
            output_guard=output_guard,
            evidence_verification=evidence_verification,
            response_contract=response_contract,
            quality_result=quality_result,
            repaired=repaired,
            pipeline_latency_ms=round(elapsed_ms, 2),
        )

