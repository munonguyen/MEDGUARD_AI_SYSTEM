"""Sensor Blindness Benchmark for MedGuard AI V6.

Evaluates semantic invariance of the Semantic Clinical Fact Parser across:
- 22 Clinical Danger Families
- 8 Distinct Linguistic Transformations (Formal, Folk, Metaphor, Caregiver, Teencode, STT-Corrupted, Code-Switch, Indirect-Functional)
- 3 Variants (PRESENT, ABSENT, HISTORICAL_OR_OTHER)
Total: 528 test cases.

Enforces:
- Gate 15: Critical Fact Recall >= 98%
- Gate 16: Critical Fact Precision >= 95%
- Gate 17: Threat Activation Recall >= 98%
- Gate 20: Experiencer Accuracy >= 99%
- Gate 21: Negation/Temporality Accuracy >= 99%
"""

from __future__ import annotations

import pytest

from app.services.clinical_fact_parser import parse_semantic_clinical_facts
from app.services.clinical_threat_graph import evaluate_threat_graph, ThreatLevel


FACT_FAMILY_BENCHMARK = [
    # 1. Vision Loss
    {
        'family': 'Sudden Vision Loss',
        'concept': 'vision_loss',
        'threat_dim': 'vision_threat',
        'expressions': {
            'formal': 'Bệnh nhân bị mất thị lực đột ngột một bên mắt trái không đau.',
            'folk': 'Tự nhiên con mắt bên trái tối sầm lại không thấy đường.',
            'metaphor': 'Mắt trái như có ai kéo tấm rèm đen sập xuống che kín hết.',
            'caregiver': 'Mẹ tôi bảo tự nhiên bà chẳng nhìn thấy gì ở mắt bên trái nữa.',
            'teencode': 'tu nhien mat trai toi thui k thay j nua bs oi',
            'stt_corrupted': 'con mat ben trai tu nhien toi sam chang nhin thay ri nua',
            'code_switch': 'vision loss dot ngot mat trai nghi ngo crao',
            'indirect_functional': 'Đưa bàn tay trước mắt trái mà hoàn toàn không nhìn thấy ngón tay nào.',
        }
    },
    # 2. Acute Limb Ischemia
    {
        'family': 'Acute Limb Ischemia',
        'concept': 'arterial_occlusion',
        'threat_dim': 'limb_threat',
        'expressions': {
            'formal': 'Tắc động mạch cánh tay cấp tính, mất mạch quay, chi thiếu máu nuôi.',
            'folk': 'Cánh tay tự nhiên trắng bệch, lạnh ngắt và đau nhức buốt.',
            'metaphor': 'Tay trái lạnh buốt như đá tảng, đau buốt cùng cực và bắt mạch không đập.',
            'caregiver': 'Bác sĩ ơi tay bố tôi bỗng trắng bệch lạnh ngắt bắt mạch quay không thấy đập.',
            'teencode': 'tay trai trang bech lanh ngat k bat dc mach quay',
            'stt_corrupted': 'canh tay tu nhien lang ngat tai nhot mat mach quay',
            'code_switch': 'acute limb ischemia tay trai pulseless lanh ngat',
            'indirect_functional': 'Bàn tay lạnh tái nhợt và bắt mạch cổ tay hoàn toàn không thấy đập nữa.',
        }
    },
    # 3. Acute Peritonitis
    {
        'family': 'Acute Peritonitis / Abdominal Rigidity',
        'concept': 'abdominal_rigidity',
        'threat_dim': 'surgical_abdomen',
        'expressions': {
            'formal': 'Viêm phúc mạc toàn thể, khám bụng co cứng đề kháng toàn bộ.',
            'folk': 'Bụng đau quặn thắt rứt ruột rứt gan, sờ vô thấy cứng ngắc.',
            'metaphor': 'Bụng cứng như miếng ván, gõ vô nghe cộp cộp đau nhói.',
            'caregiver': 'Chồng tôi đau bụng dữ dội, bụng ông ấy gồng cứng như khúc gỗ.',
            'teencode': 'bung dau du doi bung cung ngac k tho manh dc',
            'stt_corrupted': 'bung dau du doi so vo thay cung ngat nhu mieng go',
            'code_switch': 'acute peritonitis bung co cung board-like rigidity',
            'indirect_functional': 'Bụng đau nhức nhối đến mức không dám thở mạnh hay duỗi thẳng chân.',
        }
    },
    # 4. Acute Stroke
    {
        'family': 'Acute Stroke / Hemiplegia',
        'concept': 'acute_stroke',
        'threat_dim': 'neurology',
        'expressions': {
            'formal': 'Đột quỵ thiếu máu não cấp, yếu liệt nửa người và thất ngôn.',
            'folk': 'Bỗng nhiên xây xẩm cấm khẩu bải hoải một bên tay chân.',
            'metaphor': 'Miệng méo xệch, nói năng líu nhíu người ta nghe không được.',
            'caregiver': 'Mẹ tôi vừa nói chuyện thì tự nhiên miệng méo và tay phải rớt đũa.',
            'teencode': 'tu nhien tay chan bai hoai noi k ro tieng',
            'stt_corrupted': 'xay xam cam khau bai hoai tay chan noi ngong dot ngot',
            'code_switch': 'acute stroke meo mieng liet nua nguoi dot ngot',
            'indirect_functional': 'Tay phải yếu mềm nhũn cầm cái cốc cũng không nổi, bước đi xiêu vẹo.',
        }
    },
    # 5. Severe Tetanus
    {
        'family': 'Severe Tetanus Trismus',
        'concept': 'tetanic_spasm',
        'threat_dim': 'neurology',
        'expressions': {
            'formal': 'Uốn ván thể toàn thể, cứng hàm, nuốt khó và co cứng cơ vân.',
            'folk': 'Cứng hàm không há được miệng, nuốt nghẹn sặc sau vết đinh gỉ.',
            'metaphor': 'Lưng uốn cong người gà gập khi có tiếng động mạnh, hàm cứng đờ.',
            'caregiver': 'Cháu nó bị đinh gỉ đâm 1 tuần nay cứng hàm không nuốt được.',
            'teencode': 'bi dinh gi dam gio cung ham k ha mieng dc',
            'stt_corrupted': 'cung ham rang can chac nuot nghen sac sau dinh ri',
            'code_switch': 'tetanus sau vet thuong cung ham trismus nuot nghen',
            'indirect_functional': 'Răng cắn chặt không thể há miệng đút muỗng cháo, người co cứng lại.',
        }
    },
    # 6. Compartment Syndrome
    {
        'family': 'Compartment Syndrome',
        'concept': 'compartment_syndrome',
        'threat_dim': 'limb_threat',
        'expressions': {
            'formal': 'Hội chứng chèn ép khoang cẳng chân sau chấn thương, đau tăng khi gấp thụ động.',
            'folk': 'Bắp chân sưng to căng cứng như khúc gỗ đau buốt dữ dội.',
            'metaphor': 'Chân căng như quả bóng sắp nổ, đau buốt buốt tận óc khi co ngón chân.',
            'caregiver': 'Chân con tôi sưng to căng cứng sau khi bó bột, cháu khóc thét.',
            'teencode': 'bap chan sung to cang cung nhu khuc go dau buot',
            'stt_corrupted': 'cang chan sung to cang ngat dau buot khi gap thu dong',
            'code_switch': 'compartment syndrome bap chan cang cung dau du doi',
            'indirect_functional': 'Bắp chân căng tức dữ dội và mất cảm giác mu chân hoàn toàn.',
        }
    },
    # 7. Femoral Hematoma
    {
        'family': 'Femoral Hematoma / Rupture',
        'concept': 'femoral_hematoma_or_rupture',
        'threat_dim': 'limb_threat',
        'expressions': {
            'formal': 'Khối máu tụ vùng bẹn sau can thiệp mạch vành, tụt huyết áp cấp.',
            'folk': 'Sau thông tim vùng bẹn sưng to phồng căng đau buốt, chân tái lạnh.',
            'metaphor': 'Khối u ở bẹn to nhanh như quả cam đập thình thịch, người lả đi.',
            'caregiver': 'Bố tôi sau can thiệp mạch thì bẹn sưng to phồng căng tụt huyết áp.',
            'teencode': 'sau thong tim vung ben sung to phong cang tut huyet ap',
            'stt_corrupted': 'vung ben sung to phong cang tut huyet ap da chan tim tai',
            'code_switch': 'femoral hematoma sau can thiep mach ben sung to phong cang',
            'indirect_functional': 'Vết chọc động mạch bẹn sưng to đột ngột và huyết áp tụt kẹp da chân lạnh ngắt.',
        }
    },
    # 8. Vascular Access Rupture
    {
        'family': 'Vascular Access Rupture (AVF)',
        'concept': 'vascular_access_rupture_threat',
        'threat_dim': 'limb_threat',
        'expressions': {
            'formal': 'Dọa vỡ cầu nối động tĩnh mạch chạy thận nhân tạo AVF, da căng bóng sắp nứt.',
            'folk': 'Cầu tay chạy thận phình to căng bóng sắp vỡ nứt da rỉ máu.',
            'metaphor': 'Cầu mổ tay phồng như cái bọng nước mỏng tanh sắp bục ra.',
            'caregiver': 'Cầu nối chạy thận của mẹ tôi phình to căng bóng sắp vỡ.',
            'teencode': 'cau tay chay than phinh to cang bong sap vo',
            'stt_corrupted': 'cau noi avf phinh to da cang mong sap vo nut',
            'code_switch': 'avf rupture threat cau noi chay than phinh to sap vo',
            'indirect_functional': 'Khối cầu tay giãn lớn da mỏng dính nhìn thấy mạch máu sắp bục chảy máu dữ dội.',
        }
    },
    # 9. Aortic Dissection
    {
        'family': 'Aortic Dissection',
        'concept': 'aortic_dissection_or_rupture',
        'threat_dim': 'circulation',
        'expressions': {
            'formal': 'Phình tách động mạch chủ ngực bụng, đau xé ngực lan sau lưng.',
            'folk': 'Đau xé ngực đâm xuyên thẳng ra sau lưng giữa hai bả vai.',
            'metaphor': 'Cảm giác như có nhát dao xé toạc ngực xiên thẳng ra sau lưng.',
            'caregiver': 'Chồng tôi ôm ngực kêu đau như xé thịt xuyên thẳng ra sau lưng.',
            'teencode': 'dau xe nguc xuyen sau lung giua hai ba vai',
            'stt_corrupted': 'dau xe nguc dau xe lung xien thang ra sau lung',
            'code_switch': 'aortic dissection dau xe nguc xuyen sau lung',
            'indirect_functional': 'Cơn đau ngực dữ dội kinh hoàng lan dọc sống lưng làm không thể đứng thẳng.',
        }
    },
    # 10. Ischemic Priapism
    {
        'family': 'Ischemic Priapism',
        'concept': 'ischemic_priapism',
        'threat_dim': 'surgical_abdomen',
        'expressions': {
            'formal': 'Cương đau dương vật kéo dài trên 4 giờ do thiếu máu cục bộ.',
            'folk': 'Cương cứng cương đau dương vật liên tục suốt từ đêm không mềm được.',
            'metaphor': 'Chỗ kín cứng ngắc đau buốt như dùi đâm suốt nhiều giờ liền.',
            'caregiver': 'Người nhà bị cương cứng đau đớn liên tục trên 6 tiếng không hạ.',
            'teencode': 'cuong cung duong vat tren 4 gio dau don k mem dc',
            'stt_corrupted': 'cuong cung duong vat tren 5 tieng lien tuc khong mem',
            'code_switch': 'ischemic priapism cuong cung duong vat tren 4 gio',
            'indirect_functional': 'Bộ phận sinh dục cương cứng đau nhức cực độ kéo dài nhiều tiếng không tự xẹp.',
        }
    },
    # 11. Strangulated Hernia
    {
        'family': 'Strangulated Hernia',
        'concept': 'strangulated_hernia',
        'threat_dim': 'surgical_abdomen',
        'expressions': {
            'formal': 'Thoát vị bẹn nghẹt, khối phồng ở bẹn đau dữ dội không đẩy lên được.',
            'folk': 'Cục thịt ở háng thò lò đau nhức nhối nghẹn không nhét vô được.',
            'metaphor': 'Dưới háng có cục phồng căng cứng như quả trứng đau buốt không thụt vào.',
            'caregiver': 'Bé nhà tôi dưới bẹn có khối sa đau dữ dội không đẩy lên được.',
            'teencode': 'cuc thit o hang dau nhuc nhoi nghen k nhet vo dc',
            'stt_corrupted': 'khoi thoat vi o hang dau nhuc nhoi nghen khong day len dc',
            'code_switch': 'strangulated hernia thoat vi ben nghen khong nhet vo duoc',
            'indirect_functional': 'Khối phồng vùng háng bỗng sưng to đau buốt và bụng trướng căng bí trung đại tiện.',
        }
    },
    # 12. Intussusception
    {
        'family': 'Intussusception',
        'concept': 'intussusception',
        'threat_dim': 'surgical_abdomen',
        'expressions': {
            'formal': 'Lồng ruột cấp ở trẻ nhũ nhi, nôn ói và đi cầu phân nhầy máu.',
            'folk': 'Khóc thét từng cơn co gập người, đi ngoài phân như thạch cà chua.',
            'metaphor': 'Trẻ quằn quại từng cơn bụng quặn gập người nôn ra dịch xanh rớt phân đỏ.',
            'caregiver': 'Con tôi khóc thét từng cơn co gập bụng, tã dính phân như thạch cà chua.',
            'teencode': 'khoc thet tung con phan nhu thach ca chua',
            'stt_corrupted': 'khoc thet tung con co gap phan nhu thach ca chua long ruot',
            'code_switch': 'intussusception long ruot phan nhu thach ca chua',
            'indirect_functional': 'Bé quấy khóc dữ dội ngắt quãng bỏ bú nôn vọt và đại tiện ra máu nhầy.',
        }
    },
    # 13. Mesenteric Ischemia
    {
        'family': 'Mesenteric Ischemia',
        'concept': 'mesenteric_ischemia',
        'threat_dim': 'surgical_abdomen',
        'expressions': {
            'formal': 'Tắc động mạch mạc treo cấp, đau bụng dữ dội không tương xứng với thăm khám.',
            'folk': 'Sau ăn đau bụng quằn quại không tương xứng, tiền sử rung nhĩ.',
            'metaphor': 'Ruột như bị thắt nghẽn xoắn nghẹt đau chết đi sống lại sau bữa ăn.',
            'caregiver': 'Bà tôi có bệnh rung nhĩ tự nhiên đau bụng quằn quại dữ dội.',
            'teencode': 'rung nhi dau bung quan quai khong tuong xung',
            'stt_corrupted': 'rung nhi sau an dau bung quan quai khong tuong xung',
            'code_switch': 'mesenteric ischemia thieu mau mac treo dau bung du doi',
            'indirect_functional': 'Cơn đau bụng bão tố xuất hiện đột ngột ở bệnh nhân tim mạch không đỡ với thuốc giảm đau.',
        }
    },
    # 14. Acute Appendicitis
    {
        'family': 'Acute Appendicitis',
        'concept': 'acute_appendicitis',
        'threat_dim': 'surgical_abdomen',
        'expressions': {
            'formal': 'Viêm ruột thừa cấp, đau hố chậu phải ấn đau nhói kèm sốt buồn nôn.',
            'folk': 'Đau bụng quanh rốn chuyển xuống hố chậu phải sốt nôn.',
            'metaphor': 'Đau nhói buốt góc bụng dưới bên phải, bước đi phải khom lưng.',
            'caregiver': 'Con tôi kêu đau bụng quanh rốn rồi dồn xuống hố chậu phải nôn mửa.',
            'teencode': 'ho chau phai an dau nhoi ruot thua sot non',
            'stt_corrupted': 'dau bung quanh ron chuyen xuong ho chau phai sot non',
            'code_switch': 'acute appendicitis ruot thua ho chau phai an dau nhoi sot',
            'indirect_functional': 'Cơn đau âm ỉ tăng dần khu trú ở bụng dưới bên phải làm không thể ho hay nhảy cò lò.',
        }
    },
    # 15. Spinal Cord Compression
    {
        'family': 'Spinal Cord Compression',
        'concept': 'spinal_cord_compression',
        'threat_dim': 'neurology',
        'expressions': {
            'formal': 'Hội chứng chèn ép tủy sống ngực cấp, hai chân yếu nhanh liệt dần.',
            'folk': 'Hai chân liệt hoàn toàn không đứng được, tê bì ngang rốn.',
            'metaphor': 'Cảm giác như bị cắt đứt ngang hông, chân dưới mềm nhũn vô cảm.',
            'caregiver': 'Mẹ tôi 2 hôm nay hai chân yếu nhanh liệt dần không đứng dậy được.',
            'teencode': 'hai chan yeu nhanh liet dan k dung dc chen ep tuy',
            'stt_corrupted': 'hai chan yeu nhanh liet dan khong dung duoc te bi ngang ron',
            'code_switch': 'spinal cord compression hai chan liet hoan toan khong dung duoc',
            'indirect_functional': 'Đôi chân mất hết sức lực hoàn toàn không thể nhấc gót và mất cảm giác tiêu tiểu.',
        }
    },
    # 16. Thunderclap Headache
    {
        'family': 'Thunderclap Headache / SAH',
        'concept': 'intracranial_catastrophe',
        'threat_dim': 'neurology',
        'expressions': {
            'formal': 'Đau đầu như sét đánh dữ dội nhất cuộc đời, kèm cứng gáy sợ ánh sáng.',
            'folk': 'Đầu đau nhức buốt dữ dội chưa từng thấy, cổ gáy cứng ngắc không cúi được.',
            'metaphor': 'Như có tia sét nổ tung trong sọ não, đau vỡ đầu ngã quỵ xuống.',
            'caregiver': 'Chồng tôi đột ngột kêu đau đầu như sét đánh rồi ngã vật ra mê sảng.',
            'teencode': 'dau dau nhu set danh du doi nhat cuoc doi gay cung nhac',
            'stt_corrupted': 'dau dau nhu set danh gay cung nhac khong cui duoc',
            'code_switch': 'thunderclap headache dau dau set danh nghi ngo sah xuat huyet duoi nhen',
            'indirect_functional': 'Cơn nhức đầu bùng phát đạt đỉnh đau cực đại chỉ trong vài giây làm mất tri giác.',
        }
    },
    # 17. Acute Coronary Syndrome
    {
        'family': 'Acute Coronary Syndrome',
        'concept': 'acute_coronary_syndrome',
        'threat_dim': 'circulation',
        'expressions': {
            'formal': 'Hội chứng vành cấp, đau thắt ngực đè ép lan tay trái vã mồ hôi.',
            'folk': 'Tức nghẹn như tảng đá đè trên ngực, vã mồ hôi ướt đẫm lưng áo.',
            'metaphor': 'Ngực đau bóp nghẹt như đá đè, tim nhảy ra ngoài, đau thắt lan lên quai hàm.',
            'caregiver': 'Bố tôi ôm ngực kêu tức nghẹn như tảng đá đè vã mồ hôi lạnh ngắt.',
            'teencode': 'nguc de nghen tho hong noi dau nguc de ep lan tay trai',
            'stt_corrupted': 'dau bop nghet nhu da de lan len goc ham va mo hoi',
            'code_switch': 'acute coronary syndrome dau bop nghet nguc lan quai ham',
            'indirect_functional': 'Cảm giác lồng ngực bị nghiền nát nghẹt thở không thể bước thêm một bước nào.',
        }
    },
    # 18. Cardiac Tamponade
    {
        'family': 'Cardiac Tamponade',
        'concept': 'cardiac_tamponade',
        'threat_dim': 'circulation',
        'expressions': {
            'formal': 'Chèn ép tim cấp, tam chứng Beck tĩnh mạch cổ nổi to, tiếng tim mờ xa xăm.',
            'folk': 'Tĩnh mạch cổ nổi to, tiếng tim nghe mờ xa xăm, khó thở tụt huyết áp.',
            'metaphor': 'Tim đập nghẹn ngào như bị bóp trong túi nước, hơi thở yếu dần lả đi.',
            'caregiver': 'Bác sĩ ơi mẹ tôi khó thở dữ dội, mạch cổ nổi to tiếng tim mờ xa xăm.',
            'teencode': 'tinh mach co noi to tieng tim mo xa xam chen ep tim cap',
            'stt_corrupted': 'tinh mach co noi to tieng tim nghe mo xa xam tut huyet ap',
            'code_switch': 'cardiac tamponade chen ep tim cap tinh mach co noi to',
            'indirect_functional': 'Cổ họng nổi phồng tĩnh mạch ngoằn ngoèo và huyết áp tụt sâu kèm ngất lịm.',
        }
    },
    # 19. Airway Obstruction
    {
        'family': 'Airway Obstruction / Stridor',
        'concept': 'airway_obstruction_or_severe_dyspnea',
        'threat_dim': 'airway',
        'expressions': {
            'formal': 'Tắc nghẽn đường thở cấp, thở rít thanh quản stridor, tím tái đầu chi.',
            'folk': 'Thở rít như kéo nhị, nghẹn ứ ở cổ không thở được tím tái môi.',
            'metaphor': 'Cổ họng như bị bàn tay vô hình bóp nghẹt, rít lên từng cơn không ra hơi.',
            'caregiver': 'Cháu bé hóc dị vật thở rít như kéo nhị nghẹn ứ ở cổ tím ngắt.',
            'teencode': 'tho rit nhu keo nhi nghen u o co k tho dc tim tai',
            'stt_corrupted': 'tho rit thanh quan tim tai dau ngon tay va moi tho ngop',
            'code_switch': 'stridor tho rit thanh quan tac nghen duong tho cap',
            'indirect_functional': 'Không thể nói được từ nào vì họng tắc nghẽn và lồng ngực co rút lõm sâu.',
        }
    },
    # 20. Tension Pneumothorax
    {
        'family': 'Tension Pneumothorax',
        'concept': 'tension_pneumothorax',
        'threat_dim': 'breathing',
        'expressions': {
            'formal': 'Tràn khí màng phổi áp lực, lồng ngực gõ vang như trống, suy hô hấp cấp.',
            'folk': 'Lồng ngực một bên gõ vang như trống, khó thở tím tái khó nói.',
            'metaphor': 'Một bên ngực căng phồng như quả banh gõ kêu bong bong, nghẹt thở lịm người.',
            'caregiver': 'Sau tai nạn ngực cháu căng phồng gõ vang như trống không thở được.',
            'teencode': 'long nguc go vang nhu trong tran khi mang phoi ap luc',
            'stt_corrupted': 'long nguc go vang nhu trong kho tho tim tai tut huyet ap',
            'code_switch': 'tension pneumothorax tran khi ap luc long nguc go vang',
            'indirect_functional': 'Lồng ngực một bên bất động căng phồng và khí quản bị lệch sang một bên.',
        }
    },
    # 21. Acute Pulmonary Edema
    {
        'family': 'Acute Pulmonary Edema',
        'concept': 'acute_pulmonary_edema',
        'threat_dim': 'breathing',
        'expressions': {
            'formal': 'Phù phổi cấp suy tim trái, khạc ra bọt màu hồng, không thể nằm thẳng.',
            'folk': 'Khạc ra bọt màu hồng, không thể nằm thẳng phải ngồi chồm hổm để thở.',
            'metaphor': 'Phổi như ngập chìm trong nước, trào bọt hồng sủi ở miệng nghẹt thở.',
            'caregiver': 'Bố tôi khạc ra bọt màu hồng phải ngồi chồm hổm tì tay đầu gối để thở.',
            'teencode': 'khac ra bot mau hong k the nam thang phu phoi cap',
            'stt_corrupted': 'khac ra bot mau hong ngoi chom hom ti tay vao dau goi de tho',
            'code_switch': 'pulmonary edema phu phoi cap sui bot hong kho tho',
            'indirect_functional': 'Vừa đặt lưng xuống là ngạt thở trào bọt hồng ra khóe miệng phải ngồi thở dốc.',
        }
    },
    # 22. Toxic Ingestion Overdose
    {
        'family': 'Toxic Ingestion Overdose',
        'concept': 'toxic_ingestion',
        'threat_dim': 'toxic_exposure',
        'expressions': {
            'formal': 'Ngộ độc cấp do uống quá liều 15 viên paracetamol 500mg cùng lúc.',
            'folk': 'Uống 15 viên paracetamol vì buồn chán, uống cả vỉ thuốc ngủ.',
            'metaphor': 'Nuốt ực cả vốc thuốc vào bụng giờ lơ mơ nôn thốc nôn tháo.',
            'caregiver': 'Em tôi uống nhầm thuốc quá liều li bì lay gọi không tỉnh.',
            'teencode': 'uong 15 vien paracetamol 500mg qua lieu',
            'stt_corrupted': 'uong ca vi thuoc ngu qua lieu li bi lay khong tinh',
            'code_switch': 'toxic ingestion overdose uong qua lieu 15 vien paracetamol',
            'indirect_functional': 'Uống nhầm thuốc liều cao li bì nằm bất động lay gọi không tỉnh.',
        }
    },
]


