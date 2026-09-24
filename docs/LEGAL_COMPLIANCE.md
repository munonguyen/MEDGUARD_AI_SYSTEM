# Báo Cáo Phân Tích Tuân Thủ Pháp Lý MedGuard AI (Legal & Regulatory Compliance)

Tài liệu này xác định vị thế pháp lý, phạm vi tuân thủ các quy định hiện hành của pháp luật Việt Nam, và ranh giới trách nhiệm dân sự/chuyên môn của hệ thống MedGuard AI.

---

## 1. Căn Cứ Pháp Lý Áp Dụng

1. **Luật Khám bệnh, chữa bệnh số 15/2023/QH15** (có hiệu lực từ ngày 01/01/2024):
   - **Điều 8**: Quyền được bảo đảm bí mật thông tin về tình trạng sức khỏe và đời tư.
   - **Điều 19**: Trách nhiệm nghề nghiệp của người hành nghề y — bác sĩ chịu trách nhiệm chuyên môn về quyết định chẩn đoán, chỉ định điều trị và kê đơn thuốc.
   - **Điều 64**: Ứng dụng công nghệ thông tin và chuyển đổi số trong khám bệnh, chữa bệnh.
2. **Nghị định 13/2023/NĐ-CP về Bảo vệ Dữ liệu Cá nhân**:
   - **Khoản 4 Điều 2 & Điều 17**: Thông tin về tình trạng sức khỏe, tiền sử bệnh án và đời tư ghi trong bệnh án được xếp loại là **Dữ liệu cá nhân nhạy cảm**.
   - **Điều 9 & Điều 11**: Xử lý dữ liệu nhạy cảm bắt buộc phải có sự **đồng thuận tường minh (explicit consent)** của chủ thể dữ liệu; chủ thể dữ liệu có quyền được biết, đồng ý hoặc rút lại đồng thuận.
   - **Điều 27**: Áp dụng các biện pháp kỹ thuật và an ninh thông tin bắt buộc đối với dữ liệu nhạy cảm (mã hóa, phân quyền, lưu vết nhật ký).
3. **Quy định của Bộ Y tế về Đơn thuốc Điện tử (Thông tư 04/2022/TT-BYT & Thông tư 26/2025/TT-BYT)**:
   - Quy định về định dạng, mã liên thông đơn thuốc quốc gia và quy trình cấp phát thuốc ngoại trú.
   - Đơn thuốc chỉ có hiệu lực pháp lý khi được ký số bởi người hành nghề có chứng chỉ hành nghề hợp lệ.

---

## 2. Định Vị Pháp Lý Của Hệ Thống MedGuard AI

MedGuard AI được thiết kế và triển khai ở vị thế **Công cụ Hỗ trợ Ra quyết định Lâm sàng (Clinical Decision Support - CDS)**, không phải phần mềm chẩn đoán độc lập (Autonomous Diagnostic System):

```
┌─────────────────────────────────────────────────────────────┐
│  BỆNH NHÂN / NGƯỜI DÙNG                                    │
│  - Cung cấp mô tả triệu chứng hoặc ảnh chụp đơn thuốc      │
│  - Cung cấp đồng thuận xử lý AI (ConsentRecord)             │
└───────────────┬─────────────────────────────────────────────┘
                ▼
┌─────────────────────────────────────────────────────────────┐
│  MEDGUARD AI SERVICE (LỚP HỖ TRỢ KỸ THUẬT)                 │
│  - Sàng lọc nguy cơ ban đầu (Triage ESI)                    │
│  - Bóc tách văn bản đơn thuốc (Vision OCR - PENDING_REVIEW) │
│  - Tra cứu tương tác thuốc & dị ứng chéo (Rule-based)       │
│  * KHÔNG CHẨN ĐOÁN XÁC ĐỊNH — KHÔNG PHÁT HÀNH ĐƠN THUỐC    │
└───────────────┬─────────────────────────────────────────────┘
                ▼
┌─────────────────────────────────────────────────────────────┐
│  BÁC SĨ / DƯỢC SĨ CÓ CHỨNG CHỈ HÀNH NGHỀ                   │
│  - Trực tiếp thăm khám, thẩm định và ký duyệt              │
│  - Chịu trách nhiệm pháp lý cao nhất và cuối cùng           │
└─────────────────────────────────────────────────────────────┘
```

Ba nguyên tắc bất biến được thực thi bằng mã nguồn:
1. **Dịch vụ không chẩn đoán**: Đầu ra của `/v1/triage` là phân luồng chuyên khoa và mức độ khẩn cấp, không kết luận bệnh tật xác định. Mọi response đều mang trường `disclaimer` không được rỗng.
2. **Dịch vụ không kê đơn**: Không endpoint nào sinh ra đơn thuốc có hiệu lực pháp lý. Đầu ra bóc tách thị giác luôn mang trạng thái `review_status: "PENDING_REVIEW"`.
3. **Trách nhiệm tối hậu thuộc về nhân viên y tế**: Toàn bộ các cảnh báo nguy cơ cao đều bắt buộc có thao tác xác nhận hoặc giải trình ghi đè của người có thẩm quyền.

---

## 3. Thực Thi Bảo Vệ Dữ Liệu Cá Nhân Theo Nghị Định 13/2023/NĐ-CP

| Yêu cầu pháp lý (Nghị định 13) | Trạng thái kỹ thuật hiện tại |
|---|---|
| **Đồng thuận của người bệnh** | Có dependency `verify_patient_consent`; token bị thu hồi luôn bị từ chối. Chế độ development hiện cho phép thiếu token khi `MEDGUARD_ENFORCE_CONSENT=false`; production gate yêu cầu bật enforcement và tích hợp kho bằng chứng đồng thuận thật. |
| **Giả danh hóa (Pseudonymization)** | API chỉ nhận định danh giả danh `patient_ref` do khách hàng sinh. Cấm tiếp nhận và lưu trữ họ tên đầy đủ, số điện thoại, số CCCD/CMND. |
| **Cách ly dữ liệu đa khách hàng** | Contract và test đã tenant-scope; runtime local dùng SQLite memory. `rls_schema.sql` là schema đích, chưa phải bằng chứng PostgreSQL/RLS đang hoạt động. |
| **Lưu giữ tối thiểu (Data Minimization)** | Object store development có TTL 1 giờ và tenant key. Cần lifecycle policy được kiểm chứng trên S3/MinIO trước production. |
| **Bảo mật khi lưu và khi truyền** | Backend memory chỉ dùng reversible masking, không được xem là mã hóa production. S3 server-side encryption và TLS termination phải được triển khai, kiểm thử và đưa bằng chứng vận hành vào hồ sơ nghiệm thu. |
| **Tính toàn vẹn nhật ký xử lý** | Audit và knowledge SHA-256 đã có ở mức development; durable append-only storage, chống sửa/xóa và audit freeze vẫn là production blocker. |

---

## 4. Khuyến Nghị Trước Khi Triển Khai Thương Mại

1. Ký kết thỏa thuận xử lý dữ liệu (Data Processing Agreement - DPA) giữa đơn vị cung cấp dịch vụ MedGuard AI và các cơ sở khám chữa bệnh đối tác, quy định rõ quyền kiểm soát và xử lý dữ liệu y tế.
2. Trình hội đồng khoa học kỹ thuật và hội đồng đạo đức y sinh của bệnh viện phê duyệt quy trình ứng dụng AI hỗ trợ phân loại người bệnh trước khi tích hợp vào luồng khám thực tế.
