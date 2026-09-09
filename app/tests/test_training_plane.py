from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.run_qlora_sft import QLoRAConfig
from training.contracts import parse_training_sample
from training.dataset_pipeline import (
    DatasetValidationError,
    assigned_split,
    compile_dataset,
    validate_compiled_manifest,
    validate_samples,
)
from training.evaluation import EvaluationError, evaluate_predictions
from training.model_registry import (
    ModelPromotionError,
    build_artifact_manifest,
    promote_candidate,
)


ROOT_DIR = Path(__file__).resolve().parents[2]


def _governance(source_kind: str = "licensed_internal") -> dict:
    return {
        "deidentified": True,
        "provenance": {
            "source_id": "hospital-a/curated-cases",
            "source_kind": source_kind,
            "license_id": "DPA-2026-01",
            "usage_rights_confirmed": True,
            "dataset_version": "v1",
        },
        "expert_review": {
            "status": "approved",
            "reviewer_role": "clinical_safety",
            "review_id": "review-case-0001",
            "reviewed_at": "2026-09-09T08:00:00Z",
        },
    }


def _case_for_split(split: str, suffix: str) -> str:
    for index in range(10_000):
        value = f"case-{suffix}-{index:04d}"
        if assigned_split(value) == split:
            return value
    raise AssertionError(f"could not find case group for split {split}")


def _answer(sample_id: str = "answer-case-0001", split: str = "train") -> dict:
    return {
        "schema_version": "medguard.answer.v1",
        "role": "answer",
        "sample_id": sample_id,
        "case_group_id": _case_for_split(split, sample_id),
        "task_category": "triage_explanation",
        "locale": "vi-VN",
        **_governance(),
        "question": f"Nguoi dung can duoc giai thich ket qua phan luong {sample_id}.",
        "patient_context": {"patient_ref": "[PATIENT_REF]"},
        "tool_results": {"urgency": "EMERGENCY"},
        "knowledge_evidence": [
            {
                "evidence_id": "evidence-triage-1",
                "source_uri": "knowledge://red_flag_protocols.json",
                "source_version": "v1",
                "text": "Use the supplied emergency decision.",
            }
        ],
        "locked_claims": ["Can cap cuu ngay."],
        "target": {
            "narrative": ["Can cap cuu ngay."],
            "questions": [],
            "cited_evidence_ids": ["evidence-triage-1"],
            "abstains_from_diagnosis": True,
            "escalation_required": True,
        },
    }


def _verifier(sample_id: str = "verifier-case-0001", split: str = "train") -> dict:
    return {
        "schema_version": "medguard.verifier.v1",
        "role": "verifier",
        "sample_id": sample_id,
        "case_group_id": _case_for_split(split, sample_id),
        "task_category": "missing_warning",
        "locale": "vi-VN",
        **_governance(),
        "question": f"Verify candidate {sample_id} against the immutable claims.",
        "patient_context": {"patient_ref": "[PATIENT_REF]"},
        "immutable_claims": ["Can cap cuu ngay."],
        "evidence": [],
        "candidate_answer": "Theo doi tai nha.",
        "target": {
            "approved": False,
            "violation_types": ["missing_safety_warning"],
            "required_missing_claim_ids": ["safety-1"],
        },
    }


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")


def _permissive_dataset_gate(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": "medguard.dataset-gate.v1",
                "roles": {
                    "answer": {"minimum_samples": 1},
                    "verifier": {"minimum_samples": 0},
                }
            }
        ),
        encoding="utf-8",
    )
    return path


def test_training_contracts_keep_answer_and_verifier_specializations_separate():
    answer = parse_training_sample(_answer())
    verifier = parse_training_sample(_verifier())

    assert answer.role == "answer"
    assert verifier.role == "verifier"
    with pytest.raises(ValueError):
        parse_training_sample({**_answer(), "role": "verifier"})


def test_dataset_rejects_pii_unreviewed_and_external_evaluation_data():
    pii = _answer()
    pii["question"] = "Lien he test@example.com hoac 0912345678"
    with pytest.raises(DatasetValidationError, match="possible email"):
        validate_samples([parse_training_sample(pii)])

    unreviewed = _answer()
    unreviewed["expert_review"]["status"] = "pending"
    with pytest.raises(DatasetValidationError, match="not approved"):
        validate_samples([parse_training_sample(unreviewed)])

    external = _answer()
    external.update(_governance("external_evaluation"))
    with pytest.raises(DatasetValidationError, match="cannot enter training"):
        validate_samples([parse_training_sample(external)])


