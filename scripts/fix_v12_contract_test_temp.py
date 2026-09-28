from pathlib import Path

path = Path(__file__).resolve().parents[1] / "scripts/apply_agent_first_v12_temp.py"
text = path.read_text(encoding="utf-8")
old = '''    assert "BN-SECRET" not in encoded\n    assert "old" not in encoded\n    assert "Thông tin hiện tại chưa cho thấy rõ dấu hiệu cấp cứu" not in encoded\n'''
new = '''    assert "BN-SECRET" not in encoded\n    assert "patient_ref" not in contract.envelope["patient_context"]\n    assert "last_result" not in contract.envelope["patient_context"]\n    assert "Thông tin hiện tại chưa cho thấy rõ dấu hiệu cấp cứu" not in encoded\n'''
if old not in text:
    raise SystemExit("V12 contract test assertion block not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("v12_contract_test=FIXED")
