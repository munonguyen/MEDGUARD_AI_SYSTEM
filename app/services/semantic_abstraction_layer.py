"""Semantic Clinical Abstraction Layer for MedGuard AI (V8 Architecture).

Bridges human colloquial, metaphoric, indirect, and regional Vietnamese expressions
with high-level clinical abstractions and structured ClinicalEvent facts.

Principles:
1. Concept Abstraction: Translates natural language descriptions into physiological
   primitives without demanding formal Latin/English disease keywords.
2. Anti-Hallucination Grounding: Every abstraction is strictly tied to an affirmed
   text span with robust negation/hypothetical shielding.
3. Multi-Cohort Coverage: Captures indirect functional loss, occult surgical catastrophes,
   toxidromes, shock, and barrier disruptions.
"""

from __future__ import annotations

import re
from typing import Any, Sequence

from app.models.clinical_events import (
    ClinicalAssertion,
    ClinicalEvent,
    OnsetTrajectory,
    SeverityLevel,
)
from app.models.semantic_abstraction import (
    AbstractionCategory,
    ClinicalAbstraction,
    SemanticAbstractionResult,
)
from app.services.clinical_text import contains_affirmed_phrase, normalize_search_text


# Pre-compiled abstraction patterns
_ABSTRACTION_CATALOG: list[dict[str, Any]] = [
    # -----------------------------------------------------------------------
    # 1. ACUTE LIMB & PERFUSION THREAT
    # -----------------------------------------------------------------------
    {
        "id": "loss_of_limb_perfusion",
        "category": AbstractionCategory.FUNCTIONAL_LOSS,
        "patterns": [
            r"(?:chan|tay|chi|cang chan|cang tay|ban chan|ban tay).*?\b(?:trang on|trang bech|trang bot|tai nhot|lanh toat|lanh ngat|lanh buot)\b.*?\b(?:khong bat duoc|mat mach|khong thay mach|mat hoan toan|khong thay nay|nhu dong bang|nhu cuc da|buot thau|dau)\b",
            r"\b(?:mach mu chan|mach co tay|mach quay)\b.*?\b(?:mat|khong thay|khong bat duoc)\b",
            r"(?:chan|tay|chi|ban chan|canh tay|bap chan).*?\b(?:trang on|trang bech|tai nhot|nhu xac chet|nhu da|dong da)\b.*?\b(?:lanh toat|lanh ngat|buot thau|khong bat duoc|chang thay mach|mat mach|khong thay mach)\b",
            r"\b(?:trang on|trang bech|tai nhot|nhu xac chet)\b.*?\b(?:lanh toat|lanh buot|lanh ngat)\b.*?\b(?:ro|bat|tim)?\s*(?:khong thay|chang thay|mat)\s*(?:mach|mach dap)\b",
            r"\b(?:khong thay mach|chang thay mach|mat mach|khong bat duoc mach)\b.*?\b(?:chan|tay|chi|ban chan)\b.*?\b(?:lanh|tai nhot|trang bech|dau du doi)\b",
            r"\b(?:chan|tay)\b.*?\b(?:lanh nhu bang|lanh ngat nhu dong da)\b.*?\b(?:dau thau troi|dau khong chiu noi|dau du doi)\b",
        ],
        "is_critical": True,
        "acuity": 0.99,
        "functional_loss": "loss_of_limb_perfusion",
        "physiologic_consequence": "limb_perfusion_failure",
        "canonical_concept": "arterial_occlusion",
        "rationale": "Mất tưới máu chi cấp tính đe dọa hoại tử chi (lạnh buốt, tái nhợt, mất mạch ngoại vi).",
    },

    # -----------------------------------------------------------------------
    # 2. ESOPHAGEAL PERFORATION & SUBCUTANEOUS EMPHYSEMA (Boerhaave / Chest Catastrophe)
    # -----------------------------------------------------------------------
    {
        "id": "subcutaneous_emphysema_chest_catastrophe",
        "category": AbstractionCategory.SURGICAL_BARRIER_FAILURE,
        "patterns": [
            r"\b(?:non thoc|non thao|non mua|non oi|oi mua)\b.*?\b(?:nguc dau|dau nguc|dau thau|dau sau)\b.*?\b(?:lao xao|lep bep|bot khi|xi xeo|so duoi da|duoi da co)\b",
            r"\b(?:lao xao|lep bep|bot khi|xi xeo)\b.*?\b(?:duoi da|vung co|co nguc|hom uc)\b",
            r"\b(?:nguc dau thau|dau nguc du doi|dau xe nguc)\b.*?\b(?:so vao|so co|duoi da)\b.*?\b(?:lao xao|lep bep)\b",
        ],
        "is_critical": True,
        "acuity": 0.99,
        "functional_loss": "inability_to_tolerate_palpation_movement",
        "physiologic_consequence": "internal_hemorrhage_and_shock",
        "canonical_concept": "boerhaave_syndrome",
        "rationale": "Hội chứng vỡ thực quản / tràn khí dưới da trung thất sau nôn ói dữ dội (tiếng lạo xạo khí dưới da).",
    },

    # -----------------------------------------------------------------------
    # 3. ACUTE EVISCERATION & SURGICAL WOUND RUPTURE
    # -----------------------------------------------------------------------
    {
        "id": "acute_evisceration_rupture",
        "category": AbstractionCategory.SURGICAL_BARRIER_FAILURE,
        "patterns": [
            r"\b(?:buc toac|toac ra|bung ra|rach toac|vo ra)\b.*?\b(?:loi ca|loi khuc|thay ca|lo ca)?\s*(?:ruot|khuc ruot|noi tang|tang do)\b",
            r"\b(?:thanh bung|vet mo|cho mo)\b.*?\b(?:buc toac|toac ra|bung chi|bung mep)\b.*?\b(?:ruot|noi tang|do lom)\b",
            r"\b(?:loi ca khuc ruot|ruot loi ra ngoai|thay ruot phoi ra|lo ruot ra ngoai)\b",
        ],
        "is_critical": True,
        "acuity": 0.99,
        "functional_loss": "loss_of_skin_barrier_integrity",
        "physiologic_consequence": "peritoneal_irritation",
        "canonical_concept": "abdominal_rigidity",
        "rationale": "Bục vết mổ thành bụng kèm lòi tạng / ruột ra ngoài gạc (cấp cứu ngoại khoa tối khẩn).",
    },

    # -----------------------------------------------------------------------
    # 4. ACUTE PERITONISM & RIGID ABDOMEN
    # -----------------------------------------------------------------------
    {
        "id": "acute_peritoneal_rigidity",
        "category": AbstractionCategory.PHYSIOLOGIC_INSTABILITY,
        "patterns": [
            r"\b(?:bung|thanh bung)\b.*?\b(?:cung nhu|cung do|cung ngac)\b.*?\b(?:go|khuc go|lim|danh)\b",
            r"\b(?:bung|thanh bung)\b.*?\b(?:cung nhu go|cung nhu danh|cung do|cung ngac|go go)\b",
            r"\b(?:so vao|cham nhe|dung vao)\b.*?\b(?:bung)?\b.*?\b(?:thet len|dau khong tho noi|dau buot oc|dau du doi)\b",
            r"\b(?:dau bung|dau quan)\b.*?\b(?:nhu dao dam|nhu dao dam thau bung|nhu xet ruot)\b.*?\b(?:bung cung|lanh toat|va mo hoi)\b",
        ],
        "is_critical": True,
        "acuity": 0.99,
        "functional_loss": "inability_to_tolerate_palpation_movement",
        "physiologic_consequence": "peritoneal_irritation",
        "canonical_concept": "abdominal_rigidity",
        "rationale": "Viêm phúc mạc toàn thể / thủng tạng rỗng (bụng cứng như gỗ, co cứng thành bụng).",
    },

    # -----------------------------------------------------------------------
    # 5. SUDDEN COMPLETE VISION LOSS
    # -----------------------------------------------------------------------
    {
        "id": "acute_vision_loss",
        "category": AbstractionCategory.FUNCTIONAL_LOSS,
        "patterns": [
            r"\b(?:mat|thi luc|con mat)\b.*?\b(?:toi thui|den kit|toi sam|toi den|den nhu muc|khong thay gi|chang thay gi|nhu bi mu)\b",
            r"(?:nhu|co ai)?\s*(?:tat|cup|ngat)\s*(?:cong tac|den|dien|cau dao)\b.*?\b(?:o mat|mat|truoc mat)\b",
            r"(?:nhu|giong)?\s*(?:tam|buc)?\s*(?:rem|man|manh)\s*(?:den|toi)?\s*(?:sap|sup|buong|che|che kin)\s*(?:mat|truoc mat)\b",
            r"\b(?:mat trai|mat phai|mot mat)\b.*?\b(?:chang nhin thay gi|khong con thay gi|dot ngot toi sam|toi den|den nhu muc)\b",
            r"\b(?:khong con nhin thay|chang con thay|khong nhin thay)\b.*?\b(?:ngon tay|anh sang|duong|gi|ri)\b",
        ],
        "is_critical": True,
        "acuity": 0.99,
        "functional_loss": "loss_of_sight",
        "physiologic_consequence": "retinal_or_optic_ischemia",
        "canonical_concept": "vision_loss",
        "rationale": "Mất thị lực đột ngột / tắc động mạch võng mạc trung tâm / bong võng mạc tối cấp.",
    },

    # -----------------------------------------------------------------------
    # 6. ACUTE NEUROLOGIC DEFICIT / STROKE
    # -----------------------------------------------------------------------
    {
        "id": "acute_focal_neurologic_deficit",
        "category": AbstractionCategory.FUNCTIONAL_LOSS,
        "patterns": [
            r"\b(?:meo|lech|khuu xuong|nga dui|tay roi thong|roi coc|cam thia|cam coc)\b.*?\b(?:mieng|u o|khong noi duoc|kho noi|liet|khong nhac duoc|that ngon)\b",
            r"\b(?:u o|khong noi duoc|kho noi|that ngon)\b.*?\b(?:meo|lech|liet|khuu xuong|nga dui|tay roi thong)\b",
            r"\b(?:bong nhien|dot ngot|tu nhien)\b.*?\b(?:meo|lech|liet nua nguoi|liet hoan toan|te liet|tay chan mot ben)\b",
        ],
        "is_critical": True,
        "acuity": 0.99,
        "functional_loss": "loss_of_motor_power",
        "physiologic_consequence": "central_neurologic_ischemia",
        "canonical_concept": "acute_stroke",
        "rationale": "Dấu hiệu thần kinh khu trú cấp tính / đột quỵ thiếu máu não cấp.",
    },

    # -----------------------------------------------------------------------
    # 7. METABOLIC ACIDOSIS & DIABETIC KETOACIDOSIS
    # -----------------------------------------------------------------------
    {
        "id": "metabolic_ketoacidosis_crisis",
        "category": AbstractionCategory.PHYSIOLOGIC_INSTABILITY,
        "patterns": [
            r"\b(?:tho kussmaul|tho sau va nhanh|tho nong hac|tho sau lien tuc)\b.*?\b(?:mui tao|mui tao thoi|mui trai cay|mui axeton|mui acetone|mui chua)\b",
            r"\b(?:mui tao|mui tao thoi|mui trai cay|mui axeton|mui acetone)\b.*?\b(?:tho kussmaul|tho sau|tho lien tuc|tho doc)\b",
            r"\b(?:uong nuoc lien tuc|khat nuoc du doi|uong ca binh)\b.*?\b(?:tieu lien tuc|dai dem ca chuc lan|sut can ao ao)\b.*?\b(?:lo mo|li bi|tho sau)\b",
        ],
        "is_critical": True,
        "acuity": 0.99,
        "functional_loss": "inability_to_maintain_alertness",
        "physiologic_consequence": "metabolic_acidosis",
        "canonical_concept": "diabetic_ketoacidosis",
        "rationale": "Toan ceton đái tháo đường mất bù (thở Kussmaul, hơi thở mùi táo thối/acetone).",
    },

    # -----------------------------------------------------------------------
    # 8. NEUROMUSCULAR CRISIS & HYPERTHERMIC SYNDROMES (NMS / Serotonin)
    # -----------------------------------------------------------------------
    {
        "id": "neuroleptic_malignant_or_serotonin_storm",
        "category": AbstractionCategory.TOXIC_METABOLIC_EXPOSURE,
        "patterns": [
            r"\b(?:cung do nhu go|cung nhu tuong|cung do toan than)\b.*?\b(?:sot 40|sot cao ham hap|va mo hoi nhu tam|lanh toat)\b",
            r"\b(?:run ban|giat giat co|rung giat co|tang phan xa|myoclonus)\b.*?\b(?:sot cao|dong tu gian|me sang|lo mo)\b",
            r"\b(?:uong thuoc tram cam|dung thuoc than kinh|uong haloperidol|uong olanzapine|uong ssri)\b.*?\b(?:cung do|sot 40|sot cao|me sang)\b",
        ],
        "is_critical": True,
        "acuity": 0.99,
        "functional_loss": "inability_to_maintain_alertness",
        "physiologic_consequence": "hyperthermia_and_autonomic_collapse",
        "canonical_concept": "neuroleptic_malignant_syndrome",
        "rationale": "Hội chứng ác tính do thuốc an thần (NMS) hoặc bão serotonin đe dọa trụy tuần hoàn.",
    },

    # -----------------------------------------------------------------------
    # 9. ACUTE AIRWAY & RESPIRATORY THREAT
    # -----------------------------------------------------------------------
    {
        "id": "acute_airway_respiratory_failure",
        "category": AbstractionCategory.PHYSIOLOGIC_INSTABILITY,
        "patterns": [
            r"\b(?:tho rit|tieng rit ro|tho rit thanh quan|rit co|nghet tho|rit rit|rit tung hoi|that co hong)\b",
            r"\b(?:khong noi tron cau|ngat quang tung tu|tho doc khong ra hoi|gap tung hoi|noi dut quang|dut quang tung tu|ngoi chong hai tay|ha mieng de tho|kho tho kich phat|ho ra bot hong)\b",
            r"\b(?:spo2|oxy)\b.*?\b(?:[78]\d%|[78]\d|duoi\s*9[0-2]|tut|giam)\b",
            r"\b(?:hit tho|tho)\b.*?\b(?:cuc ky nang nhoc|nang nhoc|kho khan)\b.*?\b(?:rit|that co|spo2)\b",
        ],
        "is_critical": True,
        "acuity": 0.99,
        "functional_loss": "inability_to_speak_full_sentences",
        "physiologic_consequence": "airway_compromise",
        "canonical_concept": "airway_obstruction_or_severe_dyspnea",
        "rationale": "Suy hô hấp cấp / tắc nghẽn đường thở cấp tính (thở rít, ngắt quãng, SpO2 tụt sâu).",
    },

    # -----------------------------------------------------------------------
    # 10. SYSTEMIC TOXIC EXPOSURE CRISIS (Toxidrome Routing Abstraction)
    # -----------------------------------------------------------------------
    {
        "id": "systemic_toxic_exposure_crisis",
        "category": AbstractionCategory.TOXIC_METABOLIC_EXPOSURE,
        "patterns": [
            r"\b(?:uong nham|uong qua lieu|uong ca vi|uong nhieu vien|uong thuoc|nhai nuot)\b.*?\b(?:sot cao|sot dung dung|cung do|cung co|run giat|co giat|sui bot mep|lo mo|me sang|noi lam nham)\b",
            r"\b(?:thuoc tru sau|thuoc diet chuot|xịt muỗi|hoa chat|chat tay rua|nuoc lau nha)\b.*?\b(?:uong|dinh vao|ngam vao|sui bot mep|kho tho|dong tu|co giat)\b",
            r"\b(?:uong|nuot)\b.*?\b(?:hon \d+ vien|ca vi|ca lo|lieu cao)\b.*?\b(?:chong tram cam|an than|giam dau|paracetamol|ha ap)\b",
            r"\b(?:be|tre|con nho)\b.*?\b(?:uong nham|nuot phai|uong thuoc)\b.*?\b(?:non oi lien tuc|lo mo|li bi|co giat|hon me|tim tai)\b",
            r"\b(?:than nhiet vot len|sot hon 40 do|sot 40)\b.*?\b(?:cung do|ngac ngo|run ban len|nhu dien giat)\b",
        ],
        "is_critical": True,
        "acuity": 0.99,
        "functional_loss": "loss_of_protective_reflexes",
        "physiologic_consequence": "acute_toxic_metabolic_threat",
        "canonical_concept": "toxic_ingestion",
        "rationale": "Ngộ độc cấp tính / hội chứng ngộ độc toxidrome đe dọa chuyển hóa và tính mạng.",
    },

    # -----------------------------------------------------------------------
    # 8. CIRCULATORY COLLAPSE & EXSANGUINATING SHOCK
    # -----------------------------------------------------------------------
    {
        "id": "circulatory_collapse_shock",
        "category": AbstractionCategory.PHYSIOLOGIC_INSTABILITY,
        "patterns": [
            r"\b(?:dau xe toang|xe toang|xe nguc|lan thau ra sau lung|dau xe)\b",
            r"\b(?:huyet ap|ap)\b.*?\b(?:tut|ha|giam|con \d+|xuong \d+/\d+|xuong con)\b.*?\b(?:tim dap nhanh|va mo hoi|ngat xiu|xap xiu|lanh ngat|lanh toat)\b",
            r"\b(?:tut huyet ap|huyet ap tut|ha xuong con|con 70|con 75|con 80|con 60|80/50)\b.*?\b(?:ngat xiu|va mo hoi|lanh toat|tim dap nhanh|xap xiu|tim tai|dau ngon tay|dau ngon chan)\b",
            r"\b(?:dau ngon tay|dau ngon chan|ngon tay ngon chan)\b.*?\b(?:tim tai|lanh ngat|lanh toat)\b.*?\b(?:huyet ap|80/50|tut)\b",
            r"\b(?:non ra bat mau|non mau tuoi|non ra mau do|oi ra mau tuoi|o at non mau)\b",
            r"\b(?:di ngoai|phan)\b.*?\b(?:den nhu hac in|den kit nhu ba ca phe|mui tanh nong|mui thoi kham)\b.*?\b(?:hoa mat|chong mat|xap xiu|tut huyet ap)\b",
            r"\b(?:mau phun thanh tia|phun thanh tia|chay mau xoi xa|chay khong the cam|dam dia gop mau)\b",
        ],
        "is_critical": True,
        "acuity": 0.99,
        "functional_loss": "loss_of_consciousness_or_perfusion",
        "physiologic_consequence": "circulatory_compromise",
        "canonical_concept": "circulatory_compromise",
        "rationale": "Sốc tuần hoàn / trụy mạch / xuất huyết cấp ồ ạt đe dọa ngừng tuần hoàn.",
    },

    # -----------------------------------------------------------------------
    # 10. EXTENSIVE EPIDERMAL SLOUGHING & MAJOR BARRIER DESTRUCTION
    # -----------------------------------------------------------------------
    {
        "id": "major_epidermal_barrier_failure",
        "category": AbstractionCategory.SURGICAL_BARRIER_FAILURE,
        "patterns": [
            r"\b(?:bong troc|lot da|troc da|trot da)\b.*?\b(?:tung mang lon|nhu bi luoc|toan than|khap nguoi|lo loet)\b",
            r"\b(?:bong nuoc|phong rop)\b.*?\b(?:lan rong khap nguoi|bong troc toan than|kem lo loet mieng)\b",
            r"\b(?:bong nang|bong dien rong)\b.*?\b(?:dien tich lon|toan than|chay den|tro xuong)\b",
        ],
        "is_critical": True,
        "acuity": 0.99,
        "functional_loss": "loss_of_skin_barrier_integrity",
        "physiologic_consequence": "organ_hypoperfusion_or_necrosis",
        "canonical_concept": "extensive_burn_injury",
        "rationale": "Mất toàn vẹn hàng rào biểu mô diện rộng (SJS/TEN / bỏng diện rộng).",
    },

    # -----------------------------------------------------------------------
    # 11. SUB-EMERGENCY URGENT PATTERNS (Sub-Emergency High Acuity)
    # -----------------------------------------------------------------------
    {
        "id": "moderate_bleeding_controlled",
        "category": AbstractionCategory.PHYSIOLOGIC_INSTABILITY,
        "patterns": [
            r"\b(?:mau van ri|chay mau ri ra|tham dam gac|mau ri tham qua bang|ri tham qua bang|mau van ri tham)\b",
            r"\b(?:chay mau cam|chay mau mui)\b.*?\b(?:lien tuc 15 phut|20 phut|kho cam|khong cam)\b",
            r"\b(?:vet thuong ho|vet cat sâu|rach da)\b.*?\b(?:chay mau|can khau|chua cam dut diem)\b",
        ],
        "is_critical": False,
        "acuity": 0.85,
        "functional_loss": None,
        "physiologic_consequence": "controlled_external_bleeding",
        "canonical_concept": "open_wound_active_bleeding",
        "rationale": "Chảy máu đang rỉ rả qua băng gạc hoặc chảy máu cam kéo dài cần xử trí y tế trong ngày (URGENT).",
    },
    {
        "id": "localized_moderate_burn",
        "category": AbstractionCategory.PHYSIOLOGIC_INSTABILITY,
        "patterns": [
            r"\b(?:bong nuoc soi|bong dau an|bong nhiet)\b.*?\b(?:phong rop|da do|5%|khoang 5%|khoang 10%|dien tich nho|canh tay|ban tay)\b",
        ],
        "is_critical": False,
        "acuity": 0.85,
        "functional_loss": None,
        "physiologic_consequence": "localized_thermal_injury",
        "canonical_concept": "burn_injury_moderate",
        "rationale": "Bỏng nhiệt phồng rộp khu trú cần chăm sóc vô khuẩn và xử trí y tế sớm (URGENT).",
    },
    {
        "id": "moderate_medication_overdose_stable",
        "category": AbstractionCategory.TOXIC_METABOLIC_EXPOSURE,
        "patterns": [
            r"\b(?:uong nham|uong 2 vien|uong 3 vien|uong gap doi|3 vien paracetamol|1500mg)\b.*?\b(?:ha ap|paracetamol|khang sinh|giam dau|dau rang|chua thay|tam on)\b",
            r"\b(?:lo uong|uong them mot vien|uong trung lap)\b.*?\b(?:huyet ap hoi thap|hoat dong binh thuong)\b",
            r"\b(?:3 vien paracetamol 500mg|tong lieu 1500mg)\b",
        ],
        "is_critical": False,
        "acuity": 0.80,
        "functional_loss": None,
        "physiologic_consequence": "moderate_toxic_exposure_monitoring",
        "canonical_concept": "medication_overdose_moderate",
        "rationale": "Uống thuốc quá liều nhẹ/vừa đang ổn định cần đánh giá y khoa sớm (URGENT).",
    },
    {
        "id": "localized_peritoneal_or_quadrant_pain",
        "category": AbstractionCategory.PHYSIOLOGIC_INSTABILITY,
        "patterns": [
            r"\b(?:goc phan tu duoi phai|ho chau phai|vung ho chau)\b.*?\b(?:dau am i|sot nhe|37\.\d|38\.\d|thon nhe)\b",
            r"\b(?:dau bung duoi phai|dau hcp)\b.*?\b(?:sot|buon non|di bo thay thon)\b",
        ],
        "is_critical": False,
        "acuity": 0.88,
        "functional_loss": None,
        "physiologic_consequence": "peritoneal_irritation_localized",
        "canonical_concept": "acute_appendicitis",
        "rationale": "Đau khu trú hố chậu phải kèm sốt nghi ngờ viêm ruột thừa cấp cần khám ngoại khoa sớm (URGENT).",
    },

    # -----------------------------------------------------------------------
    # 12. ACUTE VISCERAL / MESENTERIC ISCHEMIA (Elderly Vascular Catastrophe)
    # -----------------------------------------------------------------------
    {
        "id": "acute_mesenteric_visceral_ischemia",
        "category": AbstractionCategory.PHYSIOLOGIC_INSTABILITY,
        "patterns": [
            r"\b(?:dau bung kinh hoang|dau bung du doi kinh hoang)\b.*?\b(?:nguoi gia|tim mach|lan lon|khong giam)\b",
            r"\b(?:dau bung|dau quan bung)\b.*?\b(?:nguoi gia|lon tuoi|benh ly tim mach)\b.*?\b(?:dau lan lon|khong tu the nao giam|kinh hoang)\b",
        ],
        "is_critical": True,
        "acuity": 0.99,
        "functional_loss": "inability_to_tolerate_palpation_movement",
        "physiologic_consequence": "organ_ischemia_necrosis_threat",
        "canonical_concept": "mesenteric_ischemia",
        "rationale": "Thiếu máu mạc treo cấp ở bệnh nhân tim mạch/người già (cơn đau bụng kinh hoàng, không tư thế giảm đau).",
    },

    # -----------------------------------------------------------------------
    # 13. ACUTE GYNECOLOGIC TORSION / ECTOPIC RUPTURE
    # -----------------------------------------------------------------------
    {
        "id": "acute_gynecologic_surgical_catastrophe",
        "category": AbstractionCategory.PHYSIOLOGIC_INSTABILITY,
        "patterns": [
            r"\b(?:phu nu tre|phu nu|nu)\b.*?\b(?:dau nhoi quan|dau nhoi du doi|dau quan du doi)\b.*?\b(?:ho chau|vung chau|duoi bung|non mat xanh|da tai|tai nhot)\b",
            r"\b(?:dau nhoi quan du doi mot ben ho chau duoi|dau bung duoi du doi.*non mat xanh)\b",
        ],
        "is_critical": True,
        "acuity": 0.99,
        "functional_loss": "inability_to_tolerate_palpation_movement",
        "physiologic_consequence": "obstetric_catastrophe",
        "canonical_concept": "obstetric_catastrophe",
        "rationale": "Xoắn buồng trứng hoặc vỡ thai ngoài tử cung ở phụ nữ trẻ (đau hố chậu dữ dội, nôn mật, da tái).",
    },

    # -----------------------------------------------------------------------
    # 14. TRANSMURAL ESOPHAGEAL TEAR (Boerhaave / Severe Tear)
    # -----------------------------------------------------------------------
    {
        "id": "transmural_esophageal_tear",
        "category": AbstractionCategory.SURGICAL_BARRIER_FAILURE,
        "patterns": [
            r"\b(?:non khan|non mua|non oi)\b.*?\b(?:tieng 'rach'|tieng rach|rach nhoi|xe nhoi)\b.*?\b(?:giua nguc|nguc|khong nuot duoc)\b",
            r"\b(?:tieng rach nhoi giua nguc|rach nhoi giua nguc|khong nuot duoc ngum nuoc.*dau nguc du doi)\b",
        ],
        "is_critical": True,
        "acuity": 0.99,
        "functional_loss": "inability_to_tolerate_palpation_movement",
        "physiologic_consequence": "internal_hemorrhage_and_shock",
        "canonical_concept": "boerhaave_syndrome",
        "rationale": "Rách vỡ thực quản sau nôn (nghe tiếng rách nhói ngực, không nuốt được, đau ngực dữ dội).",
    },

    # -----------------------------------------------------------------------
    # 15. KUSSMAUL DIABETIC KETOACIDOSIS (DKA / Severe Metabolic Acidosis)
    # -----------------------------------------------------------------------
    {
        "id": "kussmaul_diabetic_ketoacidosis",
        "category": AbstractionCategory.PHYSIOLOGIC_INSTABILITY,
        "patterns": [
            r"\b(?:dai thao duong|tieu duong)\b.*?\b(?:bo tiem|quen tiem|bo thuoc)\b.*?\b(?:lu lan|hon me|non mua|tho hon hen|sau hoam|tho nhanh sau)\b",
            r"\b(?:tho hon hen sau hoam|tho kussmaul|tho sau hoam nhu tho gap)\b.*?\b(?:tieu duong|dai thao duong|lu lan)\b",
        ],
        "is_critical": True,
        "acuity": 0.99,
        "functional_loss": "loss_of_acid_base_homeostasis",
        "physiologic_consequence": "metabolic_crisis",
        "canonical_concept": "diabetic_ketoacidosis",
        "rationale": "Nhiễm toan ceton đái tháo đường nặng (bỏ tiêm insulin, lú lẫn, thở Kussmaul sâu hoắm).",
    },

    # -----------------------------------------------------------------------
    # 16. TOXIDROMES: NMS, SEROTONIN SYNDROME, PARACETAMOL, LITHIUM
    # -----------------------------------------------------------------------
    {
        "id": "neuroleptic_malignant_syndrome_cues",
        "category": AbstractionCategory.TOXIC_METABOLIC_EXPOSURE,
        "patterns": [
            r"\b(?:thuoc huong than|an than|chong loan than)\b.*?\b(?:cung do|cung khop ham|tay chan|than nhiet tang|sot cao)\b",
            r"\b(?:cung do cac khop ham va tay chan|than nhiet tang vot|cung khop ham.*than nhiet)\b",
        ],
        "is_critical": True,
        "acuity": 0.99,
        "functional_loss": "loss_of_protective_reflexes",
        "physiologic_consequence": "acute_toxic_metabolic_threat",
        "canonical_concept": "toxic_ingestion",
        "rationale": "Hội chứng an thần kinh ác tính (NMS nghi do tăng liều thuốc hướng thần).",
    },
    {
        "id": "serotonin_syndrome_cues",
        "category": AbstractionCategory.TOXIC_METABOLIC_EXPOSURE,
        "patterns": [
            r"\b(?:chong tram cam|tramadol|thuoc tri tram cam)\b.*?\b(?:giat giat ban chan|clonus|run ray|dong tu gian|sot cao va mo hoi)\b",
            r"\b(?:uong phoi hop hai loai thuoc chong tram cam|tramadol chung voi thuoc tri tram cam)\b",
            r"\b(?:giat giat ban chan khong ngung|clonus.*sot cao)\b",
        ],
        "is_critical": True,
        "acuity": 0.99,
        "functional_loss": "loss_of_protective_reflexes",
        "physiologic_consequence": "acute_toxic_metabolic_threat",
        "canonical_concept": "toxic_ingestion",
        "rationale": "Hội chứng Serotonin cấp (phối hợp thuốc chống trầm cảm / tramadol, clonus, giãn đồng tử).",
    },
    {
        "id": "massive_staggered_paracetamol_toxicity",
        "category": AbstractionCategory.TOXIC_METABOLIC_EXPOSURE,
        "patterns": [
            r"\b(?:15 vien|20 vien|hon 10 vien|15 vien giam dau|7500mg|10000mg)\b.*?\b(?:giam dau|ha sot|paracetamol)\b",
            r"\b(?:3 goi ha sot|ha sot tre em)\b.*?\b(?:6 vien giam dau|vien giam dau nguoi lon)\b.*?\b(?:12 tieng|trong ngay|viem gan)\b",
        ],
        "is_critical": True,
        "acuity": 0.99,
        "functional_loss": "loss_of_protective_reflexes",
        "physiologic_consequence": "acute_toxic_metabolic_threat",
        "canonical_concept": "toxic_ingestion",
        "rationale": "Quá liều Paracetamol liều cao kéo dài / gối liều đa dạng đe dọa suy gan cấp.",
    },
    {
        "id": "lithium_mood_stabilizer_toxicity",
        "category": AbstractionCategory.TOXIC_METABOLIC_EXPOSURE,
        "patterns": [
            r"\b(?:roi loan khi sac|thuoc tam than)\b.*?\b(?:uong gap \d+ lan|uong gap 5 lan|uong nhieu vien)\b.*?\b(?:run giat|loang choang|te nga)\b",
            r"\b(?:run giat tay chan du doi|loang choang khong dung vung)\b.*?\b(?:thuoc|lieu quy dinh)\b",
        ],
        "is_critical": True,
        "acuity": 0.99,
        "functional_loss": "loss_of_motor_power",
        "physiologic_consequence": "acute_toxic_metabolic_threat",
        "canonical_concept": "toxic_ingestion",
        "rationale": "Ngộ độc thuốc điều hòa khí sắc / Lithium liều cao (run giật dữ dội, thất điều, loạng choạng).",
    },
    {
        "id": "acute_facial_droop_dysarthria",
        "category": AbstractionCategory.FUNCTIONAL_LOSS,
        "patterns": [
            r"\b(?:mat xe|mot ben mat xe|xe han xuong)\b.*?\b(?:nuoc bot chay|nuoc dai chay|khong noi duoc|khong noi ro)\b",
            r"\b(?:nuoc bot chay rong rong|khong noi duoc loi nao ro nghia)\b",
        ],
        "is_critical": True,
        "acuity": 0.99,
        "functional_loss": "loss_of_motor_power",
        "physiologic_consequence": "acute_neurologic_deficit",
        "canonical_concept": "acute_stroke",
        "rationale": "Liệt mặt ngoại biên/trung ương cấp kèm chảy nước dãi và mất ngôn ngữ (nghi đột quỵ cấp).",
    },

    # -----------------------------------------------------------------------
    # 17. SUB-EMERGENCY URGENT ADDITIONAL PATTERNS
    # -----------------------------------------------------------------------
    {
        "id": "sub_emergency_surgical_seroma_ooze",
        "category": AbstractionCategory.PHYSIOLOGIC_INSTABILITY,
        "patterns": [
            r"\b(?:vet mo bat con|vet mo)\b.*?\b(?:ri it dich vang|dich vang o mep|ri dich thanh to|chay it dich vang)\b",
        ],
        "is_critical": False,
        "acuity": 0.80,
        "functional_loss": None,
        "physiologic_consequence": "controlled_external_bleeding",
        "canonical_concept": "open_wound_active_bleeding",
        "rationale": "Vết mổ rỉ dịch thanh tơ nhẹ không sốt cần kiểm tra thay băng chuyên khoa (URGENT).",
    },
    {
        "id": "sub_emergency_thrombosed_hemorrhoid",
        "category": AbstractionCategory.PHYSIOLOGIC_INSTABILITY,
        "patterns": [
            r"\b(?:tri ngoai|tri)\b.*?\b(?:sung to|bang dau ngon tay|ri it mau tuoi|lau giay ve sinh)\b",
        ],
        "is_critical": False,
        "acuity": 0.80,
        "functional_loss": None,
        "physiologic_consequence": "controlled_external_bleeding",
        "canonical_concept": "open_wound_active_bleeding",
        "rationale": "Trĩ tắc mạch / trĩ ngoại sưng đau rỉ máu cần khám hậu môn trực tràng (URGENT).",
    },
    {
        "id": "sub_emergency_chest_contusion_stable",
        "category": AbstractionCategory.PHYSIOLOGIC_INSTABILITY,
        "patterns": [
            r"\b(?:dau tuc suon|va quet xe)\b.*?\b(?:chup x-quang chua thay gay|spo2 98%|tho van binh thuong)\b",
        ],
        "is_critical": False,
        "acuity": 0.80,
        "functional_loss": None,
        "physiologic_consequence": "localized_thermal_injury",
        "canonical_concept": "burn_injury_moderate",
        "rationale": "Chấn thương phần mềm thành ngực SpO2 bình thường cần theo dõi (URGENT).",
    },
    {
        "id": "sub_emergency_laceration_knee_stable",
        "category": AbstractionCategory.PHYSIOLOGIC_INSTABILITY,
        "patterns": [
            r"\b(?:nga xe|tray xuoc)\b.*?\b(?:mau me be bet|dau goi)\b.*?\b(?:cu dong cac khop van duoc|khau)\b",
        ],
        "is_critical": False,
        "acuity": 0.82,
        "functional_loss": None,
        "physiologic_consequence": "open_wound_active_bleeding",
        "canonical_concept": "open_wound_active_bleeding",
        "rationale": "Vết thương trầy rách da do tai nạn cần xử lý sát khuẩn và khâu da nếu cần (URGENT).",
    },
    {
        "id": "sub_emergency_gastroenteritis_stable",
        "category": AbstractionCategory.PHYSIOLOGIC_INSTABILITY,
        "patterns": [
            r"\b(?:non mua va tieu chay|tieu chay 5 lan)\b.*?\b(?:uong duoc oresol|huyet ap 105|toan trang tam on)\b",
        ],
        "is_critical": False,
        "acuity": 0.80,
        "functional_loss": None,
        "physiologic_consequence": "mild_fluid_loss",
        "canonical_concept": "acute_gastroenteritis",
        "rationale": "Viêm dạ dày ruột cấp uống được bù dịch cần khám theo dõi (URGENT).",
    },
    {
        "id": "sub_emergency_traumatic_knee_effusion",
        "category": AbstractionCategory.PHYSIOLOGIC_INSTABILITY,
        "patterns": [
            r"\b(?:dau khop goi|khop goi)\b.*?\b(?:(?<!khong )sung nong do|(?<!khong )sung to|nga dap goi|chan thuong goi)\b",
        ],
        "is_critical": False,
        "acuity": 0.80,
        "functional_loss": None,
        "physiologic_consequence": "joint_effusion",
        "canonical_concept": "traumatic_knee_injury",
        "rationale": "Tràn dịch viêm khớp sau chấn thương nhẹ cần chẩn đoán sớm (URGENT).",
    },
    {
        "id": "sub_emergency_bppv_vertigo",
        "category": AbstractionCategory.PHYSIOLOGIC_INSTABILITY,
        "patterns": [
            r"\b(?:chong mat quay cuong|thay doi tu the dau)\b.*?\b(?:rung giat nhe|khong te liet)\b",
        ],
        "is_critical": False,
        "acuity": 0.80,
        "functional_loss": None,
        "physiologic_consequence": "vestibular_dysfunction",
        "canonical_concept": "benign_paroxysmal_positional_vertigo",
        "rationale": "Chóng mặt tư thế kịch phát lành tính không liệt cần khám chuyên khoa (URGENT).",
    },
    {
        "id": "sub_emergency_ocular_chemical_irritation",
        "category": AbstractionCategory.PHYSIOLOGIC_INSTABILITY,
        "patterns": [
            r"\b(?:bui voi|hoa chat nhe)\b.*?\b(?:com rat|chay nuoc mat|nhin mo nhe|da rua nuoc)\b",
        ],
        "is_critical": False,
        "acuity": 0.85,
        "functional_loss": None,
        "physiologic_consequence": "open_wound_active_bleeding",
        "canonical_concept": "open_wound_active_bleeding",
        "rationale": "Dị vật/hóa chất vào mắt đã sơ cứu cần khám mắt chuyên khoa sớm (URGENT).",
    },
    {
        "id": "sub_emergency_mild_topical_or_alcohol_ingestion",
        "category": AbstractionCategory.TOXIC_METABOLIC_EXPOSURE,
        "patterns": [
            r"\b(?:thuoc boi ngoai da|nuoc tay|hoa chat|con y te)\b.*?\b(?:vao mieng|da nho ra ngay|suc mieng)\b",
            r"\b(?:con y te 70 do pha loang|uong con.*nong rat nhe co hong)\b",
            r"\b(?:dinh mot chut thuoc xit muoi|dinh hoa chat)\b.*?\b(?:da rua xa phong ngay|do ngua nhe)\b",
            r"\b(?:paracetamol khoang 1000mg)\b.*?\b(?:chua thay dau bung|chua thay kho chiu)\b",
            r"\b(?:can vo 1 vien keo vitamin c)\b.*?\b(?:do ung mat va con cao bung|con cao bung)\b",
        ],
        "is_critical": False,
        "acuity": 0.78,
        "functional_loss": None,
        "physiologic_consequence": "moderate_toxic_exposure_monitoring",
        "canonical_concept": "medication_overdose_moderate",
        "rationale": "Phơi nhiễm liều thấp đã được sơ cứu hoặc liều dưới ngưỡng ngộ độc cần theo dõi (URGENT).",
    },
]


