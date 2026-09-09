import { useEffect, useMemo, useState } from 'react';
import { CalendarDays, Clock3, LoaderCircle, RefreshCw, X } from 'lucide-react';

const dateFormatter = new Intl.DateTimeFormat('vi-VN', { weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric', timeZone: 'Asia/Ho_Chi_Minh' });
const timeFormatter = new Intl.DateTimeFormat('vi-VN', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Ho_Chi_Minh' });

export function SchedulePanel({ open, onClose, api, patientRef }) {
  const [schedules, setSchedules] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

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
    if (open) load();
  }, [open, api, patientRef]);

  const groups = useMemo(() => schedules.reduce((result, item) => {
    const key = dateFormatter.format(new Date(item.scheduled_at));
    result[key] = [...(result[key] || []), item];
    return result;
  }, {}), [schedules]);

  if (!open) return null;
  return (
    <div className="drawer-layer">
      <button className="drawer-scrim" type="button" aria-label="Đóng lịch thuốc" onClick={onClose} />
      <aside className="schedule-drawer" aria-label="Lịch uống thuốc">
        <header className="dialog-header">
          <div><span className="dialog-icon"><CalendarDays size={19} /></span><div><h2>Lịch uống thuốc</h2><p>{patientRef || 'Tất cả hồ sơ'}</p></div></div>
          <div><button className="icon-button" type="button" title="Làm mới" aria-label="Làm mới lịch" onClick={load}><RefreshCw className={busy ? 'spin' : ''} size={17} /></button><button className="icon-button" type="button" title="Đóng" aria-label="Đóng" onClick={onClose}><X size={19} /></button></div>
        </header>
        <div className="schedule-content">
          {busy && !schedules.length && <div className="drawer-state"><LoaderCircle className="spin" size={22} /><span>Đang tải lịch</span></div>}
          {error && <p className="dialog-error">{error}</p>}
          {!busy && !error && !schedules.length && <div className="drawer-state"><CalendarDays size={25} /><strong>Chưa có lịch thuốc</strong></div>}
          {Object.entries(groups).map(([day, items]) => <section className="schedule-day" key={day}><h3>{day}</h3>{items.map((item) => <div className="schedule-item" key={item.schedule_id}><time><Clock3 size={14} />{timeFormatter.format(new Date(item.scheduled_at))}</time><div><strong>{item.medication_name}</strong><span>{item.patient_ref} · {item.recurrence === 'daily' ? 'Lặp mỗi ngày' : 'Một lần'}</span></div></div>)}</section>)}
        </div>
      </aside>
    </div>
  );
}