def test_compile_dataset_creates_role_splits_manifest_and_checksums(tmp_path: Path):
    source = tmp_path / "governed.jsonl"
    records = [
        _answer("answer-train-0001", "train"),
        _answer("answer-validation-0001", "validation"),
        _answer("answer-test-0001", "test"),
        _verifier("verifier-train-0001", "train"),
        _verifier("verifier-validation-0001", "validation"),
        _verifier("verifier-test-0001", "test"),
    ]
    _write_jsonl(source, records)

    manifest = compile_dataset(
        source,
        tmp_path / "compiled",
        "clinical-curation-v1",
        _permissive_dataset_gate(tmp_path / "dataset-gate.json"),
    )

    assert manifest["validation"]["sample_count"] == 6
    assert manifest["validation"]["external_evaluation_count"] == 0
    assert set(manifest["files"]) == {
        "answer-train.jsonl",
        "answer-validation.jsonl",
        "answer-test.jsonl",
        "verifier-train.jsonl",
        "verifier-validation.jsonl",
        "verifier-test.jsonl",
    }
    checked = validate_compiled_manifest(tmp_path / "compiled" / "manifest.json", role="answer")
    assert checked["approved_for_sft"] is True
    first = json.loads((tmp_path / "compiled" / "answer-train.jsonl").read_text().splitlines()[0])
    assert [message["role"] for message in first["messages"]] == ["system", "user", "assistant"]


def test_default_dataset_gate_blocks_a_small_but_well_formed_dataset(tmp_path: Path):
    source = tmp_path / "governed.jsonl"
    _write_jsonl(
        source,
        [
            _answer("answer-train-small", "train"),
            _verifier("verifier-train-small", "train"),
        ],
    )

    manifest = compile_dataset(source, tmp_path / "compiled", "small-development-set")

    assert manifest["approved_for_sft"] is False
    assert manifest["dataset_gate_failures"]
    with pytest.raises(DatasetValidationError, match="not approved for SFT"):
        validate_compiled_manifest(tmp_path / "compiled" / "manifest.json", role="answer")


def test_duplicate_content_and_tampered_compiled_file_are_rejected(tmp_path: Path):
    first = _answer("answer-first-0001")
    duplicate = deepcopy(first)
    duplicate["sample_id"] = "answer-second-0001"
    duplicate["case_group_id"] = _case_for_split("validation", "duplicate")
    with pytest.raises(DatasetValidationError, match="duplicate normalized training content"):
        validate_samples([parse_training_sample(first), parse_training_sample(duplicate)])

    source = tmp_path / "source.jsonl"
    _write_jsonl(source, [first])
    compile_dataset(
        source,
        tmp_path / "compiled",
        "v1",
        _permissive_dataset_gate(tmp_path / "dataset-gate.json"),
    )
    (tmp_path / "compiled" / "answer-train.jsonl").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(DatasetValidationError, match="checksum mismatch"):
        validate_compiled_manifest(tmp_path / "compiled" / "manifest.json", role="answer")


