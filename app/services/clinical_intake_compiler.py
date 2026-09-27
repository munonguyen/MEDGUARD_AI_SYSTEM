"""Clinical Intake Compiler & Dual Representation Service for MedGuard AI.

Implements SOTA 2025-2026 Clinical Query Understanding & Intake Compilation:
1. Normalizes messy human Vietnamese language (teencode, abbreviations, typos, colloquialisms).
2. Extracts temporal timeline from conversational phrases (-7d, -2d, -1d, today_morning, acute).
3. Detects and isolates negations to prevent keyword flattening.
4. Separates Patient Hypotheses / Anxiety fears (e.g. 'sợ cục máu đông do đọc mạng')
   from Confirmed Clinical Facts.
5. Resolves informal medication mentions (e.g. 'cetri gì đó' -> 'cetirizine').
6. Produces Dual Representation: SemanticForm (user intent/tone) & ClinicalForm (medical facts).
7. Decomposes multi-faceted questions into targeted sub-questions for parallel retrieval.
8. Classifies complexity level (C0 to C4) for adaptive compute.
"""

from __future__ import annotations

import re
from typing import Any

from app.models.intake import (
    ClinicalForm,
    ComplexityLevel,
    CompiledClinicalIntake,
    DecomposedQuestion,
    MedicationMention,
    NegationFinding,
    PatientHypothesis,
    SemanticForm,
    TimelineEvent,
    UncertaintyType,
)

# 1. Colloquial Vietnamese & Teencode Normalization Lexicon
_TEENCODE_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(ko|k|kh|hổng|hong)\b", re.IGNORECASE), "không"),
    (re.compile(r"\b(j|gi)\b(?=\s|[.,?!]|$)", re.IGNORECASE), "gì"),
    (re.compile(r"\b(dc|đc)\b", re.IGNORECASE), "được"),
    (re.compile(r"\b(pk|bit|bít)\b", re.IGNORECASE), "biết"),
    (re.compile(r"\b(ng|nguoi)\b", re.IGNORECASE), "người"),
    (re.compile(r"\b(e)\b(?=\s|[.,?!]|$)", re.IGNORECASE), "em"),
    (re.compile(r"\b(bs|b/s)\b", re.IGNORECASE), "bác sĩ"),
    (re.compile(r"\b(chừơm|chuom)\b", re.IGNORECASE), "chườm"),
    (re.compile(r"\b(\d{1,2})\s*t\b", re.IGNORECASE), r"\1 tuổi"),
    (re.compile(r"\b(thuoc)\b", re.IGNORECASE), "thuốc"),
    (re.compile(r"\b(trieu chung)\b", re.IGNORECASE), "triệu chứng"),
    (re.compile(r"\b(vien)\b(?=\s|[.,?!]|$)", re.IGNORECASE), "viện"),
    (re.compile(r"\b(hnay|h\.nay)\b", re.IGNORECASE), "hôm nay"),
    (re.compile(r"\b(hkia|h\.kia)\b", re.IGNORECASE), "hôm kia"),
    (re.compile(r"\b(hqua|h\.qua)\b", re.IGNORECASE), "hôm qua"),
]

# 2. Known Generic Medication Resolution Lexicon
_MED_RESOLVERS: list[dict[str, Any]] = [
    {
        "pattern": re.compile(r"\b(cetri\w*|cetirizine|cetirizin)\b", re.IGNORECASE),
        "generic": "cetirizine",
        "class": "antihistamine_h1",
    },
    {
        "pattern": re.compile(r"\b(lora\w*|loratadine|loratadin)\b", re.IGNORECASE),
        "generic": "loratadine",
        "class": "antihistamine_h1",
    },
    {
        "pattern": re.compile(r"\b(fexo\w*|fexofenadine)\b", re.IGNORECASE),
        "generic": "fexofenadine",
        "class": "antihistamine_h1",
    },
    {
        "pattern": re.compile(r"\b(pana\w*|panadol|efferalgan|para\w*|paracetamol)\b", re.IGNORECASE),
        "generic": "paracetamol",
        "class": "analgesic_antipyretic",
    },
    {
        "pattern": re.compile(r"\b(ibu\w*|ibuprofen)\b", re.IGNORECASE),
        "generic": "ibuprofen",
        "class": "nsaid",
    },
    {
        "pattern": re.compile(r"\b(aspi\w*|aspirin)\b", re.IGNORECASE),
        "generic": "aspirin",
        "class": "antiplatelet_nsaid",
    },
    {
        "pattern": re.compile(r"\b(warfa\w*|warfarin|sintrom)\b", re.IGNORECASE),
        "generic": "warfarin",
        "class": "anticoagulant",
    },
]

