from app.models.chat import GroundedAnswer
from app.services.clinical_agent_contract import build_clinical_agent_contract
from app.services.clinical_contract_fallback import compose_contract_fallback
from app.services.patient_visible_response import select_patient_visible_surface
from app.services.v27_2_answering_patch import _sanitize_answer
from scripts.eval_v27_2_conversation_quality import evaluate


def test_late_safety_actions_survive_composition_hygiene_and_visible_surface():
    actions = [f"Hướng dẫn đã duyệt {index}." for index in range(7)]
    actions.append("Gọi 115 ngay; không tự lái xe.")
    warnings = [f"Cảnh báo đã duyệt {index}." for index in range(6)]
    warnings.append("Không tự phối hợp thuốc trước khi hỏi dược sĩ.")
    base = GroundedAnswer(title="Hướng dẫn", summary="Đã đánh giá.",
                          next_steps=actions, safety_notes=warnings,
                          decision_basis="versioned_rules", evidence_state="bounded_result")
    contract = build_clinical_agent_contract(
        intent="triage", question="Tôi khó thở.",
        clinical_result={"urgency": "EMERGENCY", "emergency_flag": True},
    )
    final = _sanitize_answer(compose_contract_fallback(base, contract))
    surface = select_patient_visible_surface({"answer": final.model_dump(),
                                             "verification_status": "unavailable"}).text
    assert all(value in final.next_steps and value in surface for value in actions)
    assert all(value in final.safety_notes and value in surface for value in warnings)
    assert final.summary.startswith("Gọi 115")
    assert final.questions == []


def test_grounding_keeps_patient_question_attributed_and_only_latest_turn():
    question = "Lượt trước: Tôi đau đầu.\nLượt hiện tại: Tôi có dùng ibuprofen được không?"
    contract = build_clinical_agent_contract(
        intent="safety", question=question,
        clinical_result={"overall_risk": "HIGH", "conversation_turn": question},
    )
    final = compose_contract_fallback(GroundedAnswer(title="Thuốc", summary="Cần kiểm tra.",
                                                     decision_basis="versioned_rules", evidence_state="bounded_result"), contract)
    assert "«Tôi có dùng ibuprofen được không»" not in final.summary
    assert "Lượt trước" not in final.summary
    assert "Bạn có dùng ibuprofen" not in final.summary


def test_quality_gate_rejects_partial_report_even_without_duplicate_replies(tmp_path):
    path = tmp_path / "partial.md"
    path.write_text("## V24-T1 — Test\n- Category: `triage`\n"
                    "### Question 1 — Turn 1\n\n**User:** Tôi đau tay.\n\n"
                    "**Reply:** Cần đánh giá.\n", encoding="utf-8")
    report = evaluate(path)
    assert report["gate_passed"] is False
    assert report["integrity_issues"][0]["issue"] == "expected_200_unique_questions"


def test_quality_gate_requires_nonempty_reply_for_every_question(tmp_path):
    path = tmp_path / "complete.md"
    blocks = ["## V24-T1 — Test\n- Category: `triage`\n"]
    for number in range(1, 201):
        blocks.append(f"### Question {number} — Turn {number}\n\n"
                      f"**User:** Thông tin {number}.\n\n"
                      f"**Reply:** Hướng dẫn {number}.\n\n")
    content = "".join(blocks)
    path.write_text(content, encoding="utf-8")
    assert evaluate(path)["gate_passed"] is True
    path.write_text(content.replace("**Reply:** Hướng dẫn 200.", "**Reply:**"), encoding="utf-8")
    report = evaluate(path)
    assert report["gate_passed"] is False
    assert {"issue": "empty_reply", "question_no": 200} in report["integrity_issues"]
