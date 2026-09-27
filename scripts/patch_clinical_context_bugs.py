from pathlib import Path
import re


def sub_once(path: str, pattern: str, replacement: str) -> None:
    p = Path(path)
    text = p.read_text()
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"regex target count {count} in {path}: {pattern[:100]!r}")
    p.write_text(updated)


sub_once(
    "app/services/chat.py",
    r'def _triage_episode_text\(payload: ChatRequest, latest_text: str\) -> tuple\[str, bool\]:.*?\n\n\ndef _requests_personalized_dose',
    '''def _triage_episode_text(payload: ChatRequest, latest_text: str) -> tuple[str, bool]:
    """Return only the active clinical episode, bounded to recent user turns.

    Natural chief-complaint changes are episode boundaries even without an
    explicit "vấn đề mới" marker. Short elliptical follow-ups remain attached
    to the active episode, while unrelated historical symptoms are excluded.
    """
    normalized_latest = _normalize(latest_text)
    user_messages = [
        message.content.strip()
        for message in payload.messages[:-1]
        if message.role == "user" and message.content.strip()
    ]
    previous_text = user_messages[-1] if user_messages else None
    if (
        should_start_new_episode(latest_text, previous_text)
        or is_explicit_correction(latest_text)
        or any(marker in normalized_latest for marker in _NEW_CLINICAL_EPISODE_MARKERS)
    ):
        return latest_text, False
    if not user_messages:
        return latest_text, False

    relevant_history: list[str] = []
    cursor_text = latest_text
    for previous in reversed(user_messages):
        if should_start_new_episode(cursor_text, previous):
            break
        relevant_history.append(previous)
        cursor_text = previous
        if len(relevant_history) >= 4:
            break
    relevant_history.reverse()
    if not relevant_history:
        return latest_text, False
    return "\\n".join([*relevant_history, f"Lượt hiện tại: {latest_text}"]), True


def _requests_personalized_dose'''
)

sub_once(
    "app/services/chat.py",
    r'    has_monitoring_metrics = bool\(_extract_monitoring\(latest_text\)\)\n    latest_concept_norm = normalize_clinical_concepts\(normalize_search_text\(latest_text\)\)\n    has_active_emergency = ledger\.has_active_emergency\(\) or bool\(_check_red_flag_patterns\(latest_concept_norm\)\)\n    if has_active_emergency.*?        if not conversation_risk and len\(payload\.messages\) > 1 and not should_start_new_episode\(latest_text\):',
    '''    has_monitoring_metrics = bool(_extract_monitoring(latest_text))
    latest_concept_norm = normalize_clinical_concepts(normalize_search_text(latest_text))
    previous_user_turns = [
        message.content.strip()
        for message in payload.messages[:-1]
        if message.role == "user" and message.content.strip()
    ]
    previous_user_text = previous_user_turns[-1] if previous_user_turns else None
    latest_starts_new_episode = bool(
        previous_user_text and should_start_new_episode(latest_text, previous_user_text)
    ) or is_explicit_correction(latest_text) or any(
        marker in normalized for marker in _NEW_CLINICAL_EPISODE_MARKERS
    )
    current_turn_emergency = bool(_check_red_flag_patterns(latest_concept_norm))
    has_active_emergency = current_turn_emergency or (
        not latest_starts_new_episode and ledger.has_active_emergency()
    )
    if has_active_emergency and not has_monitoring_metrics and (len(payload.messages) > 1 or intent in ("monitoring", "general", "pharmacy")):
        intent = "triage"

    if intent == "triage":
        episode_text, episode_context_used = _triage_episode_text(payload, latest_text)
        vital_signs = _extract_vital_signs(episode_text)

        conversation_risk = "EMERGENCY" if (
            len(payload.messages) > 1 and episode_context_used and ledger.has_active_emergency()
        ) else None
        if not conversation_risk and len(payload.messages) > 1 and episode_context_used:'''
)

loader = Path("app/knowledge/loader.py")
loader_text = loader.read_text()
if "from app.services.clinical_text import contains_affirmed_phrase, normalize_search_text" not in loader_text:
    loader_text = loader_text.replace(
        "from typing import Any\n",
        "from typing import Any\n\nfrom app.services.clinical_text import contains_affirmed_phrase, normalize_search_text\n",
        1,
    )
