# MedGuard: câu trả lời tập trung, chuẩn bị giọng sớm và chuyển động Unity/C#

## Kết luận từ mã và phép đo

Pipeline hiện tại đợi chat hoàn tất, sau đó gọi TTS và nhận hết MP3 rồi mới phát. Hàm TTS là bất đồng bộ, nhưng các giai đoạn giao tiếp đang nối tiếp. Chỉ nhìn thấy 14 giây chờ không đủ để kết luận toàn bộ backend là synchronous.

Một phép đo trực tiếp trong lần kiểm tra này, với câu chào tiếng Việt ngắn và `dr_tuan`, cho kết quả khoảng **8.739 giây tới chunk đầu / 9.313 giây tới toàn bộ audio**, 25.632 byte. Đây là một mẫu riêng lẻ, không phải p50/p95 hay thời gian chat đầu-cuối. Streaming MP3 đơn thuần không xoá được phần chờ trước chunk đầu.

Muốn nói ngay khi phân tích xong, cần có audio sẵn khi kết quả được duyệt. Nếu `Tdraft` là thời gian có bản nháp, `Treview` là thời gian kiểm tra và `Tvoice` là thời gian tạo câu đầu, thời điểm audio sẵn xấp xỉ:

`Tdraft + max(Treview, Tvoice) + network/decode`

Thời gian chờ thêm sau duyệt vẫn là `max(0, Tvoice - Treview) + network/decode`. Không có cơ sở hứa luôn bằng 0 với nhà cung cấp hiện tại. Nếu TTS vẫn chậm trước byte đầu, cần đo/reuse kết nối hoặc chuyển sang nhà cung cấp có first-byte latency tốt hơn; streaming SDK/preconnect là hướng đánh giá tiếp theo, chưa triển khai và chưa đo trong nhánh này.

## Thay đổi đã triển khai

1. Companion opt-in `voice.persona` trong `/v1/chat`. Sau Writer, C# hoặc frontend có thể nhận audio đã chuẩn bị khi toàn bộ kiểm duyệt hoàn tất. Backend bắt đầu tạo câu đầu tối đa 180 ký tự **trong khi Reviewer chạy**.
2. Chỉ câu cuối có `verification_status=verified` và câu đầu trùng chính xác mới nhận ticket. Bản nháp bị sửa/bị từ chối không được phát. Không stream token/âm thanh chưa qua kiểm tra trực tiếp cho người dùng.
3. Nếu TTS còn chạy, ticket lấy lại chính tác vụ đó qua GET `/v1/chat/speech/{ticket}`. Không khởi động lại một lần TTS mới sau chat. Ticket dùng một lần, xác thực tenant + consent, TTL 45 giây, tối đa 32 ticket và hai tác vụ chuẩn bị đồng thời. Audio/ticket không ghi vào lịch sử/idempotency; API không log nội dung câu hỏi hay audio.
4. Ticket được giữ trong RAM **của một process**. Khi chạy nhiều worker, cần session affinity hoặc thiết kế shared delivery phù hợp; request tới worker khác nhận 404 và fallback TTS. Không giả định cơ chế hiện tại có thể chia sẻ future qua Redis.
5. Backend tạo `spoken_reply` từ câu trả lời cuối. Không ghép thêm câu giống hệt chỉ khác hoa/thường hoặc khoảng trắng; giữ hướng dẫn, cảnh báo và các câu hỏi hiển thị đã được chọn. Không tóm tắt bằng cắt ký tự và không dùng fuzzy matching để xoá lời cảnh báo. Các câu trùng về ý nhưng khác cách diễn đạt vẫn cần Writer/Reviewer xử lý.
6. Prompt `focused` yêu cầu trả lời đúng mối quan tâm hiện tại ngay câu đầu, thường 80–160 từ, một hoặc hai đoạn, tối đa một câu hỏi quan trọng. Nội dung an toàn bắt buộc có ưu tiên cao hơn giới hạn độ dài. Không đưa thêm bệnh không liên quan hay tóm tắt lại cuộc trò chuyện. Đây là ràng buộc prompt; hiệu quả thực tế vẫn cần kiểm tra gateway đang hoạt động.
7. Frontend dùng ticket khi đúng persona/câu đầu, fallback một lần chỉ khi ticket mất/hết hạn; lỗi TTS không kéo thêm một lượt chờ đầy đủ. Audio rỗng hoặc response JSON bị từ chối. Lỗi tạo AudioContext hoặc khởi tạo lip-sync không chặn đường phát media thông thường.
8. Bộ mã Unity riêng xử lý trạng thái hội thoại, voice, idle chú ý, biểu cảm, viseme và cử chỉ đã kiểm duyệt. Xem `unity/README.md` để nhập/gắn rig. Chưa có scene/model/clip được chạy trong Unity và chưa thay avatar web bằng Unity build.

## Ngữ cảnh → hành động

Planner cần đọc **câu trả lời đã duyệt**, câu hỏi hiện tại và clinical envelope: ai gặp triệu chứng, có/không, hiện tại/quá khứ/giả định, mức khẩn cấp được xác nhận, câu hỏi kiến thức hay tình trạng thật, bước hướng dẫn và độ chắc chắn. Một từ khoá đơn lẻ không đủ để chọn cử chỉ.

