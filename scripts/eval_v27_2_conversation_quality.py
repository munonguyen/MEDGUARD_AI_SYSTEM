#!/usr/bin/env python3
"""V27.2/V27.3 hard gate for multi-turn conversation quality.

The legacy V24 benchmark remains frozen for longitudinal comparability. This
companion gate checks dimensions the old score does not cover: current-turn
relevance, context isolation, medication recall, patient-language cleanliness,
false clinical context, false emergency from explicit negation/hypotheticals,
structured-output hygiene and anti-template diversity.
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
    """Normalize benchmark text for Vietnamese-aware semantic checks."""
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
    title = _norm(row.get("title", ""))
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

    # V27.3: anaphylaxis/airway episodes must never inherit the chest-wall
    # anchoring explanation merely because a rash spread onto the chest.
    allergy_airway = any(value in q for value in ("sung moi", "co hong", "nghen", "kho tho")) and any(
        value in title for value in ("di ung", "phan ung", "phan ve")
    )
    if allergy_airway and any(
        value in r
        for value in (
            "dau co/thanh nguc",
            "dau co thanh nguc",
            "dau co/thanh nguc o luot truoc",
            "dau hieu canh bao tim-phoi da xuat hien truoc do",
        )
    ):
        issues.append("allergy_inherited_chest_mechanism")

    # Chemical inhalation may cause chest tightness/dyspnea, but that does not
    # imply an earlier mechanical chest-wall story.
    chemical_episode = any(value in title for value in ("hoa chat", "phoi nhiem"))
    if chemical_episode and any(
        value in r
        for value in (
            "dau co/thanh nguc",
            "dau co thanh nguc",
            "dac diem dau co",
            "luot truoc khong du de giai thich",
        )
    ):
        issues.append("chemical_inhalation_inherited_chest_mechanism")

    # Respiratory inability to speak a long sentence is not aphasia/focal
    # neurology. The emergency action may remain correct; the explanation must
    # stay respiratory.
    respiratory_speech = (
        any(value in q for value in ("kho noi cau dai", "khong noi tron cau", "noi cau dai"))
        and any(value in q for value in ("hut hoi", "kho tho", "tho gap"))
    )
    if respiratory_speech and any(
        value in r
        for value in (
            "dau hieu than kinh",
            "dau dau khoi phat",
            "yeu liet",
            "bien co than kinh",
            "moi mat hoac cang co",
        )
    ):
        issues.append("respiratory_speech_misread_as_neurologic")

    # Explicit absence of weakness must not be rewritten as newly present motor
    # deficit or used to create a false emergency.
    negated_weakness = bool(
        re.search(r"\b(?:khong|chua|chang)(?: co| bi| thay)?(?: te| te ran){0,2} (?:yeu|liet) (?:chan|tay)\b", q)
    )
    if negated_weakness and any(
        value in r
        for value in (
            "yeu chan moi xuat hien",
            "dau hieu khiem khuyet than kinh khu tru cap tinh",
            "goi 115",
            "khoa cap cuu",
        )
    ):
        issues.append("negated_weakness_promoted_to_emergency")

    # A user who explicitly says the medicine has not been taken may ask what
    # to do *if* symptoms worsen. That hypothetical must not be reported as an
    # overdose that already happened.
    no_ingestion_hypothetical = (
        any(value in q for value in ("chua uong", "chua dung", "khong uong", "khong dung"))
        and "neu" in q
        and "thuoc" in q
    )
    if no_ingestion_hypothetical:
        if any(value in r for value in ("ngo doc cap", "qua lieu", "da uong qua lieu")):
            issues.append("no_ingestion_reported_as_overdose")
        if r.startswith("goi 115") and not any(
            current in q
            for current in (
                "dang lo mo",
                "dang ngat",
                "bat tinh",
                "kho tho",
                "co giat",
                "khong danh thuc duoc",
            )
        ):
            issues.append("hypothetical_worsening_promoted_to_current_emergency")

    return issues


def _looks_like_transcript_blob(value: str) -> bool:
    lines = [re.sub(r"\s+", " ", line).strip().lower() for line in str(value).splitlines() if line.strip()]
    if len(lines) < 3:
        return False
    repeated = len(lines) >= 4 and len(set(line.rstrip("?.! ") for line in lines)) * 2 <= len(lines)
    oversized = len(value) > 420 and len(lines) >= 3
    return repeated or oversized


def _structured_output_violations(markdown_path: Path) -> list[dict[str, Any]]:
    """Inspect the companion frozen JSON when present for UI-field hygiene."""
    json_path = markdown_path.with_name("report.json")
    if not json_path.exists():
        return []
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [{"question_no": None, "issues": ["invalid_companion_v24_json"]}]

    violations: list[dict[str, Any]] = []
    for conversation in payload.get("conversations_detail", []):
        for turn in conversation.get("turns", []):
            answer = turn.get("answer") if isinstance(turn.get("answer"), dict) else {}
            issues: list[str] = []
            for point in answer.get("key_points", []) or []:
                if _looks_like_transcript_blob(str(point)):
                    issues.append("transcript_blob_in_key_points")
                    break
            visible_fields: list[str] = [
                str(answer.get("title") or ""),
                str(answer.get("summary") or ""),
                *[str(value) for value in (answer.get("key_points") or [])],
                *[str(value) for value in (answer.get("next_steps") or [])],
                *[str(value) for value in (answer.get("safety_notes") or [])],
            ]
            if any(re.search(r"[)\]]\.\.", value) for value in visible_fields):
                issues.append("double_terminal_punctuation")
            if issues:
                violations.append(
                    {
                        "question_no": turn.get("global_question_number"),
                        "issues": list(dict.fromkeys(issues)),
                    }
                )
    return violations


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

    structured = _structured_output_violations(path)

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
        and not structured
    )
    return {
        "gate": "V27.3_OUTPUT_QUALITY_HARDENING",
        "turns": len(rows),
        "conversations": len(by_conversation),
        "duplicate_turns": duplicate_turns,
        "duplicate_ratio": round(duplicate_ratio, 4),
        "max_duplicate_ratio": max_duplicate_ratio,
        "conversations_with_exact_duplicates": conversations_with_duplicates,
        "patient_language_violations": machine,
        "relevance_or_memory_violations": relevance,
        "structured_output_violations": structured,
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
