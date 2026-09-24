from app.services.decision_audit import decision_audit_store
from app.services.metrics_exporter import metrics_collector


def test_decision_audit_logging():
    record = decision_audit_store.log_decision(
        tenant_id="tenant-demo",
        request_id="req_test_001",
        trace_id="tr_test_001",
        triage_decision="EMERGENCY",
        decision_sources=["gate0_floor", "gate3_jev"],
        confidence=0.985,
        safety_invariants_enforced=["no_home_monitoring", "emergency_floor_locked"],
        metadata={"symptom": "đau ngực"},
    )
    assert record.decision_id.startswith("cdec_")
    assert record.triage_decision == "EMERGENCY"
    assert record.candidate_version == "v8-candidate-tri-gate"
    assert "gate3_jev" in record.decision_sources

    recent = decision_audit_store.list_decisions("tenant-demo")
    assert any(r.decision_id == record.decision_id for r in recent)


def test_observability_metrics_collection():
    metrics_collector.record_triage("EMERGENCY", latency_ms=45.2, jev_invoked=True, jev_cached=True)
    metrics_collector.record_triage("ROUTINE", latency_ms=12.1, jev_invoked=False)
    metrics_collector.record_triage("URGENT", latency_ms=52.8, jev_invoked=True, jev_cached=False)

    snapshot = metrics_collector.get_snapshot()
    assert snapshot.total_triage_requests >= 3
    assert snapshot.triage_distribution["EMERGENCY"] >= 1
    assert snapshot.triage_distribution["ROUTINE"] >= 1
    assert snapshot.jev_invocations >= 2
    assert snapshot.latency_p50_ms > 0
