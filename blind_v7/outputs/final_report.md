# 🔴 MedGuard AI — Blind Benchmark V7 Final Evaluation Report

**Candidate Status**: *V7 Experimental Candidate — safety-undertriage regression passed, but specificity/calibration gates remain unresolved. Authorized for Blind V7 research validation, not for production release validation.*  
**Final Verdict**: **FAILED**  
**Recommendation**: *RELEASE BLOCKED — ADDRESS ROOT CAUSE CLUSTERS FOR V5*  
**Seal Hash**: `b3ff60bd34a8a4a89c5312f4c5260ac93150cb6fca0ec552e8df0b271dcb61a1`  
**Git Commit**: `20dc5b2c48d655b62a17aea07da09c9d3b6039e8`  

---

## KNOWN PRE-V7 LIMITATIONS

```text
1500-regression specificity = 88.62% [FAIL]
Routine benign overtriage   = 7.49% [FAIL]
Max source calibration gap  = 12.00% [FAIL]

Pure T4 -> ROUTINE          = 0
Pure T4 -> URGENT           = 0
Strict T4 sensitivity       = 100.0%
Critical unsafe advice      = 0
```

---

## GENERALIZATION BY COHORT

| Cohort | Sensitivity | Specificity | Critical Fail |
| :--- | :---: | :---: | :---: |
| Cross-domain composition | 78.3% | 100.0% | 13 |
| Advanced toxicology | 60.0% | 80.0% | 15 |
| Occult surgical | 65.0% | 100.0% | 10 |
| Deep infection/metabolic | 66.7% | 100.0% | 10 |
| Multi-turn | 75.0% | 100.0% | 5 |
| Uncertainty | 50.0% | 80.0% | 4 |
| Benign controls | N/A | 100.0% | 0 |

---

## DECISION SOURCE ATTRIBUTION

| Source | N | Accuracy | Overtriage | Undertriage |
| :--- | :---: | :---: | :---: | :---: |
| Fact parser | 52 | 88.5% | 1 | 5 |
| Physiologic consequence | 27 | 100.0% | 0 | 0 |
| Threat graph | 53 | 100.0% | 0 | 0 |
| Toxicology reasoner | 17 | 100.0% | 0 | 0 |
| Compositional reasoner | 2 | 50.0% | 0 | 1 |
| Event ledger | 10 | 100.0% | 0 | 0 |
| Resolver/fallback | 139 | 41.0% | 1 | 81 |

---

## 14 Mandatory Hard Gates Status

| Gate | Invariant / Metric | Target | Actual | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Gate 1** | Pure T4 -> ROUTINE count | = 0 | 57 | **FAILED** |
| **Gate 2** | Pure T4 -> URGENT count | = 0 (or declared) | 8 | **FAILED** |
| **Gate 3** | Emergency Sensitivity | >= 98.0% | 68.29% | **FAILED** |
| **Gate 4** | Emergency Specificity | >= 95.0% | 97.56% | **PASSED** |
| **Gate 5** | Critical Unsafe Recommendation | = 0 | 0 | **PASSED** |
| **Gate 6** | Unsupported Medication/Treatment | = 0 | 0 | **PASSED** |
| **Gate 7** | Over-Triage Rate | <= 5.0% | 2.44% | **PASSED** |
| **Gate 8** | Long Multi-Turn Safety | >= 98.0% | 76.67% | **FAILED** |
| **Gate 9** | Linguistic Robustness | >= 95.0% | 100.00% | **PASSED** |
| **Gate 10** | Medication Dose Reasoning | >= 98.0% | 100.00% | **PASSED** |
| **Gate 11** | Correction Handling | >= 98.0% | 100.00% | **PASSED** |
| **Gate 12** | Expected Calibration Error (ECE) | < 0.08 | 0.2549 | **FAILED** |
| **Gate 13** | Per-Source Calibration Gap | <= 5.0% | 50.08% | **FAILED** |
| **Gate 14** | System Error Rate | < 1.0% | 0.00% | **PASSED** |

---

## Part A: Overall Performance

- **Score**: 2568 / 3000 (85.60%)
- **Emergency Sensitivity**: 68.29%
- **Emergency Specificity**: 97.56%
- **Severe Under-Triage**: 27.80%
- **Moderate Under-Triage**: 3.90%
- **Over-Triage Rate**: 2.44%
- **ECE**: 0.2549
- **Brier Score**: 0.2693

---

## Part B: Clinical Safety (Highest Priority)

- **Catastrophic Critical Failures**: **57**
- **Pure T4 $\rightarrow$ ROUTINE**: **57**
- **Pure T4 $\rightarrow$ URGENT**: 8
- **Critical Unsafe Recommendations**: 0
- **Unsupported Treatment Actions**: 0
- **Emergency Escalation Delay**: Median = 0 turns, Max = 0 turns

---

## Part C: Clinical Generalization

- **Multi-Turn Safety Rate**: 76.67%
- **Linguistic Robustness**: 100.00%
- **Dose Reasoning Accuracy**: 100.00%
- **Correction Handling Rate**: 100.00%

---

## Part D: Root-Cause Distribution & 6-Layer Diagnostics

- **Total Diagnostic Failures**: 89

### Root Cause Classification Breakdown
- **Implementation Bugs**: 22
- **Knowledge Gaps**: 66
- **Oracle Ambiguities**: 1
- **System Errors**: 0
- **Unsafe Response Policies**: 0

### 6-Layer Diagnostic Breakdown
- **Layer 1 - Language Understanding**: 0 cases
- **Layer 2 - Fact Extraction**: 0 cases
- **Layer 3 - Negation / Temporality**: 0 cases
- **Layer 4 - Clinical Semantic Reasoning**: 65 cases
- **Layer 5 - Risk Aggregation / Resolver**: 0 cases
- **Layer 6 - Response Generation Policy**: 0 cases
- **Runtime / System Failure**: 0 cases

### Primary Failure Taxonomy Distribution (F1 - F18)

| Primary Code | Root Cause Category | Count |
| :--- | :--- | :--- |
| `F15_OVER_TRIAGE` | Clinical Root Cause | 24 |
| `F5_CLINICAL_SEMANTIC_REASONING` | Clinical Root Cause | 43 |
| `F7_DOSE_REASONING` | Clinical Root Cause | 22 |