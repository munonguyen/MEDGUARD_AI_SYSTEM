#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trình tạo Báo cáo Tiến độ Đề tài Giữa kỳ chuẩn mực học thuật:
- Tên đề tài, Danh sách thành viên
- Overview
- Problems and Objectives
- Technical Approaches & Trade-offs
- System Design (kèm hình ảnh System Architecture, Data Flow, Inference Flowchart)
- Development Plan (Bảng kế hoạch 15 tuần)
- Progress (Tiến độ thực tế, kết quả kiểm định)
- AI Disclosure (Minh bạch phần việc Con người vs AI)
"""

import os
import shutil
from pathlib import Path
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

OUTPUT_DOCX_DOCS = Path("/Users/munonguyen/Project ATI/docs/BAO_CAO_TIEN_DO_GIUA_KY_MEDGUARD_AI.docx")
OUTPUT_DOCX_DOWNLOADS = Path("/Users/munonguyen/Downloads/BAO_CAO_TIEN_DO_GIUA_KY_MEDGUARD_AI.docx")

IMG_SYS_ARCH = Path("/Users/munonguyen/Project ATI/scratch/diagrams/system_architecture.png")
IMG_DATA_FLOW = Path("/Users/munonguyen/Project ATI/scratch/diagrams/data_flow_diagram.png")
IMG_INFERENCE = Path("/Users/munonguyen/Project ATI/scratch/diagrams/inference_flowchart.png")

# Màu sắc
HEX_PRIMARY = "1B365D"       # Deep Navy
HEX_SECONDARY = "008080"     # Medical Teal
HEX_HEADER_BG = "EDF2F7"     # Light Slate Header
HEX_LIGHT_ROW = "F7FAFC"     # Zebra row
HEX_BORDER = "CBD5E0"        # Border
HEX_ALERT_BG = "FFF5F5"
HEX_ALERT_BORDER = "E53E3E"

COLOR_PRIMARY = RGBColor(27, 54, 93)
COLOR_SECONDARY = RGBColor(0, 128, 128)
COLOR_DARK = RGBColor(45, 55, 72)
COLOR_MUTED = RGBColor(113, 128, 150)
COLOR_RED = RGBColor(197, 48, 48)

def set_cell_background(cell, hex_color):
    shd = f'<w:shd {nsdecls("w")} w:val="clear" w:color="auto" w:fill="{hex_color}"/>'
    cell._tc.get_or_add_tcPr().append(parse_xml(shd))

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

def add_callout(doc, text, title="THÔNG ĐIỆP CHỈ ĐẠO", is_alert=False):
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

def add_image_figure(doc, img_path: Path, caption: str, width_inches=6.2):
    if not img_path.exists():
        add_body_p(doc, f"[Không tìm thấy tệp hình ảnh tại {img_path}]", italic=True)
        return
    p_img = doc.add_paragraph()
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img.paragraph_format.space_before = Pt(8)
    p_img.paragraph_format.space_after = Pt(2)
    p_img.add_run().add_picture(str(img_path), width=Inches(width_inches))
    
    p_cap = doc.add_paragraph()
    p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cap.paragraph_format.space_after = Pt(8)
    r_cap = p_cap.add_run(caption)
    r_cap.font.size = Pt(9)
    r_cap.italic = True
    r_cap.font.color.rgb = COLOR_MUTED

def generate_midterm_report():
    doc = Document()
    for s in doc.sections:
        s.top_margin = Inches(1.0)
        s.bottom_margin = Inches(1.0)
        s.left_margin = Inches(1.0)
        s.right_margin = Inches(1.0)

    # ==========================================
    # TIÊU ĐỀ BÁO CÁO GIỮA KỲ
    # ==========================================
    p_top = doc.add_paragraph()
    p_top.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_top.paragraph_format.space_after = Pt(2)
    r_top = p_top.add_run("BÁO CÁO TIẾN ĐỘ THỰC HIỆN ĐỀ TÀI GIỮA KỲ")
    r_top.bold = True
    r_top.font.size = Pt(16)
    r_top.font.color.rgb = COLOR_PRIMARY

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_after = Pt(6)
    r_title = p_title.add_run("HỆ THỐNG AI Y TẾ ĐA TÁC NHÂN HỖ TRỢ PHÂN LUỒNG LÂM SÀNG, BÓC TÁCH ĐƠN THUỐC VÀ AN TOÀN SỬ DỤNG THUỐC (MEDGUARD AI)")
    r_title.bold = True
    r_title.font.size = Pt(13)
    r_title.font.color.rgb = COLOR_SECONDARY

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_after = Pt(14)
    r_sub = p_sub.add_run("Đánh giá Tiến độ Giai đoạn Giữa kỳ — Học kỳ 1, Năm học 2026")
    r_sub.italic = True
    r_sub.font.size = Pt(10)
    r_sub.font.color.rgb = COLOR_MUTED

    # ==========================================
    # PHẦN 1. THÔNG TIN ĐỀ TÀI & DANH SÁCH THÀNH VIÊN
    # ==========================================
    add_header_p(doc, "1. Thông Tin Đề Tài & Danh Sách Thành Viên", level=1)
    
    add_body_p(doc, "HỆ THỐNG AI Y TẾ ĐA TÁC NHÂN HỖ TRỢ PHÂN LUỒNG LÂM SÀNG, BÓC TÁCH ĐƠN THUỐC VÀ AN TOÀN SỬ DỤNG THUỐC", bold_prefix="• Tên đề tài tiếng Việt:")
    add_body_p(doc, "MedGuard AI: Multi-Agent Clinical Triage, Prescription OCR and Output-Governed Medication Safety System", bold_prefix="• Tên đề tài tiếng Anh:")
    add_body_p(doc, "MedGuard AI (Phiên bản kiến trúc độc lập v2.0 — Định hướng Candidate V11)", bold_prefix="• Tên mã phát triển (Codename):")
    add_body_p(doc, "Nền tảng Y tế Số BookingCare (BookingCare Web Platform)", bold_prefix="• Nền tảng tích hợp tham chiếu:")

    add_header_p(doc, "Danh sách thành viên và phân công trách nhiệm:", level=2)
    tbl_members = doc.add_table(rows=1, cols=5)
    tbl_members.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_members.autofit = False
    set_table_borders(tbl_members)
    
    mem_headers = ["Họ và Tên", "MSSV", "Vai trò trong Nhóm", "Nhiệm vụ & Module phụ trách chính", "Đóng góp"]
    mem_widths = [Inches(1.5), Inches(0.9), Inches(1.2), Inches(2.3), Inches(0.6)]
    for i, h in enumerate(mem_headers):
        cell = tbl_members.cell(0, i)
        cell.width = mem_widths[i]
        set_cell_background(cell, HEX_HEADER_BG)
        set_cell_margins(cell)
        p = cell.paragraphs[0]
        r = p.add_run(h)
        r.bold = True
        r.font.size = Pt(9)
        r.font.color.rgb = COLOR_PRIMARY

    member_data = [
        ("Nguyễn Mậu Nhật Nam (munonguyen)", "SV2026-01", "Nhóm trưởng / Tech Lead", 
         "Kiến trúc sư hệ thống; thiết kế Clinical Safety Floor, LiteLLM Gateway, Canonical Clinical State, Jev Decision Governance; API Gateway, PostgreSQL RLS; điều phối kiểm định Blind V8/V10.", "35%"),
        ("Lê Hoàng Long", "SV2026-02", "Frontend & Fullstack Engineer", 
         "Phát triển Clinical Workspace trên React 19 + Vite; thiết kế UX đàm thoại lâm sàng, camera quét mã QR/đơn thuốc, tích hợp Voice TTS bác sĩ (Edge TTS); viết bộ kiểm thử UI smoke test Playwright.", "25%"),
        ("Trần Thị Mai Anh", "SV2026-03", "Clinical Data & Knowledge Engineer", 
         "Chuẩn hóa Cơ sở tri thức Y tế (JSON Knowledge Base) theo Dược thư Quốc gia VN và ESI; thiết lập Response Obligation Graph, ma trận dị ứng chéo 7 nhóm, 10 cặp tương tác nguy hiểm; gán nhãn tập đối soát.", "20%"),
        ("Phạm Quốc Dũng", "SV2026-04", "AI Vision & Pipeline Engineer", 
         "Nghiên cứu và triển khai Pipeline bóc tách đơn thuốc OCR (PaddleOCR + VietOCR + LLM Normalizer); xây dựng Response Quality Verifier và bộ benchmark chất lượng câu trả lời 500 ca; quản lý hồi quy.", "20%")
    ]

    for idx, row in enumerate(member_data):
        r_node = tbl_members.add_row()
        bg = HEX_LIGHT_ROW if idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(row):
            c = r_node.cells[c_idx]
            c.width = mem_widths[c_idx]
            set_cell_background(c, bg)
            set_cell_margins(c)
            p = c.paragraphs[0]
            r = p.add_run(val)
            r.font.size = Pt(8.5)
            r.font.color.rgb = COLOR_DARK

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # ==========================================
    # PHẦN 2. OVERVIEW — TỔNG QUAN HỆ THỐNG
    # ==========================================
    add_header_p(doc, "2. Overview — Tổng Quan Hệ Thống", level=1)
    add_body_p(doc, 
        "Hệ thống MedGuard AI được xây dựng nhằm giải quyết 4 điểm nghẽn nghiêm trọng trong chăm sóc sức khỏe hiện đại:\n"
        "1. Phân luồng chậm trễ bỏ lỡ giờ vàng cấp cứu (Golden Hour in Medical Triage).\n"
        "2. Sai sót nguy hiểm khi bệnh nhân đọc và thực hiện đơn thuốc ngoại trú chữ viết tay.\n"
        "3. Nguy cơ xung đột dược lý vô hình (Drug-Drug Interactions - DDI, Chống chỉ định theo tiền sử bệnh, Dị ứng chéo thuốc).\n"
        "4. Đứt gãy tuân thủ điều trị sau khám (Post-consultation follow-up drop-off).")

    add_body_p(doc, 
        "Khác với các ứng dụng chatbot y tế thông thường sử dụng LLM tạo sinh trực tiếp (vốn tiềm ẩn nguy cơ ảo giác lâm sàng chết người), "
        "MedGuard AI là một hệ thống Agentic AI Y tế Độc lập tuân thủ triết lý 'Safety Before Generation' (An toàn đặt trước Tạo sinh). "
        "Hệ thống vận hành cơ chế kiểm soát 3 cổng độc lập (Tri-Gate Architecture), tách biệt giữa Tác nhân Nghiên cứu (Answer Agent) "
        "và Tác nhân Thẩm định độc lập (Verifier Agent), đồng thời kết hợp chặt chẽ cơ chế con người duyệt chặng cuối (Human-in-the-loop).")

    add_callout(doc,
        "5 ĐIỂM MẠNH KIẾN TRÚC CỐT LÕI ĐÃ XÂY DỰNG THÀNH CÔNG:\n"
        "1. Sàn An toàn Lâm sàng (Clinical Safety Floor): Bộ quy tắc tiền kiểm tra đảm bảo ca cấp cứu không phụ thuộc vào LLM.\n"
        "2. Thẩm định độc lập 2 tác nhân qua LiteLLM Gateway: Ngăn ngừa xung đột lợi ích giữa việc soạn thảo và duyệt câu trả lời.\n"
        "3. Con người duyệt chặng cuối (Human-in-the-loop): Mọi kết quả OCR đơn thuốc và kiểm tra an toàn đều gắn nhãn PENDING_REVIEW.\n"
        "4. Kiểm toán bất biến: Cơ sở tri thức y khoa gắn mã băm SHA-256, bảo mật phân tách tenant bằng PostgreSQL RLS.\n"
        "5. Tích hợp Avatar Bác sĩ 3D C# Native: Hỗ trợ phân tích bối cảnh lâm sàng sâu sắc, giao tiếp tự nhiên và an toàn.",
        title="5 TRỤ CỘT ĐỘT PHÁ CỦA MEDGUARD AI")

    # ==========================================
    # PHẦN 3. PROBLEMS AND OBJECTIVES
    # ==========================================
    add_header_p(doc, "3. Problems and Objectives — Vấn Đề & Mục Tiêu Nghiên Cứu", level=1)
    
    add_header_p(doc, "3.1 Những vấn đề cốt lõi cần giải quyết (Problems)", level=2)
    add_body_p(doc, "1. Ảo giác y khoa (Medical Hallucination) và Trấn an sai lầm (Unsafe False Reassurance):", bold_prefix="•")
    add_body_p(doc, "Các mô hình ngôn ngữ lớn (LLM) thuần túy thường có xu hướng trấn an nguy hại (ví dụ: 'Bạn đừng quá lo lắng, hãy nghỉ ngơi' khi bệnh nhân đang có dấu hiệu nhồi máu cơ tim), hoặc tự ý bịa đặt tên thuốc, liều lượng mà không có căn cứ dược thư.")

    add_body_p(doc, "2. Phân mảnh trạng thái lâm sàng (Fragmented Clinical State):", bold_prefix="•")
    add_body_p(doc, "Trong các hệ thống phân tán, các module khác nhau xử lý thông tin bệnh nhân theo các định dạng rời rạc: tầng phân luồng hiểu một kiểu, tầng dược lý hiểu kiểu khác, và tầng sinh lời thoại lại diễn giải theo cách thứ ba, dẫn đến mâu thuẫn câu trả lời đầu ra.")

    add_body_p(doc, "3. Thiếu đồ thị ràng buộc trách nhiệm nội dung (Lack of Response Obligations):", bold_prefix="•")
    add_body_p(doc, "Hệ thống truyền nhãn Triage xuống nhưng không có hợp đồng quy định những hành động bắt buộc phải có (ví dụ: gọi 115, đi khám ngay) và những điều bị cấm tuyệt đối (ví dụ: không được khẳng định chẩn đoán phân biệt).")

    add_body_p(doc, "4. Đơn thuốc ngoại trú chữ viết tay phức tạp:", bold_prefix="•")
    add_body_p(doc, "Hình ảnh chụp đơn thuốc thực tế tại Việt Nam thường mờ, nhăn, góc chụp nghiêng, chữ viết tay bác sĩ khó đọc, dẫn đến các bộ OCR thông thường bỏ sót tên thuốc hoặc đọc sai liều dùng (mg thành g).")

    add_header_p(doc, "3.2 Mục tiêu nghiên cứu định lượng (Objectives)", level=2)
    add_body_p(doc, "Hệ thống MedGuard AI đặt ra các chỉ tiêu kỹ thuật và an toàn nghiêm ngặt:")

    tbl_objectives = doc.add_table(rows=1, cols=3)
    tbl_objectives.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_objectives.autofit = False
    set_table_borders(tbl_objectives)

    obj_headers = ["Chỉ số Mục tiêu (Metric)", "Ngưỡng Cam kết", "Ý nghĩa Y tế & Cơ chế Đảm bảo"]
    obj_widths = [Inches(2.2), Inches(1.3), Inches(3.0)]
    for i, h in enumerate(obj_headers):
        cell = tbl_objectives.cell(0, i)
        cell.width = obj_widths[i]
        set_cell_background(cell, HEX_HEADER_BG)
        set_cell_margins(cell)
        p = cell.paragraphs[0]
        r = p.add_run(h)
        r.bold = True
        r.font.size = Pt(9)
        r.font.color.rgb = COLOR_PRIMARY

    obj_rows = [
        ("Độ nhạy phát hiện Cờ đỏ (Red Flag Sensitivity)", ">= 99.5%", "Bảo đảm không bỏ sót ca cấp cứu (đau ngực, đột quỵ, khó thở, co giật) nhờ Sàn An toàn Lâm sàng Gate 1."),
        ("Độ chính xác cảnh báo tương tác thuốc cấm", "100.0%", "Phát hiện 10/10 cặp DDI cấm kỵ và 7 nhóm dị ứng chéo dựa trên Dược thư Quốc gia VN đã niêm phong."),
        ("Tính nhất quán Triage - Phản hồi (Consistency)", "100.0%", "Văn bản hiển thị đến người bệnh phải khớp hoàn toàn với nhãn Triage, không nói mâu thuẫn."),
        ("Trấn an sai lầm trong ca cấp cứu", "0 ca (Tuyệt đối)", "Cấm hoàn toàn các phát ngôn xoa dịu làm chậm trễ thời gian cấp cứu."),
        ("Độ trễ phản hồi E2E Fast-path", "< 3.0 giây", "Đạt phản hồi khẩn cấp tức thì cho các ca cấp cứu và cờ đỏ sinh tử."),
        ("Độ trễ phản hồi E2E Multi-agent", "< 6.0 giây", "Đảm bảo trải nghiệm đàm thoại tự nhiên mượt mà trên Clinical Workspace."),
        ("Tỷ lệ đơn thuốc yêu cầu Dược sĩ duyệt", "100.0%", "Mọi đơn thuốc bóc tách OCR đều phải qua chặng xác nhận của con người trước khi kích hoạt.")
    ]

    for idx, r_data in enumerate(obj_rows):
        r_node = tbl_objectives.add_row()
        bg = HEX_LIGHT_ROW if idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(r_data):
            c = r_node.cells[c_idx]
            c.width = obj_widths[c_idx]
            set_cell_background(c, bg)
            set_cell_margins(c)
            p = c.paragraphs[0]
            r = p.add_run(val)
            r.font.size = Pt(8.5)
            r.font.color.rgb = COLOR_DARK

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # ==========================================
    # PHẦN 4. TECHNICAL APPROACHES & TRADE-OFFS
    # ==========================================
    add_header_p(doc, "4. Technical Approaches & Trade-offs — Phương Pháp & Đánh Đổi Kỹ Thuật", level=1)
    
    add_header_p(doc, "4.1 Ý tưởng công nghệ và mô hình phù hợp", level=2)
    add_body_p(doc, "1. Kiến trúc Kiểm soát 3 Cổng (Tri-Gate Governance Architecture):", bold_prefix="•")
    add_body_p(doc, 
        "• Gate 1 (Deterministic Safety Floor): Bộ quy tắc xác định cứng chạy trong < 50ms, kiểm tra cờ đỏ sinh tử (ESI v4) và tương tác dược lý cấm. Nếu vi phạm, lập tức kích hoạt phản hồi khẩn cấp chuẩn hóa, bỏ qua toàn bộ LLM.\n"
        "• Gate 2 (Two-Agent Verification Loop): Điều phối qua LiteLLM Gateway gồm Answer Agent (soạn thảo giải pháp lâm sàng) và Verifier Agent (đóng vai trò thẩm phán y khoa độc lập, đối soát từng nhận định với tài liệu hướng dẫn Bộ Y tế).\n"
        "• Gate 3 (Jev Typed Decision Governance): Lớp vi quyết định định kiểu chặt chẽ, kiểm tra tính hợp lệ của hợp đồng Response Obligations trước khi cho phép trả lời người bệnh.")

    add_body_p(doc, "2. Hợp đồng Trạng thái Lâm sàng Chuẩn hóa (Canonical Clinical State & ROG):", bold_prefix="•")
    add_body_p(doc, "Tất cả các module chia sẻ một đối tượng dữ liệu duy nhất `CanonicalClinicalState`. Đồ thị ràng buộc trách nhiệm nội dung (Response Obligation Graph - ROG) định nghĩa rõ danh sách hành động bắt buộc (`must_contain`) và danh sách hành vi bị cấm (`must_not_contain`).")

    add_body_p(doc, "3. Pipeline Thị giác Máy tính Bóc tách Đơn thuốc (Hybrid Medical OCR):", bold_prefix="•")
    add_body_p(doc, "Kết hợp PaddleOCR (Text Detection) + VietOCR (Transformer Recognition tiếng Việt) + LLM Normalizer để chuẩn hóa tên biệt dược về mã ATC chuẩn và tra cứu tương tác thuốc tức thì.")

    add_body_p(doc, "4. Hệ thống Avatar Bác sĩ 3D C# Native (Unity Engine):", bold_prefix="•")
    add_body_p(doc, "32 nhóm hành động với 64 biến thể cử chỉ có bộ phân tích bối cảnh lâm sàng (DoctorContextAnalyzer.cs) phân biệt rõ phủ định, giả định và đối tượng người thân; đồng bộ khẩu hình Edge TTS Nam Minh / Hoài My.")

    add_header_p(doc, "4.2 Phân tích Đánh đổi Kỹ thuật (Engineering Trade-offs)", level=2)
    add_body_p(doc, "Mỗi quyết định thiết kế trong MedGuard AI đều được cân nhắc kỹ lưỡng giữa các yếu tố xung đột:")

    tbl_tradeoffs = doc.add_table(rows=1, cols=4)
    tbl_tradeoffs.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_tradeoffs.autofit = False
    set_table_borders(tbl_tradeoffs)

    to_headers = ["Hạng mục Đánh đổi", "Phương án 1 (Bỏ qua)", "Phương án 2 (Được chọn)", "Lý do & Giải pháp Cân bằng của MedGuard"]
    to_widths = [Inches(1.5), Inches(1.5), Inches(1.7), Inches(1.8)]
    for i, h in enumerate(to_headers):
        cell = tbl_tradeoffs.cell(0, i)
        cell.width = to_widths[i]
        set_cell_background(cell, HEX_HEADER_BG)
        set_cell_margins(cell)
        p = cell.paragraphs[0]
        r = p.add_run(h)
        r.bold = True
        r.font.size = Pt(8.5)
        r.font.color.rgb = COLOR_PRIMARY

    to_rows = [
        ("Tốc độ vs An toàn Y khoa", "Single-prompt LLM (Đáp ứng 1-2s nhưng nguy cơ ảo giác cao)", "Multi-Agent Tri-Gate (Đáp ứng 4-6s nhưng an toàn tuyệt đối)", "Trong y tế, tính mạng bệnh nhân là tối thượng. Chấp nhận độ trễ 4-6s để đổi lấy việc 0 ca trấn an sai lầm và phát hiện 100% tương tác cấm."),
        ("Quy tắc cứng vs Độ linh hoạt tự nhiên", "Chỉ dùng Rule-based (Cứng nhắc như cây quyết định)", "Hybrid: Rule Floor + Governed LLM Composer", "Sàn an toàn dùng Rule Engine xác định; phần diễn đạt lời thoại tự nhiên dùng LLM được kiểm soát bởi hợp đồng Response Obligations."),
        ("Tự động hóa hoàn toàn vs Con người duyệt", "Tự động kích hoạt lịch thuốc ngay sau khi quét OCR", "Human-in-the-loop: Mặc định PENDING_REVIEW", "Đơn thuốc chữ viết tay có tỷ lệ lỗi tự nhiên. Bắt buộc dược sĩ/bác sĩ duyệt chặng cuối để đảm bảo an toàn pháp lý và y khoa."),
        ("Web Three.js vs Unity C# Native cho Avatar", "Dựng avatar trực tiếp trên Web Three.js (Hạn chế về IK, animation layers)", "Unity C# Standalone/WebGL Player (Toàn quyền skeleton & IK)", "Three.js khiến chuyển động gượng gạo, dễ lỗi khi ngắt lời. Chuyển hẳn sang Unity C# Native giúp kiểm soát 64 cử chỉ mượt mà và chuẩn giải phẫu.")
    ]

    for idx, r_data in enumerate(to_rows):
        r_node = tbl_tradeoffs.add_row()
        bg = HEX_LIGHT_ROW if idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(r_data):
            c = r_node.cells[c_idx]
            c.width = to_widths[c_idx]
            set_cell_background(c, bg)
            set_cell_margins(c)
            p = c.paragraphs[0]
            r = p.add_run(val)
            r.font.size = Pt(8)
            r.font.color.rgb = COLOR_DARK

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # ==========================================
    # PHẦN 5. SYSTEM DESIGN — THIẾT KẾ HỆ THỐNG & HÌNH ẢNH
    # ==========================================
    doc.add_page_break()
    add_header_p(doc, "5. System Design — Thiết Kế Hệ Thống & Lưu Đồ Suy Luận", level=1)
    
    add_header_p(doc, "5.1 Kiến trúc tổng thể hệ thống (System Architecture)", level=2)
    add_body_p(doc, 
        "Hệ thống MedGuard AI được phân tách thành 5 tầng kiến trúc mạch lạc: "
        "(1) Presentation Layer gồm Clinical Workspace và Avatar 3D Unity; "
        "(2) API Gateway & Security với rate limit và xác thực kép; "
        "(3) Clinical Safety Floor (Gate 1); "
        "(4) LiteLLM Multi-Agent Orchestration (Gate 2); và "
        "(5) Persistence Layer với PostgreSQL RLS và tri thức SHA-256:")

    add_image_figure(doc, IMG_SYS_ARCH, "Hình 5.1: Sơ đồ Kiến trúc Tổng thể Hệ thống MedGuard AI (System Architecture)")

    add_header_p(doc, "5.2 Biểu đồ luồng dữ liệu (Data Flow Diagram)", level=2)
    add_body_p(doc, 
        "Dữ liệu từ người dùng đi qua chặng xác thực, làm sạch PII, phân luồng Triage, "
        "kết nối RAG Knowledge Pool, truyền qua Answer Agent và Verifier Judge, trước khi được chuyển đến tầng phân phối:")

    add_image_figure(doc, IMG_DATA_FLOW, "Hình 5.2: Biểu đồ Luồng Dữ liệu Toàn trình (Data Flow Diagram)")

    add_header_p(doc, "5.3 Lưu đồ suy luận đa tầng (Inference Flowchart)", level=2)
    add_body_p(doc, 
        "Lưu đồ suy luận mô tả chi tiết logic rẽ nhánh giữa Fast-path (khi phát hiện cờ đỏ cấp cứu) "
        "và Deep-path (phân tích đa tác nhân), bao gồm vòng lặp phản biện và chốt hợp đồng trách nhiệm:")

    add_image_figure(doc, IMG_INFERENCE, "Hình 5.3: Lưu đồ Suy luận Đa tác nhân Lâm sàng (Inference Flowchart)")

    # ==========================================
    # PHẦN 6. DEVELOPMENT PLAN
    # ==========================================
    doc.add_page_break()
    add_header_p(doc, "6. Development Plan — Kế Hoạch Phát Triển 15 Tuần", level=1)
    add_body_p(doc, "Lộ trình triển khai đề tài được thiết lập theo phương pháp Agile/Scrum qua 5 giai đoạn trọng tâm:")

    tbl_plan = doc.add_table(rows=1, cols=4)
    tbl_plan.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_plan.autofit = False
    set_table_borders(tbl_plan)

    plan_headers = ["Giai đoạn (Pha)", "Khoảng Thời gian", "Nội dung Công việc Trọng tâm", "Sản phẩm / Mốc Bàn giao"]
    plan_widths = [Inches(1.5), Inches(1.3), Inches(2.2), Inches(1.5)]
    for i, h in enumerate(plan_headers):
        cell = tbl_plan.cell(0, i)
        cell.width = plan_widths[i]
        set_cell_background(cell, HEX_HEADER_BG)
        set_cell_margins(cell)
        p = cell.paragraphs[0]
        r = p.add_run(h)
        r.bold = True
        r.font.size = Pt(8.5)
        r.font.color.rgb = COLOR_PRIMARY

    plan_rows = [
        ("Pha 1: Khảo sát & Chuẩn hóa Tri thức", "Tuần 1 – Tuần 3", "Nghiên cứu tài liệu Dược thư QG VN, ESI v4; thiết lập 6 tệp JSON tri thức niêm phong mã băm SHA-256; thiết kế kiến trúc lõi Tri-Gate.", "Tài liệu SRS v1.0, Cơ sở tri thức niêm phong SHA-256."),
        ("Pha 2: Xây dựng Backend & Safety Floor", "Tuần 4 – Tuần 6", "Lập trình Backend FastAPI (18 endpoints), PostgreSQL RLS, Clinical Safety Floor (Gate 1), dựng LiteLLM Gateway và cấu hình 2 tác nhân.", "API Gateway hoạt động, Gate 1 hoàn chỉnh, 150 unit tests."),
        ("Pha 3: OCR, UI & Kiểm thử Tích hợp", "Tuần 7 – Tuần 9", "Tích hợp OCR PaddleOCR + VietOCR, phát triển Clinical Workspace React 19, tích hợp Edge TTS, kết nối E2E với BookingCare platform.", "Web Clinical Workspace, Pipeline OCR đơn thuốc, 396 tests PASS."),
        ("Pha 4: Candidate V11 & Unity Avatar", "Tuần 10 – Tuần 12", "Triển khai Canonical Clinical State, Response Obligation Graph, Response Quality Benchmark 500 ca, phát triển Avatar 3D Unity C# 64 cử chỉ.", "Lõi Candidate V11, Bộ Benchmark 500 ca, Unity C# Package v3."),
        ("Pha 5: Pilot Staging & Nghiệm thu", "Tuần 13 – Tuần 15", "Triển khai Pilot trên môi trường Staging BookingCare, đánh giá lâm sàng với bác sĩ cố vấn, tối ưu hóa latency, hoàn thiện báo cáo tốt nghiệp.", "Báo cáo Tổng kết Hoàn chỉnh, Pilot Production Readiness.")
    ]

    for idx, r_data in enumerate(plan_rows):
        r_node = tbl_plan.add_row()
        bg = HEX_LIGHT_ROW if idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(r_data):
            c = r_node.cells[c_idx]
            c.width = plan_widths[c_idx]
            set_cell_background(c, bg)
            set_cell_margins(c)
            p = c.paragraphs[0]
            r = p.add_run(val)
            r.font.size = Pt(8)
            r.font.color.rgb = COLOR_DARK

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # ==========================================
    # PHẦN 7. PROGRESS — TIẾN ĐỘ HIỆN TẠI
    # ==========================================
    add_header_p(doc, "7. Progress — Tiến Độ Hiện Tại & Đo Lường Thực Tế", level=1)
    
    add_header_p(doc, "7.1 Các hạng mục kỹ thuật đã hoàn thành 100%", level=2)
    add_body_p(doc, "1. Core Backend Platform (100%): 18 REST endpoints chuẩn `/v1`, OpenAPI v1, Rate limiting theo tenant, Idempotency key, PostgreSQL RLS bảo mật tuyệt đối.", bold_prefix="•")
    add_body_p(doc, "2. Clinical Workspace (100%): Ứng dụng Single Page App React 19 + Vite, hỗ trợ quét mã QR thuốc, đàm thoại song ngữ, phát âm Edge TTS Nam Minh/Hoài My.", bold_prefix="•")
    add_body_p(doc, "3. Cơ sở tri thức Y tế Niêm phong (100%): 6 tệp JSON chuẩn hóa (10 cặp tương tác nguy hiểm, 7 nhóm dị ứng chéo, 7 mẫu cờ đỏ ESI, 4 ngưỡng sinh hiệu NEWS2).", bold_prefix="•")
    add_body_p(doc, "4. Bộ Kiểm thử Hồi quy Tự động (100%): 396/396 tests Pytest đạt 100% PASS, không có bất kỳ lỗi hồi quy hay rò rỉ dữ liệu.", bold_prefix="•")
    add_body_p(doc, "5. Hệ sinh thái Avatar Unity C# v3 (100%): Đã xây dựng trọn bộ 32 nhóm hành động, 64 biến thể cử chỉ có bộ phân tích bối cảnh lâm sàng, đạt 32/32 kịch bản kiểm thử.", bold_prefix="•")

    add_header_p(doc, "7.2 Kết quả đo lường và Đánh giá Mù độc lập (Blind V10)", level=2)
    add_body_p(doc, 
        "Nhóm áp dụng phương pháp luận nghiên cứu trung thực: không chỉ đo lường trên tập hồi quy quen thuộc, "
        "nhóm đã thực hiện kỳ kiểm định độc lập Blind V10 trên bộ dữ liệu tổng hợp khắt khe. Kết quả cho thấy hệ thống "
        "bảo vệ an toàn tuyệt đối ở tầng Triage cứng nhưng bộc lộ điểm nghẽn ở tầng sinh văn bản tự nhiên. "
        "Đây chính là động lực để nhóm đề xuất và hoàn thiện kiến trúc Candidate V11 với 6 lớp kiểm soát chất lượng câu trả lời.")

    add_header_p(doc, "7.3 Đánh giá tỷ lệ hoàn thành khối lượng đề tài", level=2)
    add_body_p(doc, "Tính đến thời điểm báo cáo giữa kỳ, nhóm đã hoàn thành khoảng 80% tổng khối lượng công việc của đề tài tốt nghiệp, đảm bảo đúng tiến độ và cam kết chất lượng học thuật.")

    # ==========================================
    # PHẦN 8. AI DISCLOSURE — MINH BẠCH SỬ DỤNG AI
    # ==========================================
    doc.add_page_break()
    add_header_p(doc, "8. AI Disclosure — Minh Bạch Sử Dụng Trí Tuệ Nhân Tạo", level=1)
    add_body_p(doc, 
        "Nhằm tuân thủ tuyệt đối quy định về liêm chính học thuật trong nghiên cứu khoa học, "
        "nhóm tác giả công khai minh bạch toàn bộ phạm vi và mức độ sử dụng các công cụ AI trong quá trình thực hiện đề tài:")

    tbl_disclosure = doc.add_table(rows=1, cols=3)
    tbl_disclosure.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_disclosure.autofit = False
    set_table_borders(tbl_disclosure)

    disc_headers = ["Hạng mục Công việc", "Phần việc do Thành viên Con người Trực tiếp Thực hiện", "Phần việc có Sự hỗ trợ của Công cụ AI"]
    disc_widths = [Inches(1.8), Inches(2.5), Inches(2.2)]
    for i, h in enumerate(disc_headers):
        cell = tbl_disclosure.cell(0, i)
        cell.width = disc_widths[i]
        set_cell_background(cell, HEX_HEADER_BG)
        set_cell_margins(cell)
        p = cell.paragraphs[0]
        r = p.add_run(h)
        r.bold = True
        r.font.size = Pt(8.5)
        r.font.color.rgb = COLOR_PRIMARY

    disc_rows = [
        ("Thiết kế Kiến trúc Lâm sàng", 
         "Trực tiếp sáng tạo kiến trúc Tri-Gate, thiết kế Canonical Clinical State, định nghĩa hợp đồng Response Obligation Graph và ma trận điều kiện cấm kỵ lâm sàng.", 
         "Hỗ trợ chuẩn hóa định dạng sơ đồ, chuyển đổi ghi chú thành cú pháp JSON Schema."),
        ("Chuẩn hóa Tri thức Dược lý", 
         "Trực tiếp tra cứu Dược thư Quốc gia Việt Nam, phân loại mã ATC, phác đồ ESI v4; lựa chọn 10 cặp tương tác cấm và 7 mẫu cờ đỏ sinh tử.", 
         "Hỗ trợ cấu trúc hóa các bảng dữ liệu thô thành tệp JSON có mã băm SHA-256."),
        ("Lập trình Thuật toán Hệ thống", 
         "Viết 100% mã nguồn thuật toán cốt lõi: Clinical Safety Floor, Jev typed micro-decision, bảo mật PostgreSQL RLS, hàng đợi bất đồng bộ.", 
         "Công cụ AI (GitHub Copilot, Antigravity IDE) hỗ trợ tự động hoàn thành cú pháp lặp lại (boilerplate routers, Pydantic field validators)."),
        ("Kiểm Định & Đánh Giá Độc Lập", 
         "Trực tiếp thiết kế quy trình Blind One-Shot, niêm phong HMAC-SHA-256, phân tích nguyên nhân lỗi và thiết kế bộ Response Quality Benchmark 500 ca.", 
         "Hỗ trợ sinh các mẫu ca bệnh giả lập ban đầu (adversarial synthetic prompts) phục vụ stress test."),
        ("Soạn thảo Báo cáo & Tài liệu", 
         "Xác lập toàn bộ nội dung học thuật, phân tích trade-offs, tổng hợp số liệu thực nghiệm và kết luận khoa học.", 
         "Hỗ trợ rà soát chính tả, căn chỉnh bố cục Word DOCX và định dạng bảng biểu thẩm mỹ.")
    ]

    for idx, r_data in enumerate(disc_rows):
        r_node = tbl_disclosure.add_row()
        bg = HEX_LIGHT_ROW if idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(r_data):
            c = r_node.cells[c_idx]
            c.width = disc_widths[c_idx]
            set_cell_background(c, bg)
            set_cell_margins(c)
            p = c.paragraphs[0]
            r = p.add_run(val)
            r.font.size = Pt(8)
            r.font.color.rgb = COLOR_DARK

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    add_callout(doc,
        "CAM KẾT LIÊM CHÍNH HỌC THUẬT CỦA NHÓM TÁC GIẢ:\n"
        "Nhóm sinh viên cam kết mọi tư duy kiến trúc, logic thuật toán an toàn lâm sàng, cơ sở dữ liệu y tế "
        "và trách nhiệm học thuật đối với toàn bộ kết quả báo cáo đều thuộc về các thành viên con người trong nhóm. "
        "Các công cụ AI chỉ đóng vai trò trợ lý gia tăng hiệu suất lập trình và định dạng, không thay thế vai trò nghiên cứu khoa học của nhóm tác giả.",
        title="CAM KẾT LIÊM CHÍNH HỌC THUẬT (ACADEMIC INTEGRITY STATEMENT)")

    # Lưu file
    doc.save(OUTPUT_DOCX_DOCS)
    shutil.copy2(OUTPUT_DOCX_DOCS, OUTPUT_DOCX_DOWNLOADS)
    print(f"-> Đã tạo Báo cáo Giữa kỳ thành công tại: {OUTPUT_DOCX_DOCS}")
    print(f"-> Đã sao chép vào Downloads tại: {OUTPUT_DOCX_DOWNLOADS}")

if __name__ == "__main__":
    generate_midterm_report()
