import json
import re
import time
from datetime import datetime
from typing import Any
from app.core.database import db_manager
from app.models.health_twin import (
    FutureRiskPrognosis,
    OrganCoordinates,
    OrganStatus,
    PatientHealthProfile,
    RecoveryTimelinePoint,
    SafeGuardrailAlert,
    VitalSignsSummary,
)


def _get_default_organs() -> list[OrganStatus]:
    return [
        OrganStatus(
            id="head",
            name="Head & Brain",
            vietnamese_name="Đầu & Thần kinh",
            status="monitoring",
            health_score=75,
            pain_level=4,
            inflammation_level="mild",
            symptoms=["Đau đầu căng thẳng", "Nặng trán"],
            clinical_notes="Ghi nhận đau âm ỉ vùng trán và thái dương do cảm cúm đường hô hấp trên.",
            related_medications=["Paracetamol 500mg"],
            coordinates=OrganCoordinates(x=50.0, y=11.0),
            future_risk=FutureRiskPrognosis(
                risk_level="low",
                risk_title="Rủi ro Đau đầu mạn tính do lạm dụng thuốc giảm đau (MOH)",
                timeframe="1 - 2 năm",
                vaccination_status="THẦN KINH: Chưa ghi nhận tổn thương thực thể",
                latent_risk_description="Đau đầu hiện tại do đáp ứng sốt virus. Nguy cơ hình thành thói quen phụ thuộc thuốc giảm đau cấp nếu dùng Paracetamol liên tục trên 15 ngày/tháng.",
                potential_progression="Đau đầu cấp tính -> Lạm dụng thuốc giảm đau tự do -> Đau đầu dội ngược kháng trị (Medication-Overuse Headache).",
                preventive_recommendations=[
                    "Không uống thuốc giảm đau quá 3-4 ngày liên tục mà không có chỉ định bác sĩ.",
                    "Đảm bảo ngủ đủ 7-8 tiếng, hạn chế nhìn màn hình xanh quá 2 giờ liên tục khi đang sốt.",
                    "Bổ sung Magie và Vitamin B2 để hỗ trợ ổn định dẫn truyền thần kinh.",
                ],
                screening_tests=[
                    "Ghi chép nhật ký cơn đau đầu (Headache Diary)",
                    "Khám chuyên khoa thần kinh nếu xuất hiện dấu hiệu cờ đỏ (nôn vọt, cứng gáy)",
                ],
            ),
        ),
        OrganStatus(
            id="ent",
            name="Ear, Nose & Throat",
            vietnamese_name="Tai Mũi Họng",
            status="inflamed",
            health_score=65,
            pain_level=3,
            inflammation_level="moderate",
            symptoms=["Sổ mũi nước trong", "Nghẹt mũi nhẹ", "Rát họng"],
            clinical_notes="Phù nề niêm mạc mũi họng do virus cảm cúm.",
            related_medications=["Xịt mũi nước muối biển", "Súc họng NaCl 0.9%"],
            coordinates=OrganCoordinates(x=50.0, y=18.0),
            future_risk=FutureRiskPrognosis(
                risk_level="moderate",
                risk_title="Rủi ro Viêm xoang mạn tính & Viêm họng hạt tái diễn",
                timeframe="1 - 2 năm",
                vaccination_status="ĐƯỜNG THỞ TRÊN: Đang viêm cấp tính do virus cúm",
                latent_risk_description="Niêm mạc cuốn mũi đang xung huyết phù nề. Nếu ứ đọng dịch nhầy kéo dài dễ dẫn đến bội nhiễm vi khuẩn cơ hội tại các xoang cạnh mũi.",
                potential_progression="Viêm mũi họng cấp tính -> Tắc lỗ thông xoang -> Viêm xoang sàng/hàm mạn tính hoặc Viêm amiđan hốc mủ.",
                preventive_recommendations=[
                    "Rửa mũi bằng dung dịch nước muối sinh lý đẳng trương ấm 2-3 lần/ngày.",
                    "Súc họng sâu với nước muối hoặc dung dịch Povidone Iodine 1% khi ra ngoài về.",
                    "Giữ ấm vùng cổ ngực, uống nhiều nước ấm để làm loãng dịch đờm.",
                ],
                screening_tests=[
                    "Nội soi Tai Mũi Họng ống mềm định kỳ nếu triệu chứng kéo dài > 10 ngày",
                    "Chụp CT xoang liều thấp khi nghi ngờ viêm xoang tắc nghẽn",
                ],
            ),
        ),
        OrganStatus(
            id="cardiovascular",
            name="Cardiovascular",
            vietnamese_name="Tim mạch & Tuần hoàn",
            status="normal",
            health_score=95,
            pain_level=0,
            inflammation_level="none",
            symptoms=[],
            clinical_notes="Chức năng tim mạch và tuần hoàn bình thường. Chưa ghi nhận triệu chứng bất thường.",
            related_medications=[],
            coordinates=OrganCoordinates(x=52.0, y=28.5),
            future_risk=FutureRiskPrognosis(
                risk_level="moderate",
                risk_title="Rủi ro Xơ vữa mạch vành & Biến cố Tim mạch (Thang SCORE/Framingham)",
                timeframe="5 - 10 năm",
                vaccination_status="TIÊM PHÒNG CÚM HÀNG NĂM: Cần tiêm nhắc để ngừa biến cố tim mạch",
                latent_risk_description="Huyết áp 120-122 mmHg ngưỡng tiền tăng huyết áp. Thói quen ngồi nhiều kết hợp áp lực công việc làm tăng stress oxy hóa thành mạch.",
                potential_progression="Rối loạn chức năng nội mạc động mạch -> Lắng đọng mảng xơ vữa thành mạch vành -> Cơn đau thắt ngực hoặc Nhồi máu cơ tim cấp.",
                preventive_recommendations=[
                    "Duy trì huyết áp mục tiêu < 120/80 mmHg, kiểm soát lượng muối ăn < 5g/ngày.",
                    "Vận động thể thao nhịp điệu (đi bộ nhanh, bơi lội, đạp xe) tối thiểu 150 phút/tuần.",
                    "Tiêm phòng vắc-xin Cúm mùa định kỳ hàng năm (giúp giảm 20-30% nguy cơ biến cố tim mạch).",
                ],
                screening_tests=[
                    "Điện tâm đồ (ECG 12 chuyển đạo) & Siêu âm tim Doppler định kỳ hàng năm",
                    "Xét nghiệm bộ mỡ máu Lipid panel (Cholesterol toàn phần, LDL-C, HDL-C, Triglyceride)",
                ],
            ),
        ),
        OrganStatus(
            id="lungs",
            name="Respiratory & Lungs",
            vietnamese_name="Phổi & Hô hấp",
            status="monitoring",
            health_score=85,
            pain_level=1,
            inflammation_level="mild",
            symptoms=["Thỉnh thoảng húng hắng ho nhẹ"],
            clinical_notes="SpO2 98%, phế bào êm, không ran, đường thở dưới thông thoáng.",
            related_medications=[],
            coordinates=OrganCoordinates(x=43.5, y=28.0),
            future_risk=FutureRiskPrognosis(
                risk_level="moderate",
                risk_title="Rủi ro Viêm phế quản mạn & Tăng phản ứng phế quản",
                timeframe="2 - 5 năm",
                vaccination_status="VẮC-XIN PHẾ CẦU: Chưa tiêm phòng vắc-xin Phế cầu (Prevenar 13 / Pneumovax 23)",
                latent_risk_description="Đường thở trên đang viêm virus. Nếu thường xuyên tiếp xúc khói bụi hoặc thời tiết lạnh mà chưa có kháng thể phế cầu khuẩn sẽ dễ bị viêm phổi thứ phát.",
                potential_progression="Nhiễm virus hô hấp tái diễn -> Tổn thương biểu mô lông chuyển -> Viêm phế quản mạn tính & Giảm dung tích sống FEV1.",
                preventive_recommendations=[
                    "Tiêm phòng vắc-xin ngừa phế cầu khuẩn (Streptococcus pneumoniae) để bảo vệ phế nang.",
                    "Đeo khẩu trang chuẩn lọc bụi mịn N95 khi di chuyển ngoài đường phố đô thị.",
                    "Tránh hoàn toàn khói thuốc lá thụ động và các chất khí độc hại.",
                ],
                screening_tests=[
                    "Đo chức năng hô hấp (Hô hấp ký Spirometry)",
                    "Chụp X-quang phổi thẳng định kỳ 1-2 năm/lần",
                ],
            ),
        ),
        OrganStatus(
            id="stomach",
            name="Gastrointestinal & Stomach",
            vietnamese_name="Dạ dày & Tiêu hoá",
            status="normal",
            health_score=92,
            pain_level=0,
            inflammation_level="none",
            symptoms=[],
            clinical_notes="Bụng mềm, không chướng, tiêu hóa bình thường. Cần lưu ý uống thuốc sau ăn.",
            related_medications=[],
            coordinates=OrganCoordinates(x=53.5, y=36.5),
            future_risk=FutureRiskPrognosis(
                risk_level="high",
                risk_title="Rủi ro Viêm loét dạ dày tá tràng thủng & Biến chứng Ung thư dạ dày",
                timeframe="1 - 3 năm",
                vaccination_status="TẦM SOÁT KHUẨN HP: Chưa kiểm tra vi khuẩn Helicobacter pylori",
                latent_risk_description="Dạ dày rất dễ bị tổn thương nếu lạm dụng thuốc kháng viêm giảm đau (NSAID) hoặc nhiễm vi khuẩn HP âm thầm mà không phát hiện sớm.",
                potential_progression="Kích ứng niêm mạc cấp -> Ổ loét sâu thành dạ dày xuất huyết/thủng -> Viêm teo niêm mạc mạn tính & Dị sản ruột -> Nguy cơ Ung thư dạ dày.",
                preventive_recommendations=[
                    "Tuyệt đối không uống thuốc giảm đau chống viêm khi đói; dừng ngay nếu thấy cồn cào đau thượng vị.",
                    "Xét nghiệm test thở hoặc nội soi tầm soát vi khuẩn Helicobacter pylori (HP).",
                    "Ăn uống đúng giờ, tránh thói quen ăn đồ quá cay nóng, nhiều muối hoặc thực phẩm muối chua.",
                ],
                screening_tests=[
                    "Nội soi thực quản - dạ dày - tá tràng (EGD) có tiền mê",
                    "Test hơi thở C13/C14 Urea Breath Test tìm vi khuẩn HP",
                ],
            ),
        ),
        OrganStatus(
            id="liver",
            name="Liver & Metabolism",
            vietnamese_name="Gan & Chuyển hoá",
            status="normal",
            health_score=96,
            pain_level=0,
            inflammation_level="none",
            symptoms=[],
            clinical_notes="Chức năng chuyển hóa ổn định. Chú ý không dùng Paracetamol quá 3000mg/24h.",
            related_medications=[],
            coordinates=OrganCoordinates(x=43.5, y=35.0),
            future_risk=FutureRiskPrognosis(
                risk_level="high",
                risk_title="Nguy cơ Nhiễm HBV mạn tính, Xơ gan tiến triển & Ung thư gan (HCC)",
                timeframe="3 - 10 năm",
                vaccination_status="CHƯA TIÊM PHÒNG: Chưa tiêm vắc-xin Viêm gan B (Kháng thể Anti-HBs âm tính)",
                latent_risk_description="Cơ thể chưa có kháng thể bảo vệ trước virus Viêm gan B (HBV). Nếu phơi nhiễm nguồn lây qua máu, dịch tiết, thủ thuật y tế hoặc tiếp xúc cộng đồng, nguy cơ chuyển thành thể mạn tính chiếm tới 10-15%.",
                potential_progression="Nhiễm HBV mạn tính âm thầm -> Viêm hoại tử tế bào gan -> Xơ gan tiến triển (Cirrhosis) -> Đột biến gen tế bào gan dẫn đến Ung thư biểu mô tế bào gan (Hepatocellular Carcinoma - HCC) sau 5-10 năm.",
                preventive_recommendations=[
                    "Thực hiện tiêm phòng vắc-xin Viêm gan B đủ phác đồ chuẩn 3 mũi (Tháng 0, 1, 6) càng sớm càng tốt.",
                    "Xét nghiệm kiểm tra lại hiệu giá kháng thể Anti-HBs sau mũi 3 đạt > 10 mIU/mL để đảm bảo miễn dịch.",
                    "Hạn chế tối đa rượu bia, không dùng Paracetamol quá liều (> 3000mg/ngày) để giảm tải giải độc cho tế bào gan.",
                ],
                screening_tests=[
                    "Xét nghiệm cặp HBsAg & Anti-HBs kiểm tra tình trạng nhiễm và kháng thể",
                    "Định lượng men gan (AST, ALT, GGT) và chức năng gan tổng quát",
                    "Siêu âm Doppler gan & Xét nghiệm chỉ dấu sinh học ung thư gan Alpha-fetoprotein (AFP) mỗi 6 tháng",
                ],
            ),
        ),
        OrganStatus(
            id="kidneys",
            name="Kidneys & Urinary",
            vietnamese_name="Thận & Tiết niệu",
            status="normal",
            health_score=98,
            pain_level=0,
            inflammation_level="none",
            symptoms=[],
            clinical_notes="Đào thải bình thường, duy trì uống đủ 2 lít nước ấm mỗi ngày.",
            related_medications=[],
            coordinates=OrganCoordinates(x=44.5, y=40.5),
            future_risk=FutureRiskPrognosis(
                risk_level="low",
                risk_title="Rủi ro Suy giảm mức lọc cầu thận & Bệnh thận do thuốc",
                timeframe="3 - 5 năm",
                vaccination_status="CHỨC NĂNG THẬN: Ổn định, không protein niệu",
                latent_risk_description="Thận đóng vai trò đào thải chất chuyển hóa của thuốc. Nguy cơ tổn thương mô kẽ thận nếu dùng thuốc giảm đau liều cao kéo dài hoặc cơ thể thiếu nước.",
                potential_progression="Tổn thương tế bào ống thận âm thầm nếu lạm dụng thuốc kéo dài -> Giảm mức lọc cầu thận (eGFR) -> Bệnh thận mạn giai đoạn sớm.",
                preventive_recommendations=[
                    "Duy trì thói quen uống đủ 2 - 2.5 lít nước ấm mỗi ngày để bảo vệ chức năng bài tiết cầu thận.",
                    "Tuyệt đối không tự ý phối hợp nhiều loại thuốc hạ sốt giảm đau cùng lúc mà không có ý kiến bác sĩ.",
                ],
                screening_tests=[
                    "Xét nghiệm Creatinine huyết thanh & Ước tính mức lọc cầu thận eGFR",
                    "Tổng phân tích nước tiểu 10 thông số định kỳ hàng năm",
                ],
            ),
        ),
        OrganStatus(
            id="spine_joints",
            name="Spine & Musculoskeletal",
            vietnamese_name="Cơ xương khớp & Cột sống",
            status="monitoring",
            health_score=80,
            pain_level=2,
            inflammation_level="mild",
            symptoms=["Hơi mỏi người do sốt"],
            clinical_notes="Mỏi cơ nhẹ toàn thân điển hình trong hội chứng cúm.",
            related_medications=[],
            coordinates=OrganCoordinates(x=50.0, y=43.5),
            future_risk=FutureRiskPrognosis(
                risk_level="low",
                risk_title="Rủi ro Thoái hóa cột sống cổ - thắt lưng & Co cứng cơ mạn tính",
                timeframe="3 - 5 năm",
                vaccination_status="VẬN ĐỘNG HỌC: Cần cải thiện tư thế công thái học",
                latent_risk_description="Triệu chứng mỏi cơ hiện tại do phản ứng viêm với sốt, kết hợp thói quen làm việc văn phòng ngồi nhiều giờ liên tục ít thay đổi tư thế.",
                potential_progression="Căng cơ cổ vai gáy và thắt lưng mạn tính -> Giảm chiều cao đĩa đệm -> Thoái hóa cột sống & Thoát vị đĩa đệm sớm.",
                preventive_recommendations=[
                    "Thực hiện bài tập giãn cơ 5 phút sau mỗi 45-60 phút ngồi làm việc máy tính.",
                    "Điều chỉnh ghế và màn hình máy tính theo chuẩn công thái học (Ergonomics).",
                    "Bổ sung Canxi và Vitamin D3 qua thực phẩm hoặc tắm nắng buổi sớm.",
                ],
                screening_tests=[
                    "Khám chuyên khoa Cơ Xương Khớp & Đánh giá biên độ vận động cột sống",
                ],
            ),
        ),
        OrganStatus(
            id="skin",
            name="Skin & Immune System",
            vietnamese_name="Da liễu & Hệ miễn dịch",
            status="normal",
            health_score=95,
            pain_level=0,
            inflammation_level="none",
            symptoms=[],
            clinical_notes="Da ấm, không phát ban, không nổi mề đay dị ứng thuốc.",
            related_medications=[],
            coordinates=OrganCoordinates(x=32.5, y=33.5),
            future_risk=FutureRiskPrognosis(
                risk_level="low",
                risk_title="Rủi ro Dị ứng thuốc phản vệ & Lão hóa quang hóa do tia UV",
                timeframe="2 - 5 năm",
                vaccination_status="MIỄN DỊCH HỌC: Đang đáp ứng bảo vệ bình thường",
                latent_risk_description="Hệ miễn dịch đang tập trung sản xuất kháng thể chống virus cảm cúm. Cần lưu ý theo dõi các biểu hiện dị ứng nổi mề đay nếu đổi thuốc mới.",
                potential_progression="Dị ứng thuốc nhẹ không nhận biết -> Tái sử dụng thuốc dẫn đến phản ứng quá mẫn typ I hoặc hội chứng Stevens-Johnson nghiêm trọng.",
                preventive_recommendations=[
                    "Thông báo ngay cho bác sĩ nếu từng có tiền sử dị ứng với bất kỳ loại kháng sinh hoặc thuốc giảm đau nào.",
                    "Sử dụng kem chống nắng SPF 50+ phổ rộng khi hoạt động ngoài trời để bảo vệ màng tế bào biểu bì.",
                ],
                screening_tests=[
                    "Test áp bì hoặc định lượng IgE đặc hiệu nếu có tiền sử dị ứng thuốc nghi ngờ",
                ],
            ),
        ),
    ]


