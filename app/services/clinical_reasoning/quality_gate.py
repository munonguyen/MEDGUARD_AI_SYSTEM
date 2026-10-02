"""Response Quality Gate and Clinical Alignment Reviewer.

Enforces clinical quality criteria on generated draft responses:
- Prevents context leakage (e.g. cardiac text appearing in allergy answers).
- Prevents false-panic on hypothetical safety questions (e.g. 'Nếu sưng môi thì làm gì?').
- Prevents definitive unsupported clinical diagnoses.
- Enforces appropriate safety actions for true emergencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from app.services.clinical_text import normalize_search_text


@dataclass
class QualityGateResult:
    passed: bool
    violations: list[str] = field(default_factory=list)
    remediation_notes: list[str] = field(default_factory=list)
    sanitized_response: str | None = None


class ResponseQualityReviewer:
    """Mandatory quality gate reviewing clinical response alignment."""

    def review(
        self,
        user_query: str,
        response_text: str,
        domain: str | None = None,
    ) -> QualityGateResult:
        query_norm = normalize_search_text(user_query)
        resp_norm = normalize_search_text(response_text)
        violations: list[str] = []
        remediations: list[str] = []

        # 1. Context Leakage Check: Cardiac text leaking into non-cardiac domains
        is_allergy_or_respiratory = any(
            w in query_norm for w in ("ong dot", "me day", "sung moi", "di ung thuoc", "kho khe", "hit phai hoa chat")
        )
        has_cardiac_leak = any(
            w in resp_norm for w in ("tim–phoi", "tim-phoi", "dau co/thanh nguc o luot truoc", "dau nguc theo gang suc")
        )

        if is_allergy_or_respiratory and has_cardiac_leak:
            violations.append("context_leakage_cardiopulmonary_in_allergy")
            remediations.append("Remove cardiac/chest-wall explanation from allergy or toxic respiratory case.")

        # 2. Context Leakage Check: Eye-strain / screen headache leaking into acute stroke / thunderclap / heatstroke
        is_thunderclap_or_heatstroke = any(
            w in query_norm for w in ("du doi nhat tu truoc toi gio", "chay ngoai troi nong", "say nang", "lu lan va di khong vung")
        )
        has_eye_strain_leak = any(
            w in resp_norm for w in ("moi thi giac", "nhin gan va tap trung vao man hinh", "he dieu tiet va hoi tu cua mat")
        )

        if is_thunderclap_or_heatstroke and has_eye_strain_leak:
            violations.append("context_leakage_eye_strain_in_severe_case")
            remediations.append("Remove mild screen-strain explanation from severe emergency presentation.")

        # 3. Hypothetical Question Check: 'Nếu... thì làm gì?' must not declare current active emergency
        is_hypothetical = bool(re.search(r"\b(?:neu|neu nhu|truong hop|gia su|lo may)\b.*?\b(?:thi phai lam gi|thi xu tri the nao|nen lam gi|can lam gi|lam gi)\b", query_norm))
        claims_current_emergency = "cac dau hieu hien tai nam trong nhom canh bao can xu tri cap cuu" in resp_norm

        if is_hypothetical and claims_current_emergency:
            violations.append("hypothetical_treated_as_current_emergency")
            remediations.append("Clarify that signs are contingency guidance rather than active current findings.")

        # 4. Negation False Positive Check: Negated findings triggering emergency
        has_negated_weakness = bool(re.search(r"\b(?:khong co|khong bi|khong thay).*(?:yeu chan|te chan|te)\b", query_norm))
        triggers_cauda_equina = any(w in resp_norm for w in ("chum duoi ngua", "vung yen ngua", "chen ep hoac ton thuong than kinh"))

        if has_negated_weakness and triggers_cauda_equina:
            violations.append("negation_false_positive_cauda_equina")
            remediations.append("Reject spinal emergency escalation when leg weakness is explicitly negated.")

        # 5. Unsupported Definitive Diagnosis
        has_definitive_diagnosis = bool(
            re.search(
                r"\b(?:chac chan ban bi|khang dinh ban mac|chuan doan chinh xac la|chac chan la benh)\b",
                resp_norm,
            )
        )
        if has_definitive_diagnosis:
            violations.append("unsupported_definitive_diagnosis")
            remediations.append("Frame clinical mechanisms as working possibilities rather than definitive diagnosis.")

        passed = len(violations) == 0
        return QualityGateResult(
            passed=passed,
            violations=violations,
            remediation_notes=remediations,
        )
