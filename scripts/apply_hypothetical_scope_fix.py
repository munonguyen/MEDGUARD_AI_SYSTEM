from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_exact(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, got {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def patch_clinical_text() -> None:
    path = ROOT / "app/services/clinical_text.py"
    marker = '''_INQUIRY_PREFIX = re.compile(\n    r"\\b(?:doc\\s+ve|tim\\s+hieu\\s+ve|nghe\\s+noi\\s+ve|lo\\s+so\\s+vi\\s+doc\\s+ve)\\s*$",\n    re.IGNORECASE,\n)\n'''
    replacement = marker + '''_YES_NO_QUESTION_TAIL = re.compile(\n    r"^\\s*(?:khong|ko|k)(?:\\s+(?:a|ha|nhi|vay))?\\s*(?:[?.!]|$)",\n    re.IGNORECASE,\n)\n_QUESTION_MODAL = re.compile(\n    r"(?:\\b(?:lieu|khong\\s+biet|muon\\s+biet)\\b|\\bco\\s*$)",\n    re.IGNORECASE,\n)\n\n\ndef _occurrence_is_yes_no_question(text: str, start: int, end: int) -> bool:\n    """Return true when an occurrence is scoped inside a Vietnamese yes/no question.\n\n    The matcher operates on normalized text. It intentionally requires a\n    question-shaped tail such as ``khong?`` plus a nearby question modal, so a\n    factual clause such as ``toi co dau nguc, khong sot`` is not suppressed.\n    """\n    prefix = text[max(0, start - 96):start]\n    suffix = text[end:min(len(text), end + 32)]\n    if _YES_NO_QUESTION_TAIL.match(suffix) is None:\n        return False\n    clause = re.split(r"[.!?;]", prefix)[-1]\n    return _QUESTION_MODAL.search(clause) is not None\n'''
    replace_exact(path, marker, replacement, "yes/no question scope helper")

    old = '''        is_inquiry = _INQUIRY_PREFIX.search(prefix) is not None\n        if not directly_negated and not coordinated_negation and not is_inquiry:\n            return True\n'''
    new = '''        is_inquiry = (\n            _INQUIRY_PREFIX.search(prefix) is not None\n            or _occurrence_is_yes_no_question(text, match.start(), match.end())\n        )\n        if not directly_negated and not coordinated_negation and not is_inquiry:\n            return True\n'''
    replace_exact(path, old, new, "contains_affirmed_phrase inquiry scope")


def patch_tests() -> None:
    path = ROOT / "app/tests/test_response_grounding_p0.py"
    text = path.read_text(encoding="utf-8")
    old_import = '''from app.services.semantic_relation_extractor import extract_semantic_relations\n'''
    new_import = old_import + '''from app.services.clinical_text import contains_affirmed_phrase, normalize_search_text\n'''
    if "contains_affirmed_phrase, normalize_search_text" not in text:
        if text.count(old_import) != 1:
            raise RuntimeError("clinical_text test import anchor missing")
        text = text.replace(old_import, new_import)

    tests = '''\n\ndef test_yes_no_question_does_not_promote_hypothesis_to_fact():\n    text = normalize_search_text("Tôi nên chờ xem có tự hết không?")\n    assert contains_affirmed_phrase(text, "tu het") is False\n\n\ndef test_true_resolved_tia_language_remains_affirmed():\n    text = normalize_search_text("Tôi nói khó và yếu một tay khoảng 10 phút rồi tự hết hoàn toàn.")\n    assert contains_affirmed_phrase(text, "tu het") is True\n\n\ndef test_fact_with_separate_negative_clause_is_not_mistaken_for_question():\n    text = normalize_search_text("Tôi có đau ngực, không sốt.")\n    assert contains_affirmed_phrase(text, "dau nguc") is True\n\n\ndef test_stroke_question_does_not_render_hypothetical_resolution_as_observed_fact():\n    body = _chat(\n        "Người nhà tôi có dấu hiệu méo miệng, nói khó và yếu một bên tay. Tôi nên chờ xem có tự hết không?",\n        "grounding-stroke-question-scope",\n    )\n    result = body.get("result") or {}\n    answer = body.get("answer") or {}\n    text = _answer_text(body)\n    assert result.get("urgency") == "EMERGENCY"\n    assert answer.get("display_questions") == []\n    assert "gọi cấp cứu 115" in text or "gọi 115" in text\n    assert "[nói khó, tự hết]" not in text\n    assert "[noi kho, tu het]" not in normalize_search_text(text)\n'''
    if "test_yes_no_question_does_not_promote_hypothesis_to_fact" not in text:
        text += tests
    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_clinical_text()
    patch_tests()
    print("hypothetical/question scope patch applied")


if __name__ == "__main__":
    main()