def _get_healthy_organs() -> list[OrganStatus]:
    organs = _get_default_organs()
    for organ in organs:
        organ.status = "normal"
        organ.health_score = 100
        organ.pain_level = 0
        organ.inflammation_level = "none"
        organ.symptoms = []
        organ.clinical_notes = "Chức năng bình thường, chỉ số tối ưu."
        organ.warning = None
        organ.is_adverse_reaction = False
        organ.contraindicated_actions = []
    return organs


def _get_unassessed_organs() -> list[OrganStatus]:
    organs = _get_default_organs()
    for organ in organs:
        organ.status = "unassessed"
        organ.health_score = 0
        organ.pain_level = 0
        organ.inflammation_level = "none"
        organ.symptoms = []
        organ.clinical_notes = "Chưa có dữ liệu khám lâm sàng. Cần trò chuyện với Bác sĩ AI hoặc cập nhật chỉ số để phân tích thể trạng."
        organ.warning = None
        organ.is_adverse_reaction = False
        organ.contraindicated_actions = []
        organ.future_risk = None
    return organs


class PatientHealthTwinService:
    """Manages the interactive anatomical health twin, recovery timeline,
    and clinical safety guardrails for patient episodes with TiDB persistence."""

    def __init__(self) -> None:
        now_str = datetime.now().strftime("%H:%M %d/%m/%Y")
        self._fallback_profile: PatientHealthProfile = self._build_unassessed_profile(now_str)

    def _load_or_create_user_profile(self, user_id: str, tenant_id: str = "system") -> PatientHealthProfile:
        try:
            with db_manager.tenant_context(tenant_id) as session:
                rows = session.execute(
                    "SELECT * FROM medguard_health_twins WHERE user_id = ? LIMIT 1",
                    (user_id,),
                )
                if rows:
                    r = rows[0]
                    try:
                        organs_data = json.loads(r["organs_json"]) if r.get("organs_json") else []
                        vitals_data = json.loads(r["vitals_json"]) if r.get("vitals_json") else {}
                        timeline_data = json.loads(r["timeline_json"]) if r.get("timeline_json") else []
                        active_meds = json.loads(r["active_medications_json"]) if r.get("active_medications_json") else []
                        disc_meds = json.loads(r["discontinued_medications_json"]) if r.get("discontinued_medications_json") else []
                        directives = json.loads(r["clinical_directives_json"]) if r.get("clinical_directives_json") else []
                        guardrail = json.loads(r["safe_guardrail_alert_json"]) if r.get("safe_guardrail_alert_json") else None

                        organs = [OrganStatus.model_validate(o) for o in organs_data] if organs_data else _get_unassessed_organs()
                        vitals = VitalSignsSummary(**vitals_data) if vitals_data else VitalSignsSummary()
                        timeline = [RecoveryTimelinePoint.model_validate(t) for t in timeline_data] if timeline_data else []
                        alert = SafeGuardrailAlert.model_validate(guardrail) if guardrail else None

                        patient_name = user_id
                        age = None
                        gender = None
                        try:
                            from app.services.user_data_store import user_data_store
                            u_prof = user_data_store.get_user_profile(tenant_id, user_id)
                            if u_prof:
                                patient_name = u_prof.get("name") or u_prof.get("full_name") or user_id
                                age = u_prof.get("age")
                                gender = u_prof.get("gender")
                        except Exception:
                            pass

                        return PatientHealthProfile(
                            patient_id=user_id,
                            patient_name=patient_name,
                            age=age,
                            gender=gender,
                            overall_health_score=int(r.get("overall_health_score", 0)),
                            health_trend=r.get("health_trend", "unassessed"),
                            active_diagnosis=r.get("active_diagnosis", "Chưa có dữ liệu đánh giá lâm sàng — Chờ thu thập triệu chứng"),
                            vitals=vitals,
                            organs=organs,
                            active_medications=active_meds,
                            discontinued_medications=disc_meds,
                            clinical_directives=directives,
                            safe_guardrail_alert=alert,
                            timeline=timeline,
                        )
                    except Exception as exc:
                        print(f"[HealthTwin] Error parsing profile for {user_id}: {exc}")
        except Exception as e:
            print(f"[HealthTwin] DB lookup warning for {user_id}: {e}")

        # If not in DB, create initial clean unassessed baseline for this user and persist
        now_str = datetime.now().strftime("%H:%M %d/%m/%Y")
        clean_profile = self._build_unassessed_profile(now_str)
        clean_profile.patient_id = user_id
        try:
            from app.services.user_data_store import user_data_store
            u_prof = user_data_store.get_user_profile(tenant_id, user_id)
            if u_prof:
                clean_profile.patient_name = u_prof.get("name") or u_prof.get("full_name") or user_id
                clean_profile.age = u_prof.get("age")
                clean_profile.gender = u_prof.get("gender")
        except Exception:
            pass
        try:
            self._save_user_profile(user_id, clean_profile, tenant_id)
        except Exception:
            pass
        return clean_profile

    def _save_user_profile(self, user_id: str, profile: PatientHealthProfile, tenant_id: str = "system") -> None:
        now = time.time()
        organs_json = json.dumps([o.model_dump(mode="json") for o in profile.organs], ensure_ascii=False)
        vitals_json = json.dumps(profile.vitals.model_dump(mode="json"), ensure_ascii=False)
        timeline_json = json.dumps([t.model_dump(mode="json") for t in profile.timeline[-15:]], ensure_ascii=False)
        active_meds_json = json.dumps(profile.active_medications, ensure_ascii=False)
        disc_meds_json = json.dumps(profile.discontinued_medications, ensure_ascii=False)
        contra_json = json.dumps(profile.contraindicated_regimens, ensure_ascii=False)
        directives_json = json.dumps(profile.clinical_directives, ensure_ascii=False)
        alert_json = json.dumps(profile.safe_guardrail_alert.model_dump(mode="json") if profile.safe_guardrail_alert else None, ensure_ascii=False)

        try:
            with db_manager.tenant_context(tenant_id) as session:
                if session.dialect in ("mysql", "tidb"):
                    session.execute(
                        """
                        INSERT INTO medguard_health_twins (
                            user_id, overall_health_score, health_trend, active_diagnosis,
                            vitals_json, organs_json, active_medications_json,
                            discontinued_medications_json, contraindicated_regimens_json,
                            clinical_directives_json, safe_guardrail_alert_json,
                            timeline_json, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            overall_health_score = VALUES(overall_health_score),
                            health_trend = VALUES(health_trend),
                            active_diagnosis = VALUES(active_diagnosis),
                            vitals_json = VALUES(vitals_json),
                            organs_json = VALUES(organs_json),
                            active_medications_json = VALUES(active_medications_json),
                            discontinued_medications_json = VALUES(discontinued_medications_json),
                            contraindicated_regimens_json = VALUES(contraindicated_regimens_json),
                            clinical_directives_json = VALUES(clinical_directives_json),
                            safe_guardrail_alert_json = VALUES(safe_guardrail_alert_json),
                            timeline_json = VALUES(timeline_json),
                            updated_at = VALUES(updated_at)
                        """,
                        (
                            user_id,
                            profile.overall_health_score,
                            profile.health_trend,
                            profile.active_diagnosis,
                            vitals_json,
                            organs_json,
                            active_meds_json,
                            disc_meds_json,
                            contra_json,
                            directives_json,
                            alert_json,
                            timeline_json,
                            now,
                        ),
                    )
                else:
                    session.execute(
                        """
                        INSERT INTO medguard_health_twins (
                            user_id, overall_health_score, health_trend, active_diagnosis,
                            vitals_json, organs_json, active_medications_json,
                            discontinued_medications_json, contraindicated_regimens_json,
                            clinical_directives_json, safe_guardrail_alert_json,
                            timeline_json, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT (user_id) DO UPDATE SET
                            overall_health_score = excluded.overall_health_score,
                            health_trend = excluded.health_trend,
                            active_diagnosis = excluded.active_diagnosis,
                            vitals_json = excluded.vitals_json,
                            organs_json = excluded.organs_json,
                            active_medications_json = excluded.active_medications_json,
                            discontinued_medications_json = excluded.discontinued_medications_json,
                            contraindicated_regimens_json = excluded.contraindicated_regimens_json,
                            clinical_directives_json = excluded.clinical_directives_json,
                            safe_guardrail_alert_json = excluded.safe_guardrail_alert_json,
                            timeline_json = excluded.timeline_json,
                            updated_at = excluded.updated_at
                        """,
                        (
                            user_id,
                            profile.overall_health_score,
                            profile.health_trend,
                            profile.active_diagnosis,
                            vitals_json,
                            organs_json,
                            active_meds_json,
                            disc_meds_json,
                            contra_json,
                            directives_json,
                            alert_json,
                            timeline_json,
                            now,
                        ),
                    )
        except Exception as exc:
            print(f"[HealthTwin] Error saving profile for {user_id}: {exc}")

    def get_profile(self, user_id: str = "default", tenant_id: str = "system") -> PatientHealthProfile:
        return self._load_or_create_user_profile(user_id, tenant_id)

    def reset_profile(self, user_id: str = "default", tenant_id: str = "system") -> PatientHealthProfile:
        now_str = datetime.now().strftime("%H:%M %d/%m/%Y")
        new_profile = self._build_healthy_profile(now_str)
        new_profile.patient_id = user_id
        self._save_user_profile(user_id, new_profile, tenant_id)
        return new_profile

    def switch_scenario(self, scenario_id: str, user_id: str = "default", tenant_id: str = "system") -> PatientHealthProfile:
        now_str = datetime.now().strftime("%H:%M %d/%m/%Y")
        if scenario_id == "initial_flu":
            p = self._build_default_flu_profile()
        elif scenario_id == "recovered_headache":
            p = self._build_recovered_profile(now_str)
        elif scenario_id == "adr_stomach_nsaid":
            p = self._build_adr_stomach_profile(now_str)
        elif scenario_id == "severe_fever_progression":
            p = self._build_severe_progression_profile(now_str)
        elif scenario_id == "healthy_baseline":
            p = self._build_healthy_profile(now_str)
        else:
            p = self._build_healthy_profile(now_str)
        p.patient_id = user_id
        self._save_user_profile(user_id, p, tenant_id)
        return p

    def evaluate_progress(
        self,
        message: str,
        current_medications: list[str] | None = None,
        vital_updates: dict[str, Any] | None = None,
        user_id: str = "default",
        tenant_id: str = "system",
    ) -> dict[str, Any]:
        """Analyzes patient's latest update, adjusts anatomical organ status,
        updates overall health score, and enforces AI safety directives."""
        norm = message.lower().strip()
        now_str = datetime.now().strftime("%H:%M %d/%m/%Y")
        profile = self._load_or_create_user_profile(user_id, tenant_id)

        # Strip negated symptom clauses to avoid false triggers
        norm_no_neg = re.sub(
            r"\b(không|chẳng|chưa|hết|đã hết|ko)\s+(?:hề\s+|còn\s+)?(?:bị\s+|có\s+|thấy\s+)?(đau\s+đầu|nhức\s+đầu|đau\s+dạ\s+dày|đau\s+bao\s+tử|đau\s+bụng|cồn\s+cào|buồn\s+nôn|nôn|rát\s+thượng\s+vị|ợ\s+chua|ợ\s+hơi|đầy\s+bụng|khó\s+tiêu|trào\s+ngược|viêm\s+dạ\s+dày|sốt|ho|khó\s+thở|đau\s+khớp|mỏi\s+mắt|đau\s+ngực)\b",
            " ",
            norm,
        )

        # 1. Detect Improvement / Recovery
        # E.g., "hết đau đầu", "hết sổ mũi", "hết sốt", "khỏe hơn", "khỏi bệnh", "đỡ nhiều", "hoàn toàn khỏe mạnh"
        recovery_patterns = [
            r"hết\s*(đau đầu|nhức đầu|sổ mũi|nghẹt mũi|sốt|rát họng|ho|đau dạ dày|bệnh)",
            r"không còn\s*(sốt|đau đầu|sổ mũi|mệt|đau)",
            r"(đỡ|khỏi|bớt)\s*(hẳn|nhiều|rồi|bệnh)",
            r"khỏe hơn\s*(nhiều|rồi)",
            r"(?:hoàn toàn\s+)?(?:khỏe mạnh|bình thường|rất khỏe)",
            r"không\s+(?:hề\s+)?(?:bị\s+)?(?:đau|sốt|ho|bệnh|mệt)",
            r"hoàn\s+toàn\s+khỏe",
        ]
        is_recovery = any(re.search(pat, norm) for pat in recovery_patterns)

        # 2. Detect Deterioration / Adverse Drug Reaction (ADR)
        # Scan on norm_no_neg to prevent "không đau dạ dày" from falsely triggering ADR!
        adr_stomach_patterns = [
            r"(uống thuốc|dùng thuốc|sau khi uống).*?(đau dạ dày|đau bao tử|đau bụng|cồn cào|buồn nôn|nôn|rát thượng vị)",
            r"(đau dạ dày|đau bao tử|rát thượng vị|cồn cào).*?(dữ dội|nặng hơn|sau khi uống)",
            r"(đau bụng|nôn nao|buồn nôn)\s*(nhiều|hơn|dữ)",
        ]
        is_adr_stomach = any(re.search(pat, norm_no_neg) for pat in adr_stomach_patterns)

        # 3. Detect Allergic Reaction / Rash
        allergy_patterns = [
            r"(nổi mẩn|phát ban|mày đay|ngứa ngáy|sưng môi|phù mặt|khó thở dị ứng)",
        ]
        is_allergy = any(re.search(pat, norm_no_neg) for pat in allergy_patterns)

        # 4. Detect Severe Disease Escalation
        escalation_patterns = [
            r"(sốt cao hơn|sốt 39|sốt 40|rét run|khó thở dữ dội|đau ngực dữ dội|co giật)",
            r"(nặng hơn|không thở được|mệt lả|li bì)",
        ]
        is_escalation = any(re.search(pat, norm) for pat in escalation_patterns)

        detected_event = "inquiry"
        ai_analysis = ""
        action_plan = ""
        must_discontinue = False
        discontinued_items: list[str] = []

        if is_adr_stomach:
            detected_event = "adverse_reaction"
            must_discontinue = True
            discontinued_items = ["Thuốc kháng viêm giảm đau (NSAID nghi ngờ)"]
            ai_analysis = (
                "AI MedGuard phát hiện dấu hiệu Phản ứng Bất lợi của Thuốc (ADR): Kích ứng và tổn thương niêm mạc "
                "dạ dày - thượng vị do dùng thuốc giảm đau/kháng viêm (NSAID). "
                "Cần ngưng ngay lập tức để ngăn ngừa nguy cơ xuất huyết tiêu hóa."
            )
            action_plan = (
                "1. HẠN CHẾ VÀ NGỪNG NGAY thuốc giảm đau NSAID đang dùng.\n"
                "2. Chuyển sang biện pháp hỗ trợ: Uống nước ấm, dùng thuốc bảo vệ niêm mạc dạ dày (antacid/PPI) nếu có chỉ định.\n"
                "3. Tuyệt đối không để bụng đói khi uống bất kỳ loại thuốc nào.\n"
                "4. Khám chuyên khoa tiêu hóa ngay nếu xuất hiện nôn mửa dữ dội hoặc đi ngoài phân đen."
            )
            # Apply changes to profile
            profile = self._apply_adr_stomach_to_profile(profile, now_str, message)

        elif is_allergy:
            detected_event = "adverse_reaction"
            must_discontinue = True
            discontinued_items = ["Toàn bộ kháng sinh / thuốc mới uống gần nhất"]
            ai_analysis = (
                "AI MedGuard phát hiện dấu hiệu dị ứng thuốc cấp: Nổi mẩn, ngứa, phát ban trên da. "
                "Nguy cơ tiến triển phản vệ nếu tiếp tục sử dụng."
            )
            action_plan = (
                "1. NGỪNG NGAY LẬP TỨC loại thuốc mới uống.\n"
                "2. Uống nhiều nước, theo dõi sát đường thở.\n"
                "3. Nếu xuất hiện sưng mắt/môi hoặc cảm giác nghẹn thở, gọi cấp cứu 115 ngay lập tức."
            )
            profile = self._apply_allergy_to_profile(profile, now_str, message)

        elif is_escalation:
            detected_event = "deterioration"
            ai_analysis = (
                "AI MedGuard phát hiện dấu hiệu bệnh tiến triển tăng nặng (sốt cao kịch phát hoặc suy giảm hô hấp). "
                "Cách chăm sóc tại nhà hiện tại không còn đủ an toàn, cần can thiệp y tế chuyên sâu."
            )
            action_plan = (
                "1. Không tiếp tục tự điều trị tại nhà với liều thông thường.\n"
                "2. Chườm ấm hạ sốt và khẩn trương di chuyển đến bệnh viện hoặc phòng khám gần nhất.\n"
                "3. Sẵn sàng gọi xe cứu thương 115 nếu có khó thở hoặc lơ mơ."
            )
            profile = self._apply_escalation_to_profile(profile, now_str, message)

        elif is_recovery:
            detected_event = "recovery"
            ai_analysis = (
                "AI MedGuard ghi nhận sự thuyên giảm triệu chứng rõ rệt: Bệnh nhân hết đau đầu, sổ mũi, "
                "thân nhiệt trở về ngưỡng an toàn. Thể trạng đang bước vào giai đoạn hồi phục tích cực."
            )
            action_plan = (
                "1. Ngừng uống thuốc hạ sốt giảm đau Paracetamol khi đã hết đau/hết sốt hoàn toàn.\n"
                "2. Duy trì xịt rửa mũi nước muối sinh lý thêm 2-3 ngày để niêm mạc phục hồi hoàn toàn.\n"
                "3. Bổ sung dinh dưỡng, uống nước hoa quả giàu vitamin C và nghỉ ngơi điều độ."
            )
            profile = self._apply_recovery_to_profile(profile, now_str, message)

        else:
            profile, detected_event, ai_analysis, action_plan = self._apply_dynamic_user_update_to_profile(
                profile, now_str, message, norm, vital_updates
            )

        self._save_user_profile(user_id, profile, tenant_id)
        return {
            "status": "success",
            "detected_event": detected_event,
            "ai_analysis": ai_analysis,
            "action_plan": action_plan,
            "must_discontinue_previous": must_discontinue,
            "discontinued_items": discontinued_items,
            "profile": profile,
        }

    # Internal Profile Builders
    def _build_default_flu_profile(self) -> PatientHealthProfile:
        now_str = datetime.now().strftime("%H:%M %d/%m/%Y")
        organs = _get_default_organs()
        return PatientHealthProfile(
            patient_id="demo-patient-001",
            patient_name="Bệnh nhân MedGuard",
            age=34,
            gender="Nam",
            active_diagnosis="Hội chứng Cảm cúm & Viêm đường hô hấp trên",
            overall_health_score=74,
            health_trend="stable",
            vitals=VitalSignsSummary(
                heart_rate_bpm=82,
                blood_pressure_systolic=122,
                blood_pressure_diastolic=80,
                temperature_celsius=38.2,
                spo2_percent=98,
                overall_pain_level=4,
            ),
            organs=organs,
            active_medications=["Paracetamol 500mg (khi sốt >38.5°C)", "Xịt mũi nước muối biển"],
            discontinued_medications=[],
            contraindicated_regimens=[],
            clinical_directives=[
                "Uống nhiều nước ấm (2-2.5 lít/ngày)",
                "Nghỉ ngơi tại phòng thoáng khí",
                "Theo dõi nhiệt độ cơ thể mỗi 4-6 giờ",
                "Tầm soát tiêm phòng vắc-xin Viêm gan B & Cúm mùa định kỳ",
            ],
            safe_guardrail_alert=None,
            timeline=[
                RecoveryTimelinePoint(
                    id="t1",
                    timestamp="08:30 Hôm nay",
                    phase="initial_onset",
                    title="Khởi phát triệu chứng cúm",
                    trigger_message="Tôi bị sốt 38.2 độ, đau đầu và sổ mũi, rát họng.",
                    health_score=74,
                    status_label="Thăm dò ban đầu",
                    clinical_summary="Khởi phát hội chứng cúm mùa. Đau đầu và viêm niêm mạc mũi họng rõ.",
                    ai_directive="Hướng dẫn dùng Paracetamol 500mg cách 4-6h nếu sốt, xịt mũi nước muối sinh lý.",
                    medications_adjusted=["Kê Paracetamol 500mg", "Xịt mũi nước muối"],
                )
            ],
            overall_future_risks=self._extract_overall_future_risks(organs),
            last_updated=now_str,
        )

    @staticmethod
    def _extract_overall_future_risks(organs: list[OrganStatus]) -> list[FutureRiskPrognosis]:
        risks: list[FutureRiskPrognosis] = []
        for organ in organs:
            if organ.future_risk:
                risks.append(organ.future_risk)
        order = {"critical": 0, "high": 1, "moderate": 2, "low": 3}
        risks.sort(key=lambda r: order.get(r.risk_level, 99))
        return risks

    def _build_recovered_profile(self, now_str: str) -> PatientHealthProfile:
        organs = _get_default_organs()
        for organ in organs:
            if organ.id in ["head", "ent", "spine_joints"]:
                organ.status = "normal"
                organ.health_score = 96
                organ.pain_level = 0
                organ.inflammation_level = "none"
                organ.symptoms = []
                organ.clinical_notes = "Đã hết đau nhức, đường thở thông thoáng hoàn toàn."

        return PatientHealthProfile(
            patient_id="demo-patient-001",
            patient_name="Bệnh nhân MedGuard",
            age=34,
            gender="Nam",
            active_diagnosis="Hồi phục sau Cảm cúm (Đã hết triệu chứng)",
            overall_health_score=95,
            health_trend="improving",
            vitals=VitalSignsSummary(
                heart_rate_bpm=74,
                blood_pressure_systolic=118,
                blood_pressure_diastolic=78,
                temperature_celsius=36.8,
                spo2_percent=99,
                overall_pain_level=0,
            ),
            organs=organs,
            active_medications=["Nước muối sinh lý vệ sinh mũi họng"],
            discontinued_medications=["Paracetamol 500mg (Dừng do đã cắt sốt & hết đau đầu)"],
            contraindicated_regimens=[],
            clinical_directives=[
                "Dừng thuốc giảm đau hạ sốt Paracetamol",
                "Tiếp tục uống đủ nước và tăng cường dinh dưỡng hoa quả",
                "Có thể trở lại sinh hoạt và làm việc nhẹ nhàng bình thường",
            ],
            safe_guardrail_alert=None,
            timeline=[
                RecoveryTimelinePoint(
                    id="t1",
                    timestamp="08:30 Hôm qua",
                    phase="initial_onset",
                    title="Khởi phát triệu chứng cúm",
                    trigger_message="Tôi bị sốt 38.2 độ, đau đầu và sổ mũi, rát họng.",
                    health_score=74,
                    status_label="Thăm dò ban đầu",
                    clinical_summary="Hội chứng cúm mùa, đau đầu, nghẹt mũi.",
                    ai_directive="Dùng Paracetamol 500mg và nước muối sinh lý.",
                    medications_adjusted=["Kê Paracetamol 500mg"],
                ),
                RecoveryTimelinePoint(
                    id="t2",
                    timestamp="14:00 Hôm nay",
                    phase="improved_recovering",
                    title="Thuyên giảm & Hết triệu chứng",
                    trigger_message="Hôm nay tôi đã hết đau đầu và sổ mũi rồi, người thấy rất khoẻ.",
                    health_score=95,
                    status_label="Hồi phục tốt (95%)",
                    clinical_summary="Nhiệt độ 36.8°C ổn định, đau đầu biến mất, đường hô hấp thông thoáng.",
                    ai_directive="Khuyến nghị ngừng thuốc Paracetamol, duy trì giữ ấm và bổ sung vitamin C.",
                    medications_adjusted=["Dừng Paracetamol 500mg"],
                ),
            ],
            overall_future_risks=self._extract_overall_future_risks(organs),
            last_updated=now_str,
        )

    def _build_adr_stomach_profile(self, now_str: str) -> PatientHealthProfile:
        organs = _get_default_organs()
        for organ in organs:
            if organ.id == "stomach":
                organ.status = "adverse_reaction"
                organ.health_score = 38
                organ.pain_level = 7
                organ.inflammation_level = "severe"
                organ.symptoms = ["Đau quặn thượng vị", "Cồn cào nóng rát", "Buồn nôn sau uống thuốc"]
                organ.clinical_notes = "Kích ứng niêm mạc dạ dày cấp nghi do thuốc chống viêm giảm đau NSAID."
                organ.warning = "CẢNH BÁO TÁC DỤNG PHỤ: Nguy cơ viêm loét niêm mạc dạ dày cấp!"
                organ.is_adverse_reaction = True
                organ.contraindicated_actions = [
                    "TIẾP TỤC UỐNG THUỐC NSAID/ASPIRIN",
                    "Uống thuốc khi bụng đói",
                    "Dùng đồ cay nóng, cà phê, rượu bia",
                ]

        return PatientHealthProfile(
            patient_id="demo-patient-001",
            patient_name="Bệnh nhân MedGuard",
            age=34,
            gender="Nam",
            active_diagnosis="Tác dụng phụ dạ dày cấp do thuốc (NSAID-induced Gastritis)",
            overall_health_score=52,
            health_trend="critical_alert",
            vitals=VitalSignsSummary(
                heart_rate_bpm=92,
                blood_pressure_systolic=130,
                blood_pressure_diastolic=84,
                temperature_celsius=37.2,
                spo2_percent=98,
                overall_pain_level=7,
            ),
            organs=organs,
            active_medications=["Nước ấm", "Men vi sinh / Thuốc tráng bao tử (nếu có)"],
            discontinued_medications=["Ibuprofen / Thuốc giảm đau NSAID (NGỪNG KHẨN CẤP)"],
            contraindicated_regimens=[
                "Tiếp tục uống thuốc giảm đau NSAID",
                "Tự ý tăng liều thuốc khi đau bụng",
            ],
            clinical_directives=[
                "NGỪNG NGAY LẬP TỨC thuốc giảm đau NSAID đang dùng",
                "Không để bụng đói, uống nước ấm từng ngụm nhỏ",
                "Đến cơ sở y tế gần nhất nếu đau quặn dữ dội hoặc có nôn ra máu / đi ngoài phân đen",
            ],
            safe_guardrail_alert=SafeGuardrailAlert(
                alert_level="danger",
                title="HẠN CHẾ CÁCH CŨ: Dừng ngay thuốc giảm đau gây hại dạ dày",
                cause_identified="Bệnh nhân phát sinh đau rát thượng vị và buồn nôn dữ dội sau khi uống thuốc.",
                contraindicated_item="Thuốc chống viêm giảm đau NSAID (Ibuprofen, Aspirin, Diclofenac)",
                required_action="DỪNG NGAY LẬP TỨC cách uống thuốc cũ. Tuyệt đối không tiếp tục uống viên kế tiếp.",
                alternative_recommendation="Uống nước ấm, nằm nghỉ ngơi đầu cao, tham vấn dược sĩ dùng thuốc bảo vệ niêm mạc (Antacid). Khám tiêu hóa nếu đau kéo dài.",
                seek_emergency=False,
            ),
            timeline=[
                RecoveryTimelinePoint(
                    id="t1",
                    timestamp="08:30 Hôm qua",
                    phase="initial_onset",
                    title="Khởi phát triệu chứng cúm",
                    trigger_message="Tôi bị sốt 38.2 độ, đau đầu và sổ mũi, rát họng.",
                    health_score=74,
                    status_label="Thăm dò ban đầu",
                    clinical_summary="Bắt đầu điều trị cảm cúm.",
                    ai_directive="Kê thuốc hạ sốt giảm đau.",
                    medications_adjusted=["Bắt đầu dùng thuốc giảm đau"],
                ),
                RecoveryTimelinePoint(
                    id="t2",
                    timestamp="11:30 Hôm nay",
                    phase="adverse_event_escalation",
                    title="Phát sinh tác dụng phụ đau dạ dày cấp",
                    trigger_message="Uống thuốc vào bỗng bị đau dạ dày dữ dội, cồn cào buồn nôn rát bụng.",
                    health_score=52,
                    status_label="Cảnh báo ADR nguy cơ cao",
                    clinical_summary="Kích ứng niêm mạc dạ dày cấp do NSAID. Đau thượng vị 7/10.",
                    ai_directive="AI Guardrail: BẮT BUỘC DỪNG CÁCH CŨ. Ngừng ngay NSAID, đổi sang bảo vệ tiêu hóa.",
                    medications_adjusted=["NGỪNG KHẨN CẤP: Ibuprofen/NSAID"],
                ),
            ],
            overall_future_risks=self._extract_overall_future_risks(organs),
            last_updated=now_str,
        )

    def _build_severe_progression_profile(self, now_str: str) -> PatientHealthProfile:
        organs = _get_default_organs()
        for organ in organs:
            if organ.id in ["head", "lungs", "cardiovascular"]:
                organ.status = "critical"
                organ.health_score = 42
                organ.pain_level = 6
                organ.inflammation_level = "severe"
                organ.symptoms = ["Sốt cao 39.5°C rét run", "Thở gấp, đau tức ngực", "Mệt lả toàn thân"]
                organ.warning = "CẢNH BÁO BỆNH TIẾN TRIỂN NẶNG: Nguy cơ nhiễm trùng phế quản phổi!"

        return PatientHealthProfile(
            patient_id="demo-patient-001",
            patient_name="Bệnh nhân MedGuard",
            age=34,
            gender="Nam",
            active_diagnosis="Sốt cao tiến triển kịch phát - Nghi ngờ bội nhiễm đường hô hấp",
            overall_health_score=46,
            health_trend="critical_alert",
            vitals=VitalSignsSummary(
                heart_rate_bpm=110,
                blood_pressure_systolic=138,
                blood_pressure_diastolic=88,
                temperature_celsius=39.5,
                spo2_percent=94,
                overall_pain_level=6,
            ),
            organs=organs,
            active_medications=["Oresol bù nước", "Hạ sốt khẩn cấp"],
            discontinued_medications=[],
            contraindicated_regimens=["Tự ý mua kháng sinh uống tại nhà khi chưa xét nghiệm máu"],
            clinical_directives=[
                "CẦN ĐẾN CƠ SỞ Y TẾ HOẶC PHÒNG CẤP CỨU NGAY LẬP TỨC",
                "Chườm ấm vùng trán, nách, bẹn trong thời gian chờ di chuyển",
                "Uống oresol từng ngụm nhỏ bù điện giải",
            ],
            safe_guardrail_alert=SafeGuardrailAlert(
                alert_level="critical",
                title="BÁO ĐỘNG ĐỎ: Triệu chứng vượt ngưỡng an toàn điều trị tại nhà",
                cause_identified="Sốt cao 39.5°C kèm SpO2 giảm xuống 94% và thở dốc.",
                contraindicated_item="Tiếp tục nằm nhà theo dõi thông thường",
                required_action="CHUYỂN NGAY TỚI BỆNH VIỆN / TRUNG TÂM Y TẾ GẦN NHẤT",
                alternative_recommendation="Sử dụng chức năng 'Chỉ đường Real-time' trong MedGuard để đến viện nhanh nhất.",
                seek_emergency=True,
            ),
            timeline=[
                RecoveryTimelinePoint(
                    id="t1",
                    timestamp="Hôm qua",
                    phase="initial_onset",
                    title="Khởi phát cúm",
                    trigger_message="Sốt nhẹ 38.2 độ, đau đầu.",
                    health_score=74,
                    status_label="Theo dõi ban đầu",
                    clinical_summary="Điều trị cảm cúm ban đầu.",
                    ai_directive="Uống Paracetamol hạ sốt.",
                    medications_adjusted=[],
                ),
                RecoveryTimelinePoint(
                    id="t2",
                    timestamp="Hôm nay",
                    phase="adverse_event_escalation",
                    title="Tiến triển nặng - Sốt kịch phát",
                    trigger_message="Bỗng nhiên sốt cao 39.5 độ, rét run, khó thở và mệt lả.",
                    health_score=46,
                    status_label="Báo động nguy kịch",
                    clinical_summary="SpO2 tụt 94%, mạch nhanh 110 bpm, nhiệt độ 39.5°C.",
                    ai_directive="Báo động khẩn cấp: Đến ngay cơ sở y tế gần nhất, không tự điều trị tại nhà.",
                    medications_adjusted=["Ngưng phác đồ tại nhà"],
                ),
            ],
            overall_future_risks=self._extract_overall_future_risks(organs),
            last_updated=now_str,
        )

    def _build_healthy_profile(self, now_str: str) -> PatientHealthProfile:
        organs = _get_healthy_organs()
        return PatientHealthProfile(
            patient_id="default",
            patient_name="Bệnh nhân",
            age=None,
            gender=None,
            active_diagnosis="Thể trạng bình thường — Chưa ghi nhận bệnh lý cấp tính",
            overall_health_score=100,
            health_trend="stable",
            vitals=VitalSignsSummary(),
            organs=organs,
            active_medications=[],
            discontinued_medications=[],
            contraindicated_regimens=[],
            clinical_directives=[
                "Duy trì chế độ ăn giàu dinh dưỡng và vận động thể lực đều đặn",
                "Uống đủ nước mỗi ngày",
                "Ngủ đủ giấc và sinh hoạt điều độ",
            ],
            safe_guardrail_alert=None,
            timeline=[],
            overall_future_risks=self._extract_overall_future_risks(organs),
            last_updated=now_str,
        )

    def _build_unassessed_profile(self, now_str: str) -> PatientHealthProfile:
        organs = _get_unassessed_organs()
        return PatientHealthProfile(
            patient_id="default",
            patient_name="Bệnh nhân",
            age=None,
            gender=None,
            active_diagnosis="Chưa có dữ liệu đánh giá lâm sàng — Chờ thu thập triệu chứng",
            overall_health_score=0,
            health_trend="unassessed",
            vitals=VitalSignsSummary(),
            organs=organs,
            active_medications=[],
            discontinued_medications=[],
            contraindicated_regimens=[],
            clinical_directives=[
                "Bắt đầu phiên tư vấn với Bác sĩ AI hoặc đo các chỉ số sinh tồn để cá nhân hóa Bản đồ Cơ thể 3D.",
                "Chia sẻ các triệu chứng hoặc tiền sử bệnh lý nếu có.",
            ],
            safe_guardrail_alert=None,
            timeline=[],
            overall_future_risks=[],
            last_updated=now_str,
        )

    # Dynamic Helpers for message evaluation
    def _apply_dynamic_user_update_to_profile(
        self,
        current: PatientHealthProfile,
        now_str: str,
        message: str,
        norm: str,
        vital_updates: dict[str, Any] | None = None,
    ) -> tuple[PatientHealthProfile, str, str, str]:
        p = current.model_copy(deep=True)
        matched_organs: list[str] = []
        detected_symptoms: list[str] = []
        ai_directives: list[str] = []
        detected_event = "symptom_update"

        # Strip negated symptom clauses to avoid false triggers ("không đau đầu", "không sốt", "không đau dạ dày")
        cleaned_norm = re.sub(
            r"\b(không|chẳng|chưa|hết|đã hết|ko)\s+(?:hề\s+|còn\s+)?(?:bị\s+|có\s+|thấy\s+)?(đau\s+đầu|nhức\s+đầu|đau\s+dạ\s+dày|đau\s+bao\s+tử|đau\s+bụng|cồn\s+cào|buồn\s+nôn|nôn|rát\s+thượng\s+vị|ợ\s+chua|ợ\s+hơi|đầy\s+bụng|khó\s+tiêu|trào\s+ngược|viêm\s+dạ\s+dày|sốt|ho|khó\s+thở|đau\s+khớp|mỏi\s+mắt|đau\s+ngực)\b",
            " ",
            norm,
        )

        is_healthy_claim = any(
            phrase in norm
            for phrase in (
                "hoàn toàn khỏe",
                "khỏe mạnh",
                "hết bệnh",
                "bình thường rồi",
                "không có triệu chứng",
                "khỏi hẳn rồi",
                "rất khỏe",
            )
        )

        if is_healthy_claim:
            for o in p.organs:
                o.status = "normal"
                o.health_score = 96
                o.pain_level = 0
                o.inflammation_level = "none"
                o.symptoms = []
                o.clinical_notes = "Khỏe mạnh bình thường. Không ghi nhận triệu chứng bệnh lý."
                o.warning = None
                o.is_adverse_reaction = False
            p.vitals.temperature_celsius = 36.6
            p.vitals.overall_pain_level = 0
            p.overall_health_score = 96
            p.health_trend = "stable"
            p.active_diagnosis = "Thể trạng khỏe mạnh, không ghi nhận triệu chứng bệnh lý"
            ai_analysis = "AI MedGuard ghi nhận: Thể trạng của bạn hoàn toàn khỏe mạnh, không có dấu hiệu bất thường trên các cơ quan giải phẫu. Điểm sức khỏe toàn thân đạt 96/100."
            action_plan = "Duy trì chế độ ăn uống khoa học, uống đủ nước và tập luyện thể dục đều đặn."
            detected_event = "recovery"
            p.safe_guardrail_alert = None
            p.timeline = p.timeline[-14:]
            p.timeline.append(
                RecoveryTimelinePoint(
                    id=f"t{len(p.timeline)+1}",
                    timestamp=now_str,
                    day_label="Hiện tại",
                    overall_score=96,
                    temperature=36.6,
                    primary_event="Thể trạng hoàn toàn khỏe mạnh",
                    medications_adjusted=[],
                )
            )
            p.last_updated = now_str
            return p, detected_event, ai_analysis, action_plan

        # 1. Temperature detection
        temp_match = re.search(r"sốt\s*([34][0-9](?:[\.,][0-9])?)\s*(?:độ|°c)?", cleaned_norm)
        if temp_match:
            val = float(temp_match.group(1).replace(",", "."))
            p.vitals.temperature_celsius = val
            detected_symptoms.append(f"Sốt {val}°C")
        elif re.search(r"(?<![a-zà-ỹ])sốt(?![a-zà-ỹ])", cleaned_norm):
            p.vitals.temperature_celsius = 38.2
            detected_symptoms.append("Sốt")

        # 2. Blood pressure detection
        bp_match = re.search(r"huyết áp\s*([0-9]{2,3})\s*[\/]\s*([0-9]{2,3})", cleaned_norm)
        if bp_match:
            p.vitals.blood_pressure_systolic = int(bp_match.group(1))
            p.vitals.blood_pressure_diastolic = int(bp_match.group(2))
            detected_symptoms.append(f"Huyết áp {p.vitals.blood_pressure_systolic}/{p.vitals.blood_pressure_diastolic} mmHg")

        # 3. Heart rate detection
        hr_match = re.search(r"(?:nhịp tim|mạch)\s*([0-9]{2,3})", cleaned_norm)
        if hr_match:
            p.vitals.heart_rate_bpm = int(hr_match.group(1))

        # 4. Pain level detection
        pain_match = re.search(r"đau\s*([0-9]|10)\s*(?:\/10|điểm)", cleaned_norm)
        if pain_match:
            p.vitals.overall_pain_level = int(pain_match.group(1))

        # 5. Medications mentioned
        med_rules = [
            ("Paracetamol 500mg", r"paracetamol|hapacol|panadol|efferalgan"),
            ("Ibuprofen 400mg", r"ibuprofen|gofen"),
            ("Aspirin", r"aspirin"),
            ("Kháng sinh Amoxicillin", r"amoxicillin|augmentin|klamentin"),
            ("Thuốc dạ dày Omeprazole", r"omeprazole|nexium|gaviscon|phosphalugel"),
            ("Thuốc huyết áp", r"amlodipine|losartan|captopril|thuốc huyết áp"),
            ("Xịt mũi nước muối", r"xịt mũi|nước muối biển|rửa mũi"),
        ]
        for med_label, pat in med_rules:
            if re.search(pat, cleaned_norm):
                if med_label not in p.active_medications:
                    p.active_medications.append(med_label)

        # 6. Organ: Head & Brain
        if re.search(r"(?<![a-zà-ỹ])(đau\s+đầu|nhức\s+đầu|nặng\s+trán|nặng\s+đầu|hoa\s+mắt|chóng\s+mặt|buốt\s+trán|mất\s+ngủ|stress|căng\s+thẳng|đau\s+nửa\s+đầu)(?![a-zà-ỹ])", cleaned_norm):
            head = next((o for o in p.organs if o.id == "head"), None)
            if head:
                is_severe = "dữ dội" in cleaned_norm or "kinh khủng" in cleaned_norm or "quá mức" in cleaned_norm
                head.status = "inflamed" if is_severe else "monitoring"
                head.health_score = 65 if is_severe else 72
                head.pain_level = 5 if is_severe else 3
                head.inflammation_level = "moderate" if is_severe else "mild"
                head.symptoms = ["Đau nhức đầu, nặng trán"]
                head.clinical_notes = f"Ghi nhận từ phản ánh của bạn: {message}"
                matched_organs.append("Đầu & Thần kinh")
                ai_directives.append("Nghỉ ngơi tại phòng thoáng, tránh ánh sáng xanh màn hình")

        # 7. Organ: Ear, Nose & Throat (ENT)
        if re.search(r"(?<![a-zà-ỹ])(đau\s+họng|rát\s+họng|ngứa\s+cổ|sổ\s+mũi|chảy\s+nước\s+mũi|chảy\s+mũi|nghẹt\s+mũi|tắc\s+mũi|viêm\s+xoang|hắt\s+hơi|khàn\s+tiếng|mất\s+tiếng|viêm\s+họng|viêm\s+amiđan)(?![a-zà-ỹ])", cleaned_norm):
            ent = next((o for o in p.organs if o.id == "ent"), None)
            if ent:
                ent.status = "inflamed"
                ent.health_score = 65
                ent.pain_level = 3
                ent.inflammation_level = "moderate"
                ent_syms = []
                if re.search(r"đau\s+họng|rát\s+họng|ngứa\s+cổ", cleaned_norm): ent_syms.append("Đau rát họng")
                if re.search(r"sổ\s+mũi|chảy\s+nước\s+mũi|chảy\s+mũi", cleaned_norm): ent_syms.append("Sổ mũi nước trong")
                if re.search(r"nghẹt\s+mũi|tắc\s+mũi", cleaned_norm): ent_syms.append("Nghẹt mũi")
                if not ent_syms: ent_syms.append("Kích ứng niêm mạc mũi họng")
                ent.symptoms = ent_syms
                ent.clinical_notes = f"Ghi nhận từ phản ánh của bạn: {message}"
                matched_organs.append("Tai Mũi Họng")
                ai_directives.append("Súc họng nước muối ấm 0.9%, xịt rửa mũi đẳng trương")

        # 8. Organ: Lungs & Respiratory
        # Word boundary ensures "hoàn toàn" does not match "ho"!
        if re.search(r"(?<![a-zà-ỹ])(ho\s+khan|ho\s+có\s+đờm|ho\s+đờm|khó\s+thở|hụt\s+hơi|thở\s+dốc|tức\s+ngực|khò\s+khè|viêm\s+phế\s+quản|viêm\s+phổi|bị\s+ho|ho\s+nhiều|ho)(?![a-zà-ỹ])", cleaned_norm):
            lungs = next((o for o in p.organs if o.id == "lungs"), None)
            if lungs:
                is_severe = "khó thở" in cleaned_norm or "tức ngực" in cleaned_norm
                lungs.status = "inflamed" if is_severe else "monitoring"
                lungs.health_score = 68 if is_severe else 78
                lungs.pain_level = 3 if is_severe else 1
                lungs.inflammation_level = "moderate" if is_severe else "mild"
                lungs.symptoms = ["Ho, kích ứng đường thở dưới"]
                lungs.clinical_notes = f"Ghi nhận từ phản ánh của bạn: {message}"
                matched_organs.append("Phổi & Hô hấp")
                ai_directives.append("Giữ ấm vùng ngực cổ, uống nhiều nước ấm, theo dõi sát nhịp thở")

        # 9. Organ: Cardiovascular
        if re.search(r"tim đập nhanh|hồi hộp|đánh trống ngực|đau thắt ngực|nhói tim|tăng huyết áp|huyết áp cao|tụt huyết áp", cleaned_norm):
            cardio = next((o for o in p.organs if o.id == "cardiovascular"), None)
            if cardio:
                cardio.status = "monitoring"
                cardio.health_score = 75
                cardio.symptoms = ["Hồi hộp, tim đập nhanh hoặc huyết áp dao động"]
                cardio.clinical_notes = f"Ghi nhận từ bạn: {message}"
                matched_organs.append("Tim mạch & Tuần hoàn")
                ai_directives.append("Nghỉ ngơi yên tĩnh, đo lại huyết áp và nhịp tim sau 15 phút")

        # 10. Organ: Stomach & Digestion
        if re.search(r"(?<![a-zà-ỹ])(đau\s+dạ\s+dày|đau\s+bao\s+tử|đau\s+bụng|cồn\s+cào|ợ\s+chua|ợ\s+hơi|rát\s+thượng\s+vị|buồn\s+nôn|nôn|khó\s+tiêu|đầy\s+bụng|tiêu\s+chảy|trào\s+ngược)(?![a-zà-ỹ])", cleaned_norm):
            stomach = next((o for o in p.organs if o.id == "stomach"), None)
            if stomach:
                stomach.status = "inflamed"
                stomach.health_score = 62
                stomach.pain_level = 4
                stomach.inflammation_level = "moderate"
                stomach.symptoms = ["Đau rát cồn cào thượng vị, khó tiêu"]
                stomach.clinical_notes = f"Ghi nhận từ bạn: {message}"
                matched_organs.append("Dạ dày & Tiêu hoá")
                ai_directives.append("Không uống thuốc khi bụng đói, chia nhỏ bữa ăn và kiêng đồ chua cay")

        # 11. Organ: Liver & Hepatitis B Vaccine Status
        if re.search(r"chưa tiêm (phòng)?\s*(vắc[- ]?xin|vacxin)?\s*(viêm gan b|hbv)|anti-?hbs âm tính|chưa chích ngừa viêm gan", cleaned_norm):
            liver = next((o for o in p.organs if o.id == "liver"), None)
            if liver and liver.future_risk:
                liver.future_risk.risk_level = "high"
                liver.future_risk.risk_title = "Nguy cơ Nhiễm HBV mạn tính, Xơ gan tiến triển & Ung thư gan (HCC)"
                liver.future_risk.vaccination_status = "CHƯA TIÊM PHÒNG: Người dùng xác nhận chưa tiêm vắc-xin Viêm gan B (Kháng thể Anti-HBs âm tính)"
                liver.future_risk.latent_risk_description = "Bạn đã xác nhận chưa có kháng thể bảo vệ trước virus Viêm gan B (HBV). Nếu phơi nhiễm nguồn lây, nguy cơ chuyển thể mạn tính chiếm tới 10-15%, tiến triển âm thầm dẫn đến xơ gan và ung thư gan HCC sau 5-10 năm."
                liver.clinical_notes = "Ghi nhận từ người dùng: Chưa tiêm phòng vắc-xin Viêm gan B. Cần tiêm phòng đủ 3 mũi chuẩn (Tháng 0, 1, 6)."
                matched_organs.append("Gan & Chuyển hoá (Tiền sử vắc-xin)")
                detected_event = "vaccine_risk_alert"
                ai_directives.append("Thực hiện tiêm vắc-xin Viêm gan B đủ 3 mũi (Tháng 0, 1, 6) càng sớm càng tốt để ngừa ung thư gan HCC")

        elif re.search(r"đã tiêm (đủ)?\s*(?:3 mũi|phòng|vắc[- ]?xin|vacxin)?\s*(?:viêm gan b|hbv)|anti-?hbs dương tính|có kháng thể viêm gan b|đã chích ngừa viêm gan", cleaned_norm):
            liver = next((o for o in p.organs if o.id == "liver"), None)
            if liver and liver.future_risk:
                liver.future_risk.risk_level = "low"
                liver.future_risk.risk_title = "Nguy cơ HBV được bảo vệ tối ưu nhờ vắc-xin"
                liver.future_risk.vaccination_status = "ĐÃ TIÊM PHÒNG: Đã tiêm đủ vắc-xin Viêm gan B (Kháng thể Anti-HBs dương tính)"
                liver.future_risk.latent_risk_description = "Hệ miễn dịch của bạn đã có kháng thể bảo vệ vững chắc trước virus Viêm gan B. Nguy cơ ung thư gan HCC do HBV được loại trừ tối đa."
                liver.clinical_notes = "Ghi nhận từ người dùng: Đã tiêm đủ vắc-xin Viêm gan B, an toàn trước nguy cơ lây nhiễm HBV."
                matched_organs.append("Gan & Chuyển hoá (Tiền sử vắc-xin)")
                detected_event = "vaccine_verified"
                ai_directives.append("Định kỳ kiểm tra hiệu giá kháng thể Anti-HBs sau mỗi 5-10 năm")

        elif re.search(r"men gan cao|vàng da|uống nhiều rượu|uống rượu bia|nhiễm viêm gan", cleaned_norm):
            liver = next((o for o in p.organs if o.id == "liver"), None)
            if liver:
                liver.status = "monitoring"
                liver.health_score = 70
                liver.symptoms = ["Men gan cao hoặc có nguy cơ tổn thương gan do rượu"]
                liver.clinical_notes = f"Ghi nhận từ bạn: {message}"
                matched_organs.append("Gan & Chuyển hoá")
                ai_directives.append("Hạn chế tối đa rượu bia, không dùng Paracetamol quá 3000mg/24h")

        # 12. Organ: Kidneys
        if re.search(r"tiểu buốt|tiểu rắt|tiểu đêm|tiểu ra máu|đau thắt lưng hông|đau hố thận", cleaned_norm):
            kidneys = next((o for o in p.organs if o.id == "kidneys"), None)
            if kidneys:
                kidneys.status = "monitoring"
                kidneys.health_score = 75
                kidneys.symptoms = ["Triệu chứng tiết niệu hoặc đau mỏi hông lưng"]
                kidneys.clinical_notes = f"Ghi nhận từ bạn: {message}"
                matched_organs.append("Thận & Tiết niệu")
                ai_directives.append("Uống đủ 2-2.5 lít nước ấm mỗi ngày, không nhịn tiểu")

        # 13. Organ: Spine & Musculoskeletal
        if re.search(r"đau lưng|mỏi lưng|đau cổ|mỏi gáy|đau vai gáy|đau khớp|cứng khớp|mỏi người|đau cột sống", cleaned_norm):
            spine = next((o for o in p.organs if o.id == "spine_joints"), None)
            if spine:
                spine.status = "monitoring"
                spine.health_score = 75
                spine.pain_level = 3
                spine.symptoms = ["Đau mỏi cơ xương khớp hoặc cột sống"]
                spine.clinical_notes = f"Ghi nhận từ bạn: {message}"
                matched_organs.append("Cơ xương khớp & Cột sống")
                ai_directives.append("Vận động nhẹ nhàng, điều chỉnh tư thế ngồi công thái học")

        # 14. Organ: Skin & Immunity
        if re.search(r"nổi mẩn|phát ban|ngứa da|dị ứng da", cleaned_norm):
            skin = next((o for o in p.organs if o.id == "skin"), None)
            if skin:
                skin.status = "inflamed"
                skin.health_score = 70
                skin.symptoms = ["Nổi mẩn, ngứa ngáy bề mặt da"]
                skin.clinical_notes = f"Ghi nhận từ bạn: {message}"
                matched_organs.append("Da liễu & Hệ miễn dịch")
                ai_directives.append("Theo dõi sát phản ứng da, ngưng các loại mỹ phẩm hoặc thuốc nghi ngờ")

        # If user explicitly states they are healthy and no symptoms were detected:
        if is_healthy_claim and not matched_organs:
            for o in p.organs:
                o.status = "normal"
                o.health_score = 95
                o.pain_level = 0
                o.inflammation_level = "none"
                o.symptoms = []
                o.clinical_notes = "Khỏe mạnh bình thường. Chưa ghi nhận triệu chứng bất thường."
                o.warning = None
            p.vitals.temperature_celsius = 36.6
            p.vitals.overall_pain_level = 0
            p.overall_health_score = 95
            p.health_trend = "stable"
            p.active_diagnosis = "Thể trạng khỏe mạnh, không ghi nhận triệu chứng bệnh lý"
            ai_analysis = "AI MedGuard ghi nhận: Thể trạng của bạn hoàn toàn khỏe mạnh, không có dấu hiệu bất thường trên các cơ quan giải phẫu. Điểm sức khỏe toàn thân đạt 95/100."
            action_plan = "Duy trì chế độ ăn uống khoa học, uống đủ nước và tập luyện thể dục đều đặn."
            detected_event = "recovery"

        # Compute dynamic overall health score (default unassessed/zero scores to 95 baseline)
        scores = [o.health_score if (o.health_score is not None and o.health_score > 0) else 95 for o in p.organs]
        avg_score = round(sum(scores) / len(scores)) if scores else 95
        p.overall_health_score = avg_score
        p.health_trend = "deteriorating" if avg_score < 80 else "stable"

        if matched_organs:
            p.active_diagnosis = f"Ghi nhận phản ánh từ bạn: {', '.join(matched_organs)}"
            ai_analysis = (
                f"AI MedGuard đã phân tích phản ánh của bạn: Cập nhật tình trạng {', '.join(matched_organs)} "
                f"trên bản đồ cơ thể giải phẫu học. Điểm sức khỏe toàn thân hiện tại đạt {avg_score}/100."
            )
            action_plan = "\n".join(f"{i+1}. {d}" for i, d in enumerate(ai_directives)) if ai_directives else "Tiếp tục theo dõi sức khỏe và thực hiện theo khuyến nghị lâm sàng."
        else:
            ai_analysis = f"AI MedGuard đã ghi nhận thông tin theo dõi sức khoẻ từ bạn: '{message}'."
            action_plan = "Hệ thống đã lưu thông tin vào nhật ký theo dõi sức khoẻ cá nhân."

        # Add to timeline
        p.timeline.append(
            RecoveryTimelinePoint(
                id=f"t{len(p.timeline)+1}",
                timestamp=now_str,
                phase="under_treatment" if avg_score < 85 else "improved_recovering",
                title=f"Cập nhật: {', '.join(matched_organs)}" if matched_organs else "Cập nhật sức khoẻ từ bạn",
                trigger_message=message,
                health_score=p.overall_health_score,
                status_label=f"Đánh giá {p.overall_health_score}%",
                clinical_summary=f"Bạn đã cung cấp thông tin: \"{message}\". Hệ thống đã cập nhật trực tiếp vào bản đồ cơ thể.",
                ai_directive="; ".join(ai_directives) if ai_directives else "Tiếp tục theo dõi diễn tiến lâm sàng.",
                medications_adjusted=p.active_medications,
            )
        )
        p.last_updated = now_str
        p.overall_future_risks = self._extract_overall_future_risks(p.organs)
        return p, detected_event, ai_analysis, action_plan

    def _apply_adr_stomach_to_profile(self, current: PatientHealthProfile, now_str: str, message: str) -> PatientHealthProfile:
        p = current.model_copy(deep=True)
        p.active_diagnosis = "Kích ứng dạ dày cấp nghi do thuốc (ADR)"
        p.overall_health_score = max(35, p.overall_health_score - 25)
        p.health_trend = "critical_alert"
        p.vitals.overall_pain_level = 7
        p.vitals.heart_rate_bpm = 90

        for organ in p.organs:
            if organ.id == "stomach":
                organ.status = "adverse_reaction"
                organ.health_score = 35
                organ.pain_level = 7
                organ.inflammation_level = "severe"
                organ.symptoms = ["Đau rát cồn cào thượng vị", "Buồn nôn sau uống thuốc"]
                organ.warning = "CẢNH BÁO TÁC DỤNG PHỤ CẤP: Dừng ngay loại thuốc nghi ngờ gây hại dạ dày!"
                organ.is_adverse_reaction = True
                organ.contraindicated_actions = ["Tiếp tục uống thuốc cũ", "Uống thuốc khi đói"]

        discontinued = "Thuốc giảm đau NSAID / Kháng sinh nghi ngờ"
        if discontinued not in p.discontinued_medications:
            p.discontinued_medications.append(discontinued)

        p.safe_guardrail_alert = SafeGuardrailAlert(
            alert_level="danger",
            title="AI BẢO VỆ: Hạn chế và Dừng ngay loại thuốc đang gây hại dạ dày",
            cause_identified="Bệnh nhân ghi nhận cơn đau quặn thượng vị sau khi uống thuốc.",
            contraindicated_item="Thuốc giảm đau kháng viêm NSAID đang sử dụng",
            required_action="DỪNG NGAY CÁCH CŨ. Không uống thêm liều tiếp theo.",
            alternative_recommendation="Uống nước ấm, dùng thuốc bảo vệ niêm mạc dạ dày (Antacid). Khám tiêu hóa nếu đau tăng dần.",
            seek_emergency=False,
        )

        p.clinical_directives = [
            "NGỪNG NGAY thuốc nghi ngờ gây kích ứng dạ dày",
            "Uống nhiều nước ấm, nghỉ ngơi tại chỗ",
            "Đến viện nếu đau quặn dữ dội hoặc nôn mửa",
        ]

        p.timeline.append(
            RecoveryTimelinePoint(
                id=f"t{len(p.timeline)+1}",
                timestamp=now_str,
                phase="adverse_event_escalation",
                title="Cảnh báo phản ứng phụ đường tiêu hóa",
                trigger_message=message,
                health_score=p.overall_health_score,
                status_label="Nguy cơ ADR - Dừng thuốc cũ",
                clinical_summary="Đau rát dạ dày cấp sau dùng thuốc. Kích hoạt rào cản an toàn dừng thuốc cũ.",
                ai_directive="BẮT BUỘC DỪNG CÁCH CŨ. Ngừng NSAID ngay lập tức.",
                medications_adjusted=["Ngưng thuốc kích ứng dạ dày"],
            )
        )
        p.last_updated = now_str
        return p

    def _apply_allergy_to_profile(self, current: PatientHealthProfile, now_str: str, message: str) -> PatientHealthProfile:
        p = current.model_copy(deep=True)
        p.active_diagnosis = "Dị ứng thuốc cấp tính (Nổi mề đay / Ban da)"
        p.overall_health_score = max(40, p.overall_health_score - 20)
        p.health_trend = "critical_alert"

        for organ in p.organs:
            if organ.id == "skin":
                organ.status = "adverse_reaction"
                organ.health_score = 40
                organ.pain_level = 5
                organ.inflammation_level = "severe"
                organ.symptoms = ["Nổi ban đỏ", "Ngứa ngáy rát da"]
                organ.warning = "CẢNH BÁO DỊ ỨNG THUỐC: Dừng ngay để ngừa sốc phản vệ!"
                organ.is_adverse_reaction = True

        p.safe_guardrail_alert = SafeGuardrailAlert(
            alert_level="danger",
            title="DỪNG THUỐC KHẨN CẤP: Dấu hiệu dị ứng thuốc",
            cause_identified="Phản ứng nổi ban đỏ và ngứa ngáy sau dùng thuốc.",
            contraindicated_item="Toàn bộ thuốc mới bắt đầu uống",
            required_action="NGỪNG NGAY LẬP TỨC toàn bộ liều thuốc kế tiếp.",
            alternative_recommendation="Theo dõi sát hô hấp. Nếu khó thở hoặc sưng phù mặt, gọi 115 ngay.",
            seek_emergency=False,
        )

        p.timeline.append(
            RecoveryTimelinePoint(
                id=f"t{len(p.timeline)+1}",
                timestamp=now_str,
                phase="adverse_event_escalation",
                title="Phát hiện dị ứng thuốc",
                trigger_message=message,
                health_score=p.overall_health_score,
                status_label="Dị ứng thuốc cấp",
                clinical_summary="Nổi ban da và ngứa ngáy sau dùng thuốc.",
                ai_directive="Ngừng thuốc ngay lập tức, theo dõi đường thở.",
                medications_adjusted=["Ngưng thuốc gây dị ứng"],
            )
        )
        p.last_updated = now_str
        return p

    def _apply_escalation_to_profile(self, current: PatientHealthProfile, now_str: str, message: str) -> PatientHealthProfile:
        p = current.model_copy(deep=True)
        p.active_diagnosis = "Bệnh tiến triển nặng - Sốt cao / Bội nhiễm hô hấp"
        p.overall_health_score = max(35, p.overall_health_score - 30)
        p.health_trend = "critical_alert"
        p.vitals.temperature_celsius = 39.5
        p.vitals.heart_rate_bpm = 108
        p.vitals.spo2_percent = 95

        for organ in p.organs:
            if organ.id in ["head", "lungs"]:
                organ.status = "critical"
                organ.health_score = 45
                organ.pain_level = 6
                organ.inflammation_level = "severe"
                organ.warning = "TRIỆU CHỨNG TIẾN TRIỂN NẶNG VƯỢT NGƯỠNG ĐIỀU TRỊ TẠI NHÀ"

        p.safe_guardrail_alert = SafeGuardrailAlert(
            alert_level="critical",
            title="HẠN CHẾ CÁCH CŨ: Dừng tự điều trị tại nhà, cần tới bệnh viện",
            cause_identified="Bệnh nhân sốt cao kịch phát hoặc khó thở tăng nặng.",
            contraindicated_item="Tiếp tục nằm nhà uống thuốc hạ sốt đơn thuần",
            required_action="ĐẾN CƠ SỞ Y TẾ HOẶC PHÒNG CẤP CỨU GẦN NHẤT ĐỂ ĐƯỢC BÁC SĨ KHÁM TRỰC TIẾP",
            alternative_recommendation="Chườm mát vùng cổ nách bẹn, chuẩn bị hồ sơ y tế và di chuyển an toàn.",
            seek_emergency=True,
        )

        p.timeline.append(
            RecoveryTimelinePoint(
                id=f"t{len(p.timeline)+1}",
                timestamp=now_str,
                phase="adverse_event_escalation",
                title="Tiến triển nặng vượt ngưỡng",
                trigger_message=message,
                health_score=p.overall_health_score,
                status_label="Báo động nguy kịch",
                clinical_summary="Sốt cao tiến triển, nguy cơ biến chứng hô hấp.",
                ai_directive="Dừng tự điều trị tại nhà, di chuyển đến viện ngay.",
                medications_adjusted=[],
            )
        )
        p.last_updated = now_str
        return p

    def _apply_recovery_to_profile(self, current: PatientHealthProfile, now_str: str, message: str) -> PatientHealthProfile:
        p = current.model_copy(deep=True)
        p.active_diagnosis = "Giai đoạn hồi phục sau cảm cúm"
        p.overall_health_score = min(96, max(90, p.overall_health_score + 20))
        p.health_trend = "improving"
        p.vitals.temperature_celsius = 36.8
        p.vitals.overall_pain_level = 0
        p.vitals.heart_rate_bpm = 74

        for organ in p.organs:
            organ.status = "normal"
            organ.health_score = 96
            organ.pain_level = 0
            organ.inflammation_level = "none"
            organ.symptoms = []
            organ.clinical_notes = "Đã thuyên giảm hoàn toàn, không còn triệu chứng khó chịu."
            organ.warning = None
            organ.is_adverse_reaction = False

        scores = [o.health_score for o in p.organs if o.health_score]
        p.overall_health_score = round(sum(scores) / len(scores)) if scores else 96

        if "Paracetamol 500mg" in p.active_medications:
            p.active_medications.remove("Paracetamol 500mg")
            p.discontinued_medications.append("Paracetamol 500mg (Dừng do đã cắt sốt & hết đau đầu)")

        p.safe_guardrail_alert = None
        p.clinical_directives = [
            "Ngừng dùng thuốc giảm đau Paracetamol khi đã hết triệu chứng",
            "Tiếp tục uống nhiều nước và vệ sinh mũi họng bằng nước muối sinh lý",
            "Bổ sung vitamin, nghỉ ngơi hợp lý để duy trì thể trạng tối ưu",
        ]

        p.timeline = p.timeline[-14:]
        p.timeline.append(
            RecoveryTimelinePoint(
                id=f"t{len(p.timeline)+1}",
                timestamp=now_str,
                phase="improved_recovering",
                title="Thuyên giảm triệu chứng & Hồi phục",
                trigger_message=message,
                health_score=p.overall_health_score,
                status_label="Hồi phục xuất sắc (96%)",
                clinical_summary="Hết sốt, hết đau đầu sổ mũi, thể trạng phục hồi tốt.",
                ai_directive="Khuyên ngừng thuốc hạ sốt, duy trì lối sống lành mạnh.",
                medications_adjusted=["Ngừng Paracetamol khi hết triệu chứng"],
            )
        )
        p.last_updated = now_str
        return p


patient_health_twin_service = PatientHealthTwinService()
