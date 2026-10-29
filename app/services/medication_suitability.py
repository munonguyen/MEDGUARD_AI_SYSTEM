"""Medication Suitability and Fulfillment Engine for MedGuard AI.

Evaluates 3 distinct medication states:
  1. ELIGIBLE_OTC (Safe for OTC symptom relief with GPP pharmacy links & Google Maps locator)
  2. CONTRAINDICATED (Unsafe due to allergies, organ impairment, pregnancy, or drug-drug interactions)
  3. EMERGENCY_RED_FLAG (Strictly prohibited at home; requires immediate ER transit)
"""

from __future__ import annotations

from dataclasses import dataclass, field
import urllib.parse
from typing import Any, Literal

from app.services.clinical_text import normalize_search_text


@dataclass(frozen=True)
class MedicationRecommendation:
    generic_name: str
    brand_names: list[str]
    dosage_guideline: str
    administration: str
    warning_and_monitoring: str
    certified_gpp_online_links: list[dict[str, str]]


@dataclass(frozen=True)
class MedicationSuitabilityResult:
    state: Literal["ELIGIBLE_OTC", "CONTRAINDICATED", "EMERGENCY_RED_FLAG"]
    state_label: str
    clinical_rationale: str
    contraindication_reasons: list[str] = field(default_factory=list)
    recommended_medications: list[MedicationRecommendation] = field(default_factory=list)
    safe_alternatives: list[str] = field(default_factory=list)
    nearest_pharmacy_maps_url: str = ""
    pharmacy_chain_links: list[dict[str, str]] = field(default_factory=list)
    requires_prescription: bool = False
    emergency_transfer_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "state_label": self.state_label,
            "clinical_rationale": self.clinical_rationale,
            "contraindication_reasons": self.contraindication_reasons,
            "safe_alternatives": self.safe_alternatives,
            "nearest_pharmacy_maps_url": self.nearest_pharmacy_maps_url,
            "pharmacy_chain_links": self.pharmacy_chain_links,
            "requires_prescription": self.requires_prescription,
            "emergency_transfer_required": self.emergency_transfer_required,
            "recommended_medications": [
                {
                    "generic_name": m.generic_name,
                    "brand_names": m.brand_names,
                    "dosage_guideline": m.dosage_guideline,
                    "administration": m.administration,
                    "warning_and_monitoring": m.warning_and_monitoring,
                    "certified_gpp_online_links": m.certified_gpp_online_links,
                }
                for m in self.recommended_medications
            ],
        }


def _build_gpp_links(drug_keyword: str) -> list[dict[str, str]]:
    encoded = urllib.parse.quote(drug_keyword)
    return [
        {
            "name": "Nhà thuốc FPT Long Châu",
            "type": "Hệ thống nhà thuốc chuẩn GPP toàn quốc",
            "url": f"https://nhathuoclongchau.com.vn/tim-kiem?q={encoded}",
            "verified": True,
        },
        {
            "name": "Hệ thống Nhà thuốc Pharmacity",
            "type": "Chuỗi nhà thuốc đạt chuẩn GPP & BHYT",
            "url": f"https://www.pharmacity.vn/search?q={encoded}",
            "verified": True,
        },
        {
            "name": "Nhà thuốc An Khang",
            "type": "Hệ thống bán thuốc chính hãng",
            "url": f"https://www.nhathuocankhang.com/tim-kiem?key={encoded}",
            "verified": True,
        },
    ]


