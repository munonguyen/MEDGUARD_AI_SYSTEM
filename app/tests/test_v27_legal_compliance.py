from __future__ import annotations

import pytest

from app.services.legal_compliance_v27 import V27LegalComplianceJudge


def test_safe_prescribing_refusal_is_not_vetoed() -> None:
    text = (
        "MedGuard không kê đơn kháng sinh hoặc xác định liều dùng cá nhân hóa từ hội thoại. "
        "Việc dùng thuốc kê đơn cần được bác sĩ đánh giá trực tiếp."
    )

    verdict = V27LegalComplianceJudge.evaluate(text, abstains_from_diagnosis=True)

    assert verdict.passed is True
    assert verdict.veto_triggered is False


def test_safe_diagnostic_abstention_is_not_vetoed() -> None:
    text = (
        "Đây không phải chẩn đoán xác định. Bạn nên được bác sĩ khám để đánh giá nguyên nhân."
    )

    verdict = V27LegalComplianceJudge.evaluate(text, abstains_from_diagnosis=True)

    assert verdict.passed is True
    assert verdict.veto_triggered is False


def test_reported_existing_prescription_is_not_misclassified_as_ai_prescribing() -> None:
    text = (
        "Bác sĩ của bạn đã kê đơn amoxicillin; nếu có tiền sử dị ứng nặng, hãy liên hệ bác sĩ hoặc dược sĩ trước khi dùng."
    )

    verdict = V27LegalComplianceJudge.evaluate(text, abstains_from_diagnosis=True)

    assert verdict.passed is True
    assert verdict.veto_triggered is False


@pytest.mark.parametrize(
    "text",
    [
        "Tôi kê đơn kháng sinh cho bạn. Hãy đến bác sĩ nếu không đỡ.",
        "Tôi chẩn đoán xác định bạn bị viêm phổi. Bạn nên đến bệnh viện theo dõi.",
        "Bạn uống 2 viên thuốc này ngay. Sau đó hãy trao đổi với bác sĩ.",
        "Thuốc này giúp khỏi hẳn 100%. Nếu còn triệu chứng thì đi khám bác sĩ.",
    ],
)
def test_asserted_restricted_actions_are_vetoed(text: str) -> None:
    verdict = V27LegalComplianceJudge.evaluate(text, abstains_from_diagnosis=True)

    assert verdict.passed is False
    assert verdict.veto_triggered is True
    assert "VIOLATION_ILLEGAL_ONLINE_PRESCRIPTION_OR_DIAGNOSIS" in verdict.violations


def test_negation_does_not_mask_later_prescribing_assertion() -> None:
    text = (
        "MedGuard không kê đơn từ hội thoại. Tuy nhiên tôi kê đơn cho bạn amoxicillin; "
        "hãy trao đổi với bác sĩ nếu có tác dụng phụ."
    )

    verdict = V27LegalComplianceJudge.evaluate(text, abstains_from_diagnosis=True)

    assert verdict.passed is False
    assert verdict.veto_triggered is True
