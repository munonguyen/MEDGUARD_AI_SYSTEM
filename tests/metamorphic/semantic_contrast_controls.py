"""Meaning-Changing Semantic Context Controls for MedGuard AI Candidate V9.

Evaluates semantic abstraction and context-differentiation capabilities using
paired clinical presentations sharing linguistic surface features but possessing
opposite clinical risk profiles (Emergency vs Benign/Physiologic).

Target Gate:
Meaning-Changing Control Accuracy >= 95.0%
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.rules import triage_rules


@dataclass(frozen=True)
class SemanticContrastPair:
    pair_id: str
    domain: str
    high_risk_text: str
    benign_text: str
    differentiation_basis: str
    high_risk_expected: str = "EMERGENCY"
    benign_expected: str = "ROUTINE"


SEMANTIC_CONTRAST_PAIRS: list[SemanticContrastPair] = [
    SemanticContrastPair(
        pair_id="PAIR-01-CHEST",
        domain="Cardiopulmonary vs Musculoskeletal",
        high_risk_text="Ngực đè nặng dữ dội khi đi bộ gắng sức, vã mồ hôi hột và lan lên hàm trái.",
        benign_text="Ngực đau nhói khi ấn tay vào thành ngực sau buổi tập chống đẩy hôm qua, không khó thở hay vã mồ hôi.",
        differentiation_basis="Ischemic cardiac pressure with autonomic diaphoresis vs reproducible chest wall soreness after pushups.",
    ),
    SemanticContrastPair(
        pair_id="PAIR-02-VISION",
        domain="CRAO vs Chronic Refractive / Eyestrain",
        high_risk_text="Bỗng nhiên một bên mắt tối sầm hoàn toàn, đột ngột không nhìn thấy gì từ 15 phút trước.",
        benign_text="Mắt mờ nhẹ nhiều tháng nay do đục thủy tinh thể tuổi già và mỏi mắt sau khi nhìn màn hình máy tính.",
        differentiation_basis="Acute painless unilateral vision loss (CRAO/retinal detachment) vs chronic progressive cataract/eyestrain.",
    ),
    SemanticContrastPair(
        pair_id="PAIR-03-LIMB",
        domain="Acute Limb Ischemia vs Environmental Cold",
        high_risk_text="Bàn chân lạnh ngắt, da trắng bệch mất hết sắc hồng và bắt mạch chày sau không thấy đập.",
        benign_text="Hai bàn chân hơi lạnh do ngồi làm việc trong phòng điều hòa 18 độ quên đi tất, xoa ấm lại bình thường.",
        differentiation_basis="Unilateral acute ischemia with pallor and absent pulse vs physiologic vasoconstriction from air conditioning.",
    ),
    SemanticContrastPair(
        pair_id="PAIR-04-FACIAL",
        domain="Acute Stroke vs Dental Local Anesthesia",
        high_risk_text="Tự nhiên méo miệng lệch mặt sang một bên, nước bọt chảy dãi và tay phải yếu không cầm được thìa.",
        benign_text="Khóe miệng bị tê rần và hơi méo tạm thời sau khi vừa đi nha khoa nhổ răng khôn tiêm thuốc tê 1 tiếng trước.",
        differentiation_basis="Acute central/peripheral facial droop with limb weakness vs transient local dental nerve block.",
    ),
    SemanticContrastPair(
        pair_id="PAIR-05-ABDOMEN",
        domain="Peritonitis vs Functional Dyspepsia",
        high_risk_text="Bụng đau dữ dội như dao đâm, thành bụng co cứng như gỗ không dám thở mạnh.",
        benign_text="Bụng hơi tức lâm râm và đầy hơi chướng bụng sau khi ăn no bữa tiệc buffet tối nay.",
        differentiation_basis="Peritoneal irritation / board-like rigidity vs functional postprandial dyspepsia.",
    ),
    SemanticContrastPair(
        pair_id="PAIR-06-SYNCOPE",
        domain="Exertional Syncope vs Micturition Vasovagal",
        high_risk_text="Đột ngột ngất xỉu mất ý thức khi đang chạy bộ gắng sức trên máy tập thể dục.",
        benign_text="Cảm giác choáng váng ngất thoáng qua vài giây khi đang đi tiểu đêm rồi tỉnh táo lại bình thường ngay.",
        differentiation_basis="High-risk exertional syncope (malignant arrhythmia/AS) vs benign reflex micturition syncope.",
    ),
    SemanticContrastPair(
        pair_id="PAIR-07-WEAKNESS",
        domain="Focal Stroke vs Post-Gym Muscle Soreness",
        high_risk_text="Cánh tay trái tự nhiên yếu xìu rũ xuống, không thể giơ tay lên hay cầm cốc nước được.",
        benign_text="Hai bắp tay mỏi nhừ và hơi yếu cơ sau buổi tập tạ nặng nâng tạ 50kg ở phòng gym chiều qua.",
        differentiation_basis="Acute focal motor deficit vs delayed onset muscle soreness (DOMS) after weightlifting.",
    ),
    SemanticContrastPair(
        pair_id="PAIR-08-HEADACHE",
        domain="Subarachnoid Hemorrhage vs Tension Headache",
        high_risk_text="Đau đầu dữ dội như sét đánh búa bổ khởi phát đột ngột đạt đỉnh trong vài giây chưa từng bị bao giờ.",
        benign_text="Đau đầu âm ỉ hai bên thái dương do căng thẳng công việc sau cả ngày ngồi máy tính và thiếu ngủ.",
        differentiation_basis="Thunderclap headache (ruptured intracranial aneurysm) vs muscle contraction tension-type headache.",
    ),
    SemanticContrastPair(
        pair_id="PAIR-09-TOXIC",
        domain="Acute Herb Poisoning vs Routine Herbal Tea",
        high_risk_text="Sau khi uống một bát rượu ngâm củ ấu tàu lạ thì thấy tim đập chậm đờ đẫn, tê rần môi miệng và nôn mửa liên tục.",
        benign_text="Tôi vừa uống một cốc trà thảo mộc hoa cúc thông thường trước khi đi ngủ để dễ ngủ, sức khỏe hoàn toàn bình thường.",
        differentiation_basis="Aconitum alkaloid cardiotoxicity vs routine culinary chamomile herbal tea without symptoms.",
    ),
    SemanticContrastPair(
        pair_id="PAIR-10-PEDIATRIC",
        domain="Bulging Fontanelle vs Normal Infant Hunger Cry",
        high_risk_text="Bé 5 tháng sốt cao li bì, bỏ bú hoàn toàn và sờ thấy thóp trước phồng căng rõ rệt.",
        benign_text="Bé 5 tháng khóc đòi ăn vì đói sữa, bú xong thì ngủ ngoan, thóp trước phẳng và mềm bình thường.",
        differentiation_basis="Raised intracranial pressure in infant meningitis vs normal physiologic crying from hunger.",
    ),
    SemanticContrastPair(
        pair_id="PAIR-11-ALLERGY",
        domain="Anaphylactic Laryngeal Edema vs Mild Contact Rash",
        high_risk_text="Sau khi ăn tôm biển thì môi sưng phù to, thở rít thanh quản nghe rợn người và nuốt nghẹn không thở nổi.",
        benign_text="Chỉ hơi ngứa nhẹ thoáng qua ở cổ tay sau khi đeo đồng hồ dây kim loại mới mua, không khó thở hay sưng môi.",
        differentiation_basis="Impending airway collapse in anaphylaxis vs localized benign contact dermatitis.",
    ),
    SemanticContrastPair(
        pair_id="PAIR-12-RESPIRATORY",
        domain="Severe Asthma / Impending Failure vs Mild Common Cold",
        high_risk_text="Khó thở dữ dội tím tái môi, thở rên rỉ co kéo hõm ức, không thể nói trọn một câu phải ngồi chồm hổm.",
        benign_text="Hơi ngạt mũi chảy nước mũi trong và hắt hơi do cảm lạnh thông thường, thở êm và không co kéo.",
        differentiation_basis="Severe acute respiratory distress / asthma exacerbation vs mild upper respiratory tract viral infection.",
    ),
    SemanticContrastPair(
        pair_id="PAIR-13-BLEEDING",
        domain="Massive Upper GI Bleeding vs Minimal Gum Bleeding",
        high_risk_text="Nôn ra một thau máu đỏ tươi lẫn máu cục, đi ngoài phân đen như bã cà phê kèm choáng váng ngã quỵ.",
        benign_text="Chảy một chút xíu máu ở chân răng khi dùng bàn chải đánh răng cứng, súc miệng nước muối đã cầm ngay.",
        differentiation_basis="Hemorrhagic shock from bleeding peptic ulcer/esophageal varices vs minor mechanical gingivitis.",
    ),
    SemanticContrastPair(
        pair_id="PAIR-14-METABOLIC",
        domain="Diabetic Ketoacidosis vs Mild Sugar Craving",
        high_risk_text="Bệnh nhân tiểu đường type 1 thở nhanh sâu Kussmaul, hơi thở có mùi táo thối hoa quả, lơ mơ gọi hỏi đáp chậm.",
        benign_text="Hơi thèm đồ ngọt sau giờ làm việc buổi chiều, ăn một chiếc bánh quy xong cảm thấy sảng khoái bình thường.",
        differentiation_basis="Life-threatening diabetic ketoacidosis (DKA) vs transient benign physiological appetite/hypoglycemia cue.",
    ),
    SemanticContrastPair(
        pair_id="PAIR-15-PREGNANCY",
        domain="Severe Pre-Eclampsia / Imminent Eclampsia vs Mild Morning Sickness",
        high_risk_text="Sản phụ mang thai 34 tuần phù to toàn thân, đau đầu dữ dội nhìn mờ và co giật giật toàn thân.",
        benign_text="Phụ nữ mang thai 8 tuần hơi nghén buồn nôn vào buổi sáng khi ngửi mùi thức ăn, ăn chút gừng thì dễ chịu.",
        differentiation_basis="Eclamptic seizure / hypertensive crisis of pregnancy vs physiologic emesis gravidarum.",
    ),
]


def evaluate_semantic_contrast_pairs() -> dict[str, Any]:
    """Run evaluation on all 15 meaning-changing contrast pairs."""
    total_pairs = len(SEMANTIC_CONTRAST_PAIRS)
    passed_pairs = 0
    details: list[dict[str, Any]] = []

    for p in SEMANTIC_CONTRAST_PAIRS:
        res_high = triage_rules(p.high_risk_text)
        res_benign = triage_rules(p.benign_text)

        high_passed = res_high.urgency == p.high_risk_expected
        # For benign controls, success means NOT escalating to emergency (ROUTINE, URGENT, or non-emergency UNRESOLVED)
        benign_passed = res_benign.urgency != "EMERGENCY"

        pair_passed = high_passed and benign_passed
        if pair_passed:
            passed_pairs += 1

        details.append({
            "pair_id": p.pair_id,
            "domain": p.domain,
            "high_risk_act": res_high.urgency,
            "high_risk_expected": p.high_risk_expected,
            "high_risk_passed": high_passed,
            "benign_act": res_benign.urgency,
            "benign_expected": p.benign_expected,
            "benign_passed": benign_passed,
            "pair_passed": pair_passed,
            "differentiation_basis": p.differentiation_basis,
        })

    accuracy_pct = (passed_pairs / total_pairs * 100.0) if total_pairs > 0 else 0.0

    print("\n" + "=" * 85)
    print("MEDGUARD AI CANDIDATE V9 — MEANING-CHANGING SEMANTIC CONTRAST EVALUATION")
    print("=" * 85)
    print(f"Total Paired Controls: {total_pairs}")
    print(f"Passed Pairs:          {passed_pairs}/{total_pairs} ({accuracy_pct:.2f}%)")
    print(f"Target Gate:           >= 95.0% Accuracy")
    print(f"Status:                {'PASSED' if accuracy_pct >= 95.0 else 'FAILED'}")
    print("-" * 85)
    for d in details:
        status_sym = "[OK]" if d["pair_passed"] else "[FAIL]"
        print(f"  {status_sym} {d['pair_id']:<18} | High: {d['high_risk_act']} (Exp: {d['high_risk_expected']}) | Benign: {d['benign_act']} (Exp: {d['benign_expected']})")

    return {
        "total_pairs": total_pairs,
        "passed_pairs": passed_pairs,
        "accuracy_pct": round(accuracy_pct, 2),
        "target_met": accuracy_pct >= 95.0,
        "details": details,
    }


if __name__ == "__main__":
    evaluate_semantic_contrast_pairs()
