# Độ dài theo bối cảnh và điều kiện production

Ngày thực hiện: 2026-10-02. Đây là kiểm định engineering, không phải phê duyệt lâm sàng.

## Hành vi mới

- `brief`: chỉ áp dụng cho câu giáo dục chung đã có đáp án giới hạn, không có quyết định lâm sàng, hành động/cảnh báo/câu hỏi bắt buộc. Ví dụ câu hỏi ngủ sớm trả lời trực tiếp và nêu lợi ích; giờ ngủ cần phù hợp lịch sinh hoạt, ngủ đủ và đều đặn quan trọng hơn một mốc giờ cố định. Nguồn: CDC About Sleep, đọc ngày 2026-10-02.
- `focused`: trả lời trọng tâm, giữ hướng xử trí, cảnh báo và câu hỏi hữu ích ở phần chính. Giải thích cơ chế và khả năng bệnh được mở thêm. Với câu đau đầu nhẹ sau màn hình được nhận diện chính xác, phần chính giữ nghỉ ngơi, nghỉ mắt, mốc khám và toàn bộ safety-net; các bước chăm sóc tùy chọn còn ở phần chi tiết.
- `detailed`: yêu cầu giải thích chi tiết được giữ đầy đủ. Yêu cầu độ dài không thay đổi mức cấp cứu hay câu khuyến cáo bắt buộc.
- UI không cắt danh sách hành động/cảnh báo an toàn theo số mục cố định. Cảnh báo thuốc vẫn hiện trong phần chính. Toàn bộ response gốc và narrative được giữ để kiểm tra.
- Câu trả lời mới cuộn tới phần đầu; khi đang đọc lịch sử, polling không kéo người dùng xuống cuối. Kiểm thử trình duyệt kiểm tra vị trí của hành động cấp cứu trong viewport ban đầu.
- Prompt Writer nhận chế độ độ dài; các locked safety claims luôn ưu tiên hơn giới hạn từ.

## Các kết quả kỹ thuật

- 829 kiểm thử Python đạt; 1 cảnh báo deprecation Starlette/httpx. Các chỉnh sửa về metadata nguồn và render báo cáo sau lượt toàn bộ được kiểm tra lại bằng nhóm kiểm thử liên quan.
- Build frontend đạt. Chromium thật: 8 ca gồm ngủ sớm, giải thích giấc ngủ, đau đầu sau màn hình, cấp cứu, mỗi ca trên desktop và mobile. Đã mở phần chi tiết, kiểm tra tràn ngang và lỗi JavaScript.
- Độ dài phần chính: 59 từ cho ngủ sớm, 146 cho giải thích, 263 cho đau đầu nhẹ (trước tinh chỉnh: 433), 307 cho tình huống cấp cứu. Đây là số từ tách khoảng trắng trong các mục chính, không phải tokens hay điểm chất lượng y khoa.
- UI smoke tổng hợp và kiểm thử giữ vị trí đọc/cuộn đều PASS.

## Cổng phát hành

Release evidence schema 1.2.0 bổ sung `quality.public_output`. Cổng đọc từng response thật trong audit, yêu cầu tối thiểu 60 ca duy nhất, HTTP thành công, câu trả lời tồn tại, tất cả điều kiện nghiêm ngặt, hai ProfessionalResponseGate và hội đồng heuristic đạt. Cần đúng SHA ứng viên và không có thay đổi code chưa commit. Dòng summary PASS không thể che lỗi từng ca. Thiếu hoặc chưa đạt audit là blocker `public_output_quality`.

Các điều kiện cũ vẫn bắt buộc: bác sĩ độc lập duyệt, tri thức được ký duyệt, gateway Writer/Verifier thật, Postgres, hàng đợi/lưu trữ bền vững, rate limiting phân tán, secrets và consent đúng cấu hình, bằng chứng phục hồi dữ liệu và các kiểm định vận hành liên quan. Kiểm thử development và Chromium local không được dùng thay cho bằng chứng production này.

Không sửa nhãn 3 ca bất đồng urgency hoặc tạo phê duyệt bác sĩ để làm mọi chỉ số xanh. Chưa push/deploy khi còn release blockers. Báo cáo Q&A và manifest phải được sinh lại trên đúng commit của ứng viên phát hành.
