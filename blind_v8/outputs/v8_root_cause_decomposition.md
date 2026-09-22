# Báo Cáo Phân Tích Bóc Tách Nguyên Nhân Gốc (Root-Cause Decomposition) & Kiểm Định Khái Quát Hóa Lâm Sàng Blind V8

**Hệ thống:** BOOKINGCARE AI - MEDGUARD AI SYSTEM  
**Phiên bản kiểm định:** Candidate Tri-Gate V8 (Commit: `c07c53458a6328d96cec8b7d311ff45107f9582b`)  
**Thời điểm thực hiện:** 22/09/2026  
**Quy chế kiểm định:** Cryptographically Sealed One-Shot Evaluation (300 Ca unseen)  

---

## 1. Tuyên Bố Trạng Thái Dự Án Chính Thức

> **"Engineering workstreams completed; independent Blind V8 clinical-generalization gate failed. Release remains blocked pending root-cause analysis and a new unseen validation cycle."**

### 1.1 Đánh giá các hợp phần kỹ thuật (Engineering Workstreams): PASS
* **E2E Workflow:** **PASS (7/7 chặng tích hợp)** — Định danh chính xác: *"E2E functional integration validated"* (Xác thực toàn vẹn luồng dữ liệu BookingCare $\rightarrow$ MedGuard $\rightarrow$ Hàng đợi $\rightarrow$ OCR $\rightarrow$ Safety Check $\rightarrow$ Lịch nhắc $\rightarrow$ Tái khám).
* **Auditability & Observability:** **PASS** — Hoàn tất ghi nhận bản ghi kiểm toán bất biến (`cdec_<hex>`), metric P50/P90/P95/P99, tracing và circuit breaker.
* **Prescription OCR Invariant:** **PASS** — Ràng buộc sống còn `unsafe auto-accept = 0` được bảo toàn tuyệt đối (10/10 kịch bản).
* **Cổng 3 (Jev Engine) Invariant:** **PASS** — `Jev induced under-triage = 0` (Tuyệt đối không gây tổn hại hay hạ bậc an toàn).
* **Runtime & Regression Engineering:** **PASS** — 389/389 bài kiểm thử hồi quy pass hoàn toàn (100%).

### 1.2 Đánh giá năng lực khái quát hóa lâm sàng (Clinical Generalization): FAIL
```text
Clinical Generalization Gate:
  - Pure T4/Emergency Sensitivity: 62.04% (152/245)
  - Critical Under-Triage Misses:  93/245 ca cấp cứu unseen bị bỏ sót
  → KẾT LUẬN: FAIL (Release Blocked)
```
**Nguyên tắc cốt lõi:** 389/389 bài kiểm thử hồi quy thành công **không thể bù đắp** cho thất bại trên tập kiểm thử mù độc lập (Blind V8). Hệ thống bị chặn chuyển sang Controlled Clinical Use tại phòng khám cho đến khi hoàn tất phân tích bóc tách và vượt qua chu kỳ kiểm định unseen mới.

---

## 2. Niêm Phong Baseline Blind V8 & Mở Rộng Kho Dữ Liệu Hồi Quy

Thực hiện nghiêm ngặt nguyên tắc khoa học: **Tuyệt đối không sửa 93 ca rồi chạy lại và gọi là Blind V8.**

Blind V8 đã hoàn thành sứ mệnh lịch sử là phát hiện ranh giới ngoại suy của Candidate V8. Kết quả được niêm phong vĩnh viễn:
```text
Blind V8 Baseline (Sealed)
  - Tổng số ca unseen:               300 ca
  - Số ca cấp cứu (T4):              245 ca
  - Bắt đúng T4 (Caught):             152 ca
  - Bỏ sót T4 (Missed):               93 ca
  - Độ nhạy T4 (Sensitivity):        62.04%
  - Độ đặc hiệu ca lành (25 ca):     100.00%
  - Quyết định:                       FAILED / NO-GO
```

Sau khi mở Oracle để chẩn đoán, toàn bộ 300 ca của Blind V8 được sáp nhập vào kho dữ liệu kiểm thử hồi quy lịch sử:
```text
Kho hồi quy lịch sử V1–V7:   1,800 ca
Blind V8 được sáp nhập:        300 ca
-------------------------------------
TỔNG KHO HỒI QUY HIỆN TẠI:   2,100 ca
```
*Ghi chú:* Kết quả post-fix trên 2,100 ca này chỉ là bài kiểm tra chống hồi quy (Regression Test), không được dùng làm bằng chứng kiểm định độc lập (Independent Validation).

---

## 3. Phân Tích Đóng Góp Nhân Quả Của Cổng 3 (Counterfactual Jev Attribution)