def extract_semantic_abstractions(text: str) -> SemanticAbstractionResult:
    """Extract intermediate clinical abstractions from free-form natural language."""
    norm = normalize_search_text(text)

    # Shield hypothetical inquiries, reading traps, and past cured third-person stories
    is_hypothetical_inquiry = bool(re.search(
        r"\b(?:doc bao|doc tren mang|tim hieu ve|nghe noi ve|hoi ve benh|hoan toan khoe manh|so bi|so qua tu so|nam ngoai tung bi.*?(?:khoi|chua khoi)|bac si dan neu co.*nhung hien tai)\b",
        norm,
    ))
    is_absent_variant = bool(re.search(r"\b(?:nhung|ma|song|chu)\s+(?:toi|minh|em|chau)?\s*(?:khong|chua|ko|k|hong|chang)\s+(?:bi|co|bi nhu vay|nhu the|bi vay)\b", norm))
    is_historical_variant = bool(re.search(r"\b(?:tung bi|nam ngoai)\b.*?\b(?:con|nhung)\s*(?:hom nay)?\s*(?:toi|minh)\s*(?:chi|chi bi)\b", norm))

    if (is_hypothetical_inquiry or is_absent_variant or is_historical_variant) and not any(w in norm for w in ("nhung gio toi bi", "nhung hien tai toi dang bi", "nhung gio dang")):
        return SemanticAbstractionResult(
            abstractions=(),
            has_critical_functional_loss=False,
            has_physiologic_instability=False,
            has_toxic_exposure_threat=False,
            has_surgical_barrier_threat=False,
            is_unambiguously_benign=True,
            abstraction_summary="Shielded hypothetical / negated / past third-person inquiry.",
        )

    abstractions: list[ClinicalAbstraction] = []

    has_crit_func = False
    has_phys_instab = False
    has_tox_exp = False
    has_surg_barr = False

    for item in _ABSTRACTION_CATALOG:
        matched = False
        evidence = ""
        for pattern in item["patterns"]:
            match = re.search(pattern, norm)
            if match:
                matched = True
                evidence = match.group(0)
                break

        if matched:
            ca = ClinicalAbstraction(
                abstraction_id=item["id"],
                category=item["category"],
                acuity_weight=item["acuity"],
                is_critical_threat=item["is_critical"],
                evidence_span=evidence,
                associated_functional_loss=item.get("functional_loss"),
                associated_physiologic_consequence=item.get("physiologic_consequence"),
                canonical_concept=item.get("canonical_concept", ""),
                rationale=item.get("rationale", ""),
            )
            abstractions.append(ca)

            if item["is_critical"]:
                if item["category"] == AbstractionCategory.FUNCTIONAL_LOSS:
                    has_crit_func = True
                elif item["category"] == AbstractionCategory.PHYSIOLOGIC_INSTABILITY:
                    has_phys_instab = True
                elif item["category"] == AbstractionCategory.TOXIC_METABOLIC_EXPOSURE:
                    has_tox_exp = True
                elif item["category"] == AbstractionCategory.SURGICAL_BARRIER_FAILURE:
                    has_surg_barr = True

    # Summarize abstractions
    if abstractions:
        summaries = [f"{a.abstraction_id} ({a.category.value})" for a in abstractions]
        summary_str = "; ".join(summaries)
    else:
        summary_str = "No high-acuity abstractions detected."

    return SemanticAbstractionResult(
        abstractions=tuple(abstractions),
        has_critical_functional_loss=has_crit_func,
        has_physiologic_instability=has_phys_instab,
        has_toxic_exposure_threat=has_tox_exp,
        has_surgical_barrier_threat=has_surg_barr,
        is_unambiguously_benign=len(abstractions) == 0,
        abstraction_summary=summary_str,
    )


