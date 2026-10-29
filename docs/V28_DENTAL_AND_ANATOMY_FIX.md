# Đau răng và lỗi mất nghĩa khi bỏ dấu

Ngày: 2026-10-03. Hai câu người dùng đã tái hiện trên API thực:

- `Tôi đang đau răng,cần có cách nào để hết đau răng`: bộ sửa lỗi sau bỏ dấu đổi `can co` (cần có) thành `cang co`, làm chọn hướng dẫn căng cơ.
- `tôi đang đâu cơ`: `cơ` và `cổ` cùng thành `co`; bộ chọn mẫu lấy hướng dẫn cổ vai gáy dù chưa có vị trí cổ.

## Sửa

Bỏ phép sửa `can co` vì là câu tiếng Việt hợp lệ. Giữ sửa teencode không mơ hồ như `kăng kơ`. Bộ chọn hướng dẫn giữ bằng chứng vị trí từ văn bản gốc. Đau cơ chưa xác định vị trí (hoặc `dau co` không dấu, còn mơ hồ) nhận câu hỏi làm rõ, không suy diễn cổ hay thoái hóa. Cụm `cơn đau có kèm...` không được biến thành đau cơ. Đau cổ thực sự vẫn dùng hướng dẫn cổ; đau cơ có bối cảnh tập nặng vẫn qua bộ lập luận bối cảnh.

Thêm hướng dẫn đau răng có nguồn NHS, giảm đau tạm thời, khám nha sĩ và cảnh báo sưng vùng mắt/cổ, khó thở/nuốt/nói. Không chẩn đoán nguyên nhân, không kê kháng sinh/liều thuốc từ dữ kiện thiếu. Nguồn được gắn vào câu trả lời và trace; trạng thái phê duyệt vẫn pending_review. Hướng dẫn không thay đổi hoặc hạ mức cảnh báo của bộ triage.

Nguồn: https://www.nhs.uk/symptoms/toothache/ (đọc 2026-10-03).

## Xác minh

Kiểm thử API cho nguyên văn người dùng, biến thể không dấu/nhức răng, phủ định, đau cổ thật, `đau có kèm...` và đau răng kèm khó thở. Kiểm thử trình duyệt bổ sung đau răng/đau cơ trên desktop và mobile, đo văn bản DOM thực, xác minh không có RICE/thoái hóa cổ/gối khi không đúng chủ đề, giữ nguồn NHS. Báo cáo đầu ra và production evidence cần sinh lại đúng commit; kết quả hồi quy không thay thế phê duyệt lâm sàng độc lập.
