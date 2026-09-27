from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one replacement target, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def append_once(path: str, marker: str, block: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if marker in text:
        return
    target.write_text(text.rstrip() + "\n\n\n" + block.strip() + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# 1) Episode relation must be computed from previous -> latest turn everywhere.
# ---------------------------------------------------------------------------
replace_once(
    "app/services/chat.py",
    "from app.services.clinical_text import contains_affirmed_phrase, normalize_clinical_concepts, normalize_search_text\n",
    "from app.services.clinical_text import contains_affirmed_phrase, normalize_clinical_concepts, normalize_search_text\n"
    "from app.services.episode_context import select_active_episode_text\n",
)

old_episode = '''def _triage_episode_text(payload: ChatRequest, latest_text: str) -> tuple[str, bool]:
    """Carry clinical context across follow-up turns in an active episode."""
    normalized_latest = _normalize(latest_text)
    if should_start_new_episode(latest_text) or is_explicit_correction(latest_text) or any(marker in normalized_latest for marker in _NEW_CLINICAL_EPISODE_MARKERS):
        return latest_text, False

    user_messages = [
        message.content.strip()
        for message in payload.messages[:-1]
        if message.role == "user" and message.content.strip()
    ]
    if not user_messages:
        return latest_text, False

    # Retain the immediate previous clinical statements as active episode context
    relevant_history = user_messages[-3:]
    episode_text = "\\n".join([
        *relevant_history,
        f"Lượt hiện tại: {latest_text}",
    ])

    return episode_text, True
'''

new_episode = '''def _previous_user_text(payload: ChatRequest) -> str | None:
    for message in reversed(payload.messages[:-1]):
        if message.role == "user" and message.content.strip():
            return message.content.strip()
    return None


def _episode_switch_detected(payload: ChatRequest, latest_text: str) -> bool:
    """Return True only when the current complaint clearly replaces the prior one.

    The previous implementation called ``should_start_new_episode`` with only the
    latest turn, which meant natural domain switches (for example chest pain ->
    abdominal pain) were invisible to several history/risk paths.
    """
    normalized_latest = _normalize(latest_text)
    previous_text = _previous_user_text(payload)
    return (
        should_start_new_episode(latest_text, previous_text)
        or any(marker in normalized_latest for marker in _NEW_CLINICAL_EPISODE_MARKERS)
    )


def _should_isolate_latest_clinical_turn(payload: ChatRequest, latest_text: str) -> bool:
    return _episode_switch_detected(payload, latest_text) or is_explicit_correction(latest_text)


def _triage_episode_text(payload: ChatRequest, latest_text: str) -> tuple[str, bool, bool]:
    """Return the active clinical episode and whether history was retained."""
    switched_episode = _episode_switch_detected(payload, latest_text)
    if switched_episode or is_explicit_correction(latest_text):
        return latest_text, False, switched_episode

    user_messages = [
        message.content.strip()
        for message in payload.messages[:-1]
        if message.role == "user" and message.content.strip()
    ]
    if not user_messages:
        return latest_text, False, False

    # Keep a bounded candidate window, then run the same adjacent-turn episode
    # selector used at the TriageRequest boundary. This prevents one component
    # from seeing stale history that another component already discarded.
    candidate = "\\n".join([
        *user_messages[-3:],
        f"Lượt hiện tại: {latest_text}",
    ])
    selection = select_active_episode_text(candidate)
    return selection.text, selection.used_history, selection.switched_episode
'''
replace_once("app/services/chat.py", old_episode, new_episode)

replace_once(
    "app/services/chat.py",
    '    if len(payload.messages) > 1 and not should_start_new_episode(normalized_text):\n',
    '    if len(payload.messages) > 1 and not _should_isolate_latest_clinical_turn(payload, payload.messages[-1].content):\n',
)

replace_once(
    "app/services/chat.py",
    '        episode_text, episode_context_used = _triage_episode_text(payload, latest_text)\n',
    '        episode_text, episode_context_used, episode_switched = _triage_episode_text(payload, latest_text)\n',
)

old_risk = '''        # Multi-turn risk escalation tracking via Clinical Event Ledger
        conversation_risk = "EMERGENCY" if (len(payload.messages) > 1 and ledger.has_active_emergency()) else None
        if not conversation_risk and len(payload.messages) > 1 and not should_start_new_episode(latest_text):
            if is_explicit_correction(latest_text):
                conversation_risk = None
            else:
                risk_state = None
                from app.services.compositional_reasoner import evaluate_compositional_risk
                from app.services.dose_reasoning import evaluate_dose_reasoning

                for prev_m in payload.messages[:-1]:
                    if prev_m.role == "user" and prev_m.content.strip():
                        prev_text = prev_m.content.strip()
                        prev_dose = evaluate_dose_reasoning(prev_text)
                        if prev_dose and prev_dose.urgency == "EMERGENCY":
                            conversation_risk = "EMERGENCY"
                            break
                        prev_comp = evaluate_compositional_risk(prev_text)
                        if prev_comp.disposition == "EMERGENCY":
                            conversation_risk = "EMERGENCY"
                            break
'''
new_risk = '''        # Multi-turn risk memory is scoped to the selected active episode only.
        # Never rescan the whole conversation after an episode switch: doing so
        # reintroduced an old emergency floor even after the ledger invalidated it.
        conversation_risk = "EMERGENCY" if (episode_context_used and ledger.has_active_emergency()) else None
        if (
            not conversation_risk
            and episode_context_used
            and not episode_switched
            and not is_explicit_correction(latest_text)
        ):
            from app.services.compositional_reasoner import evaluate_compositional_risk
            from app.services.dose_reasoning import evaluate_dose_reasoning

            active_dose = evaluate_dose_reasoning(episode_text)
            active_comp = evaluate_compositional_risk(episode_text)
            if (
                (active_dose and active_dose.urgency == "EMERGENCY")
                or active_comp.disposition == "EMERGENCY"
            ):
                conversation_risk = "EMERGENCY"
'''
replace_once("app/services/chat.py", old_risk, new_risk)

replace_once(
    "app/services/chat.py",
    '                "episode_context_used": episode_context_used,\n',
    '                "episode_context_used": episode_context_used,\n                "episode_switched": episode_switched,\n',
)

# Do not feed stale last_result into clinical answer agents. last_result remains
# available to deterministic FHIR/delivery routes, which explicitly require it.
replace_once(
    "app/services/chat.py",
    '''    internal_agent_trace = answer.agent_trace
''',
    '''    agent_patient_context = payload.context.model_dump(mode="json")
    if intent in {"triage", "safety"}:
        agent_patient_context["last_result"] = None

    internal_agent_trace = answer.agent_trace
''',
)
replace_once(
    "app/services/chat.py",
    '            patient_context=payload.context.model_dump(mode="json"),\n',
    '            patient_context=agent_patient_context,\n',
)
replace_once(
    "app/services/chat.py",
    '            patient_context=payload.context.model_dump(mode="json"),\n',
    '            patient_context=agent_patient_context,\n',
)

# ---------------------------------------------------------------------------
# 2) Episode-domain routing and symptom-guidance routing must respect negation.
# ---------------------------------------------------------------------------
replace_once(
    "app/services/risk_memory.py",
    "from app.services.clinical_text import normalize_search_text\n",
    "from app.services.clinical_text import contains_affirmed_phrase, normalize_search_text\n",
)
replace_once(
    "app/services/risk_memory.py",
    '''        for marker in markers:
            pos = norm.find(marker)
            if pos >= 0:
                matches.append((pos, domain))
                break
''',
    '''        for marker in markers:
            pos = norm.find(marker)
            if pos >= 0 and contains_affirmed_phrase(norm, marker):
                matches.append((pos, domain))
                break
''',
)

replace_once(
    "app/knowledge/loader.py",
    "import json\n",
    "import json\nimport re\n",
)
replace_once(
    "app/knowledge/loader.py",
    "from typing import Any\n",
    "from typing import Any\n\nfrom app.services.clinical_text import contains_affirmed_phrase, normalize_search_text\n",
)
old_guidance = '''    def find_symptom_guidance(self, symptoms_text: str) -> dict[str, Any] | None:
        normalized = symptoms_text.lower().strip()
        for guidance in self.symptom_guidance:
            if guidance.get("topic") == "lower_limb_pain":
                has_lower_limb_region = any(
                    term in normalized
                    for term in (
                        "chân",
                        "đùi",
                        "bắp chân",
                        "đầu gối",
                        "cổ chân",
                        "mắt cá",
                        "bàn chân",
                    )
                )
                has_relevant_problem = any(
                    term in normalized
                    for term in ("đau", "nhức", "sưng", "khó đi", "không đi", "chịu lực")
                )
                if has_lower_limb_region and has_relevant_problem:
                    return guidance
            if any(str(keyword).lower() in normalized for keyword in guidance.get("keywords", [])):
                return guidance
        return None
'''
new_guidance = '''    def find_symptom_guidance(self, symptoms_text: str) -> dict[str, Any] | None:
        normalized = normalize_search_text(symptoms_text)
        for guidance in self.symptom_guidance:
            if guidance.get("topic") == "lower_limb_pain":
                # A body-region token and an unrelated pain token must never be
                # combined into a finding. Example: "đau thắt lưng, không tê
                # chân" previously became lower-limb pain because both "đau"
                # and "chân" occurred somewhere in the string.
                direct_problem_phrases = (
                    "dau chan", "nhuc chan", "sung chan", "te chan", "yeu chan",
                    "dau dui", "nhuc dui", "dau bap chan", "sung bap chan",
                    "dau dau goi", "sung dau goi", "dau co chan", "sung co chan",
                    "dau mat ca", "dau ban chan", "kho di", "khong di duoc",
                    "khong chiu luc duoc",
                )
                has_affirmed_problem = any(
                    contains_affirmed_phrase(normalized, phrase)
                    for phrase in direct_problem_phrases
                )
                if not has_affirmed_problem:
                    proximity = re.compile(
                        r"\\b(?:dau|nhuc|sung|te|yeu)\\b(?:\\s+[a-z0-9]+){0,4}\\s+"
                        r"(?:bap chan|dau goi|co chan|mat ca|ban chan|chan|dui)\\b"
                    )
                    has_affirmed_problem = any(
                        contains_affirmed_phrase(normalized, match.group(0))
                        for match in proximity.finditer(normalized)
                    )
                if has_affirmed_problem:
                    return guidance

            if any(
                contains_affirmed_phrase(normalized, normalize_search_text(str(keyword)))
                for keyword in guidance.get("keywords", [])
            ):
                return guidance
        return None
'''
replace_once("app/knowledge/loader.py", old_guidance, new_guidance)

# ---------------------------------------------------------------------------
# 3) Patient-facing follow-ups consume known GI slots and specialty follows the
#    same guidance selected for a routine complaint.
# ---------------------------------------------------------------------------
replace_once(
    "app/services/triage.py",
    '''    extract_clinical_facts,
    filter_known_clarifying_questions,
)''',
    '''    extract_clinical_facts,
    filter_known_clarifying_questions,
    normalize_search_text,
)''',
)

old_gi_tail = '''    if topic not in {"abdominal_pain", "upper_abdominal_discomfort"}:
        return summary, questions
    if not contains_affirmed_phrase(symptoms_text, "buồn nôn"):
        return summary, questions

    if summary:
        summary += (
            " Bạn cũng đã mô tả cảm giác buồn nôn; cần làm rõ liệu đã nôn, "
            "có uống được nước hay không và có dấu hiệu cảnh báo đi kèm không."
        )
    follow_up = (
        "Bạn đã mô tả buồn nôn; bạn đã nôn chưa, có uống được nước không, "
        "và có sốt, đầy hơi, ợ chua, tiêu chảy, táo bón, chướng hoặc cứng bụng không?"
    )
    questions = [question for question in questions if "buồn nôn" not in question]
    # Narrative rendering intentionally limits follow-up prompts to three.
    # Put the user's newly reported symptom inside that visible priority set.
    questions.insert(min(2, len(questions)), follow_up)
    return summary, questions
'''
new_gi_tail = '''    if topic not in {"abdominal_pain", "upper_abdominal_discomfort"}:
        return summary, questions

    norm = normalize_search_text(symptoms_text)
    has_nausea = contains_affirmed_phrase(norm, "buon non")
    location_label = None
    for label, markers in (
        ("vùng trên rốn", ("tren ron", "thuong vi", "dau da day")),
        ("quanh rốn", ("quanh ron",)),
        ("vùng bụng dưới", ("duoi bung", "bung duoi")),
        ("bên phải bụng", ("ben phai bung", "bung ben phai")),
        ("bên trái bụng", ("ben trai bung", "bung ben trai")),
    ):
        if any(contains_affirmed_phrase(norm, marker) for marker in markers):
            location_label = label
            break

    meal_relation = None
    if any(marker in norm for marker in ("tang khi doi", "khi doi", "luc doi", "doi bung")):
        meal_relation = "tăng khi đói"
    elif any(marker in norm for marker in ("sau khi an", "sau an", "an no", "sau bua an")):
        meal_relation = "liên quan sau ăn"

    has_burning = contains_affirmed_phrase(norm, "nong rat")
    has_reflux = contains_affirmed_phrase(norm, "o chua")
    has_high_information_detail = bool(location_label or meal_relation or has_burning or has_reflux)

    if not has_high_information_detail:
        if not has_nausea:
            return summary, questions
        if summary:
            summary += (
                " Bạn cũng đã mô tả cảm giác buồn nôn; cần làm rõ liệu đã nôn, "
                "có uống được nước hay không và có dấu hiệu cảnh báo đi kèm không."
            )
        follow_up = (
            "Bạn đã mô tả buồn nôn; bạn đã nôn chưa, có uống được nước không, "
            "và có sốt, đầy hơi, ợ chua, tiêu chảy, táo bón, chướng hoặc cứng bụng không?"
        )
        questions = [question for question in questions if "buồn nôn" not in question]
        questions.insert(min(2, len(questions)), follow_up)
        return summary, questions

    details: list[str] = []
    if location_label:
        details.append(f"khó chịu/đau ở {location_label}")
    if meal_relation:
        details.append(meal_relation)
    if has_nausea:
        details.append("kèm buồn nôn")
    if has_burning and has_reflux:
        details.append("kèm nóng rát và ợ chua")
    elif has_burning:
        details.append("kèm nóng rát")
    elif has_reflux:
        details.append("kèm ợ chua")

    summary = (
        "Thông tin hiện đã rõ hơn: " + ", ".join(details) + ". "
        "Những dữ kiện này giúp thu hẹp đánh giá nhưng chưa đủ để xác định nguyên nhân cụ thể."
    )

    refined_questions: list[str] = []
    severity_known = bool(re.search(r"\\b(?:10|[0-9])\\s*/\\s*10\\b", norm))
    if not severity_known:
        refined_questions.append("Mức đau hiện tại từ 0 đến 10 là bao nhiêu và có đang tăng nhanh không?")
    onset_known = bool(re.search(r"\\b(?:tu sang|tu trua|tu toi|hom nay|hom qua|\\d+\\s*(?:gio|ngay|tuan)|bat dau)\\b", norm))
    if not onset_known:
        refined_questions.append("Triệu chứng bắt đầu từ khi nào và diễn tiến liên tục hay từng cơn?")
    if not meal_relation:
        refined_questions.append("Cảm giác thay đổi thế nào khi đói, trong bữa ăn hoặc sau khi ăn?")
    vomiting_known = any(
        marker in norm
        for marker in ("da non", "bi non", "non oi", "non ra", "khong non", "chua non")
    )
    if has_nausea and not vomiting_known:
        refined_questions.append("Bạn đã nôn chưa và hiện có uống giữ được nước không?")
    if not (has_burning or has_reflux):
        refined_questions.append("Bạn có kèm nóng rát, ợ chua hoặc cảm giác trào lên cổ họng không?")

    # Preserve one explicit safety check while keeping the conversational surface
    # short. The full safety-net remains in result.safety_net.
    refined_questions.append(
        "Có đau tăng dữ dội, bụng cứng/chướng nhiều, ngất, nôn ra máu hoặc đi ngoài phân đen không?"
    )
    return summary, list(dict.fromkeys(refined_questions))[:3]
'''
replace_once("app/services/triage.py", old_gi_tail, new_gi_tail)

old_specialty = '''    specialty = None
    if rule.recommended_specialty:
        specialty = RecommendedSpecialty(
            code=rule.recommended_specialty[0],
            label=rule.recommended_specialty[1],
            confidence=1.0 if emergency_flag else 0.78,
        )
'''
new_specialty = '''    specialty = None
    guidance_specialty = None
    if use_guidance and guidance and final_urgency == "ROUTINE":
        guidance_specialty = {
            "back_pain": ("MUSCULOSKELETAL", "Cơ xương khớp"),
            "neck_shoulder_pain": ("MUSCULOSKELETAL", "Cơ xương khớp"),
            "muscle_strain_overexertion": ("MUSCULOSKELETAL", "Cơ xương khớp"),
            "lower_limb_pain": ("MUSCULOSKELETAL", "Cơ xương khớp"),
            "ankle_sprain": ("ORTHOPEDICS", "Chấn thương Chỉnh hình"),
            "abdominal_pain": ("GASTROENTEROLOGY", "Tiêu hóa"),
            "upper_abdominal_discomfort": ("GASTROENTEROLOGY", "Tiêu hóa"),
            "headache": ("NEUROLOGY", "Thần kinh"),
        }.get(str(guidance.get("topic", "")))
    if guidance_specialty:
        specialty = RecommendedSpecialty(
            code=guidance_specialty[0],
            label=guidance_specialty[1],
            confidence=0.86,
        )
    elif rule.recommended_specialty:
        specialty = RecommendedSpecialty(
            code=rule.recommended_specialty[0],
            label=rule.recommended_specialty[1],
            confidence=1.0 if emergency_flag else 0.78,
        )
'''
replace_once("app/services/triage.py", old_specialty, new_specialty)

replace_once(
    "app/services/triage.py",
    '                "resolution_source": resolved.source,\n                "confidence": resolved.confidence,\n',
    '                "resolution_source": resolved.source,\n                "resolution_reasons": list(resolved.reasons),\n                "confidence": resolved.confidence,\n',
)

# ---------------------------------------------------------------------------
# 4) Keep gateway/knowledge governance metadata out of patient chat by default.
# ---------------------------------------------------------------------------
replace_once(
    "frontend/src/chat/GroundedAnswer.jsx",
    '''  const structuredUrgency = result?.urgency || result?.escalation_level;
''',
    '''  const structuredUrgency = result?.urgency || result?.escalation_level;
  const showTechnicalMeta = responseMeta.showTechnicalMeta === true;
''',
)
replace_once(
    "frontend/src/chat/GroundedAnswer.jsx",
    '''      <div className="answer-assurance-row" aria-label="Trạng thái kiểm chứng câu trả lời">
        <span className={`verification-pill ${responseMeta.verification_status || 'not_requested'}`}>
          {responseMeta.verification_status === 'verified'
            ? <CheckCircle2 size={13} />
            : <CircleHelp size={13} />}
          {verificationLabels[responseMeta.verification_status] || verificationLabels.not_requested}
        </span>
        {responseMeta.knowledge_approval && (
          <span className={`knowledge-pill ${responseMeta.knowledge_approval}`}>
            {knowledgeLabels[responseMeta.knowledge_approval]}
          </span>
        )}
      </div>
''',
    '''      {showTechnicalMeta && (
        <div className="answer-assurance-row" aria-label="Trạng thái kiểm chứng câu trả lời">
          <span className={`verification-pill ${responseMeta.verification_status || 'not_requested'}`}>
            {responseMeta.verification_status === 'verified'
              ? <CheckCircle2 size={13} />
              : <CircleHelp size={13} />}
            {verificationLabels[responseMeta.verification_status] || verificationLabels.not_requested}
          </span>
          {responseMeta.knowledge_approval && (
            <span className={`knowledge-pill ${responseMeta.knowledge_approval}`}>
              {knowledgeLabels[responseMeta.knowledge_approval]}
            </span>
          )}
        </div>
      )}
''',
)

# ---------------------------------------------------------------------------
# 5) Regression coverage for every reproduced failure.
# ---------------------------------------------------------------------------
append_once(
    "app/tests/test_clinical_episode_orchestration.py",
    "test_negated_leg_findings_do_not_select_lower_limb_guidance",
    r'''

def test_negated_leg_findings_do_not_select_lower_limb_guidance():
    from app.knowledge.loader import knowledge

    guidance = knowledge.find_symptom_guidance(
        "Tôi chỉ đau ở vùng thắt lưng, không có đau lan hay tê chân."
    )

    assert guidance is not None
    assert guidance["topic"] == "back_pain"


def test_episode_domain_ignores_negated_chest_symptom():
    from app.services.risk_memory import infer_episode_domain

    assert infer_episode_domain("Không đau ngực, tôi chỉ đau bụng vùng trên rốn") == "gastrointestinal"


def test_chat_emergency_chest_episode_does_not_lock_new_abdominal_episode():
    response = client.post(
        "/v1/chat",
        headers=_headers("episode-emergency-to-gi-1"),
        json={
            "conversation_id": "conversation-emergency-to-gi",
            "intent_hint": "auto",
            "messages": [
                {"role": "user", "content": "Tôi bị đau ngực và khó thở"},
                {"role": "assistant", "content": "Bạn cần được đánh giá cấp cứu ngay."},
                {"role": "user", "content": "Tôi đang cảm thấy bụng cứ cồn cào, sốt ruột không rõ lắm."},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "triage"
    assert body["result"]["urgency"] == "ROUTINE"
    assert body["result"]["recommended_specialty"]["code"] == "GASTROENTEROLOGY"
    assert body["extracted"]["episode_switched"] is True
    answer_text = " ".join(block["text"] for block in body["answer"].get("narrative", []))
    assert "đau ngực" not in answer_text.lower()
    assert "khó thở" not in body["answer"]["summary"].lower()


def test_negated_leg_followup_stays_back_pain_and_routes_musculoskeletal():
    response = client.post(
        "/v1/chat",
        headers=_headers("episode-back-negation-1"),
        json={
            "conversation_id": "conversation-back-negation",
            "intent_hint": "triage",
            "messages": [
                {"role": "user", "content": "Tôi hơi đau lưng sau khi ngồi máy tính cả ngày"},
                {"role": "assistant", "content": "Bạn có đau lan xuống chân không?"},
                {"role": "user", "content": "Tôi chỉ đau ở vùng thắt lưng, không có đau lan hay tê chân."},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["trace"]["details"]["symptom_guidance"] == "back_pain"
    assert body["result"]["recommended_specialty"]["code"] == "MUSCULOSKELETAL"
    assert not body["answer"]["summary"].startswith("Đau chân cần được đánh giá")


def test_gi_followups_consume_location_meal_relation_and_reflux_details():
    response = client.post(
        "/v1/chat",
        headers=_headers("episode-gi-state-delta-1"),
        json={
            "conversation_id": "conversation-gi-state-delta",
            "intent_hint": "triage",
            "messages": [
                {"role": "user", "content": "tôi đang rất đau bụng và buồn nôn"},
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
    questions = " ".join(body["answer"]["questions"]).lower()
    assert "trên rốn" in summary
    assert "tăng khi đói" in summary
    assert "ợ chua" in summary
    assert "đau ở vùng trên hay dưới bụng" not in questions
    assert "thay đổi thế nào khi đói" not in questions
    assert body["result"]["trace"]["details"]["resolution_reasons"]
''',
)

# Keep the existing UI smoke test as the end-to-end oracle, but explicitly
# assert that internal gateway/approval labels are not rendered to patients.
replace_once(
    "frontend/tests/ui-smoke.mjs",
    '''  await abdominalAnswer.getByText(/Khi nói “sốt ruột”/).waitFor();
''',
    '''  await abdominalAnswer.getByText(/Khi nói “sốt ruột”/).waitFor();
  if (await abdominalAnswer.getByText(/Gateway|Nguồn chưa ghi nhận phê duyệt|Nguồn đang chờ chuyên gia duyệt/).count()) {
    throw new Error('Internal gateway/knowledge governance metadata must not render in patient chat');
  }
''',
)

print("Clinical episode/follow-up patch staged successfully")
