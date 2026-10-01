from app.models.chat import ChatMessage, ChatRequest
from app.services import answering
from app.services import chat
from app.services.clinical_agent_contract import build_clinical_agent_contract
from app.services.conversation_intelligence import _classify_medications


def _request(*messages: str) -> ChatRequest:
    return ChatRequest(
        conversation_id="v27-2-test",
        messages=[ChatMessage(role="user", content=value) for value in messages],
    )


def test_latest_monitoring_turn_wins_over_stale_headache_history() -> None:
    payload = _request(
        "Tôi hơi đau đầu sau khi làm việc máy tính.",
        "Chuyển việc khác: tôi đang dùng warfarin, có dùng ibuprofen được không?",
        "Huyết áp hiện tại của tôi là 150/95.",
    )
    latest = chat._normalize(payload.messages[-1].content)
    assert chat._detect_intent(payload, latest) == "monitoring"


def test_medication_memory_carries_pending_candidate_across_followup_turn() -> None:
    payload = _request(
        "Tôi đang dùng warfarin, có thể uống thêm ibuprofen vì đau răng không?",
        "Tôi còn đang uống aspirin liều thấp mỗi ngày nữa.",
    )
    current, proposed, _, _ = chat._extract_safety(
        payload,
        chat._normalize(payload.messages[-1].content),
    )
    assert "warfarin" in current
    assert "aspirin" in current
    assert "ibuprofen" in proposed


def test_multiple_current_medicines_keep_their_roles_when_candidate_is_added() -> None:
    current, proposed = _classify_medications(
        chat,
        "Tôi đang dùng warfarin và aspirin mỗi ngày, có thể uống thêm ibuprofen không?",
    )
    assert current == ["warfarin", "aspirin"]
    assert proposed == ["ibuprofen"]

    reversed_current, reversed_proposed = _classify_medications(
        chat,
        "Tôi có thể uống ibuprofen nếu đang dùng warfarin và aspirin mỗi ngày không?",
    )
    assert reversed_current == ["warfarin", "aspirin"]
    assert reversed_proposed == ["ibuprofen"]


def test_duplicate_ingredient_is_retained_in_both_medication_roles() -> None:
    current, proposed = _classify_medications(
        chat,
        "Tôi đang uống paracetamol, có thể dùng thêm thuốc cảm cũng chứa paracetamol không?",
    )
    assert current == ["paracetamol"]
    assert proposed == ["paracetamol"]


def test_monitoring_answer_uses_plain_language_not_internal_codes() -> None:
    answer = answering.build_grounded_answer(
        intent="monitoring",
        status="answered",
        reply="unused",
        required_fields=[],
        result={
            "escalation_level": "NONE",
            "trend": "insufficient_data",
            "alerts": [
                {
                    "metric": "overall",
                    "severity": "LOW",
                    "detail": "Cần thêm lần đo để đánh giá xu hướng.",
                    "basis": "insufficient_data",
                }
            ],
            "patient_measurements": [
                {"metric": "systolic", "value": 150.0, "unit": "mmHg"},
                {"metric": "diastolic", "value": 95.0, "unit": "mmHg"},
            ],
        },
    )
    visible = " ".join(
        [
            answer.title,
            answer.summary,
            *answer.key_points,
            *answer.next_steps,
            *answer.safety_notes,
            *answer.limitations,
        ]
    )
    assert "150/95" in visible
    assert "NONE" not in visible
    assert "insufficient_data" not in visible
    assert "ESI" not in visible


def test_safety_answer_names_remembered_medicines_without_high_code() -> None:
    answer = answering.build_grounded_answer(
        intent="safety",
        status="answered",
        reply="unused",
        required_fields=[],
        result={
            "overall_risk": "HIGH",
            "requires_human_review": True,
            "warnings": [
                {
                    "type": "DRUG_DRUG_INTERACTION",
                    "tier": "HARD_STOP",
                    "medication": "ibuprofen",
                    "detail": "Phối hợp có thể làm tăng nguy cơ chảy máu.",
                }
            ],
            "conversation_current_medications": ["warfarin"],
            "conversation_proposed_medications": ["ibuprofen"],
        },
    )
    visible = " ".join([answer.title, answer.summary, *answer.key_points])
    assert "warfarin" in visible.lower()
    assert "ibuprofen" in visible.lower()
    assert "HIGH" not in visible


def test_thunderclap_headache_replaces_old_screen_strain_explanation() -> None:
    contract = build_clinical_agent_contract(
        intent="triage",
        question=(
            "Tôi hơi đau đầu sau khi làm việc máy tính.\n"
            "Lượt hiện tại: Vừa rồi tôi đột ngột đau đầu dữ dội nhất từ trước tới giờ."
        ),
        clinical_result={
            "urgency": "EMERGENCY",
            "emergency_flag": True,
            "red_flags": ["thunderclap_headache"],
        },
    )
    frame = contract.envelope["reasoning_frame"]
    assert frame is not None
    assert frame["leading_hypothesis_ids"] == ["episode_delta_neurologic_warning"]
    assert frame["next_best_question"] is None
    explanation = contract.envelope["explanation_frame"]
    assert "thần kinh" in (
        f"{explanation['what_it_may_mean']} {explanation['mechanism']}"
    ).lower()


def test_spinal_neurologic_red_flags_replace_postural_mechanical_explanation() -> None:
    contract = build_clinical_agent_contract(
        intent="triage",
        question=(
            "Tôi mỏi lưng sau khi ngồi máy tính khoảng 9 tiếng.\n"
            "Lượt hiện tại: Tôi khó nhấc bàn chân, tê vùng quanh mông và khó kiểm soát tiểu tiện."
        ),
        clinical_result={
            "urgency": "EMERGENCY",
            "emergency_flag": True,
            "red_flags": ["spinal_neurologic_deficit"],
        },
    )
    frame = contract.envelope["reasoning_frame"]
    assert frame is not None
    assert frame["leading_hypothesis_ids"] == ["episode_delta_spinal_neurologic_warning"]
    assert frame["next_best_question"] is None
    explanation = contract.envelope["explanation_frame"]
    text = f"{explanation['what_it_may_mean']} {explanation['mechanism']}".lower()
    assert "đau cơ học đơn thuần" in text or "thần kinh" in text
