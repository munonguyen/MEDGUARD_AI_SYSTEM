"""Critical Singleton Safety Benchmark for MedGuard AI Candidate V9.

Evaluates the Evidence Strength Scorer hierarchy and benign context exclusions across:
- 40+ True Critical Emergency Singletons
- 40+ Benign Mimics & Physiological Singletons

Target Gates:
- Critical Singleton Recall >= 99.0%
- Critical Singleton Precision >= 95.0%
- Benign Singleton False Escalation <= 2.0%
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.evidence_strength_scorer import (
    score_evidence_strength,
    SingletonEvidenceTier,
)


@dataclass(frozen=True)
class SingletonTestCase:
    case_id: str
    text: str
    is_critical_singleton: bool
    concept: str
    description: str


def generate_singleton_test_suite() -> list[SingletonTestCase]:
    cases: list[SingletonTestCase] = []

    # -------------------------------------------------------------------------
    # 44 POSITIVE CRITICAL SINGLETONS (Expect tier == CRITICAL_SINGLETON)
    # -------------------------------------------------------------------------
    # 1. Acute Unilateral Blindness (CRAO / Retinal Detachment) (8)
    cases.append(SingletonTestCase("SGT-POS-01", "Đột nhiên không nhìn thấy một mắt, tối sầm hoàn toàn từ 15 phút trước.", True, "acute_unilateral_blindness", "Sudden blindness in one eye"))
    cases.append(SingletonTestCase("SGT-POS-02", "Mắt tự nhiên mất thị lực một mắt, không nhìn thấy gì ở mắt trái.", True, "acute_unilateral_blindness", "Loss of vision in left eye"))
    cases.append(SingletonTestCase("SGT-POS-03", "Bỗng nhiên mù đột ngột một bên, mắt phải tối thui như tắt đèn.", True, "acute_unilateral_blindness", "Acute unilateral black out"))
    cases.append(SingletonTestCase("SGT-POS-04", "Tự nhiên không nhìn thấy gì ở một bên mắt từ sáng thức dậy.", True, "acute_unilateral_blindness", "Morning monocular vision loss"))
    cases.append(SingletonTestCase("SGT-POS-05", "Đột ngột không thấy gì ở 1 mắt, mắt mờ đen hoàn toàn không đau.", True, "acute_unilateral_blindness", "Painless monocular loss"))
    cases.append(SingletonTestCase("SGT-POS-06", "Tự nhiên một bên mắt tối thui chẳng thấy gì xung quanh nữa.", True, "acute_unilateral_blindness", "Colloquial monocular loss"))
    cases.append(SingletonTestCase("SGT-POS-07", "Đột nhiên chẳng thấy gì ở một mắt, mắt kia vẫn nhìn bình thường.", True, "acute_unilateral_blindness", "Acute unilateral loss"))
    cases.append(SingletonTestCase("SGT-POS-08", "Mắt một bên tối thui đột ngột, nhìn qua mắt đó chỉ thấy màn đen.", True, "acute_unilateral_blindness", "Monocular curtain blackout"))

    # 2. Acute Focal Limb Weakness / Hemiparesis (8)
    cases.append(SingletonTestCase("SGT-POS-09", "Đột ngột không giơ được tay phải, tay rơi rũ xuống không cử động được.", True, "acute_focal_limb_weakness", "Sudden arm drop"))
    cases.append(SingletonTestCase("SGT-POS-10", "Tay cầm cốc nước thấy yếu đột ngột, đánh rơi cốc nước vỡ tan.", True, "acute_focal_limb_weakness", "Sudden grip weakness"))
    cases.append(SingletonTestCase("SGT-POS-11", "Yếu liệt một bên tay chân, bước đi bị khuỵu chân đột ngột.", True, "acute_focal_limb_weakness", "Sudden leg buckling"))
    cases.append(SingletonTestCase("SGT-POS-12", "Cánh tay tự nhiên yếu xìu rũ xuống như mượn của ai không nhấc lên được.", True, "acute_focal_limb_weakness", "Colloquial limb weakness"))
    cases.append(SingletonTestCase("SGT-POS-13", "Bỗng nhiên một bên tay không cầm được đũa, rơi đồ liên tục.", True, "acute_focal_limb_weakness", "Sudden loss of hand motor function"))
    cases.append(SingletonTestCase("SGT-POS-14", "Đột nhiên không đi lại được vì một bên chân bị liệt mềm.", True, "acute_focal_limb_weakness", "Acute monoplegia leg"))
    cases.append(SingletonTestCase("SGT-POS-15", "Khuỵu chân đột ngột khi đang đứng, nửa người bên phải yếu hẳn.", True, "acute_focal_limb_weakness", "Sudden hemiparesis drop"))
    cases.append(SingletonTestCase("SGT-POS-16", "Tay cầm điện thoại rớt cái độp, cánh tay liệt không giơ lên được.", True, "acute_focal_limb_weakness", "Arm weakness drop sign"))

    # 3. Acute Facial Droop & Speech Impairment (8)
    cases.append(SingletonTestCase("SGT-POS-17", "Méo miệng đột ngột, miệng lệch hẳn sang một bên khi cười.", True, "acute_facial_droop_speech", "Sudden facial droop"))
    cases.append(SingletonTestCase("SGT-POS-18", "Tê rần khóe miệng và nước bọt chảy dãi một bên không ngậm miệng được.", True, "acute_facial_droop_speech", "Facial droop with drooling"))
    cases.append(SingletonTestCase("SGT-POS-19", "Đột ngột nói ngọng líu lưỡi, ú ớ không nói thành tiếng rõ ràng.", True, "acute_facial_droop_speech", "Sudden dysarthria"))
    cases.append(SingletonTestCase("SGT-POS-20", "Một bên mặt tự nhiên bị xệ xuống, khóe miệng chảy nước dãi liên tục.", True, "acute_facial_droop_speech", "Hemifacial sag with drool"))
    cases.append(SingletonTestCase("SGT-POS-21", "Cái miệng tự nhiên méo xẹo, nói chuyện ú ớ không ai nghe được.", True, "acute_facial_droop_speech", "Colloquial stroke facial sign"))
    cases.append(SingletonTestCase("SGT-POS-22", "Bỗng nhiên nói ngọng đột ngột và khóe môi bị lệch queo.", True, "acute_facial_droop_speech", "Regional facial droop speech"))
    cases.append(SingletonTestCase("SGT-POS-23", "Tự nhiên cứng lưỡi không nói được, nước bọt cứ tự ứa ra bên mép.", True, "acute_facial_droop_speech", "Aphasia with sialorrhea"))
    cases.append(SingletonTestCase("SGT-POS-24", "Mặt lệch đột ngột một bên kèm nói khó, người nhà nhìn thấy hoảng hốt.", True, "acute_facial_droop_speech", "Acute facial asymmetry"))

    # 4. Acute Limb Perfusion Deficit / Ischemia (8)
    cases.append(SingletonTestCase("SGT-POS-25", "Chân lạnh buốt trắng bệch, sờ vào mu chân không bắt được mạch.", True, "acute_limb_ischemia_sign", "Cold pale pulseless limb"))
    cases.append(SingletonTestCase("SGT-POS-26", "Cẳng chân tự nhiên lạnh ngắt tái mét, bắt mạch cổ chân không thấy đập.", True, "acute_limb_ischemia_sign", "Acute limb hypoperfusion"))
    cases.append(SingletonTestCase("SGT-POS-27", "Bàn chân lạnh giá mất mạch hoàn toàn, da trắng bệch như không có máu.", True, "acute_limb_ischemia_sign", "Pulseless pallid foot"))
    cases.append(SingletonTestCase("SGT-POS-28", "Một bên chân lạnh cóng trắng bệch sờ mạch chày sau không thấy gì.", True, "acute_limb_ischemia_sign", "Posterior tibial pulse loss"))
    cases.append(SingletonTestCase("SGT-POS-29", "Cái giò lạnh ngắt trắng bệch, rờ mạch cổ chân hổng thấy đập.", True, "acute_limb_ischemia_sign", "Regional cold leg pulseless"))
    cases.append(SingletonTestCase("SGT-POS-30", "Chân lạnh buốt tái mét sờ mạch không thấy đập gì hết.", True, "acute_limb_ischemia_sign", "No pulse cold leg"))
    cases.append(SingletonTestCase("SGT-POS-31", "Tay lạnh ngắt không bắt được mạch, da trắng nhợt không sắc máu.", True, "acute_limb_ischemia_sign", "Cold pale arm no pulse"))
    cases.append(SingletonTestCase("SGT-POS-32", "Chi dưới lạnh buốt da trắng bệch mất mạch ngoại vi.", True, "acute_limb_ischemia_sign", "Clinical peripheral pulse deficit"))

    # 5. Airway & Pediatric Emergencies (12)
    cases.append(SingletonTestCase("SGT-POS-33", "Thở rít thanh quản nghe rợn người, nuốt nghẹn không thở được.", True, "acute_stridor_airway_collapse", "Stridor airway obstruction"))
    cases.append(SingletonTestCase("SGT-POS-34", "Sưng phù môi lưỡi không thở được, cổ họng nghẹn ngào tím tái.", True, "acute_stridor_airway_collapse", "Angioedema airway collapse"))
    cases.append(SingletonTestCase("SGT-POS-35", "Tiếng thở rít rợn người kèm nghẹt thở co kéo hõm ức.", True, "acute_stridor_airway_collapse", "Severe laryngeal stridor"))
    cases.append(SingletonTestCase("SGT-POS-36", "Trẻ bú kém thóp phồng căng rõ rệt, sờ thóp trước thấy căng cứng.", True, "bulging_fontanelle_infant", "Infant bulging fontanelle"))
    cases.append(SingletonTestCase("SGT-POS-37", "Thóp bé phồng lên căng cứng kèm sốt li bì.", True, "bulging_fontanelle_infant", "Tense bulging fontanelle"))
    cases.append(SingletonTestCase("SGT-POS-38", "Sờ thóp trước bé thấy căng phồng nhô cao khác thường.", True, "bulging_fontanelle_infant", "Bulging anterior fontanelle"))
    cases.append(SingletonTestCase("SGT-POS-39", "Thở rít thanh quản dữ dội sau khi nuốt phải dị vật.", True, "acute_stridor_airway_collapse", "Stridor after choking"))
    cases.append(SingletonTestCase("SGT-POS-40", "Thóp phồng ở trẻ sơ sinh 2 tháng tuổi kèm bỏ bú.", True, "bulging_fontanelle_infant", "Neonate bulging fontanelle"))
    cases.append(SingletonTestCase("SGT-POS-41", "Đột nhiên không nhìn thấy một mắt từ 30 phút nay.", True, "acute_unilateral_blindness", "Acute monocular blindness"))
    cases.append(SingletonTestCase("SGT-POS-42", "Đột ngột không giơ được tay, liệt một bên cánh tay.", True, "acute_focal_limb_weakness", "Sudden arm paralysis"))
    cases.append(SingletonTestCase("SGT-POS-43", "Méo miệng đột ngột và chảy nước dãi một bên.", True, "acute_facial_droop_speech", "Acute facial droop drool"))
    cases.append(SingletonTestCase("SGT-POS-44", "Chân lạnh ngắt trắng bệch sờ mạch không thấy đập.", True, "acute_limb_ischemia_sign", "Cold limb pulseless"))

    # -------------------------------------------------------------------------
    # 44 BENIGN / PHYSIOLOGICAL CONTROLS (Expect tier != CRITICAL_SINGLETON)
    # -------------------------------------------------------------------------
    # 1. Benign Mimics of Facial Droop (Post-dental procedure) (8)
    cases.append(SingletonTestCase("SGT-NEG-01", "Méo miệng và tê rần khóe miệng vì vừa nhổ răng khôn tiêm thuốc tê ở nha khoa.", False, "benign_facial", "Dental local anesthesia"))
    cases.append(SingletonTestCase("SGT-NEG-02", "Khóe môi hơi lệch và tê sau khi vừa đi trám răng tiêm tê 1 tiếng trước.", False, "benign_facial", "Dental filling local anesthetic"))
    cases.append(SingletonTestCase("SGT-NEG-03", "Nửa bên miệng bị tê rần và hơi méo tạm thời do tác dụng của thuốc tê nha khoa.", False, "benign_facial", "Dental nerve block transient"))
    cases.append(SingletonTestCase("SGT-NEG-04", "Vừa nhổ răng số 8 về thấy khoé miệng hơi xệ và tê bì môi, nha sĩ dặn vài tiếng sẽ hết.", False, "benign_facial", "Post-extraction numbness"))
    cases.append(SingletonTestCase("SGT-NEG-05", "Bọc răng sứ có tiêm thuốc tê nên miệng cười hơi méo một bên, hết thuốc tê sẽ bình thường.", False, "benign_facial", "Crown procedure anesthetic"))
    cases.append(SingletonTestCase("SGT-NEG-06", "Sau khi tiêm tê nhổ răng thấy nước bọt hơi chảy mép vì môi mất cảm giác tạm thời.", False, "benign_facial", "Local anesthetic drool"))
    cases.append(SingletonTestCase("SGT-NEG-07", "Đi nha khoa cạo vôi và gây tê lợi nên miệng hơi lệch một bên khi nói.", False, "benign_facial", "Dental periodontal numbness"))
    cases.append(SingletonTestCase("SGT-NEG-08", "Mới nhổ răng xong thuốc tê chưa tan hết nên miệng méo xệch nhẹ, không có triệu chứng gì khác.", False, "benign_facial", "Resolving dental numbness"))

    # 2. Benign Mimics of Limb Weakness (Post-gym / Muscle Fatigue) (8)
    cases.append(SingletonTestCase("SGT-NEG-09", "Tay yếu và mỏi cơ bắp tay vì vừa tập tạ nặng 40kg ở phòng gym chiều qua.", False, "benign_weakness", "Post-weightlifting DOMS"))
    cases.append(SingletonTestCase("SGT-NEG-10", "Hai cánh tay mỏi nhừ sau khi hít đất 50 cái, cảm giác tay yếu sức tạm thời.", False, "benign_weakness", "Post-pushup fatigue"))
    cases.append(SingletonTestCase("SGT-NEG-11", "Cơ đùi và bắp chân mỏi yếu sau buổi chạy bộ 10km ngày hôm qua.", False, "benign_weakness", "Post-marathon leg soreness"))
    cases.append(SingletonTestCase("SGT-NEG-12", "Mỏi cơ sau tập gym nặng, hai tay cầm cốc nước thấy hơi run mỏi cơ thông thường.", False, "benign_weakness", "Post-workout tremor fatigue"))
    cases.append(SingletonTestCase("SGT-NEG-13", "Vừa tập thể dục đẩy tạ xong thấy tay yếu mỏi, nghỉ ngơi xoa bóp cơ thấy đỡ dần.", False, "benign_weakness", "Post-exercise muscle soreness"))
    cases.append(SingletonTestCase("SGT-NEG-14", "Chân tay hơi mỏi yếu sau một ngày dọn dẹp nhà cửa bê vác đồ đạc nặng.", False, "benign_weakness", "Physical labor fatigue"))
    cases.append(SingletonTestCase("SGT-NEG-15", "Hôm qua tập tạ vai nên hôm nay cơ tay yếu mỏi nhức cơ sinh lý.", False, "benign_weakness", "Shoulder workout DOMS"))
    cases.append(SingletonTestCase("SGT-NEG-16", "Cánh tay mỏi cơ sau tập thể thao đánh cầu lông 2 tiếng liền.", False, "benign_weakness", "Badminton muscle fatigue"))

    # 3. Benign Mimics of Visual Loss (Dirty Glasses / Eyestrain / Chronic Cataract) (8)
    cases.append(SingletonTestCase("SGT-NEG-17", "Mắt mờ do kính bẩn dính dấu vân tay chưa lau, lau kính xong nhìn rõ bình thường.", False, "benign_vision", "Dirty eyeglasses blur"))
    cases.append(SingletonTestCase("SGT-NEG-18", "Mắt hơi mờ và mỏi mắt sau khi nhìn màn hình máy tính liên tục 8 tiếng làm việc.", False, "benign_vision", "Digital eyestrain asthenopia"))
    cases.append(SingletonTestCase("SGT-NEG-19", "Mắt mờ nhiều tháng nay do đục thủy tinh thể tuổi già ở người 75 tuổi.", False, "benign_vision", "Chronic senile cataract"))
    cases.append(SingletonTestCase("SGT-NEG-20", "Bụi bay vào mắt gây cay mắt chảy nước mắt và mờ mắt tạm thời, rửa nước muối đã hết.", False, "benign_vision", "Foreign body eye irritation"))
    cases.append(SingletonTestCase("SGT-NEG-21", "Mắt mờ dần nhiều năm nay do tật khúc xạ cận thị chưa thay kính mới.", False, "benign_vision", "Chronic refractive error"))
    cases.append(SingletonTestCase("SGT-NEG-22", "Mỏi mắt nhìn máy tính cả ngày thấy mắt mờ nhoè, chớp mắt nhỏ thuốc nhỏ mắt lại đỡ.", False, "benign_vision", "Computer vision syndrome"))
    cases.append(SingletonTestCase("SGT-NEG-23", "Mắt mờ thoáng qua do dụi mắt mạnh sau khi ngủ dậy, một lát sau bình thường.", False, "benign_vision", "Post-rubbing transient blur"))
    cases.append(SingletonTestCase("SGT-NEG-24", "Mắt nhìn hơi mờ vì chưa lau kính cận bám đầy bụi đường.", False, "benign_vision", "Dusty spectacles blur"))

    # 4. Benign Mimics of Cold Limbs (Environmental Cold / Air Conditioning) (8)
    cases.append(SingletonTestCase("SGT-NEG-25", "Chân hơi lạnh do ngồi phòng điều hòa 18 độ bật quạt cả buổi sáng quên đi tất.", False, "benign_cold", "AC room cold feet"))
    cases.append(SingletonTestCase("SGT-NEG-26", "Hai bàn chân lạnh vì trời lạnh mùa đông miền Bắc nhiệt độ 12 độ C, đi tất ấm lại hết.", False, "benign_cold", "Winter environmental cold"))
    cases.append(SingletonTestCase("SGT-NEG-27", "Đầu ngón tay hơi lạnh do ngồi phòng máy lạnh làm việc, mạch đập bình thường.", False, "benign_cold", "Air conditioner fingers cold"))
    cases.append(SingletonTestCase("SGT-NEG-28", "Chân lạnh do đi mưa bị ướt giày, về nhà sấy khô chân ấm áp lại bình thường.", False, "benign_cold", "Rainwater wet cold feet"))
    cases.append(SingletonTestCase("SGT-NEG-29", "Hai bàn chân hơi lạnh khi ngồi làm việc trên nền gạch hoa mùa lạnh.", False, "benign_cold", "Cold tile floor contact"))
    cases.append(SingletonTestCase("SGT-NEG-30", "Bàn tay lạnh buốt vì vừa rửa tay bằng nước đá lạnh trong tủ lạnh.", False, "benign_cold", "Ice water cold contact"))
    cases.append(SingletonTestCase("SGT-NEG-31", "Chân lạnh vì ngồi điều hòa cả ngày, xoa hai bàn chân vào nhau thấy ấm lên ngay.", False, "benign_cold", "AC room physiologic chill"))
    cases.append(SingletonTestCase("SGT-NEG-32", "Thời tiết lạnh làm hai bàn tay hơi lạnh giá, đeo găng tay vào ấm bình thường.", False, "benign_cold", "Cold weather glove relief"))

    # 5. Weak Non-specific Complaints & Reflex Phenomena (12)
    cases.append(SingletonTestCase("SGT-NEG-33", "Hơi vã mồ hôi nhẹ sau khi vừa đi bộ nhanh 3 tầng cầu thang lên văn phòng.", False, "weak_sweat", "Physiologic post-exercise sweating"))
    cases.append(SingletonTestCase("SGT-NEG-34", "Ra mồ hôi trộm về đêm thoảng qua do phòng ngủ bí bức không bật quạt.", False, "weak_sweat", "Warm room mild perspiration"))
    cases.append(SingletonTestCase("SGT-NEG-35", "Hơi buồn nôn do say xe ô tô khách đường dài, xuống xe hít thở đã đỡ nhiều.", False, "weak_nausea", "Motion sickness nausea"))
    cases.append(SingletonTestCase("SGT-NEG-36", "Thấy nôn nao nhẹ ở dạ dày do đói bụng chưa kịp ăn trưa.", False, "weak_nausea", "Hunger-related mild nausea"))
    cases.append(SingletonTestCase("SGT-NEG-37", "Người thấy uể oải mệt mỏi sau khi làm việc cả ngày cuối tuần.", False, "weak_fatigue", "Routine workday fatigue"))
    cases.append(SingletonTestCase("SGT-NEG-38", "Mệt mỏi sau khi thức khuya xem bóng đá, sáng dậy hơi thiếu ngủ.", False, "weak_fatigue", "Sleep deprivation tiredness"))
    cases.append(SingletonTestCase("SGT-NEG-39", "Cảm giác choáng váng thoáng qua khi đang đi tiểu đêm rồi tỉnh lại bình thường.", False, "ambiguous_syncope", "Micturition reflex syncope"))
    cases.append(SingletonTestCase("SGT-NEG-40", "Hơi hồi hộp tim đập nhanh thoáng qua sau khi uống ly cà phê đen đậm đặc.", False, "weak_palpitation", "Caffeine-induced palpitations"))
    cases.append(SingletonTestCase("SGT-NEG-41", "Hơi nóng bức ra mồ hôi ở trán khi ăn tô phở bò nóng cay.", False, "weak_sweat", "Gustatory sweating"))
    cases.append(SingletonTestCase("SGT-NEG-42", "Hơi đầy bụng buồn nôn nhẹ sau khi uống một cốc sữa tươi lúc đói.", False, "weak_nausea", "Lactose mild dyspepsia"))
    cases.append(SingletonTestCase("SGT-NEG-43", "Thấy mệt mệt trong người sau chuyến bay dài chuyển múi giờ.", False, "weak_fatigue", "Jet lag fatigue"))
    cases.append(SingletonTestCase("SGT-NEG-44", "Hồi hộp đánh trống ngực trước khi bước vào phòng phỏng vấn xin việc.", False, "weak_palpitation", "Situational anxiety palpitation"))

    return cases


def run_singleton_benchmark() -> dict[str, Any]:
    print("=" * 85)
    print("MEDGUARD AI CANDIDATE V9 — CRITICAL SINGLETON SAFETY BENCHMARK (88 CASES)")
    print("=" * 85)

    suite = generate_singleton_test_suite()
    total_cases = len(suite)

    pos_cases = [c for c in suite if c.is_critical_singleton]
    neg_cases = [c for c in suite if not c.is_critical_singleton]

    tp = 0
    fn = 0
    tn = 0
    fp = 0

    failures: list[dict[str, Any]] = []

    for c in suite:
        eval_res = score_evidence_strength(c.text)
        is_crit = eval_res.tier == SingletonEvidenceTier.CRITICAL_SINGLETON

        if c.is_critical_singleton:
            if is_crit:
                tp += 1
            else:
                fn += 1
                failures.append({
                    "case_id": c.case_id,
                    "type": "MISSED_CRITICAL_SINGLETON",
                    "text": c.text,
                    "concept": c.concept,
                    "actual_tier": eval_res.tier.value,
                    "rationale": eval_res.rationale,
                })
        else:
            if not is_crit:
                tn += 1
            else:
                fp += 1
                failures.append({
                    "case_id": c.case_id,
                    "type": "FALSE_CRITICAL_ESCALATION",
                    "text": c.text,
                    "concept": c.concept,
                    "actual_tier": eval_res.tier.value,
                    "rationale": eval_res.rationale,
                })

    recall = (tp / len(pos_cases) * 100.0) if pos_cases else 0.0
    precision = (tp / (tp + fp) * 100.0) if (tp + fp) else 0.0
    benign_fp_rate = (fp / len(neg_cases) * 100.0) if neg_cases else 0.0

    print(f"Total Cases Evaluated: {total_cases} (Pos: {len(pos_cases)}, Neg: {len(neg_cases)})")
    print(f"True Positives (TP):   {tp}/{len(pos_cases)}")
    print(f"False Negatives (FN):  {fn} (Missed Critical Singletons)")
    print(f"True Negatives (TN):   {tn}/{len(neg_cases)}")
    print(f"False Positives (FP):  {fp} (Benign False Escalations)")
    print()
    print(f"Critical Singleton Recall:          {recall:.2f}% (Target >= 99.0%)")
    print(f"Critical Singleton Precision:       {precision:.2f}% (Target >= 95.0%)")
    print(f"Benign Singleton False Escalation:  {benign_fp_rate:.2f}% (Target <= 2.0%)")

    recall_passed = recall >= 99.0
    precision_passed = precision >= 95.0
    fp_passed = benign_fp_rate <= 2.0
    overall_passed = recall_passed and precision_passed and fp_passed
    print(f"Overall Singleton Safety Gate:      {'PASSED' if overall_passed else 'FAILED'}")
    print("=" * 85)

    if failures:
        print(f"\n[FAILURES - {len(failures)} cases]")
        for f in failures:
            print(f"  - [{f['type']}] {f['case_id']} ({f['concept']}): {f['text'][:70]}... | {f['actual_tier']} | {f['rationale']}")

    report = {
        "total_cases": total_cases,
        "positive_cases": len(pos_cases),
        "negative_cases": len(neg_cases),
        "true_positives": tp,
        "false_negatives": fn,
        "true_negatives": tn,
        "false_positives": fp,
        "recall_pct": round(recall, 2),
        "precision_pct": round(precision, 2),
        "benign_fp_rate_pct": round(benign_fp_rate, 2),
        "recall_passed": recall_passed,
        "precision_passed": precision_passed,
        "benign_fp_passed": fp_passed,
        "overall_passed": overall_passed,
        "failures": failures,
    }

    out_file = REPO_ROOT / "outputs" / "singleton_safety_report.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\n[+] Saved singleton report to: {out_file}")
    return report


if __name__ == "__main__":
    run_singleton_benchmark()
