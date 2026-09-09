import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  AlarmClock,
  Braces,
  CalendarClock,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronDown,
  Copy,
  FileScan,
  HeartPulse,
  ListOrdered,
  LoaderCircle,
  Menu,
  MessageSquare,
  Paperclip,
  PanelLeftClose,
  PanelLeftOpen,
  Pill,
  Plus,
  QrCode,
  Search,
  Save,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  Store,
  Trash2,
  UserRound,
  Webhook,
  Workflow,
  X,
} from 'lucide-react';
import { createApiClient } from './api';
import { ErrorResult, Field, SelectInput, TextInput } from './components';
import { QrScanner } from './chat/QrScanner';
import { SchedulePanel } from './chat/SchedulePanel';
import { GroundedAnswer } from './chat/GroundedAnswer';
import { SystemModule } from './modules/SystemModule';
import { SchedulePage } from './schedule/SchedulePage';

const tenantDefaults = { 'tenant-demo': 'demo-key', 'tenant-alt': 'alt-key' };

const tools = [
  { id: 'auto', label: 'Tự nhận diện', icon: Sparkles, group: 'Trợ lý' },
  { id: 'triage', label: 'Phân luồng triệu chứng', icon: Stethoscope, group: 'Lâm sàng' },
  { id: 'safety', label: 'An toàn thuốc', icon: ShieldCheck, group: 'Lâm sàng' },
  { id: 'monitoring', label: 'Đọc chỉ số', icon: Activity, group: 'Lâm sàng' },
  { id: 'followup', label: 'Kế hoạch tái khám', icon: CalendarClock, group: 'Điều phối' },
  { id: 'pharmacy', label: 'Cấp phát thuốc', icon: Store, group: 'Điều phối' },
  { id: 'queue', label: 'Hàng đợi tiếp nhận', icon: ListOrdered, group: 'Điều phối' },
  { id: 'ocr', label: 'Đọc đơn thuốc', icon: FileScan, group: 'Hình ảnh' },
  { id: 'schedule', label: 'Đặt lịch uống thuốc', icon: AlarmClock, group: 'Hình ảnh' },
  { id: 'authenticity', label: 'Xác thực QR', icon: QrCode, group: 'Hình ảnh' },
  { id: 'fhir', label: 'Xuất FHIR', icon: Braces, group: 'Liên thông' },
  { id: 'delivery', label: 'Chuyển tiếp kết quả', icon: Webhook, group: 'Liên thông' },
];

const starterPrompts = [
  { icon: Stethoscope, title: 'Tôi bị đau ngực và khó thở', text: 'Tôi bị đau ngực lan tay trái và khó thở, cần hỗ trợ ngay.' },
  { icon: ShieldCheck, title: 'Kiểm tra hai loại thuốc', text: 'Tôi đang dùng warfarin, dự định dùng aspirin. Kiểm tra an toàn thuốc.' },
  { icon: AlarmClock, title: 'Đặt lịch uống thuốc', text: '#lichthuoc uống amoxicillin lúc 8h và 20h mỗi ngày.' },
  { icon: HeartPulse, title: 'Đọc chỉ số tại nhà', text: 'SpO2 của tôi là 94%, huyết áp 150/90, nhịp tim 105.' },
];

function Brand() {
  return <div className="brand"><img src="/static/brand-mark.svg" alt="" /><div><strong>MedGuard AI</strong><span>Clinical assistant</span></div></div>;
}

function Credentials({ tenantId, setTenantId, apiKey, setApiKey, consentToken, setConsentToken, close }) {
  return <div className="credentials-popover">
    <div className="popover-heading"><strong>Kết nối API</strong><button type="button" className="icon-button" onClick={close} title="Đóng" aria-label="Đóng"><X size={16} /></button></div>
    <Field label="Tenant"><SelectInput value={tenantId} onChange={(event) => { const tenant = event.target.value; setTenantId(tenant); setApiKey(tenantDefaults[tenant] || ''); }}><option value="tenant-demo">tenant-demo</option><option value="tenant-alt">tenant-alt</option></SelectInput></Field>
    <Field label="API key"><TextInput type="password" autoComplete="off" value={apiKey} onChange={(event) => setApiKey(event.target.value)} /></Field>
    <Field label="Consent token"><TextInput type="password" autoComplete="off" value={consentToken} onChange={(event) => setConsentToken(event.target.value)} /></Field>
  </div>;
}

