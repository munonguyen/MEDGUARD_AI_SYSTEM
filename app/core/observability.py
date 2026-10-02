"""Privacy-safe observability primitives for MedGuard AI.

The public clinical path must not depend on an external monitoring stack.  This
module therefore keeps a small in-process Prometheus-compatible registry and a
PII-redacted structured logger.  Prometheus/Grafana or another collector can
scrape/export these signals without becoming a clinical dependency.

Design constraints:
- never use raw patient text as a metric label;
- avoid tenant identifiers as high-cardinality labels;
- aggregate timing observations instead of retaining unbounded samples;
- emit valid Prometheus ``*_count`` / ``*_sum`` sample names;
- keep request correlation metadata useful without logging clinical payloads.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import threading
from dataclasses import dataclass
from time import time
from typing import Any, Iterable

from app.core.config import settings


_METRIC_NAME = re.compile(r"^[a-zA-Z_:][a-zA-Z0-9_:]*$")
_LABEL_NAME = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


@dataclass
class MetricRecord:
    name: str
    labels: dict[str, str]
    value: float
    metric_type: str = "counter"


@dataclass
class _AggregateObservation:
    count: int = 0
    total: float = 0.0


def tenant_metric_scope(tenant_id: str, allowed_tenants: Iterable[str]) -> str:
    """Return a bounded, non-identifying tenant label for metrics.

    Tenant IDs are useful for authorization/audit, but are a poor Prometheus
    label: they increase cardinality and can leak deployment/customer names.
    Metrics only need to distinguish configured traffic from anonymous or
    untrusted traffic.  Tenant-specific investigation belongs in the audit
    store, keyed by request ID.
    """

    if not tenant_id or tenant_id == "anonymous":
        return "anonymous"
    return "configured" if tenant_id in set(allowed_tenants) else "untrusted"


class PrometheusMetrics:
    """Small dependency-free Prometheus registry suitable for the API process.

    Histograms are intentionally represented as aggregate count/sum values.
    MedGuard currently does not expose buckets, so retaining every latency
    sample would only create an unbounded process-memory leak.  Real histogram
    buckets can be delegated to a production OpenTelemetry/Prometheus exporter
    later without changing clinical logic.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self._gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self._histograms: dict[
            tuple[str, tuple[tuple[str, str], ...]], _AggregateObservation
        ] = {}

    @staticmethod
    def _validate_metric_name(name: str) -> None:
        if not _METRIC_NAME.fullmatch(name):
            raise ValueError(f"invalid Prometheus metric name: {name!r}")

    @staticmethod
    def _escape_label_value(value: str) -> str:
        return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')

    def _labels_to_key(self, labels: dict[str, str]) -> tuple[tuple[str, str], ...]:
        normalized: list[tuple[str, str]] = []
        for key, value in labels.items():
            if not _LABEL_NAME.fullmatch(key):
                raise ValueError(f"invalid Prometheus label name: {key!r}")
            normalized.append((key, str(value)))
        return tuple(sorted(normalized))

    @classmethod
    def _render_labels(cls, labels: tuple[tuple[str, str], ...]) -> str:
        if not labels:
            return ""
        body = ",".join(f'{key}="{cls._escape_label_value(value)}"' for key, value in labels)
        return "{" + body + "}"

    def inc_counter(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        self._validate_metric_name(name)
        lbl_key = self._labels_to_key(labels or {})
        with self._lock:
            key = (name, lbl_key)
            self._counters[key] = self._counters.get(key, 0.0) + value

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        self._validate_metric_name(name)
        lbl_key = self._labels_to_key(labels or {})
        with self._lock:
            self._gauges[(name, lbl_key)] = value

    def observe_histogram(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        self._validate_metric_name(name)
        lbl_key = self._labels_to_key(labels or {})
        with self._lock:
            observation = self._histograms.setdefault((name, lbl_key), _AggregateObservation())
            observation.count += 1
            observation.total += float(value)

    def render(self) -> str:
        lines: list[str] = [
            "# HELP medguard_requests_total Total HTTP requests handled",
            "# TYPE medguard_requests_total counter",
        ]
        with self._lock:
            for (name, labels), value in sorted(self._counters.items()):
                lines.append(f"{name}{self._render_labels(labels)} {value}")

            for (name, labels), value in sorted(self._gauges.items()):
                lines.append(f"{name}{self._render_labels(labels)} {value}")

            # Prometheus sample names place the suffix before the label set:
            # metric_count{label="x"}, not metric{label="x"}_count.
            for (name, labels), observation in sorted(self._histograms.items()):
                rendered_labels = self._render_labels(labels)
                lines.append(f"{name}_count{rendered_labels} {observation.count}")
                lines.append(f"{name}_sum{rendered_labels} {observation.total:.6f}")

        return "\n".join(lines) + "\n"


metrics = PrometheusMetrics()


class PiiRedactingFormatter(logging.Formatter):
    """Structured JSON formatter for non-clinical operational logs.

    Raw patient prompts/answers are not valid log fields.  Request IDs are the
    correlation mechanism; detailed clinical evidence belongs in the governed,
    tenant-scoped audit store.  These regexes are a final defence against common
    identifiers accidentally reaching an operational message.
    """

    PHONE_REGEX = re.compile(r"(\+?84|0)(3|5|7|8|9)[0-9]{8}\b")
    CCCD_REGEX = re.compile(r"\b[0-9]{12}\b")
    EMAIL_REGEX = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        if settings.mask_clinical_data_in_logs:
            message = self.PHONE_REGEX.sub("[PHONE_REDACTED]", message)
            message = self.CCCD_REGEX.sub("[ID_REDACTED]", message)
            message = self.EMAIL_REGEX.sub("[EMAIL_REDACTED]", message)

        log_entry: dict[str, Any] = {
            "timestamp": time(),
            "level": record.levelname,
            "logger": record.name,
            "message": message,
        }
        for safe_field in ("request_id", "duration_ms", "confidence", "event_type"):
            if hasattr(record, safe_field):
                log_entry[safe_field] = getattr(record, safe_field)

        # Never emit the raw tenant identifier in operational logs.  The audit
        # database retains tenant-scoped evidence when authorized.
        if hasattr(record, "tenant_scope"):
            log_entry["tenant_scope"] = record.tenant_scope

        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("medguard")
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(PiiRedactingFormatter())
        logger.addHandler(handler)
    return logger


logger = setup_logging()
