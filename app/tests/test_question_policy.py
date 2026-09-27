from app.services.question_policy import plan_clinical_questions


def test_emergency_never_blocks_on_questions():
    plan = plan_clinical_questions(
        [
            "Triệu chứng bắt đầu từ khi nào?",
            "Bạn có khó thở hoặc ngất không?",
        ],
        urgency="EMERGENCY",
    )

    assert plan.questions == []
    assert plan.max_questions == 0


def test_routine_asks_one_high_value_question():
    plan = plan_clinical_questions(
        [
            "Mức đau hiện tại từ 0 đến 10 là bao nhiêu và có đang tăng nhanh không?",
            "Triệu chứng bắt đầu từ khi nào và diễn tiến liên tục hay từng cơn?",
            "Bạn có kèm nóng rát, ợ chua hoặc cảm giác trào lên cổ họng không?",
        ],
        urgency="ROUTINE",
    )

    assert len(plan.questions) == 1
    assert "0 đến 10" in plan.questions[0]


def test_urgent_prioritizes_safety_and_disposition_with_low_burden():
    plan = plan_clinical_questions(
        [
            "Bạn có đau tăng dữ dội, bụng cứng/chướng nhiều, ngất, nôn ra máu hoặc đi ngoài phân đen không?",
            "Mức đau hiện tại từ 0 đến 10 là bao nhiêu và có đang tăng nhanh không?",
            "Cảm giác thay đổi thế nào khi đói, trong bữa ăn hoặc sau khi ăn?",
        ],
        urgency="URGENT",
    )

    assert len(plan.questions) == 2
    categories = {candidate.category for candidate in plan.selected}
    assert "SAFETY" in categories
    assert "DISPOSITION" in categories


def test_duplicate_questions_are_removed_before_ranking():
    question = "Triệu chứng bắt đầu từ khi nào và diễn tiến liên tục hay từng cơn?"
    plan = plan_clinical_questions(
        [question, question, "  " + question + "  "],
        urgency="ROUTINE",
    )

    assert plan.questions == [question]
    assert plan.candidate_count == 1


def test_policy_never_invents_question_not_supplied_by_clinical_layer():
    supplied = [
        "Bạn đã nôn chưa và hiện có uống giữ được nước không?",
        "Triệu chứng bắt đầu từ khi nào và diễn tiến liên tục hay từng cơn?",
    ]
    plan = plan_clinical_questions(supplied, urgency="URGENT")

    assert set(plan.questions).issubset(set(supplied))


def test_routine_hydration_question_outranks_older_semantic_ambiguity():
    semantic = (
        "Khi nói “sốt ruột”, bạn muốn nói cảm giác bồn chồn hoặc lo lắng, "
        "hay cảm giác nóng rát và cồn cào trong bụng?"
    )
    hydration = "Bạn đã nôn chưa và hiện có uống giữ được nước không?"

    plan = plan_clinical_questions([semantic, hydration], urgency="ROUTINE")

    assert plan.questions == [hydration]
    assert plan.selected[0].category == "DISPOSITION"


def test_semantic_clarification_still_outranks_low_value_diagnostic_question():
    semantic = "Khi nói “sốt ruột”, bạn muốn nói bồn chồn hay cồn cào trong bụng?"
    diagnostic = "Bạn có thấy đầy hơi sau bữa ăn không?"

    plan = plan_clinical_questions([diagnostic, semantic], urgency="ROUTINE")

    assert plan.questions == [semantic]
    assert plan.selected[0].category == "SEMANTIC_CLARIFICATION"
