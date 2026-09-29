"""V27 chat orchestration facade.

The existing deterministic/domain orchestrator is preserved byte-for-byte in
``chat_core.py``. This facade changes only the response-authority policy:
clinical requests in enforced mode always enter the same agent-first clinical
contract, regardless of whether upstream reasoning currently has enough data to
answer or needs one targeted clarification.

V27 invariant:
    clinical request -> clinical contract -> Writer -> Reviewer/Jev
                     -> answered | needs_information

``needs_information`` is therefore an outcome of reasoning, not a switch back
to the legacy ``enhance()`` contract.
"""

from __future__ import annotations

from typing import Any

from app.services import chat_core as _core
from app.services.response_path_policy import (
    clinical_payload_with_outcome,
    is_clinical_response_path,
)

# Preserve the public/private compatibility surface used by historical runners,
# tests and API routes. The only intentionally replaced symbol is ``_response``.
_CORE_EXPORTS: set[str] = set()
for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)
        _CORE_EXPORTS.add(_name)


def _response(
    payload: ChatRequest,
    ctx: RequestContext,
    *,
    status: str,
    intent: ChatIntent,
    reply: str,
    required_fields: list[str] | None = None,
    extracted: dict[str, Any] | None = None,
    result: Any | None = None,
    agent_question: str | None = None,
    allow_agent: bool = True,
) -> ChatResponse:
    serialized = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
    fields = required_fields or []
    extracted_values = extracted or {}
    answer = build_grounded_answer(
        intent=intent,
        status=status,
        reply=reply,
        required_fields=fields,
        result=serialized,
    )
    agent_status: str | None = None
    agent_submitted = False
    clinical_task_name = (
        str(serialized.get("clinical_task"))
        if isinstance(serialized, dict) and serialized.get("clinical_task")
        else str(extracted_values.get("clinical_task"))
        if extracted_values.get("clinical_task")
        else None
    )

    # V27: clinicality and epistemic state are separate axes. A missing
    # medication name, low-confidence lab interpretation, or other clinical
    # ambiguity remains on the Writer/Reviewer path and may result in a targeted
    # clarification rather than switching contracts.
    clinical_request = is_clinical_response_path(
        intent=intent,
        clinical_task_name=clinical_task_name,
    )

    effective_allow_agent = allow_agent or (
        settings.agent_coverage_scope == "all"
        and settings.agent_mode in {"shadow", "enforced"}
        and (settings.agent_sync_enabled or settings.agent_background_enabled)
    )
    agent_first_clinical = (
        effective_allow_agent
        and clinical_request
        and settings.agent_mode == "enforced"
    )
    agent_eligible = agent_first_clinical or (
        effective_allow_agent
        and intent in _active_research_agent_intents()
    )

    agent_patient_context = payload.context.model_dump(mode="json")
    if clinical_request:
        agent_patient_context["last_result"] = None

    if agent_first_clinical:
        clinical_payload = clinical_payload_with_outcome(
            serialized,
            status=status,
            required_fields=fields,
            extracted=extracted_values,
        )
        answer = answer_agent_pipeline.generate_response(
            fallback_answer=answer,
            clinical_payload=clinical_payload,
            intent=intent,
            question=agent_question or payload.messages[-1].content,
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            conversation_id=payload.conversation_id,
            locale=payload.locale,
            patient_context=agent_patient_context,
        )
    elif agent_eligible and settings.agent_sync_enabled:
        answer = answer_agent_pipeline.enhance(
            answer=answer,
            intent=intent,
            question=agent_question or payload.messages[-1].content,
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            conversation_id=payload.conversation_id,
            locale=payload.locale,
            patient_context=agent_patient_context,
        )
    elif agent_eligible and settings.agent_background_enabled:
        agent_submitted = background_agent_runner.submit(
            answer=answer,
            intent=intent,
            question=agent_question or payload.messages[-1].content,
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            conversation_id=payload.conversation_id,
            locale=payload.locale,
            patient_context=agent_patient_context,
        )

    internal_agent_trace = answer.agent_trace
    if internal_agent_trace:
        agent_status = internal_agent_trace.status
    elif agent_submitted:
        agent_status = "shadow_pending"

    orchestrator = {
        "verified": "agent_verified",
        "shadow": "agent_shadow",
        "shadow_pending": "agent_shadow",
        "unavailable": "deterministic_fallback",
        "rejected": "deterministic_fallback",
        "error": "deterministic_fallback",
        "circuit_open": "deterministic_fallback",
    }.get(agent_status, "deterministic")
    verification_status = agent_status or (
        "unavailable" if agent_eligible and settings.agent_background_enabled else "not_requested"
    )
    if (
        verification_status == "error"
        and internal_agent_trace
        and internal_agent_trace.fallback_reason == "agent_total_timeout"
    ):
        verification_status = "timed_out"

    if verification_status == "verified":
        answer_origin = "gateway_verified"
    elif verification_status in {"timed_out", "unavailable", "rejected", "error", "circuit_open"}:
        answer_origin = "deterministic_fallback"
    else:
        answer_origin = "deterministic"

    coverage_outcome = (
        "completed"
        if verification_status in {"verified", "shadow"}
        else "accepted"
        if verification_status == "shadow_pending"
        else "attempt_failed"
        if verification_status in {"timed_out", "rejected", "unavailable", "circuit_open", "error"}
        else "not_requested"
    )
    metrics.inc_counter(
        "medguard_gateway_response_coverage_total",
        labels={
            "intent": intent,
            "status": status,
            "scope": settings.agent_coverage_scope,
            "outcome": coverage_outcome,
        },
    )

    approval_states = {source.approval_status for source in answer.sources}
    if not approval_states:
        knowledge_approval = "not_recorded"
    elif approval_states == {"approved"}:
        knowledge_approval = "approved"
    elif approval_states == {"pending_review"}:
        knowledge_approval = "pending_review"
    elif approval_states == {"not_recorded"}:
        knowledge_approval = "not_recorded"
    else:
        knowledge_approval = "mixed"

    answer = answer.model_copy(update={"agent_trace": None})
    response = ChatResponse(
        request_id=ctx.request_id,
        conversation_id=payload.conversation_id,
        status=status,
        intent=intent,
        reply=answer.summary,
        required_fields=fields,
        extracted=extracted_values,
        result=serialized,
        answer=answer,
        suggestions=_suggestions(intent) if status == "answered" else [],
        answer_origin=answer_origin,
        verification_status=verification_status,
        knowledge_approval=knowledge_approval,
        orchestrator=orchestrator,  # type: ignore[arg-type]
    )
    chat_history_store.append_exchange(ctx.tenant_id, payload, response)
    audit_store.append(
        AuditEvent(
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            action="chat.route",
            payload_type="ChatRequest",
            metadata={
                "intent": intent,
                "status": status,
                "conversation_id": payload.conversation_id,
                "agent_status": agent_status,
                "agent_fallback_reason": internal_agent_trace.fallback_reason if internal_agent_trace else None,
                "answer_assurance": "source_verified" if agent_status == "verified" else "baseline",
                "clinical_agent_first": agent_first_clinical,
                "clinical_outcome": status if clinical_request else None,
            },
        )
    )
    return response


def _sync_core_globals() -> None:
    """Mirror facade monkeypatches into the preserved orchestration module.

    Historical tests and extensions patch symbols on ``app.services.chat``.
    Since ``orchestrate_chat`` was originally defined in the monolithic module,
    its global lookups now occur in ``chat_core``. Synchronizing exported names
    before dispatch preserves those hooks without changing routing semantics.
    """
    for name in _CORE_EXPORTS:
        if name == "orchestrate_chat":
            continue
        if name in globals():
            setattr(_core, name, globals()[name])
    _core._response = _response


def orchestrate_chat(payload: ChatRequest, ctx: RequestContext) -> ChatResponse:
    _sync_core_globals()
    return _core.orchestrate_chat(payload, ctx)


# Direct callers inside chat_core must also use the V27 response policy.
_core._response = _response
