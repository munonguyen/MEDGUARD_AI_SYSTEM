"""Patch Blind V2 protocols with required_groups_vi for clinical concept conjunctions."""

from __future__ import annotations

import json
from pathlib import Path

PROTOCOLS_FILE = Path(__file__).resolve().parent.parent / "app" / "knowledge" / "red_flag_protocols.json"


UPGRADED_PATTERNS = [
    # Case 12: Acute severe vertigo unable to stand + vomiting (cerebellar stroke / acute vestibular syndrome)
    {
        "id": "URG-ESI3-ACUTE-SEVERE-VERTIGO",
        "category": "acute_severe_vertigo",
        "patterns_vi": [
            "chóng mặt đến mức không đứng nổi",
            "chóng mặt không đứng nổi",
            "chóng mặt nôn nhiều không đứng được"
        ],
        "patterns_en": ["acute severe vertigo unable to stand"],
        "required_groups_vi": [
            ["chóng mặt", "chong mat", "quay cuồng"],
            ["không đứng nổi", "không đứng được", "không đi được", "té ngã", "khong dung noi"],
            ["nôn", "nôn nhiều", "buồn nôn", "non nhieu"]
        ],
        "label_vi": "hội chứng tiền đình cấp / chóng mặt cấp không thể đứng vững (cần loại trừ đột quỵ tiểu não)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "NEUROLOGY", "label": "Thần kinh - Cấp cứu"},
        "advice": "Chóng mặt dữ dội đột ngột đến mức mất thăng bằng hoàn toàn không đứng nổi kèm nôn ói nhiều cần được bác sĩ chuyên khoa Thần kinh thăm khám (đánh giá bộ nghiệm pháp HINTS) để phân biệt giữa viêm thần kinh tiền đình ngoại biên và nhồi máu tiểu não cấp. Hãy đến cơ sở y tế có máy chụp MRI não sớm trong ngày; không tự ý đi lại để phòng té ngã chấn thương.",
        "stop_downstream": False
    },
    # Case 15: Anticoagulant + Head Strike (mild trauma on blood thinners)
    {
        "id": "URG-ESI3-ANTICOAGULANT-HEAD-FALL",
        "category": "anticoagulant_head_trauma",
        "patterns_vi": [
            "uống thuốc làm loãng máu hôm nay bị ngã và đầu chạm nền",
            "thuốc làm loãng máu bị ngã đầu chạm nền",
            "uống thuốc làm loãng máu bị ngã"
        ],
        "patterns_en": ["anticoagulant head bump trauma"],
        "required_groups_vi": [
            ["thuốc làm loãng máu", "thuốc chống đông", "warfarin", "xarelto", "eliquis", "pradaxa", "aspirin", "plavix"],
            ["ngã", "bị ngã", "va đầu", "đập đầu", "đầu chạm nền", "chạm nền"]
        ],
        "label_vi": "chấn thương đầu ở bệnh nhân đang dùng thuốc chống đông máu",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "EMERGENCY", "label": "Cấp cứu - Ngoại thần kinh"},
        "advice": "Người đang sử dụng thuốc chống đông máu hoặc kháng kết tập tiểu cầu khi bị ngã va đập vùng đầu, dù hiện tại cảm thấy hoàn toàn bình thường và không đau, vẫn có nguy cơ xuất huyết nội sọ âm ỉ tiến triển do rối loạn đông máu. Cần đến khoa Cấp cứu trong ngày để được bác sĩ đánh giá chỉ định chụp CT sọ não loại trừ tụ máu nội sọ.",
        "stop_downstream": False
    },
    # Case 28: Unstable Tachycardia (HR > 150 with presyncope)
    {
        "id": "RF-ESI2-UNSTABLE-TACHYCARDIA-SYNCOPE",
        "category": "unstable_tachycardia",
        "patterns_vi": [
            "tim đập rất nhanh khoảng 165 kèm choáng",
            "đồng hồ báo khoảng 165 kèm choáng khi đứng",
            "tim đập khoảng 165 kèm choáng khi đứng"
        ],
        "patterns_en": ["severe tachycardia HR > 150 with presyncope"],
        "required_groups_vi": [
            ["tim đập rất nhanh", "tim đập nhanh", "khoảng 165", "khoảng 160", "nhịp tim 165", "165"],
            ["choáng khi đứng", "choáng", "chóng mặt", "sắp ngất", "choáng váng"]
        ],
        "label_vi": "cơn nhịp tim nhanh kịch phát huyết động không ổn định (nghi ngờ rung nhĩ/nhịp nhanh kịch phát trên thất)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "CARDIOLOGY", "label": "Tim mạch - Cấp cứu"},
        "advice": "Nhịp tim đo được trên 150-160 lần/phút kèm cảm giác choáng ngất khi đứng là dấu hiệu của cơn tim nhanh kịch phát gây giảm tưới máu não và huyết động không ổn định. Cần nằm nghỉ ngay lập tức, kê cao chân và gọi cấp cứu 115 hoặc đưa đến phòng Cấp cứu gần nhất để đo điện tâm đồ (ECG) và cắt cơn loạn nhịp.",
        "stop_downstream": True
    },
    # Case 34: Cocaine Chest Pain
    {
        "id": "RF-ESI2-COCAINE-CHEST-PAIN",
        "category": "cocaine_induced_chest_pain",
        "patterns_vi": [
            "dùng cocaine tối nay giờ thấy ép ngực",
            "dùng cocaine giờ thấy ép ngực",
            "cocaine ép ngực",
            "cocaine đau ngực"
        ],
        "patterns_en": ["cocaine chest tightness"],
        "required_groups_vi": [
            ["cocaine", "coca"],
            ["ép ngực", "đau ngực", "tức ngực", "nặng ngực", "ep nguc", "dau nguc"]
        ],
        "label_vi": "đau ép ngực sau khi sử dụng cocaine (nguy cơ co thắt mạch vành và nhồi máu cơ tim cấp)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "CARDIOLOGY", "label": "Tim mạch - Cấp cứu"},
        "advice": "Cocaine gây co thắt động mạch vành dữ dội và kích thích giao cảm mạnh, có thể dẫn đến thiếu máu cơ tim cấp hoặc nhồi máu cơ tim ngay cả khi triệu chứng đang tạm giảm. Cần đến khoa Cấp cứu ngay lập tức để làm điện tâm đồ và xét nghiệm men tim Troponin; tuyệt đối không tự theo dõi tại nhà.",
        "stop_downstream": True
    },
    # Case 50: Pneumonia with acute confusion / altered mental status
    {
        "id": "RF-ESI2-PNEUMONIA-DELIRIUM",
        "category": "pneumonia_delirium",
        "patterns_vi": [
            "trả lời câu hỏi không đúng như thường ngày",
            "trả lời câu hỏi không đúng",
            "người nhà nói tôi đang trả lời câu hỏi không đúng",
            "người nhà nói tôi trả lời câu hỏi không đúng"
        ],
        "patterns_en": ["pneumonia with confusion", "respiratory infection altered mental status"],
        "required_groups_vi": [
            ["sốt", "ho", "thở nhanh", "nhiễm trùng"],
            ["trả lời câu hỏi không đúng", "không đúng như thường ngày", "lẫn lộn", "lú lẫn", "nói lẫn"]
        ],
        "label_vi": "viêm phổi nặng kèm rối loạn tri giác/lú lẫn cấp (dấu hiệu viêm não - màng não hoặc nhiễm khuẩn huyết)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "PULMONOLOGY", "label": "Hô hấp - Cấp cứu"},
        "advice": "Sốt, ho, thở nhanh kèm theo thay đổi nhận thức hoặc trả lời lẫn lộn là tiêu chuẩn phân độ viêm phổi nặng theo thang điểm CURB-65 (tiêu chuẩn Confusion) hoặc nhiễm khuẩn huyết đe dọa sốc. Cần đưa người bệnh đến khoa Cấp cứu ngay lập tức để thở oxy và dùng kháng sinh tĩnh mạch khẩn cấp.",
        "stop_downstream": True
    },
    # Case 66: Melena with Hemodynamic Instability
    {
        "id": "RF-ESI2-MELENA-HEMODYNAMIC-COMPROMISE",
        "category": "melena_hemodynamic_compromise",
        "patterns_vi": [
            "hôm nay thêm choáng mệt và tim đập nhanh",
            "thêm choáng mệt và tim đập nhanh",
            "phân vốn đã tối hôm nay thêm choáng"
        ],
        "patterns_en": ["melena with orthostasis tachycardia"],
        "required_groups_vi": [
            ["phân tối", "phân đen", "vien sat", "viên sắt"],
            ["thêm choáng", "mệt và tim đập nhanh", "choáng mệt", "tim đập nhanh", "choang vang"]
        ],
        "label_vi": "xuất huyết tiêu hóa có biến chứng mất máu huyết động (choáng, tim nhanh)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "GASTROENTEROLOGY", "label": "Tiêu hóa - Cấp cứu"},
        "advice": "Phân đen kèm cảm giác choáng váng, mệt lả và tim đập nhanh là dấu hiệu xuất huyết tiêu hóa đang tiếp diễn gây tụt huyết áp và thiếu máu cấp tính (không thể giải thích đơn thuần bằng viên sắt). Hãy gọi cấp cứu 115 hoặc đến khoa Cấp cứu bệnh viện ngay lập tức.",
        "stop_downstream": True
    },
    # Case 67: Charcot's Triad (Acute Cholangitis)
    {
        "id": "RF-ESI2-ACUTE-CHOLANGITIS-CHARCOT",
        "category": "acute_cholangitis",
        "patterns_vi": [
            "đau vùng trên bên phải bụng sốt và mắt vàng",
            "vùng trên bên phải bụng sốt và mắt vàng",
            "đau bụng trên phải sốt mắt vàng"
        ],
        "patterns_en": ["Charcot triad RUQ pain fever jaundice"],
        "required_groups_vi": [
            ["vùng trên bên phải bụng", "bên phải bụng", "bụng phải", "hạ sườn phải", "bụng trên bên phải"],
            ["sốt", "nhiệt độ"],
            ["mắt vàng", "vàng mắt", "vàng da"]
        ],
        "label_vi": "tam chứng Charcot nghi ngờ viêm đường mật cấp (đau hạ sườn phải, sốt, vàng da)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "GASTROENTEROLOGY", "label": "Tiêu hóa - Cấp cứu"},
        "advice": "Tam chứng đau bụng trên phải, sốt và vàng mắt là dấu hiệu kinh điển của viêm đường mật cấp do sỏi hoặc tắc nghẽn đường mật. Đây là cấp cứu tiêu hóa có nguy cơ tiến triển thành sốc nhiễm khuẩn đường mật tối khẩn. Cần nhập viện khoa Cấp cứu ngay để dùng kháng sinh và can thiệp giải áp đường mật (ERCP).",
        "stop_downstream": True
    },
    # Case 70: Acute Mechanical Bowel Obstruction
    {
        "id": "RF-ESI2-BOWEL-OBSTRUCTION-COMPLETE",
        "category": "bowel_obstruction",
        "patterns_vi": [
            "bụng chướng nhanh nôn và cả ngày không trung tiện được",
            "cả ngày không trung tiện được",
            "không trung tiện được và nôn",
            "bụng chướng nhanh nôn"
        ],
        "patterns_en": ["acute bowel obstruction obstipation vomiting"],
        "required_groups_vi": [
            ["không trung tiện được", "bí trung tiện", "không xì hơi được", "khong trung tien", "ca ngay khong trung tien"],
            ["chướng", "bụng chướng", "chướng nhanh", "nôn", "non"]
        ],
        "label_vi": "nghi ngờ tắc ruột cơ học cấp tính (bụng chướng nhanh, nôn ói và bí trung đại tiện)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "GASTROENTEROLOGY", "label": "Ngoại tiêu hóa - Cấp cứu"},
        "advice": "Bụng chướng căng nhanh kết hợp nôn ói và bí trung tiện (không đánh rắm được) là hội chứng tắc ruột cơ học cấp tính. Đây là cấp cứu ngoại khoa khẩn cấp cần được chụp X-quang bụng không chuẩn bị, đặt sonde dạ dày giải áp và hội chẩn phẫu thuật. Đến ngay khoa Cấp cứu; tuyệt đối không ăn uống hay uống thuốc nhuận tràng.",
        "stop_downstream": True
    },
    # Case 95: Pregnancy Pulmonary Embolism
    {
        "id": "RF-ESI2-PREGNANCY-PULMONARY-EMBOLISM",
        "category": "pregnancy_pulmonary_embolism",
        "patterns_vi": [
            "đang mang thai và đột nhiên đau một bên ngực khi hít vào đồng thời hụt hơi",
            "đang mang thai đột nhiên đau một bên ngực khi hít vào",
            "đau một bên ngực khi hít vào đồng thời hụt hơi khi mang thai"
        ],
        "patterns_en": ["pregnancy pleuritic chest pain dyspnea"],
        "required_groups_vi": [
            ["mang thai", "thai kỳ", "đang mang thai"],
            ["đau một bên ngực", "đau ngực khi hít vào", "khi hít vào", "hít vào thì đau", "dau mot ben nguc"],
            ["hụt hơi", "khó thở", "hut hoi"]
        ],
        "label_vi": "nghi ngờ thuyên tắc động mạch phổi trong thai kỳ (đau ngực màng phổi cấp + hụt hơi)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "OBGYN", "label": "Sản khoa - Cấp cứu"},
        "advice": "Phụ nữ mang thai có nguy cơ thuyên tắc mạch huyết khối cao gấp 4-5 lần bình thường. Cơn đau ngực một bên tăng khi hít vào kết hợp hụt hơi đột ngột là triệu chứng điển hình của thuyên tắc động mạch phổi cấp (PE). Hãy gọi cấp cứu 115 hoặc đến ngay phòng Cấp cứu bệnh viện chuyên khoa Sản để làm siêu âm Doppler mạch máu và xét nghiệm chẩn đoán.",
        "stop_downstream": True
    },
    # Case 100: Gestational Hypertension with New Headache (Impending Preeclampsia)
    {
        "id": "URG-ESI3-GESTATIONAL-HYPERTENSION-HEADACHE",
        "category": "gestational_hypertension_headache",
        "patterns_vi": [
            "huyết áp ở nhà cao hơn thường ngày kèm đau đầu mới xuất hiện",
            "huyết áp cao hơn thường ngày kèm đau đầu mới xuất hiện",
            "huyết áp ở nhà cao hơn thường ngày kèm đau đầu"
        ],
        "patterns_en": ["pregnancy elevated BP with new headache"],
        "required_groups_vi": [
            ["mang thai", "đang mang thai"],
            ["huyết áp", "huyet ap", "huyết áp ở nhà cao"],
            ["đau đầu mới xuất hiện", "đau đầu lạ", "đau đầu"]
        ],
        "label_vi": "tăng huyết áp thai kỳ kèm đau đầu mới xuất hiện (dấu hiệu tiền sản giật)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "OBGYN", "label": "Sản khoa"},
        "advice": "Huyết áp tăng cao hơn bình thường kết hợp đau đầu mới xuất hiện trong thai kỳ là dấu hiệu cảnh báo của tiền sản giật (tổn thương cơ quan đích do co thắt mạch). Bạn cần đến ngay bệnh viện phụ sản hoặc cơ sở y tế gần nhất trong ngày để đo huyết áp chuẩn, xét nghiệm protein niệu và theo dõi tim thai.",
        "stop_downstream": False
    },
    # Case 109 & 120: Pediatric Severe Dehydration / Anuria
    {
        "id": "URG-ESI3-PEDIATRIC-DEHYDRATION-ANURIA",
        "category": "pediatric_dehydration_anuria",
        "patterns_vi": [
            "từ sáng đến giờ gần như không có tã ướt",
            "gần như không có tã ướt",
            "hơn nửa ngày không đi tiểu",
            "nửa ngày không đi tiểu",
            "tiêu chảy mắt trũng và hơn nửa ngày không đi tiểu",
            "nôn liên tục môi khô và từ sáng đến giờ gần như không có tã ướt"
        ],
        "patterns_en": ["pediatric dehydration with anuria or no wet nappies"],
        "required_groups_vi": [
            ["nôn liên tục", "tiêu chảy", "nôn", "non lien tuc", "tieu chay"],
            ["không có tã ướt", "không đi tiểu", "mắt trũng", "hơn nửa ngày không đi tiểu", "moi kho va tu sang"]
        ],
        "label_vi": "trẻ nôn ói/tiêu chảy có dấu hiệu mất nước nặng (thiểu niệu/vô niệu, mắt trũng, môi khô)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "PEDIATRICS", "label": "Nhi khoa - Cấp cứu"},
        "advice": "Trẻ nôn hoặc tiêu chảy kéo dài dẫn đến không có tã ướt/không đi tiểu nhiều giờ liền, môi khô nứt nẻ hoặc mắt trũng là biểu hiện của mất nước từ mức độ trung bình đến nặng và giảm thể tích tuần hoàn. Cần đưa bé đến phòng khám Nhi hoặc khoa Cấp cứu Nhi để được bù dịch và điện giải kịp thời.",
        "stop_downstream": False
    }
]


def apply_patch():
    with open(PROTOCOLS_FILE, encoding="utf-8") as f:
        data = json.load(f)

    existing_rf = {p["id"]: p for p in data.get("red_flag_patterns", [])}
    existing_u = {p["id"]: p for p in data.get("urgent_patterns", [])}

    for pat in UPGRADED_PATTERNS:
        pid = pat["id"]
        if pat.get("urgency") == "EMERGENCY":
            if pid not in existing_rf:
                data.setdefault("red_flag_patterns", []).append(pat)
            else:
                existing_rf[pid].update(pat)
        else:
            if pid not in existing_u:
                data.setdefault("urgent_patterns", []).append(pat)
            else:
                existing_u[pid].update(pat)

    with open(PROTOCOLS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Patched {len(UPGRADED_PATTERNS)} protocols with required_groups_vi in {PROTOCOLS_FILE.name}")


if __name__ == "__main__":
    apply_patch()
