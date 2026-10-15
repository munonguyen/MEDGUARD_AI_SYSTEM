import pytest
from app.core.context import RequestContext
from app.models.product import ProductVerificationRequest
from app.services.product_verification import verify_product_code, _decode


def test_qr_decode_formats():
    # 1. Pipe positional with MEDGUARD prefix
    d1 = _decode("MEDGUARD|AMX-500|LOT-2024-09|VN24A001")
    assert d1.get("product") == "AMX-500"
    assert d1.get("lot") == "LOT-2024-09"
    assert d1.get("serial") == "VN24A001"

    # 2. Pipe positional without prefix
    d2 = _decode("AMX-500|LOT-2024-09|VN24A001")
    assert d2.get("product") == "AMX-500"
    assert d2.get("lot") == "LOT-2024-09"
    assert d2.get("serial") == "VN24A001"

    # 3. URL format
    d3 = _decode("https://medguard.vn/check?product=AMX-500&lot=LOT-2024-09&serial=VN24A001")
    assert d3.get("product") == "AMX-500"
    assert d3.get("lot") == "LOT-2024-09"
    assert d3.get("serial") == "VN24A001"

    # 4. JSON format
    d4 = _decode('{"product": "AMX-500", "lot": "LOT-2024-09", "serial": "VN24A001"}')
    assert d4.get("product") == "AMX-500"
    assert d4.get("lot") == "LOT-2024-09"
    assert d4.get("serial") == "VN24A001"

    # 5. GS1 AI format
    d5 = _decode("(01)08960001000017(10)LOT-2024-09(21)VN24A001")
    assert d5.get("gtin") == "08960001000017"
    assert d5.get("lot") == "LOT-2024-09"
    assert d5.get("serial") == "VN24A001"

    # 6. Strips conversational prefix
    d6 = _decode("Kiểm tra QR hàng giả: MEDGUARD|AMX-500|LOT-2024-09|VN24A001")
    assert d6.get("product") == "AMX-500"
    assert d6.get("lot") == "LOT-2024-09"


def test_verify_product_match():
    ctx = RequestContext(request_id="req-test-1", tenant_id="hospital-a", idempotency_key="idem-1")
    req = ProductVerificationRequest(raw_code="MEDGUARD|AMX-500|AMX2409|VN24A001")
    res = verify_product_code(req, ctx)
    assert res.verification_status == "registry_match"
    assert res.product is not None
    assert res.product["name"] == "Amoxicillin 500mg"
    assert any("trùng khớp" in r for r in res.reasons)


def test_verify_product_suspected_counterfeit_serial():
    ctx = RequestContext(request_id="req-test-2", tenant_id="hospital-a", idempotency_key="idem-2")
    # Valid product, valid lot, but counterfeit / forged serial
    req = ProductVerificationRequest(raw_code="MEDGUARD|AMX-500|AMX2409|FAKE-SERIAL-999")
    res = verify_product_code(req, ctx)
    assert res.verification_status == "suspected_counterfeit"
    assert any("không thuộc danh sách" in r or "hàng giả" in r for r in res.reasons)


def test_verify_product_suspected_counterfeit_lot():
    ctx = RequestContext(request_id="req-test-3", tenant_id="hospital-a", idempotency_key="idem-3")
    # Valid product, but fake lot
    req = ProductVerificationRequest(raw_code="MEDGUARD|AMX-500|LOT-FAKE-999|VN24A001")
    res = verify_product_code(req, ctx)
    assert res.verification_status == "suspected_counterfeit"
    assert any("Số lô" in r and "không khớp" in r for r in res.reasons)


def test_verify_product_recalled():
    ctx = RequestContext(request_id="req-test-4", tenant_id="hospital-a", idempotency_key="idem-4")
    # Recalled drug demo
    req = ProductVerificationRequest(raw_code="MEDGUARD|RECALL-001|RCL2301|VN23R001")
    res = verify_product_code(req, ctx)
    assert res.verification_status == "recalled"
    assert any("thu hồi" in r for r in res.reasons)


def test_verify_product_unknown():
    ctx = RequestContext(request_id="req-test-5", tenant_id="hospital-a", idempotency_key="idem-5")
    req = ProductVerificationRequest(raw_code="MEDGUARD|UNKNOWN-DRUG-X|LOT-001|SN-001")
    res = verify_product_code(req, ctx)
    assert res.verification_status == "unknown"


def test_api_product_verify_endpoint():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    headers = {
        "X-API-Key": "demo-key",
        "X-Tenant-Id": "tenant-demo",
        "Idempotency-Key": "test-qr-api-01",
    }
    resp = client.post(
        "/v1/product/verify",
        json={"raw_code": "product=MG-AMOX-500|lot=AMX2409|serial=VN24A001"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["verification_status"] == "registry_match"
    assert data["product"]["name"] == "Amoxicillin 500mg"


def test_chat_authenticity_intent_integration():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    headers = {
        "X-API-Key": "demo-key",
        "X-Tenant-Id": "tenant-demo",
        "X-Consent-Token": "consent-test",
        "Idempotency-Key": "test-chat-auth-01",
    }
    # 1. Genuine product scan
    resp = client.post(
        "/v1/chat",
        json={
            "conversation_id": "conv-test-auth-1",
            "messages": [{"role": "user", "content": "Kiểm tra QR hàng giả: product=MG-AMOX-500|lot=AMX2409|serial=VN24A001"}],
            "intent_hint": "authenticity",
            "locale": "vi-VN",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "authenticity"
    assert data["status"] == "answered"
    assert "chính hãng" in data["reply"].lower()
    assert data["result"]["verification_status"] == "registry_match"

    # 2. Counterfeit serial scan
    headers["Idempotency-Key"] = "test-chat-auth-02"
    resp2 = client.post(
        "/v1/chat",
        json={
            "conversation_id": "conv-test-auth-2",
            "messages": [{"role": "user", "content": "Kiểm tra QR hàng giả: product=MG-AMOX-500|lot=AMX2409|serial=FAKE-999"}],
            "intent_hint": "authenticity",
            "locale": "vi-VN",
        },
        headers=headers,
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["intent"] == "authenticity"
    assert "CẢNH BÁO" in data2["reply"] or "giả" in data2["reply"].lower()
    assert data2["result"]["verification_status"] == "suspected_counterfeit"

    # 3. EnteroBifina EAN-13 barcode scan (8936151980798)
    headers["Idempotency-Key"] = "test-chat-auth-03"
    resp3 = client.post(
        "/v1/chat",
        json={
            "conversation_id": "conv-test-auth-3",
            "messages": [{"role": "user", "content": "Kiểm tra mã vạch: 8936151980798"}],
            "intent_hint": "authenticity",
            "locale": "vi-VN",
        },
        headers=headers,
    )
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert data3["intent"] == "authenticity"
    assert data3["result"]["verification_status"] == "registry_match"
    assert "EnteroBifina" in data3["result"]["product"]["name"]
    assert "Mediphar" in data3["result"]["product"]["manufacturer"]
    assert any("6520/2019/ĐKSP" in r for r in data3["result"]["reasons"])
