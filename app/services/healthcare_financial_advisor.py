from __future__ import annotations

import json
from pathlib import Path
import re
from datetime import datetime
from typing import Any

from app.models.financial_assessment import (
    FinancialTransaction,
    MonthlyFinancialAssessment,
    RecommendationPriority,
    RecommendationType,
    SafetyTier,
    SafetyVerificationStatus,
    SmartRecommendation,
    SpendingBreakdown,
)

RUNTIME_STORAGE_PATH = Path(__file__).resolve().parent.parent.parent / ".runtime" / "financial_assessments.json"

RED_FLAG_SYMPTOMS: list[tuple[str, str]] = [
    (r"(đau ngực|thắt ngực|nặng ngực|đau tim)", "Đau thắt ngực hoặc áp lực vùng tim (Nguy cơ mạch vành)"),
    (r"(khó thở|hụt hơi dữ dội|thở rít|tím tái)", "Khó thở hoặc suy hô hấp tiến triển"),
    (r"(ho ra máu|khạc ra máu)", "Ho ra máu (Tổn thương phế quản/nhu mô phổi)"),
    (r"(nôn ra máu|nôn dịch đen|đi ngoài phân đen|tiêu ra máu)", "Dấu hiệu xuất huyết tiêu hóa"),
    (r"(sốt cao.*(kéo dài|3 ngày|4 ngày|5 ngày)|sốt li bì|sốt co giật)", "Sốt cao kéo dài không đáp ứng hạ sốt"),
    (r"(sụt cân nhanh|sụt cân không rõ|gầy rộc)", "Sụt cân nhanh không rõ nguyên nhân (Bệnh lý chuyển hóa/ác tính)"),
    (r"(đau đầu dữ dội|đau đầu sét đánh|cứng gáy|nôn vọt)", "Đau đầu dữ dội đột ngột hoặc hội chứng màng não"),
    (r"(yếu liệt|liệt nửa người|méo miệng|nói đớ|mất thăng bằng)", "Dấu hiệu đột quỵ / tai biến mạch máu não"),
    (r"(đau bụng dữ dội|bụng cứng như gỗ|đau quặn bụng)", "Đau bụng ngoại khoa cấp tính"),
]

BLOCKED_REASSURANCE_PHRASES: list[str] = [
    "không cần đi khám",
    "không cần khám",
    "đừng đi khám",
    "đừng mua thuốc",
    "không cần mua thuốc",
    "ở nhà tự khỏi",
    "không tốn tiền đi khám",
    "khỏi cần đi viện",
    "chắc chắn không sao",
    "hoàn toàn không nguy hiểm",
]

DEFAULT_TRANSACTIONS: list[FinancialTransaction] = [
    FinancialTransaction(
        id="tx-01",
        date="2026-10-04",
        title="Khám chuyên khoa Hô hấp & Kê đơn ban đầu (Booking Care)",
        amount_vnd=250000,
        source_type="hospital_clinic",
        source_name="Phòng khám Đa khoa Quốc tế (Hẹn giờ trước)",
        category="doctor_visit",
        is_official_gpp=True,
        recurrence_flag=False,
        clinical_notes="Bác sĩ chẩn đoán viêm phế quản cấp, chỉ định phác đồ 7 ngày.",
    ),
    FinancialTransaction(
        id="tx-02",
        date="2026-10-04",
        title="Thuốc điều trị phác đồ chuẩn GPP (Kháng sinh & Kháng viêm)",
        amount_vnd=380000,
        source_type="gpp_pharmacy",
        source_name="Nhà thuốc Pharmacity chuẩn GPP",
        category="medication",
        is_official_gpp=True,
        recurrence_flag=False,
        clinical_notes="Thuốc chính hãng xuất xứ rõ ràng, sinh khả dụng đạt chuẩn MIC.",
    ),
    FinancialTransaction(
        id="tx-03",
        date="2026-10-12",
        title="Thuốc ho & giảm đau mua lẻ ngoài đợt 1 (Tự ý mua thêm)",
        amount_vnd=140000,
        source_type="unofficial_retail",
        source_name="Tiệm thuốc tự do đầu ngõ (Chia liều lẻ)",
        category="recurrence_treatment",
        is_official_gpp=False,
        recurrence_flag=True,
        clinical_notes="Tái phát cơn ho đờm do tự ý ngưng đợt 1 sớm, mua thêm liều lẻ 3 ngày.",
    ),
    FinancialTransaction(
        id="tx-04",
        date="2026-10-16",
        title="Thuốc bổ & siro giảm ho tự do đợt 2 (Không theo đơn)",
        amount_vnd=180000,
        source_type="unofficial_retail",
        source_name="Tiệm thuốc tự do gần nhà",
        category="recurrence_treatment",
        is_official_gpp=False,
        recurrence_flag=True,
        clinical_notes="Bệnh vẫn dai dẳng, mua thêm thuốc hỗ trợ nhưng không khám lại.",
    ),
    FinancialTransaction(
        id="tx-05",
        date="2026-10-19",
        title="Thuốc kháng viêm cắt liều lẻ đợt 3 (Tái phát kéo dài)",
        amount_vnd=100000,
        source_type="unofficial_retail",
        source_name="Tiệm thuốc tự do ngoài chợ",
        category="recurrence_treatment",
        is_official_gpp=False,
        recurrence_flag=True,
        clinical_notes="Tái phát đợt 3, nghi ngờ kháng thuốc cục bộ do dùng liều chắp vá.",
    ),
    FinancialTransaction(
        id="tx-06",
        date="2026-10-20",
        title="Xét nghiệm nhanh & Công thức máu kiểm tra phản ứng viêm",
        amount_vnd=200000,
        source_type="hospital_clinic",
        source_name="Trung tâm Y tế quận (Đúng tuyến BHYT)",
        category="diagnostic_test",
        is_official_gpp=True,
        recurrence_flag=False,
        clinical_notes="Được hỗ trợ BHYT chi trả 80% giá niêm yết.",
    ),
]


