#!/usr/bin/env python3
"""Mutation Testing Suite for MedGuard AI.

Tests clinical decision boundary sharpness and semantic sensitivity by applying
systematic perturbations to emergency and non-emergency clinical presentations.

Evaluates whether the triage system:
  1. Correctly shifts urgency when clinical risk markers are added, removed, or negated.
  2. Resists patient rationalization / self-diagnosis traps (e.g. stress attribution).
  3. Avoids over-triage when emergency keywords are refuted by gradual onset or non-traumatic context.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.context import RequestContext
from app.models.triage import TriageRequest
from app.services.triage import evaluate_triage


@dataclass
class MutationNode:
    mutation_id: str
    description: str
    prompt: str
    expected_urgency: str
    rationale: str
    allowable_alt: str | None = None


@dataclass
class MutationTree:
    tree_id: str
    clinical_domain: str
    base_case: MutationNode
    mutations: list[MutationNode]


MUTATION_SUITE: list[MutationTree] = [
    MutationTree(
        tree_id="tree_01_chest_ischemia",
        clinical_domain="Acute Coronary / Chest Pain Boundaries",
        base_case=MutationNode(
            mutation_id="chest_base_emergency",
            description="Classic ACS presentation (Chest pressure + Dyspnea + Diaphoresis)",
            prompt="Bệnh nhân 55 tuổi đau thắt ngực đè nặng sau xương ức, khó thở và vã mồ hôi đầm đìa.",
            expected_urgency="EMERGENCY",
            rationale="High risk for STEMI/NSTEMI; mandatory ESI-2 Emergency triage.",
        ),
        mutations=[
            MutationNode(
                mutation_id="chest_mut_a_omit_sweat",
                description="Omit sweat (Chest pressure + Dyspnea)",
                prompt="Bệnh nhân 55 tuổi đau thắt ngực đè nặng sau xương ức và khó thở.",
                expected_urgency="EMERGENCY",
                rationale="Retrosternal chest pressure + dyspnea remains acute coronary red flag.",
            ),
            MutationNode(
                mutation_id="chest_mut_b_omit_dyspnea",
                description="Omit dyspnea (Chest pressure alone)",
                prompt="Bệnh nhân 55 tuổi cảm giác đau thắt ngực đè nặng như đá đè sau xương ức 20 phút nay, không khó thở.",
                expected_urgency="EMERGENCY",
                rationale="Heavy retrosternal pressure itself warrants immediate emergency workup.",
            ),
            MutationNode(
                mutation_id="chest_mut_c_musculoskeletal",
                description="Perturb to musculoskeletal wall tenderness",
                prompt="Tôi bị đau nhói ngực khi ấn mạnh tay vào khe xương sườn bên trái sau khi khiêng đồ nặng, không khó thở, không vã mồ hôi.",
                expected_urgency="ROUTINE",
                rationale="Reproducible focal chest wall tenderness without systemic red flags is benign chest wall strain.",
            ),
            MutationNode(
                mutation_id="chest_mut_d_reflux_pyrosis",
                description="Perturb to classic gastroesophageal reflux pyrosis",
                prompt="Cảm giác nóng rát cồn cào sau xương ức xuất hiện sau khi ăn no và nằm ngay, kèm ợ chua lên cổ, không khó thở, không đau lan đi đâu.",
                expected_urgency="ROUTINE",
                rationale="Positional postprandial pyrosis with acid reflux without exertional or systemic red flags.",
            ),
            MutationNode(
                mutation_id="chest_mut_e_stress_attribution_trap",
                description="Dangerous presentation with patient attributing to stress",
                prompt="Tôi bị đau thắt ngực đè nặng sau xương ức và vã mồ hôi lạnh, nhưng tôi nghĩ chỉ do căng thẳng làm việc deadline nhiều.",
                expected_urgency="EMERGENCY",
                rationale="System must NEVER dismiss objective ischemic signs based on patient stress rationalization.",
            ),
            MutationNode(
                mutation_id="chest_mut_f_subacute_pleuritic",
                description="Subacute mild chest discomfort on deep breath",
                prompt="Tôi bị đau tức ngực nhẹ mơ hồ kéo dài 3 tuần nay mỗi khi hít thở thật sâu, không khó thở, sinh hoạt bình thường.",
                expected_urgency="URGENT",
                rationale="Subacute duration (3 weeks) excludes acute coronary emergency, but warrants outpatient/urgent clinical evaluation.",
                allowable_alt="ROUTINE",
            ),
        ],
    ),
    MutationTree(
        tree_id="tree_02_anticoagulant_trauma",
        clinical_domain="Anticoagulant & Head Trauma Boundaries",
        base_case=MutationNode(
            mutation_id="anticoag_base_emergency",
            description="Anticoagulant therapy + acute blunt head trauma",
            prompt="Bệnh nhân đang uống thuốc chống đông Sintrom (warfarin) vừa bị trượt chân ngã đập đầu xuống sàn gạch cứng.",
            expected_urgency="EMERGENCY",
            rationale="High risk for delayed catastrophic intracranial hemorrhage; mandatory CT brain.",
        ),
        mutations=[
            MutationNode(
                mutation_id="anticoag_mut_a_no_trauma",
                description="Anticoagulant therapy without any trauma or bleed",
                prompt="Tôi đang uống thuốc chống đông Sintrom theo đơn bác sĩ, hôm nay không bị ngã hay va quẹt gì cả, chỉ muốn hỏi chế độ ăn uống.",
                expected_urgency="ROUTINE",
                rationale="Chronic medication consultation without trauma or bleeding signs is routine.",
            ),
            MutationNode(
                mutation_id="anticoag_mut_b_trivial_no_anticoag",
                description="Trivial head bump without anticoagulant therapy",
                prompt="Tôi không uống thuốc chống đông gì, lúc nãy vô tình quẹt nhẹ trán vào cánh tủ bếp chỉ hơi đỏ da không trầy xước không chóng mặt.",
                expected_urgency="ROUTINE",
                rationale="Minor bump with intact skin and normal sensorium in non-anticoagulated patient is routine.",
            ),
            MutationNode(
                mutation_id="anticoag_mut_c_trauma_drowsiness",
                description="Anticoagulant + trauma + altered sensorium",
                prompt="Người nhà đang dùng thuốc chống đông bị ngã va đầu, giờ gọi hỏi thấy buồn ngủ lơ mơ, trả lời chậm chạp.",
                expected_urgency="EMERGENCY",
                rationale="Anticoagulant + trauma + lethargy indicates acute developing intracranial hematoma.",
            ),
            MutationNode(
                mutation_id="anticoag_mut_d_spontaneous_hematoma",
                description="Anticoagulant with spontaneous large expanding hematoma",
                prompt="Bệnh nhân dùng thuốc chống đông máu tự nhiên thấy ở đùi xuất hiện một mảng bầm tím rất to lan rộng nhanh không rõ va đập.",
                expected_urgency="EMERGENCY",
                rationale="Spontaneous expanding hematoma under anticoagulation suggests over-anticoagulation/internal bleeding.",
                allowable_alt="URGENT",
            ),
        ],
    ),
    MutationTree(
        tree_id="tree_03_headache_thunderclap",
        clinical_domain="Headache & Thunderclap Boundaries",
        base_case=MutationNode(
            mutation_id="headache_base_emergency",
            description="True thunderclap headache (peaking within seconds)",
            prompt="Đau đầu dữ dội khởi phát đột ngột như sét đánh, đau đạt đỉnh khủng khiếp chỉ trong vòng 30 giây như nổ tung đầu.",
            expected_urgency="EMERGENCY",
            rationale="Classic subarachnoid hemorrhage presentation; immediate neuroimaging required.",
        ),
        mutations=[
            MutationNode(
                mutation_id="headache_mut_a_gradual_google_trap",
                description="Gradual 8h headache where user quotes 'thunderclap' from internet",
                prompt="Tôi bị đau đầu rất mạnh nhưng bắt đầu từ từ tăng dần suốt 8 tiếng qua, không nôn, không yếu liệt. Tôi gọi nó là đau đầu sét đánh vì đọc trên mạng thấy từ đó.",
                expected_urgency="URGENT",
                rationale="8-hour gradual progression clinically excludes thunderclap (peaking <1 min); severe headache needs urgent assessment, NOT 115 emergency dispatch.",
            ),
            MutationNode(
                mutation_id="headache_mut_b_tension_headache",
                description="Bilateral band-like headache after 10 hours at screen",
                prompt="Tôi bị nhức đầu ê ẩm hai bên thái dương như vòng thắt sau khi ngồi làm việc trước màn hình máy tính 10 tiếng liên tục, không nôn ói, không sốt.",
                expected_urgency="ROUTINE",
                rationale="Typical episodic tension-type headache associated with screen fatigue and stress.",
            ),
            MutationNode(
                mutation_id="headache_mut_c_meningismus",
                description="Headache + high fever + nuchal rigidity",
                prompt="Đau đầu dữ dội kèm sốt cao 39.5 độ, cổ cứng đờ không thể cúi cằm chạm vào ngực được.",
                expected_urgency="EMERGENCY",
                rationale="Signs of acute bacterial meningitis; emergency life-saving protocol.",
            ),
            MutationNode(
                mutation_id="headache_mut_d_cluster_autonomic",
                description="Unilateral orbital pain with tearing and conjunctival injection",
                prompt="Đau buốt dữ dội một bên hốc mắt trái xuất hiện lúc nửa đêm kèm chảy nước mắt ròng ròng và đỏ mắt, không yếu liệt.",
                expected_urgency="URGENT",
                rationale="Cluster headache presentation; intensely painful requiring urgent clinical evaluation and oxygen/triptan.",
                allowable_alt="EMERGENCY",
            ),
        ],
    ),
    MutationTree(
        tree_id="tree_04_respiratory_dyspnea",
        clinical_domain="Dyspnea & Respiratory Boundaries",
        base_case=MutationNode(
            mutation_id="resp_base_emergency",
            description="Acute severe respiratory failure with central cyanosis",
            prompt="Bệnh nhân khó thở dữ dội, tím tái môi và đầu ngón tay, vã mồ hôi, không nói được trọn một câu.",
            expected_urgency="EMERGENCY",
            rationale="Impending respiratory arrest; immediate 115 and oxygenation.",
        ),
        mutations=[
            MutationNode(
                mutation_id="resp_mut_a_mild_bronchospasm_relieved",
                description="Mild cold-induced bronchospasm relieved by inhaler",
                prompt="Thở khò khè nhẹ sau khi đi xe máy ngoài trời lạnh, vẫn nói chuyện nguyên câu bình thường, đã xịt ventolin 1 nhát thấy đỡ hẳn.",
                expected_urgency="ROUTINE",
                rationale="Mild reactive airway with immediate therapeutic response and normal conversational capability.",
                allowable_alt="URGENT",
            ),
            MutationNode(
                mutation_id="resp_mut_b_hyperventilation_anxiety",
                description="Hyperventilation syndrome after emotional conflict",
                prompt="Cảm thấy ngột ngạt khó thở sau khi cãi nhau căng thẳng, thở hổn hển liên tục kèm tê rần quanh miệng và ngón tay.",
                expected_urgency="URGENT",
                rationale="Hyperventilation syndrome with respiratory alkalosis symptoms; requires medical reassurance and rule-out.",
            ),
            MutationNode(
                mutation_id="resp_mut_c_suspected_pulmonary_embolism",
                description="Acute dyspnea after long-haul flight with unilateral leg swelling",
                prompt="Bệnh nhân đột ngột khó thở sau chuyến bay dài 12 tiếng từ châu Âu về, kèm theo bắp chân phải sưng to và đau buốt.",
                expected_urgency="EMERGENCY",
                rationale="DVT leading to acute Pulmonary Embolism; life-threatening emergency.",
            ),
        ],
    ),
    MutationTree(
        tree_id="tree_05_abdominal_pediatric",
        clinical_domain="Abdominal & Pediatric Boundaries",
        base_case=MutationNode(
            mutation_id="abdo_base_emergency",
            description="Toddler with episodic severe colic and bilious vomiting (Intussusception)",
            prompt="Bé 3 tuổi đau bụng dữ dội từng cơn, khóc thét co hai chân lên bụng, mặt tái nhợt và nôn ra dịch mật xanh.",
            expected_urgency="EMERGENCY",
            rationale="Pediatric surgical emergency (intussusception / intestinal obstruction).",
        ),
        mutations=[
            MutationNode(
                mutation_id="abdo_mut_a_postprandial_functional",
                description="Toddler mild postprandial bellyache continuing to play actively",
                prompt="Bé 3 tuổi sau khi ăn no kêu đau bụng quanh rốn một lúc, sau đó vẫn chạy nhảy cười đùa chơi đồ chơi bình thường, không nôn, bụng mềm.",
                expected_urgency="ROUTINE",
                rationale="Benign postprandial gastrocolic reflex in active child without red flags.",
            ),
            MutationNode(
                mutation_id="abdo_mut_b_appendicitis_peritonitis",
                description="RLQ abdominal pain with rebound tenderness",
                prompt="Đau bụng dưới bên phải âm ỉ tăng dần kèm sốt 38.2 độ, ấn vào hố chậu phải đau nhói buông tay ra đau giật nảy mình.",
                expected_urgency="EMERGENCY",
                rationale="Acute appendicitis with peritoneal sign (Blumberg sign).",
            ),
            MutationNode(
                mutation_id="abdo_mut_c_lactose_bloating",
                description="Transient bloating and single loose stool after cow milk",
                prompt="Tôi bị đầy hơi ậm ạch bụng sau khi uống cốc sữa tươi, đi ngoài phân lỏng một lần là êm bụng, không sốt không nôn.",
                expected_urgency="ROUTINE",
                rationale="Transient lactose intolerance / osmotic response.",
            ),
        ],
    ),
]


def run_mutation_testing() -> dict:
    ctx = RequestContext(
        request_id="mutation-runner",
        tenant_id="qa-ati",
        idempotency_key="mutation-key",
    )
    total_nodes = 0
    passed_nodes = 0
    failed_nodes = []
    tree_results = []

    print("=" * 80)
    print("MEDGUARD AI — MUTATION TESTING SUITE (CLINICAL DECISION BOUNDARIES)")
    print("=" * 80)

    for tree in MUTATION_SUITE:
        print(f"\n📂 [{tree.tree_id.upper()}] {tree.clinical_domain}")
        all_nodes = [tree.base_case] + tree.mutations
        tree_passes = 0

        for node in all_nodes:
            total_nodes += 1
            req = TriageRequest(
                patient_ref="patient-mutation",
                symptoms_text=node.prompt,
            )
            resp = evaluate_triage(req, ctx=ctx)
            pred = resp.urgency

            is_match = (pred == node.expected_urgency) or (
                node.allowable_alt and pred == node.allowable_alt
            )

            if is_match:
                passed_nodes += 1
                tree_passes += 1
                status_icon = "✅ PASS"
            else:
                status_icon = "❌ FAIL"
                failed_nodes.append(
                    {
                        "tree_id": tree.tree_id,
                        "mutation_id": node.mutation_id,
                        "prompt": node.prompt,
                        "expected": node.expected_urgency,
                        "predicted": pred,
                        "rationale": node.rationale,
                    }
                )

            print(
                f"  {status_icon} [{node.mutation_id}] "
                f"Pred: {pred:<9} | Exp: {node.expected_urgency:<9} | {node.description[:45]}"
            )

        tree_results.append(
            {
                "tree_id": tree.tree_id,
                "domain": tree.clinical_domain,
                "total": len(all_nodes),
                "passed": tree_passes,
                "rate": round(tree_passes / len(all_nodes) * 100, 2),
            }
        )

    accuracy = round(passed_nodes / total_nodes * 100, 2)
    print("\n" + "=" * 80)
    print(f"MUTATION SUMMARY: {passed_nodes}/{total_nodes} ({accuracy}%)")
    print("=" * 80)

    for tr in tree_results:
        print(f"  • {tr['tree_id']}: {tr['passed']}/{tr['total']} ({tr['rate']}%) — {tr['domain']}")

    if failed_nodes:
        print("\n⚠️ FAILURES DETECTED:")
        for f in failed_nodes:
            print(f"  - [{f['mutation_id']}] Exp: {f['expected']}, Got: {f['predicted']}")
            print(f"    Prompt: {f['prompt']}")
            print(f"    Rationale: {f['rationale']}")

    return {
        "total": total_nodes,
        "passed": passed_nodes,
        "failed": len(failed_nodes),
        "accuracy": accuracy,
        "trees": tree_results,
        "failures": failed_nodes,
    }


if __name__ == "__main__":
    result = run_mutation_testing()
    if result["failed"] > 0:
        sys.exit(1)
    sys.exit(0)
