from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one target, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "app/knowledge/loader.py",
    '''                if not has_affirmed_problem:
                    proximity = re.compile(
                        r"\\b(?:dau|nhuc|sung|te|yeu)\\b(?:\\s+[a-z0-9]+){0,4}\\s+"
                        r"(?:bap chan|dau goi|co chan|mat ca|ban chan|chan|dui)\\b"
                    )
                    has_affirmed_problem = any(
                        contains_affirmed_phrase(normalized, match.group(0))
                        for match in proximity.finditer(normalized)
                    )
''',
    '''                if not has_affirmed_problem:
                    forward_relation = re.compile(
                        r"\\b(?:dau|nhuc|sung|te|yeu)\\b(?:\\s+[a-z0-9]+){0,4}\\s+"
                        r"(?:bap chan|dau goi|co chan|mat ca|ban chan|chan|dui)\\b"
                    )
                    reverse_relation = re.compile(
                        r"\\b(?:bap chan|dau goi|co chan|mat ca|ban chan|chan|dui)\\b"
                        r"(?:\\s+[a-z0-9]+){0,4}\\s+(?:dau|nhuc|sung|te|yeu)\\b"
                    )
                    has_affirmed_problem = any(
                        contains_affirmed_phrase(normalized, match.group(0))
                        for pattern in (forward_relation, reverse_relation)
                        for match in pattern.finditer(normalized)
                    )
''',
)

print("Round-3 reverse lower-limb relation patch staged successfully")
