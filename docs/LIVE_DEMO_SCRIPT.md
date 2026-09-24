# KỊCH BẢN TRÌNH DIỄN THỰC TẾ & BỘ CA BỆNH MẪU (LIVE DEMO GUIDE)
# MEDGUARD AI SYSTEM
### *Hướng Dẫn Thao Tác Trực Quan Dành Cho Buổi Làm Việc Với Khách Hàng & Hội Đồng Chuyên Môn*

---

> **Mục tiêu:** Cung cấp tài liệu thực chiến từng bước (step-by-step) giúp đội ngũ kỹ thuật và chuyên môn tự tin thực hiện Live Demo hệ thống MedGuard AI trước các đối tác Bệnh viện, Phòng khám, Chuỗi nhà thuốc và Nhà đầu tư.  
> **Môi trường thực thi:**
> - Giao diện Web Workspace: `http://127.0.0.1:8000/` (React Clinical Workspace)
> - Giao diện API OpenAPI: `http://127.0.0.1:8000/docs` (Swagger UI)
> - Terminal / Postman: cURL command line

---

## MỤC LỤC

1. [CHUẨN BỊ MÔI TRƯỜNG TRƯỚC BUỔI DEMO](#1-chuẩn-bị-môi-trường-trước-buổi-demo)
2. [KỊCH BẢN 1: PHÂN LUỒNG CẤP CỨU TIM MẠCH & ĐỘT QUỴ (EMERGENCY TRIAGE)](#2-kịch-bản-1-phân-luồng-cấp-cứu-tim-mạch--đột-quỵ-emergency-triage)
3. [KỊCH BẢN 2: CHỐNG CHỈ ĐỊNH TƯƠNG TÁC THUỐC NGUY KỊCH (HARD STOP INTERACTION)](#3-kịch-bản-2-chống-chỉ-định-tương-tác-thuốc-nguy-kịch-hard-stop-interaction)
4. [KỊCH BẢN 3: CẢNH BÁO TƯƠNG TÁC THẬN TRỌNG CÓ GIÁM SÁT (SOFT STOP INTERACTION)](#4-kịch-bản-3-cảnh-báo-tương-tác-thận-trọng-có-giám-sát-soft-stop-interaction)
5. [KỊCH BẢN 4: NHẬN DIỆN HỘI CHỨNG NGỘ ĐỘC CẤP KHÔNG CẦN TÊN ĐỘC CHẤT (TOXIDROME)](#5-kịch-bản-4-nhận-diện-hội-chứng-ngộ-độc-cấp-không-cần-tên-độc-chất-toxidrome)
6. [KỊCH BẢN 5: CƠN TĂNG HUYẾT ÁP TỔN THƯƠNG CƠ QUAN ĐÍCH (END-ORGAN COUPLING)](#6-kịch-bản-5-cơn-tăng-huyết-áp-tổn-thương-cơ-quan-đích-end-organ-coupling)
7. [KỊCH BẢN 6: DỊ ỨNG CHÉO KHÁNG SINH & THUỐC GIẢM ĐAU (CROSS-ALLERGY MATRIX)](#7-kịch-bản-6-dị-ứng-chéo-kháng-sinh--thuốc-giảm-đau-cross-allergy-matrix)
8. [KỊCH BẢN 7: BÓC TÁCH ĐƠN THUỐC & QUY TRÌNH PHÊ DUYỆT (VISION OCR WORKFLOW)](#8-kịch-bản-7-bóc-tách-đơn-thuốc--quy-trình-phê-duyệt-vision-ocr-workflow)
9. [KỊCH BẢN 8: XÁC THỰC MÃ QR DƯỢC PHẨM & CẢNH BÁO THU HỒI (PRODUCT QR RECALL)](#9-kịch-bản-8-xác-thực-mã-qr-dược-phẩm--cảnh-báo-thu-hồi-product-qr-recall)
10. [KỊCH BẢN 9: XUẤT HỒ SƠ Y TẾ CHUẨN QUỐC TẾ (HL7 FHIR R4 EXPORT)](#10-kịch-bản-9-xuất-hồ-sơ-y-tế-chuẩn-quốc-tế-hl7-fhir-r4-export)

---

## 1. CHUẨN BỊ MÔI TRƯỜNG TRƯỚC BUỔI DEMO

### 1.1. Khởi động Dịch vụ
Mở Terminal tại thư mục `MEDGUARD_AI_SYSTEM`:
```bash
cd MEDGUARD_AI_SYSTEM
.venv/bin/uvicorn app.main:app --reload --port 8000
```
- Mở trình duyệt tại: `http://127.0.0.1:8000/` (Kiểm tra giao diện React Workspace sẵn sàng).
- Thông tin định danh Demo:
  - `X-Tenant-Id`: `tenant-demo`
  - `X-API-Key`: `demo-key`

---

## 2. KỊCH BẢN 1: PHÂN LUỒNG CẤP CỨU TIM MẠCH & ĐỘT QUỴ (EMERGENCY TRIAGE)

### 2.1. Mục tiêu biểu diễn
Chứng minh hệ thống phát hiện ngay lập tức các triệu chứng cờ đỏ (*Red Flag Patterns*), tự động phân tầng mức độ khẩn cấp cao nhất **EMERGENCY (ESI 1/2)**, điều hướng chuyên khoa Tim mạch/Đột quỵ, và kích hoạt chỉ dẫn cấp cứu 115 mà **không có độ trễ**.

### 2.2. Thao tác trên Giao diện React Workspace
Nhập câu triệu chứng sau vào ô chat:
> *"Bố tôi 62 tuổi đột ngột bị đau thắt ngực dữ dội như bị bóp nghẹt lan lên cổ và cánh tay trái, vã mồ hôi lạnh, khó thở 20 phút nay chưa bớt."*

### 2.3. Phản hồi của Hệ thống cần làm nổi bật với Khách hàng:
1. **Trạng thái xử lý an toàn**: Hiển thị thông báo trạng thái `MedGuard đang xử lý` (tối thiểu 350ms, đảm bảo trải nghiệm tự nhiên).
2. **Cảnh báo đỏ nổi bật (Urgent Alert Badge)**: Mức độ khẩn cấp: **EMERGENCY** (Mã ESI: 1 - 2).
3. **Chuyên khoa điều hướng**: **Tim mạch (Cardiology) / Hồi sức Cấp cứu**.
4. **Văn phong chuẩn y khoa**:
   - Cấm hoàn toàn các lời khuyên trấn an sai lệch như "nằm nghỉ theo dõi thêm", "uống thuốc rồi tính".
   - Bắt buộc dòng chỉ dẫn: *"Cần gọi ngay Cấp cứu 115 hoặc đưa người bệnh đến khoa Cấp cứu gần nhất ngay lập tức"*.
   - Hướng dẫn tư thế an toàn: Nới lỏng cổ áo, ngồi tựa lưng nghỉ ngơi tuyệt đối, không tự lái xe.

### 2.4. Lệnh cURL tương đương cho Khách hàng muốn xem API:
```bash
curl -X POST http://127.0.0.1:8000/v1/triage \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: demo-key' \
  -H 'X-Tenant-Id: tenant-demo' \
  -H 'Idempotency-Key: demo-triage-cardiac-01' \
  -d '{
    "patient_ref": "patient-demo-001",
    "symptoms_text": "đau thắt ngực dữ dội lan lên cổ tay trái vã mồ hôi lạnh khó thở",
    "locale": "vi-VN"
  }'
```

---

## 3. KỊCH BẢN 2: CHỐNG CHỈ ĐỊNH TƯƠNG TÁC THUỐC NGUY KỊCH (HARD STOP INTERACTION)

### 3.1. Mục tiêu biểu diễn
Chứng minh năng lực của **Rule Engine Dược lý** trong việc phát hiện tương tác đe dọa tính mạng theo **Dược thư Quốc gia Việt Nam** và Quyết định 5948/QĐ-BYT. Hệ thống kích hoạt cơ chế **`HARD_STOP`** (chặn cấp thuốc hoàn toàn, không cho phép ghi đè).

### 3.2. Ca bệnh mẫu: Cặp thuốc Sildenafil + Nitroglycerin
- Bệnh nhân đang điều trị bệnh mạch vành bằng: **Nitroglycerin**.
- Bác sĩ/Bệnh nhân đề xuất dùng thêm: **Sildenafil** (Viagra) để điều trị rối loạn cương dương hoặc tăng áp phổi.

### 3.3. Thao tác trên Swagger UI (`/docs`) hoặc cURL:
```bash
curl -X POST http://127.0.0.1:8000/v1/medication/safety-check \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: demo-key' \
  -H 'X-Tenant-Id: tenant-demo' \
  -H 'Idempotency-Key: demo-hard-stop-01' \
  -d '{
    "patient_ref": "patient-demo-002",
    "current_medications": [{"name": "Nitroglycerin", "active_ingredient": "nitroglycerin"}],
    "proposed_medications": [{"name": "Sildenafil", "active_ingredient": "sildenafil"}]
  }'
```

### 3.4. Điểm nhấn giải thích cho Khách hàng:
- Kết quả trả về mang thuộc tính `tier: "HARD_STOP"`.
- Giải thích cơ chế sinh lý bệnh: Sildenafil ức chế PDE-5 làm tăng nồng độ cGMP nội bào; phối hợp với Nitroglycerin (chất cung cấp Nitric Oxide) gây giãn mạch ồ ạt, dẫn đến **tụt huyết áp nghiêm trọng, trụy mạch đe dọa tử vong**.
- Khuyến nghị hệ thống: **Chống chỉ định tuyệt đối (Contraindicated). Không cấp phát.**

---

## 4. KỊCH BẢN 3: CẢNH BÁO TƯƠNG TÁC THẬN TRỌNG CÓ GIÁM SÁT (SOFT STOP INTERACTION)

### 4.1. Mục tiêu biểu diễn
Chứng minh sự linh hoạt lâm sàng giữa chặn đứng tuyệt đối (`HARD_STOP`) và cảnh báo có thể tiếp tục kèm điều kiện giám sát (`SOFT_STOP`), tránh hiện tượng "mệt mỏi vì cảnh báo" (*Alert Fatigue*).

### 4.2. Ca bệnh mẫu: Cặp thuốc Warfarin + Aspirin
- Bệnh nhân rung nhĩ hoặc sau thay van tim cơ học đang dùng: **Warfarin** (kháng vitamin K).
- Có chỉ định phối hợp thêm: **Aspirin** (chống kết tập tiểu cầu sau đặt stent mạch vành).

### 4.3. Thao tác cURL:
```bash
curl -X POST http://127.0.0.1:8000/v1/medication/safety-check \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: demo-key' \
  -H 'X-Tenant-Id: tenant-demo' \
  -H 'Idempotency-Key: demo-soft-stop-01' \
  -d '{
    "patient_ref": "patient-demo-003",
    "current_medications": [{"name": "Warfarin", "active_ingredient": "warfarin"}],
    "proposed_medications": [{"name": "Aspirin", "active_ingredient": "aspirin"}]
  }'
```

### 4.4. Điểm nhấn giải thích:
- Trả về `tier: "SOFT_STOP"`.
- Không chặn đứng quy trình, nhưng hiển thị cảnh báo đỏ nguy cơ xuất huyết tiêu hóa và nội sọ.
- **Yêu cầu bắt buộc**: Bác sĩ phải nhập lý do lâm sàng (`override_reason`) và chỉ định xét nghiệm kiểm tra chỉ số đông máu **INR** định kỳ.

---

## 5. KỊCH BẢN 4: NHẬN DIỆN HỘI CHỨNG NGỘ ĐỘC CẤP KHÔNG CẦN TÊN ĐỘC CHẤT (TOXIDROME)

### 5.1. Mục tiêu biểu diễn
Chứng minh sức mạnh của mô hình **Candidate V10 `toxicology_signature_router`**. Trong đời thực, bệnh nhân ngộ độc cấp thường bất tỉnh hoặc người nhà không biết tên thuốc. MedGuard AI nhận diện đúng hội chứng ngộ độc qua tổ hợp triệu chứng thực thể.

### 5.2. Nhập vào ô chat:
> *"Người nhà phát hiện bệnh nhân nằm gục trong kho làm vườn, đồng tử co nhỏ như đầu đinh ghim, vã mồ hôi đầm đìa khắp người, miệng tiết nhiều bọt dãi, thở khò khè rất chậm."*

### 5.3. Kết quả phân tích của MedGuard AI:
- Nhận diện hội chứng ngộ độc: **Hội chứng Cholinergic (Cholinergic Toxidrome)** đặc trưng của ngộ độc hóa chất trừ sâu nhóm Phospho hữu cơ hoặc Carbamate.
- Mức độ nguy cơ: **EMERGENCY**.
- Cảnh báo an toàn cho người sơ cứu: Chú ý đeo găng tay, tránh tiếp xúc trực tiếp chất nôn và dịch tiết của bệnh nhân để không bị ngộ độc chéo.

---

## 6. KỊCH BẢN 5: CƠN TĂNG HUYẾT ÁP TỔN THƯƠNG CƠ QUAN ĐÍCH (END-ORGAN COUPLING)

### 6.1. Mục tiêu biểu diễn
Chứng minh mô hình **`end_organ_coupling`** loại bỏ lỗi sai phổ biến của LLM thông thường. Khi có số đo huyết áp kịch phát kèm triệu chứng thần kinh khu trú, AI lập tức liên kết thành biến cố tổn thương cơ quan đích (Đột quỵ não/Xuất huyết não).

### 6.2. Nhập vào ô chat:
> *"Huyết áp tôi vừa đo là 195/115 mmHg, thấy đầu đau nhức dữ dội chưa từng có và một bên khóe miệng hơi méo, uống tạm viên Panadol được không?"*

### 6.3. Phản ứng an toàn của MedGuard AI:
- Nhận diện cơn tăng huyết áp cấp cứu (*Hypertensive Emergency*) ghép đôi tổn thương thần kinh (*End-organ deficit*).
- **Loại bỏ hoàn toàn ý định dùng Paracetamol/Panadol tại nhà**.
- Khóa chặn ở mức **EMERGENCY**, kích hoạt quy trình đột quỵ cấp.

---

## 7. KỊCH BẢN 6: DỊ ỨNG CHÉO KHÁNG SINH & THUỐC GIẢM ĐAU (CROSS-ALLERGY MATRIX)

### 7.1. Mục tiêu biểu diễn
Kiểm tra khả năng phát hiện dị ứng chéo thuốc thông qua ma trận **`allergy_cross_matrix.json`** chuẩn hóa theo phác đồ Chống sốc phản vệ Bộ Y tế (Thông tư 51/2017/TT-BYT).

### 7.2. Ca bệnh mẫu: Dị ứng Penicillin nhưng được kê Amoxicillin hoặc Cephalosporin
```bash
curl -X POST http://127.0.0.1:8000/v1/medication/safety-check \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: demo-key' \
  -H 'X-Tenant-Id: tenant-demo' \
  -H 'Idempotency-Key: demo-allergy-cross-01' \
  -d '{
    "patient_ref": "patient-demo-004",
    "allergies": [{"substance": "penicillin", "severity": "HIGH"}],
    "proposed_medications": [
      {"name": "Augmentin", "active_ingredient": "amoxicillin"},
      {"name": "Cefuroxime", "active_ingredient": "cefuroxime"}
    ]
  }'
```

### 7.3. Điểm nhấn:
- Cảnh báo trực tiếp: `Amoxicillin` là kháng sinh cùng nhóm Amino-penicillin $\rightarrow$ Dị ứng chéo 100%.
- Cảnh báo thận trọng: `Cefuroxime` là Cephalosporin thế hệ 2 có tỷ lệ dị ứng chéo bán phần (partial cross-reactivity) $\rightarrow$ Đề xuất chuyển kháng sinh nhóm Macrolide hoặc Quinolone.

---

## 8. KỊCH BẢN 7: BÓC TÁCH ĐƠN THUỐC & QUY TRÌNH PHÊ DUYỆT (VISION OCR WORKFLOW)

### 8.1. Mục tiêu biểu diễn
Chứng minh luồng xử lý thị giác máy tính OCR bất đồng bộ, tính minh bạch của trạng thái `PENDING_REVIEW` và quy trình Dược sĩ duyệt đơn trước khi đưa vào lịch nhắc thuốc.

### 8.2. Các bước trình diễn:
1. **Bước 1 - Gửi ảnh đơn thuốc (API trả về 202 Accepted ngay lập tức)**:
   ```bash
   curl -X POST http://127.0.0.1:8000/v1/prescription/extract \
     -H 'Content-Type: application/json' \
     -H 'X-API-Key: demo-key' \
     -H 'X-Tenant-Id: tenant-demo' \
     -H 'Idempotency-Key: demo-ocr-job-01' \
     -d '{
       "patient_ref": "patient-demo-005",
       "image_url": "s3://medguard-vault/prescriptions/sample_rx_01.jpg",
       "file_name": "sample_rx_01.jpg",
       "mime_type": "image/jpeg"
     }'
   ```
   *Nhận lại `job_id` và trạng thái `queued`.*

2. **Bước 2 - Kiểm tra trạng thái Job**:
   ```bash
   curl -X GET http://127.0.0.1:8000/v1/jobs/{job_id} \
     -H 'X-API-Key: demo-key' \
     -H 'X-Tenant-Id: tenant-demo'
   ```

3. **Bước 3 - Điểm nhấn nghiệp vụ**:
   - Dữ liệu trích xuất bao gồm danh sách thuốc với điểm tự tin (`confidence`), chuẩn hóa theo mã ATC.
   - Trạng thái bắt buộc là `review_status: "PENDING_REVIEW"`.
   - Bác sĩ/Dược sĩ bấm xác nhận duyệt đơn (`POST /v1/jobs/{job_id}/review`) $\rightarrow$ Thuốc mới chính thức được đưa vào Lịch uống thuốc tự động ([Schedules API](file:///Users/munonguyen/Project%20ATI/MEDGUARD_AI_SYSTEM/app/services/schedules.py)).

---

## 9. KỊCH BẢN 8: XÁC THỰC MÃ QR DƯỢC PHẨM & CẢNH BÁO THU HỒI (PRODUCT QR RECALL)

### 9.1. Mục tiêu biểu diễn
Chứng minh tính năng bảo vệ người tiêu dùng trước thuốc giả và thuốc thuộc diện thu hồi khẩn cấp từ Cục Quản lý Dược.

### 9.2. Thao tác trên cURL hoặc quét camera trên UI:
```bash
curl -X POST http://127.0.0.1:8000/v1/product/verify \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: demo-key' \
  -H 'X-Tenant-Id: tenant-demo' \
  -H 'Idempotency-Key: demo-qr-verify-01' \
  -d '{
    "qr_payload": "0108935001234567219988776610LOT-2026A",
    "locale": "vi-VN"
  }'
```

### 9.3. Kết quả minh họa:
- Hệ thống nhận diện: Sản phẩm khớp danh mục, nhưng **Số lô `LOT-2026A` nằm trong danh sách Thu hồi Thuốc khẩn cấp** của cơ quan y tế.
- Hướng dẫn ngay lập tức: Yêu cầu bệnh nhân ngừng uống thuốc, giữ nguyên bao bì và mang thuốc quay lại nhà thuốc/bệnh viện cấp phát.

---

## 10. KỊCH BẢN 9: XUẤT HỒ SƠ Y TẾ CHUẨN QUỐC TẾ (HL7 FHIR R4 EXPORT)

### 10.1. Mục tiêu biểu diễn
Chứng minh cho Giám đốc CNTT / CIO của Bệnh viện thấy MedGuard AI tích hợp dễ dàng vào hệ thống HIS/EMR hiện hữu thông qua chuẩn y tế toàn cầu **HL7 FHIR R4**.

### 10.2. Thao tác cURL:
```bash
curl -X POST http://127.0.0.1:8000/v1/fhir/export \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: demo-key' \
  -H 'X-Tenant-Id: tenant-demo' \
  -H 'Idempotency-Key: demo-fhir-export-01' \
  -d '{
    "patient_ref": "patient-demo-001",
    "encounter_id": "enc-20260924-001"
  }'
```

### 10.3. Cấu trúc FHIR Bundle trả về:
- `resourceType: "Bundle"`
- Chứa các tài nguyên chuẩn: `Patient`, `Observation` (chỉ số sinh hiệu và mức độ phân loại ESI), `Condition` (dấu hiệu cảnh báo lâm sàng), `MedicationRequest` (đơn thuốc an toàn đã kiểm duyệt).
- Kèm chữ ký bảo mật **HMAC Webhook** để bệnh viện chứng thực nguồn gốc dữ liệu.

---

## TỔNG KẾT BÀI TRÌNH DIỄN (KEY TAKEAWAY)

Kết thúc buổi Demo, hãy tóm tắt lại 3 thông điệp đắt giá nhất với Khách hàng:
1. **Độ an toàn tuyệt đối**: Mọi phản hồi đều chịu sự kiểm soát của Đáy an toàn lâm sàng (Safety Floor) và Cổng xác định (Tri-Gate Resolver).
2. **Tuân thủ pháp lý & quy chuẩn**: Đóng vai trò là công cụ CDS hỗ trợ bác sĩ, lưu vết kiểm toán bất biến SHA-256, tuân thủ Luật Khám chữa bệnh 2023 và Nghị định 13/2023/NĐ-CP.
3. **Sẵn sàng tích hợp ngay**: Chuẩn API RESTful, OpenAPI Swagger, và HL7 FHIR R4 giúp Bệnh viện vận hành trong vòng 2–4 tuần mà không làm gián đoạn hệ thống cũ.
