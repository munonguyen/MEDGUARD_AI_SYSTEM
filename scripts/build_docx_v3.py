#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trình tạo tài liệu đặc tả Word MedGuard_Unity_CSharp_Motion_Spec_v3.docx (32 trang chuẩn)
"""

import os
import sys
import json
import shutil
from pathlib import Path
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

from build_medguard_unity_v3 import ACTION_CATALOG, TEST_SCENARIOS

OUTPUT_DOCX_LOCAL = Path("/Users/munonguyen/Project ATI/docs/MedGuard_Unity_CSharp_Motion_Spec_v3.docx")
OUTPUT_DOCX_DOWNLOADS = Path("/Users/munonguyen/Downloads/MedGuard_Unity_CSharp_Motion_Spec_v3.docx")

HEX_PRIMARY = "1B365D"       # Deep Navy
HEX_SECONDARY = "008080"     # Medical Teal
HEX_HEADER_BG = "EDF2F7"     # Light Slate
HEX_LIGHT_ROW = "F7FAFC"     # Zebra Row
HEX_BORDER = "CBD5E0"        # Border Gray
HEX_ALERT_BG = "FFF5F5"      # Alert light red
HEX_ALERT_BORDER = "E53E3E"  # Alert red

COLOR_PRIMARY = RGBColor(27, 54, 93)
COLOR_SECONDARY = RGBColor(0, 128, 128)
COLOR_DARK = RGBColor(45, 55, 72)
COLOR_MUTED = RGBColor(113, 128, 150)
COLOR_RED = RGBColor(197, 48, 48)

def set_cell_background(cell, hex_color):
    shading_xml = f'<w:shd {nsdecls("w")} w:val="clear" w:color="auto" w:fill="{hex_color}"/>'
    cell._tc.get_or_add_tcPr().append(parse_xml(shading_xml))

def set_cell_margins(cell, top=100, bottom=100, left=140, right=140):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('w:top', top), ('w:bottom', bottom), ('w:left', left), ('w:right', right)]:
        node = OxmlElement(m)
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def set_table_borders(table, hex_color=HEX_BORDER):
    tblPr = table._tbl.tblPr
    borders_xml = f'''
    <w:tblBorders {nsdecls("w")}>
        <w:top w:val="single" w:sz="6" w:space="0" w:color="{hex_color}"/>
        <w:bottom w:val="single" w:sz="6" w:space="0" w:color="{hex_color}"/>
        <w:left w:val="none"/>
        <w:right w:val="none"/>
        <w:insideH w:val="single" w:sz="4" w:space="0" w:color="{hex_color}"/>
        <w:insideV w:val="none"/>
    </w:tblBorders>
    '''
    tblPr.append(parse_xml(borders_xml))

def add_header_p(doc, text, level=1):
    p = doc.add_paragraph()
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.bold = True
    if level == 1:
        p.paragraph_format.space_before = Pt(18)
        p.paragraph_format.space_after = Pt(6)
        run.font.size = Pt(14)
        run.font.color.rgb = COLOR_PRIMARY
    elif level == 2:
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(4)
        run.font.size = Pt(12)
        run.font.color.rgb = COLOR_SECONDARY
    elif level == 3:
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(2)
        run.font.size = Pt(10.5)
        run.font.color.rgb = COLOR_DARK
    return p

def add_body_p(doc, text, bold_prefix="", italic=False):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.15
    if bold_prefix:
        r_bold = p.add_run(bold_prefix + " ")
        r_bold.bold = True
        r_bold.font.color.rgb = COLOR_DARK
        r_bold.font.size = Pt(10)
    run = p.add_run(text)
    run.font.size = Pt(10)
    run.font.color.rgb = COLOR_DARK
    run.italic = italic
    return p

def add_callout(doc, text, title="LƯU Ý QUAN TRỌNG", is_alert=False):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    cell = table.cell(0, 0)
    cell.width = Inches(6.5)
    bg = HEX_ALERT_BG if is_alert else HEX_HEADER_BG
    border = HEX_ALERT_BORDER if is_alert else HEX_SECONDARY
    set_cell_background(cell, bg)
    set_cell_margins(cell, top=120, bottom=120, left=160, right=160)
    
    tcPr = cell._tc.get_or_add_tcPr()
    b_xml = f'<w:tcBorders {nsdecls("w")}><w:left w:val="single" w:sz="24" w:space="0" w:color="{border}"/><w:top w:val="none"/><w:right w:val="none"/><w:bottom w:val="none"/></w:tcBorders>'
    tcPr.append(parse_xml(b_xml))

    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    r_title = p.add_run(title + "\n")
    r_title.bold = True
    r_title.font.size = Pt(10)
    r_title.font.color.rgb = COLOR_RED if is_alert else COLOR_SECONDARY
    
    r_body = p.add_run(text)
    r_body.font.size = Pt(9.5)
    r_body.font.color.rgb = COLOR_DARK

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

def build_full_spec_doc():
    doc = Document()
    for s in doc.sections:
        s.top_margin = Inches(1.0)
        s.bottom_margin = Inches(1.0)
        s.left_margin = Inches(1.0)
        s.right_margin = Inches(1.0)

    # ==========================================
    # TRANG BÌA
    # ==========================================
    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(36)
    p_title.paragraph_format.space_after = Pt(8)
    r_title = p_title.add_run("ĐẶC TẢ CHUYỂN ĐỘNG TỰ NHIÊN CHO AVATAR BÁC SĨ MEDGUARD")
    r_title.bold = True
    r_title.font.size = Pt(22)
    r_title.font.color.rgb = COLOR_PRIMARY

    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_after = Pt(16)
    r_sub = p_sub.add_run("Kiến trúc Unity C# Thuần Túy, Bộ Phân Tích Bối Cảnh Lâm Sàng & Thư Viện 64 Cử Chỉ Hội Thoại")
    r_sub.font.size = Pt(13)
    r_sub.font.color.rgb = COLOR_SECONDARY

    p_meta = doc.add_paragraph()
    p_meta.paragraph_format.space_after = Pt(24)
    r_meta = p_meta.add_run("Phiên bản 3.0  |  Ngày 09 tháng 10 năm 2026\nĐội ngũ Kỹ thuật & Quản trị Chất lượng Lâm sàng MedGuard AI")
    r_meta.font.size = Pt(10)
    r_meta.font.color.rgb = COLOR_MUTED

    add_body_p(doc, 
        "Tài liệu này xác lập đặc tả kỹ thuật toàn diện cho việc xây dựng hệ sinh thái Avatar 3D Bác sĩ lâm sàng MedGuard "
        "dựa trên nền tảng Unity C# thuần túy (Native Architecture). Phiên bản 3.0 tập trung giải quyết triệt để vấn đề "
        "chuyển động cứng ngắc, loại bỏ sự pha trộn phức tạp giữa Three.js và C#, thiết lập cơ chế phân tích bối cảnh lâm sàng "
        "(Clinical Context Analysis) nhận diện chính xác các trường hợp phủ định, giả định, đối tượng thứ ba và mức độ khẩn cấp, "
        "đồng thời ban hành thư viện chuẩn mực gồm 32 nhóm hành động với 64 biến thể cử chỉ có điều kiện kích hoạt và điều kiện cấm khắt khe.")

    add_callout(doc,
        "1. Unity C# là nơi DUY NHẤT nắm toàn quyền điều khiển Skeleton, Animation Layers, IK, Lip-Sync và Social Gaze.\n"
        "2. Không thực hiện cử chỉ máy móc chỉ dựa vào từ khóa; hành động phải tuân thủ ngữ nghĩa lâm sàng thực tế.\n"
        "3. Tuyệt đối CẤM nụ cười khi cảnh báo cấp cứu, CẤM gật đầu đồng thuận khi người dùng kể triệu chứng đe dọa tính mạng, "
        "và CẤM làm cử chỉ khám bệnh giả định khi không có đạo cụ 3D kiểm chứng.",
        title="NGUYÊN TẮC BẤT BIẾN CỐT LÕI (CORE INVARIANTS)",
        is_alert=True)

    doc.add_page_break()

    # ==========================================
    # CHƯƠNG 1: CÁC ĐIỂM SỬA ĐỔI CỐT LÕI
    # ==========================================
    add_header_p(doc, "1. Các điểm sửa đổi cốt lõi so với đặc tả trước", level=1)
    add_body_p(doc, 
        "Quá trình triển khai thực tế trên bản v2 cho thấy việc cố gắng ghép nối nửa vời giữa renderer Three.js trên Web "
        "và logic C# dẫn đến xung đột luồng dữ liệu, độ trễ không ổn định và cử chỉ giật cục khi người dùng ngắt lời. "
        "Bảng dưới đây tổng hợp các điểm sửa đổi mang tính kiến trúc để chuyển đổi hoàn toàn sang Unity C# Native:")

    tbl_fixes = doc.add_table(rows=1, cols=3)
    tbl_fixes.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_fixes.autofit = False
    set_table_borders(tbl_fixes)
    
    headers_fix = ["Điểm đặc tả cũ (v1/v2)", "Vấn đề kỹ thuật thực tế", "Giải pháp chuẩn hóa v3.0 (Unity C#)"]
    widths_fix = [Inches(1.8), Inches(2.2), Inches(2.5)]
    for i, title in enumerate(headers_fix):
        cell = tbl_fixes.cell(0, i)
        cell.width = widths_fix[i]
        set_cell_background(cell, HEX_HEADER_BG)
        set_cell_margins(cell)
        p = cell.paragraphs[0]
        r = p.add_run(title)
        r.bold = True
        r.font.size = Pt(9.5)
        r.font.color.rgb = COLOR_PRIMARY

    fix_rows = [
        ("Trộn lẫn Three.js và C#", "Tranh chấp luồng render trên browser, thiếu công cụ IK/Inertialization chuyên sâu", "Chuyển hẳn sang Unity C# Standalone/WebGL Player; Unity quản lý toàn bộ rig và motion pipeline"),
        ("Đọc JSON và sửa Transform ngay", "Xung đột trực tiếp với Animator và UniVRM, gây biến dạng xương (clipping)", "Kiến trúc decoupled: Network Receiver chỉ tạo Cue DTO; Pose được cập nhật theo pipeline frame có chủ sở hữu"),
        ("Singleton cho Intent", "Trạng thái toàn cục khiến khó hỗ trợ song song hai bác sĩ hoặc test tự động", "DoctorMotionController theo từng avatar instance; sử dụng State Machine và Event-driven"),
        ("Cộng breathVal mỗi frame", "Gây hiện tượng drift tích lũy, ngực bị biến dạng to dần qua thời gian", "Lấy pose nền của frame hiện tại, áp offset nhịp thở độc lập; tích phân pha liên tục: breath = A * sin(phase)"),
        ("Perlin Noise cho toàn bộ mắt", "Tạo cảm giác mắt đảo liên tục vô hồn, thiếu giao tiếp xã hội", "Tách riêng Fixation (nhìn cố định), Saccade (chuyển hướng 150ms), Blinking và Head follow"),
        ("Cấm cập nhật hai tay cùng lúc", "Sai giải phẫu thực tế; bác sĩ thường cử động phối hợp cả hai tay", "Cả hai tay evaluate độc lập mỗi frame; lệch pha thời điểm khởi động và biên độ tự nhiên"),
        ("Queue chỉ lưu Intent đơn giản", "Thiếu speechId, timestamp, độ ưu tiên và khả năng hủy khi ngắt lời", "Hàng đợi Cue Buffer có gắn thế hệ generationId, audio timing và cơ chế xóa nhanh khi user ngắt lời"),
        ("Kích hoạt cử chỉ theo từ khóa", "Dễ bắt nhầm câu phủ định ('không khó thở') thành cử chỉ cấp cứu", "Bổ sung DoctorContextAnalyzer phân biệt phủ định, giả định, người thân trước khi chọn cử chỉ")
    ]

    for r_idx, row_data in enumerate(fix_rows):
        row = tbl_fixes.add_row()
        bg = HEX_LIGHT_ROW if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, text in enumerate(row_data):
            cell = row.cells[c_idx]
            cell.width = widths_fix[c_idx]
            set_cell_background(cell, bg)
            set_cell_margins(cell)
            p = cell.paragraphs[0]
            r = p.add_run(text)
            r.font.size = Pt(9)
            r.font.color.rgb = COLOR_DARK

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # ==========================================
    # CHƯƠNG 2: CƠ CHẾ GAME VÀ KHẢ NĂNG ỨNG DỤNG Y TẾ
    # ==========================================
    add_header_p(doc, "2. Cơ chế công nghệ Game AAA và ứng dụng Avatar Y tế", level=1)
    add_body_p(doc, 
        "Hệ thống chuyển động avatar bác sĩ không được thiết kế bằng cách cộng các góc quay ngẫu nhiên. "
        "MedGuard áp dụng các chuẩn mực công nghệ đã được chứng minh trong ngành công nghiệp game AAA:")
    
    add_body_p(doc, 
        "1. Motion Capture (Mocap) & Cleaned Retargeting: Mọi clip nền tảng phải xuất phát từ dữ liệu diễn viên đóng thế "
        "đã được làm sạch jitter, giải quyết đúng tỷ lệ xương của model VRM bác sĩ.\n"
        "2. Semantic Gesture Planning vs Motion Matching: Đối với avatar hội thoại tại chỗ (đứng/ngồi trước camera), "
        "Motion Matching chỉ cần thiết khi avatar di chuyển không gian. Với giao tiếp tư vấn y tế, cơ chế lập kế hoạch ngữ nghĩa "
        "(Semantic Gesture Planning) theo âm thanh mang lại độ chính xác lâm sàng và biểu cảm vượt trội.\n"
        "3. Inertialization (Làm mượt giữ quán tính): Khi bệnh nhân ngắt lời giữa chừng (Barge-in), hệ thống không cắt cụt hoạt ảnh. "
        "Bộ lọc quán tính C2 suy giảm độ lệch vị trí và vận tốc trong 0.3 giây, đưa cánh tay về trạng thái lắng nghe một cách tự nhiên.\n"
        "4. Layered Animation & Body Masking: Tách biệt Layer 0 (Tư thế đứng/ngồi), Layer 1 (Cử chỉ thân trên có Mask), "
        "và Layer 2 (Additive Breathing nở ngực sinh học).\n"
        "5. Two-Bone IK & Anatomical Limiters: Giới hạn tầm với của cánh tay và ngăn khuỷu tay giơ cao quá vai khi chào hỏi.")

    # ==========================================
    # CHƯƠNG 3: CHUẨN HÓA MODEL & AVATARPROFILE
    # ==========================================
    add_header_p(doc, "3. Chuẩn hóa Model & Hồ sơ nhân vật (AvatarProfile)", level=1)
    add_body_p(doc, "Hệ thống hỗ trợ chuẩn hóa hai nhân vật lâm sàng với cấu hình AvatarProfile độc lập:")
    
    add_body_p(doc, "AvatarProfile Bác sĩ Tuấn (Nam - dr_tuan):", bold_prefix="•")
    add_body_p(doc, 
        "Model: DoctorTuan.vrm. Rig: Humanoid tiêu chuẩn (55 bones). Chiều cao: 1.76m. "
        "Giọng đọc: vi-VN-NamMinhNeural (rate: -8%, pitch: -6Hz). Phong thái: Trầm ổn, đĩnh đạc, cử chỉ dứt khoát, độ mở cánh tay 15-30 độ.")
    
    add_body_p(doc, "AvatarProfile Bác sĩ Mai (Nữ - dr_mai):", bold_prefix="•")
    add_body_p(doc, 
        "Model: DoctorMai.vrm. Rig: Humanoid tiêu chuẩn (55 bones). Chiều cao: 1.63m. "
        "Giọng đọc: vi-VN-HoaiMyNeural (rate: -7%, pitch: -12Hz). Phong thái: Dịu dàng, thấu cảm sâu sắc, cử chỉ mềm mại, góc nghiêng đầu 2-4 độ.")

    # ==========================================
    # CHƯƠNG 4: PIPELINE POSE VÀ QUYỀN ĐIỀU KHIỂN XƯƠNG
    # ==========================================
    add_header_p(doc, "4. Pipeline Pose & Trật tự thực thi (Execution Pipeline)", level=1)
    add_body_p(doc, "Để triệt tiêu hiện tượng tranh chấp quyền điều khiển xương giữa Animator, IK và script C#, thứ tự frame được cố định:")

    add_callout(doc,
        "Thứ tự thực thi trong mỗi Frame Unity:\n"
        "1. Update() -> Nhận Cue DTO từ hàng đợi mạng, phân tích âm thanh RMS, cập nhật trạng thái GesturePlanner.\n"
        "2. Animator Evaluation -> Unity Animator chạy các Clip nền (Layer 0, Layer 1).\n"
        "3. ApplyPoseModifiers() -> Áp dụng lớp nhịp thở Additive Breathing vào Chest Bone.\n"
        "4. OnAnimatorIK() -> TwoBoneIK giải quyết vị trí bàn tay, áp dụng DoctorIKLimiter kẹp góc giải phẫu.\n"
        "5. LateUpdate() -> DoctorEyeGazeController xoay xương cổ/đầu và áp dụng BlendShape mắt/môi. Khóa pose cuối cùng trước khi Render.",
        title="TRẬT TỰ THỰC THI CHUẨN TRÊN TỪNG FRAME")

    # ==========================================
    # CHƯƠNG 5: PHÂN TÍCH BỐI CẢNH CÂU HỎI LÂM SÀNG (MỚI)
    # ==========================================
    add_header_p(doc, "5. Phân tích bối cảnh câu hỏi lâm sàng (Clinical Context Analysis)", level=1)
    add_body_p(doc, 
        "Điểm đột phá của phiên bản 3.0 là bộ phân tích bối cảnh lâm sàng (DoctorContextAnalyzer.cs). "
        "Thay vì kích hoạt hoạt ảnh máy móc theo từ khóa (keyword matching), avatar đánh giá 4 trục ngữ nghĩa:")

    add_body_p(doc, "1. Nhận diện phủ định triệu chứng (Negation Detection):", bold_prefix="Trục 1:")
    add_body_p(doc, 
        "Khi bệnh nhân nói 'tôi không khó thở, không đau ngực', hệ thống nhận diện từ phủ định ('không', 'chưa', 'chẳng') "
        "và KHÔNG kích hoạt biểu cảm cấp cứu đỏ. Thay vào đó, avatar thực hiện cử chỉ NEGATION_SUBTLE_NOD (gật đầu nhẹ chậm) "
        "để xác nhận đã ghi nhận thông tin loại trừ an toàn.")

    add_body_p(doc, "2. Nhận diện câu hỏi giả định (Hypothetical Queries):", bold_prefix="Trục 2:")
    add_body_p(doc, 
        "Khi người dùng hỏi tình huống lý thuyết ('Nếu lỡ uống nhầm 2 viên thuốc thì sao?'), câu hỏi chứa từ giả định "
        "('nếu', 'giả sử', 'liệu có'). Avatar KHÔNG kích hoạt hoảng loạn cấp cứu mà giữ thái độ khoa học khách quan "
        "(HYPO_HEAD_TILT_ENGAGE), nghiêng đầu nhẹ giải thích cơ chế dược lý.")

    add_body_p(doc, "3. Nhận diện đối tượng thứ ba (Third-Person Context):", bold_prefix="Trục 3:")
    add_body_p(doc, 
        "Khi câu hỏi hướng về người thân ('Mẹ tôi 80 tuổi bị sốt mê man'), avatar nhận diện chủ thể là bên thứ ba. "
        "Bác sĩ chuyển hướng giao tiếp tôn trọng, hỏi thêm tuổi tác và tiền sử người bệnh vắng mặt, không quy kết triệu chứng trực tiếp lên người hỏi.")

    add_body_p(doc, "4. Phân tầng mức độ khẩn cấp (Emergency vs Urgent vs Routine):", bold_prefix="Trục 4:")
    add_body_p(doc, 
        "• Emergency: Cảnh báo đỏ đe dọa tính mạng (đau ngực đè nặng, đột quỵ FAST, co giật). Avatar lập tức nghiêm nghị tuyệt đối, giơ tay chặn dứt khoát.\n"
        "• Urgent: Cần xử trí trong ngày (chảy máu chân răng cấp, đau ruột thừa). Cử chỉ tập trung cao độ, hướng dẫn sơ cứu ép gạc.\n"
        "• Routine: Bệnh mãn tính, chăm sóc da, tư vấn dùng thuốc. Cử chỉ cởi mở, ấm áp, nhịp nhàng.")

    add_callout(doc,
        "MA TRẬN ĐIỀU KIỆN CẤM KỴ THỰC TIỄN Y KHOA (CLINICAL INVARIANTS):\n"
        "1. CẤM cười, nháy mắt, hoặc gật đầu thoải mái khi phát hiện Red Flag cấp cứu.\n"
        "2. CẤM chỉ một ngón trỏ vào người bệnh (Finger pointing thô lỗ).\n"
        "3. CẤM chỉ tay vào khoảng không gian vô định (Pointing into empty void).\n"
        "4. CẤM làm cử chỉ khám bệnh giả định (nghe tim, bắt mạch) khi không có đạo cụ 3D thật.\n"
        "5. Khi độ tin cậy bối cảnh < 0.6: Bắt buộc giữ tư thế Lắng nghe trung tính (LISTEN_NEUTRAL_STILL).",
        title="ĐIỀU KIỆN CẤM KỴ LÂM SÀNG TUYỆT ĐỐI",
        is_alert=True)

    # ==========================================
    # CHƯƠNG 6: THƯ VIỆN 32 NHÓM & 64 BIẾN THỂ CỬ CHỈ
    # ==========================================
    doc.add_page_break()
    add_header_p(doc, "6. Thư viện 32 nhóm hành động & 64 biến thể cử chỉ chi tiết", level=1)
    add_body_p(doc, 
        "Thư viện chuyển động v3.0 được mở rộng thành 32 nhóm hành động với 64 biến thể độc lập. "
        "Mỗi biến thể có quy định chi tiết về chuyển động tay/thân, biểu cảm mặt/mắt, thời lượng chuẩn, điều kiện kích hoạt và điều kiện cấm:")

    tbl_actions = doc.add_table(rows=1, cols=6)
    tbl_actions.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_actions.autofit = False
    set_table_borders(tbl_actions)

    act_headers = ["Nhóm & Mã", "Tên biến thể", "Mục đích lâm sàng", "Chuyển động Thân & Tay", "Biểu cảm & Mắt", "Ràng buộc & Cấm"]
    act_widths = [Inches(1.2), Inches(1.1), Inches(1.2), Inches(1.3), Inches(1.1), Inches(1.1)]
    for i, title in enumerate(act_headers):
        cell = tbl_actions.cell(0, i)
        cell.width = act_widths[i]
        set_cell_background(cell, HEX_HEADER_BG)
        set_cell_margins(cell)
        p = cell.paragraphs[0]
        r = p.add_run(title)
        r.bold = True
        r.font.size = Pt(8.5)
        r.font.color.rgb = COLOR_PRIMARY

    row_count = 0
    for grp in ACTION_CATALOG:
        for var in grp["variants"]:
            row = tbl_actions.add_row()
            bg = HEX_LIGHT_ROW if row_count % 2 == 1 else "FFFFFF"
            row_count += 1
            
            c0 = row.cells[0]
            c0.width = act_widths[0]
            set_cell_background(c0, bg)
            set_cell_margins(c0)
            p0 = c0.paragraphs[0]
            r0 = p0.add_run(f"{grp['group_name']}\n[{var['id']}]")
            r0.bold = True
            r0.font.size = Pt(8)
            r0.font.color.rgb = COLOR_PRIMARY

            c1 = row.cells[1]
            c1.width = act_widths[1]
            set_cell_background(c1, bg)
            set_cell_margins(c1)
            p1 = c1.paragraphs[0]
            r1 = p1.add_run(var['name'])
            r1.font.size = Pt(8)

            c2 = row.cells[2]
            c2.width = act_widths[2]
            set_cell_background(c2, bg)
            set_cell_margins(c2)
            p2 = c2.paragraphs[0]
            r2 = p2.add_run(var['purpose'])
            r2.font.size = Pt(8)

            c3 = row.cells[3]
            c3.width = act_widths[3]
            set_cell_background(c3, bg)
            set_cell_margins(c3)
            p3 = c3.paragraphs[0]
            r3 = p3.add_run(f"{var['body_hand']}\n({var['duration_sec']}s)")
            r3.font.size = Pt(8)

            c4 = row.cells[4]
            c4.width = act_widths[4]
            set_cell_background(c4, bg)
            set_cell_margins(c4)
            p4 = c4.paragraphs[0]
            r4 = p4.add_run(var['facial_eye'])
            r4.font.size = Pt(8)

            c5 = row.cells[5]
            c5.width = act_widths[5]
            set_cell_background(c5, bg)
            set_cell_margins(c5)
            p5 = c5.paragraphs[0]
            r5 = p5.add_run(f"DÙNG: {var['preconditions']}\nCẤM: {var['prohibitions']}")
            r5.font.size = Pt(7.5)
            r5.font.color.rgb = COLOR_DARK

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # ==========================================
    # CHƯƠNG 7: LẬP KẾ HOẠCH CỬ CHỈ & 4 PHA CHUYỂN ĐỘNG
    # ==========================================
    add_header_p(doc, "7. Lập kế hoạch cử chỉ & 4 pha chuyển động (Gesture Phases)", level=1)
    add_body_p(doc, "Mỗi cử chỉ hội thoại trong MedGuard được cấu tạo từ 4 pha động học chặt chẽ:")
    add_body_p(doc, "1. Preparation (Chuẩn bị, 15-20% thời lượng): Cánh tay rời tư thế nghỉ, tăng tốc mượt hướng về mục tiêu.", bold_prefix="•")
    add_body_p(doc, "2. Stroke (Nhấn âm, 45-50% thời lượng): Điểm rơi năng lượng của cử chỉ, đồng bộ chính xác với đỉnh năng lượng âm thanh.", bold_prefix="•")
    add_body_p(doc, "3. Hold (Giữ ý nghĩa, 15-20% thời lượng): Tay dừng ở vị trí có ý nghĩa để bệnh nhân tiếp nhận thông điệp.", bold_prefix="•")
    add_body_p(doc, "4. Retraction (Thu hồi, 20% thời lượng): Tay giảm tốc mềm mại trở về vị trí nghỉ hoặc nối sang cử chỉ kế tiếp.", bold_prefix="•")

    # ==========================================
    # CHƯƠNG 8: GIAO THỨC VÀ XỬ LÝ NGẮT LỜI (BARGE-IN)
    # ==========================================
    add_header_p(doc, "8. Giao thức thời gian thực & Xử lý ngắt lời (Barge-in)", level=1)
    add_body_p(doc, 
        "Khi bệnh nhân nói chen ngang trong lúc bác sĩ đang trả lời, hệ thống thực thi quy trình ngắt lời mượt mà (Inertial Handoff):\n"
        "1. Dừng phát âm thanh TTS ngay lập tức.\n"
        "2. Bộ tạo khẩu hình ngậm miệng tự nhiên trong 60ms.\n"
        "3. Tay đang vung dở lập tức kích hoạt bộ lọc quán tính DoctorInertialBlender, đưa tay về vị trí nghỉ trong 0.3s không giật khựng.\n"
        "4. Ánh mắt lập tức chuyển hướng nhìn thẳng vào camera lắng nghe câu hỏi mới của bệnh nhân.")

    # ==========================================
    # CHƯƠNG 9: CHI TIẾT CHUYỂN ĐỘNG THÂN, CÁNH TAY VÀ NGÓN
    # ==========================================
    add_header_p(doc, "9. Chi tiết chuyển động Thân, Cánh tay và Ngón tay", level=1)
    add_body_p(doc, 
        "• Quỹ đạo vòng cung (Arc Trajectory): Tay người không bao giờ di chuyển theo đường thẳng. Tất cả vị trí được nội suy cung tròn tự nhiên.\n"
        "• Chào tự nhiên: Góc khuỷu tay dưới vai (<45 độ), cẳng tay mở góc 60 độ, không giơ thẳng đứng kiểu robot.\n"
        "• Khớp ngón tay: Mỗi ngón tay có độ cong (curl) và độ mở (splay) độc lập. Không gập cả bàn tay như mái chèo.")

    # ==========================================
    # CHƯƠNG 10: MẮT, KHUÔN MẶT, KHẨU HÌNH TIẾNG VIỆT
    # ==========================================
    add_header_p(doc, "10. Mắt, Khuôn mặt, Khẩu hình tiếng Việt & Nhịp thở", level=1)
    add_body_p(doc, 
        "• Saccade & Fixation: Ánh mắt dừng ở vùng mắt-mũi từ 1.5 - 3.5 giây, sau đó chuyển động saccade nhẹ 150-300ms.\n"
        "• Khẩu hình tiếng Việt: Khớp năng lượng RMS thành 5 Viseme cơ bản (Aa, Ih, Ou, Ee, Oh) và phụ âm môi (M, B, P).\n"
        "• Nhịp thở sinh học: Ngực phập phồng nhẹ nhàng chu kỳ 4 giây (15 nhịp/phút) với biên độ 1.5cm.")

    # ==========================================
    # CHƯƠNG 11: 32 TÌNH HUỐNG KIỂM THỬ BỐI CẢNH LÂM SÀNG
    # ==========================================
    doc.add_page_break()
    add_header_p(doc, "11. Bộ 32 tình huống kiểm thử bối cảnh lâm sàng (Context Test Scenarios)", level=1)
    add_body_p(doc, "Bảng kiểm tra tự động 32 kịch bản lâm sàng thực tế, kiểm soát toàn bộ trường hợp biên và điều kiện cấm:")

    tbl_tests = doc.add_table(rows=1, cols=5)
    tbl_tests.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_tests.autofit = False
    set_table_borders(tbl_tests)

    test_headers = ["Mã test", "Câu hỏi người dùng", "Bối cảnh phân tích", "Biến thể kỳ vọng", "Tiêu chí nghiệm thu"]
    test_widths = [Inches(1.0), Inches(1.8), Inches(1.2), Inches(1.2), Inches(1.8)]
    for i, title in enumerate(test_headers):
        cell = tbl_tests.cell(0, i)
        cell.width = test_widths[i]
        set_cell_background(cell, HEX_HEADER_BG)
        set_cell_margins(cell)
        p = cell.paragraphs[0]
        r = p.add_run(title)
        r.bold = True
        r.font.size = Pt(8.5)
        r.font.color.rgb = COLOR_PRIMARY

    for t_idx, tc in enumerate(TEST_SCENARIOS):
        row = tbl_tests.add_row()
        bg = HEX_LIGHT_ROW if t_idx % 2 == 1 else "FFFFFF"
        
        c0 = row.cells[0]
        c0.width = test_widths[0]
        set_cell_background(c0, bg)
        set_cell_margins(c0)
        p0 = c0.paragraphs[0]
        r0 = p0.add_run(tc['id'])
        r0.bold = True
        r0.font.size = Pt(8)

        c1 = row.cells[1]
        c1.width = test_widths[1]
        set_cell_background(c1, bg)
        set_cell_margins(c1)
        p1 = c1.paragraphs[0]
        r1 = p1.add_run(tc['user_query'])
        r1.font.size = Pt(8)

        c2 = row.cells[2]
        c2.width = test_widths[2]
        set_cell_background(c2, bg)
        set_cell_margins(c2)
        p2 = c2.paragraphs[0]
        r2 = p2.add_run(f"Intent: {tc['detected_intent']}\nFlags: {json.dumps(tc['context_flags'], ensure_ascii=False)}")
        r2.font.size = Pt(7.5)

        c3 = row.cells[3]
        c3.width = test_widths[3]
        set_cell_background(c3, bg)
        set_cell_margins(c3)
        p3 = c3.paragraphs[0]
        r3 = p3.add_run(tc['expected_variant'])
        r3.bold = True
        r3.font.size = Pt(8)
        r3.font.color.rgb = COLOR_PRIMARY

        c4 = row.cells[4]
        c4.width = test_widths[4]
        set_cell_background(c4, bg)
        set_cell_margins(c4)
        p4 = c4.paragraphs[0]
        r4 = p4.add_run(tc['acceptance_criteria'])
        r4.font.size = Pt(8)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # ==========================================
    # CHƯƠNG 12: NGÂN SÁCH HIỆU NĂNG
    # ==========================================
    add_header_p(doc, "12. Ngân sách hiệu năng & Tối ưu hóa (Performance Budget)", level=1)
    add_body_p(doc, 
        "• Tốc độ khung hình mục tiêu: 60 FPS ổn định trên thiết bị tiêu chuẩn (Frame budget: 16.6ms).\n"
        "• Thời gian tính toán CPU cho toàn bộ Motion Pipeline: < 2.5ms mỗi frame.\n"
        "• Draw Calls: < 40 draw calls cho toàn bộ Avatar và phòng khám 3D.\n"
        "• Dung lượng bộ nhớ: RAM heap runtime < 180MB, Texture VRAM < 250MB.")

    # ==========================================
    # CHƯƠNG 13: TIÊU CHÍ NGHIỆM THU
    # ==========================================
    add_header_p(doc, "13. Tiêu chí nghiệm thu (Acceptance Criteria)", level=1)
    add_body_p(doc, 
        "1. Vượt qua 100% 32 ca kiểm thử bối cảnh lâm sàng trong DoctorContextScenarios.cs.\n"
        "2. Không có bất kỳ frame pop (khựng hình) nào vượt quá 8 độ/frame khi ngắt lời.\n"
        "3. Tuyệt đối không vi phạm ma trận cấm kỵ (không cười trong ca cấp cứu, không chỉ vào hư không).\n"
        "4. Độ trễ từ khi nhận audio chunk đầu tiên đến khi phát sinh khẩu hình < 80ms.")

    # ==========================================
    # CHƯƠNG 14: HƯỚNG DẪN TÍCH HỢP MÃ C#
    # ==========================================
    add_header_p(doc, "14. Hướng dẫn tích hợp mã nguồn C# tham chiếu", level=1)
    add_body_p(doc, 
        "Gói mã nguồn tham chiếu MedGuard_Unity_CSharp_Reference_v3.zip đã được cấu hình sẵn theo chuẩn Unity Package Manager:\n"
        "1. Giải nén vào thư mục Assets/MedGuard/ hoặc import qua Package Manager.\n"
        "2. Kéo Prefab nhân vật bác sĩ vào Scene.\n"
        "3. Gắn DoctorMotionController lên GameObject gốc và liên kết các xương ngực, đầu, mắt.\n"
        "4. Chạy DoctorContextScenarios.RunAllTests() để xác nhận toàn bộ logic bối cảnh.")

    # ==========================================
    # CHƯƠNG 15: TÀI LIỆU THAM KHẢO
    # ==========================================
    add_header_p(doc, "15. Nguồn tài liệu kỹ thuật chuẩn quốc tế", level=1)
    add_body_p(doc, 
        "[S01] Ubisoft Motion Matching Technical Architecture (GDC 2016).\n"
        "[S02] Bollo. Inertialization: High-Performance Animation Transitions (GDC 2018).\n"
        "[S03] UniVRM Specification & Humanoid Rig Best Practices.\n"
        "[S04] Cassell, J. NVC: Nonverbal Communication and Embodied Conversational Agents (MIT Press).\n"
        "[S05] American Medical Association (AMA) Communication Standards in Clinical Encounters.")

    # Lưu file
    doc.save(OUTPUT_DOCX_LOCAL)
    shutil.copy2(OUTPUT_DOCX_LOCAL, OUTPUT_DOCX_DOWNLOADS)
    print(f"-> Đã tạo tài liệu Word thành công tại: {OUTPUT_DOCX_LOCAL}")
    print(f"-> Đã sao chép vào: {OUTPUT_DOCX_DOWNLOADS}")

if __name__ == "__main__":
    build_full_spec_doc()