@pytest.mark.parametrize('family_data', FACT_FAMILY_BENCHMARK)
def test_sensor_blindness_present_invariance(family_data: dict) -> None:
    """Tests PRESENT expressions (Gate 15: Recall >= 98%, Gate 17: Activation >= 98%, Gate 20: Experiencer >= 99%)."""
    expected_concept = family_data['concept']
    expected_dim = family_data['threat_dim']
    expressions = family_data['expressions']

    recalled = 0
    activated = 0
    experiencer_correct = 0

    for style, text in expressions.items():
        facts = parse_semantic_clinical_facts(text)
        has_concept = any(expected_concept == e.concept for e in facts.active_patient_events)
        if has_concept:
            recalled += 1

        threat = evaluate_threat_graph(facts)
        active_dims = threat.critical_dimensions or threat.high_dimensions
        has_dim = expected_dim in active_dims
        if has_dim and threat.max_threat_level in (ThreatLevel.CRITICAL, ThreatLevel.HIGH):
            activated += 1

        # Check experiencer
        if style == 'caregiver':
            if any(e.experiencer in ('patient_consultation', 'patient') for e in facts.events):
                experiencer_correct += 1
        else:
            if any(e.experiencer == 'patient' for e in facts.events):
                experiencer_correct += 1

    total = len(expressions)
    assert recalled / total >= 0.98, f"Gate 15 Failed for {family_data['family']}: Recall={recalled}/{total}"
    assert activated / total >= 0.98, f"Gate 17 Failed for {family_data['family']}: Activation={activated}/{total}"
    assert experiencer_correct / total >= 0.98, f"Gate 20 Failed for {family_data['family']}: Experiencer={experiencer_correct}/{total}"


