# MedGuard Doctor Motion System v3.0 (Unity C# Native)

Bộ mã nguồn C# và dữ liệu thiết kế tham chiếu điều khiển toàn bộ chuyển động tự nhiên cho avatar bác sĩ MedGuard trong Unity.

## Kiến trúc chính
1. **Clinical Context Analyzer (`DoctorContextAnalyzer.cs`)**: Phân tích câu hỏi bệnh nhân, nhận diện phủ định, giả định, người thứ ba và cảnh báo đỏ.
2. **Action Library (`DoctorActionLibrary.cs`)**: Quản lý 32 nhóm hành động với 64 biến thể cử chỉ có điều kiện kích hoạt và điều kiện cấm.
3. **Gesture Planner (`DoctorGesturePlanner.cs`)**: Lập kế hoạch 4 pha (Preparation, Stroke, Hold, Retraction) đồng bộ với âm thanh.
4. **Layered Animator & Inertial Blender (`DoctorLayeredAnimator.cs`, `DoctorInertialBlender.cs`)**: Ghép lớp chuyển động và làm mượt khử giật khi bị ngắt lời.
5. **Facial & Social Gaze (`DoctorEyeGazeController.cs`, `DoctorLipSyncDriver.cs`)**: Khớp khẩu hình tiếng Việt và ánh mắt giao tiếp tự nhiên.
6. **IK Anatomical Limiter (`DoctorIKLimiter.cs`)**: Giới hạn góc giải phẫu chống biến dạng rig.

## Cách sử dụng
- Kéo thả prefab bác sĩ (DoctorTuan hoặc DoctorMai).
- Gắn script `DoctorMotionController` lên GameObject gốc.
- Kết nối `DoctorConversationBridge` với MedGuard API Backend (`http://127.0.0.1:8000`).