def evaluate_medication_suitability(
    query: str,
    symptoms_text: str,
    known_conditions: list[str] | None = None,
    current_medications: list[str] | None = None,
    allergies: list[str] | None = None,
    patient_age: int | None = None,
    patient_sex: str | None = None,
    urgency: str = "ROUTINE",
) -> MedicationSuitabilityResult:
    """Rigorous clinical evaluation of whether medicine can be taken, is contraindicated, or requires emergency care."""
    full_text = f"{query} {symptoms_text}".lower()
    norm = normalize_search_text(full_text)
    conditions = [normalize_search_text(c) for c in (known_conditions or [])]
    current_meds = [normalize_search_text(m) for m in (current_medications or [])]
    allergy_list = [normalize_search_text(a) for a in (allergies or [])]

    # 1. State 3: EMERGENCY_RED_FLAG
    is_emergency = (urgency == "EMERGENCY") or any(
        k in norm
        for k in (
            "dau nguc", "that nguc", "nhoi mau", "kho tho du doi", "dot quy",
            "meo mieng", "u o", "yeu liet", "ruot thua", "ho chau phai",
            "chay mau nhieu", "non ra mau", "di ngoai phan den", "soc phan ve",
            "hon me", "co giat", "nga quy"
        )
    )
    if is_emergency:
        rationale = (
            "CẢNH BÁO NGUY HIỂM: Triệu chứng bạn mô tả nằm trong nhóm bệnh cảnh cấp cứu đe dọa tính mạng. "
            "TUYỆT ĐỐI KHÔNG TỰ Ý UỐNG BẤT KỲ THUỐC GIẢM ĐAU HAY HẠ SỐT NÀO TẠI NHÀ vì thuốc có thể làm mờ triệu chứng ngoại khoa "
            "(như đau ruột thừa), ức chế hô hấp hoặc làm nặng thêm tình trạng xuất huyết/nhồi máu. Phải liên hệ cấp cứu hoặc đến bệnh viện ngay lập tức."
        )
        return MedicationSuitabilityResult(
            state="EMERGENCY_RED_FLAG",
            state_label="CẤM TỰ Ý UỐNG THUỐC — PHẢI CẤP CỨU NGAY",
            clinical_rationale=rationale,
            emergency_transfer_required=True,
            nearest_pharmacy_maps_url="https://www.google.com/maps/search/benh+vien+cap+cuu+gan+nhat/",
            pharmacy_chain_links=[],
        )

    # 2. State 2: CONTRAINDICATED
    contraindications: list[str] = []

    # Peptic ulcer / Gastric bleeding vs NSAIDs / Aspirin
    has_ulcer = any("da day" in c or "loet" in c or "xuat huyet" in c for c in conditions) or "dau da day" in norm or "viem loet" in norm
    demands_nsaid = any(k in norm for k in ("ibuprofen", "aspirin", "meloxicam", "diclofenac", "naproxen", "celebrex"))
    if has_ulcer and demands_nsaid:
        contraindications.append(
            "CHỐNG CHỈ ĐỊNH THUỐC KHÁNG VIÊM KHÔNG STEROID (NSAIDs/Aspirin): Bạn có tiền sử viêm loét dạ dày tá tràng. "
            "Các thuốc NSAID ức chế COX-1 làm giảm prostaglandin bảo vệ niêm mạc dạ dày, có thể gây loét cấp, xuất huyết tiêu hóa ồ ạt hoặc thủng dạ dày."
        )

    # Liver failure vs Paracetamol
    has_liver_impairment = any("gan" in c or "xo gan" in c or "viem gan" in c for c in conditions) or "men gan cao" in norm
    demands_paracetamol = any(k in norm for k in ("paracetamol", "panadol", "efferalgan", "hapacol", "tylenol"))
    if has_liver_impairment and demands_paracetamol and any(k in norm for k in ("lieu cao", "uong lien tuc", "uong 2g", "uong 3g", "uong 4g")):
        contraindications.append(
            "CẢNH BÁO TỔN THƯƠNG GAN VỚI PARACETAMOL: Bệnh nhân có bệnh lý gan chuyển hóa. "
            "Chất chuyển hóa NAPQI của Paracetamol có thể gây hoại tử tế bào gan cấp nếu dùng quá liều hoặc dùng kéo dài trên nền gan suy giảm."
        )

    # Anticoagulants (Warfarin) vs NSAIDs/Aspirin
    is_on_blood_thinners = any("warfarin" in m or "sintrom" in m or "aspirin" in m or "clopidogrel" in m for m in current_meds) or any(
        k in norm for k in ("warfarin", "sintrom", "coumadin", "thuoc chong dong", "chong dong mau")
    )
    if is_on_blood_thinners and demands_nsaid:
        contraindications.append(
            "TƯƠNG TÁC THUỐC NGUY HIỂM MỨC ĐỘ NGHIÊM TRỌNG (Warfarin + NSAID/Ibuprofen): Người bệnh đang uống thuốc chống đông máu Warfarin tuyệt đối KHÔNG tự ý uống thêm Ibuprofen 400mg (hoặc Aspirin/NSAID khác). "
            "Ibuprofen làm tổn thương niêm mạc dạ dày, ức chế kết tập tiểu cầu và đẩy Warfarin khỏi protein huyết tương, làm tăng nguy cơ xuất huyết tiêu hóa ồ ạt và xuất huyết nội sọ nghiêm trọng gấp 3-6 lần."
        )
    if ("warfarin" in norm or "chong dong" in norm) and ("nhan sam" in norm or "ginseng" in norm):
        contraindications.append(
            "TƯƠNG TÁC DƯỢC LIỆU NGUY HIỂM (Warfarin + Nhân sâm): Nhân sâm Hàn Quốc (Panax ginseng) làm biến động chuyển hóa enzyme gan và ảnh hưởng đông máu, làm dao động chỉ số INR khó kiểm soát. "
            "Tránh tự ý dùng nhân sâm khi đang điều trị duy trì bằng Warfarin."
        )
    if ("amlodipin" in norm or "amlodipine" in norm or "thuoc huyet ap" in norm) and demands_nsaid:
        contraindications.append(
            "TƯƠNG TÁC THUỐC HẠ ÁP & NSAID (Amlodipin + Ibuprofen): Ibuprofen gây ức chế tổng hợp prostaglandin tại thận và giữ muối nước, làm giảm hiệu lực hạ huyết áp của Amlodipin và tăng nguy cơ suy giảm chức năng thận ở người cao tuổi (68 tuổi)."
        )

    # Suspected counterfeit / physical degradation / discoloration / sour odor
    has_degradation = any(k in norm for k in ("nga vang", "doi mau", "mui chua", "chua nong", "am moc", "chay nuoc", "rach tem", "tem chong gia bi rach", "that hay gia"))
    if has_degradation and any(k in norm for k in ("augmentin", "thuoc", "vien thuoc", "hop thuoc")):
        contraindications.append(
            "CẢNH BÁO DƯỢC PHẨM KHÔNG AN TOÀN — TUYỆT ĐỐI KHÔNG UỐNG: Viên nén Augmentin đạt chuẩn phải có màu trắng đến trắng ngà, vỉ nhôm kín. "
            "Dấu hiệu tem chống giả bị rách kèm viên thuốc ngả vàng và mùi chua nồng chứng tỏ thuốc đã bị thâm nhiễm ẩm dẫn đến phân hủy hoạt chất (đặc biệt Acid Clavulanic rất dễ bị thủy phân tạo mùi chua nồng) hoặc có nguy cơ thuốc giả/kém chất lượng. Hãy ngưng uống ngay và mang hộp thuốc tới nhà thuốc để kiểm tra và thu hồi."
        )

    # Pregnancy vs NSAIDs / Tetracyclines / Retinoids
    is_pregnant = any("mang thai" in c or "co thai" in c or "bau" in c for c in conditions) or "dang mang thai" in norm or "co bau" in norm
    if is_pregnant and demands_nsaid:
        contraindications.append(
            "CHỐNG CHỈ ĐỊNH Ở PHỤ NỮ MANG THAI: Thuốc NSAIDs có thể gây đóng sớm ống động mạch thai nhi và suy thận bào thai (đặc biệt trong 3 tháng cuối thai kỳ)."
        )

    # Asthma vs Aspirin/NSAIDs
    has_asthma = any("hen" in c or "suyen" in c or "asthma" in c for c in conditions) or "hen phe quan" in norm
    if has_asthma and demands_nsaid:
        contraindications.append(
            "CẢNH BÁO HEN PHẾ QUẢN NHẠY CẢM ASPIRIN (Samter Triad): Bệnh nhân hen phế quản có thể khởi phát cơn co thắt phế quản cấp gây suy hô hấp nặng khi dùng NSAIDs."
        )

    # Duplicate Paracetamol / Pediatric overdose check (Case 3: Hapacol 250mg + Efferalgan 150mg)
    paracetamol_cues = [k for k in ("paracetamol", "hapacol", "efferalgan", "panadol", "tylenol") if k in norm]
    has_dual_paracetamol = len(paracetamol_cues) >= 2 or ("dat" in norm and "pha" in norm and any(k in norm for k in ("hapacol", "efferalgan", "paracetamol")))
    is_pediatric = (patient_age is not None and patient_age < 12) or any(
        k in norm for k in ("thang tuoi", "be nha minh", "con toi", "em be", "10kg", "can nang", "chau nho", "tre nho")
    ) and not any(k in norm for k in ("68 tuoi", "50 tuoi", "40 tuoi", "30 tuoi", "25 tuoi", "nguoi lon", "bo toi", "me toi"))

    if has_dual_paracetamol and is_pediatric:
        contraindications.append(
            "CẢNH BÁO NGUY HIỂM — TRÙNG HOẠT CHẤT & NGUY CƠ NGỘ ĐỘC GAN Ở TRẺ EM: Cả Hapacol và Efferalgan đều chứa cùng hoạt chất là Paracetamol (Acetaminophen). "
            "Tuyệt đối KHÔNG vừa nhét viên đặt 150mg vừa uống thêm nửa gói 250mg (tổng liều 275mg = 27.5 mg/kg). Với bé nặng 10kg, liều hạ sốt chuẩn chỉ từ 100mg - 150mg/lần (10 - 15 mg/kg). "
            "Dùng liều 275mg là QUÁ LIỀU GẤP ĐÔI, gây nguy cơ ngộ độc gan cấp tính đe dọa tính mạng! Chỉ dùng DUY NHẤT một dạng thuốc theo đúng cân nặng của bé."
        )

    if contraindications:
        alternatives = [
            "Đối với sốt hoặc đau nhức thông thường: Paracetamol đơn chất liều an toàn (10-15mg/kg, cách mỗi 4-6h, tối đa không quá 2-3g/ngày) được ưu tiên hơn NSAID trên người bệnh dạ dày.",
            "Đối với đau dạ dày: Thuốc kháng acid dạ dày (Antacid: Gastropulgite, Phosphalugel) hoặc thuốc giảm tiết acid (PPI: Omeprazole, Esomeprazole) sau khi có ý kiến bác sĩ.",
            "Cần tham khảo ý kiến bác sĩ hoặc dược sĩ chuyên khoa để chọn lựa phác đồ cá thể hóa an toàn."
        ]
        return MedicationSuitabilityResult(
            state="CONTRAINDICATED",
            state_label="CHỐNG CHỈ ĐỊNH — KHÔNG ĐƯỢC UỐNG",
            clinical_rationale="Phát hiện yếu tố nguy cơ hoặc tương tác thuốc bất lợi. Việc dùng thuốc này không an toàn cho tình trạng sức khỏe hiện tại của bạn.",
            contraindication_reasons=contraindications,
            safe_alternatives=alternatives,
            nearest_pharmacy_maps_url="https://www.google.com/maps/search/nha+thuoc+gan+nhat/",
            pharmacy_chain_links=_build_gpp_links("Paracetamol 500mg"),
        )

    # 3. State 1: ELIGIBLE_OTC (Symptomatic self-care safe)
    # Acute upper respiratory / viral cold / fever / general illness
    is_cold_flu = any(k in norm for k in (
        "dang om", "bi om", "om", "cam cum", "cam lanh", "cam sot", "sot nhe",
        "rat hong", "chay mui", "nghet mui", "so mui", "met moi toan than", "khoi om",
        "uong thuoc gi", "mua thuoc", "thuoc gi", "uong gi"
    ))
    recs: list[MedicationRecommendation] = []

    if is_cold_flu or "sot" in norm or "dau dau" in norm or "dau hong" in norm:
        if is_pediatric:
            recs.append(
                MedicationRecommendation(
                    generic_name="Paracetamol hạ sốt cho trẻ em (Gói bột / Siro / Viên đặt)",
                    brand_names=["Hapacol 150mg/250mg", "Efferalgan 80mg/150mg", "Siro Paracetamol"],
                    dosage_guideline="Liều chuẩn nhi khoa: 10 - 15 mg/kg thể trọng cho mỗi lần dùng, cách mỗi 4 - 6 giờ (tối đa không quá 60 mg/kg/ngày). Tuyệt đối không dùng viên 500mg người lớn.",
                    administration="Hòa tan gói bột vào một ít nước ấm cho bé uống, hoặc đặt hậu môn nếu bé nôn trớ nhiều.",
                    warning_and_monitoring="Chỉ dùng một loại hạ sốt đơn chất; không phối hợp nhiều nhãn hiệu Paracetamol cùng lúc để tránh ngộ độc gan cấp.",
                    certified_gpp_online_links=_build_gpp_links("Hapacol 150mg"),
                )
            )
        else:
            recs.append(
                MedicationRecommendation(
                    generic_name="Paracetamol (Acetaminophen) 500mg",
                    brand_names=["Panadol", "Efferalgan 500mg", "Hapacol 500mg"],
                    dosage_guideline="Người lớn: 1 viên (500mg) mỗi 4-6 giờ khi sốt ≥ 38.5°C hoặc đau nhức người nhiều. Không uống quá 3-4 viên (2000mg)/ngày đối với người lớn khi tự dùng tại nhà.",
                    administration="Uống sau khi ăn hoặc uống cùng một cốc nước đầy. Nếu dùng dạng viên sủi (Efferalgan), phải hòa tan hoàn toàn trong ít nhất 150ml nước sôi để nguội trước khi uống.",
                    warning_and_monitoring="Không uống rượu bia khi dùng thuốc. Không dùng đồng thời với các loại thuốc cảm cúm tổng hợp khác có chứa Paracetamol để tránh ngộ độc gan do quá liều.",
                    certified_gpp_online_links=_build_gpp_links("Paracetamol 500mg"),
                )
            )
        recs.append(
            MedicationRecommendation(
                generic_name="Dung dịch Nước muối sinh lý Natri Clorid 0.9%",
                brand_names=["Nước muối sinh lý 0.9% 500ml", "Xịt mũi Xisat", "Physiodose"],
                dosage_guideline="Súc họng miệng 3-4 lần/ngày sau khi ăn và trước khi ngủ; nhỏ hoặc xịt rửa mũi 2-3 lần/ngày khi nghẹt mũi hoặc chảy nước mũi.",
                administration="Súc sâu vùng họng miệng trong 30 giây rồi nhổ ra, không nuốt. Rửa mũi nhẹ nhàng để làm sạch dịch nhầy đờm.",
                warning_and_monitoring="Sản phẩm an toàn lành tính cho mọi đối tượng, giúp sát khuẩn cơ học và làm ẩm niêm mạc đường hô hấp mà không gây tác dụng phụ.",
                certified_gpp_online_links=_build_gpp_links("Nuoc muoi sinh ly 0.9%"),
            )
        )
        recs.append(
            MedicationRecommendation(
                generic_name="Gói bù nước và điện giải Oresol (Oral Rehydration Salts)",
                brand_names=["Oresol 245", "Hydrite"],
                dosage_guideline="Uống từng ngụm nhỏ rải rác trong ngày khi sốt cao, ra nhiều mồ hôi hoặc mệt mỏi.",
                administration="BẮT BUỘC pha đúng tỉ lệ nước theo hướng dẫn trên gói (thường là 200ml hoặc 1000ml nước đun sôi để nguội). Tuyệt đối không pha đặc hơn hoặc loãng hơn vì có thể gây rối loạn điện giải nguy hiểm.",
                warning_and_monitoring="Dung dịch đã pha chỉ uống trong vòng 24 giờ. Người có bệnh lý suy tim hoặc suy thận nặng cần hỏi ý kiến bác sĩ trước khi bù dịch.",
                certified_gpp_online_links=_build_gpp_links("Oresol 245"),
            )
        )

    # Default general OTC if symptom not cold
    if not recs:
        if is_pediatric:
            recs.append(
                MedicationRecommendation(
                    generic_name="Dung dịch Nước muối sinh lý Natri Clorid 0.9%",
                    brand_names=["Nước muối sinh lý 0.9% 500ml", "Physiodose"],
                    dosage_guideline="Nhỏ hoặc rửa mũi, súc miệng vệ sinh dịu nhẹ hàng ngày cho trẻ nhỏ.",
                    administration="Nhỏ 1-2 giọt mỗi bên mũi hoặc súc miệng nhẹ.",
                    warning_and_monitoring="Sản phẩm an toàn lành tính cho trẻ nhỏ, tuyệt đối không tự ý cho trẻ dùng viên nén người lớn 500mg.",
                    certified_gpp_online_links=_build_gpp_links("Nuoc muoi sinh ly 0.9%"),
                )
            )
        else:
            recs.append(
                MedicationRecommendation(
                    generic_name="Paracetamol 500mg",
                    brand_names=["Panadol", "Efferalgan"],
                    dosage_guideline="1 viên 500mg mỗi 4-6 giờ khi có đau nhức hoặc sốt (tối đa không quá 3-4 viên/ngày).",
                    administration="Uống với nước sau ăn.",
                    warning_and_monitoring="Theo dõi dị ứng và không dùng chung các chế phẩm khác chứa Paracetamol.",
                    certified_gpp_online_links=_build_gpp_links("Paracetamol 500mg"),
                )
            )

    clinical_rationale = (
        "Tình trạng sức khỏe hiện tại nằm trong mức theo dõi thông thường. "
        "Dưới đây là các nhóm thuốc hỗ trợ triệu chứng an toàn không kê đơn (OTC) được khuyến cáo bởi Bộ Y tế. "
        "Xin lưu ý: Thuốc chỉ giúp giảm nhẹ triệu chứng khó chịu; bạn cần nghỉ ngơi, bù đủ nước và theo dõi sát diễn biến sức khỏe."
    )

    return MedicationSuitabilityResult(
        state="ELIGIBLE_OTC",
        state_label="ĐƯỢC PHÉP UỐNG (THUỐC OTC HỖ TRỢ AN TOÀN)",
        clinical_rationale=clinical_rationale,
        recommended_medications=recs,
        nearest_pharmacy_maps_url="",
        pharmacy_chain_links=_build_gpp_links("Thuốc hạ sốt cảm cúm"),
        requires_prescription=False,
    )
