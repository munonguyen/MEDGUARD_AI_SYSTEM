"""Consent verification service (Chapter 5.5).

Enforces:
- The AI service does not collect consent directly; it requires clients
  to assert and provide valid consent proof (such as a consent record ID or token).
- Revoked or declined consent is rejected immediately with HTTP 403 (consent_revoked).
- When enforcement is active, missing consent is rejected with HTTP 403 (consent_required).
"""

from __future__ import annotations

from fastapi import Header, HTTPException, Request, status

from app.core.config import settings


def verify_patient_consent(
    request: Request,
    x_consent_token: str | None = Header(default=None, alias="X-Consent-Token"),
    x_consent_record_ref: str | None = Header(
        default=None, alias="X-Consent-Record-Ref"
    ),
) -> str:
    """Verifies that client provided evidence of patient consent for AI processing."""
    from app.core.accounts import COOKIE

    if request.cookies.get(COOKIE):
        user = request.app.state.accounts.authenticate(request)
        if not user["consent"]:
            raise HTTPException(
                status_code=403, detail={"error_code": "consent_required"}
            )
        return "account-consent:" + user["user_id"]
    consent_proof = x_consent_token or x_consent_record_ref

    if consent_proof:
        normalized = consent_proof.strip()
        if normalized.lower() in ("revoked", "declined", "invalid"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": "consent_revoked",
                    "message": "Patient has declined or revoked consent for AI medical processing.",
                },
            )
        return normalized

    if settings.enforce_consent:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "consent_required",
                "message": (
                    "Patient informed consent for AI processing is required. "
                    "Provide X-Consent-Token or X-Consent-Record-Ref from client ConsentRecord."
                ),
            },
        )

    return "consent-bypass-dev"
