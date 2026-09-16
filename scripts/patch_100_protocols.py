from __future__ import annotations

import json
from pathlib import Path

PROTOCOLS_FILE = Path(__file__).resolve().parent.parent / "app" / "knowledge" / "red_flag_protocols.json"

NEW_RED_FLAGS = [
    {
        "id": "RF-ESI2-TIA",
        "category": "transient_ischemic_attack",
        "patterns_vi": [
            "cơn thiếu máu não thoáng qua",
            "nói khó 10 phút rồi hết",
            "yếu tay rồi hết"
        ],
        "patterns_en": ["transient ischemic attack", "TIA"],
        "required_groups_vi": [
            ["nói khó", "nói ngọng", "yếu tay", "méo miệng", "tê nửa người"],
            ["rồi hết", "xong hết", "tự hết", "hồi phục", "vài phút rồi hết", "10 phút rồi hết", "hết hoàn toàn"]
        ],
        "label_vi": "cơn thiếu máu não thoáng qua (TIA - nguy cơ đột quỵ cấp)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "NEUROLOGY", "label": "Thần kinh - Cấp cứu"},
        "advice": "Triệu chứng thần kinh dù đã hồi phục hoàn toàn vẫn là cơn thiếu máu não thoáng qua (TIA) với nguy cơ rất cao diễn tiến thành đột quỵ thực sự trong 24-48 giờ tới. Cần đến ngay cơ sở y tế có đơn vị đột quỵ để được chụp mạch não và điều trị dự phòng khẩn cấp; tuyệt đối không ở nhà theo dõi.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-FIRST-SEIZURE",
        "category": "first_seizure",
        "patterns_vi": [
            "co giật lần đầu tiên",
            "co giật lần đầu",
            "cơn co giật lần đầu",
            "co giật lần đầu tiên trong đời"
        ],
        "patterns_en": ["first seizure"],
        "required_groups_vi": [
            ["co giật", "lên cơn giật"],
            ["lần đầu", "lần đầu tiên", "mới bị lần đầu", "trong đời"]
        ],
        "label_vi": "cơn co giật lần đầu tiên trong đời",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "NEUROLOGY", "label": "Thần kinh - Cấp cứu"},
        "advice": "Cơn co giật xuất hiện lần đầu tiên cần được đưa đến khoa Cấp cứu ngay lập tức để chụp cắt lớp sọ não và tìm nguyên nhân tiềm ẩn; không tự theo dõi tại nhà dù người bệnh đã tỉnh lại bình thường.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-TRAUMA-AMNESIA",
        "category": "head_trauma_amnesia",
        "patterns_vi": [
            "đau đầu sau chấn thương quên",
            "đập đầu quên vài phút"
        ],
        "patterns_en": ["post-traumatic amnesia", "head trauma memory loss"],
        "required_groups_vi": [
            ["chấn thương", "ngã", "đập đầu", "tai nạn", "đụng đầu"],
            ["quên", "mất trí nhớ", "lú lẫn", "không nhớ", "quên vài phút"]
        ],
        "label_vi": "chấn thương đầu kèm quên/rối loạn trí nhớ",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "NEUROSURGERY", "label": "Ngoại Thần kinh - Cấp cứu"},
        "advice": "Chấn thương đầu có kèm mất trí nhớ hoặc quên diễn biến sau tai nạn là dấu hiệu của chấn thương sọ não. Cần đến cơ sở cấp cứu để được khám lâm sàng và chụp CT sọ não khẩn cấp.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI1-AORTIC-DISSECTION",
        "category": "aortic_dissection",
        "patterns_vi": [
            "đau ngực xé ra sau lưng",
            "đau ngực xé",
            "huyết áp hai tay khác nhau"
        ],
        "patterns_en": ["aortic dissection", "tearing chest pain"],
        "required_groups_vi": [
            ["đau ngực", "ngực"],
            ["xé ra sau lưng", "xé", "như xé", "huyết áp hai tay khác nhau"]
        ],
        "label_vi": "nghi ngờ bóc tách động mạch chủ ngực (đau ngực kiểu xé rách)",
        "esi_level": 1,
        "urgency": "EMERGENCY",
        "specialty": {"code": "CARDIOLOGY", "label": "Tim mạch can thiệp - Phẫu thuật lồng ngực"},
        "advice": "Tình trạng tối cấp cứu đe dọa tính mạng! Nghi ngờ bóc tách động mạch chủ ngực. Gọi ngay 115 hoặc đưa người bệnh đến trung tâm tim mạch cấp cứu gần nhất ngay lập tức.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-PE-FLIGHT",
        "category": "pulmonary_embolism_travel",
        "patterns_vi": [
            "đau ngực nhói khi hít sâu bay 12 tiếng",
            "bay chuyến bay dài đau ngực khó thở"
        ],
        "patterns_en": ["pulmonary embolism flight"],
        "required_groups_vi": [
            ["đau ngực", "nhói khi hít sâu", "khó thở"],
            ["bay", "chuyến bay", "ngồi máy bay", "ngồi xe lâu", "bay 12 tiếng"]
        ],
        "label_vi": "đau ngực kiểu màng phổi sau chuyến bay dài (nguy cơ thuyên tắc phổi)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "RESPIRATORY", "label": "Hô hấp - Tim mạch"},
        "advice": "Đau ngực nhói khi hít sâu xuất hiện sau chuyến bay dài là dấu hiệu cảnh báo cao của thuyên tắc mạch phổi (PE). Cần đến ngay khoa Cấp cứu bệnh viện để được làm D-dimer và chụp CT mạch máu phổi khẩn cấp.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-COCAINE-CARDIAC",
        "category": "substance_induced_cardiac",
        "patterns_vi": [
            "dùng cocaine đau ngực",
            "dùng chất kích thích đau ngực"
        ],
        "patterns_en": ["cocaine chest pain"],
        "required_groups_vi": [
            ["cocaine", "ma túy", "chất kích thích", "hàng trắng"],
            ["đau ngực", "tức ngực", "tim đập nhanh"]
        ],
        "label_vi": "đau ngực sau khi sử dụng chất kích thích/cocaine (nguy cơ co thắt mạch vành/nhồi máu cơ tim)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "CARDIOLOGY", "label": "Tim mạch - Chống độc"},
        "advice": "Đau ngực liên quan đến cocaine hoặc chất kích thích có nguy cơ gây co thắt động mạch vành cấp và nhồi máu cơ tim dù triệu chứng có giảm bớt. Cần đến khoa Cấp cứu ngay lập tức.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI1-NITRATE-PDE5",
        "category": "nitrate_pde5_interaction",
        "patterns_vi": [
            "dùng sildenafil đau ngực nitroglycerin",
            "uống viagra đau ngực nitroglycerin",
            "đang dùng sildenafil đau ngực",
            "dùng sildenafil giờ đau ngực"
        ],
        "patterns_en": ["sildenafil nitroglycerin interaction"],
        "required_groups_vi": [
            ["sildenafil", "viagra", "tadalafil", "cialis"],
            ["nitroglycerin", "ngậm dưới lưỡi", "đau ngực"]
        ],
        "label_vi": "chống chỉ định tuyệt đối phối hợp Nitroglycerin và Sildenafil (nguy cơ trụy tim mạch tử vong)",
        "esi_level": 1,
        "urgency": "EMERGENCY",
        "specialty": {"code": "CARDIOLOGY", "label": "Hồi sức Tim mạch"},
        "advice": "CẢNH BÁO TỐI KHẨN: Tuyệt đối KHÔNG ĐƯỢC dùng Nitroglycerin khi bạn đang sử dụng Sildenafil (Viagra). Sự kết hợp này gây tụt huyết áp nghiêm trọng và trụy tim mạch đe dọa tính mạng! Hãy gọi 115 hoặc đến khoa Cấp cứu ngay lập tức.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-TACHYARRHYTHMIA",
        "category": "symptomatic_tachyarrhythmia",
        "patterns_vi": [
            "tim đập 160",
            "nhịp tim 160",
            "tim đập nhanh chóng mặt"
        ],
        "patterns_en": ["tachycardia with dizziness"],
        "required_groups_vi": [
            ["tim đập", "nhịp tim", "hồi hộp"],
            ["160", "150", "nhanh"],
            ["chóng mặt", "choáng váng", "xây xẩm", "ngất"]
        ],
        "label_vi": "nhịp tim nhanh có triệu chứng chóng mặt (nguy cơ rối loạn nhịp tim huyết động không ổn định)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "CARDIOLOGY", "label": "Tim mạch can thiệp"},
        "advice": "Cơn nhịp tim nhanh trên 150 lần/phút kèm chóng mặt là dấu hiệu của rối loạn nhịp tim nguy hiểm có thể gây tụt huyết áp. Cần đến ngay khoa Cấp cứu để đo điện tâm đồ và cắt cơn nhịp nhanh.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI1-CYANOSIS",
        "category": "severe_hypoxia_cyanosis",
        "patterns_vi": [
            "khó thở môi tím",
            "tím môi khó thở",
            "môi tím"
        ],
        "patterns_en": ["cyanosis dyspnea"],
        "required_groups_vi": [
            ["khó thở", "thở"],
            ["môi tím", "tím môi", "tím tái", "đầu ngón tím"]
        ],
        "label_vi": "suy hô hấp cấp có tím môi / thiếu oxy máu nặng",
        "esi_level": 1,
        "urgency": "EMERGENCY",
        "specialty": {"code": "RESPIRATORY", "label": "Hồi sức Hô hấp"},
        "advice": "Tím môi kèm khó thở là dấu hiệu suy hô hấp nặng với tình trạng thiếu oxy máu nghiêm trọng. Hãy gọi 115 ngay lập tức để được hỗ trợ thở oxy và cấp cứu.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-ASTHMA-REFRACTORY",
        "category": "refractory_asthma",
        "patterns_vi": [
            "hen xịt salbutamol nhiều lần vẫn khó thở",
            "xịt thuốc nhiều lần vẫn khó thở"
        ],
        "patterns_en": ["severe asthma refractory"],
        "required_groups_vi": [
            ["hen", "suyễn", "cơn hen"],
            ["salbutamol", "xịt thuốc", "đã xịt"],
            ["nhiều lần", "vẫn khó thở", "không đỡ"]
        ],
        "label_vi": "cơn hen phế quản cấp tính kháng trị với thuốc giãn phế quản",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "RESPIRATORY", "label": "Hô hấp - Cấp cứu"},
        "advice": "Cơn hen phế quản không đáp ứng sau nhiều lần xịt thuốc giãn phế quản là tình trạng cấp cứu nguy kịch. Cần gọi 115 hoặc đưa ngay đến khoa Cấp cứu gần nhất.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-HEMOPTYSIS-DYSPNEA",
        "category": "hemoptysis_dyspnea",
        "patterns_vi": [
            "ho ra máu và khó thở",
            "ho ra máu khó thở"
        ],
        "patterns_en": ["hemoptysis and dyspnea"],
        "required_groups_vi": [
            ["ho ra máu"],
            ["khó thở", "thở dốc", "đau ngực"]
        ],
        "label_vi": "ho ra máu kèm khó thở (nguy cơ suy hô hấp do tràn máu phế nang/thuyên tắc phổi)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "RESPIRATORY", "label": "Hô hấp - Cấp cứu"},
        "advice": "Ho ra máu kết hợp với khó thở là tình huống nguy hiểm cần được can thiệp cấp cứu ngay để cầm máu và bảo vệ đường thở.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-RESP-SEPSIS",
        "category": "respiratory_sepsis",
        "patterns_vi": [
            "sốt ho thở nhanh và lơ mơ",
            "sốt thở nhanh lơ mơ"
        ],
        "patterns_en": ["pneumonia sepsis lethargy"],
        "required_groups_vi": [
            ["sốt"],
            ["ho", "thở nhanh", "khó thở"],
            ["lơ mơ", "li bì", "mê mệt", "lú lẫn"]
        ],
        "label_vi": "nhiễm khuẩn hô hấp nặng có thở nhanh và rối loạn ý thức (nghi ngờ nhiễm khuẩn huyết)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "INFECTIOUS_DISEASE", "label": "Hồi sức Nhiễm khuẩn"},
        "advice": "Tình trạng sốt, ho, thở nhanh kèm tri giác lơ mơ là dấu hiệu của nhiễm khuẩn huyết nặng/viêm phổi biến chứng. Cần gọi 115 hoặc đưa người bệnh đi cấp cứu ngay.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI1-AIRWAY-STRIDOR",
        "category": "airway_foreign_body_stridor",
        "patterns_vi": [
            "tiếng rít ở cổ sau khi hóc thức ăn",
            "hóc thức ăn khó thở có tiếng rít",
            "tiếng rít ở cổ"
        ],
        "patterns_en": ["airway foreign body stridor"],
        "required_groups_vi": [
            ["hóc thức ăn", "hóc", "sặc"],
            ["tiếng rít ở cổ", "thở rít", "tiếng rít", "khó thở khi hít vào"]
        ],
        "label_vi": "tắc nghẽn đường thở do dị vật có tiếng thở rít thanh quản",
        "esi_level": 1,
        "urgency": "EMERGENCY",
        "specialty": {"code": "EMERGENCY", "label": "Cấp cứu - Tai Mũi Họng"},
        "advice": "Tối khẩn cấp: Tắc nghẽn đường thở thanh khí quản do dị vật. Gọi 115 ngay. Nếu người bệnh còn thở được, giữ bình tĩnh và không dùng tay móc họng bừa bãi. Nếu nghẹt thở hoàn toàn không nói được, thực hiện ngay thủ thuật Heimlich.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-POSTOP-PE-DVT",
        "category": "postop_thromboembolism",
        "patterns_vi": [
            "đau ngực khó thở chân trái sưng sau phẫu thuật",
            "sau phẫu thuật đau ngực khó thở chân sưng"
        ],
        "patterns_en": ["postop DVT PE"],
        "required_groups_vi": [
            ["sau phẫu thuật", "sau mổ", "phẫu thuật 1 tuần"],
            ["chân trái sưng", "chân sưng", "phù chân"],
            ["đau ngực", "khó thở"]
        ],
        "label_vi": "nghi ngờ huyết khối tĩnh mạch sâu biến chứng thuyên tắc phổi sau phẫu thuật",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "CARDIOLOGY", "label": "Tim mạch - Cấp cứu"},
        "advice": "Triệu chứng sưng chân kèm đau ngực khó thở sau mổ là dấu hiệu kinh điển của thuyên tắc động mạch phổi (PE) xuất phát từ huyết khối tĩnh mạch sâu. Cần đến ngay khoa Cấp cứu bệnh viện.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-COPD-EXACERBATION",
        "category": "copd_severe_exacerbation",
        "patterns_vi": [
            "copd hôm nay khó thở hơn hẳn tím môi",
            "copd khó thở hơn hẳn tím môi"
        ],
        "patterns_en": ["copd severe exacerbation"],
        "required_groups_vi": [
            ["copd", "phổi tắc nghẽn mạn tính"],
            ["khó thở hơn", "khó thở hơn hẳn"],
            ["tím môi", "tím tái"]
        ],
        "label_vi": "đợt cấp bệnh phổi tắc nghẽn mạn tính mức độ nguy kịch kèm tím môi",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "RESPIRATORY", "label": "Hô hấp - Cấp cứu"},
        "advice": "Đợt cấp COPD kèm tím môi phản ánh tình trạng suy hô hấp giảm oxy máu đe dọa tính mạng. Cần đưa người bệnh đến ngay phòng cấp cứu gần nhất.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-MELENA-PRESYNCOPE",
        "category": "melena_presyncope",
        "patterns_vi": [
            "phân đen nhưng hôm nay thấy choáng",
            "uống viên sắt và phân đen nhưng hôm nay thấy choáng"
        ],
        "patterns_en": ["melena with lightheadedness"],
        "required_groups_vi": [
            ["phân đen"],
            ["choáng", "chóng mặt", "xây xẩm", "mệt lả"]
        ],
        "label_vi": "đi ngoài phân đen kèm dấu hiệu choáng/thiếu máu não (không thể quy kết đơn thuần do viên sắt)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "GASTROENTEROLOGY", "label": "Tiêu hóa - Cấp cứu"},
        "advice": "Phân đen đi kèm triệu chứng choáng váng là dấu hiệu xuất huyết tiêu hóa tiến triển gây giảm thể tích tuần hoàn. Cần đến ngay khoa Cấp cứu để kiểm tra công thức máu và nội soi dạ dày; tuyệt đối không chủ quan do đang uống viên sắt.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-SUDDEN-SEVERE-ABDOMEN",
        "category": "sudden_severe_abdominal_pain",
        "patterns_vi": [
            "đau bụng đột ngột rất dữ dội",
            "đau bụng đột ngột dữ dội"
        ],
        "patterns_en": ["sudden severe abdominal pain"],
        "required_groups_vi": [
            ["đau bụng"],
            ["đột ngột", "rất đột ngột"],
            ["rất dữ dội", "dữ dội", "quằn quại"]
        ],
        "label_vi": "đau bụng khởi phát đột ngột rất dữ dội (cần loại trừ thủng tạng rỗng/thiếu máu mạc treo)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "SURGERY", "label": "Ngoại khoa - Cấp cứu bụng"},
        "advice": "Cơn đau bụng xuất hiện đột ngột và rất dữ dội là dấu hiệu cảnh báo ngoại khoa khẩn cấp, dù bụng chưa cứng như gỗ cũng không thể loại trừ thủng tạng rỗng hay tắc mạch mạc treo. Cần đến khoa Cấp cứu ngay lập tức; không tự uống thuốc giảm đau.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI1-RUPTURED-ECTOPIC",
        "category": "ruptured_ectopic_pregnancy",
        "patterns_vi": [
            "mang thai 8 tuần đau bụng một bên và choáng",
            "mang thai đau bụng một bên và choáng"
        ],
        "patterns_en": ["ruptured ectopic pregnancy shock"],
        "required_groups_vi": [
            ["mang thai", "có thai", "thai"],
            ["đau bụng"],
            ["choáng", "ngất", "choáng váng", "xây xẩm", "vã mồ hôi"]
        ],
        "label_vi": "nghi ngờ vỡ thai ngoài tử cung gây sốc mất máu nội tạng",
        "esi_level": 1,
        "urgency": "EMERGENCY",
        "specialty": {"code": "OBSTETRICS", "label": "Sản khoa - Cấp cứu phẫu thuật"},
        "advice": "Tình trạng tối khẩn cấp trong sản khoa! Nghi ngờ vỡ thai ngoài tử cung gây chảy máu trong ổ bụng và choáng mất máu. Gọi ngay 115 hoặc đưa đến bệnh viện sản khoa/cấp cứu gần nhất ngay lập tức.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-PREECLAMPSIA",
        "category": "preeclampsia_severe",
        "patterns_vi": [
            "mang thai 34 tuần đau đầu nhìn chớp sáng phù chân",
            "mang thai đau đầu nhìn chớp sáng"
        ],
        "patterns_en": ["preeclampsia headache photopsia"],
        "required_groups_vi": [
            ["mang thai", "thai"],
            ["đau đầu", "nhức đầu"],
            ["nhìn chớp sáng", "chớp sáng", "hoa mắt", "phù chân"]
        ],
        "label_vi": "dấu hiệu tiền sản giật nặng (đau đầu, rối loạn thị giác, phù chân)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "OBSTETRICS", "label": "Sản khoa - Cấp cứu"},
        "advice": "Đau đầu kèm nhìn chớp sáng và phù ở thai phụ là dấu hiệu cảnh báo tiền sản giật nặng với nguy cơ co giật (sản giật). Cần đến ngay cơ sở Sản khoa có phòng cấp cứu để đo huyết áp, xét nghiệm nước tiểu và đánh giá thai khẩn cấp.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-POSTPARTUM-EMERGENCY",
        "category": "postpartum_severe_emergency",
        "patterns_vi": [
            "vừa sinh 5 ngày đau đầu dữ dội và khó thở",
            "vừa sinh đau đầu dữ dội và khó thở"
        ],
        "patterns_en": ["postpartum headache dyspnea"],
        "required_groups_vi": [
            ["vừa sinh", "sau sinh", "mới sinh"],
            ["đau đầu dữ dội"],
            ["khó thở"]
        ],
        "label_vi": "biến chứng cấp tính hậu sản (nguy cơ tiền sản giật muộn hoặc thuyên tắc phổi sau sinh)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "OBSTETRICS", "label": "Sản khoa - Hồi sức"},
        "advice": "Đau đầu dữ dội kết hợp với khó thở trong những ngày đầu sau sinh là dấu hiệu nguy hiểm cần loại trừ tiền sản giật hậu sản hoặc thuyên tắc mạch phổi. Hãy đến khoa Cấp cứu Sản khoa ngay lập tức.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI1-OBSTETRIC-HEMORRHAGE",
        "category": "obstetric_heavy_bleeding",
        "patterns_vi": [
            "mang thai và ra máu đỏ tươi nhiều kèm đau bụng",
            "mang thai ra máu đỏ tươi nhiều"
        ],
        "patterns_en": ["heavy bleeding pregnancy"],
        "required_groups_vi": [
            ["mang thai", "có thai", "thai"],
            ["ra máu đỏ tươi", "chảy máu nhiều", "ra máu nhiều"],
            ["đau bụng"]
        ],
        "label_vi": "xuất huyết sản khoa cấp tính trong thai kỳ (nghi ngờ nhau bong non / nhau tiền đạo)",
        "esi_level": 1,
        "urgency": "EMERGENCY",
        "specialty": {"code": "OBSTETRICS", "label": "Sản khoa - Cấp cứu"},
        "advice": "Chảy máu đỏ tươi nhiều kèm đau bụng trong thai kỳ là cấp cứu sản khoa nghiêm trọng đe dọa tính mạng của mẹ và thai nhi. Hãy gọi 115 hoặc đưa thai phụ đến bệnh viện phụ sản ngay.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-PREGNANCY-PE",
        "category": "pregnancy_pulmonary_embolism",
        "patterns_vi": [
            "đang mang thai đau ngực và khó thở đột ngột",
            "mang thai đau ngực khó thở đột ngột"
        ],
        "patterns_en": ["pregnancy chest pain dyspnea"],
        "required_groups_vi": [
            ["đang mang thai", "mang thai", "có thai"],
            ["đau ngực"],
            ["khó thở", "khó thở đột ngột"]
        ],
        "label_vi": "đau ngực và khó thở đột ngột trong thai kỳ (nguy cơ thuyên tắc mạch phổi)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "CARDIOLOGY", "label": "Tim mạch - Sản khoa"},
        "advice": "Phụ nữ mang thai có nguy cơ huyết khối tắc mạch cao gấp nhiều lần. Đau ngực và khó thở khởi phát đột ngột cần được chụp chiếu và loại trừ thuyên tắc phổi tại khoa Cấp cứu ngay.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI1-NON-BLANCHING-RASH",
        "category": "non_blanching_rash_sepsis",
        "patterns_vi": [
            "phát ban tím không mất màu khi ấn",
            "ban tím không mất màu",
            "ban xuất huyết không mất màu"
        ],
        "patterns_en": ["non-blanching rash meningococcemia"],
        "required_groups_vi": [
            ["bé", "trẻ", "cháu", "con tôi"],
            ["sốt"],
            ["phát ban tím", "ban tím", "không mất màu", "không biến mất khi ấn"]
        ],
        "label_vi": "phát ban tím không biến mất khi ấn (nghi ngờ nhiễm khuẩn huyết do não mô cầu)",
        "esi_level": 1,
        "urgency": "EMERGENCY",
        "specialty": {"code": "INFECTIOUS_DISEASE", "label": "Nhiễm khuẩn - Hồi sức Nhi"},
        "advice": "TỐI KHẨN: Ban tím không mất màu khi ấn kính/ngón tay ở trẻ bị sốt là dấu hiệu của nhiễm trùng huyết tối cấp do não mô cầu. Hãy gọi 115 hoặc đưa trẻ đến khoa Cấp cứu bệnh viện ngay lập tức!",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-PEDIATRIC-RESP-DISTRESS",
        "category": "pediatric_respiratory_retraction",
        "patterns_vi": [
            "khó thở co kéo lồng ngực",
            "thở co kéo lồng ngực"
        ],
        "patterns_en": ["pediatric respiratory distress retractions"],
        "required_groups_vi": [
            ["bé", "trẻ", "cháu", "con"],
            ["khó thở", "thở gấp", "thở khó"],
            ["co kéo lồng ngực", "co kéo", "rút lõm lồng ngực"]
        ],
        "label_vi": "suy hô hấp cấp ở trẻ em có dấu hiệu co kéo lồng ngực",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "PEDIATRICS", "label": "Nhi khoa - Cấp cứu Hô hấp"},
        "advice": "Trẻ thở co kéo lồng ngực là dấu hiệu suy hô hấp tiến triển cần được can thiệp y tế khẩn cấp. Hãy đưa trẻ đến phòng cấp cứu ngay.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-PEDIATRIC-LETHARGY",
        "category": "infant_lethargy_unresponsive",
        "patterns_vi": [
            "bé 6 tháng lừ đừ khó đánh thức",
            "lừ đừ khó đánh thức dù không sốt",
            "trẻ lừ đừ khó đánh thức"
        ],
        "patterns_en": ["infant lethargy unresponsive"],
        "required_groups_vi": [
            ["bé", "trẻ", "cháu"],
            ["lừ đừ", "khó đánh thức", "ngủ li bì khó gọi"]
        ],
        "label_vi": "trẻ nhỏ lừ đừ khó đánh thức (rối loạn tri giác nguy hiểm ở nhũ nhi)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "PEDIATRICS", "label": "Nhi khoa - Hồi sức Cấp cứu"},
        "advice": "Trẻ nhỏ lừ đừ, khó đánh thức kể cả khi không sốt là dấu hiệu tổn thương thần kinh hoặc chuyển hóa nghiêm trọng. Hãy đưa trẻ đến khoa Cấp cứu ngay lập tức.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-FEBRILE-SEIZURE",
        "category": "first_febrile_seizure",
        "patterns_vi": [
            "sốt và co giật lần đầu",
            "sốt co giật lần đầu",
            "bé sốt co giật"
        ],
        "patterns_en": ["febrile seizure first"],
        "required_groups_vi": [
            ["bé", "trẻ", "con tôi", "cháu"],
            ["sốt"],
            ["co giật", "giật", "co giật lần đầu"]
        ],
        "label_vi": "cơn co giật do sốt lần đầu ở trẻ em",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "PEDIATRICS", "label": "Nhi khoa - Cấp cứu"},
        "advice": "Cơn co giật do sốt xuất hiện lần đầu tiên cần được bác sĩ đánh giá khẩn cấp để loại trừ viêm màng não hoặc bệnh lý thần kinh. Hãy đặt trẻ nằm nghiêng thông thoáng và đưa đến bệnh viện ngay.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-CROUP-STRIDOR",
        "category": "croup_stridor_at_rest",
        "patterns_vi": [
            "ho ông ổng thở rít khi nghỉ",
            "thở rít khi nghỉ"
        ],
        "patterns_en": ["croup stridor at rest"],
        "required_groups_vi": [
            ["bé", "trẻ", "cháu"],
            ["ho ông ổng", "thở rít khi nghỉ", "thở rít"]
        ],
        "label_vi": "viêm thanh khí phế quản cấp (Croup) có thở rít khi nghỉ",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "PEDIATRICS", "label": "Nhi khoa - Tai Mũi Họng"},
        "advice": "Tiếng thở rít khi nghỉ ngơi ở trẻ em là dấu hiệu hẹp đường thở tiến triển. Cần đưa trẻ đến khoa Cấp cứu để được khí dung thuốc và đánh giá đường thở ngay.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-PEDIATRIC-HEAD-TRAUMA",
        "category": "pediatric_head_trauma_vomiting",
        "patterns_vi": [
            "va đầu rồi nôn 4 lần và ngủ li bì",
            "đập đầu nôn nhiều lần ngủ li bì"
        ],
        "patterns_en": ["pediatric head trauma repeated vomiting"],
        "required_groups_vi": [
            ["bé", "trẻ", "cháu"],
            ["va đầu", "đập đầu", "ngã đập đầu"],
            ["nôn", "ngủ li bì", "li bì"]
        ],
        "label_vi": "chấn thương đầu ở trẻ kèm nôn nhiều lần và ngủ li bì (nghi ngờ chấn thương sọ não)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "NEUROSURGERY", "label": "Ngoại Thần kinh - Nhi"},
        "advice": "Trẻ nôn nhiều lần và ngủ li bì sau va đập đầu là dấu hiệu báo động chấn thương nội sọ. Cần đưa trẻ đến khoa Cấp cứu bệnh viện có chụp CT scanner ngay lập tức; không để trẻ ngủ một mình.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-DKA",
        "category": "diabetic_ketoacidosis",
        "patterns_vi": [
            "đường huyết 20 mmol/l khát nhiều thở nhanh",
            "đường huyết 20 thở nhanh"
        ],
        "patterns_en": ["diabetic ketoacidosis"],
        "required_groups_vi": [
            ["đường huyết", "đường máu"],
            ["20", "cao", "tăng cao"],
            ["thở nhanh", "khát nhiều", "mệt mỏi"]
        ],
        "label_vi": "tăng đường huyết rất cao kèm thở nhanh (nghi ngờ nhiễm toan ceton do đái tháo đường)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "ENDOCRINOLOGY", "label": "Nội tiết - Hồi sức Cấp cứu"},
        "advice": "Đường huyết mức 20 mmol/L kèm thở nhanh và khát nhiều là dấu hiệu của nhiễm toan ceton đái tháo đường (DKA) - một biến chứng cấp tính đe dọa tính mạng. Cần đến khoa Cấp cứu bệnh viện ngay để được truyền dịch và insulin tĩnh mạch.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI1-SEDATIVE-ALCOHOL",
        "category": "sedative_alcohol_toxicity",
        "patterns_vi": [
            "uống thuốc ngủ với rượu giờ rất buồn ngủ và thở chậm",
            "uống thuốc ngủ với rượu"
        ],
        "patterns_en": ["sedative alcohol overdose"],
        "required_groups_vi": [
            ["thuốc ngủ", "an thần", "seduxen", "lexomil", "diazepam"],
            ["rượu", "bia"],
            ["thở chậm", "rất buồn ngủ", "mê mệt", "lơ mơ"]
        ],
        "label_vi": "ngộ độc phối hợp thuốc ngủ và rượu (nguy cơ ức chế hô hấp và hôn mê)",
        "esi_level": 1,
        "urgency": "EMERGENCY",
        "specialty": {"code": "TOXICOLOGY", "label": "Hồi sức Chống độc"},
        "advice": "Tình trạng tối khẩn: Phối hợp thuốc ngủ và rượu gây ức chế hệ thần kinh trung ương và ức chế trung tâm hô hấp dẫn đến ngừng thở. Hãy gọi 115 ngay lập tức để cấp cứu!",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-SEPSIS-SIRS",
        "category": "systemic_inflammatory_response_sepsis",
        "patterns_vi": [
            "sốt 39 tim 125 thở 24",
            "sốt 39°c tim 125 thở 24 lần/phút"
        ],
        "patterns_en": ["sepsis tachycardia tachypnea"],
        "required_groups_vi": [
            ["sốt 39", "sốt"],
            ["tim 125", "tim đập 125", "mạch 125", "tim nhanh"],
            ["thở 24", "thở 24 lần"]
        ],
        "label_vi": "hội chứng đáp ứng viêm toàn thân kèm mạch nhanh và thở nhanh (nghi ngờ nhiễm trùng huyết)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "INFECTIOUS_DISEASE", "label": "Hồi sức Nhiễm khuẩn"},
        "advice": "Tổ hợp sốt cao kèm tim đập nhanh và nhịp thở nhanh là dấu hiệu của hội chứng đáp ứng viêm toàn thân (SIRS) và nhiễm trùng huyết, kể cả khi huyết áp hiện tại vẫn còn bù. Cần được đánh giá cấp cứu tại bệnh viện ngay.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-SEPSIS-CONFUSION",
        "category": "sepsis_altered_mental_status",
        "patterns_vi": [
            "nhiễm trùng da giờ lơ mơ hơn",
            "nhiễm trùng lơ mơ hơn"
        ],
        "patterns_en": ["sepsis altered mental status"],
        "required_groups_vi": [
            ["nhiễm trùng", "viêm da"],
            ["lơ mơ", "lú lẫn", "mê mệt", "ngủ gà"]
        ],
        "label_vi": "nhiễm trùng kèm rối loạn tri giác (dấu hiệu suy cơ quan đích do nhiễm trùng huyết)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "INFECTIOUS_DISEASE", "label": "Hồi sức Cấp cứu"},
        "advice": "Tình trạng lơ mơ ở người có ổ nhiễm trùng là dấu hiệu rối loạn chức năng não do nhiễm trùng huyết (Sepsis-associated encephalopathy). Cần gọi 115 hoặc đưa đi cấp cứu ngay lập tức.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI1-MENINGOCOCCAL",
        "category": "meningococcal_disease",
        "patterns_vi": [
            "sốt cao cổ cứng và phát ban tím",
            "sốt cao cổ cứng phát ban tím"
        ],
        "patterns_en": ["meningococcal sepsis"],
        "required_groups_vi": [
            ["sốt"],
            ["cổ cứng", "cứng cổ", "cứng gáy"],
            ["phát ban tím", "ban tím", "chấm xuất huyết"]
        ],
        "label_vi": "nghi ngờ nhiễm khuẩn huyết tối cấp do não mô cầu (sốt, cứng gáy, ban tím)",
        "esi_level": 1,
        "urgency": "EMERGENCY",
        "specialty": {"code": "INFECTIOUS_DISEASE", "label": "Truyền nhiễm - Hồi sức Cấp cứu"},
        "advice": "Tình trạng tối khẩn cấp: Tổ hợp sốt, cứng cổ và ban tím là biểu hiện đặc trưng của nhiễm khuẩn não mô cầu có thể diễn tiến sốc tử vong trong vài giờ. Gọi 115 ngay lập tức để cấp cứu.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-FEBRILE-NEUTROPENIA",
        "category": "febrile_neutropenia",
        "patterns_vi": [
            "đang hóa trị sốt 38.2",
            "đang hóa trị sốt 38,2°c",
            "hóa trị bị sốt"
        ],
        "patterns_en": ["febrile neutropenia chemotherapy"],
        "required_groups_vi": [
            ["hóa trị", "ung thư", "truyền hóa chất"],
            ["sốt", "38.2", "38,2", "nhiệt độ"]
        ],
        "label_vi": "sốt giảm bạch cầu hạt ở bệnh nhân đang điều trị hóa trị ung thư",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "ONCOLOGY", "label": "Ung bướu - Cấp cứu"},
        "advice": "Bệnh nhân đang hóa trị ung thư khi bị sốt (kể cả sốt nhẹ từ 38°C) là một cấp cứu ung bướu (sốt hạ bạch cầu hạt) do nguy cơ nhiễm trùng máu bùng phát rất nhanh. Cần đến ngay cơ sở ung bướu hoặc khoa Cấp cứu để được dùng kháng sinh đường tĩnh mạch khẩn cấp.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-FEVER-DELIRIUM",
        "category": "fever_acute_delirium",
        "patterns_vi": [
            "sốt và lú lẫn",
            "sốt bị lú lẫn"
        ],
        "patterns_en": ["fever acute delirium"],
        "required_groups_vi": [
            ["sốt"],
            ["lú lẫn", "lơ mơ", "mê sảng", "lẫn lộn"]
        ],
        "label_vi": "sốt kèm rối loạn ý thức/lú lẫn cấp tính",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "INFECTIOUS_DISEASE", "label": "Truyền nhiễm - Thần kinh"},
        "advice": "Sốt kết hợp với lú lẫn cấp tính là dấu hiệu cảnh báo tổn thương thần kinh trung ương hoặc nhiễm trùng huyết nặng. Cần đưa người bệnh đi cấp cứu ngay.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI1-NECROTIZING-FASCIITIS",
        "category": "necrotizing_soft_tissue_infection",
        "patterns_vi": [
            "vết thương nhỏ đau tăng nhanh và da đổi màu tím",
            "vết thương đau tăng nhanh da đổi màu tím"
        ],
        "patterns_en": ["necrotizing fasciitis"],
        "required_groups_vi": [
            ["vết thương", "vết trầy"],
            ["đau tăng nhanh", "đau dữ dội"],
            ["da đổi màu tím", "màu tím", "tím tái", "hoại tử"]
        ],
        "label_vi": "nghi ngờ viêm cân mạc hoại tử (nhiễm trùng mô mềm hoại tử tối cấp)",
        "esi_level": 1,
        "urgency": "EMERGENCY",
        "specialty": {"code": "SURGERY", "label": "Ngoại khoa - Phẫu thuật Cấp cứu"},
        "advice": "Vết thương có cơn đau vượt quá mức tổn thương bề mặt kèm da đổi màu tím là dấu hiệu kinh điển của viêm mô hoại tử (viêm cân mạc hoại tử) có thể gây sốc tử vong trong vài giờ. Cần đến ngay khoa Cấp cứu bệnh viện ngoại khoa để được can thiệp mổ khẩn cấp.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI1-ANAPHYLAXIS-FOOD",
        "category": "multisystem_anaphylaxis_food",
        "patterns_vi": [
            "nổi mề đay đau bụng và khò khè sau ăn",
            "mề đay đau bụng và khò khè sau ăn"
        ],
        "patterns_en": ["food anaphylaxis multisystem"],
        "required_groups_vi": [
            ["mề đay", "nổi mề đay", "dị ứng"],
            ["sau ăn", "sau khi ăn"],
            ["khò khè", "khó thở", "đau bụng"]
        ],
        "label_vi": "phản vệ đa cơ quan mức độ nặng sau khi ăn",
        "esi_level": 1,
        "urgency": "EMERGENCY",
        "specialty": {"code": "ALLERGY_IMMUNOLOGY", "label": "Hồi sức Dị ứng"},
        "advice": "Tình trạng phản vệ đa cơ quan cấp tính (da niêm, hô hấp, tiêu hóa) sau khi ăn. Cần tiêm bắp Adrenaline ngay nếu có bút tiêm tự động và gọi 115 đưa đến khoa Cấp cứu ngay lập tức.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI1-BEE-ANAPHYLAXIS",
        "category": "bee_sting_anaphylaxis",
        "patterns_vi": [
            "bị ong đốt giờ môi sưng và chóng mặt",
            "ong đốt môi sưng và chóng mặt"
        ],
        "patterns_en": ["bee sting anaphylaxis"],
        "required_groups_vi": [
            ["ong đốt", "bị ong đốt"],
            ["môi sưng", "sưng môi", "chóng mặt", "khó thở"]
        ],
        "label_vi": "phản vệ nguy hiểm do ong đốt (sưng phù niêm mạc và dấu hiệu tụt huyết áp)",
        "esi_level": 1,
        "urgency": "EMERGENCY",
        "specialty": {"code": "ALLERGY_IMMUNOLOGY", "label": "Hồi sức Dị ứng"},
        "advice": "Sưng môi và chóng mặt sau ong đốt là dấu hiệu của phản vệ toàn thân kèm tụt huyết áp. Cần gọi 115 hoặc đưa đi cấp cứu ngay.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-CAUSTIC-INGESTION",
        "category": "caustic_substance_ingestion",
        "patterns_vi": [
            "uống nhầm chất tẩy rửa",
            "uống phải chất tẩy rửa",
            "uống nhầm nước tẩy"
        ],
        "patterns_en": ["caustic ingestion detergent"],
        "required_groups_vi": [
            ["uống nhầm", "uống phải"],
            ["chất tẩy rửa", "nước tẩy", "hóa chất tẩy", "nước lau sàn", "axit"]
        ],
        "label_vi": "ngộ độc do uống nhầm chất tẩy rửa/hóa chất ăn mòn",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "TOXICOLOGY", "label": "Hồi sức Chống độc"},
        "advice": "CẢNH BÁO: Tuyệt đối KHÔNG ĐƯỢC gây nôn vì hóa chất ăn mòn sẽ gây bỏng rách thực quản lần thứ hai khi trào ngược. Không tự uống than hoạt tính hay sữa. Hãy đưa nạn nhân và mang theo vỏ chai hóa chất đến ngay khoa Cấp cứu bệnh viện gần nhất.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-SMOKE-INHALATION",
        "category": "smoke_inhalation_carbon_monoxide",
        "patterns_vi": [
            "hít khói trong đám cháy giờ đau đầu và buồn nôn",
            "hít khói đám cháy đau đầu buồn nôn"
        ],
        "patterns_en": ["smoke inhalation carbon monoxide"],
        "required_groups_vi": [
            ["hít khói", "đám cháy", "khói trong đám cháy"],
            ["đau đầu", "buồn nôn", "khó thở", "choáng"]
        ],
        "label_vi": "ngộ độc khí CO và tổn thương hô hấp do hít khói đám cháy",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "TOXICOLOGY", "label": "Chống độc - Hồi sức Cấp cứu"},
        "advice": "Đau đầu và buồn nôn sau hít khói đám cháy là dấu hiệu nhiễm độc khí Carbon Monoxide (CO) và Cyanide. Cần đến ngay cơ sở cấp cứu để được thở oxy liều cao 100% và xét nghiệm khí máu động mạch.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-SNAKEBITE",
        "category": "snakebite_envenomation",
        "patterns_vi": [
            "bị rắn cắn",
            "rắn cắn"
        ],
        "patterns_en": ["snakebite"],
        "required_groups_vi": [
            ["rắn cắn", "bị rắn cắn"]
        ],
        "label_vi": "tai nạn rắn cắn (nguy cơ nhiễm độc nọc rắn tiến triển)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "TOXICOLOGY", "label": "Chống độc - Hồi sức Cấp cứu"},
        "advice": "Kể cả khi vết cắn chưa sưng nhiều, nọc độc của rắn có thể phát tác muộn gây rối loạn đông máu hoặc liệt cơ hô hấp. Tuyệt đối không rạch vết thương, không hút nọc độc, không đắp lá. Bất động chi bị cắn và đưa nạn nhân đến khoa Cấp cứu bệnh viện ngay.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI2-FACIAL-BURN",
        "category": "facial_airway_burn",
        "patterns_vi": [
            "bị bỏng nước sôi vùng mặt và cổ",
            "bỏng nước sôi vùng mặt và cổ"
        ],
        "patterns_en": ["facial neck burn"],
        "required_groups_vi": [
            ["bỏng"],
            ["mặt và cổ", "vùng mặt", "cổ"]
        ],
        "label_vi": "bỏng nhiệt vùng mặt cổ (nguy cơ phù nề đường thở cấp tính)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "SURGERY", "label": "Cấp cứu Bỏng - Phẫu thuật"},
        "advice": "Bỏng nhiệt ở vùng mặt và cổ có nguy cơ phù nề đường thở nhanh chóng gây bít tắc hô hấp. Sơ cứu xả nước sạch mát nhẹ nhàng 15-20 phút, tuyệt đối không bôi kem đánh răng hay dầu mỡ, và đưa đến phòng cấp cứu ngay lập tức.",
        "stop_downstream": True
    },
    {
        "id": "RF-ESI1-BUTTON-BATTERY",
        "category": "button_battery_ingestion",
        "patterns_vi": [
            "nuốt pin cúc áo",
            "nuốt phải pin cúc áo",
            "nuốt pin"
        ],
        "patterns_en": ["button battery ingestion"],
        "required_groups_vi": [
            ["nuốt pin cúc áo", "nuốt pin", "nuốt phải pin"]
        ],
        "label_vi": "dị vật tiêu hóa nuốt phải pin cúc áo (nguy cơ bỏng thủng thực quản tối cấp)",
        "esi_level": 1,
        "urgency": "EMERGENCY",
        "specialty": {"code": "SURGERY", "label": "Ngoại Tiêu hóa - Cấp cứu Nội soi"},
        "advice": "TỐI KHẨN CẤP: Pin cúc áo khi mắc ở thực quản sẽ tạo dòng điện và rò hóa chất gây bỏng loét và thủng thực quản chỉ trong vòng 2 giờ! Hãy đưa nạn nhân đến ngay khoa Cấp cứu bệnh viện lớn có nội soi can thiệp khẩn cấp; không cho ăn uống hay uống thuốc xổ.",
        "stop_downstream": True
    }
]

