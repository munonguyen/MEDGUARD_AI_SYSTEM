import {
  Check,
  CheckCircle2,
  CreditCard,
  Droplet,
  ExternalLink,
  MapPin,
  Pill,
  Scale,
  ShieldCheck,
  Sparkles,
  UserRound,
  X,
  XCircle,
  AlertTriangle,
  BadgeCheck,
  CalendarDays,
  Phone,
  Activity
} from 'lucide-react';

const ICON_MAP = {
  UserRound,
  CalendarDays,
  UserCheck: ShieldCheck,
  Scale,
  Droplet,
  Phone,
  CreditCard,
  BadgeCheck,
  ShieldCheck,
  AlertTriangle,
  Activity,
  Pill,
  MapPin,
};

export function ProfileUpdateConfirmationCard({
  proposal,
  status = 'pending',
  onAccept,
  onDecline,
  onOpenProfile,
  autoSubmit = false,
  onToggleAutoSubmit,
}) {
  if (!proposal) return null;

  return (
    <div className={`chat-profile-proposal-card status-${status}`} role="region" aria-label="Xác nhận cập nhật hồ sơ cá nhân">
      <div className="proposal-card-header">
        <div className="header-left">
          <div className="shield-icon-badge">
            <ShieldCheck size={18} />
          </div>
          <div className="header-text-block">
            <strong>Đề xuất cập nhật Hồ sơ & Bảo hiểm cá nhân</strong>
            <span>Phát hiện thông tin do bạn tự cung cấp trong tin nhắn</span>
          </div>
        </div>
        <div className="header-badge">
          {status === 'accepted' ? (
            <span className="badge-tag accepted">
              <Check size={12} /> Đã cập nhật
            </span>
          ) : status === 'declined' ? (
            <span className="badge-tag declined">
              <X size={12} /> Đã từ chối
            </span>
          ) : (
            <span className="badge-tag pending">
              <Sparkles size={12} /> Chờ bạn xác nhận
            </span>
          )}
        </div>
      </div>

      <div className="proposal-fields-summary">
        <p className="summary-title">MedGuard AI đã ghi nhận các thông tin sau:</p>
        <div className="proposal-items-grid">
          {proposal.previewItems?.map((item, idx) => {
            const Icon = ICON_MAP[item.icon] || ShieldCheck;
            return (
              <div className={`proposal-item-pill ${item.alert ? 'alert' : ''} ${item.verified ? 'verified' : ''}`} key={idx}>
                <div className="item-icon-box">
                  <Icon size={14} />
                </div>
                <div className="item-content-box">
                  <span className="item-label">{item.label}</span>
                  <strong className="item-val" style={item.color ? { color: item.color } : {}}>
                    {item.value}
                  </strong>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {status === 'accepted' ? (
        <div className="proposal-status-banner accepted-banner">
          <CheckCircle2 size={16} className="status-banner-icon" />
          <div className="banner-text">
            <strong>Đã cập nhật thành công vào Hồ sơ y tế cá nhân!</strong>
            <span>Các chỉ số đã được đồng bộ với Digital Twin cơ thể và Trung tâm chi tiêu Care.</span>
          </div>
          {onOpenProfile && (
            <button type="button" className="btn-view-profile" onClick={onOpenProfile}>
              <span>Xem Hồ sơ</span>
              <ExternalLink size={13} />
            </button>
          )}
        </div>
      ) : status === 'declined' ? (
        <div className="proposal-status-banner declined-banner">
          <XCircle size={16} className="status-banner-icon" />
          <div className="banner-text">
            <strong>Bạn đã từ chối cập nhật thông tin.</strong>
            <span>Hồ sơ cá nhân của bạn được giữ nguyên trạng thái ban đầu mà không có bất kỳ thay đổi nào.</span>
          </div>
        </div>
      ) : (
        <div className="proposal-actions-area">
          <p className="prompt-confirm-text">
            Bạn có cho phép hệ thống tự động cập nhật các thông tin trên vào Hồ sơ cá nhân của bạn không?
          </p>
          <div className="proposal-auto-submit-row" style={{ marginBottom: 10, display: 'flex', alignItems: 'center' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 7, cursor: 'pointer', fontSize: '12px', color: '#475569', userSelect: 'none' }}>
              <input
                type="checkbox"
                checked={autoSubmit}
                onChange={(e) => onToggleAutoSubmit?.(e.target.checked)}
                style={{ width: '15px', height: '15px', accentColor: '#0d9488', cursor: 'pointer' }}
              />
              <span><strong>Tự động áp dụng cho các lần sau</strong> (Không cần hỏi lại khi phát hiện thông tin tương tự)</span>
            </label>
          </div>
          <div className="proposal-buttons-row">
            <button
              type="button"
              className="proposal-btn accept-btn"
              onClick={() => onAccept(proposal)}
            >
              <Check size={16} />
              <span>Cho phép cập nhật</span>
            </button>
            <button
              type="button"
              className="proposal-btn decline-btn"
              onClick={onDecline}
            >
              <X size={15} />
              <span>Từ chối</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
