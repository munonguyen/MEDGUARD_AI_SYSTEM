"""Sealed Inference Runner for MedGuard AI Blind Benchmark V5.

Execution Invariants:
1. Input Blindness: Only case_id and messages are visible; ZERO oracle data.
2. Inference Isolation: Does NOT import any evaluator or oracle module.
3. Append-Only Execution: Every case is evaluated once; no retries on wrong triage.
4. Freeze Guard: Verified before execution; aborts if any sensitive file modified.
5. Sealed Manifest: Computes SHA256 of predictions.jsonl and seals output upon completion.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
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
        if fullname.startswith("blind_v5.evaluator"):
            raise ImportError(
                f"ACCESS DENIED: Runner process is prohibited from importing '{fullname}'! "
                "Inference Runner must be physically isolated from Evaluator."
            )
        return None

sys.meta_path.insert(0, _EvaluatorImportBlocker())

# Check sys.modules in case it was somehow loaded earlier
for _m in list(sys.modules.keys()):
    if _m.startswith("blind_v5.evaluator"):
        del sys.modules[_m]

# FROZEN RETRY POLICY (Section 3 of Clinical AI Evaluation Harness Protocol)
MAX_INFRA_RETRIES = 2
ALLOWED_RETRY_EXCEPTIONS = (TimeoutError, ConnectionError, OSError)
# INVARIANT: Clinical outputs (wrong triage, malformed reasoning, unsafe advice) NEVER trigger a retry.

from app.core.context import RequestContext
from app.models.chat import ChatMessage, ChatRequest
from app.models.triage import TriageRequest
from app.services.chat import orchestrate_chat
from app.services.clinical_text import (
    extract_clinical_facts,
    normalize_clinical_concepts,
    normalize_search_text,
)
from app.services.clinical_fact_parser import parse_semantic_clinical_facts
from app.services.clinical_threat_graph import evaluate_threat_graph
from app.services.dose_reasoning import evaluate_dose_reasoning
from app.services.rules import triage_rules
from app.services.semantic_risk import safe_semantic_evaluate, semantic_risk_evaluator
from app.services.triage import evaluate_triage

from blind_v5.runner.freeze_guard import (
    compute_file_sha256,
    get_git_commit,
    save_freeze_manifest,
    verify_freeze_integrity,
)
from blind_v5.runner.trace_schema import (
    CasePredictionRecord,
    ConversationLayerTrace,
    DoseLayerTrace,
    FactExtractionTrace,
    InputTrace,
    LanguageLayerTrace,
    ResolverTrace,
    ResponseLayerTrace,
    RuleLayerTrace,
    RuntimeTrace,
    SemanticLayerTrace,
    ThreatGraphTrace,
)


def run_sealed_inference(
    cases_path: Path | str,
    output_dir: Path | str,
    manifest_path: Path | str | None = None,
    enforce_freeze: bool = True,
) -> dict:
    cases_file = Path(cases_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = out_dir / "predictions.jsonl"
    run_manifest_path = out_dir / "run_manifest.json"

    print("=" * 80)
    print("MEDGUARD AI — BLIND BENCHMARK V5 SEALED INFERENCE RUNNER")
    print("=" * 80)

    # 1. Freeze Guard Verification
    if enforce_freeze:
        audit_dir = REPO_ROOT / "blind_v5" / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        freeze_manifest_file = audit_dir / "freeze_manifest.json"
        
        if not freeze_manifest_file.exists():
            print("[*] Generating baseline freeze manifest for Candidate V5...")
            save_freeze_manifest(REPO_ROOT, freeze_manifest_file)
        
        is_valid, violations = verify_freeze_integrity(REPO_ROOT, freeze_manifest_file)
        if not is_valid:
            print("[!] CRITICAL ERROR: Workspace integrity violated! Aborting runner.")
            for v in violations:
                print(f"    - {v}")
            raise RuntimeError(f"Freeze guard failed with {len(violations)} violations.")
        print("[+] Freeze integrity VERIFIED: All sensitive core files unchanged.")

    # 2. Load Sealed Cases (Contains ONLY case_id and messages)
    with open(cases_file, "r", encoding="utf-8") as f:
        raw_cases = json.load(f)

    print(f"[*] Loaded {len(raw_cases)} sealed cases from {cases_file.name}")
    print("[*] Executing one-shot append-only evaluation...")

    total_cases = len(raw_cases)
    cases_evaluated = 0
    system_errors = 0
    start_time = time.time()
    retry_audit_path = out_dir / "retry_audit.jsonl"

    if predictions_path.exists():
        predictions_path.unlink()
    if retry_audit_path.exists():
        retry_audit_path.unlink()

    with open(predictions_path, "a", encoding="utf-8") as out_f:
        for idx, c in enumerate(raw_cases, 1):
            cid = str(c.get("case_id") or c.get("id") or f"V5-{idx:04d}")
            messages = c.get("messages") or []
            if not messages:
                user_text = c.get("input") or c.get("text") or c.get("symptoms_text") or c.get("prompt") or ""
                messages = [{"role": "user", "content": user_text}]

            latest_text = messages[-1]["content"] if messages else ""
            t0 = time.perf_counter()
            exception_str = None

            ctx = RequestContext(
                request_id=f"v5-runner-{cid}",
                tenant_id="medguard-blind-v5",
                idempotency_key=f"v5-key-{cid}",
            )

            # Language Layer Capture
            norm_text = normalize_search_text(latest_text)
            mapped_concepts = normalize_clinical_concepts(norm_text)
            facts = extract_clinical_facts(latest_text)

            # Threat Graph Capture
            fact_set = parse_semantic_clinical_facts(norm_text)
            threat_eval = evaluate_threat_graph(fact_set)
            threat_trace = ThreatGraphTrace(
                active_dimensions=list(threat_eval.assessments.keys()),
                critical_dimensions=threat_eval.critical_dimensions,
                high_dimensions=threat_eval.high_dimensions,
                threat_urgency="EMERGENCY" if threat_eval.critical_dimensions else ("URGENT" if threat_eval.high_dimensions else "ROUTINE"),
                threat_confidence=0.98 if threat_eval.critical_dimensions else 0.90,
            )

            # Rule Layer Capture
            rule_res = triage_rules(latest_text)

            # Semantic Layer Capture
            sem_res = safe_semantic_evaluate(semantic_risk_evaluator, mapped_concepts)

            # Dose Layer Capture
            dose_res = evaluate_dose_reasoning(norm_text)

            # Execute Core Inference
            final_triage = "ROUTINE"
            decision_source = "hybrid"
            confidence = 0.95
            resp_text = ""
            conv_layer = ConversationLayerTrace()

            attempt = 1
            while True:
                try:
                    if len(messages) > 1:
                        chat_msgs = [ChatMessage(role=m["role"], content=m["content"]) for m in messages]
                        req = ChatRequest(
                            conversation_id=f"conv-{cid}",
                            patient_ref=f"p-{cid}",
                            messages=chat_msgs,
                        )
                        chat_resp = orchestrate_chat(req, ctx)
                        resp_text = chat_resp.reply or ""
                        res_dict = chat_resp.result or {}
                        final_triage = res_dict.get("urgency")
                        if not final_triage:
                            r = res_dict.get("overall_risk")
                            final_triage = "EMERGENCY" if r == "HIGH" else ("URGENT" if r == "MODERATE" else "ROUTINE")
                        decision_source = "conversation"
                        confidence = 0.957 if final_triage == "EMERGENCY" else 0.94
                        conv_layer = ConversationLayerTrace(
                            new_danger=(final_triage == "EMERGENCY"),
                            risk=final_triage,
                            confidence=confidence,
                        )
                    else:
                        t_req = TriageRequest(patient_ref=f"p-{cid}", symptoms_text=latest_text)
                        t_resp = evaluate_triage(t_req, ctx=ctx)
                        final_triage = t_resp.urgency
                        decision_source = t_resp.trace.details.get("resolution_source", "hybrid")
                        confidence = float(t_resp.trace.details.get("confidence", 0.95))
                        resp_text = t_resp.guidance_summary or f"Phân luồng: {final_triage}"
                    break

                except ALLOWED_RETRY_EXCEPTIONS as e:
                    if attempt <= MAX_INFRA_RETRIES:
                        with open(retry_audit_path, "a", encoding="utf-8") as rf:
                            rf.write(json.dumps({
                                "case_id": cid,
                                "attempt": attempt,
                                "retry_reason": "transport_timeout",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "error": str(e),
                            }, ensure_ascii=False) + "\n")
                        attempt += 1
                        time.sleep(0.3)
                        continue
                    else:
                        system_errors += 1
                        exception_str = f"{type(e).__name__}: {str(e)}"
                        final_triage = "SYSTEM_ERROR"
                        confidence = 0.0
                        break

                except Exception as e:
                    system_errors += 1
                    exception_str = f"{type(e).__name__}: {str(e)}"
                    final_triage = "SYSTEM_ERROR"
                    confidence = 0.0
                    break

            latency_ms = int((time.perf_counter() - t0) * 1000)

            # Response Policy Safety Inspection
            resp_lower = resp_text.lower()
            home_monitoring = any(w in resp_lower for w in ["theo dõi tại nhà", "ở nhà theo dõi", "uống nhiều nước và nghỉ ngơi"])
            immediate_action = any(w in resp_lower for w in ["cấp cứu", "khẩn cấp", "115", "đến ngay bệnh viện"])
            unsupported_treatment = any(w in resp_lower for w in ["tự ý dùng kháng sinh", "uống aspirin", "rửa dạ dày"])

            record = CasePredictionRecord(
                case_id=cid,
                input=InputTrace(raw_messages=messages),
                language_layer=LanguageLayerTrace(
                    normalized_text=norm_text,
                    mapped_concepts=[c for c in mapped_concepts.split() if c],
                ),
                fact_extraction=FactExtractionTrace(
                    affirmed_facts=getattr(facts, "confirmed_symptoms", []) if hasattr(facts, "confirmed_symptoms") else (facts.get("affirmed", []) if isinstance(facts, dict) else []),
                    negated_facts=getattr(facts, "negative_findings", []) if hasattr(facts, "negative_findings") else (facts.get("negated", []) if isinstance(facts, dict) else []),
                    uncertain_facts=[],
                    historical_facts=[],
                    corrected_facts=[],
                    temporal_facts=[],
                ),
                threat_graph=threat_trace,
                rule_layer=RuleLayerTrace(
                    matched=rule_res.matched,
                    rule_ids=rule_res.rule_ids if hasattr(rule_res, "rule_ids") else [],
                    urgency=rule_res.urgency,
                    confidence=rule_res.confidence,
                ),
                semantic_layer=SemanticLayerTrace(
                    risk_concepts=sem_res.reasons,
                    urgency=sem_res.urgency,
                    confidence=sem_res.confidence,
                ),
                conversation_layer=conv_layer,
                dose_layer=DoseLayerTrace(
                    activated=(dose_res is not None),
                    drug=getattr(dose_res, "medication_name", None),
                    total_dose_mg=getattr(dose_res, "single_dose_mg", None),
                    dose_mg_per_kg=getattr(dose_res, "estimated_mg_kg", None),
                    time_pattern=getattr(dose_res, "time_pattern", None),
                    urgency=getattr(dose_res, "urgency", None),
                ),
                resolver=ResolverTrace(
                    final_triage=final_triage,
                    decision_source=decision_source,
                    confidence=confidence,
                ),
                response_layer=ResponseLayerTrace(
                    response_text=resp_text,
                    contains_home_monitoring=home_monitoring,
                    contains_immediate_action=immediate_action,
                    contains_unsupported_treatment=unsupported_treatment,
                ),
                runtime=RuntimeTrace(
                    latency_ms=latency_ms,
                    exception=exception_str,
                ),
            )

            out_f.write(record.to_json_line() + "\n")
            cases_evaluated += 1

            if idx % 50 == 0 or idx == total_cases:
                print(f"  [{idx}/{total_cases}] Evaluated ({latency_ms}ms) -> {final_triage}")

    duration = time.time() - start_time
    pred_sha256 = compute_file_sha256(predictions_path)

    run_manifest = {
        "status": "SEALED",
        "benchmark_suite": "Blind Benchmark V5",
        "cases_file": str(cases_file.name),
        "total_cases": total_cases,
        "cases_evaluated": cases_evaluated,
        "system_errors": system_errors,
        "duration_seconds": round(duration, 2),
        "avg_latency_ms": round((duration / max(cases_evaluated, 1)) * 1000, 1),
        "predictions_sha256": pred_sha256,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(REPO_ROOT),
        "candidate_core_commit": "a78ed98391a9339ae61777a2c3d8afbfae79c5e7",
        "frozen_audit_commit": "afb9cc182c5f75120c7036d2a09ac33df92665b7",
    }

    with open(run_manifest_path, "w", encoding="utf-8") as f:
        json.dump(run_manifest, f, indent=2, ensure_ascii=False)

    print("-" * 80)
    print(f"[+] Run Complete! {cases_evaluated}/{total_cases} evaluated in {duration:.1f}s.")
    print(f"[+] SHA256 of predictions: {pred_sha256}")
    print(f"[+] Run Manifest written to: {run_manifest_path}")
    print("=" * 80)

    return run_manifest


if __name__ == "__main__":
    cases_input = sys.argv[1] if len(sys.argv) > 1 else str(REPO_ROOT / "blind_v5" / "sealed_cases" / "cases.json")
    out_dir_input = sys.argv[2] if len(sys.argv) > 2 else str(REPO_ROOT / "blind_v5" / "outputs")
    run_sealed_inference(cases_input, out_dir_input)
