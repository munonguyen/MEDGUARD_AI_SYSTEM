"""Out-of-Domain & Crisis guardrail layer for MedGuard AI.

This module runs *before* the clinical intent router and provides three
protection tiers:

1. **Crisis / Self-Harm Detection** — highest priority.  Blocks any
   request containing self-harm intent, toxic-substance queries, or
   prompt-injection attacks and returns a crisis-intervention response.

2. **Out-of-Domain (OOD) Topic Filter** — catches questions that are
   entirely outside the medical domain (programming, weather, finance,
   sports, cooking, philosophy, entertainment, technology devices …).

3. **Metaphor / Ambiguity Disambiguator** — prevents figurative uses of
   medical vocabulary (e.g. "sốt ruột" = anxious, "chảy máu nhân sự" =
   staff attrition) from being misrouted into clinical triage.

4. **Veterinary Guard** — redirects animal/pet health queries to a
   veterinary professional instead of human-medicine triage.

Design principles
-  Entirely deterministic — zero LLM calls.
-  Runs in < 1 ms for any input.
-  Returns ``None`` when the message is in-domain (clinical/pharma).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.services.clinical_text import normalize_search_text


# =====================================================================
# Result Types
# =====================================================================

OODVerdict = Literal[
    "crisis_self_harm",
    "crisis_toxic_substance",
    "crisis_prompt_injection",
    "ood_off_topic",
    "ood_metaphor",
    "ood_veterinary",
]


@dataclass(frozen=True)
class OODResult:
    """Returned when a query is blocked by the guard layer."""

    verdict: OODVerdict
    reply: str
    hotline: str | None = None


# =====================================================================
# Tier 1 — Crisis & Harm Detection (highest priority)
# =====================================================================

_RAW_CRISIS_PATTERN = re.compile(
    r"\b(tự tử|tự sát|tự vẫn|tự hại|cắt mạch máu|treo cổ|nhảy lầu|nhảy cầu)\b",
    re.IGNORECASE,
)

_CRISIS_SELF_HARM_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in (
        # Suicidal intent (unaccented forms, disambiguated from tu van = tư vấn and tu tu = từ từ)
        r"(?:muon|chan)\s*(?:chet|tu\s*tu)\b",
        r"(?:khong\s+muon|chan)\s*song\b",
        r"\b(tu\s*(?:sat|hai)|tu\s+gay\s+thuong|cat\s+mach\s+mau|treo\s+co|nhay\s+(?:lau|cau))\b",
        r"(?:y\s*dinh|toan|dinh|nghi\s+den|tim\s+cach|cach|thuoc)\s+(?:de\s+)?tu\s*(?:tu|van)\b",
        r"\btu\s*(?:tu|van)\s+(?:bang|chet|tai\s+nha|thanh\s+cong|nhu\s+the\s+nao|lam\s+sao)\b",
        r"khong\s+muon\s+song",
        r"chan\s+song",
        r"uong\s+(?:bao\s+nhieu|nhieu|\d+)\s+(?:vien|thuoc).*(?:chet|tu\s*tu|tu\s*vong)",
        r"lieu\s+(?:gay\s+)?chet",
        r"lieu\s+(?:tu\s+)?vong",
        r"(?:bao\s+nhieu|lam\s+sao).*chet",
        r"(?:uong|dung).*(?:chet|tu\s+vong)\s*(?:nhanh|duoc)",
        r"qua\s+lieu.*(?:chet|tu\s+vong|nhanh)",
    )
]

_CRISIS_TOXIC_SUBSTANCE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"chiet\s+xuat\s+(?:doc|chat\s+doc|nicotine|cyanide|ricin)",
        r"tong\s+hop\s+(?:methamphetamine|meth|heroin|fentanyl|ma\s+tuy|cocaine)",
        r"(?:pha\s+che|dieu\s+che|che\s+tao).*(?:doc\s+to|chat\s+doc|thuoc\s+chuot|thuoc\s+doc)",
        r"(?:pha|tao).*thuoc\s+chuot.*(?:lieu\s+manh|manh)",
        r"dau\s+doc",
        r"cach\s+(?:lam|tao|pha|che).*(?:bom|vu\s+khi|chat\s+no)",
    )
]

_CRISIS_PROMPT_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"(?:bo\s+qua|ignore|bypass|skip|override)\s*(?:moi|all|tat\s+ca)?\s*(?:quy\s+tac|rule|safety|an\s+toan|guideline)",
        r"system\s+prompt",
        r"(?:tu\s+gio\s+)?ban\s+la\s+(?:ai\s+)?(?:bac\s+si|doctor).*(?:khong\s+can|ignore|bo\s+qua)",
        r"ke\s+(?:don|lieu).*(?:thuoc\s+phien|morphine|opioid|fentanyl|heroin)",
        r"output\s+raw",
        r"jailbreak",
        r"dan\s*mode",
        r"(?:pretend|gia\s+vo).*(?:doctor|bac\s+si).*(?:no\s+rules|khong\s+guideline)",
    )
]

_CRISIS_HOTLINE_RESPONSE = (
    "🆘 **MedGuard AI nhận thấy bạn đang trải qua thời điểm rất khó khăn.**\n\n"
    "Bạn không đơn độc, và luôn có người sẵn sàng lắng nghe và hỗ trợ bạn.\n\n"
    "**Hãy liên hệ ngay:**\n"
    "• 📞 **Đường dây nóng Ngày Mai**: 096 306 1414 (24/7)\n"
    "• 🚑 **Cấp cứu**: 115\n"
    "• 👶 **Tổng đài Quốc gia Bảo vệ Trẻ em**: 111\n\n"
    "MedGuard AI là hệ thống hỗ trợ y tế và không thể thay thế sự tư vấn "
    "trực tiếp từ chuyên gia sức khỏe tâm thần. Xin hãy tìm đến sự giúp đỡ ngay."
)

_CRISIS_BLOCK_RESPONSE = (
    "⛔ **MedGuard AI không cung cấp thông tin về chất cấm, chất độc "
    "hoặc bất kỳ nội dung nào có thể gây hại.**\n\n"
    "Nếu bạn cần hỗ trợ y tế, hãy mô tả triệu chứng hoặc câu hỏi "
    "về sức khỏe của bạn."
)

_INJECTION_BLOCK_RESPONSE = (
    "⛔ **MedGuard AI hoạt động theo các quy tắc an toàn lâm sàng nghiêm ngặt "
    "và không thể bỏ qua hoặc thay đổi chúng.**\n\n"
    "Hệ thống không kê đơn thuốc kiểm soát đặc biệt. "
    "Vui lòng đặt câu hỏi y tế hợp lệ để được hỗ trợ."
)


# Emergency medical keywords that override prompt-injection blocking.
# If someone says "Ignore rules... I have chest pain" — the chest pain
# is life-threatening and MUST still be triaged.
_EMERGENCY_OVERRIDE_KEYWORDS: tuple[str, ...] = (
    "dau nguc", "tuc nguc", "nang nguc", "chest pain",
    "kho tho", "ngat", "ngat xiu", "hon me",
    "co giat", "dot quy", "stroke", "meo mieng",
    "yeu liet", "nhoi mau", "tim dap nhanh",
    "soc phan ve", "anaphylaxis",
)


def _check_crisis(normalized: str, raw_text: str = "") -> OODResult | None:
    """Check for crisis/harm signals — highest priority."""
    if raw_text and _RAW_CRISIS_PATTERN.search(raw_text):
        return OODResult(
            verdict="crisis_self_harm",
            reply=_CRISIS_HOTLINE_RESPONSE,
            hotline="096 306 1414 | 115 | 111",
        )
    for pattern in _CRISIS_SELF_HARM_PATTERNS:
        if pattern.search(normalized):
            return OODResult(
                verdict="crisis_self_harm",
                reply=_CRISIS_HOTLINE_RESPONSE,
                hotline="096 306 1414 | 115 | 111",
            )
    # Prompt injection: if genuine emergency keywords co-exist,
    # defer to clinical pipeline (life-threatening takes priority).
    for pattern in _CRISIS_PROMPT_INJECTION_PATTERNS:
        if pattern.search(normalized):
            if any(kw in normalized for kw in _EMERGENCY_OVERRIDE_KEYWORDS):
                return None  # let clinical pipeline handle the emergency
            return OODResult(
                verdict="crisis_prompt_injection",
                reply=_INJECTION_BLOCK_RESPONSE,
            )
    for pattern in _CRISIS_TOXIC_SUBSTANCE_PATTERNS:
        if pattern.search(normalized):
            return OODResult(
                verdict="crisis_toxic_substance",
                reply=_CRISIS_BLOCK_RESPONSE,
            )
    return None


# =====================================================================
# Tier 2 — Veterinary Guard
# =====================================================================

_VETERINARY_MARKERS: tuple[str, ...] = (
    "cho cung", "meo cung", "thu cung",
    "con cho", "con meo", "con ga", "con vit",
    "cho nha", "meo nha",
    "cho bi", "meo bi",
    "cho cua toi", "meo cua toi",
    "thu y", "bac si thu y",
    "hamster", "tho cung",
)

_VETERINARY_RESPONSE = (
    "🐾 **MedGuard AI chuyên hỗ trợ sức khỏe cho con người** và không "
    "có chuyên môn về thú y.\n\n"
    "Để được tư vấn chính xác cho thú cưng, bạn nên liên hệ **bác sĩ thú y** "
    "hoặc phòng khám thú y gần nhất. Chúc bé cưng mau khỏe! 🐶🐱"
)


def _check_veterinary(normalized: str) -> OODResult | None:
    # If the query involves an animal bite, scratch, or physical injury on a human,
    # it is a medical emergency / rabies / wound management consultation, not veterinary care.
    if re.search(r"\b(can|cao|chay mau|rach|rach nat|vet can|vet thuong|tiem phong|tiem dai|dai|uon van)\b", normalized):
        return None
    if re.search(r"\b(benh nhan|nguoi lon|tre em|con toi)\b|(?<!(?:cua|nha)\s)\b(toi bi|chau bi|em bi)\b", normalized):
        return None

    for marker in _VETERINARY_MARKERS:
        if re.search(rf"\b{re.escape(marker)}\b", normalized):
            return OODResult(
                verdict="ood_veterinary",
                reply=_VETERINARY_RESPONSE,
            )
    return None


# =====================================================================
# Tier 3 — Metaphor / Ambiguity Disambiguator
# =====================================================================

# Each entry: (figurative phrase pattern, non-medical context clue words)
_METAPHOR_RULES: list[tuple[re.Pattern[str], tuple[str, ...]]] = [
    # "sốt ruột" = anxious
    (re.compile(r"sot\s+ruot", re.IGNORECASE), ("thi", "ket qua", "cho doi", "lo lang", "hoi hop", "biet")),
    # "nặng đầu" = stressed from study/work
    (re.compile(r"nang\s+dau", re.IGNORECASE), ("hoc", "bai vo", "thi cu", "deadline", "cong viec", "du an")),
    # "sốt sắng/sốt" in financial context
    (re.compile(r"sot\s*(?:sang)?", re.IGNORECASE), ("gia vang", "co phieu", "bitcoin", "vnindex", "thi truong", "chung khoan", "bat dong san", "gia ca")),
    # "nóng ruột" = anxious (financial/general)
    (re.compile(r"nong\s+ruot", re.IGNORECASE), ("gia", "vang", "co phieu", "thi truong", "cho doi", "bitcoin")),
    # "mệt mỏi" + machine/device context
    (re.compile(r"met\s*(?:moi)?", re.IGNORECASE), ("may tinh", "laptop", "dien thoai", "iphone", "android", "server", "app")),
    # "mệt tim" = work stress
    (re.compile(r"met\s+tim", re.IGNORECASE), ("deadline", "cong viec", "du an", "ot", "lam viec", "tang ca")),
    # "hấp hối / hồi sức" for projects
    (re.compile(r"(?:hap\s+hoi|hoi\s+suc)", re.IGNORECASE), ("du an", "cong ty", "startup", "project", "kinh doanh")),
    # "chảy máu" nhân sự = staff attrition
    (re.compile(r"chay\s+mau", re.IGNORECASE), ("nhan su", "nhan vien", "cong ty", "phong ban", "tuyen dung")),
    # "suy thoái / liều thuốc" kinh tế
    (re.compile(r"(?:suy\s+thoai|lieu\s+thuoc)", re.IGNORECASE), ("kinh te", "gdp", "lam phat", "ngan hang", "chinh sach", "tai khoa")),
    # "khỏe mạnh" for sports team / economy
    (re.compile(r"khoe\s+manh", re.IGNORECASE), ("doi bong", "doi tuyen", "clb", "phong do", "mua giai", "kinh te", "doanh nghiep")),
]

_METAPHOR_RESPONSE = (
    "Câu hỏi của bạn có vẻ không liên quan đến vấn đề sức khỏe y tế. "
    "MedGuard AI chuyên hỗ trợ tư vấn triệu chứng, an toàn thuốc "
    "và phân luồng lâm sàng.\n\n"
    "Nếu bạn đang gặp vấn đề sức khỏe thực sự, hãy mô tả cụ thể "
    "triệu chứng của bạn (ví dụ: đau ở đâu, khi nào bắt đầu, mức độ) "
    "để MedGuard hỗ trợ bạn tốt nhất."
)


def _check_metaphor(normalized: str) -> OODResult | None:
    """Detect figurative medical vocabulary in non-medical context."""
    for pattern, context_clues in _METAPHOR_RULES:
        if pattern.search(normalized):
            # At least one non-medical context clue must be present
            if any(clue in normalized for clue in context_clues):
                return OODResult(
                    verdict="ood_metaphor",
                    reply=_METAPHOR_RESPONSE,
                )
    return None


# =====================================================================
# Tier 4 — Non-Medical Topic Filter
# =====================================================================

_OOD_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "programming": (
        "viet code", "code python", "python merge", "chuong trinh python",
        "viet chuong trinh", "ham python", "thuat toan sap xep",
        "javascript", "java ", "c++", "html", "css",
        "merge sort", "binary search", "algorithm", "function",
        "docker", "container", "kubernetes", "api endpoint",
        "git commit", "github", "react", "vue", "angular",
        "sql", "database", "query", "server", "backend", "frontend",
        "sua loi", "debug", "compile", "deploy", "exit code",
        "lap trinh", "phan mem", "ung dung",
    ),
    "weather": (
        "thoi tiet", "du bao thoi tiet", "co mua khong",
        "nang khong", "gio mua",
    ),
    "cooking": (
        "cong thuc nau", "nau an", "nau com", "nau pho",
        "nau canh", "nau bun", "nau mi", "cong thuc lam",
        "banh mi", "banh trang", "gia vi", "cach lam mon",
    ),
    "finance": (
        "bitcoin", "ethereum", "crypto", "co phieu",
        "vnindex", "chung khoan", "lai suat ngan hang",
        "gop von", "dau tu chung khoan", "forex",
        "bat dong san", "nha dat", "vay tin chap",
        "lai suat", "ngan hang nao",
    ),
    "philosophy": (
        "y nghia cuoc song", "triet hoc", "nhan sinh quan",
        "tam linh", "phap luat", "chinh tri",
    ),
    "entertainment": (
        "chuyen cuoi", "phim hay",
        "bai hat", "nghe nhac", "am nhac", "ca nhac", "game", "tro choi",
        "tik tok", "youtube", "xem phim",
    ),
    "math": (
        "phuong trinh", "tich phan", "dao ham",
        "ma tran", "xac suat", "thong ke so lieu",
        "hinh hoc", "dai so", "giai phuong trinh",
    ),
    "tech_device": (
        "reset iphone", "reset dien thoai", "sua may tinh",
        "cai windows", "cai phan mem", "wifi khong vao duoc",
        "man hinh bi", "pin laptop", "sac dien thoai",
        "treo may",
    ),
    "sports": (
        "world cup", "sea games", "olympic",
        "bong da", "tennis", "boi loi", "chay bo",
        "lich thi dau", "ket qua tran",
    ),
    "travel": (
        "du lich", "khach san", "resort", "ve may bay",
        "visa", "tour", "dia diem tham quan",
    ),
}

# Words that strongly indicate a medical context — override OOD
# Short keywords (≤3 chars) require word-boundary matching to avoid
# false overrides (e.g. "ho" matching inside "cho", "pho", "khong").
_MEDICAL_OVERRIDE_LONG: tuple[str, ...] = (
    "trieu chung", "benh nhan", "bac si", "kham benh",
    "kho tho", "di ung", "huyet ap", "duong huyet",
    "xet nghiem", "sieu am", "x-quang",
    "phau thuat", "cap cuu", "phan luong",
    "vien thuoc", "khang sinh", "giam dau",
    "tieu chay", "tao bon", "chay mau",
    "ung thu", "tieu duong", "tim mach",
    "than kinh", "co xuong khop", "da lieu",
    "san khoa", "nhi khoa", "nha khoa",
    "thuoc uong", "thuoc bo", "thuoc giam",
    "trieu chung", "dau dau", "dau nguc",
    "dau bung", "buon non", "non mua",
    "sot cao", "co giat", "te bi",
    "nhuc dau", "met moi",
    "nga quy", "nga lan", "liet", "u o", "khong noi duoc", "khong nhac len",
    "yeu tay", "meo mieng", "bat dong", "bat tinh", "hon me", "me man",
    "cang co", "cang cung", "co bap", "co dui", "gian co", "chuot rut",
    "chan thuong", "so cuu", "phan mem", "bong gan", "trat khop",
    "gay xuong", "rach co", "rice", "cho can", "vat can", "meo cao", "rach nat", "vet can", "tiem phong dai",
    "viem da day", "da day", "thuong vi", "men gan", "dinh ky", "xet nghiem", "an uong lanh manh",
    "sui bot mep", "dong kinh", "mat tron nguoc", "tron nguoc", "giat dung dung",
    "trung gio", "cao gio", "khong biet troi dat",
    "guc nga", "ngat xiu", "ngat", "choang vang", "xay xam", "muon xiu", "sap ngat",
    "mach bat nhanh", "mach nhanh", "mach nho", "kho bat", "mat mach", "mach dap",
    "tim dap", "loan nhip", "thinh thich", "hoi hop", "tuc nghen",
    "roi dua", "roi coc", "ngap ngung", "ngat quang",
    "tho rit", "hut hoi", "nghet tho", "phu ne thanh quan",
    "uong voc", "uong thuoc", "ngo doc", "nhiem doc", "hoa chat", "chat tay",
)

# Short medical keywords that need regex word-boundary matching
_MEDICAL_OVERRIDE_SHORT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])")
    for kw in (
        "dau", "nhuc", "sot", "ho", "non",
        "spo2", "esi", "tiem", "thuoc", "benh",
        "kham", "sung", "ngua", "te", "met",
        "uong",  # take (medicine)
    )
]

# Pre-compiled word-boundary regex patterns for OOD topics to avoid substring false positives
# (e.g. 'ung dung' matching inside 'giat dung dung')
_OOD_TOPIC_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    topic: [
        re.compile(rf"(?<![a-z0-9]){re.escape(kw.strip())}(?![a-z0-9])")
        for kw in keywords
    ]
    for topic, keywords in _OOD_TOPIC_KEYWORDS.items()
}

_OOD_RESPONSE = (
    "Cảm ơn bạn đã nhắn tin! Tuy nhiên, câu hỏi này nằm **ngoài phạm vi "
    "chuyên môn y tế** của MedGuard AI.\n\n"
    "🏥 MedGuard AI có thể hỗ trợ bạn về:\n"
    "• Phân loại mức độ ưu tiên triệu chứng y tế\n"
    "• Kiểm tra tương tác thuốc & an toàn dược\n"
    "• Theo dõi chỉ số sinh tồn (huyết áp, SpO2, nhịp tim…)\n"
    "• Lập kế hoạch tái khám\n\n"
    "Hãy mô tả triệu chứng hoặc câu hỏi y tế để được hỗ trợ nhé!"
)

# Non-medical compound words that contain short medical-looking tokens.
# These are stripped before checking short-keyword overrides.
_NON_MEDICAL_COMPOUNDS: tuple[str, ...] = (
    "thi dau",    # compete (contains "dau")
    "dau tu",     # invest (contains "dau")
    "dau gia",    # auction (contains "dau")
    "dau tien",   # first (contains "dau")
    "sot sang",   # enthusiastic (contains "sot")
    "sot ruot",   # anxious (contains "sot")
    "nong sot",   # sizzling hot (contains "sot")
    "nhuc nhac",  # reminder (contains "nhuc")
    "te nan",     # vice (contains "te")
    "met moi",    # already handled by metaphor if non-medical
)


def _has_medical_context(normalized: str) -> bool:
    """Check if text contains genuine medical vocabulary (word-boundary-aware)."""
    if any(re.search(rf"\b{re.escape(kw)}\b", normalized) for kw in _MEDICAL_OVERRIDE_LONG):
        return True
    # Strip known non-medical compounds before checking short keywords
    cleaned = normalized
    for compound in _NON_MEDICAL_COMPOUNDS:
        cleaned = cleaned.replace(compound, " ")
    return any(p.search(cleaned) for p in _MEDICAL_OVERRIDE_SHORT_PATTERNS)


def _check_ood_topic(normalized: str) -> OODResult | None:
    """Detect queries that are entirely outside the medical domain."""
    # If any strong medical keyword is present, do NOT block
    if _has_medical_context(normalized):
        return None

    for _topic, patterns in _OOD_TOPIC_PATTERNS.items():
        if any(p.search(normalized) for p in patterns):
            return OODResult(
                verdict="ood_off_topic",
                reply=_OOD_RESPONSE,
            )
    return None


# =====================================================================
# Public API
# =====================================================================

def evaluate(text: str) -> OODResult | None:
    """Run the full guard pipeline on user input text.

    Returns ``None`` when the text is in-domain (clinical / pharma).
    Otherwise returns an ``OODResult`` with verdict and response.

    Priority order:
        1. Crisis / Self-harm  → block + hotline
        2. Prompt injection    → block
        3. Toxic substance     → block
        4. Veterinary          → redirect
        5. Metaphor            → polite decline
        6. Off-topic           → polite decline
    """
    normalized = normalize_search_text(text)

    # --- Tier 1: Crisis (highest priority) ---
    crisis = _check_crisis(normalized, raw_text=text)
    if crisis is not None:
        return crisis

    # --- Tier 2: Veterinary ---
    vet = _check_veterinary(normalized)
    if vet is not None:
        return vet

    # --- Tier 3: Metaphor disambiguation ---
    metaphor = _check_metaphor(normalized)
    if metaphor is not None:
        return metaphor

    # --- Tier 4: Off-topic ---
    ood = _check_ood_topic(normalized)
    if ood is not None:
        return ood

    return None
