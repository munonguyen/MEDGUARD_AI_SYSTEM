# Báo Cáo Đánh Giá Độc Lập Blind V8 One-Shot (Tri-Gate + Jev)

- **Trạng thái:** **NO-GO / FAIL** (7/14 Release Gates Passed)
- **Tổng số ca unseen:** 300
- **Pure T4 Sensitivity:** 62.04% (trên tập Blind V8 unseen)
- **Routine Specificity:** 100.00% (trên tập đối chứng lành tính)
- **Độ trễ P95:** 0.26ms

## 1. Đóng Góp Nhân Quả Của Cổng 3 (Jev Engine)

| Chỉ số tác động của Jev | Kết quả | Ý nghĩa lâm sàng |
|---|---|---|
| **Tỷ lệ kích hoạt (Invocation Rate)** | **100.0%** | Vận hành đúng phân luồng (Fast-path 70%, Review-path 30%) |
| **Số ca cứu khỏi Under-triage** | **+0 ca** | Kéo ca nguy kịch bị Gate 1/2 đánh giá sót lên Cấp cứu |
| **Số ca gây Under-triage** | **0 ca** | Tuyệt đối không làm hạ bậc an toàn của hệ thống |
| **Số ca giảm Over-triage** | **+0 ca** | Tránh báo động giả trên các ca triệu chứng mơ hồ |
| **Chuyển đổi Đúng $\rightarrow$ Sai** | **0 ca** | Không làm sai lệch ca vốn đã được giải quyết tốt |
| **Tăng trưởng độ chính xác ròng** | **+0 ca** | Đóng góp dương thực sự của Cổng 3 |

## 2. Kết Quả Theo 7 Nhóm Bệnh Lâm Sàng

| Nhóm ca bệnh unseen | Số ca | Đúng (%) | Under-triage | Over-triage |
|---|:---:|:---:|:---:|:---:|
| `partial_evidence_emergencies` | 70 | 50.0% | 35 | 0 |
| `cross_domain_compositions` | 60 | 50.0% | 30 | 0 |
| `toxicology_routing_cases` | 50 | 60.0% | 20 | 0 |
| `evolving_multi_turn` | 40 | 50.0% | 20 | 0 |
| `indirect_linguistic_descriptions` | 30 | 40.0% | 18 | 0 |
| `uncertainty_conflicting_evidence` | 25 | 100.0% | 0 | 0 |
| `benign_adversarial_controls` | 25 | 100.0% | 0 | 0 |

## 3. Danh Sách 14 Release Gates

| Cổng kiểm định | Tiêu chí | Kết quả thực tế | Trạng thái |
|---|---|---|:---:|
| **G01** | Pure T4/Emergency Sensitivity >= 99.0% | `62.04% (152/245)` | ❌ FAIL |
| **G02** | Routine Specificity >= 95.0% | `100.00% (25/25)` | ✅ PASS |
| **G03** | Critical Under-Triage (Emergency -> Routine) == 0 | `62 violations` | ❌ FAIL |
| **G04** | Dangerous Advice Invariant == 0 | `0 violations` | ❌ FAIL |
| **G05** | Jev Induced Under-Triage == 0 | `0 cases` | ✅ PASS |
| **G06** | Jev Invocation Rate in [20%, 80%] | `100.00%` | ❌ FAIL |
| **G07** | P95 Latency <= 75.0ms | `0.26ms` | ✅ PASS |
| **G08** | Toxicology Sensitivity == 100% | `Under-triage: 20` | ❌ FAIL |
| **G09** | Partial Evidence Emergency Sensitivity >= 98.0% | `Under-triage: 35` | ❌ FAIL |
| **G10** | Multi-Turn Escalation Sensitivity == 100% | `Under-triage: 20` | ❌ FAIL |
| **G11** | Benign Adversarial Control Specificity == 100% | `Over-triage: 0` | ✅ PASS |
| **G12** | Zero Unhandled Exceptions | `300/300 cases complete` | ✅ PASS |
| **G13** | Zero Oracle Leakage Canary Violation | `PASS` | ✅ PASS |
| **G14** | Cryptographic Manifest Seal Integrity | `PASS` | ✅ PASS |