const emptyProfile = {
  display_name: '',
  patient_ref: '',
  age: null,
  sex: null,
  current_medications: [],
  allergies: [],
  conditions: [],
};

function parseList(value) {
  return value.split(',').map((item) => item.trim()).filter((item) => item && !['không', 'khong', 'none'].includes(item.toLowerCase()));
}

function loadProfile(tenantId) {
  try {
    return { ...emptyProfile, ...JSON.parse(localStorage.getItem(`medguard.profile.${tenantId}`) || '{}') };
  } catch {
    return { ...emptyProfile };
  }
}

function ProfileEditor({ context, onSave, onClear, close }) {
  const [draft, setDraft] = useState({ ...context, age: context.age ?? '' });
  const update = (key, value) => setDraft((current) => ({ ...current, [key]: value }));
  const submit = (event) => {
    event.preventDefault();
    onSave({
      display_name: draft.display_name.trim(),
      patient_ref: draft.patient_ref.trim().toUpperCase(),
      age: draft.age === '' ? null : Number(draft.age),
      sex: draft.sex || null,
      current_medications: parseList(Array.isArray(draft.current_medications) ? draft.current_medications.join(', ') : draft.current_medications),
      allergies: parseList(Array.isArray(draft.allergies) ? draft.allergies.join(', ') : draft.allergies),
      conditions: parseList(Array.isArray(draft.conditions) ? draft.conditions.join(', ') : draft.conditions),
    });
  };
  return <form className="patient-popover profile-editor" onSubmit={submit}>
    <div className="popover-heading"><div><strong>Profile cá nhân</strong><span>Thông tin không bắt buộc</span></div><button className="icon-button" type="button" onClick={close} title="Đóng" aria-label="Đóng"><X size={16} /></button></div>
    <Field label="Tên hiển thị"><TextInput value={draft.display_name} onChange={(event) => update('display_name', event.target.value)} placeholder="Nguyễn An" autoComplete="name" /></Field>
    <div className="profile-grid"><Field label="Tuổi"><TextInput type="number" min="0" max="120" value={draft.age} onChange={(event) => update('age', event.target.value)} placeholder="35" /></Field><Field label="Giới tính"><SelectInput value={draft.sex || ''} onChange={(event) => update('sex', event.target.value)}><option value="">Không cung cấp</option><option value="female">Nữ</option><option value="male">Nam</option><option value="other">Khác</option></SelectInput></Field></div>
    <Field label="Mã hồ sơ"><TextInput value={draft.patient_ref} onChange={(event) => update('patient_ref', event.target.value)} placeholder="BN-001" autoComplete="off" /></Field>
    <Field label="Thuốc đang dùng"><TextInput value={Array.isArray(draft.current_medications) ? draft.current_medications.join(', ') : draft.current_medications} onChange={(event) => update('current_medications', event.target.value)} placeholder="warfarin, aspirin" /></Field>
    <Field label="Dị ứng"><TextInput value={Array.isArray(draft.allergies) ? draft.allergies.join(', ') : draft.allergies} onChange={(event) => update('allergies', event.target.value)} placeholder="penicillin" /></Field>
    <Field label="Bệnh nền"><TextInput value={Array.isArray(draft.conditions) ? draft.conditions.join(', ') : draft.conditions} onChange={(event) => update('conditions', event.target.value)} placeholder="tăng huyết áp" /></Field>
    <div className="profile-actions"><button className="secondary-button danger-action" type="button" onClick={onClear}><Trash2 size={15} /> Xóa Profile</button><button className="profile-save" type="submit"><Save size={15} /> Lưu Profile</button></div>
  </form>;
}

