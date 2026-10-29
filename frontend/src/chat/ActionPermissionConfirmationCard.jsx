import React, { useState } from 'react';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  Clock,
  ExternalLink,
  Flame,
  HeartPulse,
  Info,
  Layers,
  MapPin,
  Pill,
  Receipt,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  WalletCards,
  X,
  XCircle,
} from 'lucide-react';
import './ActionPermissionConfirmationCard.css';

/**
 * ChatGPT-style Direct Action & Permission Confirmation Card for Cross-Module Data Sync.
 * Prompts user for explicit authorization before committing mutations to Health Twin (3D Body Map),
 * Healthcare Spending, or Dual systems, with an optional "Auto-submit for future" toggle.
 */
export function ActionPermissionConfirmationCard({
  proposal,
  status = 'pending',
  onAccept,
  onDecline,
  autoSubmit = false,
  onToggleAutoSubmit,
  onNavigate,
}) {
  const [rememberChoice, setRememberChoice] = useState(autoSubmit);

  if (!proposal) return null;

  const {
    moduleType = 'health_twin', // 'health_twin' | 'spending' | 'dual'
    moduleTitle = 'Bản đồ Cơ thể 3D',
    summaryText = '',
    extractedItems = [],
    healthMutation = null,
    expenseMutation = null,
  } = proposal;

  const isHealth = moduleType === 'health_twin';
  const isSpending = moduleType === 'spending';
  const isDual = moduleType === 'dual';

  const handleCheckboxChange = (e) => {
    const val = e.target.checked;
    setRememberChoice(val);
    onToggleAutoSubmit?.(val);
  };

  const handleAcceptClick = () => {
    onAccept?.({
      ...proposal,
      rememberAutoSubmit: rememberChoice,
    });
  };

  const getModuleIcon = () => {
    if (isHealth) return <Activity size={18} className="icon-pulse" />;
    if (isSpending) return <WalletCards size={18} />;
    return <Layers size={18} />;
  };

  const getTargetView = () => {
    if (isHealth) return 'health';
    if (isSpending) return 'spending';
    return 'health';
  };

  const getTargetViewLabel = () => {
    if (isHealth) return 'Bản đồ Cơ thể 3D';
    if (isSpending) return 'Sổ Chi Tiêu & BHYT';
    return 'Hệ sinh thái MedGuard';
  };

  return (
    <div
      className={`chatgpt-action-permission-card module-${moduleType} status-${status}`}
      role="region"
      aria-label={`Yêu cầu cấp quyền cập nhật ${moduleTitle}`}
    >
      {/* 1. Executive Top Header */}
      <div className="action-card-header">
        <div className="header-identity-group">
          <div className={`module-icon-box type-${moduleType}`}>
            {getModuleIcon()}
          </div>
          <div className="header-text-column">
            <div className="header-kicker-row">
              <span className="action-type-pill">YÊU CẦU CẤP QUYỀN TRUY CẬP</span>
              <span className="module-name-tag">{moduleTitle}</span>
            </div>
            <strong className="header-main-title">
              {isDual
                ? 'Đồng bộ Dữ liệu Bệnh lý & Chi phí Y tế'
                : isSpending
                ? 'Cập nhật Sổ Chi Tiêu & Quyền lợi BHYT'
                : 'Cập nhật Tình trạng Cơ quan & Chỉ số Sức khỏe'}
            </strong>
          </div>
        </div>

        <div className="header-status-badge">
          {status === 'accepted' ? (
            <span className="status-badge-chip accepted">
              <Check size={12} /> Đã cấp quyền
            </span>
          ) : status === 'declined' ? (
            <span className="status-badge-chip declined">
              <X size={12} /> Đã từ chối
            </span>
          ) : (
            <span className="status-badge-chip pending">
              <Sparkles size={12} /> Chờ bạn phê duyệt
            </span>
          )}
        </div>
      </div>

      {/* 2. Structured Data Diff / Preview Section */}
      <div className="action-card-body">
        <div className="proposal-rationale-note">
          <Info size={14} className="rationale-icon" />
          <span>
            {summaryText ||
              'MedGuard AI phát hiện thông tin mới từ tin nhắn của bạn. Dữ liệu bên dưới sẽ được lưu vào hệ sinh thái nếu bạn cho phép:'}
          </span>
        </div>

        <div className="extracted-data-grid">
          {extractedItems && extractedItems.length > 0 ? (
            extractedItems.map((item, idx) => (
              <div key={idx} className={`data-item-pill ${item.tone || 'neutral'}`}>
                <div className="item-icon-wrap">
                  {item.icon === 'organ' ? (
                    <Activity size={14} />
                  ) : item.icon === 'money' ? (
                    <Receipt size={14} />
                  ) : item.icon === 'pain' ? (
                    <Flame size={14} />
                  ) : item.icon === 'warning' ? (
                    <AlertTriangle size={14} />
                  ) : (
                    <ShieldCheck size={14} />
                  )}
                </div>
                <div className="item-content-wrap">
                  <span className="item-meta-label">{item.label}</span>
                  <strong className="item-meta-value">{item.value}</strong>
                  {item.subHint && <span className="item-meta-hint">{item.subHint}</span>}
                </div>
              </div>
            ))
          ) : (
            <div className="fallback-sync-pill">
              <ShieldCheck size={14} />
              <span>Dữ liệu đồng bộ trực tiếp đã được đối soát an toàn y khoa.</span>
            </div>
          )}
        </div>
      </div>

      {/* 3. Status Result Banners & Action Buttons */}
      {status === 'accepted' ? (
        <div className="action-result-banner accepted-banner">
          <div className="banner-left-meta">
            <CheckCircle2 size={18} className="banner-icon-success" />
            <div className="banner-text">
              <strong>Đã cấp quyền & Cập nhật thành công!</strong>
              <span>
                Dữ liệu đã được ghi nhận vào {moduleTitle}. Bạn có thể mở xem trực tiếp bất kỳ lúc nào.
              </span>
            </div>
          </div>
          <button
            type="button"
            className="btn-view-module-target"
            onClick={() => onNavigate?.(getTargetView())}
            title={`Xem ngay trên ${getTargetViewLabel()}`}
          >
            <span>Xem trên {getTargetViewLabel()}</span>
            <ExternalLink size={13} />
          </button>
        </div>
      ) : status === 'declined' ? (
        <div className="action-result-banner declined-banner">
          <XCircle size={18} className="banner-icon-declined" />
          <div className="banner-text">
            <strong>Bạn đã từ chối cấp quyền cập nhật.</strong>
            <span>Hệ thống giữ nguyên toàn bộ dữ liệu hiện có mà không có bất kỳ thay đổi nào.</span>
          </div>
        </div>
      ) : (
        <div className="action-footer-decision-area">
          {/* Auto-Submit / Remember Choice Checkbox */}
          <div className="auto-submit-preference-row">
            <label className="auto-submit-toggle-label">
              <input
                type="checkbox"
                checked={rememberChoice}
                onChange={handleCheckboxChange}
                className="auto-submit-checkbox"
              />
              <span className="checkbox-custom-box" />
              <span className="checkbox-text-copy">
                <strong>Tự động áp dụng cho các lần sau</strong> (Không cần hỏi lại khi phát hiện thông tin tương tự)
              </span>
            </label>
          </div>

          {/* Action Decision Buttons */}
          <div className="decision-buttons-row">
            <button
              type="button"
              className="decision-btn btn-accept-action"
              onClick={handleAcceptClick}
              title="Đồng ý cập nhật dữ liệu này vào hệ thống"
            >
              <Check size={16} />
              <span>Cho phép cập nhật</span>
            </button>
            <button
              type="button"
              className="decision-btn btn-decline-action"
              onClick={onDecline}
              title="Từ chối và giữ nguyên dữ liệu hiện tại"
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
