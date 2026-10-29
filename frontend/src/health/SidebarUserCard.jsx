import { useEffect, useRef, useState } from 'react';
import {
  BadgeCheck,
  HeartPulse,
  LogIn,
  LogOut,
  MoreHorizontal,
  Settings,
  Shield,
  ShieldCheck,
  Sparkles,
  UserRound,
  WalletCards,
} from 'lucide-react';

export function SidebarUserCard({
  context = {},
  account = null,
  isGuest = false,
  onOpenProfile,
  onSettings,
  onLogout,
  onRequireAuth,
  onNavigate,
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const cardRef = useRef(null);

  useEffect(() => {
    if (!menuOpen) return;
    const handleClickOutside = (e) => {
      if (cardRef.current && !cardRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    };
    const handleKey = (e) => {
      if (e.key === 'Escape') setMenuOpen(false);
    };
    document.addEventListener('pointerdown', handleClickOutside);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('pointerdown', handleClickOutside);
      document.removeEventListener('keydown', handleKey);
    };
  }, [menuOpen]);

  const displayName =
    context?.display_name ||
    account?.name ||
    account?.email?.split('@')[0] ||
    (isGuest ? 'Khách lâm sàng' : 'Người dùng MedGuard');

  const userInitials = (displayName || 'MG')
    .trim()
    .split(/\s+/)
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  const hasBhyt = Boolean(context?.bhyt_number);
  const hasVssId = Boolean(context?.bhxh_number);

  return (
    <div className="sidebar-user-section" ref={cardRef}>
      {menuOpen && (
        <div className="sidebar-user-popover-menu" role="menu" aria-label="Menu người dùng">
          <div className="popover-user-brief">
            <div className="brief-avatar">{userInitials}</div>
            <div className="brief-info">
              <strong className="brief-name">{displayName}</strong>
              <span className="brief-sub">
                {account?.email || (isGuest ? 'Phiên dùng thử ẩn danh' : 'Hồ sơ sức khỏe cá nhân')}
              </span>
              {hasBhyt && (
                <div className="brief-verified-badge" title="Thẻ BHYT đã liên kết">
                  <ShieldCheck size={11} />
                  <span>BHYT: {context.bhyt_number}</span>
                </div>
              )}
            </div>
          </div>

          <div className="popover-menu-divider" />

          <button
            type="button"
            className="popover-menu-item highlight"
            role="menuitem"
            onClick={() => {
              setMenuOpen(false);
              onOpenProfile?.();
            }}
          >
            <UserRound size={16} />
            <div className="menu-item-text">
              <strong>Hồ sơ cá nhân & Bảo hiểm</strong>
              <small>BHYT, VssID, Nhân thọ & Thể chất</small>
            </div>
            {hasBhyt ? (
              <span className="item-pill verified">Đã xác thực</span>
            ) : (
              <span className="item-pill action">Cập nhật</span>
            )}
          </button>

          <button
            type="button"
            className="popover-menu-item"
            role="menuitem"
            onClick={() => {
              setMenuOpen(false);
              onNavigate?.('health');
            }}
          >
            <HeartPulse size={16} />
            <div className="menu-item-text">
              <strong>Digital Twin cơ thể</strong>
              <small>Mô phỏng 9 cơ quan & chỉ số sinh tồn</small>
            </div>
          </button>

          <button
            type="button"
            className="popover-menu-item"
            role="menuitem"
            onClick={() => {
              setMenuOpen(false);
              onNavigate?.('spending');
            }}
          >
            <WalletCards size={16} />
            <div className="menu-item-text">
              <strong>Chi tiêu Y tế & Care Saver</strong>
              <small>Hạn mức BHYT & Đặt khám</small>
            </div>
          </button>

          <button
            type="button"
            className="popover-menu-item"
            role="menuitem"
            onClick={() => {
              setMenuOpen(false);
              onSettings?.();
            }}
          >
            <Settings size={16} />
            <div className="menu-item-text">
              <strong>Cài đặt hệ thống</strong>
              <small>Tùy chọn hiển thị, giọng đọc & dữ liệu</small>
            </div>
          </button>

          <div className="popover-menu-divider" />

          {account ? (
            <button
              type="button"
              className="popover-menu-item danger"
              role="menuitem"
              onClick={() => {
                setMenuOpen(false);
                onLogout?.();
              }}
            >
              <LogOut size={16} />
              <div className="menu-item-text">
                <strong>Đăng xuất</strong>
                <small>{account.email}</small>
              </div>
            </button>
          ) : (
            <button
              type="button"
              className="popover-menu-item auth-btn"
              role="menuitem"
              onClick={() => {
                setMenuOpen(false);
                onRequireAuth?.();
              }}
            >
              <LogIn size={16} />
              <div className="menu-item-text">
                <strong>Đăng nhập / Đăng ký</strong>
                <small>Lưu đồng bộ hồ sơ trên đám mây</small>
              </div>
            </button>
          )}
        </div>
      )}

      <button
        type="button"
        className={`sidebar-user-card-btn ${menuOpen ? 'menu-active' : ''}`}
        aria-haspopup="true"
        aria-expanded={menuOpen}
        onClick={() => setMenuOpen(!menuOpen)}
        title="Tài khoản & Hồ sơ cá nhân"
      >
        <div className="user-avatar-container">
          <div className="user-avatar-circle">{userInitials}</div>
          <span className={`user-status-dot ${hasBhyt ? 'verified' : 'active'}`} />
        </div>

        <div className="user-card-meta">
          <strong className="user-card-name">{displayName}</strong>
          <span className="user-card-role">
            {hasBhyt ? (
              <>
                <ShieldCheck size={11} className="role-icon-verified" />
                <span>BHYT {context.bhyt_rate || 80}%</span>
              </>
            ) : hasVssId ? (
              <>
                <BadgeCheck size={11} className="role-icon-vssid" />
                <span>VssID điện tử</span>
              </>
            ) : isGuest ? (
              <span className="guest-badge-pill">Khách trải nghiệm</span>
            ) : (
              <span>Thành viên MedGuard</span>
            )}
          </span>
        </div>

        <MoreHorizontal size={16} className="user-card-more-icon" />
      </button>
    </div>
  );
}
