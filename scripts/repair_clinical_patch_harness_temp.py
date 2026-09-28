from pathlib import Path

path = Path("scripts/patch_clinical_episode_followup_temp.py")
text = path.read_text(encoding="utf-8")
old = '''# Do not feed stale last_result into clinical answer agents. last_result remains
# available to deterministic FHIR/delivery routes, which explicitly require it.
replace_once(
    "app/services/chat.py",
    ''' + "'''" + '''    internal_agent_trace = answer.agent_trace
''' + "'''" + ''',
    ''' + "'''" + '''    agent_patient_context = payload.context.model_dump(mode="json")
    if intent in {"triage", "safety"}:
        agent_patient_context["last_result"] = None

    internal_agent_trace = answer.agent_trace
''' + "'''" + ''',
)
replace_once(
    "app/services/chat.py",
    '            patient_context=payload.context.model_dump(mode="json"),\\n',
    '            patient_context=agent_patient_context,\\n',
)
replace_once(
    "app/services/chat.py",
    '            patient_context=payload.context.model_dump(mode="json"),\\n',
    '            patient_context=agent_patient_context,\\n',
)
'''
new = '''# Do not feed stale last_result into clinical answer agents. last_result remains
# available to deterministic FHIR/delivery routes, which explicitly require it.
replace_once(
    "app/services/chat.py",
    ''' + "'''" + '''    agent_status: str | None = None
    agent_submitted = False
    agent_eligible = (
        allow_agent
        and intent in _active_research_agent_intents()
    )
    if agent_eligible and settings.agent_sync_enabled:
''' + "'''" + ''',
    ''' + "'''" + '''    agent_status: str | None = None
    agent_submitted = False
    agent_eligible = (
        allow_agent
        and intent in _active_research_agent_intents()
    )
    agent_patient_context = payload.context.model_dump(mode="json")
    if intent in {"triage", "safety"}:
        agent_patient_context["last_result"] = None
    if agent_eligible and settings.agent_sync_enabled:
''' + "'''" + ''',
)
chat_path = Path("app/services/chat.py")
chat_text = chat_path.read_text(encoding="utf-8")
old_patient_context = '            patient_context=payload.context.model_dump(mode="json"),\\n'
if chat_text.count(old_patient_context) != 2:
    raise RuntimeError(
        f"app/services/chat.py: expected 2 agent patient_context calls, found {chat_text.count(old_patient_context)}"
    )
chat_path.write_text(
    chat_text.replace(old_patient_context, '            patient_context=agent_patient_context,\\n'),
    encoding="utf-8",
)
'''
if old not in text:
    raise RuntimeError("guarded harness repair target not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("Patch harness repaired")