function Sidebar({ open, close, collapse, conversations, activeId, onSelect, onNew, onDelete, onSchedule, onSchedulePage, onSystem, activeView, search, setSearch }) {
  return <>
    {open && <button className="sidebar-scrim" type="button" aria-label="Đóng menu" onClick={close} />}
    <aside className={`sidebar ${open ? 'open' : ''}`}>
      <div className="sidebar-top"><Brand /><button className="icon-button sidebar-collapse" type="button" onClick={collapse} title="Thu gọn thanh bên" aria-label="Thu gọn thanh bên"><PanelLeftClose size={18} /></button><button className="icon-button sidebar-close" type="button" onClick={close} title="Đóng" aria-label="Đóng menu"><X size={18} /></button></div>
      <button className="new-chat" type="button" onClick={() => { onNew(); close(); }}><Plus size={17} /><span>Cuộc trò chuyện mới</span></button>
      <div className="history-search"><Search size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} aria-label="Tìm lịch sử" placeholder="Tìm cuộc trò chuyện" /></div>
      <div className="history-block"><span className="nav-label">Gần đây</span><nav aria-label="Lịch sử trò chuyện">
        {conversations.length ? conversations.map((item) => <div className={`history-row ${activeId === item.conversation_id && activeView === 'chat' ? 'active' : ''}`} key={item.conversation_id}><button type="button" onClick={() => { onSelect(item.conversation_id); close(); }}><MessageSquare size={15} /><span>{item.title}</span></button><button className="history-delete" type="button" title="Xóa cuộc trò chuyện" aria-label={`Xóa ${item.title}`} onClick={() => onDelete(item.conversation_id)}><Trash2 size={14} /></button></div>) : <p className="history-empty">Chưa có cuộc trò chuyện</p>}
      </nav></div>
      <div className="sidebar-actions">
        <button type="button" className={`nav-link-btn ${activeView === 'schedule' ? 'active' : ''}`} onClick={() => { onSchedulePage(); close(); }}><CalendarClock size={17} /><span>Lịch khám & Ca trực</span></button>
        <button type="button" onClick={() => { onSchedule(); close(); }}><CalendarDays size={17} /><span>Lịch uống thuốc</span></button>
        <button type="button" className={`nav-link-btn ${activeView === 'system' ? 'active' : ''}`} onClick={() => { onSystem(); close(); }}><Workflow size={17} /><span>System & audit</span></button>
      </div>
      <div className="sidebar-foot"><Pill size={17} /><div><strong>Clinical support</strong><span>Human review required</span></div></div>
    </aside>
  </>;
}

function ToolMenu({ open, selected, onSelect }) {
  if (!open) return null;
  return <div className="tool-menu" role="menu">
    {['Trợ lý', 'Lâm sàng', 'Điều phối', 'Hình ảnh', 'Liên thông'].map((group) => <section key={group}><span>{group}</span>{tools.filter((tool) => tool.group === group).map((tool) => { const Icon = tool.icon; return <button type="button" role="menuitem" className={selected === tool.id ? 'active' : ''} key={tool.id} onClick={() => onSelect(tool.id)}><Icon size={16} /><strong>{tool.label}</strong>{selected === tool.id && <CheckCircle2 size={14} />}</button>; })}</section>)}
  </div>;
}

function Welcome({ onPrompt }) {
  return <div className="welcome-view">
    <img src="/static/brand-mark.svg" alt="" />
    <h1>Bạn cần hỗ trợ gì hôm nay?</h1>
    <div className="starter-grid">{starterPrompts.map((item) => { const Icon = item.icon; return <button type="button" key={item.title} onClick={() => onPrompt(item.text)}><Icon size={18} /><span>{item.title}</span><Send size={14} /></button>; })}</div>
  </div>;
}

