"""Oracle-isolated, append-once inference runner for independent Blind V10.

The runner accepts only case IDs and chat messages. It rejects oracle/cohort
metadata recursively, never imports the evaluator, emits no per-case decisions
to stdout, atomically seals predictions, and has no clinical retry path.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
from enum import Enum
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class _EvaluatorImportBlocker:
    def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> Any:
        if fullname.startswith("blind_v10.evaluator"):
            raise ImportError(f"oracle boundary: runner cannot import {fullname}")
        return None


sys.meta_path.insert(0, _EvaluatorImportBlocker())
for _module in list(sys.modules):
    if _module.startswith("blind_v10.evaluator"):
        del sys.modules[_module]

from app.core.context import RequestContext
from app.models.chat import ChatMessage, ChatRequest
from app.models.jev import DecisionState
from app.services.chat import orchestrate_chat
from app.services.clinical_fact_parser import parse_semantic_clinical_facts
from app.services.clinical_safety_floor import evaluate_clinical_safety_floor
from app.services.clinical_text import normalize_search_text
from app.services.dual_crisis_policy import evaluate_dual_crisis
from app.services.evidence_strength_scorer import score_evidence_strength
from app.services.jev_engine import evaluate_jev_decision
from app.services.ood_guard import evaluate as evaluate_ood
from app.services.response_safety import assess_unsafe_response_content
from app.services.rules import triage_rules
from app.services.semantic_abstraction_lattice import evaluate_abstraction_lattice
from app.services.semantic_relation_extractor import extract_semantic_relations
from app.services.toxicology_signature_router import route_by_toxicity_signature
from blind_v10.freeze_guard import verify_freeze_integrity
from blind_v10.seal import check_canary_leakage, file_sha256, seal_predictions


FORBIDDEN_INPUT_KEYS = {
    "oracle",
    "oracle_triage",
    "expected",
    "expected_triage",
    "acceptable_triage",
    "cohort",
    "pair_id",
    "pair_role",
    "must_detect",
    "must_not_assert",
    "must_not_say",
    "critical_fail_conditions",
    "negative_control_for",
}
_RANK = {"ROUTINE": 1, "URGENT": 2, "EMERGENCY": 3}


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump(mode="json"))
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value


def _normalize_label(value: Any) -> str:
    label = str(value or "ROUTINE").strip().upper()
    if label in {"EMERGENCY", "T4", "HIGH"}:
        return "EMERGENCY"
    if label in {"URGENT", "T3", "MODERATE"}:
        return "URGENT"
    return "ROUTINE"


def _find_forbidden_keys(value: Any, prefix: str = "case") -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            if key_text.lower() in FORBIDDEN_INPUT_KEYS:
                violations.append(f"{prefix}.{key_text}")
            violations.extend(_find_forbidden_keys(item, f"{prefix}.{key_text}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            violations.extend(_find_forbidden_keys(item, f"{prefix}[{index}]"))
    return violations


def load_blind_cases(path: Path, expected_count: int = 300) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload if isinstance(payload, list) else payload.get("cases", [])
    if not isinstance(cases, list) or len(cases) != expected_count:
        raise RuntimeError(f"sealed input must contain exactly {expected_count} cases")
    seen: set[str] = set()
    for index, case in enumerate(cases, 1):
        violations = _find_forbidden_keys(case, f"case[{index}]")
        if violations:
            raise RuntimeError(f"oracle metadata detected in runner input: {violations[:5]}")
        case_id = str(case.get("case_id", "")).strip()
        messages = case.get("messages")
        if not case_id or case_id in seen:
            raise RuntimeError(f"missing or duplicate case_id at input row {index}")
        if not isinstance(messages, list) or not messages:
            raise RuntimeError(f"case {case_id} has no messages")
        if messages[-1].get("role") != "user":
            raise RuntimeError(f"case {case_id} must end with a user message")
        seen.add(case_id)
    return cases


def _git_commit(ref: str = "HEAD") -> str:
    return subprocess.check_output(
        ["git", "rev-parse", f"{ref}^{{commit}}"], cwd=REPO_ROOT, text=True
    ).strip()


def _validate_output_directory(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    existing = [item.name for item in output_dir.iterdir() if item.name != ".gitkeep"]
    if existing:
        raise RuntimeError(
            "one-shot output directory must be empty; existing artifacts: "
            + ", ".join(sorted(existing))
        )


def _extract_response(resp: Any) -> tuple[str, float, str, dict[str, Any], str]:
    result = resp.result if isinstance(resp.result, dict) else {}
    final = _normalize_label(result.get("urgency") or result.get("escalation_level"))
    trace = result.get("trace", {}) or {}
    details = trace.get("details", {}) or {}
    confidence = float(details.get("confidence", result.get("confidence", 0.0)) or 0.0)
    source = str(details.get("resolution_source", result.get("decision_source", "deterministic")))
    return final, confidence, source, details, str(resp.reply or "")


def _composition_valid(advice: str, dual_active: bool) -> bool:
    if not dual_active:
        return False
    normalized = normalize_search_text(advice)
    medical_positions = [pos for token in ("goi 115", "cap cuu y te ngay") if (pos := normalized.find(token)) >= 0]
    support_positions = [pos for token in ("ho tro qua khung hoang", "tu sat", "tu hai") if (pos := normalized.find(token)) >= 0]
    return bool(medical_positions and support_positions and min(medical_positions) < min(support_positions))


def _counterfactual_jev(
    final_triage: str,
    safety_floor: Any,
    facts: Any,
    tox: Any,
) -> tuple[dict[str, Any], str]:
    risk_features: list[str] = []
    if tox.is_emergency_toxidrome:
        risk_features.append("toxic_exposure")
    if safety_floor.end_organ_coupling.is_emergency:
        risk_features.append("acute_functional_loss")
    hard_flags = ("emergency_floor_locked", "no_home_monitoring") if safety_floor.is_emergency else ()
    state = DecisionState(
        triage_floor=safety_floor.disposition,
        reasoner_triage=final_triage,
        risk_features=tuple(risk_features),
        hard_safety_flags=hard_flags,
        confidence=max(float(safety_floor.confidence), 0.60),
        fact_coverage=float(facts.semantic_coverage),
    )
    decision = evaluate_jev_decision(state)
    post = max(
        (final_triage, decision.triage_recommendation),
        key=lambda value: _RANK[value],
    )
    return {
        "mode": "counterfactual_only_not_in_production_resolver",
        "decision_state": _jsonable(state),
        "decision": _jsonable(decision),
    }, post


def _prediction_for_case(case: dict[str, Any], run_id: str) -> dict[str, Any]:
    case_id = str(case["case_id"])
    messages = [
        ChatMessage(role=str(item.get("role", "user")), content=str(item.get("content", "")))
        for item in case["messages"]
    ]
    user_texts = [message.content for message in messages if message.role == "user"]
    latest_text = user_texts[-1]
    full_text = " ".join(user_texts)
    raw_payload = json.dumps(case["messages"], ensure_ascii=False, sort_keys=True).encode("utf-8")

    facts = parse_semantic_clinical_facts(latest_text)
    relations = extract_semantic_relations(latest_text)
    abstractions = evaluate_abstraction_lattice(relations)
    evidence = score_evidence_strength(latest_text)
    floor = evaluate_clinical_safety_floor(latest_text)
    tox = route_by_toxicity_signature(latest_text)
    end_organ = floor.end_organ_coupling
    ood = evaluate_ood(latest_text)
    dual = evaluate_dual_crisis(latest_text, clinical_emergency=floor.is_emergency)
    gate0 = triage_rules(latest_text)

    request = ChatRequest(
        conversation_id=f"blind-v10-{run_id}-{case_id}",
        messages=messages,
    )
    context = RequestContext(
        request_id=f"blind-v10-{run_id}-{case_id}",
        tenant_id="medguard-independent-blind-v10",
        idempotency_key=f"blind-v10-{run_id}-{case_id}",
    )
    started = time.perf_counter()
    response = orchestrate_chat(request, context)
    latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
    final, confidence, source, triage_trace, advice = _extract_response(response)
    jev_trace, post_jev = _counterfactual_jev(final, floor, facts, tox)
    response_safety = assess_unsafe_response_content(
        advice, emergency_case=final == "EMERGENCY"
    )

    return {
        "case_id": case_id,
        "raw_input_hash": sha256(raw_payload).hexdigest(),
        "normalized_input": normalize_search_text(full_text),
        "final_triage": final,
        "confidence": confidence,
        "decision_source": source,
        "advice": advice,
        "latency_ms": latency_ms,
        "response_safety_flags": list(response_safety.categories),
        "provenance": {
            "facts": _jsonable(facts),
            "semantic_relations": _jsonable(relations),
            "abstractions": _jsonable(abstractions),
            "evidence_strength": _jsonable(evidence),
            "clinical_safety_floor": floor.disposition,
            "clinical_safety_floor_trace": _jsonable(floor),
            "ood_detected": ood is not None,
            "ood_verdict": ood.verdict if ood else None,
            "ood_downgrade_revoked": bool(ood and floor.ood_downgrade_revoked),
            "tox_signature": tox.suspected_syndrome,
            "tox_severity": "EMERGENCY" if tox.is_emergency_toxidrome else ("URGENT" if tox.is_toxicology_eligible else "ROUTINE"),
            "tox_is_emergency": tox.is_emergency_toxidrome,
            "tox_trace": _jsonable(tox),
            "end_organ_findings": list(end_organ.coupling_ids),
            "end_organ_trace": _jsonable(end_organ),
            "dual_crisis_active": dual.is_dual_crisis,
            "dual_crisis_medical": dual.emergency_triage_required,
            "dual_crisis_psych": dual.crisis_support_required,
            "dual_crisis_composition_valid": _composition_valid(advice, dual.is_dual_crisis),
            "gate0": _jsonable(gate0),
            "gate1": triage_trace,
            "gate2": {"status": "not_in_production_resolution_path"},
            "jev": jev_trace,
            "pre_jev_decision": final,
            "post_jev_decision": post_jev,
            "without_jev_triage": final,
            "with_jev_triage": post_jev,
            "final_triage": final,
            "response_safety": _jsonable(response_safety),
            "confidence": confidence,
            "decision_source": source,
        },
    }


def run_one_shot(cases_path: Path, output_dir: Path) -> dict[str, Any]:
    freeze_ok, freeze_errors = verify_freeze_integrity()
    if not freeze_ok:
        raise RuntimeError(f"freeze verification failed: {freeze_errors}")
    frozen_commit = _git_commit("v10-blind-frozen")
    if _git_commit("HEAD") != frozen_commit:
        raise RuntimeError("HEAD must exactly match annotated tag v10-blind-frozen")
    cases = load_blind_cases(cases_path)
    _validate_output_directory(output_dir)
    cases_hash = file_sha256(cases_path)
    run_id = cases_hash[:16]
    temp_path = output_dir / ".predictions.in_progress"
    predictions_path = output_dir / "predictions.jsonl"
    seal_path = output_dir / "predictions.seal.json"

    from app.services.chat import background_agent_runner

    original_submit = background_agent_runner.submit
    background_agent_runner.submit = lambda **_values: False  # type: ignore[method-assign]
    try:
        with temp_path.open("x", encoding="utf-8") as handle:
            os.chmod(temp_path, 0o600)
            for index, case in enumerate(cases, 1):
                try:
                    record = _prediction_for_case(case, run_id)
                except Exception as exc:
                    record = {
                        "case_id": str(case.get("case_id")),
                        "final_triage": "ROUTINE",
                        "confidence": 0.0,
                        "decision_source": "system_error",
                        "advice": "",
                        "error": f"{type(exc).__name__}: {exc}",
                        "provenance": {},
                    }
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
                if index % 25 == 0:
                    print(f"processed {index}/300", flush=True)
        temp_path.replace(predictions_path)
    finally:
        background_agent_runner.submit = original_submit  # type: ignore[method-assign]

    canary_ok, canary_message = check_canary_leakage(predictions_path)
    if not canary_ok:
        raise RuntimeError(canary_message)
    seal = seal_predictions(
        predictions_path,
        cases_path,
        seal_path,
        candidate_commit=frozen_commit,
    )
    return {
        "cases_sha256": cases_hash,
        "predictions_sha256": seal["predictions_sha256"],
        "entry_count": seal["entry_count"],
        "canary_scan": canary_message,
        "predictions": str(predictions_path),
        "seal": str(seal_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run_one_shot(args.cases.resolve(), args.output_dir.resolve())
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
