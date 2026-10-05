from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from app.models.agents import AgentEvidenceSource, AnswerAgentTrace, VerificationScores
from app.models.common import DisclaimerMixin
from app.services.conversation_continuation import resolve_conversation_continuation
from app.services.question_policy import plan_clinical_questions


ChatIntent = Literal[
    "general",
    "triage",
    "safety",
    "monitoring",
    "followup",
    "pharmacy",
    "queue",
    "fhir",
    "delivery",
    "ocr",
    "schedule",
    "authenticity",
]


class ChatEvidenceSource(BaseModel):
    name: str
    version: str
    approval_status: Literal["approved", "pending_review", "not_recorded"]
    references: list[str] = Field(default_factory=list)


class AnswerNarrativeBlock(BaseModel):
    """Safe rich text assembled only from the grounded answer fields."""

    kind: Literal["paragraph", "caution", "urgent"] = "paragraph"
    text: str
    emphasis: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)


class AnswerAssurance(BaseModel):
    status: Literal["verified"]
    scores: VerificationScores


class GroundedAnswer(BaseModel):
    title: str
    summary: str
    presentation: Literal["brief", "focused", "detailed"] = "detailed"
    display_summary: str | None = None
    display_next_steps: list[str] | None = None
    clinical_hypotheses: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    display_questions: list[str] | None = None
    decision_basis: Literal[
        "versioned_rules",
        "registry_record",
        "workflow_record",
        "insufficient_information",
    ]
    evidence_state: Literal[
        "direct_rule_match",
        "bounded_result",
        "operation_confirmed",
        "partial_input",
    ]
    rule_version: str | None = None
    sources: list[ChatEvidenceSource] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    requires_human_review: bool = False
    narrative: list[AnswerNarrativeBlock] = Field(default_factory=list)
    researched_sources: list[AgentEvidenceSource] = Field(default_factory=list)
    answer_assurance: AnswerAssurance | None = None
    agent_trace: SkipJsonSchema[AnswerAgentTrace | None] = Field(default=None, exclude=True)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatContext(BaseModel):
    patient_ref: str | None = Field(default=None, max_length=128)
    age: int | None = Field(default=None, ge=0, le=120)
    sex: Literal["male", "female", "other"] | None = None
    current_medications: list[str] = Field(default_factory=list, max_length=50)
    allergies: list[str] = Field(default_factory=list, max_length=50)
    conditions: list[str] = Field(default_factory=list, max_length=50)
    last_result: dict[str, Any] | None = None


class ChatRequest(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=128)
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)
    context: ChatContext = Field(default_factory=ChatContext)
    intent_hint: Literal[
        "auto",
        "triage",
        "safety",
        "monitoring",
        "followup",
        "pharmacy",
        "queue",
        "fhir",
        "delivery",
        "ocr",
        "schedule",
        "authenticity",
    ] = "auto"
    locale: str = "vi-VN"
    original_latest_content: SkipJsonSchema[str | None] = Field(default=None, exclude=True)
    continuation_reason: SkipJsonSchema[str | None] = Field(default=None, exclude=True)

    @field_validator("messages")
    @classmethod
    def latest_message_must_be_from_user(cls, value: list[ChatMessage]) -> list[ChatMessage]:
        if value[-1].role != "user":
            raise ValueError("the latest chat message must be from the user")
        return value

    @model_validator(mode="after")
    def recover_high_confidence_continuation(self) -> "ChatRequest":
        if self.intent_hint != "auto" or not self.messages:
            return self
        resolution = resolve_conversation_continuation(
            [(message.role, message.content) for message in self.messages]
        )
        if resolution is None:
            return self

        self.intent_hint = resolution.intent
        self.continuation_reason = resolution.reason
        if resolution.augmented_latest:
            original = self.messages[-1].content
            self.original_latest_content = original
            self.messages[-1] = self.messages[-1].model_copy(
                update={"content": resolution.augmented_latest}
            )
        return self


class ChatSuggestion(BaseModel):
    label: str
    prompt: str
    intent: ChatIntent