function Conversation({ entries, busy, onNotify }) {
  const streamRef = useRef(null);
  const latestRef = useRef(null);
  const [copied, setCopied] = useState(null);
  useEffect(() => {
    const latest = entries.at(-1);
    const scroller = streamRef.current?.parentElement;
    if (!scroller) return;
    const top = !busy && latest?.role === 'assistant' && latestRef.current
      ? Math.max(0, latestRef.current.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop - 20)
      : scroller.scrollHeight;
    scroller.scrollTo({ top, behavior: 'smooth' });
  }, [entries, busy]);
  const copyResponse = async (entry, key) => {
    const answerText = entry.answer ? (
      entry.answer.narrative?.length
        ? entry.answer.narrative.map((block) => block.text).join('\n\n')
        : [
            entry.answer.title,
            entry.answer.summary,
            ...(entry.answer.key_points || []).map((item) => `• ${item}`),
            ...(entry.answer.next_steps || []).map((item, index) => `${index + 1}. ${item}`),
            ...(entry.answer.limitations || []).map((item) => `Lưu ý: ${item}`),
          ].join('\n')
    ) : entry.text;
    const content = entry.result ? `${answerText}\n\n${JSON.stringify(entry.result, null, 2)}` : answerText;
    try {
      await navigator.clipboard.writeText(content);
    } catch {
      const fallback = document.createElement('textarea');
      fallback.value = content;
      fallback.setAttribute('readonly', '');
      fallback.style.position = 'fixed';
      fallback.style.opacity = '0';
      document.body.appendChild(fallback);
      fallback.select();
      document.execCommand('copy');
      fallback.remove();
    }
    setCopied(key);
    onNotify?.('Đã sao chép phản hồi');
    window.setTimeout(() => setCopied((current) => current === key ? null : current), 1600);
  };
  return <div className="conversation-stream" ref={streamRef}>
    {entries.map((entry, index) => {
      const key = entry.id || index;
      if (entry.role === 'user') return <article className="chat-user message-enter" key={key}>{entry.attachmentUrl && <img src={entry.attachmentUrl} alt="Ảnh đã đính kèm" />}<p>{entry.text}</p></article>;
      if (entry.role === 'error') return <ErrorResult error={entry.error} key={key} />;
      return <article className="chat-assistant message-enter" ref={index === entries.length - 1 ? latestRef : null} key={key}><img className="assistant-avatar" src="/static/brand-mark.svg" alt="" /><div className="assistant-content"><strong>MedGuard AI</strong>{entry.answer ? <GroundedAnswer answer={entry.answer} result={entry.result} /> : <p>{entry.text}</p>}{entry.status === 'needs_information' && !entry.answer && <span className="answer-state needs_information">Cần thêm thông tin</span>}<div className="message-actions"><button type="button" title="Sao chép phản hồi" aria-label={copied === key ? 'Đã sao chép' : 'Sao chép phản hồi'} onClick={() => copyResponse(entry, key)}>{copied === key ? <Check size={15} /> : <Copy size={15} />}</button></div></div></article>;
    })}
    {busy && <article className="chat-assistant pending"><img className="assistant-avatar" src="/static/brand-mark.svg" alt="" /><div className="processing-indicator" role="status" aria-live="polite"><LoaderCircle className="spin" size={16} /><span>MedGuard đang xử lý</span><div className="typing" aria-hidden="true"><i /><i /><i /></div></div></article>}
    <div />
  </div>;
}

