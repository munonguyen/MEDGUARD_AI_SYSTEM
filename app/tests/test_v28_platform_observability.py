"""Regression tests for V28 platform-observability hardening."""

from __future__ import annotations

import json
import logging

import pytest

from app.core.observability import PiiRedactingFormatter, PrometheusMetrics, tenant_metric_scope
from app.core.config import settings


def test_histogram_rendering_uses_prometheus_suffix_before_labels_and_aggregates() -> None:
    registry = PrometheusMetrics()
    registry.observe_histogram(
        "medguard_stage_duration_seconds",
        0.125,
        labels={"stage": "clinical_context"},
    )
    registry.observe_histogram(
        "medguard_stage_duration_seconds",
        0.375,
        labels={"stage": "clinical_context"},
    )

    rendered = registry.render()
    assert 'medguard_stage_duration_seconds_count{stage="clinical_context"} 2' in rendered
    assert 'medguard_stage_duration_seconds_sum{stage="clinical_context"} 0.500000' in rendered
    assert '{stage="clinical_context"}_count' not in rendered


def test_tenant_ids_are_collapsed_to_bounded_metric_scope() -> None:
    registry = PrometheusMetrics()
    configured = settings.allowed_tenants[0]
    registry.inc_counter(
        "medguard_requests_total",
        labels={"tenant_id": configured, "endpoint": "/v1/chat", "status": "200"},
    )
    registry.inc_counter(
        "medguard_requests_total",
        labels={"tenant_id": "attacker-controlled-tenant", "endpoint": "/v1/chat", "status": "401"},
    )

    rendered = registry.render()
    assert configured not in rendered
    assert "attacker-controlled-tenant" not in rendered
    assert 'tenant_scope="configured"' in rendered
    assert 'tenant_scope="untrusted"' in rendered


def test_tenant_metric_scope_has_only_bounded_values() -> None:
    configured = settings.allowed_tenants[0]
    assert tenant_metric_scope(configured, settings.allowed_tenants) == "configured"
    assert tenant_metric_scope("anonymous", settings.allowed_tenants) == "anonymous"
    assert tenant_metric_scope("random-customer-name", settings.allowed_tenants) == "untrusted"


def test_metric_label_values_are_prometheus_escaped() -> None:
    registry = PrometheusMetrics()
    registry.inc_counter(
        "medguard_test_total",
        labels={"reason": 'bad"value\\with\nnewline'},
    )
    rendered = registry.render()
    assert 'reason="bad\\"value\\\\with\\nnewline"' in rendered


def test_invalid_metric_or_label_names_fail_closed() -> None:
    registry = PrometheusMetrics()
    with pytest.raises(ValueError):
        registry.inc_counter("bad metric name")
    with pytest.raises(ValueError):
        registry.inc_counter("medguard_valid_total", labels={"bad-label": "x"})


def test_structured_log_redacts_common_identifiers_and_does_not_emit_tenant_id() -> None:
    formatter = PiiRedactingFormatter()
    record = logging.LogRecord(
        name="medguard",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="contact 0912345678, 001234567890, patient@example.com",
        args=(),
        exc_info=None,
    )
    record.request_id = "req_observability_test"
    record.tenant_id = "hospital-secret-name"
    record.tenant_scope = "configured"

    payload = json.loads(formatter.format(record))
    assert payload["request_id"] == "req_observability_test"
    assert payload["tenant_scope"] == "configured"
    assert "tenant_id" not in payload
    assert "hospital-secret-name" not in json.dumps(payload)
    assert "0912345678" not in payload["message"]
    assert "001234567890" not in payload["message"]
    assert "patient@example.com" not in payload["message"]
