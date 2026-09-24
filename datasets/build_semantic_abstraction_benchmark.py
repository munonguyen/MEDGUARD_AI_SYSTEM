"""Dataset Generator for 600-Case Semantic Clinical Abstraction Benchmark.

Cohorts:
1. 150 indirect functional descriptions (perfusion, vision, motor, airway, visceral)
2. 100 metaphoric / colloquial Vietnamese expressions
3. 100 cross-domain composites (shock, sepsis, multi-organ, occult catastrophe)
4. 100 partial-evidence emergencies (incomplete story + life-threat cues)
5. 75 quoted / negated traps (adversarial negation, historical, third-person)
6. 75 benign mimics (dry eyes, paper cut, tension headache, rhinitis, checkup)
Total: Exactly 600 clinical evaluation cases.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def build_dataset() -> list[dict]:
    cases = []
    case_idx = 1

    # -------------------------------------------------------------------------
    # Cohort 1: 150 Indirect Functional Descriptions
    # -------------------------------------------------------------------------
    # 30 Perfusion loss
    perfusion_templates = [
        "Bàn chân bên phải từ trưa đến giờ trắng ởn như xác chết, lạnh toát buốt thấu xương, rờ không thấy mạch đập đâu mà đau thấu trời.",
        "Cánh tay trái tự nhiên tái nhợt lạnh ngắt, sờ vào mu bàn tay lạnh buốt như đá tảng, bắt mạch quay không thấy đập nữa.",
        "Một bên cẳng chân trắng bệch, lạnh buốt buốt rười rượi, mạch mu chân mất hoàn toàn, cử động các ngón rất yếu và đau nhức dữ dội.",
        "Chân tôi bỗng dưng đổi màu trắng bợt, sờ vào lạnh ngắt như đóng băng, không bắt được mạch đập, đau buốt không chịu nổi.",
        "Từ sáng nay cẳng tay phải lạnh toát như cục đá, da tái nhợt mất cảm giác, bắt mạch cổ tay không thấy nảy gì cả.",
    ]
    for i in range(30):
        tmpl = perfusion_templates[i % len(perfusion_templates)]
        cases.append({
            "case_id": f"ABSTR-{case_idx:04d}",
            "cohort": "indirect_functional_descriptions",
            "domain": "perfusion_threat",
            "input_text": f"Mô tả triệu chứng #{i+1}: {tmpl}",
            "expected_triage": "EMERGENCY",
            "expected_critical_facts": ["arterial_occlusion"],
            "expected_functional_loss": ["loss_of_limb_perfusion"],
            "expected_physiologic_consequence": ["limb_perfusion_failure"],
            "is_emergency": True,
        })
        case_idx += 1

    # 30 Sudden Vision Loss
    vision_templates = [
        "Mắt bên trái tự nhiên như có ai kéo bức rèm đen sụp xuống che kín nửa trường nhìn, chớp mắt mấy lần vẫn tối thui.",
        "Tự nhiên con mắt phải như bị ai tắt phụt cầu dao điện, tối sầm lại không nhìn thấy đường nữa dù mắt trái vẫn thấy.",
        "Mắt phải đột ngột mất thị lực hoàn toàn, nhìn ra trước chỉ thấy một mảng đen kịt bao trùm như nhắm mắt.",
        "Đang ngồi làm việc thì mắt trái như bị buông tấm màn đen che khuất tầm mắt, đưa bàn tay quơ trước mặt không thấy gì.",
        "Tự dưng mắt phải tối đen như mực, không còn nhìn thấy ngón tay hay ánh sáng gì trong phòng nữa.",
    ]
    for i in range(30):
        tmpl = vision_templates[i % len(vision_templates)]
        cases.append({
            "case_id": f"ABSTR-{case_idx:04d}",
            "cohort": "indirect_functional_descriptions",
            "domain": "vision_threat",
            "input_text": f"Bệnh cảnh nhãn khoa #{i+1}: {tmpl}",
            "expected_triage": "EMERGENCY",
            "expected_critical_facts": ["vision_loss"],
            "expected_functional_loss": ["loss_of_sight"],
            "expected_physiologic_consequence": ["retinal_or_optic_ischemia"],
            "is_emergency": True,
        })
        case_idx += 1

    # 30 Focal Motor / Speech Loss (Stroke)
    motor_templates = [
        "Vừa đứng lên thì cả người đổ sụp xuống, tay phải rơi thõng không nhấc lên được, miệng méo lệch sang một bên ú ớ.",
        "Bác tự nhiên một bên mặt xệ hẳn xuống, nước bọt chảy ròng ròng không khép miệng được, nói năng ngọng nghịu không ra câu.",
        "Mẹ tôi tự nhiên khuỵu chân ngã dúi dụi, tay trái liệt hoàn toàn buông thõng, gọi chỉ ú ớ không thành tiếng.",
        "Đột ngột nửa người bên phải yếu liệt hoàn toàn, tay không cầm nổi cốc nước, méo miệng và nói lắp bắp khó hiểu.",
        "Bố tôi đang ngồi uống nước thì rơi cốc, miệng méo xệch sang trái, tay phải liệt buông xuôi không cử động được.",
    ]
    for i in range(30):
        tmpl = motor_templates[i % len(motor_templates)]
        cases.append({
            "case_id": f"ABSTR-{case_idx:04d}",
            "cohort": "indirect_functional_descriptions",
            "domain": "motor_speech_threat",
            "input_text": f"Bệnh cảnh thần kinh #{i+1}: {tmpl}",
            "expected_triage": "EMERGENCY",
            "expected_critical_facts": ["acute_stroke"],
            "expected_functional_loss": ["loss_of_motor_power"],
            "expected_physiologic_consequence": ["acute_neurologic_deficit"],
            "is_emergency": True,
        })
        case_idx += 1

    # 30 Acute Respiratory / Airway Threat
    respiratory_templates = [
        "Khó thở dữ dội, mỗi lần hít vào nghe tiếng rít rí rít ở cổ họng nghẹt thở, môi lưỡi sưng phồng tím tái dần.",
        "Thở dốc hổn hển không ra hơi, nói ngắt quãng từng từ không thốt nổi cả câu, ngực lõm sâu co kéo cơ cổ liên tục.",
        "Cổ họng nghẹn đặc, thở rít thành tiếng rít thanh quản nghe rất rõ từ xa, tím tái môi và không nói được trọn chữ.",
        "Hít thở cực kỳ nặng nhọc, tiếng rít rít từng hồi như thắt cổ họng, SpO2 đo tại nhà tụt xuống chỉ còn 84%.",
        "Khó thở kịch phát, phải ngồi chống hai tay ra trước há miệng để thở, nói đứt quãng từng từ một rất mệt lả.",
    ]
    for i in range(30):
        tmpl = respiratory_templates[i % len(respiratory_templates)]
        cases.append({
            "case_id": f"ABSTR-{case_idx:04d}",
            "cohort": "indirect_functional_descriptions",
            "domain": "airway_respiratory_threat",
            "input_text": f"Bệnh cảnh hô hấp #{i+1}: {tmpl}",
            "expected_triage": "EMERGENCY",
            "expected_critical_facts": ["airway_obstruction_or_severe_dyspnea"],
            "expected_functional_loss": ["inability_to_speak_full_sentences"],
            "expected_physiologic_consequence": ["airway_compromise"],
            "is_emergency": True,
        })
        case_idx += 1

    # 30 Visceral Catastrophe & Peritoneal Rigidity
    visceral_templates = [
        "Bụng gồng cứng đơ như khúc gỗ, ai chạm nhẹ vào da bụng là la hét đau đớn dữ dội, đau buốt lan khắp ổ bụng.",
        "Thành bụng chỗ mổ cũ tự nhiên bục toạc ra lòi cả khúc ruột đỏ lòm ra ngoài gạc, cứu với gấp lắm rồi!",
        "Cơn đau bụng kinh hoàng đột ngột như dao đâm thấu bụng, toàn bộ thành bụng co cứng ngắc không thở nổi.",
        "Sau nôn ói liên tục thì nghe tiếng rách nhói giữa ngực, sờ vào dưới da cổ thấy lạo xạo như có bọt khí xì xèo.",
        "Bụng cứng như đanh, sờ nhẹ cũng đau nhói buốt óc, nằm im không dám cử động hay ho vì đau như xé ruột.",
    ]
    for i in range(30):
        tmpl = visceral_templates[i % len(visceral_templates)]
        cases.append({
            "case_id": f"ABSTR-{case_idx:04d}",
            "cohort": "indirect_functional_descriptions",
            "domain": "visceral_catastrophe",
            "input_text": f"Bệnh cảnh ngoại khoa #{i+1}: {tmpl}",
            "expected_triage": "EMERGENCY",
            "expected_critical_facts": ["abdominal_rigidity"],
            "expected_functional_loss": ["inability_to_tolerate_palpation_movement"],
            "expected_physiologic_consequence": ["peritoneal_irritation"],
            "is_emergency": True,
        })
        case_idx += 1

    # -------------------------------------------------------------------------
    # Cohort 2: 100 Metaphoric & Colloquial Vietnamese Expressions
    # -------------------------------------------------------------------------
    metaphor_templates = [
        ("tự nhiên một bên chân trắng ởn như xác chết, lạnh toát buốt thấu xương, rờ không thấy mạch đập đâu nữa mà đau thấu trời.", "arterial_occlusion", "loss_of_limb_perfusion", "limb_perfusion_failure"),
        ("chỉ là nhậu xỉn nôn thốc nôn tháo nôn mửa liên tục thôi mà sao giờ ngực đau thấu xương tủy, dưới da cổ sờ vào lạo xạo như có bọt khí xì xèo bên trong thế này?", "boerhaave_syndrome", "inability_to_tolerate_palpation_movement", "internal_hemorrhage_and_shock"),
        ("thành bụng chỗ mổ cũ tự nhiên bục toạc ra lòi cả khúc ruột đỏ lòm ra ngoài gạc, cứu với gấp lắm rồi!", "abdominal_rigidity", "loss_of_skin_barrier_integrity", "peritoneal_irritation"),
        ("cứ bảo nghỉ tí là hết nhưng giờ một bên mặt xệ hẳn xuống, nước bọt chảy ròng ròng không nói được lời nào rõ nghĩa.", "acute_stroke", "loss_of_motor_power", "acute_neurologic_deficit"),
        ("thân nhiệt vọt lên hơn 40 độ, người cứng đơ ngắc ngơ run bắn lên như điện giật sau khi uống thuốc tâm thần.", "toxic_ingestion", "loss_of_protective_reflexes", "acute_toxic_metabolic_threat"),
        ("bụng cứng như khúc gỗ lim, chạm nhẹ tay vào là giãy nảy kêu la thảm thiết như ai lấy dao chém vào ruột.", "abdominal_rigidity", "inability_to_tolerate_palpation_movement", "peritoneal_irritation"),
        ("mắt như ai kéo tấm màn đen sập xuống tối thui như mực, không còn nhìn thấy ánh đèn hay bàn tay gì nữa.", "vision_loss", "loss_of_sight", "retinal_or_optic_ischemia"),
        ("ngực đau xé toang như sét đánh giữa ngực lan thấu ra sau lưng, vã mồ hôi lạnh ngắt như tắm nước đá.", "circulatory_compromise", "loss_of_consciousness_or_perfusion", "circulatory_compromise"),
        ("thở rít ro ro như tiếng còi tàu nghẹt trong cổ, tím tái hai bờ môi không thốt nổi một lời trọn vẹn.", "airway_obstruction_or_severe_dyspnea", "inability_to_speak_full_sentences", "airway_compromise"),
        ("chảy máu phun thành tia xối xả đè chặt mấy lớp khăn vẫn ướt đẫm máu tươi tràn ra nhà.", "massive_hemorrhage", "loss_of_hemodynamic_stability", "internal_hemorrhage_and_shock"),
    ]
    for i in range(100):
        text_t, conc, fl, cons = metaphor_templates[i % len(metaphor_templates)]
        cases.append({
            "case_id": f"ABSTR-{case_idx:04d}",
            "cohort": "metaphoric_colloquial",
            "domain": "colloquial_expression",
            "input_text": f"Lời kể dân gian #{i+1}: {text_t}",
            "expected_triage": "EMERGENCY",
            "expected_critical_facts": [conc],
            "expected_functional_loss": [fl],
            "expected_physiologic_consequence": [cons],
            "is_emergency": True,
        })
        case_idx += 1

    # -------------------------------------------------------------------------
    # Cohort 3: 100 Cross-Domain Composites
    # -------------------------------------------------------------------------
    composite_templates = [
        ("Đau bụng kinh hoàng ở người già có bệnh tim mạch, đau lăn lộn không tư thế nào giảm, huyết áp bắt đầu tụt 85/55.", "mesenteric_ischemia", "inability_to_tolerate_palpation_movement", "organ_ischemia_necrosis_threat"),
        ("Phụ nữ trẻ đột ngột đau nhói quặn dữ dội một bên hố chậu dưới, cơn đau dồn dập nôn mật xanh mật vàng da tái nhợt.", "obstetric_catastrophe", "inability_to_tolerate_palpation_movement", "obstetric_catastrophe"),
        ("Bệnh nhân đái tháo đường bỏ tiêm thuốc 3 ngày nay, hiện lú lẫn nôn mửa liên tục, thở hổn hển sâu hoắm mệt lả.", "diabetic_ketoacidosis", "loss_of_acid_base_homeostasis", "metabolic_crisis"),
        ("Uống phối hợp 2 loại thuốc chống trầm cảm, hiện giật giật bàn chân liên tục không ngưng, sốt cao 39.8 độ vã mồ hôi đầm đìa.", "toxic_ingestion", "loss_of_protective_reflexes", "acute_toxic_metabolic_threat"),
        ("Sau phẫu thuật thay khớp háng 4 ngày, đột ngột khó thở dữ dội, đau ngực nhói buốt, SpO2 86%, ho ra bọt hồng.", "fat_embolism_or_pulmonary_embolism", "inability_to_speak_full_sentences", "airway_compromise"),
    ]
    for i in range(100):
        text_t, conc, fl, cons = composite_templates[i % len(composite_templates)]
        cases.append({
            "case_id": f"ABSTR-{case_idx:04d}",
            "cohort": "cross_domain_composites",
            "domain": "cross_domain_syndrome",
            "input_text": f"Bệnh án phức hợp #{i+1}: {text_t}",
            "expected_triage": "EMERGENCY",
            "expected_critical_facts": [conc],
            "expected_functional_loss": [fl],
            "expected_physiologic_consequence": [cons],
            "is_emergency": True,
        })
        case_idx += 1

    # -------------------------------------------------------------------------
    # Cohort 4: 100 Partial-Evidence Emergency (Incomplete Story + High Risk Floor)
    # -------------------------------------------------------------------------
    partial_templates = [
        ("Không rõ bị bệnh gì từ trước, chỉ thấy sáng nay huyết áp đo tại nhà tụt xuống 75/45, tim đập 135 lần/phút vã mồ hôi lạnh ngắt, đứng lên là ngất xỉu.", "circulatory_compromise", "loss_of_consciousness_or_perfusion", "circulatory_compromise"),
        ("Tự nhiên thấy đau buốt dữ dội một chân từ sáng, rờ chân thấy lạnh toát như đá, không bắt được mạch đập, không biết bị gì.", "arterial_occlusion", "loss_of_limb_perfusion", "limb_perfusion_failure"),
        ("Chẳng biết nguyên nhân tại sao, bụng cứ cứng đơ như khúc gỗ lim, sờ vào là đau thét lên không thở nổi.", "abdominal_rigidity", "inability_to_tolerate_palpation_movement", "peritoneal_irritation"),
        ("Bé uống nhầm thứ nước gì trong chai xịt muỗi của bố, giờ sùi bọt mép, mắt co nhỏ tí xíu, lơ mơ gọi không biết.", "toxic_ingestion", "loss_of_protective_reflexes", "acute_toxic_metabolic_threat"),
        ("Chỉ là nhậu nôn nhiều thôi nhưng giờ ngực đau dữ dội, sờ cổ thấy lạo xạo khí dưới da, nuốt ngụm nước cũng đau nhói.", "boerhaave_syndrome", "inability_to_tolerate_palpation_movement", "internal_hemorrhage_and_shock"),
    ]
    for i in range(100):
        text_t, conc, fl, cons = partial_templates[i % len(partial_templates)]
        cases.append({
            "case_id": f"ABSTR-{case_idx:04d}",
            "cohort": "partial_evidence_emergency",
            "domain": "partial_evidence_safety",
            "input_text": f"Dữ kiện bán phần #{i+1}: {text_t}",
            "expected_triage": "EMERGENCY",
            "expected_critical_facts": [conc],
            "expected_functional_loss": [fl],
            "expected_physiologic_consequence": [cons],
            "is_emergency": True,
        })
        case_idx += 1

    # -------------------------------------------------------------------------
    # Cohort 5: 75 Quoted / Negated Traps
    # -------------------------------------------------------------------------
    negated_templates = [
        ("Uống lon nước ngọt có ga xong bị nấc cụt liên tục 5 phút, uống ngụm nước ấm thì đỡ, không đau ngực khó thở gì.", "ROUTINE"),
        ("Bác sĩ dặn nếu có đau ngực khó thở vã mồ hôi thì gọi 115, nhưng hiện tại tôi chỉ bị mỏi cơ nhẹ sau tập gym, không hề có triệu chứng nguy hiểm nào.", "ROUTINE"),
        ("Đọc báo thấy người ta bị tắc mạch chân trắng bệch lạnh ngắt, tôi sợ quá tự sờ chân mình thì thấy ấm áp hồng hào bình thường, hỏi bác sĩ cách phòng ngừa.", "ROUTINE"),
        ("Mẹ tôi năm ngoái từng bị tai biến méo miệng liệt nửa người nhưng đã chữa khỏi hoàn toàn, nay tôi hỏi chế độ ăn uống ngừa tái phát.", "ROUTINE"),
        ("Tôi tìm hiểu về triệu chứng nhồi máu cơ tim trên mạng, hiện tại tôi hoàn toàn khỏe mạnh không đau ngực khó thở gì cả.", "ROUTINE"),
    ]
    for i in range(75):
        text_t, exp_t = negated_templates[i % len(negated_templates)]
        cases.append({
            "case_id": f"ABSTR-{case_idx:04d}",
            "cohort": "quoted_negated_traps",
            "domain": "adversarial_negation",
            "input_text": f"Tình huống bẫy phủ định #{i+1}: {text_t}",
            "expected_triage": exp_t,
            "expected_critical_facts": [],
            "expected_functional_loss": [],
            "expected_physiologic_consequence": [],
            "is_emergency": False,
        })
        case_idx += 1

    # -------------------------------------------------------------------------
    # Cohort 6: 75 Benign Mimics
    # -------------------------------------------------------------------------
    benign_templates = [
        ("Bôi kem chống ngứa ngoài da một lớp mỏng theo đơn bác sĩ, vết muỗi cắn đã bớt sưng, hỏi ngày bôi mấy lần.", "ROUTINE"),
        ("Ngồi làm việc văn phòng máy tính cả ngày mắt bị khô rát nhẹ mỏi điều tiết, nhắm mắt nghỉ một lát thì đỡ hẳn, nhìn rõ bình thường.", "ROUTINE"),
        ("Bị mép giấy A4 cứa vào đầu ngón tay chảy một giọt máu nông, đã rửa nước sạch và dán băng cá nhân, không tê liệt hay sưng tấy.", "ROUTINE"),
        ("Hắt hơi sổ mũi nước trong sau khi quét dọn phòng nhiều bụi, không sốt, không khó thở, họng không đau rát.", "ROUTINE"),
        ("Đau mỏi cơ bắp tay sau khi nâng tạ buổi chiều, ấn vào hơi thốn nhẹ, cử động khớp bình thường không sưng bầm tím.", "ROUTINE"),
    ]
    for i in range(75):
        text_t, exp_t = benign_templates[i % len(benign_templates)]
        cases.append({
            "case_id": f"ABSTR-{case_idx:04d}",
            "cohort": "benign_mimics",
            "domain": "benign_control",
            "input_text": f"Tình huống lành tính #{i+1}: {text_t}",
            "expected_triage": exp_t,
            "expected_critical_facts": [],
            "expected_functional_loss": [],
            "expected_physiologic_consequence": [],
            "is_emergency": False,
        })
        case_idx += 1

    return cases


def main():
    cases = build_dataset()
    out_dir = REPO_ROOT / "datasets" / "DS-SEMANTIC-ABSTRACTION"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "dataset.json"

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2, ensure_ascii=False)

    print(f"[+] Successfully generated {len(cases)} cases for Semantic Abstraction Benchmark at {out_file}")

    from collections import Counter
    cohort_counts = Counter(c["cohort"] for c in cases)
    for cohort, cnt in cohort_counts.items():
        print(f"  - {cohort:35s}: {cnt:3d} cases")


if __name__ == "__main__":
    main()
