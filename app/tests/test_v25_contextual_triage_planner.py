from app.services.contextual_triage_planner import build_contextual_triage_plan


def test_question_five_style_fallback_explains_mechanism_without_diagnosing():
    plan = build_contextual_triage_plan(
        symptoms_text="Tôi đau đầu nhẹ sau khi nhìn màn hình cả ngày.",
        urgency="ROUTINE",
        existing_summary="Kết quả hiện tại chưa ghi nhận dấu hiệu nguy kịch.",
        existing_questions=["Đau ở đâu?", "Đau mấy điểm?"],
    )

    assert plan.applied is True
    assert plan.summary is not None
    normalized = plan.summary.lower()
    assert "mỏi thị giác" in normalized or "điều tiết" in normalized
    assert "không phải chẩn đoán" in normalized
    assert "chưa biết" in normalized
    # V25 adds the preferred question without destroying approved candidates.
    assert len(plan.questions) == 3
    assert "đột ngột" in plan.questions[0].lower()
    assert "Đau ở đâu?" in plan.questions
    assert "Đau mấy điểm?" in plan.questions
    assert plan.reasoning is not None
    assert plan.reasoning.next_question_key == "onset_speed"


def test_followup_summary_explicitly_signals_delta_reasoning():
    plan = build_contextual_triage_plan(
        symptoms_text=(
            "Tôi đau đầu nhẹ sau khi nhìn màn hình cả ngày.\n"
            "Lượt hiện tại: Đau chủ yếu vùng trán, không sốt, nghỉ một lúc thì giảm."
        ),
        urgency="ROUTINE",
    )

    assert plan.summary is not None
    assert "dữ kiện mới" in plan.summary.lower()
    assert plan.episode is not None
    assert plan.episode.latest_user_message.startswith("Đau chủ yếu vùng trán")
    assert plan.episode.user_turns_in_active_episode == 2
    assert plan.reasoning is not None
    assert plan.reasoning.next_question_key == "onset_speed"


def test_emergency_plan_never_adds_mechanism_or_question_before_action():
    original = "Thông tin bạn mô tả khớp với dấu hiệu cảnh báo khẩn cấp."
    plan = build_contextual_triage_plan(
        symptoms_text="Đột ngột đau đầu dữ dội nhất từ trước tới giờ.",
        urgency="EMERGENCY",
        existing_summary=original,
        existing_hypotheses=["Không được hiện trước hành động."],
        existing_questions=["Câu hỏi không được hỏi lúc này?"],
    )

    assert plan.applied is False
    assert plan.reason == "emergency_action_first"
    assert plan.summary == original
    assert plan.questions == ()
    assert plan.episode is None
    assert plan.reasoning is None


def test_planner_preserves_all_candidates_and_places_information_gain_question_first():
    existing = ["Đau mấy điểm?", "Đau bao lâu?", "Có sốt không?"]
    plan = build_contextual_triage_plan(
        symptoms_text="Tôi đau lưng sau khi ngồi máy tính cả ngày.",
        urgency="ROUTINE",
        existing_questions=existing,
    )

    assert plan.reasoning is not None
    assert plan.reasoning.next_question_key in {
        "cauda_equina_features",
        "motor_sensory_deficit",
        "onset_speed",
    }
    assert len(plan.questions) == 4
    assert set(existing).issubset(set(plan.questions))
    assert plan.questions[0] == plan.reasoning.next_best_question


def test_planner_does_not_replace_existing_output_when_no_supported_mechanism():
    existing = "Bạn nên theo dõi diễn biến và cung cấp thêm thông tin."
    questions = ["Bạn khó chịu ở vị trí nào?"]
    plan = build_contextual_triage_plan(
        symptoms_text="Tôi thấy khó chịu không rõ ở đâu.",
        urgency="ROUTINE",
        existing_summary=existing,
        existing_questions=questions,
    )

    assert plan.applied is False
    assert plan.summary == existing
    assert list(plan.questions) == questions
