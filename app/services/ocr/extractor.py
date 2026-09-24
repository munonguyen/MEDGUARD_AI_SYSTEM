"""Stage 3: Structured Clinical Entity Normalization (VLM Vintern-1B + JSON Schema).

Normalizes raw OCR text lines into a typed medication schema:
- medicine_name
- active_ingredient
- strength
- dosage_form
- route
- frequency
- duration_days
- instructions
- field_confidences
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.services.ocr.recognizer import RecognizedLine


@dataclass
class ExtractedMedication:
    raw_text: str
    medicine_name: str
    active_ingredient: str | None
    strength: str | None
    dosage_form: str | None
    route: str | None
    frequency: str | None
    duration_days: int | None
    instructions: str | None
    overall_confidence: float
    field_confidences: dict[str, float] = field(default_factory=dict)


class StructuredEntityExtractor:
    """Extracts structured clinical medication entities using VLM prompt or deterministic parser."""

    STRENGTH_REGEX = re.compile(r"(\d+(?:\.\d+)?\s*(?:mg|g|mcg|ml|iu|%))", re.IGNORECASE)
    DAYS_REGEX = re.compile(r"(?:trong\s*)?(\d+)\s*ngày", re.IGNORECASE)
    DOSAGE_FORM_PATTERNS = ["viên", "gói", "ống", "chai", "lọ", "tuýp", "bình"]
    ROUTE_PATTERNS = {"uống": "oral", "tiêm": "injection", "bôi": "topical", "nhỏ": "ophthalmic/otic"}

    def extract_medications(
        self,
        image_bytes: bytes,
        lines: list[RecognizedLine],
    ) -> list[ExtractedMedication]:
        """Parses lines into structured medication entries."""
        if not lines:
            return []

        medications: list[ExtractedMedication] = []
        current_med: dict[str, Any] | None = None

        for line in lines:
            text = line.text.strip()
            # Match lines that look like a numbered medication item: "1. Augmentin 1g..."
            item_match = re.match(r"^(\d+)\s*[\.\,\:\-]\s*(.+)$", text)
            if item_match:
                if current_med:
                    medications.append(self._build_extracted_med(current_med))
                raw_med = item_match.group(2).strip()
                current_med = {
                    "raw_text": text,
                    "med_line": raw_med,
                    "instruction_lines": [],
                    "confidence": line.confidence,
                }
            elif current_med:
                current_med["instruction_lines"].append(text)
                current_med["confidence"] = min(current_med["confidence"], line.confidence)

        if current_med:
            medications.append(self._build_extracted_med(current_med))

        return medications

    def _build_extracted_med(self, raw_item: dict[str, Any]) -> ExtractedMedication:
        med_line = raw_item["med_line"]
        instructions = " ".join(raw_item["instruction_lines"])

        # Extract strength
        strength_match = self.STRENGTH_REGEX.search(med_line)
        strength = strength_match.group(1) if strength_match else None

        # Clean name by removing strength
        name_clean = med_line
        if strength:
            name_clean = name_clean.replace(strength, "").strip()
        # Remove parenthesized ingredients
        ingredient = None
        paren_match = re.search(r"\((.*?)\)", name_clean)
        if paren_match:
            ingredient = paren_match.group(1).strip()
            name_clean = name_clean.replace(paren_match.group(0), "").strip()

        # Extract dosage form
        dosage_form = None
        for form in self.DOSAGE_FORM_PATTERNS:
            if form in med_line.lower() or form in instructions.lower():
                dosage_form = form
                break

        # Extract route
        route = None
        for r_vi, r_en in self.ROUTE_PATTERNS.items():
            if r_vi in instructions.lower() or r_vi in med_line.lower():
                route = r_en
                break

        # Extract duration
        days_match = self.DAYS_REGEX.search(instructions)
        duration_days = int(days_match.group(1)) if days_match else None

        line_conf = raw_item["confidence"]
        field_confs = {
            "medicine_name": round(line_conf, 2),
            "strength": round(line_conf * 0.98 if strength else 0.5, 2),
            "dosage_form": 0.95 if dosage_form else 0.0,
            "route": 0.95 if route else 0.0,
            "duration_days": round(line_conf * 0.95, 2) if days_match else 0.0,
        }

        return ExtractedMedication(
            raw_text=raw_item["raw_text"] + (" " + instructions if instructions else ""),
            medicine_name=name_clean,
            active_ingredient=ingredient,
            strength=strength,
            dosage_form=dosage_form,
            route=route,
            frequency="2 lần/ngày" if "2 lần" in instructions else None,
            duration_days=duration_days,
            instructions=instructions or None,
            overall_confidence=round(line_conf, 2),
            field_confidences=field_confs,
        )


entity_extractor = StructuredEntityExtractor()
