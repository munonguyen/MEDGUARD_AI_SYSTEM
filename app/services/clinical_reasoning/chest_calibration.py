"""Bounded integration of V28 chest context into legacy detector candidates.

This refines isolated-keyword candidates before severity-max resolution; it
never overrides independent emergency vitals, historical risk or other rules.
Unknown or persistent/severe chest discomfort keeps the conservative path.
"""
from __future__ import annotations
import re
from app.services.clinical_text import normalize_search_text, contains_affirmed_phrase


def bounded_chest_assessment(text: str):
    from app.services.clinical_reasoning.context_router import ClinicalContextRouter
    norm = normalize_search_text(text)
    context = ClinicalContextRouter().parse(text)
    assessment = context.domain_assessment
    if not assessment or assessment.subtype not in {
        'musculoskeletal_chest_wall',
        'exertional_chest_pain_needs_prompt_assessment',
    }:
        return None
    # Absence must be explicitly supplied; an omitted symptom is unknown.
    if not all(context.negative_findings.get(k) for k in ('shortness_of_breath', 'sweating')):
        return None
    if not re.search(r'\bkhong\s+(?:dau\s+)?lan\b', norm):
        return None
    if any(context.positive_findings.get(k) for k in ('shortness_of_breath', 'sweating', 'radiation', 'dizziness')):
        return None
    danger = ('du doi', 'lien tuc', 'khong het', 'khong giam', 'keo dai',
              'khi nghi', 'luc nghi', 'gan ngat', 'ngat', 'bop nghet',
              'benh tim', 'nhoi mau', 'mach vanh', 'dai thao duong')
    if any(contains_affirmed_phrase(norm, phrase) for phrase in danger):
        return None
    return assessment
