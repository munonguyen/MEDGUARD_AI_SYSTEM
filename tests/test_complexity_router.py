"""Unit tests for Complexity Router and Adaptive Compute Tiers."""

import pytest
from app.services.clinical_intake_compiler import ClinicalIntakeCompiler
from app.services.complexity_router import ComplexityRouter


def test_complexity_router_c0_conversational():
    intake = ClinicalIntakeCompiler.compile("Chào bác sĩ ạ, chúc bác một ngày tốt lành!")
    route = ComplexityRouter.route(intake)
    assert route.level == "C0"
    assert route.pipeline_mode == "lightweight_direct"
    assert route.max_latency_budget_ms <= 1000.0
    assert route.requires_dual_agent is False


def test_complexity_router_c1_single_clinical_question():
    intake = ClinicalIntakeCompiler.compile("Thuốc Paracetamol thường dùng trong trường hợp nào và liều lượng ra sao?")
    route = ComplexityRouter.route(intake)
    assert route.level == "C1"
    assert route.pipeline_mode == "single_rag_agent"
    assert route.requires_question_decomposition is False


def test_complexity_router_c2_multi_intent():
    query = (
        "bác ơi mấy hôm nay chân bên trái đoạn dưới đầu gối nó cứ căng căng sáng ngủ dậy thấy hơn "
        "nhưng đi lại thì vẫn được hôm kia có chạy bộ cũng hơi nhiều mà em thấy trên mạng nói cục máu đông "
        "nên hơi sợ không biết có nguy hiểm ko với em đang uống thuốc dị ứng nữa"
    )
    intake = ClinicalIntakeCompiler.compile(query)
    route = ComplexityRouter.route(intake)
    assert route.level == "C2"
    assert route.pipeline_mode == "decomposed_multi_retriever"
    assert route.requires_question_decomposition is True
    assert route.requires_dual_agent is True
    assert route.requires_jev_arbitration is True
    assert len(route.sub_questions) >= 3


def test_complexity_router_c4_emergency():
    intake = ClinicalIntakeCompiler.compile("Bác sĩ ơi bố em đột ngột đau ngực đè nặng lan ra tay trái, khó thở dữ dội và toát mồ hôi lạnh!")
    route = ComplexityRouter.route(intake)
    assert route.level == "C4"
    assert route.pipeline_mode == "safety_kernel_immediate"
    assert route.max_latency_budget_ms <= 1000.0
