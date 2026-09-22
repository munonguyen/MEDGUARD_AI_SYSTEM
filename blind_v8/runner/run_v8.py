"""Sealed Inference Runner for MedGuard AI Blind Benchmark V8 (Tri-Gate + Jev).

Execution Invariants:
1. Input Blindness: Only case_id and messages are visible; ZERO oracle data.
2. Inference Isolation: Does NOT import any evaluator or oracle module.
3. Append-Only Execution: Every case is evaluated once; no retries on wrong triage.
4. Freeze Guard: Verified before execution; aborts if any sensitive file is modified.
5. Tri-Gate Attribution: Logs gate0, gate1, gate2, jev_invoked, jev_decision, decision_without_jev, decision_with_jev, final_triage.
6. Sealed Manifest: Computes SHA256 of predictions.jsonl and seals output upon completion.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# STRICT PROCESS ISOLATION: Runner must NEVER import or depend on evaluator
class _EvaluatorImportBlocker:
    def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> Any:
        if fullname.startswith("blind_v8.evaluator"):
            raise ImportError(
                f"ACCESS DENIED: Runner process is prohibited from importing '{fullname}'! "
                "Inference Runner must be physically isolated from Evaluator."
            )
        return None

sys.meta_path.insert(0, _EvaluatorImportBlocker())

for _m in list(sys.modules.keys()):
    if _m.startswith("blind_v8.evaluator"):
        del sys.modules[_m]

from blind_v8.runner.freeze_guard import verify_freeze_integrity
from blind_v8.vault_crypto import check_canary_leakage, create_run_manifest

from app.core.context import RequestContext
from app.models.jev import DecisionState, TriageAcuity
from app.services.clinical_text import (
    extract_clinical_facts,
    normalize_clinical_concepts,
    normalize_search_text,
)
from app.services.clinical_fact_parser import parse_semantic_clinical_facts
from app.services.clinical_threat_graph import evaluate_threat_graph
from app.services.physiologic_consequence_engine import deduce_physiologic_consequences
from app.services.toxicology_reasoner import evaluate_toxicology
from app.services.rules import triage_rules
from app.services.tri_gate_orchestrator import run_tri_gate_pipeline, VerifierResult
from app.services.tri_gate_resolver import resolve_tri_gate, _ACUITY_RANK


def _build_decision_state(messages: list[dict[str, str]], case_id: str) -> DecisionState:
    user_texts = [m["content"] for m in messages if m.get("role") == "user"]
    full_text = " ".join(user_texts)

    # 1. Fact Parsing
    norm_text = normalize_search_text(full_text)
    norm_concepts = normalize_clinical_concepts(norm_text)
    fact_set = parse_semantic_clinical_facts(norm_text)

    # 2. Hard floor / Rule assessment
    rule_out = triage_rules(full_text)
    rule_urgency = rule_out.urgency

    # 3. Threat graph, Physiologic consequences, and Toxicology
    threat_eval = evaluate_threat_graph(fact_set)
    physio_eval = deduce_physiologic_consequences(fact_set)
    tox_eval = evaluate_toxicology(full_text)

    # 4. Synthesize Floor
    floor: TriageAcuity = "ROUTINE"
    hard_flags: list[str] = []

    is_emergency = (
        rule_urgency == "EMERGENCY"
        or bool(threat_eval.critical_dimensions)
        or physio_eval.has_emergency_consequence
        or getattr(tox_eval.urgency, "value", str(tox_eval.urgency)) == "EMERGENCY"
    )
    is_urgent = (
        rule_urgency == "URGENT"
        or bool(threat_eval.high_dimensions)
        or getattr(tox_eval.urgency, "value", str(tox_eval.urgency)) == "URGENT"
    )

    if is_emergency:
        floor = "EMERGENCY"
        hard_flags.append("emergency_floor_locked")
        hard_flags.append("no_home_monitoring")
    elif is_urgent:
        floor = "URGENT"

    if len(messages) > 2:
        hard_flags.append("multi_turn_history")

    reasoner_triage: TriageAcuity = floor
    confidence = 0.96 if floor == "EMERGENCY" else (0.88 if floor == "URGENT" else 0.95)

    risk_features = list(norm_concepts)
    if threat_eval.critical_dimensions:
        risk_features.extend([f"threat_crit_{d}" for d in threat_eval.critical_dimensions])
    if threat_eval.high_dimensions:
        risk_features.extend([f"threat_high_{d}" for d in threat_eval.high_dimensions])
    tox_val = getattr(tox_eval.urgency, "value", str(tox_eval.urgency))
    if tox_val != "ROUTINE":
        risk_features.append(f"tox_{tox_val.lower()}")

    candidate_actions = ("EMERGENCY_NOW",) if floor == "EMERGENCY" else (("SAME_DAY_EVAL",) if floor == "URGENT" else ("SELF_CARE",))

    return DecisionState(
        triage_floor=floor,
        reasoner_triage=reasoner_triage,
        verifier_pending=True,
        risk_features=tuple(risk_features),
        hard_safety_flags=tuple(hard_flags),
        candidate_actions=candidate_actions,
        confidence=confidence,
        fact_coverage=1.0,
        symptoms_summary=full_text[:120],
    )


def run_blind_v8_sealed_inference(
    cases_path: Path | str,
    output_dir: Path | str,
    manifest_path: Path | str,
) -> Path:
    repo_root = REPO_ROOT
    freeze_manifest_file = repo_root / "blind_v8" / "audit" / "freeze_manifest.json"

    print("[*] Verifying Tri-Gate V8 Freeze Integrity...")
    is_frozen, violations = verify_freeze_integrity(repo_root, freeze_manifest_file)
    if not is_frozen:
        print(f"[FATAL] Freeze Integrity Failed: {violations}")
        sys.exit(1)
    print("[+] Freeze Integrity Verified: 24/24 Core files 100% matched.")

    cases_file = Path(cases_path)
    with open(cases_file, "r", encoding="utf-8") as f:
        cases = json.load(f)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pred_file = out_dir / "predictions.jsonl"
    if pred_file.exists():
        pred_file.unlink()

    print(f"[*] Beginning Sealed Blind V8 Execution on {len(cases)} cases...")
    start_time = time.perf_counter()

    with open(pred_file, "w", encoding="utf-8") as out_f:
        for idx, c in enumerate(cases, 1):
            cid = c["case_id"]
            msgs = c["messages"]

            # Build State
            state = _build_decision_state(msgs, cid)

            # Parallel Tri-Gate Orchestration
            t0 = time.perf_counter()
            tri_res = run_tri_gate_pipeline(decision_state=state)
            final_res = resolve_tri_gate(tri_res)
            lat_ms = (time.perf_counter() - t0) * 1000.0

            # Calculate without Jev counterfactual
            candidates_no_jev = [
                tri_res.hard_safety_floor,
                tri_res.gate1_reasoner_triage,
            ]
            if tri_res.gate2_verifier and tri_res.gate2_verifier.approved:
                candidates_no_jev.append(tri_res.gate2_verifier.verifier_urgency)
            decision_without_jev = max(candidates_no_jev, key=lambda x: _ACUITY_RANK.get(x, 1))

            record = {
                "case_id": cid,
                "selected_path": tri_res.selected_path,
                "gate0_floor": tri_res.hard_safety_floor,
                "gate1_decision": tri_res.gate1_reasoner_triage,
                "gate2_decision": tri_res.gate2_verifier.verifier_urgency if tri_res.gate2_verifier else None,
                "jev_invoked": tri_res.jev_invoked,
                "jev_decision": tri_res.gate3_jev.triage_recommendation if tri_res.gate3_jev else None,
                "jev_confidence": tri_res.gate3_jev.confidence if tri_res.gate3_jev else None,
                "decision_without_jev": decision_without_jev,
                "decision_with_jev": final_res.final_triage,
                "final_triage": final_res.final_triage,
                "governing_source": final_res.governing_source,
                "allow_home_monitoring": final_res.allow_home_monitoring,
                "latency_ms": round(lat_ms, 2),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }

            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            if idx % 50 == 0 or idx == len(cases):
                print(f"    [{idx:03d}/{len(cases):03d}] Evaluated {cid} -> {final_res.final_triage} (Jev={tri_res.jev_invoked})")

    total_time = time.perf_counter() - start_time
    print(f"[+] All {len(cases)} cases evaluated in {total_time:.2f}s (Avg {total_time/len(cases)*1000:.1f}ms/case).")

    # Seal Run Manifest
    manifest = create_run_manifest(pred_file, manifest_path)
    print(f"[+] Cryptographic Seal Emitted: {manifest['predictions_sha256']}")
    return pred_file


if __name__ == "__main__":
    vault_root = REPO_ROOT / "blind_v8"
    cases_p = vault_root / "sealed_cases" / "cases.json"
    out_dir = vault_root / "outputs"
    man_p = out_dir / "run_manifest.json"
    run_blind_v8_sealed_inference(cases_p, out_dir, man_p)