Đo lường tác động thực sự của Cổng 3 (Jev Engine) trên phân phối dữ liệu unseen thông qua thí nghiệm phản thực tế (Counterfactual Attribution):

| Chỉ số phản thực tế | Giá trị đo được | Ý nghĩa lâm sàng |
|---|:---:|---|
| **T4 Sensitivity khi KHÔNG có Jev** | **62.04% (152/245)** | Hiệu năng gốc của Cổng 1 (Rule/Fact) + Cổng 2 (Consequence/Threat) |
| **T4 Sensitivity khi CÓ Jev** | **62.04% (152/245)** | Hiệu năng toàn diện của hệ thống Tri-Gate |
| **Độ chênh lệch nhạy (Delta Sensitivity)** | **+0.00%** | Jev trung tính về mặt độ nhạy trên tập unseen V8 |
| **Wrong $\rightarrow$ Correct (Cứu sai thành đúng)** | **0 ca** | Jev không tự cứu được ca nào trong 93 ca miss |
| **Correct $\rightarrow$ Wrong (Làm hỏng ca đúng)** | **0 ca** | Jev không phá hủy bất kỳ ca triage đúng nào |
| **Prevented Under-triage (Ngăn hạ bậc sót ca)** | **0 ca** | Không phát sinh sự can thiệp đảo chiều |
| **Induced Under-triage (Gây hạ bậc nguy hiểm)** | **0 ca** | **Bảo toàn bất biến an toàn tuyệt đối (Zero Safety Harm)** |
| **Induced Over-triage (Gây báo động giả)** | **0 ca** | Không làm tăng gánh nặng cấp cứu |

### Kết luận kiến trúc về Jev:
Jev vận hành như một bộ phân xử rủi ro (Arbitrator) dựa trên cấu trúc `DecisionState` được truyền từ tầng trên (Upstream). Khi các tầng phía trên (Fact Parser, Threat Graph, Toxicology Reasoner) hoàn toàn im lặng trước các biểu đạt ngôn ngữ gián tiếp hoặc triệu chứng cô lập:
- Tầng trên trả về `floor = ROUTINE` và `risk_features = ()`.
- Cổng 3 Jev nhận một trạng thái không có kích hoạt (unactivated state) nên theo đúng nguyên lý an toàn, nó không được phép tự suy diễn (hallucinate) ra tín hiệu cấp cứu khi không có bằng chứng.
- **Do đó: Nút thắt của hệ thống nằm ở biểu diễn ngữ nghĩa và nhận diện đe dọa thượng nguồn (Upstream Semantic Abstraction & Threat Recognition), hoàn toàn không nằm ở tầng phân xử Jev.**

---

## 4. Phân Tích Bóc Tách Theo 7 Nhóm Bệnh Lâm Sàng (Cohort Decomposition)

Bảng phân tích chi tiết hiệu năng phân luồng cấp cứu (T4) trên 7 nhóm bệnh:

| Nhóm ca bệnh lâm sàng (Cohort) | T4 N | Caught | Missed | T4 Sensitivity | Ghi chú & Đánh giá rủi ro |
|---|:---:|:---:|:---:|:---:|---|
| `indirect_linguistic_descriptions` | 30 | 12 | 18 | **40.0%** | **Thất bại nặng nhất (Ngôn ngữ gián tiếp/dân tộc/ẩn dụ)** |
| `partial_evidence_emergencies` | 70 | 35 | 35 | **50.0%** | **Thất bại do triệu chứng cấp tính cô lập bị xem là thiếu tin** |
| `cross_domain_compositions` | 50 | 30 | 20 | **60.0%** | **Thất bại do tổ hợp bệnh nền đa khoa không khớp mẫu tĩnh** |
| `toxicology_routing_cases` | 50 | 30 | 20 | **60.0%** | **Thất bại do chất độc/ngộ độc ngoài danh mục từ điển tĩnh** |
| `evolving_multi_turn` | 20 | 20 | 0 | **100.0%** | **Hoàn hảo (Event Ledger tích lũy diễn tiến xuất sắc)** |
| `uncertainty_conflicting_evidence` | 25 | 25 | 0 | **100.0%** | **Hoàn hảo (Cơ chế sàn sinh hiệu bất thường vận hành chuẩn)** |
| `benign_adversarial_controls` | 0 | 0 | 0 | **N/A** | **Hoàn hảo (25/25 Routine $\rightarrow$ 100% Specificity)** |
| **TỔNG CỘNG** | **245** | **152** | **93** | **62.04%** | **93 ca cấp cứu bị under-triage** |

