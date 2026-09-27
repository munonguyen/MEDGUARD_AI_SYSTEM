"""Adaptive Complexity Router for MedGuard AI System.

Implements 5-Level Adaptive Compute (C0 to C4) according to SOTA 2025-2026 specs:
- C0 (Conversational / Greeting)       -> Direct / Lightweight Generator (~0.5s)
- C1 (Single Clinical Question)        -> Single Retrieval + Reasoning Agent (~1.5s)
- C2 (Multi-intent / Co-occurrence)    -> Question Decomposition + Multi-Retriever (~3.0s)
- C3 (Multi-hop Clinical Reasoning)    -> Dual-Agent (Writer vs Verifier) with Jev Arbiter (~5.0s)
- C4 (High-risk / Clinical Emergency)  -> Safety Kernel Immediate Emergency Lock (~0.1s - 1.0s)

Guarantees 100% Zero-Cloud Cost:
All routing, decomposition, and retrieval planning runs strictly in-process with zero external billable services.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.models.intake import (
    CompiledClinicalIntake,
    ComplexityLevel,
    DecomposedQuestion,
)


@dataclass(frozen=True)
class PipelineRoute:
    level: ComplexityLevel
    pipeline_mode: Literal[
        "lightweight_direct",
        "single_rag_agent",
        "decomposed_multi_retriever",
        "dual_agent_arbiter",
        "safety_kernel_immediate",
    ]
    max_latency_budget_ms: float
    requires_question_decomposition: bool
    requires_dual_agent: bool
    requires_jev_arbitration: bool
    sub_questions: tuple[DecomposedQuestion, ...]
    rationale: str

    @property
    def complexity_level(self) -> ComplexityLevel:
        return self.level



class ComplexityRouter:
    """Evaluates compiled clinical intake and assigns optimal compute tier."""

    @staticmethod
    def route(intake: CompiledClinicalIntake) -> PipelineRoute:
        """Assign computational resources and execution strategy based on intake complexity."""
        level = intake.complexity_level
        sub_qs = tuple(intake.decomposed_questions)

        if level == "C4":
            return PipelineRoute(
                level="C4",
                pipeline_mode="safety_kernel_immediate",
                max_latency_budget_ms=1000.0,
                requires_question_decomposition=False,
                requires_dual_agent=True,
                requires_jev_arbitration=True,
                sub_questions=sub_qs,
                rationale="Phát hiện cờ đỏ đe dọa sinh mạng: Ưu tiên kích hoạt Safety Kernel khóa 115 lập tức, sau đó Dual-Agent làm rõ hỗ trợ sơ cứu.",
            )

        if level == "C0":
            return PipelineRoute(
                level="C0",
                pipeline_mode="lightweight_direct",
                max_latency_budget_ms=500.0,
                requires_question_decomposition=False,
                requires_dual_agent=False,
                requires_jev_arbitration=False,
                sub_questions=(),
                rationale="Câu hỏi giao tiếp chào hỏi cơ bản: Phản hồi nhanh trực tiếp, không kích hoạt cụm RAG nặng.",
            )

        if level == "C1":
            return PipelineRoute(
                level="C1",
                pipeline_mode="single_rag_agent",
                max_latency_budget_ms=1500.0,
                requires_question_decomposition=False,
                requires_dual_agent=False,
                requires_jev_arbitration=False,
                sub_questions=sub_qs[:1],
                rationale="Câu hỏi y khoa đơn điểm: Kích hoạt Single RAG Agent truy xuất tài liệu chuyên khoa tương ứng.",
            )

        if level == "C3":
            return PipelineRoute(
                level="C3",
                pipeline_mode="dual_agent_arbiter",
                max_latency_budget_ms=6000.0,
                requires_question_decomposition=True,
                requires_dual_agent=True,
                requires_jev_arbitration=True,
                sub_questions=sub_qs,
                rationale="Câu hỏi đa bước phức tạp (đa bệnh nền, đa dược chất, đối tượng nguy cơ): Kích hoạt Dual-Agent (Writer & Verifier) và Jev làm Trọng tài vi mô chấm điểm.",
            )

        # Default C2: Multi-intent / Co-occurrence
        return PipelineRoute(
            level="C2",
            pipeline_mode="decomposed_multi_retriever",
            max_latency_budget_ms=4000.0,
            requires_question_decomposition=True,
            requires_dual_agent=True,
            requires_jev_arbitration=True,
            sub_questions=sub_qs,
            rationale="Câu hỏi đa ý phối hợp: Phân rã câu hỏi (Question Decomposition) thành các truy vấn con, chạy Multi-Retriever song song và dùng Jev thẩm định.",
        )
