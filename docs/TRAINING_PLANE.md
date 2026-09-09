# MedGuard Training Plane

## Purpose

The Training Plane produces versioned Answer and Verifier adapters. It does not replace deterministic clinical rules, versioned knowledge, tools, the LLM Control Plane or LiteLLM Gateway.

```text
Governed source data
  -> de-identification and rights checks
  -> independent expert review
  -> strict Answer / Verifier contracts
  -> normalized duplicate detection
  -> case-group train / validation / test split
  -> dataset coverage gate and SHA-256 manifest
  -> role-specific QLoRA SFT
  -> held-out safety evaluation
  -> checksum-bound model approval
  -> offline model registry
  -> static vLLM candidate serving
  -> LiteLLM shadow route
  -> live quality / cost / latency review
  -> explicit production alias promotion
```

Fine-tuning teaches MedGuard behavior: schema adherence, tool use, evidence grounding, locked-claim preservation, uncertainty, escalation and refusal to invent. Drug facts, interactions, contraindications, guidelines and recalls remain in approved versioned knowledge or external tools because those facts change independently of model weights.

## Data Contracts

`training/contracts.py` defines two incompatible schemas:

- `medguard.answer.v1` contains a question, deidentified context, deterministic tool results, versioned evidence, locked claims and a reviewed answer target.
- `medguard.verifier.v1` contains immutable claims, evidence, a candidate answer and a reviewed PASS/FAIL target with explicit violation types.

Every sample requires a unique sample ID, a case-group ID, source/license provenance, confirmed usage rights, `deidentified=true` and an approved expert review record. `external_evaluation` provenance is rejected from training. The MIMIC-IV-ED demo therefore remains an external distribution-shift probe.

The automated scanner rejects common email, Vietnamese phone, national-ID and patient-reference patterns. It allows only a closed placeholder set such as `[PATIENT_REF]`. This scanner is a defense in depth control, not proof of de-identification. A qualified data-governance review remains mandatory.

## Dataset Gate

Run the compiler only against governed JSONL outside source control:

```bash
.venv/bin/python scripts/prepare_training_dataset.py \
  --source /secure/governed/medguard-training-v1.jsonl \
  --output-dir .artifacts/training/medguard-training-v1 \
  --dataset-version medguard-training-v1
```

Splits are assigned from `SHA-256(seed + case_group_id)` at 80/10/10. All variants of one clinical case remain in one split. Normalized duplicate content is rejected across the whole dataset. The manifest records source/file checksums, role/split/category counts and gate failures.

`training/dataset_gate.json` requires both roles, all six Answer categories, all seven Verifier categories, separate train/validation/test coverage and both approved/rejected Verifier labels. A small valid dataset may be compiled for inspection, but `approved_for_sft=false` prevents the trainer from consuming it.

No raw, compiled or run data is committed. `.gitignore` excludes `training/raw/`, `training/compiled/`, `training/runs/` and `.artifacts/`.

`datasets/DS-CHAT-HARD/dataset.json` is a development-only red-team set containing difficult user phrasing, explicit negation, text without Vietnamese diacritics, versioned English red flags, prompt injection, medication safety, personalized-dose refusal, monitoring, schedules and unknown QR products. It is marked `training_allowed=false` and `production_evaluable=false`. Cases may enter a future training dataset only through a separate expert review and provenance workflow, and the original challenge set must remain held out to prevent test memorization.

## QLoRA SFT

Answer and Verifier use separate configs in `training/configs/`. Both templates use 4-bit NF4, double quantization, bfloat16 compute and LoRA over `all-linear`. The templates intentionally contain invalid base-model placeholders. Select a license-compatible base model, review its chat template and pin an immutable revision before changing them.

```bash
# Resolve and lock requirements-training.in in the target CUDA image first.
.venv/bin/python scripts/run_qlora_sft.py \
  --role answer \
  --config training/configs/answer_qlora.json \
  --dataset-manifest .artifacts/training/medguard-training-v1/manifest.json \
  --output-dir .artifacts/models/medguard-answer-v1
```

The runner rejects placeholders, floating revisions, role mismatches, absent validation data and manifest checksum failures before importing GPU libraries. It trains only `train`, evaluates during training only on `validation`, and never passes the held-out `test` split to `SFTTrainer`. It writes an adapter artifact manifest and does not merge or deploy the adapter.

