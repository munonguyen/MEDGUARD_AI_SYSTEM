from app.services import triage
from app.services.clinical_fact_parser import parse_semantic_clinical_facts
from app.services.clinical_threat_graph import ThreatLevel, evaluate_threat_graph
from app.services.risk_memory import infer_episode_domain
from app.services.v27_runtime_patch import _final_presentation_hygiene
from app.models.chat import GroundedAnswer


def test_respiratory_speech_limitation_routes_to_cardiorespiratory() -> None:
    assert infer_episode_domain("Tôi thấy khó nói câu dài vì hụt hơi.") == "cardiorespiratory"
    assert infer_episode_domain("Tôi khó nói và nói ngọng, méo miệng.") == "neurovestibular"


def test_throat_language_does_not_select_neck_shoulder_guidance() -> None:
    assert triage.knowledge.find_symptom_guidance(
        "Sưng môi có vẻ bớt nhưng cổ họng vẫn khó chịu và nghẹn họng."
    ) is None

    genuine = triage.knowledge.find_symptom_guidance(
        "Tôi đau cổ vai gáy sau khi ngồi máy tính lâu, xoay cổ thì đau."
    )
    assert isinstance(genuine, dict)
    assert genuine.get("topic") == "neck_shoulder_pain"


def test_toxic_threat_wording_is_exposure_neutral_for_chemical_exposure() -> None:
    facts = parse_semantic_clinical_facts(
        "Tôi hít phải mùi hóa chất mạnh, sau đó khó thở và tức ngực."
    )
    result = evaluate_threat_graph(facts)
    toxic = result.assessments["toxic_exposure"]
    if toxic.level != ThreatLevel.NONE:
        text = " ".join(toxic.findings).lower()
        assert "quá liều" not in text
        assert "phơi nhiễm" in text or "ngộ độc" in text


def test_true_medication_overdose_keeps_critical_toxic_threat() -> None:
    facts = parse_semantic_clinical_facts(
        "Tôi đã uống 15 viên paracetamol 500mg trong vài giờ và giờ buồn nôn."
    )
    result = evaluate_threat_graph(facts)
    toxic = result.assessments["toxic_exposure"]
    assert toxic.level == ThreatLevel.CRITICAL
    assert toxic.confidence >= 0.9


def test_final_presentation_hygiene_drops_multiline_history_but_keeps_actions() -> None:
    answer = GroundedAnswer(
        title="Theo dõi triệu chứng",
        summary="Triệu chứng hiện tại phù hợp theo dõi.",
        key_points=[
            "Tôi hơi đau lưng do ngồi lâu.\nKhông có tê yếu chân, chỉ mỏi cơ.",
            "Hướng chuyên khoa hiện tại: Cơ xương khớp.",
        ],
        next_steps=["Đổi tư thế và theo dõi diễn tiến."],
        safety_notes=["Đi khám nếu xuất hiện yếu chân hoặc rối loạn tiểu tiện."],
    )
    cleaned = _final_presentation_hygiene(answer)
    assert cleaned.key_points == ["Hướng chuyên khoa hiện tại: Cơ xương khớp."]
    assert cleaned.next_steps == ["Đổi tư thế và theo dõi diễn tiến."]
    assert cleaned.safety_notes == ["Đi khám nếu xuất hiện yếu chân hoặc rối loạn tiểu tiện."]
