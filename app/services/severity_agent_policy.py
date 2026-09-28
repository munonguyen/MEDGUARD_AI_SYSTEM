from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.adaptive_routing import AgentTier


@dataclass(frozen=True)
class SeverityAgentProfile:
    tier: AgentTier
    model: str
    max_input_tokens: int
    max_output_tokens: int
    web_search_required: bool
    reviewer_required: bool
    instruction_prefix: str


def profile_for_tier(tier: AgentTier, settings: Any) -> SeverityAgentProfile:
    """Return the single patient-facing agent profile for one resolved tier.

    Model names are gateway aliases. LiteLLM (or another compatible gateway)
    can map each alias to a free-credit provider pool plus same-tier fallback;
    provider failure must never change the clinical severity tier.
    """
    if tier == AgentTier.EMERGENCY:
        return SeverityAgentProfile(
            tier=tier,
            model=getattr(settings, "emergency_agent_model", "medguard-emergency-free"),
            max_input_tokens=getattr(settings, "emergency_agent_max_input_tokens", 3000),
            max_output_tokens=getattr(settings, "emergency_agent_max_output_tokens", 350),
            web_search_required=False,
            reviewer_required=False,
            instruction_prefix=(
                "EMERGENCY RESPONSE MODE. Put the locked immediate action first. "
                "Do not delay action with questions, long differential diagnosis, or background teaching. "
                "Use concise professional Vietnamese and preserve every locked safety instruction."
            ),
        )
    if tier == AgentTier.URGENT:
        return SeverityAgentProfile(
            tier=tier,
            model=getattr(settings, "urgent_agent_model", "medguard-urgent-free"),
            max_input_tokens=getattr(settings, "urgent_agent_max_input_tokens", 6000),
            max_output_tokens=getattr(settings, "urgent_agent_max_output_tokens", 650),
            web_search_required=True,
            reviewer_required=False,
            instruction_prefix=(
                "URGENT RESPONSE MODE. Explain why prompt evaluation is needed, what to do today, "
                "what to avoid, and which changes require emergency care. Ask at most one non-blocking "
                "high-information question when it can materially change disposition."
            ),
        )
    if tier == AgentTier.ROUTINE:
        return SeverityAgentProfile(
            tier=tier,
            model=getattr(settings, "routine_agent_model", "medguard-routine-free"),
            max_input_tokens=getattr(settings, "routine_agent_max_input_tokens", 4000),
            max_output_tokens=getattr(settings, "routine_agent_max_output_tokens", 450),
            web_search_required=False,
            reviewer_required=False,
            instruction_prefix=(
                "ROUTINE RESPONSE MODE. Give a direct assessment at category level, specific self-care or "
                "monitoring steps, a clear threshold for seeking care, and at most one useful follow-up question. "
                "Do not open with generic triage boilerplate."
            ),
        )
    if tier == AgentTier.CLARIFICATION:
        return SeverityAgentProfile(
            tier=tier,
            model=getattr(settings, "clarification_agent_model", "medguard-clarification-free"),
            max_input_tokens=getattr(settings, "clarification_agent_max_input_tokens", 2500),
            max_output_tokens=getattr(settings, "clarification_agent_max_output_tokens", 180),
            web_search_required=False,
            reviewer_required=False,
            instruction_prefix=(
                "CLARIFICATION MODE. The clinical state is not sufficient for safe severity routing. "
                "Do not diagnose and do not invent a care level. Briefly reflect what is understood, then ask "
                "exactly one concrete high-information question that most reduces routing uncertainty."
            ),
        )
    # DEEP routes intentionally retain the existing multi-stage graph.
    return SeverityAgentProfile(
        tier=tier,
        model=getattr(settings, "clinical_research_model", "medguard-clinical-answer"),
        max_input_tokens=getattr(settings, "agent_max_input_tokens", 12000),
        max_output_tokens=getattr(settings, "research_max_output_tokens", 700),
        web_search_required=True,
        reviewer_required=True,
        instruction_prefix="DEEP CLINICAL REASONING MODE.",
    )
