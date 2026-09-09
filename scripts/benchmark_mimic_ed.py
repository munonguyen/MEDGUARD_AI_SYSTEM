"""Exploratory triage benchmark against the deidentified MIMIC-IV-ED demo."""

from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path
import sys
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.models.triage import VitalSigns
from app.services.rules import triage_rules


TRIAGE_FILE = (
    BASE_DIR
    / "datasets"
    / "external"
    / "mimic-iv-ed-demo-2.2"
    / "ed"
    / "triage.csv.gz"
)


def _number(value: str | None) -> float | None:
    try:
        return float(value) if value and value.strip() else None
    except ValueError:
        return None


def _integer(value: str | None) -> int | None:
    number = _number(value)
    return round(number) if number is not None else None


def _temperature_c(value: str | None) -> float | None:
    number = _number(value)
    if number is None:
        return None
    return round((number - 32.0) * 5.0 / 9.0, 2) if number > 50 else number


def _urgency(esi: int) -> str:
    if esi <= 2:
        return "EMERGENCY"
    if esi == 3:
        return "URGENT"
    return "ROUTINE"


def run_mimic_ed_benchmark(path: Path = TRIAGE_FILE) -> dict[str, Any]:
    total_rows = 0
    labeled_rows = 0
    exact_matches = 0
    urgency_matches = 0
    emergency_total = 0
    emergency_detected = 0
    severe_undertriage = 0

    with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            total_rows += 1
            acuity_value = _integer(row.get("acuity"))
            if acuity_value is None or not 1 <= acuity_value <= 5:
                continue
            labeled_rows += 1
            vitals = VitalSigns(
                systolic=_integer(row.get("sbp")),
                diastolic=_integer(row.get("dbp")),
                heart_rate=_integer(row.get("heartrate")),
                temperature_c=_temperature_c(row.get("temperature")),
                spo2=_integer(row.get("o2sat")),
            )
            result = triage_rules(row.get("chiefcomplaint") or "unknown symptom", vitals)
            predicted = result.esi_level or 4
            exact_matches += int(predicted == acuity_value)
            urgency_matches += int(result.urgency == _urgency(acuity_value))
            severe_undertriage += int(predicted - acuity_value >= 2)
            if acuity_value <= 2:
                emergency_total += 1
                emergency_detected += int(result.urgency == "EMERGENCY")

    denominator = labeled_rows or 1
    emergency_denominator = emergency_total or 1
    return {
        "dataset": "mimic-iv-ed-demo-2.2",
        "total_rows": total_rows,
        "labeled_rows": labeled_rows,
        "exact_acuity_accuracy": round(exact_matches / denominator, 4),
        "urgency_accuracy": round(urgency_matches / denominator, 4),
        "severe_undertriage_rate": round(severe_undertriage / denominator, 4),
        "emergency_recall": round(emergency_detected / emergency_denominator, 4),
        "production_evaluable": False,
        "interpretation": (
            "Exploratory distribution-shift signal only; this demo is not a clinical "
            "acceptance dataset and cannot satisfy the production release gate."
        ),
    }


if __name__ == "__main__":
    print(json.dumps(run_mimic_ed_benchmark(), indent=2))
