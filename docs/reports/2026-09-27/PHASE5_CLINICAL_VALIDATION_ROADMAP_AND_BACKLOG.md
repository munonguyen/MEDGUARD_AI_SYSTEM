# KẾ HOẠCH & DANH MỤC NHIỆM VỤ PHASE 5 — CLINICAL VALIDATION & EXPERT REVIEW
**Dự án:** MedGuard AI System (Project ATI)  
**Ngày lập:** 27/09/2026  
**Định vị chuyển tiếp:** Từ **R1/R1.5 (Knowledge Infrastructure Validated / Evaluation Framework Ready)** hướng tới **R2 (Large-Corpus Evaluated)** & **R3 (Clinician Reviewed)**  
**Trạng thái kiến trúc:** **ARCHITECTURAL FREEZE (Đóng băng hoàn toàn tầng điều phối AI)**  

---

## 1. BỐI CẢNH VÀ ĐỊNH VỊ TRƯỞNG THÀNH HỆ THỐNG

Sau khi hoàn thành và nghiệm thu chặt chẽ Phase 4, toàn bộ hệ sinh thái MedGuard AI đã đạt được sự đồng thuận tuyệt đối về các ranh giới kỹ thuật:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                       MEDGUARD SYSTEM MATURITY SUMMARY                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ Phase 3: Architecture Complete                                              │
│          (Dual-Agent, Safety Kernel, Micro-Judge, Synthesis, Output Guard)   │
│                                                                             │
│ Phase 4: Knowledge Infrastructure Validated + Evaluation Framework Ready   │
│          (Source Registry, Graph, Ontology, 3-Way Retrieval, Audit Store)   │
│                                                                             │
│ Phase 5: Real-Data Validation + Expert Review + Calibration + Optimization  │
│          (N ≥ 2.000 Corpus, Double Annotation, Cohen's κ, Failure Taxonomy)│
└─────────────────────────────────────────────────────────────────────────────┘
```

### Các nguyên tắc nền tảng đã được đóng băng:
1. **Kiến trúc tri thức là cốt lõi:** Chuyển từ "LLM-Centric" sang "Knowledge-Centric".
2. **Không bổ sung Agent:** Đóng băng số lượng Agent (không thêm Agent C, Agent D hay Judge mới). Toàn bộ năng lực điều phối hiện tại đã đầy đủ.
3. **Chuyển dịch tư duy kỹ thuật:** Chấm dứt tư duy *"thêm AI / đổi model mạnh hơn"*. Toàn bộ chu kỳ phát triển từ Phase 5 tập trung vào quy trình khoa học:
   $$\mathbf{DATA} \longrightarrow \mathbf{EVALUATE} \longrightarrow \mathbf{FIND\ FAILURE} \longrightarrow \mathbf{FIX\ LOCAL\ COMPONENT} \longrightarrow \mathbf{RE\text{-}EVALUATE}$$
4. **Phân định ranh giới chi phí và môi trường:**
   - Hạ tầng tri thức & đánh giá (Phase 4): **100% In-Process / Zero AWS Cost**.
   - Suy luận ngôn ngữ phức tạp (Phase 3): Kết nối qua LiteLLM Gateway tới các model tiên tiến (Gemini Pro/Flash).

---

## 2. NĂM TRỌNG ĐIỂM BACKLOG BẮT BUỘC TRONG PHASE 5

Dựa trên kết quả quan sát hồi quy kỹ thuật của Phase 4, 5 điểm cốt tử sau đây sẽ đóng vai trò kim chỉ nam trong suốt quá trình triển khai Phase 5:

### 2.1. Ưu tiên Đo lường và Tối ưu `Retrieval Evidence Recall@k` theo từng Cohort
- **Hiện trạng quan sát:** Trong bài kiểm tra hồi quy Phase 4, `Retrieval Evidence Recall` đạt $50\%$ trên mẫu thử $N=2$ (hệ thống trích xuất được $E_1$ - Cờ đỏ DVT nhưng hụt $E_2$ - Chống chỉ định NSAID trên bệnh nhân dùng thuốc chống đông).
- **Ý nghĩa kỹ thuật:** Điều này chứng minh rằng **độ hoàn thiện của truy xuất (retrieval completeness) là điểm nghẽn tiềm tàng lớn nhất** của toàn bộ pipeline. Nếu Retriever bỏ sót bằng chứng then chốt, Reasoner Agent A dù thông minh đến đâu cũng không thể suy luận đúng.
- **Nhiệm vụ Phase 5:**
  - Tách bạch dứt khoát: **Chất lượng của Retriever** $\ne$ **Chất lượng của Reasoner**.
  - Ưu tiên đo lường $\text{Recall}_{\text{evidence}}@k$ trên từng cohort độc lập (DVT, Tương tác thuốc, Sản khoa, Cấp cứu tim mạch...), không chỉ đánh giá precision hoặc thứ hạng Top-1.

### 2.2. Nâng `System Invariance Score` thành Chỉ số Cốt lõi (Core KPI)
- **Hiện trạng quan sát:** Bài kiểm tra metamorphic Phase 4 ghi nhận `System Invariance Score = 90%` (9/10 biến thể ngôn ngữ giữ nguyên nhãn cấp cứu, 1 biến thể bị trôi dạt phân luồng).
- **Ý nghĩa kỹ thuật:** MedGuard được sinh ra để giải quyết bài toán người dùng thật: đặt câu hỏi dài, sai chính tả, teencode, lộn xộn, đảo lộn trình tự thời gian triệu chứng, hoặc hoảng loạn. Mức $90\%$ cho thấy pipeline vẫn còn rủi ro với các dạng hành văn cực đoan.
- **Nhiệm vụ Phase 5:**
  - Chuyển `System Invariance Score` từ chỉ số kiểm thử phụ thành **Core Metric** của toàn bộ đợt đánh giá.
  - Mỗi ca bệnh trong tập kiểm thử sẽ được tự động sinh 10 biến thể hành văn chuẩn hóa để đo lường độ trơ (invariance) của quyết định lâm sàng.

### 2.3. Cổng Kiểm Soát Ngặt Nghèo Cho `Strong LLM Verifier` (Chỉ kích hoạt khi Uncertain)
- **Thiết kế Cascade của Phase 4:**
  ```text
  Deterministic Checks (Negation, Certainty markers, Modal over-claiming)
          ↓
  Local NLI Model (Cross-encoder xử lý quan hệ logic lâm sàng)
          ↓
  uncertain only (Các ca ranh giới mập mờ, độ tin cậy thấp)
          ↓
  Strong LLM Verifier (Chuyên gia thẩm định logic cấp cao)
  ```
- **Rủi ro nếu không kiểm soát:** Nếu kích hoạt Strong LLM Verifier cho toàn bộ mọi claim, hệ thống sẽ tự làm bùng nổ chi phí token và độ trễ phản hồi (latency), phá vỡ nguyên tắc vận hành thời gian thực.
- **Nhiệm vụ Phase 5:**
  - Thiết lập ngưỡng kích hoạt cứng: Chỉ các claim mà tầng Deterministic Checks và Local NLI không thể phân giải chắc chắn ($0.35 \le p \le 0.65$) mới được chuyển tiếp lên Strong LLM Verifier.
  - Duy trì tỷ lệ kích hoạt tầng LLM Verifier $< 15\%$ tổng số claim.

### 2.4. Đo lường Phân vị Độ trễ Đa Thang Đo (Multi-Scale Latency Benchmarks)
- **Hiện trạng:** Độ trễ `<5 ms` ở Phase 4 là kết quả kiểm thử in-memory trên kho snapshot ban đầu ($N \approx 50$ chunks).
- **Thách thức:** Khi nạp đầy đủ các văn bản hướng dẫn điều trị của Bộ Y tế, Dược thư Quốc gia, NICE và WHO, quy mô sẽ tăng lên $10.000$, $100.000$ và $500.000$ chunks.
- **Nhiệm vụ Phase 5:**
  - Xây dựng benchmark đo lường chính xác các phân vị độ trễ: $p_{50}, p_{95}, p_{99}$ dưới tải đồng thời (concurrent load: 10, 50, 100 QPS).
  - Đánh giá thời điểm cần thiết để kích hoạt `DenseEmbeddingRetriever` (HNSW index / Vector DB) khi quy mô sparse retrieval tiệm cận ngưỡng trễ cho phép.

### 2.5. Tuân thủ Tuyệt đối Đóng Băng Kiến Trúc (Architectural Freeze)
- **Cam kết:** Không viết thêm Agent C, Agent D, hay Judge mới.
- **Định hướng tối ưu:** Mọi cải tiến đều phải xuất phát từ việc xác định nguyên nhân gốc rễ (Root Cause Analysis) qua tập dữ liệu lớn và sửa chữa cục bộ từng thành phần:
  - Lỗi nhận diện từ lóng $\rightarrow$ Cập nhật từ vựng Ontology.
  - Lỗi bỏ sót tài liệu $\rightarrow$ Bổ sung từ khóa, điều chỉnh BM25/CharNgram/Graph fusion weights.
  - Lỗi suy luận lâm sàng $\rightarrow$ Tinh chỉnh prompt và ràng buộc logic của Reasoner Agent A.
  - Lỗi bỏ qua ranh giới an toàn $\rightarrow$ Cập nhật luật cứng trong Safety Kernel.

---

## 3. BA CỔNG KIỂM SOÁT KHOA HỌC CỦA PHASE 5 (THREE GATES)

```text
                               PHASE 5 GATES
                                     │
       ┌─────────────────────────────┼─────────────────────────────┐
       ▼                             ▼                             ▼
  GATE 1: R2                     GATE 2: R3                    GATE 3
Large-Corpus Evaluated       Clinician Reviewed       Failure-Driven Optimization
- N ≥ 2.000 ca bệnh          - Double Annotation      - 11-group failure taxonomy
- Dev / Blind / Adv          - Cohen's Kappa (κ)      - Định lượng % nguyên nhân
- Disaggregated Metrics      - Adjudicator trọng tài  - Sửa cục bộ thành phần
```

### Gate 1 — R2: Large-Corpus Evaluated ($N \ge 2.000$ ca)
- **Cấu trúc phân bổ 3 tập dữ liệu độc lập:**
  1. `Developer set` (~800 ca): Dùng cho đội ngũ kỹ thuật tinh chỉnh prompt, tối ưu trọng số reranker và cân chỉnh ngưỡng Jev.
  2. `Blind set` (~800 ca): **Giữ kín tuyệt đối.** Đội ngũ kỹ thuật không được phép truy cập nội dung hay nhãn của Blind set trong suốt quá trình phát triển để tránh over-fitting.
  3. `Adversarial set` (~400+ ca): Các ca bẫy lâm sàng phức tạp, đa bệnh lý chồng chéo, lỗi hành văn cực đoan, chống chỉ định ẩn.
- **Báo cáo phân rã bắt buộc (Disaggregated Reporting):**
  - Tuyệt đối không chỉ dùng số bình quân chung (Global Average).
  - Từng cohort (Tim mạch, Hô hấp, Đột quỵ, Dược lâm sàng, Nhi khoa, Sản khoa...) phải công bố báo cáo độc lập:
    - `Emergency Recall` (Mục tiêu: $\ge 99.0\%$)
    - `Under-triage rate` (Mục tiêu: $< 1.0\%$)
    - `Over-triage rate` (Kiểm soát để không gây quá tải y tế)
    - `Specificity` (Bảo đảm không gây lo lắng không cần thiết)
    - `Drug-safety violation` (Mục tiêu: $0.0\%$)
    - `Evidence faithfulness` (Tỷ lệ luận điểm có chứng cứ bảo chứng)
    - `Retrieval Evidence Recall@k` (Độ bao phủ của bằng chứng cần thiết)
    - `System Invariance Score` (Độ vững trước biến thể ngôn ngữ)

### Gate 2 — R3: Clinician Reviewed (Hội đồng Thẩm định Y khoa Độc lập)
- **Quy trình Double Annotation cho các ca High-Risk:**
  ```text
  Bác sĩ Lâm sàng A ──┐
                      ├──► Đối chiếu ──► Đồng thuận? ──► Chấp thuận Gold Label
  Bác sĩ Lâm sàng B ──┘         │
                                └──► Bất đồng? ──► Trọng tài (Adjudicator)
  ```
- **Hệ số tin cậy tương thích:** Đo lường **Cohen's Kappa ($\kappa$)** giữa hai bác sĩ độc lập. Nếu $\kappa < 0.75$, tiến hành rà soát lại tiêu chuẩn gán nhãn guideline.
- **Nguyên tắc vàng:** Tuyệt đối không sử dụng nhận định của một bác sĩ duy nhất làm "chân lý lâm sàng" (Gold Truth).

### Gate 3 — Failure-Driven Optimization (Tối ưu hóa Định hướng theo Lỗi)
- **11 Nhóm phân loại lỗi lâm sàng (Clinical Failure Taxonomy):**
  1. `INTAKE_ERROR`: Compiler hiểu sai cấu trúc câu, trích xuất thiếu thực thể hoặc sai timeline.
  2. `ENTITY_RESOLUTION_ERROR`: Ontology phân giải sai thực thể hoặc nhầm lẫn biệt dược.
  3. `RETRIEVAL_MISS`: Retriever bỏ sót đoạn guideline hoặc khuyến cáo quan trọng.
  4. `RERANK_ERROR`: Reranker xếp bằng chứng đúng xuống dưới bằng chứng kém liên quan.
  5. `KNOWLEDGE_GAP`: Tri thức thực tế chưa có trong các văn bản đã nạp.
  6. `REASONING_ERROR`: Reasoner Agent A suy luận sai cơ chế bệnh sinh.
  7. `CRITIC_MISS`: Critic Agent B bỏ sót sai sót của bản thảo A.
  8. `JEV_MISJUDGMENT`: Jev chấm sai xác suất nguyên tử hoặc gán trọng số lệch.
  9. `SYNTHESIS_ERROR`: Final Synthesis Agent làm biến dạng câu trả lời đã được phê duyệt.
  10. `OUTPUT_GUARD_MISS`: Safety Guard không bắt được phát ngôn rủi ro còn sót lại.
  11. `EVIDENCE_ERROR`: Trích dẫn không khớp hoặc khẳng định vượt quá bằng chứng (Over-claiming).
- **Quy trình tối ưu hóa:**  
  Sau khi chạy 2.000 ca, hệ thống sẽ lập biểu đồ Pareto phân bố lỗi. Mọi nguồn lực phát triển sẽ được tập trung vào nhóm lỗi chiếm tỷ trọng cao nhất (ví dụ: nếu `RETRIEVAL_MISS` chiếm $35\% \implies$ tối ưu hóa query reformulation và ontology synonyms).

---

## 4. KẾ HOẠCH HÀNH ĐỘNG VÀ PHÂN KỲ TRIỂN KHAI

| Giai đoạn | Mục tiêu chính | Đầu ra bàn giao | Tiêu chuẩn nghiệm thu |
| :--- | :--- | :--- | :--- |
| **Phase 5.1** | Thu thập & Chuẩn bị Corpus $N \ge 2.000$ | Bộ dữ liệu Dev, Blind, Adversarial có cấu trúc | 800 Dev, 800 Blind (bảo mật), 400 Adv |
| **Phase 5.2** | Double Annotation & Đo lường $\kappa$ | Bảng gán nhãn chuyên gia độc lập | Cohen's Kappa $\kappa \ge 0.80$, Adjudicator ký duyệt |
| **Phase 5.3** | Chạy Thẩm định R2 Large-Corpus | Báo cáo Disaggregated Metrics trên 17 cohorts | Emergency Recall $\ge 99.0\%$, Zero safety violations |
| **Phase 5.4** | Phân tích Lỗi & Sửa chữa Cục bộ | Báo cáo Pareto Failure Taxonomy & Local fixes | Khắc phục $> 80\%$ các lỗi thuộc top-3 nhóm lớn nhất |
| **Phase 5.5** | Scale Latency & Đóng gói R2/R3 | Benchmark $10\text{k}-500\text{k}$ chunks & Audit freeze | $p_{95} \le 1.500\text{ ms}$, Hồ sơ chứng nhận R2/R3 |

---

## 5. KẾT LUẬN

MedGuard AI System sau Phase 4 đã hoàn tất toàn bộ khung kiến trúc, hạ tầng tri thức và động cơ đánh giá tự động. Không có bất kỳ khoảng trống kiến trúc nào cần "thêm AI" để lấp đầy.

Nhiệm vụ tối thượng của Phase 5 là **kiểm chứng thực nghiệm trên quy mô lớn bằng dữ liệu lâm sàng thực tế, dưới sự giám sát độc lập của các chuyên gia y tế**. Kết quả từ 2.000 ca bệnh sẽ là căn cứ duy nhất để định hướng mọi tinh chỉnh kỹ thuật, đảm bảo hệ thống đạt chuẩn an toàn y tế cao nhất trước khi bước vào giai đoạn thử nghiệm lâm sàng có kiểm soát (Phase 6 - R4 Controlled Pilot).
