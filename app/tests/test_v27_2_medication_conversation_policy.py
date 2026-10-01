from types import SimpleNamespace

from app.services.medication_conversation_policy import (
    _contextual_dose_reply,
    _contextual_missing_reply,
    _incident_is_supported_by_current_turn,
    _is_personalized_dose_request,
)
from app.services.clinical_text import normalize_search_text


def _payload(*user_messages: str):
    return SimpleNamespace(
        messages=[SimpleNamespace(role="user", content=value) for value in user_messages]
    )


def _incident_result(rule_version: str) -> dict[str, object]:
    return {"trace": {"rule_version": rule_version}}


def test_personalized_dose_variants_are_recognized() -> None:
    variants = (
        "Nếu chỉ uống nửa liều thuốc ngủ thì có an toàn hơn không?",
        "Bạn cho tôi liều ibuprofen cụ thể để dùng xen kẽ nhé.",
        "Bạn tính giúp tôi liều paracetamol chính xác tiếp theo được không?",
        "Tôi có nên tự bỏ liều thuốc chống đông tối nay không?",
        "Tôi đang dùng metformin, có cần tự đổi liều không?",
    )
    for value in variants:
        assert _is_personalized_dose_request(normalize_search_text(value)), value


def test_already_ingested_medication_prompt_uses_ingestion_context() -> None:
    reply = _contextual_missing_reply(
        _payload(
            "Tôi đang uống paracetamol, có thể dùng thêm thuốc cảm cũng chứa paracetamol không?",
            "Tôi đã uống một liều thuốc cảm cách đây hai giờ.",
        )
    )
    assert "đã được dùng" in reply
    assert "thời điểm" in reply
    assert "thuốc đang cân nhắc" not in reply


def test_unknown_supplement_prompt_is_not_generic_medication_prompt() -> None:
    reply = _contextual_missing_reply(
        _payload(
            "Tôi đang dùng thuốc huyết áp và muốn uống thêm một loại thực phẩm bổ sung không rõ thành phần.",
            "Trên nhãn chỉ ghi hỗn hợp thảo dược độc quyền, không có hàm lượng từng chất.",
        )
    )
    assert "thành phần" in reply
    assert "hàm lượng" in reply
    assert "Tôi cần tên thuốc đang cân nhắc" not in reply


def test_contextual_missing_replies_follow_latest_turn_and_do_not_collapse() -> None:
    ingestion = _contextual_missing_reply(
        _payload("Tôi lỡ uống nhầm gấp đôi thuốc của mình cách đây khoảng 20 phút.")
    )
    anticoagulant = _contextual_missing_reply(
        _payload("Tôi đang dùng thuốc chống đông và hôm nay bị chảy máu cam.")
    )
    sedative = _contextual_missing_reply(
        _payload("Tối nay tôi có uống rượu, có thể dùng thêm thuốc gây buồn ngủ được không?")
    )
    assert len({ingestion, anticoagulant, sedative}) == 3
    assert "gấp đôi" in ingestion
    assert "chống đông" in anticoagulant
    assert "rượu" in sedative


def test_personalized_dose_boundary_is_grounded_and_turn_specific() -> None:
    original = (
        "MedGuard không kê hoặc tính liều thuốc cá nhân hóa từ hội thoại. "
        "Liều dùng cần được bác sĩ hoặc dược sĩ xác nhận."
    )
    half_dose = _contextual_dose_reply(
        _payload("Nếu chỉ uống nửa liều thuốc ngủ thì có an toàn hơn không?"),
        original,
    )
    skip_dose = _contextual_dose_reply(
        _payload("Tôi có nên tự bỏ liều thuốc chống đông tối nay không?"),
        original,
    )
    assert half_dose != skip_dose
    assert "nửa liều" in half_dose
    assert "bỏ liều" in skip_dose
    assert "không kê đơn" in half_dose
    assert "không kê hoặc tính liều thuốc cá nhân hóa" in half_dose


def test_hypertension_incident_requires_actual_ingestion_event() -> None:
    result = _incident_result("MED-INC-HYPERTENSION-001@1.0.0")
    routine_use = normalize_search_text(
        "Tôi đang dùng thuốc huyết áp và muốn uống thêm một loại thực phẩm bổ sung."
    )
    overdose = normalize_search_text(
        "Tôi uống nhầm gấp đôi liều thuốc huyết áp sáng nay."
    )
    assert not _incident_is_supported_by_current_turn(routine_use, result)
    assert _incident_is_supported_by_current_turn(overdose, result)


def test_insulin_and_lithium_incidents_require_protocol_context() -> None:
    insulin = _incident_result("MED-INC-INSULIN-001@1.0.0")
    lithium = _incident_result("MED-INC-LITHIUM-001@1.0.0")
    assert not _incident_is_supported_by_current_turn(
        normalize_search_text("Tôi đang dùng insulin mỗi ngày."), insulin
    )
    assert _incident_is_supported_by_current_turn(
        normalize_search_text("Tôi quên tiêm insulin nền tối qua."), insulin
    )
    assert not _incident_is_supported_by_current_turn(
        normalize_search_text("Tôi đang uống lithium theo đơn."), lithium
    )
    assert _incident_is_supported_by_current_turn(
        normalize_search_text("Tôi đang uống lithium và bị tiêu chảy mất nước."), lithium
    )
