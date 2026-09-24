"""Run role-specific QLoRA SFT only from a governed compiled manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from training.dataset_pipeline import DatasetValidationError, validate_compiled_manifest  # noqa: E402
from training.model_registry import build_artifact_manifest  # noqa: E402


class QLoRAConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["medguard.qlora-config.v1"]
    role: Literal["answer", "verifier"]
    model_id: str = Field(pattern=r"^medguard-(?:answer|verifier)-v[a-zA-Z0-9._-]+$")
    base_model: str
    base_revision: str
    max_length: int = Field(ge=512, le=32768)
    load_in_4bit: Literal[True]
    bnb_4bit_quant_type: Literal["nf4"]
    bnb_4bit_use_double_quant: bool
    bnb_4bit_compute_dtype: Literal["bfloat16"]
    lora_rank: int = Field(ge=1, le=256)
    lora_alpha: int = Field(ge=1, le=512)
    lora_dropout: float = Field(ge=0, le=0.5)
    target_modules: Literal["all-linear"]
    learning_rate: float = Field(gt=0, le=0.01)
    epochs: float = Field(gt=0, le=20)
    per_device_train_batch_size: int = Field(ge=1, le=64)
    gradient_accumulation_steps: int = Field(ge=1, le=512)
    seed: int

    @model_validator(mode="after")
    def identifiers_are_pinned(self) -> "QLoRAConfig":
        if not self.model_id.startswith(f"medguard-{self.role}-v"):
            raise ValueError("model_id does not match training role")
        forbidden = {"main", "master", "latest", "head", "replace_with_immutable_commit_sha"}
        if self.base_model.startswith("REPLACE_"):
            raise ValueError("base_model must be an approved model identifier")
        if self.base_revision.lower() in forbidden or self.base_revision.startswith("REPLACE_"):
            raise ValueError("base_revision must be an immutable reviewed revision")
        if len(self.base_revision) < 7:
            raise ValueError("base_revision is too short to be immutable")
        return self


def _load_config(path: Path, role: str) -> QLoRAConfig:
    config = QLoRAConfig.model_validate_json(path.read_text(encoding="utf-8"))
    if config.role != role:
        raise ValueError("CLI role does not match QLoRA config role")
    return config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=("answer", "verifier"), required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        config = _load_config(args.config, args.role)
        validate_compiled_manifest(args.dataset_manifest, role=args.role)
        train_path = args.dataset_manifest.parent / f"{args.role}-train.jsonl"
        validation_path = args.dataset_manifest.parent / f"{args.role}-validation.jsonl"
        if not validation_path.is_file():
            raise DatasetValidationError("a separate validation split is required before SFT")
    except (OSError, ValueError, DatasetValidationError) as exc:
        print(f"QLoRA preflight rejected: {exc}", file=sys.stderr)
        return 1

    try:
        import torch
        from datasets import load_dataset
        from peft import LoraConfig, prepare_model_for_kbit_training
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from trl import SFTConfig, SFTTrainer
    except ImportError as exc:
        print(
            "training dependencies are unavailable; resolve requirements-training.in "
            "inside a pinned CUDA training image",
            file=sys.stderr,
        )
        return 2

    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type=config.bnb_4bit_quant_type,
        bnb_4bit_use_double_quant=config.bnb_4bit_use_double_quant,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    tokenizer = AutoTokenizer.from_pretrained(
        config.base_model,
        revision=config.base_revision,
        trust_remote_code=False,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        config.base_model,
        revision=config.base_revision,
        quantization_config=quantization,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=False,
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    adapter = LoraConfig(
        r=config.lora_rank,
        lora_alpha=config.lora_alpha,
        lora_dropout=config.lora_dropout,
        target_modules=config.target_modules,
        bias="none",
        task_type="CAUSAL_LM",
    )
    dataset = load_dataset(
        "json",
        data_files={"train": str(train_path), "validation": str(validation_path)},
    )
    training_args = SFTConfig(
        output_dir=str(args.output_dir),
        max_length=config.max_length,
        num_train_epochs=config.epochs,
        learning_rate=config.learning_rate,
        per_device_train_batch_size=config.per_device_train_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        gradient_checkpointing=True,
        bf16=True,
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="epoch",
        seed=config.seed,
        report_to="none",
    )
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        processing_class=tokenizer,
        peft_config=adapter,
    )
    trainer.train()
    trainer.save_model(str(args.output_dir))
    tokenizer.save_pretrained(str(args.output_dir))
    artifact = build_artifact_manifest(
        output_dir=args.output_dir,
        model_id=config.model_id,
        role=config.role,
        base_model=config.base_model,
        base_revision=config.base_revision,
        dataset_manifest_path=args.dataset_manifest,
        training_config_path=args.config,
    )
    artifact_path = args.output_dir / "artifact-manifest.json"
    artifact_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    print("Adapter trained but not promoted. Run held-out evaluation and approval next.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
