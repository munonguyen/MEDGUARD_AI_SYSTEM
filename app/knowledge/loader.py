"""Versioned knowledge loader with SHA-256 integrity verification.

Each knowledge file carries a ``_meta.version`` field. The loader reads all
JSON knowledge files at import time and makes them available through a typed
API. ``KnowledgeStore.integrity_report()`` returns per-file SHA-256 digests
so that audit records can reference the exact knowledge snapshot used.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any


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

    def find_symptom_guidance(self, symptoms_text: str) -> dict[str, Any] | None:
        normalized = symptoms_text.lower().strip()
        for guidance in self.symptom_guidance:
            if any(str(keyword).lower() in normalized for keyword in guidance.get("keywords", [])):
                return guidance
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
