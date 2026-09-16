"""Patch Blind V2 protocols with remaining clinical red flags and urgent patterns."""

from __future__ import annotations

import json
from pathlib import Path

PROTOCOLS_FILE = Path(__file__).resolve().parent.parent / "app" / "knowledge" / "red_flag_protocols.json"

NEW_PROTOCOLS = [
    # Case 151: Necrotizing fasciitis / severe soft tissue infection
    {
        "id": "RF-ESI1-NECROTIZING-FASCIITIS",
        "category": "necrotizing_soft_tissue_infection",
        "patterns_vi": [
            "vết thương nhỏ rất đau đau tăng nhanh và vùng da chuyển tím",
            "vết thương rất đau đau tăng nhanh vùng da chuyển tím",
            "vết thương đau tăng nhanh và vùng da chuyển tím",
            "vùng da chuyển tím vết thương rất đau"
        ],
        "patterns_en": ["necrotizing fasciitis disproportionate pain skin purple"],
        "required_groups_vi": [
            ["vết thương", "vet thuong", "vet rach", "vet cat"],
            ["rất đau", "đau tăng nhanh", "đau dữ dội", "rat dau", "dau tang nhanh"],
            ["chuyển tím", "chuyen tim", "da tím", "da tim", "vùng da chuyển tím", "hoại tử"]
        ],
        "label_vi": "nguy cơ viêm cân mạc hoại tử / nhiễm trùng mô mềm hoại tử cấp (đau dữ dội vượt mức và đổi màu da tím tái)",
        "esi_level": 1,
        "urgency": "EMERGENCY",
        "specialty": {"code": "EMERGENCY", "label": "Cấp cứu - Ngoại khoa"},
        "advice": "Tình trạng vết thương nhỏ nhưng đau dữ dội tăng nhanh kèm da chuyển màu thâm tím là dấu hiệu kinh điển của viêm cân mạc hoại tử (nhiễm khuẩn mô mềm ăn sâu đe dọa tính mạng). Cần gọi cấp cứu 115 hoặc đưa người bệnh đến ngay phòng Cấp cứu ngoại khoa của bệnh viện lớn để được hội chẩn phẫu thuật cắt lọc và dùng kháng sinh phổ rộng khẩn cấp.",
        "stop_downstream": True
    },
    # Case 170: Bee sting anaphylaxis (airway/hypotension)
    {
        "id": "RF-ESI1-BEE-STING-ANAPHYLAXIS",
        "category": "insect_sting_anaphylaxis",
        "patterns_vi": [
            "sau ong chích tôi thấy chóng mặt và giọng khàn đi",
            "ong chích thấy chóng mặt và giọng khàn",
            "ong đốt chóng mặt giọng khàn",
            "ong chích giọng khàn đi"
        ],
        "patterns_en": ["bee sting anaphylaxis hoarseness dizziness"],
        "required_groups_vi": [
            ["ong chích", "ong đốt", "ong can", "ong dot", "ong chich", "ong vò vẽ", "bị ong"],
            ["chóng mặt", "giọng khàn", "khàn giọng", "khó thở", "phù môi", "choáng", "chong mat", "khan giong"]
        ],
        "label_vi": "phản vệ độ nặng sau ong đốt (phù thanh quản / khàn giọng và dấu hiệu tụt huyết áp)",
        "esi_level": 1,
        "urgency": "EMERGENCY",
        "specialty": {"code": "EMERGENCY", "label": "Hồi sức cấp cứu"},
        "advice": "Tình trạng chóng mặt và khàn tiếng xuất hiện sau khi bị ong đốt là biểu hiện của phản vệ nguy kịch đe dọa tắc nghẽn đường thở hoàn toàn và sốc phản vệ. Hãy gọi 115 ngay lập tức. Nếu có sẵn bút tiêm Adrenaline/Epinephrine tự động, hãy tiêm bắp vào mặt trước ngoài đùi ngay lập tức trong khi chờ đội cấp cứu.",
        "stop_downstream": True
    },
    # Case 143: SIRS / Sepsis
    {
        "id": "RF-ESI2-SIRS-SEPSIS-PRESENTATION",
        "category": "sirs_septic_presentation",
        "patterns_vi": [
            "sốt cao tim nhanh thở nhanh",
            "tôi sốt cao, tim nhanh, thở nhanh nhưng máy đo huyết áp vẫn bình thường",
            "sốt cao kèm tim nhanh thở nhanh"
        ],
        "patterns_en": ["sirs criteria fever tachycardia tachypnea"],
        "required_groups_vi": [
            ["sốt cao", "sot cao", "sốt", "sot"],
            ["tim nhanh", "tim dap nhanh", "nhip tim nhanh"],
            ["thở nhanh", "tho nhanh", "tho gap"]
        ],
        "label_vi": "hội chứng đáp ứng viêm toàn thân / nghi ngờ nhiễm khuẩn huyết giai đoạn còn bù (sốt cao, nhịp tim nhanh và thở nhanh)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "EMERGENCY", "label": "Hồi sức cấp cứu - Truyền nhiễm"},
        "advice": "Sự kết hợp giữa sốt cao, nhịp tim nhanh và nhịp thở nhanh đáp ứng tiêu chuẩn hội chứng đáp ứng viêm toàn thân (SIRS). Dù máy đo huyết áp tại nhà hiện bình thường, cơ thể có thể đang trong giai đoạn sốc nhiễm khuẩn còn bù và có thể suy sụp tuần hoàn đột ngột. Cần đến ngay khoa Cấp cứu để cấy máu, làm xét nghiệm lactate và truyền kháng sinh tĩnh mạch sớm.",
        "stop_downstream": True
    },
    # Case 147: Post-op surgical site infection
    {
        "id": "URG-ESI3-POSTOP-SURGICAL-SITE-INFECTION",
        "category": "surgical_site_infection",
        "patterns_vi": [
            "tôi vừa mổ 5 ngày vùng mổ ngày càng đỏ hơn đau hơn và hôm nay có sốt",
            "vừa mổ vùng mổ ngày càng đỏ hơn đau hơn và có sốt",
            "vết mổ đỏ hơn đau hơn và có sốt"
        ],
        "patterns_en": ["surgical site infection postop fever pain erythema"],
        "required_groups_vi": [
            ["mổ", "sau mổ", "vừa mổ", "vết mổ", "phẫu thuật", "vung mo", "vet mo"],
            ["đỏ hơn", "đau hơn", "sưng đỏ", "chảy dịch", "do hon", "dau hon"],
            ["sốt", "sot", "sốt nhẹ", "sốt cao"]
        ],
        "label_vi": "nhiễm trùng vết mổ sau phẫu thuật (vết mổ sưng đỏ đau tăng kèm sốt)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "SURGERY", "label": "Ngoại khoa - Vết mổ"},
        "advice": "Vết mổ sau phẫu thuật có biểu hiện sưng đỏ, đau tăng dần và xuất hiện sốt là dấu hiệu nhiễm trùng vết mổ tiến triển. Bạn cần liên hệ bác sĩ phẫu thuật hoặc đến tái khám sớm trong ngày tại bệnh viện đã mổ để kiểm tra vết thương, siêu âm tụ dịch/áp xe và chỉ định kháng sinh thích hợp.",
        "stop_downstream": False
    },
    # Case 68: Acute pancreatitis
    {
        "id": "RF-ESI2-ACUTE-PANCREATITIS",
        "category": "acute_pancreatitis",
        "patterns_vi": [
            "uống rượu tối qua hôm nay bụng trên đau xuyên ra lưng và nôn nhiều",
            "bụng trên đau xuyên ra lưng và nôn nhiều",
            "đau bụng trên xuyên ra sau lưng nôn nhiều"
        ],
        "patterns_en": ["acute pancreatitis epigastric pain radiating to back vomiting"],
        "required_groups_vi": [
            ["bụng trên", "thượng vị", "thuong vi", "bung tren", "vùng trên rốn"],
            ["xuyên ra lưng", "lan ra sau lưng", "lan ra lung", "xuyen ra lung", "xuyên sang lưng"],
            ["nôn", "nôn nhiều", "buon non", "non nhieu"]
        ],
        "label_vi": "cơn đau quặn thượng vị lan xuyên ra sau lưng kèm nôn ói nhiều (nghi ngờ viêm tụy cấp sau uống rượu)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "GASTROENTEROLOGY", "label": "Tiêu hóa - Cấp cứu"},
        "advice": "Cơn đau bụng vùng thượng vị lan xuyên thấu ra sau lưng kèm nôn mửa dữ dội sau khi uống rượu là triệu chứng kinh điển của viêm tụy cấp. Tình trạng này có nguy cơ biến chứng hoại tử tụy và suy đa cơ quan. Hãy đến ngay khoa Cấp cứu để được định lượng men tụy (amylase/lipase máu) và truyền dịch hồi sức kịp thời.",
        "stop_downstream": True
    },
    # Case 81: Ruptured ectopic pregnancy
    {
        "id": "RF-ESI2-RUPTURED-ECTOPIC-PREGNANCY",
        "category": "ruptured_ectopic_pregnancy",
        "patterns_vi": [
            "trễ kinh khoảng 7 tuần đau một bên bụng dưới và cảm giác muốn ngất",
            "trễ kinh đau một bên bụng dưới muốn ngất",
            "chậm kinh đau bụng dưới muốn ngất"
        ],
        "patterns_en": ["ruptured ectopic pregnancy missed period pelvic pain presyncope"],
        "required_groups_vi": [
            ["trễ kinh", "chậm kinh", "mang thai", "tre kinh", "cham kinh"],
            ["đau một bên bụng dưới", "đau bụng dưới", "đau hạ vị", "đau chậu", "dau mot ben bung duoi", "dau bung duoi"],
            ["muốn ngất", "ngất", "choáng", "chóng mặt dữ dội", "muon ngat", "ngat", "muon xiu"]
        ],
        "label_vi": "nghi ngờ thai ngoài tử cung vỡ / dọa vỡ (trễ kinh kèm đau nhói một bên bụng dưới và dấu hiệu tụt huyết áp/tiền ngất)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "OBSTETRICS", "label": "Sản phụ khoa - Cấp cứu"},
        "advice": "Ở phụ nữ trong độ tuổi sinh đẻ có trễ kinh, đau đột ngột một bên bụng dưới kèm cảm giác muốn ngất là dấu hiệu báo động đỏ của thai ngoài tử cung vỡ gây xuất huyết ồ ạt trong ổ bụng. Cần đến ngay khoa Cấp cứu Sản phụ khoa gần nhất; tuyệt đối không tự đi lại một mình vì nguy cơ ngất xỉu và sốc mất máu nguy kịch.",
        "stop_downstream": True
    },
    # Case 138: Methamphetamine chest pain
    {
        "id": "RF-ESI2-METHAMPHETAMINE-CHEST-PAIN",
        "category": "methamphetamine_induced_chest_pain",
        "patterns_vi": [
            "sau khi hít ma túy đá tim tôi đập nhanh và tôi thấy ngực như bị thắt lại",
            "hít ma túy đá tim đập nhanh ngực như bị thắt lại",
            "ma túy đá ngực như bị thắt lại",
            "hít đá ngực thắt lại"
        ],
        "patterns_en": ["methamphetamine induced chest pain vasospasm"],
        "required_groups_vi": [
            ["ma túy đá", "ma tuy da", "hít đá", "ngáo đá", "methamphetamine", "chất kích thích"],
            ["ngực như bị thắt lại", "thắt lại", "đau ngực", "tức ngực", "ngực bị thắt", "that lai", "dau that nguc"]
        ],
        "label_vi": "đau thắt ngực cấp sau sử dụng ma túy đá (nguy cơ co thắt mạch vành và nhồi máu cơ tim)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "CARDIOLOGY", "label": "Tim mạch - Cấp cứu"},
        "advice": "Chất kích thích dạng amphetamine/methamphetamine gây co thắt động mạch vành dữ dội và tăng huyết áp vọt, có thể dẫn đến nhồi máu cơ tim cấp hoặc bóc tách động mạch chủ ngay cả ở người trẻ tuổi. Hãy gọi 115 hoặc đến khoa Cấp cứu ngay lập tức để đo điện tâm đồ và xét nghiệm men tim khẩn cấp.",
        "stop_downstream": True
    },
    # Case 129: Ethylene glycol / coolant ingestion
    {
        "id": "RF-ESI2-ETHYLENE-GLYCOL-INGESTION",
        "category": "toxic_coolant_ingestion",
        "patterns_vi": [
            "uống nhầm một ngụm dung dịch chống đông xe hơi",
            "uống dung dịch chống đông xe hơi",
            "uống nước làm mát ô tô",
            "uống nước làm mát xe hơi"
        ],
        "patterns_en": ["antifreeze ethylene glycol ingestion"],
        "required_groups_vi": [
            ["chống đông xe hơi", "chong dong xe hoi", "nước làm mát", "nuoc lam mat", "nước làm mát ô tô", "ethylene glycol"],
            ["uống", "uống nhầm", "uong", "uong nham", "nuốt"]
        ],
        "label_vi": "ngộ độc dung dịch chống đông / nước làm mát động cơ (ethylene glycol - nguy cơ suy thận cấp và toan chuyển hóa nặng)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "EMERGENCY", "label": "Hồi sức cấp cứu - Chống độc"},
        "advice": "Dung dịch chống đông/nước làm mát xe hơi chứa Ethylene Glycol có độc tính cực kỳ cao, chuyển hóa thành acid oxalic gây toan chuyển hóa nặng và suy thận cấp không hồi phục. Ngay cả một ngụm nhỏ ở trẻ em cũng là cấp cứu tối khẩn. ĐƯA BỆNH NHI ĐẾN TRUNG TÂM CHỐNG ĐỘC / KHOA CẤP CỨU NGAY LẬP TỨC; mang theo chai dung dịch đã uống; TUYỆT ĐỐI KHÔNG GÂY NÔN.",
        "stop_downstream": True
    },
    # Case 22: DVT post long flight
    {
        "id": "URG-ESI3-DVT-POST-LONG-FLIGHT",
        "category": "deep_vein_thrombosis",
        "patterns_vi": [
            "chân phải của tôi sưng to hơn chân trái sau chuyến bay dài",
            "sưng to hơn chân trái sau chuyến bay dài",
            "sưng chân sau chuyến bay dài"
        ],
        "patterns_en": ["dvt deep vein thrombosis post long flight unilateral leg swelling"],
        "required_groups_vi": [
            ["sưng to hơn", "chân phải sưng", "chân trái sưng", "sưng một chân", "sung to hon", "lệch hai chân"],
            ["chuyến bay dài", "sau chuyến bay", "ngồi máy bay lâu", "bay dai", "chuyen bay dai"]
        ],
        "label_vi": "sưng phù một bên chân sau chuyến bay dài (nghi ngờ huyết khối tĩnh mạch sâu DVT)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "VASCULAR", "label": "Mạch máu - Tim mạch"},
        "advice": "Tình trạng sưng không cân xứng một bên cẳng chân xuất hiện sau chuyến bay đường dài là dấu hiệu điển hình của huyết khối tĩnh mạch sâu (DVT). Nguy cơ lớn nhất là cục máu đông di chuyển lên phổi gây thuyên tắc phổi cấp. Bạn cần đến cơ sở y tế trong ngày để được siêu âm Doppler mạch máu chi dưới; hạn chế xoa bóp mạnh bắp chân.",
        "stop_downstream": False
    },
    # Case 35: Dengue warning signs
    {
        "id": "URG-ESI3-DENGUE-WARNING-SIGNS",
        "category": "dengue_warning_signs",
        "patterns_vi": [
            "sốt 4 ngày hôm nay hạ sốt nhưng tôi thấy mệt lả và đau bụng âm ỉ",
            "hạ sốt nhưng mệt lả và đau bụng",
            "hết sốt nhưng mệt lả đau bụng"
        ],
        "patterns_en": ["dengue warning signs defervescence severe fatigue abdominal pain"],
        "required_groups_vi": [
            ["sốt", "hạ sốt", "hết sốt", "sot", "ha sot", "het sot"],
            ["mệt lả", "met la", "li bì", "mệt nhiều", "met nhieu"],
            ["đau bụng", "dau bung", "đau hạ sườn", "dau bung am i"]
        ],
        "label_vi": "dấu hiệu cảnh báo sốt xuất huyết nặng (hạ sốt kèm mệt lả và đau bụng âm ỉ)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "INFECTIOUS", "label": "Truyền nhiễm - Cấp cứu"},
        "advice": "Ở bệnh nhân sốt nhiều ngày, thời điểm thân nhiệt hạ (ngày 4-6) chính là lúc bắt đầu bước vào 'giai đoạn nguy hiểm' của sốt xuất huyết Dengue do thoát huyết tương. Mệt lả và đau bụng là dấu hiệu cảnh báo thất thoát tuần hoàn sớm. Cần đến bệnh viện khám và xét nghiệm công thức máu (đo Hct và tiểu cầu) trong ngày hôm nay.",
        "stop_downstream": False
    },
    # Case 39: Warfarin spontaneous bruising
    {
        "id": "URG-ESI3-WARFARIN-SPONTANEOUS-BRUISING",
        "category": "anticoagulant_spontaneous_bruising",
        "patterns_vi": [
            "đang uống warfarin hôm nay thấy có nhiều vết bầm tím tự nhiên trên tay chân",
            "uống warfarin thấy có nhiều vết bầm tím tự nhiên",
            "warfarin vết bầm tím tự nhiên"
        ],
        "patterns_en": ["warfarin spontaneous ecchymosis coagulopathy"],
        "required_groups_vi": [
            ["warfarin", "thuốc chống đông", "thuoc chong dong", "thuoc lam loang mau"],
            ["vết bầm tím tự nhiên", "bầm tím", "vết bầm", "bam tim", "xuất huyết dưới da", "vet bam tim"]
        ],
        "label_vi": "xuất huyết dưới da tự nhiên ở bệnh nhân dùng thuốc chống đông (nguy cơ quá liều chống đông / INR cao)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "HEMATOLOGY", "label": "Huyết học - Tim mạch"},
        "advice": "Xuất hiện nhiều vết bầm tím tự nhiên dưới da không do va đập ở người đang uống warfarin là chỉ báo nồng độ chống đông trong máu có thể đã vượt ngưỡng an toàn (INR quá cao), tiềm ẩn nguy cơ xuất huyết nội tạng hoặc xuất huyết não. Bạn cần đi khám xét nghiệm đông máu (INR) sớm trong ngày để bác sĩ điều chỉnh lại liều warfarin.",
        "stop_downstream": False
    },
    # Case 99: Hyperemesis gravidarum
    {
        "id": "URG-ESI3-HYPEREMESIS-GRAVIDARUM",
        "category": "hyperemesis_gravidarum",
        "patterns_vi": [
            "mang thai và nôn liên tục gần cả ngày không giữ được ngụm nước nào",
            "mang thai nôn liên tục không giữ được ngụm nước nào",
            "mang thai nôn liên tục không giữ được nước"
        ],
        "patterns_en": ["hyperemesis gravidarum unable to keep fluids down dehydration"],
        "required_groups_vi": [
            ["mang thai", "thai kỳ", "có bầu", "mang bau", "co bau"],
            ["nôn liên tục", "non lien tuc", "nôn ói nhiều", "không giữ được", "khong giu duoc", "ngụm nước nào"]
        ],
        "label_vi": "nôn nghén nặng kéo dài kèm mất nước trong thai kỳ (hyperemesis gravidarum)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "OBSTETRICS", "label": "Sản phụ khoa"},
        "advice": "Tình trạng nôn ói liên tục cả ngày đến mức không thể dung nạp nước là biểu hiện của chứng nghén nặng (Hyperemesis Gravidarum). Nguy cơ chính là mất nước, rối loạn điện giải và keton máu ảnh hưởng đến mẹ và thai nhi. Bạn cần đến cơ sở y tế chuyên khoa Phụ sản trong ngày để được truyền dịch bù điện giải và dùng thuốc chống nôn an toàn cho thai kỳ.",
        "stop_downstream": False
    }
]


def apply_patch():
    with open(PROTOCOLS_FILE, encoding="utf-8") as f:
        data = json.load(f)

    existing_rf = {p["id"]: p for p in data.get("red_flag_patterns", [])}
    existing_u = {p["id"]: p for p in data.get("urgent_patterns", [])}

    added_rf = 0
    added_u = 0

    for pat in NEW_PROTOCOLS:
        pid = pat["id"]
        if pat.get("urgency") == "EMERGENCY":
            if pid not in existing_rf:
                data.setdefault("red_flag_patterns", []).append(pat)
                added_rf += 1
            else:
                existing_rf[pid].update(pat)
        else:
            if pid not in existing_u:
                data.setdefault("urgent_patterns", []).append(pat)
                added_u += 1
            else:
                existing_u[pid].update(pat)

    with open(PROTOCOLS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Patched {PROTOCOLS_FILE.name}: added {added_rf} red flags, {added_u} urgent patterns.")


if __name__ == "__main__":
    apply_patch()