@pytest.mark.parametrize('family_data', FACT_FAMILY_BENCHMARK)
def test_sensor_blindness_adversarial_absent(family_data: dict) -> None:
    """Tests ABSENT expressions (Gate 16: Precision >= 95%, Gate 21: Negation Accuracy >= 99%)."""
    expected_concept = family_data['concept']
    expected_dim = family_data['threat_dim']
    expressions = family_data['expressions']

    for style, text in expressions.items():
        abs_text = f"{text}, nhưng tôi không bị như vậy."
        facts = parse_semantic_clinical_facts(abs_text)
        threat = evaluate_threat_graph(facts)

        # Gate 21: Assertion must be ABSENT
        for e in facts.events:
            if e.concept == expected_concept:
                assert e.assertion == 'absent', f"Gate 21 failed for {family_data['family']} [{style}]: assertion={e.assertion}"

        # Gate 16: Zero active patient threat
        active_patient_has_concept = any(expected_concept == e.concept for e in facts.active_patient_events)
        assert not active_patient_has_concept, f"Gate 16 failed: Hallucinated active concept in ABSENT variant [{style}]"

        # Threat must NOT activate
        active_dims = threat.critical_dimensions or threat.high_dimensions
        assert expected_dim not in active_dims, f"Gate 16 failed: False threat activation in ABSENT variant [{style}]"