pattern = r'    def find_symptom_guidance\(self, symptoms_text: str\) -> dict\[str, Any\] \| None:.*?\n\n    @property\n    def contraindications'
replacement = '''    def find_symptom_guidance(self, symptoms_text: str) -> dict[str, Any] | None:
        normalized = normalize_search_text(symptoms_text)
        for guidance in self.symptom_guidance:
            if guidance.get("topic") == "lower_limb_pain":
                coupled_problem_phrases = (
                    "dau chan", "nhuc chan", "sung chan",
                    "dau dui", "nhuc dui", "sung dui",
                    "dau bap chan", "nhuc bap chan", "sung bap chan",
                    "dau dau goi", "sung dau goi",
                    "dau co chan", "sung co chan",
                    "dau mat ca", "sung mat ca",
                    "dau ban chan", "sung ban chan",
                )
                has_coupled_problem = any(
                    contains_affirmed_phrase(normalized, phrase)
                    for phrase in coupled_problem_phrases
                )
                has_functional_problem = any(
                    contains_affirmed_phrase(normalized, phrase)
                    for phrase in ("kho di", "khong di duoc", "khong chiu luc duoc", "khong chiu luc")
                )
                has_affirmed_region = any(
                    contains_affirmed_phrase(normalized, phrase)
                    for phrase in ("chan", "dui", "bap chan", "dau goi", "co chan", "mat ca", "ban chan")
                )
                if has_coupled_problem or (has_functional_problem and has_affirmed_region):
                    return guidance
                continue
            if any(
                contains_affirmed_phrase(normalized, normalize_search_text(str(keyword)))
                for keyword in guidance.get("keywords", [])
            ):
                return guidance
        return None

    @property
    def contraindications'''
loader_text, count = re.subn(pattern, replacement, loader_text, count=1, flags=re.S)
if count != 1:
    raise SystemExit(f"loader guidance regex count={count}")
loader.write_text(loader_text)

sub_once(
    "app/services/triage.py",
    r'    specialty = None\n    if rule\.recommended_specialty:.*?\n\n    advice = rule\.advice',
    '''    specialty = None
    if rule.recommended_specialty:
        specialty = RecommendedSpecialty(
            code=rule.recommended_specialty[0],
            label=rule.recommended_specialty[1],
            confidence=1.0 if emergency_flag else 0.78,
        )
    if use_guidance and guidance and final_urgency == "ROUTINE":
        guidance_specialties = {
            "back_pain": ("MUSCULOSKELETAL", "Cơ xương khớp"),
            "neck_shoulder_pain": ("MUSCULOSKELETAL", "Cơ xương khớp"),
        }
        override = guidance_specialties.get(str(guidance.get("topic", "")))
        if override:
            specialty = RecommendedSpecialty(
                code=override[0], label=override[1], confidence=0.86
            )

    advice = rule.advice'''
)

sub_once(
    "app/services/triage.py",
    r'    if topic not in \{"abdominal_pain", "upper_abdominal_discomfort"\}:\n        return summary, questions\n    if not contains_affirmed_phrase\(symptoms_text, "buồn nôn"\):.*?    return summary, questions\n\n\nfrom app\.services\.semantic_risk',
    '''    if topic not in {"abdominal_pain", "upper_abdominal_discomfort"}:
        return summary, questions

    norm = normalize_search_text(symptoms_text)
    has_nausea = contains_affirmed_phrase(norm, "buon non")
    gi_facts: list[str] = []
    if contains_affirmed_phrase(norm, "tren ron"):
        gi_facts.append("đau tập trung vùng trên rốn")
    if contains_affirmed_phrase(norm, "tang len khi doi") or contains_affirmed_phrase(norm, "tang khi doi"):
        gi_facts.append("đau tăng khi đói")
    if contains_affirmed_phrase(norm, "nong rat"):
        gi_facts.append("có cảm giác nóng rát")
    if contains_affirmed_phrase(norm, "o chua"):
        gi_facts.append("có ợ chua")

    if gi_facts:
        summary = (
            "Đã ghi nhận " + ", ".join(gi_facts) + ". "
            "Các dữ kiện này giúp thu hẹp hướng đánh giá tiêu hóa nhưng chưa đủ để xác định nguyên nhân chỉ từ tin nhắn."
        )
    elif has_nausea and summary:
        summary += (
            " Bạn cũng đã mô tả cảm giác buồn nôn; cần làm rõ liệu đã nôn, "
            "có uống được nước hay không và có dấu hiệu cảnh báo đi kèm không."
        )

    if contains_affirmed_phrase(norm, "tren ron"):
        questions = [q for q in questions if not any(x in q.lower() for x in ("vùng trên hay dưới", "quanh rốn", "vị trí"))]
    if contains_affirmed_phrase(norm, "tang len khi doi") or contains_affirmed_phrase(norm, "tang khi doi"):
        questions = [q for q in questions if not any(x in q.lower() for x in ("sau khi ăn", "trước hoặc sau khi ăn", "liên quan bữa ăn"))]
    if contains_affirmed_phrase(norm, "nong rat") or contains_affirmed_phrase(norm, "o chua"):
        questions = [q for q in questions if "ợ chua" not in q.lower() and "nóng rát" not in q.lower()]

    if has_nausea:
        follow_up = (
            "Bạn đã mô tả buồn nôn; bạn đã nôn chưa, có uống được nước không, "
            "và có sốt, đầy hơi, tiêu chảy, táo bón, chướng hoặc cứng bụng không?"
        )
        questions = [question for question in questions if "buồn nôn" not in question]
        questions.insert(min(2, len(questions)), follow_up)
    return summary, questions


from app.services.semantic_risk'''
)

