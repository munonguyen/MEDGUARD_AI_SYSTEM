"""Composition policy for simultaneous self-harm and medical emergencies."""

from __future__ import annotations

from dataclasses import dataclass
import re

from app.services.clinical_text import normalize_search_text
from app.services.clinical_text import contains_affirmed_phrase


@dataclass(frozen=True)
class DualCrisisAssessment:
    self_harm_crisis: bool
    medical_emergency: bool
    crisis_support_required: bool
    emergency_triage_required: bool

    @property
    def is_dual_crisis(self) -> bool:
        return self.self_harm_crisis and self.medical_emergency


def evaluate_dual_crisis(text: str, *, clinical_emergency: bool = False) -> DualCrisisAssessment:
    norm = normalize_search_text(text)
    self_harm = any(contains_affirmed_phrase(norm, phrase) for phrase in (
        "tu tu", "tu sat", "tu hai", "muon chet", "khong muon song",
        "cat mach", "treo co", "nhay lau", "nhay cau",
    ))
    if re.search(r"\bkhong\s+(?:lien quan(?: den)?|phai do)\s+tu sat\b", norm):
        self_harm = False
    harmful_action = bool(re.search(
        r"\b(?:uong|nuot|dung|tiem|cat)\b.{0,55}\b(?:vien|voc|ca vi|qua lieu|thuoc|"
        r"amlodipine|paracetamol|thuoc ngu|thuoc ha ap|chat doc|hoa chat|mach mau)\b",
        norm,
    ))
    completed_or_symptomatic = bool(re.search(
        r"\b(?:da uong|vua uong|moi uong|uong nham|nuot phai|\d+\s*vien|nhieu vien|"
        r"voc|ca vi|qua lieu|ngo doc|huyet ap tut|lo mo|li bi|lanh ngat|tho cham|kho danh thuc)\b",
        norm,
    ))
    active_ingestion_or_injury = harmful_action and completed_or_symptomatic
    explicitly_no_action = bool(re.search(
        r"\b(?:chua|khong)\s+(?:uong|nuot|dung|tiem|cat|lam)\b.{0,40}\b(?:thuoc|minh|bi thuong)\b",
        norm,
    ))
    if explicitly_no_action:
        active_ingestion_or_injury = False
    medical = clinical_emergency or active_ingestion_or_injury
    return DualCrisisAssessment(
        self_harm_crisis=self_harm,
        medical_emergency=medical,
        crisis_support_required=self_harm,
        emergency_triage_required=self_harm and medical,
    )


def compose_dual_crisis_response(crisis_reply: str) -> str:
    """Medical action always precedes supportive crisis resources."""
    return (
        "🚨 **CẤP CỨU Y TẾ NGAY — GỌI 115.** Có nguy cơ quá liều/ngộ độc hoặc tổn thương "
        "đe dọa tính mạng. Nhờ người ở cạnh gọi 115, đưa đến khoa Cấp cứu ngay, không tự lái xe, "
        "không gây nôn và không chờ triệu chứng tự hết.\n\n"
        "Đồng thời, bạn xứng đáng được hỗ trợ qua khủng hoảng này:\n\n"
        f"{crisis_reply}"
    )
