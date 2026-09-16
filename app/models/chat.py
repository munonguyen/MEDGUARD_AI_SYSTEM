from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator
from pydantic.json_schema import SkipJsonSchema

from app.models.agents import AgentEvidenceSource, AnswerAgentTrace, VerificationScores
from app.models.common import DisclaimerMixin


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
    clinical_hypotheses: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
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

    @field_validator("messages")
    @classmethod
    def latest_message_must_be_from_user(cls, value: list[ChatMessage]) -> list[ChatMessage]:
        if value[-1].role != "user":
            raise ValueError("the latest chat message must be from the user")
        return value


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