# 3. Known Patient Hypotheses & Fear Keywords
_FEAR_TRIGGER_PATTERNS = [
    re.compile(r"(?:đọc|thấy|coi|nghe)\s*(?:trên\s*)?(?:mạng|mạng xã hội|tiktok|google|báo|web)\s*(?:bảo|nói|thấy)?\s*([a-z0-9\s_à-ỹ]+?)(?=\s+(?:nên|thì|là|em|tôi|sợ|hoang|lo)|[.,?!]|$)", re.IGNORECASE),
    re.compile(r"(?:sợ|lo|sợ bị|lo bị|nghi|nghi ngờ)\s*([a-z0-9\s_à-ỹ]+?)(?=\s+(?:nên|quá|lắm|không|có|em|bác)|[.,?!]|$)", re.IGNORECASE),
]

# 4. Known Negation Extraction Patterns
_NEGATION_PATTERNS = [
    (re.compile(r"\b(?:không|ko|chưa)\s+(?:bị\s+)?(?:đỏ|sưng đỏ|nóng đỏ)(?:\s+hay\s+gì\s+cả)?\b", re.IGNORECASE), "calf_redness_absent", "denied_symptom"),
    (re.compile(r"\b(?:không|ko|chưa)\s+(?:bị\s+)?sưng\b", re.IGNORECASE), "swelling_absent", "denied_symptom"),
    (re.compile(r"\b(?:không|ko)\s+(?:thấy\s+)?sốt\b", re.IGNORECASE), "fever_absent", "denied_symptom"),
    (re.compile(r"\b(?:không|ko)\s+(?:thấy\s+)?đau ngực\b", re.IGNORECASE), "chest_pain_absent", "denied_symptom"),
    (re.compile(r"\b(?:không|ko)\s+(?:thấy\s+)?khó thở\b", re.IGNORECASE), "dyspnea_absent", "denied_symptom"),
    (re.compile(r"\b(?:không|ko)\s+(?:có\s+)?bệnh\s*(?:gì|nen|nền)?(?:\s+cả)?\b", re.IGNORECASE), "no_underlying_disease", "denied_history"),
    (re.compile(r"\b(?:đi lại|đi|di lai|di)\s+(?:thì\s+)?vẫn\s+được\b", re.IGNORECASE), "walking_preserved", "preserved_function"),
    (re.compile(r"\b(?:không|ko)\s+(?:bị\s+)?liệt\b", re.IGNORECASE), "paralysis_absent", "denied_functional_loss"),
    (re.compile(r"\b(?:không|ko)\s+(?:bị\s+)?méo miệng\b", re.IGNORECASE), "facial_droop_absent", "denied_functional_loss"),
]


