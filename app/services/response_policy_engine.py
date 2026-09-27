"""Response Policy Engine for MedGuard AI System.

Implements the SOTA Clinical Response Policy Layer:
Clinical State + Safety Result + User Intent + Uncertainty + Evidence
    -> Response Policy Engine -> Response Contract

Crucial Clinical Architecture Invariant:
Safety Kernel decides WHAT MUST NOT BE VIOLATED (minimum safety constraint),
NOT how the system speaks to the patient.
The Response Policy Engine maps clinical multidimensional severity (S0-S4)
and response needs (R0-R5) into an empathetic, clear, adaptive ResponseContract.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.models.response_policy import (
    ClinicalResponseContext,
    ClinicalSeverity,
    ResponseContract,
    ResponseNeed,
    ResponseProfile,
    ResponseRichness,
)
from app.models.safety import SafetyKernelResult
from app.services.canonical_clinical_state import CanonicalClinicalState
from app.services.clinical_text import normalize_search_text

logger = logging.getLogger(__name__)


class ResponsePolicyEngine:
    """Deterministic policy engine that governs response posture, depth, and safety boundaries."""

    @classmethod
    def evaluate(
        cls,
        *,
        query: str,
        clinical_state: CanonicalClinicalState | None = None,
        safety_kernel: SafetyKernelResult | None = None,
        raw_urgency: str | None = None,
        complexity_level: str | None = None,
        user_intent: str = "triage",
        uncertainty_profile: dict[str, Any] | None = None,
        evidence_coverage: float = 1.0,
        episode_relation: str = "new",
    ) -> ResponseContract:
        """Determines the exact ResponseContract matching the clinical reality."""
        norm_query = normalize_search_text(query)

        # ------------------------------------------------------------------
        # 1. HARD EMERGENCY SAFETY LOCK
        # ------------------------------------------------------------------
        # Safety Kernel emergency lock OR explicit multi-symptom high-lethality clinical pattern
        has_explicit_lethal_pattern = bool(
            re.search(
                r"\b(?:tuc nguc|dau nguc)\b.*?\b(?:lan (?:tay|nach|ham|lung)|vat mo hoi|va mo hoi|kho tho|ngat|choang|khong giam)\b",
                norm_query,
            )
            or re.search(
                r"\b(?:kho tho)\b.*?\b(?:tuc nguc|dau nguc)\b",
                norm_query,
            )
            or re.search(
                r"\b(?:meo mieng|meo mat|yeu nua nguoi|noi ngong|khong nhac duoc tay chan)\b",
                norm_query,
            )
            or re.search(
                r"\b(?:kho tho du doi|tho rit|phu moi|phu luoi|soc phan ve)\b",
                norm_query,
            )
            or re.search(
                r"\b(?:dau dau dot ngot du doi|chua tung dau nhu vay|worst headache)\b",
                norm_query,
            )
        )

        is_isolated_chest = bool(
            re.search(r"\b(?:tuc nguc|dau nguc|nang nguc)\b", norm_query)
            and not has_explicit_lethal_pattern
            and not any(k in norm_query for k in ("thuoc", "chua", "dieu tri", "tai nha", "khong giam", "kho tho", "lan tay", "ngat"))
            and len(norm_query.split()) <= 8
        )

        is_emergency = (
            (safety_kernel and safety_kernel.emergency_lock)
            or has_explicit_lethal_pattern
            or (raw_urgency == "EMERGENCY" and not is_isolated_chest)
        )

        if is_emergency:
            return ResponseContract(
                profile=ResponseProfile.EMERGENCY_ACTION,
                severity=ClinicalSeverity.S4_EMERGENCY,
                response_need=ResponseNeed.R5_URGENT_ACTION,
                richness_level=ResponseRichness.LEVEL_1,
                tone="calm_firm_emergency",
                medical_depth="action_focused",
                max_length=420,
                required_sections=[
                    "urgent_call_115",
                    "immediate_safety_actions",
                    "brief_triage_question",
                ],
                adaptive_quick_replies=[
                    {"label": "Đang gọi 115", "prompt": "Tôi đang gọi cấp cứu 115"},
                    {
                        "label": "Hướng dẫn lúc chờ cấp cứu",
                        "prompt": "Hướng dẫn các bước an toàn cho tôi trong lúc chờ xe cấp cứu đến",
                    },
                ],
            )

        # ------------------------------------------------------------------
        # 2. ISOLATED HIGH-STAKES SYMPTOM WITHOUT RED FLAGS (CLARIFY_FIRST + SAFETY NET)
        # ------------------------------------------------------------------
        # E.g. "tôi bị tức ngực", "tôi đau ngực" - vague single statement.
        # DO NOT immediately panic and dump the emergency template!
        # Provide broad differentials, high-priority safety net, and ask high-information questions.
        if is_isolated_chest:
            return ResponseContract(
                profile=ResponseProfile.CLARIFY_FIRST,
                severity=ClinicalSeverity.S2_UNCERTAIN,
                response_need=ResponseNeed.R3_CLARIFICATION,
                richness_level=ResponseRichness.LEVEL_2,
                tone="calm_reassuring_vigilant",
                medical_depth="moderate",
                max_length=520,
                required_sections=[
                    "direct_acknowledgment",
                    "broad_differentials",
                    "critical_safety_net",
                    "clarifying_questions",
                ],
                adaptive_quick_replies=[
                    {"label": "Có khó thở", "prompt": "Tôi có kèm theo khó thở"},
                    {"label": "Không khó thở", "prompt": "Tôi không bị khó thở"},
                    {
                        "label": "Đau khi gắng sức",
                        "prompt": "Cảm giác tức ngực xuất hiện khi tôi vận động gắng sức",
                    },
                    {
                        "label": "Đau lan lên hàm/tay",
                        "prompt": "Cơn đau có lan lên vùng cổ hàm hoặc cánh tay",
                    },
                ],
            )

        # ------------------------------------------------------------------
        # 3. VAGUE MILD SYMPTOM WITHOUT ANATOMICAL LOCATION (CLARIFY_FIRST)
        # ------------------------------------------------------------------
        # E.g. "tôi bị đau cơ", "tôi bị đau nhức", "tôi bị nổi mẩn"
        has_muscle_keyword = bool(
            re.search(r"\b(?:dau co|moi co|cang co|e am co|nhuc co)\b", norm_query)
        )
        has_muscle_location = bool(
            re.search(
                r"\b(?:tay|canh tay|bap tay|chan|bap chan|dui|lung|that lung|vai gay|co vai gay|toan than)\b",
                norm_query,
            )
        )

        if has_muscle_keyword and not has_muscle_location:
            return ResponseContract(
                profile=ResponseProfile.CLARIFY_FIRST,
                severity=ClinicalSeverity.S1_MILD,
                response_need=ResponseNeed.R3_CLARIFICATION,
                richness_level=ResponseRichness.LEVEL_1,
                tone="warm_empathetic",
                medical_depth="brief",
                max_length=420,
                required_sections=[
                    "empathetic_acknowledgment",
                    "anatomical_clarification",
                    "gentle_temporary_rest",
                ],
                adaptive_quick_replies=[
                    {"label": "Đau cơ tay", "prompt": "Tôi bị đau cơ tay rất nhiều"},
                    {"label": "Đau mỏi vai gáy", "prompt": "Tôi bị đau mỏi cơ vùng vai gáy"},
                    {"label": "Đau cơ chân", "prompt": "Tôi bị đau cơ bắp chân"},
                    {"label": "Đau cơ lưng", "prompt": "Tôi bị đau cơ vùng lưng"},
                ],
            )

        # ------------------------------------------------------------------
        # 4. SPECIFIC MILD/ROUTINE SYMPTOM WITH LOCATION (SELF_CARE)
        # ------------------------------------------------------------------
        # E.g. "đau cơ tay rất nhiều", "đau mỏi vai gáy sau khi làm việc máy tính"
        if has_muscle_keyword and has_muscle_location:
            return ResponseContract(
                profile=ResponseProfile.SELF_CARE,
                severity=ClinicalSeverity.S1_MILD,
                response_need=ResponseNeed.R2_SELF_CARE,
                richness_level=ResponseRichness.LEVEL_2,
                tone="supportive_clinical",
                medical_depth="moderate",
                max_length=620,
                required_sections=[
                    "empathy_confirmation",
                    "common_causes",
                    "safe_home_care",
                    "red_flags",
                    "specialty_guidance",
                    "exploratory_question",
                ],
                adaptive_quick_replies=[
                    {
                        "label": "Đau sau vận động / tập luyện",
                        "prompt": "Cơn đau xuất hiện sau khi tôi vận động hoặc tập luyện",
                    },
                    {
                        "label": "Đau sau va đập / chấn thương",
                        "prompt": "Cơn đau xuất hiện sau va đập chấn thương",
                    },
                    {
                        "label": "Cơn đau tự nhiên xuất hiện",
                        "prompt": "Cơn đau tự nhiên xuất hiện không rõ lý do",
                    },
                ],
            )

        # ------------------------------------------------------------------
        # 5. MEDICATION SAFETY / DRUG INTERACTION QUERY
        # ------------------------------------------------------------------
        if user_intent == "safety" or any(
            k in norm_query for k in ("tuong tac", "uong chung", "tac dung phu", "qua lieu", "quen uong")
        ):
            return ResponseContract(
                profile=ResponseProfile.MEDICATION_SAFETY,
                severity=ClinicalSeverity.S2_UNCERTAIN,
                response_need=ResponseNeed.R4_MEDICATION_SAFETY,
                richness_level=ResponseRichness.LEVEL_2,
                tone="clear_objective",
                medical_depth="moderate",
                max_length=550,
                required_sections=[
                    "interaction_verdict",
                    "pharmacological_explanation",
                    "patient_guidance",
                    "specialist_alert",
                ],
                adaptive_quick_replies=[
                    {"label": "Cách xử trí khi quên liều", "prompt": "Tôi nên xử trí như thế nào nếu quên một liều?"},
                    {"label": "Tác dụng phụ thường gặp", "prompt": "Các tác dụng phụ phổ biến của thuốc này là gì?"},
                ],
            )

        # ------------------------------------------------------------------
        # 6. SIMPLE FACTUAL / EDUCATIONAL QUERY (LEVEL 0 / LEVEL 1)
        # ------------------------------------------------------------------
        is_definition_or_fact = bool(
            re.search(r"\b(?:la gi|dinh nghia|cong dung|uong luc nao|bao nhieu la binh thuong)\b", norm_query)
        )
        if is_definition_or_fact:
            return ResponseContract(
                profile=ResponseProfile.CLINICAL_EXPLANATION,
                severity=ClinicalSeverity.S0_BENIGN,
                response_need=ResponseNeed.R1_EDUCATION,
                richness_level=ResponseRichness.LEVEL_0,
                tone="educational_accessible",
                medical_depth="brief",
                max_length=350,
                required_sections=[
                    "direct_definition",
                    "clinical_utility",
                    "basic_safety_note",
                ],
                adaptive_quick_replies=[
                    {"label": "Liều dùng thông thường", "prompt": "Liều dùng thông thường được khuyến cáo là gì?"},
                    {"label": "Ai không nên dùng", "prompt": "Những đối tượng nào chống chỉ định hoặc không nên dùng?"},
                ],
            )

        # ------------------------------------------------------------------
        # 7. DEFAULT CONVERSATIONAL CLINICAL ADVISORY (LEVEL 2)
        # ------------------------------------------------------------------
        return ResponseContract(
            profile=ResponseProfile.CONVERSATIONAL,
            severity=ClinicalSeverity.S1_MILD,
            response_need=ResponseNeed.R2_SELF_CARE,
            richness_level=ResponseRichness.LEVEL_2,
            tone="supportive_clinical",
            medical_depth="moderate",
            max_length=580,
            required_sections=[
                "empathetic_acknowledgment",
                "clinical_explanation",
                "actionable_guidance",
                "red_flags",
                "follow_up_question",
            ],
            adaptive_quick_replies=[],
        )
