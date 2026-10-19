"""Response Quality Gate and Clinical Alignment Reviewer.

Enforces clinical quality criteria on generated draft responses:
- Prevents context leakage (e.g. cardiac text appearing in allergy answers).
- Prevents false-panic on hypothetical safety questions (e.g. 'Nếu sưng môi thì làm gì?').
- Prevents negated findings from reappearing as active red flags.
- Prevents definitive unsupported clinical diagnoses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from app.services.clinical_text import normalize_search_text


@dataclass
class QualityGateResult:
    passed: bool
    violations: list[str] = field(default_factory=list)
    remediation_notes: list[str] = field(default_factory=list)
    sanitized_response: str | None = None


class ResponseQualityReviewer:
    """Mandatory deterministic quality gate reviewing clinical response alignment."""

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

        # 1. Cardiac/chest-wall explanation must not leak into an unrelated
        # allergy episode merely because prior conversation state existed.
        is_allergy_or_respiratory = any(
            w in query_norm
            for w in (
                "ong dot",
                "me day",
                "sung moi",
                "di ung thuoc",
                "kho khe",
                "hit phai hoa chat",
            )
        )
        has_cardiac_leak = any(
            w in resp_norm
            for w in (
                "tim–phoi",
                "tim-phoi",
                "dau co/thanh nguc o luot truoc",
                "dau nguc theo gang suc",
            )
        )
        if is_allergy_or_respiratory and has_cardiac_leak:
            violations.append("context_leakage_cardiopulmonary_in_allergy")
            remediations.append(
                "Remove cardiac/chest-wall explanation from allergy or toxic respiratory case."
            )

        # 2. Mild screen-strain explanations must not leak into severe acute
        # neurologic/heat illness narratives.
        is_thunderclap_or_heatstroke = any(
            w in query_norm
            for w in (
                "du doi nhat tu truoc toi gio",
                "chay ngoai troi nong",
                "say nang",
                "lu lan va di khong vung",
            )
        )
        has_eye_strain_leak = any(
            w in resp_norm
            for w in (
                "moi thi giac",
                "nhin gan va tap trung vao man hinh",
                "he dieu tiet va hoi tu cua mat",
            )
        )
        if is_thunderclap_or_heatstroke and has_eye_strain_leak:
            violations.append("context_leakage_eye_strain_in_severe_case")
            remediations.append(
                "Remove mild screen-strain explanation from severe emergency presentation."
            )

        # 3. A contingency question must not be rewritten as a current active
        # emergency. Immediate emergency instructions remain valid when phrased
        # conditionally ("nếu/khi ... thì gọi 115").
        is_hypothetical = bool(
            re.search(
                r"\b(?:neu|neu nhu|truong hop|gia su|lo may)\b.*?\b(?:thi phai lam gi|thi xu tri the nao|nen lam gi|can lam gi|lam gi)\b",
                query_norm,
            )
        )
        claims_current_emergency = any(
            phrase in resp_norm
            for phrase in (
                "cac dau hieu hien tai nam trong nhom canh bao can xu tri cap cuu",
                "cac dau hieu hien tai la tinh trang cap cuu",
                "ban dang co dau hieu cap cuu",
                "tinh trang hien tai can cap cuu",
            )
        )
        direct_immediate_action = bool(
            re.search(r"\b(?:goi 115|den khoa cap cuu).*?\b(?:ngay|ngay lap tuc|ngay bay gio)\b", resp_norm)
        )
        conditional_action = bool(
            re.search(
                r"\b(?:neu|neu nhu|khi|neu xuat hien|khi xuat hien)\b.*?\b(?:goi 115|den khoa cap cuu)\b",
                resp_norm,
            )
        )
        if is_hypothetical and (claims_current_emergency or (direct_immediate_action and not conditional_action)):
            violations.append("hypothetical_treated_as_current_emergency")
            remediations.append(
                "Clarify that the signs are contingency guidance rather than active current findings."
            )

        # 4. Explicit negation must not trigger spinal emergency language. The
        # original implementation only caught 'không có/không bị'; this also
        # handles natural Vietnamese such as 'không yếu chân' and 'chưa tê chân'.
        has_negated_weakness = bool(
            re.search(
                r"\b(?:khong|chua)(?:\s+(?:co|bi|thay|he))?\s+(?:yeu chan|te chan|liet chan|te vung yen ngua|te quanh hau mon)\b",
                query_norm,
            )
        )
        triggers_cauda_equina = any(
            w in resp_norm
            for w in (
                "chum duoi ngua",
                "vung yen ngua",
                "chen ep hoac ton thuong than kinh",
                "spinal emergency",
            )
        )
        if has_negated_weakness and triggers_cauda_equina:
            violations.append("negation_false_positive_cauda_equina")
            remediations.append(
                "Reject spinal emergency escalation when weakness/sensory red flags are explicitly negated."
            )

        # 5. Do not convert a bounded clinical assessment into a definitive
        # diagnosis unsupported by examination/testing.
        has_definitive_diagnosis = bool(
            re.search(
                r"\b(?:chac chan ban bi|khang dinh ban mac|chuan doan chinh xac la|chac chan la benh)\b",
                resp_norm,
            )
        )
        if has_definitive_diagnosis:
            violations.append("unsupported_definitive_diagnosis")
            remediations.append(
                "Frame clinical mechanisms as working possibilities rather than definitive diagnosis."
            )

        return QualityGateResult(
            passed=not violations,
            violations=violations,
            remediation_notes=remediations,
        )
