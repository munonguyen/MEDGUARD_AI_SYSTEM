from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"locator count in {path}: expected 1, got {count}: {old[:90]!r}")
    p.write_text(text.replace(old, new, 1))


def replace_after(path: str, marker: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit(f"marker not found in {path}: {marker!r}")
    prefix, tail = text[:pos], text[pos:]
    count = tail.count(old)
    if count < 1:
        raise SystemExit(f"locator not found after marker in {path}: {old[:90]!r}")
    p.write_text(prefix + tail.replace(old, new, 1))


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
replace_once(
    "app/core/config.py",
    '''    pharma_verifier_model: str = field(\n        default_factory=lambda: getenv("MEDGUARD_PHARMA_VERIFIER_MODEL", "medguard-pharma-verifier")\n    )\n    research_reasoning_effort: str = field(''',
    '''    pharma_verifier_model: str = field(\n        default_factory=lambda: getenv("MEDGUARD_PHARMA_VERIFIER_MODEL", "medguard-pharma-verifier")\n    )\n\n    # V14 adaptive compute. These are gateway aliases, not hard-coded vendors.\n    severity_single_agent_enabled: bool = field(\n        default_factory=lambda: _env_bool("MEDGUARD_SEVERITY_SINGLE_AGENT_ENABLED", True)\n    )\n    routine_agent_model: str = field(\n        default_factory=lambda: getenv("MEDGUARD_ROUTINE_AGENT_MODEL", "medguard-routine-free")\n    )\n    urgent_agent_model: str = field(\n        default_factory=lambda: getenv("MEDGUARD_URGENT_AGENT_MODEL", "medguard-urgent-free")\n    )\n    emergency_agent_model: str = field(\n        default_factory=lambda: getenv("MEDGUARD_EMERGENCY_AGENT_MODEL", "medguard-emergency-free")\n    )\n    routine_agent_max_input_tokens: int = field(\n        default_factory=lambda: _env_int("MEDGUARD_ROUTINE_AGENT_MAX_INPUT_TOKENS", 4_000)\n    )\n    urgent_agent_max_input_tokens: int = field(\n        default_factory=lambda: _env_int("MEDGUARD_URGENT_AGENT_MAX_INPUT_TOKENS", 6_000)\n    )\n    emergency_agent_max_input_tokens: int = field(\n        default_factory=lambda: _env_int("MEDGUARD_EMERGENCY_AGENT_MAX_INPUT_TOKENS", 3_000)\n    )\n    routine_agent_max_output_tokens: int = field(\n        default_factory=lambda: _env_int("MEDGUARD_ROUTINE_AGENT_MAX_OUTPUT_TOKENS", 450)\n    )\n    urgent_agent_max_output_tokens: int = field(\n        default_factory=lambda: _env_int("MEDGUARD_URGENT_AGENT_MAX_OUTPUT_TOKENS", 650)\n    )\n    emergency_agent_max_output_tokens: int = field(\n        default_factory=lambda: _env_int("MEDGUARD_EMERGENCY_AGENT_MAX_OUTPUT_TOKENS", 350)\n    )\n    kev_base_url: str | None = field(\n        default_factory=lambda: (getenv("MEDGUARD_KEV_BASE_URL", "").rstrip("/") or None)\n    )\n    kev_model: str = field(default_factory=lambda: getenv("MEDGUARD_KEV_MODEL", "kev-latest"))\n    kev_mode: str = field(default_factory=lambda: getenv("MEDGUARD_KEV_MODE", "shadow").lower())\n    kev_timeout_seconds: float = field(\n        default_factory=lambda: _env_float("MEDGUARD_KEV_TIMEOUT_SECONDS", 0.35)\n    )\n    kev_min_confidence: float = field(\n        default_factory=lambda: _env_float("MEDGUARD_KEV_MIN_CONFIDENCE", 0.72)\n    )\n    kev_min_margin: float = field(\n        default_factory=lambda: _env_float("MEDGUARD_KEV_MIN_MARGIN", 0.15)\n    )\n    research_reasoning_effort: str = field(''',
)

replace_once(
    "app/core/config.py",
    '''        if self.agent_coverage_scope not in {"clinical", "all"}:\n            raise ValueError("MEDGUARD_AGENT_COVERAGE_SCOPE must be clinical or all")\n''',
    '''        if self.agent_coverage_scope not in {"clinical", "all"}:\n            raise ValueError("MEDGUARD_AGENT_COVERAGE_SCOPE must be clinical or all")\n        if self.kev_mode not in {"disabled", "shadow", "enforced"}:\n            raise ValueError("MEDGUARD_KEV_MODE must be disabled, shadow, or enforced")\n        if self.kev_timeout_seconds <= 0 or self.kev_timeout_seconds > 2:\n            raise ValueError("MEDGUARD_KEV_TIMEOUT_SECONDS must be > 0 and <= 2")\n        if not 0 <= self.kev_min_confidence <= 1 or not 0 <= self.kev_min_margin <= 1:\n            raise ValueError("Kev confidence and margin thresholds must be between 0 and 1")\n        for name, value in {\n            "MEDGUARD_ROUTINE_AGENT_MAX_INPUT_TOKENS": self.routine_agent_max_input_tokens,\n            "MEDGUARD_URGENT_AGENT_MAX_INPUT_TOKENS": self.urgent_agent_max_input_tokens,\n            "MEDGUARD_EMERGENCY_AGENT_MAX_INPUT_TOKENS": self.emergency_agent_max_input_tokens,\n            "MEDGUARD_ROUTINE_AGENT_MAX_OUTPUT_TOKENS": self.routine_agent_max_output_tokens,\n            "MEDGUARD_URGENT_AGENT_MAX_OUTPUT_TOKENS": self.urgent_agent_max_output_tokens,\n            "MEDGUARD_EMERGENCY_AGENT_MAX_OUTPUT_TOKENS": self.emergency_agent_max_output_tokens,\n        }.items():\n            if value < 1:\n                raise ValueError(f"{name} must be at least 1")\n''',
)

# ---------------------------------------------------------------------------
# Answer pipeline
# ---------------------------------------------------------------------------
replace_once(
    "app/services/answer_agents.py",
    'from app.services.clinical_agent_contract import build_clinical_agent_contract\n',
    'from app.services.clinical_agent_contract import build_clinical_agent_contract\nfrom app.models.adaptive_routing import AgentTier\nfrom app.services.severity_agent_policy import profile_for_tier\n',
)

replace_after(
    "app/services/answer_agents.py",
    "    def generate_response(",
    '''        patient_context: dict[str, Any] | None = None,\n    ) -> GroundedAnswer:\n        """Primary V12 clinical response path.''',
    '''        patient_context: dict[str, Any] | None = None,\n        agent_tier: str | None = None,\n    ) -> GroundedAnswer:\n        """Primary V12/V14 clinical response path.''',
)

replace_after(
    "app/services/answer_agents.py",
    "    def generate_response(",
    '''        configured = (\n            self.research_provider.is_configured\n            and self.verifier_provider.is_configured\n            and self.config.research_model\n            and self.config.verifier_model\n        )\n''',
    '''        requested_tier = None\n        try:\n            requested_tier = AgentTier(agent_tier) if agent_tier else None\n        except ValueError:\n            requested_tier = None\n        requested_profile = profile_for_tier(requested_tier, settings) if requested_tier else None\n        single_agent_requested = bool(\n            requested_profile\n            and not requested_profile.reviewer_required\n            and getattr(settings, "severity_single_agent_enabled", True)\n        )\n        configured = bool(\n            self.research_provider.is_configured\n            and (requested_profile.model if requested_profile else self.config.research_model)\n            and (single_agent_requested or (self.verifier_provider.is_configured and self.config.verifier_model))\n        )\n''',
)

replace_after(
    "app/services/answer_agents.py",
    "    def generate_response(",
    '''            tool_result_override=contract.envelope,\n        )\n''',
    '''            tool_result_override=contract.envelope,\n            agent_tier=agent_tier,\n        )\n''',
)

replace_after(
    "app/services/answer_agents.py",
    "    def _execute(",
    '''        claims_override: list[dict[str, Any]] | None = None,\n        tool_result_override: dict[str, Any] | None = None,\n    ) -> GroundedAnswer:\n''',
    '''        claims_override: list[dict[str, Any]] | None = None,\n        tool_result_override: dict[str, Any] | None = None,\n        agent_tier: str | None = None,\n    ) -> GroundedAnswer:\n''',
)

replace_after(
    "app/services/answer_agents.py",
    "    def _execute(",
    '''        state = MedicalAgentState(\n            request_id=request_id,''',
    '''        selected_tier = None\n        try:\n            selected_tier = AgentTier(agent_tier) if agent_tier else None\n        except ValueError:\n            selected_tier = None\n        selected_profile = profile_for_tier(selected_tier, settings) if selected_tier else None\n        single_agent_path = bool(\n            selected_profile\n            and not selected_profile.reviewer_required\n            and getattr(settings, "severity_single_agent_enabled", True)\n        )\n\n        state = MedicalAgentState(\n            request_id=request_id,''',
)

replace_after(
    "app/services/answer_agents.py",
    "    def _execute(",
    '        self.graph.clinical_research_model = self.config.clinical_research_model\n',
    '''        self.graph.clinical_research_model = (\n            selected_profile.model if selected_profile and state.domain == "clinical"\n            else self.config.clinical_research_model\n        )\n''',
)

replace_after(
    "app/services/answer_agents.py",
    "    def _execute(",
    '''        self.graph.max_input_tokens = self.config.max_input_tokens\n        self.graph.research_max_output_tokens = self.config.research_max_output_tokens\n''',
    '''        self.graph.max_input_tokens = selected_profile.max_input_tokens if selected_profile else self.config.max_input_tokens\n        self.graph.research_max_output_tokens = selected_profile.max_output_tokens if selected_profile else self.config.research_max_output_tokens\n''',
)

replace_after(
    "app/services/answer_agents.py",
    "    def _execute(",
    '''        writer_instructions = (\n            _PHARMA_RESEARCH_INSTRUCTIONS\n            if domain == "pharmacology"\n            else _CLINICAL_RESEARCH_INSTRUCTIONS\n        )\n''',
    '''        writer_instructions = (\n            _PHARMA_RESEARCH_INSTRUCTIONS\n            if domain == "pharmacology"\n            else _CLINICAL_RESEARCH_INSTRUCTIONS\n        )\n        if selected_profile and domain == "clinical":\n            writer_instructions = selected_profile.instruction_prefix + "\\n\\n" + writer_instructions\n''',
)

replace_after(
    "app/services/answer_agents.py",
    "    def _execute(",
    '''            # 2. Graph execution loop (Writer <-> Reviewer feedback cycle)\n            while state.iteration <= self.graph.max_iterations:\n                writer_ok = self.graph.node_writer(\n                    state,\n                    instructions=writer_instructions,\n                    redact_question_fn=_redact_question,\n                    stage_trace_fn=_stage,\n                )\n                if not writer_ok:\n                    break\n\n                self.graph.node_reviewer(\n                    state,\n                    instructions=verifier_instructions,\n                    stage_trace_fn=_stage,\n                    gate_reason_fn=_gate_reason,\n                )\n\n                decision = self.graph.route_decision(state)\n                if decision == "COMPLETE":\n                    break\n                elif decision == "REVISE":\n                    continue\n                else:  # FALLBACK\n                    break\n''',
    '''            # Resolved severity paths call exactly one Writer LLM.\n            # UNCERTAIN/DEEP retains the existing Writer/Reviewer graph.\n            if single_agent_path:\n                writer_ok = self.graph.node_writer(\n                    state,\n                    instructions=writer_instructions,\n                    redact_question_fn=_redact_question,\n                    stage_trace_fn=_stage,\n                )\n                if writer_ok:\n                    state.status = "verified"\n            else:\n                while state.iteration <= self.graph.max_iterations:\n                    writer_ok = self.graph.node_writer(\n                        state,\n                        instructions=writer_instructions,\n                        redact_question_fn=_redact_question,\n                        stage_trace_fn=_stage,\n                    )\n                    if not writer_ok:\n                        break\n                    self.graph.node_reviewer(\n                        state,\n                        instructions=verifier_instructions,\n                        stage_trace_fn=_stage,\n                        gate_reason_fn=_gate_reason,\n                    )\n                    decision = self.graph.route_decision(state)\n                    if decision == "COMPLETE":\n                        break\n                    if decision == "REVISE":\n                        continue\n                    break\n''',
)

replace_after(
    "app/services/answer_agents.py",
    "    def _execute(",
    '''                triage_urgency=(\n                    "EMERGENCY"\n                    if answer.title.startswith("Bạn cần được đánh giá cấp cứu")\n                    else "ROUTINE"\n                ),\n''',
    '''                triage_urgency=(\n                    selected_tier.value.upper()\n                    if selected_tier in {AgentTier.ROUTINE, AgentTier.URGENT, AgentTier.EMERGENCY}\n                    else ("EMERGENCY" if answer.title.startswith("Bạn cần được đánh giá cấp cứu") else "ROUTINE")\n                ),\n''',
)

replace_after(
    "app/services/answer_agents.py",
    "    def _execute(",
    '''                    "answer_assurance": AnswerAssurance(status="verified", scores=state.verification.scores),\n                    "agent_trace": trace,\n''',
    '''                    "answer_assurance": (\n                        AnswerAssurance(status="verified", scores=state.verification.scores)\n                        if state.verification is not None else None\n                    ),\n                    "agent_trace": trace,\n''',
)

# ---------------------------------------------------------------------------
# Chat runtime
# ---------------------------------------------------------------------------
replace_once(
    "app/services/chat.py",
    'from app.services.temporal_syndrome import evaluate_temporal_syndrome\n',
    'from app.services.temporal_syndrome import evaluate_temporal_syndrome\nfrom app.models.adaptive_routing import AgentTier\nfrom app.services.adaptive_dispatcher import adjudicate_uncertain_route, resolve_adaptive_route\nfrom app.services.kev_router import KevRouter, KevRouterConfig, build_compact_kev_state\n',
)

replace_once(
    "app/services/chat.py",
    '_INTENT_KEYWORDS: dict[ChatIntent, tuple[str, ...]] = {\n',
    '''_kev_router = KevRouter(\n    KevRouterConfig(\n        base_url=getattr(settings, "kev_base_url", None),\n        model=getattr(settings, "kev_model", "kev-latest"),\n        timeout_seconds=getattr(settings, "kev_timeout_seconds", 0.35),\n        mode=getattr(settings, "kev_mode", "shadow"),\n    )\n)\n\n\n_INTENT_KEYWORDS: dict[ChatIntent, tuple[str, ...]] = {\n''',
)

replace_after(
    "app/services/chat.py",
    "def _response(",
    '''    if agent_first_clinical:\n        answer = answer_agent_pipeline.generate_response(\n''',
    '''    adaptive_agent_tier: str | None = None\n    if agent_first_clinical and isinstance(serialized, dict):\n        task_for_route = (clinical_task_name or "acute_symptom").lower()\n        kev_state = build_compact_kev_state(\n            clinical_task=task_for_route, clinical_result=serialized, patient_context=agent_patient_context\n        )\n        kev_signal = _kev_router.evaluate(kev_state, serialized)\n        adaptive_route = resolve_adaptive_route(\n            clinical_task=task_for_route,\n            clinical_result=serialized,\n            kev=kev_signal,\n            kev_mode=getattr(settings, "kev_mode", "shadow"),\n            min_confidence=getattr(settings, "kev_min_confidence", 0.72),\n            min_margin=getattr(settings, "kev_min_margin", 0.15),\n        )\n        if adaptive_route.requires_jev:\n            adaptive_route = adjudicate_uncertain_route(decision=adaptive_route, clinical_result=serialized)\n        if adaptive_route.agent_tier in {AgentTier.ROUTINE, AgentTier.URGENT, AgentTier.EMERGENCY}:\n            adaptive_agent_tier = adaptive_route.agent_tier.value\n        serialized = {\n            **serialized,\n            "adaptive_routing": {**adaptive_route.model_dump(mode="json"), "kev": kev_signal.model_dump(mode="json")},\n        }\n\n    if agent_first_clinical:\n        answer = answer_agent_pipeline.generate_response(\n''',
)

replace_after(
    "app/services/chat.py",
    "        answer = answer_agent_pipeline.generate_response(",
    '''            patient_context=agent_patient_context,\n        )\n''',
    '''            patient_context=agent_patient_context,\n            agent_tier=adaptive_agent_tier,\n        )\n''',
)

print("V14 adaptive severity-agent runtime patch applied")