### Nhận định chuyên sâu:
1. **Điểm sáng:** Hệ thống xử lý xuất sắc các ca nhiều lượt thoại (`evolving_multi_turn`: 100%) và các ca có xung đột sinh hiệu rõ ràng (`uncertainty_conflicting_evidence`: 100%), đồng thời không tạo ra bất kỳ báo động giả nào trên tập đối chứng (`benign_adversarial_controls`: 100% Specificity).
2. **Điểm tối:** Sự sụt giảm độ nhạy tập trung toàn bộ ở 4 nhóm đầu, đặc biệt là `indirect_linguistic_descriptions` (chỉ đạt 40.0%) và `partial_evidence_emergencies` (chỉ đạt 50.0%).

---

## 5. Ma Trận Replay Từng Tầng Của 93 Ca Cấp Cứu Bị Bỏ Sót

Replay toàn bộ 93 ca qua chuỗi xử lý:
$$\text{Raw Input} \rightarrow \text{Fact Parser} \rightarrow \text{Semantic Abstraction} \rightarrow \text{Partial Evidence Guard} \rightarrow \text{Threat Graph / Tox} \rightarrow \text{Gate 1} \rightarrow \text{Gate 2} \rightarrow \text{Jev} \rightarrow \text{Resolver}$$

| Điểm thất bại trong chuỗi xử lý (Failure Point) | Số ca gánh chịu | Tỷ lệ (%) | Cơ chế gây lỗi lâm sàng |
|---|:---:|:---:|---|
| **Critical fact không trích xuất được** | 0 | 0.0% | Từ khóa thô vẫn vào bộ đệm văn bản |
| **Fact trích xuất nhưng Semantic Abstraction thiếu** | 0 | 0.0% | Đã gộp vào phân tích Threat Graph |
| **Partial-evidence safety guard không kích hoạt** | **35** | **37.6%** | Bệnh nhân chỉ nói 1 câu ngắn ("nước bọt hơi chảy, tay cầm cốc yếu"), hệ thống coi là "thiếu dữ kiện" và hạ về `ROUTINE` thay vì nâng lên mức `PROVISIONAL EMERGENCY` |
| **Threat Graph / Reasoning hoàn toàn im lặng** | **38** | **40.9%** | Ngôn ngữ mô tả gián tiếp ("như có đá tảng đè", "nhìn một hóa hai", "chân tay như mượn của ai") không kích hoạt các nút trong Threat Graph |
| **Toxicology Reasoner hoàn toàn im lặng** | **20** | **21.5%** | Chất độc tự nhiên (nấm lạ rừng, củ ấu tàu, lá ngón, hóa chất tẩy rửa không nhãn mác) không khớp với từ khóa hóa dược tĩnh |
| **Physiologic consequence sai/thiếu** | 0 | 0.0% | Hệ thống quy nạp sinh lý phụ thuộc vào đầu vào của Threat Graph |
| **Gate 1 under-triage đơn thuần** | 0 | 0.0% | Khi Threat Graph im lặng thì Gate 1 tự động trả về ROUTINE |
| **Gate 2 không cứu được** | 93 | 100.0% | Gate 2 chỉ kích hoạt khi có kích hoạt ban đầu |
| **Jev không cứu được** | 93 | 100.0% | Do upstream state hoàn toàn rỗng |
| **Final Resolver thất bại** | 0 | 0.0% | Bộ giải quyết đơn điệu Max hoạt động đúng 100% |
| **Oracle Ambiguity (Nghi ngờ nhãn chuẩn)** | 0 | 0.0% | 100% các ca cấp cứu đều có chỉ định y khoa rõ ràng |

---

## 6. Làm Rõ Đo Lường Độ Trễ (Latency Dissection: 0.26ms vs 53ms)

Tránh nhầm lẫn giữa vi đo nội trình (In-Process micro-benchmark) và độ trễ đầu cuối toàn diện (End-to-End API latency):

| Thành phần đo lường | Độ trễ trung bình | Bản chất xử lý |
|---|:---:|---|
| **1. Clinical Fact Parser + Normalizer** | **~0.84 ms** | Regex, tách từ tiếng Việt, chuẩn hóa dấu, teencode |
| **2. Threat Graph + Consequence + Toxicology** | **~87.0 ms** | Duyệt đồ thị đe dọa, suy luận độc chất, quy nạp sinh lý đa tầng |
| **3. Jev / Tri-Gate Micro-Decision Pipeline** | **~0.05 ms** | Phân loại rủi ro in-memory, kiểm tra bất biến an toàn |
| **4. Final Deterministic Resolver** | **~0.004 ms** | Phép toán so sánh thứ tự ưu tiên đơn điệu Max |
| **TỔNG NỘI TRÌNH IN-PROCESS (Pure CPU Pipeline)** | **~87.9 ms** | **Toàn bộ pipeline logic chạy thuần CPU in-process** |
| **Blind V8 Runner Timing (0.26ms)** | **0.26 ms (P95)** | **Chỉ đo riêng Cổng 3 Jev + Resolver** trên DecisionState có sẵn |
| **Tri-Gate E2E HTTP Endpoint (53ms)** | **~53.0 ms (P95)** | **Đo toàn trình qua FastAPI / HTTP**: Serialization JSON + Pydantic validation + Ghi bản ghi kiểm toán SQLite (`cdec_<hex>`) |

