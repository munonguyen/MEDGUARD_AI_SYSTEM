import { useEffect, useState } from 'react';
import { ShieldCheck, LoaderCircle, LogOut } from 'lucide-react';
import { createApiClient } from './api';
import App from './App';

export default function AccountGate() {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [registration, setRegistration] = useState(false);
  const [canRegister, setCanRegister] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const api = createApiClient({ csrfToken: session?.csrf_token });
  useEffect(() => {
    let active = true;
    // Remove legacy tenant-shared health profiles from browser storage.
    try { Object.keys(localStorage).filter((key) => key.startsWith('medguard.profile.') || ['medguard.user_meds.data','medguard.med_taken_records','medguard.schedules.taken'].includes(key)).forEach((key) => localStorage.removeItem(key)); } catch { /* Private browsing */ }
    Promise.allSettled([createApiClient().request('/v1/auth/me'), createApiClient().request('/v1/auth/config')]).then(([me, config]) => {
      if (!active) return;
      if (me.status === 'fulfilled') setSession(me.value);
      setCanRegister(config.status === 'fulfilled' && config.value.registration_enabled);
      setLoading(false);
    });
    const expired = () => { setSession(null); setNotice('Phiên đã hết hạn. Đăng nhập lại để tiếp tục.'); };
    window.addEventListener('medguard:session-expired', expired);
    return () => { active = false; window.removeEventListener('medguard:session-expired', expired); };
  }, []);
  const submit = async (event) => {
    event.preventDefault();
    if (busy) return;
    const form = new FormData(event.currentTarget);
    setBusy(true); setError(''); setNotice('');
    try {
      const body = { email: form.get('email'), password: form.get('password') };
      if (registration) {
        await api.request('/v1/auth/register', { method: 'POST', body: { ...body, display_name: form.get('name'), consent: form.get('consent') === 'on' } });
        setRegistration(false); setNotice('Đã tạo tài khoản. Vui lòng đăng nhập.');
      } else setSession(await api.request('/v1/auth/login', { method: 'POST', body }));
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  };
  const logout = async () => {
    try { await api.request('/v1/auth/logout', { method: 'POST' }); setSession(null); }
    catch (failure) { setError(failure.message); }
  };
  if (loading) return <main className="account-loading" aria-label="Đang kiểm tra phiên"><LoaderCircle className="spin" /></main>;
  if (session) return <><App key={session.account.account_id} session={session} onLogout={logout} onSession={setSession} />{error && <div className="global-account-error" role="alert">{error}</div>}</>;
  return <main className="account-page">
    <section className="account-intro"><img src="/static/brand-mark.svg" alt="" /><span className="account-eyebrow">MEDGUARD AI</span><h1>Thông tin rõ ràng.<br />Chăm sóc chủ động.</h1><p>Trợ lý hỗ trợ hiểu triệu chứng, kiểm tra an toàn thuốc và chuẩn bị cho buổi khám.</p><div className="account-trust"><ShieldCheck size={20} /><span>Lịch sử riêng theo tài khoản. Bạn quyết định khi nào chia sẻ hồ sơ sức khỏe.</span></div><p className="account-emergency">Có dấu hiệu cấp cứu? Gọi 115 hoặc đến cơ sở cấp cứu ngay. Không chờ phản hồi từ AI.</p></section>
    <section className="account-form-panel"><form onSubmit={submit} className="account-form">
      <h2>{registration ? 'Tạo tài khoản' : 'Chào mừng trở lại'}</h2><p>{registration ? 'Bắt đầu với một không gian chăm sóc riêng.' : 'Đăng nhập để tiếp tục cuộc trò chuyện của bạn.'}</p>
      {registration && <label>Tên hiển thị<input name="name" required maxLength="80" autoComplete="name" /></label>}
      <label>Email<input name="email" type="email" required maxLength="254" autoComplete="email" /></label>
      <label>Mật khẩu<input name="password" type="password" required minLength="12" maxLength="128" autoComplete={registration ? 'new-password' : 'current-password'} /></label>
      {registration && <><small>Dùng ít nhất 12 ký tự. Bạn có thể dán mật khẩu từ trình quản lý mật khẩu.</small><label className="consent-option"><input name="consent" type="checkbox" /><span>Tôi đồng ý xử lý và lưu thông tin sức khỏe để hỗ trợ tư vấn AI. Có thể thay đổi lựa chọn sau khi đăng nhập. AI có thể sai và không thay thế khám trực tiếp.</span></label></>}
      {error && <p className="account-error" role="alert">{error}</p>}{notice && <p className="account-notice" role="status">{notice}</p>}
      <button className="account-submit" disabled={busy} type="submit">{busy ? 'Đang xử lý…' : registration ? 'Tạo tài khoản' : 'Đăng nhập'}</button>
      {canRegister && <button className="account-switch" type="button" disabled={busy} onClick={() => { setRegistration(!registration); setError(''); setNotice(''); }}>{registration ? 'Đã có tài khoản? Đăng nhập' : 'Chưa có tài khoản? Đăng ký'}</button>}
    </form></section>
  </main>;
}
