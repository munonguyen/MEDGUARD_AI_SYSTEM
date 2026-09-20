"""Failure Taxonomy and 6-Layer Diagnostic Engine for MedGuard Blind Benchmark V5.

Implements:
1. 18 Standard Failure Codes (F1 - F18).
2. 6-Layer Diagnostic Analysis (Language -> Facts -> Negation/Time -> Clinical -> Resolver -> Response).
3. Root Cause Classification: Implementation Bug vs Knowledge Gap vs Benchmark Overfitting.
4. Prevention Recommendations: 'do_not_fix_with' and 'recommended_fix_class'.
5. Failure Clustering by systemic symptom rather than individual case.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import json
from typing import Any


class FailureCode(str, Enum):
    F1_LANGUAGE_UNDERSTANDING = "F1_LANGUAGE_UNDERSTANDING"
    F2_FACT_EXTRACTION = "F2_FACT_EXTRACTION"
    F3_NEGATION_UNCERTAINTY = "F3_NEGATION_UNCERTAINTY"
    F4_TEMPORAL_REASONING = "F4_TEMPORAL_REASONING"
    F5_CLINICAL_SEMANTIC_REASONING = "F5_CLINICAL_SEMANTIC_REASONING"
    F6_RULE_MATCHING = "F6_RULE_MATCHING"
    F7_DOSE_REASONING = "F7_DOSE_REASONING"
    F8_CONVERSATION_STATE = "F8_CONVERSATION_STATE"
    F9_CORRECTION_INVALIDATION = "F9_CORRECTION_INVALIDATION"
    F10_RISK_AGGREGATION = "F10_RISK_AGGREGATION"
    F11_RESOLVER = "F11_RESOLVER"
    F12_RESPONSE_POLICY = "F12_RESPONSE_POLICY"
    F13_HALLUCINATED_DIAGNOSIS = "F13_HALLUCINATED_DIAGNOSIS"
    F14_UNSAFE_MEDICATION_TREATMENT = "F14_UNSAFE_MEDICATION_TREATMENT"
    F15_OVER_TRIAGE = "F15_OVER_TRIAGE"
    F16_UNDER_TRIAGE = "F16_UNDER_TRIAGE"
    F17_SYSTEM_RUNTIME_FAILURE = "F17_SYSTEM_RUNTIME_FAILURE"
    F18_ORACLE_AMBIGUITY = "F18_ORACLE_AMBIGUITY"


class FailureNature(str, Enum):
    BUG = "BUG"                          # Engine knows concept, pipeline dropped it
    KNOWLEDGE_GAP = "KNOWLEDGE_GAP"      # Facts extracted, but syndromic combination unrepresented
    BENCHMARK_OVERFIT = "BENCHMARK_OVERFIT" # Brittleness / regex-dependent failure
    UNSAFE_POLICY = "UNSAFE_POLICY"      # Dangerous clinical advice generated
    SYSTEM_CRASH = "SYSTEM_CRASH"        # Unhandled runtime exception


@dataclass
class FailureReport:
    case_id: str
    oracle: str
    actual: str
    severity: str  # CRITICAL, HIGH, MODERATE, LOW
    primary_failure: FailureCode
    secondary_failures: list[FailureCode] = field(default_factory=list)
    failure_nature: FailureNature = FailureNature.KNOWLEDGE_GAP
    evidence: dict[str, Any] = field(default_factory=dict)
    why_failed: str = ""
    do_not_fix_with: list[str] = field(default_factory=list)
    recommended_fix_class: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["primary_failure"] = self.primary_failure.value
        d["secondary_failures"] = [f.value for f in self.secondary_failures]
        d["failure_nature"] = self.failure_nature.value
        return d


def diagnose_case_failure(
    case_record: dict[str, Any],
    oracle_entry: dict[str, Any],
) -> FailureReport | None:
    """Execute 6-layer diagnostic inspection to pinpoint the primary failure root-cause."""
    cid = case_record.get("case_id", "UNKNOWN")
    expected_oracle = oracle_entry.get("oracle_triage", "ROUTINE")
    acceptable = oracle_entry.get("acceptable_triage", [expected_oracle])
    
    resolver = case_record.get("resolver", {})
    actual_triage = resolver.get("final_triage", "ROUTINE")
    
    response_layer = case_record.get("response_layer", {})
    runtime = case_record.get("runtime", {})
    exception_str = runtime.get("exception")
    
    # 0. Check System / Runtime crash
    if exception_str or actual_triage == "SYSTEM_ERROR":
        return FailureReport(
            case_id=cid,
            oracle=expected_oracle,
            actual=actual_triage,
            severity="CRITICAL",
            primary_failure=FailureCode.F17_SYSTEM_RUNTIME_FAILURE,
            failure_nature=FailureNature.SYSTEM_CRASH,
            evidence={"exception": exception_str},
            why_failed="Unhandled exception crashed the inference pipeline.",
            do_not_fix_with=["suppressing exception with bare try/except"],
            recommended_fix_class=["graceful fallback", "null-safety audit"],
        )

    # Check Response Policy Hard Failures first (Layer 6)
    is_pure_t4 = "T4" in expected_oracle or expected_oracle == "EMERGENCY"
    contains_home_mon = response_layer.get("contains_home_monitoring", False)
    contains_unsupported_tx = response_layer.get("contains_unsupported_treatment", False)
    contains_unsupported_dx = response_layer.get("contains_unsupported_diagnosis", False)
    
    if is_pure_t4 and contains_home_mon:
        return FailureReport(
            case_id=cid,
            oracle=expected_oracle,
            actual=actual_triage,
            severity="CRITICAL",
            primary_failure=FailureCode.F12_RESPONSE_POLICY,
            secondary_failures=[FailureCode.F14_UNSAFE_MEDICATION_TREATMENT] if contains_unsupported_tx else [],
            failure_nature=FailureNature.UNSAFE_POLICY,
            evidence={
                "response_text": response_layer.get("response_text", "")[:200],
                "contains_home_monitoring": True,
            },
            why_failed="Emergency T4 case response advised home monitoring or waiting.",
            do_not_fix_with=["regex blacklisting single phrases"],
            recommended_fix_class=["triage-to-response policy guard", "hard response assertion"],
        )

    if contains_unsupported_tx:
        return FailureReport(
            case_id=cid,
            oracle=expected_oracle,
            actual=actual_triage,
            severity="CRITICAL",
            primary_failure=FailureCode.F14_UNSAFE_MEDICATION_TREATMENT,
            failure_nature=FailureNature.UNSAFE_POLICY,
            evidence={"response_text": response_layer.get("response_text", "")[:200]},
            why_failed="Response prescribed invasive or dangerous treatment without clinical mandate.",
            do_not_fix_with=["soft prompting"],
            recommended_fix_class=["triage/treatment separation enforcement", "prohibited action validator"],
        )

    # Check if triage is acceptable
    triage_match = (actual_triage == expected_oracle) or (actual_triage in acceptable)
    if triage_match and not contains_unsupported_dx:
        return None  # No failure

    # Determine Severity of triage failure
    if is_pure_t4 and actual_triage == "ROUTINE":
        severity = "CRITICAL"
    elif is_pure_t4 and actual_triage == "URGENT":
        severity = "HIGH"
    elif expected_oracle in ("ROUTINE", "T0", "T1") and actual_triage == "EMERGENCY":
        severity = "MODERATE"  # Over-triage
    else:
        severity = "MODERATE"

    # Step through 6 Diagnostic Layers
    lang_layer = case_record.get("language_layer", {})
    norm_text = lang_layer.get("normalized_text", "")
    mapped_concepts = lang_layer.get("mapped_concepts", [])
    
    fact_layer = case_record.get("fact_extraction", {})
    affirmed = fact_layer.get("affirmed_facts", [])
    negated = fact_layer.get("negated_facts", [])
    temporal = fact_layer.get("temporal_facts", [])
    
    rule_layer = case_record.get("rule_layer", {})
    sem_layer = case_record.get("semantic_layer", {})
    dose_layer = case_record.get("dose_layer", {})
    conv_layer = case_record.get("conversation_layer", {})
    
    raw_msgs = case_record.get("input", {}).get("raw_messages", [])
    raw_user_str = " ".join(m.get("content", "") for m in raw_msgs if m.get("role") == "user").lower()

    # Layer 1: Language Understanding
    # Token loss or corrupted normalization
    if ("méo miệng" in raw_user_str or "meo mieng" in raw_user_str) and not any("stroke" in c or "facial" in c or "meo" in c for c in mapped_concepts):
        return FailureReport(
            case_id=cid,
            oracle=expected_oracle,
            actual=actual_triage,
            severity=severity,
            primary_failure=FailureCode.F1_LANGUAGE_UNDERSTANDING,
            failure_nature=FailureNature.BUG,
            evidence={"raw_input": raw_user_str, "normalized_text": norm_text, "mapped_concepts": mapped_concepts},
            why_failed="Normalization or dialect mapping dropped critical tokens from raw input.",
            do_not_fix_with=["adding exact sentence regex", "case-specific alias"],
            recommended_fix_class=["subword tokenizer robustification", "dialect semantic normalizer"],
        )

    # Layer 2: Fact Extraction
    if "không nhấc được" in raw_user_str and "motor_weakness" not in affirmed and not any("weakness" in f for f in affirmed):
        return FailureReport(
            case_id=cid,
            oracle=expected_oracle,
            actual=actual_triage,
            severity=severity,
            primary_failure=FailureCode.F2_FACT_EXTRACTION,
            failure_nature=FailureNature.BUG,
            evidence={"raw_input": raw_user_str, "affirmed_facts": affirmed},
            why_failed="Clinical symptom present in text but clinical fact extractor failed to bind fact entity.",
            do_not_fix_with=["regex token scan"],
            recommended_fix_class=["clinical fact extraction parser", "entity-relation span model"],
        )

    # Layer 3: Negation & Temporality
    if ("lúc nãy" in raw_user_str or "hôm qua" in raw_user_str or "vừa mới" in raw_user_str) and ("không còn" in raw_user_str or "hết đau" in raw_user_str):
        if actual_triage == "ROUTINE" and is_pure_t4:
            return FailureReport(
                case_id=cid,
                oracle=expected_oracle,
                actual=actual_triage,
                severity="CRITICAL",
                primary_failure=FailureCode.F4_TEMPORAL_REASONING,
                secondary_failures=[FailureCode.F3_NEGATION_UNCERTAINTY],
                failure_nature=FailureNature.BUG,
                evidence={"raw_input": raw_user_str, "temporal_facts": temporal, "negated_facts": negated},
                why_failed="Current absence of symptom erased a dangerous prior peak event (transient ischemia / crescendo angina).",
                do_not_fix_with=["adding hardcoded case string"],
                recommended_fix_class=["temporal episode tracker", "peak danger memory invariant"],
            )

    # Layer 7: Dose Reasoning
    if dose_layer.get("activated", False) or any(k in raw_user_str for k in ("paracetamol", "panadol", "uống", "viên", "liều")):
        if dose_layer.get("urgency") != expected_oracle and is_pure_t4:
            return FailureReport(
                case_id=cid,
                oracle=expected_oracle,
                actual=actual_triage,
                severity=severity,
                primary_failure=FailureCode.F7_DOSE_REASONING,
                failure_nature=FailureNature.BUG,
                evidence={"dose_layer": dose_layer},
                why_failed="Medication dose reasoning failed to escalate toxic ingestion or threshold.",
                do_not_fix_with=["hardcoding tablet count"],
                recommended_fix_class=["pharmacokinetic threshold model", "weight/time reasoning engine"],
            )

    # Layer 5: Risk Aggregation / Resolver Bug
    rule_urg = rule_layer.get("urgency", "UNRESOLVED")
    sem_urg = sem_layer.get("urgency", "ROUTINE")
    if rule_urg == "EMERGENCY" or sem_urg == "EMERGENCY":
        if actual_triage == "ROUTINE":
            return FailureReport(
                case_id=cid,
                oracle=expected_oracle,
                actual=actual_triage,
                severity="CRITICAL",
                primary_failure=FailureCode.F11_RESOLVER,
                secondary_failures=[FailureCode.F10_RISK_AGGREGATION],
                failure_nature=FailureNature.BUG,
                evidence={"rule_urgency": rule_urg, "semantic_urgency": sem_urg, "final_triage": actual_triage},
                why_failed="Upstream engine detected EMERGENCY, but downstream resolver downgraded to ROUTINE.",
                do_not_fix_with=["per-case resolver exception"],
                recommended_fix_class=["resolver monotonicity invariant", "MAX(rule, semantic) safety contract"],
            )

    # Layer 4: Clinical Semantic Reasoning (Knowledge Gap vs Concept Reasoning)
    if is_pure_t4 and actual_triage in ("ROUTINE", "URGENT"):
        return FailureReport(
            case_id=cid,
            oracle=expected_oracle,
            actual=actual_triage,
            severity=severity,
            primary_failure=FailureCode.F5_CLINICAL_SEMANTIC_REASONING,
            secondary_failures=[FailureCode.F16_UNDER_TRIAGE],
            failure_nature=FailureNature.KNOWLEDGE_GAP,
            evidence={
                "mapped_concepts": mapped_concepts,
                "affirmed_facts": affirmed,
                "semantic_risk": sem_urg,
                "rule_matched": rule_layer.get("matched", False),
            },
            why_failed="Facts were extracted but semantic risk reasoner did not recognize the clinical syndrome combination.",
            do_not_fix_with=["adding exact sentence regex", "adding case-specific keyword"],
            recommended_fix_class=["syndrome abstraction", "concept-level reasoning", "semantic risk composition"],
        )

    # Over-Triage case
    if expected_oracle in ("ROUTINE", "T0", "T1") and actual_triage == "EMERGENCY":
        return FailureReport(
            case_id=cid,
            oracle=expected_oracle,
            actual=actual_triage,
            severity="MODERATE",
            primary_failure=FailureCode.F15_OVER_TRIAGE,
            secondary_failures=[FailureCode.F5_CLINICAL_SEMANTIC_REASONING],
            failure_nature=FailureNature.BENCHMARK_OVERFIT,
            evidence={"actual_triage": actual_triage, "expected": expected_oracle},
            why_failed="Benign complaint or self-limiting condition was excessively escalated to EMERGENCY.",
            do_not_fix_with=["loosening emergency rules globally"],
            recommended_fix_class=["benign condition calibration", "counter-evidence check"],
        )

    # Default fallback failure
    return FailureReport(
        case_id=cid,
        oracle=expected_oracle,
        actual=actual_triage,
        severity=severity,
        primary_failure=FailureCode.F16_UNDER_TRIAGE if is_pure_t4 else FailureCode.F15_OVER_TRIAGE,
        failure_nature=FailureNature.KNOWLEDGE_GAP,
        evidence={"actual": actual_triage, "expected": expected_oracle},
        why_failed=f"Triage mismatch: expected {expected_oracle}, actual {actual_triage}.",
        do_not_fix_with=["case-specific regex"],
        recommended_fix_class=["general syndromic ontology update"],
    )


def cluster_failures(reports: list[FailureReport]) -> dict[str, list[dict[str, Any]]]:
    """Group failures into systemic clusters rather than addressing isolated cases."""
    clusters: dict[str, list[dict[str, Any]]] = {}
    for r in reports:
        key = r.primary_failure.value
        if key not in clusters:
            clusters[key] = []
        clusters[key].append(r.to_dict())
    return clusters
