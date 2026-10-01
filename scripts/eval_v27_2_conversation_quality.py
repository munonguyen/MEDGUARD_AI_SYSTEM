#!/usr/bin/env python3
"""V27.3 hard gate for conversation quality and patient-output hygiene.

The legacy V24 benchmark remains frozen for longitudinal comparability. This
companion gate covers dimensions that the old score does not: current-turn
relevance, context isolation, medication recall, patient-language cleanliness,
anti-template diversity, and structured patient-facing output hygiene.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from typing import Any
import unicodedata


DEFAULT_REPORT = Path("artifacts/v24_200_turn_quality/REPORT_200_QUESTIONS_ANSWERS.md")
DEFAULT_JSON = Path("artifacts/v27_2_conversation_quality/report.json")
_MAX_KEY_POINT_LENGTH = 320


def _norm(value: str) -> str:
    """Normalize benchmark text for Vietnamese-aware semantic checks."""
    decomposed = unicodedata.normalize("NFD", str(value or "").strip().lower())
    normalized = "".join(
        character for character in decomposed if unicodedata.category(character) != "Mn"
    ).replace("đ", "d")
    return re.sub(r"\s+", " ", normalized).strip()


def _field(block: str, label: str) -> str:
    marker = f"**{label}:**"
    start = block.find(marker)
    if start < 0:
        return ""
    content_start = start + len(marker)
    remainder = block[content_start:]
    next_match = re.search(r"\n\*\*[^*\n]+:\*\*", remainder)
    if next_match:
        remainder = remainder[: next_match.start()]
    return remainder.strip()


def _bullet_values(raw: str) -> list[str]:
    values: list[str] = []
    current: list[str] = []
    for raw_line in str(raw or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("- "):
            if current:
                values.append("\n".join(current).strip())
            current = [line[2:].strip()]
        elif current:
            current.append(line)
    if current:
        values.append("\n".join(current).strip())
    return [value for value in values if value]


def _parse(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    conversation_pattern = re.compile(
        r"## (V24-[A-Z]\d+) — (.*?)\n(.*?)(?=\n## V24-[A-Z]\d+|\Z)",
        re.S,
    )
    question_pattern = re.compile(
        r"### Question (\d+) — Turn (\d+)\n\n\*\*User:\*\* (.*?)\n\n"
        r"(.*?)(?=\n### Question \d+ — Turn \d+|\Z)",
        re.S,
    )
    rows: list[dict[str, Any]] = []
    for conversation_id, title, block in conversation_pattern.findall(text):
        category_match = re.search(r"- Category: `([^`]+)`", block)
        category = category_match.group(1) if category_match else "unknown"
        for question_no, turn_no, question, turn_block in question_pattern.findall(block):
            row = {
                "conversation_id": conversation_id,
                "title": title.strip(),
                "category": category,
                "question_no": int(question_no),
                "turn": int(turn_no),
                "question": question.strip(),
                "reply": _field(turn_block, "Reply"),
                "answer_title": _field(turn_block, "Title"),
                "summary": _field(turn_block, "Summary"),
                "key_points_raw": _field(turn_block, "Key points"),
                "next_steps_raw": _field(turn_block, "Next steps"),
                "safety_notes_raw": _field(turn_block, "Safety notes"),
                "questions_raw": _field(turn_block, "Questions"),
                "limitations_raw": _field(turn_block, "Limitations"),
            }
            row["key_points"] = _bullet_values(row["key_points_raw"])
            rows.append(row)
    return rows


def _patient_surface(row: dict[str, Any]) -> str:
    return "\n".join(
        str(row.get(key) or "")
        for key in (
            "reply",
            "answer_title",
            "summary",
            "key_points_raw",
            "next_steps_raw",
            "safety_notes_raw",
            "questions_raw",
            "limitations_raw",
        )
    )


def _machine_language_violations(row: dict[str, Any]) -> list[str]:
    surface = _patient_surface(row)
    patterns = (
        r"\bNONE\b",
        r"\bHIGH\b",
        r"\bMODERATE\b",
        r"\bLOW\b",
        r"\binsufficient_data\b",
        r"\bESI\s*[1-5]\b",
        r"Mức chuyển tuyến hiện tại:",
        r"Mã ưu tiên nội bộ:",
    )
    return [pattern for pattern in patterns if re.search(pattern, surface, re.I)]


def _relevance_violations(row: dict[str, Any]) -> list[str]:
    q = _norm(row["question"])
    r = _norm(row["reply"])
    issues: list[str] = []

    if "huyet ap" in q:
        numbers = re.findall(r"\b\d{2,3}\b", q)
        if numbers and not any(number in r for number in numbers):
            issues.append("monitoring_value_not_reflected")
        if any(stale in r for stale in ("moi thi giac", "nhin man hinh", "dieu tiet va hoi tu")):
            issues.append("cross_intent_headache_leak")

    medicine_names = [
        value
        for value in (
            "warfarin",
            "ibuprofen",
            "aspirin",
            "paracetamol",
            "acetaminophen",
            "lithium",
            "insulin",
        )
        if value in q
    ]
    medication_category = row["category"] == "cross_intent_context_switch" or str(row["category"]).startswith(
        "medication_safety"
    )
    if medicine_names and medication_category:
        if not any(value in r for value in medicine_names):
            issues.append("medication_not_reflected")
        if any(value in r for value in ("can ten thuoc", "ten chinh xac cua thuoc", "thuoc dang can nhac la gi")):
            issues.append("forgot_known_medication")

    thunderclap = (
        "dot ngot" in q and ("du doi" in q or "du doi nhat" in q)
    ) or "du doi nhat tu truoc toi gio" in q
    if thunderclap and any(value in r for value in ("moi thi giac", "nhin man hinh lam moi")):
        if not any(value in r for value in ("khong nen quy", "khong con phu hop", "than kinh cap", "canh bao")):
            issues.append("stale_benign_headache_hypothesis")

    spinal_red_flag = any(
        value in q
        for value in (
            "kho nhac ban chan",
            "te vung quanh mong",
            "te vung yen ngua",
            "kho kiem soat tieu tien",
            "tieu khong tu chu",
        )
    )
    if spinal_red_flag and "co hoc hop ly hon" in r:
        if not any(value in r for value in ("khong con phu hop", "than kinh", "khong nen quy")):
            issues.append("stale_mechanical_spine_hypothesis")

    return issues


def _key_point_signature(value: str) -> str:
    signature = _norm(value).rstrip(".?! ")
    for prefix in (
        "dau hieu da duoc xac nhan tu benh canh hien tai:",
        "dau hieu duoc nhan dien:",
    ):
        if signature.startswith(prefix):
            signature = signature[len(prefix):].strip()
            break
    return signature


def _output_hygiene_violations(
    row: dict[str, Any],
    *,
    conversation_questions: list[str] | None = None,
) -> list[str]:
    issues: list[str] = []
    key_points = list(row.get("key_points") or [])
    key_raw = str(row.get("key_points_raw") or "")
    surface = _patient_surface(row)

    if re.search(r"(?<!\.)\.\.(?!\.)", surface):
        issues.append("duplicate_terminal_punctuation")
    if any("\n" in value for value in key_points):
        issues.append("multiline_key_point")
    if any(len(re.sub(r"\s+", " ", value).strip()) > _MAX_KEY_POINT_LENGTH for value in key_points):
        issues.append("oversized_key_point")

    signatures = [_key_point_signature(value) for value in key_points if _key_point_signature(value)]
    if len(signatures) != len(set(signatures)):
        issues.append("duplicate_semantic_key_point")

    current_question_norm = _norm(str(row.get("question") or ""))
    key_norm = _norm(key_raw)
    if current_question_norm and len(current_question_norm) >= 12 and key_norm.count(current_question_norm) > 1:
        issues.append("current_turn_duplicated_in_key_points")

    history_hits = 0
    for question in conversation_questions or []:
        normalized = _norm(question)
        if len(normalized) >= 12 and normalized in key_norm:
            history_hits += 1
    if history_hits >= 2:
        issues.append("conversation_transcript_leaked_into_key_points")

    return list(dict.fromkeys(issues))


def evaluate(path: Path, *, max_duplicate_ratio: float = 0.15) -> dict[str, Any]:
    rows = _parse(path)
    if not rows:
        raise ValueError("conversation report contains no parsed turns")

    reply_counts = Counter(_norm(row["reply"]) for row in rows)
    duplicate_turns = sum(count for count in reply_counts.values() if count > 1)
    duplicate_ratio = duplicate_turns / len(rows)

    by_conversation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_conversation[row["conversation_id"]].append(row)
    conversations_with_duplicates = 0
    for conversation in by_conversation.values():
        values = [_norm(row["reply"]) for row in conversation]
        if len(values) != len(set(values)):
            conversations_with_duplicates += 1

    machine: list[dict[str, Any]] = []
    relevance: list[dict[str, Any]] = []
    hygiene: list[dict[str, Any]] = []
    conversation_history: dict[str, list[str]] = defaultdict(list)

    for row in rows:
        history = [*conversation_history[row["conversation_id"]], row["question"]]
        machine_issues = _machine_language_violations(row)
        if machine_issues:
            machine.append({"question_no": row["question_no"], "issues": machine_issues})
        relevance_issues = _relevance_violations(row)
        if relevance_issues:
            relevance.append({"question_no": row["question_no"], "issues": relevance_issues})
        hygiene_issues = _output_hygiene_violations(row, conversation_questions=history)
        if hygiene_issues:
            hygiene.append({"question_no": row["question_no"], "issues": hygiene_issues})
        conversation_history[row["conversation_id"]].append(row["question"])

    category_stats: dict[str, dict[str, Any]] = {}
    for category in sorted({row["category"] for row in rows}):
        subset = [row for row in rows if row["category"] == category]
        counts = Counter(_norm(row["reply"]) for row in subset)
        category_stats[category] = {
            "turns": len(subset),
            "unique_replies": len(counts),
            "duplicate_turns": sum(count for count in counts.values() if count > 1),
        }

    gate_passed = (
        duplicate_ratio <= max_duplicate_ratio
        and not machine
        and not relevance
        and not hygiene
    )
    return {
        "gate": "V27.3_CONVERSATION_AND_OUTPUT_QUALITY",
        "turns": len(rows),
        "conversations": len(by_conversation),
        "duplicate_turns": duplicate_turns,
        "duplicate_ratio": round(duplicate_ratio, 4),
        "max_duplicate_ratio": max_duplicate_ratio,
        "conversations_with_exact_duplicates": conversations_with_duplicates,
        "patient_language_violations": machine,
        "relevance_or_memory_violations": relevance,
        "output_hygiene_violations": hygiene,
        "category_stats": category_stats,
        "gate_passed": gate_passed,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--max-duplicate-ratio", type=float, default=0.15)
    args = parser.parse_args()

    report = evaluate(args.input, max_duplicate_ratio=args.max_duplicate_ratio)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["gate_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
