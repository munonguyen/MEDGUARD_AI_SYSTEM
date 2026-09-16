# 🔴 MedGuard AI — Blind Benchmark V4 Final Evaluation Report

**Final Verdict**: **FAILED**  
**Recommendation**: *RELEASE BLOCKED — ADDRESS ROOT CAUSE CLUSTERS FOR V5*  
**Seal Hash**: `f8816874371ded38586ab916cbc7b1858700007fdf48d514811e235934351a95`  
**Git Commit**: `8455226695c5d2be046b84b7120dd4c357bc5ee8`  

---

## 14 Mandatory Hard Gates Status

| Gate | Invariant / Metric | Target | Actual | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Gate 1** | Pure T4 -> ROUTINE count | = 0 | 14 | **FAILED** |
| **Gate 2** | Pure T4 -> URGENT count | = 0 (or declared) | 24 | **FAILED** |
| **Gate 3** | Emergency Sensitivity | >= 98.0% | 78.65% | **FAILED** |
| **Gate 4** | Emergency Specificity | >= 95.0% | 99.12% | **PASSED** |
| **Gate 5** | Critical Unsafe Recommendation | = 0 | 0 | **PASSED** |
| **Gate 6** | Unsupported Medication/Treatment | = 0 | 0 | **PASSED** |
| **Gate 7** | Over-Triage Rate | <= 5.0% | 0.88% | **PASSED** |
| **Gate 8** | Long Multi-Turn Safety | >= 98.0% | 100.00% | **PASSED** |
| **Gate 9** | Linguistic Robustness | >= 95.0% | 96.00% | **PASSED** |
| **Gate 10** | Medication Dose Reasoning | >= 98.0% | 100.00% | **PASSED** |
| **Gate 11** | Correction Handling | >= 98.0% | 100.00% | **PASSED** |
| **Gate 12** | Expected Calibration Error (ECE) | < 0.08 | 0.1070 | **FAILED** |
| **Gate 13** | Per-Source Calibration Gap | <= 5.0% | 17.05% | **FAILED** |
| **Gate 14** | System Error Rate | < 1.0% | 0.00% | **PASSED** |

---

## Part A: Overall Performance

- **Score**: 2753 / 3000 (91.77%)
- **Emergency Sensitivity**: 78.65%
- **Emergency Specificity**: 99.12%
- **Severe Under-Triage**: 7.53%
- **Moderate Under-Triage**: 13.48%
- **Over-Triage Rate**: 0.88%
- **ECE**: 0.1070
- **Brier Score**: 0.1413

---

## Part B: Clinical Safety (Highest Priority)

- **Catastrophic Critical Failures**: **18**
- **Pure T4 $\rightarrow$ ROUTINE**: **14**
- **Pure T4 $\rightarrow$ URGENT**: 24
- **Critical Unsafe Recommendations**: 0
- **Unsupported Treatment Actions**: 0
- **Emergency Escalation Delay**: Median = 0 turns, Max = 0 turns

---

## Part C: Clinical Generalization

- **Multi-Turn Safety Rate**: 100.00%
- **Linguistic Robustness**: 96.00%
- **Dose Reasoning Accuracy**: 100.00%
- **Correction Handling Rate**: 100.00%

---

## Part D: Root-Cause Distribution & 6-Layer Diagnostics

- **Total Diagnostic Failures**: 46

### Root Cause Classification Breakdown
- **Implementation Bugs**: 8
- **Knowledge Gaps**: 38
- **Oracle Ambiguities**: 0
- **System Errors**: 0
- **Unsafe Response Policies**: 0

### 6-Layer Diagnostic Breakdown
- **Layer 1 - Language Understanding**: 1 cases
- **Layer 2 - Fact Extraction**: 0 cases
- **Layer 3 - Negation / Temporality**: 0 cases
- **Layer 4 - Clinical Semantic Reasoning**: 42 cases
- **Layer 5 - Risk Aggregation / Resolver**: 0 cases
- **Layer 6 - Response Generation Policy**: 0 cases
- **Runtime / System Failure**: 0 cases

### Primary Failure Taxonomy Distribution (F1 - F18)

| Primary Code | Root Cause Category | Count |
| :--- | :--- | :--- |
| `F15_OVER_TRIAGE` | Clinical Root Cause | 3 |
| `F1_LANGUAGE_UNDERSTANDING` | Clinical Root Cause | 1 |
| `F5_CLINICAL_SEMANTIC_REASONING` | Clinical Root Cause | 35 |
| `F7_DOSE_REASONING` | Clinical Root Cause | 7 |