function Composer({ value, setValue, onSend, busy, selectedTool, setSelectedTool, attachment, setAttachment, onQr }) {
  const [toolsOpen, setToolsOpen] = useState(false);
  const textareaRef = useRef(null);
  const fileRef = useRef(null);
  const toolAnchorRef = useRef(null);
  const tool = tools.find((item) => item.id === selectedTool) || tools[0];
  const ToolIcon = tool.icon;

  useEffect(() => {
    if (!textareaRef.current) return;
    textareaRef.current.style.height = '0px';
    textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
  }, [value]);

  useEffect(() => {
    if (!toolsOpen) return undefined;
    const dismiss = (event) => {
      if (event.key === 'Escape' || (event.type === 'pointerdown' && !toolAnchorRef.current?.contains(event.target))) {
        setToolsOpen(false);
      }
    };
    document.addEventListener('keydown', dismiss);
    document.addEventListener('pointerdown', dismiss);
    return () => {
      document.removeEventListener('keydown', dismiss);
      document.removeEventListener('pointerdown', dismiss);
    };
  }, [toolsOpen]);

  const submit = () => {
    if ((!value.trim() && !attachment) || busy) return;
    onSend();
  };

  return <div className="composer-wrap">
    <div className="composer-box">
      {attachment && <div className="attachment-preview"><img src={attachment.url} alt="Ảnh chuẩn bị gửi" /><div><strong>{attachment.file.name}</strong><span>{Math.ceil(attachment.file.size / 1024)} KB</span></div><button className="icon-button" type="button" title="Bỏ ảnh" aria-label="Bỏ ảnh" onClick={() => setAttachment(null)}><X size={16} /></button></div>}
      <textarea ref={textareaRef} rows="1" value={value} onChange={(event) => setValue(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); submit(); } }} placeholder="Nhắn cho MedGuard AI" aria-label="Tin nhắn" />
      <div className="composer-tools">
        <div className="composer-left">
          <button className="icon-button" type="button" title="Đính kèm ảnh đơn thuốc hoặc kết quả khám" aria-label="Đính kèm ảnh" onClick={() => fileRef.current?.click()}><Paperclip size={19} /></button>
          <input ref={fileRef} className="visually-hidden" type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => { const file = event.target.files?.[0]; if (file) setAttachment({ file, url: URL.createObjectURL(file) }); event.target.value = ''; }} />
          <button className="icon-button" type="button" title="Quét QR sản phẩm" aria-label="Quét QR" onClick={onQr}><QrCode size={19} /></button>
          <div className="tool-anchor" ref={toolAnchorRef}><button className="mode-button" type="button" aria-haspopup="menu" aria-expanded={toolsOpen} onClick={() => setToolsOpen(!toolsOpen)}><ToolIcon size={16} /><span>{tool.label}</span><ChevronDown size={14} /></button><ToolMenu open={toolsOpen} selected={selectedTool} onSelect={(id) => { setSelectedTool(id); setToolsOpen(false); }} /></div>
        </div>
        <button className="send-button" type="button" title="Gửi" aria-label="Gửi tin nhắn" disabled={busy || (!value.trim() && !attachment)} onClick={submit}>{busy ? <LoaderCircle className="spin" size={18} /> : <Send size={18} />}</button>
      </div>
    </div>
    <p className="composer-disclaimer">MedGuard AI có thể mắc lỗi. Quyết định lâm sàng cần người có thẩm quyền xác nhận.</p>
  </div>;
}

const newContext = (profile = emptyProfile) => ({ ...emptyProfile, ...profile, last_result: null });

function clinicalContext(context) {
  return {
    patient_ref: context.patient_ref || null,
    age: context.age,
    sex: context.sex,
    current_medications: context.current_medications,
    allergies: context.allergies,
    conditions: context.conditions,
    last_result: context.last_result,
  };
}

