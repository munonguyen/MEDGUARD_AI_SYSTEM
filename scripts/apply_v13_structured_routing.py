from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHAT = ROOT / "app/services/chat.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    text = CHAT.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "from app.models.chat import ChatIntent, ChatRequest, ChatResponse, ChatSuggestion\n",
        "from app.models.chat import ChatIntent, ChatRequest, ChatResponse, ChatSuggestion\n"
        "from app.models.clinical_task import ClinicalTask\n",
        "clinical task model import",
    )

    text = replace_once(
        text,
        "from app.services.clinical_text import contains_affirmed_phrase, normalize_clinical_concepts, normalize_search_text\n",
        "from app.services.clinical_text import contains_affirmed_phrase, normalize_clinical_concepts, normalize_search_text\n"
        "from app.services.clinical_task_router import resolve_clinical_task\n"
        "from app.services.exposure_reasoner import evaluate_exposure_reaction\n"
        "from app.services.lab_interpreter import interpret_laboratory_text\n"
        "from app.services.temporal_syndrome import evaluate_temporal_syndrome\n",
        "V13 service imports",
    )

    old_agent = '''    agent_first_clinical = (\n        allow_agent\n        and status == "answered"\n        and intent in {"triage", "safety"}\n        and settings.agent_mode == "enforced"\n    )\n'''
    new_agent = '''    clinical_task_name = (\n        str(serialized.get("clinical_task"))\n        if isinstance(serialized, dict) and serialized.get("clinical_task")\n        else None\n    )\n    agent_first_clinical = (\n        allow_agent\n        and status == "answered"\n        and (\n            intent in {"triage", "safety"}\n            or clinical_task_name in {"LAB_INTERPRETATION", "EXPOSURE_REACTION"}\n        )\n        and settings.agent_mode == "enforced"\n    )\n'''
    text = replace_once(text, old_agent, new_agent, "agent-first clinical task support")

    text = replace_once(
        text,
        '''    if intent in {"triage", "safety"}:\n        agent_patient_context["last_result"] = None\n''',
        '''    if intent in {"triage", "safety"} or clinical_task_name:\n        agent_patient_context["last_result"] = None\n''',
        "clinical task stale-result isolation",
    )

    marker = '''    intent = _detect_intent(payload, normalized)\n'''
    task_block = '''    # V13: task classification is independent from severity.  The emergency\n    # sentinel may raise urgency later, but it must never turn a lab question\n    # into an acute-triage task or hide an exposure-reaction question behind\n    # the generic fallback.\n    clinical_task_decision = resolve_clinical_task(latest_text)\n\n    if (\n        clinical_task_decision.task == ClinicalTask.LAB_INTERPRETATION\n        and not pre_ood_safety_floor.is_emergency\n    ):\n        lab_result = interpret_laboratory_text(latest_text)\n        lab_dict = lab_result.to_dict()\n        if lab_result.confidence < 0.60:\n            return _response(\n                payload,\n                ctx,\n                status="needs_information",\n                intent="general",\n                reply=lab_result.summary,\n                required_fields=["request_detail"],\n                extracted={"clinical_task": lab_result.clinical_task},\n                result=lab_dict,\n                allow_agent=False,\n            )\n        fallback_reply = " ".join(\n            [\n                lab_result.summary,\n                *lab_result.interpretation_points,\n                *lab_result.prohibited_actions,\n            ]\n        ).strip()\n        return _response(\n            payload,\n            ctx,\n            status="answered",\n            intent="general",\n            reply=fallback_reply,\n            extracted={\n                "clinical_task": lab_result.clinical_task,\n                "task_confidence": clinical_task_decision.confidence,\n            },\n            result=lab_dict,\n            agent_question=latest_text,\n            allow_agent=True,\n        )\n\n    if (\n        clinical_task_decision.task == ClinicalTask.EXPOSURE_REACTION\n        and not pre_ood_safety_floor.is_emergency\n    ):\n        exposure = evaluate_exposure_reaction(latest_text)\n        # Airway/systemic emergencies stay on the established acute-triage path\n        # so deterministic emergency actions remain authoritative.\n        if exposure.urgency != "EMERGENCY":\n            exposure_dict = exposure.to_dict()\n            fallback_reply = " ".join(\n                [\n                    exposure.summary,\n                    *exposure.prohibited_actions,\n                    *exposure.what_to_do_now,\n                    *exposure.warning_signs,\n                ]\n            ).strip()\n            return _response(\n                payload,\n                ctx,\n                status="answered",\n                intent="general",\n                reply=fallback_reply,\n                extracted={\n                    "clinical_task": exposure.clinical_task,\n                    "task_confidence": clinical_task_decision.confidence,\n                },\n                result=exposure_dict,\n                agent_question=latest_text,\n                allow_agent=True,\n            )\n\n    intent = _detect_intent(payload, normalized)\n'''
    text = replace_once(text, marker, task_block, "clinical task orchestration")

    old_triage = '''        conversation_risk = "EMERGENCY" if (episode_context_used and ledger.has_active_emergency()) else None\n        if (\n            not conversation_risk\n            and episode_context_used\n'''
    new_triage = '''        conversation_risk = "EMERGENCY" if (episode_context_used and ledger.has_active_emergency()) else None\n        temporal_syndrome = evaluate_temporal_syndrome(episode_text)\n        if temporal_syndrome.urgency == "EMERGENCY":\n            conversation_risk = "EMERGENCY"\n        elif temporal_syndrome.urgency == "URGENT" and conversation_risk != "EMERGENCY":\n            conversation_risk = "URGENT"\n        if (\n            not conversation_risk\n            and episode_context_used\n'''
    text = replace_once(text, old_triage, new_triage, "temporal syndrome floor")

    old_extracted = '''                "medical_emergency_flag": result.urgency == "EMERGENCY",\n                "crisis_support_flag": dual_crisis.crisis_support_required,\n'''
    new_extracted = '''                "medical_emergency_flag": result.urgency == "EMERGENCY",\n                "crisis_support_flag": dual_crisis.crisis_support_required,\n                "clinical_task": clinical_task_decision.task.value,\n                "temporal_syndrome": temporal_syndrome.to_dict(),\n'''
    text = replace_once(text, old_extracted, new_extracted, "triage task trace")

    CHAT.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