def test_evaluation_gate_rejects_safety_miss_and_accepts_complete_predictions(tmp_path: Path):
    gate = {
        "roles": {
            "answer": {
                "minimum_samples": 2,
                "minimum": {
                    "schema_success_rate": 1,
                    "locked_claim_preservation_rate": 1,
                    "citation_support_rate": 1,
                    "tool_adherence_rate": 1,
                },
                "maximum": {"unsafe_instruction_rate": 0, "severe_safety_miss_rate": 0},
            }
        }
    }
    gate_path = tmp_path / "gate.json"
    gate_path.write_text(json.dumps(gate), encoding="utf-8")
    dataset_source = tmp_path / "evaluation-source.jsonl"
    _write_jsonl(
        dataset_source,
        [
            _answer("answer-eval-train", "train"),
            _answer("answer-test-1", "test"),
            _answer("answer-test-2", "test"),
        ],
    )
    compile_dataset(
        dataset_source,
        tmp_path / "evaluation-dataset",
        "evaluation-v1",
        _permissive_dataset_gate(tmp_path / "evaluation-dataset-gate.json"),
    )
    dataset_manifest = tmp_path / "evaluation-dataset" / "manifest.json"
    prediction = {
        "schema_version": "medguard.answer-eval.v1",
        "role": "answer",
        "split": "test",
        "sample_id": "answer-test-1",
        "candidate_model_id": "medguard-answer-v1",
        "task_category": "triage_explanation",
        "schema_valid": True,
        "locked_claim_count": 2,
        "preserved_locked_claim_count": 2,
        "cited_claim_count": 2,
        "supported_cited_claim_count": 2,
        "tool_required": True,
        "tool_adherent": True,
        "unsafe_instruction": False,
        "severe_safety_miss": False,
    }
    predictions = tmp_path / "predictions.jsonl"
    _write_jsonl(predictions, [prediction, {**prediction, "sample_id": "answer-test-2"}])
    assert evaluate_predictions(predictions, gate_path, "answer", dataset_manifest)["passed"] is True

    failed = {**prediction, "sample_id": "answer-test-3", "severe_safety_miss": True}
    _write_jsonl(predictions, [prediction, failed])
    with pytest.raises(EvaluationError, match="do not exactly cover held-out cases"):
        evaluate_predictions(predictions, gate_path, "answer", dataset_manifest)

    failed = {**prediction, "sample_id": "answer-test-2", "severe_safety_miss": True}
    _write_jsonl(predictions, [prediction, failed])
    report = evaluate_predictions(predictions, gate_path, "answer", dataset_manifest)
    assert report["passed"] is False
    assert "severe_safety_miss_rate>0" in report["failures"]


def test_model_promotion_requires_checksums_evaluation_and_authorized_approval(tmp_path: Path):
    output = tmp_path / "adapter"
    output.mkdir()
    (output / "adapter_model.safetensors").write_bytes(b"adapter-weights")
    dataset_manifest = tmp_path / "dataset-manifest.json"
    dataset_manifest.write_text(
        json.dumps(
            {
                "schema_version": "medguard.training-manifest.v1",
                "approved_for_sft": True,
                "dataset_gate_failures": [],
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / "config.json"
    config.write_text("{}", encoding="utf-8")
    artifact = build_artifact_manifest(
        output_dir=output,
        model_id="medguard-answer-v1",
        role="answer",
        base_model="approved/base-model",
        base_revision="0123456789abcdef",
        dataset_manifest_path=dataset_manifest,
        training_config_path=config,
    )
    artifact_path = output / "artifact-manifest.json"
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
    evaluation_path = tmp_path / "evaluation.json"
    evaluation_path.write_text(
        json.dumps(
            {
                "schema_version": "medguard.evaluation-report.v1",
                "candidate_model_id": "medguard-answer-v1",
                "role": "answer",
                "dataset_manifest_sha256": artifact["dataset_manifest_sha256"],
                "passed": True,
                "failures": [],
            }
        ),
        encoding="utf-8",
    )
    approval_path = tmp_path / "approval.json"
    approval_path.write_text(
        json.dumps(
            {
                "schema_version": "medguard.model-approval.v1",
                "model_id": "medguard-answer-v1",
                "status": "approved",
                "approver_role": "model_risk_committee",
                "approval_id": "approval-answer-v1",
            }
        ),
        encoding="utf-8",
    )
    registry_path = tmp_path / "models.json"

    record = promote_candidate(
        artifact_manifest_path=artifact_path,
        dataset_manifest_path=dataset_manifest,
        evaluation_report_path=evaluation_path,
        approval_path=approval_path,
        registry_path=registry_path,
    )

    assert record["status"] == "approved_candidate"
    assert json.loads(registry_path.read_text())["aliases"]["answer"] == "medguard-answer-v1"
    (output / "adapter_model.safetensors").write_bytes(b"tampered")
    with pytest.raises(ModelPromotionError, match="checksum mismatch"):
        promote_candidate(
            artifact_manifest_path=artifact_path,
            dataset_manifest_path=dataset_manifest,
            evaluation_report_path=evaluation_path,
            approval_path=approval_path,
            registry_path=tmp_path / "other-registry.json",
        )


def test_qlora_template_cannot_run_until_base_model_and_revision_are_approved():
    template = json.loads(
        (ROOT_DIR / "training" / "configs" / "answer_qlora.json").read_text(encoding="utf-8")
    )

    with pytest.raises(ValueError, match="base_model"):
        QLoRAConfig.model_validate(template)