| Bối cảnh | Hành động cho phép | Hành động phải chặn |
|---|---|---|
| Người dùng đang kể tình trạng | Gaze chú ý, chớp mắt, thở nhỏ | Tay giải thích theo tiếng nói người dùng; gật khẳng định |
| Thông tin còn thiếu | Hỏi rõ, bàn tay mở nhẹ khi có clip/cue phù hợp | Cử chỉ chắc chắn hoặc trấn an rằng không nguy hiểm |
| Giải thích một cơ chế | Một cung tay nhỏ ở ý chính, sau đó trả tay nghỉ | Mỗi câu đưa tay phải lên ngực |
| “Tôi không khó thở” | Giữ dấu hiệu ở trạng thái phủ định | Mặt hoảng hốt/cử chỉ cấp cứu từ chữ “khó thở” |
| “Nếu bị sốt thì…” | Giải thích tình huống giả định | Coi người dùng đang bị sốt |
| Câu hỏi kiến thức | Giải thích tập trung, mặt trung tính ấm | Biểu cảm đau/bệnh hoặc chuyển sang chẩn đoán |
| Người dùng lo lắng, affect được xác nhận | Quan tâm nhẹ, giọng bình tĩnh | Cười lớn, vẫy tay chào trong lời cảnh báo |
| Mức khẩn cấp đã được xác nhận | Hướng dẫn rõ trước, nhấn nhẹ | Chờ màn chào, động tác phô trương, trấn an hạ mức khẩn cấp |
| Hướng dẫn nhiều bước | Cử chỉ đếm đã được rig/clip duyệt | Xoay cả bàn tay cứng hoặc đếm không đúng số bước |
| Chỉ vị trí trên giao diện | Hướng gaze/tay tới mục tiêu nhìn thấy | Chỉ vào không khí hoặc sai bên cơ thể |
| Người dùng ngắt lời | Dừng audio/cue, chuyển về chú ý | Phát tiếp câu trước hay giật tay về bind pose |

32 nhóm / 64 biến thể nằm trong catalogue authoring. Chúng chưa phải animation assets. Bước tiếp theo bắt buộc để đánh giá tự nhiên là gắn clip và rig thật, không chỉ bổ sung enum hay anchor.

## Nghiệm thu

- Đo riêng end-of-user-speech → draft, draft → reviewer, TTS → first byte, approved answer → playback và user-end → first audio; báo p50/p95 từ nhiều lượt. Không dùng `text_ready` làm bằng chứng âm thanh đã phát.
- Duy trì kiểm thử safety/negation/hypothetical/current-episode khi thay prompt. Kiểm tra câu trả lời thực từ gateway, không chỉ deterministic fallback hoặc fake provider.
- Không đọc bản nháp bị từ chối, không giọng cũ sau cancel, không lẫn tenant/persona, không bỏ câu cảnh báo khi chia đoạn và không tuyên bố thành công khi không có audio.
- Kiểm tra Safari/iOS autoplay bằng thao tác người dùng, hai persona và nhiều lượt liên tiếp. Media clock tiến là bằng chứng phát media trong browser; không chứng minh thiết bị người dùng nghe thấy âm thanh.
- Chuyển động phải được xem trên video Unity có audio thật: nghe, nói, pause, ngắt lời, đổi bối cảnh và lỗi TTS. Compile bằng stub không phải kiểm chứng Animator/IK hay chất lượng hoạt ảnh.

Nguồn chính thức dùng để kiểm tra hướng kiến trúc: Unity Manual — Audio in Web; Unity Animation Rigging manual; Microsoft Speech SDK — lower synthesis latency. Các giới hạn nền tảng được dẫn ở `unity/README.md`.

## Kết quả kiểm tra của nhánh

- **120 kiểm tra backend PASS**: chat, TTS, agent Writer/Reviewer, voice preparation, độ dài/ngữ cảnh/quality gate/phủ định/tình huống giả định. Các kiểm tra agent dùng provider fixture; chúng không chứng minh chất lượng LLM triển khai thực tế.
- **4 nhóm kiểm tra Node PASS**: chia câu/queue, cancellation/API, canonical clinical reply và prepared speech. Frontend production build PASS; vẫn có cảnh báo bundle lớn từ Vite.
- **Browser regression PASS** trên hai VRM của web avatar hiện có: microphone, media playback, silence, cancel, persona switch, provider failure và layout mobile. Đây là kiểm tra web avatar cũ, không phải Unity.
- **Live TTS + browser PASS** với cả hai persona và hai lượt liên tiếp mỗi persona. Một mẫu first-media-playback: nam **9.837 giây**, nữ **9.279 giây**. Có MP3 thật, profile đúng và media clock tiến; môi trường headless không xác minh loa của thiết bị người dùng hay độ chính xác viseme tiếng Việt.
- Live status báo **AI gateway configured=false**. Vì vậy nhánh này chưa có phép đo end-to-end Writer/Reviewer thực hoặc bằng chứng câu trả lời LLM thật đã hết lan man. Cần cấu hình gateway để kiểm chứng phần đó; không dùng deterministic fallback để tuyên bố AI đã trả lời tốt.
- C# biên dịch qua Roslyn với Unity signature stubs và **24 kiểm tra logic PASS**. Unity Test Runner, scene, Animator, rig, clips, audio output và naturalness trên model thật **chưa được kiểm tra**.
- Tệp MOV người dùng gửi chưa tải được. Không có kết luận quan sát trực tiếp video trong báo cáo này.
