import { Lock, ShieldCheck, BarChart2, HeartPulse, WalletCards, ArrowLeft, LogIn, Sparkles, CheckCircle2 } from 'lucide-react';

export function DataManagementAuthGate({
  moduleTitle = 'Hồ Sơ Sức Khoẻ & Giải Phẫu Thời Gian Thực',
  moduleType = 'health',
  onRequireAuth,
  onBackToChat,
}) {
  const isSpending = moduleType === 'spending';

  return (
    <div className="dm-auth-gate-shell" data-testid="data-management-auth-gate">
      <div className="dm-auth-gate-card">
        <div className="dm-auth-badge-row">
          <span className="dm-auth-security-pill">
            <Lock size={13} />
            <span>PHÂN QUYỀN BẢO MẬT DỮ LIỆU CÁ NHÂN • YÊU CẦU ĐĂNG NHẬP</span>
          </span>
          <span className="dm-auth-hipaa-tag">
            <ShieldCheck size={13} />
            <span>Chuẩn Bảo Mật Hồ Sơ Lâm Sàng</span>
          </span>
        </div>

        <div className="dm-auth-hero-grid">
          <div className="dm-auth-left">
            <div className="dm-auth-icon-circle">
              {isSpending ? <WalletCards size={28} /> : <HeartPulse size={28} />}
            </div>
            <h2 className="dm-auth-title">
              {moduleTitle} chỉ dành cho Thành viên đã Đăng nhập
            </h2>
            <p className="dm-auth-subtitle">
              Để bảo vệ quyền riêng tư y tế và lưu trữ đồng bộ biểu đồ sức khoẻ theo đợt (Giờ / Ngày / Tuần / Tháng), bản đồ 9 cơ quan giải phẫu cũng như sổ quản lý chi tiêu BHYT của riêng bạn, hệ thống phân quyền chỉ cho phép <strong>tài khoản đã xác thực</strong> truy cập trang quản lý dữ liệu này.
            </p>

            <div className="dm-auth-feature-pills">
              <div className="dm-feat-item">
                <CheckCircle2 size={15} />
                <span>Biểu đồ Radar 6 chiều & Thống kê sức khoẻ theo từng Đợt</span>
              </div>
              <div className="dm-feat-item">
                <CheckCircle2 size={15} />
                <span>Tự động cập nhật mọi triệu chứng & cảm giác từ khung Chat</span>
              </div>
              <div className="dm-feat-item">
                <CheckCircle2 size={15} />
                <span>Quản trị chi phí y tế, BHYT & Đối sánh giá trần Cục Dược DAV</span>
              </div>
            </div>

            <div className="dm-auth-actions-row">
              <button
                type="button"
                className="dm-auth-primary-btn"
                onClick={() => {
                  if (typeof onRequireAuth === 'function') {
                    onRequireAuth();
                  } else {
                    try {
                      localStorage.removeItem('medguard.guest_mode');
                    } catch {}
                    window.location.href = '/?login=1';
                  }
                }}
              >
                <LogIn size={17} />
                <span>Đăng nhập / Tạo tài khoản để Mở khóa ngay</span>
              </button>

              {onBackToChat && (
                <button
                  type="button"
                  className="dm-auth-secondary-btn"
                  onClick={onBackToChat}
                >
                  <ArrowLeft size={16} />
                  <span>Quay lại Phòng Hội thoại Dùng thử</span>
                </button>
              )}
            </div>
          </div>

          {/* Visual Preview of Multi-Chart Suite (Locked Preview) */}
          <div className="dm-auth-preview-col" aria-hidden="true">
            <div className="dm-preview-header">
              <BarChart2 size={15} />
              <span>Xem trước Giao diện Đa Biểu Đồ Trực Quan (Đã khoá bảo mật)</span>
            </div>
            <div className="dm-preview-charts-grid">
              <div className="dm-mini-chart-box">
                <span className="dm-mini-label">Radar Thể Trạng 6 Chiều</span>
                <svg viewBox="0 0 100 80" className="dm-mini-svg">
                  <polygon points="50,10 82,28 82,58 50,74 18,58 18,28" fill="rgba(13,148,136,0.12)" stroke="#0d9488" strokeWidth="2" />
                  <polygon points="50,22 70,34 70,52 50,62 30,52 30,34" fill="none" stroke="#cbd5e1" strokeDasharray="2 2" />
                </svg>
              </div>
              <div className="dm-mini-chart-box">
                <span className="dm-mini-label">Biểu Đồ Theo Đợt (Giờ/Ngày/Tuần)</span>
                <svg viewBox="0 0 100 80" className="dm-mini-svg">
                  <path d="M8,62 Q30,55 48,38 T92,18" fill="none" stroke="#2563eb" strokeWidth="2.5" />
                  <rect x="14" y="46" width="10" height="22" rx="3" fill="#93c5fd" />
                  <rect x="34" y="36" width="10" height="32" rx="3" fill="#60a5fa" />
                  <rect x="54" y="26" width="10" height="42" rx="3" fill="#3b82f6" />
                  <rect x="74" y="16" width="10" height="52" rx="3" fill="#0d9488" />
                </svg>
              </div>
              <div className="dm-mini-chart-box">
                <span className="dm-mini-label">Phân Bổ 9 Cơ Quan & Sinh Hiệu</span>
                <div className="dm-mini-bars">
                  <div className="dm-bar-line"><span style={{ width: '92%', background: '#0d9488' }} /></div>
                  <div className="dm-bar-line"><span style={{ width: '78%', background: '#2563eb' }} /></div>
                  <div className="dm-bar-line"><span style={{ width: '64%', background: '#d97706' }} /></div>
                </div>
              </div>
              <div className="dm-mini-chart-box">
                <span className="dm-mini-label">Cơ Cấu Chi Tiêu & Quỹ BHYT</span>
                <svg viewBox="0 0 100 80" className="dm-mini-svg">
                  <circle cx="50" cy="40" r="24" fill="none" stroke="#e2e8f0" strokeWidth="10" />
                  <circle cx="50" cy="40" r="24" fill="none" stroke="#0d9488" strokeWidth="10" strokeDasharray="90 65" transform="rotate(-90 50 40)" />
                  <circle cx="50" cy="40" r="24" fill="none" stroke="#2563eb" strokeWidth="10" strokeDasharray="45 110" strokeDashoffset="-90" transform="rotate(-90 50 40)" />
                </svg>
              </div>
            </div>
            <div className="dm-preview-lock-overlay">
              <Sparkles size={14} />
              <span>Đăng nhập để mở khoá toàn bộ biểu đồ tương tác thời gian thực</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
