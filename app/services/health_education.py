"""Bounded general education; no diagnosis, calorie target or personal diet prescription."""
import re
from app.services.clinical_text import normalize_search_text


def _guidance(title, summary, actions, questions, reference, *, intent="general"):
    return {"title": title, "summary": summary, "next_steps": actions,
            "questions": questions, "references": [reference], "intent": intent,
            "limitations": "Thông tin hỗ trợ này không thay thế đánh giá trực tiếp hoặc hướng dẫn cá nhân của nhân viên y tế."}


def request_guidance(text: str) -> dict | None:
    """Recognize explicit education/safety questions, never determine acuity.

    The caller must exclude present emergencies before rendering these answers.
    Severity and multi-turn history remain owned by the clinical pipeline.
    """
    n = normalize_search_text(text)
    if "thuoc" in n and re.search(r"\b(?:co the|co nen|nen|muon)\s+(?:tu\s+)?ngung\b", n):
        return _guidance("Không tự ngừng thuốc chỉ vì thấy đỡ",
            "Không tự ngừng thuốc đang được kê chỉ vì triệu chứng đã đỡ. Chưa biết tên thuốc, mục đích điều trị và thời gian dùng nên chưa thể quyết định có thể ngừng hay cần giảm dần cho riêng bạn.",
            ["Trao đổi với bác sĩ kê thuốc hoặc dược sĩ trước khi ngừng hay thay đổi liều; kiểm tra thời gian dùng trên đơn và nhãn thuốc.",
             "Nếu muốn ngừng vì tác dụng phụ, hãy nêu rõ triệu chứng và liên hệ nhân viên y tế để được hướng dẫn phù hợp."],
            ["Tên thuốc, liều trên đơn và thời gian bạn đã dùng là gì?", "Bạn muốn ngừng vì đã đỡ hay vì đang có tác dụng phụ?"],
            "https://www.fda.gov/consumers/womens-health/use-medicines-wisely", intent="safety")
    if "quen" in n and "thuoc" in n and any(x in n for x in ("gap doi", "bu lieu", "nen uong")):
        return _guidance("Xử trí khi quên một liều thuốc",
            "Không tự tăng liều để bù liều đã quên. Chưa biết tên thuốc, hàm lượng và thời điểm liều kế tiếp nên chưa thể xác định bạn cần uống bù hay bỏ qua liều.",
            ["Kiểm tra mục liều đã quên trên nhãn thuốc hoặc tờ hướng dẫn; hỏi bác sĩ hoặc dược sĩ trước khi thay đổi lịch dùng.",
             "Nếu đã dùng thêm thuốc hoặc có choáng, ngất, đau ngực hay khó thở, cần liên hệ cơ sở y tế ngay."],
            ["Tên thuốc, hàm lượng và thời điểm bạn thường uống là gì; bạn đã uống bù chưa?"],
            "https://sps.nhs.uk/articles/advising-on-missed-or-delayed-doses-of-medicines/", intent="safety")
    if "thuoc" in n and any(x in n for x in ("cua nguoi nha", "cua nguoi khac", "dung chung don")):
        return _guidance("Không dùng thuốc kê cho người khác",
            "Không dùng thuốc của người khác dù triệu chứng giống nhau. Nguyên nhân, bệnh nền, dị ứng và thuốc đang dùng có thể khác; chưa thể xác định thuốc đó có phù hợp với bạn.",
            ["Hỏi bác sĩ hoặc dược sĩ với tên thuốc và tình trạng của bạn trước khi dùng."],
            ["Bạn đang có triệu chứng gì và tên thuốc đang cân nhắc là gì?"],
            "https://www.fda.gov/consumers/womens-health/use-medicines-wisely", intent="safety")
    if "khang sinh" in n and any(x in n for x in ("cam cum", "cam lanh", "virus")) and any(x in n for x in ("co dung", "tren mang", "chua", "co the")):
        return _guidance("Kháng sinh và bệnh do virus",
            "Kháng sinh không chữa nhiễm virus như cảm cúm. Chỉ dùng khi bác sĩ xác định có chỉ định điều trị nhiễm khuẩn; không tự dùng để rút ngắn cảm cúm.",
            ["Nghỉ ngơi, uống đủ nước và theo dõi triệu chứng; hỏi bác sĩ nếu bệnh nặng lên hoặc bạn thuộc nhóm nguy cơ cao."], [],
            "https://www.nhs.uk/conditions/respiratory-tract-infection/")
    if "vitamin c" in n and any(x in n for x in ("cam cum", "cam lanh")):
        return _guidance("Vitamin C và cảm cúm",
            "Chưa có bằng chứng đủ để coi vitamin C liều cao là cách điều trị cảm cúm. Một số nghiên cứu về cảm lạnh ghi nhận lợi ích nhỏ khi bổ sung đều đặn, nhưng bắt đầu dùng sau khi bệnh xuất hiện không cho hiệu quả nhất quán; cảm lạnh và cúm cũng không phải cùng một bệnh.",
            ["Không dùng liều cao để thay thế điều trị; có thể gây tiêu chảy, buồn nôn và đau bụng.",
             "Nghỉ ngơi, uống đủ nước, theo dõi; đi khám nếu khó thở, đau ngực, bệnh nặng lên hoặc bạn có nguy cơ biến chứng."], [],
            "https://ods.od.nih.gov/factsheets/VitaminC-HealthProfessional/")
    if "giam" in n and "kg" in n and any(x in n for x in ("nhanh", "mot thang", "1 thang")):
        return _guidance("Giảm cân an toàn và bền vững",
            "Giảm nhiều cân trong thời gian ngắn có thể quá nhanh và không an toàn. Chưa biết tuổi, cân nặng, bệnh nền và cách bạn định thực hiện nên chưa thể đặt mục tiêu giảm cân riêng.",
            ["Ưu tiên thay đổi từ từ về khẩu phần, vận động và giấc ngủ; trao đổi với bác sĩ hoặc chuyên gia dinh dưỡng để đặt mục tiêu phù hợp."],
            ["Bạn bao nhiêu tuổi, cao và nặng bao nhiêu; có bệnh nền hoặc đang dùng thuốc nào không?"],
            "https://www.nhs.uk/better-health/lose-weight/")
    if "huyet ap" in n and any(x in n for x in ("chua khoi", "khoi hoan toan")):
        return _guidance("Kiểm soát tăng huyết áp lâu dài",
            "Tăng huyết áp thường cần kiểm soát lâu dài bằng lối sống, theo dõi và thuốc khi có chỉ định. Không thể khẳng định khả năng khỏi hoàn toàn cho riêng bạn chỉ từ tin nhắn.",
            ["Đo huyết áp đúng kỹ thuật, ghi nhật ký và tái khám theo hẹn.",
             "Dùng thuốc đúng đơn; không tự ngừng thuốc. Trao đổi với bác sĩ trước khi giảm liều hoặc ngừng thuốc; duy trì lối sống phù hợp."],
            ["Các số đo huyết áp gần đây và tên thuốc bạn đang dùng là gì?"],
            "https://www.nhs.uk/conditions/high-blood-pressure-hypertension/")
    if re.search(r"\b(?:cuc|khoi|hach)\b.{0,25}\bco\b", n) and "ung thu" in n:
        return _guidance("Cần khám để đánh giá khối ở cổ",
            "Khối ở cổ có nhiều nguyên nhân, như hạch phản ứng, nang hoặc bệnh tuyến giáp; không thể xác định có phải ung thư qua tin nhắn.",
            ["Đi khám để được đánh giá trực tiếp, nhất là khi khối to lên, cứng, khó di động hoặc kéo dài hơn hai tuần.",
             "Nếu khó thở hoặc nuốt rất khó, cần đánh giá cấp cứu ngay."],
            ["Khối xuất hiện bao lâu, có đau hoặc to lên không; có sốt, sụt cân hay khó nuốt không?"],
            "https://www.nhs.uk/symptoms/lumps/")
    if "anh" in n and "vet thuong" in n and any(x in n for x in ("khang dinh", "nhiem trung")):
        return _guidance("Ảnh không đủ để xác nhận nhiễm trùng",
            "Không thể khẳng định vết thương nhiễm trùng chỉ từ lời mô tả hoặc ảnh. Chưa có đánh giá trực tiếp về độ sâu, đau, nhiệt độ vùng da và triệu chứng toàn thân.",
            ["Đi khám nếu đỏ, sưng, nóng, đau tăng, chảy mủ hoặc sốt; cần đánh giá sớm nếu vết thương sâu, do cắn hoặc bẩn.",
             "Giữ vết thương sạch và che bằng băng sạch trong lúc chờ đánh giá."],
            ["Vết thương do đâu, xuất hiện khi nào; có sốt, đỏ lan, đau tăng hoặc mủ không?"],
            "https://www.nhs.uk/conditions/cuts-and-grazes/")
    if any(x in n for x in ("chac chan 100", "chac chan toi mac", "khang dinh toi mac")):
        return _guidance("Cần dữ kiện để đánh giá nguyên nhân",
            "Không thể khẳng định chẩn đoán với độ chắc chắn tuyệt đối qua hội thoại. Cần mô tả triệu chứng, khám và đôi khi xét nghiệm để phân biệt các nguyên nhân.",
            ["Mô tả triệu chứng hiện tại, thời điểm bắt đầu và mức độ; đi khám nếu kéo dài, tăng lên hoặc có dấu hiệu cảnh báo."],
            ["Triệu chứng chính hiện tại của bạn là gì và bắt đầu lúc nào?"],
            "https://www.nhs.uk/symptoms/")
    return nutrition_guidance(text)


