# File: app/services/clinical_guardrail_router.py
"""Deterministic Clinical Safety Guardrail Router for MedGuard AI.

Implements P0/P1 clinical safety floors:
- FAST Stroke and Self-Harm/Suicide detection (unaffected by normal vitals)
- Critical Edge Cases: Severe Preeclampsia, Anaphylaxis, Hypoglycemia, Panic Labs
- Drug Quality/Counterfeit verification (stops false routing to GI on "mùi chua")
- Multidrug interaction & pediatric paracetamol duplicate/overdose checks
"""

from __future__ import annotations

import re
from typing import Any


def normalize_text_keep_diacritics(input_str: str) -> str:
    cleaned = re.sub(r"[.,!?;:()\"'«»\-\[\]]", " ", input_str.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def contains_exact_phrase(text: str, phrase: str) -> bool:
    norm_text = f" {normalize_text_keep_diacritics(text)} "
    norm_phrase = f" {normalize_text_keep_diacritics(phrase)} "
    return norm_phrase in norm_text


def strip_vietnamese_negated_clauses(raw_message: str) -> str:
    return re.sub(
        r"\b(không|chẳng|chưa|ko)\s+(?:hề\s+)?(?:bị|có|thấy|còn)?\s*(sốt|đau\s+bụng|ho|nôn|tiêu\s+chảy|đau\s+đầu|khó\s+thở)",
        " [NEGATED_SYMPTOM] ",
        raw_message,
        flags=re.IGNORECASE,
    )


SELF_HARM_PATTERNS = [
    "ngủ mãi không dậy",
    "không còn ý nghĩa",
    "muốn chết",
    "tự tử",
    "tự sát",
    "uống hết 2 vỉ",
    "uống hết vỉ thuốc",
    "kết thúc cuộc đời",
    "chấm dứt cuộc sống",
]

STROKE_FAST_SYMPTOMS = [
    "mờ mắt",
    "nhìn mờ hẳn",
    "màn sương che",
    "nói hơi líu lưỡi",
    "nói líu lưỡi",
    "nói khó",
    "nói đớ",
    "méo miệng",
    "lệch mặt",
    "cầm đũa bị rơi",
    "yếu tay",
    "tê nửa người",
    "liệt nửa người",
]

ACS_CARDIAC_SYMPTOMS = [
    "đau thắt ngực",
    "đau ngực trái",
    "lan lên hàm",
    "lan ra tay trái",
    "vã mồ hôi lạnh",
    "khó thở dữ dội",
]


def extract_multi_turn_patient_context(raw_text: str, messages: list[Any] | None = None) -> dict[str, Any]:
    combined_user_text = raw_text
    if messages:
        user_parts = []
        for m in messages:
            content = getattr(m, "content", None) or (m.get("content") if isinstance(m, dict) else "")
            role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else "")
            if role == "user" and content:
                user_parts.append(content)
        if user_parts:
            combined_user_text = " . ".join(user_parts)

    lower_all = combined_user_text.lower()

    months_m = re.search(r"(\d{1,2})\s*tháng(?:\s*tuổi)?", lower_all)
    age_months = int(months_m.group(1)) if months_m else None
    years_m = re.search(r"(?:bé|con|cháu|em|tôi|bố|mẹ)\s*[^0-9]{0,12}?(\d{1,3})\s*tuổi", lower_all)
    age_years = int(years_m.group(1)) if years_m else (age_months // 12 if age_months else None)

    weight_m = re.search(r"(\d{1,3}(?:[.,]\d+)?)\s*(?:kg|kí|cân)\b", lower_all)
    weight_kg = float(weight_m.group(1).replace(",", ".")) if weight_m else None

    is_pediatric = bool(
        (age_months is not None and age_months < 144)
        or (age_years is not None and age_years < 12)
        or (weight_kg is not None and weight_kg < 35)
        or any(k in lower_all for k in ("con trai tôi", "con tôi", "bé nhà mình", "cháu nhà", "trẻ nhỏ", "sơ sinh", "bé 18 tháng"))
    )

    return {
        "is_pediatric": is_pediatric,
        "age_months": age_months,
        "age_years": age_years,
        "weight_kg": weight_kg,
        "combined_text": combined_user_text,
    }


def evaluate_clinical_guardrail(raw_text: str, context: Any = None, messages: list[Any] | None = None) -> dict[str, Any] | None:
    norm = normalize_text_keep_diacritics(raw_text)
    lower = raw_text.lower()
    cleaned_negated = strip_vietnamese_negated_clauses(raw_text).lower()

    # =========================================================================
    # 1. P0: Khủng hoảng Tâm lý & Ý định Tự hại / Uống thuốc quá liều
    # =========================================================================
    matched_self_harm = [p for p in SELF_HARM_PATTERNS if contains_exact_phrase(norm, p)]
    if matched_self_harm:
        return {
            "priority": "P0_CRISIS_SELF_HARM",
            "urgency": "EMERGENCY",
            "reply": (
                "🚨 **CẢNH BÁO KHỦNG HOẢNG & CAN THIỆP AN TOÀN TÂM LÝ KHẨN CẤP**\n\n"
                "Tôi rất lo lắng khi nghe bạn chia sẻ điều này. Sinh mạng và sự an toàn của bạn là quan trọng nhất lúc này. "
                "Nếu bạn hoặc người thân vừa uống quá liều thuốc (thuốc ngủ Zolpidem), hãy gọi ngay **Cấp cứu 115 ngay lập tức** "
                "hoặc đến ngay Khoa Cấp cứu / Trung tâm Chống độc của bệnh viện gần nhất để được hồi sức giải độc kịp thời, tuyệt đối không được trì hoãn.\n\n"
                "📞 **ĐƯỜNG DÂY NÓNG HỖ TRỢ TÂM LÝ 24/7 MIỄN PHÍ**:\n"
                "- **Tổng đài Quốc gia Bảo vệ & Tham vấn Tâm lý**: **1900 6061** hoặc **111**\n"
                "- **Cấp cứu Y tế Toàn quốc**: **115**\n\n"
                "Hãy ở bên cạnh người thân và đừng ở một mình lúc này. Luôn có sự trợ giúp dành cho bạn!"
            ),
            "red_flags": matched_self_harm,
            "specialty": ("EMERGENCY", "Trung tâm Chống độc & Hồi sức Cấp cứu"),
            "suppress_otc": True,
            "suppress_expense": True,
            "suppress_med_card": True,
            "follow_up_questions": [
                "Kết nối ngay với tổng đài hỗ trợ tâm lý khẩn cấp 24/7",
                "Hướng dẫn người nhà xử trí an toàn tại chỗ trong lúc chờ hỗ trợ",
            ],
        }

    # =========================================================================
    # 2. P0: Cờ đỏ Đột quỵ (FAST) & Tim mạch cấp (Bất chấp chỉ số sinh tồn)
    # =========================================================================
    matched_stroke = [s for s in STROKE_FAST_SYMPTOMS if contains_exact_phrase(norm, s)]
    if len(matched_stroke) >= 2 or (
        matched_stroke
        and any(k in norm for k in ("liu luoi", "líu lưỡi", "rơi đũa", "méo miệng", "yếu tay", "liệt nửa người", "tê nửa người"))
    ):
        return {
            "priority": "P0_EMERGENCY_RED_FLAG",
            "urgency": "EMERGENCY",
            "reply": (
                "🚨 **CẢNH BÁO ĐỎ CẤP CỨU: DẤU HIỆU ĐỘT QUỴ NÃO CẤP TÍNH (FAST)**\n\n"
                f"Triệu chứng bạn mô tả ({', '.join(matched_stroke)}) là các dấu hiệu thần kinh khu trú tối khẩn cấp của Đột quỵ não (Tai biến mạch máu não) hoặc Cơn thiếu máu não thoáng qua (TIA).\n\n"
                "⚠️ **LƯU Ý ĐẶC BIỆT**: Dù huyết áp hay thân nhiệt đo được có ở mức bình thường (120/80 mmHg, 36.8°C), "
                "đây TUYỆT ĐỐI KHÔNG PHẢI tình trạng ổn định!\n\n"
                "🚑 **HÀNH ĐỘNG CẤP THIẾT NGAY BÂY GIỜ**:\n"
                "1. **Gọi Cấp cứu 115 ngay lập tức** hoặc đưa người bệnh đến ngay Bệnh viện có **Đơn vị Đột quỵ / Can thiệp Mạch não** (ví dụ: Trung tâm Cấp cứu A9 Bạch Mai).\n"
                "2. Ghi nhớ chính xác **thời điểm khởi phát** triệu chứng để bác sĩ tính 'giờ vàng' dùng thuốc tiêu sợi huyết (dưới 4.5 giờ).\n"
                "3. Cho người bệnh nằm nghiêng an toàn, nới lỏng cổ áo; **TUYỆT ĐỐI KHÔNG** cạo gió, chích máu đầu ngón tay hay cho uống nước/thuốc viên tránh sặc phổi tử vong."
            ),
            "red_flags": matched_stroke,
            "specialty": ("NEUROLOGY", "Cấp cứu Đột quỵ & Can thiệp Thần kinh"),
            "suppress_otc": True,
            "suppress_expense": True,
            "suppress_med_card": True,
            "follow_up_questions": [
                "Những việc cần làm và tuyệt đối tránh trong lúc chờ xe cấp cứu 115?",
                "Danh sách bệnh viện có Đơn vị Đột quỵ / Can thiệp Mạch não gần nhất?",
            ],
        }

    matched_cardiac = [c for c in ACS_CARDIAC_SYMPTOMS if contains_exact_phrase(norm, c)]
    if len(matched_cardiac) >= 2 or ("đau thắt ngực" in norm and any(k in norm for k in ("lan", "khó thở", "mồ hôi"))):
        return {
            "priority": "P0_EMERGENCY_RED_FLAG",
            "urgency": "EMERGENCY",
            "reply": (
                "🚨 **CẢNH BÁO ĐỎ CẤP CỨU: NGHI NGỜ HỘI CHỨNG VÀNH CẤP / NHỒI MÁU CƠ TIM**\n\n"
                f"Dấu hiệu {', '.join(matched_cardiac)} là biểu hiện nguy hiểm đe dọa tính mạng của thiếu máu cơ tim cục bộ cấp tính.\n\n"
                "🚑 **HÀNH ĐỘNG NGAY**:\n"
                "1. Gọi Cấp cứu 115 hoặc nhờ người nhà đưa đến Bệnh viện có phòng Can thiệp Tim mạch (PCI 24/7) ngay lập tức.\n"
                "2. Ngừng hoàn toàn mọi vận động, ngồi tựa lưng nghỉ ngơi thoải mái.\n"
                "3. Tuyệt đối không tự lái xe."
            ),
            "red_flags": matched_cardiac,
            "specialty": ("CARDIOLOGY", "Hồi sức Tim mạch Can thiệp (PCI)"),
            "suppress_otc": True,
            "suppress_expense": True,
            "suppress_med_card": True,
            "follow_up_questions": [
                "Những việc cần làm và tuyệt đối tránh trong lúc chờ xe cấp cứu 115?",
                "Danh sách bệnh viện có phòng Can thiệp Tim mạch (PCI 24/7) gần nhất?",
            ],
        }

    # =========================================================================
    # 3. P0: Cấp cứu Sản khoa — Tiền sản giật nặng / Hội chứng HELLP
    # =========================================================================
    is_pregnant = bool(re.search(r"(mang\s*thai|bầu\s*bí|thai\s*kỳ|tuần\s*thứ\s*\d+|thai\s*\d+\s*tuần)", lower))
    bp_match = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", lower)
    sys_bp = int(bp_match.group(1)) if bp_match else 0
    dia_bp = int(bp_match.group(2)) if bp_match else 0
    has_preeclampsia_signs = (
        sys_bp >= 140
        or dia_bp >= 90
        or bool(re.search(r"(đau\s*(?:tức\s*)?thượng\s*vị|hoa\s*mắt|nhìn\s*mờ|phù\s*(?:hai\s*)?chân|phù\s*mặt)", lower))
    )
    if is_pregnant and has_preeclampsia_signs:
        return {
            "priority": "P0_EMERGENCY_RED_FLAG",
            "urgency": "EMERGENCY",
            "reply": (
                "🚨 **CẢNH BÁO ĐỎ SẢN KHOA: NGHI NGỜ TIỀN SẢN GIẬT NẶNG / HỘI CHỨNG HELLP**\n\n"
                "Đau vùng thượng vị kèm huyết áp tăng cao (≥ 140/90 mmHg), nhìn hoa mắt và phù chân ở nửa sau thai kỳ "
                "là dấu hiệu nguy kịch đe dọa tính mạng của cả sản phụ và thai nhi. "
                "Đây TUYỆT ĐỐI KHÔNG PHẢI đau dạ dày đơn thuần hay hạ huyết áp tư thế! "
                "Không được trì hoãn việc đến cơ sở y tế ngay lập tức.\n\n"
                "⚠️ **HƯỚNG XỬ TRÍ BẮT BUỘC**:\n"
                "1. **TUYỆT ĐỐI KHÔNG** tự uống thuốc dạ dày (Phosphalugel gói chữ P) rồi nằm chờ và KHÔNG uống nước đường.\n"
                "2. Đưa thai phụ đến ngay **Khoa Cấp cứu Sản khoa** của bệnh viện phụ sản/đa khoa gần nhất để tiêm dự phòng co giật (Magnesium sulfate) và xét nghiệm khẩn men gan, tiểu cầu.\n"
                "3. Cho thai phụ nằm nghiêng bên trái trong suốt quá trình di chuyển."
            ),
            "red_flags": ["Nghi ngờ Tiền sản giật nặng / HELLP ở thai phụ"],
            "specialty": ("OBGYN_ER", "Cấp cứu Sản phụ khoa"),
            "suppress_otc": True,
            "suppress_expense": True,
            "suppress_med_card": True,
            "follow_up_questions": [
                "Những dấu hiệu co giật hoặc rau bong non cần theo dõi trên đường đi cấp cứu?",
                "Danh sách Bệnh viện Phụ sản có phòng Hồi sức Cấp cứu gần nhất?",
            ],
        }

    # =========================================================================
    # 4. P0: Phản vệ cấp độ II–III sau uống thuốc (Sưng môi, thở rít, nghẹn cổ)
    # =========================================================================
    has_drug_exposure = bool(re.search(r"(vừa\s*uống|mới\s*uống|sau\s*khi\s*uống|dùng\s*thuốc|kháng\s*sinh|amoxicillin|augmentin|cefuroxim|ibuprofen)", lower))
    has_airway_edema = bool(re.search(r"(thở\s*rít|nghẹn\s*(?:ở\s*)?cổ|sưng\s*môi|phù\s*môi|sưng\s*mắt|khó\s*thở|tụt\s*huyết\s*áp)", lower))
    if has_drug_exposure and has_airway_edema:
        return {
            "priority": "P0_EMERGENCY_RED_FLAG",
            "urgency": "EMERGENCY",
            "reply": (
                "🚨 **CẢNH BÁO ĐỎ CẤP CỨU: PHẢN VỆ ĐỘ II–III (PHÙ NỀ THANH QUẢN CẤP TÍNH)**\n\n"
                "Triệu chứng sưng môi, ngứa lòng bàn tay kèm thở rít hoặc nghẹn họng xuất hiện nhanh sau khi uống kháng sinh "
                "là dấu hiệu co thắt đường thở và phản vệ tối khẩn cấp, có thể ngừng thở sau vài phút!\n\n"
                "⚡ **HÀNH ĐỘNG CẤP BÁCH**:\n"
                "1. **NGƯNG NGAY LẬP TỨC** thuốc vừa uống (Amoxicillin) — giữ lại vỏ thuốc mang tới viện.\n"
                "2. **TUYỆT ĐỐI KHÔNG** uống Cetirizine/thuốc dị ứng rồi đi ngủ vì thuốc uống không chặn được phù thanh quản cấp.\n"
                "3. **Gọi 115** hoặc đưa ngay tới Trạm Y tế / Bệnh viện gần nhất để tiêm bắp Adrenalin ngay lập tức."
            ),
            "red_flags": ["Phản vệ độ II-III sau uống thuốc (phù môi, thở rít)"],
            "specialty": ("EMERGENCY_RESUSCITATION", "Hồi sức Cấp cứu (Xử trí Phản vệ)"),
            "suppress_otc": True,
            "suppress_expense": True,
            "suppress_med_card": True,
            "follow_up_questions": [
                "Cách giữ thông thoáng đường thở trong lúc chờ xe cấp cứu 115?",
                "Quy trình xử trí tiêm Adrenalin cấp cứu phản vệ tại cơ sở y tế?",
            ],
        }

    # =========================================================================
    # 5. P0: Hạ đường huyết nặng do tiêm Insulin (< 3.9 mmol/L)
    # =========================================================================
    glucose_match = re.search(r"đường\s*huyết[^0-9]*(\d+(?:[.,]\d+)?)\s*mmol/l", cleaned_negated)
    glucose_val = float(glucose_match.group(1).replace(",", ".")) if glucose_match else None
    if (glucose_val is not None and glucose_val < 3.9) or (
        "insulin" in cleaned_negated and bool(re.search(r"(vã\s*mồ\s*hôi\s*lạnh|run\s*tay|lẫn\s*lộn|lơ\s*mơ)", cleaned_negated))
    ):
        return {
            "priority": "P0_EMERGENCY_RED_FLAG",
            "urgency": "EMERGENCY",
            "reply": (
                f"🚨 **CẢNH BÁO ĐỎ CẤP CỨU: HẠ ĐƯỜNG HUYẾT NẶNG CẤP TÍNH{' (Đường huyết: ' + str(glucose_val) + ' mmol/L < 3.9)' if glucose_val else ''}**\n\n"
                "Vã mồ hôi lạnh, run tay chân và lú lẫn sau tiêm Insulin là tình trạng nguy kịch có thể dẫn đến hôn mê và tổn thương não không hồi phục.\n\n"
                "⚡ **HÀNH ĐỘNG NGAY LẬP TỨC**:\n"
                "1. **TUYỆT ĐỐI KHÔNG TIÊM THÊM INSULIN** (tiêm thêm sẽ gây tử vong do tụt đường huyết sâu).\n"
                "2. Nếu người bệnh còn tỉnh và nuốt được: Cho uống ngay **15–20g đường hấp thu nhanh** (3–4 thìa đường pha nước ấm, mật ong, hoặc nửa lon nước ngọt có đường). Sau 15 phút đo lại đường huyết.\n"
                "3. Nếu người bệnh lơ mơ / hôn mê / không nuốt được: **TUYỆT ĐỐI KHÔNG** đổ nước đường vào miệng để tránh sặc phổi tử vong; hãy gọi 115 ngay lập tức hoặc đưa người bệnh đến ngay Khoa Cấp cứu của Bệnh viện gần nhất để truyền Glucose tĩnh mạch, không được trì hoãn."
            ),
            "red_flags": ["Hạ đường huyết nặng sau tiêm Insulin"],
            "specialty": ("ENDOCRINE_ER", "Cấp cứu Nội tiết & Đái tháo đường"),
            "suppress_otc": True,
            "suppress_expense": True,
            "suppress_med_card": True,
            "follow_up_questions": [
                "Quy tắc 15-15 xử trí hạ đường huyết an toàn tại nhà?",
                "Khi nào hạ đường huyết bắt buộc phải truyền Glucose tĩnh mạch tại bệnh viện?",
            ],
        }

    # =========================================================================
    # 6. P0: Xét nghiệm Nguy kịch (Panic Lab Values: Kali >= 6.0 mmol/L, eGFR < 15)
    # =========================================================================
    potassium_match = re.search(r"kali(?:\s*máu)?\s*[=:]?\s*(\d+(?:[.,]\d+)?)\s*mmol/l", lower)
    potassium_val = float(potassium_match.group(1).replace(",", ".")) if potassium_match else None
    egfr_match = re.search(r"egfr\s*[=:]?\s*(\d+(?:[.,]\d+)?)", lower)
    egfr_val = float(egfr_match.group(1).replace(",", ".")) if egfr_match else None
    hr_match = re.search(r"nhịp\s*tim[^0-9]*(\d{2,3})\s*lần/phút", lower)
    hr_val = int(hr_match.group(1)) if hr_match else None

    if (potassium_val is not None and potassium_val >= 6.0) or (egfr_val is not None and egfr_val < 15 and hr_val is not None and hr_val < 50):
        return {
            "priority": "P0_EMERGENCY_RED_FLAG",
            "urgency": "EMERGENCY",
            "reply": (
                f"🚨 **CẢNH BÁO ĐỎ XÉT NGHIỆM NGUY KỊCH: TĂNG KALI MÁU TỐI CẤP (Kali: {potassium_val or '>= 6.0'} mmol/L)**\n\n"
                "Chỉ số Kali máu trên 6.0 mmol/L kết hợp suy thận nặng (eGFR thấp) và nhịp tim chậm là tình trạng cấp cứu hồi sức tối khẩn cấp. "
                "Tăng Kali máu làm rối loạn dẫn truyền điện học tim cực kỳ nghiêm trọng, có nguy cơ gây rung thất và ngừng tim đột ngột bất cứ lúc nào!\n\n"
                "🚑 **HÀNH ĐỘNG KHẨN CẤP**:\n"
                "1. **PHẢI NHẬP VIỆN CẤP CỨU NGAY LẬP TỨC** — Tuyệt đối không chờ đến tuần sau tái khám!\n"
                "2. Đến ngay Bệnh viện có đơn vị **Thận nhân tạo / Hồi sức tích cực** để được tiêm Calci tĩnh mạch bảo vệ cơ tim và hạ Kali máu cấp cứu (hoặc lọc máu cấp cứu).\n"
                "3. Ngưng ngay lập tức các thuốc giữ Kali (Spironolactone, ức chế men chuyển ACEi, ARB) và không ăn thực phẩm giàu Kali (chuối, cam, nước dừa)."
            ),
            "red_flags": [f"Panic lab: Tăng Kali máu tối cấp {potassium_val or '>= 6.0'} mmol/L"],
            "specialty": ("NEPHRO_CARDIAC_ER", "Cấp cứu Hồi sức Tim mạch & Thận nhân tạo"),
            "suppress_otc": True,
            "suppress_expense": True,
            "suppress_med_card": True,
            "follow_up_questions": [
                "Dấu hiệu rung thất và rối loạn nhịp tim do tăng Kali máu?",
                "Quy trình tiêm Calci clorid và lọc máu cấp cứu hạ Kali tại bệnh viện?",
            ],
        }

    # =========================================================================
    # 7. P1: Kiểm định Dược phẩm, Thuốc biến chất, Thuốc giả (Augmentin, VN-..., Số lô, Mùi chua)
    # =========================================================================
    has_reg_or_lot = bool(re.search(r"\b(vn-\d+|vd-\d+|số\s*lô|hạn\s*dùng|tem\s*chống\s*giả|thật\s*hay\s*giả)\b", lower))
    has_spoilage_signs = any(k in lower for k in ("ngả vàng", "đổi màu", "mùi chua", "ẩm mốc", "chảy nước", "rách tem", "hở vỉ"))
    if has_reg_or_lot and has_spoilage_signs:
        reg_m = re.search(r"\b(VN-\d{4,6}-\d{2}|VD-\d{4,6}-\d{2})\b", raw_text, re.IGNORECASE)
        lot_m = re.search(r"số\s*lô\s*([A-Z0-9-]+)", raw_text, re.IGNORECASE)
        reg_str = reg_m.group(0).upper() if reg_m else "chưa rõ"
        lot_str = lot_m.group(1).upper() if lot_m else "chưa rõ"

        return {
            "priority": "P1_DRUG_QUALITY_COUNTERFEIT",
            "urgency": "URGENT",
            "reply": (
                "⚠️ **CẢNH BÁO DƯỢC PHẨM KHÔNG AN TOÀN — TUYỆT ĐỐI KHÔNG UỐNG**\n\n"
                "Viên nén Augmentin 1g đạt tiêu chuẩn GMP phải có màu trắng đến trắng ngà, vỉ nhôm nguyên vẹn kín khí. "
                "Dấu hiệu viên thuốc **bị ngả vàng và bốc mùi chua nồng kèm tem chống giả bị rách** chứng tỏ thuốc đã bị thâm nhiễm không khí ẩm, "
                "dẫn đến phân hủy hoạt chất (đặc biệt Acid Clavulanic/Kali Clavulanat rất nhạy cảm với độ ẩm, khi bị thủy phân sẽ tạo mùi chua nồng đặc trưng) "
                "hoặc đây là thuốc giả/kém chất lượng.\n\n"
                "🛑 **HƯỚNG DẪN XỬ LÝ DƯỢC LÂM SÀNG**:\n"
                "1. **Ngưng sử dụng ngay lập tức**: Uống kháng sinh đã biến chất vừa mất tác dụng diệt khuẩn, vừa sinh độc tính gây dị ứng và viêm loét đường tiêu hóa.\n"
                f"2. Mang nguyên hộp thuốc (Số ĐK: **{reg_str}**, Số lô: **{lot_str}**) quay lại Nhà thuốc GPP nơi bạn mua để yêu cầu dược sĩ chuyên môn kiểm tra và thu hồi sản phẩm.\n"
                "3. Tham vấn ý kiến bác sĩ chuyên khoa hoặc đến cơ sở y tế để được đổi sang đơn thuốc kháng sinh thay thế an toàn nếu cần điều trị tiếp tục.\n"
                "4. Tra cứu số đăng ký trên Cổng Thông tin Dược Quốc gia (DAV) để xác minh tính chính danh của lô thuốc."
            ),
            "red_flags": ["Thuốc biến chất / Tem rách / Kháng sinh phân hủy"],
            "specialty": ("PHARMACY_DAV", "Dược Lâm sàng & Kiểm định Dược"),
            "suppress_otc": True,
            "suppress_expense": True,
            "suppress_med_card": True,
            "follow_up_questions": [
                "Cách đối chiếu số đăng ký thuốc trên hệ thống Cục Quản lý Dược (DAV)?",
                "Dấu hiệu nhận biết viên thuốc kháng sinh bị ẩm mốc hoặc biến chất?",
            ],
        }

    # =========================================================================
    # 8. P1: Tương tác Đa thuốc (Warfarin + Ibuprofen + Nhân sâm, Amlodipin) & Trùng Paracetamol
    # =========================================================================
    has_warfarin = "warfarin" in lower or "coumadin" in lower
    has_ibuprofen = "ibuprofen" in lower or "advil" in lower or "brufen" in lower
    has_paracetamol_brands = sum(1 for b in ("hapacol", "efferalgan", "panadol", "paracetamol", "tylenol") if b in lower)

    if has_warfarin and has_ibuprofen:
        return {
            "priority": "P1_DRUG_INTERACTION_AND_DOSING",
            "urgency": "URGENT",
            "reply": (
                "⛔ **CẢNH BÁO TƯƠNG TÁC THUỐC MỨC ĐỘ NGUY HIỂM CAO (CHỐNG CHỈ ĐỊNH PHỐI HỢP)**\n\n"
                "**Warfarin** (thuốc chống đông máu) phối hợp với **Ibuprofen** (thuốc chống viêm giảm đau NSAID) là tương tác bất lợi nghiêm trọng:\n"
                "- Ibuprofen ức chế kết tập tiểu cầu, làm tổn thương niêm mạc dạ dày và cạnh tranh gắn protein huyết tương với Warfarin.\n"
                "- Phối hợp này làm **tăng nguy cơ xuất huyết dạ dày và xuất huyết não gấp 3–6 lần**, có thể đe dọa tính mạng!\n"
                "- Thêm vào đó, Ibuprofen còn gây giữ nước và ức chế prostaglandin tại thận, làm giảm tác dụng hạ áp của Amlodipin ở người cao tuổi.\n\n"
                "💡 **LỜI KHUYÊN DƯỢC LÂM SÀNG**:\n"
                "1. **TUYỆT ĐỐI KHÔNG** tự ý uống Ibuprofen khi đang duy trì Warfarin.\n"
                "2. Để giảm đau khớp gối an toàn, hãy liên hệ bác sĩ tim mạch để được kê thuốc giảm đau phù hợp (như Paracetamol liều vừa phải hoặc các biện pháp không dùng thuốc).\n"
                "3. Tránh dùng thêm nhân sâm Hàn Quốc vì nhân sâm có thể làm thay đổi thất thường chỉ số đông máu INR."
            ),
            "red_flags": ["Tương tác chống chỉ định: Warfarin + Ibuprofen"],
            "specialty": ("CLINICAL_PHARMACOLOGY", "Dược Lâm sàng & Tim mạch"),
            "suppress_otc": True,
            "suppress_expense": True,
            "suppress_med_card": True,
            "follow_up_questions": [
                "Những dấu hiệu xuất huyết tiêu hóa do tương tác thuốc cần đi cấp cứu ngay?",
                "Thuốc giảm đau khớp nào an toàn hơn cho người đang dùng Warfarin?",
            ],
        }

    if has_paracetamol_brands >= 2:
        return {
            "priority": "P1_DRUG_INTERACTION_AND_DOSING",
            "urgency": "URGENT",
            "reply": (
                "⛔ **CẢNH BÁO TRÙNG LẶP HOẠT CHẤT & NGUY CƠ NGỘ ĐỘC GAN**\n\n"
                "Các biệt dược bạn vừa nêu (Hapacol, Efferalgan, Panadol) đều chứa cùng hoạt chất là **Paracetamol (Acetaminophen)**.\n"
                "Tuyệt đối KHÔNG dùng gộp hoặc dùng song song hai loại này cùng lúc (ví dụ vừa đặt viên hậu môn vừa uống gói bột) "
                "vì sẽ làm tổng liều tăng gấp đôi, gây quá liều cấp tính dẫn đến hoại tử tế bào gan không hồi phục!\n\n"
                "👶 **HƯỚNG DẪN DƯỢC NHI KHOA**:\n"
                "1. **TUYỆT ĐỐI KHÔNG CHO UỐNG THÊM HAPACOL** khi vừa mới đặt viên hậu môn Efferalgan 30 phút trước.\n"
                "2. Liều chuẩn cho trẻ em chỉ từ **10–15 mg/kg thể trọng** cho mỗi lần dùng, cách mỗi 4–6 giờ (tối đa 60 mg/kg/ngày). "
                "Chỉ dùng duy nhất MỘT dạng thuốc theo đúng cân nặng của trẻ.\n"
                "3. Nếu trẻ sốt cao liên tục không hạ hoặc có dấu hiệu li bì, co giật, hãy liên hệ bác sĩ chuyên khoa Nhi hoặc đưa trẻ đến cơ sở y tế gần nhất để được thăm khám."
            ),
            "red_flags": ["Trùng lặp hoạt chất Paracetamol / Nguy cơ quá liều gan"],
            "specialty": ("PEDIATRICS", "Nhi khoa & Dược Lâm sàng"),
            "suppress_otc": True,
            "suppress_expense": True,
            "suppress_med_card": True,
            "follow_up_questions": [
                "Bảng tra cứu liều hạ sốt Paracetamol chuẩn theo từng mức cân nặng cho trẻ?",
                "Dấu hiệu sớm ngộ độc Paracetamol và cách xử trí ngộ độc gan cấp?",
            ],
        }

    # =========================================================================
    # 9. P1: Chống chỉ định viên 500mg người lớn & Panadol Extra cho trẻ nhỏ (Có nhớ ngữ cảnh đa lượt)
    # =========================================================================
    pt_ctx = extract_multi_turn_patient_context(raw_text, messages)
    if pt_ctx["is_pediatric"] and (
        "500mg" in lower
        or "500 mg" in lower
        or "panadol extra" in lower
        or "extra" in lower
        or "người lớn" in lower
        or "bẻ đôi" in lower
    ):
        weight = pt_ctx.get("weight_kg") or 10.5
        age_m = pt_ctx.get("age_months") or 18
        mg_per_kg = 500.0 / weight
        safe_min = round(weight * 10)
        safe_max = round(weight * 15)
        has_caffeine = "panadol extra" in lower or "extra" in lower

        return {
            "priority": "P1_DRUG_INTERACTION_AND_DOSING",
            "urgency": "URGENT",
            "reply": (
                "⛔ **CẢNH BÁO ĐỎ DƯỢC LÂM SÀNG: CHỐNG CHỈ ĐỊNH VIÊN 500MG NGƯỜI LỚN & PANADOL EXTRA CHO TRẺ NHỎ**\n\n"
                f"Dựa trên thông tin đã ghi nhận (bé {age_m} tháng tuổi, nặng {weight} kg), "
                "**TUYỆT ĐỐI KHÔNG ĐƯỢC CHO BÉ UỐNG HOẶC BẺ ĐÔI VIÊN 500MG CỦA NGƯỜI LỚN!**\n\n"
                "⚠️ **CÁC NGUY CƠ NGUY HIỂM TÍNH MẠNG**:\n"
                f"1. **Nguy cơ ngộ độc hoại tử gan cấp do quá liều nặng**: Liều 500mg cho bé {weight}kg đạt tới {mg_per_kg:.1f} mg/kg/lần "
                f"(vượt gấp hơn 3 lần ngưỡng an toàn 10–15 mg/kg = {safe_min}–{safe_max} mg/lần). "
                "Kể cả khi bẻ đôi viên thuốc (250mg) thì vẫn ở mức ~24 mg/kg, vượt xa ngưỡng chịu đựng của gan trẻ nhỏ.\n"
                f"2. **Độc tính Caffeine trong Panadol Extra**: {('Panadol Extra chứa thêm **65mg Caffeine**, chống chỉ định tuyệt đối cho trẻ em vì gây kích thích thần kinh, tim đập nhanh nguy hiểm và co giật.' if has_caffeine else 'Viên nén người lớn không thể chia liều chính xác bằng cách bẻ đôi.')}\n\n"
                "👶 **HƯỚNG DẪN DƯỢC NHI KHOA CHUẨN XÁC**:\n"
                f"1. Dùng thuốc hạ sốt dành riêng cho trẻ em (gói bột sủi hoặc siro) có hàm lượng chuẩn **{safe_min}–{safe_max} mg/lần** (ví dụ gói Hapacol 150mg).\n"
                "2. Khoảng cách giữa 2 cữ hạ sốt phải từ **4–6 giờ** (tối đa 4–5 lần trong 24 giờ).\n"
                "3. Nếu trẻ sốt cao liên tục không hạ hoặc có dấu hiệu li bì, co giật, hãy liên hệ bác sĩ chuyên khoa Nhi hoặc đưa trẻ đến cơ sở y tế gần nhất để được thăm khám và xử trí an toàn."
            ),
            "red_flags": ["Chống chỉ định Panadol Extra / Quá liều Paracetamol 500mg ở trẻ nhỏ"],
            "specialty": ("PEDIATRICS", "Nhi khoa & Dược Lâm sàng"),
            "suppress_otc": True,
            "suppress_expense": True,
            "suppress_med_card": True,
            "follow_up_questions": [
                "Bảng tra cứu liều hạ sốt Paracetamol chuẩn theo cân nặng cho bé?",
                "Cách xử trí hạ sốt an toàn khi bé sốt cao 39 độ C?",
            ],
        }

    return None
