from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one target, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# The state-aware GI tailoring introduced by the primary patch uses regexes.
replace_once(
    "app/services/triage.py",
    "from time import perf_counter\n",
    "import re\nfrom time import perf_counter\n",
)

# "bụng cồn cào" is a concrete GI chief complaint. Without it the episode
# router cannot distinguish a new GI episode from a previous chest emergency.
replace_once(
    "app/services/risk_memory.py",
    '''        "nong rat bung",
        "o chua",
''',
    '''        "nong rat bung",
        "bung con cao",
        "con cao",
        "kho chiu o bung",
        "o chua",
''',
)

# Accent stripping turns both "còn" and "cồn" into "con". A bare "con "
# continuation marker therefore misclassifies "cồn cào" as continuation of a
# previous episode. Keep only semantically specific continuation markers.
replace_once(
    "app/services/risk_memory.py",
    '''    "van ",
    "van con",
    "van bi",
    "con ",
    "ngoai ra",
''',
    '''    "van ",
    "van con",
    "van bi",
    "ngoai ra",
''',
)

# Back-pain guidance needs a relation-aware matcher for natural Vietnamese such
# as "đau ở vùng thắt lưng". It must run before lower-limb detection so an
# explicitly negated "không ... tê chân" cannot hijack the topic.
replace_once(
    "app/knowledge/loader.py",
    '''    def find_symptom_guidance(self, symptoms_text: str) -> dict[str, Any] | None:
        normalized = normalize_search_text(symptoms_text)
        for guidance in self.symptom_guidance:
''',
    '''    def find_symptom_guidance(self, symptoms_text: str) -> dict[str, Any] | None:
        normalized = normalize_search_text(symptoms_text)

        back_problem = any(
            contains_affirmed_phrase(normalized, phrase)
            for phrase in ("dau lung", "moi lung", "dau that lung", "moi that lung", "nhuc lung")
        )
        if not back_problem:
            back_relation = re.compile(
                r"\\b(?:dau|moi|nhuc)\\b(?:\\s+[a-z0-9]+){0,4}\\s+(?:that lung|lung)\\b"
            )
            back_problem = any(
                contains_affirmed_phrase(normalized, match.group(0))
                for match in back_relation.finditer(normalized)
            )
        if back_problem:
            for guidance in self.symptom_guidance:
                if guidance.get("topic") == "back_pain":
                    return guidance

        for guidance in self.symptom_guidance:
''',
)

# Retrieval/guidance availability is separate from disposition authority.
# Even when a deterministic rule locks URGENT, patient-facing summary,
# clarifying questions and safety-net should consume already-known episode
# details instead of falling back to a generic template. Guidance actions and
# self-care remain restricted to their original conservative conditions.
replace_once(
    "app/services/triage.py",
    '''    guidance = knowledge.find_symptom_guidance(payload.symptoms_text)
    use_guidance = guidance is not None and (
        final_urgency == "ROUTINE" or guidance.get("topic") == "lower_limb_pain"
    )
    guidance_summary, guidance_questions = (
        _tailor_guidance(guidance, payload.symptoms_text)
        if use_guidance and guidance is not None
        else (None, [])
    )
    clarifying_questions = guidance_questions if use_guidance else rule.clarifying_questions
''',
    '''    guidance = knowledge.find_symptom_guidance(payload.symptoms_text)
    has_guidance = guidance is not None
    use_guidance_actions = has_guidance and (
        final_urgency == "ROUTINE" or guidance.get("topic") == "lower_limb_pain"
    )
    guidance_summary, guidance_questions = (
        _tailor_guidance(guidance, payload.symptoms_text)
        if has_guidance and guidance is not None
        else (None, [])
    )
    if final_urgency == "URGENT" and guidance_summary:
        guidance_summary = (
            guidance_summary.rstrip()
            + " Do mức độ triệu chứng hiện tại, bạn nên được nhân viên y tế đánh giá trực tiếp sớm trong ngày."
        )
    clarifying_questions = guidance_questions if has_guidance else rule.clarifying_questions
''',
)

replace_once(
    "app/services/triage.py",
    '''        if use_guidance and guidance
        else []
''',
    '''        if use_guidance_actions and guidance
        else []
''',
)

replace_once(
    "app/services/triage.py",
    '''    if use_guidance and guidance and final_urgency == "ROUTINE":
''',
    '''    if use_guidance_actions and guidance and final_urgency == "ROUTINE":
''',
)

replace_once(
    "app/services/triage.py",
    '''    elif use_guidance and guidance and guidance.get("advice"):
''',
    '''    elif use_guidance_actions and guidance and guidance.get("advice"):
''',
)

replace_once(
    "app/services/triage.py",
    '''        self_care=[str(value) for value in guidance.get("self_care", [])] if use_guidance else [],
        safety_net=[str(value) for value in guidance.get("safety_net", [])] if use_guidance else [],
''',
    '''        self_care=[str(value) for value in guidance.get("self_care", [])] if use_guidance_actions else [],
        safety_net=(
            [str(value) for value in guidance.get("safety_net", [])]
            if has_guidance and guidance and final_urgency in {"ROUTINE", "URGENT"}
            else []
        ),
''',
)

replace_once(
    "app/services/triage.py",
    '''                "symptom_guidance": guidance.get("topic") if use_guidance else None,
                "knowledge_integrity": knowledge.integrity_report(),
''',
    '''                "symptom_guidance": guidance.get("topic") if has_guidance and guidance else None,
                "guidance_actions_applied": bool(use_guidance_actions),
                "knowledge_integrity": knowledge.integrity_report(),
''',
)

# The regression must distinguish stale current findings from legitimate future
# safety-net wording. A GI safety-net may mention chest pain as a new warning
# sign; that is not evidence that the prior chest episode leaked into state.
replace_once(
    "app/tests/test_clinical_episode_orchestration.py",
    '''    answer_text = " ".join(block["text"] for block in body["answer"].get("narrative", []))
    assert "đau ngực" not in answer_text.lower()
    assert "khó thở" not in body["answer"]["summary"].lower()
''',
    '''    summary = body["answer"]["summary"].lower()
    current_red_flags = " ".join(body["result"].get("red_flags", [])).lower()
    trace = body["result"]["trace"]["details"]
    assert "đau ngực" not in summary
    assert "khó thở" not in summary
    assert "đau ngực" not in current_red_flags
    assert "tức ngực" not in current_red_flags
    assert trace["conversation_risk"] is None
    assert trace["rule_urgency"] != "EMERGENCY"
''',
)

print("Round-2 clinical episode patch staged successfully")
