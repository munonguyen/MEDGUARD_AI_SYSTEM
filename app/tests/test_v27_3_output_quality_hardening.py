from app.services.clinical_agent_contract import build_clinical_agent_contract
from app.services.clinical_fact_parser import parse_semantic_clinical_facts
from app.services.semantic_abstraction_lattice import evaluate_abstraction_lattice
from app.services.semantic_relation_extractor import extract_semantic_relations
from app.services.v27_2_answering_patch import _clean_key_points, _clean_machine_language
from scripts.eval_v27_2_conversation_quality import _relevance_violations


def _visible_explanation(contract) -> str:
    explanation = contract.envelope["explanation_frame"]
    return f"{explanation['what_it_may_mean']} {explanation['mechanism']}".lower()


def _row(question: str, reply: str, *, title: str, category: str = "triage_multiturn") -> dict:
    return {
        "conversation_id": "V24-X",
        "title": title,
        "category": category,
        "question_no": 1,
        "turn": 1,
        "question": question,
        "reply": reply,
    }


def test_anaphylaxis_does_not_inherit_mechanical_chest_explanation() -> None:
    contract = build_clinical_agent_contract(
        intent="triage",
        question=(
            "Sau khi uống thuốc mới tôi nổi vài mảng mề đay ở cánh tay.\n"
            "Ban đang lan thêm lên ngực nhưng tôi vẫn thở bình thường.\n"
            "Lượt hiện tại: Môi bắt đầu sưng và tôi thấy khó thở, cổ họng như bị nghẹn."
        ),
        clinical_result={
            "urgency": "EMERGENCY",
            "emergency_flag": True,
            "red_flags": ["phản vệ độ nặng sau dùng thuốc mới"],
        },
    )
    text = _visible_explanation(contract)
    assert "đau cơ/thành ngực" not in text
    assert "đau cơ thành ngực" not in text
    assert "đỡ sau khi nghỉ" not in text


def test_chemical_inhalation_does_not_inherit_chest_wall_baseline() -> None:
    contract = build_clinical_agent_contract(
        intent="triage",
        question=(
            "Tôi vừa hít phải mùi hóa chất mạnh khi lau nhà và bị rát họng.\n"
            "Lượt hiện tại: Bây giờ tôi khó thở và thấy tức ngực."
        ),
        clinical_result={
            "urgency": "EMERGENCY",
            "emergency_flag": True,
            "red_flags": ["phơi nhiễm hóa chất đường hô hấp kèm khó thở/tức ngực"],
        },
    )
    text = _visible_explanation(contract)
    assert "đau cơ/thành ngực" not in text
    assert "đặc điểm đau cơ" not in text


def test_respiratory_speech_limitation_is_not_rewritten_as_neurologic_deficit() -> None:
    contract = build_clinical_agent_contract(
        intent="triage",
        question=(
            "Tôi hơi khò khè sau khi dọn phòng nhiều bụi.\n"
            "Lượt hiện tại: Tôi thấy khó nói câu dài vì hụt hơi."
        ),
        clinical_result={
            "urgency": "EMERGENCY",
            "emergency_flag": True,
            "red_flags": ["khó thở nặng ảnh hưởng khả năng nói"],
        },
    )
    text = _visible_explanation(contract)
    assert "đau đầu khởi phát" not in text
    assert "dấu hiệu thần kinh" not in text
    assert "biến cố thần kinh" not in text


def test_true_mechanical_chest_delta_still_promotes_cardiorespiratory_warning() -> None:
    contract = build_clinical_agent_contract(
        intent="triage",
        question=(
            "Tôi hơi tức cơ ngực sau buổi tập gym tối qua, ấn vào thì đau hơn.\n"
            "Lượt hiện tại: Hôm nay đi bộ nhanh thì cảm giác nặng ngực rõ hơn và hơi hụt hơi."
        ),
        clinical_result={
            "urgency": "URGENT",
            "emergency_flag": False,
            "red_flags": ["nặng ngực theo gắng sức kèm hụt hơi"],
        },
    )
    frame = contract.envelope["reasoning_frame"]
    assert frame is not None
    assert "episode_delta_cardiorespiratory_warning" in frame["leading_hypothesis_ids"]