class ChatResponse(DisclaimerMixin):
    request_id: str
    conversation_id: str
    status: Literal["answered", "needs_information", "unsupported"]
    intent: ChatIntent
    reply: str
    required_fields: list[str] = Field(default_factory=list)
    extracted: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    answer: GroundedAnswer | None = None
    suggestions: list[ChatSuggestion] = Field(default_factory=list)
    answer_origin: Literal[
        "deterministic",
        "gateway_verified",
        "deterministic_fallback",
    ] = "deterministic"
    verification_status: Literal[
        "not_requested",
        "shadow_pending",
        "shadow",
        "verified",
        "timed_out",
        "rejected",
        "unavailable",
        "circuit_open",
        "error",
    ] = "not_requested"
    knowledge_approval: Literal[
        "approved",
        "pending_review",
        "not_recorded",
        "mixed",
    ] = "not_recorded"
    orchestrator: SkipJsonSchema[Literal[
        "deterministic",
        "agent_verified",
        "agent_shadow",
        "deterministic_fallback",
    ]] = Field(default="deterministic", exclude=True)

    def _attach_question_policy_trace(self, plan: Any) -> None:
        if not isinstance(self.result, dict):
            return
        trace = self.result.get("trace")
        if not isinstance(trace, dict):
            return
        details = dict(trace.get("details") or {})
        details["question_policy"] = plan.trace_payload()
        updated_trace = dict(trace)
        updated_trace["details"] = details
        updated_result = dict(self.result)
        updated_result["trace"] = updated_trace
        self.result = updated_result

    def _default_next_step(self, urgency: str) -> str | None:
        """Return a bounded action when an otherwise valid answer has none.

        This is a presentation/release invariant, not a clinical reasoner.  It
        does not infer severity; it uses only the already-resolved intent,
        status and urgency supplied by upstream domain logic.
        """
        if self.intent == "monitoring":
            if urgency == "EMERGENCY":
                return (
                    "Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay; không tự lái xe và "
                    "không trì hoãn để tiếp tục theo dõi chỉ số tại nhà."
                )
            if urgency == "URGENT":
                return (
                    "Liên hệ cơ sở y tế để được đánh giá sớm; nếu chỉ số xấu đi hoặc "
                    "xuất hiện khó thở, đau ngực, lơ mơ hay choáng, hãy đi cấp cứu."
                )
            return (
                "Tiếp tục ghi lại chỉ số đúng đơn vị và đo lại theo hướng dẫn; liên hệ "
                "cơ sở y tế nếu chỉ số xấu đi hoặc xuất hiện triệu chứng mới."
            )

        if self.intent == "safety":
            return (
                "Không tự bắt đầu, ngừng, đổi liều hoặc phối hợp thuốc dựa chỉ trên hội thoại; "
                "hãy trao đổi với bác sĩ hoặc dược sĩ khi quyết định dùng thuốc có thể thay đổi."
            )

        if self.intent == "schedule":
            return (
                "Kiểm tra lại tên thuốc và thời gian trên lịch; nếu cần, bạn có thể yêu cầu "
                "đổi giờ, tạm dừng hoặc hủy lịch."
            )

        if self.intent == "followup":
            return (
                "Nếu chưa có mốc phù hợp, hãy cho biết thời điểm dự kiến hoặc điều kiện cần "
                "tái khám để hệ thống hỗ trợ điều chỉnh kế hoạch."
            )

        if self.intent == "pharmacy":
            return (
                "Kiểm tra lại thuốc và thông tin cấp phát; nếu có điểm chưa khớp, hãy liên hệ "
                "dược sĩ trước khi sử dụng."
            )

        return None

    def _narrative_with_selected_questions(
        self,
        selected_questions: list[str],
    ) -> list[AnswerNarrativeBlock]:
        """Keep the patient-facing shortlist consistent with the narrative."""
        if self.answer is None:
            return []
        prompt_label = "Bạn cho mình biết thêm"
        selected = selected_questions[:2]
        replacement = ""
        if selected:
            normalized_questions: list[str] = []
            for raw in selected:
                question = raw.strip()
                if question and question[-1] not in "?!":
                    question += "?"
                if question:
                    normalized_questions.append(question)
            replacement = f"{prompt_label}: {' '.join(normalized_questions)}"

        updated: list[AnswerNarrativeBlock] = []
        found_question_block = False
        for block in self.answer.narrative:
            if block.text.strip().startswith(prompt_label):
                found_question_block = True
                if replacement:
                    updated.append(
                        block.model_copy(
                            update={
                                "text": replacement,
                                "emphasis": [prompt_label],
                            }
                        )
                    )
                continue
            updated.append(block)

        if replacement and not found_question_block:
            updated.append(
                AnswerNarrativeBlock(
                    kind="paragraph",
                    text=replacement,
                    emphasis=[prompt_label],
                )
            )
        return updated

    @model_validator(mode="after")
    def apply_patient_question_policy(self) -> "ChatResponse":
        """Enforce patient-surface dialogue, actionability and emergency invariants."""
        if self.answer is None:
            return self

        result = self.result if isinstance(self.result, dict) else {}
        urgency = str(
            result.get("urgency")
            or result.get("escalation_level")
            or "ROUTINE"
        ).upper()

        # V26 output contract: an answered clinical/workflow response should not
        # end as a passive description when a safe next action can be expressed
        # from the already-resolved intent/urgency.  Jev can therefore evaluate
        # a stable structured action field instead of relying on prose heuristics.
        if not self.answer.next_steps:
            default_step = self._default_next_step(urgency)
            if default_step:
                self.answer = self.answer.model_copy(update={"next_steps": [default_step]})

        if not isinstance(self.result, dict):
            return self

        if urgency == "EMERGENCY":
            uncertainty = (
                "Hệ thống không xác định nguyên nhân hoặc chẩn đoán chỉ từ tin nhắn này; "
                "không thể khẳng định chẩn đoán từ xa."
            )
            obsolete_phrase = "thay vì tiếp tục tự theo dõi tại nhà"

            summary = self.answer.summary.replace(obsolete_phrase, "ngay")
            if "không thể khẳng định" not in summary.lower():
                summary = f"{summary.rstrip()} {uncertainty}".strip()

            narrative: list[AnswerNarrativeBlock] = []
            has_uncertainty = False
            for block in self.answer.narrative:
                text = block.text.replace(obsolete_phrase, "ngay")
                if "không thể khẳng định" in text.lower():
                    has_uncertainty = True
                if text.strip().startswith("Bạn cho mình biết thêm"):
                    continue
                narrative.append(block.model_copy(update={"text": text}))
            if not has_uncertainty:
                insert_at = 1 if narrative else 0
                narrative.insert(
                    insert_at,
                    AnswerNarrativeBlock(kind="paragraph", text=uncertainty),
                )

            self.answer = self.answer.model_copy(
                update={
                    "summary": summary,
                    "questions": [],
                    "display_questions": [],
                    "narrative": narrative,
                }
            )
            emergency_plan = plan_clinical_questions([], urgency="EMERGENCY")
            self._attach_question_policy_trace(emergency_plan)
            return self

        if self.intent != "triage":
            return self

        # Keep the complete approved candidate set in ``questions`` for audit,
        # evaluation and downstream reasoning.  Only ``display_questions`` and
        # the patient narrative are pruned by the dialogue policy.
        plan = plan_clinical_questions(list(self.answer.questions), urgency=urgency)
        selected_questions = list(plan.questions)
        self.answer = self.answer.model_copy(
            update={
                "display_questions": selected_questions,
                "narrative": self._narrative_with_selected_questions(selected_questions),
            }
        )
        self._attach_question_policy_trace(plan)
        return self


class ConversationSummary(BaseModel):
    conversation_id: str
    title: str
    patient_ref: str | None = None
    message_count: int
    created_at: str
    updated_at: str


class StoredChatMessage(BaseModel):
    message_id: str
    request_id: str | None = None
    role: Literal["user", "assistant"]
    content: str
    intent: str | None = None
    status: str | None = None
    result: dict[str, Any] | None = None
    answer: GroundedAnswer | None = None
    answer_origin: Literal[
        "deterministic", "gateway_verified", "deterministic_fallback"
    ] | None = None
    verification_status: Literal[
        "not_requested", "shadow_pending", "shadow", "verified", "timed_out",
        "rejected", "unavailable", "circuit_open", "error",
    ] | None = None
    knowledge_approval: Literal[
        "approved", "pending_review", "not_recorded", "mixed"
    ] | None = None
    created_at: str


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummary] = Field(default_factory=list)


class ConversationHistoryResponse(BaseModel):
    conversation: ConversationSummary
    messages: list[StoredChatMessage] = Field(default_factory=list)
