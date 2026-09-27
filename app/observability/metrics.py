"""Clinical Calibration and Performance Evaluation Metrics.

Computes:
1. Expected Calibration Error (ECE): Measures reliability of probability scores (e.g. Jev micro-scores).
2. Brier Score: Strictly proper scoring rule for probabilistic calibration.
3. Multi-class Clinical Classification Metrics (Recall, Specificity, F1 per cohort).
"""

from __future__ import annotations

import math
from typing import Any


def compute_brier_score(predictions: list[float], ground_truths: list[int]) -> float:
    """Calculates Brier Score: (1 / N) * sum((p_i - y_i)^2).

    Lower is better (0.0 = perfect calibration).
    """
    if not predictions or len(predictions) != len(ground_truths):
        return 0.0

    total_sq_error = sum((p - y) ** 2 for p, y in zip(predictions, ground_truths))
    return round(total_sq_error / len(predictions), 4)


def compute_ece(
    confidences: list[float],
    ground_truths: list[int],
    num_bins: int = 10,
) -> float:
    """Calculates Expected Calibration Error (ECE) across partitioned probability bins."""
    if not confidences or len(confidences) != len(ground_truths):
        return 0.0

    n = len(confidences)
    bin_boundaries = [i / num_bins for i in range(num_bins + 1)]
    ece = 0.0

    for i in range(num_bins):
        bin_lower = bin_boundaries[i]
        bin_upper = bin_boundaries[i + 1]

        # Extract items falling into current bin
        bin_items = [
            (c, y)
            for c, y in zip(confidences, ground_truths)
            if (bin_lower <= c < bin_upper) or (i == num_bins - 1 and bin_lower <= c <= bin_upper)
        ]

        bin_size = len(bin_items)
        if bin_size == 0:
            continue

        bin_acc = sum(y for _, y in bin_items) / bin_size
        bin_conf = sum(c for c, _ in bin_items) / bin_size

        ece += (bin_size / n) * abs(bin_acc - bin_conf)

    return round(ece, 4)


def compute_cohort_metrics(
    predictions: list[str],
    targets: list[str],
    positive_label: str = "EMERGENCY",
) -> dict[str, float]:
    """Computes Recall, Specificity, and F1 for a specific clinical label."""
    if not predictions or len(predictions) != len(targets):
        return {"recall": 0.0, "specificity": 0.0, "f1": 0.0}

    tp = sum(1 for p, t in zip(predictions, targets) if p == positive_label and t == positive_label)
    fn = sum(1 for p, t in zip(predictions, targets) if p != positive_label and t == positive_label)
    fp = sum(1 for p, t in zip(predictions, targets) if p == positive_label and t != positive_label)
    tn = sum(1 for p, t in zip(predictions, targets) if p != positive_label and t != positive_label)

    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "recall": round(recall, 4),
        "specificity": round(specificity, 4),
        "precision": round(precision, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "tn": tn,
    }


def compute_evidence_recall(
    retrieved_evidence_ids: list[str] | set[str],
    gold_evidence_ids: list[str] | set[str],
) -> float:
    """Calculates Retrieval Evidence Recall: |retrieved ∩ gold| / |gold|.

    Decouples retrieval capability from downstream reasoning capability.
    If gold_evidence_ids is empty, returns 1.0 (no evidence required).
    """
    if not gold_evidence_ids:
        return 1.0
    retrieved_set = set(retrieved_evidence_ids)
    gold_set = set(gold_evidence_ids)
    matched = retrieved_set.intersection(gold_set)
    return round(len(matched) / len(gold_set), 4)


def compute_invariance_score(
    variant_triages: list[str],
    baseline_triage: str,
) -> float:
    """Calculates System Invariance Score across metamorphic input variants.

    Measures percentage of linguistic variations (teencode, tone-less, verbose,
    inverted timeline, anxious tone, mixed EN/VI) that preserve identical clinical triage.
    """
    if not variant_triages:
        return 1.0
    base = baseline_triage.strip().upper()
    matched = sum(1 for t in variant_triages if t.strip().upper() == base)
    return round(matched / len(variant_triages), 4)

