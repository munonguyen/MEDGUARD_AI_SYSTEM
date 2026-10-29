import { useState } from 'react';
import {
  ArrowUpRight,
  Check,
  CheckCircle2,
  DollarSign,
  ExternalLink,
  ShieldCheck,
  Sparkles,
  TrendingDown,
  Wallet,
  X,
} from 'lucide-react';

export function SpendingProposalCard({
  proposal,
  status = 'pending',
  onAccept,
  onDecline,
  onOpenSpending,
  autoSubmit = false,
  onToggleAutoSubmit,
}) {
  const [internalStatus, setInternalStatus] = useState(status);
  const [rememberAutoSubmit, setRememberAutoSubmit] = useState(autoSubmit);
  const tx = proposal?.spending;

  if (!tx) return null;

  const currentStatus = status !== 'pending' ? status : internalStatus;

  const handleAccept = () => {
    setInternalStatus('accepted');
    if (rememberAutoSubmit && onToggleAutoSubmit) {
      onToggleAutoSubmit(true);
    }
    onAccept?.(proposal);
  };

  const handleDecline = () => {
    setInternalStatus('declined');
    onDecline?.();
  };

  const amountDisplay = `${Math.abs(tx.amount_vnd).toLocaleString('vi-VN')} ₫`;
  const bhytDisplay = tx.bhyt_covered_vnd > 0 ? `${tx.bhyt_covered_vnd.toLocaleString('vi-VN')} ₫` : null;

  return (
    <div
      className={`chat-action-card spending-proposal-card ${currentStatus}`}
      role="region"
      aria-label="Đề xuất ghi nhận chi tiêu y tế"
    >
      <div className="card-header">
        <div className="card-header-icon spending-icon">
          <Wallet size={18} />
        </div>
        <div className="card-header-text">
          <div className="card-title-row">
            <div className="header-kicker-row">
              <span className="action-type-pill">Sổ Thu Chi Y Tế</span>
              <span className="module-name-tag">Tiết Kiệm & BHYT</span>
            </div>
            <strong className="card-main-title">Đề xuất Ghi nhận Chi phí Y tế</strong>
          </div>
          <span className="card-subtitle">
            Tự động phát hiện khoản chi y khoa trong cuộc trò chuyện
          </span>
        </div>
        <span className={`status-badge ${currentStatus}`}>
          {currentStatus === 'accepted' ? (
            <>
              <Check size={12} /> Đã lưu vào Sổ chi tiêu
            </>
          ) : currentStatus === 'declined' ? (
            'Đã bỏ qua'
          ) : (
            'Chờ xác nhận'
          )}
        </span>
      </div>

      <div className="card-body-content">
        <div className="card-details-grid">
          <div className="detail-item">
            <span className="detail-label">Khoản mục chi tiêu</span>
            <strong className="detail-value text-highlight spending-highlight">
              {tx.title}
            </strong>
          </div>

          <div className="detail-item">
            <span className="detail-label">Số tiền thực chi</span>
            <strong className="detail-value spending-amount">
              {amountDisplay}
            </strong>
          </div>

          <div className="detail-item">
            <span className="detail-label">Phân nhóm chi phí</span>
            <span className="detail-value">{tx.category_name || 'Thuốc kê đơn GPP'}</span>
          </div>

          <div className="detail-item">
            <span className="detail-label">Cơ sở y tế / Nhà thuốc</span>
            <span className="detail-value">{tx.provider}</span>
          </div>

          {bhytDisplay && (
            <div className="detail-item full-width bhyt-benefit-box">
              <span className="detail-label">Quyền lợi Quỹ BHYT chi trả</span>
              <strong className="detail-value">{bhytDisplay} (Hưởng 80% đúng tuyến)</strong>
            </div>
          )}
        </div>
      </div>

      {currentStatus === 'pending' && (
        <div className="card-footer-area">
          <div className="auto-submit-preference-row">
            <label className="auto-submit-toggle-label">
              <input
                type="checkbox"
                className="auto-submit-checkbox"
                checked={rememberAutoSubmit}
                onChange={(e) => {
                  setRememberAutoSubmit(e.target.checked);
                  onToggleAutoSubmit?.(e.target.checked);
                }}
              />
              <span className="checkbox-text-copy">
                Tự động áp dụng cho các lần sau (<strong>Auto-submit</strong>)
              </span>
            </label>
          </div>

          <div className="card-actions-row">
            <button
              type="button"
              className="action-btn accept-btn"
              onClick={handleAccept}
            >
              <CheckCircle2 size={15} />
              <span>Lưu vào Chi tiêu y tế</span>
            </button>
            <button
              type="button"
              className="action-btn decline-btn"
              onClick={handleDecline}
            >
              <X size={15} />
              <span>Bỏ qua</span>
            </button>
          </div>
        </div>
      )}

      {currentStatus === 'accepted' && (
        <div className="card-success-banner">
          <div className="success-msg">
            <CheckCircle2 size={16} />
            <span>Đã ghi nhận thành công vào Sổ chi tiêu y tế & TiDB Cloud!</span>
          </div>
          {onOpenSpending && (
            <button
              type="button"
              className="view-link-btn"
              onClick={onOpenSpending}
            >
              <span>Xem Sổ chi tiêu</span>
              <ArrowUpRight size={14} />
            </button>
          )}
        </div>
      )}

      {currentStatus === 'declined' && (
        <div className="card-declined-banner">
          <div className="declined-msg">
            <X size={15} />
            <span>Đã bỏ qua đề xuất ghi nhận chi tiêu y tế này.</span>
          </div>
        </div>
      )}
    </div>
  );
}