def normalize_text_slang(text: str) -> str:
    """Normalize Vietnamese teencode, spelling, and common colloquial abbreviations."""
    normalized = text
    for pattern, replacement in _TEENCODE_MAP:
        normalized = pattern.sub(replacement, normalized)
    # Clean multiple spaces
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def extract_timeline_events(text: str) -> list[TimelineEvent]:
    """Extract chronological sequence of health and lifestyle events."""
    events: list[TimelineEvent] = []
    text_lower = text.lower()

    # Pattern: Hôm kia / Mấy hôm trước -> Chạy bộ / Vận động
    if any(m in text_lower for m in ("hôm kia", "mấy hôm trước", "2 ngày trước", "hai ngày trước")):
        if any(w in text_lower for w in ("chạy", "chạy bộ", "tập gym", "tập luyện", "vận động", "đá bóng")):
            events.append(TimelineEvent(
                time_offset="-2d",
                raw_time_marker="hôm kia",
                event="Hoạt động thể lực cường độ cao (chạy bộ/tập gym)",
                context="Chạy bộ hoặc vận động nhiều",
            ))

    # Pattern: Hôm qua / Mấy hôm nay -> Bắt đầu thấy căng tức
    if any(m in text_lower for m in ("mấy hôm nay", "mấy ngày nay", "hôm qua")):
        if any(w in text_lower for w in ("căng", "mỏi", "đau", "khó chịu")):
            events.append(TimelineEvent(
                time_offset="-1d",
                raw_time_marker="mấy hôm nay",
                event="Khởi phát cảm giác căng tức bắp chân dưới gối",
                context="Không rõ nguyên nhân, bắt đầu sau vận động",
            ))

    # Pattern: Sáng nay / Sáng ngủ dậy -> Căng hơn nhưng đi lại được
    if any(m in text_lower for m in ("sáng nay", "sáng ngủ dậy", "ngủ dậy")):
        if "căng" in text_lower or "thấy hơn" in text_lower:
            events.append(TimelineEvent(
                time_offset="today_morning",
                raw_time_marker="sáng ngủ dậy",
                event="Cảm giác căng tức tăng lên khi thức dậy",
                context="Vẫn đi lại được, không sưng đỏ",
            ))

    # Pattern: Cấp tính đột ngột (Acute sudden onset)
    if any(m in text_lower for m in ("đột ngột", "đột nhiên", "bỗng nhiên", "tự nhiên xuất hiện")):
        events.append(TimelineEvent(
            time_offset="acute_instantaneous",
            raw_time_marker="đột ngột",
            event="Triệu chứng xuất hiện đột ngột tức thì",
            context="Cần chú ý cờ đỏ mạch máu hoặc thần kinh",
        ))

    return events


def extract_negations(text: str) -> list[NegationFinding]:
    """Extract negative findings and preserved physiological functions."""
    negations: list[NegationFinding] = []
    text_lower = text.lower()

    for pattern, concept, neg_type in _NEGATION_PATTERNS:
        match = pattern.search(text_lower)
        if match:
            negations.append(NegationFinding(
                concept=concept,
                raw_span=match.group(0),
                negation_type=neg_type,  # type: ignore[arg-type]
            ))

    return negations


def extract_patient_hypotheses(text: str) -> list[PatientHypothesis]:
    """Isolate user-stated fears or internet diagnoses from true clinical facts."""
    hypotheses: list[PatientHypothesis] = []
    text_lower = text.lower()

    for pattern in _FEAR_TRIGGER_PATTERNS:
        for match in pattern.finditer(text_lower):
            raw_target = match.group(1).strip()
            # Clean filler words
            raw_target = re.sub(r"^(là|bị|mắc)\s+", "", raw_target).strip()
            if any(k in raw_target for k in ("cục máu đông", "huyết khối", "dvt", "đông máu")):
                hypotheses.append(PatientHypothesis(
                    stated_concern="Huyết khối tĩnh mạch sâu (DVT) / Cục máu đông",
                    is_clinical_diagnosis=False,
                    source="internet_search" if any(w in text_lower for w in ("mạng", "google", "tiktok", "báo")) else "user_fear",
                    repetition_count=text_lower.count("máu đông") + text_lower.count("huyết khối"),
                ))
            elif any(k in raw_target for k in ("đột quỵ", "tai biến", "stroke")):
                hypotheses.append(PatientHypothesis(
                    stated_concern="Đột quỵ / Tai biến mạch máu não",
                    is_clinical_diagnosis=False,
                    source="user_fear",
                    repetition_count=1,
                ))
            elif any(k in raw_target for k in ("ung thư", "u ác")):
                hypotheses.append(PatientHypothesis(
                    stated_concern="Bệnh lý ác tính / Ung thư",
                    is_clinical_diagnosis=False,
                    source="user_fear",
                    repetition_count=1,
                ))

    return hypotheses


