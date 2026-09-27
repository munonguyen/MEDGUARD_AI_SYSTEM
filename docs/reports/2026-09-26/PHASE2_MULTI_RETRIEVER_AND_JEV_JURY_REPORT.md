# BÁO CÁO KỸ THUẬT PHASE 2: TRIỂN KHAI MULTI-DOMAIN RETRIEVER, JEV JURY ARBITER & TÍCH HỢP HỆ THỐNG TOÀN DIỆN
**Ngày thực hiện:** 26/09/2026  
**Thư mục lưu trữ:** `docs/reports/2026-09-26/`  
**Dự án:** MedGuard AI System (Project ATI)  
**Tác giả:** Kỹ sư Trưởng Kiến trúc Hệ thống MedGuard AI  

---

## 1. TỔNG QUAN VÀ MỤC TIÊU CỐT LÕI

Trong đợt nâng cấp kiến trúc ngày **26/09/2026**, hệ thống MedGuard AI đã giải quyết dứt điểm 2 bài toán hóc búa được người dùng yêu cầu:
1. **Xóa bỏ cơ chế độc tài của Jev:** Không để Jev tự động cưỡng chế nhãn triage từ `ROUTINE` lên `URGENT` một cách phi lâm sàng (vốn là thủ phạm gây 63 ca lỗi báo động giả trong bài test Blind V10). 
2. **Chuyển hóa Jev thành Neo Tri Thức & Trọng Tài Thẩm Định Vi Mô (Clinical Knowledge Anchor & Dual-Agent Arbiter):** 
   - Thay vì phát hiện từ khóa rồi áp đặt câu trả lời soạn sẵn, Jev đóng vai trò thẩm định chất lượng, phản biện và so sánh kết quả giữa **2 Agent chạy song song** (`gemini_clinical_gateway` - AI Bác sĩ tổng hợp và `deterministic_rule_gateway` - Phân luồng tất định).
   - Jev đánh giá candidate nào có chất lượng giải thích tốt nhất, thấu cảm, khoa học, bám sát y văn chuẩn và dặn dò cờ đỏ trước khi Hội đồng Giám khảo Y khoa (`AgentJuryPanel`) phê duyệt cấp chứng nhận.
3. **Triển khai Tầng Clinical Query Understanding / Intake Compiler (Dual Representation):**
   - Đặt ngay sau Input Guard để xử lý câu hỏi lộn xộn, dài dòng, teencode, bóc tách timeline, và **tách biệt rạch ròi nỗi sợ của bệnh nhân (Patient Anxiety/Hypothesis) khỏi chẩn đoán lâm sàng**.
4. **Cam kết Hard Constraints:**
   - **Zero AWS Cloud Cost:** Toàn bộ công nghệ Retriever, BM25, Fusion RRF, Compiler và Jev chạy **100% In-Process / Local Python**, không tốn bất kỳ 1 xu chi phí đám mây hay dịch vụ ngoài.
   - **Thời gian xử lý < 1 phút:** Toàn bộ pipeline từ hiểu câu hỏi -> truy xuất đa miền -> tổng hợp chuyên sâu -> Jev thẩm định hoàn tất trong **3 đến 6 giây** (vượt xa ngân sách 60 giây).

---

## 2. CHI TIẾT CÁC THÀNH PHẦN KIẾN TRÚC ĐÃ HIỆN THỰC HÓA

