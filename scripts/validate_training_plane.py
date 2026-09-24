"""Validate Training Plane isolation and fail-closed deployment contracts."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from scripts.run_qlora_sft import QLoRAConfig  # noqa: E402


def validate_training_plane() -> dict[str, Any]:
    training_dir = BASE_DIR / "training"
    answer_raw = json.loads((training_dir / "configs" / "answer_qlora.json").read_text())
    verifier_raw = json.loads((training_dir / "configs" / "verifier_qlora.json").read_text())
    dataset_gate = json.loads((training_dir / "dataset_gate.json").read_text())
    gate = json.loads((training_dir / "evaluation_gate.json").read_text())
    registry = json.loads((training_dir / "registry" / "models.json").read_text())
    serving = (BASE_DIR / "infrastructure" / "model-serving" / "docker-compose.yml").read_text()
    active_gateway = (BASE_DIR / "infrastructure" / "litellm" / "config.yaml").read_text()
    candidate_gateway = (
        BASE_DIR / "infrastructure" / "litellm" / "expert-models.candidate.yaml"
    ).read_text()

    answer_shape = answer_raw.get("role") == "answer" and answer_raw.get("target_modules") == "all-linear"
    verifier_shape = (
        verifier_raw.get("role") == "verifier" and verifier_raw.get("target_modules") == "all-linear"
    )
    templates_fail_closed = True
    for value in (answer_raw, verifier_raw):
        try:
            QLoRAConfig.model_validate(value)
        except ValueError:
            continue
        templates_fail_closed = False
    role_gates = set(gate.get("roles", {})) == {"answer", "verifier"}
    dataset_role_gates = set(dataset_gate.get("roles", {})) == {"answer", "verifier"}
    category_coverage = (
        len(dataset_gate["roles"]["answer"].get("minimum_category_samples", {})) == 6
        and len(dataset_gate["roles"]["verifier"].get("minimum_category_samples", {})) == 7
    )
    zero_tolerance = all(
        gate["roles"]["answer"]["maximum"].get(metric) == 0
        for metric in ("unsafe_instruction_rate", "severe_safety_miss_rate")
    )
    registry_shape = (
        registry.get("schema_version") == "medguard.model-registry.v1"
        and set(registry.get("aliases", {})) == {"answer", "verifier"}
    )
    dynamic_lora_disabled = 'VLLM_ALLOW_RUNTIME_LORA_UPDATING: "False"' in serving
    candidates_isolated = (
        "medguard-answer-expert-candidate" in candidate_gateway
        and "medguard-verifier-expert-candidate" in candidate_gateway
        and "expert-candidate" not in active_gateway
    )
    external_data_isolated = not any(
        path.is_file() and "mimic" in path.name.lower()
        for path in training_dir.rglob("*")
    )
    checks = {
        "answer_qlora_shape": answer_shape,
        "verifier_qlora_shape": verifier_shape,
        "templates_require_approved_base": templates_fail_closed,
        "separate_role_evaluation_gates": role_gates,
        "separate_role_dataset_gates": dataset_role_gates,
        "required_dataset_category_coverage": category_coverage,
        "zero_tolerance_answer_safety": zero_tolerance,
        "registry_contract": registry_shape,
        "dynamic_lora_disabled": dynamic_lora_disabled,
        "candidate_aliases_isolated": candidates_isolated,
        "external_evaluation_data_isolated": external_data_isolated,
    }
    aliases = registry.get("aliases", {})
    return {
        "checks": checks,
        "all_passed": all(checks.values()),
        "approved_answer_model": aliases.get("answer"),
        "approved_verifier_model": aliases.get("verifier"),
        "expert_models_ready": bool(aliases.get("answer") and aliases.get("verifier")),
    }


def main() -> int:
    report = validate_training_plane()
    print(json.dumps(report, indent=2))
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
