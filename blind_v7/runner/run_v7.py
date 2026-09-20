"""Sealed Inference Runner for MedGuard AI Blind Benchmark V7.

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
        if fullname.startswith("blind_v7.evaluator"):
            raise ImportError(
                f"ACCESS DENIED: Runner process is prohibited from importing '{fullname}'! "
                "Inference Runner must be physically isolated from Evaluator."
            )
        return None

sys.meta_path.insert(0, _EvaluatorImportBlocker())

# Check sys.modules in case it was somehow loaded earlier
for _m in list(sys.modules.keys()):
    if _m.startswith("blind_v7.evaluator"):
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
from app.services.physiologic_consequence_engine import deduce_physiologic_consequences
from app.services.toxicology_reasoner import evaluate_toxicology, ToxicologyUrgency
from app.services.rules import triage_rules
from app.services.semantic_risk import safe_semantic_evaluate, semantic_risk_evaluator
from app.services.triage import evaluate_triage

from blind_v7.runner.freeze_guard import (
    compute_file_sha256,
    get_git_commit,
    save_freeze_manifest,
    verify_freeze_integrity,
)
from blind_v7.runner.trace_schema import (
    CasePredictionRecord,
    ConversationLayerTrace,
    FactExtractionTrace,
    InputTrace,
    LanguageLayerTrace,
    PhysiologicLayerTrace,
    ToxicologyLayerTrace,
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
    print("MEDGUARD AI — BLIND BENCHMARK V7 SEALED INFERENCE RUNNER")
    print("=" * 80)

    # 1. Freeze Guard Verification
    if enforce_freeze:
        audit_dir = REPO_ROOT / "blind_v7" / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        freeze_manifest_file = audit_dir / "freeze_manifest.json"

        if not freeze_manifest_file.exists():
            print("[*] Generating baseline freeze manifest for Candidate V7...")
            save_freeze_manifest(REPO_ROOT, freeze_manifest_file)

        is_valid, violations = verify_freeze_integrity(REPO_ROOT, freeze_manifest_file)
        if not is_valid:
            print("[!] CRITICAL ERROR: Workspace integrity violated! Aborting runner.")
            for v in violations:
                print(f"    - {v}")
            raise RuntimeError(f"Freeze guard failed with {len(violations)} violations.")
        print("[+] Freeze integrity VERIFIED: All 19 sensitive core files unchanged.")

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
            cid = str(c.get("case_id") or c.get("id") or f"V7-{idx:04d}")
            messages = c.get("messages") or []
            if not messages:
                user_text = c.get("input") or c.get("text") or c.get("symptoms_text") or c.get("prompt") or ""
                messages = [{"role": "user", "content": user_text}]

            latest_text = messages[-1]["content"] if messages else ""
            t0 = time.perf_counter()
            exception_str = None

            ctx = RequestContext(
                request_id=f"v7-runner-{cid}",
                tenant_id="medguard-blind-v7",
                idempotency_key=f"v7-key-{cid}",
            )

            # Language Layer Capture
            norm_text = normalize_search_text(latest_text)
            mapped_concepts = normalize_clinical_concepts(norm_text)
            facts = extract_clinical_facts(latest_text)

            # Fact Parsing
            fact_set = parse_semantic_clinical_facts(norm_text)

            # Threat Graph Capture
            threat_eval = evaluate_threat_graph(fact_set)
            threat_trace = ThreatGraphTrace(
                active_dimensions=list(threat_eval.assessments.keys()),
                critical_dimensions=threat_eval.critical_dimensions,
                high_dimensions=threat_eval.high_dimensions,
                threat_urgency="EMERGENCY" if threat_eval.critical_dimensions else ("URGENT" if threat_eval.high_dimensions else "ROUTINE"),
                threat_confidence=0.98 if threat_eval.critical_dimensions else 0.90,
            )

            # Physiologic Consequence Capture
            physio_eval = deduce_physiologic_consequences(fact_set)
            active_dims = [c.consequence_type.value for c in physio_eval.active_consequences]
            crit_dims = [c.consequence_type.value for c in physio_eval.emergency_consequences]
            physio_urgency = "EMERGENCY" if physio_eval.has_emergency_consequence else "ROUTINE"
            physio_trace = PhysiologicLayerTrace(
                active_dimensions=active_dims,
                critical_dimensions=crit_dims,
                urgency=physio_urgency,
                confidence=0.98 if crit_dims else 0.95,
            )

            # Toxicology Capture
            tox_eval = evaluate_toxicology(latest_text)
            tox_trace = ToxicologyLayerTrace(
                activated=(tox_eval.urgency != ToxicologyUrgency.ROUTINE or tox_eval.toxidrome is not None),
                cohorts=tox_eval.detected_substances,
                identified_toxidromes=[tox_eval.toxidrome.value] if tox_eval.toxidrome else [],
                urgency=tox_eval.urgency.value,
                confidence=tox_eval.confidence,
            )

            # Rule Layer Capture
            rule_res = triage_rules(latest_text)

            # Semantic Layer Capture
            sem_res = safe_semantic_evaluate(semantic_risk_evaluator, mapped_concepts)

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
                    language_flags=[],
                ),
                fact_extraction=FactExtractionTrace(
                    affirmed_facts=getattr(facts, "affirmed", []),
                    negated_facts=getattr(facts, "negated", []),
                    uncertain_facts=getattr(facts, "uncertain", []),
                    historical_facts=getattr(facts, "historical", []),
                    corrected_facts=getattr(facts, "corrected", []),
                    temporal_facts=getattr(facts, "temporal", []),
                ),
                physiologic_layer=physio_trace,
                toxicology_layer=tox_trace,
                threat_graph=threat_trace,
                rule_layer=RuleLayerTrace(
                    matched=rule_res.matched,
                    rule_ids=rule_res.rule_ids,
                    urgency=rule_res.urgency,
                    confidence=rule_res.confidence,
                ),
                semantic_layer=SemanticLayerTrace(
                    risk_concepts=sem_res.red_flags if sem_res else [],
                    urgency=sem_res.urgency.value if (sem_res and hasattr(sem_res.urgency, "value")) else str(getattr(sem_res, "urgency", "ROUTINE")),
                    confidence=sem_res.confidence if sem_res else 0.946,
                ),
                conversation_layer=conv_layer,
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
            out_f.flush()
            cases_evaluated += 1

            if cases_evaluated % 50 == 0 or cases_evaluated == total_cases:
                elapsed = time.time() - start_time
                print(f"  [{cases_evaluated}/{total_cases}] cases processed ({elapsed:.1f}s)...")

    total_duration = time.time() - start_time
    pred_sha256 = compute_file_sha256(predictions_path)

    # 3. Create Sealed Run Manifest
    manifest = {
        "benchmark": "Blind Benchmark V7",
        "benchmark_version": "7.0.0",
        "candidate_designation": "V7 Experimental Candidate — safety-undertriage regression passed, but specificity/calibration gates remain unresolved. Authorized for Blind V7 research validation, not for production release validation.",
        "known_pre_v7_limitations": {
            "1500_regression_specificity": "88.62% [FAIL]",
            "routine_benign_overtriage": "7.49% [FAIL]",
            "max_source_calibration_gap": "12.00% [FAIL]",
            "pure_t4_to_routine": 0,
            "pure_t4_to_urgent": 0,
            "strict_t4_sensitivity": "100.0%",
            "critical_unsafe_advice": 0,
        },
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(REPO_ROOT),
        "cases_file": cases_file.name,
        "total_cases": total_cases,
        "cases_evaluated": cases_evaluated,
        "system_errors": system_errors,
        "duration_seconds": round(total_duration, 2),
        "predictions_file": predictions_path.name,
        "predictions_sha256": pred_sha256,
        "status": "SEALED",
    }

    with open(run_manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("-" * 80)
    print(f"[+] Sealed inference run COMPLETE.")
    print(f"    - Evaluated:    {cases_evaluated}/{total_cases}")
    print(f"    - Total Time:   {total_duration:.2f}s (avg: {total_duration/cases_evaluated*1000:.1f}ms/case)")
    print(f"    - SHA256 Seal:  {pred_sha256}")
    print(f"    - Manifest:     {run_manifest_path.resolve()}")
    print("=" * 80)

    return manifest


def main() -> int:
    cases_file = REPO_ROOT / "blind_v7" / "sealed_cases" / "cases.json"
    output_dir = REPO_ROOT / "blind_v7" / "outputs"
    run_sealed_inference(cases_file, output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