*Khẳng định:* Cả hai benchmark đều chạy trên logic thuật toán nội bộ, **hoàn toàn không gọi LLM bên ngoài**, đảm bảo khả năng tái lập và không phụ thuộc mạng.

---

## 7. Prescription OCR: An Toàn Đạt Chuẩn — Năng Lực Cần Hỗ Trợ

Kết quả từ bộ benchmark lâm sàng 10 kịch bản đơn thuốc (`DS-PRESCRIPTION-OCR`):

```text
Prescription OCR Safety Invariant:
  - Unsafe Auto-Accept Count: 0 (Đạt tiêu chuẩn y tế tuyệt đối)
  - Trạng thái an toàn: PASS

Prescription OCR Autonomous Extraction:
  - Drug Identification Recall: 45.00% (9/20 hoạt chất nhận diện đúng)
  - Đơn thuốc chữ viết tay, chụp nghiêng, thiếu sáng bị từ chối tự động
  - Trạng thái tự hành: NOT READY

CHẾ ĐỘ VẬN HÀNH QUY ĐỊNH:
  Mode: PENDING_REVIEW / Human-In-The-Loop Assisted Extraction
  (Bắt buộc dược sĩ / bác sĩ đối soát và phê duyệt trước khi nhập vào hồ sơ hoặc sinh lịch nhắc)
```

---

## 8. Phân Tách Hai Giai Đoạn Shadow Mode

Với độ nhạy cấp cứu unseen đạt 62.04%, **tuyệt đối không áp dụng MedGuard để đưa ra chỉ định trực tiếp cho người bệnh**. Lộ trình triển khai được chuẩn hóa thành 2 giai đoạn:

```text
                         ┌────────────────────────────────────────────────────────┐
                         │              CHƯA ĐẠT UNSEEN GATE V8                   │
                         └──────────────────────────┬─────────────────────────────┘
                                                    │
                                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ GIAI ĐOẠN 1: SHADOW MODE A — HỒI CỨU / NGOẠI TUYẾN (Retrospective / Offline)                                   │
│  - Nguồn dữ liệu: Hồ sơ bệnh án lịch sử đã được khử định danh (De-identified historical cases).                 │
│  - Cơ chế: So sánh đối đầu giữa quyết định phân loại thực tế của Bác sĩ và dự đoán ngầm của MedGuard.           │
│  - An toàn: Tuyệt đối 0% rủi ro cho người bệnh (Zero clinical exposure).                                        │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                    │
                                  Vượt qua chu kỳ kiểm định Blind V9
                                                    │
                                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ GIAI ĐOẠN 2: SHADOW MODE B — TIỀN CỨU CHẠY NGẦM TẠI PHÒNG KHÁM (Prospective Silent)                            │
│  - Vận hành tại: Phòng khám đối tác BookingCare trong ca trực thực tế.                                          │
│  - Bác sĩ và bệnh nhân vận hành quy trình thông thường; MedGuard lắng nghe và ghi nhận dự đoán ngầm.            │
│  - Tuyệt đối ẩn kết quả đối với bác sĩ (Silent operation); đối soát tỷ lệ đồng thuận sau ca trực.               │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                    │
                                         Hội đồng y khoa nghiệm thu
                                                    │
                                                    ▼
                                     CONTROLLED CLINICAL PILOT
```

---

## 9. Khung Chẩn Đoán Khái Quát Hóa (Generalization Framework) & Chiến Lược V9

Lịch sử từ V4 đến V8 chỉ ra một quy luật rõ ràng:
$$\text{Thêm rules thủ công} \rightarrow \text{Regression đạt 100\%} \rightarrow \text{Gặp Blind mới} \rightarrow \text{Generalization sụt giảm}$$

Do đó, **không được tiếp tục sửa 93 ca miss bằng 93 if-else mới**. MedGuard thiết lập **Khung Chẩn Đoán Biến Dạng Ngữ Nghĩa (Metamorphic Generalization Framework)**:

