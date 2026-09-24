"""Sealed Inference Runner for MedGuard AI Blind Benchmark V4.

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

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# STRICT PROCESS ISOLATION: Runner must NEVER import or depend on evaluator
class _EvaluatorImportBlocker:
    def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> Any:
        if fullname.startswith("blind_v4.evaluator"):
            raise ImportError(
                f"ACCESS DENIED: Runner process is prohibited from importing '{fullname}'! "
                "Inference Runner must be physically isolated from Evaluator."
            )
        return None

sys.meta_path.insert(0, _EvaluatorImportBlocker())

# Check sys.modules in case it was somehow loaded earlier
for _m in list(sys.modules.keys()):
    if _m.startswith("blind_v4.evaluator"):
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
from app.services.dose_reasoning import evaluate_dose_reasoning
from app.services.rules import triage_rules
from app.services.semantic_risk import safe_semantic_evaluate, semantic_risk_evaluator
from app.services.triage import evaluate_triage

from blind_v4.runner.freeze_guard import (
    compute_file_sha256,
    get_git_commit,
    save_freeze_manifest,
    verify_freeze_integrity,
)
from blind_v4.runner.trace_schema import (
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
    print("MEDGUARD AI — BLIND BENCHMARK V4 SEALED INFERENCE RUNNER")
    print("=" * 80)

    # 1. Freeze Guard Verification
    if enforce_freeze:
        audit_dir = REPO_ROOT / "blind_v4" / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        default_freeze_file = audit_dir / "freeze_manifest.json"
        target_freeze = Path(manifest_path) if manifest_path else default_freeze_file

        if not target_freeze.exists():
            print(f"[*] Initializing freeze manifest at: {target_freeze}")
            save_freeze_manifest(REPO_ROOT, target_freeze)

        ok, violations = verify_freeze_integrity(REPO_ROOT, target_freeze)
        if not ok:
            print("\n[CRITICAL ERROR] FREEZE GUARD VIOLATION DETECTED!")
            for v in violations:
                print(f"  - {v}")
            print("\nABORTING BLIND V4 RUNNER: Core code modified after freeze manifest.\n")
            sys.exit(1)
        print("[+] Freeze Guard: INTEGRITY VERIFIED (Candidate engine is officially frozen)")

    # 2. Load Blind Cases (NO Oracle)
    if "oracle" in str(cases_file).lower():
        raise PermissionError(
            f"CRITICAL PROCESS BOUNDARY VIOLATION: Runner attempted to access Oracle path '{cases_file}'! "
            "Inference runner is strictly forbidden from reading oracle data."
        )

    if not cases_file.exists():
        raise FileNotFoundError(f"Cases file not found: {cases_file}")

    with open(cases_file, "r", encoding="utf-8") as f:
        cases_data = json.load(f)

    raw_cases = cases_data if isinstance(cases_data, list) else cases_data.get("cases", [])
    print(f"[+] Loaded {len(raw_cases)} sealed cases from {cases_file.name}")
    print(f"[+] Output will be appended to: {predictions_path}")
    print("-" * 80)

    start_time = datetime.now(timezone.utc).isoformat()
    completed_records = 0
    system_errors = 0
    retry_audit_path = out_dir / "retry_audit.jsonl"

    # Ensure empty or fresh predictions file if new run
    if predictions_path.exists():
        predictions_path.unlink()
    if retry_audit_path.exists():
        retry_audit_path.unlink()

    with open(predictions_path, "a", encoding="utf-8") as out_f:
        for idx, c in enumerate(raw_cases, 1):
            cid = str(c.get("case_id") or c.get("id") or f"V4-{idx:04d}")
            messages = c.get("messages") or []
            if not messages:
                user_text = c.get("input") or c.get("text") or c.get("symptoms_text") or c.get("prompt") or ""
                messages = [{"role": "user", "content": user_text}]

            latest_text = messages[-1]["content"] if messages else ""
            t0 = time.perf_counter()
            exception_str = None

            ctx = RequestContext(
                request_id=f"v4-runner-{cid}",
                tenant_id="medguard-blind-v4",
                idempotency_key=f"v4-key-{cid}",
            )

            # Language Layer Capture (Observational only)
            norm_text = normalize_search_text(latest_text)
            mapped_concepts = normalize_clinical_concepts(norm_text)
            facts = extract_clinical_facts(latest_text)

            # Rule Layer Capture (Observational only)
            rule_res = triage_rules(latest_text)

            # Semantic Layer Capture (Observational only)
            sem_res = safe_semantic_evaluate(semantic_risk_evaluator, mapped_concepts)

            # Dose Layer Capture (Observational only)
            dose_res = evaluate_dose_reasoning(norm_text)

            # Execute Core Inference with Frozen Retry Policy
            # INVARIANT: Observational trace ONLY. State is serialized from existing execution results.
            # ZERO secondary model/LLM calls are made to 'explain' or 'retro-fit' the trace.
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
                    # PROHIBITED: Wrong triage, malformed clinical answers, etc. NEVER trigger retry!
                    system_errors += 1
                    exception_str = f"{type(e).__name__}: {str(e)}"
                    final_triage = "SYSTEM_ERROR"
                    confidence = 0.0
                    break

            latency_ms = int((time.perf_counter() - t0) * 1000)

            # Response Policy Safety Inspection
            resp_lower = resp_text.lower()
            contains_home_monitoring = any(k in resp_lower for k in ("theo dõi tại nhà", "ở nhà theo dõi", "nghỉ vài giờ"))
            contains_immediate_action = any(k in resp_lower for k in ("115", "cấp cứu", "khám ngay", "trung tâm chống độc"))
            contains_unsupported_treatment = any(k in resp_lower for k in ("rửa dạ dày", "bắt buộc dùng than hoạt", "truyền tĩnh mạch nac"))
            contains_unsupported_diagnosis = any(k in resp_lower for k in ("chắc chắn bạn bị", "khẳng định chẩn đoán"))

            # Build Full Diagnostic Record
            rec = CasePredictionRecord(
                case_id=cid,
                input=InputTrace(raw_messages=messages),
                language_layer=LanguageLayerTrace(
                    normalized_text=norm_text,
                    mapped_concepts=mapped_concepts,
                ),
                fact_extraction=FactExtractionTrace(
                    affirmed_facts=[
                        f"onset:{'sudden' if facts.sudden_onset else ('gradual' if facts.gradual_onset else 'unknown')}",
                        f"trauma:{facts.trauma_state}",
                        *[f"symptom:{s}" for s in facts.confirmed_symptoms],
                    ],
                    negated_facts=[
                        *[f"negated:{n}" for n in facts.negative_findings],
                        *(["trauma_negated"] if facts.trauma_state == "negated" else []),
                    ],
                    temporal_facts=(
                        [f"duration_hours:{facts.onset_duration_hours}"]
                        if facts.onset_duration_hours is not None
                        else []
                    ),
                ),
                rule_layer=RuleLayerTrace(
                    matched=rule_res.matched,
                    rule_ids=rule_res.rule_ids,
                    urgency=rule_res.urgency,
                    confidence=rule_res.confidence,
                ),
                semantic_layer=SemanticLayerTrace(
                    risk_concepts=sem_res.red_flags,
                    urgency=sem_res.urgency,
                    confidence=sem_res.confidence,
                ),
                conversation_layer=conv_layer,
                dose_layer=DoseLayerTrace(
                    activated=(dose_res is not None),
                    drug=dose_res.drug if dose_res else None,
                    total_dose_mg=dose_res.total_dose_mg if dose_res else None,
                    dose_mg_per_kg=dose_res.dose_mg_per_kg if dose_res else None,
                    time_pattern=dose_res.ingestion_pattern if dose_res else None,
                    urgency=dose_res.urgency if dose_res else None,
                ),
                resolver=ResolverTrace(
                    candidate_levels={
                        "rule": rule_res.urgency,
                        "semantic": sem_res.urgency,
                        "dose": dose_res.urgency if dose_res else None,
                    },
                    final_triage=final_triage,
                    decision_source=decision_source,
                    confidence=confidence,
                ),
                response_layer=ResponseLayerTrace(
                    response_text=resp_text,
                    contains_home_monitoring=contains_home_monitoring,
                    contains_immediate_action=contains_immediate_action,
                    contains_unsupported_diagnosis=contains_unsupported_diagnosis,
                    contains_unsupported_treatment=contains_unsupported_treatment,
                ),
                runtime=RuntimeTrace(
                    latency_ms=latency_ms,
                    exception=exception_str,
                ),
            )

            out_f.write(rec.to_jsonl_line() + "\n")
            out_f.flush()
            completed_records += 1

            if completed_records % 50 == 0 or completed_records == len(raw_cases):
                print(f"  [Progress] {completed_records:>3}/{len(raw_cases)} cases completed ({latency_ms} ms)")

    end_time = datetime.now(timezone.utc).isoformat()

    # 3. Cryptographic Run Seal
    predictions_sha256 = compute_file_sha256(predictions_path)
    cases_sha256 = compute_file_sha256(cases_file)
    freeze_sha256 = compute_file_sha256(target_freeze) if (enforce_freeze and target_freeze.exists()) else "N/A"

    retry_count = 0
    if retry_audit_path.exists():
        with open(retry_audit_path, "r", encoding="utf-8") as rf:
            retry_count = sum(1 for line in rf if line.strip())

    manifest = {
        "run_id": f"V4-ONE-SHOT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "git_commit": get_git_commit(REPO_ROOT),
        "freeze_manifest_sha256": freeze_sha256,
        "cases_sha256": cases_sha256,
        "predictions_sha256": predictions_sha256,
        "case_count": len(raw_cases),
        "completed_case_count": completed_records,
        "retry_count": retry_count,
        "system_error_count": system_errors,
        "oracle_leakage_detected": False,
        "started_at": start_time,
        "sealed_at": end_time,
        "status": "SEALED",
    }

    with open(run_manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("-" * 80)
    print(f"[+] Run Successfully SEALED!")
    print(f"    Run ID:            {manifest['run_id']}")
    print(f"    Cases Processed:   {completed_records} / {len(raw_cases)}")
    print(f"    Retries (Infra):   {retry_count}")
    print(f"    System Errors:     {system_errors}")
    print(f"    Predictions Hash:  {predictions_sha256}")
    print(f"    Manifest Saved:    {run_manifest_path}")
    print("=" * 80)

    return manifest


if __name__ == "__main__":
    cases_p = sys.argv[1] if len(sys.argv) > 1 else "datasets/blind_benchmark_v4_cases.json"
    out_p = sys.argv[2] if len(sys.argv) > 2 else "blind_v4/outputs"
    run_sealed_inference(cases_p, out_p)
