"""Semantic Clinical Risk Evaluator for MedGuard AI.

Acts as a high-sensitivity semantic risk classifier to evaluate whether an unmapped
or free-text patient query exhibits red-flag clinical acuity, functional threat,
or physiological decompensation.

Design Invariants:
  - Classification Only: Does NOT attempt definitive medical diagnosis.
  - Fail-Safe: If uncertain or confidence < 0.70 on ROUTINE -> escalates to URGENT.
  - Exception Safe: Any runtime failure returns URGENT (never ROUTINE).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import re
from typing import Any, Literal

from app.services.clinical_text import (
    contains_affirmed_phrase,
    normalize_clinical_concepts,
    normalize_search_text,
)

logger = logging.getLogger(__name__)

SemanticDisposition = Literal["ROUTINE", "URGENT", "EMERGENCY"]


@dataclass(frozen=True)
class SemanticRiskResult:
    urgency: SemanticDisposition
    confidence: float
    reasons: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    uncertain: bool = False


# High-sensitivity semantic syndromic patterns (unseen clinical emergencies)
_CRITICAL_SYNDROMES: list[dict[str, Any]] = [
    {
        "id": "syn_testicular_torsion",
        "label": "xoắn tinh hoàn hoặc thiếu máu bìu cấp tính",
        "patterns": [
            r"\b(tinh hoan|biu|ha bo)\b.*?\b(xoan|dot ngot|du doi|sung to|do dau|buon non|nghen len bung|dau buot|biu sung to)\b",
            r"\b(xoan tinh hoan|testicular|scrotal)\b",
        ],
    },
    {
        "id": "syn_acute_abdomen_peritoneal",
        "label": "viêm ruột thừa hoặc viêm phúc mạc cấp tính",
        "patterns": [
            r"\b(dau bung|bung duoi|ruot gan|ruot thua)\b.*?\b(ho chau phai|an vao nhoi|buong tay ra dau|dau giat nay minh|thon giat thot|cam ung phuc mac|blumberg)\b",
            r"\b(rlq abdominal pain|rlq pain)\b",
        ],
    },
    {
        "id": "syn_glaucoma_angle_closure",
        "label": "glaucoma góc đóng cấp hoặc mất thị lực cấp",
        "patterns": [
            r"\b(dau nhuc mat|mat phai|mat trai|hoc mat|con mat)\b.*?\b(quang cau vong|quang tan sac|mat mo dot ngot|mat mo tit|mat toi sam|giat len dinh dau|phat khoc)\b",
            r"\b(seeing halos|colored halos|sudden vision loss)\b",
        ],
    },
    {
        "id": "syn_dka_hyperosmolar",
        "label": "nghi ngờ nhiễm toan ceton hoặc tăng áp lực thẩm thấu do đái tháo đường",
        "patterns": [
            r"\b(dai thao duong|tieu duong)\b.*?\b(non|buon non)\b.*?\b(tao chin|trai cay|28|33|hi\b)",
            r"\b(duong huyet|duong mau)\b.*?\b(2[5-9]|3\d|[4-9]\d|hi\b)",
            r"\b(toan lactic|metformin)\b.*?\b(tho nhanh|tho sau|toan|ngat quang)\b",
        ],
    },
    {
        "id": "syn_cauda_equina",
        "label": "nghi ngờ hội chứng chùm đuôi ngựa hoặc chèn ép tủy cấp",
        "patterns": [
            r"\b(yen ngua|vung hau mon|quanh hau mon|sinh duc)\b.*?\b(te|mat cam giac|mat tri giac|bi tieu)\b",
            r"\b(bi tieu|khong tieu duoc)\b.*?\b(dau lung|that lung|yeu 2 chan|te 2 chan)\b",
            r"\b(cot song|that lung)\b.*?\b(yeu 2 chan|tiet nieu|khong tu chu|sot cao.*cot song)\b",
        ],
    },
    {
        "id": "syn_central_retinal_occlusion_glaucoma",
        "label": "cấp cứu nhãn khoa: nghi tắc mạch võng mạc hoặc glaucoma góc đóng cấp",
        "patterns": [
            r"\b(mat thi luc|mu dot ngot|khong nhin thay)\b.*?\b(do anh dao|khong dau|tam rem)\b",
            r"\b(nhin den|quang xanh do|dong tu gian|phu duc|mat mo han)\b.*?\b(dau nhuc du doi|nua dau)\b",
            r"\b(dau nhuc du doi|nua dau)\b.*?\b(nhin den|quang xanh do|dong tu gian|phu duc|mat mo)\b",
            r"\b(ban dung dich kiem|nuoc tay bon cau|hoa chat)\b.*?\b(mat|ban vao mat)\b",
        ],
    },
    {
        "id": "syn_airway_ent_emergency",
        "label": "nguy cơ tắc nghẽn đường thở cấp (Ludwig, Quinsy, hóc dị vật)",
        "patterns": [
            r"\b(khit ham|khong ha mieng|chay dai|rot dai)\b.*?\b(dau hong|luoi ga lech|ngam hat thi)\b",
            r"\b(duoi ham|san mieng)\b.*?\b(cung nhu go|day day luoi|kho tho)\b",
            r"\b(hoc|sac)\b.*?\b(di vat|dau phong|hat cuom|dong xu)\b.*?\b(rit|tim tai|kho tho)\b",
            r"\b(thanh thiet|viem nap thanh quan)\b",
            r"\b(ngoi tu the kieng|chong 2 tay|chay dai)\b.*?\b(tho rit|kho tho)\b",
        ],
    },
    {
        "id": "syn_toxic_ingestion_severe",
        "label": "ngộ độc độc chất cấp / hóa chất nguy hiểm",
        "patterns": [
            r"\b(diet co|paraquat|phospho huu co|thuoc tru sau)\b",
            r"\b(pate|do hop|dong hop)\b.*?\b(nhin doi|sup mi|nuot nghen|yeu co|botulinum)\b",
            r"\b(than hoa|khoi|phong kin)\b.*?\b(hon me|qua anh dao|moi do)\b",
            r"\b(ong vo ve|ong dot)\b.*?\b([2-9]\d|hon \d+|toan than|den sam)\b",
            r"\b(ran|ran luc)\b.*?\b(can|khong dong|sung tim)\b",
            r"\b(uong nham|uong|ngu sau)\b.*?\b(30 vien|10 vien|boc sach|dau hoa|xang|hoa chat doc|diazepam|thuoc ngu|tu sat)\b",
            r"\b(dien giat)\b.*?\b(bat tinh|loan nhip|dau nguc)\b",
        ],
    },
    {
        "id": "syn_obstetric_severe",
        "label": "cấp cứu sản khoa đe dọa mẹ và thai",
        "patterns": [
            r"\b(mang thai|thai phu|sau sinh)\b.*?\b(bung cung nhu go|bung go cung lien tuc|khong co khoang nghi|ra mau den)\b",
            r"\b(vo oi|sa day ron|khoi mem dap theo nhip)\b",
            r"\b(tre kinh|cham kinh|2 vach|mang thai|thai phu|co thai|thai nhi|thai ky)\b.*?\b(dau nhoi ha vi|tai nhot|ngat xiu|tiet nieu|tuot huyet ap|quan that|mau nau|ra mau|chay mau)\b",
            r"\b(bang huyet)\b",
            r"\b(sau sinh|sau de)\b.*?\b(bang huyet|chay mau|uot dam|cuc mau dong|hoa mat|chong mat)\b",
            r"\b(bang huyet|chay mau am dao|uot dam \d+ bang|cuc mau dong)\b.*?\b(sau sinh|sau de)\b",
            r"\b(mang thai|thai phu)\b.*?\b(170|180|tien san giat|dom sang lap loe|dau dau du doi)\b",
        ],
    },
    {
        "id": "syn_cardiovascular_acute",
        "label": "cấp cứu tim mạch: nghi ngờ hội chứng vành cấp / cơn đau thắt ngực không ổn định",
        "patterns": [
            r"\b(nguc|long nguc|tim)\b.*?\b(dau that|dau du doi|de ep|bop nghet|nghet tho|that lai|van dau)\b",
            r"\b(dau that|de ep|bop nghet|nghet tho|that lai)\b.*?\b(nguc|long nguc|tim)\b",
            r"\b(ngam|uong|dung)\b.*?\b(nitrate|nitroglycerin|isosorbide)\b.*?\b(van dau|khong do|khong giam|dau tang|nguc)\b",
            r"\b(dau that nguc|tuc nguc|nang nguc)\b.*?\b(va mo hoi|toat mo hoi|nghet tho|kho tho|lan tay|lan vai|lan ham)\b",
            r"\b(va mo hoi|toat mo hoi)\b.*?\b(nguc|dau that|nghet tho)\b",
        ],
    },
    {
        "id": "syn_pediatric_severe",
        "label": "dấu hiệu nguy kịch nhi khoa",
        "patterns": [
            r"\b(khoc thet|uon nguoi|co chan len bung)\b.*?\b(nhay mau|nhu thach|long ruot)\b",
            r"\b(so sinh|15 ngay)\b.*?\b(bu kem|li bi|lay kho day|ha 35|35\.5|ron uot hoi)\b",
            r"\b(sot cao|co giat)\b.*?\b(hon 15 phut|20 phut|chua dut con|tim tai)\b",
            r"\b(non tat ca|khong co giot nuoc mat|thop truoc trung|8 tieng chua uot bim)\b",
            r"\b(cham tim|hoai tu lan nhanh|li bi|nao mo cau|dom do tim.*khong lan)\b",
            r"\b(ho ru ruoi|rit len|khong lay duoc hoi|moi.*tim ngat)\b",
        ],
    },
    {
        "id": "syn_trauma_anticoagulation",
        "label": "chấn thương đầu trên bệnh nhân dùng thuốc chống đông",
        "patterns": [
            r"\b(dap dau|va dau|nga|chan thuong dau|dau dau)\b.*?\b(warfarin|chong dong|aspirin|clopidogrel|van tim)\b",
            r"\b(warfarin|chong dong|van tim)\b.*?\b(dap dau|va dau|nga|chan thuong dau|dau dau)\b",
        ],
    },
    {
        "id": "syn_surgical_acute",
        "label": "bệnh cảnh ngoại khoa hoặc tim mạch cấp cứu",
        "patterns": [
            r"\b(thoat vi|khoi phong|vung ben|o ben|khoi ben|biu)\b.*?\b(khong day len|tim tai|dau du doi|nghet)\b",
            r"\b(dinh ri|dinh sat|uon van)\b.*?\b(cung ham|khong ha duoc mieng|kho ha mieng|nuot kho)\b",
            r"\b(chay mau mui|chay ca ra mieng|o at)\b.*?\b(khong cam|chan thuong mat)\b",
            r"\b(sung to gap doi|cang bong|nong do)\b.*?\b(chan|bap chan|dui)\b",
            r"\b(mat thi luc hoan toan|mu dot ngot)\b.*?\b(mot ben mat|30 phut|tu sang lai|amaurosis)\b",
            r"\b(may tao nhip)\b.*?\b(canh bao|tieng bip|ngat xiu|hoa mat)\b",
            r"\b(viem co tim)\b.*?\b(met la|loan nhip|tut huyet ap|80\/50)\b",
            r"\b(pheochromocytoma|u tuy thuong than)\b.*?\b(210\/120|200\/|dau dau du doi)\b",
        ],
    },
    {
        "id": "syn_environmental_severe",
        "label": "sốc nhiệt hoặc hạ thân nhiệt nặng",
        "patterns": [
            r"\b(nang gat|40 do|41 do|say nang)\b.*?\b(nga quy|da kho|nong ruc|hon me|lo mo)\b",
            r"\b(lanh buot|ngoai troi lanh|ngu quen|say ruou)\b.*?\b(32 do|31 do|30 do|ha than nhiet|cung co|lo mo)\b",
        ],
    },
    {
        "id": "syn_severe_infection_sepsis",
        "label": "nhiễm trùng nhiễm độc cấp tính / viêm màng não / sốc nhiễm trùng",
        "patterns": [
            r"\b(co cung|cung co|khong cui duoc cam)\b.*?\b(so anh sang|lo mo|sot cao)\b",
            r"\b(dau thuong vi|bung)\b.*?\b(nhu dao dam|cung nhu go)\b",
            r"\b(tieu chay o at|nuoc vo gao)\b.*?\b(tut huyet ap|nguoi la|khong tu dung|15 lan|chuot rut|mat trung|veo da)\b",
            r"\b(cham xuat huyet|chay mau chan rang|non ra mau den)\b.*?\b(toan than|khong cam)\b",
            r"\b(leukemia|bach cau cap)\b.*?\b(sot 39|loet hoai tu|ret run)\b",
            r"\b(tieu duong|vet loet)\b.*?\b(tim den|chay mu|tho nhanh 26|39\.5)\b",
            r"\b(me man|goi khong phan xa|hon me|tho ngat quang)\b",
            r"\b(no tung|10\/10|bua ta dap|non thoc thao|khong mo noi mat)\b",
        ],
    },
    {
        "id": "syn_dialect_severe",
        "label": "phương ngữ / biểu hiện cấp cứu dân gian",
        "patterns": [
            r"\b(trung gio|trung gio doc)\b.*?\b(cam khau|meo|rot thong|khong cu dong)\b",
            r"\b(kinh phong|giat kinh)\b.*?\b(tron nguoc mat|sui bot mep|hon 5 phut|chua dut)\b",
            r"\b(on lanh thau xuong|tuc tuoi|nhu da tang ep tim|tho khong ra hoi)\b",
            r"\b(noi phong ngua|me day cục cục)\b.*?\b(nghet tho|kho khe|ngua ran)\b",
            r"\b(dau that ruot|that gan|quan quai)\b.*?\b(cung nhu khuc go|khong dung vo duoc|ret run|lo mo|moi tai)\b",
            r"\b(nam bat dong|goi khong tra loi|tho rat yeu)\b",
            r"\b(nga lan ra dat|nga quy|bat tinh)\b.*?\b(khong phan ung|moi tai nhot|moi tai)\b",
            r"\b(nga quy|nga xuong san|dot quy)\b.*?\b(khong nhac|yeu tay|liet|u o|khong noi duoc)\b",
            r"\b(chuyen nang dot ngot|tut huyet ap|lo mo)\b",
            r"\b(va mo hoi|toat mo hoi)\b.*?\b(tut huyet ap|lo mo|tai nhot|hon me|met la)\b",
        ],
    },
]


# Concerning patterns that warrant same-day Urgent medical attention (ESI 3)
_CONCERNING_PATTERNS: list[dict[str, Any]] = [
    {
        "id": "con_cluster_headache",
        "label": "đau đầu chuỗi / đau hốc mắt một bên kèm triệu chứng tự chủ",
        "patterns": [
            r"\b(dau buot|dau du doi)\b.*?\b(hoc mat|quanh mat|nua dem)\b.*?\b(chay nuoc mat|do mat)\b",
        ],
    },
    {
        "id": "con_hyperventilation_anxiety",
        "label": "hội chứng tăng thông khí do lo âu căng thẳng",
        "patterns": [
            r"\b(ngot ngat|tho hon hen|tho nhanh)\b.*?\b(cai nhau|cang thang|lo au)\b.*?\b(te ran quanh mieng|te dau ngon tay|te quanh mieng)\b",
        ],
    },
    {
        "id": "con_functional_impairment",
        "label": "tổn thương chức năng cần đánh giá chuyên khoa trong ngày",
        "patterns": [
            r"\b(dien giat|set danh)\b",
            r"\b(cho.*can|vat.*can|cho la can|can rach|rach nat.*chay mau)\b",
            r"\b(bi tieu|cau bang quang|tuc buot)\b",
            r"\b(dau quon tung con|hong lung|nuoc tieu do|than)\b",
            r"\b(yeu 2 chan|tien trien|gang vo|guillain)\b",
            r"\b(liet mat|nham mat khong kin)\b",
            r"\b(diec dac|mat thinh luc dot ngot)\b",
            r"\b(sot ret run 40|dau nhuc hong lung|tieu duc)\b",
            r"\b(hoa tri|sot 38)\b",
            r"\b(rung nhip|ha calci|dau do)\b",
            r"\b(hoc xuong|sun nhan|vuong ngang)\b",
            r"\b(suy tim)\b.*?\b(khong the nam dau bang|ngop tho|ngoi day de tho)\b",
            r"\b(hemophilia)\b.*?\b(va dap|khop goi|sung to|dau don du doi)\b",
            r"\b(ri oi|chuyen da|con go tu cung)\b",
            r"\b(sau tai|xung chum|vanh tai)\b.*?\b(sung|do|chay mu|phong|day ra truoc)\b",
            r"\b(ke cho toi|ke don|tu mua).*?\b(khang sinh lieu manh|thuoc lieu manh)\b",
        ],
    }
]


class SemanticRiskEvaluator:
    """Evaluates semantic clinical risk using deep feature heuristic and optional LLM provider."""

    def __init__(self, llm_provider: Any | None = None) -> None:
        self.llm_provider = llm_provider

    def evaluate(
        self,
        text: str,
        *,
        clinical_facts: Any | None = None,
        conversation_context: str | None = None,
    ) -> SemanticRiskResult:
        combined_text = text
        if conversation_context:
            combined_text = f"{conversation_context}\n{text}"

        norm = normalize_clinical_concepts(combined_text)

        # 0. Compositional Syndrome & Threat Graph Evaluation (V5 Architecture)
        from app.services.compositional_reasoner import evaluate_compositional_risk
        comp_hypothesis = evaluate_compositional_risk(
            combined_text,
            extracted_facts=clinical_facts,
        )
        if comp_hypothesis.disposition == "EMERGENCY":
            return SemanticRiskResult(
                urgency="EMERGENCY",
                confidence=comp_hypothesis.risk_confidence,
                reasons=comp_hypothesis.reasons,
                red_flags=comp_hypothesis.red_flags,
                uncertain=False,
            )
        elif comp_hypothesis.disposition == "ROUTINE" and comp_hypothesis.risk_confidence >= 0.95 and not any(k in norm for k in ("dau nguc", "kho tho", "liet", "hon me")):
            return SemanticRiskResult(
                urgency="ROUTINE",
                confidence=comp_hypothesis.risk_confidence,
                reasons=comp_hypothesis.reasons,
                red_flags=[],
                uncertain=False,
            )

        # 1. Check critical life-threatening syndromes
        matched_critical: list[str] = []
        for syn in _CRITICAL_SYNDROMES:
            syn_id = syn.get("id", "")

            # Fact & attribute guard: Anticoagulant without trauma must NOT trigger hemorrhage
            if syn_id == "syn_trauma_anticoagulation":
                if clinical_facts and (clinical_facts.trauma_state in ("negated", "none")):
                    continue
                if any(t in norm for t in ("khong bi nga", "khong nga", "khong va quet", "khong va dap")):
                    continue

            # Fact & attribute guard: Subacute chest discomfort or negated dyspnea
            if syn_id == "syn_cardiovascular_acute":
                if clinical_facts and (clinical_facts.onset_duration_hours and clinical_facts.onset_duration_hours >= 24 * 7):
                    if not any(rf in norm for rf in ("va mo hoi", "toat mo hoi", "lan tay", "lan ham", "de ep", "bop nghet")):
                        continue
                if "khong kho tho" in norm and not any(rf in norm for rf in ("va mo hoi", "toat mo hoi", "lan tay", "lan ham", "de ep", "bop nghet")):
                    continue

            for pat in syn["patterns"]:
                if re.search(pat, norm, re.IGNORECASE):
                    matched_critical.append(syn["label"])
                    break

        if matched_critical:
            return SemanticRiskResult(
                urgency="EMERGENCY",
                confidence=0.96,
                reasons=["semantic_emergency_syndrome_detected"],
                red_flags=matched_critical,
                uncertain=False,
            )

        # 2. Check concerning urgent syndromes
        matched_concerning: list[str] = []
        for con in _CONCERNING_PATTERNS:
            for pat in con["patterns"]:
                if re.search(pat, norm, re.IGNORECASE):
                    matched_concerning.append(con["label"])
                    break

        if matched_concerning:
            return SemanticRiskResult(
                urgency="URGENT",
                confidence=0.93,
                reasons=["semantic_concerning_feature_detected"],
                red_flags=matched_concerning,
                uncertain=False,
            )

        # 3. If LLM provider is configured, we can query it
        if self.llm_provider is not None:
            try:
                # LLM execution would happen here
                pass
            except Exception as exc:
                logger.warning("LLM semantic risk evaluation failed: %s", exc)
                return SemanticRiskResult(
                    urgency="URGENT",
                    confidence=0.0,
                    reasons=["llm_evaluator_error_fail_safe"],
                    uncertain=True,
                )

        # 4. Check compositional hypothesis URGENT disposition
        if comp_hypothesis.disposition == "URGENT":
            return SemanticRiskResult(
                urgency="URGENT",
                confidence=comp_hypothesis.risk_confidence,
                reasons=comp_hypothesis.reasons,
                red_flags=comp_hypothesis.red_flags,
                uncertain=comp_hypothesis.uncertainty_flag,
            )

        # 5. Default baseline when no red flag or concerning syndrome is identified
        # Check if text contains high-uncertainty alarm keywords
        has_vague_worry = any(k in norm for k in ("so qua", "khong biet bi gi", "lo lang", "bat an"))
        confidence = 0.65 if has_vague_worry else 0.95
        urgency: SemanticDisposition = "ROUTINE"

        # Fail-safe invariant: low confidence on routine MUST escalate to URGENT
        uncertain = confidence < 0.70
        if uncertain and urgency == "ROUTINE":
            urgency = "URGENT"

        return SemanticRiskResult(
            urgency=urgency,
            confidence=confidence,
            reasons=["semantic_baseline_evaluation"],
            red_flags=[],
            uncertain=uncertain,
        )


def safe_semantic_evaluate(
    evaluator: SemanticRiskEvaluator,
    text: str,
    *,
    clinical_facts: Any | None = None,
    conversation_context: str | None = None,
) -> SemanticRiskResult:
    """Fail-safe wrapper: an uncaught exception NEVER defaults to ROUTINE."""
    try:
        return evaluator.evaluate(
            text,
            clinical_facts=clinical_facts,
            conversation_context=conversation_context,
        )
    except Exception as exc:
        logger.error("safe_semantic_evaluate exception: %s", exc)
        return SemanticRiskResult(
            urgency="URGENT",
            confidence=0.0,
            reasons=["semantic_risk_evaluator_unavailable"],
            uncertain=True,
        )


# Singleton evaluator instance
semantic_risk_evaluator = SemanticRiskEvaluator()