### 9.1 Khung kiểm thử Metamorphic Testing
Với mỗi phát biểu cấp cứu bị bỏ sót:
1. Sinh tự động 20 biến thể tương đương ngữ nghĩa (Semantic-equivalent transformations):
   - Thay đổi đại từ nhân xưng, phương ngữ Bắc - Trung - Nam.
   - Chuyển từ mô tả triệu chứng y khoa sang cảm giác dân dã ("đè nghẹt", "đau như dao đâm", "choáng váng xây xẩm").
   - Đảo trật tự câu, thêm yếu tố nhiễu cảm xúc ("tôi lo quá", "không biết có sao không bác sĩ").
2. Đo lường tính bất biến trong quyết định (Decision Invariance):
   $$\text{Invariance Rate} = \frac{\text{Số biến thể giữ nguyên mức EMERGENCY}}{20} \ge 98\%$$

### 9.2 Ba cụm cải tiến kiến trúc cho V9 (V9 Architecture by Failure Cluster)
Thay vì vá víu 93 rule lẻ, V9 sẽ tái cấu trúc 3 thành phần cốt lõi:

* **Cụm 1: Semantic Concept Projection Lattice (Giải quyết 38 ca Threat Graph im lặng)**  
  Xây dựng lưới ánh xạ khái niệm đa tầng (concept lattice), kết nối các biểu đạt dân gian tiếng Việt phong phú về các nút tổn thương đích (Target Organ Damage nodes: Cerebral Ischemia, Myocardial Infarction, Airway Obstruction).

* **Cụm 2: Provisional Acute Sentinel Guard (Giải quyết 35 ca Partial Evidence bị sót)**  
  Tái thiết lập luật an toàn: Khi xuất hiện một triệu chứng cấp tính có entropy cao (High-entropy acute sign: ví dụ tê liệt nửa mặt, mất ngôn ngữ đột ngột, sưng phù môi cấp tính), hệ thống **bắt buộc áp sàn Provisional EMERGENCY** thay vì đánh giá là thiếu dữ liệu. An toàn y tế ưu tiên bảo vệ tính mạng hơn là chờ đủ thông tin.

* **Cụm 3: Systemic Toxidrome Ontology (Giải quyết 20 ca Toxicology im lặng)**  
  Chuyển đổi từ nhận diện danh từ chất độc tĩnh sang nhận diện **Hội chứng Độc học Hệ thống (Systemic Toxidromes)**: Cholinergic, Anticholinergic, Sympathomimetic, Opioid, và Caustic/Corrosive Ingestion dựa trên phức hợp triệu chứng lâm sàng.

---

## 10. Tiêu Chuẩn Nghiệm Thu Bắt Buộc Trước Khi Đóng Băng Blind V9

Candidate V9 chỉ được phép đóng băng (Freeze) và cấp phép bước vào kỳ kiểm định mù mới (Blind V9) khi thỏa mãn toàn bộ 7 tiêu chuẩn định lượng khắt khe:

1. **Kho hồi quy lịch sử mở rộng (Historical 2,100 Cases):**  
   - Pure T4 Under-triage = **0 vi phạm** (100% bảo toàn).  
   - Routine Specificity $\ge$ **95.0%**.
2. **Kiểm thử bất biến ngữ nghĩa (Metamorphic Transformations):**  
   - T4 Decision Invariance $\ge$ **98.0%** trên 20 biến thể cho mỗi mẫu bệnh.
3. **Bộ kiểm thử triệu chứng cô lập (Partial-Evidence Holdout):**  
   - Recall $\ge$ **99.0%** trên các ca cấp cứu chỉ có một dấu hiệu đơn lẻ.
4. **Bộ kiểm thử độc chất học (Toxicology Routing Holdout):**  
   - Recall $\ge$ **98.0%** trên các ca ngộ độc không điển hình.
5. **Bộ kiểm thử dữ liệu mơ hồ (Uncertainty Holdout):**  
   - Unsafe Downgrade = **0 ca**.
6. **Thuộc tính nhân quả của Cổng 3 Jev (Jev Counterfactual Attribution):**  
   - Correct $\rightarrow$ Wrong = **0 ca**.  
   - Counterfactual Net Benefit $\ge$ **0**.
7. **Độ chuẩn định xác suất (Probability Calibration):**  
   - Out-of-fold Expected Calibration Error (OOF ECE) < **0.08**.

---
*Báo cáo được niêm phong lưu trữ trong hồ sơ kỹ thuật đồ án tốt nghiệp — Đảm bảo tính trung thực, chuẩn mực khoa học và an toàn người bệnh.*
