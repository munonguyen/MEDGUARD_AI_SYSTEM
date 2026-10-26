import { useState } from 'react';
import {
  ArrowUpRight,
  Check,
  CheckCircle2,
  Clock,
  ExternalLink,
  Info,
  Pill,
  Sparkles,
  X,
} from 'lucide-react';

export function MedicationProposalCard({
  proposal,
  status = 'pending',
  onAccept,
  onDecline,
  onOpenMedication,
}) {
  const [internalStatus, setInternalStatus] = useState(status);
  const med = proposal?.medication;

  if (!med) return null;

  const currentStatus = status !== 'pending' ? status : internalStatus;

  const handleAccept = () => {
    setInternalStatus('accepted');
    onAccept?.(proposal);
  };

  const handleDecline = () => {
    setInternalStatus('declined');
    onDecline?.();
  };

  const slotLabels = {
    morning: 'Sáng',
    noon: 'Trưa',
    evening: 'Tối',
    bedtime: 'Trước khi ngủ',
  };

  return (
    <div
      className={`chat-action-card med-proposal-card ${currentStatus}`}
      role="region"
      aria-label="Đề xuất thêm lịch uống thuốc"
    >
      <div className="card-header">
        <div className="card-header-icon med-icon">
          <Pill size={18} />
        </div>
        <div className="card-header-text">
          <div className="card-title-row">
            <strong>Đề xuất thêm Lịch uống thuốc</strong>
            <span className={`status-badge ${currentStatus}`}>
              {currentStatus === 'accepted' ? (
                <>
                  <Check size={12} /> Đã thêm vào lịch
                </>
              ) : currentStatus === 'declined' ? (
                'Đã bỏ qua'
              ) : (
                'Chờ xác nhận'
              )}
            </span>
          </div>
          <span className="card-subtitle">
            Phát hiện đơn thuốc & thời điểm uống trong tin nhắn
          </span>
        </div>
      </div>

      <div className="card-details-grid">
        <div className="detail-item">
          <span className="detail-label">Tên thuốc & Hàm lượng</span>
          <strong className="detail-value text-highlight">
            {med.name} {med.strength && med.strength !== 'Chuẩn đơn' ? `(${med.strength})` : ''}
          </strong>
        </div>

        <div className="detail-item">
          <span className="detail-label">Liều dùng mỗi lần</span>
          <strong className="detail-value">{med.dosage || '1 viên'}</strong>
        </div>

        <div className="detail-item">
          <span className="detail-label">Khung giờ nhắc thuốc</span>
          <div className="time-badge-box">
            <Clock size={13} />
            <strong>{med.timing}</strong>
            <span className="slot-tag">({slotLabels[med.slot] || 'Hàng ngày'})</span>
          </div>
        </div>

        <div className="detail-item full-width">
          <span className="detail-label">Chỉ dẫn y khoa</span>
          <span className="detail-instruction">{med.instruction}</span>
        </div>
      </div>

      {currentStatus === 'pending' && (
        <div className="card-actions-row">
          <button
            type="button"
            className="action-btn accept-btn"
            onClick={handleAccept}
          >
            <Check size={15} />
            <span>Thêm vào Lịch uống thuốc</span>
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
      )}

      {currentStatus === 'accepted' && (
        <div className="card-success-banner">
          <div className="success-msg">
            <CheckCircle2 size={16} />
            <span>Đã tự động thêm vào Thời khóa biểu nhắc thuốc của bạn!</span>
          </div>
          {onOpenMedication && (
            <button
              type="button"
              className="view-link-btn"
              onClick={onOpenMedication}
            >
              <span>Xem Lịch thuốc</span>
              <ArrowUpRight size={14} />
            </button>
          )}
        </div>
      )}
    </div>
  );
}