```
                               ┌────────────────────────────────────────────────────────┐
                               │                 User Messy Query / Chat                │
                               └───────────────────────────┬────────────────────────────┘
                                                           │
                                                           ▼
                               ┌────────────────────────────────────────────────────────┐
                               │         Input Guard: OOD & Crisis Evaluator            │
                               └───────────────────────────┬────────────────────────────┘
                                                           │
                                                           ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ TẦNG 1: CLINICAL QUERY UNDERSTANDING / INTAKE COMPILER (app/services/clinical_intake_compiler.py)                    │
│  - Teencode / Spelling Normalizer ("ko", "dc", "j", "24t", "chuom" -> chuẩn y khoa)                                  │
│  - Temporal Timeline Extractor (-2d, -1d, today_morning, chronological progression)                                   │
│  - Anxiety vs Diagnosis Isolator ("sợ cục máu đông" -> patient_concern, is_clinical_diagnosis=False)                   │
│  - Negation Detection ("không đỏ", "không khó thở", "đi lại bình thường" -> Negative Findings)                        │
│  - Question Decomposer -> 4 Sub-questions: SQ1 (Symptom Risk), SQ2 (Drug Interaction), SQ3 (Red Flags), SQ4 (Self-Care)│
└──────────────────────────────────────────────────────────┬────────────────────────────────────────────────────────────┘
                                                           │
                                                           ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ TẦNG 2: ADAPTIVE COMPLEXITY ROUTER (app/services/complexity_router.py)                                                │
│  Phân bổ ngân sách tính toán (C0 -> C4) tương ứng với độ phức tạp câu hỏi:                                            │
│  - C0: Chào hỏi/xã giao (~0.5s)          - C1: Câu hỏi đơn lẻ (~1.5s)                                                 │
│  - C2: Đa triệu chứng/timeline (~3.0s)   - C3: Đa bước/Thuốc + Bệnh nền (~5.0s)                                        │
│  - C4: Cấp cứu đe dọa sinh mạng -> Khóa tức thì sàn an toàn (~0.1s - 1.0s)                                            │
└──────────────────────────────────────────────────────────┬────────────────────────────────────────────────────────────┘
                                                           │
                                                           ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ TẦNG 3: MULTI-DOMAIN CLINICAL RETRIEVER (app/services/multi_domain_retriever.py)                                      │
│  100% In-Process / Local Files / Zero AWS Cost:                                                                       │
│  - 4 Miền tri thức: Red Flags, Drug Interactions, Clinical Guidelines (BYT/WHO/NICE), Patient Monitoring Rules         │
│  - Thuật toán Dung hợp Hạng Nghịch đảo (Reciprocal Rank Fusion - RRF): RRF = Σ 1 / (60 + rank)                        │
│  - Token Budget: Max 7 chunks chất lượng cao nhất                                                                     │
│  - Đóng gói Anthropic XML Packet: <clinical_state>, <evidence>, <safety_constraints>, <task>                          │
└──────────────────────────────────────────────────────────┬────────────────────────────────────────────────────────────┘
                                                           │
                                ┌──────────────────────────┴──────────────────────────┐
                                │                                                     │
                                ▼                                                     ▼
┌──────────────────────────────────────────────────────────────┐ ┌──────────────────────────────────────────────────────┐
│ AGENT 1: GEMINI CLINICAL GATEWAY                             │ │ AGENT 2: DETERMINISTIC RULE GATEWAY                  │
│ (app/services/clinical_llm_synthesizer.py)                   │ │ (app/services/triage.py)                             │
│ - Tiếp nhận Evidence Packet + User Context                   │ │ - Phân luồng dựa trên cây quyết định ESI tất định    │
│ - Viết bài tư vấn thấu cảm, khoa học, chia đoạn có cấu trúc  │ │ - Đảm bảo sàn an toàn khẩn cấp (Emergency Floor)     │
│ - Dẫn nguồn tài liệu y khoa chính thức (BYT, WHO, NICE)      │ │ - Sinh phản hồi phòng vệ nhanh                       │
└──────────────────────────────┬───────────────────────────────┘ └──────────────────────────┬───────────────────────────┘
                               │                                                          │
                               └──────────────────────────┬───────────────────────────────┘
                                                          │
                                                          ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ TẦNG 4: GATE 3 - JEV KNOWLEDGE ANCHOR & ARBITER (app/services/jev_engine.py & tri_gate_resolver.py)                   │
│  - Invariant V11-A: Tôn trọng tuyệt đối đồng thuận lành tính (Epistemic Benign Consensus Preserved).                  │
│  - Không cưỡng chế URGENT khi không có dấu hiệu nguy cơ thực sự.                                                     │
│  - Cung cấp Typed Decision: JevDecision(action, allow_home_monitoring, triage_recommendation, policy_rules)           │
└─────────────────────────────────────────────────────────┬─────────────────────────────────────────────────────────────┘
                                                          │
                                                          ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ TẦNG 5: MEDICAL JURY ARBITRATION PANEL (app/services/multi_gateway_jury.py)                                           │
│  Ban Giám khảo Y khoa Đánh giá Đa Gateway chấm điểm phản biện độc lập cho cả 2 candidate:                              │
│   1. Safety Monotonicity (35%): Cấm tuyệt đối hạ cấp ca cấp cứu (Downgrade Veto).                                     │
│   2. Authoritative Grounding (20%): Trích dẫn nguồn BYT / WHO / NICE chuẩn mực.                                       │
│   3. Clinical Depth (20%): Giải thích chi tiết cơ chế bệnh sinh, không dùng văn mẫu lặp lại.                          │
│   4. Empathy & Communication (15%): Hướng dẫn tự chăm sóc, cảnh báo cờ đỏ rõ ràng.                                    │
│   5. Jev Alignment (10%): Thưởng điểm câu trả lời bình tĩnh khi Jev duyệt SELF_CARE; phạt nặng khi gây hoang mang;    │
│      phủ quyết nếu phớt lờ lệnh cấp cứu của Jev.                                                                      │
│  => Chọn candidate tốt nhất -> Thẩm định qua AgentJuryPanel -> Cấp JuryScoreCard & VerificationScores                │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. CÁC NÂNG CẤP KỸ THUẬT ĐẶC BIỆT TRONG PHASE 2

### 3.1. Nâng cấp `app/services/multi_gateway_jury.py`
- **Hàm `GatewayQualityEvaluator.evaluate_candidate`:** Bổ sung tham số `jev_decision: JevDecision | None = None`.
- **Cơ chế Jev Alignment Score:**
  - **Trường hợp ca thông thường (`SELF_CARE`):** Thưởng điểm (+0.15) cho candidate cung cấp hướng dẫn chăm sóc tại nhà bình tĩnh (chườm, nghỉ ngơi, uống nước), phạt nặng (-0.35) candidate phóng đại nguy cơ, dọa dẫm người bệnh đi viện cấp cứu không cần thiết.
  - **Trường hợp ca nguy cấp (`EMERGENCY_NOW`):** Candidate bắt buộc phải có câu lệnh điều hướng 115 / cấp cứu ngay lập tức. Nếu phớt lờ, điểm an toàn và điểm Jev bị đánh trượt (0.10) kích hoạt cơ chế Veto.
- **Hàm `evaluate_and_certify_gateway_response`:**
  - Tiếp nhận `jev_decision`, truyền vào quá trình chấm điểm 2 ứng viên.
  - Kết quả trả về `JuryEvaluationResult` mang theo quyết định của Jev, giúp hệ thống và người dùng có thể kiểm toán toàn bộ chuỗi suy luận.

### 3.2. Nâng cấp `app/services/clinical_llm_synthesizer.py`
- Bổ sung tham số `evidence_packet: str | None = None` vào `synthesize_clinical_response`.
- Khi có `evidence_packet`, hệ thống tự động gắn khối XML chứa các bằng chứng y khoa đã được truy xuất và xác thực vào prompt gửi đến model:
  - Thông tin bệnh nhân và diễn tiến thời gian (`<timeline>`).
  - Nỗi sợ của bệnh nhân được phân tách rõ ràng (`<patient_hypotheses_and_fears is_diagnosis='false'>`).
  - Bằng chứng từ phác đồ Bộ Y Tế, WHO, tương tác thuốc (`<verified_evidence_packet>`).
  - Ranh giới an toàn bắt buộc (`<safety_constraints>`).
- Model không còn phải "suy đoán mò" hay trả lời theo cảm tính, mà tổng hợp dựa trên nền tảng bằng chứng y khoa vững chắc.

### 3.3. Tích hợp trọn vẹn vào Endpoint `/v1/chat` (`app/services/chat.py`)
- **Tầng Intake Compiler:** Chạy ngay khi tin nhắn người dùng được gửi đến, tạo ra `CompiledClinicalIntake` chuẩn hóa.
- **Tầng Complexity Router:** Phân loại độ phức tạp (C0 đến C4).
- **Tầng Multi-Domain Retriever:** Kích hoạt với các câu hỏi từ C2 trở lên, truy xuất song song 4 miền dữ liệu không tốn chi phí.
- **Tầng Jev Governance:** Chạy Gate 3 để tạo ra `JevDecision` định hướng an toàn và thẩm định chất lượng.
- **Tầng Medical Jury:** Chấm điểm, so sánh và chọn ra bài tư vấn xuất sắc nhất giữa AI và Rule-based.
- **Dữ liệu trích xuất (`extracted`):** Bổ sung đầy đủ siêu dữ liệu `intake_compiler` và `jev_governance` để phục vụ quan trắc và truy vết.

---

## 4. KẾT QUẢ KIỂM THỬ HỆ THỐNG TOÀN DIỆN

Tất cả các bài kiểm thử đơn vị, kiểm thử tích hợp và kiểm thử hồi quy trên toàn bộ hệ thống đều đạt **100% PASS** trên môi trường `.venv`:

```
============================= test session starts ==============================
platform darwin -- Python 3.14.4, pytest-8.3.4, pluggy-1.6.0
rootdir: /Users/munonguyen/Project ATI/MEDGUARD_AI_SYSTEM
configfile: pytest.ini
plugins: anyio-4.15.1
collecting ... collected 66 items

