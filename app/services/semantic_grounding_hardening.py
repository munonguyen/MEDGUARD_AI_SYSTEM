"""V27.3 grounding guards for explicitly negative or hypothetical evidence.

These adapters do not lower a supported safety signal. They only prevent two
classes of false evidence from becoming active patient facts:

* a high-risk concept that is explicitly negated in the same clause; and
* toxic ingestion when the user explicitly states the medicine has not been
  taken and there is no affirmed medication ingestion elsewhere in the episode.

The underlying parsers remain the sole source of clinical concepts. This module
only corrects assertion state for bounded, text-grounded negation cases.
"""

from __future__ import annotations

import re
from types import ModuleType
from typing import Any

from app.models.clinical_events import ClinicalAssertion
from app.services.clinical_text import normalize_search_text


_RELATION_MARKER = "_medguard_v27_3_relation_grounding"
_FACT_MARKER = "_medguard_v27_3_fact_grounding"


def _norm(value: str) -> str:
    return normalize_search_text(str(value or ""))


def _focal_weakness_is_explicitly_negated(text: str) -> bool:
    """Recognize bounded coordinated negation such as ``không có tê yếu chân``.

    The legacy relation extractor checks only the tokens immediately preceding
    ``yếu chân``. In natural Vietnamese, a coordinated symptom such as ``tê`` can
    sit between the negator and ``yếu chân`` and accidentally break that scope.
    Do not generalize beyond explicit local negation because missing a true focal
    deficit is higher risk than leaving an ambiguous phrase for clarification.
    """
    norm = _norm(text)
    return bool(
        re.search(
            r"\b(?:khong|chua|chang|ko|k)"
            r"(?:\s+(?:co|bi|thay|he))?"
            r"(?:\s+(?:te|te ran|cam thay te)){0,2}"
            r"\s+(?:yeu|liet)\s+(?:chan|tay|mot ben|nua nguoi)\b",
            norm,
        )
        or re.search(
            r"\b(?:khong|chua|chang|ko|k)"
            r"(?:\s+(?:co|bi|thay|he))?\s+te\s+yeu\s+(?:chan|tay)\b",
            norm,
        )
    )


def _without_negated_relations(graph: Any, canonical_names: set[str]) -> Any:
    concepts = dict(getattr(graph, "concepts", {}) or {})
    changed = False
    for cid, concept in list(concepts.items()):
        if getattr(concept, "canonical_name", "") not in canonical_names:
            continue
        if getattr(concept, "is_negated", False):
            continue
        try:
            concepts[cid] = concept.__class__(
                concept_id=concept.concept_id,
                canonical_name=concept.canonical_name,
                category=concept.category,
                certainty=concept.certainty,
                evidence_span=concept.evidence_span,
                organ_system=concept.organ_system,
                is_negated=True,
                attributes=dict(getattr(concept, "attributes", {}) or {}),
            )
            changed = True
        except Exception:
            continue
    if not changed:
        return graph

    relations = [
        relation
        for relation in list(getattr(graph, "relations", ()) or ())
        if getattr(relation, "source_concept", "") not in canonical_names
        and getattr(relation, "target_concept", "") not in canonical_names
    ]
    return graph.__class__(
        raw_text=getattr(graph, "raw_text", ""),
        normalized_text=getattr(graph, "normalized_text", ""),
        concepts=concepts,
        relations=relations,
    )


def install_semantic_relation_grounding(module: ModuleType) -> None:
    if getattr(module, _RELATION_MARKER, False):
        return
    original = getattr(module, "extract_semantic_relations", None)
    if original is None:
        return

    def extract_semantic_relations(text: str):
        graph = original(text)
        if _focal_weakness_is_explicitly_negated(text):
            graph = _without_negated_relations(graph, {"focal_weakness"})
        return graph

    module.extract_semantic_relations = extract_semantic_relations
    setattr(module, _RELATION_MARKER, True)


def _explicit_no_medication_ingestion(text: str) -> bool:
    norm = _norm(text)
    return bool(
        re.search(
            r"\b(?:chua|khong|chua he|khong he)\s+(?:uong|dung|tiem)\b"
            r".{0,45}\b(?:thuoc|vien|lieu|paracetamol|acetaminophen|ibuprofen|aspirin|"
            r"warfarin|insulin|lithium|thuoc ngu|thuoc an than)\b",
            norm,
        )
    )


def _affirmed_medication_ingestion(text: str) -> bool:
    """Return true only for an affirmed medicine ingestion, not alcohol use."""
    norm = _norm(text)
    medication = (
        r"(?:thuoc|vien|lieu|paracetamol|acetaminophen|ibuprofen|aspirin|warfarin|"
        r"insulin|lithium|thuoc ngu|thuoc an than)"
    )
    patterns = (
        rf"\b(?:da|vua|lo|trot|nham)\s+(?:uong|dung|tiem)\b.{{0,60}}\b{medication}\b",
        rf"\b(?:uong|dung|tiem)\s+(?:nham|qua lieu|gap doi)\b.{{0,60}}\b{medication}\b",
        rf"\b(?:uong|dung)\b.{{0,35}}\b(?:\d{{2,}}\s*(?:vien|mg)|ca vi|qua lieu)\b.{{0,35}}\b{medication}\b",
        rf"\b{medication}\b.{{0,35}}\b(?:\d{{2,}}\s*(?:vien|mg)|ca vi|qua lieu)\b",
    )
    return any(re.search(pattern, norm) for pattern in patterns)


def _remove_false_toxic_ingestion(facts: Any) -> Any:
    updated = []
    changed = False
    for event in tuple(getattr(facts, "events", ()) or ()):
        is_toxic = (
            getattr(event, "concept", "") == "toxic_ingestion"
            or getattr(event, "physiologic_consequence", "") == "acute_toxic_metabolic_threat"
        )
        if is_toxic and getattr(event, "assertion", None) == ClinicalAssertion.PRESENT:
            event = event.model_copy(update={"assertion": ClinicalAssertion.ABSENT})
            changed = True
        updated.append(event)
    if not changed:
        return facts
    return facts.model_copy(update={"events": tuple(updated)})


def install_clinical_fact_grounding(module: ModuleType) -> None:
    if getattr(module, _FACT_MARKER, False):
        return
    original = getattr(module, "parse_semantic_clinical_facts", None)
    if original is None:
        return

    def parse_semantic_clinical_facts(text: str):
        facts = original(text)
        if _explicit_no_medication_ingestion(text) and not _affirmed_medication_ingestion(text):
            return _remove_false_toxic_ingestion(facts)
        return facts

    module.parse_semantic_clinical_facts = parse_semantic_clinical_facts
    setattr(module, _FACT_MARKER, True)