def test_coordinated_negation_does_not_create_focal_weakness_emergency() -> None:
    text = "Không có tê yếu chân hay sốt, chỉ mỏi cơ thôi."
    graph = extract_semantic_relations(text)
    assert not graph.has_concept("focal_weakness")
    lattice = evaluate_abstraction_lattice(graph)
    assert lattice.has_emergency_threat is False


def test_no_ingestion_hypothetical_does_not_create_toxic_ingestion_fact() -> None:
    text = (
        "Tối nay tôi có uống rượu và đang cân nhắc thuốc ngủ.\n"
        "Tôi hơi chóng mặt sau khi uống rượu.\n"
        "Nếu chỉ uống nửa liều thuốc ngủ thì có an toàn hơn không?\n"
        "Lượt hiện tại: Tôi chưa uống thuốc ngủ; nên làm gì nếu chóng mặt tăng hoặc lơ mơ?"
    )
    facts = parse_semantic_clinical_facts(text)
    assert not facts.has_concept("toxic_ingestion")
    assert not facts.has_consequence("acute_toxic_metabolic_threat")


def test_affirmed_overdose_is_not_suppressed_by_no_ingestion_guard() -> None:
    facts = parse_semantic_clinical_facts(
        "Tôi đã uống 15 viên paracetamol 500mg trong vài giờ qua và giờ buồn nôn."
    )
    assert facts.has_concept("toxic_ingestion") or facts.has_consequence("acute_toxic_metabolic_threat")


def test_key_point_cleanup_drops_duplicate_transcript_and_semantic_duplicate() -> None:
    blob = (
        "Lượt một về đau ngực.\nLượt hai nặng ngực.\nLượt một về đau ngực.\nLượt hai nặng ngực."
    )
    points = _clean_key_points(
        [
            "Dấu hiệu đã được xác nhận từ bệnh cảnh hiện tại: khó thở.",
            "Dấu hiệu được nhận diện: khó thở",
            blob,
        ]
    )
    assert len(points) == 1
    assert "khó thở" in points[0]
    assert "Lượt một" not in " ".join(points)


def test_patient_text_cleanup_removes_double_terminal_punctuation() -> None:
    value = _clean_machine_language(
        "Hội chứng cảnh báo cần đánh giá (nghi thiếu máu cơ tim/ACS).."
    )
    assert value.endswith("ACS).")
    assert ".." not in value


def test_quality_gate_detects_allergy_chest_leak() -> None:
    issues = _relevance_violations(
        _row(
            "Môi bắt đầu sưng và tôi thấy khó thở, cổ họng như bị nghẹn.",
            "Việc bạn thấy đỡ sau khi nghỉ không xóa các dấu hiệu cảnh báo tim–phổi đã xuất hiện trước đó; đau cơ/thành ngực ở lượt trước không đủ.",
            title="Phản ứng dị ứng tiến triển",
        )
    )
    assert "allergy_inherited_chest_mechanism" in issues


def test_quality_gate_detects_respiratory_speech_neuro_leak() -> None:
    issues = _relevance_violations(
        _row(
            "Tôi thấy khó nói câu dài vì hụt hơi.",
            "Dữ kiện mới thuộc nhóm dấu hiệu thần kinh; đau đầu khởi phát đột ngột có thể phản ánh biến cố thần kinh.",
            title="Khò khè tăng dần",
        )
    )
    assert "respiratory_speech_misread_as_neurologic" in issues


def test_quality_gate_detects_negated_weakness_false_emergency() -> None:
    issues = _relevance_violations(
        _row(
            "Không có tê yếu chân hay sốt, chỉ mỏi cơ thôi.",
            "Gọi 115 hoặc đến khoa Cấp cứu. Yếu chân mới xuất hiện.",
            title="Đau lưng do tư thế",
        )
    )
    assert "negated_weakness_promoted_to_emergency" in issues


def test_quality_gate_detects_no_ingestion_false_overdose() -> None:
    issues = _relevance_violations(
        _row(
            "Tôi chưa uống thuốc ngủ; nên làm gì nếu chóng mặt tăng hoặc lơ mơ?",
            "Gọi 115 ngay vì đây là ngộ độc cấp do quá liều thuốc.",
            title="Rượu và thuốc gây buồn ngủ",
            category="medication_safety_multiturn",
        )
    )
    assert "no_ingestion_reported_as_overdose" in issues
    assert "hypothetical_worsening_promoted_to_current_emergency" in issues
