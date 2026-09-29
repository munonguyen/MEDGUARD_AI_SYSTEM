"""Versioned knowledge loader with SHA-256 integrity verification.

Each knowledge file carries a ``_meta.version`` field. The loader reads all
JSON knowledge files at import time and makes them available through a typed
API. ``KnowledgeStore.integrity_report()`` returns per-file SHA-256 digests
so that audit records can reference the exact knowledge snapshot used.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.services.clinical_text import contains_affirmed_phrase, normalize_search_text


_KNOWLEDGE_DIR = Path(__file__).resolve().parent

_FILE_NAMES = (
    "drug_interactions.json",
    "allergy_cross_matrix.json",
    "red_flag_protocols.json",
    "contraindications.json",
    "atc_codes.json",
    "icd10_codes.json",
    "monitoring_rules.json",
    "product_registry.json",
    "medication_incident_protocols.json",
)


@dataclass(frozen=True)
class KnowledgeFile:
    name: str
    version: str
    sha256: str
    data: dict[str, Any]


@dataclass
class KnowledgeStore:
    """Process-local, immutable knowledge snapshot loaded once at startup."""

    files: dict[str, KnowledgeFile] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Typed accessors
    # ------------------------------------------------------------------

    @property
    def drug_interactions(self) -> list[dict[str, Any]]:
        return self.files.get("drug_interactions.json", KnowledgeFile("", "", "", {})).data.get("interactions", [])

    @property
    def allergy_groups(self) -> list[dict[str, Any]]:
        return self.files.get("allergy_cross_matrix.json", KnowledgeFile("", "", "", {})).data.get("allergy_groups", [])

    @property
    def red_flag_patterns(self) -> list[dict[str, Any]]:
        return self.files.get("red_flag_protocols.json", KnowledgeFile("", "", "", {})).data.get("red_flag_patterns", [])

    @property
    def urgent_patterns(self) -> list[dict[str, Any]]:
        return self.files.get("red_flag_protocols.json", KnowledgeFile("", "", "", {})).data.get("urgent_patterns", [])

    @property
    def routine_administrative_patterns(self) -> list[dict[str, Any]]:
        return self.files.get("red_flag_protocols.json", KnowledgeFile("", "", "", {})).data.get("routine_administrative_patterns", [])

    @property
    def vital_sign_thresholds(self) -> list[dict[str, Any]]:
        return self.files.get("red_flag_protocols.json", KnowledgeFile("", "", "", {})).data.get("vital_sign_thresholds", [])

    @property
    def specialty_routing(self) -> list[dict[str, Any]]:
        return self.files.get("red_flag_protocols.json", KnowledgeFile("", "", "", {})).data.get("specialty_routing", [])

    @property
    def symptom_guidance(self) -> list[dict[str, Any]]:
        return self.files.get("red_flag_protocols.json", KnowledgeFile("", "", "", {})).data.get("symptom_guidance", [])

    @property
    def reported_ingestion_protocols(self) -> list[dict[str, Any]]:
        return self.files.get(
            "medication_incident_protocols.json", KnowledgeFile("", "", "", {})
        ).data.get("reported_ingestion_protocols", [])

    def _contextualize_guidance(self, guidance: dict[str, Any], symptoms_text: str) -> dict[str, Any]:
        """Overlay V25 explanation/question planning without mutating knowledge.

        The knowledge file still decides whether a symptom topic matched. V25
        only improves the explanatory hypotheses and follow-up question after a
        match exists. The import is intentionally local so the immutable
        knowledge snapshot can load before the clinical reasoning modules.
        """
        try:
            from app.services.contextual_triage_planner import (
                build_contextual_triage_plan,
                reasoning_trace_payload,
            )

            plan = build_contextual_triage_plan(
                symptoms_text=symptoms_text,
                urgency="ROUTINE",
                existing_summary=(
                    str(guidance.get("summary")) if guidance.get("summary") else None
                ),
                existing_hypotheses=[
                    str(value) for value in guidance.get("clinical_hypotheses", [])
                ],
                existing_questions=[
                    str(value) for value in guidance.get("clarifying_questions", [])
                ],
            )
        except Exception:
            return guidance

        if not plan.applied:
            return guidance

        contextual = dict(guidance)
        if plan.summary:
            contextual["summary"] = plan.summary
        if plan.hypotheses:
            contextual["clinical_hypotheses"] = list(plan.hypotheses)
        if plan.questions:
            contextual["clarifying_questions"] = list(plan.questions)
        contextual["v25_contextual_reasoning"] = reasoning_trace_payload(plan)
        return contextual

    def find_symptom_guidance(self, symptoms_text: str) -> dict[str, Any] | None:
        normalized = normalize_search_text(symptoms_text)

        back_problem = any(
            contains_affirmed_phrase(normalized, phrase)
            for phrase in ("dau lung", "moi lung", "dau that lung", "moi that lung", "nhuc lung")
        )
        if not back_problem:
            back_relation = re.compile(
                r"\b(?:dau|moi|nhuc)\b(?:\s+[a-z0-9]+){0,4}\s+(?:that lung|lung)\b"
            )
            back_problem = any(
                contains_affirmed_phrase(normalized, match.group(0))
                for match in back_relation.finditer(normalized)
            )
        if back_problem:
            for guidance in self.symptom_guidance:
                if guidance.get("topic") == "back_pain":
                    return self._contextualize_guidance(guidance, symptoms_text)

        for guidance in self.symptom_guidance:
            if guidance.get("topic") == "lower_limb_pain":
                # A body-region token and an unrelated pain token must never be
                # combined into a finding. Example: "đau thắt lưng, không tê
                # chân" previously became lower-limb pain because both "đau"
                # and "chân" occurred somewhere in the string.
                direct_problem_phrases = (
                    "dau chan", "nhuc chan", "sung chan", "te chan", "yeu chan",
                    "dau dui", "nhuc dui", "dau bap chan", "sung bap chan",
                    "dau dau goi", "sung dau goi", "dau co chan", "sung co chan",
                    "dau mat ca", "dau ban chan", "kho di", "khong di duoc",
                    "khong chiu luc duoc",
                )
                has_affirmed_problem = any(
                    contains_affirmed_phrase(normalized, phrase)
                    for phrase in direct_problem_phrases
                )
                if not has_affirmed_problem:
                    forward_relation = re.compile(
                        r"\b(?:dau|nhuc|sung|te|yeu)\b(?:\s+[a-z0-9]+){0,4}\s+"
                        r"(?:bap chan|dau goi|co chan|mat ca|ban chan|chan|dui)\b"
                    )
                    reverse_relation = re.compile(
                        r"\b(?:bap chan|dau goi|co chan|mat ca|ban chan|chan|dui)\b"
                        r"(?:\s+[a-z0-9]+){0,4}\s+(?:dau|nhuc|sung|te|yeu)\b"
                    )
                    has_affirmed_problem = any(
                        contains_affirmed_phrase(normalized, match.group(0))
                        for pattern in (forward_relation, reverse_relation)
                        for match in pattern.finditer(normalized)
                    )
                if has_affirmed_problem:
                    return self._contextualize_guidance(guidance, symptoms_text)

            if any(
                contains_affirmed_phrase(normalized, normalize_search_text(str(keyword)))
                for keyword in guidance.get("keywords", [])
            ):
                return self._contextualize_guidance(guidance, symptoms_text)
        return None

    @property
    def contraindications(self) -> list[dict[str, Any]]:
        return self.files.get("contraindications.json", KnowledgeFile("", "", "", {})).data.get("contraindications", [])

    @property
    def atc_directory(self) -> dict[str, Any]:
        return self.files.get("atc_codes.json", KnowledgeFile("", "", "", {})).data.get("atc_directory", {})

    @property
    def icd10_directory(self) -> dict[str, Any]:
        return self.files.get("icd10_codes.json", KnowledgeFile("", "", "", {})).data.get("icd10_directory", {})

    @property
    def monitoring_rules(self) -> list[dict[str, Any]]:
        return self.files.get("monitoring_rules.json", KnowledgeFile("", "", "", {})).data.get("rules", [])

    @property
    def monitoring_minimum_points(self) -> int:
        value = self.files.get("monitoring_rules.json", KnowledgeFile("", "", "", {})).data.get(
            "minimum_points_for_trend", 3
        )
        return max(2, int(value))

    @property
    def product_registry(self) -> list[dict[str, Any]]:
        return self.files.get("product_registry.json", KnowledgeFile("", "", "", {})).data.get("products", [])

    # ------------------------------------------------------------------
    # Domain Helpers
    # ------------------------------------------------------------------

    def find_atc(self, substance_name: str) -> dict[str, Any] | None:
        normalized = substance_name.lower().strip()
        return self.atc_directory.get(normalized)

    def find_icd10(self, code: str) -> dict[str, Any] | None:
        normalized = code.upper().strip()
        return self.icd10_directory.get(normalized)

    # ------------------------------------------------------------------
    # Integrity & versioning (memoized for zero-allocation trace generation)
    # ------------------------------------------------------------------

    _version_string_cache: str | None = None
    _integrity_report_cache: dict[str, dict[str, str]] | None = None

    def version_string(self) -> str:
        """Return a composite version tag for trace/audit."""
        if self._version_string_cache is not None:
            return self._version_string_cache
        parts = [f"{kf.name}@{kf.version}" for kf in sorted(self.files.values(), key=lambda k: k.name)]
        self._version_string_cache = "|".join(parts)
        return self._version_string_cache

    def integrity_report(self) -> dict[str, dict[str, str]]:
        """Return per-file version and SHA-256 for audit embedding."""
        if self._integrity_report_cache is not None:
            return self._integrity_report_cache
        self._integrity_report_cache = {
            kf.name: {"version": kf.version, "sha256": kf.sha256}
            for kf in sorted(self.files.values(), key=lambda k: k.name)
        }
        return self._integrity_report_cache


def _load_knowledge_file(path: Path) -> KnowledgeFile:
    raw = path.read_bytes()
    digest = sha256(raw).hexdigest()
    data = json.loads(raw)
    version = data.get("_meta", {}).get("version", "unknown")
    return KnowledgeFile(name=path.name, version=version, sha256=digest, data=data)


def load_knowledge_store() -> KnowledgeStore:
    """Load all knowledge files from the package directory."""
    store = KnowledgeStore()
    for name in _FILE_NAMES:
        path = _KNOWLEDGE_DIR / name
        if path.exists():
            store.files[name] = _load_knowledge_file(path)
    # Pre-warm memoized reports
    store.version_string()
    store.integrity_report()
    return store


# Singleton loaded once at import time.
knowledge = load_knowledge_store()