def nutrition_guidance(text: str) -> dict | None:
    normalized = normalize_search_text(text)
    if not ("tang co" in normalized and any(x in normalized for x in ("an", "dinh duong", "protein"))):
        return None
    return {
        "title": "Ăn uống và tập luyện để hỗ trợ tăng cơ",
        "summary": "Ăn đủ và đa dạng, kết hợp tập sức mạnh tăng dần là nền tảng hỗ trợ tăng cơ. "
                   "Chưa đủ thông tin về mức vận động, khẩu phần và bệnh nền để xác định nhu cầu năng lượng hay protein riêng cho bạn.",
        "next_steps": [
            "Duy trì bữa ăn đều đặn; bổ sung nguồn protein như cá, trứng, thịt nạc, sữa hoặc đậu trong các bữa.",
            "Ăn đa dạng rau, trái cây và thực phẩm giàu tinh bột, ưu tiên ngũ cốc nguyên hạt; uống đủ nước.",
            "Kết hợp tập sức mạnh phù hợp, tăng tải từ từ và dành thời gian nghỉ phục hồi; theo dõi sức mạnh và khả năng hồi phục.",
            "Trao đổi với chuyên gia dinh dưỡng nếu cần khẩu phần cụ thể hoặc có bệnh thận, bệnh gan hay tình trạng sức khỏe ảnh hưởng chế độ ăn.",
        ],
        "questions": ["Bạn tập sức mạnh bao nhiêu buổi mỗi tuần và thường ăn gì trong một ngày?",
                      "Bạn có bệnh nền hoặc hạn chế thực phẩm nào cần lưu ý không?"],
        "limitations": "Đây là thông tin giáo dục chung, không thay thế đánh giá và kế hoạch dinh dưỡng cá nhân của chuyên gia.",
        "intent": "general",
        "references": ["https://www.nhs.uk/live-well/eat-well/food-guidelines-and-food-labels/the-eatwell-guide/"],
    }