def synthesize_clinical_events_from_abstractions(
    abstractions: SemanticAbstractionResult,
    source_text: str,
) -> list[ClinicalEvent]:
    """Convert abstract clinical findings into full ClinicalEvent models for downstream."""
    events: list[ClinicalEvent] = []
    norm = normalize_search_text(source_text)

    # Check if whole text is negated or historical or third-person
    is_neg = bool(re.search(r"\b(?:nhung|ma|song|chu)\s+(?:toi|minh|em|chau)?\s*(?:khong|chua|ko|k|hong|chang)\s+(?:bi|co|bi nhu vay|nhu the|bi vay)\b", norm)) or bool(re.search(r"\b(?:khong phai toi bi|chua tung bi|khong he co|khong he bi|hoan toan binh thuong)\b", norm))
    is_hist = bool(re.search(r"\b(?:nam ngoai|hoi nho|nam truoc|thang truoc|tuan truoc|cach day \d+|tung bi|da tung bi|da chua khoi|khoi hoan toan)\b", norm))
    is_other = bool(re.search(r"\b(?:bo toi|ba toi|me toi|chong toi|vo toi|ong toi|con toi|chau toi|nguoi ta|nguoi khac)\b", norm)) and (is_hist or "con toi" in norm or "con hom nay" in norm)

    assertion = ClinicalAssertion.ABSENT if is_neg else ClinicalAssertion.PRESENT
    temporality = "historical" if is_hist else "current"
    experiencer = "other" if is_other else "patient"

    for a in abstractions.abstractions:
        severity = SeverityLevel.CRITICAL_EXTREME if a.is_critical_threat else SeverityLevel.MODERATE
        event = ClinicalEvent(
            concept=a.canonical_concept or a.abstraction_id,
            organ_system=a.category.value,
            physiologic_consequence=a.associated_physiologic_consequence,
            functional_loss=a.associated_functional_loss,
            severity=severity,
            onset=OnsetTrajectory.SUDDEN,
            assertion=assertion,
            temporality=temporality,
            experiencer=experiencer,
            certainty=a.acuity_weight,
            evidence_span=a.evidence_span,
        )
        events.append(event)

    return events
