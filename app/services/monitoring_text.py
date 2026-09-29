"""Conservative normalization for explicit home-monitoring measurements.

The function only rewrites a turn when a named metric and a plausible numeric
value occur together.  It does not infer severity and it never extracts an
unlabelled number.  The original user-authored text is preserved separately by
``ChatRequest`` before the canonical routing view is used.
"""

from __future__ import annotations

import re

from app.services.clinical_text import normalize_search_text


def canonicalize_monitoring_measurement(text: str) -> str | None:
    norm = normalize_search_text(text).replace(",", ".")

    spo2 = re.search(r"\bspo2\b[^0-9\n]{0,45}?(\d{2,3}(?:\.\d+)?)\s*%?", norm)
    if spo2:
        value = float(spo2.group(1))
        if 50 <= value <= 100:
            return f"SpO2 {value:g}%. {text}"

    pressure = re.search(
        r"\b(?:huyet ap|ha)\b[^0-9\n]{0,45}?(\d{2,3})\s*/\s*(\d{2,3})(?:\s*mmhg)?",
        norm,
    )
    if pressure:
        systolic, diastolic = int(pressure.group(1)), int(pressure.group(2))
        if 40 <= systolic <= 300 and 20 <= diastolic <= 200:
            return f"Huyết áp {systolic}/{diastolic} mmHg. {text}"

    heart_rate = re.search(
        r"\b(?:nhip tim|mach)\b[^0-9\n]{0,45}?(\d{2,3})(?:\s*(?:lan\s*/?\s*phut|bpm))?",
        norm,
    )
    if heart_rate:
        value = int(heart_rate.group(1))
        if 20 <= value <= 300:
            return f"Nhịp tim {value} bpm. {text}"

    temperature = re.search(
        r"\b(?:nhiet do|than nhiet|sot)\b[^0-9\n]{0,45}?((?:3[5-9]|4[0-3])(?:\.\d+)?)"
        r"(?:\s*(?:do\s*c|°c|c))?",
        norm,
    )
    if temperature:
        value = float(temperature.group(1))
        if 25 <= value <= 45:
            return f"Nhiệt độ {value:g} C. {text}"

    glucose = re.search(
        r"\b(?:duong huyet|glucose)\b[^0-9\n]{0,45}?(\d{2,4}(?:\.\d+)?)"
        r"(?:\s*(mg\s*/?\s*dl|mmol\s*/?\s*l))?",
        norm,
    )
    if glucose:
        value = float(glucose.group(1))
        unit_raw = glucose.group(2) or "mg/dl"
        unit = "mmol/L" if "mmol" in unit_raw else "mg/dL"
        if unit == "mg/dL" and 0 <= value <= 1500:
            return f"Đường huyết {value:g} mg/dL. {text}"
        if unit == "mmol/L" and 0 <= value <= 50:
            # Chat's current monitoring domain stores glucose in mg/dL only;
            # retain the original turn rather than silently converting units.
            return None

    return None
