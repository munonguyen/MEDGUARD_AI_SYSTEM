from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_exact(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, got {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    answering = ROOT / "app/services/answering.py"
    replace_exact(
        answering,
        '                "phân luồng. Bạn cần được nhân viên cấp cứu đánh giá ngay; hệ thống không "\n                "thể xác định nguyên nhân hoặc chẩn đoán chỉ từ tin nhắn này."\n',
        '                "phân luồng. Bạn cần được nhân viên cấp cứu đánh giá ngay; hệ thống không "\n                "xác định nguyên nhân hoặc chẩn đoán chỉ từ tin nhắn này; đồng thời không thể "\n                "khẳng định chẩn đoán từ xa."\n',
        "emergency wording compatibility",
    )

    tests = ROOT / "app/tests/test_response_grounding_p0.py"
    replace_exact(
        tests,
        '    assert "không thể xác định" in ((body.get("answer") or {}).get("summary") or "").lower()\n',
        '    summary = ((body.get("answer") or {}).get("summary") or "").lower()\n    assert "không xác định nguyên nhân hoặc chẩn đoán" in summary\n    assert "không thể khẳng định" in summary\n',
        "uncertainty regression compatibility",
    )
    print("response-grounding compatibility patch applied")


if __name__ == "__main__":
    main()
