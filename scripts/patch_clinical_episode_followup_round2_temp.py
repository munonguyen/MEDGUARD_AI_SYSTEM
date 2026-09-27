from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one target, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


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

print("Round-2 clinical episode patch staged successfully")
