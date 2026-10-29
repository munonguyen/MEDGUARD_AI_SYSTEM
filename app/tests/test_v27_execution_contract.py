from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.v27_execution_contract import (
    assert_agent_execution,
    assert_independent_evaluation_contexts,
    audit_agent_execution,
    independent_evaluation_contexts,
)


def test_verified_agent_response_passes_v27_contract() -> None:
    response = SimpleNamespace(
        request_id="req-v27-ok",
        intent="triage",
        status="answered",
        answer={"summary": "grounded"},
        answer_origin="gateway_verified",
        verification_status="verified",
        orchestrator="agent_verified",
        knowledge_approval="approved",
    )

    audit = assert_agent_execution(response)

    assert audit.passed is True
    assert audit.violations == ()


@pytest.mark.parametrize(
    ("verification_status", "answer_origin", "orchestrator", "expected"),
    [
        (
            "not_requested",
            "deterministic",
            "deterministic",
            {
                "V27_AGENT_NOT_VERIFIED",
                "V27_ANSWER_NOT_GATEWAY_VERIFIED",
                "V27_ORCHESTRATOR_BYPASS",
            },
        ),
        (
            "shadow",
            "deterministic",
            "agent_shadow",
            {
                "V27_AGENT_NOT_VERIFIED",
                "V27_ANSWER_NOT_GATEWAY_VERIFIED",
                "V27_ORCHESTRATOR_BYPASS",
            },
        ),
        (
            "rejected",
            "deterministic_fallback",
            "deterministic_fallback",
            {
                "V27_AGENT_NOT_VERIFIED",
                "V27_ANSWER_NOT_GATEWAY_VERIFIED",
                "V27_ORCHESTRATOR_BYPASS",
            },
        ),
    ],
)
def test_non_verified_paths_fail_closed_for_v27_regression(
    verification_status: str,
    answer_origin: str,
    orchestrator: str,
    expected: set[str],
) -> None:
    response = SimpleNamespace(
        request_id="req-v27-fail",
        intent="safety",
        status="answered",
        answer={"summary": "fallback"},
        answer_origin=answer_origin,
        verification_status=verification_status,
        orchestrator=orchestrator,
        knowledge_approval="not_recorded",
    )

    audit = audit_agent_execution(response)

    assert audit.passed is False
    assert set(audit.violations) == expected


def test_answered_response_without_grounded_answer_is_rejected() -> None:
    response = {
        "request_id": "req-v27-no-answer",
        "intent": "triage",
        "status": "answered",
        "answer": None,
        "answer_origin": "gateway_verified",
        "verification_status": "verified",
        "knowledge_approval": "approved",
    }

    audit = audit_agent_execution(response)

    assert audit.passed is False
    assert "V27_MISSING_GROUNDED_ANSWER" in audit.violations


def test_real_retrieval_context_is_allowed() -> None:
    answer = "Không tự phối hợp hai thuốc giảm đau nếu chưa xác nhận hoạt chất."
    contexts = [
        "Tài liệu dược lâm sàng yêu cầu kiểm tra hoạt chất, tổng liều và chống chỉ định trước khi phối hợp thuốc.",
        "Nguy cơ tương tác phải được đánh giá theo thuốc đang sử dụng và bệnh nền.",
    ]

    passed, violations = independent_evaluation_contexts(
        answer_text=answer,
        contexts=contexts,
    )

    assert passed is True
    assert violations == ()


def test_answer_as_context_is_rejected() -> None:
    answer = "Gọi 115 hoặc đến khoa Cấp cứu ngay; không tự lái xe."

    passed, violations = independent_evaluation_contexts(
        answer_text=answer,
        contexts=[answer],
    )

    assert passed is False
    assert "V27_EVALUATION_ANSWER_AS_CONTEXT" in violations

    with pytest.raises(AssertionError, match="V27_EVALUATION_ANSWER_AS_CONTEXT"):
        assert_independent_evaluation_contexts(
            answer_text=answer,
            contexts=[answer],
        )


def test_missing_context_is_rejected() -> None:
    passed, violations = independent_evaluation_contexts(
        answer_text="Một câu trả lời y tế có claim cần nguồn.",
        contexts=[],
    )

    assert passed is False
    assert violations == ("V27_EVALUATION_CONTEXT_MISSING",)
