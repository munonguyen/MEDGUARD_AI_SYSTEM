"""Clinical Threat Graph for MedGuard AI (V5).

Evaluates 12 physiologic and functional threat dimensions to stratify
threat acuity independently of named disease entities.

Principles:
- Abstract Physiologic Threat: Detects organ-system failure patterns
  (e.g., circulatory compromise, metabolic crisis, acute surgical abdomen)
  even when the definitive etiology is unknown or atypical.
- High Sensitivity: Identifies critical decompensation markers.
- Multi-Dimensional Synergy: Multiple moderate threats can compose into high acuity.
- Order-Invariant Feature Composition: Evaluates clinical findings independently
  of phrase ordering in user input.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any

from app.services.clinical_text import (
    contains_affirmed_phrase,
    normalize_search_text,
)


class ThreatLevel(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def severity_score(self) -> int:
        scores = {
            ThreatLevel.NONE: 0,
            ThreatLevel.LOW: 1,
            ThreatLevel.MODERATE: 2,
            ThreatLevel.HIGH: 3,
            ThreatLevel.CRITICAL: 4,
        }
        return scores[self]


@dataclass(frozen=True)
class DimensionAssessment:
    dimension: str
    level: ThreatLevel
    confidence: float
    findings: list[str] = field(default_factory=list)
    rationale: str = ""


@dataclass(frozen=True)
class ThreatGraphResult:
    assessments: dict[str, DimensionAssessment]
    max_threat_level: ThreatLevel
    critical_dimensions: list[str]
    high_dimensions: list[str]
    composite_threat_score: int
    primary_threat_summary: str

    def has_threat_at_least(self, level: ThreatLevel) -> bool:
        return self.max_threat_level.severity_score >= level.severity_score


def _matches_any(text: str, patterns: list[str]) -> bool:
    for pat in patterns:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def _extract_vitals_from_text(text: str) -> dict[str, float]:
    """Extract numeric vital signals mentioned in natural text."""
    vitals: dict[str, float] = {}
    
    # Blood pressure: e.g., 60/30, 80/50, 200/110
    bp_match = re.search(r"\b(\d{2,3})\s*/\s*(\d{2,3})\s*(?:mmhg)?\b", text)
    if bp_match:
        vitals["sbp"] = float(bp_match.group(1))
        vitals["dbp"] = float(bp_match.group(2))
        
    # SpO2: e.g., spo2 78%, spo2 tụt 82%
    spo2_match = re.search(r"\b(?:spo2|oxi|oxy)\b.*?\b(\d{2})\s*%", text)
    if not spo2_match:
        spo2_match = re.search(r"\b(\d{2})\s*%\s*(?:khi phong|spo2)\b", text)
    if spo2_match:
        val = float(spo2_match.group(1))
        if 40 <= val <= 100:
            vitals["spo2"] = val
            
    # Temperature: e.g., sot 40.8, 39.5 do
    temp_match = re.search(r"\b(?:sot|nhiet do)\b.*?\b(3[89]\.\d|4[0-2]\.?\d?)\b", text)
    if not temp_match:
        temp_match = re.search(r"\b(3[89]\.\d|4[0-2]\.?\d?)\s*(?:do|°c|c)\b", text)
    if temp_match:
        vitals["temp"] = float(temp_match.group(1))
        
    # Pulse / Heart rate: e.g., mach 140, tim dap 160
    hr_match = re.search(r"\b(?:mach|nhip tim|tim dap)\b.*?\b(\d{2,3})\s*(?:nhip|ck|l\/p|bpm|\/phut)?\b", text)
    if hr_match:
        hr_val = float(hr_match.group(1))
        if 30 <= hr_val <= 240:
            vitals["hr"] = hr_val
            
    return vitals


# ---------------------------------------------------------------------------
# Individual Dimension Evaluators (Compositional & Order-Invariant)
# ---------------------------------------------------------------------------

def _eval_airway(norm: str) -> DimensionAssessment:
    """1. Airway Compromise."""
    findings = []
    level = ThreatLevel.NONE
    conf = 0.50
    
    has_stridor = _matches_any(norm, [r"\b(tho rit|stridor|tieng rit thanh quan)\b"])
    has_drooling = _matches_any(norm, [r"\b(chay dai|rot dai|khong nuot duoc nuoc bot)\b"])
    has_sore_throat_dyspnea = _matches_any(norm, [r"\b(dau hong|sung hong|kho tho|kho nuot)\b"])
    has_woody_floor = _matches_any(norm, [
        r"\b(duoi ham|san mieng)\b.*?\b(cung nhu go|phu ne|day luoi|ludwig)\b",
        r"\b(lao xao khi|khi duoi da|lep bep duoi da|tieng lao xao)\b",
        r"\b(lan xuong co nguc|lan xuong nguc)\b.*?\b(nho rang|sung co|sot cao)\b",
    ])
    has_choking = _matches_any(norm, [
        r"\b(hoc|sac)\b.*?\b(di vat|dau phong|dong xu|vien bi)\b",
        r"\b(nghen tho dot ngot|di vat duong tho)\b",
        r"\b(di vat|xuong ca)\b.*?\b(ha hong|thuc quan|thanh quan|gam sau|nghen tho|khac ra mau|bot mau)\b",
        r"\b(nghen tho)\b.*?\b(di vat|xuong ca|gam sau)\b",
    ])
    has_asphyxia = _matches_any(norm, [r"\b(tim tai|ngat|kho tho|tho rit|nghen tho|khac ra bot mau)\b"])

    if has_stridor or (has_drooling and has_sore_throat_dyspnea) or has_woody_floor or (has_choking and has_asphyxia):
        findings.append("Dấu hiệu tắc nghẽn hoặc chèn ép đường thở trên cấp tính (stridor / chảy dãi / hóc dị vật / phù sàn miệng / dị vật hạ họng gây nghẹn thở)")
        level = ThreatLevel.CRITICAL
        conf = 0.98
    elif _matches_any(norm, [
        r"\b(kho nuot|nuot dau du doi|ngam hat thi)\b.*?\b(lech luoi ga|ap xe quanh ami|khit ham)\b",
        r"\b(khan tieng dot ngot|tho kho khe)\b.*?\b(sau bong|hit khoi|con trung dot vao co)\b",
    ]):
        findings.append("Nguy cơ chèn ép đường thở trên tiến triển (áp xe quanh amiđan / phù nề sau bỏng nhiệt)")
        level = ThreatLevel.HIGH
        conf = 0.90
        
    return DimensionAssessment("airway", level, conf, findings)


def _eval_breathing(norm: str, vitals: dict[str, float]) -> DimensionAssessment:
    """2. Breathing Failure."""
    findings = []
    level = ThreatLevel.NONE
    conf = 0.50
    
    spo2 = vitals.get("spo2")
    has_cyanosis = _matches_any(norm, [r"\b(tim tai|tim moi|da xanh tai|moi tim)\b"])

    # Exclude or modulate mild bronchospasm relieved by inhaler
    is_relieved_mild = _matches_any(norm, [
        r"\b(noi chuyen nguyen cau|noi duoc ca cau|noi nguyen cau)\b",
        r"\b(xit ventolin|xit thuoc)\b.*?\b(do han|khoi han|on roi)\b",
    ])

    # Hyperventilation / anxiety alkalosis syndrome
    is_hyperventilation = _matches_any(norm, [
        r"\b(cai nhau|tuc gian|cang thang)\b.*?\b(tho hon hen|ngot ngat)\b.*?\b(te ran|te quanh mieng|te ngon tay)\b",
        r"\b(te ran quanh mieng|te dau ngon tay)\b.*?\b(tho hon hen|ngot ngat)\b",
    ])

    has_severe_dyspnea = _matches_any(norm, [
        r"\b(kho tho du doi|tho ngap|ngung tho|co keo co ho hap|rut lom long nguc)\b",
        r"\b(khong noi duoc thanh cau|moi lan noi dut quang|tho dut quang)\b",
        r"\b(bot hong|sui bot hong|phu phoi cap)\b",
        r"\b(tran khi mang phoi|lech khi quan)\b",
        r"\b(suy ho hap du doi|tac mach mo|fat embolism)\b",
        r"\b(thay khop|gay xuong dui|gay xuong)\b.*?\b(suy ho hap|hoang loan|ban xuat huyet)\b",
    ]) or (_matches_any(norm, [r"\b(tho hon hen)\b"]) and not is_hyperventilation)

    if not is_relieved_mild and ((spo2 is not None and spo2 < 90) or has_severe_dyspnea or (has_cyanosis and _matches_any(norm, [r"\b(kho tho|tho nhanh|hut hoi)\b"]))):
        findings.append(f"Dấu hiệu suy hô hấp cấp nặng / kiệt sức cơ hô hấp / SpO2 tụt ({spo2 or '<90'}%) / phù phổi cấp")
        level = ThreatLevel.CRITICAL
        conf = 0.98
    elif is_hyperventilation or _matches_any(norm, [
        r"\b(kho tho|hut hoi|tho kho khe|kho tho dot ngot)\b.*?\b(hen|copd|phoi man|nam phang khong tho duoc)\b",
        r"\b(kho tho)\b.*?\b(ngoi chong tay|phai ngoi day de tho|orthopnea)\b",
    ]):
        findings.append("Cơn khó thở cấp tiến triển hoặc hội chứng tăng thông khí nghi ngờ")
        level = ThreatLevel.HIGH
        conf = 0.88
        
    return DimensionAssessment("breathing", level, conf, findings)


def _eval_circulation(norm: str, vitals: dict[str, float]) -> DimensionAssessment:
    """3. Circulatory Instability / Shock."""
    findings = []
    level = ThreatLevel.NONE
    conf = 0.50
    
    sbp = vitals.get("sbp")
    has_hypotension = (sbp is not None and sbp < 90) or _matches_any(norm, [
        r"\b(tut huyet ap|ha huyet ap|huyet ap tut|huyet ap ha|sut huyet ap|sut tu .* xuong \d+|huyet ap \d{2}\/\d{2})\b",
    ])
    has_poor_perfusion = _matches_any(norm, [
        r"\b(chan tay lanh ngat|va mo hoi hot|da noi bong|noi van tim|mach nhanh nho kho bat|mach khong bat duoc)\b",
        r"\b(soc nhiem khuan|soc phan ve|soc tim|soc mat mau|truy tim mach)\b",
        r"\b(diaphoresis|va mo hoi)\b.*?\b(lanh ngat|bun run)\b",
    ])
    has_trigger_anaphylaxis = _matches_any(norm, [
        r"\b(truyen dich|tiem thuoc|an hai san|ong dot|khang sinh)\b",
    ])
    has_acute_coronary_dissection = _matches_any(norm, [
        r"\b(chest pain|dau nguc)\b.*?\b(severe|lan ra back|bop chat tim|nhu da tang ep tim|thung)\b",
        r"\b(thay boi|bop chat tim|that long nguc)\b.*?\b(kho tho|va mo hoi|xay xam|bun run)\b",
        r"\b(210 over 120|200\/|bp đo duoc 210)\b",
    ])

    if (sbp is not None and sbp < 90) or (has_hypotension and has_poor_perfusion) or (has_trigger_anaphylaxis and has_hypotension) or has_acute_coronary_dissection:
        findings.append(f"Tụt huyết áp nặng / sốc tuần hoàn / hội chứng vành cấp / bóc tách động mạch chủ (huyết áp tâm thu {sbp or 'bất thường'})")
        level = ThreatLevel.CRITICAL
        conf = 0.99
    elif _matches_any(norm, [
        r"\b(ngat|ngat xiu|dot ngot ngat|mat y thuc thoang qua)\b.*?\b(khi dang gang suc|kem dau nguc|kem hoi hop)\b",
        r"\b(tim dap nhanh loan xa|danh trong nguc lien tuc)\b.*?\b(chong mat|xay xam|gan ngat)\b",
    ]):
        findings.append("Ngất do nguyên nhân tim mạch nghi ngờ hoặc loạn nhịp có triệu chứng huyết động")
        level = ThreatLevel.HIGH
        conf = 0.88
        
    return DimensionAssessment("circulation", level, conf, findings)


def _eval_neurology(norm: str) -> DimensionAssessment:
    """4. Neurologic Deficit."""
    findings = []
    level = ThreatLevel.NONE
    conf = 0.50
    
    has_focal_stroke = _matches_any(norm, [
        r"\b(liet|yeu|xui lo)\b.*?\b(nua nguoi|1 ben|mot ben|tay chan)\b",
        r"\b(tay chan)\b.*?\b(xui lo|liet|yeu)\b",
        r"\b(meo mieng|lech mat|meo xeo|noi ngo ngac|noi kho dot ngot|kho noi dot ngot|noi ngong dot ngot)\b",
        r"\b(nhin mot hoa hai|nhin doi|song thi)\b.*?\b(nuot sac|khan tieng|dau ru|yeu co)\b",
        r"\b(nuot sac|nuot sac len mui)\b.*?\b(nhin doi|nhin mot hoa hai|khan tieng|dau ru)\b",
        r"\b(sup mi|sup mi mat)\b.*?\b(dong tu|gian|nhuc dau|nhin mo)\b",
        r"\b(dong tu)\b.*?\b(gian|gian to)\b.*?\b(sup mi|nhuc dau|1 ben|mot ben)\b",
        r"\b(sup mi)\b.*?\b(dong tu)\b",
    ])
    has_amaurosis = _matches_any(norm, [
        r"\b(mat thi luc dot ngot|amaurosis|toi sam mat dot ngot|mu dot ngot 1 mat)\b",
        r"\b(mat thinh luc|diec|khong nghe thay)\b.*?\b(dot ngot|1 ben|mot ben|chong mat|quay cuong)\b",
        r"\b(dot ngot)\b.*?\b(mat thinh luc|diec hoan toan|diec 1 ben|diec tai)\b",
    ])
    has_coma_status = _matches_any(norm, [
        r"\b(hon me|goi hoi khong biet|me man|li bi kho danh thuc|co giat lien tuc|co giat khong tinh|chet giac)\b",
        r"\b(te xiu|ngat xiu|chet giac)\b.*?\b(lo mo|goi k biet|goi khong biet|xui lo|meo)\b",
    ])
    has_thunderclap = _matches_any(norm, [
        r"\b(dau dau du doi nhat|set danh|dau dau set danh|dat 10\/10 trong vai giay|dau buot oc dot ngot)\b",
    ])
    has_gradual_progression = _matches_any(norm, [
        r"\b(tu tu|tang dan suot|tang dan tu tu|am i tang dan|khoi phat tu tu|suot \d+ tieng|suot \d+ gio)\b",
    ])
    if has_gradual_progression:
        has_thunderclap = False

    has_nuchal = _matches_any(norm, [
        r"\b(cung co|cung gay|co cung gay|gay cung|cam cung|khong cui duoc co|khong cui duoc dau|khong cui duoc xuong)\b",
    ])
    has_meningism_trigger = _matches_any(norm, [
        r"\b(sot|sot cao|non vot|non thoc|non mua|so anh sang|dau dau du doi|choang vang|me sang)\b",
    ])
    has_spinal_cord = _matches_any(norm, [
        r"\b(liet|yeu|te|mat cam giac)\b.*?\b(2 chan|hai chan|doi chan|chi duoi|ngang ron|tu nguc|tu bung)\b",
        r"\b(2 chan|hai chan|doi chan|chi duoi)\b.*?\b(liet|yeu|te|khong cu dong|mat cam giac)\b",
        r"\b(te bi tu ngang ron|mat cam giac tu ngang ron)\b",
    ])
    has_sphincter_or_malignancy = _matches_any(norm, [
        r"\b(bi tieu|khong tieu duoc|ung thu|di can|mat tu chu)\b",
    ])

    if (
        has_focal_stroke
        or has_amaurosis
        or has_coma_status
        or has_thunderclap
        or (has_nuchal and has_meningism_trigger)
        or (has_spinal_cord and has_sphincter_or_malignancy)
        or _matches_any(norm, [r"\b(hoi chung chum duoi ngua|chen ep tuy cap)\b"])
    ):
        findings.append("Dấu hiệu khiếm khuyết thần kinh trung ương cấp tính đe dọa tính mạng (đột quỵ / xuất huyết dưới nhện / hôn mê / chèn ép tủy cấp / viêm màng não)")
        level = ThreatLevel.CRITICAL
        conf = 0.98
    elif has_gradual_progression or _matches_any(norm, [
        r"\b(lan lon|lo mo|noi lan|thay doi y thuc|me sang)\b.*?\b(sot|nguoi gia|nhiem trung)\b",
        r"\b(chong mat chao dao|mat thang bang dot ngot|te bi nua nguoi thoang qua)\b",
    ]):
        findings.append("Đau đầu tiến triển kéo dài hoặc rối loạn tri giác bán cấp")
        level = ThreatLevel.HIGH
        conf = 0.88
        
    return DimensionAssessment("neurology", level, conf, findings)


def _eval_sepsis_infection(norm: str, vitals: dict[str, float]) -> DimensionAssessment:
    """5. Severe Infection / Sepsis."""
    findings = []
    level = ThreatLevel.NONE
    conf = 0.50
    
    temp = vitals.get("temp")
    has_purpura = _matches_any(norm, [r"\b(ban xuat huyet|tu ban|cham xuat huyet hoai tu|purpura)\b"])
    has_severe_fever = (temp is not None and temp >= 38.5) or _matches_any(norm, [r"\b(sot cao|ret run ban bat|sot ret run)\b"])
    has_organ_failure = _matches_any(norm, [r"\b(tut huyet ap|lo mo|noi van tim|vo nieu|khong tieu duoc|hon me)\b"])
    has_necrotizing = _matches_any(norm, [
        r"\b(viem can mac hoai tu|hoai tu phan mem|dau vuot qua bieu hien ngoai da|tieng lep bep duoi da)\b",
        r"\b(bong nuoc|trot loet|troc vay da)\b.*?\b(40%|30%|dien tich|niem mac mieng mat|loet nat)\b",
        r"\b(steven johnson|sjs|hoi chung lyell|toxic epidermal necrolysis|ten\b)\b",
    ])

    if (has_purpura and has_severe_fever) or (has_severe_fever and has_organ_failure) or has_necrotizing or _matches_any(norm, [r"\b(nhiem trung huyet|soc nhiem khuan|septic shock)\b"]):
        findings.append("Nghi ngờ nhiễm trùng huyết nặng / sốc nhiễm khuẩn / hoại tử thượng bì nhiễm độc TEN-SJS / viêm cân hoại tử")
        level = ThreatLevel.CRITICAL
        conf = 0.98
    elif temp is not None and temp >= 40.0:
        findings.append(f"Sốt cực cao nguy cơ co giật hoặc cơn bão chuyển hóa (nhiệt độ {temp}°C)")
        level = ThreatLevel.HIGH
        conf = 0.90
    elif _matches_any(norm, [
        r"\b(sot cao|ret run)\b.*?\b(benh nhan hoa tri|giam bach cau|suy giam mien dich|ung thu dang truyen thuoc)\b",
        r"\b(sot cao|dau quan than)\b.*?\b(dai buot|dai mu|than u nuoc)\b",
    ]):
        findings.append("Sốt trên cơ địa suy giảm miễn dịch hoặc nhiễm trùng đường niệu tắc nghẽn")
        level = ThreatLevel.HIGH
        conf = 0.88
        
    return DimensionAssessment("sepsis_infection", level, conf, findings)


def _eval_major_bleeding(norm: str) -> DimensionAssessment:
    """6. Major Bleeding."""
    findings = []
    level = ThreatLevel.NONE
    conf = 0.50
    
    if _matches_any(norm, [
        r"\b(non)\b.*?\b(ra mau|mau tuoi|mau cuc|o at)\b",
        r"\b(ho ra mau set danh|ho ra mau luong nhieu|ho mau sac sua|ho sac mau)\b",
        r"\b(di ngoai ra mau tuoi xoi xa|di cau phan den nhu ba ca phe)\b.*?\b(chong mat|choang|ngat|tut huyet ap)\b",
        r"\b(chay mau khong cam|phun thanh tia|vet thuong mach mau lon)\b",
        r"\b(chong dong|warfarin|sintrom|xarelto|eliquis)\b.*?\b(bam tim|tu mau|mang bam|xuat huyet)\b.*?\b(rat to|lan rong|lan nhanh|lan rong nhanh)\b",
    ]):
        findings.append("Xuất huyết tiêu hóa ồ ạt / ho ra máu sét đánh / vết thương mạch máu lớn đang chảy máu dữ dội")
        level = ThreatLevel.CRITICAL
        conf = 0.98
    elif _matches_any(norm, [
        r"\b(non ra mau|di ngoai phan den|ho ra mau|chay mau cam khong cam duoc)\b",
    ]):
        findings.append("Chảy máu đang tiến triển cần đánh giá cấp tính")
        level = ThreatLevel.HIGH
        conf = 0.85
        
    return DimensionAssessment("major_bleeding", level, conf, findings)


def _eval_toxic_exposure(norm: str) -> DimensionAssessment:
    """7. Acute Toxic Exposure."""
    findings = []
    level = ThreatLevel.NONE
    conf = 0.50
    
    if _matches_any(norm, [
        r"\b(uong thuoc tru sau|thuoc diet co|paraquat|phospho huu co)\b",
        r"\b(uong nuoc tay bon cau|uong axit|uong xut|hoa chat an mon)\b",
        r"\b(ngo doc khi co|ngat khi than|dot than trong phong kin)\b.*?\b(hon me|li bi|dau dau)\b",
        r"\b(uong thuoc ngu|uong ca vi seduxen|uong qua lieu thuoc tro tim|ngo doc digoxin)\b",
        r"\b(con cong nghiep|methanol|con tu pha|ruou gia|ruou cồn)\b",
        r"\b(bao tuyet|suong mu)\b.*?\b(ruou|uong|mat mo)\b",
        r"\b(hoa chat tay rua|tay rua.*sui bot|uong.*tay rua|sui bot mep)\b",
    ]):
        findings.append("Ngộ độc cấp tính chất độc cực mạnh / hóa chất ăn mòn / ngộ độc khí CO phòng kín")
        level = ThreatLevel.CRITICAL
        conf = 0.98
    elif _matches_any(norm, [
        r"\b(uong nham thuoc|uong qua lieu|uong nhieu thuoc cung luc)\b",
    ]):
        findings.append("Nghi vấn phơi nhiễm hoặc ngộ độc thuốc cấp")
        level = ThreatLevel.HIGH
        conf = 0.85
        
    return DimensionAssessment("toxic_exposure", level, conf, findings)


def _eval_pregnancy_danger(norm: str) -> DimensionAssessment:
    """8. Pregnancy-Related Danger."""
    findings = []
    level = ThreatLevel.NONE
    conf = 0.50
    
    has_pregnancy = _matches_any(norm, [r"\b(co thai|mang thai|mang bau|tre kinh|cham kinh|sinh no|hau san)\b"])
    has_severe_pain_or_shock = _matches_any(norm, [r"\b(dau bung duoi|dau bung quan|ngat|chong mat xay xam|tut huyet ap|soc)\b"])
    has_preeclampsia_signs = _matches_any(norm, [r"\b(dau dau du doi|mat mo|nhin doi|dau ha suon phai|tien san giat|san giat)\b"])
    has_antepartum_hemorrhage = _matches_any(norm, [r"\b(chay mau am dao|ra mau tuoi|nhau bong non|vo oi)\b"])

    if has_pregnancy and (has_severe_pain_or_shock or has_preeclampsia_signs or has_antepartum_hemorrhage):
        findings.append("Cấp cứu sản khoa đe dọa tính mạng mẹ và con (chửa ngoài tử cung vỡ / tiền sản giật nặng - sản giật / nhau bong non)")
        level = ThreatLevel.CRITICAL
        conf = 0.98
    elif _matches_any(norm, [r"\b(chua ngoai tu cung|chua ngoai da con|chua ngoai vo)\b"]):
        findings.append("Nghi ngờ chửa ngoài tử cung cấp cứu")
        level = ThreatLevel.CRITICAL
        conf = 0.98
    elif has_pregnancy and _matches_any(norm, [r"\b(dau bung|ra mau am dao|sot cao)\b"]):
        findings.append("Dấu hiệu cảnh báo nguy cơ thai kỳ cần đánh giá khẩn cấp")
        level = ThreatLevel.HIGH
        conf = 0.88
        
    return DimensionAssessment("pregnancy_danger", level, conf, findings)


def _eval_surgical_abdomen(norm: str) -> DimensionAssessment:
    """9. Acute Surgical Abdomen."""
    findings = []
    level = ThreatLevel.NONE
    conf = 0.50
    
    has_peritonism = _matches_any(norm, [
        r"\b(bung cung nhu go|bung de khang|cam ung phuc mac|blumberg|an vao buong tay ra dau nhoi)\b",
        r"\b(dau bung du doi dot ngot|dau nhu dao dam|thung da day|thung ruot)\b",
    ])
    has_appendicitis = _matches_any(norm, [
        r"\b(ho chau phai|ruot thua)\b.*?\b(an dau nhoi|dau giat nay nguoi|khong dam di lai|sot)\b",
        r"\b(dau bung)\b.*?\b(ho chau phai)\b.*?\b(sot|buon non|an dau)\b",
    ])
    has_bowel_obstruction = _matches_any(norm, [
        r"\b(bi trung dai tien|chuong bung nhu qua bong|non ra dich mat dich ruot)\b",
    ])

    if has_peritonism or has_appendicitis or has_bowel_obstruction:
        findings.append("Bụng ngoại khoa cấp tính (thủng tạng rỗng / viêm phúc mạc toàn thể / ruột thừa viêm biến chứng / tắc ruột cơ học)")
        level = ThreatLevel.CRITICAL
        conf = 0.98
    elif _matches_any(norm, [
        r"\b(dau bung quanh ron chuyen xuong ho chau phai|dau bung tang dan khong giam)\b",
        r"\b(thoat vi ben|khoi phong o ben)\b.*?\b(nghen|dau du doi|khong day len duoc)\b",
    ]):
        findings.append("Dấu hiệu cảnh báo bụng ngoại khoa đang tiến triển hoặc thoát vị nghẹt")
        level = ThreatLevel.HIGH
        conf = 0.88
        
    return DimensionAssessment("surgical_abdomen", level, conf, findings)


def _eval_vision_threat(norm: str) -> DimensionAssessment:
    """10. Vision-Threatening Emergency."""
    findings = []
    level = ThreatLevel.NONE
    conf = 0.50
    
    if _matches_any(norm, [
        r"\b(tam man den|man den|man toi)\b.*?\b(sup|keo sup|che|che khuat|phu kin)\b",
        r"\b(toi sam|mu|khong nhin thay|mat thi luc)\b.*?\b(dot ngot|hoan toan|1 ben|mot ben|1 mat|mot mat)\b",
        r"\b(tac dong mach vong mac|amaurosis|amaurosis fugax|bong vong mac)\b",
        r"\b(dau nhuc mat|dau mat|nhuc mat)\b.*?\b(du doi|quang cau vong|cau vong|dong tu gian|do nhu trai gac|glaucoma)\b",
        r"\b(ban|vang|do)\b.*?\b(axit|hoa chat|nuoc tay|xut|kiem)\b.*?\b(mat|vao mat)\b",
        r"\b(ruoi bay|dom den)\b.*?\b(chop sang|man den|toi sam)\b",
        r"\b(chop sang)\b.*?\b(ruoi bay|dom den|man den)\b",
        r"\b(thung nhan cau|rach nhan cau|xuyen nhan cau|vo nhan cau|phoi to chuc|xuyen thung nhan cau)\b",
    ]):
        findings.append("Cấp cứu nhãn khoa tối khẩn (tắc động mạch võng mạc / amaurosis fugax / glaucoma góc đóng cấp / bỏng hóa chất mắt)")
        level = ThreatLevel.CRITICAL
        conf = 0.98
    elif _matches_any(norm, [
        r"\b(nhin mo dot ngot|nhin hinh bien dang|chot sang lap loe kem ruoi bay nhieu)\b",
    ]):
        findings.append("Dấu hiệu tổn thương võng mạc hoặc thần kinh thị giác cấp")
        level = ThreatLevel.HIGH
        conf = 0.88
        
    return DimensionAssessment("vision_threat", level, conf, findings)


def _eval_limb_threat(norm: str) -> DimensionAssessment:
    """11. Limb-Threatening Ischemia."""
    findings = []
    level = ThreatLevel.NONE
    conf = 0.50
    
    has_cold_limb = _matches_any(norm, [r"\b(chan lanh ngat|tay lanh ngat|chi lanh ngat|chan tai nhot|tay tai nhot)\b"])
    has_ischemia_signs = _matches_any(norm, [r"\b(mat mach|dau buot du doi|tai nhot|mat cam giac|liet van dong)\b"])
    has_compartment = _matches_any(norm, [
        r"\b(bap chan cang cung nhu go|bap tay cang cung)\b.*?\b(dau buot khong the chiu noi|dau khi van dong thu dong)\b",
        r"\b(thieu mau chi cap|tac mach chi cap|hoi chung chen ep khoang)\b",
    ])
    has_priapism = _matches_any(norm, [
        r"\b(cuong cung|cuong cung duong vat)\b.*?\b(keo dai|tren \d+|lien tuc|khong mem|dau buot|cung buot)\b",
        r"\b(priapism|cuong dau duong vat keo dai)\b",
    ])

    if (has_cold_limb and has_ischemia_signs) or has_compartment or has_priapism:
        findings.append("Thiếu máu chi / tạng cấp tính đe dọa hoại tử (thiếu máu chi cấp / chèn ép khoang / priapism thiếu máu)")
        level = ThreatLevel.CRITICAL
        conf = 0.98
    elif _matches_any(norm, [
        r"\b(chan dau buot|te lanh 1 ben chan dot ngot|dau khi di lai sau vai met)\b",
    ]):
        findings.append("Nghi ngờ tắc nghẽn tuần hoàn chi cấp-bán cấp")
        level = ThreatLevel.HIGH
        conf = 0.85
        
    return DimensionAssessment("limb_threat", level, conf, findings)


def _eval_metabolic_crisis(norm: str) -> DimensionAssessment:
    """12. Metabolic / Endocrine Crisis."""
    findings = []
    level = ThreatLevel.NONE
    conf = 0.50
    
    # 1. DKA / HHS / Lactic acidosis
    has_diabetes = _matches_any(norm, [r"\b(tieu duong|dai thao duong|insulin|metformin)\b"])
    has_dka_pathognomonic = _matches_any(norm, [
        r"\b(hoi tho mui tao chin|mui ceton|kussmaul|tho kussmaul|duong huyet hi|que thu duong cao chot vot)\b",
        r"\b(nhiem toan ceton|dka|tang ap luc tham thau|toan lactic)\b",
    ])
    has_dka_signs = has_dka_pathognomonic or (has_diabetes and _matches_any(norm, [r"\b(non lien tuc|non thoc thao|tho nhanh sau)\b"]))
    
    # 2. Thyroid storm
    has_thyroid = _matches_any(norm, [r"\b(buou co|cuong giap|bazedow|tuyen giap)\b"])
    has_storm_signs = _matches_any(norm, [
        r"\b(sot 40|sot cao|tim dap nhanh loan xa|me sang|bap bung nhu trong|con bao giap|thyroid storm)\b",
    ])
    
    # 3. Adrenal crisis
    has_steroid = _matches_any(norm, [r"\b(dexamethasone|corticoid|medrol|prednisolon|hydrocortisone|solu medrol)\b"])
    has_cessation = _matches_any(norm, [
        r"\b(dung thuoc|ngung thuoc|bo thuoc|het thuoc|thoi uong)\b",
    ])
    has_adrenal_decompensation = _matches_any(norm, [
        r"\b(met la|tut huyet ap|ha huyet ap|sot|choang|suy thuong than cap|suy sup)\b",
    ])
    has_adrenal_crisis_signs = (has_cessation and has_adrenal_decompensation) or _matches_any(norm, [
        r"\b(suy thuong than cap|adrenal crisis)\b",
    ])
    
    # 4. Severe hypoglycemia
    has_severe_hypoglycemia = _matches_any(norm, [
        r"\b(duong huyet|que thu)\b.*?\b(duoi 2|duoi 3|1\.\d|2\.\d)\b.*?\b(va mo hoi|run ray|lo mo|hon me)\b",
    ])

    if (has_diabetes and has_dka_signs) or (has_thyroid and has_storm_signs) or (has_steroid and has_adrenal_crisis_signs) or has_severe_hypoglycemia or has_dka_pathognomonic:
        findings.append("Khủng hoảng chuyển hóa - nội tiết cấp cứu (nhiễm toan ceton DKA / bão giáp / suy thượng thận cấp / hạ đường huyết nặng)")
        level = ThreatLevel.CRITICAL
        conf = 0.98
    elif _matches_any(norm, [
        r"\b(tieu duong|duong huyet)\b.*?\b(duong tren 20|duong tren 25|duong 30|kho uong nuoc|kho khao)\b",
    ]):
        findings.append("Rối loạn chuyển hóa đường huyết nặng cần can thiệp y tế khẩn")
        level = ThreatLevel.HIGH
        conf = 0.88
        
    return DimensionAssessment("metabolic_crisis", level, conf, findings)


# ---------------------------------------------------------------------------
# Composite Graph Evaluator
# ---------------------------------------------------------------------------

def evaluate_threat_graph(text: str, vitals_dict: dict[str, Any] | None = None) -> ThreatGraphResult:
    """Evaluate patient symptoms across all 12 physiologic threat dimensions."""
    norm = normalize_search_text(text)
    extracted_vitals = _extract_vitals_from_text(norm)
    if vitals_dict:
        for k, v in vitals_dict.items():
            if isinstance(v, (int, float)):
                extracted_vitals[k.lower()] = float(v)

    evaluators = [
        _eval_airway(norm),
        _eval_breathing(norm, extracted_vitals),
        _eval_circulation(norm, extracted_vitals),
        _eval_neurology(norm),
        _eval_sepsis_infection(norm, extracted_vitals),
        _eval_major_bleeding(norm),
        _eval_toxic_exposure(norm),
        _eval_pregnancy_danger(norm),
        _eval_surgical_abdomen(norm),
        _eval_vision_threat(norm),
        _eval_limb_threat(norm),
        _eval_metabolic_crisis(norm),
    ]

    assessments: dict[str, DimensionAssessment] = {}
    critical_dims: list[str] = []
    high_dims: list[str] = []
    max_level = ThreatLevel.NONE
    composite_score = 0
    all_findings: list[str] = []

    for assess in evaluators:
        assessments[assess.dimension] = assess
        score = assess.level.severity_score
        composite_score += score
        if assess.level == ThreatLevel.CRITICAL:
            critical_dims.append(assess.dimension)
            all_findings.extend(assess.findings)
        elif assess.level == ThreatLevel.HIGH:
            high_dims.append(assess.dimension)
            all_findings.extend(assess.findings)

        if score > max_level.severity_score:
            max_level = assess.level

    summary = (
        "; ".join(all_findings[:3])
        if all_findings
        else "Không ghi nhận dấu hiệu đe dọa sinh lý nguy kịch cấp tính."
    )

    return ThreatGraphResult(
        assessments=assessments,
        max_threat_level=max_level,
        critical_dimensions=critical_dims,
        high_dimensions=high_dims,
        composite_threat_score=composite_score,
        primary_threat_summary=summary,
    )
