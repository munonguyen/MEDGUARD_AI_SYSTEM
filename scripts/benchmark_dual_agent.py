#!/usr/bin/env python3
"""Benchmark evaluation script for Dual-Agent (Writer + Verifier) Architecture.

Evaluates all 120 cases in datasets/DS-DUAL-AGENT-TRAINING/dataset.json across 8 groups:
  1. WRITER_CLINICAL (20 cases)
  2. WRITER_PHARMA (15 cases)
  3. VERIFIER_APPROVE (15 cases)
  4. VERIFIER_REJECT (10 cases)
  5. GATE_EDGE_CASES (15 cases)
  6. LANGUAGE_VARIANTS (15 cases)
  7. MULTI_TURN (15 cases)
  8. ADVERSARIAL_BOUNDARY (15 cases)

Usage:
    .venv/bin/python scripts/benchmark_dual_agent.py
"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import json
from pathlib import Path
import sys
import time
from typing import Any

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.models.agents import AgentDraft, AgentEvidenceClaim, AgentVerification  # noqa: E402
from app.models.chat import AnswerNarrativeBlock, GroundedAnswer  # noqa: E402
from app.services.agent_provider import ProviderResult  # noqa: E402
from app.services.answer_agents import (  # noqa: E402
    AnswerAgentConfig,
    AnswerAgentPipeline,
    _claims,
    _gate_reason,
)
from app.services.circuit import CircuitBreaker  # noqa: E402
from app.services.knowledge_retriever import resolve_domain  # noqa: E402
from app.services.ood_guard import evaluate  # noqa: E402

client = TestClient(app)

DATASET_PATH = PROJECT_ROOT / "datasets" / "DS-DUAL-AGENT-TRAINING" / "dataset.json"
REPORT_PATH = PROJECT_ROOT / "datasets" / "DS-DUAL-AGENT-TRAINING" / "eval_report.json"

TRUSTED_NICE_URL = "https://www.nice.org.uk/guidance/cg150/chapter/recommendations"
TRUSTED_WHO_URL = "https://www.who.int/news-room/fact-sheets/detail/headache-disorders"
TRUSTED_FDA_URL = "https://www.fda.gov/drugs/drug-safety-and-availability"


class MockBenchmarkProvider:
    def __init__(self, name: str, data: Any, citations=(), queries=()) -> None:
        self.provider_name = name
        self.data = data
        self.citations = tuple(citations)
        self.queries = tuple(queries)
        self.calls: list[dict[str, Any]] = []

    @property
    def is_configured(self) -> bool:
        return True

    def complete(self, **values: Any) -> ProviderResult:
        self.calls.append(values)
        return ProviderResult(
            data=self.data,
            response_id=f"{self.provider_name}-bench",
            model=values.get("model", "benchmark-model"),
            latency_ms=8,
            citations=self.citations,
            search_queries=self.queries,
        )


def _headers(key: str) -> dict[str, str]:
    return {
        "X-API-Key": "demo-key",
        "X-Tenant-Id": "tenant-demo",
        "Idempotency-Key": key,
        "X-Consent-Token": "consent-eval",
    }


def _make_benchmark_draft(*, locked_action: str = "Theo dõi triệu chứng và nghỉ ngơi.") -> AgentDraft:
    return AgentDraft.model_validate(
        {
            "question_analysis": {
                "interpreted_request": "Đánh giá triệu chứng và dấu hiệu cảnh báo.",
                "key_questions": ["Có dấu hiệu cấp cứu không?"],
                "ambiguities": ["Chưa rõ thời điểm khởi phát"],
                "risk_level": "medium",
            },
            "evidence_claims": [
                {
                    "claim_id": "ext_guideline",
                    "text": "Khuyến nghị đánh giá dấu hiệu cảnh báo theo guideline.",
                    "source_ids": ["src_nice"],
                }
            ],
            "narrative": [
                {
                    "kind": "paragraph",
                    "text": "Đánh giá hiện tại. Chưa đủ dữ kiện để xác định nguyên nhân. Khuyến nghị đánh giá dấu hiệu cảnh báo theo guideline.",
                    "emphasis": ["Đánh giá hiện tại"],
                    "claim_ids": ["title_1", "summary_2", "ext_guideline"],
                    "source_ids": ["src_nice"],
                },
                {
                    "kind": "caution",
                    "text": f"Dấu hiệu được nhận diện: đau đầu {locked_action} Đi cấp cứu ngay nếu đau đột ngột dữ dội. Cơn đau bắt đầu từ lúc nào?",
                    "emphasis": ["Đi cấp cứu ngay nếu đau đột ngột dữ dội."],
                    "claim_ids": ["finding_3", "action_4", "safety_5", "question_6"],
                    "source_ids": ["src_nice"],
                },
            ],
            "sources": [
                {
                    "source_id": "src_nice",
                    "title": "Headache guidance",
                    "publisher": "NICE",
                    "url": TRUSTED_NICE_URL,
                    "authority_tier": "guideline_or_regulator",
                    "supports_claim_ids": [
                        "title_1",
                        "summary_2",
                        "finding_3",
                        "action_4",
                        "safety_5",
                        "question_6",
                        "ext_guideline",
                    ],
                }
            ],
            "notes": "Guideline chính thống.",
        }
    )


def _make_benchmark_verification(*, approved: bool = True, **kwargs) -> AgentVerification:
    scores = {
        "grounding": 0.98,
        "safety": 0.99,
        "completeness": 0.96,
        "clarity": 0.95,
        "citation_coverage": 0.98,
    }
    if "grounding" in kwargs:
        scores["grounding"] = kwargs.pop("grounding")
    if "safety" in kwargs:
        scores["safety"] = kwargs.pop("safety")
    if "completeness" in kwargs:
        scores["completeness"] = kwargs.pop("completeness")
    if "citation_coverage" in kwargs:
        scores["citation_coverage"] = kwargs.pop("citation_coverage")

    data = {
        "approved": approved,
        "scores": scores,
        "issues": [] if approved else ["Không đạt tiêu chuẩn y khoa an toàn"],
        "missing_claim_ids": kwargs.get("missing_claim_ids", []),
        "unsupported_claims": kwargs.get("unsupported_claims", []),
        "source_issues": kwargs.get("source_issues", []),
        "summary": "Đạt" if approved else "Từ chối",
    }
    return AgentVerification.model_validate(data)


def _benchmark_pipeline(
    draft: AgentDraft,
    report: AgentVerification,
    circuit_threshold: float = 0.5,
    min_requests: int = 1,
) -> AnswerAgentPipeline:
    res_p = MockBenchmarkProvider("research-p", draft, citations=(TRUSTED_NICE_URL,), queries=("guideline",))
    ver_p = MockBenchmarkProvider("verifier-p", report, citations=(TRUSTED_NICE_URL,), queries=("verify guideline",))
    cfg = AnswerAgentConfig(
        mode="enforced",
        research_model="test-res",
        verifier_model="test-ver",
        min_grounding=0.90,
        min_safety=0.95,
        min_completeness=0.85,
        min_citation_coverage=0.90,
    )
    return AnswerAgentPipeline(
        config=cfg,
        research_provider=res_p,
        verifier_provider=ver_p,
        circuit=CircuitBreaker(error_threshold=circuit_threshold, min_requests=min_requests),
    )


def _evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    case_id = case["case_id"]
    group = case["group"]
    sub_category = case.get("sub_category", "")
    t0 = time.perf_counter()

    passed = True
    failures: list[str] = []
    details: dict[str, Any] = {}

    # -------------------------------------------------------------
    # 1. WRITER_CLINICAL
    # -------------------------------------------------------------
    if group == "WRITER_CLINICAL":
        text = case["input"]
        resp = client.post(
            "/v1/chat",
            headers=_headers(f"eval-{case_id}"),
            json={
                "conversation_id": f"conv-{case_id}",
                "messages": [{"role": "user", "content": text}],
            },
        )
        body = resp.json()
        details["http_status"] = resp.status_code
        details["intent"] = body.get("intent")
        urgency = (body.get("result") or {}).get("urgency")
        details["urgency"] = urgency

        domain = resolve_domain(body.get("intent"), text)
        details["domain"] = domain

        if resp.status_code != 200:
            passed = False
            failures.append(f"HTTP status {resp.status_code}")
        if domain != "clinical":
            passed = False
            failures.append(f"Expected clinical domain, got {domain}")
        if case.get("expected_intent") and body.get("intent") != case["expected_intent"]:
            passed = False
            failures.append(f"Expected intent={case['expected_intent']}, got {body.get('intent')}")
        if case.get("expected_urgency") and urgency != case["expected_urgency"]:
            passed = False
            failures.append(f"Expected urgency={case['expected_urgency']}, got {urgency}")

    # -------------------------------------------------------------
    # 2. WRITER_PHARMA
    # -------------------------------------------------------------
    elif group == "WRITER_PHARMA":
        text = case["input"]
        resp = client.post(
            "/v1/chat",
            headers=_headers(f"eval-{case_id}"),
            json={
                "conversation_id": f"conv-{case_id}",
                "messages": [{"role": "user", "content": text}],
            },
        )
        body = resp.json()
        details["http_status"] = resp.status_code
        details["intent"] = body.get("intent")
        domain = resolve_domain(body.get("intent"), text)
        details["domain"] = domain

        if resp.status_code != 200:
            passed = False
            failures.append(f"HTTP status {resp.status_code}")
        if domain != "pharmacology":
            passed = False
            failures.append(f"Expected pharmacology domain, got {domain}")
        if body.get("intent") != case.get("expected_intent", "safety"):
            passed = False
            failures.append(f"Expected intent={case.get('expected_intent')}, got {body.get('intent')}")

    # -------------------------------------------------------------
    # 3. VERIFIER_APPROVE
    # -------------------------------------------------------------
    elif group == "VERIFIER_APPROVE":
        draft = _make_benchmark_draft()
        verif = _make_benchmark_verification(approved=True)
        pipe = _benchmark_pipeline(draft, verif)
        ans = GroundedAnswer(
            title="Đánh giá hiện tại",
            summary="Chưa đủ dữ kiện để xác định nguyên nhân.",
            key_points=["Dấu hiệu được nhận diện: đau đầu"],
            next_steps=["Theo dõi triệu chứng và nghỉ ngơi."],
            safety_notes=["Đi cấp cứu ngay nếu đau đột ngột dữ dội."],
            questions=["Cơn đau bắt đầu từ lúc nào?"],
            decision_basis="versioned_rules",
            evidence_state="direct_rule_match",
            narrative=[AnswerNarrativeBlock(text="Bản deterministic.")],
        )
        res = pipe.enhance(answer=ans, intent="triage", question=case["input"], request_id=f"req-{case_id}")
        details["status"] = res.agent_trace.status
        details["fallback_reason"] = res.agent_trace.fallback_reason

        if res.agent_trace.status != "verified":
            passed = False
            failures.append(f"Expected status=verified, got {res.agent_trace.status} (reason: {res.agent_trace.fallback_reason})")
        if res.agent_trace.fallback_reason is not None:
            passed = False
            failures.append(f"Expected no fallback reason, got {res.agent_trace.fallback_reason}")

    # -------------------------------------------------------------
    # 4. VERIFIER_REJECT
    # -------------------------------------------------------------
    elif group == "VERIFIER_REJECT":
        # Verifier rejects the unsafe draft
        draft = _make_benchmark_draft(locked_action="Bạn có thể tự ý dùng thuốc liều cao.")
        verif = _make_benchmark_verification(approved=False)
        pipe = _benchmark_pipeline(draft, verif)
        ans = GroundedAnswer(
            title="Đánh giá hiện tại",
            summary="Chưa đủ dữ kiện để xác định nguyên nhân.",
            key_points=["Dấu hiệu được nhận diện: đau đầu"],
            next_steps=["Theo dõi triệu chứng và nghỉ ngơi."],
            safety_notes=["Đi cấp cứu ngay nếu đau đột ngột dữ dội."],
            questions=["Cơn đau bắt đầu từ lúc nào?"],
            decision_basis="versioned_rules",
            evidence_state="direct_rule_match",
            narrative=[AnswerNarrativeBlock(text="Bản deterministic.")],
        )
        res = pipe.enhance(answer=ans, intent="triage", question=case["input"], request_id=f"req-{case_id}")
        details["status"] = res.agent_trace.status
        details["fallback_reason"] = res.agent_trace.fallback_reason

        if res.agent_trace.status != "rejected":
            passed = False
            failures.append(f"Expected status=rejected, got {res.agent_trace.status}")

    # -------------------------------------------------------------
    # 5. GATE_EDGE_CASES
    # -------------------------------------------------------------
    elif group == "GATE_EDGE_CASES":
        gate_test = case.get("expected_gate_test")
        ans = GroundedAnswer(
            title="Đánh giá hiện tại",
            summary="Chưa đủ dữ kiện để xác định nguyên nhân.",
            key_points=["Dấu hiệu được nhận diện: đau đầu"],
            next_steps=["Theo dõi triệu chứng và nghỉ ngơi."],
            safety_notes=["Đi cấp cứu ngay nếu đau đột ngột dữ dội."],
            questions=["Cơn đau bắt đầu từ lúc nào?"],
            decision_basis="versioned_rules",
            evidence_state="direct_rule_match",
            narrative=[AnswerNarrativeBlock(text="Bản deterministic.")],
        )
        claims = _claims(ans, "triage")
        cfg = AnswerAgentConfig(
            mode="enforced",
            research_model="m1",
            verifier_model="m2",
            min_grounding=0.90,
            min_safety=0.95,
            min_completeness=0.85,
            min_citation_coverage=0.90,
        )

        draft = _make_benchmark_draft()
        verif = _make_benchmark_verification(approved=True)

        if gate_test == "emphasis_sanitized":
            draft.narrative[0].emphasis = ["Đánh giá hiện tại", "Cụm từ hallucinated không có trong text"]
            reason = _gate_reason(
                draft=draft,
                verification=verif,
                claims=claims,
                provider_citations=(TRUSTED_NICE_URL,),
                provider_queries=("q",),
                verifier_citations=(TRUSTED_NICE_URL,),
                retrieved_source_urls=(),
                config=cfg,
            )
            passed = (reason is None) and (draft.narrative[0].emphasis == ["Đánh giá hiện tại"])
            details["detected_reason"] = reason
            if not passed:
                failures.append(f"Emphasis not sanitized properly: reason={reason}, emphasis={draft.narrative[0].emphasis}")

        elif gate_test == "markup_blocked":
            draft.narrative[0].text += " <script>alert(1)</script>"
            reason = _gate_reason(
                draft=draft,
                verification=verif,
                claims=claims,
                provider_citations=(TRUSTED_NICE_URL,),
                provider_queries=("q",),
                verifier_citations=(TRUSTED_NICE_URL,),
                retrieved_source_urls=(),
                config=cfg,
            )
            passed = (reason == "markup_not_allowed")
            details["detected_reason"] = reason
            if not passed:
                failures.append(f"Expected markup_not_allowed, got {reason}")

        elif gate_test == "duplicate_source_rejected":
            draft.sources.append(deepcopy(draft.sources[0]))
            reason = _gate_reason(
                draft=draft,
                verification=verif,
                claims=claims,
                provider_citations=(TRUSTED_NICE_URL,),
                provider_queries=("q",),
                verifier_citations=(TRUSTED_NICE_URL,),
                retrieved_source_urls=(),
                config=cfg,
            )
            passed = (reason == "duplicate_source_id")
            details["detected_reason"] = reason
            if not passed:
                failures.append(f"Expected duplicate_source_id, got {reason}")

        elif gate_test == "duplicate_evidence_claim_rejected":
            draft.evidence_claims.append(deepcopy(draft.evidence_claims[0]))
            reason = _gate_reason(
                draft=draft,
                verification=verif,
                claims=claims,
                provider_citations=(TRUSTED_NICE_URL,),
                provider_queries=("q",),
                verifier_citations=(TRUSTED_NICE_URL,),
                retrieved_source_urls=(),
                config=cfg,
            )
            passed = (reason == "duplicate_evidence_claim_id")
            details["detected_reason"] = reason
            if not passed:
                failures.append(f"Expected duplicate_evidence_claim_id, got {reason}")

        elif gate_test == "unknown_claim_reference":
            draft.narrative[0].claim_ids.append("claim_unknown_xyz")
            reason = _gate_reason(
                draft=draft,
                verification=verif,
                claims=claims,
                provider_citations=(TRUSTED_NICE_URL,),
                provider_queries=("q",),
                verifier_citations=(TRUSTED_NICE_URL,),
                retrieved_source_urls=(),
                config=cfg,
            )
            passed = (reason == "unknown_claim_reference")
            details["detected_reason"] = reason
            if not passed:
                failures.append(f"Expected unknown_claim_reference, got {reason}")

        elif gate_test == "untrusted_source_domain":
            untrusted_url = "https://untrusted-blog.xyz/health"
            draft.sources[0].url = untrusted_url
            reason = _gate_reason(
                draft=draft,
                verification=verif,
                claims=claims,
                provider_citations=(untrusted_url,),
                provider_queries=("q",),
                verifier_citations=(TRUSTED_NICE_URL,),
                retrieved_source_urls=(),
                config=cfg,
            )
            passed = (reason == "untrusted_source_domain")
            details["detected_reason"] = reason
            if not passed:
                failures.append(f"Expected untrusted_source_domain, got {reason}")

        elif gate_test == "grounding_below_threshold":
            verif = _make_benchmark_verification(approved=True, grounding=0.88)
            reason = _gate_reason(
                draft=draft,
                verification=verif,
                claims=claims,
                provider_citations=(TRUSTED_NICE_URL,),
                provider_queries=("q",),
                verifier_citations=(TRUSTED_NICE_URL,),
                retrieved_source_urls=(),
                config=cfg,
            )
            passed = (reason == "grounding_below_threshold")
            details["detected_reason"] = reason
            if not passed:
                failures.append(f"Expected grounding_below_threshold, got {reason}")

        elif gate_test == "safety_below_threshold":
            verif = _make_benchmark_verification(approved=True, safety=0.92)
            reason = _gate_reason(
                draft=draft,
                verification=verif,
                claims=claims,
                provider_citations=(TRUSTED_NICE_URL,),
                provider_queries=("q",),
                verifier_citations=(TRUSTED_NICE_URL,),
                retrieved_source_urls=(),
                config=cfg,
            )
            passed = (reason == "safety_below_threshold")
            details["detected_reason"] = reason
            if not passed:
                failures.append(f"Expected safety_below_threshold, got {reason}")

        elif gate_test == "completeness_below_threshold":
            verif = _make_benchmark_verification(approved=True, completeness=0.80)
            reason = _gate_reason(
                draft=draft,
                verification=verif,
                claims=claims,
                provider_citations=(TRUSTED_NICE_URL,),
                provider_queries=("q",),
                verifier_citations=(TRUSTED_NICE_URL,),
                retrieved_source_urls=(),
                config=cfg,
            )
            passed = (reason == "completeness_below_threshold")
            details["detected_reason"] = reason
            if not passed:
                failures.append(f"Expected completeness_below_threshold, got {reason}")

        elif gate_test == "citation_coverage_below_threshold":
            verif = _make_benchmark_verification(approved=True, citation_coverage=0.85)
            reason = _gate_reason(
                draft=draft,
                verification=verif,
                claims=claims,
                provider_citations=(TRUSTED_NICE_URL,),
                provider_queries=("q",),
                verifier_citations=(TRUSTED_NICE_URL,),
                retrieved_source_urls=(),
                config=cfg,
            )
            passed = (reason == "citation_coverage_below_threshold")
            details["detected_reason"] = reason
            if not passed:
                failures.append(f"Expected citation_coverage_below_threshold, got {reason}")

        elif gate_test == "locked_claim_changed":
            draft.narrative[1].text = "Dấu hiệu nhận diện: đau đầu. Hãy tự nghỉ ngơi thư giãn tại nhà."
            reason = _gate_reason(
                draft=draft,
                verification=verif,
                claims=claims,
                provider_citations=(TRUSTED_NICE_URL,),
                provider_queries=("q",),
                verifier_citations=(TRUSTED_NICE_URL,),
                retrieved_source_urls=(),
                config=cfg,
            )
            passed = (reason == "locked_claim_changed")
            details["detected_reason"] = reason
            if not passed:
                failures.append(f"Expected locked_claim_changed, got {reason}")

        elif gate_test == "unused_evidence_claim":
            extra = AgentEvidenceClaim(claim_id="ext_unused", text="Thừa một claim", source_ids=["src_nice"])
            draft.evidence_claims.append(extra)
            draft.sources[0].supports_claim_ids.append("ext_unused")
            reason = _gate_reason(
                draft=draft,
                verification=verif,
                claims=claims,
                provider_citations=(TRUSTED_NICE_URL,),
                provider_queries=("q",),
                verifier_citations=(TRUSTED_NICE_URL,),
                retrieved_source_urls=(),
                config=cfg,
            )
            passed = (reason == "unused_evidence_claim")
            details["detected_reason"] = reason
            if not passed:
                failures.append(f"Expected unused_evidence_claim, got {reason}")

        elif gate_test == "source_claim_link_mismatch":
            draft.sources[0].supports_claim_ids.remove("ext_guideline")
            reason = _gate_reason(
                draft=draft,
                verification=verif,
                claims=claims,
                provider_citations=(TRUSTED_NICE_URL,),
                provider_queries=("q",),
                verifier_citations=(TRUSTED_NICE_URL,),
                retrieved_source_urls=(),
                config=cfg,
            )
            passed = (reason in ("narrative_claim_source_mismatch", "source_claim_link_mismatch"))
            details["detected_reason"] = reason
            if not passed:
                failures.append(f"Expected claim source link mismatch, got {reason}")

        elif gate_test == "verifier_reported_source_issues":
            verif = _make_benchmark_verification(approved=False, source_issues=["Nguồn không hợp lệ"])
            reason = _gate_reason(
                draft=draft,
                verification=verif,
                claims=claims,
                provider_citations=(TRUSTED_NICE_URL,),
                provider_queries=("q",),
                verifier_citations=(TRUSTED_NICE_URL,),
                retrieved_source_urls=(),
                config=cfg,
            )
            passed = (reason == "verifier_reported_source_issues")
            details["detected_reason"] = reason
            if not passed:
                failures.append(f"Expected verifier_reported_source_issues, got {reason}")

        elif gate_test == "circuit_open":
            pipe = _benchmark_pipeline(draft, verif, circuit_threshold=0.5, min_requests=1)
            pipe.circuit.record_failure()
            res = pipe.enhance(answer=ans, intent="triage", question="đau đầu", request_id=f"req-{case_id}")
            passed = (res.agent_trace.status == "circuit_open" and res.agent_trace.fallback_reason == "model_circuit_open")
            details["detected_reason"] = res.agent_trace.fallback_reason
            if not passed:
                failures.append(f"Expected circuit open rejection, got status={res.agent_trace.status}, reason={res.agent_trace.fallback_reason}")

    # -------------------------------------------------------------
    # 6. LANGUAGE_VARIANTS
    # -------------------------------------------------------------
    elif group == "LANGUAGE_VARIANTS":
        text = case["input"]
        resp = client.post(
            "/v1/chat",
            headers=_headers(f"eval-{case_id}"),
            json={
                "conversation_id": f"conv-{case_id}",
                "messages": [{"role": "user", "content": text}],
            },
        )
        body = resp.json()
        details["http_status"] = resp.status_code
        details["intent"] = body.get("intent")
        urgency = (body.get("result") or {}).get("urgency")
        details["urgency"] = urgency

        if resp.status_code != 200:
            passed = False
            failures.append(f"HTTP status {resp.status_code}")
        if body.get("intent") != case.get("expected_intent"):
            passed = False
            failures.append(f"Expected intent={case.get('expected_intent')}, got {body.get('intent')}")
        if case.get("expected_urgency") and urgency != case["expected_urgency"]:
            passed = False
            failures.append(f"Expected urgency={case['expected_urgency']}, got {urgency}")

    # -------------------------------------------------------------
    # 7. MULTI_TURN
    # -------------------------------------------------------------
    elif group == "MULTI_TURN":
        turns: list[str] = case["input"] if isinstance(case["input"], list) else [case["input"]]
        expected_intents: list[str] = case.get("expected_intent_sequence", [])
        actual_intents: list[str] = []

        history: list[dict[str, str]] = []
        conv_id = f"conv-mt-{case_id}"

        for idx, user_text in enumerate(turns):
            history.append({"role": "user", "content": user_text})
            resp = client.post(
                "/v1/chat",
                headers=_headers(f"eval-{case_id}-t{idx}"),
                json={"conversation_id": conv_id, "messages": history},
            )
            body = resp.json()
            intent = body.get("intent", "")
            actual_intents.append(intent)
            reply = body.get("reply", "")
            history.append({"role": "assistant", "content": reply})

        details["actual_intent_sequence"] = actual_intents
        details["expected_intent_sequence"] = expected_intents

        if actual_intents != expected_intents:
            passed = False
            failures.append(f"Intent sequence mismatch: expected {expected_intents}, got {actual_intents}")

    # -------------------------------------------------------------
    # 8. ADVERSARIAL_BOUNDARY
    # -------------------------------------------------------------
    elif group == "ADVERSARIAL_BOUNDARY":
        text = case["input"]
        expected_verdict = case.get("expected_ood_verdict")
        ood_res = evaluate(text)
        actual_verdict = ood_res.verdict if ood_res else None

        details["actual_ood_verdict"] = actual_verdict
        details["expected_ood_verdict"] = expected_verdict

        if actual_verdict != expected_verdict:
            passed = False
            failures.append(f"OOD verdict mismatch: expected {expected_verdict}, got {actual_verdict}")

        # Also verify /v1/chat returns 200 without crashing
        resp = client.post(
            "/v1/chat",
            headers=_headers(f"eval-{case_id}"),
            json={"conversation_id": f"conv-{case_id}", "messages": [{"role": "user", "content": text}]},
        )
        if resp.status_code != 200:
            passed = False
            failures.append(f"Chat endpoint crashed with status {resp.status_code}")

    latency_ms = round((time.perf_counter() - t0) * 1000, 1)

    return {
        "case_id": case_id,
        "group": group,
        "sub_category": sub_category,
        "description": case.get("description", ""),
        "passed": passed,
        "failures": failures,
        "latency_ms": latency_ms,
        "details": details,
    }


def main() -> None:
    if not DATASET_PATH.exists():
        print(f"Error: Dataset not found at {DATASET_PATH}")
        sys.exit(1)

    with open(DATASET_PATH, encoding="utf-8") as f:
        dataset = json.load(f)

    cases = dataset["cases"]
    print(f"\n{'='*76}")
    print(f"  MedGuard AI — Dual-Agent Architecture Benchmark Evaluation")
    print(f"  Dataset: {DATASET_PATH.name}  |  Total Cases: {len(cases)}")
    print(f"{'='*76}\n")

    results: list[dict[str, Any]] = []
    group_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"total": 0, "passed": 0, "failed": 0, "latencies": []}
    )

    t_start = time.perf_counter()

    for idx, case in enumerate(cases, 1):
        res = _evaluate_case(case)
        results.append(res)
        g = res["group"]
        group_stats[g]["total"] += 1
        group_stats[g]["latencies"].append(res["latency_ms"])
        if res["passed"]:
            group_stats[g]["passed"] += 1
        else:
            group_stats[g]["failed"] += 1

        status_sym = "✅" if res["passed"] else "❌"
        print(f"  [{idx:3d}/{len(cases):3d}] {status_sym} {case['case_id']} ({g:<20}) {res['latency_ms']:>6.1f}ms")

    total_time = round(time.perf_counter() - t_start, 2)
    total_cases = len(results)
    total_passed = sum(1 for r in results if r["passed"])
    total_failed = total_cases - total_passed
    overall_acc = (total_passed / total_cases * 100) if total_cases else 0

    print(f"\n{'─'*76}")
    print(f"  {'Group':<22} {'Total':>6} {'Pass':>6} {'Fail':>6} {'Avg Latency':>13} {'Accuracy':>10}")
    print(f"{'─'*76}")

    group_order = [
        "WRITER_CLINICAL",
        "WRITER_PHARMA",
        "VERIFIER_APPROVE",
        "VERIFIER_REJECT",
        "GATE_EDGE_CASES",
        "LANGUAGE_VARIANTS",
        "MULTI_TURN",
        "ADVERSARIAL_BOUNDARY",
    ]

    for g in group_order:
        st = group_stats[g]
        acc = (st["passed"] / st["total"] * 100) if st["total"] else 0
        avg_lat = sum(st["latencies"]) / len(st["latencies"]) if st["latencies"] else 0
        mark = "✅" if st["failed"] == 0 else "❌"
        print(f"  {mark} {g:<20} {st['total']:>6} {st['passed']:>6} {st['failed']:>6} {avg_lat:>10.1f}ms {acc:>9.1f}%")

    print(f"{'─'*76}")
    overall_mark = "🎯" if total_failed == 0 else "⚠️"
    print(f"  {overall_mark} {'OVERALL':<20} {total_cases:>6} {total_passed:>6} {total_failed:>6} {'-':>12} {overall_acc:>9.1f}%")
    print(f"  Total Execution Time: {total_time}s")
    print(f"{'─'*76}\n")

    # Failed cases report
    failed_cases = [r for r in results if not r["passed"]]
    if failed_cases:
        print(f"  ❌ FAILED CASES ({len(failed_cases)}):")
        print(f"{'─'*76}")
        for r in failed_cases:
            print(f"  [{r['case_id']}] {r['group']} / {r['sub_category']}: {r['description']}")
            for f in r["failures"]:
                print(f"      → {f}")
        print()
    else:
        print("  🎉 ALL 120 DUAL-AGENT BENCHMARK CASES PASSED PERFECTLY!\n")

    # Save evaluation report
    report_data = {
        "dataset": "DS-DUAL-AGENT-TRAINING",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
        "total_cases": total_cases,
        "passed": total_passed,
        "failed": total_failed,
        "accuracy": round(overall_acc, 2),
        "total_time_seconds": total_time,
        "group_summary": {
            g: {
                "total": group_stats[g]["total"],
                "passed": group_stats[g]["passed"],
                "failed": group_stats[g]["failed"],
                "accuracy": round((group_stats[g]["passed"] / group_stats[g]["total"] * 100), 1),
                "avg_latency_ms": round(sum(group_stats[g]["latencies"]) / len(group_stats[g]["latencies"]), 1),
            }
            for g in group_order
        },
        "results": results,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    print(f"  Saved evaluation report to: {REPORT_PATH}\n")


if __name__ == "__main__":
    main()
