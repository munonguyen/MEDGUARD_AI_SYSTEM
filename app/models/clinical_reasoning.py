from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SupportLevel = Literal["weak", "plausible", "supported"]
ReasoningRole = Literal["leading", "contributor", "must_not_miss_pathway"]


class MechanismHypothesis(BaseModel):
    """A diagnosis-neutral mechanism hypothesis grounded in episode evidence."""

    model_config = ConfigDict(frozen=True)

    hypothesis_id: str
    label: str
    role: ReasoningRole
    support_level: SupportLevel
    mechanism: str
    evidence_for: tuple[str, ...] = Field(default_factory=tuple)
    evidence_against: tuple[str, ...] = Field(default_factory=tuple)
    unresolved: tuple[str, ...] = Field(default_factory=tuple)
    patient_safe_statement: str


class ClinicalReasoningFrame(BaseModel):
    """Structured reasoning supplied to the Writer; never a diagnosis itself."""

    model_config = ConfigDict(frozen=True)

    version: str = "v25.2"
    mechanisms: tuple[MechanismHypothesis, ...] = Field(default_factory=tuple)
    leading_hypothesis_ids: tuple[str, ...] = Field(default_factory=tuple)
    must_not_miss_unknowns: tuple[str, ...] = Field(default_factory=tuple)
    next_best_question: str | None = None
    next_question_key: str | None = None
    reasoning_limits: tuple[str, ...] = (
        "Cơ chế được mô tả là giả thuyết làm việc, không phải chẩn đoán xác định.",
        "Mối liên hệ thời gian không tự chứng minh quan hệ nhân quả.",
        "Dữ kiện người dùng chưa đề cập phải giữ ở trạng thái unknown, không được suy diễn là âm tính.",
    )

    def to_agent_payload(self) -> dict:
        return self.model_dump(mode="json")
