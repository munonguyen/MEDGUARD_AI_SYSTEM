import { useState } from 'react';
import {
  ArrowUpRight,
  Building2,
  CalendarDays,
  Check,
  CheckCircle2,
  Clock,
  ShieldCheck,
  Stethoscope,
  User,
  X,
} from 'lucide-react';

export function AppointmentProposalCard({
  proposal,
  status = 'pending',
  onAccept,
  onDecline,
  onOpenSchedule,
  autoSubmit = false,
  onToggleAutoSubmit,
}) {
  const [internalStatus, setInternalStatus] = useState(status);
  const [rememberAutoSubmit, setRememberAutoSubmit] = useState(autoSubmit);
  const appt = proposal?.appointment;

  if (!appt) return null;

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

  return (
    <div
      className={`chat-action-card appt-proposal-card ${currentStatus}`}
      role="region"
      aria-label="Đề xuất đặt lịch hẹn khám bệnh"
    >
      <div className="card-header">
        <div className="card-header-icon appt-icon">
          <Stethoscope size={18} />
        </div>
        <div className="card-header-text">
          <div className="card-title-row">
            <div className="header-kicker-row">
              <span className="action-type-pill">Đề xuất đặt lịch khám</span>
              <span className="module-name-tag">Đặt Lịch Bác Sĩ</span>
            </div>
            <strong className="card-main-title">Phiếu đề xuất Đặt lịch khám Bác sĩ</strong>
          </div>
          <span className="card-subtitle">
            Hệ thống trích xuất thông tin chuyên khoa & thời gian hẹn từ tin nhắn
          </span>
        </div>
        <span className={`status-badge ${currentStatus}`}>
          {currentStatus === 'accepted' ? (
            <>
              <Check size={12} /> Đã đặt hẹn
            </>
          ) : currentStatus === 'declined' ? (
            'Đã hủy'
          ) : (
            'Chờ xác nhận'
          )}
        </span>
      </div>

      <div className="card-body-content">
        <div className="appt-voucher-body">
          <div className="voucher-row main-highlight">
            <div className="doctor-badge-box">
              <span className="voucher-label">BÁC SĨ PHỤ TRÁCH</span>
              <strong className="doctor-name">{appt.doctor}</strong>
              <span className="dept-tag">{appt.department}</span>
            </div>
            <div className="time-badge-box">
              <span className="voucher-label">THỜI GIAN KHÁM</span>
              <div className="time-val">
                <CalendarDays size={13} />
                <strong>{appt.date}</strong>
              </div>
              <div className="slot-val">
                <Clock size={13} />
                <span>{appt.timeSlot}</span>
              </div>
            </div>
          </div>

          <div className="voucher-grid-2">
            <div className="voucher-item">
              <span className="voucher-label">BỆNH VIỆN / CƠ SỞ KCB</span>
              <div className="hosp-info">
                <Building2 size={13} />
                <span>{appt.hospital}</span>
              </div>
              <small className="room-text">{appt.room}</small>
            </div>

            <div className="voucher-item">
              <span className="voucher-label">BỆNH NHÂN ĐĂNG KÝ</span>
              <div className="patient-info">
                <User size={13} />
                <span>{appt.patientName}</span>
              </div>
              {appt.bhytCovered && (
                <div className="bhyt-pill" title="Áp dụng thanh toán BHYT đúng tuyến">
                  <ShieldCheck size={11} />
                  <span>BHYT hỗ trợ {appt.bhytRate}%</span>
                </div>
              )}
            </div>
          </div>

          <div className="voucher-notes">
            <strong>Lưu ý tiếp đón:</strong> <span>{appt.prepNotes}</span>
          </div>
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
              <Check size={15} />
              <span>Xác nhận Đặt lịch khám</span>
            </button>
            <button
              type="button"
              className="action-btn decline-btn"
              onClick={handleDecline}
            >
              <X size={15} />
              <span>Hủy hẹn</span>
            </button>
          </div>
        </div>
      )}

      {currentStatus === 'accepted' && (
        <div className="card-success-banner">
          <div className="success-msg">
            <CheckCircle2 size={16} />
            <span>Đã xác nhận đặt lịch hẹn thành công! Mã ca khám: <strong>{appt.id}</strong></span>
          </div>
          {onOpenSchedule && (
            <button
              type="button"
              className="view-link-btn"
              onClick={onOpenSchedule}
            >
              <span>Xem Lịch khám</span>
              <ArrowUpRight size={14} />
            </button>
          )}
        </div>
      )}

      {currentStatus === 'declined' && (
        <div className="card-declined-banner">
          <div className="declined-msg">
            <X size={15} />
            <span>Đã hủy bỏ đề xuất đặt lịch khám này.</span>
          </div>
        </div>
      )}
    </div>
  );
}
