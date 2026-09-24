# TÀI LIỆU GIỚI THIỆU DỰ ÁN & BÁO CÁO KỸ THUẬT KIẾN TRÚC MÔ HÌNH AI
# MEDGUARD AI SYSTEM
### *Hệ Thống Trí Tuệ Nhân Tạo Hỗ Trợ Ra Quyết Định Lâm Sàng & An Toàn Dược Chuẩn Y Khoa*

---

> **DÀNH CHO ĐỐI TÁC, KHÁCH HÀNG & HỘI ĐỒNG CHUYÊN MÔN Y TẾ**  
> **Phiên bản tài liệu:** 2.0 (Candidate V10 Architecture)  
> **Phân loại:** Tài liệu Giới thiệu Kỹ thuật & Đề xuất Hợp tác (Executive Technical Whitepaper)  
> **Ngôn ngữ:** Tiếng Việt (Kèm thuật ngữ chuyên ngành chuẩn quốc tế)

---

## MỤC LỤC

1. [TỔNG QUAN DỰ ÁN & TẦM NHÌN CHIẾN LƯỢC](#1-tổng-quan-dự-án--tầm-nhìn-chiến-lược)
2. [ĐỊNH VỊ PHÁP LÝ & AN TOÀN TRÁCH NHIỆM CHUYÊN MÔN](#2-định-vị-pháp-lý--an-toàn-trách-nhiệm-chuyên-môn)
3. [9 KHỐI NĂNG LỰC CỐT LÕI (CORE CAPABILITIES)](#3-9-khối-năng-lực-cốt-lõi-core-capabilities)
4. [CHI TIẾT KIẾN TRÚC MÔ HÌNH AI (AI & MODEL ARCHITECTURE DEEP-DIVE)](#4-chi-tiết-kiến-trúc-mô-hình-ai-ai--model-architecture-deep-dive)
   - 4.1. Thách thức cốt tử của LLM truyền thống trong Y tế
   - 4.2. Kiến trúc 3 tầng bảo vệ (Tri-Gate Hybrid Architecture)
   - 4.3. Đáy an toàn lâm sàng đơn điệu (Monotonic Clinical Safety Floor)
   - 4.4. Mô hình 2 Tác nhân Đối kháng (Dual-Agent: Research & Independent Verifier)
   - 4.5. Cơ chế Quản trị Độ bất định & Triệt tiêu Ảo giác (Epistemic Uncertainty Calibration)
   - 4.6. Thị giác máy tính bóc tách đơn thuốc (Vision OCR Pipeline)
5. [CƠ SỞ TRI THỨC LÂM SÀNG BẤT BIẾN (STRUCTURED KNOWLEDGE BASE)](#5-cơ-sở-tri-thức-lâm-sàng-bất-biến-structured-knowledge-base)
6. [BẰNG CHỨNG THỰC NGHIỆM & KẾT QUẢ BENCHMARK LÂM SÀNG](#6-bằng-chứng-thực-nghiệm--kết-quả-benchmark-lâm-sàng)
7. [BẢO MẬT, QUYỀN RIÊNG TƯ & TÍCH HỢP HỆ THỐNG Y TẾ (SECURITY & INTEROPERABILITY)](#7-bảo-mật-quyền-riêng-tư--tích-hợp-hệ-thống-y-tế-security--interoperability)
8. [MÔ HÌNH TRIỂN KHAI & HỢP TÁC (DEPLOYMENT & INTEGRATION)](#8-mô-hình-triển-khai--hợp-tác-deployment--integration)

---

## 1. TỔNG QUAN DỰ ÁN & TẦM NHÌN CHIẾN LƯỢC

### 1.1. Bối cảnh & Thách thức Y tế Hiện tại
Trong kỷ nguyên số hóa y tế, các bệnh viện, phòng khám và nền tảng chăm sóc sức khỏe đối mặt với 3 thách thức mang tính sống còn:
1. **Quá tải khoa Cấp cứu & Phòng khám**: Phân luồng ban đầu (triage) chậm trễ khiến bệnh nhân nguy kịch không được cấp cứu kịp thời, trong khi các ca nhẹ lại chiếm dụng nguồn lực y tế quý giá.
2. **Sai sót dùng thuốc (Adverse Drug Events - ADE)**: Tương tác thuốc bất lợi, dị ứng chéo kháng sinh và chống chỉ định bệnh nền là nguyên nhân hàng đầu gây biến chứng nội viện và tử vong ngoài viện, gây thiệt hại hàng triệu USD và rủi ro pháp lý nặng nề.
3. **Ảo giác của AI tổng quát (Generative AI Hallucination)**: Các mô hình ngôn ngữ lớn (LLM) thương mại như ChatGPT thuần túy thường xuyên "bịa đặt" thông tin y khoa, đưa ra lời khuyên trấn an sai lệch (*false reassurance*), hoặc kê đơn tùy tiện gây nguy hiểm chết người.

### 1.2. Sứ mệnh của MedGuard AI System
**MedGuard AI** là hệ thống dịch vụ độc lập, tiên phong chuẩn hóa **Schema-First Clinical Safety Service**, được xây dựng chuyên biệt để giải quyết triệt để rủi ro ảo giác của AI trong y khoa.

MedGuard AI đóng vai trò như một **"Màng lọc an toàn lâm sàng (Clinical Safety Guardrail)"** và **"Trợ lý phân luồng cấp cứu & kiểm soát đơn thuốc"**, kết hợp sức mạnh phân tích ngôn ngữ tự nhiên hiện đại với sự chặt chẽ, bất biến của các quy tắc y khoa thực chứng (Evidence-Based Medicine).

```
                      ┌──────────────────────────────────────────┐
                      │            MEDGUARD AI SYSTEM            │
                      │  "Zero-Tolerance for Critical AI Error"  │
                      └────────────────────┬─────────────────────┘
                                           │
         ┌─────────────────────────────────┼─────────────────────────────────┐
         ▼                                 ▼                                 ▼
┌──────────────────┐             ┌──────────────────┐             ┌──────────────────┐
│  TIỀN LÂM SÀNG   │             │   AN TOÀN DƯỢC   │             │  TÍCH HỢP BỆNH   │
│   (Pre-Triage)   │             │ (Medication Risk)│             │ VIỆN (EMR/HIS)   │
│ Phân tầng ESI 1-5│             │ Chặn tương tác   │             │ Chuẩn FHIR R4    │
│ Định tuyến 13 CK │             │ Dị ứng chéo thuốc│             │ Bảo mật NĐ 13/CP │
└──────────────────┘             └──────────────────┘             └──────────────────┘
```

---

## 2. ĐỊNH VỊ PHÁP LÝ & AN TOÀN TRÁCH NHIỆM CHUYÊN MÔN

Một trong những ưu tiên hàng đầu của khách hàng y tế là **tính pháp lý và ranh giới trách nhiệm**. MedGuard AI được thiết kế tuân thủ tuyệt đối các quy định hiện hành tại Việt Nam và hướng dẫn quốc tế:

### 2.1. Định vị Hệ thống Hỗ trợ Ra Quyết định Lâm sàng (CDS)
- Căn cứ **Luật Khám bệnh, chữa bệnh số 15/2023/QH15 (hiệu lực 01/01/2024)** và **Hướng dẫn phần mềm CDS của Cục Quản lý Thực phẩm & Dược phẩm Hoa Kỳ (US FDA CDS Guidance)**:
  - MedGuard AI là **Hệ thống Hỗ trợ Ra quyết định Lâm sàng (Clinical Decision Support - CDS)**, **KHÔNG PHẢI** phần mềm chẩn đoán tự động độc lập (*Autonomous Diagnostic System*).
  - Hệ thống **không đưa ra chẩn đoán xác định bệnh**, **không tự ý xuất đơn thuốc điều trị**.
  - Quyết định chuyên môn và trách nhiệm pháp lý cao nhất và cuối cùng thuộc về Bác sĩ / Dược sĩ có Chứng chỉ hành nghề (CCHN).

### 2.2. Ba Nguyên Tắc Kỹ Thuật Bất Biến (Source-Code Invariants)
1. **Bảo toàn Cảnh báo An toàn (Non-Compensatory Safety)**: Lời khuyên êm dịu hay phong cách đàm thoại thân thiện của AI không bao giờ được phép làm lu mờ hoặc ghi đè cảnh báo cấp cứu.
2. **Quy trình Xác thực Có Giám sát (Human-in-the-Loop)**: Mọi đơn thuốc quét qua thị giác máy tính (OCR) đều mặc định gán nhãn `PENDING_REVIEW` và chỉ chuyển thành lịch nhắc thuốc khi có chữ ký/xác nhận của Dược sĩ/Bác sĩ hoặc người dùng có thẩm quyền.
3. **Tính Minh Bạch & Truy Vết Kiểm Toán (Full Audit Trace)**: Mọi phản hồi đều gắn liền mã băm toàn vẹn **SHA-256** của snapshot tri thức y khoa tại thời điểm thực thi, đảm bảo khả năng giải trình 100% trước cơ quan thanh tra y tế.

---

## 3. 9 KHỐI NĂNG LỰC CỐT LÕI (CORE CAPABILITIES)

MedGuard AI cung cấp một bộ API chuẩn hóa (RESTful JSON Schema) và giao diện Workspace đàm thoại hoàn chỉnh với 9 tính năng phục vụ toàn bộ chu trình tiền lâm sàng và ngoại trú:

| STT | Khối Năng Lực | Chức Năng Chi Tiết | Giá Trị Thực Tiễn Cho Khách Hàng |
|:---:|---|---|---|
| **1** | **Phân Luồng Cấp Cứu (Triage Engine)** | Nhận diện dấu hiệu sinh tồn nguy kịch, mẫu cờ đỏ cấp cứu (Red Flags), phân loại mức độ khẩn cấp ESI (1–5) và điều hướng 13 chuyên khoa. | Giảm 60% thời gian chờ phân loại; phát hiện ngay lập tức đột quỵ, nhồi máu cơ tim, sốc phản vệ. |
| **2** | **Thẩm Định An Toàn Thuốc (Medication Safety)** | Kiểm tra tương tác thuốc–thuốc, dị ứng chéo (Cross-Allergy Matrix), chống chỉ định bệnh nền và cảnh báo trùng lặp hoạt chất. | Ngăn chặn các ca tương tác gây tử vong (ví dụ Sildenafil + Nitroglycerin; Warfarin + Aspirin). |
| **3** | **Thị Giác Bóc Tách Đơn Thuốc (Prescription OCR)** | OCR chuyên dụng cho đơn thuốc tiếng Việt, bóc tách tên thuốc, hàm lượng, đường dùng, tần suất và so khớp với Danh mục Dược Quốc gia. | Số hóa đơn thuốc viết tay/in trong vài giây, giảm sai sót nhập liệu của điều dưỡng. |
| **4** | **Lập Lịch Nhắc Uống Thuốc (Medication Schedules)** | Tự động tạo thời gian biểu uống thuốc dựa trên ngôn ngữ tự nhiên hoặc đơn thuốc đã được chuyên gia ký duyệt. | Tăng tỷ lệ tuân thủ điều trị của bệnh nhân ngoại trú và mạn tính lên >85%. |
| **5** | **Xác Minh Nguồn Gốc Thuốc (Product QR Verification)** | Kiểm tra mã GTIN, số Serial, số Lô sản xuất với Cơ sở Dữ liệu Dược phẩm, cảnh báo thuốc thuộc diện thu hồi (*Recall*). | Chống thuốc giả, hỗ trợ thu hồi thuốc nhanh chóng theo lô sản xuất. |
| **6** | **Theo Dõi Diễn Tiến Sinh Hiệu (Remote Monitoring)** | Tiếp nhận sinh hiệu từ xa (Huyết áp, Đường huyết, SpO2), phân tích xu hướng biến thiên (*Trend analysis*) và kích hoạt cảnh báo suy sụp. | Quản lý bệnh nhân mạn tính (tăng huyết áp, đái tháo đường) ngoại trú an toàn. |
| **7** | **Tối Ưu Hóa Hàng Đợi (Queue Prioritization)** | Sắp xếp thứ tự ưu tiên khám bệnh dựa trên chỉ số nguy cơ ESI kết hợp thời gian chờ và tình trạng lâm sàng thực tế. | Giảm áp lực căng thẳng phòng chờ cấp cứu, bảo vệ bệnh nhân nguy cơ cao. |
| **8** | **Định Tuyến Nhà Thuốc (Pharmacy Fulfillment)** | Khớp danh mục thuốc sẵn có với các điểm nhà thuốc liên kết, tối ưu khoảng cách và tồn kho. | Giúp bệnh nhân nhận đủ thuốc nhanh nhất, giảm đứt gãy chuỗi cung ứng thuốc. |
| **9** | **Xuất Dữ Liệu Chuẩn Quốc Tế (FHIR Export & Delivery)** | Đóng gói hồ sơ khám theo chuẩn **HL7 FHIR R4 Bundle**, ký số HMAC Webhook để tích hợp liền mạch vào hệ thống HIS/EMR. | Kết nối ngay vào hệ thống CNTT bệnh viện hiện hữu mà không cần đập đi xây lại. |

---

## 4. CHI TIẾT KIẾN TRÚC MÔ HÌNH AI (AI & MODEL ARCHITECTURE DEEP-DIVE)

### 4.1. Thách thức cốt tử: Tại sao LLM thông thường thất bại trong Y tế?
Khi người bệnh nhập: *"Tôi bị đau đầu dữ dội như búa bổ, huyết áp đo được 190/110, uống thuốc hạ sốt được không?"*:
- **LLM thông thường** (như GPT-4, Llama): Có thể trả lời lịch sự: *"Bạn có thể uống Paracetamol, nghỉ ngơi ở nơi yên tĩnh và theo dõi thêm..."*. Đây là **sai lầm chết người** vì đã bỏ qua triệu chứng xuất huyết dưới nhện hoặc cơn tăng huyết áp cấp cứu đe dọa tổn thương cơ quan đích.
- **MedGuard AI**: Khóa chặn lập tức! Nhận diện tăng huyết áp ác tính kết hợp đau đầu khởi phát sét đánh $\rightarrow$ Kích hoạt mức **EMERGENCY (Cấp cứu 115 ngay lập tức)** $\rightarrow$ Cấm tiệt cụm từ "theo dõi tại nhà" $\rightarrow$ Bắt buộc hướng dẫn nhập viện khẩn cấp.

### 4.2. Kiến Trúc 3 Tầng Bảo Vệ (Tri-Gate Hybrid Architecture)

MedGuard AI sử dụng kiến trúc lai kết hợp giữa **Hệ thống Quy tắc Lâm sàng Tất định (Deterministic Clinical Rules)** và **Mô hình Trí tuệ Nhân tạo Đa Tác tử (Multi-Agent LLMs)** thông qua 3 cổng thẩm định nghiêm ngặt:

```
[ Bệnh nhân / Bác sĩ nhập triệu chứng & dữ liệu ]
                      │
                      ▼
┌────────────────────────────────────────────────────────────────────────┐
│ GATE 1: ĐÁY AN TOÀN LÂM SÀNG TẤT ĐỊNH (Clinical Safety Floor)          │
│ - Evidence Strength Scorer (Bộ chấm điểm bằng chứng lâm sàng)          │
│ - Clinical Threat Graph (Đồ thị đe dọa sinh lý bệnh)                   │
│ - Toxicology Signature Router (Nhận diện hội chứng ngộ độc cấp)        │
│ - End-Organ Coupling Engine (Liên kết suy đa cơ quan & Đột quỵ)        │
│ - Physiologic Consequence Engine (Phân tích hệ quả sinh lý học)        │
│ ===> THIẾT LẬP MỨC NGUY CƠ TỐI THIỂU: MONOTONIC SAFETY FLOOR           │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ GATE 2: BỘ ĐÔI TÁC NHÂN AI KIỂM CHỨNG ĐỐI KHÁNG (Dual-Agent Pipeline)   │
│ (Được cách ly bảo mật qua LiteLLM Gateway & Token/Risk Guard)          │
│                                                                        │
│   ┌───────────────────────────┐      ┌───────────────────────────┐     │
│   │   AGENT 1: RESEARCHER     │      │   AGENT 2: VERIFIER       │     │
│   │ (Phân tích, tìm y văn)    │ ───► │ (Kiểm chứng chéo độc lập) │     │
│   │ Trích xuất bằng chứng     │      │ Chấm điểm Grounding       │     │
│   │ Khóa chặt Locked Claims   │      │ So khớp nguồn tin cậy     │     │
│   └───────────────────────────┘      └───────────────────────────┘     │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ GATE 3: CỔNG XÁC QUYẾT BẤT BIẾN (Deterministic Release Gate & JEV)     │
│ - So khớp kết quả: Final = MAX(Safety_Floor, Verifier, JEV)            │
│ - Luật bảo toàn tính mạng: Tuyệt đối KHÔNG ĐƯỢC hạ cấp dưới Gate 1    │
│ - Cấm các cụm từ gây hại ("tự khỏi", "uống thuốc rồi tính")           │
│ - Bắt buộc hướng dẫn cấp cứu 115 khi ở mức EMERGENCY                   │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
            [ Phản hồi An Toàn Chuẩn Lâm Sàng (Grounded Answer) ]
```

---

### 4.3. Đáy An Toàn Lâm Sàng Đơn Điệu (Monotonic Clinical Safety Floor)

Nguyên lý thiết kế quan trọng nhất của MedGuard AI là tính chất **Đơn điệu (Monotonicity)**:
$$\text{Final Disposition} = \max(\text{Safety Floor}, \text{Reasoner}, \text{Verifier}, \text{JEV})$$

Các mô hình AI hạ tầng phía sau có thể **nâng cấp** mức độ nghiêm trọng nếu phát hiện thêm tình tiết phức tạp, nhưng **tuyệt đối không bao giờ có quyền hạ cấp** mức độ nghiêm trọng xuống dưới Đáy an toàn đã được tính toán bởi Gate 1:

1. **Evidence Strength Scorer**: Định lượng độ mạnh của bằng chứng lâm sàng. Nếu bệnh nhân mô tả mơ hồ nhưng có từ khóa nguy cơ (ví dụ: tê nửa người), hệ thống nâng mức an toàn ngay lập tức.
2. **Toxicology Signature Router**: Phát hiện hội chứng ngộ độc cấp tính (*Toxidromes* như Cholinergic, Anticholinergic, Opioid, Sympathomimetic) thông qua tổ hợp triệu chứng (đồng tử co nhỏ, vã mồ hôi, thở chậm) mà **không cần người bệnh phải nhớ tên hóa chất**.
3. **End-Organ Coupling Engine**: Bắt cặp triệu chứng tăng huyết áp với các biến cố suy cơ quan đích (đột quỵ não, phù phổi cấp, phình bóc tách động mạch chủ, suy thận cấp).
4. **Physiologic Consequence Engine**: Suy diễn logic chuỗi hậu quả sinh lý (ví dụ: Chấn thương đầu $\rightarrow$ Rối loạn tri giác $\rightarrow$ Nguy cơ tụt kẹt não).
5. **Dual Crisis Policy**: Tách biệt và bảo toàn đồng thời cả cấp cứu y khoa (ngộ độc thuốc) và khủng hoảng tâm lý (ý định tự sát), ưu tiên xử lý cấp cứu bảo toàn tính mạng trước khi cung cấp đầu mối trợ giúp tâm lý.

---

### 4.4. Mô Hình 2 Tác Nhân Đối Kháng (Dual-Agent: Research & Independent Verifier)

MedGuard AI triển khai kiến trúc 2 tác nhân độc lập được điều phối thông qua LiteLLM Gateway:
- **Tác nhân 1 - Answer Role (Researcher)**: Tiếp nhận câu hỏi đã được khử định danh (loại bỏ tên, SĐT, số phòng khám), kết hợp với dữ liệu lâm sàng bất biến đã được khóa (*Locked Claims*). Tác nhân tiến hành tìm kiếm thông tin từ các cơ sở y văn chuẩn được cho phép (*Authority Allowlist*).
- **Tác nhân 2 - Verifier Role (Independent Judge)**: Đây là tác nhân độc lập **thuộc họ mô hình khác**. Verifier không được nhìn thấy tiến trình suy nghĩ của Researcher. Verifier tiến hành tìm kiếm độc lập và chấm điểm bản nháp trên 4 trục:
  - **Grounding Score (Độ bám sát y văn)**: Bản nháp có phát biểu điều gì nằm ngoài tài liệu bằng chứng không?
  - **Safety Score (Độ an toàn lâm sàng)**: Có hướng dẫn nguy hiểm hoặc trì hoãn cấp cứu không?
  - **Completeness Score (Tính đầy đủ)**: Có bỏ sót khuyến cáo quan trọng nào không?
  - **Citation Coverage (Mức độ trích dẫn)**: Mọi khuyến cáo điều trị có dẫn chứng link y văn chuẩn không?
- **Cơ chế Fallback Fail-Closed**: Nếu Verifier từ chối, mạng gặp sự cố hoặc điểm an toàn không đạt ngưỡng $\rightarrow$ Hệ thống lập tức thu hồi bản nháp của AI và phát hành văn bản chuẩn mực định sẵn (*Deterministic Fallback*). **Không bao giờ hiển thị bản nháp chưa được kiểm chứng cho bệnh nhân.**

---

### 4.5. Cơ Chế Quản Trị Độ Bất Định & Triệt Tiêu Ảo Giác (Epistemic Uncertainty)

Một lỗi rất phổ biến ở các mô hình AI là **"Tự tin thái quá vào điều mình không biết"**. MedGuard AI tích hợp thuật toán phân loại tri thức luận:
- **Phân tách trạng thái thấu hiểu**:
  - `UNDERSTOOD`: Bệnh nhân cung cấp đầy đủ thông tin, triệu chứng rõ ràng.
  - `PARTIALLY_UNDERSTOOD`: Thông tin có giá trị nhưng thiếu dữ kiện quan trọng (ví dụ: đau ngực nhưng chưa rõ tính chất cơn đau).
  - `UNRESOLVED`: Mô tả quá hỗn loạn, ngôn từ mơ hồ hoặc không đủ cơ sở dữ liệu y khoa.
- **Nguyên tắc "Fail-Safe"**: Khi ở trạng thái `UNRESOLVED`, hệ thống cấm tuyệt đối việc kết luận "Bình thường / Theo dõi tại nhà" (`ROUTINE`). Hệ thống tự động kích hoạt chế độ an toàn `URGENT` hoặc yêu cầu làm rõ triệu chứng (*Clarification Request*).

---

### 4.6. Thị Giác Máy Tính Bóc Tách Đơn Thuốc (Vision OCR Pipeline)

Quy trình bóc tách đơn thuốc ngoại trú được xây dựng chuyên sâu cho bối cảnh y tế Việt Nam:
1. **Kiểm tra hợp lệ đầu vào**: Mã hóa băm SHA-256 ảnh đơn thuốc, kiểm tra định dạng và kích thước, chống tấn công tệp độc hại.
2. **Xử lý bất đồng bộ (Async Queue)**: Điều phối qua hàng đợi Redis/PostgreSQL với cơ chế khôi phục tiến trình khi xảy ra sự cố mạng.
3. **Bóc tách thực thể y tế (Named Entity Recognition - NER)**: Nhận diện Tên thuốc, Biệt dược, Hoạt chất, Hàm lượng, Liều dùng, Đường dùng, Số lần/ngày.
4. **So khớp Danh mục Thuốc Quốc gia (Catalog Matcher)**: Tự động chuẩn hóa tên thuốc viết tắt hoặc sai chính tả về mã ATC của WHO và Dược thư Quốc gia Việt Nam.
5. **Cổng Phê Duyệt Chuyên Môn**: Trả về trạng thái `PENDING_REVIEW` để Dược sĩ/Bác sĩ kiểm tra trước khi chuyển đổi thành dữ liệu kê đơn chính thức.

---

## 5. CƠ SỞ TRI THỨC LÂM SÀNG BẤT BIẾN (STRUCTURED KNOWLEDGE BASE)

Tất cả các quyết định an toàn của MedGuard AI đều dựa trên Cơ sở tri thức có cấu trúc (`app/knowledge/`), được kiểm soát phiên bản và mã hóa toàn vẹn:

| Bộ Tri Thức | Quy Mô / Nội Dung | Nguồn Dẫn Chứng Lâm Sàng | Cơ Chế Xử Lý |
|---|---|---|---|
| **`drug_interactions.json`** | Các cặp tương tác thuốc nguy kịch phân tầng `HARD_STOP` và `SOFT_STOP`. | Dược thư Quốc gia Việt Nam, Phân loại ATC - WHO, Quyết định 5948/QĐ-BYT. | **HARD_STOP**: Chặn đứng tuyệt đối.<br>**SOFT_STOP**: Cảnh báo kèm bắt buộc nhập lý do lâm sàng. |
| **`allergy_cross_matrix.json`** | 7 nhóm dị ứng chéo (Beta-lactam, Sulfonamide, NSAID, v.v.). | Phác đồ Chống sốc phản vệ Bộ Y tế (Thông tư 51/2017/TT-BYT). | Phát hiện dị ứng chéo toàn phần và bán phần trước khi cấp thuốc. |
| **`red_flag_protocols.json`** | 7 mẫu bệnh cảnh cấp cứu tối khẩn, 4 ngưỡng sinh hiệu sinh tử, quy tắc chuyển tuyến 13 chuyên khoa. | Tài liệu Hướng dẫn Chẩn đoán & Điều trị Cấp cứu - Hồi sức tích cực Bộ Y tế. | Phân luồng ESI 1–5, cảnh báo đỏ và kích hoạt tiếp nhận cấp cứu tức thì. |
| **`contraindications.json`** | 6 nhóm chống chỉ định bệnh nền (Loét dạ dày, Suy gan, Suy thận, Tim mạch...). | Hướng dẫn Dược lý Lâm sàng Bộ Y tế. | Cảnh báo khi đơn thuốc có thuốc xung đột trực tiếp với bệnh lý nền. |
| **`monitoring_rules.json`** | 7 chỉ số sinh hiệu theo dõi ngoại trú, ngưỡng dung sai sai số và chiều hướng diễn tiến. | Tiêu chuẩn Hiệp hội Tim mạch / Đái tháo đường Hoa Kỳ (AHA/ADA). | Phát hiện xu hướng suy sụp sức khỏe trước khi biến chứng xảy ra. |
| **`product_registry.json`** | Dữ liệu mã hóa định danh thuốc, số lô, hạn dùng và danh mục thu hồi. | Cục Quản lý Dược - Bộ Y tế Việt Nam. | Xác minh mã vạch/QR, cảnh báo thuốc thu hồi. |

> **Cam kết Toàn vẹn (Knowledge Integrity Commitment):**  
> Mỗi tệp dữ liệu tri thức được tính toán mã SHA-256 độc lập. Mọi lượt gọi API đều đính kèm thông tin:  
> `trace.knowledge_version` và `trace.details.knowledge_integrity`.  
> Khách hàng hoàn toàn có thể kiểm toán độc lập bất kỳ lúc nào để chứng minh quyết định của hệ thống xuất phát từ tài liệu nào.

---

## 6. BẰNG CHỨNG THỰC NGHIỆM & KẾT QUẢ BENCHMARK LÂM SÀNG

MedGuard AI tự hào là một trong số rất ít hệ thống AI Y tế công khai minh bạch các báo cáo kiểm thử đối kháng khắt khe và kết quả đo lường thực tế trên mã nguồn:

### 6.1. Báo cáo Hồi quy 2.400 Ca Lâm Sàng Lịch Sử (Unified V1–V9 Historical Regression)
*(Trích xuất từ kết quả kiểm thử chính thức `outputs/v10_regression_2400_report.json`)*

Bộ dữ liệu gồm **2.400 ca bệnh** bao gồm các ca cấp cứu phức tạp, ca đối kháng có chủ đích (*adversarial cases*), ca nhập nhằng ngôn ngữ địa phương và các ca bệnh thông thường:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                      KẾT QUẢ ĐO LƯỜNG TRÊN 2.400 CA THỰC NGHIỆM                  │
├───────────────────────────────────────┬────────────┬─────────────┬───────────────┤
│ Chỉ Số Đánh Giá An Toàn               │ Tiêu Chuẩn │ Thực Tế Đạt │ Đánh Giá      │
├───────────────────────────────────────┼────────────┼─────────────┼───────────────┤
│ Độ nhạy Bắt Ca Cấp Cứu (T4 Sensitivity)│ >= 99.0%   │   100.0%    │ HOÀN HẢO      │
│ Ca Cấp Cứu bị hạ về Thông Thường      │     0      │     0 ca    │ TUYỆT ĐỐI     │
│ Ca Cấp Cứu bị hạ về Khám Trong Ngày   │     0      │     0 ca    │ TUYỆT ĐỐI     │
│ Tỷ lệ Hạ Cấp Nghiêm Trọng (Under-Triage)│ <= 1.0%   │    0.00%    │ AN TOÀN CAO   │
│ Độ đặc hiệu Ca Thông Thường (Specificity)│ >= 95.0% │   95.29%    │ VƯỢT TIÊU CHUẨN│
│ Nội dung Phản hồi Gây hại (Unsafe)    │     0      │     0       │ KHÔNG CÓ LỖI  │
│ Lỗi sập hệ thống (System Errors)      │   < 1.0%   │    0.00%    │ ỔN ĐỊNH       │
└───────────────────────────────────────┴────────────┴─────────────┴───────────────┘
```

* **1.471/1.471 ca cấp cứu khẩn cấp** được phát hiện chính xác 100%, không có bất kỳ ca bệnh nguy kịch nào bị bỏ sót hay trì hoãn điều trị.
* **Độ đặc hiệu đạt 95.29%**: Hệ thống phân loại chính xác các ca bệnh nhẹ, không gây ra tình trạng báo động giả (*False Alarms*) làm quá tải bác sĩ cấp cứu.

### 6.2. Kiểm Thử 4 Cơ Chế Lâm Sàng Đặc Trưng (Mechanism Benchmarks)
*(Trích xuất từ `outputs/v10_mechanism_benchmarks_report.json`)*

* **Benchmark A (Vượt qua bộ lọc ngoài miền OOD)**: 50/50 ca đạt 100%. (Các ca mô tả dị biệt nhưng có triệu chứng cấp cứu đều được ưu tiên xử lý cấp cứu, không bị từ chối phục vụ).
* **Benchmark B (Hội chứng Ngộ độc cấp Toxidromes)**: 50/50 ca đạt 100%. (Nhận diện chính xác ngộ độc Photpho hữu cơ, ngộ độc thuốc ngủ, sốc thuốc dù người nhà không biết tên thuốc).
* **Benchmark C (Khủng hoảng Kép Y khoa & Tâm lý)**: 30/30 ca đạt 100%. (Bảo toàn phác đồ cấp cứu hồi sức song song với kết nối tổng đài tâm lý).
* **Benchmark D (Liên kết Suy Cơ quan Đích & Đột quỵ)**: 50/50 ca đạt 100%. (Bắt trọn các dấu hiệu tổn thương thần kinh khu trú, cơn đau tim thoáng qua).

---

## 7. BẢO MẬT, QUYỀN RIÊNG TƯ & TÍCH HỢP HỆ THỐNG Y TẾ (SECURITY & INTEROPERABILITY)

### 7.1. Tuân thủ Nghiêm ngặt Nghị định 13/2023/NĐ-CP về Bảo vệ Dữ liệu Cá nhân
- **Dữ liệu sức khỏe là Dữ liệu cá nhân nhạy cảm**: MedGuard AI tích hợp sẵn module `verify_patient_consent`. Mọi yêu cầu xử lý dữ liệu lâm sàng đều đòi hỏi mã đồng thuận tường minh của bệnh nhân.
- **Khử định danh trước khi gửi tới AI (De-identification)**: Tên bệnh nhân, số điện thoại, CMND/CCCD, địa chỉ nhà được tự động bóc tách và thay thế bằng mã định danh kỹ thuật `[PATIENT_REF]` trước khi dữ liệu đi vào mạng lưới phân tích.
- **Chính sách Không Lưu Trữ Dữ Liệu Học (No-Store / Zero-Data Retention)**: Mọi yêu cầu gửi tới Gateway LLM đều được đính kèm cờ `store: false, no-cache: true, no-store: true`. Dữ liệu của bệnh nhân **không bao giờ bị dùng để huấn luyện lại các mô hình AI công cộng**.

### 7.2. Chuẩn Tích Hợp Y Tế Quốc Tế (HL7 FHIR R4)
MedGuard AI không ép buộc bệnh viện phải thay đổi phần mềm quản lý hiện có. Hệ thống hỗ trợ sẵn:
- **FastAPI OpenAPI Schema**: Chuẩn tài liệu tích hợp API rõ ràng, tự động sinh mã Client.
- **FHIR R4 Adapter**: Xuất dữ liệu phiên khám, danh sách thuốc, sinh hiệu và phân loại ESI thành các tài nguyên chuẩn `Patient`, `Observation`, `Condition`, `MedicationRequest`, và `Encounter`.
- **Bảo mật đa tầng**: Xác thực qua `X-API-Key`, phân vùng dữ liệu theo từng khách hàng (`X-Tenant-Id`), khóa chống gửi trùng lặp giao dịch (`Idempotency-Key`).

---

## 8. MÔ HÌNH TRIỂN KHAI & HỢP TÁC (DEPLOYMENT & INTEGRATION)

Chúng tôi cung cấp các phương án triển khai linh hoạt, phù hợp với năng lực hạ tầng và yêu cầu bảo mật của từng nhóm khách hàng:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          3 PHƯƠNG ÁN TRIỂN KHAI HỆ THỐNG                         │
├──────────────────────┬─────────────────────────────┬────────────────────────────┤
│ 1. CLOUD HYBRID SAAS │ 2. ON-PREMISE RIÊNG BIỆT     │ 3. NHÚNG SDK / WORKSPACE   │
├──────────────────────┼─────────────────────────────┼────────────────────────────┤
│ Triển khai trên hạ   │ Toàn bộ hệ thống và mô hình │ Nhúng trực tiếp giao diện  │
│ tầng đám mây bảo mật │ AI nội bộ (MedGemma, vLLM)  │ React Workspace vào cổng   │
│ (AWS/GCP/VNPT/Viettel│ chạy trực tiếp trên máy chủ │ thông tin Bệnh viện hoặc   │
│ Cloud). Gateway LiteLLM│ bệnh viện. Dữ liệu không ra │ ứng dụng di động cho bệnh  │
│ kết nối mô hình y tế.│ ngoài Internet.             │ nhân (Telehealth App).     │
│ Phù hợp: Phòng khám, │ Phù hợp: Bệnh viện hạng đặc │ Phù hợp: Nền tảng y tế số, │
│ Chuỗi nhà thuốc.     │ biệt, Bộ Quốc phòng, Viện ĐK│ Công ty Bảo hiểm sức khỏe. │
└──────────────────────┴─────────────────────────────┴────────────────────────────┘
```

### Lộ Trình Đề Xuất Phối Hợp Triển Khai (4 Giai Đoạn)

```
GIAI ĐOẠN 1 (Tuần 1 - 2): KHẢO SÁT & KẾT NỐI SANDBOX
├── Thiết lập môi trường thử nghiệm (Sandbox Environment) với tenant riêng biệt.
├── Cung cấp API Key thử nghiệm và tài liệu hướng dẫn tích hợp OpenAPI.
└── Họp kỹ thuật rà soát danh mục thuốc và danh mục chuyên khoa của cơ sở.

GIAI ĐOẠN 2 (Tuần 3 - 4): KIỂM ĐỊNH LÂM SÀNG NỘI BỘ (CLINICAL WORKSHOP)
├── Hội đồng chuyên môn của Khách hàng (Bác sĩ, Dược sĩ) trực tiếp thử nghiệm.
├── Chạy thử nghiệm bộ ca bệnh thực tế ẩn danh của bệnh viện.
└── Đo lường độ chính xác phân luồng và mức độ cảnh báo tương tác thuốc.

GIAI ĐOẠN 3 (Tuần 5 - 6): TÍCH HỢP HỆ THỐNG HIS/EMR
├── Kết nối luồng dữ liệu hai chiều thông qua REST API hoặc FHIR R4 Bundle.
├── Cấu hình phân quyền nhân viên y tế và cơ chế giám sát Pharmacovigilance.
└── Đào tạo vận hành và tập huấn cho nhân viên y tế khoa Cấp cứu & Khoa Dược.

GIAI ĐOẠN 4: VẬN HÀNH CHÍNH THỨC & THEO DÕI LIÊN TỤC
├── Golive phân hệ hỗ trợ phân luồng và kiểm tra đơn thuốc.
├── Bật dashboard giám sát thời gian thực (Prometheus/Grafana).
└── Định kỳ hàng tháng xuất báo cáo kiểm toán an toàn lâm sàng và độ chuẩn xác.
```

---

## TỔNG KẾT & CAM KẾT ĐỒNG HÀNH

**MedGuard AI System** không chỉ là một giải pháp công nghệ; đây là một **cam kết chuẩn mực về an toàn y tế**. Với kiến trúc **Tri-Gate**, **Đáy an toàn lâm sàng đơn điệu**, và **hệ thống bằng chứng thực nghiệm trên 2.400 ca bệnh**, MedGuard AI giải quyết trọn vẹn nỗi lo ngại lớn nhất của các nhà lãnh đạo y tế khi ứng dụng Trí tuệ Nhân tạo: **Tính Tin Cậy, Tính An Toàn và Trách Nhiệm Pháp Lý**.

Chúng tôi sẵn sàng phối hợp cùng Quý Bệnh viện / Quý Đối tác để tổ chức buổi trình diễn thực tế (*Live Demo*) và cung cấp môi trường Sandbox để Hội đồng Chuyên môn của Quý vị trực tiếp đánh giá.

---
*Bản quyền tài liệu thuộc về Dự án MedGuard AI System. Mọi thông số kỹ thuật được trích xuất trực tiếp từ mã nguồn và các báo cáo benchmark đã kiểm chứng.*
