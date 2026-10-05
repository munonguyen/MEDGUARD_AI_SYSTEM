import {useEffect,useState} from 'react';
import App from './App';
import {setBrowserSession} from './api';

async function auth(path,body,csrf,method='POST'){
 const r=await fetch('/v1/auth/'+path,{method,credentials:'same-origin',headers:{'Content-Type':'application/json',...(csrf?{'X-CSRF-Token':csrf}:{})},...(body?{body:JSON.stringify(body)}:{})});
 const data=await r.json();if(!r.ok){
  if(r.status===401&&csrf&&['session_expired','login_required'].includes(data.detail?.error_code||data.error_code))window.dispatchEvent(new Event('medguard:session-expired'));
  const code=data.detail?.error_code||data.error_code;
  const messages={invalid_credentials:'Email, mật khẩu hoặc mã xác thực không đúng. Mã MFA chỉ dùng một lần.',email_verification_required:'Hãy xác thực email trước khi đăng nhập.',email_delivery_failed:'Máy chủ chưa gửi được email. Hãy thử lại hoặc liên hệ quản trị viên.',email_delivery_not_configured:'Máy chủ chưa cấu hình gửi email. Vui lòng liên hệ quản trị viên.',authentication_rate_limited:'Bạn đã thử quá nhiều lần. Hãy đợi một phút rồi thử lại.',password_requires_12_to_256_bytes:'Mật khẩu cần ít nhất 12 ký tự và tối đa 256 byte.',account_not_created:'Không thể tạo tài khoản. Nếu đã đăng ký, hãy đăng nhập hoặc khôi phục mật khẩu.',invalid_or_expired_token:'Liên kết đã hết hạn hoặc đã được sử dụng.',session_expired:'Phiên đã hết hạn. Hãy đăng nhập lại.',csrf_invalid:'Không thể xác thực yêu cầu. Hãy tải lại trang.',consent_required:'Cần đồng ý xử lý dữ liệu để tạo tài khoản.'};
  throw new Error(messages[code]||data.detail?.message||data.message||'Không thể hoàn tất yêu cầu');
 }return data;
}
export default function AuthShell(){
 const [user,setUser]=useState(null),[csrf,setCsrf]=useState(''),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false);
 const query=new URLSearchParams(location.hash.slice(1) || location.search);
 const [mode,setMode]=useState(()=>query.has('reset_token')?'reset':query.has('verify_token')?'verify':'login');
 const [email,setEmail]=useState(''),[password,setPassword]=useState(''),[otp,setOtp]=useState(''),[consent,setConsent]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 const [backups,setBackups]=useState([]);
 const [manage,setManage]=useState(false),[sessions,setSessions]=useState([]),[newPassword,setNewPassword]=useState(''),[setup,setSetup]=useState(null);
 const [linkToken]=useState(query.get('reset_token')||query.get('verify_token')||'');
 useEffect(()=>{if(linkToken)history.replaceState(null,'',location.pathname);},[linkToken]);
 const clear=()=>{setBrowserSession(null);setUser(null);setCsrf('');setPassword('');setNewPassword('');setOtp('');setSetup(null);setManage(false);setMode('login');};
 useEffect(()=>{
  const expired=()=>{clear();setError('Phiên đã hết hạn. Hãy đăng nhập lại.');};window.addEventListener('medguard:session-expired',expired);
  Promise.all([auth('me',null,null,'GET'),auth('csrf',null,null,'GET')]).then(([a,b])=>{setUser(a.user);setEmail(a.user.email);setCsrf(b.csrf_token);setBrowserSession({user:a.user,csrf:b.csrf_token});}).catch(()=>{}).finally(()=>setLoading(false));
  return()=>window.removeEventListener('medguard:session-expired',expired);
 },[]);
 const perform=async(fn)=>{setBusy(true);setError('');setNotice('');try{await fn();}catch(e){setError(e.message);}finally{setBusy(false);}};
 const submit=e=>{e.preventDefault();perform(async()=>{
  if(mode==='login'){const d=await auth('login',{email,password,otp:otp||null});setUser(d.user);setCsrf(d.csrf_token);setBrowserSession({user:d.user,csrf:d.csrf_token});setPassword('');setOtp('');setBackups([]);}
  if(mode==='register'){const d=await auth('register',{email,password,consent});setNotice(d.message);setMode('login');setPassword('');}
  if(mode==='forgot'){const d=await auth('forgot-password',{email});setNotice(d.message);}
  if(mode==='reset'){const d=await auth('reset-password',{token:linkToken,password});clear();setNotice(d.message);}
  if(mode==='verify'){const d=await auth('verify-email',{token:linkToken});setNotice(d.message);setMode('login');}
 });};
 if(loading)return <main className="auth-screen"><p role="status">Đang kiểm tra phiên đăng nhập…</p></main>;
 if(!user||mode==='reset'||mode==='verify')return <main className="auth-screen"><section className="auth-card"><img src="/static/brand-mark.svg" alt=""/><h1>MedGuard AI</h1><p>{({login:'Đăng nhập để quản lý hội thoại riêng của bạn',register:'Tạo tài khoản',forgot:'Khôi phục mật khẩu',reset:'Đặt mật khẩu mới',verify:'Xác thực email'})[mode]}</p>
  <form onSubmit={submit}>
   {['login','register','forgot'].includes(mode)&&<label>Email<input type="email" autoComplete="username" required maxLength={254} value={email} onChange={e=>setEmail(e.target.value)}/></label>}
   {['login','register','reset'].includes(mode)&&<label>Mật khẩu<input type="password" autoComplete={mode==='login'?'current-password':'new-password'} required minLength={mode==='login'?1:12} maxLength={256} value={password} onChange={e=>setPassword(e.target.value)}/></label>}
   {mode==='register'&&<small>Dùng ít nhất 12 ký tự; nên dùng mật khẩu riêng hoặc trình quản lý mật khẩu.</small>}
   {mode==='login'&&<label>Mã MFA hoặc mã khôi phục (nếu đã bật)<input autoComplete="one-time-code" maxLength={32} value={otp} onChange={e=>setOtp(e.target.value)}/></label>}
   {mode==='register'&&<label className="auth-consent"><input type="checkbox" checked={consent} required onChange={e=>setConsent(e.target.checked)}/>Tôi đồng ý sử dụng dữ liệu tôi cung cấp để xử lý yêu cầu hỗ trợ sức khỏe. AI không thay thế bác sĩ.</label>}
   {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}{backups.length>0&&<div><h2>Mã khôi phục — lưu lại trước khi tiếp tục</h2><p>Mỗi mã chỉ sử dụng một lần. Không chia sẻ các mã này.</p>{backups.map(c=><code className="auth-secret" key={c}>{c}</code>)}</div>}
   <button disabled={busy}>{busy?'Đang xử lý…':({login:'Đăng nhập',register:'Tạo tài khoản',forgot:'Gửi liên kết khôi phục',reset:'Đặt lại mật khẩu',verify:'Xác thực email'})[mode]}</button>
  </form>{mode==='login'&&<button disabled={busy||!email} onClick={()=>perform(async()=>setNotice((await auth('verification-email',{email})).message))}>Gửi lại email xác thực</button>}<nav><button onClick={()=>{setMode(mode==='register'?'login':'register');setError('');}}> {mode==='register'?'Đã có tài khoản':'Đăng ký'}</button><button onClick={()=>{setMode(mode==='forgot'?'login':'forgot');setError('');}}>{mode==='forgot'?'Về đăng nhập':'Quên mật khẩu'}</button></nav>
 </section></main>;
 const action=(path,body,then)=>perform(async()=>{const d=await auth(path,body,csrf);setNotice(d.message||'Hoàn tất');if(then)await then(d);});
 return <><div className="account-bar"><span>{user.email}{user.mfa_enabled?' · MFA':''}</span><button onClick={()=>perform(async()=>{setManage(!manage);setSessions((await auth('sessions',null,csrf,'GET')).sessions);})}>Tài khoản & bảo mật</button><button disabled={busy} onClick={()=>action('logout',null,clear)}>Đăng xuất</button></div>
 {manage?<main className="auth-screen"><section className="auth-card"><h1>Tài khoản & bảo mật</h1><p>{user.email} · {user.email_verified?'Email đã xác thực':'Email chưa xác thực'}</p>
 {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
 <button disabled={busy} onClick={()=>action('verification-email')}>Gửi email xác thực</button>
 <h2>Đổi mật khẩu / xác nhận thao tác</h2><label>Mật khẩu hiện tại<input type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)}/></label><label>Mật khẩu mới<input type="password" autoComplete="new-password" minLength={12} value={newPassword} onChange={e=>setNewPassword(e.target.value)}/></label><label>Mã MFA hoặc mã khôi phục<input value={otp} onChange={e=>setOtp(e.target.value)} maxLength={32}/></label>
 <button disabled={busy} onClick={()=>action('password',{current_password:password,new_password:newPassword,otp:otp||null},clear)}>Đổi mật khẩu và thu hồi phiên</button>
 <h2>Xác thực hai lớp</h2>{!user.mfa_enabled?<><button disabled={busy} onClick={()=>action('mfa/setup',{current_password:password},setSetup)}>Thiết lập MFA</button>{setup&&<><p>Thêm khóa vào ứng dụng Authenticator rồi nhập mã 6 số. Giữ khóa này riêng tư.</p><code className="auth-secret">{setup.secret}</code><button disabled={busy} onClick={()=>action('mfa/enable',{token:setup.setup_token,code:otp},d=>{setBackups(d.recovery_codes||[]);clear();})}>Xác nhận bật MFA</button></>}</>:<button disabled={busy} onClick={()=>action('mfa/disable',{current_password:password,otp:otp||null},clear)}>Tắt MFA sau xác thực</button>}
 <h2>Phiên đăng nhập</h2>{sessions.map(s=><div className="auth-session" key={s.id}><span>{s.current?'Phiên hiện tại':'Phiên khác'} · {new Date(s.last_seen*1000).toLocaleString()}</span><button disabled={busy} onClick={()=>perform(async()=>{await auth('sessions/'+s.id,null,csrf,'DELETE');if(s.current)clear();else setSessions(sessions.filter(x=>x.id!==s.id));})}>Thu hồi</button></div>)}
 <button disabled={busy} onClick={()=>action('logout-all',null,clear)}>Đăng xuất tất cả thiết bị</button><button onClick={()=>{setManage(false);setPassword('');setOtp('');setSetup(null);}}>Về trò chuyện</button>
 </section></main>:<App key={user.id} account={user}/>}</>;
}