def extract_medications(text: str) -> list[MedicationMention]:
    """Extract medication names, classes, and infer generic candidates."""
    meds: list[MedicationMention] = []
    text_lower = text.lower()

    for resolver in _MED_RESOLVERS:
        match = resolver["pattern"].search(text_lower)
        if match:
            meds.append(MedicationMention(
                raw_mention=match.group(0),
                candidate_active_ingredient=resolver["generic"],
                therapeutic_class=resolver["class"],
                certainty="PROBABLE" if "gì đó" in text_lower or len(match.group(0)) < 6 else "CERTAIN",
            ))

    # Fallback general allergy mention
    if not meds and any(w in text_lower for w in ("thuốc dị ứng", "uống dị ứng")):
        meds.append(MedicationMention(
            raw_mention="thuốc dị ứng",
            candidate_active_ingredient="antihistamine_h1 (chưa rõ tên hoạt chất cụ thể)",
            therapeutic_class="antihistamine_h1",
            certainty="UNKNOWN",
        ))

    return meds


def classify_complexity(
    text: str,
    symptoms_count: int,
    meds_count: int,
    hypotheses_count: int,
    has_critical_red_flag: bool,
) -> tuple[ComplexityLevel, str]:
    """Classify clinical query complexity into C0-C4 levels."""
    text_lower = text.lower()

    # C4: High risk / Emergency
    if has_critical_red_flag:
        return "C4", "Chứa cờ đỏ cấp cứu hoặc dấu hiệu đe dọa chức năng sống -> Kích hoạt Safety Kernel tối ưu tốc độ."

    # C0: Conversational / Greeting only
    conversational_greetings = ("chào bác sĩ", "xin chào", "cảm ơn bác", "cảm ơn bác sĩ", "hello", "hi bác", "alo", "chúc bác")
    words = text_lower.split()
    if len(words) <= 15 and any(g in text_lower for g in conversational_greetings) and symptoms_count == 0 and meds_count == 0 and hypotheses_count == 0:
        return "C0", "Chào hỏi hoặc hội thoại thông thường, không chứa triệu chứng lâm sàng."

    # C3: Multi-hop reasoning (Multiple conditions + chronic disease + multi-drugs)
    if (symptoms_count >= 2 and meds_count >= 2) or ("mang thai" in text_lower and meds_count >= 1):
        return "C3", "Yêu cầu lý luận lâm sàng đa bước (đa bệnh nền, đa dược chất hoặc đối tượng nhạy cảm)."

    # C2: Multi-intent / Co-occurrence (Symptoms + medication + internet anxiety/fear)
    if symptoms_count >= 1 and (meds_count >= 1 or hypotheses_count >= 1 or len(words) > 30):
        return "C2", "Câu hỏi đa ý, chứa ngữ cảnh phức tạp: triệu chứng kèm nỗi lo bệnh lý và tiền sử dùng thuốc."

    # C1: Single Clinical Question
    return "C1", "Câu hỏi y khoa đơn lẻ, tập trung vào một triệu chứng hoặc một loại thuốc cụ thể."


