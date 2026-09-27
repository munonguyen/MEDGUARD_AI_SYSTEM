"""Safety Kernel for MedGuard AI System.

Phase 3.1 Architecture Invariant:
1. Complete Independence: Runs parallel/prior to any reasoning agent.
2. 100% Deterministic: NO generative model, NO hallucination risk, execution latency < 1 ms.
3. Monotonic Emergency Floor: If Safety Kernel triggers an emergency lock, NO downstream
   agent (Reasoning Agent, Critic, or Jev) has authority to downgrade or remove it.
4. Non-Debatable Hard Directives: Outputs unambiguous mandatory actions (e.g. Call 115).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any
from app.models.intake import CompiledClinicalIntake
from app.models.safety import SafetyKernelResult


def _clean_text(text: str) -> str:
    """Normalize text for reliable deterministic keyword and regex matching."""
    norm = unicodedata.normalize("NFKD", text.lower())
    # remove combining diacritical marks and map Vietnamese stroke 'đ' to 'd'
    no_marks = "".join(c for c in norm if not unicodedata.combining(c)).replace("đ", "d")
    return f" {text.lower()} | {no_marks} "



class SafetyKernel:
    """Deterministic Safety Floor Kernel: Identifies hard life-threats & contraindications."""

    @classmethod
    def evaluate(
        cls,
        intake_or_text: CompiledClinicalIntake | str,
        patient_context: dict[str, Any] | None = None,
    ) -> SafetyKernelResult:
        if isinstance(intake_or_text, CompiledClinicalIntake):
            raw_text = intake_or_text.raw_query
            positives = intake_or_text.clinical_form.positive_findings
            anatomical = intake_or_text.clinical_form.anatomical_sites
        else:
            raw_text = str(intake_or_text)
            positives = []
            anatomical = []

        norm = _clean_text(raw_text)
        triggered_rules: list[str] = []
        hard_red_flags: list[str] = []
        med_blocks: list[str] = []
        mandatory_actions: list[str] = []

        # 1. Stroke / FAST Syndrome
        fast_markers = [
            ("meo mieng", "Méo miệng / lệch mặt cấp tính"),
            ("liet nua nguoi", "Yếu liệt nửa người đột ngột"),
            ("te nua nguoi", "Tê bì yếu nửa người"),
            ("noi do", "Nói đớ, khó nói đột ngột"),
            ("khong noi duoc", "Mất ngôn ngữ / không nói được đột ngột"),
            ("stroke", "Dấu hiệu nghi ngờ đột quỵ não FAST"),
        ]
        for marker, desc in fast_markers:
            if marker in norm:
                triggered_rules.append("SK_STROKE_FAST")
                hard_red_flags.append(desc)
                break

        # 2. Acute Coronary Syndrome (ACS) / Severe Chest Pain
        is_acs = (
            ("dau nguc" in norm or "that nguc" in norm or "nhoi mau co tim" in norm)
            and ("lan tay trai" in norm or "lan cam" in norm or "de nang" in norm or "va mo hoi" in norm or "kho tho" in norm or "bop nghet" in norm)
        ) or any(m in norm for m in ["nhoi mau co tim", "bop nghet nguc", "dau that nguc"])
        if is_acs:
            triggered_rules.append("SK_CARDIAC_ACS")
            hard_red_flags.append("Hội chứng vành cấp nghi ngờ (đau ngực đè nặng, lan tay trái/khó thở/vã mồ hôi)")


        # 3. Anaphylaxis Pattern
        anaphylaxis_conditions = (
            ("kho tho" in norm or "tho rit" in norm or "stridor" in norm)
            and ("di ung" in norm or "noi me day" in norm or "phu moi" in norm or "phu mat" in norm or "sau khi uong" in norm or "sau khi tiem" in norm)
        )
        if anaphylaxis_conditions or "soc phan ve" in norm:
            triggered_rules.append("SK_ANAPHYLAXIS")
            hard_red_flags.append("Phản ứng phản vệ nguy kịch đường thở")

        # 4. Thunderclap Severe Sudden Headache
        thunderclap_markers = [
            ("set danh", "Đau đầu dữ dội như sét đánh"),
            ("dau dau du doi chua tung co", "Đau đầu dữ dội nhất trong đời"),
            ("chua tung dau nhu vay", "Đau đầu đột ngột dữ dội chưa từng có"),
            ("dau dau set danh", "Hội chứng đau đầu sét đánh nghi xuất huyết dưới nhện"),
        ]
        for marker, desc in thunderclap_markers:
            if marker in norm:
                triggered_rules.append("SK_THUNDERCLAP_HEADACHE")
                hard_red_flags.append(desc)
                break

        # 5. Massive Hemorrhage / Critical Bleeding
        bleeding_markers = [
            ("non ra mau", "Nôn ra máu tươi hoặc máu đen"),
            ("ho ra mau", "Ho ra máu lượng nhiều"),
            ("chay mau khong cam", "Chảy máu ồ ạt không cầm được"),
            ("di ngoai phan den nhu ba ca phe", "Xuất huyết tiêu hóa nghi ngờ"),
        ]
        for marker, desc in bleeding_markers:
            if marker in norm:
                triggered_rules.append("SK_CRITICAL_BLEEDING")
                hard_red_flags.append(desc)
                break

        # 6. Critical Dyspnea / Respiratory Failure
        dyspnea_markers = [
            ("khong tho duoc", "Khó thở dữ dội, nghẹt thở"),
            ("tim tai", "Tím tái môi đầu chi do thiếu oxy"),
            ("spo2 duoi 90", "Độ bão hòa oxy SpO2 < 90%"),
            ("spo2 < 90", "Độ bão hòa oxy SpO2 nguy kịch"),
        ]
        for marker, desc in dyspnea_markers:
            if marker in norm:
                triggered_rules.append("SK_RESPIRATORY_FAILURE")
                hard_red_flags.append(desc)
                break

        # 7. Medication Hard Blocks & Absolute Contraindications
        if "aspirin" in norm and any(k in norm for k in ["sot xuat huyet", "loet da day", "chay mau", "xuat huyet"]):
            triggered_rules.append("SK_DRUG_ASPIRIN_BLEEDING")
            med_blocks.append("CHỐNG CHỈ ĐỊNH: Tuyệt đối không dùng Aspirin khi có nguy cơ xuất huyết hoặc sốt xuất huyết.")

        if any(k in norm for k in ["paracetamol", "panadol", "hapacol", "efferalgan"]):
            dose_match = re.search(r"(\d+)\s*(vien|g|gam|gram)", norm)
            if dose_match:
                val = int(dose_match.group(1))
                unit = dose_match.group(2)
                if (unit in ["g", "gam", "gram"] and val >= 4) or (unit == "vien" and val >= 8):
                    triggered_rules.append("SK_PARACETAMOL_OVERDOSE")
                    hard_red_flags.append("Nguy cơ ngộ độc Paracetamol cấp (quá liều > 4g/ngày)")

        # Compile Kernel Result
        emergency_lock = len(hard_red_flags) > 0
        if emergency_lock:
            minimum_triage = "EMERGENCY"
            mandatory_actions.extend([
                "Gọi ngay cấp cứu 115 hoặc đến ngay cơ sở y tế gần nhất có khoa Cấp cứu",
                "Tuyệt đối không tự lái xe hoặc di chuyển một mình",
                "Nghỉ ngơi tại chỗ trong tư thế thoải mái nhất, nới lỏng quần áo",
            ])
            disposition = "EMERGENCY_LOCK_ACTIVE"
        elif any(rule.startswith("SK_DRUG") for rule in triggered_rules):
            minimum_triage = "URGENT"
            mandatory_actions.append("Ngừng ngay việc sử dụng thuốc bị cảnh báo chống chỉ định và tham vấn bác sĩ")
            disposition = "MEDICATION_ALERT_ACTIVE"
        else:
            minimum_triage = "ROUTINE"
            disposition = "SAFE_ROUTINE"

        return SafetyKernelResult(
            emergency_lock=emergency_lock,
            minimum_triage=minimum_triage,
            hard_red_flags=hard_red_flags,
            medication_hard_blocks=med_blocks,
            mandatory_actions=mandatory_actions,
            triggered_rules=triggered_rules,
            disposition=disposition,
        )
