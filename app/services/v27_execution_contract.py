"""V27 execution and evaluation invariants.

This module is deliberately non-authoring.  It does not generate patient-facing
content and does not repair answers.  It only makes two V27 requirements
machine-checkable:

1. every released chat response can be audited for the enforced Writer ->
   Reviewer path; and
2. jury evaluation must use evidence that is independent from the candidate
   answer, preventing answer-as-context leakage.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Iterable


@dataclass(frozen=True)
class V27ExecutionAudit:
    passed: bool
    request_id: str | None
    intent: str | None
    status: str | None
    answer_origin: str | None
    verification_status: str | None
    orchestrator: str | None
    knowledge_approval: str | None
    violations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _value(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def audit_agent_execution(
    response: Any,
    *,
    require_verified_agent: bool = True,
) -> V27ExecutionAudit:
    """Audit a ChatResponse without exposing hidden agent reasoning.

    V27 treats Jev/Reviewer as a release gate, not an answer author.  Therefore
    an enforced response is considered agent-path compliant only when the
    public provenance says the answer was gateway verified and the internal
    orchestrator marker confirms the verified agent path.
    """

    request_id = _value(response, "request_id")
    intent = _value(response, "intent")
    status = _value(response, "status")
    answer_origin = _value(response, "answer_origin")
    verification_status = _value(response, "verification_status")
    orchestrator = _value(response, "orchestrator")
    knowledge_approval = _value(response, "knowledge_approval")
    answer = _value(response, "answer")

    violations: list[str] = []
    if status == "answered" and answer is None:
        violations.append("V27_MISSING_GROUNDED_ANSWER")

    if require_verified_agent:
        if verification_status != "verified":
            violations.append("V27_AGENT_NOT_VERIFIED")
        if answer_origin != "gateway_verified":
            violations.append("V27_ANSWER_NOT_GATEWAY_VERIFIED")
        if orchestrator not in {None, "agent_verified"}:
            # JSON responses intentionally exclude this internal field.  When
            # auditing an in-process ChatResponse it must identify the path.
            violations.append("V27_ORCHESTRATOR_BYPASS")

    return V27ExecutionAudit(
        passed=not violations,
        request_id=str(request_id) if request_id is not None else None,
        intent=str(intent) if intent is not None else None,
        status=str(status) if status is not None else None,
        answer_origin=str(answer_origin) if answer_origin is not None else None,
        verification_status=(
            str(verification_status) if verification_status is not None else None
        ),
        orchestrator=str(orchestrator) if orchestrator is not None else None,
        knowledge_approval=(
            str(knowledge_approval) if knowledge_approval is not None else None
        ),
        violations=tuple(dict.fromkeys(violations)),
    )


def assert_agent_execution(
    response: Any,
    *,
    require_verified_agent: bool = True,
) -> V27ExecutionAudit:
    audit = audit_agent_execution(
        response,
        require_verified_agent=require_verified_agent,
    )
    if not audit.passed:
        raise AssertionError(
            "V27 agent execution contract failed: " + ", ".join(audit.violations)
        )
    return audit


def _normalize_evaluation_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def independent_evaluation_contexts(
    *,
    answer_text: str,
    contexts: Iterable[str],
) -> tuple[bool, tuple[str, ...]]:
    """Reject circular jury evidence such as ``contexts=[answer_text]``.

    This intentionally detects only strong leakage.  It does not reject normal
    overlap between an evidence document and a grounded answer.
    """

    normalized_answer = _normalize_evaluation_text(answer_text)
    normalized_contexts = [
        _normalize_evaluation_text(value)
        for value in contexts
        if isinstance(value, str) and value.strip()
    ]
    violations: list[str] = []

    if not normalized_contexts:
        violations.append("V27_EVALUATION_CONTEXT_MISSING")
        return False, tuple(violations)

    if normalized_answer:
        for context in normalized_contexts:
            if context == normalized_answer:
                violations.append("V27_EVALUATION_ANSWER_AS_CONTEXT")
                break

        if len(normalized_contexts) == 1:
            context = normalized_contexts[0]
            shorter = min(len(context), len(normalized_answer))
            longer = max(len(context), len(normalized_answer), 1)
            if (
                shorter >= 120
                and shorter / longer >= 0.98
                and (context in normalized_answer or normalized_answer in context)
            ):
                violations.append("V27_EVALUATION_NEAR_CIRCULAR_CONTEXT")

    return not violations, tuple(dict.fromkeys(violations))


def assert_independent_evaluation_contexts(
    *,
    answer_text: str,
    contexts: Iterable[str],
) -> None:
    passed, violations = independent_evaluation_contexts(
        answer_text=answer_text,
        contexts=contexts,
    )
    if not passed:
        raise AssertionError(
            "V27 evaluation independence contract failed: "
            + ", ".join(violations)
        )
