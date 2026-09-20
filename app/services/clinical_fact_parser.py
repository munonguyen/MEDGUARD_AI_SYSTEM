"""Semantic Clinical Fact Parser for MedGuard AI V6.

Decouples human natural language (formal, folk, metaphor, regional dialect,
caregiver, teencode, and indirect functional descriptions) into structured,
evidence-grounded ClinicalEvent and ClinicalFactSet schemas.
"""

from __future__ import annotations

import re
from typing import Any

from app.models.clinical_events import (
    ClinicalAssertion,
    ClinicalEvent,
    ClinicalFactSet,
    OnsetTrajectory,
    SeverityLevel,
)
from app.services.clinical_text import normalize_search_text


# Negation indicators in standard and colloquial Vietnamese (preceding and trailing)
_NEGATION_PREFIXES = (
    r"\b(khong|chua|khong phai|chong|ko|k|hong\s+(?:co|bi|thay|phai|he|con)|hổng|cha|chả|chang|chẳng|khong he|khong thay|khong con|chu khong|hoan toan khong|khong co|chua he)\b"
)

_NEGATION_TRAILING = (
    r"(?:(?:nhung|ma|song|chu)\s+)?(?:toi|minh|em|chau)\s+(?:khong|chua|ko|k|hong|chang|khong he)\s+(?:bi|co|bi nhu vay|nhu the|bi vay)\b|"
    r"\b(?:nhung|ma|song|chu)\s+(?:khong|chua|ko|k|hong|chang)\s+(?:bi|bi nhu vay|nhu the|bi vay)\b|"
    r"\b(?:nhung|ma|song|chu)\s+(?:thuc te|that ra|thuc ra|hoa ra)?\s*(?:chi|chi la)\s*(?:bi|do)\b|"
    r"\b(?:khong phai toi bi|khong phai bi|chua tung bi|khong co trieu chung nay|khong he co|khong he bi|hoan toan binh thuong|"
    r"am ap hong hao binh thuong|hoan toan khoe manh|khong he co trieu chung|khong co trieu chung nguy hiem nao|thay am ap|thay binh thuong)\b"
)

# Temporality markers
_HISTORICAL_PATTERNS = (
    r"\b(nam ngoai|hoi nho|hoi xua|hoi tre|nam truoc|thang truoc|tuan truoc|cach day \d+|"
    r"tung bi|da tung bi|tung co|da tung co|truoc day|truoc kia|da chua khoi|khoi hoan toan|da khoi)\b"
)

_HYPOTHETICAL_PATTERNS = (
    r"\b((?:toi\s+)?doc\s+(?:bao|tren\s+bao|tren\s+mang|thay|duoc)|doc\s+bao|doc\s+tren\s+mang|"
    r"nghe\s+noi|nghe\s+bao|neu\s+bi|neu\s+co|gia\s+su|gia\s+dinh|"
    r"cho\s+toi\s+hoi\s+ve|la\s+benh\s+gi|co\s+nguy\s+hiem\s+khong|tim\s+hieu\s+ve|"
    r"tra\s+google|tim\s+tren\s+google|google\s+bao|google\s+noi|doc\s+ve|nghi\s+minh\s+bi|"
    r"so\s+bi|nghi\s+la\s+bi|tuong\s+bi|thay\s+bao\s+la|hoi\s+xem\s+co\s+phai|so\s+minh\s+bi|"
    r"bac\s+si\s+dan\s+neu\s+co)\b"
)

# Third-person experiencer patterns
_THIRD_PERSON_SUBJECTS = (
    r"\b(bo toi|ba toi|me toi|chong toi|vo toi|ong toi|ba ngoai|ong ngoai|ba noi|ong noi|"
    r"con toi|chau toi|ong cu|ba cu|nguoi nha toi|ban toi|hang xom|nguoi ta|nguoi khac|ai do|thay nguoi ta)\b"
)

# Onset / sudden progression indicators
_SUDDEN_ONSET_PATTERNS = (
    r"\b(dot ngot|tu nhien|bong nhien|dot nhien|vua moi|tuc thi|nhu set danh|ngay lap tuc|nhanh chong|cap tinh)\b"
)

