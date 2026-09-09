"""Deterministic clinical-safety rule engine backed by versioned knowledge files.

This module implements the core clinical-safety logic for MedGuard AI.
All decisions are deterministic and rule-based; no LLM is used for
risk/severity resolution.

Design invariants:
  - Severity-max: when multiple signals disagree, the more severe wins.
  - Fail-closed: unknown/missing data never silently becomes "safe".
  - basis field: every warning cites ``structured_table`` or ``knowledge_file``.
  - LLM boundary: an LLM may only *explain* an already-decided result.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.knowledge.loader import knowledge
from app.models.safety import SafetyRequest
from app.models.triage import VitalSigns
from app.services.clinical_text import contains_affirmed_phrase, normalize_search_text


# =====================================================================
# Triage Rules
# =====================================================================

@dataclass(frozen=True)
class TriageRuleResult:
    urgency: str
    emergency_flag: bool
    red_flags: list[str]
    esi_level: int | None
    recommended_specialty: tuple[str, str] | None
    clarifying_questions: list[str]
    advice: str


def _check_red_flag_patterns(text: str) -> list[dict]:
    """Match text against knowledge-backed red-flag patterns."""
    matched = []
    for pattern in knowledge.red_flag_patterns:
        for phrase in (*pattern.get("patterns_vi", []), *pattern.get("patterns_en", [])):
            if contains_affirmed_phrase(text, normalize_search_text(phrase)):
                matched.append(pattern)
                break
    return matched


def _check_vital_signs(vitals: VitalSigns | None) -> list[tuple[str, str, str, int]]:
    """Check vital signs against knowledge-backed thresholds.

    Returns list of (red_flag_text, urgency, detail, esi_level).
    """
    if not vitals:
        return []
    findings: list[tuple[str, str, str, int]] = []
    for threshold in knowledge.vital_sign_thresholds:
        metric = threshold["metric"]
        value = getattr(vitals, metric, None)
        if value is None:
            continue
        critical_above = threshold.get("critical_above")
        critical_below = threshold.get("critical_below")
        warning_above = threshold.get("warning_above")
        warning_below = threshold.get("warning_below")

        if critical_above is not None and value >= critical_above:
            findings.append((
                threshold["detail_critical"],
                threshold["critical_urgency"],
                threshold["detail_critical"],
                threshold["critical_esi"],
            ))
        elif critical_below is not None and value < critical_below:
            findings.append((
                threshold["detail_critical"],
                threshold["critical_urgency"],
                threshold["detail_critical"],
                threshold["critical_esi"],
            ))
        elif warning_above is not None and value >= warning_above:
            findings.append((
                threshold["detail_warning"],
                threshold["warning_urgency"],
                threshold["detail_warning"],
                threshold["warning_esi"],
            ))
        elif warning_below is not None and value < warning_below:
            findings.append((
                threshold["detail_warning"],
                threshold["warning_urgency"],
                threshold["detail_warning"],
                threshold["warning_esi"],
            ))
    return findings


def _route_specialty(text: str) -> tuple[str, str, float] | None:
    """Route to specialty based on keyword matching from knowledge base."""
    best: tuple[str, str, float] | None = None
    best_count = 0
    for route in knowledge.specialty_routing:
        matches = sum(
            1
            for keyword in route["keywords"]
            if contains_affirmed_phrase(text, normalize_search_text(keyword))
        )
        if matches > best_count:
            best_count = matches
            spec = route["specialty"]
            best = (spec["code"], spec["label"], route["confidence"])
    return best


def triage_rules(symptoms_text: str, vitals: VitalSigns | None = None) -> TriageRuleResult:
    text = normalize_search_text(symptoms_text)

    # Phase 1: Red-flag pattern matching from knowledge base
    matched_patterns = _check_red_flag_patterns(text)
    red_flags: list[str] = []
    emergency_specialty: tuple[str, str] | None = None
    emergency_esi: int | None = None

    for pattern in matched_patterns:
        for phrase in (*pattern.get("patterns_vi", []), *pattern.get("patterns_en", [])):
            normalized_phrase = normalize_search_text(phrase)
            if contains_affirmed_phrase(text, normalized_phrase) and phrase not in red_flags:
                red_flags.append(phrase)
        spec = pattern.get("specialty", {})
        if spec:
            candidate = (spec["code"], spec["label"])
            if emergency_specialty is None:
                emergency_specialty = candidate
                emergency_esi = pattern.get("esi_level")
            elif pattern.get("esi_level", 5) < (emergency_esi or 5):
                emergency_specialty = candidate
                emergency_esi = pattern.get("esi_level")

    # Phase 2: Vital signs from knowledge-backed thresholds
    vital_findings = _check_vital_signs(vitals)
    emergency_vital_findings = [finding for finding in vital_findings if finding[1] == "EMERGENCY"]
    red_flags.extend(finding[0] for finding in emergency_vital_findings)

    # Phase 3: Resolution — severity-max
    if matched_patterns or emergency_vital_findings:
        # Determine ESI: min of pattern ESI and vital ESI (most severe)
        best_esi = emergency_esi
        for _, _, _, v_esi in emergency_vital_findings:
            if best_esi is None or v_esi < best_esi:
                best_esi = v_esi

        # Choose specialty: pattern-based if available, else EMERGENCY
        specialty = emergency_specialty or ("EMERGENCY", "Cấp cứu")

        # Determine advice from the most severe matched pattern
        advice = "Cần liên hệ cấp cứu hoặc đến cơ sở y tế gần nhất ngay lập tức."
        for pattern in matched_patterns:
            if pattern.get("advice"):
                advice = pattern["advice"]
                break

        return TriageRuleResult(
            urgency="EMERGENCY",
            emergency_flag=True,
            red_flags=red_flags,
            esi_level=best_esi or 2,
            recommended_specialty=specialty,
            clarifying_questions=[],
            advice=advice,
        )

    # Phase 4: Vital-only urgent (no text red flags but abnormal vitals)
    if vital_findings:
        return TriageRuleResult(
            urgency="URGENT",
            emergency_flag=False,
            red_flags=["sinh hiệu cần được đánh giá sớm"],
            esi_level=3,
            recommended_specialty=("GENERAL", "Tổng quát"),
            clarifying_questions=[
                "Sinh hiệu bất thường bắt đầu từ khi nào?",
                "Có triệu chứng nặng lên hoặc dấu hiệu mới không?",
            ],
            advice="Nên được nhân viên y tế đánh giá sớm; nếu triệu chứng nặng lên, hãy đến cơ sở cấp cứu.",
        )

    # Phase 5: Urgent clinical patterns from knowledge base (ESI 3)
    for u_pat in knowledge.urgent_patterns:
        for phrase in u_pat.get("patterns_vi", []):
            if contains_affirmed_phrase(text, normalize_search_text(phrase)):
                routed = _route_specialty(text)
                specialty = (routed[0], routed[1]) if routed else ("GENERAL", "Nội tổng quát")
                return TriageRuleResult(
                    urgency="URGENT",
                    emergency_flag=False,
                    red_flags=[],
                    esi_level=3,
                    recommended_specialty=specialty,
                    clarifying_questions=[
                        "Triệu chứng bắt đầu từ bao giờ và mức độ tăng hay giảm?",
                        "Có kèm theo sốt cao hay nôn ói không?",
                    ],
                    advice="Nên được thăm khám lâm sàng sớm trong ngày để được chẩn đoán và điều trị kịp thời.",
                )

    # Phase 6: Administrative / Routine review patterns from knowledge base (ESI 5)
    for r_pat in knowledge.routine_administrative_patterns:
        for phrase in r_pat.get("patterns_vi", []):
            if contains_affirmed_phrase(text, normalize_search_text(phrase)):
                routed = _route_specialty(text)
                specialty = (routed[0], routed[1]) if routed else ("GENERAL", "Đa khoa")
                return TriageRuleResult(
                    urgency="ROUTINE",
                    emergency_flag=False,
                    red_flags=[],
                    esi_level=5,
                    recommended_specialty=specialty,
                    clarifying_questions=[
                        "Hiện tại có bất kỳ triệu chứng khó chịu hoặc bất thường nào mới xuất hiện không?",
                    ],
                    advice="Đặt lịch hẹn tái khám hoặc tư vấn định kỳ theo kế hoạch điều trị.",
                )

    # Phase 7: Mild / routine single resource with specialty routing (ESI 4)
    routed = _route_specialty(text)
    specialty = (routed[0], routed[1]) if routed else ("GENERAL", "Tổng quát")

    return TriageRuleResult(
        urgency="ROUTINE",
        emergency_flag=False,
        red_flags=[],
        esi_level=4,
        recommended_specialty=specialty,
        clarifying_questions=[
            "Triệu chứng xuất hiện từ khi nào?",
            "Có sốt hoặc đau tăng dần không?",
        ],
        advice="Nên đặt lịch khám chuyên khoa phù hợp và theo dõi diễn tiến.",
    )


# =====================================================================
# Safety Rules
# =====================================================================

@dataclass(frozen=True)
class SafetyCheckResult:
    overall_risk: str
    requires_human_review: bool
    warnings: list[dict]
    unknown_ingredients: list[str]


RISK_ORDER = ["LOW", "MODERATE", "HIGH"]


def _escalate_risk(current: str, candidate: str) -> str:
    """Return the more severe risk level."""
    if RISK_ORDER.index(candidate) > RISK_ORDER.index(current):
        return candidate
    return current


def _normalize_ingredient(name: str | None, active_ingredient: str | None) -> str:
    value = (active_ingredient or name or "").strip().lower()
    return value.replace(" ", "")


def _check_allergy_cross_reactivity(
    allergies: set[str],
    med_name: str,
    med_key: str,
) -> list[dict]:
    """Check if medication matches any allergy cross-reactivity group."""
    warnings: list[dict] = []
    for group in knowledge.allergy_groups:
        # Check if patient has the primary allergen
        primary = group["primary_allergen"].lower()
        if primary not in allergies:
            # Check if any alias of the primary allergen is in the patient's allergies
            continue

        # Check if the proposed medication is in the cross-reactive list
        cross_substances = [s.lower().replace(" ", "") for s in group.get("cross_reactive_substances", [])]
        partial_substances = [s.lower().replace(" ", "") for s in group.get("partial_cross_reactive", [])]

        if med_key in cross_substances or any(alias in med_key for alias in cross_substances):
            warnings.append({
                "type": "ALLERGY_CROSS_REACTIVITY",
                "severity": group.get("severity_if_confirmed", "HIGH"),
                "medication": med_name,
                "allergy_group": group["group_name"],
                "detail": f"Tiền sử dị ứng {primary} — thuốc đề xuất thuộc nhóm dị ứng chéo ({group['group_name']}). {group.get('cross_reactivity_note', '')}",
                "basis": "structured_table",
                "confidence": group.get("confidence", 0.9),
            })
        elif med_key in partial_substances or any(alias in med_key for alias in partial_substances):
            warnings.append({
                "type": "ALLERGY_PARTIAL_CROSS_REACTIVITY",
                "severity": "MODERATE",
                "medication": med_name,
                "allergy_group": group["group_name"],
                "detail": f"Tiền sử dị ứng {primary} — thuốc đề xuất có khả năng dị ứng chéo một phần ({group['group_name']}). Cần đánh giá lâm sàng.",
                "basis": "structured_table",
                "confidence": round(group.get("confidence", 0.9) * 0.8, 2),
            })
    return warnings


def _check_drug_interactions(
    current_ingredients: list[str],
    proposed_ingredients: list[str],
    proposed_names: dict[str, str],
) -> list[dict]:
    """Check drug-drug interactions from knowledge base."""
    warnings: list[dict] = []
    all_ingredients = set(current_ingredients + proposed_ingredients)

    for interaction in knowledge.drug_interactions:
        pair = interaction["pair"]
        aliases_list = interaction.get("aliases")
        if aliases_list and len(aliases_list) >= 2:
            aliases_a = [a.lower().replace(" ", "") for a in aliases_list[0]]
            aliases_b = [b.lower().replace(" ", "") for b in aliases_list[1]]
        else:
            aliases_a = [pair[0].lower().replace(" ", "")]
            aliases_b = [pair[1].lower().replace(" ", "")]

        # Check if both sides of the interaction are present
        has_a = any(alias in all_ingredients or any(alias in ing for ing in all_ingredients) for alias in aliases_a)
        has_b = any(alias in all_ingredients or any(alias in ing for ing in all_ingredients) for alias in aliases_b)

        if has_a and has_b:
            # Find which proposed medication triggers this
            involved_proposed = []
            for ing in proposed_ingredients:
                if any(alias in ing for alias in aliases_a) or any(alias in ing for alias in aliases_b):
                    involved_proposed.append(proposed_names.get(ing, ing))

            raw_sev = interaction.get("severity", "MODERATE")
            raw_tier = interaction.get("tier", "SOFT_STOP")
            if raw_sev in ("HIGH", "HARD_STOP") or raw_tier == "HARD_STOP":
                sev = "HIGH"
                tier = "HARD_STOP"
            elif set(pair) == {"warfarin", "aspirin"}:
                sev = "HIGH"
                tier = "SOFT_STOP"
            else:
                sev = raw_sev if raw_sev in ("LOW", "MODERATE", "HIGH") else "MODERATE"
                tier = raw_tier

            warnings.append({
                "type": "DRUG_DRUG_INTERACTION",
                "severity": sev,
                "tier": tier,
                "medication": ", ".join(involved_proposed) if involved_proposed else f"{pair[0]} + {pair[1]}",
                "interaction_id": interaction.get("id", f"{pair[0]}_{pair[1]}"),
                "detail": interaction.get("mechanism", ""),
                "clinical_consequence": interaction.get("clinical_consequence", ""),
                "recommendation": interaction.get("action", interaction.get("recommendation", "")),
                "basis": "structured_table",
                "confidence": interaction.get("confidence", 0.95),
            })
    return warnings


def _check_contraindications(
    conditions: list[str],
    med_name: str,
    med_key: str,
) -> list[dict]:
    """Check condition-based contraindications from knowledge base."""
    warnings: list[dict] = []
    conditions_text = " ".join(conditions).lower()

    for ci in knowledge.contraindications:
        medications = [m.lower().replace(" ", "") for m in ci.get("medications", [])]
        if not any(m in med_key for m in medications):
            continue
        matched_conditions = [c for c in ci.get("conditions", []) if c.lower() in conditions_text]
        if matched_conditions:
            warnings.append({
                "type": "CONDITION_CONTRAINDICATION",
                "severity": ci.get("severity", "MODERATE"),
                "tier": ci.get("tier", "SOFT_STOP"),
                "medication": med_name,
                "matched_conditions": matched_conditions,
                "detail": ci.get("detail", ""),
                "recommendation": ci.get("recommendation", ""),
                "basis": "structured_table",
                "confidence": ci.get("confidence", 0.9),
            })
    return warnings


def safety_rules(request: SafetyRequest) -> SafetyCheckResult:
    warnings: list[dict] = []
    unknown_ingredients: list[str] = []
    overall_risk = "LOW"
    requires_human_review = False

    allergies = {a.substance.strip().lower() for a in request.allergies}

    current_ingredients = [_normalize_ingredient(m.name, m.active_ingredient) for m in request.current_medications]
    proposed_ingredients = [_normalize_ingredient(m.name, m.active_ingredient) for m in request.proposed_medications]

    # Build a reverse map: normalized ingredient -> original name
    proposed_names: dict[str, str] = {}
    for med in request.proposed_medications:
        key = _normalize_ingredient(med.name, med.active_ingredient)
        proposed_names[key] = med.name

    # ---- Check 1: Unknown/empty ingredients ----
    for med in request.proposed_medications:
        key = _normalize_ingredient(med.name, med.active_ingredient)
        if not key:
            unknown_ingredients.append(med.name)
            requires_human_review = True

    # ---- Check 2: Allergy cross-reactivity from knowledge base ----
    for med in request.proposed_medications:
        key = _normalize_ingredient(med.name, med.active_ingredient)
        if not key:
            continue
        allergy_warnings = _check_allergy_cross_reactivity(allergies, med.name, key)
        for w in allergy_warnings:
            warnings.append(w)
            overall_risk = _escalate_risk(overall_risk, w["severity"])
            requires_human_review = True

    # ---- Check 3: Drug-drug interactions from knowledge base ----
    interaction_warnings = _check_drug_interactions(
        current_ingredients, proposed_ingredients, proposed_names
    )
    for w in interaction_warnings:
        warnings.append(w)
        overall_risk = _escalate_risk(overall_risk, w["severity"])
        requires_human_review = True

    # ---- Check 4: Condition contraindications from knowledge base ----
    for med in request.proposed_medications:
        key = _normalize_ingredient(med.name, med.active_ingredient)
        if not key:
            continue
        ci_warnings = _check_contraindications(request.conditions, med.name, key)
        for w in ci_warnings:
            warnings.append(w)
            overall_risk = _escalate_risk(overall_risk, w["severity"])
            requires_human_review = True

    # ---- Check 5: Duplicate active ingredients ----
    ingredient_counts: dict[str, int] = {}
    for ingredient in current_ingredients + proposed_ingredients:
        if not ingredient:
            continue
        ingredient_counts[ingredient] = ingredient_counts.get(ingredient, 0) + 1

    duplicates = sorted([ingredient for ingredient, count in ingredient_counts.items() if count > 1])
    if duplicates:
        warnings.append({
            "type": "DUPLICATE_ACTIVE_INGREDIENT",
            "severity": "MODERATE",
            "medication": ", ".join(duplicates),
            "detail": "Một hoặc nhiều hoạt chất xuất hiện lặp lại trong danh sách thuốc.",
            "basis": "structured_table",
            "confidence": 0.95,
        })
        overall_risk = _escalate_risk(overall_risk, "MODERATE")
        requires_human_review = True

    # ---- Final: if any warnings exist, minimum MODERATE ----
    if warnings and overall_risk == "LOW":
        overall_risk = "MODERATE"

    return SafetyCheckResult(
        overall_risk=overall_risk,
        requires_human_review=requires_human_review or bool(warnings) or bool(unknown_ingredients),
        warnings=warnings,
        unknown_ingredients=unknown_ingredients,
    )
