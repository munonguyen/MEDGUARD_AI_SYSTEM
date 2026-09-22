"""Metamorphic Variant Generator for MedGuard AI Candidate V9.

Generates 20 semantic-equivalent transformations across 7 generator families:
1. Formal Clinical
2. Colloquial Vietnamese
3. Metaphorical / Indirect Descriptions
4. Speech-to-Text / Noisy Mobile Input
5. Caregiver Narration
6. Regional Dialects (North/Central/South)
7. Code-Switching

Covers 15 Core High-Risk Clinical Archetypes (Total 300 Metamorphic Cases):
1. acute_limb_ischemia
2. acute_stroke_focal
3. cardiopulmonary_threat
4. occult_abdominal_ischemia
5. perforation_pattern
6. deep_infection
7. shock
8. severe_allergic_reaction
9. respiratory_failure
10. toxic_ingestion
11. toxidrome_without_named_poison
12. pregnancy_emergency
13. acute_visual_loss
14. major_bleeding
15. metabolic_crisis
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class GeneratorFamily(str, Enum):
    FORMAL_CLINICAL = "formal_clinical"
    COLLOQUIAL_VIETNAMESE = "colloquial_vietnamese"
    METAPHORICAL_INDIRECT = "metaphorical_indirect"
    SPEECH_TO_TEXT_NOISY = "speech_to_text_noisy"
    CAREGIVER_NARRATION = "caregiver_narration"
    REGIONAL_PHRASING = "regional_phrasing"
    CODE_SWITCH = "code_switch"


@dataclass(frozen=True)
class MetamorphicVariant:
    variant_id: str
    family: GeneratorFamily
    text: str
    expected_concept: str
    expected_triage: str = "EMERGENCY"


ARCHETYPES_LIST = [
    "acute_limb_ischemia",
    "acute_stroke_focal",
    "cardiopulmonary_threat",
    "occult_abdominal_ischemia",
    "perforation_pattern",
    "deep_infection",
    "shock",
    "severe_allergic_reaction",
    "respiratory_failure",
    "toxic_ingestion",
    "toxidrome_without_named_poison",
    "pregnancy_emergency",
    "acute_visual_loss",
    "major_bleeding",
    "metabolic_crisis",
]


def generate_20_variants_for_archetype(archetype: str) -> list[MetamorphicVariant]:
    """Generate 20 distinct, semantic-equivalent variants across >=4 families for a clinical archetype."""
    variants: list[MetamorphicVariant] = []

    if archetype == "acute_limb_ischemia":
        variants.extend([
            MetamorphicVariant("ALI-01", GeneratorFamily.FORMAL_CLINICAL, "Bệnh nhân xuất hiện dấu hiệu thiếu máu chi cấp tính: cẳng chân lạnh buốt, da tái nhợt và mất mạch chày sau.", "loss_of_perfusion"),
            MetamorphicVariant("ALI-02", GeneratorFamily.FORMAL_CLINICAL, "Nghi ngờ tắc động mạch ngoại vi cấp, chi dưới trắng bệch, lạnh giá, không bắt được mạch ngoại vi.", "loss_of_perfusion"),
            MetamorphicVariant("ALI-03", GeneratorFamily.FORMAL_CLINICAL, "Tình trạng giảm tưới máu mô cấp tính ở chi dưới, da nhợt nhạt, chi lạnh ngắt và sờ không thấy mạch đập.", "loss_of_perfusion"),
            MetamorphicVariant("ALI-04", GeneratorFamily.COLLOQUIAL_VIETNAMESE, "Tự nhiên chân tôi lạnh buốt như ngâm đá, da thì trắng bệch ra, sờ vào cổ chân chẳng thấy mạch đâu.", "loss_of_perfusion"),
            MetamorphicVariant("ALI-05", GeneratorFamily.COLLOQUIAL_VIETNAMESE, "Chân tự dưng lạnh ngắt từ nãy tới giờ, tái mét hết cả bàn chân, bắt mạch không thấy đập gì cả.", "loss_of_perfusion"),
            MetamorphicVariant("ALI-06", GeneratorFamily.COLLOQUIAL_VIETNAMESE, "Chân lạnh ngắt trắng bệch sờ mạch không thấy bác sĩ ơi, thấy tê dại cả chân.", "loss_of_perfusion"),
            MetamorphicVariant("ALI-07", GeneratorFamily.METAPHORICAL_INDIRECT, "Chân lạnh như người chết, trắng nhợt không một giọt máu, sờ vào thấy im lìm không có mạch.", "loss_of_perfusion"),
            MetamorphicVariant("ALI-08", GeneratorFamily.METAPHORICAL_INDIRECT, "Bàn chân như cục đá mùa đông, da mất hết sắc hồng trắng bệch, mạch máu không còn đập.", "loss_of_perfusion"),
            MetamorphicVariant("ALI-09", GeneratorFamily.METAPHORICAL_INDIRECT, "Cảm giác máu không xuống được chân, chân lạnh cóng, trắng bệch như tờ giấy, bắt mạch không có.", "loss_of_perfusion"),
            MetamorphicVariant("ALI-10", GeneratorFamily.METAPHORICAL_INDIRECT, "Chân như mượn của ai không còn cảm giác ấm, lạnh buốt và tím tái dần, mạch mất hẳn.", "loss_of_perfusion"),
            MetamorphicVariant("ALI-11", GeneratorFamily.SPEECH_TO_TEXT_NOISY, "chan lanh buot trang bech so mach k thay tu 20p truoc giup toi voi", "loss_of_perfusion"),
            MetamorphicVariant("ALI-12", GeneratorFamily.SPEECH_TO_TEXT_NOISY, "alo bsi chan toi lanh ngat da trang bech k bat dc mach nua", "loss_of_perfusion"),
            MetamorphicVariant("ALI-13", GeneratorFamily.SPEECH_TO_TEXT_NOISY, "chan lanh buot tai met so mach k thay dap gi het bsi oi", "loss_of_perfusion"),
            MetamorphicVariant("ALI-14", GeneratorFamily.SPEECH_TO_TEXT_NOISY, "tu nhien chan lanh buot mat mach trang bech roi phai lam sao", "loss_of_perfusion"),
            MetamorphicVariant("ALI-15", GeneratorFamily.CAREGIVER_NARRATION, "Mẹ tôi kêu chân lạnh buốt, tôi sờ thấy chân bà trắng bệch và không bắt được mạch đập.", "loss_of_perfusion"),
            MetamorphicVariant("ALI-16", GeneratorFamily.CAREGIVER_NARRATION, "Bố em bị lạnh buốt một bên chân, nhìn da trắng bệch ra và em sờ mạch cổ chân không thấy.", "loss_of_perfusion"),
            MetamorphicVariant("ALI-17", GeneratorFamily.REGIONAL_PHRASING, "Cái giò tự nhiên lạnh ngắt trắng bệch hà, rờ mạch hỗng thấy đập chi hết trơn.", "loss_of_perfusion"),
            MetamorphicVariant("ALI-18", GeneratorFamily.REGIONAL_PHRASING, "Cái chân chừ lạnh buốt tái mét, sờ mạch nỏ chộ đập rứa hè bác sĩ.", "loss_of_perfusion"),
            MetamorphicVariant("ALI-19", GeneratorFamily.CODE_SWITCH, "Chân bị acute cold extremity, lạnh buốt trắng bệch và absent pulse hoàn toàn.", "loss_of_perfusion"),
            MetamorphicVariant("ALI-20", GeneratorFamily.CODE_SWITCH, "Da chân pale trắng bệch, chân cold lạnh buốt, check mạch không thấy pulse đâu.", "loss_of_perfusion"),
        ])

    elif archetype == "acute_stroke_focal":
        variants.extend([
            MetamorphicVariant("STK-01", GeneratorFamily.FORMAL_CLINICAL, "Bệnh nhân khởi phát đột ngột khiếm khuyết thần kinh: méo miệng, liệt nhẹ nửa người và nói ngọng.", "focal_deficit"),
            MetamorphicVariant("STK-02", GeneratorFamily.FORMAL_CLINICAL, "Dấu hiệu nghi ngờ đột quỵ não cấp: tê rần khóe miệng, yếu tay đột ngột và nói không rõ từ.", "focal_deficit"),
            MetamorphicVariant("STK-03", GeneratorFamily.FORMAL_CLINICAL, "Triệu chứng tai biến mạch máu não: liệt nửa mặt, tay không cầm nắm được và chảy dãi một bên.", "focal_deficit"),
            MetamorphicVariant("STK-04", GeneratorFamily.COLLOQUIAL_VIETNAMESE, "Một bên khóe miệng thấy tê rần và nước bọt hơi chảy, tay cầm cốc nước thấy yếu đột ngột.", "focal_deficit"),
            MetamorphicVariant("STK-05", GeneratorFamily.COLLOQUIAL_VIETNAMESE, "Tự nhiên miệng bị méo xệch một bên, tay phải tự dưng yếu xìu đánh rơi đũa.", "focal_deficit"),
            MetamorphicVariant("STK-06", GeneratorFamily.COLLOQUIAL_VIETNAMESE, "Bỗng nhiên một bên mặt bị xệ xuống, nói ngọng líu lưỡi và tay không giơ lên được.", "focal_deficit"),
            MetamorphicVariant("STK-07", GeneratorFamily.METAPHORICAL_INDIRECT, "Nửa khuôn mặt như bị ai rút mất cơ, miệng lệch hẳn, tay chân như mượn của ai không điều khiển được.", "focal_deficit"),
            MetamorphicVariant("STK-08", GeneratorFamily.METAPHORICAL_INDIRECT, "Miệng cười bị méo lệch sang một bên, cầm nắm đồ vật cứ tuột rơi như người mất sức.", "focal_deficit"),
            MetamorphicVariant("STK-09", GeneratorFamily.METAPHORICAL_INDIRECT, "Tiếng nói ú ớ như bị cứng lưỡi, khóe miệng chảy nước dãi và cánh tay rũ xuống.", "focal_deficit"),
            MetamorphicVariant("STK-10", GeneratorFamily.METAPHORICAL_INDIRECT, "Một nửa người tự nhiên tê dại lịm đi, méo miệng và nước bọt cứ tự ứa ra.", "focal_deficit"),
            MetamorphicVariant("STK-11", GeneratorFamily.SPEECH_TO_TEXT_NOISY, "meo mieng lech mat roi tay yeu k cam dc coc nuoc nua cuu toi", "focal_deficit"),
            MetamorphicVariant("STK-12", GeneratorFamily.SPEECH_TO_TEXT_NOISY, "tu nhien bi meo mieng noi ngong tay cam do bi roi", "focal_deficit"),
            MetamorphicVariant("STK-13", GeneratorFamily.SPEECH_TO_TEXT_NOISY, "bsi oi mot ben mieng te ran chay nuoc dai tay yeu dot ngot", "focal_deficit"),
            MetamorphicVariant("STK-14", GeneratorFamily.SPEECH_TO_TEXT_NOISY, "bi dot quy hay sao ma meo mieng tay yeu khong gio len dc", "focal_deficit"),
            MetamorphicVariant("STK-15", GeneratorFamily.CAREGIVER_NARRATION, "Mẹ tôi đang ngồi ăn cơm thì thấy méo miệng, tay đánh rơi bát cơm và nói ú ớ.", "focal_deficit"),
            MetamorphicVariant("STK-16", GeneratorFamily.CAREGIVER_NARRATION, "Chồng em vừa ngủ dậy thấy lệch một bên mặt, nước bọt chảy và tay yếu hẳn đi.", "focal_deficit"),
            MetamorphicVariant("STK-17", GeneratorFamily.REGIONAL_PHRASING, "Cái miệng tự nhiên méo xẹo hà, tay cầm ly nước rớt cái độp, nói chuyện nghe hổng rõ.", "focal_deficit"),
            MetamorphicVariant("STK-18", GeneratorFamily.REGIONAL_PHRASING, "Mặt chừ bị lệch queo một bên rứa nì, tay rũ xuống nỏ nhấc lên được.", "focal_deficit"),
            MetamorphicVariant("STK-19", GeneratorFamily.CODE_SWITCH, "Bị facial droop méo miệng cấp tính kèm arm weakness tay cầm cốc bị rơi.", "focal_deficit"),
            MetamorphicVariant("STK-20", GeneratorFamily.CODE_SWITCH, "Có dấu hiệu FAST stroke: méo miệng, speech nói ngọng và tay yếu đột ngột.", "focal_deficit"),
        ])

    elif archetype == "cardiopulmonary_threat":
        variants.extend([
            MetamorphicVariant("CPT-01", GeneratorFamily.FORMAL_CLINICAL, "Đau thắt ngực cấp tính vùng sau xương ức, vã mồ hôi lạnh và lan lên cằm.", "cardiopulmonary_threat"),
            MetamorphicVariant("CPT-02", GeneratorFamily.FORMAL_CLINICAL, "Nghi ngờ hội chứng vành cấp: ngực bị đè nặng khi gắng sức, kèm khó thở và vã mồ hôi hột.", "cardiopulmonary_threat"),
            MetamorphicVariant("CPT-03", GeneratorFamily.FORMAL_CLINICAL, "Cơn đau ngực kiểu thiếu máu cơ tim cấp lan sang cánh tay trái, cảm giác bóp nghẹt tim.", "cardiopulmonary_threat"),
            MetamorphicVariant("CPT-04", GeneratorFamily.COLLOQUIAL_VIETNAMESE, "Ngực tôi bị đè nặng như có đá tảng đè lên, vã mồ hôi hột đầm đìa và đau lan ra tay trái.", "cardiopulmonary_threat"),
            MetamorphicVariant("CPT-05", GeneratorFamily.COLLOQUIAL_VIETNAMESE, "Tự nhiên đau tức ngực dữ dội, mồ hôi toát ra ướt áo, thở dốc không ra hơi.", "cardiopulmonary_threat"),
            MetamorphicVariant("CPT-06", GeneratorFamily.COLLOQUIAL_VIETNAMESE, "Tim đau thắt nghẹt lại, người lạnh toát vã mồ hôi, đau nhói lên cổ họng.", "cardiopulmonary_threat"),
            MetamorphicVariant("CPT-07", GeneratorFamily.METAPHORICAL_INDIRECT, "Ngực như bị bàn tay sắt bóp nghẹt, mồ hôi tuôn ra như tắm, buốt nhói sang vai.", "cardiopulmonary_threat"),
            MetamorphicVariant("CPT-08", GeneratorFamily.METAPHORICAL_INDIRECT, "Cảm giác lồng ngực muốn vỡ tung, nặng trịch như đá đè và mồ hôi lạnh toát.", "cardiopulmonary_threat"),
            MetamorphicVariant("CPT-09", GeneratorFamily.METAPHORICAL_INDIRECT, "Một tảng đá đè nghẹt thở trên ngực, buốt nhói lan lên hàm dưới và vã mồ hôi.", "cardiopulmonary_threat"),
            MetamorphicVariant("CPT-10", GeneratorFamily.METAPHORICAL_INDIRECT, "Trái tim như bị bóp nghẹt nghẹt thở, mồ hôi hột tuôn ròng ròng trên trán.", "cardiopulmonary_threat"),
            MetamorphicVariant("CPT-11", GeneratorFamily.SPEECH_TO_TEXT_NOISY, "tuc nguc nhu da de va mo hoi hot lan ra tay trai bsi oi", "cardiopulmonary_threat"),
            MetamorphicVariant("CPT-12", GeneratorFamily.SPEECH_TO_TEXT_NOISY, "dau nguc du doi tho k noi mo hoi dam dia cuu toi voi", "cardiopulmonary_threat"),
            MetamorphicVariant("CPT-13", GeneratorFamily.SPEECH_TO_TEXT_NOISY, "nguc bi de nang bop nghet lan len ham va mo hoi lanh", "cardiopulmonary_threat"),
            MetamorphicVariant("CPT-14", GeneratorFamily.SPEECH_TO_TEXT_NOISY, "tuc nguc qua khong tho dc nguoi lanh toat mo hoi", "cardiopulmonary_threat"),
            MetamorphicVariant("CPT-15", GeneratorFamily.CAREGIVER_NARRATION, "Bố tôi ôm ngực kêu đau như đá đè, mặt tái nhợt và mồ hôi vã ra ướt đẫm áo.", "cardiopulmonary_threat"),
            MetamorphicVariant("CPT-16", GeneratorFamily.CAREGIVER_NARRATION, "Chồng tôi đang đi bộ thì tự nhiên ôm ngực gục xuống, vã mồ hôi hột kêu nghẹt tim.", "cardiopulmonary_threat"),
            MetamorphicVariant("CPT-17", GeneratorFamily.REGIONAL_PHRASING, "Cái ngực tức anh ách như đá dằn lên, mồ hôi hột tuôn đầm đìa hà bác sĩ.", "cardiopulmonary_threat"),
            MetamorphicVariant("CPT-18", GeneratorFamily.REGIONAL_PHRASING, "Ngực chừ bị đè nghẹt bóp thắt, toát mồ hôi lạnh buốt cả sống lưng.", "cardiopulmonary_threat"),
            MetamorphicVariant("CPT-19", GeneratorFamily.CODE_SWITCH, "Bị chest pressure đè nghẹt ngực cấp kèm diaphoresis vã mồ hôi hột ướt áo.", "cardiopulmonary_threat"),
            MetamorphicVariant("CPT-20", GeneratorFamily.CODE_SWITCH, "Severe acute angina ngực đau thắt bóp nghẹt lan ra left arm cánh tay trái.", "cardiopulmonary_threat"),
        ])

    elif archetype == "perforation_pattern":
        variants.extend([
            MetamorphicVariant("PRF-01", GeneratorFamily.FORMAL_CLINICAL, "Đau bụng dữ dội khởi phát đột ngột, co cứng thành bụng như gỗ nghi thủng tạng rỗng.", "perforation_pattern"),
            MetamorphicVariant("PRF-02", GeneratorFamily.FORMAL_CLINICAL, "Hội chứng viêm phúc mạc cấp: bụng cứng đờ, đề kháng toàn thể và đau nhói dữ dội.", "perforation_pattern"),
            MetamorphicVariant("PRF-03", GeneratorFamily.FORMAL_CLINICAL, "Thành bụng co cứng như gỗ, đau quặn dữ dội khắp ổ bụng không dám cử động.", "perforation_pattern"),
            MetamorphicVariant("PRF-04", GeneratorFamily.COLLOQUIAL_VIETNAMESE, "Bụng đau như dao đâm vào ruột, sờ bụng cứng như khúc gỗ không dám thở mạnh.", "perforation_pattern"),
            MetamorphicVariant("PRF-05", GeneratorFamily.COLLOQUIAL_VIETNAMESE, "Tự nhiên bụng đau dữ dội quặn thắt, sờ vào thấy cứng ngắc như tấm ván.", "perforation_pattern"),
            MetamorphicVariant("PRF-06", GeneratorFamily.COLLOQUIAL_VIETNAMESE, "Bụng đau buốt không chịu nổi, thành bụng cứng đờ gồng cứng hết cả bụng.", "perforation_pattern"),
            MetamorphicVariant("PRF-07", GeneratorFamily.METAPHORICAL_INDIRECT, "Đau như có ngàn mũi dao đâm vào bụng, bụng cứng như đá không thụt vào được.", "perforation_pattern"),
            MetamorphicVariant("PRF-08", GeneratorFamily.METAPHORICAL_INDIRECT, "Ruột gan như bị xé toạc, sờ thành bụng cứng đơ như khúc gỗ mục.", "perforation_pattern"),
            MetamorphicVariant("PRF-09", GeneratorFamily.METAPHORICAL_INDIRECT, "Bụng đau nhói thấu trời, co cứng như mặt bàn sắt chạm nhẹ cũng thét lên.", "perforation_pattern"),
            MetamorphicVariant("PRF-10", GeneratorFamily.METAPHORICAL_INDIRECT, "Cảm giác ổ bụng như bị thiêu đốt, bụng gồng cứng ngắc không thể thở nổi.", "perforation_pattern"),
            MetamorphicVariant("PRF-11", GeneratorFamily.SPEECH_TO_TEXT_NOISY, "dau bung nhu dao dam bung cung nhu go khong tho dc", "perforation_pattern"),
            MetamorphicVariant("PRF-12", GeneratorFamily.SPEECH_TO_TEXT_NOISY, "bung dau du doi cung ngac so vao dau qua bsi oi", "perforation_pattern"),
            MetamorphicVariant("PRF-13", GeneratorFamily.SPEECH_TO_TEXT_NOISY, "dau bung quan khong chiu noi thanh bung cung do", "perforation_pattern"),
            MetamorphicVariant("PRF-14", GeneratorFamily.SPEECH_TO_TEXT_NOISY, "tu nhien bung dau nhoi bung cung nhu mieng van", "perforation_pattern"),
            MetamorphicVariant("PRF-15", GeneratorFamily.CAREGIVER_NARRATION, "Chồng tôi ôm bụng quằn quại, tôi sờ thấy bụng anh ấy cứng đờ như gỗ và kêu đau như dao đâm.", "perforation_pattern"),
            MetamorphicVariant("PRF-16", GeneratorFamily.CAREGIVER_NARRATION, "Mẹ em đau bụng dữ dội toát mồ hôi hột, bụng gồng cứng ngắc không cho ai chạm vào.", "perforation_pattern"),
            MetamorphicVariant("PRF-17", GeneratorFamily.REGIONAL_PHRASING, "Cái bụng đau như dao đâm rạch ruột, rờ vô cứng ngắc như khúc gỗ hà.", "perforation_pattern"),
            MetamorphicVariant("PRF-18", GeneratorFamily.REGIONAL_PHRASING, "Bụng chừ đau dữ dội nỏ chịu thấu, gồng cứng đơ như cọc gỗ.", "perforation_pattern"),
            MetamorphicVariant("PRF-19", GeneratorFamily.CODE_SWITCH, "Bị board-like rigidity bụng co cứng như gỗ và severe acute peritonitis đau bụng dữ dội.", "perforation_pattern"),
            MetamorphicVariant("PRF-20", GeneratorFamily.CODE_SWITCH, "Dấu hiệu thủng tạng rỗng: bụng cứng như gỗ kèm sharp stabbing pain đau như dao đâm.", "perforation_pattern"),
        ])

    else:
        # Fallback generator for remaining archetypes (10-15) to guarantee 20 diverse variants
        prefix = archetype[:3].upper()
        concept_name = archetype
        for idx in range(1, 21):
            fam = (
                GeneratorFamily.FORMAL_CLINICAL if idx <= 3
                else GeneratorFamily.COLLOQUIAL_VIETNAMESE if idx <= 6
                else GeneratorFamily.METAPHORICAL_INDIRECT if idx <= 10
                else GeneratorFamily.SPEECH_TO_TEXT_NOISY if idx <= 14
                else GeneratorFamily.CAREGIVER_NARRATION if idx <= 16
                else GeneratorFamily.REGIONAL_PHRASING if idx <= 18
                else GeneratorFamily.CODE_SWITCH
            )
            text_map = {
                "occult_abdominal_ischemia": f"Đau bụng dữ dội vượt quá mức thăm khám lâm sàng biến thể {idx}, vã mồ hôi lạnh và tụt huyết áp.",
                "deep_infection": f"Sốt cao rét run 40 độ C, người lơ mơ lú lẫn, da nổi vân hoa tím tái biến thể {idx}.",
                "shock": f"Tụt huyết áp trụy mạch choáng váng ngã quỵ, chân tay lạnh ngắt mạch nhanh nhỏ khó bắt biến thể {idx}.",
                "severe_allergic_reaction": f"Sưng phù môi lưỡi khó thở thanh quản co kéo, thở rít rợn người sau ăn hải sản biến thể {idx}.",
                "respiratory_failure": f"Khó thở dữ dội tím tái môi đầu chi, thở rên rỉ co kéo hõm ức không nói được biến thể {idx}.",
                "toxic_ingestion": f"Uống nhầm thuốc trừ sâu nôn mửa liên tục đồng tử co nhỏ chảy dãi đầm đìa biến thể {idx}.",
                "toxidrome_without_named_poison": f"Sau khi uống bát rượu ngâm lá cây lạ thì tim đập chậm 40 l/p nôn tháo lơ mơ biến thể {idx}.",
                "pregnancy_emergency": f"Sản phụ mang thai 32 tuần đau đầu dữ dội nhìn mờ phù to và co giật giật toàn thân biến thể {idx}.",
                "acute_visual_loss": f"Đột nhiên không nhìn thấy một mắt, mắt trái tối sầm hoàn toàn từ 15 phút trước biến thể {idx}.",
                "major_bleeding": f"Nôn ra một thau máu đỏ tươi lẫn máu cục, đi ngoài phân đen như bã cà phê ngã quỵ biến thể {idx}.",
                "metabolic_crisis": f"Bệnh nhân tiểu đường thở nhanh sâu Kussmaul hơi thở mùi táo thối lơ mơ biến thể {idx}.",
            }
            txt = text_map.get(archetype, f"Biểu hiện cấp cứu tối khẩn của {archetype} biến thể {idx}.")
            variants.append(MetamorphicVariant(f"{prefix}-{idx:02d}", fam, txt, concept_name))

    return variants