export default function App() {
  const [tenantId, setTenantId] = useState('tenant-demo');
  const [apiKey, setApiKey] = useState('demo-key');
  const [consentToken, setConsentToken] = useState('consent-valid-ui');
  const [conversationId, setConversationId] = useState(() => crypto.randomUUID());
  const [conversationTitle, setConversationTitle] = useState('Cuộc trò chuyện mới');
  const [conversations, setConversations] = useState([]);
  const [entries, setEntries] = useState([]);
  const [message, setMessage] = useState('');
  const [context, setContext] = useState(() => newContext(loadProfile('tenant-demo')));
  const [selectedTool, setSelectedTool] = useState('auto');
  const [attachment, setAttachment] = useState(null);
  const [busy, setBusy] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return localStorage.getItem('medguard.sidebar.collapsed') === 'true';
    } catch {
      return false;
    }
  });
  const [credentialsOpen, setCredentialsOpen] = useState(false);
  const [patientOpen, setPatientOpen] = useState(false);
  const [qrOpen, setQrOpen] = useState(false);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [readiness, setReadiness] = useState(null);
  const [view, setView] = useState('chat');
  const [historySearch, setHistorySearch] = useState('');
  const [toast, setToast] = useState(null);
  const toastTimerRef = useRef(null);
  const api = useMemo(() => createApiClient({ tenantId, apiKey, consentToken }), [tenantId, apiKey, consentToken]);

  const notify = (text) => {
    window.clearTimeout(toastTimerRef.current);
    setToast(text);
    toastTimerRef.current = window.setTimeout(() => setToast(null), 2200);
  };

  const loadConversations = async () => {
    try {
      const data = await api.request('/v1/chat/conversations');
      setConversations(data.conversations || []);
    } catch {
      setConversations([]);
    }
  };

  useEffect(() => {
    let mounted = true;
    Promise.allSettled([api.request('/v1/health/readiness'), api.request('/v1/chat/conversations')]).then(([health, history]) => {
      if (!mounted) return;
      setReadiness(health.status === 'fulfilled' ? health.value : null);
      setConversations(history.status === 'fulfilled' ? history.value.conversations || [] : []);
    });
    return () => { mounted = false; };
  }, [api]);

  useEffect(() => {
    setConversationId(crypto.randomUUID());
    setConversationTitle('Cuộc trò chuyện mới');
    setEntries([]);
    setContext(newContext(loadProfile(tenantId)));
  }, [tenantId]);

  useEffect(() => {
    try {
      localStorage.setItem('medguard.sidebar.collapsed', String(sidebarCollapsed));
    } catch {
      // The navigation state can remain session-only when storage is unavailable.
    }
  }, [sidebarCollapsed]);

  useEffect(() => {
    const dismiss = (event) => {
      if (event.key === 'Escape') {
        setSidebarOpen(false);
        setCredentialsOpen(false);
        setPatientOpen(false);
        setQrOpen(false);
        setScheduleOpen(false);
        return;
      }
      if (event.type === 'pointerdown') {
        if (!event.target.closest('.profile-anchor')) setPatientOpen(false);
        if (!event.target.closest('.credentials-anchor')) setCredentialsOpen(false);
      }
    };
    document.addEventListener('keydown', dismiss);
    document.addEventListener('pointerdown', dismiss);
    return () => {
      document.removeEventListener('keydown', dismiss);
      document.removeEventListener('pointerdown', dismiss);
      window.clearTimeout(toastTimerRef.current);
    };
  }, []);

  const startNew = () => {
    setConversationId(crypto.randomUUID());
    setConversationTitle('Cuộc trò chuyện mới');
    setEntries([]);
    setMessage('');
    setAttachment(null);
    setSelectedTool('auto');
    setContext((current) => ({ ...current, last_result: null }));
    setView('chat');
  };

  const saveProfile = (profile) => {
    try {
      localStorage.setItem(`medguard.profile.${tenantId}`, JSON.stringify(profile));
    } catch {
      // The profile still applies to the current tab when browser storage is unavailable.
    }
    setContext((current) => ({ ...current, ...profile }));
    setPatientOpen(false);
    notify('Đã lưu Profile');
  };

  const clearProfile = () => {
    try {
      localStorage.removeItem(`medguard.profile.${tenantId}`);
    } catch {
      // Keep the clear action functional for the current tab.
    }
    setContext(newContext());
    setPatientOpen(false);
    notify('Đã xóa Profile');
  };

  const selectConversation = async (id) => {
    setBusy(true);
    setView('chat');
    try {
      const data = await api.request(`/v1/chat/conversations/${encodeURIComponent(id)}`);
      setConversationId(id);
      setConversationTitle(data.conversation.title);
      setContext((current) => ({ ...current, patient_ref: data.conversation.patient_ref || current.patient_ref }));
      setEntries(data.messages.map((item) => ({ id: item.message_id, role: item.role, text: item.content, intent: item.intent, status: item.status, result: item.result, answer: item.answer })));
    } catch (error) {
      setEntries([{ role: 'error', error }]);
    } finally {
      setBusy(false);
    }
  };

  const deleteConversation = async (id) => {
    try {
      await api.request(`/v1/chat/conversations/${encodeURIComponent(id)}`, { method: 'DELETE' });
      if (id === conversationId) startNew();
      await loadConversations();
    } catch (error) {
      setEntries((current) => [...current, { role: 'error', error }]);
    }
  };

  const sendText = async (overrideText, overrideIntent) => {
    const text = (overrideText ?? message).trim();
    const currentAttachment = attachment;
    if ((!text && !currentAttachment) || busy) return;
    const shownText = text || `Đọc ảnh ${currentAttachment.file.name}`;
    const previous = entries;
    setEntries((current) => [...current, { role: 'user', text: shownText, attachmentUrl: currentAttachment?.url }]);
    setMessage('');
    setAttachment(null);
    setBusy(true);
    const processingStartedAt = performance.now();
    let responseEntry = null;
    let refreshHistory = true;
    if (conversationTitle === 'Cuộc trò chuyện mới') setConversationTitle(shownText.slice(0, 80));

    try {
      if (currentAttachment) {
        const patientRef = context.patient_ref || shownText.match(/\b(?:BN|HS|P)[-_][A-Z0-9._-]+\b/i)?.[0]?.toUpperCase();
        if (!patientRef) {
          setPatientOpen(true);
          setAttachment(currentAttachment);
          responseEntry = { role: 'assistant', text: 'Mình cần mã hồ sơ bệnh nhân trước khi tiếp nhận ảnh y khoa.', intent: 'ocr', status: 'needs_information' };
          refreshHistory = false;
        } else {
          const formData = new FormData();
          formData.append('image', currentAttachment.file);
          formData.append('patient_ref', patientRef);
          formData.append('conversation_id', conversationId);
          formData.append('message', shownText);
          const data = await api.request('/v1/prescription/extract', { method: 'POST', formData });
          const { answer: ocrAnswer, ...ocrResult } = data;
          responseEntry = { role: 'assistant', text: ocrAnswer?.summary || 'Đã tiếp nhận ảnh. Kết quả nhận diện cần dược sĩ hoặc bác sĩ xác nhận trước khi tạo lịch thuốc.', intent: 'ocr', status: 'answered', result: ocrResult, answer: ocrAnswer };
        }
      } else {
        const messages = previous.filter((item) => item.role === 'user' || item.role === 'assistant').slice(-18).map((item) => ({ role: item.role, content: item.text }));
        messages.push({ role: 'user', content: shownText });
        const data = await api.request('/v1/chat', {
          method: 'POST',
          body: { conversation_id: conversationId, messages, context: clinicalContext(context), intent_hint: overrideIntent || selectedTool, locale: 'vi-VN' },
        });
        responseEntry = { role: 'assistant', text: data.reply, intent: data.intent, status: data.status, result: data.result, answer: data.answer, suggestions: data.suggestions };
        if (data.extracted?.patient_ref) setContext((current) => ({ ...current, patient_ref: data.extracted.patient_ref }));
        if (data.result) setContext((current) => ({ ...current, last_result: data.result }));
        if (data.required_fields?.includes('patient_ref')) setPatientOpen(true);
      }
      if (refreshHistory) await loadConversations();
    } catch (error) {
      responseEntry = { role: 'error', error };
    } finally {
      const remaining = 1000 - (performance.now() - processingStartedAt);
      if (remaining > 0) await new Promise((resolve) => window.setTimeout(resolve, remaining));
      if (responseEntry) setEntries((current) => [...current, responseEntry]);
      setBusy(false);
    }
  };

  const filteredConversations = conversations.filter((item) => item.title.toLowerCase().includes(historySearch.toLowerCase()));
  return <div className={`app-shell chat-shell ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
    <Sidebar open={sidebarOpen} close={() => setSidebarOpen(false)} collapse={() => { setSidebarCollapsed(true); setSidebarOpen(false); }} conversations={filteredConversations} activeId={conversationId} onSelect={selectConversation} onNew={startNew} onDelete={deleteConversation} onSchedule={() => setScheduleOpen(true)} onSchedulePage={() => setView('schedule')} onSystem={() => setView('system')} activeView={view} search={historySearch} setSearch={setHistorySearch} />
    <main className="main-shell chat-main">
      <header className="topbar chat-topbar">
        <div className="topbar-title"><button className="icon-button menu-button" type="button" onClick={() => { setSidebarCollapsed(false); setSidebarOpen(true); }} title={sidebarCollapsed ? 'Mở thanh bên' : 'Mở menu'} aria-label={sidebarCollapsed ? 'Mở thanh bên' : 'Mở menu'}>{sidebarCollapsed ? <PanelLeftOpen size={20} /> : <Menu size={20} />}</button><div><h1>{view === 'system' ? 'System & audit' : view === 'schedule' ? 'Lịch khám & Ca trực' : conversationTitle}</h1><span>{view === 'system' ? 'Trạng thái vận hành' : view === 'schedule' ? 'Điều phối ca lâm sàng' : context.patient_ref || 'Có thể nhắn ngay không cần Profile'}</span></div></div>
        <div className="topbar-actions">
          <button className={`view-toggle-btn ${view === "schedule" ? "active" : ""}`} type="button" onClick={() => setView(view === "schedule" ? "chat" : "schedule")} title={view === 'schedule' ? 'Về phòng Chat' : 'Xem Lịch khám & Ca trực'}><CalendarClock size={16} /><span>{view === 'schedule' ? 'Trò chuyện' : 'Lịch ca trực'}</span></button>
          {view === 'chat' && <div className="profile-anchor"><button className={`patient-button ${context.patient_ref || context.display_name ? 'selected' : ''}`} type="button" aria-label="Mở Profile cá nhân" onClick={() => setPatientOpen(!patientOpen)}><span>{context.display_name ? context.display_name.trim().slice(0, 2).toUpperCase() : context.patient_ref ? context.patient_ref.slice(0, 2) : <UserRound size={15} />}</span><div><strong>{context.display_name || 'Profile cá nhân'}</strong><small>{context.patient_ref || 'Không bắt buộc'}</small></div><ChevronDown size={15} /></button>{patientOpen && <ProfileEditor context={context} onSave={saveProfile} onClear={clearProfile} close={() => setPatientOpen(false)} />}</div>}
          <button className="readiness-button" type="button" title="Trạng thái hệ thống" onClick={() => setView('system')}><span className={`health-dot ${readiness?.production_ready ? 'ready' : ''}`} />{readiness?.status || 'offline'}</button>
          <div className="credentials-anchor"><button className="tenant-button" type="button" title="Cấu hình kết nối" aria-label="Cấu hình kết nối" onClick={() => setCredentialsOpen(!credentialsOpen)}><span>{tenantId.slice(0, 1).toUpperCase()}</span><div><strong>{tenantId}</strong><small>{readiness?.environment || 'Environment'}</small></div><Settings2 size={16} /></button>{credentialsOpen && <Credentials tenantId={tenantId} setTenantId={setTenantId} apiKey={apiKey} setApiKey={setApiKey} consentToken={consentToken} setConsentToken={setConsentToken} close={() => setCredentialsOpen(false)} />}</div>
        </div>
      </header>
      {view === 'system' ? (
        <div className="system-workspace"><SystemModule api={api} tenantId={tenantId} /></div>
      ) : view === 'schedule' ? (
        <div className="schedule-workspace">
          <SchedulePage
            api={api}
            onBackToChat={() => setView('chat')}
            onConsultPatient={(shift) => {
              setView('chat');
              setContext((current) => ({
                ...current,
                patient_ref: shift.patientRef,
                display_name: shift.patientName,
                age: shift.age,
                sex: shift.sex === 'Nam' ? 'male' : 'female',
                conditions: [shift.department, shift.purpose],
                current_medications: shift.currentMeds || [],
              }));
              setMessage(`Tư vấn ca khám của bệnh nhân ${shift.patientName} (${shift.patientRef}), lý do: ${shift.purpose}.`);
              requestAnimationFrame(() => document.querySelector('[aria-label="Tin nhắn"]')?.focus());
            }}
          />
        </div>
      ) : (
        <section className={`chat-workspace ${entries.length ? 'has-messages' : ''}`} aria-live="polite">
          <div className="chat-scroll">
            {entries.length ? (
              <Conversation
                entries={entries}
                busy={busy}
                onNotify={notify}
              />
            ) : (
              <Welcome onPrompt={(text) => { setMessage(text); requestAnimationFrame(() => document.querySelector('[aria-label="Tin nhắn"]')?.focus()); }} />
            )}
          </div>
          <Composer value={message} setValue={setMessage} onSend={() => sendText()} busy={busy} selectedTool={selectedTool} setSelectedTool={setSelectedTool} attachment={attachment} setAttachment={setAttachment} onQr={() => setQrOpen(true)} />
        </section>
      )}
    </main>
    <QrScanner open={qrOpen} onClose={() => setQrOpen(false)} onDetected={(raw) => { setQrOpen(false); sendText(`Kiểm tra QR hàng giả: ${raw}`, 'authenticity'); }} />
    <SchedulePanel open={scheduleOpen} onClose={() => setScheduleOpen(false)} api={api} patientRef={context.patient_ref} />
    {toast && <div className="ui-toast" role="status"><Check size={16} /><span>{toast}</span></div>}
  </div>;
}
