#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MedGuard Unity C# Motion Specification v3 & Reference Package Generator
"""

import os
import sys
import json
import zipfile
import shutil
from pathlib import Path

import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

ROOT = Path("/Users/munonguyen/Project ATI")
DOCS_DIR = ROOT / "docs"
DOWNLOADS_DIR = Path("/Users/munonguyen/Downloads")
OUTPUT_DOCX = DOCS_DIR / "MedGuard_Unity_CSharp_Motion_Spec_v3.docx"
OUTPUT_ZIP = DOCS_DIR / "MedGuard_Unity_CSharp_Reference_v3.zip"
UNITY_REF_DIR = ROOT / "unity" / "MedGuard_Unity_CSharp_Reference_v3"

DOCS_DIR.mkdir(parents=True, exist_ok=True)
UNITY_REF_DIR.mkdir(parents=True, exist_ok=True)

# -------------------------------------------------------------
# 1. DỮ LIỆU THIẾT KẾ: 32 NHÓM HÀNH ĐỘNG & 64 BIẾN THỂ CỬ CHỈ
# -------------------------------------------------------------
ACTION_CATALOG = [
    {
        "group_id": "GRP_01_GREETING",
        "group_name": "Chào đón ban đầu",
        "intent": "greeting",
        "variants": [
            {
                "id": "GREET_WARM_NOD",
                "name": "Chào ấm áp kèm cúi đầu nhẹ",
                "purpose": "Khởi đầu phiên khám Routine/Thường quy",
                "body_hand": "Cúi đầu nhẹ 5-8 độ, hai tay để ngang bụng/ngực dưới, mở nhẹ 15 độ",
                "facial_eye": "Nụ cười mỉm thân thiện 20%, ánh mắt ấm áp nhìn trực diện bệnh nhân",
                "duration_sec": 2.2,
                "preconditions": "Mở đầu hội thoại; mức độ khẩn cấp là ROUTINE; bệnh nhân không báo đau dữ dội",
                "prohibitions": "CẤM dùng khi phát hiện Red Flag (cấp cứu), bệnh nhân đang đau quằn quại hoặc hoảng loạn"
            },
            {
                "id": "GREET_NEUTRAL_OPEN",
                "name": "Chào trung tính mở lòng bàn tay",
                "purpose": "Khởi đầu phiên khám khi bối cảnh chưa rõ hoặc có dấu hiệu lo âu",
                "body_hand": "Thân thẳng đĩnh đạc, hai lòng bàn tay ngửa nhẹ 45 độ ngang thắt lưng",
                "facial_eye": "Khuôn mặt trung tính điềm tĩnh (Neutral), ánh mắt chú tâm 100%",
                "duration_sec": 1.8,
                "preconditions": "Mở đầu hội thoại; bối cảnh chưa xác định rõ mức độ",
                "prohibitions": "CẤM vẫy tay cao quá vai; CẤM cười toe toét"
            }
        ]
    },
    {
        "group_id": "GRP_02_ATTENTIVE_LISTENING",
        "group_name": "Lắng nghe tập trung",
        "intent": "listening",
        "variants": [
            {
                "id": "LISTEN_LEAN_FORWARD",
                "name": "Nghiêng người chú ý",
                "purpose": "Thể hiện sự tập trung cao độ khi bệnh nhân kể bệnh sử",
                "body_hand": "Thân trên nghiêng nhẹ về phía trước 3 độ, hai tay đan nhẹ hoặc giữ trên bàn, gật đầu nhịp chậm (1.5s/gật)",
                "facial_eye": "Mày thư giãn, mắt duy trì eye contact 75%, chớp mắt tự nhiên 15-20 nhịp/phút",
                "duration_sec": 3.5,
                "preconditions": "Người dùng đang nhập liệu hoặc đang nói; trạng thái hệ thống là Listening",
                "prohibitions": "CẤM ngắt lời; CẤM làm cử chỉ tay thừa thãi gây phân tâm; CẤM cười"
            },
            {
                "id": "LISTEN_NEUTRAL_STILL",
                "name": "Lắng nghe trung tính điềm đạm",
                "purpose": "Giữ tư thế chuẩn mực khi bệnh nhân mô tả ca bệnh phức tạp",
                "body_hand": "Thân mình bất động vững vàng, thở nhẹ nhàng, hai tay thả lỏng tự nhiên",
                "facial_eye": "Mặt điềm tĩnh, micro-saccade quanh vùng mắt-mũi của bệnh nhân",
                "duration_sec": 4.0,
                "preconditions": "Bệnh sử dài hoặc triệu chứng có tính chất nghiêm trọng",
                "prohibitions": "CẤM gật đầu liên tục (khiến bệnh nhân lầm tưởng bác sĩ đã đồng thuận kết luận)"
            }
        ]
    },
    {
        "group_id": "GRP_03_EMPATHY_REASSURANCE",
        "group_name": "Đồng cảm & Trấn an",
        "intent": "empathy",
        "variants": [
            {
                "id": "EMPATHY_HAND_CHEST",
                "name": "Tay đặt ngực trên thấu cảm",
                "purpose": "Bày tỏ sự chia sẻ sâu sắc khi bệnh nhân lo lắng, sợ hãi",
                "body_hand": "Tay phải nâng nhẹ đặt lên ngực trên, đầu nghiêng nhẹ 2 độ, vai mềm mại",
                "facial_eye": "Ánh mắt ấm áp, chân mày giãn nở thể hiện sự nâng đỡ tinh thần",
                "duration_sec": 2.8,
                "preconditions": "Bệnh nhân bày tỏ sợ hãi, lo lắng về bệnh tật; phân loại cảm xúc là ANXIOUS/DISTRESSED",
                "prohibitions": "CẤM dùng khi người dùng hỏi thuần túy kiến thức logic hoặc khi thông báo cấp cứu"
            },
            {
                "id": "EMPATHY_OPEN_CALM",
                "name": "Hai tay hạ thấp xoa dịu",
                "purpose": "Khuyên bệnh nhân giữ bình tĩnh, hít thở sâu",
                "body_hand": "Hai tay đưa ra trước thấp hơn khuỷu tay, lòng bàn tay úp nhẹ hạ xuống từ từ (soothing motion)",
                "facial_eye": "Gương mặt dịu dàng, nhịp thở sâu mẫu (vai hạ nhẹ 1cm)",
                "duration_sec": 3.2,
                "preconditions": "Bệnh nhân thở dốc do hoảng loạn hoặc căng thẳng tâm lý",
                "prohibitions": "CẤM dùng khi bệnh nhân đang có triệu chứng thực thể cấp tính (nhồi máu cơ tim, đột quỵ)"
            }
        ]
    },
    {
        "group_id": "GRP_04_SYMPTOM_INQUIRY",
        "group_name": "Hỏi sâu triệu chứng",
        "intent": "inquiry",
        "variants": [
            {
                "id": "INQUIRE_OPEN_PALMS",
                "name": "Mở tay hỏi chi tiết",
                "purpose": "Đặt câu hỏi mở khai thác thêm thông tin bệnh sử",
                "body_hand": "Hai bàn tay mở hướng về phía trước ngang eo, đầu hơi nghiêng thăm dò",
                "facial_eye": "Chân mày hơi nhướng 10% thể hiện sự quan tâm đón nhận",
                "duration_sec": 2.4,
                "preconditions": "Bác sĩ đang hỏi thêm: Thời gian khởi phát, vị trí, mức độ",
                "prohibitions": "CẤM chỉ ngón trỏ vào người bệnh; CẤM khoanh tay trước ngực"
            },
            {
                "id": "INQUIRE_CLARIFICATION",
                "name": "Tay chỉ định làm rõ",
                "purpose": "Hỏi rõ tính chất triệu chứng (đau nhói hay đau âm ỉ)",
                "body_hand": "Một tay đưa nhẹ ra trước kết hợp gật nhẹ, tay kia giữ vị trí ổn định",
                "facial_eye": "Mắt mở to chú ý, hướng thẳng vào bệnh nhân",
                "duration_sec": 2.0,
                "preconditions": "Cần phân biệt giữa 2 trạng thái triệu chứng",
                "prohibitions": "CẤM làm động tác dò xét gay gắt"
            }
        ]
    },
    {
        "group_id": "GRP_05_NEGATION_RECOGNITION",
        "group_name": "Ghi nhận thông tin phủ định",
        "intent": "negation_ack",
        "variants": [
            {
                "id": "NEGATION_SUBTLE_NOD",
                "name": "Gật đầu xác nhận loại trừ",
                "purpose": "Xác nhận đã nghe rõ người dùng KHÔNG có triệu chứng đó",
                "body_hand": "Gật đầu dứt khoát 1 nhịp chậm (amplitude 4 độ), hai tay giữ nguyên vị trí nghỉ",
                "facial_eye": "Biểu cảm thấu hiểu, duy trì ánh mắt tin cậy",
                "duration_sec": 1.6,
                "preconditions": "Phát hiện câu có phủ định (không sốt, không khó thở, không đau ngực)",
                "prohibitions": "CẤM LẮC ĐẦU (bệnh nhân dễ hiểu nhầm là bác sĩ không đồng ý hoặc nghi ngờ)"
            },
            {
                "id": "NEGATION_NOTING_DOWN",
                "name": "Liếc mắt ghi nhận âm tính",
                "purpose": "Mô phỏng động tác đánh dấu vào hồ sơ bệnh án",
                "body_hand": "Một tay hạ nhẹ như đang đặt lên tập hồ sơ, đầu hơi cúi 3 độ trong 1 giây",
                "facial_eye": "Mắt nhìn xuống góc dưới 1.2s rồi nhìn thẳng lại bệnh nhân",
                "duration_sec": 2.5,
                "preconditions": "Ghi nhận các triệu chứng âm tính quan trọng (Negative findings)",
                "prohibitions": "CẤM nhìn xuống quá lâu (>2s); CẤM biểu cảm lơ đãng"
            }
        ]
    },
    {
        "group_id": "GRP_06_EMERGENCY_ALERT",
        "group_name": "Cảnh báo dấu hiệu đỏ / Cấp cứu",
        "intent": "emergency_alert",
        "variants": [
            {
                "id": "EMERGENCY_SERIOUS_STILL",
                "name": "Nghiêm nghị bất động cảnh báo đỏ",
                "purpose": "Báo động tình trạng khẩn cấp đe dọa tính mạng",
                "body_hand": "Thân thẳng tuyệt đối, hai tay đặt chắc chắn ngang bàn/thân, không vung vẩy",
                "facial_eye": "Mặt nghiêm nghị tuyệt đối (Severe Neutral), mắt nhìn thẳng 100%, không chớp mắt liên tục",
                "duration_sec": 3.0,
                "preconditions": "Phát hiện Red Flag (đau thắt ngực, dấu hiệu FAST đột quỵ, khó thở tím tái, nôn ra máu)",
                "prohibitions": "CẤM TUYỆT ĐỐI nụ cười, nháy mắt, gật đầu thoải mái, hoặc bất kỳ cử chỉ đùa cợt nào"
            },
            {
                "id": "EMERGENCY_RAISE_PALM_HALT",
                "name": "Nâng lòng bàn tay ngăn chặn",
                "purpose": "Yêu cầu ngừng ngay hành vi nguy hiểm hoặc gọi cấp cứu 115 lập tức",
                "body_hand": "Một tay nâng lên ngang ngực lòng bàn tay hướng về trước ở thế dừng lại (Stop/Halt), dứt khoát",
                "facial_eye": "Chân mày khép nhẹ kiên quyết, ánh mắt mạnh mẽ đầy quyền uy y khoa",
                "duration_sec": 2.2,
                "preconditions": "Cần hành động cấp bách ngay tức khắc: gọi 115, không được tự lái xe, không uống aspirin khi nghi đột quỵ xuất huyết",
                "prohibitions": "CẤM giơ tay cao quá vai; CẤM chỉ trích người bệnh"
            }
        ]
    },
    {
        "group_id": "GRP_07_URGENT_REFERRAL",
        "group_name": "Hướng dẫn khám gấp",
        "intent": "urgent_referral",
        "variants": [
            {
                "id": "URGENT_DIRECTIVE_HAND",
                "name": "Bàn tay chỉ dẫn phương hướng",
                "purpose": "Hướng dẫn đến cơ sở y tế gần nhất trong 2-4 giờ",
                "body_hand": "Bàn tay mở nghiêng 45 độ hướng về phía trước như chỉ dẫn lối đi an toàn",
                "facial_eye": "Biểu cảm khẩn trương nhưng kiểm soát, giọng nói dứt khoát",
                "duration_sec": 2.5,
                "preconditions": "Mức độ URGENT (sốt cao co giật đã hạ, đau bụng hố chậu phải nghi ruột thừa)",
                "prohibitions": "CẤM chỉ một ngón trỏ (Finger pointing thô lỗ)"
            },
            {
                "id": "URGENT_FOCUSED_LEAN",
                "name": "Nghiêng người nhấn mạnh thời gian",
                "purpose": "Nhấn mạnh cửa sổ thời gian vàng để điều trị",
                "body_hand": "Thân người rướn nhẹ về trước 4 độ, một tay nhấn nhịp nhẹ theo từ khóa thời gian",
                "facial_eye": "Ánh mắt tập trung cao độ, nhịp chớp mắt giảm",
                "duration_sec": 2.8,
                "preconditions": "Bệnh có thời gian vàng (cửa sổ tiêu sợi huyết, xoắn tinh hoàn)",
                "prohibitions": "CẤM đập bàn hoặc vung tay hỗn loạn"
            }
        ]
    },
    {
        "group_id": "GRP_08_EXPLANATION_ANATOMICAL",
        "group_name": "Giải thích cơ chế bệnh học",
        "intent": "explanation",
        "variants": [
            {
                "id": "EXPLAIN_DUAL_HAND_LEVEL",
                "name": "Hai tay nhịp nhàng phân tích",
                "purpose": "Giải thích nguyên nhân, sinh lý bệnh học cho người bệnh hiểu",
                "body_hand": "Hai tay giữ ngang ngực, di chuyển mở rộng và thu hẹp nhịp nhàng theo trọng âm câu nói",
                "facial_eye": "Gương mặt cởi mở, mắt chuyển động linh hoạt theo nhịp diễn đạt",
                "duration_sec": 3.6,
                "preconditions": "Đoạn văn giải thích cơ chế, cấu trúc giải phẫu",
                "prohibitions": "CẤM vung tay ra ngoài khung nhìn camera (clipping boundary)"
            },
            {
                "id": "EXPLAIN_PRECISION_PINCH",
                "name": "Ngón tay chụm tinh tế",
                "purpose": "Nhấn mạnh chi tiết vi mô, liều lượng nhỏ, nang lông, vi khuẩn",
                "body_hand": "Ngón cái và ngón trỏ khép gần nhau (Precision grip) đưa ra trước ngang ngực",
                "facial_eye": "Mắt hội tụ nhìn vào khoảng không giữa hai ngón rồi nhìn lại bệnh nhân",
                "duration_sec": 2.4,
                "preconditions": "Giải thích về kích thước tổn thương (vài milimet), nang tóc, vi khuẩn, nồng độ",
                "prohibitions": "CẤM đưa ngón tay sát mặt mình"
            }
        ]
    },
    {
        "group_id": "GRP_09_MEDICATION_INSTRUCTION",
        "group_name": "Hướng dẫn dùng thuốc an toàn",
        "intent": "medication_guide",
        "variants": [
            {
                "id": "MED_HAND_HOLD_IMAGINED",
                "name": "Bàn tay khum giữ hướng dẫn",
                "purpose": "Hướng dẫn cách uống thuốc, thời điểm uống sau ăn",
                "body_hand": "Bàn tay trái khum nhẹ như đang giữ chỉ dẫn, tay phải diễn giải minh họa",
                "facial_eye": "Gương mặt ân cần, nhắc nhở từng điều cẩn thận",
                "duration_sec": 3.0,
                "preconditions": "Đang tư vấn đơn thuốc hoặc hướng dẫn cách dùng thuốc",
                "prohibitions": "CẤM giả vờ động tác nuốt thuốc hoặc giả vờ tiêm chích vào người"
            },
            {
                "id": "MED_COUNTING_SEQUENCE",
                "name": "Bàn tay đếm nhịp liều lượng",
                "purpose": "Liệt kê các lần uống thuốc trong ngày (sáng - trưa - tối)",
                "body_hand": "Bàn tay mở lần lượt các ngón dứt khoát nhẹ nhàng theo các mốc thời gian",
                "facial_eye": "Mắt theo dõi tiến trình truyền đạt, đảm bảo bệnh nhân hiểu",
                "duration_sec": 3.5,
                "preconditions": "Liệt kê danh sách thuốc hoặc phác đồ nhiều bước",
                "prohibitions": "CẤM búng ngón tay"
            }
        ]
    },
    {
        "group_id": "GRP_10_LIFESTYLE_ADVICE",
        "group_name": "Tư vấn lối sống & Dinh dưỡng",
        "intent": "lifestyle_advice",
        "variants": [
            {
                "id": "LIFESTYLE_OPEN_EXPANSIVE",
                "name": "Hai tay mở rộng thư thái",
                "purpose": "Khuyên tập thể dục, hít thở không khí trong lành, giải tỏa stress",
                "body_hand": "Hai tay mở rộng sang hai bên ngang ngực dưới, thân mình thả lỏng",
                "facial_eye": "Nụ cười ấm áp 15%, ánh mắt khích lệ tích cực",
                "duration_sec": 3.0,
                "preconditions": "Khuyên bảo về vận động, nghỉ ngơi, tinh thần lạc quan",
                "prohibitions": "CẤM dùng trong bối cảnh cấp cứu hoặc bệnh nhân đang chịu đau cấp"
            },
            {
                "id": "LIFESTYLE_CALM_SETTLE",
                "name": "Hạ tay nhẹ nhàng ổn định",
                "purpose": "Nhấn mạnh tầm quan trọng của giấc ngủ đủ và uống đủ nước",
                "body_hand": "Hai tay từ từ hạ về tư thế đan tay ngang bụng, tư thế đứng/ngồi thẳng cân bằng",
                "facial_eye": "Gương mặt an tĩnh, điềm đạm",
                "duration_sec": 2.6,
                "preconditions": "Khuyên ngủ đủ giấc, giảm bớt công việc",
                "prohibitions": "CẤM ngáp hoặc biểu hiện mệt mỏi"
            }
        ]
    },
    {
        "group_id": "GRP_11_UNCERTAIN_THINKING",
        "group_name": "Suy ngẫm / Xử lý thông tin phức tạp",
        "intent": "thinking",
        "variants": [
            {
                "id": "THINK_EYE_DEFLECT",
                "name": "Ánh mắt lệch góc suy ngẫm",
                "purpose": "Thể hiện bác sĩ đang phân tích dữ liệu lâm sàng phức tạp",
                "body_hand": "Thân mình giữ nguyên, một tay nâng nhẹ ngang sườn, đầu nghiêng 3 độ",
                "facial_eye": "Ánh mắt nhìn lệch 15 độ sang góc trên-phải trong 0.8 giây rồi quay lại nhìn thẳng",
                "duration_sec": 2.0,
                "preconditions": "Hệ thống AI đang tổng hợp suy luận hoặc bệnh cảnh có nhiều khả năng",
                "prohibitions": "CẤM gãi đầu gãi tai; CẤM cắn môi; CẤM chau mày quá căng thẳng"
            },
            {
                "id": "THINK_HAND_CHIN_NEAR",
                "name": "Tay gần cằm đắn đo",
                "purpose": "Cân nhắc phác đồ điều trị tối ưu",
                "body_hand": "Bàn tay đưa lên cách cằm 5-8cm (KHÔNG chạm da mặt để tránh clipping), đầu gật chậm",
                "facial_eye": "Mắt hơi hẹp lại 5% thể hiện chiều sâu tư duy",
                "duration_sec": 2.5,
                "preconditions": "Đang phân tích chẩn đoán phân biệt",
                "prohibitions": "CẤM tay chạm vào mặt hoặc che miệng (gây hỏng khẩu hình)"
            }
        ]
    },
    {
        "group_id": "GRP_12_DISCLAIMER_CLINICAL",
        "group_name": "Khuyến cáo giới hạn AI",
        "intent": "disclaimer",
        "variants": [
            {
                "id": "DISCLAIM_PALMS_OUT_LOW",
                "name": "Hai lòng bàn tay mở thấp khuyến cáo",
                "purpose": "Khẳng định AI chỉ mang tính tham khảo, không thay thế bác sĩ",
                "body_hand": "Hai lòng bàn tay mở thấp ngang eo hướng ra ngoài, đầu lắc nhẹ 2 độ rất chậm",
                "facial_eye": "Gương mặt mực thước, chân thành, mắt nhìn thẳng",
                "duration_sec": 2.8,
                "preconditions": "Đoạn tuyên bố từ chối trách nhiệm hoặc giới hạn công nghệ",
                "prohibitions": "CẤM nhún vai cợt nhả; CẤM cười toe toét"
            },
            {
                "id": "DISCLAIM_HAND_TO_CHEST_FORMAL",
                "name": "Đặt tay trước ngực đoan trang",
                "purpose": "Nhấn mạnh trách nhiệm cần thăm khám trực tiếp",
                "body_hand": "Tay phải khép ngón đặt nghiêm trang trước ngực, người thẳng",
                "facial_eye": "Biểu cảm nghiêm túc, tôn trọng giới hạn y khoa",
                "duration_sec": 2.4,
                "preconditions": "Yêu cầu người bệnh phải có chỉ định của bác sĩ chuyên khoa",
                "prohibitions": "CẤM cử chỉ giật cục"
            }
        ]
    },
    {
        "group_id": "GRP_13_HYPOTHETICAL_CLARIFY",
        "group_name": "Phản hồi câu hỏi giả định",
        "intent": "hypothetical",
        "variants": [
            {
                "id": "HYPO_HEAD_TILT_ENGAGE",
                "name": "Nghiêng đầu giải thích giả định",
                "purpose": "Trả lời câu hỏi lý thuyết hoặc tình huống giả định của người dùng",
                "body_hand": "Đầu nghiêng nhẹ 4 độ, một tay mở giải thích khách quan",
                "facial_eye": "Ánh mắt khoa học khách quan, không biểu cảm hoảng sợ",
                "duration_sec": 2.6,
                "preconditions": "Câu hỏi chứa từ khóa giả định: 'nếu bị...', 'giả sử...', 'có phải nếu...'",
                "prohibitions": "CẤM kích hoạt biểu cảm hoảng sợ khi câu hỏi chỉ là giả định"
            },
            {
                "id": "HYPO_GESTURE_WEIGHING",
                "name": "Hai tay như bàn cân so sánh",
                "purpose": "So sánh hai khả năng giả định A và B",
                "body_hand": "Hai tay nâng hạ so le nhẹ nhàng như cân nhắc hai khía cạnh",
                "facial_eye": "Mắt nhìn lần lượt giữa hai bên tay rồi nhìn thẳng",
                "duration_sec": 3.2,
                "preconditions": "So sánh giữa lợi ích và nguy cơ, hoặc so sánh 2 khả năng giả định",
                "prohibitions": "CẤM vung tay quá mạnh"
            }
        ]
    },
    {
        "group_id": "GRP_14_THIRD_PERSON_ADDRESS",
        "group_name": "Bệnh cảnh của người thân",
        "intent": "third_person",
        "variants": [
            {
                "id": "THIRD_PERSON_RESPECTFUL_NOD",
                "name": "Gật đầu lắng nghe về người thân",
                "purpose": "Ghi nhận thông tin bệnh của mẹ, con nhỏ, người nhà",
                "body_hand": "Thân mình chú ý lắng nghe, gật đầu tôn trọng, tay giữ vị trí đĩnh đạc",
                "facial_eye": "Ánh mắt chia sẻ trách nhiệm chăm sóc người thân",
                "duration_sec": 2.5,
                "preconditions": "Chủ thể câu hỏi là ngôi thứ ba: 'mẹ tôi', 'con tôi', 'bố em', 'người quen'",
                "prohibitions": "CẤM quy kết triệu chứng trực tiếp lên cơ thể người hỏi"
            },
            {
                "id": "THIRD_PERSON_GUIDE_PROMPT",
                "name": "Mở tay hỏi tuổi và tiền sử người thân",
                "purpose": "Khai thác thêm tuổi tác và bệnh nền của người bệnh thực sự",
                "body_hand": "Hai tay mở nhẹ nhàng hướng tới người hỏi, đầu gật khích lệ",
                "facial_eye": "Mắt tập trung, ân cần",
                "duration_sec": 2.8,
                "preconditions": "Cần biết độ tuổi chính xác của người thân (người già hoặc trẻ nhỏ)",
                "prohibitions": "CẤM gắt gỏng đòi hỏi thông tin"
            }
        ]
    },
    {
        "group_id": "GRP_15_CONTRADICTION_PROBE",
        "group_name": "Phát hiện thông tin mâu thuẫn",
        "intent": "contradiction",
        "variants": [
            {
                "id": "CONTRADICT_GENTLE_PAUSE",
                "name": "Dừng nhẹ tế nhị làm rõ",
                "purpose": "Khi phát hiện thông tin mâu thuẫn trong lời kể",
                "body_hand": "Dừng mọi cử động trong 0.6 giây, đầu hơi nghiêng nhẹ 2 độ, hai tay giữ tĩnh",
                "facial_eye": "Mày hơi nhíu nhẹ 5% thể hiện sự băn khoăn tế nhị, mắt hỏi dò thân thiện",
                "duration_sec": 2.2,
                "preconditions": "Người dùng vừa nói không đau nhưng câu sau lại kêu rất nhức nhối",
                "prohibitions": "CẤM cười mỉa mai; CẤM lắc đầu phản đối thô bạo"
            },
            {
                "id": "CONTRADICT_PALM_ROTATION",
                "name": "Lật bàn tay đề nghị xác nhận",
                "purpose": "Đề nghị người dùng xác nhận lại mốc thời gian chính xác",
                "body_hand": "Bàn tay lật chậm rãi từ úp sang ngửa ngang thắt lưng",
                "facial_eye": "Ánh mắt chân thành chờ đợi sự xác nhận",
                "duration_sec": 2.5,
                "preconditions": "Mâu thuẫn về thời gian hoặc liều lượng uống thuốc",
                "prohibitions": "CẤM đập tay hoặc thái độ phán xét"
            }
        ]
    },
    {
        "group_id": "GRP_16_CHRONIC_MANAGEMENT",
        "group_name": "Tư vấn bệnh mãn tính",
        "intent": "chronic_care",
        "variants": [
            {
                "id": "CHRONIC_STEADY_WARMTH",
                "name": "Tư thế đĩnh đạc kiên trì",
                "purpose": "Đồng hành quản lý bệnh tiểu đường, huyết áp lâu năm",
                "body_hand": "Tư thế vững vàng đĩnh đạc, hai tay giữ vị trí ổn định, chuyển động chậm rãi",
                "facial_eye": "Nụ cười nhẹ bền bỉ 10%, ánh mắt kiên định truyền cảm hứng",
                "duration_sec": 3.2,
                "preconditions": "Tư vấn bệnh không lây nhiễm kéo dài (NCD: Tiểu đường, Tăng huyết áp, Gout)",
                "prohibitions": "CẤM cử chỉ vội vã, hối thúc"
            },
            {
                "id": "CHRONIC_RHYTHM_COUNT",
                "name": "Nhịp tay nhắc đo chỉ số định kỳ",
                "purpose": "Nhắc nhở thói quen đo huyết áp / đường huyết tại nhà",
                "body_hand": "Tay nhịp đều đặn theo từng mốc thời gian kiểm tra nhật ký sức khỏe",
                "facial_eye": "Ánh mắt nhắc nhở ân cần",
                "duration_sec": 2.8,
                "preconditions": "Hướng dẫn ghi chép sổ theo dõi huyết áp/đường huyết",
                "prohibitions": "CẤM chỉ tay đe dọa biến chứng"
            }
        ]
    },
    {
        "group_id": "GRP_17_PAIN_ASSESSMENT",
        "group_name": "Đánh giá mức độ đau",
        "intent": "pain_assessment",
        "variants": [
            {
                "id": "PAIN_SYMPATHETIC_WINCE_MICRO",
                "name": "Vi thấu cảm cơn đau",
                "purpose": "Thể hiện sự đồng cảm khi nghe bệnh nhân đau đớn",
                "body_hand": "Hai tay giữ thấp mở nhẹ, vai hơi hạ thể hiện sự sẻ chia",
                "facial_eye": "Chân mày khép nhẹ 10% trong 0.4s thể hiện cảm nhận được nỗi đau",
                "duration_sec": 2.2,
                "preconditions": "Bệnh nhân mô tả đau nhói dữ dội, đau quặn thắt",
                "prohibitions": "CẤM cười; CẤM nháy mắt; CẤM biểu cảm vô cảm dửng dưng"
            },
            {
                "id": "PAIN_SCALE_INDICATION",
                "name": "Bàn tay minh họa thang điểm đau",
                "purpose": "Hướng dẫn tự chấm điểm đau từ 1 đến 10",
                "body_hand": "Tay nâng từ thấp lên cao chậm rãi minh họa các mức độ đau",
                "facial_eye": "Mắt theo dõi mức độ chỉ định, chờ phản hồi",
                "duration_sec": 3.0,
                "preconditions": "Hỏi thang điểm đau VAS (Visual Analog Scale)",
                "prohibitions": "CẤM cử chỉ giật mình đột ngột"
            }
        ]
    },
    {
        "group_id": "GRP_18_PREVENTION_HYGIENE",
        "group_name": "Vệ sinh & Phòng ngừa",
        "intent": "hygiene",
        "variants": [
            {
                "id": "HYGIENE_CLEAN_GESTURE",
                "name": "Cử chỉ gọn gàng vô khuẩn",
                "purpose": "Hướng dẫn rửa tay, chăm sóc da, vệ sinh răng miệng",
                "body_hand": "Hai bàn tay chuyển động gọn gàng sạch sẽ, dứt khoát ngang ngực",
                "facial_eye": "Khuôn mặt sáng sủa, ánh mắt tin cậy",
                "duration_sec": 2.8,
                "preconditions": "Tư vấn vệ sinh vết thương, súc miệng, khử trùng",
                "prohibitions": "CẤM đưa tay chạm vào mắt mũi miệng của chính mình"
            },
            {
                "id": "HYGIENE_STEP_DELINEATION",
                "name": "Phân định các bước sát khuẩn",
                "purpose": "Hướng dẫn trình tự xử lý vết thương đúng quy trình",
                "body_hand": "Tay phân chia không gian rõ ràng bước 1 - bước 2 - bước 3",
                "facial_eye": "Mắt nhấn nhá theo từng bước",
                "duration_sec": 3.2,
                "preconditions": "Quy trình sơ cứu hoặc sát khuẩn da",
                "prohibitions": "CẤM cử chỉ cẩu thả, quơ quào"
            }
        ]
    },
    {
        "group_id": "GRP_19_FOLLOW_UP_SCHEDULING",
        "group_name": "Hẹn tái khám & Theo dõi",
        "intent": "followup",
        "variants": [
            {
                "id": "FOLLOWUP_CALENDAR_INDICATE",
                "name": "Bàn tay nghiêng nhắc hẹn lịch",
                "purpose": "Dặn dò ngày tái khám sau đợt thuốc",
                "body_hand": "Bàn tay nghiêng nhẹ như đang xem lịch theo dõi, đầu gật nhẹ",
                "facial_eye": "Ánh mắt nhắc nhở chu đáo, nụ cười nhẹ 15%",
                "duration_sec": 2.5,
                "preconditions": "Hẹn khám lại sau 3 ngày, 7 ngày hoặc khi có dấu hiệu bất thường",
                "prohibitions": "CẤM biểu cảm hối thúc tiêu cực"
            },
            {
                "id": "FOLLOWUP_REASSURING_WAVE_LOW",
                "name": "Tay nâng an tâm theo dõi",
                "purpose": "Trấn an người bệnh yên tâm điều trị tại nhà",
                "body_hand": "Một tay nâng nhẹ một nhịp như lời chào hẹn gặp lại, thân đĩnh đạc",
                "facial_eye": "Nụ cười ấm áp, mắt nhìn thẳng bệnh nhân",
                "duration_sec": 2.4,
                "preconditions": "Kết thúc phần dặn dò theo dõi tại nhà",
                "prohibitions": "CẤM vẫy tay cao quá vai"
            }
        ]
    },
    {
        "group_id": "GRP_20_ALLERGY_WARNING",
        "group_name": "Cảnh báo dị ứng thuốc / Sốc",
        "intent": "allergy_alert",
        "variants": [
            {
                "id": "ALLERGY_ALERT_STEADY",
                "name": "Tư thế cảnh báo phản vệ",
                "purpose": "Cảnh báo nguy cơ dị ứng thuốc, phù mạch, sốc phản vệ",
                "body_hand": "Thân bất động, một tay giơ ngang ngực cảnh báo, một tay nắm nhẹ",
                "facial_eye": "Mắt mở to tập trung, chân mày nghiêm nghị",
                "duration_sec": 2.8,
                "preconditions": "Bệnh nhân có tiền sử dị ứng kháng sinh hoặc nổi mề đay sau uống thuốc",
                "prohibitions": "CẤM cử chỉ lơ là, cợt nhả"
            },
            {
                "id": "ALLERGY_EMERGENCY_STOP",
                "name": "Ra hiệu ngưng thuốc lập tức",
                "purpose": "Yêu cầu ngừng ngay loại thuốc gây dị ứng",
                "body_hand": "Bàn tay chặt dứt khoát ngang ngực ra hiệu dừng lại ngay lập tức",
                "facial_eye": "Ánh mắt kiên quyết, biểu cảm cảnh báo cấp 1",
                "duration_sec": 2.0,
                "preconditions": "Bệnh nhân xuất hiện phát ban, ngứa môi, khó thở sau dùng thuốc",
                "prohibitions": "CẤM ngập ngừng, do dự"
            }
        ]
    },
    {
        "group_id": "GRP_21_SPECIAL_POPULATION",
        "group_name": "Đối tượng đặc biệt (Bà bầu, Trẻ em, Người già)",
        "intent": "special_population",
        "variants": [
            {
                "id": "SPECIAL_GENTLE_LEAN",
                "name": "Nghiêng người cẩn trọng",
                "purpose": "Tư vấn thuốc cho phụ nữ có thai hoặc cho con bú",
                "body_hand": "Nghiêng người nhẹ, cử chỉ hai tay cực kỳ cẩn trọng, mềm mại",
                "facial_eye": "Biểu cảm nâng niu chu đáo, mắt ấm áp",
                "duration_sec": 3.0,
                "preconditions": "Đối tượng là phụ nữ mang thai, cho con bú, trẻ sơ sinh",
                "prohibitions": "CẤM cử chỉ mạnh bạo hoặc kê đơn tùy tiện"
            },
            {
                "id": "SPECIAL_PROTECTIVE_HOLD",
                "name": "Hai tay che chở bảo bọc",
                "purpose": "Nhấn mạnh chống chỉ định tuyệt đối trên đối tượng nhạy cảm",
                "body_hand": "Hai tay đặt gần nhau trước ngực thể hiện sự bảo bọc cẩn thận",
                "facial_eye": "Ánh mắt nhắc nhở thận trọng tối đa",
                "duration_sec": 2.8,
                "preconditions": "Cảnh báo thuốc có nguy cơ gây quái thai hoặc độc tính cho trẻ",
                "prohibitions": "CẤM xem nhẹ tác dụng phụ"
            }
        ]
    },
    {
        "group_id": "GRP_22_DIET_NUTRITION",
        "group_name": "Chế độ ăn uống kiêng cữ",
        "intent": "diet_advice",
        "variants": [
            {
                "id": "DIET_SEPARATION_HANDS",
                "name": "Hai tay phân tách kiêng - nên",
                "purpose": "Chỉ rõ thực phẩm nên dùng và thực phẩm cần kiêng",
                "body_hand": "Hai tay tách sang hai bên (bên trái khuyến khích - bên phải hạn chế)",
                "facial_eye": "Khuôn mặt khách quan, điều độ",
                "duration_sec": 3.2,
                "preconditions": "Hướng dẫn ăn kiêng đường, muối, chất béo, kiêng cay nóng",
                "prohibitions": "CẤM cử chỉ ghê tởm thức ăn"
            },
            {
                "id": "DIET_AFFIRMATIVE_PALM",
                "name": "Lòng bàn tay nâng món tốt",
                "purpose": "Khuyến khích uống nhiều nước và ăn nhiều chất xơ",
                "body_hand": "Lòng bàn tay ngửa hướng lên nhẹ nhàng mang tính khích lệ",
                "facial_eye": "Nụ cười nhẹ khuyến khích 15%",
                "duration_sec": 2.5,
                "preconditions": "Khuyên dùng rau xanh, trái cây, uống đủ 2 lít nước",
                "prohibitions": "CẤM xua tay thô lỗ"
            }
        ]
    },
    {
        "group_id": "GRP_23_MENTAL_HEALTH_SUPPORT",
        "group_name": "Hỗ trợ tâm lý & Căng thẳng",
        "intent": "mental_health",
        "variants": [
            {
                "id": "MENTAL_DEEP_BREATHE_SYNC",
                "name": "Đồng bộ nhịp thở sâu",
                "purpose": "Hướng dẫn bệnh nhân giải tỏa cơn hoảng loạn",
                "body_hand": "Hai tay hạ thấp mở nhẹ, ngực nở nhẹ theo nhịp hít sâu rồi thở chậm",
                "facial_eye": "Ánh mắt an dịu, chân mày thả lỏng hoàn toàn",
                "duration_sec": 4.0,
                "preconditions": "Bệnh nhân căng thẳng cực độ, mất ngủ, rối loạn lo âu",
                "prohibitions": "CẤM nhìn đồng hồ hoặc tỏ ra sốt ruột"
            },
            {
                "id": "MENTAL_OPEN_HEARING",
                "name": "Tư thế mở lòng tĩnh lặng",
                "purpose": "Tạo không gian an toàn để bệnh nhân giãi bày tâm sự",
                "body_hand": "Hai tay mở nhẹ trên đùi/bàn, thân mình tĩnh lặng tuyệt đối",
                "facial_eye": "Ánh mắt bao dung, chăm chú lắng nghe",
                "duration_sec": 3.5,
                "preconditions": "Bệnh nhân chia sẻ nỗi đau tâm lý, trầm cảm",
                "prohibitions": "CẤM ngắt lời hoặc đưa ra phán xét đạo đức"
            }
        ]
    },
    {
        "group_id": "GRP_24_LAB_TEST_EXPLANATION",
        "group_name": "Giải thích kết quả xét nghiệm",
        "intent": "lab_analysis",
        "variants": [
            {
                "id": "LAB_READING_ATTENTION",
                "name": "Đọc chỉ số rồi giải thích",
                "purpose": "Phân tích các chỉ số xét nghiệm máu, men gan, nước tiểu",
                "body_hand": "Mắt nhìn xuống 20 độ như đọc kết quả trong 1.2s, sau đó ngước lên giải thích",
                "facial_eye": "Gương mặt khoa học chính xác, điềm đạm",
                "duration_sec": 3.2,
                "preconditions": "Giải thích kết quả xét nghiệm hoặc kết quả chẩn đoán hình ảnh",
                "prohibitions": "CẤM nhăn mặt làm bệnh nhân hốt hoảng"
            },
            {
                "id": "LAB_NORMAL_REASSURE",
                "name": "Tay hạ báo tin chỉ số tốt",
                "purpose": "Thông báo các chỉ số nằm trong giới hạn bình thường",
                "body_hand": "Hai tay hạ xuống nhẹ nhàng, thân người thả lỏng",
                "facial_eye": "Ánh mắt vui vẻ nhẹ nhõm, nụ cười 20%",
                "duration_sec": 2.4,
                "preconditions": "Kết quả xét nghiệm âm tính hoặc bình thường",
                "prohibitions": "CẤM cười quá trớn"
            }
        ]
    },
    {
        "group_id": "GRP_25_VACCINATION_CONSULT",
        "group_name": "Tư vấn tiêm chủng",
        "intent": "vaccine",
        "variants": [
            {
                "id": "VACCINE_ARM_INDICATE_PROXIMAL",
                "name": "Chỉ vùng cơ delta gián tiếp",
                "purpose": "Giải thích vị trí tiêm bắp và phản ứng sưng đau tại chỗ",
                "body_hand": "Một tay chỉ nhẹ về hướng cánh tay đối diện (cách 10cm, không chạm vào tay)",
                "facial_eye": "Ánh mắt theo dõi hướng chỉ dẫn",
                "duration_sec": 2.6,
                "preconditions": "Giải thích vị trí tiêm vắc xin hoặc theo dõi phản ứng sau tiêm",
                "prohibitions": "CẤM làm động tác giả vờ đâm kim tiêm rùng rợn"
            },
            {
                "id": "VACCINE_IMMUNITY_SHIELD",
                "name": "Hai tay che chở miễn dịch",
                "purpose": "Giải thích hiệu quả tạo kháng thể bảo vệ của vắc xin",
                "body_hand": "Hai tay đưa ra trước đan nhẹ tạo cảm giác lá chắn bảo vệ",
                "facial_eye": "Ánh mắt kiên định, tự tin",
                "duration_sec": 3.0,
                "preconditions": "Giải thích cơ chế phòng ngừa dịch bệnh của vắc xin",
                "prohibitions": "CẤM cử động cứng ngắc"
            }
        ]
    },
    {
        "group_id": "GRP_26_INTERRUPTION_HANDOFF",
        "group_name": "Xử lý khi người dùng ngắt lời",
        "intent": "interruption",
        "variants": [
            {
                "id": "INTERRUPT_SMOOTH_SETTLE",
                "name": "Hạ tay quán tính 0.3s ngậm miệng",
                "purpose": "Dừng nói mượt mà ngay khi người dùng nói chen ngang (Barge-in)",
                "body_hand": "Tay đang chuyển động lập tức giảm tốc mượt mà (Inertial damp) về tư thế nghỉ trong 0.3s",
                "facial_eye": "Khẩu hình khép tự nhiên ngay lập tức, mắt hướng ngay về camera",
                "duration_sec": 0.4,
                "preconditions": "Phát hiện âm thanh người dùng nói đè lên (Barge-in trigger)",
                "prohibitions": "CẤM giật cục khựng hình (frame pop); CẤM tiếp tục nói đè lên user"
            },
            {
                "id": "INTERRUPT_HEAD_RESET",
                "name": "Quay đầu chú ý lắng nghe lại",
                "purpose": "Chuyển toàn bộ trọng tâm chú ý sang câu nói mới của user",
                "body_hand": "Đầu xoay nhẹ căn chỉnh thẳng với camera, hai tay giữ vị trí lắng nghe",
                "facial_eye": "Mắt mở to đón nhận câu hỏi mới",
                "duration_sec": 0.5,
                "preconditions": "Sau khi đã dừng cử chỉ cũ",
                "prohibitions": "CẤM lắc đầu tỏ vẻ khó chịu vì bị ngắt lời"
            }
        ]
    },
    {
        "group_id": "GRP_27_AUDIO_LOSS_HANDOFF",
        "group_name": "Mất tín hiệu âm thanh / Lỗi mạng",
        "intent": "audio_loss",
        "variants": [
            {
                "id": "AUDIO_LOSS_PUZZLED_NEUTRAL",
                "name": "Nghiêng đầu lắng nghe tín hiệu",
                "purpose": "Xử lý khi mất gói âm thanh hoặc ASR không nhận dạng được",
                "body_hand": "Đầu hơi nghiêng 3 độ, một tay đưa nhẹ ngang sườn, giữ tĩnh",
                "facial_eye": "Ánh mắt tập trung lắng nghe nhưng không căng thẳng",
                "duration_sec": 2.2,
                "preconditions": "Mất gói audio TTS hoặc độ tin cậy ASR < 0.5",
                "prohibitions": "CẤM nhún vai cẩu thả"
            },
            {
                "id": "AUDIO_LOSS_REQUEST_REPEAT",
                "name": "Mở tay xin nhắc lại",
                "purpose": "Đề nghị người dùng nhắc lại câu hỏi do đường truyền kém",
                "body_hand": "Một tay đưa nhẹ ra trước kết hợp nụ cười thông cảm nhẹ",
                "facial_eye": "Nụ cười thông cảm 10%, mắt ân cần",
                "duration_sec": 2.0,
                "preconditions": "Cần người dùng nhắc lại câu hỏi",
                "prohibitions": "CẤM thái độ cáu kỉnh vì lỗi mạng"
            }
        ]
    },
    {
        "group_id": "GRP_28_CONFIRMATION_CHECK",
        "group_name": "Hỏi lại xác nhận hiểu đúng",
        "intent": "confirm_understanding",
        "variants": [
            {
                "id": "CONFIRM_FORWARD_NOD",
                "name": "Gật nhẹ hỏi đã nắm rõ chưa",
                "purpose": "Hỏi xem bệnh nhân đã hiểu rõ hướng dẫn dùng thuốc chưa",
                "body_hand": "Gật đầu một nhịp nhỏ, hai tay mở nhỏ hướng về bệnh nhân",
                "facial_eye": "Ánh mắt duy trì eye contact chân thành",
                "duration_sec": 2.2,
                "preconditions": "Sau khi vừa truyền đạt hướng dẫn quan trọng",
                "prohibitions": "CẤM trợn mắt hoặc gật đầu quá nhanh"
            },
            {
                "id": "CONFIRM_PAUSE_WAIT",
                "name": "Giữ tĩnh chờ phản hồi",
                "purpose": "Tạo khoảng lặng cần thiết để người bệnh suy ngẫm và trả lời",
                "body_hand": "Toàn thân giữ tĩnh trong 1.5 giây, nhịp thở đều đặn",
                "facial_eye": "Ánh mắt kiên nhẫn chờ đợi",
                "duration_sec": 1.8,
                "preconditions": "Sau câu hỏi xác nhận",
                "prohibitions": "CẤM ngọ nguậy mất tập trung"
            }
        ]
    },
    {
        "group_id": "GRP_29_TERMINATION_CLOSING",
        "group_name": "Chào tạm biệt & Kết thúc phiên",
        "intent": "closing",
        "variants": [
            {
                "id": "CLOSE_FORMAL_BOW",
                "name": "Cúi đầu chào trang trọng",
                "purpose": "Kết thúc phiên tư vấn khám bệnh chuẩn mực y khoa",
                "body_hand": "Đầu cúi chào nhẹ 5 độ, hai tay đặt ngay ngắn trước bụng/bàn",
                "facial_eye": "Nụ cười mỉm chuyên nghiệp 20%, ánh mắt ấm áp",
                "duration_sec": 2.5,
                "preconditions": "Kết thúc phiên hội thoại thành công",
                "prohibitions": "CẤM gập người quá sâu kiểu kịch nghệ"
            },
            {
                "id": "CLOSE_WARM_WISH",
                "name": "Nâng tay chúc sức khỏe",
                "purpose": "Gửi lời chúc người bệnh mau bình phục",
                "body_hand": "Tay phải nâng nhẹ vẫy góc 15 độ rất chậm kết hợp tay trái để ngang ngực",
                "facial_eye": "Ánh mắt tươi sáng, nụ cười chân thành",
                "duration_sec": 2.8,
                "preconditions": "Lời chúc sức khỏe cuối buổi",
                "prohibitions": "CẤM quay lưng trước khi animation kết thúc"
            }
        ]
    },
    {
        "group_id": "GRP_30_HIGH_FEVER_CONVULSION",
        "group_name": "Xử lý sốt cao co giật ở trẻ",
        "intent": "emergency_convulsion",
        "variants": [
            {
                "id": "CONVULSION_URGENT_CALM",
                "name": "Ra hiệu bình tĩnh dứt khoát",
                "purpose": "Hướng dẫn phụ huynh sơ cứu trẻ co giật đúng cách",
                "body_hand": "Thân mình rướn tới, hai tay giữ phẳng hạ thấp ra lệnh bình tĩnh, giọng dứt khoát",
                "facial_eye": "Mặt cực kỳ nghiêm túc, mắt mở to truyền sự tập trung",
                "duration_sec": 2.8,
                "preconditions": "Trẻ em sốt cao co giật; tình huống cấp bách",
                "prohibitions": "CẤM cử chỉ hoảng hốt, luống cuống; CẤM cười"
            },
            {
                "id": "CONVULSION_SIDE_POSITION",
                "name": "Hai tay mô phỏng tư thế nằm nghiêng",
                "purpose": "Dặn đặt trẻ nằm nghiêng an toàn, KHÔNG nhét vật cứng vào miệng",
                "body_hand": "Hai tay đưa nhẹ sang một bên minh họa mặt phẳng nằm nghiêng",
                "facial_eye": "Ánh mắt kiên quyết nhấn mạnh điều KHÔNG ĐƯỢC LÀM",
                "duration_sec": 3.0,
                "preconditions": "Hướng dẫn tư thế nghiêng chống sặc đường thở",
                "prohibitions": "CẤM làm động tác thọc tay vào miệng"
            }
        ]
    },
    {
        "group_id": "GRP_31_BLEEDING_HEMOSTASIS",
        "group_name": "Xử trí chảy máu - Răng / Vết thương",
        "intent": "bleeding_control",
        "variants": [
            {
                "id": "HEMOSTASIS_COMPRESS_GESTURE",
                "name": "Mô phỏng ép chặt cầm máu tại chỗ",
                "purpose": "Hướng dẫn cắn chặt gạc cầm máu chân răng hoặc ép vết thương",
                "body_hand": "Bàn tay nắm nhẹ mô phỏng lực ép gạc liên tục trong 30-45 phút",
                "facial_eye": "Gương mặt nghiêm túc, chăm chú theo dõi",
                "duration_sec": 3.0,
                "preconditions": "Chảy máu chân răng sau nhổ, vết cắt chảy máu",
                "prohibitions": "CẤM đưa tay lên miệng mình; CẤM làm động tác khạc nhổ"
            },
            {
                "id": "HEMOSTASIS_ELEVATION_INDICATE",
                "name": "Nhắc nhở ngồi thẳng đầu cao",
                "purpose": "Dặn không nằm ngửa để tránh nuốt máu gây nôn",
                "body_hand": "Bàn tay nâng hướng thẳng đứng nhắc giữ đầu cao, không cúi gập",
                "facial_eye": "Ánh mắt dặn dò cẩn thận",
                "duration_sec": 2.6,
                "preconditions": "Chảy máu khoang miệng hoặc chảy máu cam",
                "prohibitions": "CẤM ngửa cổ ra sau (sai nguyên tắc sơ cứu)"
            }
        ]
    },
    {
        "group_id": "GRP_32_BURN_TRAUMA_FIRST_AID",
        "group_name": "Sơ cứu bỏng & Chấn thương",
        "intent": "burn_first_aid",
        "variants": [
            {
                "id": "BURN_COOL_WATER_INDICATE",
                "name": "Minh họa xả nước mát liên tục",
                "purpose": "Hướng dẫn ngâm/xả nước mát sạch 15-20 phút ngay lập tức",
                "body_hand": "Hai tay mở thấp chuyển động xuôi nhẹ minh họa dòng nước chảy liên tục",
                "facial_eye": "Gương mặt khẩn trương dứt khoát",
                "duration_sec": 3.0,
                "preconditions": "Bị bỏng nhiệt, nước sôi, hóa chất",
                "prohibitions": "CẤM chạm vào vết bỏng; CẤM xoa tay (gây hiểu nhầm bôi thuốc bừa bãi)"
            },
            {
                "id": "BURN_PROTECT_CLEAN",
                "name": "Bàn tay khum che chở vô khuẩn",
                "purpose": "Nhắc che gạc sạch và đến viện, không bôi kem đánh răng/mỡ trăn",
                "body_hand": "Hai bàn tay khum che chở nhẹ nhàng, sau đó mở ra chỉ dẫn đến viện",
                "facial_eye": "Ánh mắt nhấn mạnh điều kiêng kỵ dân gian sai lầm",
                "duration_sec": 3.2,
                "preconditions": "Cảnh báo không dùng mẹo dân gian nguy hại",
                "prohibitions": "CẤM cử chỉ xua tay xem thường"
            }
        ]
    }
]

# -------------------------------------------------------------
# 2. DỮ LIỆU THIẾT KẾ: 32 TÌNH HUỐNG KIỂM THỬ BỐI CẢNH (TEST SCENARIOS)
# -------------------------------------------------------------
TEST_SCENARIOS = [
    {
        "id": "TC_01_NEGATION_CHEST_PAIN",
        "user_query": "Tôi chỉ bị mỏi cơ vai gáy chứ không khó thở, không đau ngực",
        "detected_intent": "negation_ack",
        "context_flags": {"has_negation": True, "emergency_flag": False, "subject": "self"},
        "expected_variant": "NEGATION_SUBTLE_NOD",
        "prohibited_actions": ["EMERGENCY_SERIOUS_STILL", "LISTEN_LEAN_FORWARD_NOD_CONTINUOUS"],
        "acceptance_criteria": "Avatar gật đầu 1 nhịp chậm xác nhận đã hiểu thông tin loại trừ, không kích hoạt báo động cấp cứu."
    },
    {
        "id": "TC_02_HYPOTHETICAL_OVERDOSE",
        "user_query": "Nếu lỡ uống nhầm 2 viên thuốc hạ áp cùng lúc thì có nguy hiểm không bác sĩ?",
        "detected_intent": "hypothetical",
        "context_flags": {"is_hypothetical": True, "emergency_flag": False, "subject": "self"},
        "expected_variant": "HYPO_HEAD_TILT_ENGAGE",
        "prohibited_actions": ["EMERGENCY_RAISE_PALM_HALT", "GREET_WARM_NOD"],
        "acceptance_criteria": "Avatar giữ thái độ khoa học khách quan, nghiêng đầu nhẹ giải thích cơ chế, không hoảng sợ vô căn cứ."
    },
    {
        "id": "TC_03_THIRD_PERSON_ELDERLY_FEVER",
        "user_query": "Bà ngoại tôi 82 tuổi hôm nay bị sốt 39 độ và bắt đầu mê man",
        "detected_intent": "emergency_alert",
        "context_flags": {"subject": "third_person", "emergency_flag": True, "vulnerable_population": True},
        "expected_variant": "EMERGENCY_SERIOUS_STILL",
        "prohibited_actions": ["GREET_WARM_NOD", "LIFESTYLE_OPEN_EXPANSIVE"],
        "acceptance_criteria": "Avatar lập tức chuyển sang biểu cảm nghiêm nghị tuyệt đối, không cười, hướng dẫn gọi cấp cứu ngay."
    },
    {
        "id": "TC_04_BLEEDING_GUM_ACUTE",
        "user_query": "Tôi đang bị chảy máu chân răng cần phải làm gì để không còn chảy máu nữa",
        "detected_intent": "bleeding_control",
        "context_flags": {"urgency": "urgent", "bleeding": True, "subject": "self"},
        "expected_variant": "HEMOSTASIS_COMPRESS_GESTURE",
        "prohibited_actions": ["GREET_WARM_NOD", "EXPLAIN_PRECISION_PINCH"],
        "acceptance_criteria": "Mô phỏng lực ép gạc cầm máu tại chỗ, biểu cảm tập trung, hướng dẫn không khạc nhổ."
    },
    {
        "id": "TC_05_STROKE_FAST_SIGNS",
        "user_query": "Bố tôi tự nhiên cười bị méo một bên miệng và tay phải không nhấc lên được",
        "detected_intent": "emergency_alert",
        "context_flags": {"subject": "third_person", "emergency_flag": True, "stroke_fast": True},
        "expected_variant": "EMERGENCY_RAISE_PALM_HALT",
        "prohibited_actions": ["LIFESTYLE_OPEN_EXPANSIVE", "HYPO_HEAD_TILT_ENGAGE"],
        "acceptance_criteria": "Giơ tay chặn dứt khoát, yêu cầu gọi 115 lập tức, không cho uống bất kỳ loại thuốc hay hạ áp nào."
    },
    {
        "id": "TC_06_PREGNANCY_HEADACHE",
        "user_query": "Em đang mang thai tuần thứ 12 bị đau đầu thì có uống được thuốc giảm đau không?",
        "detected_intent": "special_population",
        "context_flags": {"pregnancy": True, "subject": "self"},
        "expected_variant": "SPECIAL_GENTLE_LEAN",
        "prohibited_actions": ["MED_COUNTING_SEQUENCE", "LIFESTYLE_OPEN_EXPANSIVE"],
        "acceptance_criteria": "Thân mình nghiêng cẩn trọng, giọng trầm ấm cảnh báo chống chỉ định NSAID trên phụ nữ mang thai."
    },
    {
        "id": "TC_07_CHILD_FEVER_CONVULSION",
        "user_query": "Bé nhà em 2 tuổi đang sốt 40 độ co giật chân tay em sợ quá",
        "detected_intent": "emergency_convulsion",
        "context_flags": {"pediatric": True, "emergency_flag": True, "convulsion": True},
        "expected_variant": "CONVULSION_URGENT_CALM",
        "prohibited_actions": ["THINK_EYE_DEFLECT", "DISCLAIM_PALMS_OUT_LOW"],
        "acceptance_criteria": "Ra hiệu hai tay hạ thấp bình tĩnh dứt khoát, hướng dẫn nằm nghiêng an toàn, không nhét vật vào miệng."
    },
    {
        "id": "TC_08_SCALD_BURN_FIRST_AID",
        "user_query": "Tôi vừa bị đổ nguyên ấm nước sôi vào cẳng chân đang rất rát",
        "detected_intent": "burn_first_aid",
        "context_flags": {"acute_trauma": True, "burn": True},
        "expected_variant": "BURN_COOL_WATER_INDICATE",
        "prohibited_actions": ["PAIN_SCALE_INDICATION", "LIFESTYLE_OPEN_EXPANSIVE"],
        "acceptance_criteria": "Minh họa dòng nước mát chảy liên tục, dặn xả nước 15-20 phút, cấm bôi kem đánh răng/mỡ trăn."
    },
    {
        "id": "TC_09_NEGATION_NO_FEVER",
        "user_query": "Họng tôi chỉ rát buốt nuốt vướng chứ tôi đo nhiệt kế không hề sốt",
        "detected_intent": "negation_ack",
        "context_flags": {"has_negation": True, "symptom": "sore_throat"},
        "expected_variant": "NEGATION_SUBTLE_NOD",
        "prohibited_actions": ["EMERGENCY_SERIOUS_STILL"],
        "acceptance_criteria": "Avatar gật đầu nhẹ ghi nhận không sốt, tiếp tục tư vấn chăm sóc họng thường quy."
    },
    {
        "id": "TC_10_USER_BARGE_IN",
        "user_query": "[User chen ngang khi bác sĩ đang nói đoạn dài]",
        "detected_intent": "interruption",
        "context_flags": {"interrupted": True},
        "expected_variant": "INTERRUPT_SMOOTH_SETTLE",
        "prohibited_actions": ["TIẾP TỤC NÓI", "GIẬT TAY ĐỘT NGỘT"],
        "acceptance_criteria": "Giảm tốc mượt mà hạ tay trong 0.3s, miệng ngậm tự nhiên, mắt hướng về phía người dùng."
    },
    {
        "id": "TC_11_AUDIO_STREAM_DROP",
        "user_query": "[Mất gói mạng audio từ backend trong 2 giây]",
        "detected_intent": "audio_loss",
        "context_flags": {"network_drop": True},
        "expected_variant": "AUDIO_LOSS_PUZZLED_NEUTRAL",
        "prohibited_actions": ["KHỰNG HÌNH", "LOOP LIPSYNC"],
        "acceptance_criteria": "Giữ tư thế trung tính chăm chú, không bị méo khẩu hình, hỏi lại nhẹ nhàng."
    },
    {
        "id": "TC_12_CONTRADICTORY_PAIN",
        "user_query": "Tôi không thấy đau gì cả nhưng mà chạm nhẹ vào bụng là đau điếng người",
        "detected_intent": "contradiction",
        "context_flags": {"contradiction": True},
        "expected_variant": "CONTRADICT_GENTLE_PAUSE",
        "prohibited_actions": ["CƯỜI MỈA MAI", "GẬT ĐẦU ĐỒNG THUẬN"],
        "acceptance_criteria": "Dừng nhẹ 0.6s tế nhị, đề nghị người dùng làm rõ phản ứng thành bụng."
    },
    {
        "id": "TC_13_INSOMNIA_ANXIETY",
        "user_query": "Dạo này em hay bị mất ngủ, tim đập nhanh hồi hộp khi nghĩ đến công việc",
        "detected_intent": "mental_health",
        "context_flags": {"psychological": True, "urgency": "routine"},
        "expected_variant": "MENTAL_DEEP_BREATHE_SYNC",
        "prohibited_actions": ["EMERGENCY_RAISE_PALM_HALT", "LOOK_AT_WATCH"],
        "acceptance_criteria": "Hạ vai thở sâu mẫu, gương mặt an hòa, lắng nghe chân thành."
    },
    {
        "id": "TC_14_DIABETES_CHRONIC_CARE",
        "user_query": "Bác sĩ ơi chỉ số đường huyết lúc đói của tôi sáng nay là 7.8 có cao quá không?",
        "detected_intent": "chronic_care",
        "context_flags": {"chronic": True},
        "expected_variant": "CHRONIC_STEADY_WARMTH",
        "prohibited_actions": ["EMERGENCY_SERIOUS_STILL", "VỘI VÃ"],
        "acceptance_criteria": "Tư thế đĩnh đạc kiên nhẫn, giải thích chỉ số và nhắc tuân thủ chế độ ăn."
    },
    {
        "id": "TC_15_ANTIBIOTIC_ALLERGY",
        "user_query": "Uống viên amoxicillin xong 15 phút em thấy ngứa ran cổ và nổi mề đay đầy người",
        "detected_intent": "allergy_alert",
        "context_flags": {"allergy": True, "urgent": True},
        "expected_variant": "ALLERGY_EMERGENCY_STOP",
        "prohibited_actions": ["LIFESTYLE_OPEN_EXPANSIVE", "CƯỜI"],
        "acceptance_criteria": "Ra hiệu ngừng thuốc dứt khoát, yêu cầu theo dõi hô hấp và tới trạm y tế."
    },
    {
        "id": "TC_16_ROUTINE_SKIN_CARE",
        "user_query": "Mùa đông da mặt em hay bị khô nứt nẻ thì nên bôi kem dưỡng ẩm loại nào?",
        "detected_intent": "lifestyle_advice",
        "context_flags": {"urgency": "routine"},
        "expected_variant": "LIFESTYLE_OPEN_EXPANSIVE",
        "prohibited_actions": ["EMERGENCY_SERIOUS_STILL"],
        "acceptance_criteria": "Cử chỉ mở rộng thoải mái, nụ cười nhẹ 15%, tư vấn cấp ẩm và uống nước."
    },
    {
        "id": "TC_17_ACUTE_CHEST_PAIN_RED_FLAG",
        "user_query": "Ngực tôi đau nghẹn như có đá đè lan lên cằm và cánh tay trái vã mồ hôi lạnh",
        "detected_intent": "emergency_alert",
        "context_flags": {"emergency_flag": True, "cardiac": True},
        "expected_variant": "EMERGENCY_SERIOUS_STILL",
        "prohibited_actions": ["MỌI NỤ CƯỜI", "GẬT ĐẦU THƯ THÁI"],
        "acceptance_criteria": "Thân mình nghiêm nghị bất động, cảnh báo nhồi máu cơ tim, gọi 115 ngay."
    },
    {
        "id": "TC_18_HYPOTHETICAL_VACCINE_SIDE_EFFECT",
        "user_query": "Nếu tiêm vắc xin cúm thì sau đó có khả năng bị sốt nhẹ không?",
        "detected_intent": "vaccine",
        "context_flags": {"is_hypothetical": True},
        "expected_variant": "VACCINE_IMMUNITY_SHIELD",
        "prohibited_actions": ["EMERGENCY_RAISE_PALM_HALT"],
        "acceptance_criteria": "Giải thích phản ứng tạo kháng thể bình thường, tư vấn chườm mát."
    },
    {
        "id": "TC_19_THIRD_PERSON_CHILD_COUGH",
        "user_query": "Cháu gái em 4 tuổi bị ho đêm nhiều kèm thở rít",
        "detected_intent": "third_person",
        "context_flags": {"pediatric": True, "subject": "third_person"},
        "expected_variant": "THIRD_PERSON_RESPECTFUL_NOD",
        "prohibited_actions": ["CHỈ NGÓN TAY"],
        "acceptance_criteria": "Gật đầu thấu cảm, khai thác thêm tiếng thở rít thanh quản."
    },
    {
        "id": "TC_20_LAB_LIVER_ENZYMES",
        "user_query": "Chỉ số men gan AST 65 ALT 78 của em có phải bị viêm gan nặng rồi không?",
        "detected_intent": "lab_analysis",
        "context_flags": {"lab_test": True},
        "expected_variant": "LAB_READING_ATTENTION",
        "prohibited_actions": ["NHĂN MẶT HOẢNG HỐT"],
        "acceptance_criteria": "Ánh mắt đọc chỉ số rồi nhìn thẳng giải thích mức độ tăng nhẹ, tránh hù dọa."
    },
    {
        "id": "TC_21_POST_OP_WOUND_CARE",
        "user_query": "Vết khâu tiểu phẫu ở tay sau 5 ngày đã được tháo băng rửa nước bình thường chưa?",
        "detected_intent": "hygiene",
        "context_flags": {"wound_care": True},
        "expected_variant": "HYGIENE_CLEAN_GESTURE",
        "prohibited_actions": ["CHẠM MẶT"],
        "acceptance_criteria": "Cử chỉ vô khuẩn gọn gàng, hướng dẫn giữ khô vết khâu."
    },
    {
        "id": "TC_22_HYPERTENSION_SALT_RESTRICTION",
        "user_query": "Tôi bị huyết áp cao thì cần kiêng những loại đồ ăn nào trong mâm cơm?",
        "detected_intent": "diet_advice",
        "context_flags": {"diet": True},
        "expected_variant": "DIET_SEPARATION_HANDS",
        "prohibited_actions": ["BIỂU CẢM GHÊ TỞM"],
        "acceptance_criteria": "Hai tay phân định thực phẩm nhiều muối vs thực phẩm thanh đạm."
    },
    {
        "id": "TC_23_SEEKING_EXACT_HAIR_LOSS_PILLS",
        "user_query": "Tôi cần uống thuốc gì để chống rụng tóc dứt điểm?",
        "detected_intent": "medication_guide",
        "context_flags": {"drug_inquiry": True},
        "expected_variant": "MED_HAND_HOLD_IMAGINED",
        "prohibited_actions": ["GIẢ VỜ NUỐT THUỐC"],
        "acceptance_criteria": "Hướng dẫn thận trọng, chỉ ra nguyên nhân đa yếu tố và khuyên khám chuyên khoa."
    },
    {
        "id": "TC_24_BALDNESS_MANAGEMENT",
        "user_query": "Tôi đang bị hói đỉnh đầu, làm gì để hết bị hói?",
        "detected_intent": "explanation",
        "context_flags": {"alopecia": True},
        "expected_variant": "EXPLAIN_PRECISION_PINCH",
        "prohibited_actions": ["CƯỜI CỢT NHẢ", "CHỈ VÀO ĐẦU MÌNH"],
        "acceptance_criteria": "Giải thích cơ chế hormone DHT và nang tóc bằng cử chỉ tinh tế, không tự chỉ vào đầu mình."
    },
    {
        "id": "TC_25_HEADACHE_SEVERITY_SCALE",
        "user_query": "Đầu em đau nhức dữ dội như búa bổ không mở nổi mắt",
        "detected_intent": "pain_assessment",
        "context_flags": {"severe_pain": True},
        "expected_variant": "PAIN_SYMPATHETIC_WINCE_MICRO",
        "prohibited_actions": ["CƯỜI", "VÔ CẢM"],
        "acceptance_criteria": "Vi thấu cảm chân mày 10%, hỏi thêm dấu hiệu cứng gáy, hướng dẫn khám ngay."
    },
    {
        "id": "TC_26_DISCLAIMER_AI_LIMITS",
        "user_query": "Bác sĩ AI có thể kê luôn đơn thuốc kháng sinh cho tôi được không?",
        "detected_intent": "disclaimer",
        "context_flags": {"prescribe_request": True},
        "expected_variant": "DISCLAIM_PALMS_OUT_LOW",
        "prohibited_actions": ["NHÚN VAI", "CƯỜI LỚN"],
        "acceptance_criteria": "Mở hai lòng bàn tay thấp mực thước, tuyên bố giới hạn pháp lý và an toàn người bệnh."
    },
    {
        "id": "TC_27_UNCERTAIN_MULTIPLE_SYMPTOMS",
        "user_query": "Vừa mệt mỏi, vừa rụng tóc, hay lạnh đầu ngón tay mà lại tăng cân bất thường",
        "detected_intent": "thinking",
        "context_flags": {"complex_presentation": True},
        "expected_variant": "THINK_EYE_DEFLECT",
        "prohibited_actions": ["GÃI ĐẦU", "CHAU MÀY CĂNG THẲNG"],
        "acceptance_criteria": "Ánh mắt suy ngẫm góc 15 độ, phân tích khả năng suy giáp hoặc rối loạn chuyển hóa."
    },
    {
        "id": "TC_28_CONFIRMING_INHALER_USE",
        "user_query": "Tôi xịt ống hen hít sâu nín thở 10 giây như vậy đúng chưa?",
        "detected_intent": "confirm_understanding",
        "context_flags": {"technique_check": True},
        "expected_variant": "CONFIRM_FORWARD_NOD",
        "prohibited_actions": ["TRỢN MẮT"],
        "acceptance_criteria": "Gật nhẹ đồng thuận, khen ngợi kỹ thuật chuẩn và nhắc súc miệng sau xịt corticoid."
    },
    {
        "id": "TC_29_FOLLOW_UP_CHECK_IN",
        "user_query": "Hôm nay là ngày thứ 3 tôi uống thuốc theo đơn rồi thấy đỡ đau nhiều",
        "detected_intent": "followup",
        "context_flags": {"improving": True},
        "expected_variant": "FOLLOWUP_REASSURING_WAVE_LOW",
        "prohibited_actions": ["CẢNH BÁO ĐỎ"],
        "acceptance_criteria": "Tay nâng an tâm, dặn uống đủ liệu trình không tự ý ngưng thuốc giữa chừng."
    },
    {
        "id": "TC_30_TERMINATING_CONSULTATION",
        "user_query": "Cảm ơn bác sĩ nhiều, tôi đã hiểu rõ mọi thứ rồi",
        "detected_intent": "closing",
        "context_flags": {"closing": True},
        "expected_variant": "CLOSE_FORMAL_BOW",
        "prohibited_actions": ["CÚI GẬP QUÁ SÂU"],
        "acceptance_criteria": "Đầu cúi chào nhẹ 5 độ, hai tay đặt ngay ngắn, lời chúc sức khỏe trang trọng."
    },
    {
        "id": "TC_31_LOW_ASR_CONFIDENCE",
        "user_query": "[Giọng người dùng quá nhỏ hoặc nhiều tiếng ồn, ASR score 0.35]",
        "detected_intent": "audio_loss",
        "context_flags": {"asr_low_confidence": True},
        "expected_variant": "AUDIO_LOSS_REQUEST_REPEAT",
        "prohibited_actions": ["CÁU KỈNH", "ĐOÁN MÒ TRIỆU CHỨNG"],
        "acceptance_criteria": "Avatar mở tay xin nhắc lại với nụ cười thông cảm, không đoán mò triệu chứng nguy hiểm."
    },
    {
        "id": "TC_32_EMERGENCY_POISONING_INGESTION",
        "user_query": "Cháu bé vừa uống nhầm chai nước rửa bồn cầu cách đây 5 phút",
        "detected_intent": "emergency_alert",
        "context_flags": {"poisoning": True, "emergency_flag": True},
        "expected_variant": "EMERGENCY_RAISE_PALM_HALT",
        "prohibited_actions": ["GẬT ĐẦU", "LIFESTYLE_OPEN_EXPANSIVE"],
        "acceptance_criteria": "Giơ tay chặn khẩn cấp, CẤM móc họng gây nôn vì nguy cơ bỏng thực quản, đưa đi cấp cứu ngay kèm vỏ chai."
    }
]

print(f"-> Đã chuẩn bị {len(ACTION_CATALOG)} nhóm hành động với {sum(len(g['variants']) for g in ACTION_CATALOG)} biến thể.")
print(f"-> Đã chuẩn bị {len(TEST_SCENARIOS)} tình huống kiểm thử bối cảnh lâm sàng.")
