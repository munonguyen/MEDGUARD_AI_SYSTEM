# Quyền soạn câu trả lời

2026-10-03. Luồng hiện có: dữ kiện/bối cảnh và safety floor → Researcher lấy nguồn → Writer soạn → Reviewer phản biện/sửa/từ chối → kiểm tra an toàn cục bộ → xuất.

Lỗi: narrative được agent duyệt vẫn bị giấu sau summary/action mẫu trên UI. Sửa: verification_status=verified và answer_origin=gateway_verified thì narrative là nội dung chính, API reply cũng trả narrative. Không lọc mất đoạn hỏi thêm của agent. Audit projection phản ánh UI. Khi agent thiếu cấu hình/lỗi/từ chối, UI công khai chưa hoàn tất thẩm định, nội dung là hướng dẫn dự phòng. Fallback không mang nhãn verified.

Runtime: enforced, sync, coverage=all nhưng gateway/Writer provider/Reviewer provider chưa cấu hình. Kiểm thử provider và UI mô phỏng chỉ chứng minh hợp đồng, không phải bằng chứng mô hình thực hay phê duyệt lâm sàng. Chưa sửa quyền quyết định mức độ nguy hiểm của safety floor. Chưa áp dụng chính sách chặn toàn bộ hướng dẫn dự phòng ở API. Production vẫn cần gateway thật, đánh giá chuỗi agent và clinical/operational evidence.
