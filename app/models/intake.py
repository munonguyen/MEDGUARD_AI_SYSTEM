"""Typed Data Contracts for Clinical Intake Compiler & Dual Representation.

Implements the 2025-2026 state-of-the-art Clinical Query Understanding specifications:
- Preserves raw query alongside normalized and machine representations.
- Dual Representation: Semantic Form (what user means, anxiety, concerns) vs Clinical Form (medical facts).
- Explicit Negation Detection and Timeline Extraction.
- Distinction between Patient Hypotheses (fears/internet searches) and Confirmed Diagnoses.
- 5-Level Complexity Classification (C0-C4) and Question Decomposition.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

ComplexityLevel = Literal["C0", "C1", "C2", "C3", "C4"]
UncertaintyType = Literal["linguistic", "missing_information", "clinical", "retrieval"]


class TimelineEvent(BaseModel):
    """Structured temporal event extracted from conversational text."""
    time_offset: str = Field(description="Normalized relative time offset, e.g., -2d, -1d, today_morning, acute")
    raw_time_marker: str = Field(description="Original colloquial time phrase, e.g., 'hôm kia', 'mấy hôm trước', 'sáng nay'")
    event: str = Field(description="Normalized event description, e.g., 'Chạy bộ cường độ cao', 'Căng bắp chân'")
    context: str = Field(default="", description="Surrounding contextual details")


class PatientHypothesis(BaseModel):
    """User-stated suspicion, fear, or self-diagnosis from internet/reading.
    
    CRITICAL INVARIANT: Stated concerns (e.g. 'cục máu đông', 'ung thư') must NEVER
    be flattened into confirmed clinical diagnoses.
    """
    stated_concern: str = Field(description="The user's stated concern, e.g., 'cục máu đông', 'DVT'")
    is_clinical_diagnosis: bool = Field(default=False, description="Always False for self-stated fears")
    source: Literal["user_fear", "internet_search", "family_suggestion", "previous_diagnosis"] = Field(
        default="internet_search"
    )
    repetition_count: int = Field(default=1, description="Number of times repeated in message (anxiety indicator, NOT severity)")


class MedicationMention(BaseModel):
    """Extracted medication with confidence and generic mapping."""
    raw_mention: str = Field(description="Raw text, e.g., 'cetri gì đó', 'thuốc dị ứng'")
    candidate_active_ingredient: str | None = Field(default=None, description="Resolved generic, e.g., 'cetirizine'")
    therapeutic_class: str | None = Field(default=None, description="Class, e.g., 'antihistamine_h1'")
    certainty: Literal["CERTAIN", "PROBABLE", "UNKNOWN"] = Field(default="PROBABLE")


class NegationFinding(BaseModel):
    """Explicitly denied symptom, history, or functional impairment.
    
    Prevents negation flattening (e.g. 'không đau ngực' becoming 'chest_pain' keyword).
    """
    concept: str = Field(description="Normalized medical concept, e.g., 'chest_pain', 'redness', 'impaired_walking'")
    raw_span: str = Field(description="Original denied phrase, e.g., 'không đỏ', 'ko đỏ hay j cả', 'đi vẫn được'")
    negation_type: Literal["denied_symptom", "denied_history", "preserved_function"] = Field(default="denied_symptom")


class SemanticForm(BaseModel):
    """Semantic representation: What the user means, fears, and needs emotionally."""
    primary_intent: str = Field(description="Primary user goal, e.g., 'risk_assessment', 'medication_safety', 'self_care'")
    secondary_intents: list[str] = Field(default_factory=list, description="Secondary intents, e.g., ['possible_cause', 'when_to_seek_care']")
    patient_concerns: list[PatientHypothesis] = Field(default_factory=list, description="Fears/self-hypotheses")
    emotional_tone: Literal["anxious", "panicked", "calm", "seeking_clarity"] = Field(default="anxious")
    conversational_preambles: list[str] = Field(default_factory=list, description="Polite phrases, e.g., 'bác ơi', 'em cũng ko rõ'")


class ClinicalForm(BaseModel):
    """Clinical representation: Medical facts for downstream clinical reasoning gates."""
    positive_findings: list[str] = Field(default_factory=list, description="Confirmed symptoms and signs, e.g., ['left_calf_tightness']")
    negative_findings: list[NegationFinding] = Field(default_factory=list, description="Explicitly absent symptoms/signs")
    anatomical_sites: list[str] = Field(default_factory=list, description="Body sites involved, e.g., ['left_calf', 'below_knee']")
    functional_status: str = Field(default="ambulatory_preserved", description="Mobility/functional integrity, e.g., 'walking_preserved'")
    timeline: list[TimelineEvent] = Field(default_factory=list, description="Chronological event sequence")
    medications: list[MedicationMention] = Field(default_factory=list, description="Active medications reported")
    patient_age: int | None = Field(default=None, description="Patient age if stated")
    chronic_history: list[str] = Field(default_factory=list, description="Underlying chronic conditions")
    unknowns: list[str] = Field(default_factory=list, description="Clinical facts that remain missing")


class DecomposedQuestion(BaseModel):
    """Sub-question decomposed from multi-faceted, messy queries for targeted retrieval."""
    sub_question_id: str = Field(description="Sub-question ID, e.g., 'SQ1', 'SQ2'")
    focus_domain: Literal["symptom_risk", "drug_interaction", "red_flags", "self_care", "emergency_check"] = Field(
        description="Domain targeted by this sub-question"
    )
    question_text: str = Field(description="Natural question text for the doctor/agent")
    retrieval_query: str = Field(description="Dense, clean query optimized for domain RAG without user noise")


class CompiledClinicalIntake(BaseModel):
    """Full output of the Clinical Intake Compiler.
    
    Serves as the Single Source of Truth after Input Guard, consumed by
    Complexity Router, Multi-Retriever, Tri-Gate, and Dual-Agent.
    """
    raw_query: str = Field(description="Original untouched raw user message")
    normalized_query: str = Field(description="Normalized Vietnamese query (typos/slang corrected)")
    semantic_form: SemanticForm = Field(description="User goals, anxieties, and communication intent")
    clinical_form: ClinicalForm = Field(description="Objective medical facts, timeline, and negations")
    complexity_level: ComplexityLevel = Field(description="Routing complexity C0-C4")
    complexity_rationale: str = Field(description="Justification for chosen complexity level")
    decomposed_questions: list[DecomposedQuestion] = Field(default_factory=list, description="Parallel sub-queries")
    uncertainty_types: list[UncertaintyType] = Field(default_factory=list, description="Classified uncertainty categories")
    high_value_missing_fields: list[str] = Field(
        default_factory=list,
        description="Missing clinical parameters that have high information gain to alter triage"
    )

    @property
    def symptom_features(self) -> list[str]:
        return self.clinical_form.positive_findings

    @property
    def red_flag_mentions(self) -> list[str]:
        return [f for f in self.clinical_form.positive_findings if "red_flag" in f or "emergency" in f]

    @property
    def patient_concerns(self) -> list[PatientHypothesis]:
        return self.semantic_form.patient_concerns

    @property
    def timeline(self) -> list[TimelineEvent]:
        return self.clinical_form.timeline

    @property
    def negated_findings(self) -> list[NegationFinding]:
        return self.clinical_form.negative_findings

