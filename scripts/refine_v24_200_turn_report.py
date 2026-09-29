#!/usr/bin/env python3
"""Audit and refine V24 scoring without changing the observed Q/A transcript.

The first V24 run intentionally surfaced two evaluator issues:
1. delete/cancel was counted as successful when no card had ever existed;
2. URGENT expectation mismatches were labeled 'critical' together with hard
   EMERGENCY failures.

This pass keeps every observed response intact and only corrects evaluation
semantics. It writes a new Markdown report rather than hiding the original.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import json
import statistics
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "artifacts" / "v24_200_turn_quality"
JSON_PATH = OUT_DIR / "report.json"
REFINED_JSON = OUT_DIR / "report_refined.json"
REFINED_MD = OUT_DIR / "REPORT_200_QUESTIONS_ANSWERS_REFINED.md"


def _active(snapshot: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in snapshot if item.get("status") == "active"]


def _rewrite_card_delete_score(turn: dict[str, Any], previous_snapshot: list[dict[str, Any]]) -> None:
    expected = turn.get("expected") or {}
    if expected.get("card_assertion") != "removed_or_cancelled":
        return
    ev = turn["evaluation"]
    dims = ev.get("dimensions") or {}
    current = turn.get("card_snapshot") or []
    previous_active = _active(previous_snapshot)
    current_active = _active(current)
    # A delete/cancel action can pass only if an active card existed before the
    # request and is no longer active afterwards. Empty -> empty is NOT success.
    valid_transition = bool(previous_active) and not current_active
    if valid_transition:
        return
    old_card_score = int(dims.get("card_state", 0) or 0)
    if old_card_score:
        ev["score"] = max(0, int(ev.get("score", 0)) - old_card_score)
        dims["card_state"] = 0
    flags = list(ev.get("flags") or [])
    if "CARD_DELETE_WITHOUT_EXISTING_CARD" not in flags:
        flags.append("CARD_DELETE_WITHOUT_EXISTING_CARD")
    ev["flags"] = flags


def _refine_critical_semantics(turn: dict[str, Any]) -> None:
    ev = turn["evaluation"]
    expected = turn.get("expected") or {}
    flags = list(ev.get("flags") or [])
    hard_emergency_expected = (
        expected.get("min_urgency") == "EMERGENCY"
        or bool(expected.get("sticky_emergency"))
    )
    false_reassurance = "FALSE_REASSURANCE" in flags
    emergency_failure = hard_emergency_expected and any(
        flag.startswith("UNDER_TRIAGE")
        or flag == "CONTEXT_LOST_EMERGENCY_MEMORY"
        for flag in flags
    )
    ev["critical_failure"] = bool(false_reassurance or emergency_failure)
    ev["severity_mismatch"] = any(flag.startswith("UNDER_TRIAGE") for flag in flags)
    ev["urgent_expectation_mismatch"] = bool(
        expected.get("min_urgency") == "URGENT" and ev["severity_mismatch"]
    )
    ev["emergency_expectation_failure"] = bool(emergency_failure)


def _recompute(report: dict[str, Any]) -> None:
    all_turns: list[dict[str, Any]] = []
    card_previous: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for conversation in report["conversations_detail"]:
        previous_snapshot: list[dict[str, Any]] = []
        for turn in conversation["turns"]:
            if conversation["category"] == "card_schedule_operations":
                _rewrite_card_delete_score(turn, previous_snapshot)
                previous_snapshot = list(turn.get("card_snapshot") or [])
            _refine_critical_semantics(turn)
            all_turns.append({
                "scenario_id": conversation["scenario_id"],
                "category": conversation["category"],
                **turn,
            })
        conversation["average_score"] = round(
            statistics.mean(t["evaluation"]["score"] for t in conversation["turns"]), 2
        )

    scores = [t["evaluation"]["score"] for t in all_turns]
    report["average_score"] = round(statistics.mean(scores), 2)
    report["median_score"] = round(statistics.median(scores), 2)
    report["minimum_score"] = min(scores)
    report["maximum_score"] = max(scores)
    report["critical_failures"] = sum(t["evaluation"]["critical_failure"] for t in all_turns)
    report["hard_emergency_failures"] = report["critical_failures"]
    report["severity_mismatches"] = sum(t["evaluation"].get("severity_mismatch", False) for t in all_turns)
    report["urgent_expectation_mismatches"] = sum(t["evaluation"].get("urgent_expectation_mismatch", False) for t in all_turns)
    report["emergency_expectation_failures"] = sum(t["evaluation"].get("emergency_expectation_failure", False) for t in all_turns)
    report["below_70"] = sum(t["evaluation"]["score"] < 70 for t in all_turns)

    card_turns = [t for t in all_turns if t["category"] == "card_schedule_operations"]
    report["card_state_failures"] = sum(
        int(t["evaluation"].get("dimensions", {}).get("card_state", 0) or 0) < 35
        for t in card_turns
    )

    intent_matches = sum(
        int(t["evaluation"].get("dimensions", {}).get("routing", 0) or 0) == 15
        for t in all_turns
    )
    context_full = sum(
        int(t["evaluation"].get("dimensions", {}).get("context_continuity", 0) or 0) == 20
        for t in all_turns
    )
    communication_strong = sum(
        int(t["evaluation"].get("dimensions", {}).get("communication", 0) or 0) == 10
        for t in all_turns
    )
    actionability_full = sum(
        int(
            t["evaluation"].get("dimensions", {}).get(
                "actionability",
                t["evaluation"].get("dimensions", {}).get("usefulness", 0),
            ) or 0
        ) == 15
        for t in all_turns
    )
    n = len(all_turns)
    report["objective_rates"] = {
        "http_success_rate": round(
            100 * (1 - sum(any(f.startswith("HTTP_ERROR") for f in t["evaluation"].get("flags", [])) for t in all_turns) / n), 2
        ),
        "expected_intent_match_rate": round(100 * intent_matches / n, 2),
        "full_context_continuity_rate": round(100 * context_full / n, 2),
        "strong_communication_rate": round(100 * communication_strong / n, 2),
        "full_actionability_rate": round(100 * actionability_full / n, 2),
        "card_state_success_rate": round(100 * (len(card_turns) - report["card_state_failures"]) / len(card_turns), 2),
    }

    by_category: dict[str, dict[str, Any]] = {}
    for category in sorted({t["category"] for t in all_turns}):
        subset = [t for t in all_turns if t["category"] == category]
        by_category[category] = {
            "turns": len(subset),
            "average_score": round(statistics.mean(t["evaluation"]["score"] for t in subset), 2),
            "critical_failures": sum(t["evaluation"]["critical_failure"] for t in subset),
            "severity_mismatches": sum(t["evaluation"].get("severity_mismatch", False) for t in subset),
            "below_70": sum(t["evaluation"]["score"] < 70 for t in subset),
        }
    report["category_summary"] = by_category

    card_ops: dict[str, dict[str, int]] = defaultdict(lambda: {"turns": 0, "passed": 0})
    for t in card_turns:
        assertion = str((t.get("expected") or {}).get("card_assertion"))
        card_ops[assertion]["turns"] += 1
        if int(t["evaluation"].get("dimensions", {}).get("card_state", 0) or 0) == 35:
            card_ops[assertion]["passed"] += 1
    report["card_operation_summary"] = dict(card_ops)

    flag_counts = Counter()
    for t in all_turns:
        flag_counts.update(t["evaluation"].get("flags") or [])
    report["top_failure_flags"] = flag_counts.most_common(30)
    report["scoring_audit"] = {
        "version": "v24-refined-1",
        "corrections": [
            "delete/cancel requires an existing active card before the action",
            "only EMERGENCY/sticky-emergency under-triage or false reassurance is labeled critical",
            "URGENT expectation mismatches remain visible as severity mismatches but are not called critical clinical failures",
        ],
    }


def _answer_markdown(turn: dict[str, Any]) -> str:
    # Preserve the exact rendered answer captured during the original run.
    return str(turn.get("answer_markdown") or f"**Reply:** {turn.get('raw_reply') or '-'}")


def _write_markdown(report: dict[str, Any]) -> None:
    rates = report["objective_rates"]
    lines = [
        "# MedGuard AI V24 — Refined 200 Questions / Answers Quality Report",
        "",
        "> **Important:** This is an engineering evaluation on synthetic/de-identified prompts. The Q/A below are the exact observed outputs from the V24 run. Severity expectations are benchmark labels, not clinician-approved ground truth.",
        "",
        "## Corrected executive summary",
        "",
        f"- Conversations: **{report['conversations']}**",
        f"- User questions / evaluated turns: **{report['questions']}**",
        f"- Overall heuristic quality score: **{report['average_score']}/100**",
        f"- Median: **{report['median_score']}/100**",
        f"- Hard emergency safety/context failures: **{report['hard_emergency_failures']}**",
        f"- All severity expectation mismatches: **{report['severity_mismatches']}**",
        f"- Of those, URGENT expectation mismatches (not labeled critical): **{report['urgent_expectation_mismatches']}**",
        f"- Turns below 70/100: **{report['below_70']}**",
        f"- p95 response latency: **{report['p95_latency_ms']:.1f} ms**",
        f"- Card-operation turns: **{report['card_turns']}**",
        f"- Card persisted-state failures: **{report['card_state_failures']} / {report['card_turns']}**",
        "",
        "## Objective observed rates",
        "",
        f"- HTTP success: **{rates['http_success_rate']}%**",
        f"- Expected intent match: **{rates['expected_intent_match_rate']}%**",
        f"- Full context-continuity score: **{rates['full_context_continuity_rate']}%**",
        f"- Strong communication score: **{rates['strong_communication_rate']}%**",
        f"- Full actionability score: **{rates['full_actionability_rate']}%**",
        f"- Persisted card-state success: **{rates['card_state_success_rate']}%**",
        "",
        "## Card operation results",
        "",
        "| Operation | Turns | Persisted-state pass |",
        "|---|---:|---:|",
    ]
    for name, value in report["card_operation_summary"].items():
        lines.append(f"| {name} | {value['turns']} | {value['passed']} |")

    lines.extend([
        "",
        "## Category summary",
        "",
        "| Category | Turns | Avg /100 | Hard critical | Severity mismatches | Below 70 |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for category, value in report["category_summary"].items():
        lines.append(
            f"| {category} | {value['turns']} | {value['average_score']} | {value['critical_failures']} | {value['severity_mismatches']} | {value['below_70']} |"
        )

    lines.extend([
        "",
        "## Scoring audit",
        "",
        "This refined report fixes two scoring issues discovered after the first run: an empty→empty delete is no longer counted as a card success, and an URGENT-label mismatch is no longer called a critical clinical failure. The underlying questions and answers are unchanged.",
        "",
        "## Full 200-question transcript",
        "",
    ])

    for conversation in report["conversations_detail"]:
        lines.extend([
            f"## {conversation['scenario_id']} — {conversation['title']}",
            "",
            f"- Category: `{conversation['category']}`",
            f"- Context ref: `{conversation['patient_ref']}`",
            f"- Conversation average: **{conversation['average_score']}/100**",
            "",
        ])
        for turn in conversation["turns"]:
            ev = turn["evaluation"]
            lines.extend([
                f"### Question {turn['global_question_number']} — Turn {turn['turn']}",
                "",
                f"**User:** {turn['question']}",
                "",
                _answer_markdown(turn),
                "",
                f"**Observed:** intent=`{ev.get('intent')}` · status=`{ev.get('status')}` · urgency=`{ev.get('urgency')}` · latency=`{ev.get('latency_ms')} ms`",
                "",
                f"**Refined quality score:** **{ev['score']}/{ev['maximum']}** · hard_critical_failure=`{str(ev.get('critical_failure', False)).lower()}` · severity_mismatch=`{str(ev.get('severity_mismatch', False)).lower()}`",
                "",
                f"**Dimensions:** `{json.dumps(ev.get('dimensions') or {}, ensure_ascii=False, separators=(',', ':'))}`",
                "",
                f"**Flags:** {', '.join(ev.get('flags') or []) if ev.get('flags') else 'None'}",
                "",
            ])
            if (turn.get("expected") or {}).get("card_assertion"):
                lines.extend([
                    f"**Card expectation:** `{turn['expected']['card_assertion']}` · expected_hour=`{turn['expected'].get('expected_hour')}`",
                    "",
                    "**Persisted card snapshot:**",
                    "```json",
                    json.dumps(turn.get("card_snapshot") or [], ensure_ascii=False, indent=2),
                    "```",
                    "",
                ])
    REFINED_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    report = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    _recompute(report)
    REFINED_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_markdown(report)
    print(
        f"refined questions={report['questions']} average={report['average_score']}/100 "
        f"hard_critical={report['hard_emergency_failures']} severity_mismatches={report['severity_mismatches']} "
        f"below70={report['below_70']} card_failures={report['card_state_failures']}/{report['card_turns']} "
        f"intent_match={report['objective_rates']['expected_intent_match_rate']}%"
    )
    print(f"refined_markdown={REFINED_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