tests = Path("app/tests/test_clinical_episode_orchestration.py")
text = tests.read_text()
if "test_negated_leg_findings_do_not_route_to_lower_limb_guidance" not in text:
    text += '''


def test_negated_leg_findings_do_not_route_to_lower_limb_guidance():
    from app.knowledge.loader import knowledge
    guidance = knowledge.find_symptom_guidance(
        "Tôi chỉ đau ở vùng thắt lưng, không có đau lan hay tê chân."
    )
    assert guidance is not None
    assert guidance.get("topic") == "back_pain"


def test_routine_postural_back_pain_uses_musculoskeletal_specialty():
    response = client.post(
        "/v1/chat",
        headers=_headers("episode-back-specialty-1"),
        json={
            "conversation_id": "conversation-back-specialty",
            "intent_hint": "triage",
            "messages": [{"role": "user", "content": "Tôi hơi đau lưng sau khi ngồi máy tính cả ngày"}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["urgency"] == "ROUTINE"
    assert body["result"]["recommended_specialty"]["code"] == "MUSCULOSKELETAL"
    assert body["result"]["recommended_specialty"]["label"] == "Cơ xương khớp"


def test_emergency_chest_episode_does_not_leak_into_new_abdominal_episode():
    response = client.post(
        "/v1/chat",
        headers=_headers("episode-emergency-to-abdominal-1"),
        json={
            "conversation_id": "conversation-emergency-to-abdominal",
            "intent_hint": "triage",
            "messages": [
                {"role": "user", "content": "Tôi đau ngực dữ dội, khó thở và vã mồ hôi."},
                {"role": "assistant", "content": "Bạn cần được đánh giá cấp cứu ngay."},
                {"role": "user", "content": "Tôi đang cảm thấy bụng cứ cồn cào, sốt ruột không rõ lắm."},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "triage"
    assert body["result"]["urgency"] != "EMERGENCY"
    assert body["result"]["recommended_specialty"]["code"] == "GASTROENTEROLOGY"
    assert body["extracted"]["episode_context_used"] is False
    assert "đau ngực" not in body["answer"]["summary"].lower()


def test_emergency_chest_continuation_preserves_emergency_floor():
    response = client.post(
        "/v1/chat",
        headers=_headers("episode-emergency-continuation-1"),
        json={
            "conversation_id": "conversation-emergency-continuation",
            "intent_hint": "triage",
            "messages": [
                {"role": "user", "content": "Tôi đau ngực dữ dội và khó thở."},
                {"role": "assistant", "content": "Bạn cần được đánh giá cấp cứu ngay."},
                {"role": "user", "content": "Tôi vẫn đau ngực và giờ còn vã mồ hôi."},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["urgency"] == "EMERGENCY"
    assert body["extracted"]["episode_context_used"] is True


def test_gi_followup_summary_uses_accumulated_episode_facts_without_reasking_known_slots():
    response = client.post(
        "/v1/chat",
        headers=_headers("episode-gi-delta-1"),
        json={
            "conversation_id": "conversation-gi-delta",
            "intent_hint": "triage",
            "messages": [
                {"role": "user", "content": "Tôi đang rất đau bụng và buồn nôn"},
                {"role": "assistant", "content": "Bạn đau ở vị trí nào?"},
                {"role": "user", "content": "Cơn đau của tôi tập trung ở vùng trên rốn."},
                {"role": "assistant", "content": "Đau có liên quan bữa ăn không?"},
                {"role": "user", "content": "Cơn đau thường xuất hiện hoặc tăng lên khi đói"},
                {"role": "assistant", "content": "Có nóng rát hay ợ chua không?"},
                {"role": "user", "content": "Cơn đau có kèm theo nóng rát và ợ chua"},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    summary = body["answer"]["summary"].lower()
    assert "trên rốn" in summary
    assert "tăng khi đói" in summary
    assert "ợ chua" in summary
    questions = " ".join(body["answer"]["questions"]).lower()
    assert "vùng trên hay dưới" not in questions
    assert "trước hoặc sau khi ăn" not in questions
'''
    tests.write_text(text)
