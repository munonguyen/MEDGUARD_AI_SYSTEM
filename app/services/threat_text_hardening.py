"""V27.3 patient-language wording for toxic threat findings.

The clinical threat level and confidence are unchanged. Only the combined legacy
label that conflated environmental toxic exposure with medication overdose is
replaced by an exposure-neutral description suitable for structured red flags.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any


_MARKER = "_medguard_v27_3_toxic_threat_text"
_LEGACY = "Ngộ độc cấp chất độc cực mạnh / ngộ độc thuốc quá liều cấp tính"
_PLAIN = "Phơi nhiễm hoặc ngộ độc độc chất cấp tính có nguy cơ đe dọa tính mạng"


def install_threat_text_hardening(module: ModuleType) -> None:
    if getattr(module, _MARKER, False):
        return
    original = getattr(module, "_eval_toxic_exposure", None)
    if original is None:
        return

    def _eval_toxic_exposure(fact_set: Any, vitals: dict[str, float]):
        assessment = original(fact_set, vitals)
        findings = [
            _PLAIN if str(value) == _LEGACY else str(value)
            for value in list(getattr(assessment, "findings", ()) or ())
        ]
        if findings == list(getattr(assessment, "findings", ()) or ()):
            return assessment
        return assessment.__class__(
            dimension=assessment.dimension,
            level=assessment.level,
            confidence=assessment.confidence,
            findings=findings,
            rationale=assessment.rationale,
        )

    module._eval_toxic_exposure = _eval_toxic_exposure
    setattr(module, _MARKER, True)
