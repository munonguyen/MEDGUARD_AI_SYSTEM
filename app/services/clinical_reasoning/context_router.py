"""Clinical context router.

V28.1 replaces keyword-only urgency decisions with structured evidence.
The router extracts symptom context, severity signals and negative findings
before downstream risk classification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re


@dataclass
class ClinicalContextResult:
    symptoms: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    severity: dict[str, str] = field(default_factory=dict)
    positive_findings: dict[str, bool] = field(default_factory=dict)
    negative_findings: dict[str, bool] = field(default_factory=dict)
    risk_features: list[str] = field(default_factory=list)


class ClinicalContextRouter:
    """Rule-based safety floor before LLM reasoning.

    It intentionally does not diagnose. It only converts patient text into
    structured evidence so that later agents can reason on context.
    """

    NEGATIONS = (
        "không",
        "chưa",
        "không hề",
        "không thấy",
    )

    TERMS = {
        "chest_pain": ("đau ngực", "tức ngực"),
        "headache": ("đau đầu",),
        "back_pain": ("đau lưng",),
        "leg_weakness": ("yếu chân", "liệt chân"),
        "shortness_of_breath": ("khó thở", "hụt hơi"),
        "sweating": ("vã mồ hôi", "đổ mồ hôi"),
        "radiation": ("lan tay", "lan hàm"),
        "exercise": ("tập gym", "tập luyện", "chống đẩy", "vận động"),
        "fever": ("sốt",),
    }

    def parse(self, text: str) -> ClinicalContextResult:
        lowered = text.lower()
        result = ClinicalContextResult()

        for key, patterns in self.TERMS.items():
            found = any(p in lowered for p in patterns)
            if not found:
                continue

            negated = self._is_negated(lowered, patterns)
            if negated:
                result.negative_findings[key] = True
            else:
                result.positive_findings[key] = True

        if result.positive_findings.get("exercise"):
            result.triggers.append("exercise_related")

        for key in result.positive_findings:
            if key not in {"exercise"}:
                result.symptoms.append(key)

        if any(word in lowered for word in ("dữ dội", "rất đau", "chưa từng")):
            result.severity["level"] = "high"

        result.risk_features = self._red_flags(result)
        return result

    def _is_negated(self, text: str, patterns: tuple[str, ...]) -> bool:
        for pattern in patterns:
            idx = text.find(pattern)
            if idx < 0:
                continue
            prefix = text[max(0, idx - 15):idx]
            if any(n in prefix for n in self.NEGATIONS):
                return True
        return False

    def _red_flags(self, result: ClinicalContextResult) -> list[str]:
        flags = []
        positive = result.positive_findings

        if positive.get("chest_pain") and any(
            positive.get(x)
            for x in ("shortness_of_breath", "sweating", "radiation")
        ):
            flags.append("cardiac_warning_pattern")

        if positive.get("back_pain") and positive.get("leg_weakness"):
            flags.append("spinal_neurological_warning")

        if positive.get("headache") and result.severity.get("level") == "high":
            flags.append("severe_headache_pattern")

        return flags
