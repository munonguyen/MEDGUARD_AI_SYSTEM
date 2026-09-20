# 🔴 MedGuard AI — Blind Benchmark V6 Final Evaluation Report

**Final Verdict**: **FAILED**  
**Recommendation**: *RELEASE BLOCKED — ADDRESS ROOT CAUSE CLUSTERS FOR V5*  
**Seal Hash**: `031feee52c0133145c1ffa7b6b73847896a8a24eb73a67e93292ff3aaf91065f`  
**Git Commit**: `20dc5b2c48d655b62a17aea07da09c9d3b6039e8`  

---

## 14 Mandatory Hard Gates Status

| Gate | Invariant / Metric | Target | Actual | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Gate 1** | Pure T4 -> ROUTINE count | = 0 | 20 | **FAILED** |
| **Gate 2** | Pure T4 -> URGENT count | = 0 (or declared) | 10 | **FAILED** |
| **Gate 3** | Emergency Sensitivity | >= 98.0% | 86.30% | **FAILED** |
| **Gate 4** | Emergency Specificity | >= 95.0% | 97.53% | **PASSED** |
| **Gate 5** | Critical Unsafe Recommendation | = 0 | 0 | **PASSED** |
| **Gate 6** | Unsupported Medication/Treatment | = 0 | 0 | **PASSED** |
| **Gate 7** | Over-Triage Rate | <= 5.0% | 2.47% | **PASSED** |
| **Gate 8** | Long Multi-Turn Safety | >= 98.0% | 100.00% | **PASSED** |
| **Gate 9** | Linguistic Robustness | >= 95.0% | 100.00% | **PASSED** |
| **Gate 10** | Medication Dose Reasoning | >= 98.0% | 100.00% | **PASSED** |
| **Gate 11** | Correction Handling | >= 98.0% | 100.00% | **PASSED** |
| **Gate 12** | Expected Calibration Error (ECE) | < 0.08 | 0.0716 | **PASSED** |
| **Gate 13** | Per-Source Calibration Gap | <= 5.0% | 16.89% | **FAILED** |
| **Gate 14** | System Error Rate | < 1.0% | 0.00% | **PASSED** |

---

## Part A: Overall Performance

- **Score**: 2692 / 3000 (89.73%)
- **Emergency Sensitivity**: 86.30%
- **Emergency Specificity**: 97.53%
- **Severe Under-Triage**: 9.13%
- **Moderate Under-Triage**: 4.57%
- **Over-Triage Rate**: 2.47%
- **ECE**: 0.0716
- **Brier Score**: 0.1011

---

## Part B: Clinical Safety (Highest Priority)

- **Catastrophic Critical Failures**: **20**
- **Pure T4 $\rightarrow$ ROUTINE**: **20**
- **Pure T4 $\rightarrow$ URGENT**: 10
- **Critical Unsafe Recommendations**: 0
- **Unsupported Treatment Actions**: 0
- **Emergency Escalation Delay**: Median = 0 turns, Max = 0 turns

---

## Part C: Clinical Generalization

- **Multi-Turn Safety Rate**: 100.00%
- **Linguistic Robustness**: 100.00%
- **Dose Reasoning Accuracy**: 100.00%
- **Correction Handling Rate**: 100.00%

---

## Part D: Root-Cause Distribution & 6-Layer Diagnostics

- **Total Diagnostic Failures**: 33

### Root Cause Classification Breakdown
- **Implementation Bugs**: 10
- **Knowledge Gaps**: 21
- **Oracle Ambiguities**: 2
- **System Errors**: 0
- **Unsafe Response Policies**: 0

### 6-Layer Diagnostic Breakdown
- **Layer 1 - Language Understanding**: 0 cases
- **Layer 2 - Fact Extraction**: 0 cases
- **Layer 3 - Negation / Temporality**: 0 cases
- **Layer 4 - Clinical Semantic Reasoning**: 30 cases
- **Layer 5 - Risk Aggregation / Resolver**: 0 cases
- **Layer 6 - Response Generation Policy**: 0 cases
- **Runtime / System Failure**: 0 cases

### Primary Failure Taxonomy Distribution (F1 - F18)

| Primary Code | Root Cause Category | Count |
| :--- | :--- | :--- |
| `F15_OVER_TRIAGE` | Clinical Root Cause | 3 |
| `F5_CLINICAL_SEMANTIC_REASONING` | Clinical Root Cause | 20 |
| `F7_DOSE_REASONING` | Clinical Root Cause | 10 |