This follows the current [TRL SFT conversational dataset contract](https://huggingface.co/docs/trl/sft_trainer) and [PEFT QLoRA guidance for all linear layers](https://huggingface.co/docs/peft/main/package_reference/lora). Exact package and CUDA versions must be resolved together and frozen in the training image; `requirements-training.in` is intentionally not a reproducibility claim.

## Held-Out Evaluation

Generate role-specific predictions from the untouched `test` split, then evaluate them:

```bash
.venv/bin/python scripts/evaluate_training_candidate.py \
  --role answer \
  --predictions /secure/evaluations/medguard-answer-v1.jsonl \
  --dataset-manifest .artifacts/training/medguard-training-v1/manifest.json \
  --output .artifacts/evaluations/medguard-answer-v1.json
```

The evaluator requires predictions to cover exactly every sample ID and task category in the role's held-out test split. The report is checksum-bound to that dataset manifest. The Answer gate checks schema success, locked-claim preservation, citation support, tool adherence, unsafe instruction rate and severe safety misses. The Verifier gate checks unsafe recall, safe specificity, false passes, missing-warning recall and violation-type recall. Both require category and class coverage. Training loss alone never satisfies promotion.

The default thresholds are development governance targets, not validated clinical acceptance criteria. Clinical and model-risk owners must independently approve the final thresholds and adjudicate the test labels.

## Registry And Promotion

Promotion requires four matching objects:

- SHA-256 artifact manifest generated by the trainer.
- SHA-256 dataset manifest approved for SFT.
- Passing held-out evaluation report for the same model ID, role and dataset-manifest checksum.
- Explicit approval record from clinical safety or the model-risk committee.

```bash
.venv/bin/python scripts/promote_model_candidate.py \
  --artifact-manifest .artifacts/models/medguard-answer-v1/artifact-manifest.json \
  --dataset-manifest .artifacts/training/medguard-training-v1/manifest.json \
  --evaluation-report .artifacts/evaluations/medguard-answer-v1.json \
  --approval /secure/approvals/medguard-answer-v1.json
```

Promotion updates `training/registry/models.json`, stores a rollback pointer and never edits live LiteLLM routing. `training/approval-template.json` is pending and cannot promote anything.

## Serving And Gateway

`infrastructure/model-serving/docker-compose.yml` defines isolated Answer and Verifier vLLM services using static LoRA adapters. It pins base revisions, binds ports to localhost, protects APIs with internal keys and explicitly sets `VLLM_ALLOW_RUNTIME_LORA_UPDATING=False`. vLLM documents static LoRA serving through its OpenAI-compatible server and warns that dynamic adapter loading is unsafe outside a trusted environment: [vLLM LoRA adapters](https://docs.vllm.ai/en/stable/features/lora/), [vLLM security](https://docs.vllm.ai/en/latest/usage/security/).

`infrastructure/litellm/expert-models.candidate.yaml` is deliberately separate from the active Gateway config. After registry promotion, deploy candidate endpoints under restricted aliases, probe structured output and tool/search capabilities, then run deidentified shadow traffic. Production aliases change only after live quality, safety, latency, cost and rollback evidence pass review.

An OpenAI-compatible vLLM endpoint does not by itself provide MedGuard's trusted web search. Before either self-hosted role can enter a live fallback chain, it must receive independently retrieved, allowlisted evidence through an approved tool contract, or expose a search capability that satisfies the existing citation gate. Until then, the deterministic release gate rejects missing search evidence. Fine-tuning is never used as a substitute for retrieval.

Using one base model with two adapters saves storage but does not provide genuinely independent model-family verification. For high-risk release, keep a distinct-family verifier or external verifier fallback plus the deterministic release gate.

## DPO Status

DPO is deferred. It may be added only after SFT passes and independently reviewed preference pairs exist. The current project does not generate synthetic chosen/rejected pairs and does not treat model-authored preference labels as expert approval.

## Current Status

```bash
.venv/bin/python scripts/validate_training_plane.py
```

The architecture contract currently passes all 11 controls. No governed training dataset, trained adapter, held-out prediction set or approved model exists in the repository, so `expert_models_ready=false`. This is the correct fail-closed state.
