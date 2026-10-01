import { useEffect, useState } from 'react';
import { ArrowLeft, CalendarDays, Plus, RefreshCw, Trash2, Pencil, X } from 'lucide-react';

const zone = 'Asia/Ho_Chi_Minh';
const dateParts = (value) => Object.fromEntries(new Intl.DateTimeFormat('en-CA', { timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date(value)).map(({type,value}) => [type,value]));
const localDate = (value = new Date()) => { const p = dateParts(value); return `${p.year}-${p.month}-${p.day}`; };
const localTime = (value) => new Intl.DateTimeFormat('en-GB', { timeZone: zone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(value));
const displayTime = new Intl.DateTimeFormat('vi-VN', { timeZone: zone, dateStyle: 'medium', timeStyle: 'short' });
const emptyForm = () => ({ medication_name: '', dosage_text: '', date: localDate(), time: '', recurrence: 'once' });

export function MedicationPage({ api, patientRef, onBackToChat, onNotify }) {
  const [schedules, setSchedules] = useState([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [form, setForm] = useState(null);
  const [editing, setEditing] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const load = async () => {
    setLoading(true); setError('');
    try { const result = await api.request('/v1/medication-schedules'); setSchedules(result.schedules || []); }
    catch (cause) { setError(cause.message); }
    finally { setLoading(false); }
  };
  useEffect(() => {
    let current = true;
    setLoading(true);
    api.request('/v1/medication-schedules').then((result) => { if(current) setSchedules(result.schedules || []); }).catch((cause) => { if(current) setError(cause.message); }).finally(() => { if(current) setLoading(false); });
    return () => { current = false; };
  }, [api]);
  const change = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  const edit = (item) => { setEditing(item.schedule_id); setForm({ medication_name: item.medication_name, dosage_text: item.dosage_text || '', date: localDate(item.scheduled_at), time: localTime(item.scheduled_at), recurrence: item.recurrence }); setError(''); };
  const save = async (event) => {
    event.preventDefault(); if(busy) return;
    setBusy(true); setError('');
    try {
      const body = { medication_name: form.medication_name.trim(), dosage_text: form.dosage_text.trim(), scheduled_at: `${form.date}T${form.time}:00+07:00`, recurrence: form.recurrence };
      await api.request(editing ? `/v1/medication-schedules/${encodeURIComponent(editing)}` : '/v1/medication-schedules', { method: editing ? 'PUT' : 'POST', body: editing ? body : { ...body, patient_ref: patientRef || 'Ca-nhan', source: 'chat' } });
      setForm(null); setEditing(null); onNotify?.('Đã lưu lịch của bạn.'); await load();
    } catch(cause) { setError(cause.message); }
    finally { setBusy(false); }
  };
  const remove = async () => {
    if(busy) return; setBusy(true); setError('');
    try { await api.request(`/v1/medication-schedules/${encodeURIComponent(deleting)}`, {method:'DELETE'}); setDeleting(null); onNotify?.('Đã xóa lịch.'); await load(); }
    catch(cause) { setError(cause.message); }
    finally { setBusy(false); }
  };
  return <section className="patient-medications" aria-labelledby="medication-title">
    <header><div><span className="medication-eyebrow"><CalendarDays size={18} /> LỊCH CÁ NHÂN</span><h2 id="medication-title">Lịch uống thuốc của bạn</h2><p>Ghi lại thời gian theo đơn hoặc hướng dẫn bạn đã được nhân viên y tế cung cấp.</p></div><button className="medication-secondary" type="button" onClick={onBackToChat}><ArrowLeft size={16} /> Về trò chuyện</button></header>
    <p className="medication-boundary">Lịch này lưu riêng theo tài khoản và hiển thị giờ Việt Nam (UTC+7). Đây là ghi chú lịch, chưa gửi thông báo khi bạn đóng ứng dụng. Không tự thay đổi thuốc hoặc liều dựa trên lịch này.</p>
    <div className="medication-toolbar"><button className="medication-primary" type="button" disabled={busy} onClick={() => { setEditing(null); setForm(emptyForm()); setError(''); }}><Plus size={16} /> Thêm lịch uống thuốc</button><button className="medication-secondary" type="button" disabled={loading || busy} onClick={load}><RefreshCw size={16} /> Tải lại lịch</button></div>
    {error && <p className="account-error" role="alert">{error}</p>}
    {form && <form className="medication-form" onSubmit={save}>
      <div className="medication-form-title"><h3>{editing ? 'Sửa lịch uống thuốc' : 'Thêm lịch theo hướng dẫn có sẵn'}</h3><button type="button" className="medication-secondary" disabled={busy} aria-label="Đóng form lịch thuốc" onClick={() => setForm(null)}><X size={16} /></button></div>
      <label>Tên thuốc theo đơn<input required maxLength="255" value={form.medication_name} onChange={(event) => change('medication_name', event.target.value)} /></label>
      <label>Liều và hướng dẫn đã được kê (tùy chọn)<input maxLength="255" value={form.dosage_text} onChange={(event) => change('dosage_text', event.target.value)} /></label>
      <div className="medication-form-row"><label>Ngày bắt đầu<input type="date" required value={form.date} onChange={(event) => change('date', event.target.value)} /></label><label>Giờ uống (UTC+7)<input type="time" required value={form.time} onChange={(event) => change('time', event.target.value)} /></label><label>Lặp lại<select value={form.recurrence} onChange={(event) => change('recurrence', event.target.value)}><option value="once">Một lần</option><option value="daily">Hàng ngày</option></select></label></div>
      <button className="medication-primary" disabled={busy} type="submit">{busy ? 'Đang lưu…' : 'Lưu lịch uống thuốc'}</button>
    </form>}
    {loading ? <p role="status">Đang tải lịch…</p> : schedules.length === 0 ? <div className="medication-empty"><CalendarDays size={32} /><h3>Chưa có lịch uống thuốc</h3><p>Thêm lịch từ hướng dẫn của bạn. Hệ thống không tự tạo đơn thuốc mẫu.</p></div> : <ul className="medication-list">{schedules.map((item) => <li key={item.schedule_id} data-schedule-id={item.schedule_id}><div><h3>{item.medication_name}</h3><p>{item.dosage_text || 'Chưa ghi liều; dùng theo hướng dẫn đã được kê.'}</p><time dateTime={item.scheduled_at}>{displayTime.format(new Date(item.scheduled_at))}</time><span className="medication-frequency">{item.recurrence === 'daily' ? ' · Hàng ngày' : ' · Một lần'}{item.status === 'cancelled' ? ' · Đã hủy' : ''}</span></div><div className="medication-item-actions"><button className="medication-secondary" type="button" disabled={busy} aria-label={`Sửa lịch ${item.medication_name}`} onClick={() => edit(item)}><Pencil size={16} /> Sửa</button><button className="medication-secondary" type="button" disabled={busy} aria-label={`Xóa lịch ${item.medication_name}`} onClick={() => setDeleting(item.schedule_id)}><Trash2 size={16} /> Xóa</button></div>{deleting === item.schedule_id && <div className="medication-delete" role="group" aria-label="Xác nhận xóa lịch"><p>Xóa lịch này khỏi tài khoản?</p><button type="button" className="medication-primary" disabled={busy} onClick={remove}>Xác nhận xóa</button><button type="button" className="medication-secondary" disabled={busy} onClick={() => setDeleting(null)}>Giữ lại</button></div>}</li>)}</ul>}
  </section>;
}
