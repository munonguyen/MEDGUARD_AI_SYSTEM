"""Toxicology Routing Recall and Precision Benchmark for MedGuard AI Candidate V9.

Evaluates multi-dimensional toxicity signature router across:
- 50+ positive toxic exposure cases (with and without named toxins)
- 50+ benign negative controls (therapeutic dosing, routine herbal teas, normal food)

Target Gates:
- Toxicology Routing Recall >= 99.0%
- Toxicology Routing Precision >= 95.0%
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

from app.services.toxicology_signature_router import route_by_toxicity_signature


@dataclass(frozen=True)
class ToxTestCase:
    case_id: str
    text: str
    is_toxic: bool
    category: str
    description: str


def generate_toxicology_test_suite() -> list[ToxTestCase]:
    cases: list[ToxTestCase] = []

    # -------------------------------------------------------------------------
    # 52 POSITIVE TOXIC CASES (Expect is_toxicology_eligible = True)
    # -------------------------------------------------------------------------
    # 1. Pesticides & Agricultural Chemicals (8)
    cases.append(ToxTestCase("TOX-POS-01", "Bệnh nhân uống nhầm nửa chén thuốc trừ sâu, nôn mửa liên tục và vã mồ hôi đầm đìa.", True, "pesticide", "Organophosphate ingestion"))
    cases.append(ToxTestCase("TOX-POS-02", "Uống thuốc bảo vệ thực vật tự tử, đồng tử co nhỏ như đầu đinh ghim, chảy nhiều đờm dãi.", True, "pesticide", "Cholinergic crisis"))
    cases.append(ToxTestCase("TOX-POS-03", "Phun thuốc diệt cỏ paraquat bị đổ tràn vào người và nuốt phải, rát bỏng miệng họng khó thở.", True, "pesticide", "Paraquat toxicity"))
    cases.append(ToxTestCase("TOX-POS-04", "Bé 3 tuổi chơi nghịch nuốt nhầm thuốc trừ sâu trong chai nước ngọt, đang lơ mơ co giật.", True, "pesticide", "Pediatric accidental pesticide"))
    cases.append(ToxTestCase("TOX-POS-05", "Uống nhầm ngụm thuốc rầy xanh, bụng đau quặn thắt, nôn thốc tháo và tím tái môi.", True, "pesticide", "Insecticide ingestion"))
    cases.append(ToxTestCase("TOX-POS-06", "Tiếp xúc thuốc sâu nồng độ cao trong phòng kín 2 tiếng, khó thở thở rít và buồn nôn liên tục.", True, "pesticide", "Inhalation organophosphate"))
    cases.append(ToxTestCase("TOX-POS-07", "Nuốt phải hóa chất diệt mối mọt nông nghiệp, người vã mồ hôi lạnh, mạch chậm dưới 45 lần/phút.", True, "pesticide", "Pesticide bradycardia"))
    cases.append(ToxTestCase("TOX-POS-08", "Ngộ độc thuốc diệt ốc bươu vàng, nôn ói xối xả, hạ huyết áp choáng váng.", True, "pesticide", "Molluscicide toxicity"))

    # 2. Rodenticides (6)
    cases.append(ToxTestCase("TOX-POS-09", "Uống nhầm viên kẹo tẩm thuốc diệt chuột Trung Quốc, nôn ra máu và co giật cơ.", True, "rodenticide", "Zinc phosphide/rodenticide"))
    cases.append(ToxTestCase("TOX-POS-10", "Bệnh nhân uống một gói thuốc diệt chuột dạng bột màu xám, đau rát thực quản và lơ mơ.", True, "rodenticide", "Rodenticide ingestion"))
    cases.append(ToxTestCase("TOX-POS-11", "Trẻ nhỏ nhặt viên thuốc chuột màu hồng ngậm vào miệng, mẹ phát hiện cạy miệng thấy nôn ói.", True, "rodenticide", "Pediatric rodenticide"))
    cases.append(ToxTestCase("TOX-POS-12", "Uống thuốc diệt chuột tự vẫn cách đây 30 phút, hơi thở hôi mùi tỏi cay nồng.", True, "rodenticide", "Phosphide garlic odor"))
    cases.append(ToxTestCase("TOX-POS-13", "Nuốt hạt lúa tẩm thuốc chuột hạt gạo đỏ, buồn nôn nhiều và hoa mắt chóng mặt.", True, "rodenticide", "Anticoagulant rodenticide early"))
    cases.append(ToxTestCase("TOX-POS-14", "Uống nhầm ống thuốc chuột nước màu đỏ không nhãn, nôn tháo và rối loạn nhịp tim.", True, "rodenticide", "Unknown liquid rodenticide"))

    # 3. Cardiotoxic & Neurotoxic Plants / Mushrooms / Herbal Decoctions (12)
    cases.append(ToxTestCase("TOX-POS-15", "Uống rượu ngâm củ ấu tàu lạ, sau 20 phút thấy tê dại đầu lưỡi, tim đập loạn xạ thình thịch.", True, "toxic_plant", "Aconitine cardiotoxicity"))
    cases.append(ToxTestCase("TOX-POS-16", "Nhai phải lá ngón rừng, nôn mửa dữ dội, sụp mi mắt và liệt cơ hô hấp.", True, "toxic_plant", "Gelsemium elegans (la ngon)"))
    cases.append(ToxTestCase("TOX-POS-17", "Ăn nấm rừng hái trên rẫy về nấu canh, sau ăn 2 tiếng cả nhà nôn mửa tiêu chảy xối xả.", True, "toxic_mushroom", "Wild poisonous mushrooms"))
    cases.append(ToxTestCase("TOX-POS-18", "Uống thuốc nam gia truyền rễ cây lạ chữa khớp, tim đập chậm 40 l/p và tụt huyết áp.", True, "toxic_plant", "Unknown herbal bradycardia"))
    cases.append(ToxTestCase("TOX-POS-19", "Nhai hạt mã tiền ngâm rượu, cơ thể co cứng từng cơn, co giật kiểu uốn ván.", True, "toxic_plant", "Strychnine (ma tien)"))
    cases.append(ToxTestCase("TOX-POS-20", "Uống nước sắc từ lá cây trúc đào, nôn nhiều và mạch chậm ngắt quãng rối loạn nhịp tim.", True, "toxic_plant", "Oleander cardiac glycoside"))
    cases.append(ToxTestCase("TOX-POS-21", "Nhai hạt thầu dầu, đau bụng quặn thắt dữ dội và đi ngoài ra máu.", True, "toxic_plant", "Ricin poisoning"))
    cases.append(ToxTestCase("TOX-POS-22", "Uống rượu ngâm rễ cây mật nhân phối hợp rễ cây lạ không rõ nguồn gốc, ảo giác lơ mơ mê sảng.", True, "toxic_plant", "Herbal neurotoxin"))
    cases.append(ToxTestCase("TOX-POS-23", "Bột lá cây lạ mua trên mạng uống giảm cân, tim đập nhanh 160 l/p vã mồ hôi và run rẩy.", True, "toxic_plant", "Unregulated weightloss herb"))
    cases.append(ToxTestCase("TOX-POS-24", "Ăn phải nấm lạ màu trắng mọc sau vườn, đau bụng dữ dội và da vàng mắt vàng sau đó.", True, "toxic_mushroom", "Amanita hepatotoxic"))
    cases.append(ToxTestCase("TOX-POS-25", "Uống thuốc bắc ngâm rượu không nhãn mác, tê rần môi miệng tay chân và nôn tro không ngừng.", True, "toxic_plant", "Unlabeled herbal liquor"))
    cases.append(ToxTestCase("TOX-POS-26", "Nấu canh cây cà độc dược ăn nhầm, đồng tử giãn to, da đỏ bừng khô nóng và nói sảng.", True, "toxic_plant", "Datura anticholinergic"))

    # 4. Caustic & Industrial Household Chemicals (8)
    cases.append(ToxTestCase("TOX-POS-27", "Uống nhầm ngụm nước tẩy bồn cầu axit clohydric, bỏng rát cổ họng và nôn ra nhầy máu.", True, "caustic", "Acid caustic ingestion"))
    cases.append(ToxTestCase("TOX-POS-28", "Trẻ nuốt nhầm nước javen tẩy trắng quần áo, khóc thét sưng nề môi miệng nôn ói.", True, "caustic", "Alkali bleach ingestion"))
    cases.append(ToxTestCase("TOX-POS-29", "Uống nhầm dầu hỏa đựng trong chai trà xanh, nôn sặc sụa và khó thở tím tái.", True, "hydrocarbon", "Hydrocarbon kerosene aspiration"))
    cases.append(ToxTestCase("TOX-POS-30", "Nuốt phải dung môi pha sơn xăng thơm, chóng mặt nôn mửa và lơ mơ.", True, "hydrocarbon", "Solvent paint thinner"))
    cases.append(ToxTestCase("TOX-POS-31", "Uống nhầm nước rửa kính ô tô chứa methanol, mắt mờ như nhìn qua sương mù và đau đầu nôn ói.", True, "toxic_alcohol", "Methanol windshield washer"))
    cases.append(ToxTestCase("TOX-POS-32", "Nuốt nhầm viên pin cúc áo đồ chơi, nghẹn họng đau rát ngực sau xương ức.", True, "foreign_body", "Button battery ingestion"))
    cases.append(ToxTestCase("TOX-POS-33", "Hít phải khí clo nồng độ cao trong bể bơi, ho sặc sụa co thắt phế quản và thở rít.", True, "toxic_gas", "Chlorine gas inhalation"))
    cases.append(ToxTestCase("TOX-POS-34", "Uống phải hóa chất thông cống xút kiềm đặc, bỏng loét môi miệng và nuốt nghẹn hoàn toàn.", True, "caustic", "Sodium hydroxide drain opener"))

    # 5. Overdose of Pharmaceuticals (10)
    cases.append(ToxTestCase("TOX-POS-35", "Uống một lúc 20 viên paracetamol 500mg để tự hại, sau 1 tiếng buồn nôn và vã mồ hôi.", True, "pharma_overdose", "Acetaminophen massive overdose"))
    cases.append(ToxTestCase("TOX-POS-36", "Uống cả vỉ thuốc ngủ seduxen diazepam 10 viên, đang ngủ sâu lay gọi không dậy.", True, "pharma_overdose", "Benzodiazepine overdose"))
    cases.append(ToxTestCase("TOX-POS-37", "Uống nhầm cả lọ thuốc hạ áp amlodipin của bà, huyết áp tụt kẹp và choáng váng ngất xỉu.", True, "pharma_overdose", "CCB overdose"))
    cases.append(ToxTestCase("TOX-POS-38", "Uống 15 viên thuốc chống trầm cảm amitriptylin, khô miệng đồng tử giãn và co giật cơ.", True, "pharma_overdose", "TCA overdose"))
    cases.append(ToxTestCase("TOX-POS-39", "Bé 2 tuổi nếm nuốt nhầm cả vỉ thuốc sắt của mẹ, nôn ói dịch đen đau bụng quằn quại.", True, "pharma_overdose", "Iron toxicity"))
    cases.append(ToxTestCase("TOX-POS-40", "Uống quá liều thuốc trợ tim digoxin, nhìn mọi vật có quầng vàng xanh và buồn nôn loạn nhịp.", True, "pharma_overdose", "Digoxin toxicity xanthopsia"))
    cases.append(ToxTestCase("TOX-POS-41", "Uống nhầm một nắm thuốc hạ đường huyết gliclazide, vã mồ hôi run rẩy hôn mê tụt đường huyết.", True, "pharma_overdose", "Sulfonylurea overdose"))
    cases.append(ToxTestCase("TOX-POS-42", "Uống quá liều thuốc giảm đau opioid morphin, thở chậm 6 lần/phút đồng tử co nhỏ như mũi kim.", True, "pharma_overdose", "Opioid triad"))
    cases.append(ToxTestCase("TOX-POS-43", "Trẻ em nuốt nhầm thuốc ho dextromethorphan cả lọ, ảo giác hưng phấn rồi lơ mơ.", True, "pharma_overdose", "Dextromethorphan overdose"))
    cases.append(ToxTestCase("TOX-POS-44", "Uống nhầm 10 viên thuốc chống động kinh carbamazepine, đi đứng lảo đảo rung giật nhãn cầu.", True, "pharma_overdose", "Carbamazepine toxicity"))

    # 6. Venoms & Toxin Inhalation / Environmental (8)
    cases.append(ToxTestCase("TOX-POS-45", "Bị ong vò vẽ đốt hơn 30 nốt khắp đầu mình, người tím tái khó thở và đái ra nước tiểu màu đen.", True, "envenomation", "Massive wasp sting rhabdomyolysis"))
    cases.append(ToxTestCase("TOX-POS-46", "Bị rắn cạp nia cắn ở vườn, sụp mi mắt khó nuốt khó thở và yếu liệt tứ chi.", True, "envenomation", "Bungarus krait neurotoxicity"))
    cases.append(ToxTestCase("TOX-POS-47", "Bị rắn lục đuôi đỏ cắn chảy máu liên tục không cầm ở vết răng cắn, sưng nề hoại tử tay.", True, "envenomation", "Viper coagulopathy"))
    cases.append(ToxTestCase("TOX-POS-48", "Sưởi than hoa trong phòng ngủ đóng kín cửa, cả hai vợ chồng hôn mê lơ mơ da đỏ hồng.", True, "toxic_gas", "Carbon monoxide poisoning"))
    cases.append(ToxTestCase("TOX-POS-49", "Bị bọ cạp rừng cắn vào chân buốt nhức dữ dội, vã mồ hôi tăng tiết đờm dãi và tim đập nhanh.", True, "envenomation", "Scorpion venom autonomic storm"))
    cases.append(ToxTestCase("TOX-POS-50", "Uống rượu tự nấu chứa cồn công nghiệp methanol, mắt mờ hoàn toàn và thở nhanh sâu toan chuyển hóa.", True, "toxic_alcohol", "Methanol illicit alcohol"))
    cases.append(ToxTestCase("TOX-POS-51", "Ăn phải cá nóc nướng ngoài biển, tê môi lưỡi mất cảm giác miệng và liệt hô hấp.", True, "marine_toxin", "Tetrodotoxin pufferfish"))
    cases.append(ToxTestCase("TOX-POS-52", "Ăn so biển nhầm với sam biển, sau 30 phút nôn mửa tê cứng tay chân và ngừng thở.", True, "marine_toxin", "Horseshoe crab tetrodotoxin"))

    # -------------------------------------------------------------------------
    # 52 BENIGN NEGATIVE CONTROLS (Expect is_toxicology_eligible = False)
    # -------------------------------------------------------------------------
    # 1. Therapeutic Normal Dosage Vitamins & Minerals (10)
    cases.append(ToxTestCase("TOX-NEG-01", "Tôi vừa uống 1 viên vitamin C 500mg sau bữa ăn sáng, sức khỏe hoàn toàn bình thường.", False, "benign_vitamin", "Daily vitamin C normal dose"))
    cases.append(ToxTestCase("TOX-NEG-02", "Uống một viên vitamin tổng hợp multivitamin đúng liều chỉ định hàng ngày, không có triệu chứng gì.", False, "benign_vitamin", "Multivitamin standard intake"))
    cases.append(ToxTestCase("TOX-NEG-03", "Hôm nay tôi uống 1 viên kẽm bổ sung sau khi ăn no, cảm thấy người khỏe mạnh bình thường.", False, "benign_vitamin", "Zinc standard supplement"))
    cases.append(ToxTestCase("TOX-NEG-04", "Bé nhà em vừa uống 1 giọt vitamin D3 định kỳ buổi sáng theo hướng dẫn bác sĩ, bé chơi ngoan.", False, "benign_vitamin", "Infant Vitamin D3 routine drop"))
    cases.append(ToxTestCase("TOX-NEG-05", "Tôi uống 1 viên dầu cá omega 3 sau bữa trưa, cơ thể hoàn toàn khỏe khoắn.", False, "benign_vitamin", "Fish oil routine dose"))
    cases.append(ToxTestCase("TOX-NEG-06", "Uống một viên canxi hữu cơ buổi sáng theo đơn bổ sung thai kỳ, không có khó chịu gì.", False, "benign_vitamin", "Calcium prenatal supplement"))
    cases.append(ToxTestCase("TOX-NEG-07", "Tôi uống 1 viên sủi bổ sung vitamin B complex đúng liều, người tỉnh táo làm việc bình thường.", False, "benign_vitamin", "B-complex effervescent normal"))
    cases.append(ToxTestCase("TOX-NEG-08", "Mẹ tôi uống viên bổ mắt lutein mỗi ngày 1 viên, thị lực ổn định không có dấu hiệu bất thường.", False, "benign_vitamin", "Lutein eye vitamin"))
    cases.append(ToxTestCase("TOX-NEG-09", "Uống một viên sắt bổ máu theo đơn bác sĩ kê đơn khi đi khám định kỳ, sức khỏe bình thường.", False, "benign_vitamin", "Prescribed iron normal dose"))
    cases.append(ToxTestCase("TOX-NEG-10", "Em uống 1 viên men vi sinh probiotic sau khi ăn sáng, bụng êm tiêu hóa bình thường.", False, "benign_vitamin", "Probiotic routine capsule"))

    # 2. Standard Dosing of Common OTC Cold / Pain Medications (10)
    cases.append(ToxTestCase("TOX-NEG-11", "Tôi bị sốt nhẹ và uống đúng 1 viên hạ sốt paracetamol 500mg, hiện đã hạ sốt và người dễ chịu.", False, "benign_otc", "Paracetamol standard therapeutic dose"))
    cases.append(ToxTestCase("TOX-NEG-12", "Uống 1 viên panadol extra giảm đau đầu do ngồi máy tính, uống đúng liều chỉ định trên hộp.", False, "benign_otc", "Panadol standard dose"))
    cases.append(ToxTestCase("TOX-NEG-13", "Bé bị cảm sốt được mẹ cho uống 1 gói hapacol 250mg đúng cân nặng, bé đã đỡ sốt và ngủ ngon.", False, "benign_otc", "Pediatric antipyretic correct weight dose"))
    cases.append(ToxTestCase("TOX-NEG-14", "Tôi uống 1 viên thuốc dị ứng loratadine chống hắt hơi do thời tiết, không thấy mệt mỏi.", False, "benign_otc", "Antihistamine standard dose"))
    cases.append(ToxTestCase("TOX-NEG-15", "Uống 1 gói siro ho thảo dược prospan giảm ho rát họng thông thường, sức khỏe ổn định.", False, "benign_otc", "Herbal cough syrup standard dose"))
    cases.append(ToxTestCase("TOX-NEG-16", "Tôi uống thuốc huyết áp amlodipine 5mg buổi sáng hàng ngày theo đơn bác sĩ, huyết áp ổn định 120/80.", False, "benign_otc", "Chronic medication standard dose"))
    cases.append(ToxTestCase("TOX-NEG-17", "Uống 1 viên men tiêu hóa berberin khi hơi lỏng bụng, sau đó bụng êm không còn đi ngoài.", False, "benign_otc", "Berberine standard dose"))
    cases.append(ToxTestCase("TOX-NEG-18", "Uống thuốc đau dạ dày omeprazole 1 viên trước bữa ăn sáng theo đơn tái khám, người bình thường.", False, "benign_otc", "Omeprazole prescribed dose"))
    cases.append(ToxTestCase("TOX-NEG-19", "Ngậm 1 viên kẹo ngậm ho thảo mộc bạc hà thông thường, họng dễ chịu mát mẻ.", False, "benign_otc", "Throat lozenge routine"))
    cases.append(ToxTestCase("TOX-NEG-20", "Dùng thuốc xịt mũi nước muối sinh lý rửa mũi khi trời trở lạnh, không có triệu chứng gì bất thường.", False, "benign_otc", "Saline nasal spray"))

    # 3. Routine Culinary & Herbal Teas (12)
    cases.append(ToxTestCase("TOX-NEG-21", "Tôi vừa uống một cốc trà hoa cúc thảo mộc thông thường để thư giãn trước khi đi ngủ, cơ thể rất thoải mái.", False, "benign_tea", "Chamomile tea"))
    cases.append(ToxTestCase("TOX-NEG-22", "Uống một tách trà atiso giải nhiệt buổi chiều, vị ngọt nhẹ không có cảm giác khó chịu.", False, "benign_tea", "Artichoke tea"))
    cases.append(ToxTestCase("TOX-NEG-23", "Pha một ly trà gừng ấm uống giữ ấm họng khi trời lạnh, cơ thể ấm áp bình thường.", False, "benign_tea", "Ginger tea"))
    cases.append(ToxTestCase("TOX-NEG-24", "Tôi uống một cốc trà tâm sen hãm nước sôi để dễ ngủ, người nhẹ nhàng không thấy mệt.", False, "benign_tea", "Lotus seed plumule tea"))
    cases.append(ToxTestCase("TOX-NEG-25", "Uống một ly trà xanh tươi pha loãng buổi sáng sau ăn, đầu óc tỉnh táo làm việc.", False, "benign_tea", "Fresh green tea"))
    cases.append(ToxTestCase("TOX-NEG-26", "Gia đình tôi uống nước chè xanh truyền thống hàng ngày, sức khỏe mọi người đều tốt.", False, "benign_tea", "Daily green tea beverage"))
    cases.append(ToxTestCase("TOX-NEG-27", "Tôi uống trà thảo mộc túi lọc mua ở siêu thị có hoa cúc và cỏ ngọt, hoàn toàn bình thường.", False, "benign_tea", "Supermarket herbal tea"))
    cases.append(ToxTestCase("TOX-NEG-28", "Uống một cốc nước đậu đen rang nấu nước uống thanh nhiệt, không có triệu chứng lạ.", False, "benign_tea", "Roasted black bean water"))
    cases.append(ToxTestCase("TOX-NEG-29", "Pha trà lá sen khô uống giải khát mùa hè, cơ thể sảng khoái không có vấn đề gì.", False, "benign_tea", "Lotus leaf beverage"))
    cases.append(ToxTestCase("TOX-NEG-30", "Uống một ly nước chanh ấm pha mật ong buổi sớm, họng êm dịu bình thường.", False, "benign_tea", "Honey lemon water"))
    cases.append(ToxTestCase("TOX-NEG-31", "Uống một cốc sữa chua uống lên men sau bữa trưa, hệ tiêu hóa khỏe mạnh.", False, "benign_tea", "Yogurt drink"))
    cases.append(ToxTestCase("TOX-NEG-32", "Uống một ly nước cam vắt tươi bổ sung vitamin C, người khỏe mạnh.", False, "benign_tea", "Fresh orange juice"))

    # 4. Everyday Foods & Normal Culinary Ingestion (10)
    cases.append(ToxTestCase("TOX-NEG-33", "Hôm nay tôi ăn thử món trái cây quả thanh mai nhập khẩu ở siêu thị, vị chua ngọt ngon miệng người bình thường.", False, "benign_food", "Exotic supermarket fruit"))
    cases.append(ToxTestCase("TOX-NEG-34", "Ăn một bát canh nấm kim châm nấu thịt bò mua ở siêu thị Co.opmart, tiêu hóa êm ái.", False, "benign_food", "Culinary enoki mushrooms"))
    cases.append(ToxTestCase("TOX-NEG-35", "Ăn món canh rau ngót nấu tôm buổi trưa, gia đình ăn ngon miệng và không có triệu chứng gì.", False, "benign_food", "Normal family meal"))
    cases.append(ToxTestCase("TOX-NEG-36", "Ăn món salad rau củ hữu cơ tươi sống, cảm thấy tiêu hóa nhẹ nhàng bình thường.", False, "benign_food", "Organic salad"))
    cases.append(ToxTestCase("TOX-NEG-37", "Thử ăn món đặc sản bún cá cay Hải Phòng khi đi du lịch, người hoàn toàn khỏe khoắn.", False, "benign_food", "Regional cuisine"))
    cases.append(ToxTestCase("TOX-NEG-38", "Ăn một quả táo gala rửa sạch gọt vỏ sau bữa ăn, không có bất kỳ biểu hiện lạ nào.", False, "benign_food", "Peeled apple snack"))
    cases.append(ToxTestCase("TOX-NEG-39", "Ăn chè dưỡng nhan có hạt sen táo đỏ tuyết yến nấu ở nhà, cơ thể khỏe mạnh da dẻ hồng hào.", False, "benign_food", "Home-cooked herbal dessert"))
    cases.append(ToxTestCase("TOX-NEG-40", "Uống một ly sữa đậu nành nóng ăn kèm bánh bao buổi sáng, no bụng và dễ chịu.", False, "benign_food", "Soymilk breakfast"))
    cases.append(ToxTestCase("TOX-NEG-41", "Ăn cơm với món mướp đắng xào trứng, vị đắng thanh nhẹ người bình thường khỏe khoắn.", False, "benign_food", "Bitter melon dish"))
    cases.append(ToxTestCase("TOX-NEG-42", "Ăn bánh quy bơ và uống nước lọc khi giải lao, không có triệu chứng gì bất thường.", False, "benign_food", "Biscuit snack"))

    # 5. Routine Domestic Handling / Cleaners without ingestion or injury (10)
    cases.append(ToxTestCase("TOX-NEG-43", "Tôi lau sàn nhà bằng nước lau sàn sunlight hương hoa hồng có đeo găng tay, nhà cửa sạch sẽ.", False, "benign_handling", "Flooring cleaner routine use"))
    cases.append(ToxTestCase("TOX-NEG-44", "Rửa chén bát bằng nước rửa chén sunlight, tráng sạch nước không có cảm giác ngứa hay dị ứng.", False, "benign_handling", "Dishwashing liquid routine"))
    cases.append(ToxTestCase("TOX-NEG-45", "Xịt nước hoa phòng hương oải hương trong phòng khách, mùi hương dễ chịu không bị hắt hơi.", False, "benign_handling", "Air freshener normal smell"))
    cases.append(ToxTestCase("TOX-NEG-46", "Giặt quần áo bằng viên giặt omo xả thơm, da dẻ bình thường không kích ứng.", False, "benign_handling", "Laundry detergent pod normal use"))
    cases.append(ToxTestCase("TOX-NEG-47", "Xịt cồn 70 độ sát khuẩn tay nhanh trước khi ăn cơm, tay khô ráo bình thường.", False, "benign_handling", "Hand sanitizer 70% alcohol"))
    cases.append(ToxTestCase("TOX-NEG-48", "Dùng nước xịt kính lau gương soi trong nhà tắm, đeo khẩu trang cẩn thận và không có khó chịu gì.", False, "benign_handling", "Glass cleaner routine"))
    cases.append(ToxTestCase("TOX-NEG-49", "Tưới cây hoa hồng trong vườn bằng nước máy thông thường, tâm trạng vui vẻ.", False, "benign_handling", "Garden watering normal"))
    cases.append(ToxTestCase("TOX-NEG-50", "Dùng xà phòng diệt khuẩn lifebuoy rửa tay sau khi đi làm về, bàn tay sạch sẽ không ngứa.", False, "benign_handling", "Bar soap handwash"))
    cases.append(ToxTestCase("TOX-NEG-51", "Thắp một nén hương trầm tự nhiên ngày rằm, phòng thoáng khí không khói cay mắt.", False, "benign_handling", "Incense normal use"))
    cases.append(ToxTestCase("TOX-NEG-52", "Bôi kem dưỡng ẩm cerave lên da mặt trước khi đi ngủ, da mềm mại không nổi mẩn đỏ.", False, "benign_handling", "Moisturizer cream normal use"))

    return cases


def run_toxicology_benchmark() -> dict[str, Any]:
    print("=" * 85)
    print("MEDGUARD AI CANDIDATE V9 — TOXICOLOGY ROUTING BENCHMARK (104 CASES)")
    print("=" * 85)

    suite = generate_toxicology_test_suite()
    total_cases = len(suite)

    pos_cases = [c for c in suite if c.is_toxic]
    neg_cases = [c for c in suite if not c.is_toxic]

    tp = 0
    fn = 0
    tn = 0
    fp = 0

    failures: list[dict[str, Any]] = []

    for c in suite:
        res = route_by_toxicity_signature(c.text)
        routed = res.is_toxicology_eligible

        if c.is_toxic:
            if routed:
                tp += 1
            else:
                fn += 1
                failures.append({
                    "case_id": c.case_id,
                    "type": "FALSE_NEGATIVE_ROUTING",
                    "text": c.text,
                    "category": c.category,
                    "rationale": res.rationale,
                })
        else:
            if not routed:
                tn += 1
            else:
                fp += 1
                failures.append({
                    "case_id": c.case_id,
                    "type": "FALSE_POSITIVE_ROUTING",
                    "text": c.text,
                    "category": c.category,
                    "rationale": res.rationale,
                    "suspected_syndrome": res.suspected_syndrome,
                })

    recall = (tp / len(pos_cases) * 100.0) if pos_cases else 0.0
    precision = (tp / (tp + fp) * 100.0) if (tp + fp) else 0.0

    print(f"Total Cases Evaluated: {total_cases} (Pos: {len(pos_cases)}, Neg: {len(neg_cases)})")
    print(f"True Positives (TP):   {tp}/{len(pos_cases)}")
    print(f"False Negatives (FN):  {fn} (Missed Toxic Cases)")
    print(f"True Negatives (TN):   {tn}/{len(neg_cases)}")
    print(f"False Positives (FP):  {fp} (Benign Cases Incorrectly Routed)")
    print()
    print(f"Toxicology Routing Recall:    {recall:.2f}% (Target >= 99.0%)")
    print(f"Toxicology Routing Precision: {precision:.2f}% (Target >= 95.0%)")
    recall_passed = recall >= 99.0
    precision_passed = precision >= 95.0
    print(f"Overall Toxicology Gate:      {'PASSED' if (recall_passed and precision_passed) else 'FAILED'}")
    print("=" * 85)

    if failures:
        print(f"\n[FAILURES - {len(failures)} cases]")
        for f in failures:
            print(f"  - [{f['type']}] {f['case_id']} ({f['category']}): {f['text'][:70]}... | {f['rationale']}")

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
        "recall_passed": recall_passed,
        "precision_passed": precision_passed,
        "overall_passed": recall_passed and precision_passed,
        "failures": failures,
    }

    out_file = REPO_ROOT / "outputs" / "toxicology_routing_report.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\n[+] Saved toxicology report to: {out_file}")
    return report


if __name__ == "__main__":
    run_toxicology_benchmark()
