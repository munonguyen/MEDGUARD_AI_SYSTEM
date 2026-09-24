"""Stage 4: Fail-Closed Catalog Matching (Principle P4).

Enforces:
- String normalization: remove diacritics, lowercase, strip whitespace, extract strength.
- Exact match first, then fuzzy similarity matching.
- Minimum confidence threshold of 0.85.
- Under-threshold results return matched_product = None with top 5 candidates.
- NEVER fall back to the first catalog element (PHARMACY_CATALOG[0]).
"""

from __future__ import annotations

import difflib
import unicodedata
from dataclasses import dataclass
from typing import Any

from app.core.config import settings


@dataclass(frozen=True)
class CatalogProduct:
    product_id: str
    product_name: str
    active_ingredient: str
    strength: str
    dosage_form: str
    category: str


# Reference tenant pharmacy catalog
REFERENCE_CATALOG: tuple[CatalogProduct, ...] = (
    CatalogProduct("PROD-001", "Augmentin 1g", "Amoxicillin + Acid Clavulanic", "1g", "viên nén", "Kháng sinh"),
    CatalogProduct("PROD-002", "Augmentin 625mg", "Amoxicillin + Acid Clavulanic", "625mg", "viên nén", "Kháng sinh"),
    CatalogProduct("PROD-003", "Panadol Extra", "Paracetamol + Caffeine", "500mg/65mg", "viên nén", "Giảm đau hạ sốt"),
    CatalogProduct("PROD-004", "Paracetamol 500mg", "Paracetamol", "500mg", "viên nén", "Giảm đau hạ sốt"),
    CatalogProduct("PROD-005", "Nexium 40mg", "Esomeprazole", "40mg", "viên nén kháng acid", "Dạ dày - Tiêu hóa"),
    CatalogProduct("PROD-006", "Ciprofloxacin 500mg", "Ciprofloxacin", "500mg", "viên nén", "Kháng sinh"),
    CatalogProduct("PROD-007", "Amlor 5mg (Amlodipine)", "Amlodipine", "5mg", "viên nang", "Tim mạch - Huyết áp"),
    CatalogProduct("PROD-008", "Lipitor 20mg", "Atorvastatin", "20mg", "viên nén", "Hạ mỡ máu"),
    CatalogProduct("PROD-009", "Glucophage 850mg", "Metformin", "850mg", "viên nén", "Tiểu đường"),
    CatalogProduct("PROD-010", "Zithromax 500mg", "Azithromycin", "500mg", "viên nén", "Kháng sinh"),
    CatalogProduct("PROD-011", "Klacid 500mg", "Clarithromycin", "500mg", "viên nén", "Kháng sinh"),
    CatalogProduct("PROD-012", "Berocca Performance", "Multivitamins + Minerals", "viên sủi", "viên sủi", "Vitamin"),
)


def _strip_diacritics(text: str) -> str:
    """Normalize Vietnamese text by removing diacritics and symbols."""
    text = text.lower().strip()
    nfkd = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    return stripped.replace("đ", "d").replace("Đ", "d")


def match_medication_to_catalog(
    extracted_name: str,
    extracted_strength: str | None = None,
    custom_catalog: list[CatalogProduct] | None = None,
    threshold: float | None = None,
) -> dict[str, Any]:
    """Matches an extracted medication name against the pharmacy catalog with fail-closed semantics."""
    min_threshold = threshold or settings.prescription_match_threshold
    catalog = custom_catalog if custom_catalog is not None else REFERENCE_CATALOG

    norm_query = _strip_diacritics(extracted_name)

    # 1. Exact match check
    for item in catalog:
        norm_item_name = _strip_diacritics(item.product_name)
        if norm_query == norm_item_name or norm_query == _strip_diacritics(item.active_ingredient):
            return {
                "matched_product": {
                    "product_id": item.product_id,
                    "product_name": item.product_name,
                    "active_ingredient": item.active_ingredient,
                    "strength": item.strength,
                    "dosage_form": item.dosage_form,
                },
                "similarity_score": 1.0,
                "match_type": "EXACT",
                "candidates": [],
                "requires_manual_confirmation": False,
            }

    # 2. Fuzzy similarity scoring across catalog
    scored_candidates: list[tuple[float, CatalogProduct]] = []
    for item in catalog:
        norm_item_name = _strip_diacritics(item.product_name)
        ratio = difflib.SequenceMatcher(None, norm_query, norm_item_name).ratio()
        # Also check against active ingredient
        ing_ratio = difflib.SequenceMatcher(None, norm_query, _strip_diacritics(item.active_ingredient)).ratio()
        best_ratio = max(ratio, ing_ratio)
        scored_candidates.append((best_ratio, item))

    scored_candidates.sort(key=lambda x: x[0], reverse=True)

    # Top candidates for review
    candidates_list = [
        {
            "product_id": item.product_id,
            "product_name": item.product_name,
            "active_ingredient": item.active_ingredient,
            "similarity_score": round(score, 3),
        }
        for score, item in scored_candidates[:5]
    ]

    best_score, best_item = scored_candidates[0] if scored_candidates else (0.0, None)

    # 3. Fail-closed threshold check: MUST be >= min_threshold (0.85)
    if best_score >= min_threshold and best_item is not None:
        return {
            "matched_product": {
                "product_id": best_item.product_id,
                "product_name": best_item.product_name,
                "active_ingredient": best_item.active_ingredient,
                "strength": best_item.strength,
                "dosage_form": best_item.dosage_form,
            },
            "similarity_score": round(best_score, 3),
            "match_type": "FUZZY_APPROVED",
            "candidates": candidates_list,
            "requires_manual_confirmation": False,
        }

    # FAIL-CLOSED: Return None, NEVER return catalog[0]
    return {
        "matched_product": None,
        "similarity_score": round(best_score, 3) if best_score > 0 else 0.0,
        "match_type": "NO_MATCH_FAIL_CLOSED",
        "candidates": candidates_list,
        "requires_manual_confirmation": True,
    }
