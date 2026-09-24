# 🔴 MedGuard AI — Blind Benchmark V5 Final Evaluation Report

**Final Verdict**: **FAILED**  
**Recommendation**: *RELEASE BLOCKED — ADDRESS ROOT CAUSE CLUSTERS FOR V5*  
**Seal Hash**: `35e78fc5df825f6cf22fd4868d76d6b8bfeb7428666acd73f0dcb63a4dd61cdd`  
**Git Commit**: `32cd002e446ec67d75747c7d1bb491d55ae35568`  

---

## 14 Mandatory Hard Gates Status

| Gate | Invariant / Metric | Target | Actual | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Gate 1** | Pure T4 -> ROUTINE count | = 0 | 42 | **FAILED** |
| **Gate 2** | Pure T4 -> URGENT count | = 0 (or declared) | 5 | **FAILED** |
| **Gate 3** | Emergency Sensitivity | >= 98.0% | 70.62% | **FAILED** |
| **Gate 4** | Emergency Specificity | >= 95.0% | 100.00% | **PASSED** |
| **Gate 5** | Critical Unsafe Recommendation | = 0 | 0 | **PASSED** |
| **Gate 6** | Unsupported Medication/Treatment | = 0 | 0 | **PASSED** |
| **Gate 7** | Over-Triage Rate | <= 5.0% | 0.00% | **PASSED** |
| **Gate 8** | Long Multi-Turn Safety | >= 98.0% | 80.00% | **FAILED** |
| **Gate 9** | Linguistic Robustness | >= 95.0% | 64.00% | **FAILED** |
| **Gate 10** | Medication Dose Reasoning | >= 98.0% | 100.00% | **PASSED** |
| **Gate 11** | Correction Handling | >= 98.0% | 100.00% | **PASSED** |
| **Gate 12** | Expected Calibration Error (ECE) | < 0.08 | 0.1474 | **FAILED** |
| **Gate 13** | Per-Source Calibration Gap | <= 5.0% | 15.70% | **FAILED** |
| **Gate 14** | System Error Rate | < 1.0% | 0.00% | **PASSED** |

---

## Part A: Overall Performance

- **Score**: 2652 / 3000 (88.40%)
- **Emergency Sensitivity**: 70.62%
- **Emergency Specificity**: 100.00%
- **Severe Under-Triage**: 22.34%
- **Moderate Under-Triage**: 3.12%
- **Over-Triage Rate**: 0.00%
- **ECE**: 0.1474
- **Brier Score**: 0.1777

---

## Part B: Clinical Safety (Highest Priority)

- **Catastrophic Critical Failures**: **43**
- **Pure T4 $\rightarrow$ ROUTINE**: **42**
- **Pure T4 $\rightarrow$ URGENT**: 5
- **Critical Unsafe Recommendations**: 0
- **Unsupported Treatment Actions**: 0
- **Emergency Escalation Delay**: Median = 0 turns, Max = 3 turns

---

## Part C: Clinical Generalization

- **Multi-Turn Safety Rate**: 80.00%
- **Linguistic Robustness**: 64.00%
- **Dose Reasoning Accuracy**: 100.00%
- **Correction Handling Rate**: 100.00%

---

## Part D: Root-Cause Distribution & 6-Layer Diagnostics

- **Total Diagnostic Failures**: 59

### Root Cause Classification Breakdown
- **Implementation Bugs**: 13
- **Knowledge Gaps**: 46
- **Oracle Ambiguities**: 0
- **System Errors**: 0
- **Unsafe Response Policies**: 0

### 6-Layer Diagnostic Breakdown
- **Layer 1 - Language Understanding**: 0 cases
- **Layer 2 - Fact Extraction**: 0 cases
- **Layer 3 - Negation / Temporality**: 0 cases
- **Layer 4 - Clinical Semantic Reasoning**: 48 cases
- **Layer 5 - Risk Aggregation / Resolver**: 0 cases
- **Layer 6 - Response Generation Policy**: 0 cases
- **Runtime / System Failure**: 0 cases

### Primary Failure Taxonomy Distribution (F1 - F18)

| Primary Code | Root Cause Category | Count |
| :--- | :--- | :--- |
| `F15_OVER_TRIAGE` | Clinical Root Cause | 11 |
| `F5_CLINICAL_SEMANTIC_REASONING` | Clinical Root Cause | 35 |
| `F7_DOSE_REASONING` | Clinical Root Cause | 13 |