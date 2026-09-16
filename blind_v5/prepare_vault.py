"""Utility to split and vault Benchmark cases into Sealed Cases and Oracle Vault for V5.

Enforces:
1. Input Blindness: sealed_cases/ contains ONLY case_id and messages.
2. Oracle Secrecy: oracle_vault/ contains labels, acceptable ranges, and fail criteria.
3. Cryptographic Envelopes: Produces .json and authenticated .enc sealed files.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

# Ensure workspace root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blind_v5.vault_crypto import ORACLE_LEAKAGE_CANARY, save_sealed_vault


def split_and_vault_cases(
    raw_cases: list[dict[str, Any]],
    vault_root: Path | str,
    key: bytes | None = None,
    keep_plaintext_oracle: bool = False,
) -> tuple[Path, Path]:
    v_root = Path(vault_root)
    sealed_cases_dir = v_root / "sealed_cases"
    oracle_vault_dir = v_root / "oracle_vault"

    sealed_cases_dir.mkdir(parents=True, exist_ok=True)
    oracle_vault_dir.mkdir(parents=True, exist_ok=True)

    cases_json = sealed_cases_dir / "cases.json"
    cases_enc = sealed_cases_dir / "cases.enc"
    oracle_json = oracle_vault_dir / "oracle.json"
    oracle_enc = oracle_vault_dir / "oracle.enc"

    sealed_cases_list: list[dict[str, Any]] = []
    oracle_list: list[dict[str, Any]] = []

    for idx, c in enumerate(raw_cases, 1):
        cid = str(c.get("case_id") or c.get("id") or f"V5-{idx:04d}")
        
        # Extract messages
        msgs = c.get("messages")
        if not msgs:
            user_text = c.get("input") or c.get("text") or c.get("symptoms_text") or c.get("prompt") or ""
            history = c.get("messages_history") or []
            msgs = []
            for h in history:
                msgs.append({"role": h.get("role", "user"), "content": h.get("content", "")})
            msgs.append({"role": "user", "content": user_text})

        # Sealed Case Record (ZERO Oracle Info)
        sealed_cases_list.append({
            "case_id": cid,
            "messages": msgs,
        })

        # Oracle Vault Record
        exp_triage = str(c.get("expected_triage") or c.get("oracle_triage") or "ROUTINE")
        acceptable = c.get("acceptable_triage")
        if not acceptable:
            acceptable = ["EMERGENCY"] if exp_triage in ("T4", "EMERGENCY") else [exp_triage]

        oracle_list.append({
            "case_id": cid,
            "oracle_triage": exp_triage,
            "acceptable_triage": acceptable,
            "critical_fail_conditions": c.get("critical_fail_conditions") or [
                "final_triage == ROUTINE" if "T4" in exp_triage else "",
                "home_monitoring_advice == true" if "T4" in exp_triage else "",
            ],
            "must_detect": c.get("must_detect") or c.get("red_flags") or [],
            "must_not_assert": c.get("must_not_assert") or ["definitive_diagnosis"],
            "cohort": c.get("cohort") or c.get("group") or "general",
            "clinical_domain": c.get("clinical_domain") or "general_triage",
        })

    # Write plain JSON for sealed cases ONLY
    with open(cases_json, "w", encoding="utf-8") as f:
        json.dump(sealed_cases_list, f, indent=2, ensure_ascii=False)

    # Package Oracle Vault with Secret Canary to detect any premature leakage
    oracle_package = {
        "vault_canary": ORACLE_LEAKAGE_CANARY,
        "total_cases": len(oracle_list),
        "cases": oracle_list,
    }

    # Encrypt and seal Oracle Vault
    save_sealed_vault(oracle_package, oracle_enc, key=key)
    save_sealed_vault(sealed_cases_list, cases_enc, key=key)

    if keep_plaintext_oracle:
        with open(oracle_json, "w", encoding="utf-8") as f:
            json.dump(oracle_package, f, indent=2, ensure_ascii=False)

    return cases_json, oracle_enc