@pytest.mark.parametrize('family_data', FACT_FAMILY_BENCHMARK)
def test_sensor_blindness_adversarial_historical(family_data: dict) -> None:
    """Tests HISTORICAL / THIRD-PARTY expressions (Gate 16: Precision >= 95%, Gate 20/21: Accuracy >= 99%)."""
    expected_concept = family_data['concept']
    expected_dim = family_data['threat_dim']
    expressions = family_data['expressions']

    for style, text in expressions.items():
        hist_text = f"Bố tôi từng bị {text} năm ngoái, còn hôm nay tôi chỉ đau vai."
        facts = parse_semantic_clinical_facts(hist_text)
        threat = evaluate_threat_graph(facts)

        # Gate 20/21: Must identify historical temporality or non-patient experiencer
        for e in facts.events:
            if e.concept == expected_concept:
                assert e.temporality == 'historical' or e.experiencer == 'other',                     f"Gate 20/21 failed for {family_data['family']} [{style}]: temp={e.temporality}, exp={e.experiencer}"

        # Gate 16: Zero active patient threat
        active_patient_has_concept = any(expected_concept == e.concept for e in facts.active_patient_events)
        assert not active_patient_has_concept, f"Gate 16 failed: Hallucinated active concept in HISTORICAL variant [{style}]"

        # Threat must NOT activate
        active_dims = threat.critical_dimensions or threat.high_dimensions
        assert expected_dim not in active_dims, f"Gate 16 failed: False threat activation in HISTORICAL variant [{style}]"
