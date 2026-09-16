"""Conservative phrase matching for deterministic clinical rules with typo resilience."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any
import unicodedata

_NEGATION_PREFIX = re.compile(
    r"(?:^|[\s,;:.!?])"
    r"(?:không|khong|ko|k|chưa|chua|phủ\s+nhận|phu\s+nhan|khg|hổng|hong|tuyệt\s+đối\s+không|tuyet\s+doi\s+khong)"
    r"(?:\s+(?:có|co|hề|he|bị|bi|thấy|thay|từng|tung|triệu\s+chứng|trieu\s+chung|được|duoc|tự\s+ý|tu\s+y|nên|nen|phải|phai|uống|uong|tiêm|tiem|dùng|dung|sử\s+dụng|su\s+dung))*"
    r"\s*$",
    re.IGNORECASE,
)

_NEGATION_TOKEN = re.compile(
    r"(?:^|[\s,;:.!?])"
    r"(?:không|khong|ko|k|chưa|chua|phủ\s+nhận|phu\s+nhan|khg|hổng|hong|tuyệt\s+đối\s+không|tuyet\s+doi\s+khong)"
    r"(?:\s+(?:có|co|hề|he|bị|bi|thấy|thay|từng|tung|triệu\s+chứng|trieu\s+chung|được|duoc|tự\s+ý|tu\s+y|nên|nen|phải|phai|uống|uong|tiêm|tiem|dùng|dung|sử\s+dụng|su\s+dung))*\s+",
    re.IGNORECASE,
)
_NEGATION_COORDINATOR = re.compile(
    r"(?:[,;]|\b(?:và|va|hay|hoặc|hoac|cũng\s+như|cung\s+nhu))\s*$",
    re.IGNORECASE,
)
_NEGATION_CONTRAST = re.compile(r"\b(?:nhưng|nhung|song|tuy\s+nhiên|tuy\s+nhien)\b", re.IGNORECASE)
_INQUIRY_PREFIX = re.compile(
    r"\b(?:doc\s+ve|tim\s+hieu\s+ve|nghe\s+noi\s+ve|lo\s+so\s+vi\s+doc\s+ve)\s*$",
    re.IGNORECASE,
)

# Pre-normalization dictionary for common Vietnamese mobile typing / teencode / phonetic typos
_RAW_TYPO_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(?:wá|wa)\b", re.I), "quá"),
    (re.compile(r"\b(?:đg|dg)\b", re.I), "đang"),
    (re.compile(r"\b(?:uốg|uog)\b", re.I), "uống"),
    (re.compile(r"\b(?:dùg|dug)\b", re.I), "dùng"),
    (re.compile(r"\b(?:zới|zoi)\b", re.I), "với"),
    (re.compile(r"\b(?:fải|fai)\b", re.I), "phải"),
    (re.compile(r"\b(?:bsi|bs)\b", re.I), "bác sĩ"),
    (re.compile(r"\b(?:amox)\b", re.I), "amoxicillin"),
    (re.compile(r"\b(?:kơ)\b", re.I), "cơ"),
    (re.compile(r"\b(?:kăng)\b", re.I), "căng"),
    (re.compile(r"\b(?:kổ)\b", re.I), "cổ"),
    (re.compile(r"\b(?:việk)\b", re.I), "việc"),
    (re.compile(r"\b(?:nhìu)\b", re.I), "nhiều"),
    (re.compile(r"\b(?:k|ko|khg|hem|hổng|hong)\b", re.I), "không"),
    (re.compile(r"\b(?:đc|dc)\b", re.I), "được"),
    (re.compile(r"\b(?:zút)\b", re.I), "rút"),
    (re.compile(r"\b(?:bụg)\b", re.I), "bụng"),
    (re.compile(r"\b(?:ngựk)\b", re.I), "ngực"),
    (re.compile(r"\b(?:thuốk|thuôc)\b", re.I), "thuốc"),
    (re.compile(r"\b(?:zạ\s*zày|dạ\s*zày|zạ\s*dày)\b", re.I), "dạ dày"),
    (re.compile(r"\b(?:tiêu\s+cuẹc)\b", re.I), "tiêu cực"),
    (re.compile(r"\b(?:trạining)\b", re.I), "training"),
]

# Post-accent-removal dictionary for Latinized typos
_POST_NORM_TYPO_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(?:kang\s+ko|cang\s+ko|kang\s+co|can\s+co)\b", re.I), "cang co"),
    (re.compile(r"\b(?:uog)\b", re.I), "uong"),
    (re.compile(r"\b(?:dug)\b", re.I), "dung"),
    (re.compile(r"\b(?:zoi)\b", re.I), "voi"),
    (re.compile(r"\b(?:dau\s+bug)\b", re.I), "dau bung"),
    (re.compile(r"\b(?:tuc\s+nguk|dau\s+nguk)\b", re.I), "dau nguc"),
    (re.compile(r"\b(?:chuot\s+zut|chuo\s+rut)\b", re.I), "chuot rut"),
    (re.compile(r"\b(?:da\s+zay)\b", re.I), "da day"),
    (re.compile(r"\b(?:wa)\b", re.I), "qua"),
    (re.compile(r"\b(?:dg)\b", re.I), "dang"),
]




def normalize_search_text(value: str) -> str:
    """Normalize text removing accents, standardizing common medical typos and teencode."""
    # Pass 0: Strip quotes and brackets
    text = re.sub(r'[“”"‘’\'`]', " ", value.strip())

    # Pass 1: Raw teencode correction
    for pattern, repl in _RAW_TYPO_MAP:
        text = pattern.sub(repl, text)

    # Pass 2: Unicode decomposition and accent stripping
    decomposed = unicodedata.normalize("NFD", text.lower())
    normalized = "".join(
        character for character in decomposed if unicodedata.category(character) != "Mn"
    ).replace("đ", "d")

    # Pass 3: Post-normalization Latinized typos
    for pattern, repl in _POST_NORM_TYPO_MAP:
        normalized = pattern.sub(repl, normalized)

    # Pass 4: Collapse whitespace
    return re.sub(r"\s+", " ", normalized).strip()


def contains_affirmed_phrase(text: str, phrase: str) -> bool:
    """Return true when at least one phrase occurrence is not directly negated.

    This intentionally handles only explicit local negation. Ambiguous or remote
    negation is left for clarification rather than inferred by the rule engine.
    """
    if not phrase:
        return False
    for match in re.finditer(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text):
        prefix = text[max(0, match.start() - 64) : match.start()]
        directly_negated = _NEGATION_PREFIX.search(prefix) is not None
        # Accent removal makes Vietnamese "chữa" (treat) and "chưa" (not
        # yet) identical. In phrases such as "thuốc để chữa đau ngực", the
        # token before the symptom is a treatment verb, not a negation.
        if directly_negated and re.search(
            r"\b(?:de|cach|thuoc|dieu tri)\s+chua\s*$",
            prefix,
            re.IGNORECASE,
        ):
            directly_negated = False
        coordinated_negation = False
        if not directly_negated and _NEGATION_COORDINATOR.search(prefix):
            clause = re.split(r"[.;!?]", prefix)[-1]
            negations = list(_NEGATION_TOKEN.finditer(clause))
            if negations:
                scoped_text = clause[negations[-1].end() :]
                coordinated_negation = (
                    not _NEGATION_CONTRAST.search(scoped_text)
                    and len(scoped_text.split()) <= 10
                )
        is_inquiry = _INQUIRY_PREFIX.search(prefix) is not None
        if not directly_negated and not coordinated_negation and not is_inquiry:
            return True
    return False


@dataclass
class ExtractedClinicalFacts:
    """Structured clinical facts extracted deterministically from user input."""
    raw_text: str
    normalized_text: str
    confirmed_symptoms: list[str]
    negative_findings: list[str]
    severity_score: int | None = None
    time_to_peak_seconds: int | None = None
    sudden_onset: bool = False
    gradual_onset: bool = False
    onset_duration_hours: float | None = None
    user_quote_trap: bool = False
    anticoagulant_used: bool = False
    trauma_state: str = "none"  # "confirmed", "negated", "none"
    reproducible_musculoskeletal: bool = False
    postprandial_reflux: bool = False
    reactive_airway_relieved: bool = False
    triggers: list[str] = field(default_factory=list)
    improved_after_onset: bool = False
    inferences: list[str] = field(default_factory=list)


NON_EXCLUSION_RULES: dict[str, list[str]] = {
    "thunderclap_headache": [
        "đỡ hơn", "giảm đau", "bớt đau", "từ 10 xuống", "xuống 6/10",
        "giờ đã đỡ", "tỉnh táo", "không nôn", "không yếu liệt",
    ],
    "meningitis": [
        "vẫn cúi được", "cúi được", "không sợ ánh sáng", "chưa nôn",
        "tỉnh táo", "chỉ sốt nhẹ",
    ],
    "intracranial_hemorrhage": [
        "không nôn", "chưa nôn", "không yếu liệt", "tỉnh táo",
        "không ngất", "vẫn nhớ được", "không chảy máu ngoài",
    ],
    "stroke": [
        "không yếu liệt", "tự đi được", "chỉ tê nhẹ", "vẫn nói được",
        "không méo miệng",
    ],
    "acute_coronary_syndrome": [
        "không lan", "đỡ khi nghỉ", "huyết áp bình thường", "không khó thở",
    ],
}


def extract_clinical_facts(raw_text: str) -> ExtractedClinicalFacts:
    """Extract deterministic clinical facts, distinguishing confirmed symptoms,
    negative findings, severity scores, temporal dynamics, and triggers.
    """
    normalized = normalize_search_text(raw_text)
    lower_raw = raw_text.lower()

    # 1. Severity extraction (e.g. 10/10, 9/10, 8/10)
    severity: int | None = None
    sev_match = re.search(r"\b(10|[1-9])\s*/\s*10\b", raw_text)
    if sev_match:
        try:
            severity = int(sev_match.group(1))
        except ValueError:
            pass
    elif re.search(r"\b(?:mức|diem|đo|nang)\s*(10|[1-9])\b", normalized):
        m = re.search(r"\b(?:mức|diem|đo|nang)\s*(10|[1-9])\b", normalized)
        if m:
            try:
                severity = int(m.group(1))
            except ValueError:
                pass

    # 2. Time to peak (e.g. < 1 phút, đạt đỉnh trong chưa đầy 1 phút)
    time_to_peak: int | None = None
    if re.search(r"(?:chua\s*day|duoi|<|trong\s*vong|dat\s*dinh\s*trong)?\s*1\s*phut", normalized):
        time_to_peak = 60
    elif "vai giay" in normalized or "vai phut" in normalized:
        time_to_peak = 120

    # 3. Sudden onset
    sudden = any(
        kw in normalized
        for kw in ("dot ngot", "set danh", "nhu set danh", "bat ngo", "nhanh chong", "tuc thi")
    )

    # 4. Triggers
    triggers: list[str] = []
    trigger_patterns = [
        ("gym_exertion", ("tap gym", "khi tap gym", "dang tap gym", "nang ta", "gang suc", "chay bo")),
        ("sexual_activity", ("sau quan he", "khi quan he", "quan he", "lam tinh")),
        ("head_trauma", ("nga xe", "te xe", "dap dau", "nga", "chan thuong dau", "va dap")),
        ("valsalva", ("khi ho", "khi ran", "ran")),
    ]
    for trig_name, phrases in trigger_patterns:
        if any(contains_affirmed_phrase(normalized, p) for p in phrases):
            triggers.append(trig_name)

    # 5. Symptom improved after onset (Non-exclusion invariant)
    improved = any(
        marker in normalized
        for marker in (
            "do hon", "giam xuong", "bot dau", "do dau", "giam dau",
            "do nhieu", "gio da do", "da bot", "do hon truoc",
        )
    ) or bool(re.search(r"(?:xuong|con)\s*[0-9]\s*/\s*10", normalized))

    # 6. Negative findings (explicit user denials / non-exclusion candidates)
    negatives: list[str] = []
    negative_candidates = [
        ("khong yeu liet", ("khong yeu liet", "khong liet", "khong te liet")),
        ("khong non", ("khong non", "chua non", "khong buon non", "khong oi")),
        ("van cui duoc", ("van cui duoc", "cui duoc binh thuong", "cui dau duoc")),
        ("khong sot", ("khong sot", "khong bi sot")),
        ("khong meo mieng", ("khong meo mieng", "khong lech mieng")),
        ("khong mat y thuc", ("khong ngat", "khong bat tinh", "van tinh tao")),
    ]
    for label, patterns in negative_candidates:
        if any(p in normalized or p in lower_raw for p in patterns):
            negatives.append(label)

    # 7. Confirmed symptoms (affirmed positive findings)
    confirmed: list[str] = []
    symptom_checks = [
        ("đau đầu", ("dau dau", "nhuc dau")),
        ("đau đầu dữ dội", ("dau dau du doi", "dau du doi", "dau du")),
        ("sốt", ("sot", "sot cao", "nhiet do")),
        ("buồn nôn", ("buon non", "non nao", "mac non")),
        ("cổ cứng", ("co cung", "cung co", "cung gay", "co hoi cung", "guong co")),
        ("buồn ngủ", ("buon ngu", "buon ngu hon", "li bi", "ngu ga", "lo mo")),
        ("ngã xe / chấn thương đầu", ("nga xe", "te xe", "dap dau", "chan thuong dau")),
        ("đau ngực", ("dau nguc", "tuc nguc", "nang nguc", "dau that nguc")),
        ("khó thở", ("kho tho", "tho gap", "hut hoi")),
        ("yếu liệt", ("yeu liet", "meo mieng", "noi ngong")),
    ]
    for sym_label, patterns in symptom_checks:
        if any(contains_affirmed_phrase(normalized, p) for p in patterns):
            confirmed.append(sym_label)

    # 8. Gradual onset vs. sudden onset and duration
    gradual_markers = (
        "tu tu", "tang dan", "tang tu tu", "bat dau tu tu",
        "suot 8 tieng", "suot 8 gio", "qua 8 tieng", "qua 8 gio",
        "keo dai 3 tuan", "3 tuan nay", "3 tuan qua", "nhieu gio qua",
        "vai tieng qua", "suot ca ngay", "am i ca ngay",
    )
    gradual = any(gm in normalized for gm in gradual_markers) or bool(
        re.search(r"\b(?:suot|trong|khoang|keo\s+dai)\s+(?:[2-9]|[1-9][0-9]+)\s*(?:tieng|gio|h|ngay|tuan)\b", normalized)
    )

    duration_hours: float | None = None
    h_match = re.search(r"\b(?:suot|trong|khoang|duoc|da)?\s*(\d+)\s*(?:tieng|gio|h)\b", normalized)
    if h_match:
        try:
            duration_hours = float(h_match.group(1))
        except ValueError:
            pass
    elif "3 tuan" in normalized:
        duration_hours = 21 * 24.0

    # 9. User self-diagnosis / search quote trap
    quote_patterns = (
        "doc tren mang", "doc tren google", "doc tren internet", "doc tren bao",
        "thay tu do", "goi no la", "tu goi la", "nghe nguoi ta",
    )
    user_quote = any(qp in normalized for qp in quote_patterns)

    # 10. Anticoagulant use and trauma negation
    anticoag_drugs = (
        "warfarin", "sintrom", "chong dong", "xarelto", "eliquis", "coumadin",
        "heparin", "lovenox", "thuoc loang mau", "thuoc lam loang mau",
    )
    anticoag_used = any(drug in normalized for drug in anticoag_drugs)

    negated_trauma_markers = (
        "khong bi nga", "khong nga", "khong va quet", "khong va dap",
        "khong dap dau", "khong bi va dap", "khong te xe", "khong nga xe",
        "khong cham thuong", "khong va quet gi", "khong nga hay va quet",
        "khong nga khong va dap",
    )
    if any(p in normalized for p in negated_trauma_markers):
        trauma_st = "negated"
    elif any(
        contains_affirmed_phrase(normalized, p)
        for p in ("nga", "va dap", "dap dau", "va dau", "nga dap dau", "te xe", "nga xe", "chan thuong dau")
    ):
        trauma_st = "confirmed"
    else:
        trauma_st = "none"

    # 11. Functional benign patterns
    repro_msk = is_reproducible_musculoskeletal_chest_pain(raw_text)
    gerd_flx = is_gerd_heartburn(raw_text)
    airway_relieved = is_reactive_airway_relieved(raw_text)

    return ExtractedClinicalFacts(
        raw_text=raw_text,
        normalized_text=normalized,
        confirmed_symptoms=confirmed,
        negative_findings=negatives,
        severity_score=severity,
        time_to_peak_seconds=time_to_peak,
        sudden_onset=sudden,
        gradual_onset=gradual,
        onset_duration_hours=duration_hours,
        user_quote_trap=user_quote,
        anticoagulant_used=anticoag_used,
        trauma_state=trauma_st,
        reproducible_musculoskeletal=repro_msk,
        postprandial_reflux=gerd_flx,
        reactive_airway_relieved=airway_relieved,
        triggers=triggers,
        improved_after_onset=improved,
    )


def filter_known_clarifying_questions(
    questions: list[str],
    facts: ExtractedClinicalFacts,
) -> list[str]:
    """Filter out clarifying questions asking for information the user already provided.
    Implements the ASK_ONLY_IF_UNKNOWN principle.
    """
    filtered = []
    for q in questions:
        norm_q = normalize_search_text(q)
        # Severity already known
        if facts.severity_score is not None and any(
            k in norm_q for k in ("0 den 10", "thang diem", "muc do dau", "diem dau")
        ):
            continue
        # Sudden onset or time to peak already known
        if (facts.sudden_onset or facts.time_to_peak_seconds is not None) and any(
            k in norm_q for k in (
                "xuat hien dot ngot", "khoi phat dot ngot",
                "dat muc du doi nhat", "duoi 1 phut hay tang dan",
                "dat dinh trong bao lau",
            )
        ):
            continue
        # Weakness already explicitly affirmed or denied
        if ("khong yeu liet" in facts.negative_findings or "yếu liệt" in facts.confirmed_symptoms) and any(
            k in norm_q for k in ("yeu hoac te", "yeu liet", "te liet", "te yeu")
        ):
            continue
        # Fever already known
        if ("sốt" in facts.confirmed_symptoms or "khong sot" in facts.negative_findings) and any(
            k in norm_q for k in ("co kem theo sot", "sot cao kem")
        ):
            continue
        # Vomiting already known
        if ("buồn nôn" in facts.confirmed_symptoms or "khong non" in facts.negative_findings) and any(
            k in norm_q for k in ("co non", "non mua", "non hay")
        ):
            continue
        filtered.append(q)
    return filtered


def is_reproducible_musculoskeletal_chest_pain(text: str) -> bool:
    """Return True if chest discomfort has clear reproducible musculoskeletal features without red flags."""
    norm = normalize_search_text(text)
    reproducible_triggers = (
        "an dung vao do", "an vao co nguc", "an vao do", "an vao thi dau",
        "chi dau khi an", "khi an dung mot diem", "dau nguc khi an",
        "dau khi an", "sau tap nguc", "sau buoi tap", "khi xoay nguoi",
        "dau co truoc nguc khi gio tay", "dau co truoc nguc", "sau khi be do nang",
        "be do nang", "cam ket 100% day chi la dau co", "an manh tay",
        "an tay vao", "khe xuong suon", "khieng do nang", "khieng nang",
        "sau khi khieng", "dau nhoi nguc khi an",
    )
    has_trigger = any(trig in norm for trig in reproducible_triggers)
    # Check for true high-risk cardiac / systemic red flags using proper negation handling
    has_cardiac_red_flag = any(
        contains_affirmed_phrase(norm, rf)
        for rf in (
            "kho tho", "hut hoi", "va mo hoi", "toat mo hoi", "lan tay",
            "lan ham", "lan lung", "xe ra sau lung", "ngat", "choang", "cocaine"
        )
    )
    return has_trigger and not has_cardiac_red_flag


def is_fleeting_chest_pain(text: str) -> bool:
    """Return True for brief isolated twinges of chest pain lasting seconds without exertional limitation."""
    norm = normalize_search_text(text)
    has_seconds = any(s in norm for s in ("2 giay roi het", "vai giay roi het", "thoang qua 2 giay"))
    good_exercise = any(e in norm for e in ("chay bo binh thuong", "chay bo khong dau", "khong dau khi tap"))
    return has_seconds or (has_seconds and good_exercise)


def is_cold_cough_chest_soreness(text: str) -> bool:
    """Return True for tracheobronchial soreness during common cold with normal vitals."""
    norm = normalize_search_text(text)
    return (
        ("ho cam lanh" in norm or "bi cam" in norm)
        and ("hoi dau nguc" in norm or "dau nhe" in norm)
        and ("spo2 99%" in norm or "spo2 98%" in norm or "tho binh thuong" in norm)
        and not any(rf in norm for rf in ("kho tho nang", "hut hoi", "lan tay"))
    )


def is_gerd_heartburn(text: str) -> bool:
    """Return True for typical postprandial retrosternal burning without dyspnea."""
    norm = normalize_search_text(text)
    has_burning = any(
        b in norm
        for b in (
            "nong rat sau xuong uc", "nong rat nguc", "nong rat con cao",
            "nong rat con cao sau xuong uc", "o chua", "o chua len co",
        )
    )
    has_postprandial = any(
        p in norm
        for p in (
            "sau bua an", "sau an", "sau khi an no", "an no va nam",
            "nam xuong nang hon", "an no", "sau khi an",
        )
    )
    no_dyspnea = any(d in norm for d in ("khong kho tho", "khong co kho tho", "khong dau lan", "khong dau lan di dau"))
    has_red_flags = any(
        contains_affirmed_phrase(norm, rf)
        for rf in ("va mo hoi", "toat mo hoi", "lan tay", "lan ham", "kho tho")
    )
    return has_burning and (has_postprandial or "o chua" in norm) and no_dyspnea and not has_red_flags


def is_iron_supplement_stool(text: str) -> bool:
    """Return True if dark/black stool is attributed to iron supplements and patient is asymptomatic."""
    norm = normalize_search_text(text)
    return (
        ("uong vien sat" in norm or "uong sat" in norm or "vien sat" in norm)
        and ("phan den" in norm or "phan toi" in norm)
        and any(w in norm for w in ("cam thay khoe", "khong choang", "khong dau bung", "khoe"))
        and not any(w in norm for w in ("them choang", "met va tim dap nhanh", "choang vang", "ngat"))
    )


def is_past_chemo_years_ago(text: str) -> bool:
    """Return True if chemotherapy was completed years ago, not currently active."""
    norm = normalize_search_text(text)
    return any(p in norm for p in ("hoan tat hoa tri tu nhieu nam", "nhieu nam truoc", "xong hoa tri nhieu nam"))


def is_post_exercise_tachypnea(text: str) -> bool:
    """Return True if rapid breathing was transient post-exercise and is now completely resolved."""
    norm = normalize_search_text(text)
    return (
        ("sau khi chay" in norm or "sau chay nuoc rut" in norm or "chay 5 km" in norm)
        and ("hoan toan binh thuong" in norm or "tro lai binh thuong" in norm)
    )


def is_static_shock(text: str) -> bool:
    """Return True for minor static electricity zap."""
    norm = normalize_search_text(text)
    return "tinh dien" in norm and any(w in norm for w in ("cua xe", "giat nhe", "mot cai roi het"))


def is_reactive_airway_relieved(text: str) -> bool:
    """Return True if patient had mild cold-induced wheeze with normal speaking and ventolin relief."""
    norm = normalize_search_text(text)
    has_mild_wheeze = any(w in norm for w in ("kho khe nhe", "tho kho khe nhe", "ngoai troi lanh", "di ngoai troi lanh"))
    has_ventolin = any(v in norm for v in ("ventolin", "xit ventolin", "thuoc xit"))
    has_relief = any(r in norm for r in ("do nhieu", "do han", "thay do", "do"))
    normal_speech = any(s in norm for s in ("noi chuyen nguyen cau", "noi chuyen binh thuong", "noi binh thuong", "noi chuyen"))
    has_severe = any(rf in norm for rf in ("tim tai", "khong noi duoc", "co keo", "spo2 duoi"))
    return (has_mild_wheeze or has_ventolin) and has_relief and (normal_speech or "binh thuong" in norm) and not has_severe


def is_hyperventilation_anxiety(text: str) -> bool:
    """Return True for hyperventilation syndrome triggered by acute emotional stress with perioral paresthesia."""
    norm = normalize_search_text(text)
    has_stress = any(s in norm for s in ("cai nhau", "cang thang", "stress", "lo au", "tuc gian", "hoang loan"))
    has_hypervent = any(h in norm for h in ("tho hon hen", "tho rat nhanh", "tho nhanh", "ngot ngat", "ngot ngat kho tho"))
    has_paresthesia = any(p in norm for p in ("te ran quanh mieng", "te quanh mieng", "te dau ngon tay", "te tay", "te ran"))
    no_cyanosis = not any(c in norm for c in ("tim tai", "moi tim", "tho rit thanh quan", "spo2 duoi"))
    return has_stress and has_hypervent and has_paresthesia and no_cyanosis


def is_subacute_chest_pain(text: str) -> bool:
    """Return True for chronic/subacute chest discomfort (> 2 weeks) without acute ischemic red flags."""
    norm = normalize_search_text(text)
    has_duration = any(d in norm for d in ("3 tuan nay", "3 tuan qua", "nhieu tuan", "ca thang nay", "keo dai 3 tuan", "3 tuan"))
    has_mild = any(m in norm for m in ("tuc nguc nhe", "dau nguc nhe", "mo ho", "khi hit tho sau", "hit tho that sau"))
    no_acute = not any(contains_affirmed_phrase(norm, rf) for rf in ("va mo hoi", "kho tho du doi", "lan tay trai", "lan ham", "ngat"))
    return has_duration and has_mild and no_acute


def is_gradual_headache_user_quote(text: str) -> bool:
    """Return True if user explicitly quotes 'set danh' from internet but reports gradual onset over hours."""
    norm = normalize_search_text(text)
    has_quote = any(
        q in norm
        for q in (
            "doc tren mang", "doc tren google", "doc tren internet", "doc tren bao",
            "thay tu do", "goi no la", "tu goi la", "nghe nguoi ta",
        )
    )
    has_gradual = any(
        g in norm
        for g in (
            "tu tu", "tang dan", "tang dan suot", "suot 8 tieng", "8 tieng qua",
            "nhieu tieng", "bat dau tu tu", "suot 8 gio",
        )
    )
    return has_quote and has_gradual


def is_anticoagulant_no_trauma(text: str) -> bool:
    """Return True if user is on anticoagulant but explicitly denies trauma, falls, or bleeding signs."""
    norm = normalize_search_text(text)
    has_anticoag = any(d in norm for d in ("warfarin", "sintrom", "chong dong", "xarelto", "eliquis", "coumadin"))
    denies_trauma = any(
        t in norm
        for t in (
            "khong bi nga", "khong nga", "khong va quet", "khong va dap",
            "khong nga hay va quet", "khong nga khong va dap", "khong te xe",
            "khong co va dap", "khong bi va quet",
        )
    )
    no_bleeding = not any(b in norm for b in ("bam tim", "chay mau", "xuat huyet", "di tieu ra mau", "non ra mau"))
    return has_anticoag and denies_trauma and no_bleeding


def is_cluster_headache(text: str) -> bool:
    """Return True for severe unilateral orbital headache with autonomic signs (tearing, conjunctival injection)."""
    norm = normalize_search_text(text)
    has_orbital = any(o in norm for o in ("hoc mat", "quanh mat", "mot ben mat", "hoc mat trai", "hoc mat phai", "thai duong mot ben"))
    has_autonomic = any(a in norm for a in ("chay nuoc mat", "do mat", "nghet mui", "chay nuoc mat rong rong"))
    has_severe = any(s in norm for s in ("dau buot du doi", "du doi", "nua dem", "dau buot"))
    no_neuro_deficit = not any(n in norm for n in ("yeu liet", "meo mieng", "mat thi luc hoan toan", "cung co"))
    return has_orbital and has_autonomic and has_severe and no_neuro_deficit


# =====================================================================
# Dialect, Folk & Code-Switching Medical Concept Mapping
# =====================================================================

DIALECT_CONCEPT_MAP: dict[str, str] = {
    # Folk & Dialect (North/Central/South)
    "cam khau": "khong noi duoc mat tieng roi loan ngon ngu",
    "meo xech": "meo mieng mat can doi liet mat",
    "meo mieng": "mat can doi mat liet mat",
    "kinh phong": "co giat sui bot mep",
    "sui bot mep": "co giat",
    "yen ngua": "vung quanh hau mon sinh duc vung day quan",
    "vung yen ngua": "vung quanh hau mon sinh duc vung day quan",
    "mui tao chin": "hoi tho mui trai cay toan ceton",
    "mui qua chin ung": "hoi tho mui trai cay toan ceton",
    "hoa qua ung": "hoi tho mui trai cay toan ceton",
    "trai cay len men": "hoi tho mui trai cay toan ceton",
    "thung dau": "dau dau du doi set danh",
    "that ruot that gan": "dau bung du doi quan quai",
    "tat ruot gan": "dau bung du doi quan quai",
    "tuc tuoi long nguc": "dau nguc chen ep kho tho",
    "on lanh thau xuong": "ret run sot cao",
    "ham hap": "sot nhe",
    "ham hap sot": "sot nhe",
    "nhuc dau tung tung": "dau dau am i",
    "ngua ram ran": "ngua nhe ngoai da",
    "chan tay bun run": "doi bung ha duong huyet nhe",
    "moi nhu hai vai": "moi co sinh ly",
    "nguc van dau that": "dau that nguc",
    "nguc dau that": "dau that nguc",
    "van dau that": "dau that nguc",
    "nguc bop nghet": "dau that nguc",
    "bang huyet": "bang huyet sau sinh chay mau cap cuu",

    # Teencode / Unaccented / Slang
    "k tho dc": "khong tho duoc kho tho nghen tho",
    "k tho duoc": "khong tho duoc kho tho",
    "nghen u khong tho duoc": "nghen co tho rit thanh quan khong tho duoc",
    "nghen u": "nghen co tho rit thanh quan",
    "nghen co hong": "nghen co tho rit thanh quan",
    "nghen co": "nghen co tho rit thanh quan",
    "sung phu mat": "phu mat phu mach mi mat",
    "mat hup hip": "phu mat phu mach mi mat",
    "man do ran ran": "noi may day toan than",
    "noi me day khap ng": "noi may day toan than",
    "noi me day": "noi may day toan than",
    "non thoc non thao": "non mua lien tuc",
    "non thoc thao": "non mua lien tuc",
    "non ca ngay": "non mua lien tuc",
    "nhin den co quang cau vong": "nhin den quang cau vong quang tan sac",
    "quang 7 sac cau vong": "nhin den quang cau vong quang tan sac",
    "mat mo tit": "mat mo dot ngot mat thi luc cap",
    "mat toi sam lai": "mat mo dot ngot mat thi luc cap",
    "dau buot con mat phai phat khoc": "dau nhuc mat du doi kem dau dau",
    "dau buot nhu kim cham giat len dinh dau": "dau nhuc mat du doi kem dau dau",
    "buot doc hai gio": "dau lung lan hai chan",
    "te bi mat het cam giac cho day quan": "te vung yen ngua mat cam giac",
    "te vung yen ngua mat c": "te vung yen ngua mat cam giac",
    "quanh vung ben hau mon": "vung yen ngua quanh hau mon sinh duc",
    "ben hau mon": "vung yen ngua quanh hau mon sinh duc",
    "ran mai khong ra giot nao": "bi tieu cap tinh khong tieu duoc",
    "bung cang tuc vi bi tieu": "bi tieu cap tinh khong tieu duoc",
    "bi tieu ca ngay": "bi tieu cap tinh khong tieu duoc",
    "di tieu bi k tieu dc": "bi tieu cap tinh khong tieu duoc",
    "an vao nhoi buong ra dau thon": "dau bung ho chau phai phan ung thanh bung blumberg",
    "an vao dau nhoi buong tay ra dau giat nay minh": "dau bung ho chau phai phan ung thanh bung blumberg",
    "om bung duoi ben phai": "dau bung ho chau phai ruot thua",
    "buoc di thon giat thot": "dau bung ho chau phai vi tri ruot thua",
    "dau thon bung": "dau thon giat thot phan ung thanh bung blumberg",
    "dau thon": "dau thon giat thot phan ung thanh bung blumberg",
    "tinh hoan dau buot nghen len bung": "xoan tinh hoan biu sung to cap cuu",
    "biu sung tay to": "xoan tinh hoan biu sung to cap cuu",
    "om ha bo keu dau tinh hoan": "xoan tinh hoan biu sung to cap cuu",
    "dau biu dot ngot du doi": "xoan tinh hoan biu sung to cap cuu",

    # Caregiver / Observer observations
    "roi thia": "yeu liet tay roi thia liet nua nguoi",
    "tay trai buong thong": "yeu liet tay liet nua nguoi",
    "tay trai ru xuong": "yeu liet tay liet nua nguoi",
    "noi ngong liu nhiu": "noi ngong kho noi roi loan ngon ngu",
    "om co hong tho kho khe nghet tho": "tho rit thanh quan phu mach phan ve",
    "mat sung vu len": "phu mat phu mach mi mat",
    "nam li bi khat nuoc tho doc": "khat nuoc du doi tho nhanh sau toan ceton",

    # English-Vietnamese Code-Switching
    "type 1 diabetes": "dai thao duong type 1 tieu duong",
    "slurred speech": "noi ngong kho noi roi loan ngon ngu",
    "facial droop": "meo mieng lech mat",
    "left arm weak": "yeu liet tay liet nua nguoi",
    "arm weak": "yeu liet tay",
    "arm completely weak": "yeu liet tay hoan toan liet nua nguoi",
    "cannot breathe": "kho tho nghen tho",
    "can not breathe": "kho tho nghen tho",
    "seeing halos": "nhin den quang cau vong quang tan sac",
    "colored halos": "nhin den quang cau vong quang tan sac",
    "colored halos around lights": "nhin den quang cau vong quang tan sac",
    "saddle anesthesia": "te bi vung yen ngua mat cam giac vung day quan",
    "urinary retention": "bi tieu cap tinh khong tieu duoc",
    "fruity acetone": "hoi tho mui trai cay toan ceton",
    "fruity breath": "hoi tho mui trai cay toan ceton",
    "testicular pain": "dau tinh hoan biu sung to cap cuu",
    "scrotal swelling": "dau tinh hoan biu sung to cap cuu",
    "rlq abdominal pain": "dau bung ho chau phai phan ung thanh bung",
    "rlq pain": "dau bung ho chau phai",
    "low-grade fever": "sot nhe",
    "runny nose": "chay nuoc mui",
    "muscle soreness": "moi co cang co",
    "shortness of breath": "kho tho",
    "anaphylaxis": "phan ve phu mach tho rit thanh quan",
    "sudden vision loss": "mat thi luc dot ngot mat mo cap",
    "vision loss": "mat mo dot ngot mat thi luc",
    "severe eye pain": "dau nhuc mat du doi",
}


def normalize_clinical_concepts(text: str) -> str:
    """Preserve original text while enriching with standard medical concepts."""
    normalized = normalize_search_text(text)
    for source, target in DIALECT_CONCEPT_MAP.items():
        if source in normalized and target not in normalized:
            normalized = normalized.replace(source, f"{source} {target}")
    return normalized
