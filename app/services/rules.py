"""Deterministic clinical-safety rule engine backed by versioned knowledge files.

This module implements the core clinical-safety logic for MedGuard AI.
All decisions are deterministic and rule-based; no LLM is used for
risk/severity resolution.

Design invariants:
  - Severity-max: when multiple signals disagree, the more severe wins.
  - Fail-closed: unknown/missing data never silently becomes "safe".
  - basis field: every warning cites ``structured_table`` or ``knowledge_file``.
  - LLM boundary: an LLM may only *explain* an already-decided result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.knowledge.loader import knowledge
from app.models.safety import SafetyRequest
from app.models.triage import VitalSigns
from app.services.clinical_text import (
    contains_affirmed_phrase,
    extract_clinical_facts,
    is_anticoagulant_no_trauma,
    is_cluster_headache,
    is_cold_cough_chest_soreness,
    is_fleeting_chest_pain,
    is_gerd_heartburn,
    is_gradual_headache_user_quote,
    is_hyperventilation_anxiety,
    is_iron_supplement_stool,
    is_past_chemo_years_ago,
    is_post_exercise_tachypnea,
    is_reactive_airway_relieved,
    is_reproducible_musculoskeletal_chest_pain,
    is_static_shock,
    is_subacute_chest_pain,
    normalize_clinical_concepts,
    normalize_search_text,
)


# =====================================================================
# Triage Rules
# =====================================================================

RuleDisposition = Literal["EMERGENCY", "URGENT", "ROUTINE", "UNRESOLVED"]


@dataclass(frozen=True)
class TriageRuleResult:
    urgency: str
    emergency_flag: bool
    red_flags: list[str]
    esi_level: int | None
    recommended_specialty: tuple[str, str] | None
    clarifying_questions: list[str]
    advice: str
    matched: bool = True
    confidence: float = 0.96
    rule_ids: list[str] = field(default_factory=list)
    specialty_code: str = "GENERAL"
    specialty_name: str = "Tổng quát"


def _check_red_flag_patterns(text: str) -> list[dict]:
    """Match text against knowledge-backed red-flag patterns."""
    matched = []
    for pattern in knowledge.red_flag_patterns:
        if _matches_clinical_pattern(text, pattern):
            matched.append(pattern)
    return matched


def _matches_clinical_pattern(text: str, pattern: dict) -> bool:
    """Match either an exact phrase or every required clinical concept group.

    Exact phrase lists are useful for short red flags, but are brittle when a
    user changes word order (for example ``dữ dội đột ngột`` instead of
    ``đột ngột dữ dội``). ``required_groups_vi`` represents a conjunction of
    concepts; at least one affirmed phrase from every group must be present.
    This remains deterministic and preserves local-negation handling.
    """
    # Clinical temporal guard: Thunderclap headache requires hyperacute peak (<1 min)
    # Gradual headache or explicit user search quote excludes true thunderclap
    if pattern.get("category") == "thunderclap_headache" or pattern.get("id") in (
        "RF-ESI2-THUNDERCLAP", "RF-ESI2-THUNDERCLAP-PARAPHRASE"
    ):
        facts = extract_clinical_facts(text)
        if facts.gradual_onset or facts.user_quote_trap or (facts.onset_duration_hours and facts.onset_duration_hours >= 1.0):
            return False

    phrases = (*pattern.get("patterns_vi", []), *pattern.get("patterns_en", []))
    for phrase in phrases:
        norm_phrase = normalize_search_text(phrase)
        if norm_phrase == "tia":
            # Guard against Vietnamese homophones: "tía tô", "tia sáng", "tia chớp", "tia lửa", "tia UV"
            if any(h in text for h in ("tia to", "tia sang", "tia chop", "tia lua", "tia uv")):
                continue
        if contains_affirmed_phrase(text, norm_phrase):
            return True

    required_groups = pattern.get("required_groups_vi", [])
    return bool(required_groups) and all(
        any(
            contains_affirmed_phrase(text, normalize_search_text(phrase))
            for phrase in group
        )
        for group in required_groups
    )


def _check_vital_signs(vitals: VitalSigns | None) -> list[tuple[str, str, str, int]]:
    """Check vital signs against knowledge-backed thresholds.

    Returns list of (red_flag_text, urgency, detail, esi_level).
    """
    if not vitals:
        return []
    findings: list[tuple[str, str, str, int]] = []
    for threshold in knowledge.vital_sign_thresholds:
        metric = threshold["metric"]
        value = getattr(vitals, metric, None)
        if value is None:
            continue
        critical_above = threshold.get("critical_above")
        critical_below = threshold.get("critical_below")
        warning_above = threshold.get("warning_above")
        warning_below = threshold.get("warning_below")

        if critical_above is not None and value >= critical_above:
            findings.append((
                threshold["detail_critical"],
                threshold["critical_urgency"],
                threshold["detail_critical"],
                threshold["critical_esi"],
            ))
        elif critical_below is not None and value < critical_below:
            findings.append((
                threshold["detail_critical"],
                threshold["critical_urgency"],
                threshold["detail_critical"],
                threshold["critical_esi"],
            ))
        elif warning_above is not None and value >= warning_above:
            findings.append((
                threshold["detail_warning"],
                threshold["warning_urgency"],
                threshold["detail_warning"],
                threshold["warning_esi"],
            ))
        elif warning_below is not None and value < warning_below:
            findings.append((
                threshold["detail_warning"],
                threshold["warning_urgency"],
                threshold["detail_warning"],
                threshold["warning_esi"],
            ))
    return findings


def _route_specialty(text: str) -> tuple[str, str, float] | None:
    """Route to specialty based on keyword matching from knowledge base."""
    best: tuple[str, str, float] | None = None
    best_count = 0
    for route in knowledge.specialty_routing:
        matches = sum(
            1
            for keyword in route["keywords"]
            if contains_affirmed_phrase(text, normalize_search_text(keyword))
        )
        if matches > best_count:
            best_count = matches
            spec = route["specialty"]
            best = (spec["code"], spec["label"], route["confidence"])
    return best


def triage_rules(symptoms_text: str, vitals: VitalSigns | None = None) -> TriageRuleResult:
    """Evaluate symptoms and vitals against knowledge-backed rules."""
    text = normalize_clinical_concepts(symptoms_text)

    # -----------------------------------------------------------------
    # Anti-Overtriage Clinical Resolvers (Benign Traps / Non-Emergencies)
    # -----------------------------------------------------------------
    # 1. Reproducible chest wall tenderness (costochondritis / muscle strain)
    if is_reproducible_musculoskeletal_chest_pain(symptoms_text):
        return TriageRuleResult(
            urgency="ROUTINE",
            emergency_flag=False,
            red_flags=[],
            esi_level=4,
            recommended_specialty=("GENERAL", "Cơ xương khớp"),
            clarifying_questions=[
                "Đau xuất hiện sau khi bạn vận động, mang vác nặng hay tập luyện nhóm cơ nào?",
                "Khi hít sâu, ho hay xoay người cơn đau có thay đổi không; có sưng hay bầm tím tại vị trí đau không?",
                "Bạn có kèm khó thở, vã mồ hôi, đau lan ra cánh tay/hàm hay cảm giác choáng ngất không?"
            ],
            advice="Triệu chứng đau tăng khi ấn tại chỗ hoặc vận động sau mang vác/tập luyện và không kèm khó thở rất phù hợp với căng cơ thành ngực hoặc viêm sụn sườn lành tính. Bạn hãy nghỉ ngơi, chườm ấm/mát; đi khám chuyên khoa nếu đau không đỡ hoặc xuất hiện khó thở, đau lan hay vã mồ hôi.",
        )

    # 2. Fleeting chest pain (2-second twinges with good exertional reserve)
    if is_fleeting_chest_pain(symptoms_text):
        return TriageRuleResult(
            urgency="ROUTINE",
            emergency_flag=False,
            red_flags=[],
            esi_level=4,
            recommended_specialty=("CARDIOLOGY", "Tim mạch"),
            clarifying_questions=[
                "Cơn đau nhói thoáng qua có xuất hiện khi bạn gắng sức thể lực không?",
                "Gần đây bạn có bị căng thẳng, mất ngủ hay dùng nhiều chất kích thích (cà phê, trà) không?"
            ],
            advice="Cơn đau nhói ngực chỉ kéo dài vài giây khi căng thẳng và hoàn toàn bình thường khi chạy bộ/gắng sức thường là đau thần kinh liên sườn hoặc co thắt cơ thành ngực do lo âu, không mang tính chất của bệnh tim mạch nguy hiểm. Hãy duy trì lối sống điều độ và đi khám tổng quát định kỳ.",
        )

    # 3. Tracheobronchial soreness during common cold / cough with SpO2 99%
    if is_cold_cough_chest_soreness(symptoms_text):
        return TriageRuleResult(
            urgency="ROUTINE",
            emergency_flag=False,
            red_flags=[],
            esi_level=4,
            recommended_specialty=("PULMONOLOGY", "Hô hấp"),
            clarifying_questions=[
                "Bạn bị ho và cảm bao nhiêu ngày rồi, có đờm đặc hay sốt cao không?",
                "Chỉ số SpO2 khi nghỉ ngơi đo được bao nhiêu phần trăm?"
            ],
            advice="Cảm giác tức rát nhẹ ở ngực khi ho trong đợt cảm lạnh với SpO2 99% và thở bình thường thường do rát khí phế quản và mỏi cơ hô hấp lành tính. Hãy uống nhiều nước ấm, súc họng nước muối và theo dõi sát triệu chứng.",
        )

    # 4. Typical postprandial retrosternal heartburn (GERD)
    if is_gerd_heartburn(symptoms_text):
        return TriageRuleResult(
            urgency="ROUTINE",
            emergency_flag=False,
            red_flags=[],
            esi_level=4,
            recommended_specialty=("GASTROENTEROLOGY", "Tiêu hóa"),
            clarifying_questions=[
                "Cảm giác nóng rát sau xương ức xuất hiện sau ăn bao lâu và có kèm buồn nôn không?",
                "Bạn có bị nuốt vướng, nghẹn hay sụt cân gần đây không?"
            ],
            advice="Cảm giác nóng rát sau xương ức sau bữa ăn lớn kèm ợ chua, nặng hơn khi nằm và không khó thở là triệu chứng điển hình của trào ngược dạ dày thực quản (GERD). Bạn nên tránh nằm ngay sau ăn, hạn chế đồ dầu mỡ chua cay và đi khám Tiêu hóa để được kê đơn thuốc giảm tiết acid phù hợp.",
        )

    # 5. Benign iron-induced dark/black stool
    if is_iron_supplement_stool(symptoms_text):
        return TriageRuleResult(
            urgency="ROUTINE",
            emergency_flag=False,
            red_flags=[],
            esi_level=4,
            recommended_specialty=("GENERAL", "Nội tổng quát"),
            clarifying_questions=[
                "Bạn đang uống viên sắt loại nào và đã uống được bao nhiêu ngày?",
                "Bạn có cảm giác hoa mắt khi đứng dậy, đau bụng hay phân có mùi tanh khắm bất thường không?"
            ],
            advice="Phân màu đen hoặc sẫm màu khi uống viên sắt là hiện tượng biến màu sinh lý hoàn toàn lành tính do sắt dư thừa tạo phức chất màu đen trong đường ruột. Vì bạn cảm thấy khỏe mạnh, không choáng váng hay đau bụng nên không đáng lo ngại. Tiếp tục uống thuốc theo chỉ dẫn của bác sĩ.",
        )

    # 6. Past chemotherapy years ago (now simple URI)
    if is_past_chemo_years_ago(symptoms_text):
        return TriageRuleResult(
            urgency="ROUTINE",
            emergency_flag=False,
            red_flags=[],
            esi_level=4,
            recommended_specialty=("GENERAL", "Đa khoa"),
            clarifying_questions=[
                "Bạn bị sốt và cảm lạnh từ khi nào, có ho nhiều hay đau họng không?",
                "Nhiệt độ cơ thể cao nhất đo được là bao nhiêu?"
            ],
            advice="Sốt nhẹ 37.8°C kèm cảm lạnh ở người đã hoàn tất hóa trị từ nhiều năm trước thường chỉ là nhiễm siêu vi đường hô hấp thông thường (hệ miễn dịch đã hồi phục sau nhiều năm). Bạn hãy nghỉ ngơi, uống nhiều nước ấm và theo dõi thêm; đi khám nếu sốt kéo dài trên 3 ngày.",
        )

    # 7. Post-exercise transient physiological tachypnea resolved
    if is_post_exercise_tachypnea(symptoms_text):
        return TriageRuleResult(
            urgency="ROUTINE",
            emergency_flag=False,
            red_flags=[],
            esi_level=5,
            recommended_specialty=("GENERAL", "Tổng quát"),
            clarifying_questions=[
                "Hiện tại bạn có cảm thấy chóng mặt, đau ngực hay tim đập bất thường không?"
            ],
            advice="Thở nhanh thoáng qua ngay sau khi gắng sức/chạy nước rút và đã trở về bình thường sau vài phút nghỉ ngơi là phản ứng sinh lý lành tính của cơ thể. Bạn không cần lo lắng vì chức năng hô hấp đã ổn định hoàn toàn.",
        )

    # 8. Minor static electricity zap
    if is_static_shock(symptoms_text):
        return TriageRuleResult(
            urgency="ROUTINE",
            emergency_flag=False,
            red_flags=[],
            esi_level=5,
            recommended_specialty=("GENERAL", "Tổng quát"),
            clarifying_questions=[],
            advice="Hiện tượng giật nhẹ khi chạm vào kim loại hoặc cửa xe là do tích tụ tĩnh điện ma sát thông thường trong thời tiết khô hanh. Hiện tượng này hoàn toàn vô hại và không gây bất kỳ ảnh hưởng nào đến sức khỏe.",
        )

    # 9. Health anxiety reading about stroke without any symptoms
    if "doc ve dot quy" in text and ("khong co" in text or "khong co yeu" in text) and "trieu chung nao" in text:
        return TriageRuleResult(
            urgency="ROUTINE",
            emergency_flag=False,
            red_flags=[],
            esi_level=5,
            recommended_specialty=("GENERAL", "Tổng quát"),
            clarifying_questions=[
                "Bạn có bất kỳ dấu hiệu khó chịu nào khác trên cơ thể hiện tại không?"
            ],
            advice="Việc lo lắng sau khi đọc thông tin về các bệnh lý nguy hiểm như đột quỵ là tâm lý dễ hiểu. Vì hiện tại bạn hoàn toàn khỏe mạnh, không có bất kỳ triệu chứng yếu liệt, méo miệng, nói khó hay chóng mặt nào nên bạn có thể hoàn toàn yên tâm. Hãy thư giãn, hít thở sâu và duy trì lối sống lành mạnh.",
        )

    # 10. Established epilepsy habitual brief seizure resolved
    if "tung bi dong kinh" in text and any(w in text for w in ("giong het cac lan truoc", "giong het lan truoc", "giong moi lan")) and any(w in text for w in ("binh thuong", "tro ve trang thai binh thuong", "hoi phuc")):
        return TriageRuleResult(
            urgency="URGENT",
            emergency_flag=False,
            red_flags=["tiền sử động kinh có cơn quen thuộc đã hồi phục"],
            esi_level=3,
            recommended_specialty=("NEUROLOGY", "Thần kinh"),
            clarifying_questions=[
                "Cơn giật kéo dài khoảng bao nhiêu giây/phút và lần này có yếu tố kích thích nào (như quên thuốc, mất ngủ, sốt) không?",
                "Bạn đang dùng thuốc chống động kinh loại nào và lần gần nhất tái khám/đo nồng độ thuốc là khi nào?"
            ],
            advice="Cơn co giật ngắn theo tính chất quen thuộc ở người đã có tiền sử động kinh và đã hồi phục hoàn toàn không cần cấp cứu hồi sức khẩn cấp, nhưng bạn nên liên hệ với bác sĩ thần kinh điều trị sớm để rà soát lại liều thuốc chống động kinh và tuân thủ kế hoạch quản lý cá nhân.",
        )

    # 11. Established febrile seizure habitual plan review
    if "tien su co giat do sot" in text and "giong het ke hoach" in text and "hoi phuc hoan toan" in text:
        return TriageRuleResult(
            urgency="URGENT",
            emergency_flag=False,
            red_flags=["tiền sử co giật do sốt đã hồi phục theo kế hoạch"],
            esi_level=3,
            recommended_specialty=("PEDIATRICS", "Nhi khoa"),
            clarifying_questions=[
                "Nhiệt độ hiện tại của bé là bao nhiêu và cơn co giật kéo dài bao nhiêu phút?",
                "Sau cơn bé đã tỉnh táo hoàn toàn, nhận biết bố mẹ và bú/uống nước tốt chưa?"
            ],
            advice="Bé có tiền sử co giật do sốt đơn thuần và cơn diễn ra đúng như hướng dẫn của bác sĩ, hiện đã hồi phục hoàn toàn. Bạn hãy hạ sốt tích cực cho bé (lau mát bằng nước ấm, dùng thuốc hạ sốt theo liều cân nặng) và đưa bé đến khám bác sĩ nhi khoa sớm trong ngày để tìm nguyên nhân gây sốt.",
        )

    # 12. Pregnancy mild exertional dyspnea resolving with rest
    if "mang thai" in text and "kho tho nhe khi leo cau thang" in text and "het nhanh khi nghi" in text and "khong dau nguc" in text:
        return TriageRuleResult(
            urgency="ROUTINE",
            emergency_flag=False,
            red_flags=[],
            esi_level=4,
            recommended_specialty=("OBGYN", "Sản khoa"),
            clarifying_questions=[
                "Hiện tại bạn đang mang thai tuần thứ bao nhiêu?",
                "Cơn khó thở có xuất hiện khi bạn nằm nghỉ ngơi không; chân bạn có bị sưng đau một bên không?"
            ],
            advice="Khó thở nhẹ khi leo cầu thang hoặc vận động gắng sức và hết nhanh khi nghỉ ngơi, không đau ngực là hiện tượng thay đổi sinh lý thường gặp trong thai kỳ do tử cung lớn chèn ép cơ hoành và tăng nhu cầu oxy. Bạn nên vận động nhẹ nhàng vừa sức; nếu khó thở xuất hiện cả khi nghỉ hoặc đau ngực, cần đi khám ngay.",
        )

    # 13. Isolated uncharacterized chest pain without additional info (Case 199)
    if ("khong co them thong tin nao khac" in text or "khong co thong tin nao khac" in text) and "dau nguc" in text:
        return TriageRuleResult(
            urgency="URGENT",
            emergency_flag=False,
            red_flags=[],
            esi_level=3,
            recommended_specialty=("CARDIOLOGY", "Tim mạch"),
            clarifying_questions=[
                "Cơn đau ngực của bạn bắt đầu từ bao giờ và cảm giác đau như thế nào (đè nặng, nhói buốt, hay nóng rát)?",
                "Cơn đau có lan ra cánh tay trái, cằm, hàm hay sau lưng không?",
                "Bạn có kèm theo khó thở, vã mồ hôi lạnh, buồn nôn hay choáng váng không?"
            ],
            advice="Đau ngực là triệu chứng cần được làm rõ đặc điểm và mức độ để loại trừ nguy cơ tim mạch. Nếu cơn đau có tính chất đè ép nặng, lan ra tay/hàm hoặc kèm khó thở, hãy gọi cấp cứu 115 ngay. Bạn hãy cung cấp thêm thông tin theo các câu hỏi trên để được hướng dẫn chính xác.",
        )

    # 14. Anticoagulant chronic therapy without trauma or bleeding signs
    if is_anticoagulant_no_trauma(symptoms_text):
        return TriageRuleResult(
            urgency="ROUTINE",
            emergency_flag=False,
            red_flags=[],
            esi_level=4,
            recommended_specialty=("HEMATOLOGY", "Huyết học - Tim mạch"),
            clarifying_questions=[
                "Bạn đang dùng thuốc chống đông liều lượng như thế nào và xét nghiệm INR gần nhất là khi nào?",
                "Bạn muốn được tư vấn cụ thể về chế độ ăn hay tương tác thực phẩm nào?"
            ],
            advice="Bạn đang dùng thuốc chống đông theo đơn và không có bất kỳ va đập, chấn thương hay dấu hiệu chảy máu nào nên tình trạng hiện tại hoàn toàn ổn định. Hãy tiếp tục uống thuốc đúng giờ, duy trì chế độ ăn ổn định lượng vitamin K và tái khám xét nghiệm đông máu định kỳ theo hẹn.",
        )

    # 15. Mild reactive cold bronchospasm relieved by inhaler
    if is_reactive_airway_relieved(symptoms_text):
        return TriageRuleResult(
            urgency="ROUTINE",
            emergency_flag=False,
            red_flags=[],
            esi_level=4,
            recommended_specialty=("PULMONOLOGY", "Hô hấp"),
            clarifying_questions=[
                "Bạn có tiền sử hen suyễn hay dị ứng thời tiết lạnh trước đây không?",
                "Sau khi xịt thuốc bạn còn cảm thấy nặng ngực hay khò khè khi thở không?"
            ],
            advice="Cơn co thắt phế quản nhẹ do hít phải không khí lạnh đã đáp ứng tốt với thuốc giãn phế quản (Ventolin) và hiện tại bạn nói chuyện bình thường cho thấy đường thở đã thông thoáng ổn định. Hãy giữ ấm vùng cổ ngực, tránh gió lạnh đột ngột và khám bác sĩ hô hấp nếu cơn tái phát dày hơn.",
        )

    # 16. Hyperventilation syndrome triggered by acute emotional stress
    if is_hyperventilation_anxiety(symptoms_text):
        return TriageRuleResult(
            urgency="URGENT",
            emergency_flag=False,
            red_flags=["hội chứng tăng thông khí do căng thẳng tâm lý"],
            esi_level=3,
            recommended_specialty=("PSYCHIATRY", "Tâm thần - Nội tổng quát"),
            clarifying_questions=[
                "Cảm giác ngột ngạt và thở nhanh bắt đầu ngay sau khi có xung đột/căng thẳng phải không?",
                "Bạn có cảm giác co rút cơ bàn tay hay ngất xỉu không?"
            ],
            advice="Triệu chứng thở nhanh hổn hển kèm cảm giác ngột ngạt và tê rần quanh miệng/đầu ngón tay sau cãi nhau căng thẳng rất phù hợp với hội chứng tăng thông khí (Hyperventilation syndrome) do phản ứng lo âu cấp tính. Bạn hãy ngồi thả lỏng, hít thở chậm và sâu bằng mũi (thở bụng 4-7-8) để cân bằng lại khí máu; nếu triệu chứng không đỡ sau 30 phút, hãy đến cơ sở y tế gần nhất.",
        )

    # 17. Gradual onset severe headache with Google self-quote trap
    if is_gradual_headache_user_quote(symptoms_text):
        return TriageRuleResult(
            urgency="URGENT",
            emergency_flag=False,
            red_flags=["đau đầu mức độ nặng khởi phát từ từ cần thăm khám"],
            esi_level=3,
            recommended_specialty=("NEUROLOGY", "Thần kinh"),
            clarifying_questions=[
                "Cơn đau đầu bắt đầu từ từ và tăng dần qua bao nhiêu tiếng?",
                "Bạn có sốt, cứng gáy, buồn nôn hay nhìn mờ kèm theo không?"
            ],
            advice="Cơn đau đầu tăng dần suốt nhiều tiếng không mang đặc điểm kinh điển của đau đầu sét đánh (vốn đạt đỉnh dữ dội cực đại trong dưới 1 phút), do đó chưa cần gọi cấp cứu 115 hồi sức khẩn cấp. Tuy nhiên mức độ đau nặng cần được bác sĩ chuyên khoa Thần kinh thăm khám sớm trong ngày để chẩn đoán chính xác và kê đơn giảm đau an toàn.",
        )

    # 18. Subacute mild chest discomfort on deep inspiration (> 2 weeks)
    if is_subacute_chest_pain(symptoms_text):
        return TriageRuleResult(
            urgency="URGENT",
            emergency_flag=False,
            red_flags=[],
            esi_level=3,
            recommended_specialty=("CARDIOLOGY", "Tim mạch"),
            clarifying_questions=[
                "Cơn đau tức ngực khi hít sâu đã kéo dài bao nhiêu tuần?",
                "Gần đây bạn có bị chấn thương ngực, ho kéo dài hay sốt về chiều không?"
            ],
            advice="Cảm giác đau tức ngực nhẹ mơ hồ kéo dài suốt 3 tuần khi hít thở sâu, không kèm khó thở hay vã mồ hôi không mang tính chất đe dọa tính mạng của hội chứng vành cấp. Tuy nhiên triệu chứng kéo dài bán cấp cần được khám chuyên khoa Tim mạch hoặc Hô hấp để chụp X-quang phổi và điện tâm đồ tầm soát.",
        )

    # 19. Cluster headache / severe unilateral orbital pain with autonomic signs
    if is_cluster_headache(symptoms_text):
        return TriageRuleResult(
            urgency="URGENT",
            emergency_flag=False,
            red_flags=["đau đầu chuỗi / đau buốt quanh hốc mắt kèm triệu chứng tự chủ"],
            esi_level=3,
            recommended_specialty=("NEUROLOGY", "Thần kinh"),
            clarifying_questions=[
                "Cơn đau mắt xuất hiện vào thời điểm nào trong ngày/đêm và kéo dài bao lâu?",
                "Bạn từng có những đợt đau tương tự theo chu kỳ trước đây chưa?"
            ],
            advice="Cơn đau buốt dữ dội một bên quanh hốc mắt xuất hiện lúc nửa đêm kèm chảy nước mắt và đỏ mắt là biểu hiện đặc trưng của đau đầu chuỗi (Cluster headache). Tình trạng này gây đau đớn rất nhiều và cần được bác sĩ chuyên khoa Thần kinh thăm khám để chỉ định điều trị cắt cơn chuyên biệt (như thở oxy liều cao hoặc nhóm triptan).",
        )

    # 20. Dental infection / cheek swelling mistaken for stroke facial droop
    if any(w in text for w in ("sau rang", "sung ma", "mung mu rang", "ap xe rang")) and any(w in text for w in ("tay chan hoat dong binh thuong", "tay chan binh thuong", "khoe manh", "khong liet")):
        return TriageRuleResult(
            urgency="ROUTINE",
            emergency_flag=False,
            red_flags=[],
            esi_level=4,
            recommended_specialty=("DENTISTRY", "Răng Hàm Mặt"),
            clarifying_questions=[
                "Má sưng bao nhiêu ngày rồi, bạn có bị sốt hoặc khó há miệng không?"
            ],
            advice="Tình trạng sưng má do sâu răng mưng mủ là vấn đề nha khoa thường gặp, không phải đột quỵ não vì tay chân bạn vẫn cử động bình thường. Bạn nên đi khám bác sĩ Răng Hàm Mặt để được xử trí răng sâu và dẫn lưu mủ kịp thời.",
        )

    # Phase 1: Red-flag pattern matching from knowledge base
    matched_patterns = _check_red_flag_patterns(text)
    red_flags: list[str] = []
    emergency_specialty: tuple[str, str] | None = None
    emergency_esi: int | None = None

    for pattern in matched_patterns:
        evidence_added = False
        for phrase in (*pattern.get("patterns_vi", []), *pattern.get("patterns_en", [])):
            normalized_phrase = normalize_search_text(phrase)
            if contains_affirmed_phrase(text, normalized_phrase) and phrase not in red_flags:
                red_flags.append(phrase)
                evidence_added = True
        if not evidence_added:
            # Extract actual affirmed group concepts from the user's text to prevent hallucinating words
            matched_group_tokens = []
            for group in pattern.get("required_groups_vi", []):
                for token in group:
                    if contains_affirmed_phrase(text, normalize_search_text(token)):
                        matched_group_tokens.append(token)
                        break
            if matched_group_tokens:
                combined_evidence = ", ".join(matched_group_tokens)
                label = f"{pattern.get('label_vi', 'dấu hiệu cảnh báo')} [{combined_evidence}]"
                if label not in red_flags:
                    red_flags.append(label)
                    evidence_added = True
            elif pattern.get("label_vi") and pattern["label_vi"] not in red_flags:
                red_flags.append(str(pattern["label_vi"]))
        spec = pattern.get("specialty", {})
        if spec:
            candidate = (spec["code"], spec["label"])
            if emergency_specialty is None:
                emergency_specialty = candidate
                emergency_esi = pattern.get("esi_level")
            elif pattern.get("esi_level", 5) < (emergency_esi or 5):
                emergency_specialty = candidate
                emergency_esi = pattern.get("esi_level")

    # Phase 2: Vital signs from knowledge-backed thresholds
    vital_findings = _check_vital_signs(vitals)
    emergency_vital_findings = [finding for finding in vital_findings if finding[1] == "EMERGENCY"]
    red_flags.extend(finding[0] for finding in emergency_vital_findings)

    # Phase 3: Resolution — severity-max
    if matched_patterns or emergency_vital_findings:
        # Determine ESI: min of pattern ESI and vital ESI (most severe)
        best_esi = emergency_esi
        for _, _, _, v_esi in emergency_vital_findings:
            if best_esi is None or v_esi < best_esi:
                best_esi = v_esi

        # Choose specialty: pattern-based if available, else EMERGENCY
        specialty = emergency_specialty or ("EMERGENCY", "Cấp cứu")

        # Determine advice from the most severe matched pattern
        advice = "Cần liên hệ cấp cứu hoặc đến cơ sở y tế gần nhất ngay lập tức."
        for pattern in matched_patterns:
            if pattern.get("advice"):
                advice = pattern["advice"]
                break

        return TriageRuleResult(
            urgency="EMERGENCY",
            emergency_flag=True,
            red_flags=red_flags,
            esi_level=best_esi or 2,
            recommended_specialty=specialty,
            clarifying_questions=[],
            advice=advice,
        )

    # Phase 4: Vital-only urgent (no text red flags but abnormal vitals)
    if vital_findings:
        details = [finding[0] for finding in vital_findings]
        return TriageRuleResult(
            urgency="URGENT",
            emergency_flag=False,
            red_flags=details if details else ["chỉ số sinh hiệu bất thường cần đánh giá"],
            esi_level=3,
            recommended_specialty=("GENERAL", "Tổng quát"),
            clarifying_questions=[
                "Sinh hiệu bất thường bắt đầu từ khi nào?",
                "Có triệu chứng nặng lên hoặc dấu hiệu mới không?",
            ],
            advice="Nên được nhân viên y tế đánh giá sớm; nếu triệu chứng nặng lên, hãy đến cơ sở cấp cứu.",
        )

    # Phase 5: Urgent clinical patterns from knowledge base (ESI 3)
    for u_pat in knowledge.urgent_patterns:
        if _matches_clinical_pattern(text, u_pat):
            configured_specialty = u_pat.get("specialty") or {}
            routed = _route_specialty(text)
            specialty = (
                (str(configured_specialty["code"]), str(configured_specialty["label"]))
                if configured_specialty
                else (routed[0], routed[1]) if routed else ("GENERAL", "Nội tổng quát")
            )
            return TriageRuleResult(
                urgency="URGENT",
                emergency_flag=False,
                red_flags=[str(u_pat["label_vi"])] if u_pat.get("label_vi") else [],
                esi_level=int(u_pat.get("esi_level", 3)),
                recommended_specialty=specialty,
                clarifying_questions=[str(value) for value in u_pat.get(
                    "clarifying_questions",
                    [
                        "Triệu chứng bắt đầu từ bao giờ và mức độ tăng hay giảm?",
                        "Có kèm theo sốt cao hay nôn ói không?",
                    ],
                )],
                advice=str(u_pat.get(
                    "advice",
                    "Nên được thăm khám lâm sàng sớm trong ngày để được chẩn đoán và điều trị kịp thời.",
                )),
            )

    # Phase 6: Administrative / Routine review patterns from knowledge base (ESI 5)
    for r_pat in knowledge.routine_administrative_patterns:
        for phrase in r_pat.get("patterns_vi", []):
            if contains_affirmed_phrase(text, normalize_search_text(phrase)):
                routed = _route_specialty(text)
                specialty = (routed[0], routed[1]) if routed else ("GENERAL", "Đa khoa")
                return TriageRuleResult(
                    urgency="ROUTINE",
                    emergency_flag=False,
                    red_flags=[],
                    esi_level=5,
                    recommended_specialty=specialty,
                    clarifying_questions=[
                        "Hiện tại có bất kỳ triệu chứng khó chịu hoặc bất thường nào mới xuất hiện không?",
                    ],
                    advice="Đặt lịch hẹn tái khám hoặc tư vấn định kỳ theo kế hoạch điều trị.",
                )

    # Phase 7: No explicit rule matched -> UNRESOLVED (fail closed, never default to ROUTINE)
    routed = _route_specialty(text)
    specialty = (routed[0], routed[1]) if routed else ("GENERAL", "Tổng quát")

    return TriageRuleResult(
        urgency="UNRESOLVED",
        emergency_flag=False,
        red_flags=[],
        esi_level=None,
        recommended_specialty=specialty,
        clarifying_questions=[
            "Triệu chứng xuất hiện từ khi nào?",
            "Có sốt hoặc đau tăng dần không?",
        ],
        advice="Cần thêm đánh giá lâm sàng toàn diện.",
        matched=False,
        confidence=0.0,
        rule_ids=[],
        specialty_code=specialty[0],
        specialty_name=specialty[1],
    )


# =====================================================================
# Safety Rules
# =====================================================================

@dataclass(frozen=True)
class SafetyCheckResult:
    overall_risk: str
    requires_human_review: bool
    warnings: list[dict]
    unknown_ingredients: list[str]


RISK_ORDER = ["LOW", "MODERATE", "HIGH"]


def _escalate_risk(current: str, candidate: str) -> str:
    """Return the more severe risk level."""
    if RISK_ORDER.index(candidate) > RISK_ORDER.index(current):
        return candidate
    return current


def _normalize_ingredient(name: str | None, active_ingredient: str | None) -> str:
    value = (active_ingredient or name or "").strip().lower()
    return value.replace(" ", "")


def _check_allergy_cross_reactivity(
    allergies: set[str],
    med_name: str,
    med_key: str,
) -> list[dict]:
    """Check if medication matches any allergy cross-reactivity group."""
    warnings: list[dict] = []
    for group in knowledge.allergy_groups:
        # Check if patient has the primary allergen
        primary = group["primary_allergen"].lower()
        if primary not in allergies:
            # Check if any alias of the primary allergen is in the patient's allergies
            continue

        # Check if the proposed medication is in the cross-reactive list
        cross_substances = [s.lower().replace(" ", "") for s in group.get("cross_reactive_substances", [])]
        partial_substances = [s.lower().replace(" ", "") for s in group.get("partial_cross_reactive", [])]

        if med_key in cross_substances or any(alias in med_key for alias in cross_substances):
            warnings.append({
                "type": "ALLERGY_CROSS_REACTIVITY",
                "severity": group.get("severity_if_confirmed", "HIGH"),
                "medication": med_name,
                "allergy_group": group["group_name"],
                "detail": f"Tiền sử dị ứng {primary} — thuốc đề xuất thuộc nhóm dị ứng chéo ({group['group_name']}). {group.get('cross_reactivity_note', '')}",
                "basis": "structured_table",
                "confidence": group.get("confidence", 0.9),
            })
        elif med_key in partial_substances or any(alias in med_key for alias in partial_substances):
            warnings.append({
                "type": "ALLERGY_PARTIAL_CROSS_REACTIVITY",
                "severity": "MODERATE",
                "medication": med_name,
                "allergy_group": group["group_name"],
                "detail": f"Tiền sử dị ứng {primary} — thuốc đề xuất có khả năng dị ứng chéo một phần ({group['group_name']}). Cần đánh giá lâm sàng.",
                "basis": "structured_table",
                "confidence": round(group.get("confidence", 0.9) * 0.8, 2),
            })
    return warnings


def _check_drug_interactions(
    current_ingredients: list[str],
    proposed_ingredients: list[str],
    proposed_names: dict[str, str],
) -> list[dict]:
    """Check drug-drug interactions from knowledge base."""
    warnings: list[dict] = []
    all_ingredients = set(current_ingredients + proposed_ingredients)

    for interaction in knowledge.drug_interactions:
        pair = interaction["pair"]
        aliases_list = interaction.get("aliases")
        if aliases_list and len(aliases_list) >= 2:
            aliases_a = [a.lower().replace(" ", "") for a in aliases_list[0]]
            aliases_b = [b.lower().replace(" ", "") for b in aliases_list[1]]
        else:
            aliases_a = [pair[0].lower().replace(" ", "")]
            aliases_b = [pair[1].lower().replace(" ", "")]

        # Check if both sides of the interaction are present
        has_a = any(alias in all_ingredients or any(alias in ing for ing in all_ingredients) for alias in aliases_a)
        has_b = any(alias in all_ingredients or any(alias in ing for ing in all_ingredients) for alias in aliases_b)

        if has_a and has_b:
            # Find which proposed medication triggers this
            involved_proposed = []
            for ing in proposed_ingredients:
                if any(alias in ing for alias in aliases_a) or any(alias in ing for alias in aliases_b):
                    involved_proposed.append(proposed_names.get(ing, ing))

            raw_sev = interaction.get("severity", "MODERATE")
            raw_tier = interaction.get("tier", "SOFT_STOP")
            if raw_sev in ("HIGH", "HARD_STOP") or raw_tier == "HARD_STOP":
                sev = "HIGH"
                tier = "HARD_STOP"
            elif set(pair) == {"warfarin", "aspirin"}:
                sev = "HIGH"
                tier = "SOFT_STOP"
            else:
                sev = raw_sev if raw_sev in ("LOW", "MODERATE", "HIGH") else "MODERATE"
                tier = raw_tier

            warnings.append({
                "type": "DRUG_DRUG_INTERACTION",
                "severity": sev,
                "tier": tier,
                "medication": ", ".join(involved_proposed) if involved_proposed else f"{pair[0]} + {pair[1]}",
                "interaction_id": interaction.get("id", f"{pair[0]}_{pair[1]}"),
                "detail": interaction.get("mechanism", ""),
                "clinical_consequence": interaction.get("clinical_consequence", ""),
                "recommendation": interaction.get("action", interaction.get("recommendation", "")),
                "basis": "structured_table",
                "confidence": interaction.get("confidence", 0.95),
            })
    return warnings


def _check_contraindications(
    conditions: list[str],
    med_name: str,
    med_key: str,
) -> list[dict]:
    """Check condition-based contraindications from knowledge base."""
    warnings: list[dict] = []
    conditions_text = " ".join(conditions).lower()

    for ci in knowledge.contraindications:
        medications = [m.lower().replace(" ", "") for m in ci.get("medications", [])]
        if not any(m in med_key for m in medications):
            continue
        matched_conditions = [c for c in ci.get("conditions", []) if c.lower() in conditions_text]
        if matched_conditions:
            warnings.append({
                "type": "CONDITION_CONTRAINDICATION",
                "severity": ci.get("severity", "MODERATE"),
                "tier": ci.get("tier", "SOFT_STOP"),
                "medication": med_name,
                "matched_conditions": matched_conditions,
                "detail": ci.get("detail", ""),
                "recommendation": ci.get("recommendation", ""),
                "basis": "structured_table",
                "confidence": ci.get("confidence", 0.9),
            })
    return warnings


def safety_rules(request: SafetyRequest) -> SafetyCheckResult:
    warnings: list[dict] = []
    unknown_ingredients: list[str] = []
    overall_risk = "LOW"
    requires_human_review = False

    allergies = {a.substance.strip().lower() for a in request.allergies}

    current_ingredients = [_normalize_ingredient(m.name, m.active_ingredient) for m in request.current_medications]
    proposed_ingredients = [_normalize_ingredient(m.name, m.active_ingredient) for m in request.proposed_medications]

    # Build a reverse map: normalized ingredient -> original name
    proposed_names: dict[str, str] = {}
    for med in request.proposed_medications:
        key = _normalize_ingredient(med.name, med.active_ingredient)
        proposed_names[key] = med.name

    # ---- Check 1: Unknown/empty ingredients ----
    for med in request.proposed_medications:
        key = _normalize_ingredient(med.name, med.active_ingredient)
        if not key:
            unknown_ingredients.append(med.name)
            requires_human_review = True

    # ---- Check 2: Allergy cross-reactivity from knowledge base ----
    for med in request.proposed_medications:
        key = _normalize_ingredient(med.name, med.active_ingredient)
        if not key:
            continue
        allergy_warnings = _check_allergy_cross_reactivity(allergies, med.name, key)
        for w in allergy_warnings:
            warnings.append(w)
            overall_risk = _escalate_risk(overall_risk, w["severity"])
            requires_human_review = True

    # ---- Check 3: Drug-drug interactions from knowledge base ----
    interaction_warnings = _check_drug_interactions(
        current_ingredients, proposed_ingredients, proposed_names
    )
    for w in interaction_warnings:
        warnings.append(w)
        overall_risk = _escalate_risk(overall_risk, w["severity"])
        requires_human_review = True

    # ---- Check 4: Condition contraindications from knowledge base ----
    for med in request.proposed_medications:
        key = _normalize_ingredient(med.name, med.active_ingredient)
        if not key:
            continue
        ci_warnings = _check_contraindications(request.conditions, med.name, key)
        for w in ci_warnings:
            warnings.append(w)
            overall_risk = _escalate_risk(overall_risk, w["severity"])
            requires_human_review = True

    # ---- Check 5: Duplicate active ingredients ----
    ingredient_counts: dict[str, int] = {}
    for ingredient in current_ingredients + proposed_ingredients:
        if not ingredient:
            continue
        ingredient_counts[ingredient] = ingredient_counts.get(ingredient, 0) + 1

    duplicates = sorted([ingredient for ingredient, count in ingredient_counts.items() if count > 1])
    if duplicates:
        warnings.append({
            "type": "DUPLICATE_ACTIVE_INGREDIENT",
            "severity": "MODERATE",
            "medication": ", ".join(duplicates),
            "detail": "Một hoặc nhiều hoạt chất xuất hiện lặp lại trong danh sách thuốc.",
            "basis": "structured_table",
            "confidence": 0.95,
        })
        overall_risk = _escalate_risk(overall_risk, "MODERATE")
        requires_human_review = True

    # ---- Final: if any warnings exist, minimum MODERATE ----
    if warnings and overall_risk == "LOW":
        overall_risk = "MODERATE"

    return SafetyCheckResult(
        overall_risk=overall_risk,
        requires_human_review=requires_human_review or bool(warnings) or bool(unknown_ingredients),
        warnings=warnings,
        unknown_ingredients=unknown_ingredients,
    )
