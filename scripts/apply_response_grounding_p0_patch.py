from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_exact(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, got {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def patch_semantic_lattice() -> None:
    path = ROOT / "app/services/semantic_abstraction_lattice.py"
    replace_exact(
        path,
        '    has_stress_headache = bool(re.search(r"\\b(cang thang cong viec|thieu ngu|ngoi may tinh|am i hai ben)\\b", norm))\n',
        '''    # Context such as sleep deprivation or computer work is not a symptom.\n    # Only create a benign tension-headache abstraction when a headache/head-location\n    # symptom is actually present in the user's text.\n    has_headache_symptom = bool(re.search(\n        r"\\b(dau dau|nhuc dau|nang dau|dau thai duong|thai duong.*?dau|dau.*?thai duong)\\b",\n        norm,\n    ))\n    has_stress_headache = has_headache_symptom and bool(\n        re.search(r"\\b(cang thang cong viec|thieu ngu|ngoi may tinh|am i hai ben)\\b", norm)\n    )\n''',
        "tension-headache semantic gate",
    )

    replace_exact(
        path,
        '''    elif has_obstetric and (has_syncope or has_diaphoresis or bool(re.search(r"\\b(choang vang|chong mat|ngat|xuat huyet|chay mau)\\b", norm))):\n        patterns.append(\n            AbstractionPattern(\n                archetype=AbstractThreatArchetype.PREGNANCY_EMERGENCY,\n                is_emergency=True,\n                confidence=0.99,\n                grounding_concepts=["obstetric_acute_abdomen", "hemodynamic_compromise"],\n                clinical_rationale="Nghi ngờ thai ngoài tử cung vỡ hoặc cấp cứu bụng sản phụ khoa (đau bụng cấp kèm trễ kinh và choáng váng).",\n            )\n        )\n''',
        '''    elif has_obstetric and (has_syncope or has_diaphoresis or bool(re.search(r"\\b(choang vang|chong mat|ngat|xuat huyet|chay mau)\\b", norm))):\n        # Patient-facing rationale must only assert features present in the input.\n        # Differential diagnoses may be named as possibilities, but rule antecedents\n        # that were not observed must never be rewritten as patient facts.\n        obstetric_evidence: list[str] = []\n        if re.search(r"\\b(mang thai|co bau|san phu)\\b", norm):\n            obstetric_evidence.append("đang mang thai")\n        elif re.search(r"\\b(tre kinh|cham kinh)\\b", norm):\n            obstetric_evidence.append("trễ/chậm kinh")\n        if re.search(r"\\b(dau bung|dau ho chau)\\b", norm):\n            obstetric_evidence.append("đau bụng/đau hố chậu")\n        if re.search(r"\\b(xuat huyet|chay mau)\\b", norm):\n            obstetric_evidence.append("chảy máu")\n        if has_syncope or re.search(r"\\b(choang vang|chong mat|ngat)\\b", norm):\n            obstetric_evidence.append("choáng/ngất")\n        if has_diaphoresis:\n            obstetric_evidence.append("vã mồ hôi/dấu hiệu tuần hoàn")\n        evidence_text = ", ".join(dict.fromkeys(obstetric_evidence)) or "dấu hiệu sản khoa cấp"\n        patterns.append(\n            AbstractionPattern(\n                archetype=AbstractThreatArchetype.PREGNANCY_EMERGENCY,\n                is_emergency=True,\n                confidence=0.99,\n                grounding_concepts=["obstetric_acute_abdomen", "hemodynamic_compromise"],\n                clinical_rationale=(\n                    f"Nhóm dấu hiệu sản khoa cấp ({evidence_text}) cần được đánh giá khẩn để "\n                    "loại trừ nguyên nhân nguy hiểm như thai ngoài tử cung hoặc chảy máu sản khoa."\n                ),\n            )\n        )\n''',
        "pregnancy rationale grounding",
    )


def patch_answering() -> None:
    path = ROOT / "app/services/answering.py"
    replace_exact(
        path,
        '                "phân luồng. Bạn cần được nhân viên cấp cứu đánh giá ngay; hệ thống không "\n                "xác định nguyên nhân hoặc chẩn đoán chỉ từ tin nhắn này."\n',
        '                "phân luồng. Bạn cần được nhân viên cấp cứu đánh giá ngay; hệ thống không "\n                "thể xác định nguyên nhân hoặc chẩn đoán chỉ từ tin nhắn này."\n',
        "explicit emergency diagnostic uncertainty",
    )


def write_regressions() -> None:
    path = ROOT / "app/tests/test_response_grounding_p0.py"
    path.write_text(
        '''from __future__ import annotations\n\nfrom unittest.mock import patch\n\nfrom fastapi.testclient import TestClient\n\nfrom app.main import app\nfrom app.services.semantic_abstraction_lattice import (\n    AbstractThreatArchetype,\n    evaluate_abstraction_lattice,\n)\nfrom app.services.semantic_relation_extractor import extract_semantic_relations\n\n\ndef _archetypes(text: str):\n    graph = extract_semantic_relations(text)\n    return evaluate_abstraction_lattice(graph).active_archetypes\n\n\ndef _chat(prompt: str, key: str):\n    client = TestClient(app)\n    with patch("app.services.chat.background_agent_runner.submit", return_value=False), patch(\n        "app.services.chat.active_learning_store.capture_case", return_value=None\n    ):\n        response = client.post(\n            "/v1/chat",\n            headers={\n                "X-API-Key": "demo-key",\n                "X-Tenant-Id": "tenant-demo",\n                "X-Consent-Token": "consent-grounding-regression",\n                "Idempotency-Key": key,\n            },\n            json={\n                "conversation_id": key,\n                "messages": [{"role": "user", "content": prompt}],\n            },\n        )\n    assert response.status_code == 200\n    return response.json()\n\n\ndef _answer_text(body: dict) -> str:\n    answer = body.get("answer") or {}\n    values: list[str] = []\n    for key in (\n        "summary", "clinical_hypotheses", "key_points", "next_steps",\n        "safety_notes", "questions", "limitations",\n    ):\n        value = answer.get(key)\n        if isinstance(value, list):\n            values.extend(str(item) for item in value)\n        elif value:\n            values.append(str(value))\n    return " ".join(values).lower()\n\n\ndef test_sleep_deprivation_cannot_invent_tension_headache_for_chest_pain():\n    patterns = _archetypes(\n        "Tôi bị đau ngực nhưng tôi nghĩ chỉ do thiếu ngủ. Tôi cứ ở nhà theo dõi được không?"\n    )\n    assert all(\n        p.archetype != AbstractThreatArchetype.BENIGN_TENSION_HEADACHE\n        for p in patterns\n    )\n\n\ndef test_actual_tension_headache_remains_supported():\n    patterns = _archetypes(\n        "Tôi đau đầu âm ỉ hai bên thái dương sau mấy hôm thiếu ngủ và ngồi máy tính nhiều."\n    )\n    assert any(\n        p.archetype == AbstractThreatArchetype.BENIGN_TENSION_HEADACHE\n        for p in patterns\n    )\n\n\ndef test_pregnancy_emergency_rationale_only_states_observed_features():\n    patterns = _archetypes(\n        "Tôi đang mang thai và bị đau bụng kèm chảy máu. Tôi nên làm gì?"\n    )\n    pregnancy = next(\n        p for p in patterns\n        if p.archetype == AbstractThreatArchetype.PREGNANCY_EMERGENCY\n    )\n    rationale = pregnancy.clinical_rationale.lower()\n    assert "đang mang thai" in rationale\n    assert "đau bụng" in rationale\n    assert "chảy máu" in rationale\n    assert "trễ kinh" not in rationale\n    assert "choáng" not in rationale\n\n\ndef test_chat_chest_pain_sleep_deprivation_never_turns_into_headache():\n    body = _chat(\n        "Tôi bị đau ngực nhưng tôi nghĩ chỉ do thiếu ngủ. Tôi cứ ở nhà theo dõi được không?",\n        "grounding-chest-sleep",\n    )\n    specialty = ((body.get("result") or {}).get("recommended_specialty") or {}).get("code")\n    assert "đau đầu" not in _answer_text(body)\n    assert specialty != "NEUROLOGY"\n\n\ndef test_pregnancy_chat_does_not_assert_unreported_dizziness_or_missed_period():\n    body = _chat(\n        "Tôi đang mang thai và bị đau bụng kèm chảy máu. Tôi nên làm gì?",\n        "grounding-pregnancy",\n    )\n    text = _answer_text(body)\n    assert "trễ kinh" not in text\n    assert "choáng váng" not in text\n\n\ndef test_emergency_summary_uses_explicit_diagnostic_uncertainty():\n    body = _chat(\n        "Người nhà tôi có dấu hiệu méo miệng, nói khó và yếu một bên tay.",\n        "grounding-stroke-uncertainty",\n    )\n    assert (body.get("result") or {}).get("urgency") == "EMERGENCY"\n    assert "không thể xác định" in ((body.get("answer") or {}).get("summary") or "").lower()\n''',
        encoding="utf-8",
    )


def main() -> None:
    patch_semantic_lattice()
    patch_answering()
    write_regressions()
    print("response-grounding P0 patch applied")


if __name__ == "__main__":
    main()