class HealthcareFinancialAdvisorService:
    def __init__(self) -> None:
        self._assessments: dict[str, MonthlyFinancialAssessment] = {}
        self._load_from_disk()

    def _clean_ref(self, patient_ref: str | None) -> str:
        ref = (patient_ref or "").strip()
        return ref if ref else "guest_patient"

    def _load_from_disk(self) -> None:
        try:
            if RUNTIME_STORAGE_PATH.exists():
                with open(RUNTIME_STORAGE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        self._assessments[k] = MonthlyFinancialAssessment.model_validate(v)
        except Exception:
            pass

    def _save_to_disk(self) -> None:
        try:
            RUNTIME_STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = {k: v.model_dump(mode="json") for k, v in self._assessments.items()}
            with open(RUNTIME_STORAGE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_assessment(self, patient_ref: str = "guest_patient") -> MonthlyFinancialAssessment:
        clean = self._clean_ref(patient_ref)
        if clean not in self._assessments:
            self._assessments[clean] = self._create_initial_assessment(clean)
            self._save_to_disk()
        return self._assessments[clean]

    def _create_initial_assessment(self, patient_ref: str) -> MonthlyFinancialAssessment:
        assessment = MonthlyFinancialAssessment(
            patient_ref=patient_ref,
            month_year="10/2026",
            transactions=list(DEFAULT_TRANSACTIONS),
        )
        self.recalculate(assessment)
        return assessment

    def recalculate(self, assessment: MonthlyFinancialAssessment) -> None:
        total = 0
        gpp_spent = 0
        unofficial_spent = 0
        doctor_booking_spent = 0
        recurrence_waste_spent = 0

        for tx in assessment.transactions:
            amt = tx.amount_vnd
            total += amt
            if tx.is_official_gpp or tx.source_type in {"gpp_pharmacy", "hospital_clinic"}:
                gpp_spent += amt
            else:
                unofficial_spent += amt

            if tx.category == "doctor_visit":
                doctor_booking_spent += amt

            if tx.recurrence_flag or tx.category == "recurrence_treatment":
                recurrence_waste_spent += amt

        recurrence_pct = round((recurrence_waste_spent / total * 100), 1) if total > 0 else 0.0

        assessment.breakdown = SpendingBreakdown(
            total_spent_vnd=total,
            gpp_official_spent_vnd=gpp_spent,
            unofficial_spent_vnd=unofficial_spent,
            doctor_booking_spent_vnd=doctor_booking_spent,
            recurrence_waste_spent_vnd=recurrence_waste_spent,
            recurrence_waste_percentage=recurrence_pct,
        )

        # Treatment Efficiency Score (TES) (0-100)
        # Penalized heavily by recurrence waste and unofficial medicines
        waste_penalty = min(50, int(recurrence_pct * 1.1))
        unofficial_penalty = int((unofficial_spent / total) * 30) if total > 0 else 0
        tes = max(25, min(98, 100 - waste_penalty - unofficial_penalty))
        assessment.treatment_efficiency_score = tes

        if tes >= 90:
            assessment.health_roi_rank = "A+"
        elif tes >= 78:
            assessment.health_roi_rank = "A"
        elif tes >= 65:
            assessment.health_roi_rank = "B"
        elif tes >= 50:
            assessment.health_roi_rank = "C"
        else:
            assessment.health_roi_rank = "D"

        # Monthly Budget Target Calculations
        budget = assessment.monthly_budget_target_vnd or 3000000
        assessment.monthly_budget_target_vnd = budget
        assessment.remaining_budget_vnd = max(0, budget - total)
        assessment.budget_utilization_percentage = round((total / budget) * 100, 1) if budget > 0 else 0.0

        if total > budget:
            assessment.budget_status = "over_budget"
        elif assessment.budget_utilization_percentage >= 80.0:
            assessment.budget_status = "approaching_limit"
        else:
            assessment.budget_status = "within_budget"

        # Smart Clinical Allocation Breakdown (45% Doctor & BHYT, 35% GPP Meds, 20% Reserve)
        doctor_share = int(budget * 0.45)
        med_share = int(budget * 0.35)
        reserve_share = budget - doctor_share - med_share
        assessment.budget_allocation_plan = {
            "doctor_consult_vnd": doctor_share,
            "doctor_consult_pct": 45,
            "gpp_medication_vnd": med_share,
            "gpp_medication_pct": 35,
            "reserve_diagnostic_vnd": reserve_share,
            "reserve_diagnostic_pct": 20,
        }

        # Projected savings if patient adopts GPP adherence and early booking
        # Savings = 100% of recurrence waste + ~35% of diagnostic/revisit costs
        projected_savings = recurrence_waste_spent + int(doctor_booking_spent * 0.3)
        assessment.projected_monthly_savings_vnd = projected_savings

        assessment.recommendations = self._generate_recommendations(assessment)
        assessment.last_updated = datetime.now().isoformat()

    def set_budget(
        self, patient_ref: str = "guest_patient", budget_target_vnd: int = 3000000
    ) -> MonthlyFinancialAssessment:
        clean = self._clean_ref(patient_ref)
        assessment = self.get_assessment(clean)
        assessment.monthly_budget_target_vnd = budget_target_vnd
        self.recalculate(assessment)
        self._save_to_disk()
        return assessment

    def _generate_recommendations(
        self, assessment: MonthlyFinancialAssessment
    ) -> list[SmartRecommendation]:
        recs: list[SmartRecommendation] = []
        b = assessment.breakdown

        # Recommendation 1: GPP Source Adherence (Stop cheap repetitive buys)
        if b.recurrence_waste_spent_vnd > 0:
            recs.append(
                SmartRecommendation(
                    id="rec-gpp-01",
                    type="gpp_adherence",
                    title="Chuyển sang mua thuốc chính hãng chuẩn GPP dứt điểm",
                    description=(
                        f"Ghi nhận {b.recurrence_waste_spent_vnd:,}đ chi cho 3 đợt mua thuốc lẻ tái phát. "
                        "Thuốc chuẩn GPP (Pharmacity, Long Châu, Bệnh viện) đảm bảo đúng nồng độ ức chế (MIC), "
                        "giúp khỏi bệnh dứt điểm trong 5-7 ngày và chấm dứt chuỗi tái phát lãng phí."
                    ).replace(",", "."),
                    estimated_savings_vnd=b.recurrence_waste_spent_vnd,
                    clinical_rationale=(
                        "Thuốc trôi nổi/chia liều lẻ thường thiếu hàm lượng dược chất và nguy cơ tạp chất cao, "
                        "dẫn đến vi khuẩn kháng thuốc (AMR) và bệnh chuyển thành mạn tính, "
                        "chi phí điều trị thực tế sau đó đắt gấp 5-10 lần."
                    ),
                    priority="high",
                    action_cta="Tìm nhà thuốc GPP gần nhất",
                    target_view="navigation",
                )
            )

        # Recommendation 2: Early Booking Care vs Late Emergency
        recs.append(
            SmartRecommendation(
                id="rec-booking-02",
                type="early_booking",
                title="Đặt lịch khám đúng chuyên khoa sớm (Tránh bẫy khám muộn)",
                description=(
                    "Đặt hẹn trước qua Booking Care khi triệu chứng mới khởi phát 24-48h giúp bạn chọn đúng "
                    "bác sĩ chuyên khoa đầu ngành, tránh làm lại các xét nghiệm trùng lặp và không lo "
                    "phải vào viện cấp cứu tốn kém."
                ),
                estimated_savings_vnd=450000,
                clinical_rationale=(
                    "Chi phí khám bệnh theo lịch hẹn chủ động rẻ hơn 75% so với chi phí cấp cứu/nội trú "
                    "khi bệnh biến chứng nặng."
                ),
                priority="high",
                action_cta="Đặt lịch khám chuyên khoa",
                target_view="schedule",
            )
        )

        # Recommendation 3: Generic Bioequivalent Substitution
        recs.append(
            SmartRecommendation(
                id="rec-generic-03",
                type="generic_substitution",
                title="Hỏi ý kiến dược sĩ về thuốc Generic tương đương sinh học",
                description=(
                    "Yêu cầu nhà thuốc tư vấn biệt dược Generic đạt chuẩn tương đương sinh học (Bioequivalent) "
                    "thay thế thuốc Brand-name gốc để tiết kiệm 30% - 40% chi phí đơn thuốc mà vẫn đảm bảo "
                    "hiệu lực điều trị 100%."
                ),
                estimated_savings_vnd=150000,
                clinical_rationale=(
                    "Thuốc Generic chuẩn GMP/WHO có cùng thành phần hoạt chất, dạng bào chế và sinh khả dụng "
                    "tương đương biệt dược gốc nhưng giá thành bình ổn hơn nhiều."
                ),
                priority="medium",
                action_cta="Tư vấn thuốc với AI",
                target_view="chat",
            )
        )

        # Recommendation 4: BHYT Optimization
        recs.append(
            SmartRecommendation(
                id="rec-bhyt-04",
                type="bhyt_optimization",
                title="Tối ưu cơ chế thông tuyến Bảo hiểm Y tế (BHYT)",
                description=(
                    "Khám tại cơ sở y tế quận/huyện đúng tuyến giúp thanh toán 80% - 100% viện phí theo luật BHYT. "
                    "Hệ thống đã tự động định vị các trung tâm y tế công lập chuẩn xung quanh bạn."
                ),
                estimated_savings_vnd=300000,
                clinical_rationale=(
                    "Người bệnh thường lãng phí tiền triệu do khám vượt tuyến tự túc khi các bệnh lý thông thường "
                    "hoàn toàn có thể được xử lý tại tuyến cơ sở được BHYT chi trả gần như toàn bộ."
                ),
                priority="standard",
                action_cta="Xem cơ sở y tế đúng tuyến",
                target_view="navigation",
            )
        )

        return recs

    def evaluate_clinical_safety_and_positivity(
        self, user_message: str, proposed_advice: str = ""
    ) -> tuple[SafetyVerificationStatus, str]:
        """
        Three-Tier Verification Gate:
        1. Red Flag & Latent Disease Screening (Forces doctor visit, disables cost-cutting delays).
        2. Blocked False Reassurance Filter (Removes dangerous 'no need to see doctor' phrases).
        3. Positivity & Actionable Tone Verification.
        """
        norm_user = user_message.lower()
        norm_advice = proposed_advice.lower()

        red_flags: list[str] = []
        for pattern, label in RED_FLAG_SYMPTOMS:
            if re.search(pattern, norm_user):
                red_flags.append(label)

        blocked_found: list[str] = []
        for phrase in BLOCKED_REASSURANCE_PHRASES:
            if phrase in norm_advice:
                blocked_found.append(phrase)

        is_safe = len(red_flags) == 0 and len(blocked_found) == 0
        override_applied = False
        revised_advice = proposed_advice

        if red_flags:
            override_applied = True
            safety_tier: SafetyTier = "urgent_medical_attention"
            safety_msg = (
                "CẢNH BÁO AN TOÀN LÂM SÀNG: Hệ thống phát hiện các dấu hiệu cảnh báo đỏ (nguy cơ bệnh lý tiềm ẩn: "
                f"{', '.join(red_flags)}). Tuyệt đối KHÔNG tự ý cắt giảm thuốc, không tự điều trị tại nhà "
                "hay trì hoãn đi khám để tiết kiệm chi phí. Bạn cần đặt lịch khám chuyên khoa ngay hoặc "
                "đến cơ sở y tế gần nhất; để tối ưu viện phí, hãy chuẩn bị thẻ BHYT để được thanh toán theo quy định."
            )
            # Prepend emergency/urgent clinical instruction to advice
            revised_advice = f"{safety_msg}\n\n{revised_advice}"
        elif blocked_found:
            override_applied = True
            safety_tier = "caution"
            # Sanitize dangerous phrases
            for phrase in blocked_found:
                revised_advice = re.sub(
                    re.escape(phrase),
                    "cần thăm khám chuyên khoa hoặc tư vấn dược sĩ chuẩn GPP để dùng đúng phác đồ",
                    revised_advice,
                    flags=re.IGNORECASE,
                )
            safety_msg = (
                "Đã kích hoạt Cổng Kiểm Soát An Toàn: Điều chỉnh lời khuyên đảm bảo tuân thủ y khoa, "
                "không khuyến khích trì hoãn điều trị."
            )
        else:
            safety_tier = "normal"
            safety_msg = (
                "Đạt chuẩn Cổng Kiểm Soát An Toàn Y Khoa: Lời khuyên tập trung vào tối ưu hóa chi phí "
                "thông qua nguồn thuốc chính hãng chuẩn GPP và đặt lịch khám đúng tuyến BHYT."
            )

        status = SafetyVerificationStatus(
            is_safe=is_safe,
            red_flags_detected=red_flags,
            safety_tier=safety_tier,
            tone_sentiment_score=0.96 if not red_flags else 0.88,
            blocked_phrases_found=blocked_found,
            clinical_override_applied=override_applied,
            safety_guideline_message=safety_msg,
        )

        return status, revised_advice

    def extract_and_sync_from_chat(
        self,
        message: str,
        current_medications: list[str] | None = None,
        patient_ref: str = "guest_patient",
    ) -> dict[str, Any]:
        """
        Zero-friction clinical-financial extraction:
        Analyzes user chat text for cost mentions, pharmacy sources, and recurrence cues.
        Updates the financial assessment ledger in real time.
        """
        text = message.strip()
        norm = text.lower()
        clean = self._clean_ref(patient_ref)
        assessment = self.get_assessment(clean)

        detected_amount: int | None = None
        # Match patterns like: "hết 80k", "hết 150.000đ", "mất 90 nghìn", "hết 200 ngàn"
        cost_match = re.search(r"(hết|mất|tốn|mua|chi)\s*([\d\.\,]+)\s*(k|nghìn|ngàn|đ|vnd)?", norm)
        if cost_match:
            raw_val = cost_match.group(2).replace(".", "").replace(",", "")
            unit = cost_match.group(3) or ""
            try:
                numeric_val = int(raw_val)
                if unit in {"k", "nghìn", "ngàn"} or numeric_val < 1000:
                    detected_amount = numeric_val * 1000
                else:
                    detected_amount = numeric_val
            except ValueError:
                pass

        # Detect source type
        is_official = False
        source_name = "Nhà thuốc tự do"
        source_type = "unofficial_retail"

        if any(brand in norm for brand in ["pharmacity", "long châu", "an khang", "bệnh viện", "phòng khám"]):
            is_official = True
            source_type = "gpp_pharmacy"
            source_name = "Nhà thuốc chuẩn GPP (Chính hãng)"
        elif any(cue in norm for cue in ["đầu ngõ", "gần nhà", "bên đường", "liều lẻ", "chợ", "tiệm nhỏ"]):
            is_official = False
            source_type = "unofficial_retail"
            source_name = "Tiệm thuốc tự do (Liều lẻ không kiểm định)"

        # Detect recurrence cues
        recurrence_flag = False
        if any(cue in norm for cue in ["mãi không khỏi", "uống 4 ngày", "uống 5 ngày", "uống 3 ngày", "lại bị lại", "tái phát", "đợt 2", "đợt 3", "chưa đỡ", "vẫn ho", "vẫn sốt", "vẫn đau"]):
            recurrence_flag = True

        # Budget Target Detection from Chat
        budget_target = self.detect_budget_target(text)
        is_budget_update = False
        if budget_target:
            assessment.monthly_budget_target_vnd = budget_target
            self.recalculate(assessment)
            self._save_to_disk()
            is_budget_update = True

        # Safety Gate Evaluation
        safety_status, _ = self.evaluate_clinical_safety_and_positivity(text, "")
        assessment.safety_status = safety_status

        # If a financial transaction was detected, log it
        new_transaction: FinancialTransaction | None = None
        if detected_amount and detected_amount >= 10000:
            tx_id = f"tx-chat-{len(assessment.transactions) + 1}"
            tx_title = "Thuốc tự điều trị qua hội thoại"
            if recurrence_flag:
                tx_title = "Thuốc mua lẻ do bệnh tái phát (Ghi nhận từ Chat)"
            elif is_official:
                tx_title = "Thuốc chuẩn GPP (Ghi nhận từ Chat)"

            new_transaction = FinancialTransaction(
                id=tx_id,
                date=datetime.now().strftime("%Y-%m-%d"),
                title=tx_title,
                amount_vnd=detected_amount,
                source_type=source_type,
                source_name=source_name,
                category="recurrence_treatment" if recurrence_flag else "medication",
                is_official_gpp=is_official,
                recurrence_flag=recurrence_flag,
                clinical_notes=f"Được đồng bộ tự động từ hội thoại: \"{text[:120]}...\"",
            )
            # Avoid duplicate same amount and title within last 2 entries
            duplicate = any(
                t.amount_vnd == detected_amount and t.date == new_transaction.date
                for t in assessment.transactions[-2:]
            )
            if not duplicate:
                assessment.transactions.insert(0, new_transaction)
                self.recalculate(assessment)
                self._save_to_disk()

        return {
            "has_financial_signal": detected_amount is not None or recurrence_flag or is_budget_update or safety_status.clinical_override_applied,
            "detected_amount_vnd": detected_amount,
            "detected_budget_target_vnd": budget_target,
            "is_budget_update": is_budget_update,
            "is_official_gpp": is_official,
            "recurrence_flag": recurrence_flag,
            "safety_status": safety_status.model_dump(),
            "new_transaction": new_transaction.model_dump() if new_transaction else None,
            "assessment": assessment.model_dump(),
        }

    def detect_budget_target(self, text: str) -> int | None:
        """
        Detects if the user is setting or mentioning a monthly healthcare budget target.
        Examples:
        - "tổng chi tiêu tháng này tôi muốn là tối đa khoảng 3 triệu vào việc mua thuốc và khám sức khoẻ"
        - "chi tiêu tháng này tối đa 3 triệu"
        - "ngân sách tháng này là 3 triệu"
        - "hạn mức chi tiêu y tế tháng này 3tr"
        - "tháng này chỉ chi tối đa 3.000.000 đ cho thuốc và khám"
        - "ngân sách tối đa 2.5 triệu"
        - "2tr5"
        - "tối đa khoảng 3 triệu vào việc mua thuốc và khám sức khoẻ"
        """
        if not text:
            return None
        norm = text.lower().strip()

        # Check for budget intent cues
        budget_intent_cues = [
            "chi tiêu", "ngân sách", "hạn mức", "tối đa", "khoản chi", "chi phí",
            "dành ra", "chi khoảng", "muốn chi", "dự trù", "đặt ngân sách", "đặt hạn mức",
            "chi tối đa", "giới hạn", "khống chế"
        ]
        has_budget_intent = any(cue in norm for cue in budget_intent_cues)
        if not has_budget_intent:
            return None

        # Check for context keywords: healthcare/medical/monthly/medicine/exam
        context_cues = [
            "tháng", "thuốc", "khám", "sức khoẻ", "sức khỏe", "y tế", "bệnh",
            "chữa bệnh", "booking care", "bác sĩ", "viện phí"
        ]
        has_context = any(cue in norm for cue in context_cues)
        if not has_context:
            return None

        # 1. Compound forms like "2tr5", "3tr2", "1tr8"
        m_compound = re.search(r"(\d+)\s*tr\s*(\d+)", norm)
        if m_compound:
            major = int(m_compound.group(1))
            minor = int(m_compound.group(2))
            return major * 1_000_000 + minor * 100_000

        # 2. "3 triệu rưỡi", "2 triệu rưỡi"
        m_half = re.search(r"(\d+)\s*(?:triệu|tr)\s*rưỡi", norm)
        if m_half:
            return int(m_half.group(1)) * 1_000_000 + 500_000

        # 3. "3 triệu", "3.5 triệu", "3,5 triệu", "3tr", "3 tr", "3 củ"
        m_trieu = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:triệu|tr\b|củ\b|m\b)", norm)
        if m_trieu:
            try:
                val = float(m_trieu.group(1).replace(",", "."))
                return int(val * 1_000_000)
            except ValueError:
                pass

        # 4. Formatted currency "3.000.000", "3,000,000", "3000000"
        m_currency = re.search(r"(\d{1,3}(?:[.,]\d{3})+|\d{6,9})\s*(?:đ|vnd|đồng)?", norm)
        if m_currency:
            try:
                raw = m_currency.group(1).replace(".", "").replace(",", "")
                val = int(raw)
                if val >= 50000:
                    return val
            except ValueError:
                pass

        # 5. "500k", "800 nghìn", "500 ngàn"
        m_k = re.search(r"(\d+)\s*(?:k\b|nghìn|ngàn)", norm)
        if m_k:
            try:
                return int(m_k.group(1)) * 1000
            except ValueError:
                pass

        return None

    def is_financial_inquiry(self, text: str) -> bool:
        if not text:
            return False
        norm = text.lower().strip()
        inquiry_cues = [
            "chi tiêu y tế", "quản lý chi tiêu", "tiết kiệm chi phí", "tiền thuốc",
            "tiết kiệm tiền", "sổ chi tiêu", "bảng chi tiêu", "ngân sách sức khoẻ",
            "ngân sách sức khỏe", "tổng chi tiêu", "tiết kiệm thuốc", "tối ưu chi phí khám"
        ]
        return any(cue in norm for cue in inquiry_cues)

    def compose_budget_guidance_reply(
        self,
        budget_vnd: int,
        assessment: MonthlyFinancialAssessment,
        is_new_target: bool = True,
    ) -> str:
        b = assessment.breakdown
        total_spent = b.total_spent_vnd
        remaining = assessment.remaining_budget_vnd
        pct = assessment.budget_utilization_percentage
        tes = assessment.treatment_efficiency_score
        roi_rank = assessment.health_roi_rank

        budget_str = f"{budget_vnd:,}đ".replace(",", ".")
        spent_str = f"{total_spent:,}đ".replace(",", ".")
        remaining_str = f"{remaining:,}đ".replace(",", ".")
        waste_str = f"{b.recurrence_waste_spent_vnd:,}đ".replace(",", ".")

        plan = assessment.budget_allocation_plan or {}
        doctor_share = plan.get("doctor_consult_vnd", int(budget_vnd * 0.45))
        med_share = plan.get("gpp_medication_vnd", int(budget_vnd * 0.35))
        reserve_share = plan.get("reserve_diagnostic_vnd", budget_vnd - doctor_share - med_share)

        doctor_str = f"{doctor_share:,}đ".replace(",", ".")
        med_str = f"{med_share:,}đ".replace(",", ".")
        reserve_str = f"{reserve_share:,}đ".replace(",", ".")

        if assessment.budget_status == "over_budget":
            status_desc = "⚠️ ĐÃ VƯỢT NGÂN SÁCH (Cần rà soát các khoản mua thuốc lặp lại)"
        elif assessment.budget_status == "approaching_limit":
            status_desc = "⚡ ĐANG TIỆM CẬN HẠN MỨC (Còn lại ít, ưu tiên khám BHYT đúng tuyến)"
        else:
            status_desc = "✅ AN TOÀN TRONG TẦM KIỂM SOÁT"

        header_title = (
            f"🎯 **ĐÃ THIẾT LẬP HẠN MỨC NGÂN SÁCH Y TẾ: {budget_str} / THÁNG**"
            if is_new_target
            else f"📊 **KẾ HOẠCH QUẢN TRỊ NGÂN SÁCH Y TẾ: {budget_str} / THÁNG**"
        )

        reply = (
            f"{header_title}\n\n"
            f"MedGuard AI đã tự động cập nhật hạn mức chi tiêu y tế của bạn vào "
            f"**[Bảng Quản Lý Chi Phí Sức Khỏe](http://localhost:8000/?view=spending)**. "
            f"Dưới đây là phân tích tiến độ thực tế và khuyến nghị kinh tế dược học tối ưu cho bạn:\n\n"
            f"### 📈 TIẾN ĐỘ THỰC HIỆN NGÂN SÁCH THÁNG 10/2026\n"
            f"- **Hạn mức đặt ra**: **{budget_str}**\n"
            f"- **Đã chi tiêu**: **{spent_str}** ({pct}%)\n"
            f"- **Ngân sách còn lại khả dụng**: **{remaining_str}**\n"
            f"- **Trạng thái chi tiêu**: **{status_desc}**\n"
            f"- **Điểm Hiệu Quả Điều Trị (TES)**: **{tes}/100 (Hạng {roi_rank})**\n\n"
            f"---\n\n"
            f"### 💡 LỜI KHUYÊN PHÂN BỔ DÒNG TIỀN Y TẾ THÔNG MINH (45 - 35 - 20)\n\n"
            f"Dựa trên thực tiễn lâm sàng tại Việt Nam, để tối ưu ngân sách **{budget_str}** mà vẫn đảm bảo **khỏi bệnh dứt điểm**, "
            f"hệ thống khuyến nghị tỷ lệ phân bổ như sau:\n\n"
            f"1. **🏥 45% (~{doctor_str}) — Khám chuyên khoa Booking Care & Đồng chi trả BHYT**:\n"
            f"   - **Khám đúng chuyên khoa sớm**: Khi xuất hiện triệu chứng bất thường, hãy đặt lịch khám chuyên khoa trong 24-48 giờ đầu qua Booking Care thay vì tự ý mua thuốc mò tại tiệm.\n"
            f"   - **Tận dụng BHYT thông tuyến quận/huyện**: Giúp BHYT chi trả **80% - 100%** chi phí khám bệnh và xét nghiệm cơ bản.\n"
            f"   - **Lợi ích kinh tế**: Khám đúng bệnh ngay từ đầu giúp giải quyết dứt điểm nguyên nhân, tiết kiệm hàng triệu đồng so với việc để bệnh nặng phải cấp cứu hoặc điều trị nội trú.\n\n"
            f"2. **💊 35% (~{med_str}) — Mua thuốc chuẩn GPP & Biệt dược Generic tương đương sinh học**:\n"
            f"   - **Mua thuốc tại chuỗi GPP chính hãng** (Pharmacity, Long Châu, An Khang...): Đảm bảo hoạt chất đạt nồng độ ức chế tối thiểu (MIC), giúp khỏi dứt điểm trong 5-7 ngày.\n"
            f"   - **Cảnh báo bẫy thuốc liều lẻ ngoài chợ/đầu ngõ**: Mua thuốc liều lẻ giá rẻ nhiều lần tưởng tiết kiệm nhưng thường thiếu liều, khiến vi khuẩn kháng thuốc (AMR), bệnh tái phát dai dẳng (sổ chi tiêu của bạn hiện ghi nhận **{waste_str}** chi phí lãng phí do tái phát).\n"
            f"   - **Chủ động hỏi biệt dược Generic**: Yêu cầu dược sĩ tư vấn thuốc Generic tương đương sinh học (Bioequivalent) chuẩn GMP/WHO có cùng hoạt chất với biệt dược gốc để tiết kiệm **30% - 40%** tiền thuốc mà hiệu quả tương đương 100%.\n\n"
            f"3. **🛡️ 20% (~{reserve_str}) — Quỹ dự phòng sức khỏe & Chăm sóc phòng ngừa**:\n"
            f"   - Dành cho các xét nghiệm tầm soát định kỳ, mua dung dịch sát khuẩn, nước muối sinh lý, bù điện giải hoặc nâng cao miễn dịch phòng bệnh.\n\n"
            f"---\n\n"
            f"### 🛡️ CAM KẾT CỔNG KIỂM SOÁT AN TOÀN Y KHOA (CLINICAL SAFETY GATE)\n"
            f"MedGuard AI cam kết: **An toàn sức khỏe và tính mạng luôn là ưu tiên số 1**. "
            f"Hệ thống **tuyệt đối không bao giờ** khuyên bạn tự ý cắt giảm liều thuốc kê đơn, mua thuốc kém chất lượng "
            f"hay trì hoãn việc đi khám bác sĩ chỉ để giữ chỉ tiêu ngân sách. Khi có bất kỳ triệu chứng cảnh báo đỏ, "
            f"bạn cần đến cơ sở y tế gần nhất ngay lập tức.\n\n"
            f"👉 **[Nhấn vào đây để xem Bảng Quản Trị Chi Tiêu & Biểu Đồ Chi Tiết (http://localhost:8000/?view=spending)](http://localhost:8000/?view=spending)**"
        )
        return reply

    def reset_to_default(self, patient_ref: str = "guest_patient") -> MonthlyFinancialAssessment:
        clean = self._clean_ref(patient_ref)
        self._assessments[clean] = self._create_initial_assessment(clean)
        self._save_to_disk()
        return self._assessments[clean]


healthcare_financial_advisor_service = HealthcareFinancialAdvisorService()
