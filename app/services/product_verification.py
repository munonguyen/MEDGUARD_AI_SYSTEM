"""Fail-closed QR payload parsing and versioned product-registry matching."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from hashlib import sha256
from urllib.parse import parse_qs, urlparse

from app.core.context import RequestContext
from app.knowledge.loader import knowledge
from app.models.product import ProductVerificationRequest, ProductVerificationResponse
from app.services.audit import AuditEvent, audit_store


def _decode(raw_code: str) -> dict[str, str]:
    raw = raw_code.strip()
    # Strip user chat prefixes
    raw = re.sub(
        r"^(kiểm tra (qr|mã vạch|mã)( hàng giả)?|quét (qr|mã vạch|mã)|xác thực (qr|mã vạch|mã)|mã qr|qr code|mã vạch|barcode)[\s:]*",
        "",
        raw,
        flags=re.IGNORECASE,
    ).strip()

    # 1. URL format
    if raw.startswith(("http://", "https://")):
        try:
            parsed_url = urlparse(raw)
            qs = parse_qs(parsed_url.query)
            decoded = {k.lower(): v[0].strip() for k, v in qs.items() if v}
            if "code" in decoded and not decoded.get("product"):
                decoded["product"] = decoded.pop("code")
            if decoded:
                return decoded
        except Exception:
            pass

    # 2. JSON format
    if raw.startswith("{") and raw.endswith("}"):
        try:
            parsed = json.loads(raw)
            return {str(key).lower(): str(value).strip() for key, value in parsed.items() if value is not None}
        except json.JSONDecodeError:
            pass

    # 3. Delimited key-value or positional (pipe or ampersand)
    if "|" in raw or "&" in raw:
        delimiter = "|" if "|" in raw else "&"
        parts = [p.strip() for p in raw.split(delimiter) if p.strip()]
        decoded: dict[str, str] = {}
        has_eq = False
        for part in parts:
            if "=" in part:
                has_eq = True
                key, value = part.split("=", 1)
                decoded[key.strip().lower()] = value.strip()
        if has_eq:
            return decoded

        # Positional format: [MEDGUARD], <product>, <lot>, <serial>
        if len(parts) >= 2:
            offset = 1 if parts[0].upper() == "MEDGUARD" else 0
            res: dict[str, str] = {}
            if len(parts) > offset:
                res["product"] = parts[offset]
            if len(parts) > offset + 1:
                res["lot"] = parts[offset + 1]
            if len(parts) > offset + 2:
                res["serial"] = parts[offset + 2]
            return res

    # 4. GS1 Application Identifiers format e.g. (01)08960001000017(21)VN24A001(10)AMX2409
    gs1_matches = dict(re.findall(r"\((\d{2})\)([^\(]+)", raw))
    if gs1_matches:
        res = {}
        if "01" in gs1_matches:
            res["gtin"] = gs1_matches["01"].strip()
        if "21" in gs1_matches:
            res["serial"] = gs1_matches["21"].strip()
        if "10" in gs1_matches:
            res["lot"] = gs1_matches["10"].strip()
        if "17" in gs1_matches:
            res["exp"] = gs1_matches["17"].strip()
        if res:
            return res

    return {"product": raw}


def verify_product_code(
    payload: ProductVerificationRequest,
    ctx: RequestContext,
) -> ProductVerificationResponse:
    decoded = _decode(payload.raw_code)
    product_code = (
        decoded.get("product")
        or decoded.get("product_code")
        or decoded.get("gtin")
        or decoded.get("code")
    )
    _ALIASES = {
        "AMX-500": "MG-AMOX-500",
        "AMOX-500": "MG-AMOX-500",
        "ASP-81": "MG-ASP-81",
        "PARA-500": "MG-PARA-500",
        "PAN-EXT": "MG-PAN-EXT",
        "AUG-625": "MG-AUG-625",
        "RECALLED-DEMO-01": "MG-RECALL-001",
        "RECALL-001": "MG-RECALL-001",
    }
    candidate_keys: set[str] = set()
    if product_code:
        raw_key = str(product_code).strip()
        raw_upper = raw_key.upper()
        candidate_keys.update({raw_key, raw_upper})
        if raw_upper.isdigit():
            if len(raw_upper) == 13:
                candidate_keys.add(f"0{raw_upper}")
            elif len(raw_upper) == 14 and raw_upper.startswith("0"):
                candidate_keys.add(raw_upper[1:])
        if raw_upper in _ALIASES:
            candidate_keys.add(_ALIASES[raw_upper])
        if not raw_upper.startswith("MG-"):
            candidate_keys.add(f"MG-{raw_upper}")
        else:
            candidate_keys.add(raw_upper[3:])

    product = next(
        (
            item
            for item in knowledge.product_registry
            if any(
                cand in {
                    str(item.get("product_code")),
                    str(item.get("product_code", "")).upper(),
                    str(item.get("gtin")),
                    f"0{item.get('gtin', '')}" if len(str(item.get("gtin", ""))) == 13 else "",
                    str(item.get("gtin", ""))[1:] if len(str(item.get("gtin", ""))) == 14 and str(item.get("gtin", "")).startswith("0") else "",
                }
                for cand in candidate_keys
            )
        ),
        None,
    )
    reasons: list[str] = []
    status = "unknown"
    if not product_code:
        status = "invalid"
        reasons.append("Không tìm thấy mã sản phẩm hoặc mã vạch GTIN hợp lệ.")
    elif product is None:
        reasons.append(f"Mã sản phẩm / mã vạch '{product_code}' chưa tồn tại trong registry nhà sản xuất đang kết nối.")
    elif product.get("status") == "recalled":
        status = "recalled"
        reasons.append("CẢNH BÁO: Lô sản phẩm nằm trong danh mục thu hồi khẩn cấp của nhà sản xuất / cơ quan y tế.")
    else:
        serial = decoded.get("serial")
        lot = decoded.get("lot")
        today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        is_expired = bool(product.get("expires_on") and product["expires_on"] < today_iso)

        if is_expired:
            status = "expired"
            reasons.append(f"CẢNH BÁO: Thuốc đã hết hạn sử dụng từ ngày {product['expires_on']}.")
        elif product.get("authorized_serials") and not serial:
            status = "unknown"
            reasons.append(f"Đã nhận diện sản phẩm {product.get('name')}, nhưng mã thiếu serial hoặc lot để xác thực chống giả cá thể.")
        elif serial and product.get("authorized_serials") and serial not in product.get("authorized_serials", []):
            status = "suspected_counterfeit"
            reasons.append(f"CẢNH BÁO: Serial '{serial}' không thuộc danh sách được nhà sản xuất công bố xuất xưởng (nguy cơ hàng giả/hàng nhái).")
        elif lot and product.get("lots") and lot not in product.get("lots", []):
            status = "suspected_counterfeit"
            reasons.append(f"CẢNH BÁO: Số lô '{lot}' không khớp với hồ sơ lưu hành của sản phẩm.")
        else:
            status = "registry_match"
            if not serial and not product.get("authorized_serials"):
                reasons.append(f"Mã vạch thương phẩm (GTIN/EAN-13: {product.get('gtin')}) trùng khớp với hồ sơ công bố của {product.get('manufacturer')}.")
            else:
                reasons.append("Mã sản phẩm, số lô (lot) và mã định danh (serial) hoàn toàn trùng khớp với hồ sơ registry của nhà sản xuất.")

        if product.get("registration_number"):
            reasons.append(f"Số đăng ký / Số ĐKSP: {product['registration_number']}")
        if product.get("regulatory_note"):
            reasons.append(f"Lưu ý phân loại: {product['regulatory_note']}")

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
