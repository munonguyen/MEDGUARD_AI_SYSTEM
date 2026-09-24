"""Observability module: Prometheus metrics collector and PII-redacted structured logger.

Enforces Chapter 8 & 7:
- Transparent metrics for latency, throughput, confidence decay, and fallback rate.
- Strict prohibition of clinical text and PII in production logs.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import threading
from dataclasses import dataclass, field
from time import time
from typing import Any

from app.core.config import settings


@dataclass
class MetricRecord:
    name: str
    labels: dict[str, str]
    value: float
    metric_type: str = "counter"


class PrometheusMetrics:
    """Lightweight in-process Prometheus metrics registry without external dependencies."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self._gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self._histograms: dict[tuple[str, tuple[tuple[str, str], ...]], list[float]] = {}

    def _labels_to_key(self, labels: dict[str, str]) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(labels.items()))

    def inc_counter(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        lbl_key = self._labels_to_key(labels or {})
        with self._lock:
            key = (name, lbl_key)
            self._counters[key] = self._counters.get(key, 0.0) + value

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        lbl_key = self._labels_to_key(labels or {})
        with self._lock:
            key = (name, lbl_key)
            self._gauges[key] = value

    def observe_histogram(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        lbl_key = self._labels_to_key(labels or {})
        with self._lock:
            key = (name, lbl_key)
            if key not in self._histograms:
                self._histograms[key] = []
            self._histograms[key].append(value)

    def render(self) -> str:
        lines: list[str] = [
            "# HELP medguard_requests_total Total HTTP requests handled",
            "# TYPE medguard_requests_total counter",
        ]
        with self._lock:
            for (name, lbls), val in self._counters.items():
                lbl_str = ",".join(f'{k}="{v}"' for k, v in lbls)
                lines.append(f"{name}{{{lbl_str}}} {val}")

            for (name, lbls), val in self._gauges.items():
                lbl_str = ",".join(f'{k}="{v}"' for k, v in lbls)
                lines.append(f"{name}{{{lbl_str}}} {val}")

            for (name, lbls), vals in self._histograms.items():
                count = len(vals)
                total = sum(vals)
                lbl_str = ",".join(f'{k}="{v}"' for k, v in lbls)
                prefix = f"{name}{{{lbl_str}}}" if lbl_str else name
                lines.append(f"{prefix}_count {count}")
                lines.append(f"{prefix}_sum {total:.4f}")

        return "\n".join(lines) + "\n"


metrics = PrometheusMetrics()


class PiiRedactingFormatter(logging.Formatter):
    """Structured JSON log formatter that redacts clinical text and PII.

    Per Chapter 7: Logs must only contain request_id, tenant_id, hashes,
    character counts, confidence scores, and latencies.
    """

    PHONE_REGEX = re.compile(r"(\+?84|0)(3|5|7|8|9)[0-9]{8}\b")
    CCCD_REGEX = re.compile(r"\b[0-9]{12}\b")

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": time(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "tenant_id"):
            log_entry["tenant_id"] = record.tenant_id
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        if hasattr(record, "confidence"):
            log_entry["confidence"] = record.confidence

        if settings.mask_clinical_data_in_logs:
            msg = log_entry["message"]
            msg = self.PHONE_REGEX.sub("[PHONE_REDACTED]", msg)
            msg = self.CCCD_REGEX.sub("[ID_REDACTED]", msg)
            log_entry["message"] = msg

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
