/**
 * Single Source of Truth for Workspace Navigation and Auth-Gate Policies.
 * Ensures consistent lock tags in Sidebar and dynamic, accurate messaging in DataManagementAuthGate.
 */

export const WORKSPACE_ROUTE_POLICIES = {
  chat: {
    id: 'chat',
    label: 'Hội thoại Lâm sàng',
    requiresAuth: false,
  },
  companion: {
    id: 'companion',
    label: 'Bác sĩ 3D Live',
    requiresAuth: false,
  },
  navigation: {
    id: 'navigation',
    label: 'Bản đồ Cấp cứu, Tìm Thuốc & Google Places',
    requiresAuth: false,
  },
  health: {
    id: 'health',
    label: 'Cơ thể & Sức khoẻ',
    requiresAuth: true,
    authGateTitle: 'Hồ Sơ Cơ Thể 3D & Thống Kê Sức Khoẻ Đa Biểu Đồ',
    authGateDescription:
      'Lưu trữ đồng bộ biểu đồ sức khoẻ theo đợt (Giờ / Ngày / Tuần / Tháng) và bản đồ 9 cơ quan giải phẫu của riêng bạn.',
    authGateBullets: [
      'Biểu đồ Radar 6 chiều & Thống kê sức khoẻ theo từng Đợt',
      'Tự động cập nhật triệu chứng đã xác thực từ khung Chat',
      'Cảnh báo sớm phản ứng phụ của thuốc (ADR) và tương tác bất lợi',
    ],
  },
  schedule: {
    id: 'schedule',
    label: 'Lịch khám bác sĩ',
    requiresAuth: true,
    authGateTitle: 'Quản Lý Lịch Khám & Đặt Hẹn Chuyên Khoa',
    authGateDescription:
      'Đồng bộ lịch hẹn khám chuyên khoa, nhắc lịch tái khám định kỳ và lưu trữ phiếu khám lâm sàng bảo mật.',
    authGateBullets: [
      'Đặt lịch khám đúng chuyên khoa theo kết quả phân luồng',
      'Nhắc lịch tái khám và chuẩn bị hồ sơ xét nghiệm trước buổi khám',
      'Lưu trữ hồ sơ chẩn đoán của bác sĩ điều trị',
    ],
  },
  medication: {
    id: 'medication',
    label: 'Lịch uống thuốc',
    requiresAuth: true,
    authGateTitle: 'Thời Khóa Biểu Nhắc Thuốc & Kiểm Soát Tương Tác Dược',
    authGateDescription:
      'Thiết lập lịch nhắc uống thuốc theo ca (Sáng / Trưa / Tối) đã được kiểm tra tương tác thuốc an toàn.',
    authGateBullets: [
      'Cảnh báo tương tác thuốc tự động trước khi thêm vào tủ thuốc cá nhân',
      'Theo dõi tỷ lệ tuân thủ điều trị cho người cao tuổi và bệnh mạn tính',
      'Tự động tích hợp đơn thuốc điện tử từ mã QR đơn thuốc',
    ],
  },
  spending: {
    id: 'spending',
    label: 'Chi tiêu & BHYT',
    requiresAuth: true,
    authGateTitle: 'Sổ Quản Lý Chi Tiêu Y Tế & Tối Ưu Quyền Lợi BHYT',
    authGateDescription:
      'Theo dõi chi phí khám chữa bệnh, ước tính mức hưởng BHYT đúng tuyến và đối sánh giá thuốc công bố Cục Quản lý Dược.',
    authGateBullets: [
      'Phân tích chi phí y tế thực tế và quyền lợi đồng chi trả BHYT',
      'Đối sánh giá trần thuốc kê đơn minh bạch theo DAV',
      'Phát hiện lãng phí và gợi ý nhóm thuốc Generic tương đương sinh học',
    ],
  },
  profile: {
    id: 'profile',
    label: 'Hồ sơ & Bảo hiểm',
    requiresAuth: true,
    authGateTitle: 'Hồ Sơ Định Danh Bệnh Nhân & Thẻ BHYT được Bảo mật chuẩn HIPAA',
    authGateDescription:
      'Thông tin định danh cá nhân (CCCD, mã số BHYT, tiền sử dị ứng thuốc và liên hệ khẩn cấp) yêu cầu xác thực tài khoản.',
    authGateBullets: [
      'Mã hóa AES-256 cho thông tin định danh và thẻ BHYT',
      'Tự động áp dụng chiều cao, cân nặng và tiền sử dị ứng khi kiểm tra đơn thuốc',
      'Bảo vệ quyền riêng tư y tế chống rò rỉ dữ liệu phiên khách',
    ],
  },
};
