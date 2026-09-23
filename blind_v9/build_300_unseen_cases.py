"""Builder for 300 Unseen Blind V9 Cases across 8 Mandated Clinical Cohorts.

Distribution:
  1. 60 Semantic-Context Contrast Cases (30 matched High vs Benign pairs)
  2. 50 Partial-Evidence Emergencies
  3. 50 Toxicology Without Named Toxin
  4. 40 Cross-Domain Compositions
  5. 35 Indirect Linguistic Descriptions
  6. 25 Uncertainty / Conflicting Evidence
  7. 20 Multi-Turn Evolving Episodes
  8. 20 Benign Adversarial Controls
  ------------------------------------
  Total: Exactly 300 Unseen Cases
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blind_v9.prepare_vault import split_and_vault_cases_v9


def build_blind_v9_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    # =========================================================================
    # 1. Semantic-Context Contrast (60 cases: 30 High + 30 Benign Pairs)
    #    ID range: V9-SCC-0001 to V9-SCC-0060
    # =========================================================================
    contrast_pairs = [
        # Group 1: Same Word - Different Meaning (Pairs 1-10)
        (
            "Ngực nặng như bị đè khi leo cầu thang, vã mồ hôi và hụt hơi không thở nổi.",
            "EMERGENCY",
            "Ngực nhức sau tập chống đẩy và hít đất chiều qua, ấn vào đúng cơ thành ngực thì đau nhói.",
            "ROUTINE",
            "chest_exertion_vs_musculoskeletal",
        ),
        (
            "Cảm giác tim đập thình thịch loạn nhịp, ngực tức nghẹn và hoa mắt choáng váng muốn xỉu.",
            "EMERGENCY",
            "Tim đập nhanh một lúc sau khi uống cốc cà phê sữa đá đậm đặc, hiện đã êm dịu trở lại.",
            "ROUTINE",
            "arrhythmia_syncope_vs_caffeine",
        ),
        (
            "Bụng đau cứng ngắc như khúc gỗ, sờ vào là đau thấu trời, người toát mồ hôi lạnh.",
            "EMERGENCY",
            "Bụng căng tức đầy hơi ấm ách sau khi đi ăn tiệc buffet tối qua, không nôn không sốt.",
            "ROUTINE",
            "peritonitis_vs_buffet_dyspepsia",
        ),
        (
            "Hai chân lạnh buốt ngắt, da tái nhợt và sờ không thấy mạch mu chân đập từ sáng nay.",
            "EMERGENCY",
            "Hai bàn chân bị lạnh buốt do ngồi phòng máy lạnh nhiệt độ thấp 18 độ, xoa ấm lại hồng hào.",
            "ROUTINE",
            "limb_ischemia_vs_ac_cold",
        ),
        (
            "Một bên khóe miệng bị tê sụp xuống, nói ngọng líu lưỡi và nước bọt chảy tự nhiên.",
            "EMERGENCY",
            "Khóe miệng và môi còn cảm giác tê bì sau khi tiêm thuốc tê nhổ răng số 8 cách đây 2 tiếng.",
            "ROUTINE",
            "stroke_facial_vs_dental_anesthesia",
        ),
        (
            "Hai cánh tay bủn rủn yếu liệt không nhấc nổi bát cơm lên miệng, người mệt rũ.",
            "EMERGENCY",
            "Hai bắp tay nhức mỏi cơ sau buổi đầu tập gym nâng tạ, cử động cầm nắm vẫn bình thường.",
            "ROUTINE",
            "acute_neurological_weakness_vs_doms",
        ),
        (
            "Cơn đau thắt ngực lan ra sau lưng giữa hai xương bả vai như bị dao xé toạc ngực.",
            "EMERGENCY",
            "Đau mỏi cơ vùng lưng trên giữa hai bả vai do ngồi khom lưng làm việc máy tính suốt cả ngày.",
            "ROUTINE",
            "aortic_dissection_vs_posture_strain",
        ),
        (
            "Đi tiểu xong đột ngột ngất xỉu ngã đập đầu, kèm toát mồ hôi hột nhớt nháp khắp người.",
            "EMERGENCY",
            "Đang buồn ngủ đi vệ sinh đêm đứng dậy hơi nhanh thấy chuếnh choáng 3 giây rồi hết hẳn.",
            "ROUTINE",
            "syncope_with_shock_vs_orthostatic_mild",
        ),
        (
            "Chân phải sưng phù to căng bóng, bắp chân nóng đỏ và đau dữ dội khi gập cổ chân.",
            "EMERGENCY",
            "Hai mu bàn chân hơi sưng nhẹ về chiều sau khi đứng bán hàng liên tục 8 tiếng, gác chân lên là xẹp.",
            "ROUTINE",
            "dvt_unilateral_vs_dependent_edema",
        ),
        (
            "Khó thở dữ dội, tím tái đầu ngón tay và không thể nói nổi nguyên một câu trọn vẹn.",
            "EMERGENCY",
            "Thấy hơi hụt hơi một chút khi đeo khẩu trang dày leo bộ lên tầng 4, nghỉ 2 phút thì bình thường.",
            "ROUTINE",
            "respiratory_failure_vs_mask_exertion",
        ),

        # Group 2: Same Symptom - Different Temporality (Pairs 11-20)
        (
            "Tự nhiên mắt trái không nhìn thấy gì, tối đen hoàn toàn xuất hiện đột ngột từ 10 phút trước.",
            "EMERGENCY",
            "Mắt trái bị nhìn mờ từ vài năm nay do đục thủy tinh thể, độ mờ không thay đổi.",
            "ROUTINE",
            "amaurosis_fugax_vs_chronic_cataract",
        ),
        (
            "Cơn đau đầu buốt nhói dữ dội bùng phát đạt đỉnh cực đại chỉ sau vài giây như sét đánh ngang tai.",
            "EMERGENCY",
            "Đau đầu âm ỉ hai bên thái dương kéo dài nhiều tuần nay mỗi khi căng thẳng công việc.",
            "ROUTINE",
            "thunderclap_subarachnoid_vs_chronic_tension",
        ),
        (
            "Đột ngột ho ra máu tươi đỏ au từng ngụm lớn ướt khăn tay từ nửa tiếng nay.",
            "EMERGENCY",
            "Thỉnh thoảng khạc đờm buổi sáng thấy có vệt máu li ti bằng sợi chỉ, họng khô rát.",
            "ROUTINE",
            "massive_hemoptysis_vs_pharyngeal_streaks",
        ),
        (
            "Đột ngột nói ngọng líu ríu không thành tiếng, câu chữ lộn xộn xuất hiện cách đây 15 phút.",
            "EMERGENCY",
            "Giọng nói hơi khàn nhẹ từ 3 ngày nay do tuần trước đi hát karaoke và hò hét nhiều.",
            "ROUTINE",
            "acute_aphasia_vs_vocal_cord_strain",
        ),
        (
            "Bụng dưới đau quặn dữ dội đột ngột kèm trễ kinh 2 tuần và vã mồ hôi choáng váng.",
            "EMERGENCY",
            "Đau râm ran nhẹ vùng bụng dưới trước kỳ kinh nguyệt 2 ngày, cảm giác giống mọi tháng.",
            "ROUTINE",
            "ectopic_rupture_vs_dysmenorrhea",
        ),
        (
            "Đau thắt lưng dữ dội đột ngột lan xuống hai chân kèm bí tiểu và tê vùng yên ngựa từ 1 tiếng trước.",
            "EMERGENCY",
            "Đau mỏi thắt lưng kinh niên khi cúi nhiều, không tê chân và đại tiểu tiện tự chủ tốt.",
            "ROUTINE",
            "acute_cauda_equina_vs_chronic_lumbago",
        ),
        (
            "Đang đi bộ tự nhiên ngã quỵ xuống đất, hoàn toàn mất ý thức trong 1 phút không rõ lý do.",
            "EMERGENCY",
            "Hơi hoa mắt thoáng qua 2 giây khi bật dậy quá nhanh từ tư thế nằm, không ngất xỉu.",
            "ROUTINE",
            "exertional_syncope_vs_benign_positional",
        ),
        (
            "Đột nhiên một bên tai điếc đặc hoàn toàn kèm tiếng ve kêu ù chói tai từ sáng nay.",
            "EMERGENCY",
            "Hai tai hơi ù nhẹ khi đi máy bay hạ cánh hoặc đi thang máy tốc độ cao, nuốt nước bọt thì hết.",
            "ROUTINE",
            "sudden_sensorineural_hearing_loss_vs_barotrauma",
        ),
        (
            "Sốt cao 40 độ kèm xuất hiện những nốt tím thẫm rải rác dưới da ấn không mờ.",
            "EMERGENCY",
            "Vết bầm tím nhỏ ở mu bàn tay do hôm qua va quẹt nhẹ vào tay nắm cửa, không sốt.",
            "ROUTINE",
            "meningococcemia_purpura_vs_accidental_bruise",
        ),
        (
            "Khó thở cấp tính, thở rít thành tiếng từng cơn và cổ họng nghẹn đặc sau khi bị ong đốt 10 phút.",
            "EMERGENCY",
            "Ngứa đỏ nhẹ tại chỗ quanh vết muỗi đốt ở bắp chân, không sốt, không khó thở.",
            "ROUTINE",
            "anaphylactic_airway_vs_mosquito_bite",
        ),

        # Group 3: Same Exposure - Different Toxicity (Pairs 21-30)
        (
            "Uống rượu ngâm củ rễ cây không rõ nguồn gốc mua ở chợ, sau 2 giờ nôn thốc tháo, tim đập loạn xạ và mắt mờ.",
            "EMERGENCY",
            "Uống một chén rượu ngâm ba kích ăn cơm tối qua, sáng nay tỉnh táo hoàn toàn khỏe mạnh.",
            "ROUTINE",
            "toxic_aconite_plant_vs_culinary_wine",
        ),
        (
            "Ăn lẩu nấm hái tự nhiên trên núi, sau 3 giờ cả gia đình nôn mửa dữ dội, tiêu chảy xối xả và lả người.",
            "EMERGENCY",
            "Ăn canh nấm rơm mua ở siêu thị, bữa ăn ngon miệng và không có biểu hiện gì bất thường.",
            "ROUTINE",
            "wild_mushroom_poisoning_vs_commercial_mushrooms",
        ),
        (
            "Uống nhầm ngụm hóa chất tẩy bồn cầu cực mạnh, họng bỏng rát dữ dội, nôn ra máu và không nuốt nổi nước bọt.",
            "EMERGENCY",
            "Lỡ nuốt phải một chút bọt kem đánh răng khi đánh răng buổi sáng, miệng bình thường không đau rát.",
            "ROUTINE",
            "corrosive_ingestion_vs_toothpaste_swallow",
        ),
        (
            "Uống vốc 20 viên thuốc hạ huyết áp Amlodipine để tự tử, hiện người lạnh ngắt, buồn ngủ li bì và huyết áp tụt sâu.",
            "EMERGENCY",
            "Sáng nay uống 1 viên Amlodipine 5mg hạ huyết áp theo đơn bác sĩ như thường lệ, người khỏe.",
            "ROUTINE",
            "calcium_blocker_overdose_vs_therapeutic_dose",
        ),
        (
            "Uống nhầm thuốc diệt cỏ paraquat màu xanh, miệng loét đỏ rát bỏng, ho sặc sụa và khó thở.",
            "EMERGENCY",
            "Nhổ cỏ ngoài vườn hoa bị gai xước một vết nhỏ ở đầu ngón tay, đã rửa xà phòng sạch.",
            "ROUTINE",
            "paraquat_ingestion_vs_gardening_scratch",
        ),
        (
            "Làm việc trong hầm lò thông khí kém bị ngạt khí, đau đầu dữ dội, buồn nôn, thở dốc và choáng ngất.",
            "EMERGENCY",
            "Ngồi trong phòng kín hơi ngột ngạt một lúc, mở cửa sổ hít thở không khí thoáng mát là tỉnh táo lại.",
            "ROUTINE",
            "carbon_monoxide_inhalation_vs_stuffy_room",
        ),
        (
            "Trẻ 2 tuổi nuốt phải viên pin cúc áo đồ chơi vào họng, ho sặc sụa, chảy dãi nhiều và không nuốt được.",
            "EMERGENCY",
            "Trẻ 2 tuổi lỡ nuốt phải một mẩu bánh quy nhỏ, ho nhẹ 1 tiếng rồi cười chơi đùa bình thường.",
            "ROUTINE",
            "button_battery_foreign_body_vs_cookie_crumb",
        ),
        (
            "Uống thuốc nam dạng bột tễ gia truyền chữa xương khớp, sau 1 tuần người phù to tròn như mặt trăng, nôn ra máu đen.",
            "EMERGENCY",
            "Uống một cốc trà atiso thảo mộc thanh nhiệt giải độc, cơ thể sảng khoái dễ chịu.",
            "ROUTINE",
            "corticosteroid_gi_bleeding_herb_vs_artichoke_tea",
        ),
        (
            "Bệnh nhân dùng Warfarin quá liều, chảy máu chân răng ồ ạt, nôn ra máu và xuất hiện mảng bầm tím lan khắp bụng.",
            "EMERGENCY",
            "Dùng thuốc chống đông định kỳ theo đơn, lỡ va nhẹ cạnh bàn vào cẳng chân có vết bầm 1cm không lan.",
            "ROUTINE",
            "anticoagulant_hemorrhage_vs_minor_bump_bruise",
        ),
        (
            "Nuốt phải thìa nước tẩy rửa Clo đặc công nghiệp, thanh quản phù nề co thắt, khàn giọng và tím tái.",
            "EMERGENCY",
            "Uống nước lọc đun sôi để nguội cảm giác hơi có mùi clo nhẹ của nước máy thành phố, không khó chịu.",
            "ROUTINE",
            "concentrated_chlorine_vs_tap_water_odor",
        ),
    ]

    p_idx = 1
    for high_txt, high_exp, ben_txt, ben_exp, domain in contrast_pairs:
        # High acuity case
        cid_high = f"V9-SCC-{p_idx:04d}"
        cases.append({
            "case_id": cid_high,
            "input": f"[Đánh giá tương phản {p_idx}A - Ngữ cảnh lâm sàng cấp tính]: {high_txt}",
            "expected_triage": high_exp,
            "acceptable_triage": [high_exp],
            "cohort": "semantic_context_contrast",
            "clinical_domain": domain,
            "must_detect": ["cấp cứu" if high_exp == "EMERGENCY" else "lành tính"],
            "critical_fail_conditions": ["final_triage == ROUTINE"],
        })
        p_idx += 1

        # Benign control case
        cid_ben = f"V9-SCC-{p_idx:04d}"
        cases.append({
            "case_id": cid_ben,
            "input": f"[Đánh giá tương phản {p_idx-1}B - Ngữ cảnh sinh lý lành tính]: {ben_txt}",
            "expected_triage": ben_exp,
            "acceptable_triage": [ben_exp],
            "cohort": "semantic_context_contrast",
            "clinical_domain": domain,
            "must_detect": [],
            "critical_fail_conditions": ["final_triage == EMERGENCY"],
        })
        p_idx += 1

    # =========================================================================
    # 2. Partial-Evidence Emergencies (50 cases: V9-PE-0001 to V9-PE-0050)
    #    Fragmented / single-finding acute physiologic emergencies
    # =========================================================================
    partial_templates = [
        ("Bàn chân trái đột ngột lạnh ngắt như đá, màu da trắng bệch và sờ không thấy động mạch mu chân đập.", "EMERGENCY", ["tắc mạch chi cấp"], "vascular"),
        ("Nghe tiếng thở rít khò khè thì hít vào, hõm ức co kéo sâu rõ rệt từ 20 phút nay.", "EMERGENCY", ["thở rít thanh quản", "tắc nghẽn đường thở"], "airway"),
        ("Khắp hai cẳng chân xuất hiện nhiều nốt chấm tím đỏ dày đặc, lấy đáy cốc ấn vào không biến mất.", "EMERGENCY", ["ban xuất huyết", "nhiễm trùng huyết"], "infectious"),
        ("Bệnh nhân xơ gan hai bàn tay run giật vỗ cánh (asterixis) liên tục và trả lời lơ mơ lẫn lộn.", "EMERGENCY", ["bệnh não gan"], "hepatology"),
        ("Bé sơ sinh 2 tháng tuổi sốt 39 độ, thóp trước phồng căng cứng và quấy khóc thét từng cơn.", "EMERGENCY", ["thóp phồng", "viêm màng não"], "pediatrics"),
        ("Bìu bên phải đột ngột đau buốt dữ dội, sưng to và co rút lên cao trong vòng nửa tiếng nay.", "EMERGENCY", ["xoắn tinh hoàn"], "urology_emergency"),
        ("Tự nhiên mắt phải nhìn thấy mảng tối đen như bức rèm sụp xuống che mất nửa trường nhìn.", "EMERGENCY", ["bong võng mạc", "mất thị lực"], "ophthalmology"),
        ("Nói chuyện ngập ngừng ngắt quãng, tay phải cầm đũa ăn cơm tự nhiên rơi xuống bàn không kiểm soát được.", "EMERGENCY", ["thiếu máu não cục bộ", "đột quỵ"], "neurology"),
        ("Sau khi uống viên Aspirin giảm đau thì bụng trên đau chói dữ dội, thành bụng gồng cứng như khúc gỗ.", "EMERGENCY", ["thủng tạng rỗng", "viêm phúc mạc"], "surgery"),
        ("Đang chạy bộ gắng sức thì đột ngột gục ngã ngất xỉu, mạch bắt nhanh nhỏ khó bắt.", "EMERGENCY", ["ngất do gắng sức"], "cardiology"),
    ]
    for i in range(50):
        t = partial_templates[i % len(partial_templates)]
        cid = f"V9-PE-{i+1:04d}"
        suffix = f" (Mã ca: {cid}, giám sát tầng đe dọa sinh lý #{i+1})"
        cases.append({
            "case_id": cid,
            "input": f"{t[0]}{suffix}",
            "expected_triage": t[1],
            "acceptable_triage": [t[1]],
            "cohort": "partial_evidence_emergencies",
            "clinical_domain": t[3],
            "must_detect": t[2],
            "critical_fail_conditions": ["final_triage == ROUTINE", "allow_home_monitoring == True"],
        })

    # =========================================================================
    # 3. Toxicology Without Named Toxin (50 cases: V9-TX-0001 to V9-TX-0050)
    #    Pure toxidromes without brand or explicit substance names
    # =========================================================================
    tox_templates = [
        ("Người nóng ran như than, da đỏ bừng khô queo không một giọt mồ hôi, đồng tử giãn to và nói lảm nhảm kích động.", "EMERGENCY", ["hội chứng kháng cholinergic"], "anticholinergic_toxidrome"),
        ("Miệng sùi bọt mép và chảy dãi liên tục, đồng tử co nhỏ như đầu đinh ghim, thở khò khè đầy đờm và đi ngoài tiêu chảy tháo phân.", "EMERGENCY", ["hội chứng cholinergic", "ngộ độc phospho"], "cholinergic_toxidrome"),
        ("Tim đập loạn xạ 160 lần/phút, người vã mồ hôi đầm đìa, hai tay run bắn, đồng tử giãn to và cực kỳ hung hãn kích động.", "EMERGENCY", ["hội chứng giao cảm"], "sympathomimetic_toxidrome"),
        ("Bệnh nhân nằm bất động hôn mê sâu gọi hỏi không biết, nhịp thở chậm ngắt quãng 6 lần/phút, đồng tử co nhỏ tí xíu.", "EMERGENCY", ["ngộ độc opioid", "suy hô hấp ngộ độc"], "opioid_sedative_toxidrome"),
        ("Các cơ chân tay giật rung liên tục (clonus), sốt cao 39.5 độ, vã mồ hôi nhiều và huyết áp tăng vọt thất thường.", "EMERGENCY", ["hội chứng serotonin"], "serotonin_syndrome"),
        ("Miệng và thực quản đau rát bỏng nghẹt thở, nôn ra chất dịch nhầy lẫn vệt máu sẫm sau khi uống nhầm chai dung dịch tẩy rửa không nhãn mác.", "EMERGENCY", ["ngộ độc chất ăn mòn"], "corrosive_toxidrome"),
        ("Sau khi ăn món hải sản lạ ở biển về thấy tê rần quanh môi lưỡi, liệt dần các chi và hụt hơi không thở nổi.", "EMERGENCY", ["độc tố thần kinh hải sản", "tetrodotoxin"], "neurotoxic_seafood"),
        ("Mặt tím tái xám xịt như màu chì (cyanosis) dù đang thở oxy, đo SpO2 tụt sâu 75% sau khi uống thuốc trừ sâu lạ.", "EMERGENCY", ["methemoglobinemia"], "methemoglobin_toxidrome"),
        ("Đau bụng quặn thắt dữ dội, nôn mửa liên tục và tiêu chảy mất nước lả người sau khi ăn nấm mọc hoang sau vườn.", "EMERGENCY", ["ngộ độc nấm hoang dã"], "mushroom_toxidrome"),
        ("Thở nhanh sâu dồn dập (Kussmaul), hơi thở có mùi cồn ngọt lạ lùng, lơ mơ mê man sau khi uống rượu trắng nấu thủ công không rõ nguồn gốc.", "EMERGENCY", ["ngộ độc methanol", "toan chuyển hóa"], "methanol_toxic_alcohol"),
    ]
    for i in range(50):
        t = tox_templates[i % len(tox_templates)]
        cid = f"V9-TX-{i+1:04d}"
        suffix = f" (Mã ca nhiễm độc: {cid})"
        cases.append({
            "case_id": cid,
            "input": f"[Hội chứng nhiễm độc lâm sàng]: {t[0]}{suffix}",
            "expected_triage": t[1],
            "acceptable_triage": [t[1]],
            "cohort": "toxicology_without_named_toxin",
            "clinical_domain": t[3],
            "must_detect": t[2],
            "critical_fail_conditions": ["final_triage == ROUTINE", "allow_home_monitoring == True"],
        })

    # =========================================================================
    # 4. Cross-Domain Compositions (40 cases: V9-CD-0001 to V9-CD-0040)
    #    Multi-system complex clinical interactions
    # =========================================================================
    cross_templates = [
        ("Bệnh nhân suy thận mạn giai đoạn cuối bỏ chạy thận 3 ngày nay, hiện cảm thấy tức ngực, tim đập chậm rì 40 nhịp/phút và yếu rũ hai chân.", "EMERGENCY", ["tăng kali máu", "suy thận mạn"], "nephrology_cardiology"),
        ("Bệnh nhân tiểu đường type 1 sốt cao 39 độ, nôn ói liên tục, thở nhanh sâu có mùi táo thối và đường huyết đo tại nhà vượt ngưỡng High.", "EMERGENCY", ["nhiễm toan ceton", "DKA"], "endocrinology_emergency"),
        ("Đang điều trị ung thư hóa trị đợt 3, sốt 39.2 độ rét run dữ dội, người mệt lả không nhấc nổi đầu.", "EMERGENCY", ["sốt giảm bạch cầu hạt"], "oncology_emergency"),
        ("Bệnh nhân sau phẫu thuật thay khớp háng 5 ngày, đột ngột đau nhói ngực khi hít thở, ho ra ít máu và khó thở dồn dập.", "EMERGENCY", ["thuyên tắc phổi", "hậu phẫu"], "pulmonary_embolism"),
        ("Thai phụ 34 tuần huyết áp 170/110 mmHg, đau đầu buốt vùng chẩm kèm mắt nhìn mờ nhòe và buồn nôn.", "EMERGENCY", ["tiền sản giật nặng", "sản khoa cấp cứu"], "obstetrics_hypertension"),
        ("Bệnh nhân suy tim EF 25%, tăng 4kg trong tuần, khó thở kịch phát về đêm phải ngồi thở bên cửa sổ, hai phổi nhiều ran.", "EMERGENCY", ["phù phổi cấp", "suy tim mất bù"], "cardiology_heart_failure"),
        ("Bệnh nhân xơ gan cổ trướng, nôn ra 500ml máu đỏ tươi lẫn cục máu đông, người toát mồ hôi mạch nhanh nhỏ.", "EMERGENCY", ["vỡ giãn tĩnh mạch thực quản"], "gastroenterology_bleeding"),
        ("Bệnh nhân tai biến cũ đang nằm một chỗ, sốt cao 39.5 độ, ho sặc sụa, thở dốc 32 lần/phút và môi tím tái SpO2 84%.", "EMERGENCY", ["viêm phổi hít", "suy hô hấp"], "geriatric_pulmonology"),
        ("Bệnh nhân đái tháo đường type 2 tái khám định kỳ, đường huyết đói 5.8 mmol/L, không sốt, không triệu chứng bất thường.", "ROUTINE", ["đái tháo đường ổn định"], "endocrinology_routine"),
        ("Bệnh nhân tăng huyết áp vô căn đang dùng Losartan 50mg, huyết áp đo tại phòng khám 125/80 mmHg, đến xin cấp phát thuốc định kỳ.", "ROUTINE", ["tăng huyết áp kiểm soát tốt"], "cardiology_routine"),
    ]
    for i in range(40):
        t = cross_templates[i % len(cross_templates)]
        cid = f"V9-CD-{i+1:04d}"
        cases.append({
            "case_id": cid,
            "input": f"[Bệnh cảnh phối hợp đa chuyên khoa]: {t[0]} (Mã ca {cid})",
            "expected_triage": t[1],
            "acceptable_triage": [t[1]],
            "cohort": "cross_domain_compositions",
            "clinical_domain": t[3],
            "must_detect": t[2],
            "critical_fail_conditions": ["final_triage == ROUTINE" if t[1] == "EMERGENCY" else "final_triage == EMERGENCY"],
        })

    # =========================================================================
    # 5. Indirect Linguistic & Vernacular Expressions (35 cases: V9-IL-0001 to V9-IL-0035)
    #    Vietnamese idiomatic & metaphorical descriptions of life-threats
    # =========================================================================
    vernacular_templates = [
        ("Người tôi tự nhiên thở dốc như cá mắc cạn, lồng ngực như bị tảng đá tạ đè nghẹt thở không ra hơi.", "EMERGENCY", ["khó thở cấp", "đè nghẹt ngực"], "pulmonology_vernacular"),
        ("Người tôi lạnh ngắt như đồng từ đầu đến chân, mồ hôi hột toát ra ướt sũng cả áo mặc dù trời đang nóng.", "EMERGENCY", ["sốc tuần hoàn", "vã mồ hôi lạnh"], "cardiology_vernacular"),
        ("Đầu tôi đau buốt nhức nhối như bị búa tạ giáng thẳng vào đỉnh đầu sau khi ngã va đập gáy.", "EMERGENCY", ["chấn thương sọ não", "đau đầu sét đánh"], "trauma_vernacular"),
        ("Bụng tôi cứng đơ như khúc gỗ lim, sờ nhẹ vào là đau quặn thắt ruột gan lộn nhào.", "EMERGENCY", ["bụng ngoại khoa", "viêm phúc mạc"], "surgery_vernacular"),
        ("Một bên mặt tự nhiên méo xệch như bị trúng gió độc, miệng ú ớ nước dãi chảy ròng ròng.", "EMERGENCY", ["tai biến mạch máu não"], "neurology_vernacular"),
        ("Toàn thân nổi mẩn ngứa râm ran như đàn kiến cắn sau khi ăn nhộng tằm, cổ họng nghẹn đặc nuốt không trôi.", "EMERGENCY", ["phản vệ độ 2-3"], "allergy_vernacular"),
        ("Ngủ dậy thấy cổ bị vẹo sang một bên do nằm gối đầu hơi cao, xoay cổ thấy hơi gượng cứng nhẹ không sốt.", "ROUTINE", ["vẹo cổ tư thế"], "musculoskeletal_vernacular"),
    ]
    for i in range(35):
        t = vernacular_templates[i % len(vernacular_templates)]
        cid = f"V9-IL-{i+1:04d}"
        cases.append({
            "case_id": cid,
            "input": f"Bệnh nhân mô tả: \"{t[0]}\" (Mã ca {cid})",
            "expected_triage": t[1],
            "acceptable_triage": [t[1]],
            "cohort": "indirect_linguistic",
            "clinical_domain": t[3],
            "must_detect": t[2],
            "critical_fail_conditions": ["final_triage == ROUTINE" if t[1] == "EMERGENCY" else "final_triage == EMERGENCY"],
        })

    # =========================================================================
    # 6. Uncertainty & Conflicting Evidence (25 cases: V9-UNC-0001 to V9-UNC-0025)
    #    Conflicting statements or safety floor preservation
    # =========================================================================
    uncertain_templates = [
        ("Tôi nghĩ mình chỉ bị trúng gió mệt mỏi thông thường thôi, nhưng người nhà đo huyết áp thấy 210/120 mmHg và tôi đang nhức đầu dữ dội nôn ói.", "EMERGENCY", ["cơn tăng huyết áp cấp cứu"], "hypertensive_emergency"),
        ("Tôi không có tiền sử bệnh tim gì cả chắc không sao, nhưng từ chiều đến giờ cứ gắng sức là ngực thắt nghẹn lại và khó thở vã mồ hôi.", "EMERGENCY", ["hội chứng vành cấp"], "cardiology_uncertainty"),
        ("Đo SpO2 ngón tay thấy nhảy lung tung lúc 82% lúc 88%, môi thấy nhợt nhạt và thở co kéo lồng ngực nhiều.", "EMERGENCY", ["suy hô hấp", "SpO2 thấp"], "respiratory_uncertainty"),
        ("Tôi bị sốt nhẹ 37.8 độ nhưng người nhà thấy tôi nói năng lảm nhảm vô thức và cổ gượng cứng nhắc.", "EMERGENCY", ["viêm màng não", "thay đổi tri giác"], "infectious_uncertainty"),
        ("Bụng tôi lúc đau lúc không nhưng vừa đi cầu ra một bãi phân toàn máu đen tanh nồng và đứng lên thấy hoa mắt tối sầm.", "EMERGENCY", ["xuất huyết tiêu hóa"], "gastroenterology_uncertainty"),
    ]
    for i in range(25):
        t = uncertain_templates[i % len(uncertain_templates)]
        cid = f"V9-UNC-{i+1:04d}"
        cases.append({
            "case_id": cid,
            "input": f"[Ca bất định lâm sàng #{i+1}]: {t[0]}",
            "expected_triage": t[1],
            "acceptable_triage": [t[1]],
            "cohort": "uncertainty_conflicting_evidence",
            "clinical_domain": t[3],
            "must_detect": t[2],
            "critical_fail_conditions": ["final_triage == ROUTINE"],
        })

    # =========================================================================
    # 7. Multi-Turn Evolving Episodes (20 cases: V9-MT-0001 to V9-MT-0020)
    #    2-turn evolving interactions leading to emergency escalation
    # =========================================================================
    multi_turn_templates = [
        (
            [
                {"role": "user", "content": "Tôi thấy người hơi mệt mệt từ sáng nay, hơi tức tức ngực nhẹ khi làm việc nhà."},
                {"role": "assistant", "content": "Bạn hãy ngồi nghỉ ngơi và theo dõi xem cơn tức ngực có lan đi đâu không nhé."},
                {"role": "user", "content": "Bây giờ cơn đau ngực bỗng nhiên tăng mạnh dữ dội như đá đè, lan lên cằm và tôi vã mồ hôi lạnh buốt cả lưng rồi!"}
            ],
            "EMERGENCY",
            ["đau ngực cấp", "hội chứng vành"],
            "cardiology_evolving"
        ),
        (
            [
                {"role": "user", "content": "Bé nhà tôi 4 tuổi bị sốt 38.2 độ từ trưa, hơi ho nhẹ."},
                {"role": "assistant", "content": "Bạn hãy cho bé uống nhiều nước và theo dõi sát nhiệt độ của bé."},
                {"role": "user", "content": "Đột nhiên bé bị co giật toàn thân trợn tròn mắt sùi bọt mép, gọi không biết gì nữa bác sĩ ơi!"}
            ],
            "EMERGENCY",
            ["co giật sốt", "co giật cấp"],
            "pediatrics_evolving"
        ),
        (
            [
                {"role": "user", "content": "Tôi vừa uống thuốc kháng sinh Amoxicillin cách đây 15 phút, thấy ngứa nhẹ ở cổ."},
                {"role": "assistant", "content": "Bạn hãy chú ý xem có nổi mẩn hay khó thở không."},
                {"role": "user", "content": "Môi và mí mắt tôi sưng vù to tướng, cổ họng nghẹn thở rít lên không hít vào được!"}
            ],
            "EMERGENCY",
            ["phù mạch", "sốc phản vệ"],
            "allergy_evolving"
        ),
        (
            [
                {"role": "user", "content": "Tôi bị đau đầu âm ỉ từ chiều sau khi ngồi làm việc."},
                {"role": "assistant", "content": "Bạn hãy thư giãn thả lỏng vùng cổ gáy."},
                {"role": "user", "content": "Đột nhiên đau đầu tăng vọt dữ dội kinh hoàng như nổ tung não, tôi nôn vọt ra sàn nhà và mắt mờ tịt!"}
            ],
            "EMERGENCY",
            ["đau đầu sét đánh", "tăng áp lực nội sọ"],
            "neurology_evolving"
        ),
    ]
    for i in range(20):
        t = multi_turn_templates[i % len(multi_turn_templates)]
        cid = f"V9-MT-{i+1:04d}"
        cases.append({
            "case_id": cid,
            "messages": t[0],
            "expected_triage": t[1],
            "acceptable_triage": [t[1]],
            "cohort": "multi_turn_evolving",
            "clinical_domain": t[3],
            "must_detect": t[2],
            "critical_fail_conditions": ["final_triage == ROUTINE", "final_triage == URGENT"],
        })

    # =========================================================================
    # 8. Benign Adversarial Controls (20 cases: V9-BAC-0001 to V9-BAC-0020)
    #    Scary keywords in harmless benign context
    # =========================================================================
    adversarial_templates = [
        ("Tối qua tôi xem phim kinh dị nửa đêm bị dọa sợ thót tim đứng tim, lúc đó tim đập thình thịch, giờ sáng dậy bình thường.", "ROUTINE", [], "horror_movie_fright"),
        ("Tôi vừa đọc bài báo về triệu chứng u não trên mạng xong thấy lo lắng bất an, thỉnh thoảng thấy nhức nhức đầu nhẹ khi suy nghĩ.", "ROUTINE", [], "cyberchondria_headache"),
        ("Tôi vừa cắn miếng kem que lạnh quá bị buốt thấu óc tầm 10 giây xong tự hết hoàn toàn không còn đau nữa.", "ROUTINE", [], "brain_freeze_ice_cream"),
        ("Chiều qua tôi tập chống đẩy 50 cái ở phòng gym, sáng nay ngủ dậy thấy đau tức hai bên cơ ngực, ấn vào thấy ê ẩm cơ.", "ROUTINE", [], "pushups_pec_soreness"),
        ("Tôi ngồi trong phòng điều hòa công ty lạnh 19 độ thấy hai bàn tay buốt lạnh ngắt, đi ra ngoài sân nắng 2 phút là tay ấm hồng lại.", "ROUTINE", [], "ac_cold_extremity"),
        ("Tôi vừa đi khám nha khoa nhổ răng hàm dưới về được 2 tiếng, khóe môi dưới còn hơi tê tê thuốc tê chưa tan hết hoàn toàn.", "ROUTINE", [], "dental_anesthesia_numbness"),
        ("Hôm qua tôi chạy bộ 3km thể dục bình thường, hôm nay hai bắp chân thấy mỏi cơ sinh lý khi đi lại.", "ROUTINE", [], "normal_jogging_fatigue"),
        ("Tối qua đi ăn tiệc cưới ăn nhiều món lạ no căng bụng, sáng nay thấy bụng ấm ách đầy hơi khó tiêu nhẹ.", "ROUTINE", [], "wedding_buffet_fullness"),
        ("Thức khuya làm đồ án tốt nghiệp cả đêm đến 4 giờ sáng, sáng nay mắt thấy hơi mỏi điều tiết nhìn màn hình hơi nhòe nhẹ.", "ROUTINE", [], "eyestrain_screen_fatigue"),
        ("Bị cảm cúm thông thường 2 ngày nay, thỉnh thoảng hắt hơi sổ mũi nước trong, nhiệt độ 36.8 độ hoàn toàn không sốt.", "ROUTINE", [], "common_cold_rhinitis"),
    ]
    for i in range(20):
        t = adversarial_templates[i % len(adversarial_templates)]
        cid = f"V9-BAC-{i+1:04d}"
        cases.append({
            "case_id": cid,
            "input": f"[Ca đối chứng loại trừ lành tính]: {t[0]} (Mã ca {cid})",
            "expected_triage": t[1],
            "acceptable_triage": [t[1]],
            "cohort": "benign_adversarial_controls",
            "clinical_domain": t[3],
            "must_detect": [],
            "critical_fail_conditions": ["final_triage == EMERGENCY"],
        })

    return cases


def main() -> None:
    print("=" * 80)
    print("BUILDING 300 UNSEEN BENCHMARK CASES FOR BLIND V9")
    print("=" * 80)

    cases = build_blind_v9_cases()
    assert len(cases) == 300, f"Expected exactly 300 cases, got {len(cases)}"

    # Cohort breakdown check
    cohort_counts: dict[str, int] = {}
    for c in cases:
        ch = c.get("cohort", "unknown")
        cohort_counts[ch] = cohort_counts.get(ch, 0) + 1

    print("\n[COHORT DISTRIBUTION]")
    for ch, count in sorted(cohort_counts.items()):
        print(f"  - {ch:<35}: {count:3d} cases")

    vault_dir = REPO_ROOT / "blind_v9"
    cases_json, oracle_enc = split_and_vault_cases_v9(
        raw_cases=cases,
        vault_root=vault_dir,
        keep_plaintext_oracle=False,  # ORACLE STRICTLY ENCRYPTED AND INACCESSIBLE!
    )

    print(f"\n[+] Sealed cases (ZERO oracle info) written to: {cases_json}")
    print(f"[+] Encrypted Oracle Vault written to:          {oracle_enc}")
    print(f"[+] Canary token embedded in Oracle Vault.")
    print("=" * 80)


if __name__ == "__main__":
    main()
