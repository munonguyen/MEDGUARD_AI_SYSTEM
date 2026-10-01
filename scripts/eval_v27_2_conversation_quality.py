#!/usr/bin/env python3
"""V27.2 hard gate for multi-turn conversation quality.

The legacy benchmark is intentionally frozen for longitudinal comparability.
This companion gate checks dimensions that the old 100/100 score did not cover:
current-turn relevance, context isolation, medication recall, patient-language
cleanliness and anti-template diversity.
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


def _norm(value: str) -> str:
    """Normalize benchmark text for Vietnamese-aware semantic checks.

    The hard gate rules intentionally use accent-free tokens so they also work
    for mobile/ASR inputs. Keep this helper dependency-free because the gate is
    a release artifact and must remain runnable even if application imports fail.
    """
    decomposed = unicodedata.normalize("NFD", str(value or "").strip().lower())
    normalized = "".join(
        character for character in decomposed if unicodedata.category(character) != "Mn"
    ).replace("đ", "d")
    return re.sub(r"\s+", " ", normalized).strip()


def _parse(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    conversation_pattern = re.compile(
        r"## (V24-[A-Z]\d+) — (.*?)\n(.*?)(?=\n## V24-[A-Z]\d+|\Z)",
        re.S,
    )
    question_pattern = re.compile(
        r"### Question (\d+) — Turn (\d+)\n\n\*\*User:\*\* (.*?)\n\n"
        r"\*\*Reply:\*\* (.*?)(?=\n\*\*Title:\*\*)",
        re.S,
    )
    rows: list[dict[str, Any]] = []
    for conversation_id, title, block in conversation_pattern.findall(text):
        category_match = re.search(r"- Category: `([^`]+)`", block)
        category = category_match.group(1) if category_match else "unknown"
        for question_no, turn_no, question, reply in question_pattern.findall(block):
            rows.append(
                {
                    "conversation_id": conversation_id,
                    "title": title.strip(),
                    "category": category,
                    "question_no": int(question_no),
                    "turn": int(turn_no),
                    "question": question.strip(),
                    "reply": reply.strip(),
                }
            )
    return rows


def _machine_language_violations(row: dict[str, Any]) -> list[str]:
    reply = row["reply"]
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
    return [pattern for pattern in patterns if re.search(pattern, reply, re.I)]


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
    if medicine_names and row["category"] in {"medication_safety", "cross_intent_context_switch"}:
        if not any(value in r for value in medicine_names):
            issues.append("medication_not_reflected")
        if any(value in r for value in ("can ten thuoc", "ten chinh xac cua thuoc", "thuoc dang can nhac la gi")):
            issues.append("forgot_known_medication")

    thunderclap = (
        "dot ngot" in q
        and ("du doi" in q or "du doi nhat" in q)
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
    for row in rows:
        machine_issues = _machine_language_violations(row)
        if machine_issues:
            machine.append({"question_no": row["question_no"], "issues": machine_issues})
        relevance_issues = _relevance_violations(row)
        if relevance_issues:
            relevance.append({"question_no": row["question_no"], "issues": relevance_issues})

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
    )
    return {
        "gate": "V27.2_CONVERSATION_INTELLIGENCE",
        "turns": len(rows),
        "conversations": len(by_conversation),
        "duplicate_turns": duplicate_turns,
        "duplicate_ratio": round(duplicate_ratio, 4),
        "max_duplicate_ratio": max_duplicate_ratio,
        "conversations_with_exact_duplicates": conversations_with_duplicates,
        "patient_language_violations": machine,
        "relevance_or_memory_violations": relevance,
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
