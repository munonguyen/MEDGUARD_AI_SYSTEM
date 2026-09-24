"""Read-only GO/NO-GO audit for an independently supplied Blind V10 suite."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blind_v10.freeze_guard import verify_freeze_integrity
from blind_v10.runner.run_v10 import load_blind_cases
from blind_v10.seal import CANARY_ENV, HMAC_KEY_ENV, file_sha256


def _git_commit(ref: str) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", f"{ref}^{{commit}}"], cwd=REPO_ROOT, text=True
    ).strip()


def audit_go_nogo(
    cases_path: Path,
    output_dir: Path,
) -> tuple[bool, list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": passed, "detail": detail})

    freeze_ok, freeze_errors = verify_freeze_integrity()
    add("freeze_guard", freeze_ok, "valid" if freeze_ok else repr(freeze_errors))

    try:
        core_commit = _git_commit("v10-candidate-core")
        frozen_commit = _git_commit("v10-blind-frozen")
        head_commit = _git_commit("HEAD")
        tags_ok = head_commit == frozen_commit and bool(core_commit)
        add(
            "immutable_git_identity",
            tags_ok,
            f"core={core_commit}; frozen={frozen_commit}; HEAD={head_commit}",
        )
    except Exception as exc:
        add("immutable_git_identity", False, str(exc))

    try:
        cases = load_blind_cases(cases_path)
        add("sealed_case_contract", len(cases) == 300, f"{len(cases)}/300 oracle-free cases")
        add("sealed_cases_sha256", True, file_sha256(cases_path))
    except Exception as exc:
        add("sealed_case_contract", False, str(exc))
        add("sealed_cases_sha256", False, "not computed")

    existing = []
    if output_dir.exists():
        existing = [item.name for item in output_dir.iterdir() if item.name != ".gitkeep"]
    add(
        "empty_output_directory",
        not existing,
        "empty" if not existing else f"existing: {', '.join(sorted(existing))}",
    )

    hmac_configured = len(os.environ.get(HMAC_KEY_ENV, "")) >= 32
    canary_configured = len(os.environ.get(CANARY_ENV, "")) >= 16
    add("independent_hmac_key", hmac_configured, f"{HMAC_KEY_ENV} configured={hmac_configured}")
    add("oracle_canary", canary_configured, f"{CANARY_ENV} configured={canary_configured}")

    plaintext_oracles = [
        path
        for path in cases_path.parent.rglob("*")
        if path.is_file()
        and path != cases_path
        and path.name.lower() in {"oracle.json", "oracle.jsonl", "answers.json"}
    ]
    add(
        "oracle_inaccessible_to_runner",
        not plaintext_oracles,
        "no plaintext oracle adjacent to cases"
        if not plaintext_oracles
        else f"plaintext oracle files found: {plaintext_oracles}",
    )

    evaluator_source = (REPO_ROOT / "blind_v10" / "evaluator" / "evaluate_v10.py").read_text(encoding="utf-8")
    gates_locked = all(f'"B10-G{index}"' in evaluator_source for index in range(1, 15))
    add("predeclared_release_gates", gates_locked, "B10-G1 through B10-G14 present")

    runner_source = (REPO_ROOT / "blind_v10" / "runner" / "run_v10.py").read_text(encoding="utf-8")
    runner_isolated = "blind_v10.evaluator" not in runner_source.replace(
        'fullname.startswith("blind_v10.evaluator")', ""
    )
    add("runner_evaluator_isolation", runner_isolated, "runner has no evaluator import")

    return all(item["passed"] for item in checks), checks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    go, checks = audit_go_nogo(args.cases.resolve(), args.output_dir.resolve())
    result = {"decision": "GO" if go else "NO-GO", "checks": checks}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if go else 1)


if __name__ == "__main__":
    main()
