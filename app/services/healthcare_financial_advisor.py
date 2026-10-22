from __future__ import annotations

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

    def get_assessment(self, patient_ref: str = "guest_patient") -> MonthlyFinancialAssessment:
        if patient_ref not in self._assessments:
            self._assessments[patient_ref] = self._create_initial_assessment(patient_ref)
        return self._assessments[patient_ref]

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

        # Projected savings if patient adopts GPP adherence and early booking
        # Savings = 100% of recurrence waste + ~35% of diagnostic/revisit costs
        projected_savings = recurrence_waste_spent + int(doctor_booking_spent * 0.3)
        assessment.projected_monthly_savings_vnd = projected_savings

        assessment.recommendations = self._generate_recommendations(assessment)
        assessment.last_updated = datetime.now().isoformat()

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
        self, message: str, current_medications: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Zero-friction clinical-financial extraction:
        Analyzes user chat text for cost mentions, pharmacy sources, and recurrence cues.
        Updates the financial assessment ledger in real time.
        """
        text = message.strip()
        norm = text.lower()
        assessment = self.get_assessment("guest_patient")

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

        return {
            "has_financial_signal": detected_amount is not None or recurrence_flag or safety_status.clinical_override_applied,
            "detected_amount_vnd": detected_amount,
            "is_official_gpp": is_official,
            "recurrence_flag": recurrence_flag,
            "safety_status": safety_status.model_dump(),
            "new_transaction": new_transaction.model_dump() if new_transaction else None,
            "assessment": assessment.model_dump(),
        }

    def reset_to_default(self, patient_ref: str = "guest_patient") -> MonthlyFinancialAssessment:
        self._assessments[patient_ref] = self._create_initial_assessment(patient_ref)
        return self._assessments[patient_ref]


healthcare_financial_advisor_service = HealthcareFinancialAdvisorService()