# Fact extraction rules: (regex_pattern, concept, organ_system, physiologic_consequence, functional_loss, severity, default_onset)
_SEMANTIC_FACT_RULES: list[dict[str, Any]] = [
    # -----------------------------------------------------------------------
    # 1. OPHTHALMOLOGY / VISION THREAT
    # -----------------------------------------------------------------------
    {
        "patterns": [
            r"\b(?:mat thi luc|mu dot ngot|tac dong mach vong mac|bong vong mac|amaurosis|glaucoma|crao|retinal detachment|vision loss)\b",
            r"(?:mat|thi luc|con mat|nhin)\b.*?\b(?:toi thui|den kit|toi sam|khong nhin thay|chang nhin thay|khong thay duong|khong thay gi|chang thay gi|k thay j|k thay gi|chang nhin thay ri|k thay ri)",
            r"\b(?:chang nhin thay gi|khong nhin thay gi|chang thay gi|k thay j|khong thay gi|chang nhin thay ri|k thay ri)\b.*?\b(?:o mat|mat|con mat|1 mat|mot mat|ben trai|ben phai)\b",
            r"(?:nhu|co ai)?\s*(?:keo|sap|buong)?\s*(?:tam|buc)?\s*(?:rem|man|manh)\s*(?:den|toi)?\s*(?:sap|sup|che|che phu|che mat|che kin|xuong)",
            r"(?:nhu|giong)?\s*(?:ai)?\s*(?:tat|cup|ngat)\s*(?:cong tac|den|dien|cau dao)\b",
            r"\b(?:nhin hinh bien dang|nhin doi dot ngot|chop sang lap loe kem ruoi bay|ruoi bay day dac)",
            r"\b(?:do nhu trai gac.*dau mat|dau nhuc mat du doi.*quang cau vong|dau nhuc mat.*quang cau vong)",
            r"\b(?:dua tay truoc mat|dua ban tay truoc mat|ngo quoc).*?\b(?:khong thay|chang thay|k thay|khong nhin|chang thay ri)",
            r"\b(?:ruoi bay.*chop sang|mang den che khuat|mang den che.*truong nhin|che khuat nua truong nhin)\b",
            r"\b(?:xuyen thung nhan cau|rach sau mi mat.*thung nhan cau|phoi to chuc den.*mat|chay dich trong.*mat)\b",
        ],
        "concept": "vision_loss",
        "organ_system": "ophthalmology",
        "physiologic_consequence": "retinal_or_optic_ischemia",
        "functional_loss": "loss_of_sight",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    {
        "patterns": [
            r"\b(?:mat thinh luc hoan toan|diec dot ngot|dot ngot mat thinh luc|mat thinh luc.*chong mat quay cuong|sudden hearing loss)\b",
        ],
        "concept": "sudden_hearing_loss",
        "organ_system": "ent",
        "physiologic_consequence": "sensory_organ_ischemia",
        "functional_loss": "loss_of_hearing",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    # -----------------------------------------------------------------------
    # 2. VASCULAR & LIMB THREAT
    # -----------------------------------------------------------------------
    {
        "patterns": [
            r"\b(?:canh tay|canh tay trai|canh tay phai|ban tay|ban chan|chan|tay|chi|cang chan)\b.*?\b(?:trang bech|tai nhot|tai nhot|lanh buot|lanh ngat|lang ngat|nhu da tang)",
            r"\b(?:bat mach|bat mach quay|mach quay|mach mu chan)\b.*?\b(?:khong thay dap|hoan toan khong|khong dap|mat mach|khong bat duoc|mat mach quay)",
            r"\b(?:thieu mau chi cap|tac mach chi cap|tac dong mach|mat mach|acute limb ischemia|cold limb|pulseless)\b",
        ],
        "concept": "arterial_occlusion",
        "organ_system": "vascular",
        "physiologic_consequence": "limb_perfusion_failure",
        "functional_loss": "loss_of_limb_perfusion",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    {
        "patterns": [
            r"\b(?:chan mo|bap chan|bap tay|cang chan|cang tay)\b.*?\b(?:sung to|cang cung|cang cung nhu|nhu khuc go)",
            r"\b(?:dau buot|dau buot du doi|dau nhuc nhoi)\b.*?\b(?:khi gap|gap thu dong|van dong thu dong)",
            r"\b(?:mat cam giac mu chan|mat cam giac dau chi|hoi chung chen ep khoang|compartment syndrome)\b",
            r"\b(?:chan cang nhu qua bong|co ngon chan.*dau buot|chan.*sung to cang cung|bo bot.*sung to)\b",
        ],
        "concept": "compartment_syndrome",
        "organ_system": "musculoskeletal_vascular",
        "physiologic_consequence": "compartment_pressure_ischemia",
        "functional_loss": "loss_of_limb_mobility_sensation",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    {
        "patterns": [
            r"\b(?:sau thong tim|sau can thiep.*mach|sau choc dong mach|femoral hematoma|pseudoaneurysm)\b.*?\b(?:vung ben|ben)\b.*?\b(?:sung to|phong to|phong cang|dau buot|khoi mau tu)",
            r"\b(?:vung ben|ben)\b.*?\b(?:sung to phong|phong cang)\b.*?\b(?:tut huyet ap|da chan.*tim tai|lanh ngat)",
            r"\b(?:khoi mau tu vung ben|vung ben.*khoi mau tu|khoi u o ben.*thinh thich|vet choc dong mach ben|choc dong mach.*ben.*sung to)\b",
        ],
        "concept": "femoral_hematoma_or_rupture",
        "organ_system": "vascular",
        "physiologic_consequence": "catastrophic_vascular_threat",
        "functional_loss": "loss_of_limb_perfusion",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    {
        "patterns": [
            r"\b(?:cau noi|avf|cau tay|cau chay than|avf rupture)\b.*?\b(?:phinh to|cang bong|sap vo|vo cau noi)",
            r"\b(?:da mong|cang mong|cang bong)\b.*?\b(?:sap vo|nut|chay mau)",
            r"\b(?:cau mo tay|bong nuoc.*sap buc|chay than.*sap vo)\b",
        ],
        "concept": "vascular_access_rupture_threat",
        "organ_system": "vascular",
        "physiologic_consequence": "catastrophic_vascular_threat",
        "functional_loss": "imminent_exsanguination_threat",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    {
        "patterns": [
            r"\b(?:phinh dong mach chu|dong mach chu bung|khoi u o bung|khoi u nay dap|aortic dissection)\b.*?\b(?:dau lung|lan.*ben|lan xuong ben|nay dap theo nhip tim|dap manh)",
            r"\b(?:dau xe nguc|dau xe lung|dau xuyen sau lung|dau nhu xe|xien thang ra sau lung|xuyen thang ra sau lung|giua hai ba vai)",
            r"\b(?:dau nguc.*lan doc song lung|dau nguc.*kinh hoang.*sau lung|dau xe nguc)\b",
        ],
        "concept": "aortic_dissection_or_rupture",
        "organ_system": "cardiovascular",
        "physiologic_consequence": "catastrophic_vascular_threat",
        "functional_loss": "hemodynamic_collapse_threat",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    {
        "patterns": [
            r"\b(?:cuong cung|cuong dau|cuong cung duong vat|priapism)\b.*?\b(?:tren \d+|khong mem|lien tuc|keo dai|priapism)",
            r"\b(?:cho kin cung ngac|cung ngac dau buot.*nhieu gio|cung dau.*nhieu gio)\b",
        ],
        "concept": "ischemic_priapism",
        "organ_system": "urology",
        "physiologic_consequence": "organ_ischemia_necrosis_threat",
        "functional_loss": "acute_urological_crisis",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.PERSISTENT,
    },
    # -----------------------------------------------------------------------
    # 3. SURGICAL ABDOMEN & PERITONISM
    # -----------------------------------------------------------------------
    {
        "patterns": [
            r"\b(?:bung|bung dau)\b.*?\b(?:cung ngac|cung ngat|cung nhu|nhu mieng van|nhu go|co cung|de khang|cam ung phuc mac|nhu dao dam|khong dam tho manh)",
            r"\b(?:go vo nghe cop cop|dau quan that rut rut ruot gan|thung da day|thung ruot|viem phuc mac|board-like rigidity|peritonitis)\b",
            r"\b(?:dau bung du doi|bung go cung lien tuc|bung go cung kem dau|an vao buong tay ra dau nhoi)",
        ],
        "concept": "abdominal_rigidity",
        "organ_system": "abdomen",
        "physiologic_consequence": "peritoneal_irritation",
        "functional_loss": "inability_to_tolerate_palpation_movement",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    {
        "patterns": [
            r"\b(?:cuc thit|khoi phong|thoat vi|khoi sa|cuc thit o hang|duoi hang co)\b.*?\b(?:tho lo|dau nhuc nhoi|nghen|khong day len|khong nhet|khong vo duoc)",
            r"\b(?:bung truong cang nhu cai trong|chuong bung nhu qua bong|bi trung dai tien)",
            r"\b(?:duoi hang co cuc phong|cuc phong.*khong thut vao|khong nhet len|thoat vi ben nghen)\b",
        ],
        "concept": "strangulated_hernia",
        "organ_system": "abdomen",
        "physiologic_consequence": "bowel_strangulation_or_obstruction",
        "functional_loss": "gastrointestinal_transit_failure",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    {
        "patterns": [
            r"\b(?:khoc thet tung con|khoc thet.*co gap|phan nhu thach ca chua|mau nhu thach ca chua|(?<!thanh\s)long\s+ruot|intussusception)\b",
            r"\b(?:quan quai tung con.*phan do|bung quan gap nguoi.*phan|quay khoc du doi ngat quang.*dai tien ra mau|quay khoc.*bo bu non vot.*mau)\b",
        ],
        "concept": "intussusception",
        "organ_system": "abdomen",
        "physiologic_consequence": "bowel_strangulation_or_obstruction",
        "functional_loss": "gastrointestinal_transit_failure",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    {
        "patterns": [
            r"\b(?:rung nhi.*dau bung|dau bung.*rung nhi|sau an.*dau bung quan quai|thieu mau mac treo|tac dong mach mac treo|mesenteric ischemia)\b",
            r"\b(?:ruot.*that nghen|xoan nghet.*dau.*sau bua an|dau bung bao to|dau bung.*dot ngot o benh nhan tim mach)\b",
        ],
        "concept": "mesenteric_ischemia",
        "organ_system": "abdomen",
        "physiologic_consequence": "organ_ischemia_necrosis_threat",
        "functional_loss": "inability_to_tolerate_palpation_movement",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    {
        "patterns": [
            r"(ho chau phai.*an dau nhoi|dau bung quanh ron chuyen xuong ho chau phai|ruot thua.*sot.*non|acute appendicitis)",
            r"\b(?:dau nhoi buot goc bung duoi ben phai|bung duoi ben phai.*khom lung|don xuong ho chau phai|khu tru o bung duoi ben phai|bung duoi ben phai.*khong the ho|nhay co lo.*dau bung)\b",
        ],
        "concept": "acute_appendicitis",
        "organ_system": "abdomen",
        "physiologic_consequence": "localized_peritoneal_inflammation",
        "functional_loss": "abdominal_splinting",
        "severity": SeverityLevel.SEVERE,
        "onset": OnsetTrajectory.PROGRESSIVE,
    },
    # -----------------------------------------------------------------------
    # 4. NEUROLOGY / STROKE / TETANUS / INTRACRANIAL
    # -----------------------------------------------------------------------
    {
        "patterns": [
            r"\b(?:dot quy|tai bien|liet nua nguoi|that ngon|liet tay chan)\b",
            r"\b(?:xay xam\s+cam khau|cam khau|bai hoai.*tay chan|tay chan bai hoai|meo mieng|mieng meo|rot dua)\b",
            r"\b(?:noi nang liu nhiu|noi k ro tieng|noi ngong dot ngot)\b",
            r"\b(?:cam cai coc cung khong noi|yeu nua nguoi dot ngot|di xieu veo dot ngot|yeu mem nhun)\b",
            r"\b(?:nhin mot hoa hai|nuot.*sac len mui|khan tieng.*loang choang|liet hanh tuy)\b",
        ],
        "concept": "acute_stroke",
        "organ_system": "neurology",
        "physiologic_consequence": "acute_neurologic_deficit",
        "functional_loss": "loss_of_motor_power",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    {
        "patterns": [
            r"\b(?:cung ham|rang can chat|can chat rang|uon van)\b",
            r"\b(?:khong ha duoc mieng|k ha mieng|khong the ha mieng|nuot nghen sac|kho ha mieng)\b",
            r"\b(?:uon cong nguoi ga gap|ga gap khi co tieng dong|nguoi co cung lai|co cung co van)\b",
            r"\b(?:dinh gi|vat set|dinh gỉ)\b.*?\b(?:cung ham|uon cong|co cung|nuot|dam)\b",
        ],
        "concept": "tetanic_spasm",
        "organ_system": "neurology",
        "physiologic_consequence": "neuromuscular_airway_compromise",
        "functional_loss": "loss_of_swallowing_and_jaw_opening",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    {
        "patterns": [
            r"\b(?:hai chan yeu nhanh|liet dan khong dung duoc|te bi.*ngang ron|hai chan liet hoan toan|chen ep tuy|spinal cord compression|cauda equina)\b",
            r"\b(?:cat dut ngang hong|chan duoi mem nhun|chan duoi.*vo cam|doi chan mat het suc luc|khong the nhac got.*mat cam giac)\b",
        ],
        "concept": "spinal_cord_compression",
        "organ_system": "neurology",
        "physiologic_consequence": "acute_neurologic_deficit",
        "functional_loss": "loss_of_motor_power",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    {
        "patterns": [
            r"(dau dau nhu set danh|dau dau(?:\s+du doi)?\s*(?:nhu\s*)?set danh|dau dau du doi.*?(?:set danh|non vot lien tuc)|dau dau du doi nhat cuoc doi|dau dau kem cung co so anh sang|hon me|li bi|co giat|thunderclap headache|subarachnoid hemorrhage|sah|xuat huyet duoi nhen)",
            r"\b(?:nhuc dau.*sup mi.*dong tu.*gian|nhuc dau nua dau.*nhin mo.*sup mi)\b",
            r"\b(?:cam cung do gay cung nhac khong cui duoc|gay cung nhac|co cung gay|co gay cung ngac)\b",
            r"\b(?:dau dau.*chua tung thay|tia set no tung trong so nao|dau vo dau nga quy|nhuc dau.*dat dinh.*trong vai giay|nhuc dau.*mat tri giac)\b",
        ],
        "concept": "intracranial_catastrophe",
        "organ_system": "neurology",
        "physiologic_consequence": "raised_intracranial_pressure_or_meningeal_irritation",
        "functional_loss": "impaired_consciousness_or_severe_cephalalgia",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    # -----------------------------------------------------------------------
    # 5. CARDIOVASCULAR & SHOCK / RUPTURED ORGAN
    # -----------------------------------------------------------------------
    {
        "patterns": [
            r"(nguc de nghen tho hong noi|tim dap thinh thinh nhu trong tran.*nhay ra khoi|dau nguc de ep lan tay trai|dau bop nghet nhu da de|hoi chung vanh cap|dau that nguc|that nguc de ep|acute coronary syndrome|acs|nhoi mau co tim)",
            r"\b(?:tuc nghen nhu tang da de|tang da de.*nguc|va mo hoi uot dam lung ao.*nguc|lan len.*goc ham|lan.*quai ham|lan.*rang duoi|long nguc bi nghien nat|nguc bi nghien nat)\b",
        ],
        "concept": "acute_coronary_syndrome",
        "organ_system": "cardiovascular",
        "physiologic_consequence": "myocardial_ischemia_threat",
        "functional_loss": "loss_of_exertional_tolerance",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    {
        "patterns": [
            r"\b(?:tinh mach co noi to|tieng tim.*mo xa xam|tieng tim nghe mo xa xam|chen ep tim cap|becks triad|cardiac tamponade|pericardial tamponade)\b",
            r"\b(?:tieng co mang tim.*dau nguc du doi|viem mang ngoai tim cap|tim dap.*bop trong tui nuoc|tim.*trong tui nuoc|noi phong tinh mach ngoan ngoeo)\b",
        ],
        "concept": "cardiac_tamponade",
        "organ_system": "cardiovascular",
        "physiologic_consequence": "circulatory_compromise",
        "functional_loss": "hemodynamic_collapse_threat",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    {
        "patterns": [
            r"(sau con non mua du doi.*dau buot choi nguc|non xong dau nguc du doi|boerhaave|vo thuc quan|tran khi duoi da.*o co)",
        ],
        "concept": "boerhaave_syndrome",
        "organ_system": "cardiovascular_thoracic",
        "physiologic_consequence": "catastrophic_vascular_threat",
        "functional_loss": "hemodynamic_collapse_threat",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    {
        "patterns": [
            r"(dau choi.*ha suon trai lan.*vai|mat tai met ngat lim sau.*mononucleosis|vo lach.*ngat)",
        ],
        "concept": "splenic_rupture",
        "organ_system": "abdomen_hemodynamics",
        "physiologic_consequence": "internal_hemorrhage_and_shock",
        "functional_loss": "hemodynamic_collapse",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    {
        "patterns": [
            r"(mat tai met ngat lim|ngat dot ngot|soc mat mau|tut huyet ap.*va mo hoi lanh|mach nhanh nho kho bat)",
            r"\b(?:dung bong chet giac|chet giac|tai met nhu tau la chuoi|tho giat nguoc hong ra hoi|keu reo hong nhuc nhich)\b",
            r"\b(?:dai thao duong.*lu lan me man.*tut huyet ap|dai thao duong.*khong dau nguc.*lu lan)\b",
        ],
        "concept": "hemodynamic_shock",
        "organ_system": "cardiovascular",
        "physiologic_consequence": "circulatory_compromise",
        "functional_loss": "loss_of_consciousness_postural_collapse",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    {
        "patterns": [
            r"\b(?:truyen dich|tiem thuoc|sau tiem)\b.*?\b(?:ret run|tim tai|kho tho|phu ne|ngat)\b.*?\b(?:tut huyet ap|sut.*xuong|huyet ap sut|\d+/\d+)",
            r"\b(?:soc phan ve|tuc tho bop nghet hong.*phu ne.*mi mat|tiem thuoc can quang.*phu ne.*tut huyet ap|anaphylaxis|anaphylactic shock)\b",
        ],
        "concept": "anaphylaxis_shock",
        "organ_system": "cardiovascular_immune",
        "physiologic_consequence": "circulatory_compromise",
        "functional_loss": "hemodynamic_collapse",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    # -----------------------------------------------------------------------
    # 6. RESPIRATORY & AIRWAY
    # -----------------------------------------------------------------------
    {
        "patterns": [
            r"(tho rit nhu keo nhi|tho rit thanh quan|nghen u o co khong tho duoc|tim tai dau ngon tay va moi|tho ngop|kho tho du doi khong noi duoc|stridor|airway obstruction)",
            r"\b(?:di vat.*gam sau ha hong|xuong ca.*ha hong.*nghen tho|hoc di vat.*ho khac ra bot mau|ban tay vo hinh bop nghet|co hong.*bop nghet.*rit|khong the noi duoc tu nao.*hong tac nghen|long nguc co rut lom sau)\b",
        ],
        "concept": "airway_obstruction_or_severe_dyspnea",
        "organ_system": "respiratory",
        "physiologic_consequence": "airway_compromise",
        "functional_loss": "inability_to_speak_full_sentences",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    {
        "patterns": [
            r"\b(?:go vang nhu trong|long nguc.*go vang nhu trong|tran khi mang phoi ap luc|tension pneumothorax|tran khi ap luc)\b",
            r"\b(?:nguc cang phong nhu qua banh|go keu bong bong|khi quan bi lech|long nguc.*bat dong cang phong)\b",
        ],
        "concept": "tension_pneumothorax",
        "organ_system": "respiratory",
        "physiologic_consequence": "airway_compromise",
        "functional_loss": "inability_to_speak_full_sentences",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    {
        "patterns": [
            r"\b(?:khong the nam thang.*ngoi chom hom|ngoi chom hom ti tay vao dau goi de tho|khac ra.*bot mau hong|sui bot hong|pulmonary edema|phu phoi cap)\b",
            r"\b(?:phu phoi cap|suy tim trai cap.*bot hong|phoi nhu ngap chim|trao bot hong|sui bot hong o mieng|vua dat lung xuong la ngat tho)\b",
        ],
        "concept": "acute_pulmonary_edema",
        "organ_system": "respiratory_cardiovascular",
        "physiologic_consequence": "airway_compromise",
        "functional_loss": "inability_to_speak_full_sentences",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    {
        "patterns": [
            r"\b(?:sau phau thuat thay khop|thay khop hang.*suy ho hap|thuyen tac mo|noi ban xuat huyet ket mac.*co nguc)\b",
            r"\b(?:sau de mo.*ho sac ra bot mau|thuyen tac phoi sau sinh)\b",
        ],
        "concept": "fat_embolism_or_pulmonary_embolism",
        "organ_system": "respiratory",
        "physiologic_consequence": "airway_compromise",
        "functional_loss": "inability_to_speak_full_sentences",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    # -----------------------------------------------------------------------
    # 7. TOXICOLOGY / MASSIVE OVERDOSE
    # -----------------------------------------------------------------------
    {
        "patterns": [
            r"(\b(?:[89]|\d{2,})\s*vien\s*(?:paracetamol|panadol|efferalgan|thuoc ngu|thuoc an than|thuoc ha ap|thuoc tim mach|thuoc)\b|\b(?:4000|5000|6000|7000|7500|8000|10000|\d{5,})\s*mg\s*paracetamol\b)",
            r"(uong thuoc tru sau|diet co|paraquat|phospho huu co|uong nuoc tay bon cau|axit|xut|con cong nghiep|methanol|ethylene glycol|nuoc lam mat)",
            r"(uong nham thuoc.*(?:qua lieu|lieu cao|li bi)|uong qua lieu.*thuoc|uong ca vi thuoc ngu|uong ca vi thuoc|\b(?:uong|uong nham)\s+\d{2,}\s*vien\b|toxic ingestion|overdose|ca voc thuoc)",
        ],
        "concept": "toxic_ingestion",
        "organ_system": "toxicology",
        "physiologic_consequence": "acute_toxic_metabolic_threat",
        "functional_loss": "target_organ_poisoning",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    # -----------------------------------------------------------------------
    # 8. METABOLIC & ONCOLOGIC CRISIS / SEVERE SEPSIS
    # -----------------------------------------------------------------------
    {
        "patterns": [
            r"\b(?:buou co cuong giap.*sot vot|sot vot \d+.*tim dap nhanh nhu trong tran|bao giap)\b",
        ],
        "concept": "thyroid_storm",
        "organ_system": "endocrine",
        "physiologic_consequence": "metabolic_crisis",
        "functional_loss": "organ_hypoperfusion_or_necrosis",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    {
        "patterns": [
            r"\b(?:mui qua chin len men|tho doc sau kussmaul|kussmaul|nhiem toan ceton|dka)\b",
            r"\b(?:dai thao duong.*tho hon hen don dap.*khat nuoc du doi)\b",
        ],
        "concept": "diabetic_ketoacidosis",
        "organ_system": "endocrine",
        "physiologic_consequence": "metabolic_crisis",
        "functional_loss": "organ_hypoperfusion_or_necrosis",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    {
        "patterns": [
            r"(ung thu mau dang hoa tri.*liet mem.*nhip tim cham|nhip tim cham loan 40.*nuoc tieu do duc|hoi chung ly giai u)",
            r"(sot cao ret run cam cap.*li bi.*da noi van tim|nhiem trung huyet.*tut huyet ap)",
            r"\b(?:sot cao.*lao xao tieng khi lan rong duoi da|lao xao khi duoi da|hoai thu sinh hoi|viem can hoai tu)\b",
        ],
        "concept": "tumor_lysis_or_septic_shock",
        "organ_system": "metabolic_infection",
        "physiologic_consequence": "metabolic_crisis",
        "functional_loss": "organ_hypoperfusion_or_necrosis",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    {
        "patterns": [
            r"\b(?:soc nhiet|say nang.*nga quy|than nhiet.*4[012].*me sang|da kho nong khong toat mo hoi|nang gat.*nga quy|soc nhiet.*hon me)\b",
        ],
        "concept": "heat_stroke",
        "organ_system": "metabolic_environmental",
        "physiologic_consequence": "metabolic_crisis",
        "functional_loss": "impaired_consciousness_or_severe_cephalalgia",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    # -----------------------------------------------------------------------
    # 9. OBSTETRICS / GYNECOLOGY DANGER (Order-Independent)
    # -----------------------------------------------------------------------
    {
        "patterns": [
            r"(?:co thai|mang thai|tre kinh|cham kinh|sau de|sau sinh|san phu)\b.*?\b(?:dau bung quan|dau bung du doi|chay mau am dao|ra mau am dao|hoa mat choang vang|tien san giat|mat mo.*dau dau du doi|ngat|choang vang khi dung)",
            r"(?:dau bung quan|dau bung du doi|chay mau am dao|ra mau am dao|choang vang khi dung)\b.*?\b(?:co thai|mang thai|tre kinh|cham kinh|sau de|sau sinh|san phu)",
            r"(chua ngoai tu cung vo|nhau bong non|tu cung co cung nhu go)",
        ],
        "concept": "obstetric_catastrophe",
        "organ_system": "obstetrics",
        "physiologic_consequence": "obstetric_catastrophe",
        "functional_loss": "fetal_maternal_threat",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    # -----------------------------------------------------------------------
    # 10. MASSIVE BLEEDING & POST-OP HEMORRHAGE
    # -----------------------------------------------------------------------
    {
        "patterns": [
            r"\b(?:non|oi)\b.*?\b(?:ra\s*)?mau\s*(?:do\s*tuoi|o\s*at|hon\s*\d+\s*ml|lan\s*mau\s*cuc)",
            r"(?:di\s*cau|di\s*ngoai)\b.*?\b(?:ra\s*)?mau\s*(?:do\s*tuoi|day\s*bon\s*cau|hon\s*\d+\s*ml|o\s*at)",
            r"(?:di\s*cau|di\s*ngoai)\s*phan\s*den\s*(?:nhu\s*ba\s*ca\s*phe|tanh\s*hoi|kem\s*choang)",
            r"(?:sau\s*mo|sau\s*phau\s*thuat|sau\s*mo\s*tri)\b.*?\b(?:di\s*cau\s*o\s*at\s*ra\s*mau|ra\s*mau\s*do\s*tuoi|chay\s*mau\s*o\s*at|mau\s*day\s*bon\s*cau)",
            r"(ho ra mau set danh|phun thanh tia|chay mau khong cam)",
        ],
        "concept": "massive_hemorrhage",
        "organ_system": "hematology",
        "physiologic_consequence": "exsanguinating_hemorrhage",
        "functional_loss": "hemodynamic_volume_loss",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    # -----------------------------------------------------------------------
    # 11. ORBITAL / PERIORBITAL INFECTION WITH VISION THREAT
    # -----------------------------------------------------------------------
    {
        "patterns": [
            r"\b(?:sung ne mat|mat do ruc|mat sung|viem hoc mat)\b.*?\b(?:nhan cau loi|loi mat|loi nhan cau|nhin doi|liet van nhan|dau nhuc du doi)\b",
            r"\b(?:nhan cau loi|loi mat|loi nhan cau)\b.*?\b(?:sung ne mat|mat do ruc|mat sung|dau nhuc.*liec mat|nhin doi|sot cao)\b",
            r"\b(?:viem mo te bao hoc mat|cavernous sinus thrombosis|orbital cellulitis|orbital abscess)\b",
        ],
        "concept": "orbital_cellulitis_cavernous_sinus",
        "organ_system": "ophthalmology",
        "physiologic_consequence": "retinal_or_optic_ischemia",
        "functional_loss": "loss_of_sight",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    # -----------------------------------------------------------------------
    # 12. UROSEPSIS WITH HYPOTENSION
    # -----------------------------------------------------------------------
    {
        "patterns": [
            r"\b(?:sot cao.*ret run|ret run.*sot cao)\b.*?\b(?:nuoc tieu duc|nuoc tieu co mu|mu nuoc tieu|dau hong lung|dau quan hong lung)\b.*?\b(?:huyet ap tut|ha huyet ap|tut ha|\d{2}/\d{2}\s*mmhg)",
            r"\b(?:nuoc tieu duc|nuoc tieu co mu|mu nuoc tieu|dau hong lung|dau quan hong lung)\b.*?\b(?:sot cao.*ret run|ret run.*sot cao)\b.*?\b(?:huyet ap tut|ha huyet ap|tut ha|\d{2}/\d{2}\s*mmhg)",
            r"\b(?:huyet ap tut|ha huyet ap|tut ha|\d{2}/\d{2}\s*mmhg)\b.*?\b(?:sot cao.*ret run|ret run.*sot cao)\b.*?\b(?:nuoc tieu duc|nuoc tieu co mu|dau hong lung|dau quan hong lung)",
            r"\b(?:viem dai be than|pyelonephritis|urosepsis|nhiem trung duong tieu)\b.*?\b(?:huyet ap tut|ha huyet ap|soc nhiem trung|tut ha|\d{2}/\d{2}\s*mmhg)",
        ],
        "concept": "urosepsis_hypotension",
        "organ_system": "urology_infection",
        "physiologic_consequence": "metabolic_crisis",
        "functional_loss": "organ_hypoperfusion_or_necrosis",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    # -----------------------------------------------------------------------
    # 13. TOXIC EPIDERMAL NECROLYSIS (SJS / TEN)
    # -----------------------------------------------------------------------
    {
        "patterns": [
            r"\b(?:noi bong nuoc|bong nuoc trot loet|da trot loet|troc vay da|da bong trot)\b.*?\b(?:dien tich.*\d+\s*%|toan than|loet niem mac|loet nat niem mac|loet mieng|loet mat)",
            r"\b(?:sot phat ban|phat ban)\b.*?\b(?:thuoc|khang sinh|uong thuoc)\b.*?\b(?:bong nuoc|trot loet|troc vay|troc da|loet niem mac|loet mieng)",
            r"\b(?:stevens johnson|sjs|hoi chung ten|sjs[\s/-]*ten|toxic epidermal necrolysis|hoai tu bieu bi nhiem doc|bong da nhiem doc)\b",
        ],
        "concept": "toxic_epidermal_necrolysis",
        "organ_system": "dermatology_immune",
        "physiologic_consequence": "metabolic_crisis",
        "functional_loss": "organ_hypoperfusion_or_necrosis",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.PROGRESSIVE,
    },
    # -----------------------------------------------------------------------
    # 14. POSTPARTUM SEPSIS
    # -----------------------------------------------------------------------
    {
        "patterns": [
            r"\b(?:sau sinh|sau de|san phu)\b.*?\b(?:sot cao|run ray|ret run)\b.*?\b(?:dich san dich|san dich hoi|san dich tanh|dich hoi kham|hoi kham tanh tuoi)\b",
            r"\b(?:sau sinh|sau de|san phu)\b.*?\b(?:dich san dich|san dich hoi|san dich tanh|dich hoi kham|hoi kham tanh tuoi)\b.*?\b(?:sot cao|run ray|ret run)\b",
            r"\b(?:sau sinh|sau de|san phu)\b.*?\b(?:sot cao|run ray|ret run)\b.*?\b(?:dau bung duoi|dau bung du doi|cham vao nay nguoi|dau co that|cham bung dau)\b",
            r"\b(?:nhiem trung hau san|viem noi mac tu cung|viem phu mac chau hau san|postpartum sepsis|puerperal sepsis)\b",
        ],
        "concept": "postpartum_sepsis",
        "organ_system": "obstetrics",
        "physiologic_consequence": "obstetric_catastrophe",
        "functional_loss": "fetal_maternal_threat",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
    # -----------------------------------------------------------------------
    # 15. EXTENSIVE BURN INJURY (≥30% TBSA)
    # -----------------------------------------------------------------------
    {
        "patterns": [
            r"\b(?:bong nuoc soi|bong lua|bong nhiet|bong hoa chat|bong dien|bong)\b.*?\b(?:dien tich.*(?:tren\s*)?\d{2,}\s*%|toan than|dien rong)\b",
            r"\b(?:bong)\b.*?\b(?:phong rop|trot loet|do hon|da phong rop)\b.*?\b(?:ret run|dau don du doi|dien tich.*\d{2,}\s*%|toan than)\b",
            r"\b(?:bong do (?:3|iii)|bong nang|bong dien rong|major burn|extensive burn)\b",
        ],
        "concept": "extensive_burn_injury",
        "organ_system": "trauma_burn",
        "physiologic_consequence": "metabolic_crisis",
        "functional_loss": "organ_hypoperfusion_or_necrosis",
        "severity": SeverityLevel.CRITICAL_EXTREME,
        "onset": OnsetTrajectory.SUDDEN,
    },
]


def _find_evidence_span(text: str, match_obj: re.Match) -> str:
    """Extract a genuine, contiguous evidence span from the text supporting the finding."""
    start, end = match_obj.span()
    # Expand slightly to capture local natural phrase boundaries
    phrase = text[start:end].strip()
    return phrase


def parse_semantic_clinical_facts(raw_text: str) -> ClinicalFactSet:
    """Parse raw clinical text into an evidence-grounded ClinicalFactSet.
    
    Guarantees:
    - Every event has an authentic non-empty evidence_span.
    - Negations are extracted with assertion=ABSENT.
    - High-acuity physiologic consequences and functional losses are abstracted.
    """
    normalized = normalize_search_text(raw_text)
    events: list[ClinicalEvent] = []
    matched_spans: list[tuple[int, int]] = []

    # Detect global onset marker
    global_sudden = bool(re.search(_SUDDEN_ONSET_PATTERNS, normalized))

    for rule in _SEMANTIC_FACT_RULES:
        for pat in rule["patterns"]:
            for m in re.finditer(pat, normalized, re.IGNORECASE):
                span_start, span_end = m.span()
                matched_phrase = normalized[span_start:span_end].strip()
                if not matched_phrase:
                    continue

                # 1. Check for negation in preceding window (up to 60 characters) or trailing window (up to 120 characters)
                preceding_window = normalized[max(0, span_start - 60):span_start]
                is_preceding_neg = bool(re.search(_NEGATION_PREFIXES + r"\s*$", preceding_window.strip()))
                trailing_window = normalized[span_end:min(len(normalized), span_end + 120)]
                is_trailing_neg = bool(re.search(_NEGATION_TRAILING, trailing_window.strip()))
                is_negated = is_preceding_neg or is_trailing_neg
                assertion = ClinicalAssertion.ABSENT if is_negated else ClinicalAssertion.PRESENT

                # 2. Check temporality (historical vs hypothetical vs current)
                local_context = normalized[max(0, span_start - 60):min(len(normalized), span_end + 60)]
                if re.search(_HISTORICAL_PATTERNS, local_context) or re.search(r"\b(?:tien su|co tien su)\b", preceding_window):
                    temporality = "historical"
                elif re.search(_HYPOTHETICAL_PATTERNS, local_context) or re.search(_HYPOTHETICAL_PATTERNS, normalized[:span_start]):
                    temporality = "hypothetical"
                else:
                    temporality = "current"

                # 3. Check experiencer (patient vs patient_consultation vs other)
                preceding_subject_window = normalized[max(0, span_start - 60):span_start]
                has_third_person = bool(re.search(_THIRD_PERSON_SUBJECTS, preceding_subject_window))
                if has_third_person:
                    # If historical or subsequent clause indicates patient's separate problem
                    if temporality == "historical" or re.search(r"\b(?:con|nhung)\s*(?:hom nay)?\s*(?:toi|minh)\b", normalized[span_end:]):
                        experiencer = "other"
                    else:
                        experiencer = "patient_consultation"
                else:
                    experiencer = "patient"

                # 4. Check for specific sudden onset
                local_onset = OnsetTrajectory.SUDDEN if global_sudden or re.search(r"\b(dot ngot|tu nhien|bong nhien)\b", matched_phrase) else rule.get("onset", OnsetTrajectory.SUDDEN)

                event = ClinicalEvent(
                    concept=rule["concept"],
                    organ_system=rule["organ_system"],
                    onset=local_onset,
                    severity=rule["severity"],
                    assertion=assertion,
                    temporality=temporality,
                    experiencer=experiencer,
                    physiologic_consequence=rule.get("physiologic_consequence"),
                    functional_loss=rule.get("functional_loss"),
                    certainty=0.95 if not is_negated else 0.90,
                    evidence_span=matched_phrase,
                )
                events.append(event)
                matched_spans.append((span_start, span_end))

    # 5. Synthesize clinical events from Semantic Abstraction Layer (V8 Architecture)
    try:
        from app.services.semantic_abstraction_layer import (
            extract_semantic_abstractions,
            synthesize_clinical_events_from_abstractions,
        )
        abstractions = extract_semantic_abstractions(raw_text)
        abs_events = synthesize_clinical_events_from_abstractions(abstractions, raw_text)
        for a_ev in abs_events:
            # Avoid duplicate concepts
            if not any(e.concept == a_ev.concept for e in events):
                events.append(a_ev)
                matched_spans.append((0, len(normalized)))
    except Exception:
        pass

    # Calculate semantic coverage
    total_len = len(normalized.strip())
    covered_len = sum(e - s for s, e in matched_spans)
    coverage = min(1.0, (covered_len / max(total_len, 1)) * 1.5) if total_len > 0 else 1.0

    return ClinicalFactSet(
        raw_text=raw_text,
        normalized_text=normalized,
        events=tuple(events),
        semantic_coverage=round(coverage, 2),
    )
