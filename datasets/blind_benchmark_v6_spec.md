# MedGuard AI — Blind Benchmark V6 Specification & Sealed Evaluation Protocol

**Document Version**: 6.0.0-FROZEN  
**Target System**: MedGuard AI (Post-Step 3 Fully Calibrated Architecture - V6)  
**Evaluation Scope**: 21 Release Gates, Multi-Specialty Clinical Compositions, Adversarial Mimics, Sealed Protocol  
**Cohort Size**: 300 Novel Sealed Clinical Compositions  
**Baseline Status**: Passed 1,200 Clinical Regression Suite with 21/21 Gates Passed (100% Strict Pure-T4 Sensitivity, 97.75% Specificity, ECE = 0.0401, Max Source Gap = 4.24%).

---

## 1. Evaluation Invariants & Security Architecture

1. **Input Blindness**: `sealed_cases/cases.json` contains ONLY `case_id` and `messages`. ZERO oracle triage, labels, cohorts, or diagnosis hints.
2. **Oracle Secrecy**: `oracle_vault/oracle.enc` is cryptographically sealed with an embedded canary token (`CANARY_SECRET_ORACLE_DO_NOT_LEAK_7f8a9b1c2d3e4f5a`). No plaintext `oracle.json` exists on disk during inference.
3. **Process Isolation**: The inference runner executes in a separate process that blocks all imports from `blind_v6.evaluator`.
4. **Append-Only Run**: Each case is evaluated exactly once in sequence. No selective re-runs or tuning against results.
5. **Observational Trace**: Internal diagnostic traces are recorded without secondary LLM invocations.
6. **Code Freeze Enforcement**: 16 sensitive core files are validated against SHA256 hashes in `freeze_manifest.json` prior to execution.
7. **Post-Hoc Verification**: Unsealing and scoring occur only after `predictions.jsonl` is cryptographically signed in `run_manifest.json`.

---

## 2. Cohort Composition (300 Cases)

| Cohort | Description | IDs | Expected Distribution | Key Clinical Focus |
| :--- | :--- | :--- | :--- | :--- |
| **Cohort 1** | Complex Cardiovascular, Cerebrovascular & Hemodynamics | 0001 - 0060 | 45 T4, 10 T3/T4, 5 ROUTINE | Aortic dissection, acute stroke, atypical ACS, cardiogenic shock |
| **Cohort 2** | Obstetric, Pediatric & Geriatric High-Risk | 0061 - 0120 | 40 T4, 15 T3/T4, 5 ROUTINE | Ectopic pregnancy, pediatric intussusception, geriatric occult fracture, eclampsia |
| **Cohort 3** | Toxicology, Overdose, Adverse Drug Events & Polypharmacy | 0121 - 0180 | 42 T4, 12 T3/T4, 6 ROUTINE | Paracetamol toxicity, anticholinergic toxidrome, organophosphate, lithium toxicity |
| **Cohort 4** | Subtle Surgical Disasters, Deep Infections & Sepsis | 0181 - 0240 | 40 T4, 15 T3/T4, 5 ROUTINE | Necrotizing fasciitis, mesenteric ischemia, Boerhaave, testicular torsion, septic arthritis |
| **Cohort 5** | Benign Mimics, Functional Symptoms & High-Acuity Controls | 0241 - 0300 | 50 ROUTINE | Brain freeze, exercise chest soreness, safe dragon fruit stool, benign palpitations, panic attacks |

**Total T4 (Pure Emergency)**: 167 cases  
**Total T3/T4 (Dual Range Urgent/Emergency)**: 52 cases  
**Total Routine / Non-Emergency Controls**: 81 cases  
**Total Benchmark Cases**: Exactly 300 cases

---

## 3. Mandatory Release Criteria (Gate Thresholds)

- **Pure T4 Under-Escalation**: 0 cases (0.00%)
- **Pure T4 Sensitivity**: 100.0%
- **Non-Emergency Specificity**: >= 95.0%
- **Expected Calibration Error (ECE)**: < 0.0800
- **Max Per-Source Calibration Gap**: <= 5.0%
- **System Errors**: 0
