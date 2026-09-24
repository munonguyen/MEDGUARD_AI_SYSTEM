# MedGuard AI - Bao cao benchmark co bang chung

**Thoi diem do:** 2026-09-09

**Pham vi:** Development architecture validation

**Production acceptance:** KHONG DAT

## Ket qua

| Nang luc | Chi so | Nguong | Ket qua | Trang thai |
|---|---|---:|---:|---|
| OCR | CER | <= 10% | N/A | KHONG DU DIEU KIEN DO |
| OCR | WER ten thuoc | <= 15% | N/A | KHONG DU DIEU KIEN DO |
| Catalog matcher tren chuoi da gan nhan | Precision | >= 98% | 100.00% | DAT |
| Triage | Cohen's kappa | >= 0.70 | 0.944 | DAT |
| Triage | Severe under-triage | <= 1% | 0.00% | DAT |
| Triage | Emergency recall | >= 98% | 100.00% | DAT |
| Drug interaction | Recall | >= 95% | 100.00% | DAT |
| Drug interaction | Precision | >= 85% | 100.00% | DAT |
| Allergy | Recall | >= 98% | 100.00% | DAT |
| Adversarial | Fail-closed rate | >= 90% | 100.00% | DAT |
| Catalog safety | Default-item violations | 0 | 0 | DAT |
| External MIMIC demo | Emergency recall | >= 98% | 24.35% | KHONG DU DIEU KIEN DO |
| External MIMIC demo | Severe under-triage | <= 1% | 33.82% | KHONG DU DIEU KIEN DO |

## Tinh day du cua phep do

- DS-OCR co 300 nhan JSON, nhung chi co 0 anh co the chay; thieu 300 anh va co 0 loi pipeline.
- CER/WER chi duoc cong bo khi OCR doc anh that. Ground truth khong duoc dung lam prediction.
- 9/11 quality checks dang dat; production gate chi DAT khi tat ca check dat va OCR co du lieu anh that.
- Cac dataset hien tai la fixture do project tao. Ket qua khong thay the external clinical validation hoac phe duyet cua hoi dong chuyen mon.
- MIMIC-IV-ED demo: checksum=hop le, 207 dong co acuity; emergency recall=24.35%, severe under-triage=33.82%.
- MIMIC demo la phep thu lech phan phoi tieng Anh, khong phai tap chap nhan lam sang (`production_evaluable=false`). Ket qua yeu la blocker can xu ly, khong duoc dung de dieu chinh rule theo nhan demo.
