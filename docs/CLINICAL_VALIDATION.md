# Quy Trình Thẩm Định Lâm Sàng MedGuard AI (Clinical Validation Protocol)

Tài liệu này xác lập quy trình thẩm định lâm sàng độc lập, quản trị hội đồng chuyên gia y tế, và cơ chế giám sát sau phát hành (Pharmacovigilance) của hệ thống MedGuard AI. Mục tiêu là nhận diện, đo lường và giảm rủi ro có hệ thống; tài liệu không tuyên bố an toàn tuyệt đối hoặc thay thế đánh giá của người có chuyên môn.

---

## 1. Hội Đồng Chuyên Gia Thẩm Định (Clinical Advisory Board)

Mọi cơ sở tri thức (Knowledge Base) và quy tắc lâm sàng (Rule Engine) của MedGuard AI bắt buộc phải được thẩm định và phê duyệt bằng văn bản có chữ ký số bởi hội đồng gồm 3 chuyên gia:

1. **Bác sĩ Chuyên khoa Cấp cứu (Emergency Medicine Specialist)**:
   - Thẩm định các mẫu bệnh cảnh cấp cứu (`RF-ESI1`, `RF-ESI2`), ngưỡng sinh hiệu nguy kịch, và thuật toán phân loại mức độ ESI (Emergency Severity Index 1–5).
   - Ký duyệt ngưỡng an toàn: tỷ lệ hạ cấp sai nghiêm trọng (under-triage rate) bắt buộc $\le 1.0\%$.
2. **Dược sĩ Lâm sàng (Clinical Pharmacist)**:
   - Thẩm định danh mục tương tác thuốc–thuốc theo Dược thư Quốc gia Việt Nam (VNDTF) và phân loại ATC của WHO.
   - Thẩm duyệt ranh giới giữa `HARD_STOP` (chống chỉ định tuyệt đối, không được ghi đè) và `SOFT_STOP` (cảnh báo thận trọng có thể ghi đè kèm lý do lâm sàng).
   - Thẩm định ma trận dị ứng chéo 7 nhóm kháng sinh và thuốc giảm đau.
3. **Chuyên gia Pháp chế Y tế (Medical Legal Counsel)**:
   - Đánh giá tính tuân thủ các quy định về đơn thuốc điện tử và bảo mật dữ liệu sức khỏe người bệnh.

---

## 2. Tiêu Chuẩn Phân Loại Mức Độ Nguy Cơ Tương Tác Thuốc

MedGuard AI áp dụng phân tầng 2 cấp nghiêm ngặt:

| Cấp độ | Định nghĩa lâm sàng | Cơ chế can thiệp của hệ thống | Ví dụ điển hình |
|---|---|---|---|
| **HARD_STOP** | Chống chỉ định tuyệt đối theo Dược thư QG VN hoặc Quyết định 5948/QĐ-BYT. Hậu quả lâm sàng đe dọa tính mạng hoặc tử vong. | Hệ thống **chặn hoàn toàn** quy trình cấp phát. Không cho phép người dùng phổ thông bỏ qua. Bắt buộc có hội chẩn bác sĩ chuyên khoa hoặc chuyển thuốc thay thế. | Sildenafil + Nitroglycerin (tụt HA trụy mạch); Simvastatin + Clarithromycin (tiêu cơ vân suy thận cấp); Methotrexate + NSAID liều cao (suy tủy). |
| **SOFT_STOP** | Tương tác nguy cơ cao nhưng có thể dùng trong các phác đồ chuyên khoa có giám sát nồng độ thuốc hoặc xét nghiệm định kỳ. | Hệ thống hiển thị cảnh báo đỏ nổi bật, giải thích cơ chế, hướng dẫn theo dõi (INR, ECG, Kali máu), và **bắt buộc ghi nhận lý do lâm sàng** khi bác sĩ chọn tiếp tục. | Warfarin + Aspirin (van tim cơ học/sau stent); ACEI + Spironolactone (suy tim cần theo dõi Kali); Clopidogrel + Omeprazole. |

---

## 3. Quy Trình Thẩm Định Nhãn Vàng 3 Bên (Tri-Party Consensus)

Đối với bộ dữ liệu đánh giá lâm sàng `DS-TRIAGE` và `DS-OCR`:
- **Bước 1**: Hai chuyên viên lâm sàng gán nhãn độc lập (mức ESI hoặc bóc tách tên thuốc).
- **Bước 2**: Tính toán mức độ đồng thuận giữa hai người gán nhãn qua hệ số Cohen's kappa. Nếu $\kappa \ge 0.85$, nhãn được chấp nhận tự động.
- **Bước 3**: Với các ca có bất đồng đánh giá (discrepancy), ca bệnh được chuyển lên **Trưởng tiểu ban thẩm định lâm sàng** phân xử để chốt nhãn vàng cuối cùng.

---

## 4. Giám Sát Sau Triển Khai (Pharmacovigilance & Continuous Audit)

1. **Theo dõi Tỷ lệ Ghi đè (Human Override Ratio)**:
   - Thu thập chỉ số `medguard_human_override_total{action}` từ phía khách hàng.
   - Nếu tỷ lệ bác sĩ bỏ qua cảnh báo của một cặp thuốc vượt quá 40%, cặp thuốc đó sẽ tự động được đưa vào danh sách xem xét lại để tránh hiện tượng "mệt mỏi vì cảnh báo" (alert fatigue).
2. **Theo dõi Sự cố Bất lợi (Adverse Drug Event Reporting)**:
   - Thiết lập kênh báo cáo sự cố lâm sàng khẩn cấp. Khi có biến cố bất lợi xảy ra liên quan đến khuyến nghị của AI, toàn bộ nhật ký phiên xử lý được đóng băng (audit freeze) kèm mã băm SHA-256 của snapshot tri thức để phục vụ điều tra chuyên môn.

---

## 5. Dữ Liệu Ngoài Và Kiểm Tra Lệch Phân Phối

Project lưu bản MIMIC-IV-ED Demo 2.2 đã khử định danh tại `datasets/external/mimic-iv-ed-demo-2.2/`, kèm giấy phép nguồn, manifest và SHA-256. `scripts/validate_external_datasets.py` phải xác nhận tính toàn vẹn trước khi chạy `scripts/benchmark_mimic_ed.py`.

Đây chỉ là phép kiểm tra lệch phân phối: chief complaint chủ yếu bằng tiếng Anh, dữ liệu đến từ một bộ ED và nhãn acuity không phải ground truth đầy đủ cho quyết định urgency của MedGuard. Vì vậy kết quả luôn có `production_evaluable=false`, không được dùng để tuyên bố độ chính xác lâm sàng hay tự điều chỉnh rule theo nhãn demo.

Đo ngày 2026-09-08 trên 207/222 dòng có acuity cho thấy emergency recall 12,17% và severe under-triage 39,61%. Kết quả này là blocker nghiêm trọng đối với dữ liệu ngoài miền tiếng Việt. Trước production cần một tập Việt Nam/đa ngôn ngữ được gán nhãn độc lập theo quy trình đồng thuận ba bên, tách train/tuning/evaluation và có phân tầng theo cơ sở, nhóm tuổi, giới, bệnh nền, loại triệu chứng và chất lượng dữ liệu.
