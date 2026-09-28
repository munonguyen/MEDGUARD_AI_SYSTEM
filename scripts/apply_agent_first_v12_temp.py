from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, found {count}: {old[:100]!r}")
    write(path, text.replace(old, new, 1))


def regex_once(path: str, pattern: str, replacement: str) -> None:
    text = read(path)
    updated, count = re.subn(pattern, lambda _: replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{path}: regex expected one match, found {count}: {pattern[:100]!r}")
    write(path, updated)


# ---------------------------------------------------------------------------
# 1) Clinical envelope / communication contract. This is NOT a response
# template. It is structured input + immutable safety constraints for agents.
# ---------------------------------------------------------------------------
write(
    "app/services/clinical_agent_contract.py",
    '''"""Structured clinical contract for the V12 agent-first response path.

The deterministic stack owns facts, safety floors, red flags and tool results.
The agent stack owns clinical explanation and patient-facing prose.  This module
bridges the two without passing legacy deterministic prose to the writer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.chat import ChatIntent


@dataclass(frozen=True)
class ClinicalAgentContract:
    envelope: dict[str, Any]
    claims: list[dict[str, Any]]


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _safe_patient_context(context: dict[str, Any] | None) -> dict[str, Any]:
    source = context or {}
    # Patient identifiers and previous generated answer state must never become
    # medical evidence for the writer.
    allowed = ("age", "sex", "current_medications", "allergies", "conditions")
    return {key: source.get(key) for key in allowed if source.get(key) not in (None, [], "")}


def _questions(result: dict[str, Any]) -> list[str]:
    values = result.get("clarifying_questions") or result.get("guidance_questions") or []
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()][:3]


def build_clinical_agent_contract(
    *,
    intent: ChatIntent,
    question: str,
    clinical_result: dict[str, Any] | None,
    patient_context: dict[str, Any] | None = None,
) -> ClinicalAgentContract:
    result = dict(clinical_result or {})
    claims: list[dict[str, Any]] = []

    def add(category: str, text: str, *, required: bool = True, locked: bool = False) -> None:
        value = text.strip()
        if not value:
            return
        claims.append(
            {
                "id": f"{category}_{len(claims) + 1}",
                "category": category,
                "text": value,
                "required": required,
                "locked": locked,
            }
        )

    urgency = _text(result.get("urgency") or result.get("escalation_level") or "ROUTINE").upper()
    if intent == "triage":
        add("summary", f"Mức xử trí tối thiểu đã được hệ thống an toàn xác định: {urgency}.")

        specialty = result.get("recommended_specialty")
        if isinstance(specialty, dict):
            label = _text(specialty.get("label"))
            if label:
                add("finding", f"Hướng chuyên khoa hiện tại: {label}.", required=False)

        red_flags = result.get("red_flags") or []
        if isinstance(red_flags, list):
            for flag in red_flags[:6]:
                add("finding", f"Dấu hiệu đã được xác nhận từ bệnh cảnh hiện tại: {_text(flag)}.")

        if urgency == "EMERGENCY" or bool(result.get("emergency_flag")):
            # This is a safety constraint, not a response template. The writer
            # may explain around it but must preserve the immediate action.
            add(
                "action",
                "Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức; không tự lái xe và không trì hoãn để tiếp tục hỏi trực tuyến.",
                locked=True,
            )
            add(
                "safety",
                "Không được hạ mức xử trí cấp cứu chỉ vì triệu chứng tạm thời giảm hoặc người bệnh muốn ở nhà theo dõi.",
                locked=False,
            )
        else:
            advice = _text(result.get("advice"))
            if advice:
                add("action", advice, required=False)

        for value in _questions(result):
            add("question", value, required=False)

    elif intent == "safety":
        risk = _text(result.get("overall_risk") or result.get("risk_level") or result.get("severity"))
        if risk:
            add("summary", f"Mức nguy cơ an toàn thuốc hiện tại: {risk}.")
        for key in ("warnings", "alerts", "recommendations", "actions"):
            values = result.get(key) or []
            if isinstance(values, list):
                for value in values[:6]:
                    if isinstance(value, dict):
                        message = _text(value.get("message") or value.get("text") or value.get("recommendation"))
                    else:
                        message = _text(value)
                    if message:
                        add("safety", message, required=True, locked=False)

    envelope = {
        "version": "v12-agent-first",
        "intent": intent,
        "user_question": question,
        "clinical_result": result,
        "patient_context": _safe_patient_context(patient_context),
        "communication_contract": {
            "compose_original_response": True,
            "legacy_template_prose_is_not_evidence": True,
            "directly_answer_main_concern_first": True,
            "detect_and_correct_dangerous_misconceptions": True,
            "explain_mechanism_in_plain_language_only_when_supported": True,
            "separate_assessment_from_diagnosis": True,
            "give_concrete_next_action": True,
            "avoid_generic_non_answers": True,
            "question_budget": 0 if urgency == "EMERGENCY" else 1,
            "emergency_action_precedes_explanation": urgency == "EMERGENCY",
        },
        # Derived from the supplied human doctor-response dataset as behavioral
        # principles only. They are not medical facts and never select canned
        # text by keyword.
        "professional_response_principles": [
            "Address the patient's actual concern before background explanation.",
            "If the patient proposes a dangerous action, interrupt and correct it before explaining why.",
            "Explain the clinical mechanism in everyday language only when the evidence supports it.",
            "Give a specific action plan and a clear threshold for seeking care.",
            "Ask only the single highest-information follow-up question when it can change management.",
            "Do not reuse fixed response templates or infer patient facts from rule antecedents.",
        ],
    }
    return ClinicalAgentContract(envelope=envelope, claims=claims)
''',
)

# ---------------------------------------------------------------------------
# 2) Agent prompts: writer is the primary clinical communicator, not an editor.
# ---------------------------------------------------------------------------
answer_agents = "app/services/answer_agents.py"
text = read(answer_agents)
text = text.replace(
    "from app.services.jury_evaluator import MedicalSafetyGate, QAGEvaluator\n",
    "from app.services.jury_evaluator import MedicalSafetyGate, QAGEvaluator\n"
    "from app.services.clinical_agent_contract import build_clinical_agent_contract\n",
    1,
)

clinical_prompt = '''_CLINICAL_RESEARCH_INSTRUCTIONS = """You are MedGuard's primary Clinical Reasoner and Patient Response Writer.
You are NOT editing a pre-written deterministic answer. Build the response from the supplied clinical envelope, bounded claims, current episode and retrieved evidence.

PROFESSIONAL CLINICAL COMMUNICATION RULES:
1. REASON BEFORE WRITING: identify the patient's real concern, current clinical pattern, uncertainty, safety implications and the single best next action. Do not map a keyword directly to canned prose.
2. DIRECTNESS: answer the practical concern in the first 1-2 sentences. Do not open routine cases with boilerplate such as 'thông tin hiện tại chưa cho thấy rõ dấu hiệu cấp cứu' or 'cần thêm đánh giá lâm sàng toàn diện'.
3. DANGEROUS MISCONCEPTIONS FIRST: if the patient proposes an unsafe action, clearly stop/correct that action before giving mechanism or background explanation.
4. CLINICAL HUMILITY: distinguish an assessment/pattern from a diagnosis. Never invent symptoms, diagnoses, medication history, rule antecedents or examination findings that the user did not provide.
5. ACTIONABILITY: give concrete, situation-specific next steps. Avoid generic advice that would fit almost any symptom.
6. SAFETY: obey locked safety claims exactly. Emergency action comes before explanation and never waits for additional questions.
7. FOLLOW-UP: ask at most one high-information question when it could materially change triage, disposition or the leading clinical interpretation. Do not re-ask facts already present in the envelope.
8. EXPLANATION: explain mechanisms in plain Vietnamese only when supported by supplied claims/evidence. Use a calm, confident professional tone without false certainty.
9. ORIGINAL COMPOSITION: do not copy fixed templates from memory or reconstruct legacy deterministic prose. The professional_response_principles are communication behavior, not medical evidence.
10. Produce normally 2-4 concise narrative blocks and no more than 260 words unless locked emergency content requires more. Each patient-specific medical claim must cite a supplied claim_id/source_id. All locked claims must appear verbatim. Return structured output only."""'''
text, count = re.subn(
    r'_CLINICAL_RESEARCH_INSTRUCTIONS = """.*?"""\n\n\n_CLINICAL_VERIFIER_INSTRUCTIONS',
    clinical_prompt + "\n\n\n_CLINICAL_VERIFIER_INSTRUCTIONS",
    text,
    count=1,
    flags=re.S,
)
if count != 1:
    raise RuntimeError("Could not replace clinical writer prompt")

verifier_prompt = '''_CLINICAL_VERIFIER_INSTRUCTIONS = """You are MedGuard's independent Clinical Quality Judge.
You do not write the patient answer and you do not perform a second diagnosis. Evaluate whether the Writer faithfully converted the supplied clinical envelope and evidence into a professional patient response.

JUDGE RULES:
1. FACT GROUNDING: reject invented symptoms, diagnoses, medication facts, examination findings, or rule antecedents not present in the envelope/evidence.
2. SAFETY CONSISTENCY: locked urgency/actions are non-negotiable; reject downgrade, delay, false reassurance or conflicting advice.
3. DIRECTNESS: reject generic non-answers and responses that fail to address the user's practical concern early.
4. ACTIONABILITY: reject an answer that gives explanation without a clear next action appropriate to the resolved care level.
5. UNCERTAINTY CALIBRATION: reject definitive diagnosis when only a pattern/possibility is supported; also reject meaningless boilerplate uncertainty.
6. QUESTION QUALITY: reject repeated/low-information questions; emergency responses must not block action with follow-up questions.
7. COMMUNICATION QUALITY: prefer calm, natural, doctor-like Vietnamese; reject internal system wording, triage implementation jargon and template leakage.
8. SOURCE ENTAILMENT: every cited source must directly support its associated claim; a trusted domain alone is not evidence.
9. INDEPENDENT SCORING: approval requires no unsupported claims/source issues/missing locked claims and grounding >= 0.90, safety >= 0.95, completeness >= 0.85, citation coverage >= 0.90.
10. When rejected, return concrete revision issues only. Do not rewrite the answer yourself. Return structured output only."""'''
text, count = re.subn(
    r'_CLINICAL_VERIFIER_INSTRUCTIONS = """.*?"""\n\n\n\n_PHARMA_RESEARCH_INSTRUCTIONS',
    verifier_prompt + "\n\n\n\n_PHARMA_RESEARCH_INSTRUCTIONS",
    text,
    count=1,
    flags=re.S,
)
if count != 1:
    raise RuntimeError("Could not replace clinical verifier prompt")

# One revision is the normal professional path; fail closed after that.
text = text.replace("    max_iterations: int = 0\n", "    max_iterations: int = 1\n", 1)
text = text.replace(
    '            max_iterations=getattr(settings, "agent_max_iterations", 0),\n',
    '            max_iterations=getattr(settings, "agent_max_iterations", 1),\n',
    1,
)

# _execute can consume a structured contract rather than prose-derived claims.
old_sig = '''        patient_context: dict[str, Any],\n        policy: AgentRequestPolicy,\n    ) -> GroundedAnswer:\n        domain = resolve_domain(intent, question)\n        claims = _claims(answer, intent)\n        tool_result = answer.model_dump(mode="json", exclude={"agent_trace"})\n'''
new_sig = '''        patient_context: dict[str, Any],\n        policy: AgentRequestPolicy,\n        claims_override: list[dict[str, Any]] | None = None,\n        tool_result_override: dict[str, Any] | None = None,\n    ) -> GroundedAnswer:\n        domain = resolve_domain(intent, question)\n        claims = claims_override if claims_override is not None else _claims(answer, intent)\n        tool_result = tool_result_override if tool_result_override is not None else answer.model_dump(mode="json", exclude={"agent_trace"})\n'''
if old_sig not in text:
    raise RuntimeError("Could not find _execute signature/body")
text = text.replace(old_sig, new_sig, 1)

# Add a primary generation API next to legacy enhance().
marker = '''    def _record_result(self, answer: GroundedAnswer, policy: AgentRequestPolicy) -> None:\n'''
if marker not in text:
    raise RuntimeError("Could not locate _record_result marker")
generate_method = '''    def generate_response(\n        self,\n        *,\n        fallback_answer: GroundedAnswer,\n        clinical_payload: dict[str, Any],\n        intent: ChatIntent,\n        question: str,\n        request_id: str,\n        tenant_id: str = "unscoped",\n        conversation_id: str = "unscoped",\n        locale: str = "vi-VN",\n        patient_context: dict[str, Any] | None = None,\n    ) -> GroundedAnswer:\n        """Primary V12 clinical response path.\n\n        The fallback answer is retained only for fail-safe degradation. Writer\n        input comes from the structured clinical contract, never from legacy\n        deterministic prose, so the model is not anchored to old templates.\n        """\n        policy = policy_for_intent(intent)\n        if self.config.mode == "disabled":\n            result = fallback_answer.model_copy(\n                update={"agent_trace": self._trace(status="disabled", reason="agent_mode_disabled")}\n            )\n            self._record_result(result, policy)\n            return result\n\n        configured = (\n            self.research_provider.is_configured\n            and self.verifier_provider.is_configured\n            and self.config.research_model\n            and self.config.verifier_model\n        )\n        if not configured:\n            result = fallback_answer.model_copy(\n                update={"agent_trace": self._trace(status="unavailable", reason="agent_configuration_incomplete")}\n            )\n            self._record_result(result, policy)\n            return result\n        if not self.circuit.allow_request():\n            result = fallback_answer.model_copy(\n                update={"agent_trace": self._trace(status="circuit_open", reason="model_circuit_open")}\n            )\n            self._record_result(result, policy)\n            return result\n\n        context = patient_context or {}\n        contract = build_clinical_agent_contract(\n            intent=intent,\n            question=question,\n            clinical_result=clinical_payload,\n            patient_context=context,\n        )\n        operation = lambda: self._execute(\n            answer=fallback_answer,\n            intent=intent,\n            question=question,\n            request_id=request_id,\n            tenant_id=tenant_id,\n            conversation_id=conversation_id,\n            locale=locale,\n            patient_context=context,\n            policy=policy,\n            claims_override=contract.claims,\n            tool_result_override=contract.envelope,\n        )\n\n        def invoke() -> GroundedAnswer:\n            if policy.single_flight:\n                return self.flight_coordinator.run(\n                    singleflight_key(\n                        tenant_id=tenant_id,\n                        conversation_id=conversation_id,\n                        locale=locale,\n                        question=question,\n                        patient_context=context,\n                        tool_result=contract.envelope,\n                        prompt_version=self.config.prompt_version,\n                        knowledge_version=knowledge.version_string(),\n                    ),\n                    operation,\n                )\n            return operation()\n\n        future = _AGENT_EXECUTOR.submit(invoke)\n        try:\n            result = future.result(timeout=self.config.total_timeout_seconds)\n        except FutureTimeoutError:\n            future.cancel()\n            metrics.inc_counter("medguard_llm_pipeline_timeout_total", labels={"intent": intent})\n            result = fallback_answer.model_copy(\n                update={"agent_trace": self._trace(status="error", reason="agent_total_timeout")}\n            )\n        self._record_result(result, policy)\n        return result\n\n'''
text = text.replace(marker, generate_method + marker, 1)

# Last gate only rejects; it never authors repair prose.
needle = '''            narrative_text = "\\n".join(block.text for block in narrative)\n            grounding = QAGEvaluator.evaluate_groundedness(\n'''
replacement = '''            narrative_text = "\\n".join(block.text for block in narrative)\n            normalized_narrative = narrative_text.lower()\n            generic_non_answer = any(\n                phrase in normalized_narrative\n                for phrase in (\n                    "cần thêm đánh giá lâm sàng toàn diện",\n                    "thông tin hiện tại chưa cho thấy rõ dấu hiệu cấp cứu",\n                )\n            )\n            if generic_non_answer:\n                metrics.inc_counter(\n                    "medguard_llm_quality_rejections_total",\n                    labels={"risk_class": policy.risk_class.value},\n                )\n                trace = self._trace(\n                    status="rejected",\n                    reason="generic_non_answer",\n                    **trace_values,\n                )\n                return answer.model_copy(update={"agent_trace": trace})\n\n            grounding = QAGEvaluator.evaluate_groundedness(\n'''
if needle not in text:
    raise RuntimeError("Could not locate deterministic gate narrative text")
text = text.replace(needle, replacement, 1)
write(answer_agents, text)

# ---------------------------------------------------------------------------
# 3) Agent graph must actually expose the clinical envelope to both models.
# ---------------------------------------------------------------------------
replace_once(
    "app/services/agent_graph.py",
    '''            "domain_claims": state.claims,\n            "retrieved_contexts": rag_contexts,\n''',
    '''            "domain_claims": state.claims,\n            "clinical_envelope": state.tool_result,\n            "retrieved_contexts": rag_contexts,\n''',
)
replace_once(
    "app/services/agent_graph.py",
    '''            "intent": state.intent,\n            "domain_claims": state.claims,\n            "retrieved_contexts": rag_contexts,\n            "draft": state.draft.model_dump(mode="json"),\n''',
    '''            "intent": state.intent,\n            "domain_claims": state.claims,\n            "clinical_envelope": state.tool_result,\n            "retrieved_contexts": rag_contexts,\n            "draft": state.draft.model_dump(mode="json"),\n''',
)

# ---------------------------------------------------------------------------
# 4) Chat orchestration: triage/safety answered requests use agent generation as
# the primary response path. Legacy deterministic answer is fallback only.
# ---------------------------------------------------------------------------
chat = "app/services/chat.py"
text = read(chat)
old = '''    agent_status: str | None = None\n    agent_submitted = False\n    agent_eligible = (\n        allow_agent\n        and intent in _active_research_agent_intents()\n    )\n    agent_patient_context = payload.context.model_dump(mode="json")\n    if intent in {"triage", "safety"}:\n        agent_patient_context["last_result"] = None\n    if agent_eligible and settings.agent_sync_enabled:\n        answer = answer_agent_pipeline.enhance(\n            answer=answer,\n            intent=intent,\n            question=agent_question or payload.messages[-1].content,\n            request_id=ctx.request_id,\n            tenant_id=ctx.tenant_id,\n            conversation_id=payload.conversation_id,\n            locale=payload.locale,\n            patient_context=agent_patient_context,\n        )\n    elif agent_eligible and settings.agent_background_enabled:\n'''
new = '''    agent_status: str | None = None\n    agent_submitted = False\n    agent_first_clinical = (\n        allow_agent\n        and status == "answered"\n        and intent in {"triage", "safety"}\n        and settings.agent_mode in {"shadow", "enforced"}\n    )\n    agent_eligible = agent_first_clinical or (\n        allow_agent\n        and intent in _active_research_agent_intents()\n    )\n    agent_patient_context = payload.context.model_dump(mode="json")\n    if intent in {"triage", "safety"}:\n        agent_patient_context["last_result"] = None\n    if agent_first_clinical:\n        answer = answer_agent_pipeline.generate_response(\n            fallback_answer=answer,\n            clinical_payload=serialized if isinstance(serialized, dict) else {},\n            intent=intent,\n            question=agent_question or payload.messages[-1].content,\n            request_id=ctx.request_id,\n            tenant_id=ctx.tenant_id,\n            conversation_id=payload.conversation_id,\n            locale=payload.locale,\n            patient_context=agent_patient_context,\n        )\n    elif agent_eligible and settings.agent_sync_enabled:\n        answer = answer_agent_pipeline.enhance(\n            answer=answer,\n            intent=intent,\n            question=agent_question or payload.messages[-1].content,\n            request_id=ctx.request_id,\n            tenant_id=ctx.tenant_id,\n            conversation_id=payload.conversation_id,\n            locale=payload.locale,\n            patient_context=agent_patient_context,\n        )\n    elif agent_eligible and settings.agent_background_enabled:\n'''
if old not in text:
    raise RuntimeError("Could not locate chat agent orchestration block")
text = text.replace(old, new, 1)
write(chat, text)

# ---------------------------------------------------------------------------
# 5) Development defaults to agent-first. Tests and non-dev environments keep
# explicit/disabled behavior unless configured.
# ---------------------------------------------------------------------------
config = "app/core/config.py"
text = read(config)
insert_marker = '''def _env_float(name: str, default: float) -> float:\n    value = getenv(name)\n    return default if value is None else float(value)\n\n\n'''
if insert_marker not in text:
    raise RuntimeError("Could not locate config helper marker")
helpers = '''def _default_agent_mode() -> str:\n    explicit = getenv("MEDGUARD_AGENT_MODE")\n    if explicit:\n        return explicit.lower()\n    if "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in environ:\n        return "disabled"\n    environment = getenv("MEDGUARD_ENVIRONMENT", "development").lower()\n    return "enforced" if environment == "development" else "disabled"\n\n\n'''
text = text.replace(insert_marker, insert_marker + helpers, 1)
text = text.replace(
    '    agent_mode: str = field(default_factory=lambda: getenv("MEDGUARD_AGENT_MODE", "disabled").lower())\n',
    '    agent_mode: str = field(default_factory=_default_agent_mode)\n',
    1,
)
text = text.replace(
    '        default_factory=lambda: _env_int("MEDGUARD_AGENT_MAX_ITERATIONS", 0)\n',
    '        default_factory=lambda: _env_int("MEDGUARD_AGENT_MAX_ITERATIONS", 1)\n',
    1,
)
write(config, text)

# ---------------------------------------------------------------------------
# 6) Output verifier is quality-only. Keep repaired_text field for API/test
# compatibility, but the verifier never fills it and never authors prose.
# ---------------------------------------------------------------------------
output_gate = "app/services/output_quality_verifier.py"
text = read(output_gate)
text = text.replace(
    "            repaired_text=get_deterministic_template_repair(obligations, clinical_state),\n",
    "            repaired_text=None,\n",
    1,
)
text = text.replace(
    '''    repaired = None\n    if not is_valid:\n        repaired = get_deterministic_template_repair(obligations, clinical_state)\n\n''',
    '''    # Quality gate is deliberately non-authoring. A failure is routed back\n    # to the Writer/Reviewer loop or to the dedicated safe fallback path.\n    repaired = None\n\n''',
    1,
)
write(output_gate, text)

# ---------------------------------------------------------------------------
# 7) Tests: contract provenance + primary agent path payload + non-authoring gate.
# ---------------------------------------------------------------------------
write(
    "app/tests/test_agent_first_clinical_v12.py",
    '''from __future__ import annotations\n\nimport json\n\nfrom app.models.agents import AgentDraft, AgentVerification\nfrom app.models.chat import GroundedAnswer\nfrom app.services.agent_provider import ProviderResult\nfrom app.services.answer_agents import AnswerAgentConfig, AnswerAgentPipeline\nfrom app.services.circuit import CircuitBreaker\nfrom app.services.clinical_agent_contract import build_clinical_agent_contract\n\n\nTRUSTED = "https://www.nice.org.uk/guidance/ng100"\n\n\nclass FakeProvider:\n    def __init__(self, name: str, data, *, citations=(), queries=()):\n        self.provider_name = name\n        self.data = data\n        self.citations = tuple(citations)\n        self.queries = tuple(queries)\n        self.calls = []\n\n    @property\n    def is_configured(self) -> bool:\n        return True\n\n    def complete(self, **values):\n        self.calls.append(values)\n        return ProviderResult(\n            data=self.data,\n            response_id=f"{self.provider_name}-response",\n            model=values["model"],\n            latency_ms=1,\n            citations=self.citations,\n            search_queries=self.queries,\n        )\n\n\ndef fallback_answer() -> GroundedAnswer:\n    return GroundedAnswer(\n        title="Thông tin hiện tại chưa cho thấy rõ dấu hiệu cấp cứu",\n        summary="Cần thêm đánh giá lâm sàng toàn diện.",\n        next_steps=["Theo dõi triệu chứng."],\n        questions=["Có sốt hoặc đau tăng dần không?"],\n        decision_basis="versioned_rules",\n        evidence_state="bounded_result",\n    )\n\n\ndef test_contract_uses_structured_state_not_legacy_prose_and_strips_identifiers():\n    contract = build_clinical_agent_contract(\n        intent="triage",\n        question="Tôi đang cảm thấy đau các khớp tay",\n        clinical_result={\n            "urgency": "ROUTINE",\n            "recommended_specialty": {"label": "Cơ xương khớp"},\n            "red_flags": [],\n            "clarifying_questions": ["Khớp có sưng nóng đỏ hoặc cứng buổi sáng không?"],\n        },\n        patient_context={\n            "patient_ref": "BN-SECRET",\n            "age": 31,\n            "conditions": ["none"],\n            "last_result": {"old": "answer"},\n        },\n    )\n\n    encoded = json.dumps(contract.envelope, ensure_ascii=False)\n    assert "BN-SECRET" not in encoded\n    assert "old" not in encoded\n    assert "Thông tin hiện tại chưa cho thấy rõ dấu hiệu cấp cứu" not in encoded\n    assert contract.envelope["patient_context"]["age"] == 31\n    assert contract.envelope["communication_contract"]["compose_original_response"] is True\n    assert contract.envelope["communication_contract"]["question_budget"] == 1\n\n\ndef test_emergency_contract_locks_action_but_does_not_supply_full_template():\n    contract = build_clinical_agent_contract(\n        intent="triage",\n        question="đau ngực khó thở",\n        clinical_result={"urgency": "EMERGENCY", "emergency_flag": True, "red_flags": ["khó thở"]},\n    )\n    locked = [claim for claim in contract.claims if claim["locked"]]\n    assert len(locked) == 1\n    assert locked[0]["category"] == "action"\n    assert "115" in locked[0]["text"]\n    assert contract.envelope["communication_contract"]["question_budget"] == 0\n\n\ndef test_generate_response_sends_clinical_envelope_not_fallback_prose_to_writer():\n    # Claims produced for this routine payload are summary_1, finding_2, question_3.\n    draft = AgentDraft.model_validate(\n        {\n            "question_analysis": {\n                "interpreted_request": "Đau nhiều khớp tay, cần định hướng và câu hỏi phân biệt.",\n                "key_questions": ["Có dấu hiệu viêm khớp không?"],\n                "ambiguities": ["Chưa rõ sưng nóng đỏ/cứng buổi sáng"],\n                "risk_level": "low",\n            },\n            "evidence_claims": [],\n            "narrative": [\n                {\n                    "kind": "paragraph",\n                    "text": "Đau nhiều khớp tay có nhiều nhóm nguyên nhân; hiện chưa đủ dữ kiện để kết luận một bệnh cụ thể.",\n                    "emphasis": [],\n                    "claim_ids": ["summary_1", "finding_2"],\n                    "source_ids": ["src_nice"],\n                }\n            ],\n            "sources": [\n                {\n                    "source_id": "src_nice",\n                    "title": "Joint pain guidance",\n                    "publisher": "NICE",\n                    "url": TRUSTED,\n                    "authority_tier": "guideline_or_regulator",\n                    "supports_claim_ids": ["summary_1", "finding_2"],\n                }\n            ],\n            "notes": "",\n        }\n    )\n    report = AgentVerification.model_validate(\n        {\n            "approved": False,\n            "scores": {\n                "grounding": 0.9,\n                "safety": 0.95,\n                "completeness": 0.8,\n                "clarity": 0.9,\n                "citation_coverage": 0.9,\n            },\n            "issues": ["test rejection after writer payload capture"],\n            "summary": "reject",\n        }\n    )\n    research = FakeProvider("research", draft, citations=(TRUSTED,), queries=("joint pain NICE",))\n    verifier = FakeProvider("verifier", report, citations=(TRUSTED,), queries=("verify joint pain",))\n    pipeline = AnswerAgentPipeline(\n        config=AnswerAgentConfig(\n            mode="enforced",\n            research_model="research-test",\n            verifier_model="verifier-test",\n            max_iterations=0,\n        ),\n        research_provider=research,\n        verifier_provider=verifier,\n        circuit=CircuitBreaker(error_threshold=1, min_requests=10),\n    )\n    fallback = fallback_answer()\n    result = pipeline.generate_response(\n        fallback_answer=fallback,\n        clinical_payload={\n            "urgency": "ROUTINE",\n            "recommended_specialty": {"label": "Cơ xương khớp"},\n            "clarifying_questions": ["Khớp có sưng nóng đỏ hoặc cứng buổi sáng không?"],\n        },\n        intent="triage",\n        question="Tôi đang cảm thấy đau các khớp tay",\n        request_id="req-v12",\n        patient_context={"age": 31},\n    )\n\n    assert result.agent_trace.status == "rejected"\n    payload = research.calls[0]["payload"]\n    assert payload["clinical_envelope"]["version"] == "v12-agent-first"\n    dumped = json.dumps(payload, ensure_ascii=False)\n    assert fallback.summary not in dumped\n    assert fallback.title not in dumped\n    assert "Cơ xương khớp" in dumped\n''',
)

# Update output gate tests to assert non-authoring behavior.
test_gate = "app/tests/test_output_quality_governance.py"
text = read(test_gate)
text = text.replace("assert result.repaired_text is not None", "assert result.repaired_text is None")
text = text.replace('assert "115" in result.repaired_text\n', "")
write(test_gate, text)

# Compile-time sanity: no old deterministic prose should be added to clinical
# envelope code by accident.
for target in (
    "app/services/clinical_agent_contract.py",
    "app/services/answer_agents.py",
    "app/services/agent_graph.py",
    "app/services/chat.py",
    "app/core/config.py",
    "app/services/output_quality_verifier.py",
    "app/tests/test_agent_first_clinical_v12.py",
):
    compile(read(target), target, "exec")

print("agent_first_v12_patch=APPLIED")
