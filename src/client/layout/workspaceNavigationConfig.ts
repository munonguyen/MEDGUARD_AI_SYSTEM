// File: src/client/layout/workspaceNavigationConfig.ts

export interface WorkspaceRoutePolicy {
  id: 'chat' | 'navigation' | 'health' | 'companion' | 'appointments' | 'medications' | 'expenses' | 'profile';
  label: string;
  requiresAuth: boolean;
  authGateTitle?: string;
  authGateDescription?: string;
  authGateBullets?: string[];
}

/**
 * Nguồn cấu hình duy nhất (Single Source of Truth) cho cả Sidebar và AuthGate:
 * Đảm bảo tab nào có requiresAuth = true thì hiện icon 🔒 trên Sidebar và hiển thị đúng mô tả của tab đó.
 */
export const WORKSPACE_ROUTE_POLICIES: WorkspaceRoutePolicy[] = [
  {
    id: 'chat',
    label: 'Hội thoại Lâm sàng',
    requiresAuth: false
  },
  {
    id: 'companion',
    label: 'Bác sĩ 3D Live',
    requiresAuth: false
  },
  {
    id: 'navigation',
    label: 'Chỉ đường & Cấp cứu GPP',
    requiresAuth: false
  },
  {
    id: 'health',
    label: 'Cơ thể & Sức khoẻ',
    requiresAuth: true,
    authGateTitle: 'Hồ Sơ Cơ Thể 3D & Thống Kê Sức Khoẻ Đa Biểu Đồ chỉ dành cho Thành viên đã Đăng nhập',
    authGateDescription:
      'Lưu trữ đồng bộ biểu đồ sức khoẻ theo đợt (Giờ / Ngày / Tuần / Tháng) và bản đồ 9 cơ quan giải phẫu của riêng bạn.',
    authGateBullets: [
      'Biểu đồ Radar 6 chiều & Thống kê sức khoẻ theo từng Đợt',
      'Tự động cập nhật triệu chứng đã xác thực từ khung Chat'
    ]
  },
  {
    id: 'appointments',
    label: 'Lịch khám bác sĩ',
    requiresAuth: true,
    authGateTitle: 'Quản Lý Lịch Khám & Đặt Hẹn Chuyên Khoa chỉ dành cho Thành viên đã Đăng nhập',
    authGateDescription:
      'Đồng bộ lịch hẹn khám chuyên khoa, nhắc lịch tái khám định kỳ và lưu trữ phiếu khám lâm sàng bảo mật.',
    authGateBullets: [
      'Đặt lịch khám đúng chuyên khoa theo kết quả phân luồng',
      'Nhắc lịch tái khám và chuẩn bị hồ sơ xét nghiệm trước buổi khám'
    ]
  },
  {
    id: 'medications',
    label: 'Lịch uống thuốc',
    requiresAuth: true,
    authGateTitle: 'Thời Khóa Biểu Nhắc Thuốc & Kiểm Soát Tương Tác Dược dành cho Thành viên đã Đăng nhập',
    authGateDescription:
      'Thiết lập lịch nhắc uống thuốc theo ca (Sáng / Trưa / Tối) đã được kiểm tra tương tác thuốc an toàn.',
    authGateBullets: [
      'Cảnh báo tương tác thuốc tự động trước khi thêm vào tủ thuốc cá nhân',
      'Theo dõi tỷ lệ tuân thủ điều trị cho người cao tuổi và bệnh mạn tính'
    ]
  },
  {
    id: 'expenses',
    label: 'Chi tiêu & BHYT',
    requiresAuth: true,
    authGateTitle: 'Sổ Quản Lý Chi Tiêu Y Tế & Tối Ưu Quyền Lợi BHYT dành cho Thành viên đã Đăng nhập',
    authGateDescription:
      'Theo dõi chi phí khám chữa bệnh, ước tính mức hưởng BHYT đúng tuyến và đối sánh giá thuốc công bố Cục Quản lý Dược.',
    authGateBullets: [
      'Phân tích chi phí y tế thực tế và quyền lợi đồng chi trả BHYT',
      'Đối sánh giá trần thuốc kê đơn minh bạch'
    ]
  },
  {
    id: 'profile',
    label: 'Hồ sơ & Bảo hiểm',
    requiresAuth: true, // Khóa bảo mật trang chứa CCCD, SĐT, mã thẻ BHYT trong chế độ Khách!
    authGateTitle: 'Hồ Sơ Định Danh Bệnh Nhân & Thẻ BHYT được Bảo mật chuẩn HIPAA',
    authGateDescription:
      'Thông tin định danh cá nhân (CCCD, mã số BHYT, tiền sử dị ứng thuốc và liên hệ khẩn cấp) yêu cầu xác thực tài khoản.',
    authGateBullets: [
      'Mã hóa AES-256 cho thông tin định danh và thẻ BHYT',
      'Tự động áp dụng chiều cao, cân nặng và tiền sử dị ứng khi kiểm tra đơn thuốc'
    ]
  }
];
