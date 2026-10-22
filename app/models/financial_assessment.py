from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

TransactionSourceType = Literal[
    "gpp_pharmacy",      # Chuỗi nhà thuốc chuẩn GPP (Pharmacity, Long Châu, An Khang...)
    "hospital_clinic",   # Nhà thuốc bệnh viện / Phòng khám chuyên khoa
    "unofficial_retail", # Tiệm thuốc tự do, liều lẻ không hóa đơn/chứng nhận
    "online_unknown",    # Mua thuốc qua mạng không rõ nguồn gốc
]

TransactionCategory = Literal[
    "medication",            # Đơn thuốc điều trị
    "doctor_visit",          # Công khám bác sĩ / Đặt lịch Booking Care
    "diagnostic_test",       # Xét nghiệm / Chẩn đoán hình ảnh
    "recurrence_treatment",  # Chi phí phát sinh do tái phát bệnh / đợt cấp
    "emergency",             # Cấp cứu / Điều trị nội trú
]

SafetyTier = Literal[
    "normal",                    # Bình thường, an toàn tối ưu chi phí
    "caution",                   # Cần theo dõi, không tự ý giảm liều
    "urgent_medical_attention",  # Có dấu hiệu cờ đỏ, bắt buộc khám chuyên khoa
    "emergency",                 # Cấp cứu khẩn cấp, bỏ qua mọi tính toán tiết kiệm
]

RecommendationType = Literal[
    "gpp_adherence",         # Tuân thủ mua nguồn GPP chuẩn để dứt điểm bệnh
    "generic_substitution",  # Dùng thuốc Generic tương đương sinh học giá bình ổn
    "early_booking",         # Đặt lịch khám sớm tránh biến chứng tốn kém
    "bhyt_optimization",     # Tối ưu thông tuyến BHYT giảm 80-100%
    "preventive_care",       # Chăm sóc dự phòng tiết kiệm dài hạn
]

RecommendationPriority = Literal["high", "medium", "standard"]


class FinancialTransaction(BaseModel):
    id: str
    date: str
    title: str
    amount_vnd: int
    source_type: TransactionSourceType = "gpp_pharmacy"
    source_name: str
    category: TransactionCategory = "medication"
    is_official_gpp: bool = True
    recurrence_flag: bool = False
    clinical_notes: str = ""


class SafetyVerificationStatus(BaseModel):
    is_safe: bool = True
    red_flags_detected: list[str] = Field(default_factory=list)
    safety_tier: SafetyTier = "normal"
    tone_sentiment_score: float = 0.95
    blocked_phrases_found: list[str] = Field(default_factory=list)
    clinical_override_applied: bool = False
    safety_guideline_message: str = (
        "Ưu tiên điều trị an toàn tuyệt đối. Tiết kiệm tài chính là tối ưu phương thức "
        "(thuốc chuẩn, khám đúng chuyên khoa, dùng BHYT) chứ tuyệt đối không trì hoãn khám bệnh."
    )


class SpendingBreakdown(BaseModel):
    total_spent_vnd: int = 0
    gpp_official_spent_vnd: int = 0
    unofficial_spent_vnd: int = 0
    doctor_booking_spent_vnd: int = 0
    recurrence_waste_spent_vnd: int = 0
    recurrence_waste_percentage: float = 0.0


class SmartRecommendation(BaseModel):
    id: str
    type: RecommendationType
    title: str
    description: str
    estimated_savings_vnd: int = 0
    clinical_rationale: str
    priority: RecommendationPriority = "medium"
    action_cta: str | None = None
    target_view: str | None = None


class MonthlyFinancialAssessment(BaseModel):
    patient_ref: str = "guest_patient"
    month_year: str = "10/2026"
    breakdown: SpendingBreakdown = Field(default_factory=SpendingBreakdown)
    safety_status: SafetyVerificationStatus = Field(default_factory=SafetyVerificationStatus)
    treatment_efficiency_score: int = Field(default=82, ge=0, le=100)
    health_roi_rank: Literal["A+", "A", "B", "C", "D"] = "A"
    projected_monthly_savings_vnd: int = 0
    transactions: list[FinancialTransaction] = Field(default_factory=list)
    recommendations: list[SmartRecommendation] = Field(default_factory=list)
    clinical_summary: str = ""
    last_updated: str = Field(default_factory=lambda: datetime.now().isoformat())
