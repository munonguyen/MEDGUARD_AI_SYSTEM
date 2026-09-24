"""Cryptographic Vault and Seal Verification Utility for Blind Benchmark V5.

Ensures that:
1. Oracle data is encrypted or sealed, inaccessible to inference runner.
2. Inference output (predictions.jsonl) is cryptographically signed/hashed upon completion.
3. Evaluator strictly verifies that the run is SEALED and tamper-free before unlocking Oracle.
"""

from __future__ import annotations

import base64
from hashlib import pbkdf2_hmac, sha256
import hmac
import json
import os
from pathlib import Path
from typing import Any

# Default salt for HMAC / key derivation (can be overridden via environment)
DEFAULT_VAULT_SALT = b"medguard_blind_v5_sealed_eval_salt_2026"

# Secret Canary Token to detect any premature leakage of Oracle into runner/predictions
ORACLE_LEAKAGE_CANARY = "DO_NOT_LEAK_V5_CANARY_8D33"


def check_canary_leakage(text_or_path: str | Path) -> tuple[bool, str]:
    """Scan text or file to verify Oracle canary has NOT leaked into runner outputs.
    
    Returns (True, 'CLEAN') if canary is not found, or (False, error_msg) if leaked.
    """
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
    """Package JSON data into an authenticated sealed envelope.
    
    Uses HMAC-SHA256 signature and Base64 encoded payload to ensure tamper-proof packaging.
    """
    raw_bytes = json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")
    b64_payload = base64.b64encode(raw_bytes).decode("ascii")
    
    if key is None:
        key = derive_key(os.getenv("MEDGUARD_VAULT_KEY", "medguard-v5-sealed-vault-default-key"))
        
    signature = hmac.new(key, raw_bytes, sha256).hexdigest()
    content_hash = sha256(raw_bytes).hexdigest()
    
    return {
        "format": "medguard-sealed-vault-v1",
        "sha256": content_hash,
        "signature": signature,
        "payload": b64_payload,
    }


def unseal_vault_data(envelope: dict[str, str], key: bytes | None = None) -> Any:
    """Unseal and verify the authenticated vault envelope.
    
    Raises ValueError if signature does not match or payload has been tampered with.
    """
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
        key = derive_key(os.getenv("MEDGUARD_VAULT_KEY", "medguard-v5-sealed-vault-default-key"))
        
    actual_sig = hmac.new(key, raw_bytes, sha256).hexdigest()
    if not hmac.compare_digest(actual_sig, expected_sig):
        raise PermissionError("Vault authentication failure: invalid HMAC signature")
        
    return json.loads(raw_bytes.decode("utf-8"))


def save_sealed_vault(data: Any, out_path: str | Path, key: bytes | None = None) -> None:
    """Seal data and write envelope to disk."""
    envelope = seal_vault_data(data, key=key)
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(envelope, f, indent=2, ensure_ascii=False)


def load_sealed_vault(in_path: str | Path, key: bytes | None = None) -> Any:
    """Read sealed envelope from disk, verify authentication, and return data."""
    p = Path(in_path)
    if not p.exists():
        raise FileNotFoundError(f"Vault envelope not found at: {p}")
    with open(p, "r", encoding="utf-8") as f:
        envelope = json.load(f)
    return unseal_vault_data(envelope, key=key)


def verify_run_seal(predictions_path: Path | str, manifest_path: Path | str) -> tuple[bool, str]:
    """Verify that predictions.jsonl is locked, sealed, and matches the manifest."""
    p_file = Path(predictions_path)
    m_file = Path(manifest_path)
    
    if not m_file.exists():
        return False, f"Run manifest not found at: {m_file}. Run has not completed or has not been sealed."
        
    if not p_file.exists():
        return False, f"Predictions file not found at: {p_file}."
        
    try:
        with open(m_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        return False, f"Failed to parse run manifest: {e}"
        
    status = manifest.get("status")
    if status != "SEALED":
        return False, f"Run status is '{status}', expected 'SEALED'. Evaluator cannot run on unsealed inference."
        
    expected_hash = manifest.get("predictions_sha256") or manifest.get("prediction_sha256")
    if not expected_hash:
        return False, "Run manifest does not contain 'predictions_sha256' or 'prediction_sha256'."
        
    actual_hash = compute_sha256(p_file)
    if actual_hash != expected_hash:
        return False, (
            f"PREDICTION TAMPER DETECTED!\n"
            f"  Manifest Hash:    {expected_hash}\n"
            f"  Predictions Hash: {actual_hash}\n"
            f"Predictions file was modified after run seal."
        )
        
    return True, "Manifest is SEALED and SHA256 matches perfectly."

