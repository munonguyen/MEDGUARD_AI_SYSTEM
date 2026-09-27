"""Typed Data Contracts for Dual-Agent Reasoning, Critique, Jev Micro-Judge & Final Synthesis.

Phase 3 Core Architecture:
- Agent A: Clinical Reasoner (Produces structured draft with claims & evidence IDs).
- Agent B: Independent Evidence & Safety Critic (Audits draft A against facts, evidence, and safety constraints).
- Jev: Micro-Judge (Evaluates atomic claim validity, over-triage probability, and intent alignment).
- Arbitration: Deterministic Decision Engine (Decides ACCEPT_A, REPAIR_A, REGENERATE, SAFE_FALLBACK).
- Final Synthesis: Merges approved claims and verified evidence into the polished patient response.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class Claim(BaseModel):
    """Atomic medical claim produced by the reasoner or final synthesis."""
    claim_id: str = Field(description="Unique claim ID, e.g. 'C1', 'C2'")
    text: str = Field(description="Medical assertion made in the response")
    evidence_ids: list[str] = Field(default_factory=list, description="IDs of evidence chunks supporting this claim, e.g. ['E1', 'E3']")
    approved: bool = Field(default=True, description="Approval flag from the Critic and Evidence Verifier")
    rejected_reason: str | None = Field(default=None, description="Reason if claim was rejected by Critic")


class ReasoningDraft(BaseModel):
    """Structured clinical draft produced by Agent A (Clinical Reasoner)."""
    draft_id: str = Field(description="Draft ID")
    urgency: Literal["ROUTINE", "URGENT", "EMERGENCY"] = Field(description="Clinical urgency assessed by Reasoner")
    specialty_code: str = Field(description="Medical specialty code, e.g. 'ORTHOPEDICS', 'ENT', 'CARDIOLOGY'")
    specialty_label: str = Field(description="Human readable specialty label in Vietnamese")
    clinical_interpretation: str = Field(description="Differential reasoning and symptom explanation")
    likely_explanations: list[str] = Field(default_factory=list, description="Differential causes ranked by likelihood")
    self_care: list[str] = Field(default_factory=list, description="Safe actionable home self-care steps")
    red_flags: list[str] = Field(default_factory=list, description="Warning signs requiring immediate medical escalation")
    follow_up_questions: list[str] = Field(default_factory=list, description="Clarifying questions to gather missing clinical facts")
    claims: list[Claim] = Field(default_factory=list, description="Atomic claims with evidence ID linkage")
    draft_answer: str = Field(description="Complete draft advisory text")
    sources: list[dict[str, Any]] = Field(default_factory=list, description="Cited sources attached to draft")


class CriticViolation(BaseModel):
    """Clinical or safety violation flagged by Agent B (Critic)."""
    code: Literal[
        "UNSUPPORTED_DIAGNOSIS",
        "RED_FLAG_OMISSION",
        "OVER_TRIAGE",
        "UNDER_TRIAGE",
        "DRUG_CONTRAINDICATION",
        "DRUG_INTERACTION_OMISSION",
        "INCORRECT_SELF_CARE",
        "UNSAFE_SELF_CARE",
        "PATIENT_FACT_CONTRADICTION",
        "CONTRADICTS_PATIENT_FACTS",
        "CITATION_MISMATCH",
        "CLAIM_EVIDENCE_MISMATCH",
        "MISSING_UNCERTAINTY_LANGUAGE",
    ]
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = Field(default="MEDIUM")
    span: str = Field(description="Problematic phrase or section from Draft A")
    reason: str = Field(description="Detailed clinical reason why this is a violation")
    supporting_evidence_ids: list[str] = Field(default_factory=list, description="Evidence chunks backing the violation")


class ClaimLedgerEntry(BaseModel):
    """Audited entry for a single atomic medical claim in the pipeline ledger."""
    claim_id: str = Field(description="Unique claim ID, e.g. 'C1'")
    claim_text: str = Field(description="Medical claim statement")
    status: Literal["PENDING", "APPROVED", "REJECTED", "REPAIRED"] = Field(default="PENDING")
    evidence_ids: list[str] = Field(default_factory=list)
    critic_verdict: str = Field(default="PASS")
    evidence_relation: Literal["SUPPORTS", "PARTIALLY_SUPPORTS", "CONTRADICTS", "NOT_RELEVANT"] = Field(default="SUPPORTS")
    used_in_final: bool = Field(default=False)
    audit_notes: str = ""


class ClaimLedger(BaseModel):
    """Centralized Claim Ledger tracking atomic claims between Reasoner, Critic, and Final Synthesis."""
    ledger_id: str
    claims: dict[str, ClaimLedgerEntry] = Field(default_factory=dict)

    def record_draft_claims(self, claims: list[Claim]) -> None:
        for c in claims:
            self.claims[c.claim_id] = ClaimLedgerEntry(
                claim_id=c.claim_id,
                claim_text=c.text,
                status="PENDING",
                evidence_ids=list(c.evidence_ids),
            )

    def apply_critic_verdict(self, approved_ids: list[str], rejected_ids: list[str], violations: list[CriticViolation]) -> None:
        violation_map = {v.span: v.reason for v in violations}
        for cid, entry in self.claims.items():
            if cid in rejected_ids:
                entry.status = "REJECTED"
                entry.critic_verdict = "FAIL"
                entry.audit_notes = violation_map.get(entry.claim_text, "Rejected by Critic")
            elif cid in approved_ids:
                entry.status = "APPROVED"
                entry.critic_verdict = "PASS"

    def mark_used(self, used_claim_ids: list[str]) -> None:
        for cid in used_claim_ids:
            if cid in self.claims:
                self.claims[cid].used_in_final = True


class CriticMissingPoint(BaseModel):
    """Clinical element omitted in Draft A that must be present for safety."""
    type: Literal["red_flag", "self_care", "clarification", "drug_caution", "emergency_transit"]
    concept: str = Field(description="Missing medical concept or warning")
    mandatory: bool = Field(default=True)
    remedy_instruction: str = Field(description="Instruction on how to add this missing point")


class CriticReport(BaseModel):
    """Independent audit report from Agent B (Evidence & Safety Critic)."""
    critic_pass: bool = Field(description="True if Draft A has zero HIGH or CRITICAL violations")
    violations: list[CriticViolation] = Field(default_factory=list)
    missing_points: list[CriticMissingPoint] = Field(default_factory=list)
    approved_claims: list[str] = Field(default_factory=list, description="Claim IDs approved without objection")
    rejected_claims: list[str] = Field(default_factory=list, description="Claim IDs rejected due to violations")
    critique_summary: str = Field(default="", description="Summary narrative of critique findings")

    @property
    def has_high_severity_violation(self) -> bool:
        return any(v.severity in ("HIGH", "CRITICAL") for v in self.violations)


class JevMicroJudgment(BaseModel):
    """Atomic probability and quality judgment from Gate 3 (Jev Micro-Judge).
    
    Invariant Phase 3: Jev NEVER outputs global triage or home monitoring booleans.
    It purely scores atomic probabilities to anchor epistemic arbitration.
    """
    unsupported_claim_probability: float = Field(
        ge=0.0, le=1.0, description="Probability that draft contains unsupported/hallucinated medical claims"
    )
    overtriage_probability: float = Field(
        ge=0.0, le=1.0, description="Probability of unnecessary panic / false emergency escalation on benign case"
    )
    undertriage_probability: float = Field(
        ge=0.0, le=1.0, description="Probability that a true emergency/red flag is downplayed"
    )
    context_alignment_score: float = Field(
        ge=0.0, le=1.0, description="How well response addresses patient's actual concern without inventing gym/exercise"
    )
    redflag_coverage_score: float = Field(
        ge=0.0, le=1.0, description="Degree of necessary warning signs and red flags covered"
    )
    evidence_grounding_score: float = Field(
        ge=0.0, le=1.0, description="Degree of claim substantiate by verified guidelines"
    )
    advisory_notes: list[str] = Field(default_factory=list)


class ArbitrationDecision(BaseModel):
    """Deterministic arbitration policy resolving Agent A, Critic Agent B, and Jev Micro-Judge."""
    action: Literal["ACCEPT_A", "REPAIR_A", "REGENERATE", "SAFE_FALLBACK"]
    reasons: list[str] = Field(default_factory=list)
    claims_to_repair: list[str] = Field(default_factory=list)
    mandatory_emergency: bool = Field(default=False)
    fallback_policy: str | None = Field(default=None)


class FinalSynthesisResult(BaseModel):
    """Final, verified response produced by the Final Synthesis Agent."""
    final_answer: str = Field(description="Polished, empathetic, structured patient response")
    title: str = Field(description="Headline reflecting accurate clinical assessment")
    summary: str = Field(description="1-2 sentence executive clinical summary")
    claims_used: list[str] = Field(default_factory=list, description="Claim IDs included in final answer")
    evidence_used: list[str] = Field(default_factory=list, description="Evidence IDs cited in final answer")
    safety_constraints_preserved: bool = Field(default=True)
    urgency: Literal["ROUTINE", "URGENT", "EMERGENCY"]
    specialty_code: str
    specialty_label: str
    narrative_blocks: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    clarifying_questions: list[str] = Field(default_factory=list)
    self_care: list[str] = Field(default_factory=list)

    @property
    def reply(self) -> str:
        return self.final_answer

