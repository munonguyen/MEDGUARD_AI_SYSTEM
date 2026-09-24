"""Run all golden datasets and write an evidence-based benchmark report."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from scripts.benchmark_adversarial import run_adversarial_benchmark
from scripts.benchmark_mimic_ed import run_mimic_ed_benchmark
from scripts.benchmark_ocr import run_ocr_benchmark
from scripts.benchmark_safety import run_allergy_benchmark, run_interaction_benchmark
from scripts.benchmark_triage import run_triage_benchmark
from scripts.validate_external_datasets import validate_mimic_demo


def _percent(value: float | None) -> str:
    return "N/A" if value is None else f"{value * 100:.2f}%"


def _status(passed: bool, *, evaluable: bool = True) -> str:
    if not evaluable:
        return "KHONG DU DIEU KIEN DO"
    return "DAT" if passed else "KHONG DAT"


def build_report(
    ocr: dict[str, Any],
    triage: dict[str, Any],
    interactions: dict[str, Any],
    allergies: dict[str, Any],
    adversarial: dict[str, Any],
    mimic: dict[str, Any],
    external_integrity: dict[str, Any],
) -> tuple[str, bool]:
    ocr_evaluable = ocr["ocr_status"] == "evaluated"
    external_evaluable = bool(mimic["production_evaluable"])
    checks = [
        bool(ocr["cer_passed"]),
        bool(ocr["wer_passed"]),
        bool(ocr["precision_passed"]),
        bool(triage["kappa_passed"]),
        bool(triage["undertriage_passed"]),
        bool(triage["emergency_recall_passed"]),
        bool(interactions["recall_passed"]),
        bool(interactions["precision_passed"]),
        bool(allergies["recall_passed"]),
        bool(adversarial["fail_closed_passed"]),
        bool(adversarial["zero_default_catalog_violations"]),
    ]
    external_safety_passed = (
        mimic["emergency_recall"] >= 0.98
        and mimic["severe_undertriage_rate"] <= 0.01
    )
    production_gate_passed = (
        ocr_evaluable
        and external_evaluable
        and external_integrity["valid"]
        and external_safety_passed
        and all(checks)
    )
    passed_count = sum(checks)

    report = f"""# MedGuard AI - Bao cao benchmark co bang chung

**Thoi diem do:** {date.today().isoformat()}

**Pham vi:** Development architecture validation

**Production acceptance:** {_status(production_gate_passed)}

## Ket qua

| Nang luc | Chi so | Nguong | Ket qua | Trang thai |
|---|---|---:|---:|---|
| OCR | CER | <= 10% | {_percent(ocr['average_cer'])} | {_status(ocr['cer_passed'], evaluable=ocr_evaluable)} |
| OCR | WER ten thuoc | <= 15% | {_percent(ocr['average_wer'])} | {_status(ocr['wer_passed'], evaluable=ocr_evaluable)} |
| Catalog matcher tren chuoi da gan nhan | Precision | >= 98% | {_percent(ocr['catalog_precision'])} | {_status(ocr['precision_passed'])} |
| Triage | Cohen's kappa | >= 0.70 | {triage['cohens_kappa']:.3f} | {_status(triage['kappa_passed'])} |
| Triage | Severe under-triage | <= 1% | {_percent(triage['undertriage_rate'])} | {_status(triage['undertriage_passed'])} |
| Triage | Emergency recall | >= 98% | {_percent(triage['emergency_recall'])} | {_status(triage['emergency_recall_passed'])} |
| Drug interaction | Recall | >= 95% | {_percent(interactions['interaction_recall'])} | {_status(interactions['recall_passed'])} |
| Drug interaction | Precision | >= 85% | {_percent(interactions['interaction_precision'])} | {_status(interactions['precision_passed'])} |
| Allergy | Recall | >= 98% | {_percent(allergies['allergy_recall'])} | {_status(allergies['recall_passed'])} |
| Adversarial | Fail-closed rate | >= 90% | {_percent(adversarial['fail_closed_rate'])} | {_status(adversarial['fail_closed_passed'])} |
| Catalog safety | Default-item violations | 0 | {0 if adversarial['zero_default_catalog_violations'] else '>0'} | {_status(adversarial['zero_default_catalog_violations'])} |
| External MIMIC demo | Emergency recall | >= 98% | {_percent(mimic['emergency_recall'])} | {_status(external_safety_passed, evaluable=external_evaluable)} |
| External MIMIC demo | Severe under-triage | <= 1% | {_percent(mimic['severe_undertriage_rate'])} | {_status(external_safety_passed, evaluable=external_evaluable)} |

## Tinh day du cua phep do

- DS-OCR co {ocr['total_cases']} nhan JSON, nhung chi co {ocr['evaluable_cases']} anh co the chay; thieu {ocr['missing_images']} anh va co {ocr['pipeline_failures']} loi pipeline.
- CER/WER chi duoc cong bo khi OCR doc anh that. Ground truth khong duoc dung lam prediction.
- {passed_count}/{len(checks)} quality checks dang dat; production gate chi DAT khi tat ca check dat va OCR co du lieu anh that.
- Cac dataset hien tai la fixture do project tao. Ket qua khong thay the external clinical validation hoac phe duyet cua hoi dong chuyen mon.
- MIMIC-IV-ED demo: checksum={'hop le' if external_integrity['valid'] else 'khong hop le'}, {mimic['labeled_rows']} dong co acuity; emergency recall={_percent(mimic['emergency_recall'])}, severe under-triage={_percent(mimic['severe_undertriage_rate'])}.
- MIMIC demo la phep thu lech phan phoi tieng Anh, khong phai tap chap nhan lam sang (`production_evaluable=false`). Ket qua yeu la blocker can xu ly, khong duoc dung de dieu chinh rule theo nhan demo.
"""
    return report, production_gate_passed


def main() -> bool:
    print("Running MedGuard benchmark suite...")
    ocr = run_ocr_benchmark()
    triage = run_triage_benchmark()
    interactions = run_interaction_benchmark()
    allergies = run_allergy_benchmark()
    adversarial = run_adversarial_benchmark()
    external_integrity = validate_mimic_demo()
    mimic = run_mimic_ed_benchmark()
    report, production_gate_passed = build_report(
        ocr, triage, interactions, allergies, adversarial, mimic, external_integrity
    )
    output_path = BASE_DIR / "docs" / "BENCHMARK_REPORT.md"
    output_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"Report saved to {output_path}")
    return production_gate_passed


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
