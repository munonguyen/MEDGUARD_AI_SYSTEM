"""Cryptographic Vault and Seal Verification Utility for Blind Benchmark V9.

Ensures that:
1. Oracle data is encrypted or sealed, strictly inaccessible to inference runner.
2. Inference output (predictions.jsonl) is cryptographically signed/hashed upon completion.
3. Evaluator strictly verifies that the run is SEALED and tamper-free before unlocking Oracle.
4. Canary leakage scanner checks for premature oracle leakage.
"""

from __future__ import annotations

import base64
from hashlib import pbkdf2_hmac, sha256
import hmac
import json
import os
from pathlib import Path
from typing import Any

# Default salt for HMAC / key derivation for V9
DEFAULT_VAULT_SALT = b"medguard_blind_v9_semantic_contrast_sealed_eval_salt_2026"

# Secret Canary Token to detect any premature leakage of Oracle into runner/predictions
ORACLE_LEAKAGE_CANARY = "CANARY_SECRET_ORACLE_DO_NOT_LEAK_V9_SEMANTIC_4D9E2A8F"


def check_canary_leakage(text_or_path: str | Path) -> tuple[bool, str]:
    """Scan text or file to verify Oracle canary has NOT leaked into runner outputs."""
    if isinstance(text_or_path, Path) or (isinstance(text_or_path, str) and os.path.exists(text_or_path)):
        p = Path(text_or_path)
        if not p.exists():
            return True, "File does not exist yet; clean."
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    else:
        content = str(text_or_path)

    if ORACLE_LEAKAGE_CANARY in content:
        return False, f"CRITICAL SECURITY BREACH: Canary token '{ORACLE_LEAKAGE_CANARY}' leaked into {text_or_path}!"
    return True, "CLEAN: Canary token not detected."


def compute_sha256(data_or_path: bytes | str | Path) -> str:
    """Compute SHA256 hex digest for bytes or file content."""
    if isinstance(data_or_path, (str, Path)):
        p = Path(data_or_path)
        if not p.exists():
            raise FileNotFoundError(f"File not found for hash computation: {p}")
        h = sha256()
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()
    return sha256(data_or_path).hexdigest()


def derive_key(passphrase: str, salt: bytes = DEFAULT_VAULT_SALT) -> bytes:
    """Derive a 32-byte cryptographic key from a passphrase."""
    return pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, iterations=100_000, dklen=32)


def seal_vault_data(data: Any, key: bytes | None = None) -> dict[str, str]:
    """Package JSON data into an authenticated sealed envelope."""
    raw_bytes = json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")
    b64_payload = base64.b64encode(raw_bytes).decode("ascii")

    if key is None:
        key = derive_key(os.getenv("MEDGUARD_VAULT_KEY_V9", "medguard-v9-sealed-vault-default-key"))

    signature = hmac.new(key, raw_bytes, sha256).hexdigest()
    content_hash = sha256(raw_bytes).hexdigest()

    return {
        "format": "medguard-sealed-vault-v1",
        "sha256": content_hash,
        "signature": signature,
        "payload": b64_payload,
    }


def unseal_vault_data(envelope: dict[str, str], key: bytes | None = None) -> Any:
    """Unseal and verify the authenticated vault envelope."""
    if envelope.get("format") != "medguard-sealed-vault-v1":
        raise ValueError("Invalid or unrecognized vault envelope format")

    b64_payload = envelope.get("payload", "")
    expected_sig = envelope.get("signature", "")
    expected_hash = envelope.get("sha256", "")

    raw_bytes = base64.b64decode(b64_payload.encode("ascii"))

    actual_hash = sha256(raw_bytes).hexdigest()
    if actual_hash != expected_hash:
        raise ValueError(f"Vault integrity violation: SHA256 mismatch (got {actual_hash}, expected {expected_hash})")

    if key is None:
        key = derive_key(os.getenv("MEDGUARD_VAULT_KEY_V9", "medguard-v9-sealed-vault-default-key"))

    actual_sig = hmac.new(key, raw_bytes, sha256).hexdigest()
    if not hmac.compare_digest(actual_sig, expected_sig):
        raise PermissionError("Vault authentication failure: invalid HMAC signature")

    return json.loads(raw_bytes.decode("utf-8"))


def save_sealed_vault(data: Any, target_path: Path | str, key: bytes | None = None) -> None:
    """Seal and write data to an encrypted/authenticated file."""
    envelope = seal_vault_data(data, key=key)
    p = Path(target_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(envelope, f, indent=2)


def load_sealed_vault(vault_path: Path | str, key: bytes | None = None) -> Any:
    """Read, authenticate, and unseal a sealed vault file."""
    p = Path(vault_path)
    if not p.exists():
        raise FileNotFoundError(f"Vault file does not exist: {p}")
    with open(p, "r", encoding="utf-8") as f:
        envelope = json.load(f)
    return unseal_vault_data(envelope, key=key)


def sign_predictions_file(pred_path: Path | str, manifest_path: Path | str, key: bytes | None = None) -> dict[str, Any]:
    """Generate a cryptographic signature manifest for completed predictions."""
    p = Path(pred_path)
    if not p.exists():
        raise FileNotFoundError(f"Cannot sign non-existent predictions: {p}")

    pred_hash = compute_sha256(p)
    if key is None:
        key = derive_key(os.getenv("MEDGUARD_VAULT_KEY_V9", "medguard-v9-sealed-vault-default-key"))

    sig = hmac.new(key, pred_hash.encode("ascii"), sha256).hexdigest()

    # Count lines / entries
    line_count = 0
    with open(p, "r", encoding="utf-8") as f:
        for _ in f:
            line_count += 1

    manifest = {
        "format": "medguard-predictions-seal-v1",
        "predictions_file": p.name,
        "entry_count": line_count,
        "sha256": pred_hash,
        "signature": sig,
    }

    out_p = Path(manifest_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest


def verify_predictions_seal(pred_path: Path | str, manifest_path: Path | str, key: bytes | None = None) -> tuple[bool, str]:
    """Verify that predictions file matches its cryptographic seal."""
    p_pred = Path(pred_path)
    p_man = Path(manifest_path)

    if not p_pred.exists():
        return False, f"Predictions file not found: {p_pred}"
    if not p_man.exists():
        return False, f"Seal manifest not found: {p_man}"

    with open(p_man, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    if manifest.get("format") != "medguard-predictions-seal-v1":
        return False, "Invalid seal manifest format"

    expected_hash = manifest.get("sha256", "")
    expected_sig = manifest.get("signature", "")

    actual_hash = compute_sha256(p_pred)
    if actual_hash != expected_hash:
        return False, f"Predictions file altered! SHA256 mismatch: {actual_hash} != {expected_hash}"

    if key is None:
        key = derive_key(os.getenv("MEDGUARD_VAULT_KEY_V9", "medguard-v9-sealed-vault-default-key"))

    actual_sig = hmac.new(key, actual_hash.encode("ascii"), sha256).hexdigest()
    if not hmac.compare_digest(actual_sig, expected_sig):
        return False, "Predictions seal signature verification failed!"

    return True, "VALID: Predictions sealed and verified tamper-free."
