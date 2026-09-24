"""Fail-closed QR payload parsing and versioned product-registry matching."""

from __future__ import annotations

import json
from hashlib import sha256

from app.core.context import RequestContext
from app.knowledge.loader import knowledge
from app.models.product import ProductVerificationRequest, ProductVerificationResponse
from app.services.audit import AuditEvent, audit_store


def _decode(raw_code: str) -> dict[str, str]:
    raw = raw_code.strip()
    if raw.startswith("{"):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return {str(key).lower(): str(value).strip() for key, value in parsed.items() if value is not None}
    if "|" in raw:
        decoded: dict[str, str] = {}
        for part in raw.split("|"):
            if "=" in part:
                key, value = part.split("=", 1)
                decoded[key.strip().lower()] = value.strip()
        return decoded
    return {"product": raw}


def verify_product_code(
    payload: ProductVerificationRequest,
    ctx: RequestContext,
) -> ProductVerificationResponse:
    decoded = _decode(payload.raw_code)
    product_code = decoded.get("product") or decoded.get("product_code") or decoded.get("gtin")
    product = next(
        (
            item
            for item in knowledge.product_registry
            if product_code in {str(item.get("product_code")), str(item.get("gtin"))}
        ),
        None,
    )
    reasons: list[str] = []
    status = "unknown"
    if not product_code:
        status = "invalid"
        reasons.append("QR không chứa product_code hoặc GTIN hợp lệ.")
    elif product is None:
        reasons.append("Mã sản phẩm chưa tồn tại trong registry đang được cấu hình.")
    elif product.get("status") == "recalled":
        status = "recalled"
        reasons.append("Lô sản phẩm nằm trong danh sách thu hồi của registry.")
    else:
        serial = decoded.get("serial")
        lot = decoded.get("lot")
        if not serial or not lot:
            reasons.append("Thiếu serial hoặc lot nên chưa thể đối chiếu đầy đủ.")
        elif serial not in product.get("authorized_serials", []):
            status = "suspected_counterfeit"
            reasons.append("Serial không thuộc danh sách được nhà sản xuất công bố.")
        elif lot not in product.get("lots", []):
            status = "suspected_counterfeit"
            reasons.append("Mã lô không khớp hồ sơ sản phẩm.")
        else:
            status = "registry_match"
            reasons.append("Product code, serial và lot khớp registry phiên bản hiện tại.")

    response = ProductVerificationResponse(
        request_id=ctx.request_id,
        verification_status=status,
        product=product,
        decoded=decoded,
        reasons=reasons,
    )
    audit_store.append(
        AuditEvent(
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            action="product.verify",
            payload_type="ProductVerificationRequest",
            metadata={
                "code_sha256": sha256(payload.raw_code.encode("utf-8")).hexdigest(),
                "verification_status": status,
                "registry_version": knowledge.files["product_registry.json"].version,
            },
        )
    )
    return response
