import { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  Calendar,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock3,
  LoaderCircle,
  Pill,
  Plus,
  RefreshCw,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react';

const dateFormatter = new Intl.DateTimeFormat('vi-VN', {
  weekday: 'long',
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  timeZone: 'Asia/Ho_Chi_Minh',
});

const timeFormatter = new Intl.DateTimeFormat('vi-VN', {
  hour: '2-digit',
  minute: '2-digit',
  timeZone: 'Asia/Ho_Chi_Minh',
});

export function SchedulePanel({ open, onClose, api, patientRef, onOpenSchedulePage, onNotify }) {
  const [schedules, setSchedules] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);
  const [adding, setAdding] = useState(false);

  // Form State
  const [medName, setMedName] = useState('');
  const [medDosage, setMedDosage] = useState('');
  const [medTime, setMedTime] = useState('08:00');
  const [medRecurrence, setMedRecurrence] = useState('daily');

  // Check-in tracking state stored in localStorage
  const [takenMap, setTakenMap] = useState(() => {
    try {
      const raw = localStorage.getItem('medguard.schedules.taken');
      return raw ? JSON.parse(raw) : {};
    } catch {
      return {};
    }
  });

  const load = async () => {
    setBusy(true);
    setError('');
    try {
      const query = patientRef ? `?patient_ref=${encodeURIComponent(patientRef)}` : '';
      const data = await api.request(`/v1/medication-schedules${query}`);
      setSchedules(data.schedules || []);
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (open) {
      load();
    }
  }, [open, api, patientRef]);

  const toggleTaken = (scheduleId) => {
    setTakenMap((prev) => {
      const next = { ...prev, [scheduleId]: !prev[scheduleId] };
      try {
        localStorage.setItem('medguard.schedules.taken', JSON.stringify(next));
      } catch {
        // Fallback for storage restricted environments
      }
      return next;
    });
    const willBeTaken = !takenMap[scheduleId];
    onNotify?.(willBeTaken ? '✓ Đã điểm danh uống thuốc' : 'Đã hủy điểm danh thuốc');
  };

  const handleAddMedication = async (e) => {
    e.preventDefault();
    if (!medName.trim()) return;
    setAdding(true);
    try {
      const todayStr = new Date().toISOString().slice(0, 10);
      const scheduledIso = `${todayStr}T${medTime}:00Z`;
      await api.request('/v1/medication-schedules', {
        method: 'POST',
        body: {
          patient_ref: patientRef || 'BN-CANHAN',
          medication_name: medName.trim(),
          dosage_text: medDosage.trim() || '1 viên',
          scheduled_at: scheduledIso,
          recurrence: medRecurrence,
          source: 'chat',
        },
      });
      setMedName('');
      setMedDosage('');
      setShowAddForm(false);
      onNotify?.(`Đã thêm mốc uống thuốc: ${medName}`);
      await load();
    } catch (err) {
      setError(err.message || 'Không thể tạo mốc thuốc');
    } finally {
      setAdding(false);
    }
  };

  const handleDeleteMedication = async (scheduleId) => {
    try {
      await api.request(`/v1/medication-schedules/${encodeURIComponent(scheduleId)}`, {
        method: 'DELETE',
      });
      onNotify?.('Đã xóa mốc uống thuốc');
      await load();
    } catch (err) {
      setError(err.message || 'Không thể xóa mốc thuốc');
    }
  };

  const handleLoadSample = async () => {
    setBusy(true);
    try {
      const todayStr = new Date().toISOString().slice(0, 10);
      const samples = [
        {
          patient_ref: patientRef || 'BN-CANHAN',
          medication_name: 'Amlodipine 5mg',
          dosage_text: '1 viên · Sau ăn sáng 30p',
          scheduled_at: `${todayStr}T08:00:00Z`,
          recurrence: 'daily',
          source: 'chat',
        },
        {
          patient_ref: patientRef || 'BN-CANHAN',
          medication_name: 'Metformin 500mg',
          dosage_text: '1 viên · Trong bữa trưa',
          scheduled_at: `${todayStr}T12:30:00Z`,
          recurrence: 'daily',
          source: 'chat',
        },
        {
          patient_ref: patientRef || 'BN-CANHAN',
          medication_name: 'Esomeprazole 40mg',
          dosage_text: '1 viên · Trước ăn tối 60p',
          scheduled_at: `${todayStr}T18:00:00Z`,
          recurrence: 'daily',
          source: 'chat',
        },
      ];
      for (const item of samples) {
        await api.request('/v1/medication-schedules', { method: 'POST', body: item });
      }
      onNotify?.('Đã nạp 3 mốc thuốc điều trị mẫu');
      await load();
    } catch (err) {
      setError(err.message || 'Lỗi nạp thuốc mẫu');
    } finally {
      setBusy(false);
    }
  };

  const groups = useMemo(() => {
    return schedules.reduce((result, item) => {
      const key = dateFormatter.format(new Date(item.scheduled_at));
      result[key] = [...(result[key] || []), item];
      return result;
    }, {});
  }, [schedules]);

  const totalMeds = schedules.length;
  const takenCount = schedules.filter((s) => takenMap[s.schedule_id]).length;
  const percentComplete = totalMeds > 0 ? Math.round((takenCount / totalMeds) * 100) : 0;

  if (!open) return null;

  return (
    <div className="drawer-layer" role="dialog" aria-modal="true" aria-label="Lịch uống thuốc">
      <button className="drawer-scrim" type="button" aria-label="Đóng lịch thuốc" onClick={onClose} />
      <aside className="schedule-drawer" aria-label="Lịch uống thuốc">
        {/* Header */}
        <header className="dialog-header drawer-topbar">
          <div className="drawer-title-group">
            <span className="dialog-icon drawer-icon-badge">
              <CalendarDays size={20} />
            </span>
            <div>
              <h2>Lịch uống thuốc</h2>
              <p>{patientRef ? `Hồ sơ: ${patientRef}` : 'Theo dõi uống thuốc hàng ngày'}</p>
            </div>
          </div>
          <div className="drawer-actions">
            <button
              className="quick-add-btn"
              type="button"
              title="Thêm mốc thuốc mới"
              onClick={() => setShowAddForm((v) => !v)}
            >
              <Plus size={15} />
              <span>Thêm thuốc</span>
            </button>
            <button
              className="icon-button"
              type="button"
              title="Làm mới"
              aria-label="Làm mới lịch"
              onClick={load}
            >
              <RefreshCw className={busy ? 'spin' : ''} size={17} />
            </button>
            <button
              className="icon-button"
              type="button"
              title="Đóng"
              aria-label="Đóng"
              onClick={onClose}
            >
              <X size={19} />
            </button>
          </div>
        </header>

        {/* Adherence Progress Bar */}
        {totalMeds > 0 && (
          <div className="adherence-card">
            <div className="adherence-header">
              <span>Tiến độ uống hôm nay</span>
              <strong>
                {takenCount}/{totalMeds} liều ({percentComplete}%)
              </strong>
            </div>
            <div className="adherence-bar-track">
              <div
                className="adherence-bar-fill"
                style={{ width: `${percentComplete}%` }}
              />
            </div>
          </div>
        )}

        {/* Inline Add Form */}
        {showAddForm && (
          <form className="drawer-add-form animate-fade-in" onSubmit={handleAddMedication}>
            <div className="form-head">
              <strong>+ Thêm mốc uống thuốc mới</strong>
              <button
                type="button"
                className="icon-button"
                onClick={() => setShowAddForm(false)}
                title="Hủy"
              >
                <X size={15} />
              </button>
            </div>
            <div className="form-inputs">
              <input
                type="text"
                placeholder="Tên thuốc (VD: Panadol Extra 500mg)"
                value={medName}
                onChange={(e) => setMedName(e.target.value)}
                required
                className="drawer-input"
              />
              <div className="form-row-2">
                <input
                  type="text"
                  placeholder="Liều lượng (VD: 1 viên sau ăn)"
                  value={medDosage}
                  onChange={(e) => setMedDosage(e.target.value)}
                  className="drawer-input"
                />
                <input
                  type="time"
                  value={medTime}
                  onChange={(e) => setMedTime(e.target.value)}
                  className="drawer-input"
                  required
                />
              </div>
              <div className="form-row-2">
                <select
                  value={medRecurrence}
                  onChange={(e) => setMedRecurrence(e.target.value)}
                  className="drawer-input"
                >
                  <option value="daily">Lặp hàng ngày</option>
                  <option value="once">Chỉ một lần</option>
                </select>
                <button
                  type="submit"
                  className="primary-button add-submit-btn"
                  disabled={adding || !medName.trim()}
                >
                  {adding ? <LoaderCircle className="spin" size={15} /> : <Plus size={15} />}
                  <span>{adding ? 'Đang lưu...' : 'Lưu mốc thuốc'}</span>
                </button>
              </div>
            </div>
          </form>
        )}

        {/* Drawer Content */}
        <div className="schedule-content">
          {busy && !schedules.length && (
            <div className="drawer-state">
              <LoaderCircle className="spin" size={24} />
              <span>Đang đồng bộ danh sách thuốc...</span>
            </div>
          )}

          {error && (
            <div className="drawer-error-box">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          {/* Empty State with Actionable Guidance */}
          {!busy && !error && !schedules.length && (
            <div className="drawer-empty-rich animate-fade-in">
              <div className="empty-icon-wrap">
                <Pill size={32} />
              </div>
              <h3>Chưa có lịch thuốc hôm nay</h3>
              <p>
                Bạn có thể tạo mốc uống thuốc thủ công, tải phác đồ mẫu điều trị, hoặc nhắn trực tiếp cho trợ lý AI.
              </p>

              <div className="empty-actions-col">
                <button
                  type="button"
                  className="primary-button empty-sample-btn"
                  onClick={handleLoadSample}
                >
                  <Sparkles size={16} />
                  <span>Tải phác đồ thuốc mẫu (Huyết áp & Tiểu đường)</span>
                </button>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => setShowAddForm(true)}
                >
                  <Plus size={16} />
                  <span>+ Thêm thuốc thủ công</span>
                </button>
              </div>

              {/* AI Prompt Hint Card */}
              <div className="ai-hint-box">
                <div className="hint-badge">💡 Mẹo ra lệnh AI</div>
                <p>
                  Gõ tin nhắn trong phòng Chat:
                  <br />
                  <code>#lichthuoc uống amoxicillin lúc 8h và 20h mỗi ngày.</code>
                </p>
                <span className="hint-sub">Trợ lý sẽ tự động bóc tách tên thuốc, liều dùng và giờ uống!</span>
              </div>

              {/* Link to Weekly Timetable */}
              <button
                type="button"
                className="switch-to-timetable-btn"
                onClick={() => {
                  onClose();
                  onOpenSchedulePage?.();
                }}
              >
                <Calendar size={16} />
                <span>Xem Thời khóa biểu tuần & Lịch khám</span>
                <ChevronRight size={16} />
              </button>
            </div>
          )}

          {/* Schedule Groups (Required .schedule-item class for Playwright smoke test) */}
          {Object.entries(groups).map(([day, items]) => (
            <section className="schedule-day animate-fade-in" key={day}>
              <div className="schedule-day-title">
                <CalendarDays size={14} />
                <h3>{day}</h3>
              </div>
              <div className="schedule-items-list">
                {items.map((item) => {
                  const isTaken = Boolean(takenMap[item.schedule_id]);
                  return (
                    <div
                      className={`schedule-item ${isTaken ? 'is-taken' : ''}`}
                      key={item.schedule_id}
                    >
                      <time className="schedule-time">
                        <Clock3 size={14} />
                        {timeFormatter.format(new Date(item.scheduled_at))}
                      </time>

                      <div className="schedule-info">
                        <strong className="med-name">{item.medication_name}</strong>
                        <span className="med-meta">
                          {item.dosage_text ? `${item.dosage_text} · ` : ''}
                          {item.recurrence === 'daily' ? 'Lặp hàng ngày' : 'Một lần'}
                        </span>
                      </div>

                      <div className="schedule-item-actions">
                        <button
                          type="button"
                          className={`check-in-pill ${isTaken ? 'checked' : ''}`}
                          onClick={() => toggleTaken(item.schedule_id)}
                          title={isTaken ? 'Bấm để hủy đánh dấu' : 'Bấm để điểm danh đã uống'}
                        >
                          {isTaken ? <CheckCircle2 size={15} /> : <Check size={14} />}
                          <span>{isTaken ? 'Đã uống' : 'Uống thuốc'}</span>
                        </button>

                        <button
                          type="button"
                          className="icon-button delete-schedule-btn"
                          title="Xóa mốc thuốc"
                          aria-label={`Xóa ${item.medication_name}`}
                          onClick={() => handleDeleteMedication(item.schedule_id)}
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          ))}

          {/* Bottom Timetable Link when schedules exist */}
          {schedules.length > 0 && (
            <div className="drawer-bottom-link">
              <button
                type="button"
                className="switch-to-timetable-btn"
                onClick={() => {
                  onClose();
                  onOpenSchedulePage?.();
                }}
              >
                <Calendar size={16} />
                <span>Mở Thời khóa biểu tuần & Lịch khám</span>
                <ChevronRight size={16} />
              </button>
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
