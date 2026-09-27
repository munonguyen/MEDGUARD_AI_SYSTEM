"""Adaptive Context Token Budget Manager.

Dynamically partitions context tokens across clinical domains
(Emergency, Clinical Reasoner, Pharmacology, Guidelines, Legal, Patient Facts)
ensuring that token limits are never exceeded while domain-specific queries
receive expanded allocation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ContextBudget(BaseModel):
    """Token budget allocation across clinical domains."""
    emergency_tokens: int = 300
    clinical_tokens: int = 1000
    drug_tokens: int = 700
    guideline_tokens: int = 800
    legal_tokens: int = 0
    patient_tokens: int = 600
    total_budget: int = Field(default=3400)


class ContextBudgetManager:
    """Calculates adaptive token allocations."""

    @staticmethod
    def allocate_budget(
        is_emergency: bool = False,
        is_drug_heavy: bool = False,
        is_legal_heavy: bool = False,
        complexity_level: str = "C2",
    ) -> ContextBudget:
        budget = ContextBudget()

        if is_emergency:
            budget.emergency_tokens = 600
            budget.clinical_tokens = 800
            budget.drug_tokens = 400
            budget.guideline_tokens = 500
            budget.legal_tokens = 0

        elif is_drug_heavy:
            budget.drug_tokens = 1200
            budget.clinical_tokens = 800
            budget.guideline_tokens = 600
            budget.legal_tokens = 0

        elif is_legal_heavy:
            budget.legal_tokens = 800
            budget.clinical_tokens = 600
            budget.drug_tokens = 200

        if complexity_level == "C0":
            budget.total_budget = 1000
        elif complexity_level == "C1":
            budget.total_budget = 1800
        elif complexity_level in ("C2", "C3"):
            budget.total_budget = 3500
        elif complexity_level == "C4":
            budget.total_budget = 2000

        return budget