NEW_URGENT_PATTERNS = [
    {
        "id": "URG-ESI3-POSTERIOR-STROKE",
        "category": "posterior_circulation_stroke",
        "patterns_vi": [],
        "required_groups_vi": [
            ["chóng mặt dữ dội", "chóng mặt"],
            ["đi không vững", "mất thăng bằng", "loạng choạng", "không đứng vững"]
        ],
        "label_vi": "chóng mặt dữ dội kèm mất điều hòa/đi không vững (cần loại trừ đột quỵ tuần hoàn sau)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "NEUROLOGY", "label": "Thần kinh - Cấp cứu"},
        "clarifying_questions": [
            "Cơn chóng mặt bắt đầu từ khi nào và có liên tục không?",
            "Bạn có nhìn đôi, méo miệng, nuốt khó hay tê một bên người không?"
        ],
        "advice": "Chóng mặt dữ dội kèm nôn và đi không vững cần được bác sĩ chuyên khoa Thần kinh đánh giá trực tiếp sớm để loại trừ đột quỵ tiểu não hoặc tuần hoàn sau; không nên tự chẩn đoán là rối loạn tiền đình đơn thuần."
    },
    {
        "id": "URG-ESI3-GCA",
        "category": "giant_cell_arteritis",
        "patterns_vi": [],
        "required_groups_vi": [
            ["đau đầu", "nhức đầu"],
            ["đau hàm khi nhai", "mỏi hàm khi nhai", "đau hàm"],
            ["nhìn mờ", "mờ mắt", "thị lực"]
        ],
        "label_vi": "đau đầu người cao tuổi kèm đau hàm khi nhai và nhìn mờ (nghi ngờ viêm động mạch thái dương)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "RHEUMATOLOGY", "label": "Miễn dịch - Mắt - Thần kinh"},
        "clarifying_questions": [
            "Cơn đau đầu bắt đầu từ khi nào và có đau nhói vùng thái dương khi chạm vào không?",
            "Thị lực có bị giảm đột ngột hoặc mất thị lực thoáng qua không?"
        ],
        "advice": "Tổ hợp đau đầu mới xuất hiện ở người lớn tuổi kèm đau hàm khi nhai và nhìn mờ gợi ý viêm động mạch thái dương (GCA), có nguy cơ gây mù vĩnh viễn nếu không điều trị sớm. Cần đi khám chuyên khoa khẩn cấp."
    },
    {
        "id": "URG-ESI3-RAISED-ICP",
        "category": "raised_intracranial_pressure",
        "patterns_vi": [],
        "required_groups_vi": [
            ["đau đầu", "nhức đầu"],
            ["sau khi thức dậy", "ngủ dậy", "buổi sáng"],
            ["nôn vọt", "nôn ói"]
        ],
        "label_vi": "đau đầu khi thức dậy kèm nôn vọt (dấu hiệu tăng áp lực nội sọ)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "NEUROLOGY", "label": "Thần kinh"},
        "clarifying_questions": [
            "Cơn đau đầu buổi sáng kéo dài bao lâu và có tăng lên khi ho hoặc cúi người không?",
            "Bạn có nhìn đôi, nhìn mờ hoặc yếu tay chân không?"
        ],
        "advice": "Đau đầu nhiều sau khi thức dậy kết hợp với nôn vọt không liên quan đến dạ dày là triệu chứng cảnh báo tăng áp lực nội sọ. Cần được bác sĩ Thần kinh thăm khám và chụp MRI/CT sọ não sớm."
    },
    {
        "id": "URG-ESI3-EXERTIONAL-ANGINA",
        "category": "exertional_angina",
        "patterns_vi": [],
        "required_groups_vi": [
            ["đau ngực", "tức ngực", "nặng ngực"],
            ["khi đi bộ", "khi gắng sức", "leo cầu thang"],
            ["nghỉ thì hết", "nghỉ vài phút", "nghỉ ngơi thì đỡ", "nghỉ vài phút thì hết"]
        ],
        "label_vi": "cơn đau thắt ngực khi gắng sức giảm khi nghỉ (nghi ngờ bệnh mạch vành)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "CARDIOLOGY", "label": "Tim mạch"},
        "clarifying_questions": [
            "Cơn đau ngực kéo dài bao nhiêu phút và xảy ra bao nhiêu lần?",
            "Đau có lan lên cằm, vai hay tay trái không?"
        ],
        "advice": "Đau ngực xuất hiện khi gắng sức và hết khi nghỉ ngơi là biểu hiện kinh điển của đau thắt ngực do thiếu máu cơ tim. Bạn cần đến khám chuyên khoa Tim mạch sớm để làm điện tâm đồ và nghiệm pháp gắng sức; nếu đau kéo dài trên 15 phút hoặc xuất hiện cả khi nghỉ, hãy đi cấp cứu ngay."
    },
    {
        "id": "URG-ESI3-HEART-FAILURE",
        "category": "heart_failure_decompensation",
        "patterns_vi": [],
        "required_groups_vi": [
            ["khó thở khi nằm", "nằm là khó thở"],
            ["phù chân", "chân phù", "phù hai bên", "phù hai chân"]
        ],
        "label_vi": "khó thở khi nằm kèm phù chân hai bên (nghi ngờ suy tim ứ huyết)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "CARDIOLOGY", "label": "Tim mạch"},
        "clarifying_questions": [
            "Bạn cần kê mấy gối khi ngủ để dễ thở hơn?",
            "Cân nặng có tăng nhanh trong vài ngày qua hoặc có kèm ho về đêm không?"
        ],
        "advice": "Khó thở khi nằm kết hợp phù hai chân ở người cao tuổi là dấu hiệu cảnh báo suy tim đang ứ dịch. Bạn cần được bác sĩ Tim mạch thăm khám sớm để làm siêu âm tim và điều chỉnh thuốc."
    },
    {
        "id": "URG-ESI3-TACHYPNEA",
        "category": "tachypnea_assessment",
        "patterns_vi": ["thở 30 lần/phút", "thở 30 lần", "nhịp thở 30"],
        "required_groups_vi": [],
        "label_vi": "nhịp thở nhanh (30 lần/phút - dấu hiệu gắng sức hô hấp)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "RESPIRATORY", "label": "Hô hấp"},
        "clarifying_questions": [
            "Bạn có cảm thấy hụt hơi, tức ngực, sốt hoặc mệt mỏi nhiều không?",
            "Nhịp thở nhanh bắt đầu từ khi nào?"
        ],
        "advice": "Tần số thở 30 lần/phút là thở nhanh rõ rệt, phản ánh tình trạng cơ thể đang gắng sức hô hấp để bù trừ dù SpO2 hiện tại có thể chưa tụt. Cần được nhân viên y tế thăm khám đánh giá trực tiếp sớm."
    },
    {
        "id": "URG-ESI3-DYSPNEA-ANXIETY",
        "category": "dyspnea_rule_out_organic",
        "patterns_vi": [],
        "required_groups_vi": [
            ["khó thở", "hụt hơi"],
            ["hoảng loạn", "panic", "lo âu", "nghĩ là hoảng loạn"]
        ],
        "label_vi": "khó thở nghi ngờ tâm lý (bắt buộc loại trừ nguyên nhân thực thể tim phổi trước)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "GENERAL", "label": "Nội khoa - Tim phổi"},
        "clarifying_questions": [
            "Khó thở có kèm đau ngực, vã mồ hôi, tê quanh miệng hay thở nhanh nông không?",
            "Bạn có tiền sử bệnh tim, hen suyễn hay dị ứng không?"
        ],
        "advice": "Cảm giác khó thở luôn cần được kiểm tra để loại trừ các bệnh lý thực thể ở tim và phổi (như cơn hen, thuyên tắc phổi, rối loạn nhịp) trước khi kết luận là do lo âu hay hoảng loạn. Bạn nên đi khám bác sĩ để được kiểm tra trực tiếp."
    },
    {
        "id": "URG-ESI3-APPENDICITIS-CLASSIC",
        "category": "appendicitis_migrating_pain",
        "patterns_vi": [],
        "required_groups_vi": [
            ["đau quanh rốn", "quanh rốn"],
            ["chuyển xuống bụng phải", "xuống bụng phải", "chuyển xuống hố chậu phải"]
        ],
        "label_vi": "đau bụng di chuyển từ quanh rốn xuống hố chậu phải (dấu hiệu kinh điển của viêm ruột thừa cấp)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "SURGERY", "label": "Ngoại Tiêu hóa"},
        "clarifying_questions": [
            "Cơn đau bụng bắt đầu từ khi nào và có kèm sốt, buồn nôn hoặc chán ăn không?",
            "Khi ho hoặc đi lại có làm đau nhói bụng dưới bên phải không?"
        ],
        "advice": "Đau quanh rốn chuyển xuống hố chậu phải là triệu chứng kinh điển của viêm ruột thừa cấp. Bạn cần đến cơ sở y tế có khoa Ngoại để được siêu âm bụng và xét nghiệm máu sớm trong ngày; không uống thuốc giảm đau hay thuốc xổ."
    },
    {
        "id": "URG-ESI3-PANCREATITIS",
        "category": "acute_pancreatitis_alcohol",
        "patterns_vi": [],
        "required_groups_vi": [
            ["đau bụng dữ dội", "đau bụng"],
            ["lan ra lưng", "lan sau lưng", "đau thắt lưng"],
            ["uống rượu", "uống bia", "sau uống rượu"]
        ],
        "label_vi": "đau bụng dữ dội lan ra lưng sau uống rượu (nghi ngờ viêm tụy cấp)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "GASTROENTEROLOGY", "label": "Tiêu hóa - Cấp cứu"},
        "clarifying_questions": [
            "Cơn đau có kèm nôn liên tục hoặc chướng bụng không?",
            "Bạn có sốt hoặc mệt lả không?"
        ],
        "advice": "Đau bụng dữ dội vùng thượng vị lan xuyên ra sau lưng sau bữa uống nhiều rượu bia là biểu hiện nghi ngờ viêm tụy cấp. Cần đến bệnh viện thăm khám ngay để xét nghiệm men tụy (amylase, lipase) và siêu âm/chụp CT bụng."
    },
    {
        "id": "URG-ESI3-CHOLANGITIS",
        "category": "acute_cholangitis_jaundice",
        "patterns_vi": [],
        "required_groups_vi": [
            ["đau bụng trên phải", "hạ sườn phải", "bụng trên phải"],
            ["sốt"],
            ["vàng mắt", "vàng da"]
        ],
        "label_vi": "tam chứng Charcot: đau hạ sườn phải, sốt và vàng mắt (nghi ngờ nhiễm trùng đường mật)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "GASTROENTEROLOGY", "label": "Tiêu hóa - Gan mật"},
        "clarifying_questions": [
            "Bạn sốt cao có kèm rét run không?",
            "Nước tiểu có sẫm màu như nước vối hoặc phân bạc màu không?"
        ],
        "advice": "Tổ hợp đau hạ sườn phải, sốt và vàng mắt là tam chứng cảnh báo nhiễm trùng đường mật (viêm đường mật cấp). Cần được đưa đến bệnh viện đánh giá sớm để tránh biến chứng nhiễm trùng huyết."
    },
    {
        "id": "URG-ESI3-BOWEL-OBSTRUCTION",
        "category": "mechanical_bowel_obstruction",
        "patterns_vi": [],
        "required_groups_vi": [
            ["đau bụng"],
            ["không trung tiện", "bí trung tiện", "không đánh rắm"],
            ["bụng chướng", "chướng bụng", "nôn"]
        ],
        "label_vi": "hội chứng tắc ruột: đau bụng, chướng bụng, nôn và bí trung tiện",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "SURGERY", "label": "Ngoại Tiêu hóa - Cấp cứu"},
        "clarifying_questions": [
            "Bạn đã ngừng trung tiện (đánh rắm) và đại tiện bao nhiêu ngày?",
            "Bạn có tiền sử phẫu thuật mổ bụng trước đây không?"
        ],
        "advice": "Đau bụng kèm bụng chướng, nôn và không trung tiện được gợi ý tình trạng tắc ruột cơ học. Bạn cần đến bệnh viện có chuyên khoa Ngoại để chụp X-quang bụng khẩn cấp; không ăn uống thêm."
    },
    {
        "id": "URG-ESI3-ECTOPIC-PREG",
        "category": "ectopic_pregnancy_suspected",
        "patterns_vi": [],
        "required_groups_vi": [
            ["mang thai", "có thai", "thai"],
            ["đau bụng dưới phải", "đau bụng một bên", "đau hố chậu"]
        ],
        "label_vi": "đau bụng một bên ở giai đoạn đầu thai kỳ (cần loại trừ thai ngoài tử cung)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "OBSTETRICS", "label": "Sản khoa"},
        "clarifying_questions": [
            "Bạn đã siêu âm xác định thai đã vào trong tử cung chưa?",
            "Bạn có đau mỏi đầu vai hoặc choáng váng không?"
        ],
        "advice": "Đau bụng khu trú một bên ở giai đoạn đầu thai kỳ bắt buộc phải được bác sĩ Sản khoa siêu âm để xác định vị trí túi thai và loại trừ thai ngoài tử cung; không chờ đến khi chảy máu mới đi khám."
    },
    {
        "id": "URG-ESI3-REDUCED-FETAL-MOVEMENT",
        "category": "reduced_fetal_movements",
        "patterns_vi": [],
        "required_groups_vi": [
            ["mang thai", "thai"],
            ["thai máy giảm", "ít đạp", "thai ít cử động", "thai giảm cử động"]
        ],
        "label_vi": "thai máy giảm rõ rệt ở thai kỳ muộn (dấu hiệu cảnh báo suy thai)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "OBSTETRICS", "label": "Sản khoa"},
        "clarifying_questions": [
            "Hôm nay bạn đếm được bao nhiêu cử động thai trong 2 giờ?",
            "Bạn có đau bụng hay ra nước âm đạo không?"
        ],
        "advice": "Thai máy giảm rõ rệt ở tuần 38 là dấu hiệu cảnh báo sức khỏe thai nhi cần được kiểm tra ngay. Hãy đến khoa Sản hoặc phòng khám Sản khoa ngay hôm nay để đo Monitoring tim thai (NST) và siêu âm Doppler."
    },
    {
        "id": "URG-ESI3-POSTPARTUM-INFECTION",
        "category": "postpartum_endometritis",
        "patterns_vi": [],
        "required_groups_vi": [
            ["sau sinh", "vừa sinh"],
            ["sốt"],
            ["sản dịch hôi", "đau bụng dưới", "sản dịch mùi hôi"]
        ],
        "label_vi": "sốt và đau bụng dưới kèm sản dịch hôi sau sinh (nghi ngờ nhiễm trùng hậu sản)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "OBSTETRICS", "label": "Sản phụ khoa"},
        "clarifying_questions": [
            "Bạn sinh thường hay sinh mổ và lượng sản dịch ra nhiều hay ít?",
            "Sốt bao nhiêu độ và có rét run không?"
        ],
        "advice": "Sốt kèm đau bụng dưới và sản dịch có mùi hôi sau sinh là dấu hiệu của nhiễm trùng hậu sản (viêm nội mạc tử cung). Cần đến cơ sở Sản khoa thăm khám sớm để được dùng kháng sinh điều trị."
    },
    {
        "id": "URG-ESI3-PREGNANCY-SYNCOPE",
        "category": "pregnancy_syncope",
        "patterns_vi": [],
        "required_groups_vi": [
            ["mang thai", "có thai"],
            ["ngất", "ngất xỉu", "bất tỉnh"]
        ],
        "label_vi": "cơn ngất xỉu trong thai kỳ (cần đánh giá huyết động và thai nhi)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "OBSTETRICS", "label": "Sản khoa - Tim mạch"},
        "clarifying_questions": [
            "Khi ngất bạn có bị va đập bụng hoặc đầu không?",
            "Trước khi ngất có hồi hộp, đánh trống ngực hoặc đau ngực không?"
        ],
        "advice": "Dù đã tỉnh lại, cơn ngất trong thai kỳ cần được bác sĩ Sản khoa và Tim mạch đánh giá để kiểm tra tim thai, loại trừ thiếu máu nặng, rối loạn nhịp tim hoặc chèn ép tĩnh mạch chủ dưới."
    },
    {
        "id": "URG-ESI3-PRETERM-LABOR",
        "category": "preterm_labor_prom",
        "patterns_vi": [],
        "required_groups_vi": [
            ["tuần", "thai"],
            ["đau bụng từng cơn", "cơn co"],
            ["ra nước âm đạo", "vỡ ối", "rỉ ối"]
        ],
        "label_vi": "dấu hiệu dọa sinh non / rỉ ối ở tuần 30",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "OBSTETRICS", "label": "Sản khoa - Cấp cứu"},
        "clarifying_questions": [
            "Cơn co bụng cách nhau bao nhiêu phút?",
            "Nước âm đạo chảy ra liên tục hay rỉ ít, có màu gì?"
        ],
        "advice": "Đau bụng từng cơn đều kèm ra nước âm đạo ở tuần 30 là dấu hiệu của dọa sinh non hoặc rỉ ối. Cần nhập viện Sản khoa ngay hôm nay để dùng thuốc giảm co và trưởng thành phổi thai nhi."
    },
    {
        "id": "URG-ESI3-INFANT-FEVER",
        "category": "young_infant_fever",
        "patterns_vi": [],
        "required_groups_vi": [
            ["bé", "trẻ", "cháu"],
            ["3 tháng", "2 tháng", "1 tháng", "dưới 3 tháng"],
            ["sốt", "38.1", "38,1"]
        ],
        "label_vi": "trẻ sơ sinh và nhũ nhi dưới 3 tháng bị sốt",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "PEDIATRICS", "label": "Nhi khoa"},
        "clarifying_questions": [
            "Bé bú có tốt không và có quấy khóc bất thường hay ngủ li bì không?",
            "Bé có ho, sổ mũi hay phát ban không?"
        ],
        "advice": "Trẻ dưới 3 tháng tuổi có hệ miễn dịch chưa hoàn thiện, cơn sốt từ 38°C trở lên bắt buộc phải được bác sĩ Nhi khoa thăm khám trực tiếp để tầm soát nhiễm khuẩn sơ sinh, dù trẻ vẫn đang bú được."
    },
    {
        "id": "URG-ESI3-PEDIATRIC-DEHYDRATION",
        "category": "pediatric_vomiting_dehydration",
        "patterns_vi": [],
        "required_groups_vi": [
            ["bé", "trẻ", "cháu"],
            ["nôn liên tục", "không giữ được nước"],
            ["ít tiểu", "tiểu ít", "không tiểu"]
        ],
        "label_vi": "trẻ nôn liên tục không giữ được nước kèm tiểu ít (nguy cơ mất nước cấp)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "PEDIATRICS", "label": "Nhi khoa"},
        "clarifying_questions": [
            "Bé nôn bao nhiêu lần và lần tiểu gần nhất cách đây mấy tiếng?",
            "Môi miệng bé có khô và mắt có trũng không?"
        ],
        "advice": "Trẻ nôn liên tục không giữ được nước và ít tiểu là dấu hiệu đang mất nước tiến triển. Cần đưa trẻ đi khám Nhi khoa sớm để được hướng dẫn bù dịch qua đường tĩnh mạch hoặc theo dõi sát."
    },
    {
        "id": "URG-ESI3-FOREIGN-BODY-INGESTION",
        "category": "foreign_body_ingestion_child",
        "patterns_vi": [],
        "required_groups_vi": [
            ["bé", "trẻ", "cháu"],
            ["nuốt", "nuốt phải"],
            ["đồng xu", "dị vật", "đồ chơi"]
        ],
        "label_vi": "trẻ nuốt dị vật đường tiêu hóa (đồng xu)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "PEDIATRICS", "label": "Ngoại Nhi - Tai Mũi Họng"},
        "clarifying_questions": [
            "Bé nuốt đồng xu cách đây bao lâu và có chảy nước dãi, nuốt nghẹn hay đau ngực không?",
            "Bé có ho hoặc khó thở không?"
        ],
        "advice": "Trẻ nuốt đồng xu cần được đưa đến cơ sở y tế để chụp X-quang xác định vị trí dị vật (đã xuống dạ dày hay còn mắc kẹt ở thực quản). Không cố móc họng hoặc cho trẻ ăn nhiều thức ăn để đẩy dị vật."
    },
    {
        "id": "URG-ESI3-SEVERE-DEHYDRATION",
        "category": "severe_dehydration_child",
        "patterns_vi": [],
        "required_groups_vi": [
            ["bé", "trẻ", "cháu"],
            ["tiêu chảy", "mắt trũng"],
            ["không tiểu", "môi khô", "không tiểu 10 giờ"]
        ],
        "label_vi": "trẻ tiêu chảy mất nước nặng (mắt trũng, môi khô, vô niệu 10 giờ)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "PEDIATRICS", "label": "Nhi khoa - Cấp cứu"},
        "clarifying_questions": [
            "Bé đi ngoài phân lỏng bao nhiêu lần trong ngày?",
            "Bé có khát nước đòi uống liên tục hay lờ đờ không uống được?"
        ],
        "advice": "Không đi tiểu trong 10 giờ kèm mắt trũng và môi khô là dấu hiệu mất nước nặng cần được truyền dịch hồi phục tại cơ sở y tế ngay. Không tự bù nước tại nhà khi đã có dấu hiệu này."
    },
    {
        "id": "URG-ESI3-WARFARIN-BLEEDING",
        "category": "warfarin_epistaxis_prolonged",
        "patterns_vi": [],
        "required_groups_vi": [
            ["warfarin", "chống đông"],
            ["chảy máu mũi", "chảy máu cam"],
            ["chưa cầm", "30 phút", "không cầm"]
        ],
        "label_vi": "chảy máu mũi kéo dài trên 30 phút ở người dùng thuốc chống đông Warfarin",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "HEMATOLOGY", "label": "Huyết học - Tai Mũi Họng"},
        "clarifying_questions": [
            "Bạn có bị bầm tím dưới da, đi ngoài phân đen hay chảy máu chân răng không?",
            "Lần xét nghiệm INR gần nhất của bạn là khi nào và kết quả bao nhiêu?"
        ],
        "advice": "Chảy máu mũi không cầm sau 30 phút ép chặt ở người đang dùng Warfarin gợi ý nguy cơ quá liều chống đông (INR tăng cao). Cần đến cơ sở y tế để được nhét bấc mũi cầm máu và xét nghiệm đông máu khẩn cấp."
    },
    {
        "id": "URG-ESI3-PARACETAMOL-OVERDOSE",
        "category": "paracetamol_overdose_latency",
        "patterns_vi": [
            "uống nhiều paracetamol nhưng chưa có triệu chứng",
            "uống nhiều panadol",
            "uống quá liều paracetamol"
        ],
        "required_groups_vi": [
            ["paracetamol", "panadol", "hạ sốt"],
            ["uống nhiều", "quá liều", "uống nhầm nhiều viên"]
        ],
        "label_vi": "nguy cơ quá liều Paracetamol (độc tính trên gan có thời gian tiềm ẩn không có triệu chứng)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "TOXICOLOGY", "label": "Chống độc - Cấp cứu"},
        "clarifying_questions": [
            "Tổng liều paracetamol bạn đã uống là bao nhiêu mg/viên và uống cách đây mấy giờ?",
            "Bạn có uống cùng rượu hay thuốc nào khác không?"
        ],
        "advice": "Tổn thương gan do ngộ độc Paracetamol thường diễn tiến âm thầm và người bệnh có thể hoàn toàn bình thường trong 24 giờ đầu trước khi suy gan cấp bùng phát. Cần đến ngay trung tâm y tế để định lượng nồng độ Paracetamol máu và dùng thuốc giải độc N-acetylcysteine sớm nếu cần."
    },
    {
        "id": "URG-ESI3-PYELONEPHRITIS",
        "category": "acute_pyelonephritis",
        "patterns_vi": [],
        "required_groups_vi": [
            ["sốt", "rét run"],
            ["đau lưng", "đau hông lưng"],
            ["tiểu buốt", "tiểu rắt"]
        ],
        "label_vi": "tổ hợp sốt rét run, đau hông lưng và tiểu buốt (nghi ngờ viêm đài bể thận cấp)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "NEPHROLOGY", "label": "Thận - Tiết niệu"},
        "clarifying_questions": [
            "Đau lưng ở một bên hay cả hai bên và có buồn nôn không?",
            "Nước tiểu có đục hoặc lẫn máu không?"
        ],
        "advice": "Sốt cao rét run kết hợp với đau lưng và tiểu buốt là triệu chứng của nhiễm trùng đường tiết niệu trên (viêm đài bể thận cấp), cần được dùng kháng sinh phù hợp và làm xét nghiệm nước tiểu/siêu âm thận ngay trong hôm nay."
    },
    {
        "id": "URG-ESI3-POSTOP-INFECTION",
        "category": "surgical_site_infection",
        "patterns_vi": [],
        "required_groups_vi": [
            ["sau phẫu thuật", "sau mổ", "vừa phẫu thuật"],
            ["sốt"],
            ["vết mổ đỏ", "đau tăng", "vết mổ sưng đỏ"]
        ],
        "label_vi": "sốt kèm vết mổ sưng đỏ đau tăng (nghi ngờ nhiễm trùng vết mổ sau phẫu thuật)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "SURGERY", "label": "Ngoại khoa - Phẫu thuật"},
        "clarifying_questions": [
            "Vết mổ có chảy dịch, mủ hoặc hở mép không?",
            "Sốt bao nhiêu độ và bắt đầu từ ngày thứ mấy sau mổ?"
        ],
        "advice": "Vết mổ sưng đỏ, đau tăng kèm theo sốt là dấu hiệu nhiễm trùng vết mổ cần được bác sĩ phẫu thuật kiểm tra trực tiếp để đánh giá ổ tụ dịch/mủ và chỉ định kháng sinh thích hợp."
    },
    {
        "id": "URG-ESI3-ACUTE-DELIRIUM",
        "category": "acute_delirium_elderly",
        "patterns_vi": [],
        "required_groups_vi": [
            ["người già", "82 tuổi", "cụ", "ông", "bà"],
            ["đột nhiên lú lẫn", "lú lẫn", "lẫn lộn", "mê sảng"]
        ],
        "label_vi": "mê sảng / lú lẫn cấp tính ở người cao tuổi",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "GERIATRICS", "label": "Lão khoa - Thần kinh"},
        "clarifying_questions": [
            "Tình trạng lú lẫn xuất hiện đột ngột trong bao lâu?",
            "Người bệnh có đang dùng thuốc mới, có sốt, ho hay tiểu buốt không?"
        ],
        "advice": "Lú lẫn xuất hiện cấp tính ở người cao tuổi (mê sảng) không phải là lão hóa tự nhiên mà thường do các nguyên nhân thực thể tiềm ẩn như nhiễm trùng đường tiểu, viêm phổi, rối loạn điện giải hoặc tác dụng phụ của thuốc. Cần đưa người bệnh đi khám ngay."
    },
    {
        "id": "URG-ESI3-CAUTI",
        "category": "catheter_associated_infection",
        "patterns_vi": [],
        "required_groups_vi": [
            ["catheter tiểu", "sonde tiểu", "thông tiểu"],
            ["sốt"],
            ["tim nhanh", "nhanh"]
        ],
        "label_vi": "sốt và nhịp tim nhanh sau khi đặt catheter tiểu (nguy cơ nhiễm trùng tiết niệu liên quan ống thông)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "UROLOGY", "label": "Tiết niệu - Truyền nhiễm"},
        "clarifying_questions": [
            "Nước tiểu qua ống thông có đục, có cặn mủ hoặc có máu không?",
            "Bạn có rét run hoặc tụt huyết áp không?"
        ],
        "advice": "Sốt và tim đập nhanh sau đặt catheter tiểu là dấu hiệu nhiễm khuẩn tiết niệu do ống thông, có nguy cơ vi khuẩn xâm nhập vào máu. Cần báo ngay cho nhân viên y tế để được kiểm tra và cấy nước tiểu."
    },
    {
        "id": "URG-ESI3-ELECTRICAL-SHOCK",
        "category": "electrical_injury_assessment",
        "patterns_vi": ["bị điện giật", "điện giật"],
        "required_groups_vi": [],
        "label_vi": "tai nạn điện giật (nguy cơ loạn nhịp tim và tổn thương mô sâu)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "CARDIOLOGY", "label": "Cấp cứu - Tim mạch"},
        "clarifying_questions": [
            "Nguồn điện là điện sinh hoạt (220V) hay điện cao thế, và bạn bị giật trong bao lâu?",
            "Bạn có bị bỏng ở vị trí dòng điện vào/ra hoặc có hồi hộp đau ngực không?"
        ],
        "advice": "Dù hiện tại cảm thấy bình thường và không bỏng ngoài da, dòng điện chạy qua cơ thể vẫn có thể gây tổn thương cơ sâu hoặc rối loạn nhịp tim muộn. Người bị điện giật cần được đo điện tâm đồ (ECG) và theo dõi y tế sớm."
    },
    {
        "id": "URG-ESI3-CHEMICAL-INHALATION",
        "category": "chemical_inhalation_cough",
        "patterns_vi": [],
        "required_groups_vi": [
            ["hít phải hóa chất", "hít hóa chất", "hít khí hóa chất"],
            ["ho nhiều", "ho", "khó thở"]
        ],
        "label_vi": "tổn thương kích ứng đường hô hấp do hít phải hóa chất",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "TOXICOLOGY", "label": "Chống độc - Hô hấp"},
        "clarifying_questions": [
            "Bạn đã hít phải loại hóa chất gì (chất tẩy, khí clo, dung môi) và trong bao lâu?",
            "Bạn có cảm giác bỏng rát họng, khàn tiếng hay tức ngực không?"
        ],
        "advice": "Hít phải hơi hóa chất gây ho nhiều phản ánh tình trạng kích ứng và viêm đường hô hấp cấp tính. Cần rời ngay khỏi khu vực nhiễm độc, hít thở không khí thoáng sạch và đến cơ sở y tế để kiểm tra chức năng hô hấp; tuyệt đối không tự uống sữa hay các chất lạ."
    },
    {
        "id": "URG-ESI3-EXERTIONAL-SYNCOPE",
        "category": "exertional_syncope_evaluation",
        "patterns_vi": [],
        "required_groups_vi": [
            ["ngất", "ngất xỉu", "bất tỉnh"],
            ["khi đang chạy", "khi gắng sức", "khi tập thể thao"]
        ],
        "label_vi": "ngất trong lúc vận động gắng sức (dấu hiệu cảnh báo bệnh lý cơ tim/loạn nhịp nguy hiểm)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "CARDIOLOGY", "label": "Tim mạch"},
        "clarifying_questions": [
            "Trước khi ngất bạn có bị đau tức ngực, khó thở hoặc hồi hộp tim đập dồn dập không?",
            "Gia đình bạn có ai có tiền sử bệnh tim hoặc đột tử khi còn trẻ không?"
        ],
        "advice": "Cơn ngất xảy ra trong khi đang chạy hoặc gắng sức thể thao là dấu hiệu nguy hiểm hơn nhiều so với ngất thông thường (nguy cơ bệnh cơ tim phì đại hoặc hội chứng rối loạn nhịp tim bẩm sinh). Cần ngừng chơi thể thao và đến khám chuyên khoa Tim mạch ngay."
    }
]


def patch():
    with open(PROTOCOLS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    existing_rf_ids = {item["id"] for item in data.get("red_flag_patterns", [])}
    existing_urg_ids = {item["id"] for item in data.get("urgent_patterns", [])}

    added_rf = 0
    for item in NEW_RED_FLAGS:
        if item["id"] not in existing_rf_ids:
            data["red_flag_patterns"].append(item)
            existing_rf_ids.add(item["id"])
            added_rf += 1

    added_urg = 0
    for item in NEW_URGENT_PATTERNS:
        if item["id"] not in existing_urg_ids:
            data["urgent_patterns"].append(item)
            existing_urg_ids.add(item["id"])
            added_urg += 1

    with open(PROTOCOLS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Patched red_flag_protocols.json: +{added_rf} red flags, +{added_urg} urgent patterns. Total RF: {len(data['red_flag_patterns'])}, Total URG: {len(data['urgent_patterns'])}")


if __name__ == "__main__":
    patch()
