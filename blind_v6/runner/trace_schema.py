"""Trace Schema for MedGuard AI Blind Benchmark V6.

Defines the multi-layer diagnostic capture structure logged during sealed inference,
including the 12-dimension Clinical Threat Graph, Clinical Event Ledger, and Compositional Reasoner.
Zero Oracle fields are present in this schema to prevent any leakage.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Any


@dataclass
class InputTrace:
    raw_messages: list[dict[str, str]] = field(default_factory=list)


@dataclass
class LanguageLayerTrace:
    normalized_text: str = ""
    mapped_concepts: list[str] = field(default_factory=list)
    language_flags: list[str] = field(default_factory=list)


@dataclass
class FactExtractionTrace:
    affirmed_facts: list[str] = field(default_factory=list)
    negated_facts: list[str] = field(default_factory=list)
    uncertain_facts: list[str] = field(default_factory=list)
    historical_facts: list[str] = field(default_factory=list)
    corrected_facts: list[str] = field(default_factory=list)
    temporal_facts: list[str] = field(default_factory=list)


@dataclass
class ThreatGraphTrace:
    active_dimensions: list[str] = field(default_factory=list)
    critical_dimensions: list[str] = field(default_factory=list)
    high_dimensions: list[str] = field(default_factory=list)
    threat_urgency: str = "ROUTINE"
    threat_confidence: float = 0.90


@dataclass
class RuleLayerTrace:
    matched: bool = False
    rule_ids: list[str] = field(default_factory=list)
    urgency: str = "UNRESOLVED"
    confidence: float = 0.0


@dataclass
class SemanticLayerTrace:
    risk_concepts: list[str] = field(default_factory=list)
    urgency: str = "ROUTINE"
    confidence: float = 0.946


@dataclass
class ConversationLayerTrace:
    prior_peak_risk: str | None = None
    new_danger: bool = False
    correction: bool = False
    risk: str | None = None
    confidence: float | None = None


@dataclass
class DoseLayerTrace:
    activated: bool = False
    drug: str | None = None
    total_dose_mg: float | None = None
    dose_mg_per_kg: float | None = None
    time_pattern: str | None = None
    urgency: str | None = None


@dataclass
class ResolverTrace:
    candidate_levels: dict[str, Any] = field(default_factory=dict)
    final_triage: str = "ROUTINE"
    decision_source: str = "hybrid"
    confidence: float = 0.95


@dataclass
class ResponseLayerTrace:
    response_text: str = ""
    contains_home_monitoring: bool = False
    contains_immediate_action: bool = False
    contains_unsupported_diagnosis: bool = False
    contains_unsupported_treatment: bool = False


@dataclass
class RuntimeTrace:
    latency_ms: int = 0
    exception: str | None = None


@dataclass
class CasePredictionRecord:
    case_id: str
    input: InputTrace = field(default_factory=InputTrace)
    language_layer: LanguageLayerTrace = field(default_factory=LanguageLayerTrace)
    fact_extraction: FactExtractionTrace = field(default_factory=FactExtractionTrace)
    threat_graph: ThreatGraphTrace = field(default_factory=ThreatGraphTrace)
    rule_layer: RuleLayerTrace = field(default_factory=RuleLayerTrace)
    semantic_layer: SemanticLayerTrace = field(default_factory=SemanticLayerTrace)
    conversation_layer: ConversationLayerTrace = field(default_factory=ConversationLayerTrace)
    dose_layer: DoseLayerTrace = field(default_factory=DoseLayerTrace)
    resolver: ResolverTrace = field(default_factory=ResolverTrace)
    response_layer: ResponseLayerTrace = field(default_factory=ResponseLayerTrace)
    runtime: RuntimeTrace = field(default_factory=RuntimeTrace)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json_line(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)