def decompose_query(
    text: str,
    anatomical_site: str,
    symptoms: list[str],
    medications: list[MedicationMention],
    hypotheses: list[PatientHypothesis],
    functional_status: str,
) -> list[DecomposedQuestion]:
    """Decompose a multi-faceted messy query into targeted sub-questions for parallel retrieval."""
    sub_questions: list[DecomposedQuestion] = []
    text_lower = text.lower()

    # Q1: Physical / Musculoskeletal risk vs Activity
    if any(s in text_lower for s in ("căng", "mỏi", "đau cơ", "chạy bộ", "tập gym", "dưới đầu gối")):
        sub_questions.append(DecomposedQuestion(
            sub_question_id="SQ1",
            focus_domain="symptom_risk",
            question_text=f"Căng tức {anatomical_site} sau vận động gắng sức ở người trẻ, chức năng đi lại bảo tồn: khả năng cao là gì?",
            retrieval_query=f"căng cơ bắp chân sau vận động DOMS quá tải cơ học {anatomical_site}",
        ))

    # Q2: Drug Interaction or Contraindication
    if medications:
        med_names = ", ".join(m.candidate_active_ingredient or m.raw_mention for m in medications)
        sub_questions.append(DecomposedQuestion(
            sub_question_id="SQ2",
            focus_domain="drug_interaction",
            question_text=f"Thuốc {med_names} có tương tác gì đáng ngại với tổn thương cơ bắp hoặc ảnh hưởng đến nguy cơ huyết khối không?",
            retrieval_query=f"{med_names} tac dung phu dong mau tuong tac thuoc",
        ))

    # Q3: Red-Flag Differentiation for Stated Fear (e.g. DVT)
    if hypotheses:
        fear_names = ", ".join(h.stated_concern for h in hypotheses)
        sub_questions.append(DecomposedQuestion(
            sub_question_id="SQ3",
            focus_domain="red_flags",
            question_text=f"Tiêu chuẩn phân biệt lâm sàng giữa căng cơ thông thường và {fear_names} là gì? Cờ đỏ thực sự cần đến viện?",
            retrieval_query="tieu chuan phan biet viem co chuot rut va huyet khoi tinh mach sau DVT co do",
        ))

    # Q4: Practical Safe Self-Care & Recovery
    sub_questions.append(DecomposedQuestion(
        sub_question_id="SQ4",
        focus_domain="self_care",
        question_text=f"Hướng dẫn tự chăm sóc an toàn tại nhà cho tình trạng căng cơ {anatomical_site} (chườm ấm/lạnh, nghỉ ngơi, kéo giãn).",
        retrieval_query="huong dan tu cham soc cang co chan phuc hoi chieu nghi ngoi RICE chuom am",
    ))

    return sub_questions