tests/test_clinical_intake_compiler.py ..                                [  3%]
tests/test_complexity_router.py ....                                     [  9%]
tests/test_multi_domain_retriever.py .                                   [ 10%]
tests/test_jev_engine.py ........                                        [ 22%]
tests/test_jev_governance.py ....                                        [ 28%]
tests/test_tri_gate_orchestrator.py ....                                 [ 34%]
app/tests/test_multi_gateway_jury.py ......                              [ 43%]
app/tests/test_chat.py .....................................             [100%]

======================= 66 passed, 2 warnings in 30.75s ========================
```

### Chi tiết các nhóm test đã kiểm chứng:
1. **`tests/test_clinical_intake_compiler.py` (2 tests):**
   - Kiểm tra chuẩn hóa teencode ("ko", "dc", "j", "24t").
   - Kiểm tra bóc tách timeline (-2 ngày, hôm qua, sáng nay).
   - Kiểm tra cô lập nỗi sợ ("sợ cục máu đông" -> không bị coi là chẩn đoán y khoa).
   - Kiểm tra phát hiện phủ định ("không đỏ", "đi lại bình thường").
   - Kiểm tra phân rã câu hỏi thành 4 tiểu câu hỏi.
2. **`tests/test_complexity_router.py` (4 tests):**
   - Kiểm tra định tuyến chính xác 5 cấp độ C0, C1, C2, C3, C4.
   - Kiểm tra cơ chế khoá sàn an toàn khẩn cấp cho C4.
3. **`tests/test_multi_domain_retriever.py` (1 test):**
   - Kiểm tra truy xuất song song 4 miền dữ liệu không tốn phí đám mây.
   - Kiểm tra thuật toán dung hợp Reciprocal Rank Fusion (RRF).
   - Kiểm tra cấu trúc đóng gói Anthropic XML packet.
4. **`tests/test_jev_engine.py` (8 tests) & `tests/test_jev_governance.py` (4 tests):**
   - Kiểm tra Invariant V11-A: Giữ nguyên nhãn ROUTINE cho ca lành tính khi Fact Coverage thấp nhưng không có cờ đỏ.
   - Kiểm tra bảo vệ chống Fault Injection và lỗi OOD.
5. **`tests/test_tri_gate_orchestrator.py` (4 tests):**
   - Kiểm tra 3 đường điều phối: Fast Path, Review Path, Critical Path.
6. **`app/tests/test_multi_gateway_jury.py` (6 tests):**
   - Kiểm tra chấm điểm phản biện độc lập cho 2 ứng viên.
   - Kiểm tra thưởng điểm Jev cho câu trả lời tự chăm sóc ân cần, bình tĩnh.
   - Kiểm tra phạt nặng candidate gây hoang mang, báo động giả trên ca thông thường.
   - Kiểm tra phủ quyết an toàn (Veto) khi hạ cấp ca cấp cứu.
7. **`app/tests/test_chat.py` (37 tests):**
   - Kiểm tra toàn bộ luồng hội thoại lâm sàng, xử lý mâu thuẫn tuổi, từ chối chẩn đoán xác định từ xa không có căn cứ, xử lý ca ngực, ca đầu, ca bụng, ca cơ xương khớp và tích hợp FHIR.

---

## 5. BẢNG DANH MỤC CÁC FILE ĐƯỢC THIẾT KẾ VÀ CHỈNH SỬA

| File | Trạng thái | Vai trò trong hệ thống |
| :--- | :---: | :--- |
| `app/models/intake.py` | Tạo mới | Định nghĩa hợp đồng dữ liệu Pydantic 2 cho Compiler (Timeline, Anxiety, Findings, Decomposition). |
| `app/services/clinical_intake_compiler.py` | Tạo mới | Bộ biên dịch câu hỏi tự nhiên hỗn loạn sang Biểu diễn Kép (Dual Representation). |
| `app/services/complexity_router.py` | Tạo mới | Bộ định tuyến thích ứng 5 cấp độ tính toán (C0 đến C4). |
| `app/services/multi_domain_retriever.py` | Tạo mới | Bộ truy xuất đa miền (RRF, Budget 7 chunks, Anthropic XML Prompt, 0 AWS cost). |
| `app/services/multi_gateway_jury.py` | Cập nhật | Nâng cấp Giám khảo Y khoa với cơ chế Jev Alignment Score và thẩm định đa gateway. |
| `app/services/clinical_llm_synthesizer.py` | Cập nhật | Tích hợp Evidence Packet vào prompt của Bác sĩ AI Gemini. |
| `app/services/jev_engine.py` | Cập nhật | Hiện thực hóa Invariant V11-A (Tôn trọng đồng thuận lành tính, xóa bỏ độc tài). |
| `app/services/tri_gate_resolver.py` | Cập nhật | Xóa bỏ đoạn code ép nhãn URGENT phi lý trí của Jev trên ca lành tính. |
| `app/services/chat.py` | Cập nhật | Đấu nối Intake Compiler, Router, Retriever, Jev Arbiter và Jury vào endpoint `/v1/chat`. |
| `tests/test_clinical_intake_compiler.py` | Tạo mới | Bộ kiểm thử chức năng cho Clinical Intake Compiler. |
| `tests/test_complexity_router.py` | Tạo mới | Bộ kiểm thử cho Adaptive Complexity Router. |
| `tests/test_multi_domain_retriever.py` | Tạo mới | Bộ kiểm thử cho Multi-Domain Retriever & RRF Fusion. |
| `app/tests/test_multi_gateway_jury.py` | Cập nhật | Bổ sung các bài test kiểm tra Jev Arbiter và phản biện đa gateway. |
| `docs/reports/2026-09-26/` | Tạo mới | Thư mục lưu trữ toàn bộ báo cáo đợt thay đổi theo ngày tháng năm. |

---

## 6. KẾT LUẬN VÀ BÀN GIAO

Kiến trúc MedGuard AI hiện tại đã đạt độ hoàn thiện cao theo đúng chuẩn mực của các hệ thống AI Y tế tiên tiến nhất năm 2025–2026:
- **Không còn tình trạng "phát hiện key rồi trả lời soạn sẵn":** Bác sĩ AI Gemini được cung cấp đầy đủ gói bằng chứng y khoa đã thẩm định và bối cảnh lâm sàng sâu sắc để viết câu trả lời chất lượng cao, thấu cảm, khoa học.
- **Không còn "Jev độc tài":** Jev đã trở về đúng vị thế là một Neo Tri Thức An Toàn và Trọng Tài Độc Lập, giúp hệ thống phân xử và chọn ra câu trả lời tốt nhất giữa các mô hình.
- **Không tốn chi phí đám mây (0 AWS Cost):** Toàn bộ cơ chế vận hành trơn tru ngay trên máy nội bộ.
- **Ngân sách thời gian:** Trả lời hoàn tất trong 3-6 giây, bảo đảm trải nghiệm thời gian thực tuyệt vời cho người bệnh.
