"""Clinical Clarification Planner for MedGuard AI System.

Selects 1-3 targeted clarifying questions that maximize Information Gain
to discriminate critical triage boundaries (e.g., ROUTINE vs. URGENT vs. EMERGENCY),
avoiding fatigue from unprioritized generic questionnaires.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.services.canonical_clinical_state import CanonicalClinicalState
from app.services.clinical_text import normalize_search_text


@dataclass(frozen=True)
class ClarificationQuestion:
    id: str
    text: str
    target_risk: str  # e.g., "stroke", "subarachnoid_hemorrhage", "myocardial_infarction"
    information_gain: float  # 0.0 to 1.0 (higher = greater triage discrimination power)
    category: str  # "onset", "radiation", "associated_red_flag", "vitals"


# Curated high-information-gain clinical questions
_HIGH_GAIN_QUESTION_REGISTRY: tuple[ClarificationQuestion, ...] = (
    ClarificationQuestion(
        id="q_thunderclap",
        text="Cơn đau đầu có khởi phát đột ngột dữ dội và đạt mức cực đỉnh trong vòng dưới 1 phút (như sét đánh) không?",
        target_risk="subarachnoid_hemorrhage",
        information_gain=0.98,
        category="onset",
    ),
    ClarificationQuestion(
        id="q_chest_crush_radiate",
        text="Cơn đau ngực có cảm giác đè nặng như đá đè và lan lên hàm, cổ, lưng hoặc xuống cánh tay trái không?",
        target_risk="acute_coronary_syndrome",
        information_gain=0.96,
        category="radiation",
    ),
    ClarificationQuestion(
        id="q_acute_dyspnea",
        text="Bạn có cảm thấy khó thở dữ dội, không thể nói trọn một câu ngắn hoặc phải ngồi dậy để thở không?",
        target_risk="pulmonary_edema_or_embolism",
        information_gain=0.95,
        category="associated_red_flag",
    ),
    ClarificationQuestion(
        id="q_focal_weakness",
        text="Bạn có nhận thấy đột ngột méo mặt, yếu một bên tay chân hoặc nói ngọng, khó diễn đạt lời nói không?",
        target_risk="acute_ischemic_stroke",
        information_gain=0.97,
        category="associated_red_flag",
    ),
    ClarificationQuestion(
        id="q_peritoneal_signs",
        text="Bụng của bạn có đau quằn quại dữ dội, sờ vào thấy cứng như gỗ hoặc đau chói khi ấn rồi thả tay nhanh không?",
        target_risk="peritonitis_acute_abdomen",
        information_gain=0.94,
        category="associated_red_flag",
    ),
    ClarificationQuestion(
        id="q_syncope",
        text="Cơn khó chịu có kèm theo choáng váng muốn xỉu, ngất thoáng qua hoặc mất ý thức không?",
        target_risk="cardiogenic_syncope",
        information_gain=0.93,
        category="associated_red_flag",
    ),
    ClarificationQuestion(
        id="q_fever_stiff_neck",
        text="Bạn có sốt cao kèm theo cứng cổ gáy (khó cúi cằm chạm ngực) hoặc sợ ánh sáng chói không?",
        target_risk="meningitis",
        information_gain=0.92,
        category="associated_red_flag",
    ),
)


class ClinicalClarificationPlanner:
    """Selects the most informative clarifying questions given the clinical state."""

    @staticmethod
    def plan_clarifications(
        state: CanonicalClinicalState,
        *,
        max_questions: int = 3,
    ) -> list[str]:
        """Select top 1-3 questions with highest information gain not already addressed."""
        norm_text = state.normalized_text
        negations = [normalize_search_text(n) for n in state.negations]

        candidates: list[ClarificationQuestion] = []
        for q in _HIGH_GAIN_QUESTION_REGISTRY:
            # Check if this topic or question is already covered in user text or negations
            if q.target_risk in norm_text or any(q.target_risk in n for n in negations):
                continue
            # Contextual relevance heuristics
            if "dau dau" in norm_text and q.target_risk in ("subarachnoid_hemorrhage", "meningitis"):
                candidates.append(q)
            elif "dau nguc" in norm_text and q.target_risk in ("acute_coronary_syndrome", "pulmonary_edema_or_embolism"):
                candidates.append(q)
            elif any(k in norm_text for k in ("bung", "dau bung", "da day")) and q.target_risk == "peritonitis_acute_abdomen":
                candidates.append(q)
            elif any(k in norm_text for k in ("chong mat", "yeu", "te", "tay chan")) and q.target_risk in ("acute_ischemic_stroke", "cardiogenic_syncope"):
                candidates.append(q)

        # If specific candidates found, sort by information gain
        if candidates:
            candidates.sort(key=lambda x: x.information_gain, reverse=True)
            return [c.text for c in candidates[:max_questions]]

        # Fallback: if general unresolved case, select highest gain general screening questions
        general = sorted(_HIGH_GAIN_QUESTION_REGISTRY, key=lambda x: x.information_gain, reverse=True)
        return [g.text for g in general[:max_questions]]
