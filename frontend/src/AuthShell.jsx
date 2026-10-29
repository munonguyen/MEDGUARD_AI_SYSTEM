import { useEffect, useState, useMemo } from 'react';
import App from './App';
import { setBrowserSession } from './api';
import InteractiveBackground from './InteractiveBackground';
import {
  Mail,
  Lock,
  Eye,
  EyeOff,
  KeyRound,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  ArrowRight,
  Activity,
  HeartPulse,
  Shield,
  Stethoscope,
  ChevronLeft,
  RefreshCw,
  FileCheck,
} from 'lucide-react';

async function auth(path, body, csrf, method = 'POST') {
  const r = await fetch('/v1/auth/' + path, {
    method,
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      ...(csrf ? { 'X-CSRF-Token': csrf } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  const data = await r.json();
  if (!r.ok) {
    if (
      r.status === 401 &&
      csrf &&
      ['session_expired', 'login_required'].includes(data.detail?.error_code || data.error_code)
    ) {
      window.dispatchEvent(new Event('medguard:session-expired'));
    }
    const code = data.detail?.error_code || data.error_code;
    const messages = {
      invalid_credentials: 'Email, mật khẩu hoặc mã xác thực không đúng. Mã MFA chỉ dùng một lần.',
      email_verification_required: 'Hãy xác thực email trước khi đăng nhập.',
      email_delivery_failed: 'Máy chủ chưa gửi được email. Hãy thử lại hoặc liên hệ quản trị viên.',
      email_delivery_not_configured: 'Máy chủ chưa cấu hình gửi email. Vui lòng liên hệ quản trị viên.',
      authentication_rate_limited: 'Bạn đã thử quá nhiều lần. Hãy đợi một phút rồi thử lại.',
      password_requires_12_to_256_bytes: 'Mật khẩu cần ít nhất 12 ký tự và tối đa 256 byte.',
      account_not_created: 'Không thể tạo tài khoản. Nếu đã đăng ký, hãy đăng nhập hoặc khôi phục mật khẩu.',
      invalid_or_expired_token: 'Liên kết đã hết hạn hoặc đã được sử dụng.',
      session_expired: 'Phiên đã hết hạn. Hãy đăng nhập lại.',
      cross_origin_request:
        'Địa chỉ trang không khớp cấu hình bảo mật của máy chủ. Hãy kiểm tra địa chỉ truy cập và khởi động lại frontend/backend.',
      csrf_invalid: 'Không thể xác thực yêu cầu. Hãy tải lại trang.',
      consent_required: 'Cần đồng ý xử lý dữ liệu để tạo tài khoản.',
    };
    throw new Error(messages[code] || data.detail?.message || data.message || 'Không thể hoàn tất yêu cầu');
  }
  return data;
}

const GUEST_MAX_QUESTIONS = 3;

export default function AuthShell() {
  const [user, setUser] = useState(null);
  const [csrf, setCsrf] = useState('');
  const [loading, setLoading] = useState(() => {
    try {
      return localStorage.getItem('medguard.has_session') === '1';
    } catch {
      return false;
    }
  });
  const [busy, setBusy] = useState(false);

  const query = new URLSearchParams(location.hash.slice(1) || location.search);
  const [mode, setMode] = useState(() =>
    query.has('reset_token') ? 'reset' : query.has('verify_token') ? 'verify' : 'login'
  );

  const [isGuest, setIsGuest] = useState(() => {
    try {
      const q = new URLSearchParams(location.hash.slice(1) || location.search);
      if (
        q.has('guest') ||
        q.get('view') === 'companion' ||
        q.get('view') === 'navigation' ||
        q.get('view') === 'profile' ||
        location.hash.includes('companion')
      )
        return true;
      return localStorage.getItem('medguard.guest_mode') === 'true';
    } catch {
      return false;
    }
  });

  const [guestCount, setGuestCount] = useState(() => {
    try {
      return parseInt(localStorage.getItem('medguard.guest_usage_count') || '0', 10);
    } catch {
      return 0;
    }
  });
  const guestRemaining = Math.max(0, GUEST_MAX_QUESTIONS - guestCount);

  // Form states
  const [email, setEmail] = useState(() => {
    try {
      return localStorage.getItem('medguard.remembered_email') || '';
    } catch {
      return '';
    }
  });
  const [password, setPassword] = useState('');
  const [otp, setOtp] = useState('');
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [backups, setBackups] = useState([]);
  const [manage, setManage] = useState(false);
  const [sessions, setSessions] = useState([]);
  const [newPassword, setNewPassword] = useState('');
  const [setup, setSetup] = useState(null);
  const [linkToken, setLinkToken] = useState(query.get('reset_token') || query.get('verify_token') || '');

  // UI Interactive States
  const [showPassword, setShowPassword] = useState(false);
  const [capsLockActive, setCapsLockActive] = useState(false);
  const [rememberEmail, setRememberEmail] = useState(() => {
    try {
      return Boolean(localStorage.getItem('medguard.remembered_email'));
    } catch {
      return false;
    }
  });
  const [mousePos, setMousePos] = useState({ x: 500, y: 300 });

  // Mouse movement listener for ambient lighting
  const handleMouseMove = (e) => {
    setMousePos({ x: e.clientX, y: e.clientY });
  };

  // Password strength score (0 to 4)
  const passwordStrength = useMemo(() => {
    if (!password) return 0;
    let score = 0;
    if (password.length >= 8) score++;
    if (password.length >= 12) score++;
    if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score++;
    if (/[0-9]/.test(password) || /[^A-Za-z0-9]/.test(password)) score++;
    return score;
  }, [password]);

  const strengthLabels = ['Rất yếu', 'Yếu', 'Trung bình', 'Khá tốt', 'Rất mạnh (An toàn)'];
  const strengthColors = ['#ef4444', '#f97316', '#eab308', '#10b981', '#14b8a6'];

  useEffect(() => {
    const readLink = () => {
      const params = new URLSearchParams(location.hash.slice(1) || location.search);
      const token = params.get('reset_token') || params.get('verify_token');
      if (token) {
        setLinkToken(token);
        setMode(params.has('reset_token') ? 'reset' : 'verify');
        history.replaceState(null, '', location.pathname);
      }
    };
    readLink();
    window.addEventListener('hashchange', readLink);
    return () => window.removeEventListener('hashchange', readLink);
  }, []);

  const clear = () => {
    try {
      localStorage.removeItem('medguard.auth.remember');
      localStorage.removeItem('medguard.has_session');
    } catch {}
    setBrowserSession(null);
    setUser(null);
    setCsrf('');
    setPassword('');
    setNewPassword('');
    setOtp('');
    setSetup(null);
    setManage(false);
    setMode('login');
  };

  useEffect(() => {
    const expired = () => {
      clear();
      setError('Phiên đã hết hạn. Hãy đăng nhập lại.');
    };
    window.addEventListener('medguard:session-expired', expired);

    const initAuth = async () => {
      try {
        localStorage.removeItem('medguard.auth.remember');
      } catch {}
      try {
        const a = await auth('me', null, null, 'GET');
        if (a && a.user) {
          setUser(a.user);
          setEmail(a.user.email);
          let csrfToken = a.csrf_token;
          if (!csrfToken) {
            try {
              const b = await auth('csrf', null, null, 'GET');
              csrfToken = b.csrf_token;
            } catch {}
          }
          setCsrf(csrfToken || '');
          setBrowserSession({ user: a.user, csrf: csrfToken || '' });
          try {
            localStorage.setItem('medguard.has_session', '1');
          } catch {}
          return;
        }
      } catch {
        try {
          localStorage.removeItem('medguard.has_session');
        } catch {}
        setBrowserSession(null);
      }
    };

    initAuth().finally(() => setLoading(false));
    return () => window.removeEventListener('medguard:session-expired', expired);
  }, []);

  const perform = async (fn) => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const handleKeyModifier = (e) => {
    if (e.getModifierState) {
      setCapsLockActive(e.getModifierState('CapsLock'));
    }
  };

  const submit = (e) => {
    e.preventDefault();
    const form = e.currentTarget;
    const submitEmail = form.elements?.username?.value || email;
    const submitPassword = form.elements?.password?.value || password;
    const submitOtp = form.elements?.otp?.value || otp;

    // Handle remembered email
    try {
      if (rememberEmail && submitEmail) {
        localStorage.setItem('medguard.remembered_email', submitEmail);
      } else {
        localStorage.removeItem('medguard.remembered_email');
      }
      localStorage.removeItem('medguard.auth.remember');
    } catch {}

    perform(async () => {
      if (mode === 'login') {
        const d = await auth('login', { email: submitEmail, password: submitPassword, otp: submitOtp || null });
        setUser(d.user);
        setEmail(d.user.email);
        setCsrf(d.csrf_token);
        setBrowserSession({ user: d.user, csrf: d.csrf_token });
        try {
          localStorage.setItem('medguard.has_session', '1');
        } catch {}
        setPassword('');
        setOtp('');
        setBackups([]);
        setIsGuest(false);
        try {
          localStorage.removeItem('medguard.guest_mode');
        } catch {}
      }
      if (mode === 'register') {
        const d = await auth('register', { email: submitEmail, password: submitPassword, consent });
        setNotice(d.message);
        setMode('login');
        setPassword('');
      }
      if (mode === 'forgot') {
        const d = await auth('forgot-password', { email: submitEmail });
        setNotice(d.message);
      }
      if (mode === 'reset') {
        const d = await auth('reset-password', { token: linkToken, password: submitPassword });
        clear();
        setNotice(d.message);
      }
      if (mode === 'verify') {
        const d = await auth('verify-email', { token: linkToken });
        setNotice(d.message);
        setMode('login');
      }
    });
  };

  if (loading) {
    return (
      <main className="auth-screen auth-loading-screen">
        <div className="auth-loading-ambient-glow" />
        <div className="auth-loading-card">
          <div className="auth-loading-brand-wrap">
            <div className="auth-loading-ring-outer" />
            <div className="auth-loading-ring-inner" />
            <img src="/static/brand-mark.svg" alt="MedGuard AI" className="auth-loading-logo" width="48" height="48" />
          </div>

          <div className="auth-loading-title-group">
            <h2 className="auth-loading-app-title">MedGuard AI</h2>
            <span className="auth-loading-subtext">Hệ Thống Trợ Lý Lâm Sàng & Quản Lý Sức Khỏe Toàn Diện</span>
          </div>

          <div className="auth-loading-progress-box">
            <div className="auth-loading-progress-track">
              <div className="auth-loading-progress-bar" />
            </div>
            <div className="auth-loading-progress-pulse" />
          </div>

          <p className="auth-loading-status" role="status">
            Đang kết nối phiên làm việc &amp; chuẩn bị hồ sơ lâm sàng…
          </p>

          <div className="auth-loading-badges">
            <span className="auth-badge-item">
              <ShieldCheck size={13} className="text-teal" />
              <span>Chuẩn Dược DAV</span>
            </span>
            <span className="auth-badge-dot">•</span>
            <span className="auth-badge-item">
              <HeartPulse size={13} className="text-teal" />
              <span>Tiết Kiệm BHYT</span>
            </span>
            <span className="auth-badge-dot">•</span>
            <span className="auth-badge-item">
              <CheckCircle2 size={13} className="text-teal" />
              <span>Bảo Mật Y Tế 24/7</span>
            </span>
          </div>
        </div>
      </main>
    );
  }

  if (!user && isGuest && mode !== 'reset' && mode !== 'verify') {
    return (
      <div className="authenticated-shell guest-shell">
        <App
          key="guest-app"
          account={null}
          isGuest={true}
          guestCount={guestCount}
          guestMax={GUEST_MAX_QUESTIONS}
          onGuestQuestionAsked={() => {
            setGuestCount((prev) => {
              const next = prev + 1;
              try {
                localStorage.setItem('medguard.guest_usage_count', String(next));
              } catch {}
              return next;
            });
          }}
          onRequireAuth={() => {
            setIsGuest(false);
            try {
              localStorage.removeItem('medguard.guest_mode');
            } catch {}
            setMode('login');
          }}
        />
      </div>
    );
  }

  // Account Management Modal / Screen
  if (manage) {
    const action = (path, body, then) =>
      perform(async () => {
        const d = await auth(path, body, csrf);
        setNotice(d.message || 'Hoàn tất');
        if (then) await then(d);
      });

    return (
      <main className="auth-screen auth-manage-viewport" onMouseMove={handleMouseMove}>
        <InteractiveBackground mouseX={mousePos.x} mouseY={mousePos.y} />
        <section className="auth-card auth-manage-card">
          <div className="auth-manage-header">
            <div className="auth-brand-badge">
              <ShieldCheck size={18} />
              <span>TRUNG TÂM BẢO MẬT & TÀI KHOẢN</span>
            </div>
            <h1>Cài đặt Tài khoản & Xác thực</h1>
            <p className="auth-card-subtitle">
              {user.email} ·{' '}
              <span className={user.email_verified ? 'text-teal-400' : 'text-amber-400'}>
                {user.email_verified ? '● Email đã xác thực' : '○ Email chưa xác thực'}
              </span>
            </p>
          </div>

          {error && (
            <div className="auth-alert error" role="alert">
              <AlertCircle size={18} />
              <span>{error}</span>
            </div>
          )}
          {notice && (
            <div className="auth-alert success" role="status">
              <CheckCircle2 size={18} />
              <span>{notice}</span>
            </div>
          )}

          <div className="auth-manage-section">
            <h2>Xác thực danh tính</h2>
            {!user.email_verified && (
              <button
                type="button"
                className="auth-secondary-btn"
                disabled={busy}
                onClick={() => action('verification-email')}
              >
                <Mail size={15} /> Gửi email xác thực lại
              </button>
            )}
          </div>

          <div className="auth-manage-section">
            <h2>Đổi mật khẩu bảo mật</h2>
            <label>
              <span>Mật khẩu hiện tại</span>
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            <label>
              <span>Mật khẩu mới (tối thiểu 12 ký tự)</span>
              <input
                type="password"
                autoComplete="new-password"
                minLength={12}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />
            </label>
            <label>
              <span>Mã xác thực MFA hoặc mã khôi phục</span>
              <input
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
                maxLength={32}
                placeholder="6 số hoặc mã khôi phục"
              />
            </label>
            <button
              type="button"
              className="auth-primary-btn"
              disabled={busy || !password || !newPassword}
              onClick={() =>
                action('password', { current_password: password, new_password: newPassword, otp: otp || null }, clear)
              }
            >
              Cập nhật mật khẩu & Thu hồi các phiên cũ
            </button>
          </div>

          <div className="auth-manage-section">
            <h2>Xác thực 2 yếu tố (2FA / MFA)</h2>
            {!user.mfa_enabled ? (
              <>
                <button
                  type="button"
                  className="auth-secondary-btn"
                  disabled={busy}
                  onClick={() => action('mfa/setup', { current_password: password }, setSetup)}
                >
                  <KeyRound size={16} /> Thiết lập MFA Authenticator
                </button>
                {setup && (
                  <div className="auth-mfa-box">
                    <p>Thêm khóa vào ứng dụng Authenticator (Google/Microsoft Authenticator) rồi nhập mã 6 số:</p>
                    <code className="auth-secret">{setup.secret}</code>
                    <input
                      type="text"
                      placeholder="Nhập mã 6 chữ số từ app"
                      value={otp}
                      onChange={(e) => setOtp(e.target.value)}
                    />
                    <button
                      type="button"
                      className="auth-primary-btn"
                      disabled={busy || !otp}
                      onClick={() =>
                        action('mfa/enable', { token: setup.setup_token, code: otp }, (d) => {
                          setBackups(d.recovery_codes || []);
                          clear();
                        })
                      }
                    >
                      Xác nhận kích hoạt MFA
                    </button>
                  </div>
                )}
              </>
            ) : (
              <button
                type="button"
                className="auth-danger-btn"
                disabled={busy}
                onClick={() => action('mfa/disable', { current_password: password, otp: otp || null }, clear)}
              >
                Hủy kích hoạt MFA
              </button>
            )}
          </div>

          <div className="auth-manage-section">
            <h2>Phiên đăng nhập đang hoạt động</h2>
            <div className="auth-sessions-list">
              {sessions.map((s) => (
                <div className="auth-session-item" key={s.id}>
                  <div className="auth-session-meta">
                    <strong>{s.current ? '● Thiết bị hiện tại' : '○ Thiết bị khác'}</strong>
                    <small>Hoạt động gần nhất: {new Date(s.last_seen * 1000).toLocaleString()}</small>
                  </div>
                  <button
                    type="button"
                    className="auth-revoke-btn"
                    disabled={busy}
                    onClick={() =>
                      perform(async () => {
                        await auth('sessions/' + s.id, null, csrf, 'DELETE');
                        if (s.current) clear();
                        else setSessions(sessions.filter((x) => x.id !== s.id));
                      })
                    }
                  >
                    Thu hồi
                  </button>
                </div>
              ))}
            </div>
            <button
              type="button"
              className="auth-secondary-btn auth-logout-all-btn"
              disabled={busy}
              onClick={() => action('logout-all', null, clear)}
            >
              Đăng xuất khỏi tất cả thiết bị
            </button>
          </div>

          <div className="auth-manage-footer">
            <button
              type="button"
              className="auth-back-btn"
              onClick={() => {
                setManage(false);
                setPassword('');
                setOtp('');
                setSetup(null);
              }}
            >
              <ChevronLeft size={16} /> Quay lại màn hình làm việc
            </button>
          </div>
        </section>
      </main>
    );
  }

  // Active User Logged In
  if (user && mode !== 'reset' && mode !== 'verify') {
    const action = (path, body, then) =>
      perform(async () => {
        const d = await auth(path, body, csrf);
        setNotice(d.message || 'Hoàn tất');
        if (then) await then(d);
      });

    return (
      <App
        key={user.id}
        account={user}
        onManageAccount={() =>
          perform(async () => {
            setManage(true);
            setSessions((await auth('sessions', null, csrf, 'GET')).sessions);
          })
        }
        onLogout={() => action('logout', null, clear)}
      />
    );
  }

  // Main Login / Registration / Recovery Screen
  return (
    <main className="auth-screen auth-modern-viewport" onMouseMove={handleMouseMove}>
      <InteractiveBackground mouseX={mousePos.x} mouseY={mousePos.y} />

      <div className="auth-layout-container">
        {/* Left Column: Brand Showcase & Value Propositions (Desktop/Tablet) */}
        <section className="auth-hero-showcase" aria-label="Giới thiệu MedGuard AI">
          <div className="auth-hero-header">
            <div className="auth-hero-badge">
              <span className="auth-pulse-dot" />
              <span>HỆ THỐNG AI Y TẾ THẾ HỆ MỚI • MEDGUARD</span>
            </div>
            <div className="auth-hero-brand">
              <img
                src="/static/brand-mark.svg"
                alt="Biểu trưng MedGuard AI"
                width="54"
                height="54"
                className="auth-hero-logo"
              />
              <div className="auth-hero-brand-text">
                <h2>MedGuard AI</h2>
                <p>Nền tảng Lâm sàng & Bác sĩ Ảo 3D</p>
              </div>
            </div>
            <h1 className="auth-hero-headline">
              Chăm sóc sức khỏe thông minh, chuẩn xác &amp; bảo mật toàn trình.
            </h1>
            <p className="auth-hero-description">
              Hệ thống trợ lý y tế tích hợp chẩn đoán đa chuyên khoa, phân tích tương tác thuốc thời gian thực và mô hình
              sinh đôi kỹ thuật số giải phẫu học trực quan.
            </p>
          </div>

          <div className="auth-feature-cards">
            <div className="auth-feature-card">
              <div className="auth-feature-icon">
                <Stethoscope size={22} />
              </div>
              <div className="auth-feature-text">
                <h3>Bác sĩ Ảo 3D &amp; Hội thoại Giọng nói</h3>
                <p>Tương tác tự nhiên thời gian thực, tư vấn triệu chứng và định hướng chuyên khoa tức thì.</p>
              </div>
            </div>

            <div className="auth-feature-card">
              <div className="auth-feature-icon">
                <HeartPulse size={22} />
              </div>
              <div className="auth-feature-text">
                <h3>Kiểm tra An toàn Thuốc &amp; Dị ứng</h3>
                <p>Cảnh báo tương tác dược động học, liều lượng và rủi ro thuốc giả bằng mã định danh.</p>
              </div>
            </div>

            <div className="auth-feature-card">
              <div className="auth-feature-icon">
                <Shield size={22} />
              </div>
              <div className="auth-feature-text">
                <h3>Bảo mật Dữ liệu Chuẩn HIPAA &amp; TiDB</h3>
                <p>Mã hóa AES-256 bit, phân quyền nhiều lớp và bảo đảm quyền riêng tư y tế tuyệt đối.</p>
              </div>
            </div>
          </div>

          {/* System Telemetry Indicator */}
          <div className="auth-system-status">
            <div className="auth-status-item">
              <span className="auth-live-dot" />
              <span>Máy chủ AI: <strong>Trực tuyến</strong></span>
            </div>
            <div className="auth-status-divider" />
            <div className="auth-status-item">
              <span>Độ trễ: <strong>~18ms</strong></span>
            </div>
            <div className="auth-status-divider" />
            <div className="auth-status-item">
              <span>Chuẩn mã hóa: <strong>AES-256</strong></span>
            </div>
          </div>
        </section>

        {/* Right Column: Interactive Frosted Glass Auth Card */}
        <section className="auth-card auth-card-modern" aria-label="Biểu mẫu xác thực">
          {/* Mobile Top Brand (Hidden on Desktop) */}
          <div className="auth-card-mobile-brand">
            <img src="/static/brand-mark.svg" alt="Biểu trưng MedGuard AI" width="44" height="44" />
            <div>
              <h3>MedGuard AI</h3>
              <span>Clinical Operations Workspace</span>
            </div>
          </div>

          {/* Sliding Mode Tab Switcher (for Login & Register) */}
          {['login', 'register'].includes(mode) && (
            <div className="auth-mode-tabs" aria-label="Lựa chọn phương thức">
              <div
                className={`auth-tab-glider ${mode === 'register' ? 'glider-register' : 'glider-login'}`}
                aria-hidden="true"
              />
              <button
                type="button"
                id="tab-login"
                className={`auth-tab-btn ${mode === 'login' ? 'active' : ''}`}
                aria-label="Tab Đăng nhập"
                onClick={() => {
                  setMode('login');
                  setError('');
                }}
              >
                <span>Đăng nhập</span>
              </button>
              <button
                type="button"
                id="tab-register"
                className={`auth-tab-btn ${mode === 'register' ? 'active' : ''}`}
                aria-label="Tab Đăng ký"
                onClick={() => {
                  setMode('register');
                  setError('');
                }}
              >
                <span>Đăng ký</span>
              </button>
            </div>

          )}

          {/* Header Context */}
          <header className="auth-card-header">
            <h1 className="auth-title">
              {({
                login: 'Đăng nhập tài khoản',
                register: 'Tạo tài khoản MedGuard',
                forgot: 'Khôi phục mật khẩu',
                reset: 'Thiết lập mật khẩu mới',
                verify: 'Xác thực địa chỉ email',
              })[mode]}
            </h1>
            <p className="auth-subtitle">
              {({
                login: 'Truy cập không gian làm việc lâm sàng và hồ sơ sức khỏe của bạn.',
                register: 'Bắt đầu sử dụng trợ lý y tế thông minh và đồng hành sức khỏe.',
                forgot: 'Nhập email đã đăng ký để nhận liên kết khôi phục an toàn.',
                reset: 'Nhập mật khẩu mới mạnh để bảo vệ tài khoản của bạn.',
                verify: 'Xác nhận kích hoạt tài khoản để truy cập đầy đủ tính năng.',
              })[mode]}
            </p>
          </header>

          {/* Interactive Form */}
          <form onSubmit={submit} method="post" action="#" className="auth-form" noValidate={false}>
            {/* Email Field */}
            {['login', 'register', 'forgot'].includes(mode) && (
              <div className="auth-field-group">
                <label htmlFor="auth-username" className="auth-label">
                  Email
                </label>
                <div className="auth-input-wrapper">
                  <Mail className="auth-input-icon" size={18} aria-hidden="true" />
                  <input
                    id="auth-username"
                    name="username"
                    type="email"
                    autoComplete="username"
                    required
                    maxLength={254}
                    placeholder="bacsi.nguyen@benhvien.vn"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="auth-input"
                  />
                </div>
              </div>
            )}

            {/* Password Field */}
            {['login', 'register', 'reset'].includes(mode) && (
              <div className="auth-field-group">
                <div className="auth-password-header">
                  <label htmlFor="auth-password" className="auth-label">
                    Mật khẩu
                  </label>
                  {mode === 'login' && (
                    <button
                      type="button"
                      className="auth-forgot-link"
                      onClick={() => {
                        setMode('forgot');
                        setError('');
                      }}
                    >
                      Quên mật khẩu?
                    </button>
                  )}
                </div>

                <div className="auth-input-wrapper">
                  <Lock className="auth-input-icon" size={18} aria-hidden="true" />
                  <input
                    id="auth-password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                    required
                    minLength={mode === 'login' ? 1 : 12}
                    maxLength={256}
                    placeholder={mode === 'login' ? 'Nhập mật khẩu của bạn' : 'Ít nhất 12 ký tự bảo mật'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    onKeyDown={handleKeyModifier}
                    onKeyUp={handleKeyModifier}
                    className="auth-input auth-password-input"
                  />
                  <button
                    type="button"
                    className="auth-password-toggle-btn"
                    onClick={() => setShowPassword((prev) => !prev)}
                    title={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                    aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>

                {/* Caps Lock Detection Warning */}
                {capsLockActive && (
                  <div className="auth-capslock-badge" role="status">
                    <span>⚠️ Phím Caps Lock đang bật</span>
                  </div>
                )}

                {/* Password Strength Meter for Register/Reset */}
                {['register', 'reset'].includes(mode) && password.length > 0 && (
                  <div className="auth-strength-container" aria-live="polite">
                    <div className="auth-strength-bars">
                      {[1, 2, 3, 4].map((step) => (
                        <div
                          key={step}
                          className="auth-strength-segment"
                          style={{
                            background: passwordStrength >= step ? strengthColors[passwordStrength] : '#334155',
                          }}
                        />
                      ))}
                    </div>
                    <div className="auth-strength-text">
                      <span>Độ mạnh: </span>
                      <strong style={{ color: strengthColors[passwordStrength] }}>
                        {strengthLabels[passwordStrength]}
                      </strong>
                    </div>
                  </div>
                )}

                {mode === 'register' && (
                  <small className="auth-hint">
                    Dùng ít nhất 12 ký tự; kết hợp chữ in hoa, chữ số và ký tự đặc biệt.
                  </small>
                )}
              </div>
            )}

            {/* MFA / OTP Field */}
            {mode === 'login' && (
              <div className="auth-field-group">
                <label htmlFor="auth-otp" className="auth-label">
                  Mã MFA hoặc mã khôi phục (nếu đã bật)
                </label>
                <div className="auth-input-wrapper">
                  <KeyRound className="auth-input-icon" size={18} aria-hidden="true" />
                  <input
                    id="auth-otp"
                    name="otp"
                    autoComplete="one-time-code"
                    maxLength={32}
                    placeholder="Mã 6 chữ số từ app Authenticator"
                    value={otp}
                    onChange={(e) => setOtp(e.target.value)}
                    className="auth-input"
                  />
                </div>
              </div>
            )}

            {/* Remember Email Option (Login mode) */}
            {mode === 'login' && (
              <label className="auth-remember-label">
                <input
                  type="checkbox"
                  checked={rememberEmail}
                  onChange={(e) => setRememberEmail(e.target.checked)}
                />
                <span>Ghi nhớ địa chỉ email trên thiết bị này</span>
              </label>
            )}

            {/* Consent Checkbox for Register */}
            {mode === 'register' && (
              <label className="auth-consent">
                <input
                  type="checkbox"
                  checked={consent}
                  required
                  onChange={(e) => setConsent(e.target.checked)}
                />
                <span>
                  Tôi đồng ý sử dụng dữ liệu tôi cung cấp để xử lý yêu cầu hỗ trợ sức khỏe. AI không thay thế bác sĩ.
                </span>
              </label>
            )}

            {/* Error Message */}
            {error && (
              <div className="auth-alert error" role="alert">
                <AlertCircle size={18} className="auth-alert-icon" />
                <span>{error}</span>
              </div>
            )}

            {/* Success / Status Notice */}
            {notice && (
              <div className="auth-alert success" role="status">
                <CheckCircle2 size={18} className="auth-alert-icon" />
                <span>{notice}</span>
              </div>
            )}

            {/* MFA Backup Codes Reveal */}
            {backups.length > 0 && (
              <div className="auth-backups-container">
                <h2>Mã khôi phục — lưu lại trước khi tiếp tục</h2>
                <p>Mỗi mã chỉ sử dụng một lần. Không chia sẻ các mã này.</p>
                <div className="auth-backups-grid">
                  {backups.map((c) => (
                    <code className="auth-secret" key={c}>
                      {c}
                    </code>
                  ))}
                </div>
              </div>
            )}

            {/* Main Submit Button */}
            <button type="submit" className="auth-submit-btn" disabled={busy}>
              {busy ? (
                <>
                  <RefreshCw size={18} className="auth-spinner-icon" />
                  <span>Đang xử lý…</span>
                </>
              ) : (
                <>
                  <span>
                    {({
                      login: 'Đăng nhập',
                      register: 'Tạo tài khoản',
                      forgot: 'Gửi liên kết khôi phục',
                      reset: 'Đặt lại mật khẩu',
                      verify: 'Xác thực email',
                    })[mode]}
                  </span>
                  <ArrowRight size={18} className="auth-btn-arrow" />
                </>
              )}
            </button>
          </form>

          {/* Resend Verification Email (Login mode) */}
          {mode === 'login' && (
            <button
              type="button"
              className="auth-resend-link"
              disabled={busy || !email}
              onClick={() =>
                perform(async () => setNotice((await auth('verification-email', { email })).message))
              }
            >
              <Mail size={14} /> Gửi lại email xác thực
            </button>
          )}

          {/* Navigation for Forgot/Reset modes */}
          {['forgot', 'reset', 'verify'].includes(mode) && (
            <nav className="auth-bottom-nav">
              <button
                type="button"
                className="auth-nav-link"
                onClick={() => {
                  setMode('login');
                  setError('');
                }}
              >
                <ChevronLeft size={16} /> Quay lại màn hình đăng nhập
              </button>
            </nav>
          )}

          {/* Quick Guest Mode Experience */}
          <div className="auth-guest-section">
            <div className="auth-guest-divider">
              <span>HOẶC TRẢI NGHIỆM NHANH</span>
            </div>
            <button
              type="button"
              className="auth-guest-btn"
              onClick={() => {
                setIsGuest(true);
                try {
                  localStorage.setItem('medguard.guest_mode', 'true');
                } catch {}
              }}
            >
              <div className="auth-guest-btn-content">
                <Sparkles size={18} className="auth-guest-sparkle" />
                <span>
                  Trải nghiệm ngay không cần đăng nhập ({guestRemaining > 0 ? `${guestRemaining} lượt dùng thử` : 'dùng thử'})
                </span>
              </div>
              <ArrowRight size={16} className="auth-guest-arrow" />
            </button>
          </div>

          {/* Footer Security Badges */}
          <footer className="auth-card-footer">
            <div className="auth-security-pill">
              <ShieldCheck size={14} />
              <span>Mã hóa AES-256 • Chuẩn An toàn Y tế HIPAA</span>
            </div>
          </footer>
        </section>
      </div>
    </main>
  );
}