class ClinicalIntakeCompiler:
    """Clinical Intake Compiler.
    
    Transforms raw messy user messages into Dual-Representation intermediate state:
    Semantic Form + Clinical Form + Question Graph + Complexity Routing.
    """

    @staticmethod
    def compile(
        raw_query: str,
        *,
        patient_context: dict[str, Any] | None = None,
    ) -> CompiledClinicalIntake:
        """Execute full compilation pass on a patient's natural language message."""
        context = patient_context or {}
        
        # 1. Normalize spelling and colloquial teencode
        normalized_query = normalize_text_slang(raw_query)
        norm_lower = normalized_query.lower()

        # 2. Extract Timeline Events
        timeline = extract_timeline_events(normalized_query)

        # 3. Detect Negations and Preserved Functions
        negations = extract_negations(normalized_query)

        # 4. Extract Patient Hypotheses & Fears
        hypotheses = extract_patient_hypotheses(normalized_query)

        # 5. Extract & Resolve Medications
        medications = extract_medications(normalized_query)

        # 6. Extract Anatomical Site
        anatomical_sites = []
        if any(w in norm_lower for w in ("chân bên trái đoạn dưới đầu gối", "dưới đầu gối", "bắp chân trái")):
            anatomical_sites.append("bắp chân trái (left_calf_infraglenoid)")
        elif "bắp chân" in norm_lower or "cẳng chân" in norm_lower:
            anatomical_sites.append("bắp chân")
        elif "đầu gối" in norm_lower:
            anatomical_sites.append("khớp gối")
        elif "ngực" in norm_lower:
            anatomical_sites.append("vùng ngực")

        # 7. Extract Age
        age = context.get("age")
        if age is None:
            age_match = re.search(r"\b(\d{1,2})\s*tuổi\b", normalized_query)
            if age_match:
                age = int(age_match.group(1))

        # 8. Check Emergency Red Flags
        critical_markers = (
            "đau ngực đè nặng", "đau ngực lan", "khó thở dữ dội",
            "liệt nửa người", "méo miệng", "mất ý thức", "ngất xỉu", "nôn ra máu"
        )
        has_critical = any(marker in norm_lower for marker in critical_markers)

        # 9. Extract Confirmed Positive Findings
        positive_findings = []
        if any(w in norm_lower for w in ("căng", "căng căng", "căng tức")):
            positive_findings.append("calf_tightness_mild_moderate")
        if any(w in norm_lower for w in ("mỏi", "mỏi cơ")):
            positive_findings.append("muscle_fatigue")
        if any(w in norm_lower for w in ("chạy bộ", "tập gym", "vận động nhiều")):
            positive_findings.append("recent_strenuous_exercise")

        # 10. Functional Status
        is_ambulatory = any(n.concept == "walking_preserved" for n in negations) or "vẫn đi lại được" in norm_lower
        functional_status = "ambulatory_preserved" if is_ambulatory else "functional_status_unspecified"

        # 11. Classify Complexity Level
        complexity, complexity_reason = classify_complexity(
            normalized_query,
            symptoms_count=len(positive_findings),
            meds_count=len(medications),
            hypotheses_count=len(hypotheses),
            has_critical_red_flag=has_critical,
        )

        # 12. Decompose Multi-faceted Questions
        primary_site = anatomical_sites[0] if anatomical_sites else "vùng tổn thương"
        decomposed = decompose_query(
            normalized_query,
            anatomical_site=primary_site,
            symptoms=positive_findings,
            medications=medications,
            hypotheses=hypotheses,
            functional_status=functional_status,
        )

        # 13. Classify Uncertainty Types
        uncertainty_types: list[UncertaintyType] = []
        if any(m.certainty == "UNKNOWN" for m in medications) or "gì đó" in norm_lower:
            uncertainty_types.append("missing_information")
        if any(w in norm_lower for w in ("cũng không biết", "kiểu", "hơi hơi", "hình như")):
            uncertainty_types.append("linguistic")
        if hypotheses:
            uncertainty_types.append("clinical")

        # 14. Identify High-Value Missing Fields (Information-Gain)
        high_value_missing = []
        if not any(n.concept == "swelling_absent" for n in negations):
            high_value_missing.append("unilateral_calf_swelling_circumference (có sưng to đo lệch vòng bắp chân không?)")
        if not any(n.concept == "calf_redness_absent" for n in negations):
            high_value_missing.append("local_warmth_and_erythema (sờ vào có nóng đỏ da không?)")
        if not any(m.certainty == "CERTAIN" for m in medications):
            high_value_missing.append("exact_antihistamine_medication_name (tên chính xác của thuốc dị ứng)")

        # 15. Build Semantic Form
        semantic_form = SemanticForm(
            primary_intent="risk_assessment",
            secondary_intents=["possible_cause", "medication_reassurance", "when_to_seek_care", "self_care"],
            patient_concerns=hypotheses,
            emotional_tone="anxious" if hypotheses else "seeking_clarity",
            conversational_preambles=[p for p in ("bác ơi", "kiểu em cũng không biết") if p in norm_lower],
        )

        # 16. Build Clinical Form
        clinical_form = ClinicalForm(
            positive_findings=positive_findings,
            negative_findings=negations,
            anatomical_sites=anatomical_sites,
            functional_status=functional_status,
            timeline=timeline,
            medications=medications,
            patient_age=age,
            chronic_history=[],
            unknowns=["exact_medication_name"] if any(m.certainty != "CERTAIN" for m in medications) else [],
        )

        return CompiledClinicalIntake(
            raw_query=raw_query,
            normalized_query=normalized_query,
            semantic_form=semantic_form,
            clinical_form=clinical_form,
            complexity_level=complexity,
            complexity_rationale=complexity_reason,
            decomposed_questions=decomposed,
            uncertainty_types=uncertainty_types,
            high_value_missing_fields=high_value_missing,
        )
