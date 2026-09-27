from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one match in {path}, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


triage = "app/services/triage.py"
replace_once(
    triage,
    "from app.services.rules import triage_rules\n",
    "from app.services.rules import triage_rules\nfrom app.services.question_policy import plan_clinical_questions\n",
)
replace_once(
    triage,
    '''    clarifying_questions = guidance_questions if has_guidance else rule.clarifying_questions\n    if emergency_flag:\n        clarifying_questions = []\n    else:\n        clarifying_questions = filter_known_clarifying_questions(clarifying_questions, facts)\n''',
    '''    clarifying_questions = guidance_questions if has_guidance else rule.clarifying_questions\n    if emergency_flag:\n        clarifying_questions = []\n    else:\n        clarifying_questions = filter_known_clarifying_questions(clarifying_questions, facts)\n\n    # Dialogue policy ranks only questions already approved by the clinical\n    # layer. It cannot change urgency, specialty, red flags, or invent facts.\n    question_plan = plan_clinical_questions(\n        clarifying_questions,\n        urgency=final_urgency,\n    )\n    clarifying_questions = question_plan.questions\n''',
)
replace_once(
    triage,
    '''                "guidance_actions_applied": bool(use_guidance_actions),\n                "knowledge_integrity": knowledge.integrity_report(),\n''',
    '''                "guidance_actions_applied": bool(use_guidance_actions),\n                "question_policy": question_plan.trace_payload(),\n                "knowledge_integrity": knowledge.integrity_report(),\n''',
)

answering = "app/services/answering.py"
replace_once(
    answering,
    '''    visible_safety_notes = answer.safety_notes[:2]\n    if visible_safety_notes:\n        safety_text = _as_sentences(visible_safety_notes)\n        emergency_phrase = next(\n            (value for value in visible_safety_notes if "cấp cứu ngay" in value.lower()),\n            visible_safety_notes[0],\n        )\n        emergency_phrase = emergency_phrase.split(";")[0]\n        blocks.append(\n            _block(\n                safety_text,\n                kind="urgent" if is_emergency else "paragraph",\n                emphasis=[emergency_phrase],\n            )\n        )\n\n    visible_next_steps = answer.next_steps\n    if len(visible_next_steps) > 4:\n        visible_next_steps = [*visible_next_steps[:3], visible_next_steps[-1]]\n    if visible_next_steps:\n        action_text = _as_sentences(visible_next_steps)\n        blocks.append(\n            _block(\n                action_text,\n                kind="urgent" if is_emergency else "paragraph",\n                emphasis=[visible_next_steps[0] if is_emergency else ""],\n            )\n        )\n\n    visible_questions = answer.questions[:3]\n''',
    '''    # Response contract: tell the user what to do before expanding the\n    # safety-net. This is especially important in emergencies, where action\n    # must never be delayed by explanatory prose or follow-up questions.\n    visible_next_steps = answer.next_steps\n    if len(visible_next_steps) > 4:\n        visible_next_steps = [*visible_next_steps[:3], visible_next_steps[-1]]\n    if visible_next_steps:\n        action_text = _as_sentences(visible_next_steps)\n        blocks.append(\n            _block(\n                action_text,\n                kind="urgent" if is_emergency else "paragraph",\n                emphasis=[visible_next_steps[0] if is_emergency else ""],\n            )\n        )\n\n    visible_safety_notes = answer.safety_notes[:2]\n    if visible_safety_notes:\n        safety_text = _as_sentences(visible_safety_notes)\n        emergency_phrase = next(\n            (value for value in visible_safety_notes if "cấp cứu ngay" in value.lower()),\n            visible_safety_notes[0],\n        )\n        emergency_phrase = emergency_phrase.split(";")[0]\n        blocks.append(\n            _block(\n                safety_text,\n                kind="urgent" if is_emergency else "paragraph",\n                emphasis=[emergency_phrase],\n            )\n        )\n\n    # The clinical dialogue policy normally returns <=2 questions. Keep a\n    # renderer-side cap as a final user-burden guard for non-triage intents.\n    visible_questions = answer.questions[:2]\n''',
)

print("dialogue policy integration patch staged")
