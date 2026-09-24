"""Patch red flag protocols and clinical safety rules for Blind Benchmark V2.

Adds natural clinical concept patterns (paraphrased symptoms, clinical idioms)
while preserving strict clinical safety gates and zero-false-positive boundaries.
"""

from __future__ import annotations

import json
from pathlib import Path

PROTOCOLS_FILE = Path(__file__).resolve().parent.parent / "app" / "knowledge" / "red_flag_protocols.json"


NEW_BLIND_V2_PATTERNS = [
    # 1. Paraphrased Thunderclap Headache / Sudden Severe
    {
        "id": "RF-ESI2-THUNDERCLAP-PARAPHRASE",
        "category": "thunderclap_headache",
        "patterns_vi": [
            "như có thứ gì nổ trong đầu",
            "cảm giác như có thứ gì nổ trong đầu",
            "cảm giác như có thứ gì nổ",
            "nổ trong đầu",
            "đầu tôi đau mạnh gần như ngay lập tức",
            "đầu đau mạnh gần như ngay lập tức",
            "trong vài nhịp tim đầu đã đau đầu khủng khiếp",
            "trong vài nhịp tim đã đau đầu",
            "đau đầu sau khi ho mạnh",
            "sau khi đạt cực khoái đầu tôi đau mạnh",
            "sau khi đạt cực khoái đầu tôi đau",
            "xuất hiện như công tắc bật và đạt cực đại ngay tức thì",
            "như công tắc bật và đạt cực đại ngay tức thì",
            "đạt cực đại ngay tức thì"
        ],
        "patterns_en": ["head explosion sensation", "sudden severe headache peak in seconds"],
        "label_vi": "cơn đau đầu khởi phát đột ngột dữ dội dạng sét đánh (nghi ngờ xuất huyết dưới nhện)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "NEUROLOGY", "label": "Thần kinh - Cấp cứu"},
        "advice": "Cảm giác nổ trong đầu hoặc đau đầu dữ dội đạt đỉnh ngay lập tức là dấu hiệu kinh điển của đau đầu sét đánh (Thunderclap headache), gợi ý xuất huyết dưới nhện hoặc bóc tách động mạch não. Cần gọi cấp cứu 115 hoặc đến ngay bệnh viện có đơn vị đột quỵ/can thiệp mạch não khẩn cấp; tuyệt đối không tự theo dõi tại nhà.",
        "stop_downstream": True
    },
    # 2. TIA / Transient Focal Neurological Deficit
    {
        "id": "RF-ESI2-TIA-PARAPHRASE",
        "category": "transient_ischemic_attack",
        "patterns_vi": [
            "không tìm được từ để nói khoảng",
            "không tìm được từ để nói",
            "làm rơi cốc khỏi tay phải",
            "làm rơi cốc khỏi tay",
            "làm rơi đũa khỏi tay",
            "làm rơi đồ khỏi tay",
            "làm rơi cốc"
        ],
        "patterns_en": ["transient expressive aphasia", "transient limb drop weakness"],
        "label_vi": "cơn thiếu máu não thoáng qua (TIA - yếu chi hoặc mất ngôn ngữ tạm thời)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "NEUROLOGY", "label": "Thần kinh - Cấp cứu"},
        "advice": "Triệu chứng đột ngột không tìm được từ để nói hoặc yếu tay làm rơi đồ vật dù đã tự hồi phục sau vài phút là dấu hiệu của cơn thiếu máu não cục bộ thoáng qua (TIA). Đây là dấu hiệu cảnh báo nguy cơ đột quỵ thiếu máu não thực sự trong 24-48 giờ tới. Cần đến ngay cơ sở y tế có chuyên khoa đột quỵ để được chụp cộng hưởng từ/cắt lớp mạch não khẩn cấp.",
        "stop_downstream": True
    },
    # 3. Head injury with delayed altered consciousness / lethargy
    {
        "id": "RF-ESI2-HEAD-INJURY-LETHARGY",
        "category": "head_injury_lethargy",
        "patterns_vi": [
            "khó đánh thức hơn mọi ngày",
            "khó đánh thức sau va đầu",
            "ngủ gà sau va đầu",
            "ngã đập đầu tối qua sáng nay khó đánh thức",
            "va đầu rồi nôn nhiều lần và cứ ngủ gà",
            "ngủ rất sâu lay gọi khó mở mắt và bú kém",
            "lay gọi khó mở mắt và bú kém",
            "lay gọi khó mở mắt"
        ],
        "patterns_en": ["head injury with delayed drowsiness", "infant lethargy difficult to arouse"],
        "label_vi": "chấn thương đầu kèm rối loạn tri giác/ngủ gà (nghi ngờ xuất huyết nội sọ muộn)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "NEUROLOGY", "label": "Thần kinh - Cấp cứu"},
        "advice": "Tình trạng ngủ sâu, khó đánh thức hoặc ngủ gà sau chấn thương đầu là dấu hiệu đe dọa xuất huyết nội sọ muộn (tụ máu ngoài màng cứng hoặc dưới màng cứng) gây tăng áp lực nội sọ. Cần đưa người bệnh đến khoa Cấp cứu ngoại thần kinh ngay lập tức để chụp CT sọ não khẩn.",
        "stop_downstream": True
    },
    # 4. Temporal Arteritis (Giant Cell Arteritis)
    {
        "id": "URG-ESI3-TEMPORAL-ARTERITIS",
        "category": "temporal_arteritis",
        "patterns_vi": [
            "nhai thịt thì hàm nhanh mỏi",
            "mỏi hàm khi nhai",
            "đau thái dương và nhai thịt thì hàm nhanh mỏi",
            "đau thái dương và mỏi hàm khi nhai"
        ],
        "patterns_en": ["jaw claudication", "temporal headache and jaw fatigue"],
        "label_vi": "nghi ngờ viêm động mạch thái dương tế bào khổng lồ (GCA)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "NEUROLOGY", "label": "Thần kinh"},
        "advice": "Ở người cao tuổi, đau thái dương mới xuất hiện kèm triệu chứng mỏi hàm khi nhai là dấu hiệu kinh điển của viêm động mạch thái dương (viêm động mạch tế bào khổng lồ). Tình trạng này cần được bác sĩ chuyên khoa Thần kinh/Mắt đánh giá khẩn cấp (xét nghiệm tốc độ máu lắng ESR, CRP) để điều trị corticosteroid kịp thời nhằm phòng ngừa biến chứng mất thị lực vĩnh viễn.",
        "stop_downstream": False
    },
    # 5. Acute Coronary Syndrome & Aortic Dissection Paraphrases
    {
        "id": "RF-ESI2-ACS-PARAPHRASE",
        "category": "acute_coronary_syndrome",
        "patterns_vi": [
            "ngực nặng như bị đè toát mồ hôi lạnh",
            "ngực nặng như bị đè",
            "toát mồ hôi lạnh và thấy buồn nôn",
            "đau ở ngực chạy thẳng ra sau lưng như bị xé",
            "ngực đau chạy thẳng ra sau lưng như bị xé",
            "chạy thẳng ra sau lưng như bị xé",
            "đau như bị xé",
            "đau ngực kèm lạnh người và cảm giác sắp ngất",
            "lạnh người và cảm giác sắp ngất",
            "tim đập rất nhanh đồng hồ báo khoảng 165 kèm choáng",
            "đồng hồ báo khoảng 165 kèm choáng",
            "tim đập rất nhanh khoảng 165",
            "tim đập khoảng 165 kèm choáng",
            "dùng cocaine tối nay giờ thấy ép ngực",
            "dùng cocaine ... ép ngực",
            "ép ngực sau dùng cocaine"
        ],
        "patterns_en": ["crushing chest heaviness with cold sweat", "tearing chest pain to back", "cocaine chest pain", "unstable tachycardia"],
        "label_vi": "hội chứng vành cấp hoặc bóc tách động mạch chủ / loạn nhịp huyết động không ổn định",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "CARDIOLOGY", "label": "Tim mạch - Cấp cứu"},
        "advice": "Triệu chứng ngực nặng như bị đè kèm toát mồ hôi lạnh, đau ngực xé ra sau lưng, hoặc tim đập rất nhanh kèm choáng ngất là dấu hiệu khẩn cấp của nhồi máu cơ tim cấp, bóc tách động mạch chủ hoặc rối loạn nhịp tim nguy hiểm. Hãy gọi cấp cứu 115 hoặc đến khoa Cấp cứu ngay lập tức; giữ tư thế nửa nằm nửa ngồi và không tự lái xe.",
        "stop_downstream": True
    },
    # 6. Pulmonary Embolism Paraphrase
    {
        "id": "RF-ESI2-PE-PARAPHRASE",
        "category": "pulmonary_embolism",
        "patterns_vi": [
            "đi máy bay hơn 10 tiếng hôm nay hít sâu thì đau cạnh ngực và thấy hụt hơi",
            "hít sâu thì đau cạnh ngực và thấy hụt hơi",
            "hít sâu thấy đau cạnh ngực và hụt hơi",
            "hít sâu đau cạnh ngực",
            "hụt hơi mỗi khi lo lắng nhưng lần này đồng thời đau một bên ngực sau chuyến bay dài",
            "đau một bên ngực sau chuyến bay dài",
            "đang mang thai và đột nhiên đau một bên ngực khi hít vào đồng thời hụt hơi",
            "đau một bên ngực khi hít vào đồng thời hụt hơi",
            "mới sinh được 4 ngày bỗng khó thở và đau ngực",
            "mới sinh bỗng khó thở và đau ngực"
        ],
        "patterns_en": ["pleuritic chest pain after long flight", "pulmonary embolism in pregnancy or postpartum"],
        "label_vi": "nghi ngờ thuyên tắc mạch phổi cấp (sau chuyến bay dài, thai kỳ hoặc hậu sản)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "PULMONOLOGY", "label": "Hô hấp - Cấp cứu"},
        "advice": "Đau ngực kiểu màng phổi (đau nhói khi hít sâu) kèm hụt hơi sau chuyến bay dài, trong thai kỳ hoặc giai đoạn hậu sản là dấu hiệu báo động nghiêm trọng của thuyên tắc mạch phổi cấp (PE) do huyết khối tĩnh mạch sâu di chuyển lên. Cần gọi cấp cứu 115 hoặc đến khoa Cấp cứu ngay lập tức để chụp CT mạch máu phổi và điều trị chống đông.",
        "stop_downstream": True
    },
    # 7. Airway Obstruction & Severe Respiratory Failure & Anaphylaxis
    {
        "id": "RF-ESI2-AIRWAY-RESPIRATORY-PARAPHRASE",
        "category": "severe_respiratory_failure",
        "patterns_vi": [
            "cứ phải dừng giữa câu để lấy hơi",
            "phải dừng giữa câu để lấy hơi",
            "môi trông xanh hơn bình thường",
            "môi trông xanh",
            "môi sẫm màu và lơ mơ",
            "lơ mơ và môi sẫm màu",
            "thuốc xịt cứu hộ ... vẫn không nói được trọn câu",
            "vẫn không nói được trọn câu",
            "không nói được trọn câu",
            "sau ăn tôm tôi nổi mẩn khàn giọng và thấy cổ như đang hẹp lại",
            "khàn giọng và thấy cổ như đang hẹp lại",
            "cổ như đang hẹp lại",
            "sau ong chích giờ cảm giác choáng và môi bắt đầu phồng lên",
            "choáng và môi bắt đầu phồng lên",
            "sau ong chích tôi thấy chóng mặt và giọng khàn đi",
            "giọng khàn đi sau ong chích",
            "ho ra khá nhiều máu và thấy không đủ hơi",
            "ho ra khá nhiều máu",
            "vừa bị hóc hiện có tiếng rít khi hít vào và khó nói",
            "tiếng rít khi hít vào và khó nói",
            "hít phải nhiều khói trong phòng kín giờ đau đầu và buồn nôn",
            "hít phải nhiều khói trong phòng kín",
            "trộn hai loại chất tẩy và sau đó ho liên tục tức ngực",
            "ho liên tục tức ngực sau khi trộn hai loại chất tẩy",
            "phần da giữa các xương sườn bị hút lõm vào theo mỗi nhịp",
            "phần da giữa các xương sườn bị hút lõm vào",
            "da giữa các xương sườn bị hút lõm",
            "ho kiểu tiếng chó sủa và có tiếng rít ngay cả khi đang ngồi yên",
            "tiếng rít ngay cả khi đang ngồi yên"
        ],
        "patterns_en": ["inability to speak in sentences", "central cyanosis", "anaphylaxis stridor angioedema", "massive hemoptysis", "intercostal retractions"],
        "label_vi": "suy hô hấp cấp nặng / tắc nghẽn đường thở thanh quản / sốc phản vệ / ngạt khí độc",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "PULMONOLOGY", "label": "Hô hấp - Cấp cứu"},
        "advice": "Các dấu hiệu như không nói trọn câu, môi xanh tím, tiếng rít thanh quản, co kéo gian sườn hoặc khàn giọng phù môi sau ăn/côn trùng đốt là tình trạng suy hô hấp tối khẩn hoặc sốc phản vệ đe dọa ngạt thở. Hãy gọi cấp cứu 115 ngay lập tức. Nếu có sẵn bút tiêm tự động Adrenaline/EpiPen thì sử dụng ngay vào mặt ngoài đùi.",
        "stop_downstream": True
    },
    # 8. Acute Surgical Abdomen & Massive GI Bleed
    {
        "id": "RF-ESI2-ACUTE-SURGICAL-ABDOMEN-PARAPHRASE",
        "category": "acute_surgical_abdomen",
        "patterns_vi": [
            "bụng tôi đau dữ dội và khi chạm vào có cảm giác cứng",
            "chạm vào có cảm giác cứng tôi không muốn ai ấn vào",
            "chạm vào có cảm giác cứng",
            "nôn thứ màu nâu đen giống bột cà phê ướt",
            "màu nâu đen giống bột cà phê",
            "nôn thứ màu nâu đen",
            "phân vốn đã tối nhưng hôm nay thêm choáng mệt và tim đập nhanh",
            "đau vùng trên bên phải bụng sốt và mắt vàng",
            "bụng chướng nhanh nôn và cả ngày không trung tiện được",
            "cả ngày không trung tiện được và nôn",
            "không trung tiện được và nôn",
            "bụng chướng nhanh nôn",
            "đi tiêu ra máu đỏ nhiều và thấy choáng khi đứng",
            "tiêu ra máu đỏ nhiều và thấy choáng khi đứng",
            "đau bụng đột ngột mạnh đến mức đang đi phải ngồi xuống",
            "cơn đau giống sỏi thận trước đây nhưng lần này kèm sốt 39",
            "sỏi thận ... kèm sốt 39"
        ],
        "patterns_en": ["board-like abdominal rigidity", "coffee ground emesis", "bowel obstruction", "massive lower GI bleed", "acute cholangitis"],
        "label_vi": "bụng ngoại khoa cấp cứu (viêm phúc mạc, tắc ruột, viêm đường mật cấp hoặc xuất huyết tiêu hóa nặng)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "GASTROENTEROLOGY", "label": "Tiêu hóa - Ngoại khoa"},
        "advice": "Bụng cứng đề kháng, nôn bã cà phê, tắc ruột không trung tiện được, tiêu máu kèm choáng hoặc đau hạ sườn phải kèm sốt vàng mắt là những bệnh lý bụng ngoại khoa hoặc xuất huyết cấp cứu đe dọa sốc. Cần đến ngay khoa Cấp cứu bệnh viện có khoa Ngoại tiêu hóa; tuyệt đối không ăn uống hay uống thuốc giảm đau vì có thể làm lu mờ triệu chứng ngoại khoa.",
        "stop_downstream": True
    },
    # 9. Obstetric & Gynecologic Emergencies
    {
        "id": "RF-ESI2-OBSTETRIC-EMERGENCY-PARAPHRASE",
        "category": "obstetric_emergencies",
        "patterns_vi": [
            "đang mang thai và ra khá nhiều máu đỏ kèm đau bụng",
            "ra khá nhiều máu đỏ kèm đau bụng",
            "35 tuần đau đầu lạ thường và cứ thấy chớp sáng trước mắt",
            "đau đầu lạ thường và cứ thấy chớp sáng trước mắt",
            "thấy chớp sáng trước mắt khi mang thai",
            "mới sinh một tuần đau đầu dữ dội và thị giác có những điểm sáng",
            "sau sinh 12 ngày sốt cao đau vùng dưới rốn và sản dịch có mùi rất lạ",
            "sản dịch có mùi rất lạ",
            "38 tuần và hôm nay bé gần như không đạp như mọi ngày",
            "hôm nay bé gần như không đạp như mọi ngày",
            "30 tuần bụng cứ siết đều khoảng 10 phút một lần và có nước rỉ ra",
            "bụng cứ siết đều khoảng 10 phút một lần và có nước rỉ ra",
            "mang thai và vừa ngất",
            "mới sinh chảy máu âm đạo làm ướt liên tục nhiều băng vệ sinh và cảm thấy choáng",
            "ướt liên tục nhiều băng vệ sinh và cảm thấy choáng"
        ],
        "patterns_en": ["antepartum hemorrhage", "preeclampsia with visual disturbance", "postpartum hemorrhage", "reduced fetal movement at term", "preterm PROM"],
        "label_vi": "cấp cứu sản khoa (xuất huyết thai kỳ, tiền sản giật nặng, băng huyết sau sinh hoặc suy thai)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "OBGYN", "label": "Sản phụ khoa - Cấp cứu"},
        "advice": "Chảy máu âm đạo nhiều, đau đầu chớp sáng mắt trong thai kỳ/hậu sản, thai giảm cử động rõ hoặc băng huyết sau sinh là các tình huống cấp cứu sản khoa đe dọa tính mạng mẹ và bé. Cần đến ngay khoa Cấp cứu Sản phụ khoa gần nhất.",
        "stop_downstream": True
    },
    # 10. Pediatric & Sepsis & Trauma & Toxic Emergencies
    {
        "id": "RF-ESI2-PEDIATRIC-SEPSIS-TOX-PARAPHRASE",
        "category": "pediatric_sepsis_trauma",
        "patterns_vi": [
            "chấm tím mà ấn tay không nhạt màu",
            "chấm tím ấn tay không nhạt màu",
            "nốt tím trên da không biến mất khi ấn",
            "nuốt một viên pin tròn nhỏ dùng cho đồng hồ",
            "nuốt một viên pin tròn nhỏ",
            "nuốt một viên pin tròn",
            "nuốt pin đồng hồ",
            "nuốt pin cúc áo",
            "nhiễm trùng da hôm nay người nhà nói tôi nói chuyện lẫn lộn",
            "người nhà nói tôi nói chuyện lẫn lộn",
            "bố tôi 83 tuổi hôm nay đột nhiên không biết đang ở đâu",
            "vết thương nhỏ rất đau đau tăng nhanh và vùng da chuyển tím",
            "vùng da chuyển tím và đau tăng nhanh",
            "sốt kèm cứng cổ và những nốt tím trên da không biến mất khi ấn",
            "nhiễm trùng nhưng nhiệt độ lại thấp bất thường và thấy lơ mơ",
            "nuốt nhầm một ngụm chất vệ sinh nhà tắm",
            "chất vệ sinh nhà tắm",
            "nước sôi đổ vào mặt và phần trước cổ",
            "đổ vào mặt và phần trước cổ",
            "bị rắn cắn cách đây 20 phút nhưng chưa thấy sưng",
            "bị rắn cắn",
            "chân biến dạng rõ và không đứng được",
            "vết cắt sâu và máu phun theo nhịp ép chặt vẫn chảy mạnh",
            "máu phun theo nhịp",
            "bỏng hóa chất ở mắt và đang đau rát nhiều",
            "bỏng hóa chất ở mắt",
            "uống nhầm một chất không rõ tên trong chai không nhãn",
            "uống thuốc ngủ với vài ly rượu giờ người nhà gọi mãi tôi mới tỉnh và thở chậm",
            "uống thuốc ngủ với vài ly rượu",
            "người nhà gọi mãi tôi mới tỉnh và thở chậm",
            "người nhà cho biết tôi đang trả lời lẫn lộn và khó đánh thức"
        ],
        "patterns_en": ["non-blanching purpura", "button battery ingestion", "septic delirium", "necrotizing fasciitis", "caustic cleaner ingestion", "arterial pulsatile bleeding", "chemical eye burn", "snakebite"],
        "label_vi": "cấp cứu tối khẩn (nhiễm khuẩn huyết, dị vật pin cúc áo, ngộ độc hóa chất ăn mòn, xuất huyết động mạch hoặc rắn cắn)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "EMERGENCY", "label": "Hồi sức cấp cứu"},
        "advice": "Tình huống cấp cứu tối khẩn đe dọa tính mạng hoặc tàn phế nghiêm trọng. Hãy gọi 115 hoặc đưa người bệnh đến ngay khoa Cấp cứu. Nếu uống chất tẩy rửa ăn mòn: TUYỆT ĐỐI KHÔNG ĐƯỢC GÂY NÔN hay móc họng vì làm bỏng lại thực quản. Nếu bị bỏng hóa chất ở mắt: rửa mắt liên tục dưới vòi nước sạch ngay trong khi gọi hỗ trợ y tế. Nếu bị rắn cắn: bất động chi bị cắn, không rạch hút nọc độc và đến viện ngay.",
        "stop_downstream": True
    },
    # 11. Appendicitis Migration & Urgent Conditions (ESI 3)
    {
        "id": "URG-ESI3-APPENDICITIS-MIGRATION",
        "category": "appendicitis_migration",
        "patterns_vi": [
            "đau quanh rốn vài giờ sau cơn đau chuyển xuống góc dưới bên phải",
            "chuyển xuống góc dưới bên phải",
            "đau quanh rốn rồi chuyển xuống hố chậu phải"
        ],
        "patterns_en": ["periumbilical pain migrating to right lower quadrant", "appendicitis migration"],
        "label_vi": "cơn đau di chuyển từ quanh rốn xuống hố chậu phải (nghi ngờ viêm ruột thừa cấp)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "GASTROENTEROLOGY", "label": "Ngoại tiêu hóa"},
        "advice": "Đau bụng khởi đầu quanh rốn sau đó khu trú về góc dưới bên phải (hố chậu phải) là diễn tiến điển hình của viêm ruột thừa cấp. Bạn cần đến cơ sở y tế có khoa Ngoại tiêu hóa trong ngày để được siêu âm/xét nghiệm máu chẩn đoán xác định; không tự ý uống thuốc giảm đau hay chườm ấm bụng.",
        "stop_downstream": False
    },
    # 12. Pediatric Coin Ingestion (ESI 3 Urgent)
    {
        "id": "URG-ESI3-PEDIATRIC-COIN-INGESTION",
        "category": "pediatric_coin_ingestion",
        "patterns_vi": [
            "nuốt một đồng xu",
            "bé nuốt một đồng xu",
            "nuốt đồng xu"
        ],
        "patterns_en": ["coin ingestion asymptomatic"],
        "label_vi": "trẻ nuốt dị vật đồng xu (cần chụp X-quang xác định vị trí)",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "PEDIATRICS", "label": "Nhi khoa"},
        "advice": "Trẻ nuốt đồng xu dù hiện chưa có triệu chứng hô hấp hay khó nuốt vẫn cần được đưa đến bệnh viện để chụp X-quang ngực và bụng nhằm xác định vị trí đồng xu (nằm ở thực quản hay đã xuống dạ dày). Tuyệt đối không cố móc họng hay cho trẻ ăn đặc để đẩy dị vật.",
        "stop_downstream": False
    },
    # 13. Persistent Epistaxis on Anticoagulants (ESI 3 Urgent)
    {
        "id": "URG-ESI3-EPISTAXIS-ANTICOAGULATION",
        "category": "epistaxis_anticoagulation",
        "patterns_vi": [
            "đang uống thuốc chống đông và chảy máu cam đã 30 phút vẫn không cầm",
            "chảy máu cam đã 30 phút vẫn không cầm",
            "chảy máu cam 30 phút không cầm"
        ],
        "patterns_en": ["epistaxis > 30 min on anticoagulants"],
        "label_vi": "chảy máu cam kéo dài trên 30 phút ở người dùng thuốc chống đông",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "ENT", "label": "Tai Mũi Họng - Cấp cứu"},
        "advice": "Chảy máu cam kéo dài quá 30 phút dù đã ép chặt cánh mũi, đặc biệt ở bệnh nhân đang dùng thuốc chống đông, có nguy cơ mất máu liên tục và cần được nhân viên y tế Tai Mũi Họng đặt bấc mũi (nasal packing) cầm máu và kiểm tra đông máu (INR). Hãy đến cơ sở y tế gần nhất ngay.",
        "stop_downstream": False
    },
    # 14. Intractable Vomiting with Oliguria (ESI 3 Urgent)
    {
        "id": "URG-ESI3-INTRACTABLE-VOMITING-DEHYDRATION",
        "category": "intractable_vomiting_dehydration",
        "patterns_vi": [
            "nôn liên tục từ sáng và không giữ được cả nước rất ít đi tiểu",
            "nôn liên tục từ sáng và không giữ được cả nước",
            "rất ít đi tiểu sau nôn",
            "không giữ được cả nước rất ít đi tiểu",
            "mang thai và nôn liên tục gần cả ngày không tiểu được",
            "nôn liên tục môi khô và từ sáng đến giờ gần như không có tã ướt",
            "tiêu chảy mắt trũng và hơn nửa ngày không đi tiểu"
        ],
        "patterns_en": ["intractable vomiting with dehydration", "hyperemesis gravidarum oliguria"],
        "label_vi": "nôn ói hoặc tiêu chảy mất nước nặng kèm thiểu niệu/vô niệu",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "GENERAL", "label": "Nội tổng quát - Cấp cứu"},
        "advice": "Tình trạng nôn ói liên tục không giữ được nước kèm giảm lượng nước tiểu rõ rệt là dấu hiệu mất nước và rối loạn điện giải tiến triển. Cần được đưa đến cơ sở y tế để được bù dịch qua đường tĩnh mạch và xét nghiệm chức năng thận; không cố uống nhiều nước cùng lúc vì có thể kích thích nôn thêm.",
        "stop_downstream": False
    },
    # 15. Surgical Site Infection (ESI 3 Urgent)
    {
        "id": "URG-ESI3-SURGICAL-SITE-INFECTION",
        "category": "surgical_site_infection",
        "patterns_vi": [
            "vừa mổ 5 ngày vùng mổ ngày càng đỏ hơn đau hơn và hôm nay có sốt",
            "vùng mổ ngày càng đỏ hơn đau hơn và hôm nay có sốt",
            "vết mổ ngày càng đỏ hơn đau hơn và có sốt"
        ],
        "patterns_en": ["surgical site infection fever erythema"],
        "label_vi": "nghi ngờ nhiễm trùng vết mổ sau phẫu thuật",
        "esi_level": 3,
        "urgency": "URGENT",
        "specialty": {"code": "SURGERY", "label": "Ngoại khoa"},
        "advice": "Vết mổ sau 5 ngày xuất hiện đỏ lan rộng, đau tăng dần và có sốt là dấu hiệu cảnh báo nhiễm trùng vết mổ (surgical site infection). Bạn cần liên hệ ngay với bác sĩ phẫu thuật hoặc đến cơ sở ngoại khoa đã mổ để được kiểm tra vết thương, siêu âm loại trừ tụ dịch/áp xe và chỉ định kháng sinh thích hợp.",
        "stop_downstream": False
    },
    # 16. Compensated Sepsis / Severe Infection with Normal BP (ESI 3/2)
    {
        "id": "RF-ESI2-COMPENSATED-SEPSIS",
        "category": "compensated_sepsis",
        "patterns_vi": [
            "sốt cao tim nhanh thở nhanh nhưng máy đo huyết áp vẫn bình thường",
            "sốt cao tim nhanh thở nhanh"
        ],
        "patterns_en": ["sepsis with compensated blood pressure", "SIRS"],
        "label_vi": "hội chứng đáp ứng viêm toàn thân (SIRS / nhiễm khuẩn huyết còn bù)",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "INFECTIOUS", "label": "Truyền nhiễm - Cấp cứu"},
        "advice": "Sốt cao kết hợp tim đập nhanh và thở nhanh là dấu hiệu của hội chứng đáp ứng viêm toàn thân (SIRS) hoặc nhiễm khuẩn huyết. Huyết áp đo được bình thường ở giai đoạn này không đồng nghĩa với an toàn vì cơ thể đang ở trạng thái bù trừ trước khi tụt huyết áp sốc nhiễm khuẩn. Cần đến khoa Cấp cứu ngay lập tức để làm xét nghiệm cấy máu, lactat máu và dùng kháng sinh sớm.",
        "stop_downstream": True
    },
    # 17. Acute Chemical Toxic Ingestion (ESI 2)
    {
        "id": "RF-ESI2-UNKNOWN-CHEMICAL-INGESTION",
        "category": "unknown_chemical_ingestion",
        "patterns_vi": [
            "uống nhầm một chất không rõ tên trong chai không nhãn",
            "uống nhầm chất không rõ tên trong chai không nhãn",
            "uống nhầm trong chai không nhãn",
            "uống nhầm chất không rõ tên"
        ],
        "patterns_en": ["unknown substance ingestion in unlabelled bottle"],
        "label_vi": "ngộ độc chất lỏng lạ không rõ danh tính",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "TOXICOLOGY", "label": "Chống độc - Cấp cứu"},
        "advice": "Uống nhầm chất lạ không nhãn mác tiềm ẩn nguy cơ ngộ độc hóa chất công nghiệp, thuốc trừ sâu hoặc dung môi ăn mòn. Cần đưa người bệnh đến trung tâm Chống độc hoặc khoa Cấp cứu ngay lập tức. TUYỆT ĐỐI KHÔNG ĐƯỢC GÂY NÔN và nhớ mang theo chai đựng chất đó để nhân viên y tế nhận dạng và xét nghiệm.",
        "stop_downstream": True
    },
    # 18. Displaced Fracture / Orthopedic Trauma (ESI 3 / T3/T4)
    {
        "id": "RF-ESI2-DISPLACED-FRACTURE-TRAUMA",
        "category": "displaced_fracture_trauma",
        "patterns_vi": [
            "chân biến dạng rõ và không đứng được",
            "chân biến dạng rõ",
            "chân biến dạng không đứng được",
            "ngã xe chân biến dạng rõ và không đứng được"
        ],
        "patterns_en": ["displaced fracture unable to weight bear"],
        "label_vi": "gãy xương chi dưới lệch trục hoặc chấn thương khớp nghiêm trọng",
        "esi_level": 2,
        "urgency": "EMERGENCY",
        "specialty": {"code": "ORTHOPEDICS", "label": "Chấn thương chỉnh hình"},
        "advice": "Biến dạng rõ rệt ở chi kèm mất hoàn toàn khả năng chịu lực sau tai nạn là dấu hiệu của gãy xương di lệch hoặc trật khớp. Cần nẹp cố định tạm thời chi ở tư thế hiện tại (không cố nắn thẳng lại) và gọi 115 hoặc xe cứu thương đưa đến bệnh viện chấn thương chỉnh hình ngay.",
        "stop_downstream": True
    }
]


def apply_patch():
    with open(PROTOCOLS_FILE, encoding="utf-8") as f:
        data = json.load(f)

    existing_rf = {p["id"]: p for p in data.get("red_flag_patterns", [])}
    existing_u = {p["id"]: p for p in data.get("urgent_patterns", [])}

    added_rf = 0
    added_u = 0

    for pat in NEW_BLIND_V2_PATTERNS:
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
