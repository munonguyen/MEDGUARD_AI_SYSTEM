#!/usr/bin/env python3
"""Metamorphic Testing Suite for MedGuard AI.

Evaluates semantic invariance across linguistically perturbed clinical descriptions.
For each clinical entity, 5 variants are tested:
  - Variant A: Formal clinical / medical terminology
  - Variant B: Folk / colloquial Vietnamese
  - Variant C: Teencode / unaccented / typo-dense Vietnamese
  - Variant D: English-Vietnamese code-switching
  - Variant E: Third-person / caregiver observational report

Metamorphic Invariant:
  Triage(A) == Triage(B) == Triage(C) == Triage(D) == Triage(E)
  EmergencyFlag(A) == EmergencyFlag(B) == EmergencyFlag(C) == EmergencyFlag(D) == EmergencyFlag(E)
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.context import RequestContext
from app.models.triage import TriageRequest
from app.services.triage import evaluate_triage


@dataclass
class MetamorphicVariant:
    variant_type: str  # 'A_formal', 'B_folk', 'C_teencode', 'D_code_switch', 'E_caregiver'
    text: str


@dataclass
class MetamorphicGroup:
    group_id: str
    syndrome_name: str
    expected_urgency: str
    expected_emergency: bool
    variants: list[MetamorphicVariant]


METAMORPHIC_SUITE: list[MetamorphicGroup] = [
    MetamorphicGroup(
        group_id="meta_01_stroke_fast",
        syndrome_name="Acute Ischemic Stroke (FAST Syndrome)",
        expected_urgency="EMERGENCY",
        expected_emergency=True,
        variants=[
            MetamorphicVariant(
                "A_formal",
                "Bệnh nhân đột ngột yếu liệt nửa người bên trái, méo mặt một bên và rối loạn ngôn ngữ diễn đạt.",
            ),
            MetamorphicVariant(
                "B_folk",
                "Ông nhà tôi tự nhiên trúng gió độc, miệng méo xệch một bên, tay trái rũ xuống không nhấc lên được.",
            ),
            MetamorphicVariant(
                "C_teencode",
                "me t tu nhien meo mieng noi k ro tay trai k nhac len dc",
            ),
            MetamorphicVariant(
                "D_code_switch",
                "My mother suddenly bị méo mặt, slurred speech và left arm completely weak.",
            ),
            MetamorphicVariant(
                "E_caregiver",
                "Tôi thấy mẹ tôi đang ngồi ăn cơm thì rơi thìa, tay trái buông thõng và nói ngọng líu nhíu.",
            ),
        ],
    ),
    MetamorphicGroup(
        group_id="meta_02_anaphylaxis",
        syndrome_name="Severe Anaphylaxis (Airway & Cutaneous)",
        expected_urgency="EMERGENCY",
        expected_emergency=True,
        variants=[
            MetamorphicVariant(
                "A_formal",
                "Bệnh nhân khó thở rít thanh quản, phù mạch vùng mi mắt và nổi mày đay toàn thân sau khi ăn tôm.",
            ),
            MetamorphicVariant(
                "B_folk",
                "Vừa ăn mấy con tôm xong là cổ họng nghẹn ứ không thở được, mắt húp híp, người nổi mẩn đỏ rần rần.",
            ),
            MetamorphicVariant(
                "C_teencode",
                "an tom xong bi sung phu mat k tho dc nghen co hong noi me day khap ng",
            ),
            MetamorphicVariant(
                "D_code_switch",
                "Sau khi ăn seafood bị anaphylaxis, sưng phù môi mắt and can not breathe.",
            ),
            MetamorphicVariant(
                "E_caregiver",
                "Cháu ăn hải sản xong tự nhiên ôm cổ họng thở khò khè nghẹt thở, mặt sưng vù lên.",
            ),
        ],
    ),
    MetamorphicGroup(
        group_id="meta_03_dka",
        syndrome_name="Diabetic Ketoacidosis (DKA)",
        expected_urgency="EMERGENCY",
        expected_emergency=True,
        variants=[
            MetamorphicVariant(
                "A_formal",
                "Bệnh nhân đái tháo đường type 1 nôn ói liên tục, thở nhanh sâu Kussmaul, hơi thở có mùi trái cây lên men.",
            ),
            MetamorphicVariant(
                "B_folk",
                "Bị tiểu đường mà từ sáng nôn thốc nôn tháo, khát nước dữ dội, người nhà ngửi thấy miệng thở ra mùi chua như hoa quả ủng.",
            ),
            MetamorphicVariant(
                "C_teencode",
                "tieu duong type 1 non ca ngay k an dc j tho nhanh hoi tho co mui trai cay len men",
            ),
            MetamorphicVariant(
                "D_code_switch",
                "Patient with type 1 diabetes nôn mửa liên tục, rapid breathing và breath smells like fruity acetone.",
            ),
            MetamorphicVariant(
                "E_caregiver",
                "Em gái tôi bị tiểu đường tuýp 1, hôm nay mệt lả nằm li bì, khát nước liên tục, thở dốc và hơi thở có mùi quả chín ủng.",
            ),
        ],
    ),
    MetamorphicGroup(
        group_id="meta_04_acute_glaucoma",
        syndrome_name="Acute Angle-Closure Glaucoma",
        expected_urgency="EMERGENCY",
        expected_emergency=True,
        variants=[
            MetamorphicVariant(
                "A_formal",
                "Đau nhức mắt dữ dội một bên lan lên nửa đầu, nhìn thấy quầng tán sắc cầu vồng quanh ánh đèn, mắt mờ đột ngột.",
            ),
            MetamorphicVariant(
                "B_folk",
                "Mắt phải đau buốt như kim châm giật lên đỉnh đầu, nhìn bóng đèn thấy quầng 7 sắc cầu vồng, mắt mờ tịt không thấy đường.",
            ),
            MetamorphicVariant(
                "C_teencode",
                "dau nhuc mat phai du doi nhin den co quang cau vong mat mo han k thay j",
            ),
            MetamorphicVariant(
                "D_code_switch",
                "Severe eye pain lan lên headache, seeing colored halos around lights và sudden vision loss.",
            ),
            MetamorphicVariant(
                "E_caregiver",
                "Mẹ tôi kêu đau buốt nhức buốt con mắt bên phải phát khóc, bảo nhìn đèn thấy cầu vồng và tự nhiên mắt tối sầm lại.",
            ),
        ],
    ),
    MetamorphicGroup(
        group_id="meta_05_cauda_equina",
        syndrome_name="Cauda Equina Syndrome",
        expected_urgency="EMERGENCY",
        expected_emergency=True,
        variants=[
            MetamorphicVariant(
                "A_formal",
                "Đau thắt lưng lan xuống hai chân kèm tê bì vùng yên ngựa quanh hậu môn và bí tiểu cấp tính.",
            ),
            MetamorphicVariant(
                "B_folk",
                "Đau lưng dữ dội buốt dọc hai giò, tê bì mất hết cảm giác chỗ đáy quần vùng kín, muốn đi tiểu mà rặn mãi không ra giọt nào.",
            ),
            MetamorphicVariant(
                "C_teencode",
                "dau lung lan 2 chan te vung yen ngua mat cam giac di tieu bi k tieu dc",
            ),
            MetamorphicVariant(
                "D_code_switch",
                "Lower back pain lan xuống cả 2 chân kèm saddle anesthesia và urinary retention không tiểu được.",
            ),
            MetamorphicVariant(
                "E_caregiver",
                "Bố tôi đau lưng gục xuống, hai chân bủn rủn, bảo quanh vùng bẹn hậu môn tê như tiêm thuốc tê và bụng căng tức vì bí tiểu cả ngày.",
            ),
        ],
    ),
    MetamorphicGroup(
        group_id="meta_06_muscle_strain_benign",
        syndrome_name="Benign Post-exercise Muscle Strain",
        expected_urgency="ROUTINE",
        expected_emergency=False,
        variants=[
            MetamorphicVariant(
                "A_formal",
                "Căng mỏi cơ hai bên bắp tay sau buổi tập tạ ngày hôm qua, vận động nhẹ nhàng thì đỡ, không sưng đau dữ dội.",
            ),
            MetamorphicVariant(
                "B_folk",
                "Hôm qua đi tập gym về nay hai cánh tay ê ẩm nhức mỏi, xoa bóp thì thấy dễ chịu, không bầm tím gì cả.",
            ),
            MetamorphicVariant(
                "C_teencode",
                "di tap ta ve bi moi co tay e am xoa bop thay do k sung gi",
            ),
            MetamorphicVariant(
                "D_code_switch",
                "Muscle soreness ở bắp tay after workout yesterday, no swelling, vận động nhẹ thấy ổn.",
            ),
            MetamorphicVariant(
                "E_caregiver",
                "Bạn tôi đi nâng tạ về kêu mỏi cơ hai bắp tay, sờ vào thấy hơi căng cứng nhưng không sưng không bầm.",
            ),
        ],
    ),
    MetamorphicGroup(
        group_id="meta_07_tension_headache_benign",
        syndrome_name="Benign Screen-Fatigue Tension Headache",
        expected_urgency="ROUTINE",
        expected_emergency=False,
        variants=[
            MetamorphicVariant(
                "A_formal",
                "Đau đầu âm ỉ hai bên thái dương như dải băng siết chặt sau nhiều giờ làm việc căng thẳng, không nôn ói, không sốt.",
            ),
            MetamorphicVariant(
                "B_folk",
                "Ngồi dán mắt vào máy tính cả ngày xong đầu cứ nặng trịch ê ẩm hai bên màng tang, xoa dầu nghỉ ngơi thì êm dần.",
            ),
            MetamorphicVariant(
                "C_teencode",
                "ngoi may tinh lau bi dau dau e am 2 ben thai duong k sot k non oi",
            ),
            MetamorphicVariant(
                "D_code_switch",
                "Mild tension headache hai bên thái dương do stress công việc, no vomiting, no fever.",
            ),
            MetamorphicVariant(
                "E_caregiver",
                "Chồng tôi ngồi làm đồ án suốt đêm kêu nhức đầu ê ẩm hai bên thái dương, uống cốc nước ấm nằm nghỉ thấy đỡ.",
            ),
        ],
    ),
    MetamorphicGroup(
        group_id="meta_08_appendicitis",
        syndrome_name="Acute Appendicitis (Peritoneal Irritation)",
        expected_urgency="EMERGENCY",
        expected_emergency=True,
        variants=[
            MetamorphicVariant(
                "A_formal",
                "Đau bụng khu trú vùng hố chậu phải kèm sốt nhẹ và nôn ói, đau tăng khi cử động hoặc ho.",
            ),
            MetamorphicVariant(
                "B_folk",
                "Bụng dưới bên phải đau nhói liên tục, người hâm hấp sốt, bước đi thốn giật thót cả ruột gan.",
            ),
            MetamorphicVariant(
                "C_teencode",
                "dau bung duoi ben phai sot nhe an vao nhoi buong ra dau thon",
            ),
            MetamorphicVariant(
                "D_code_switch",
                "RLQ abdominal pain tăng dần kèm low-grade fever, đau chói khi ho hay đi lại.",
            ),
            MetamorphicVariant(
                "E_caregiver",
                "Con gái tôi ôm bụng dưới bên phải khóc, người sốt nhẹ 38 độ, bảo con đi lại hay ho là đau thốn bụng.",
            ),
        ],
    ),
    MetamorphicGroup(
        group_id="meta_09_testicular_torsion",
        syndrome_name="Acute Testicular Torsion",
        expected_urgency="EMERGENCY",
        expected_emergency=True,
        variants=[
            MetamorphicVariant(
                "A_formal",
                "Đau dữ dội khởi phát đột ngột một bên tinh hoàn, bìu sưng to đỏ đau kèm buồn nôn.",
            ),
            MetamorphicVariant(
                "B_folk",
                "Đang ngủ tự nhiên tinh hoàn bên trái đau buốt nghẹn lên bụng, bìu sưng tấy to như quả trứng, buồn nôn cồn cào.",
            ),
            MetamorphicVariant(
                "C_teencode",
                "dau biu dot ngot du doi 1 ben sung to do dau kem buon non",
            ),
            MetamorphicVariant(
                "D_code_switch",
                "Sudden onset severe testicular pain kèm scrotal swelling và nausea buồn nôn.",
            ),
            MetamorphicVariant(
                "E_caregiver",
                "Cháu trai 14 tuổi đột ngột ôm hạ bộ kêu đau tinh hoàn dữ dội, bìu sưng to và nôn nao trong người.",
            ),
        ],
    ),
    MetamorphicGroup(
        group_id="meta_10_allergic_rhinitis_benign",
        syndrome_name="Mild Allergic Rhinitis",
        expected_urgency="ROUTINE",
        expected_emergency=False,
        variants=[
            MetamorphicVariant(
                "A_formal",
                "Ngứa mũi, hắt hơi liên tục thành tràng kèm chảy nước mũi trong sau khi tiếp xúc với phấn hoa, không sốt không khó thở.",
            ),
            MetamorphicVariant(
                "B_folk",
                "Cứ ngửi thấy mùi phấn hoa hay quét nhà là ngứa mũi nhảy mũi liên hồi, nước mũi chảy ròng ròng, người bình thường không mệt.",
            ),
            MetamorphicVariant(
                "C_teencode",
                "ngua mui hat hoi lien tuc chay nuoc mui trong k sot k kho tho",
            ),
            MetamorphicVariant(
                "D_code_switch",
                "Allergic rhinitis hắt xì liên tục chảy runny nose sau khi dọn nhà, no fever, no dyspnea.",
            ),
            MetamorphicVariant(
                "E_caregiver",
                "Mẹ tôi sáng dậy cứ hắt xì cả chục cái vì lạnh, xì ra nước mũi trong veo, ngoài ra ăn ngủ bình thường.",
            ),
        ],
    ),
]


def run_metamorphic_testing() -> dict:
    ctx = RequestContext(
        request_id="meta-runner",
        tenant_id="qa-ati",
        idempotency_key="meta-key",
    )
    total_groups = len(METAMORPHIC_SUITE)
    fully_invariant_groups = 0
    total_variants = 0
    correct_variants = 0
    group_summaries = []

    print("=" * 85)
    print("MEDGUARD AI — METAMORPHIC TESTING SUITE (LINGUISTIC PARAPHRASE INVARIANCE)")
    print("=" * 85)

    for group in METAMORPHIC_SUITE:
        print(f"\n🔬 [{group.group_id.upper()}] {group.syndrome_name}")
        variant_predictions = []
        is_group_perfect = True

        for var in group.variants:
            total_variants += 1
            req = TriageRequest(
                patient_ref="patient-meta",
                symptoms_text=var.text,
            )
            resp = evaluate_triage(req, ctx=ctx)
            pred_urgency = resp.urgency
            pred_emergency = resp.emergency_flag

            is_correct = (pred_urgency == group.expected_urgency) and (
                pred_emergency == group.expected_emergency
            )

            if is_correct:
                correct_variants += 1
                v_icon = "✅"
            else:
                is_group_perfect = False
                v_icon = "❌"

            variant_predictions.append(
                {
                    "variant": var.variant_type,
                    "pred_urgency": pred_urgency,
                    "pred_emergency": pred_emergency,
                    "correct": is_correct,
                    "text": var.text,
                }
            )

            print(
                f"  {v_icon} {var.variant_type:<14} | "
                f"Pred: {pred_urgency:<9} | Exp: {group.expected_urgency:<9} | {var.text[:42]}..."
            )

        # Check internal invariance across the 5 variants
        first_pred = variant_predictions[0]["pred_urgency"]
        is_internally_invariant = all(
            vp["pred_urgency"] == first_pred for vp in variant_predictions
        )

        if is_group_perfect and is_internally_invariant:
            fully_invariant_groups += 1
            g_status = "🏆 100% INVARIANT & ACCURATE"
        elif is_internally_invariant:
            g_status = "⚠️ INVARIANT BUT OFF-TARGET"
        else:
            g_status = "❌ VARIANT DIVERGENCE (INCONSISTENT)"

        print(f"  👉 Group Verdict: {g_status}")

        group_summaries.append(
            {
                "group_id": group.group_id,
                "syndrome": group.syndrome_name,
                "internally_invariant": is_internally_invariant,
                "perfect_accuracy": is_group_perfect,
                "predictions": variant_predictions,
            }
        )

    invariance_rate = round(fully_invariant_groups / total_groups * 100, 2)
    variant_acc = round(correct_variants / total_variants * 100, 2)

    print("\n" + "=" * 85)
    print("METAMORPHIC SUITE RESULTS")
    print("=" * 85)
    print(f"Total Syndromes / Groups:        {total_groups}")
    print(f"Fully Invariant & Accurate:       {fully_invariant_groups}/{total_groups} ({invariance_rate}%)")
    print(f"Total Perturbation Variants:      {total_variants}")
    print(f"Individual Variant Accuracy:      {correct_variants}/{total_variants} ({variant_acc}%)")
    print("=" * 85)

    return {
        "total_groups": total_groups,
        "fully_invariant_groups": fully_invariant_groups,
        "invariance_rate": invariance_rate,
        "total_variants": total_variants,
        "correct_variants": correct_variants,
        "variant_accuracy": variant_acc,
        "groups": group_summaries,
    }


if __name__ == "__main__":
    res = run_metamorphic_testing()
    if res["fully_invariant_groups"] < res["total_groups"]:
        sys.exit(1)
    sys.exit(0)
