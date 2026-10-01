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
  Settings,
  Settings2,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  Store,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  UserRound,
  Volume2,
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
import { MedicationPage } from './schedule/MedicationPage';
import { SettingsModal } from './settings/SettingsModal';

const tools = [
  { id: 'auto', label: 'Tự nhận diện', icon: Sparkles, group: 'Trợ lý' },
  { id: 'triage', label: 'Phân luồng triệu chứng', icon: Stethoscope, group: 'Lâm sàng' },
  { id: 'safety', label: 'An toàn thuốc', icon: ShieldCheck, group: 'Lâm sàng' },
  { id: 'monitoring', label: 'Đọc chỉ số', icon: Activity, group: 'Lâm sàng' },
  { id: 'followup', label: 'Kế hoạch tái khám', icon: CalendarClock, group: 'Điều phối' },
  { id: 'ocr', label: 'Đọc đơn thuốc', icon: FileScan, group: 'Hình ảnh' },
  { id: 'schedule', label: 'Đặt lịch uống thuốc', icon: AlarmClock, group: 'Hình ảnh' },
  { id: 'authenticity', label: 'Xác thực QR', icon: QrCode, group: 'Hình ảnh' },
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

function Sidebar({ open, close, collapse, conversations, activeId, onSelect, onNew, onDelete, onSchedule, onSchedulePage, onMedicationPage, onSettings, onSystem, activeView, search, setSearch }) {
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

        <button type="button" className={`nav-link-btn ${activeView === 'medication' ? 'active' : ''}`} onClick={() => { onMedicationPage(); close(); }}><CalendarDays size={17} /><span>Lịch uống thuốc</span></button>
        <button type="button" className="nav-link-btn" onClick={() => { onSettings(); close(); }}><Settings size={17} /><span>Cài đặt</span></button>
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
  const [feedback, setFeedback] = useState({});
  const [speakingKey, setSpeakingKey] = useState(null);

  // Smart scrolling states
  const [showScrollBottom, setShowScrollBottom] = useState(false);
  const [hasNewMessages, setHasNewMessages] = useState(false);
  const isAtBottomRef = useRef(true);
  const prevEntriesLengthRef = useRef(entries.length);
  useEffect(() => () => { if ('speechSynthesis' in window) window.speechSynthesis.cancel(); }, []);

  // Dynamic clinical loading phases
  const [loadingPhase, setLoadingPhase] = useState(0);

  useEffect(() => {
    if (!busy) {
      setLoadingPhase(0);
      return undefined;
    }
    const timer1 = setTimeout(() => setLoadingPhase(1), 1600);
    const timer2 = setTimeout(() => setLoadingPhase(2), 3400);
    return () => {
      clearTimeout(timer1);
      clearTimeout(timer2);
    };
  }, [busy]);

  const scrollToBottom = (smooth = true) => {
    const scroller = streamRef.current?.parentElement;
    if (!scroller) return;
    scroller.scrollTo({
      top: scroller.scrollHeight,
      behavior: smooth ? 'smooth' : 'auto',
    });
    isAtBottomRef.current = true;
    setShowScrollBottom(false);
    setHasNewMessages(false);
  };

  // Listen to user scrolling inside .chat-scroll
  useEffect(() => {
    const scroller = streamRef.current?.parentElement;
    if (!scroller) return undefined;

    const onScroll = () => {
      const threshold = 70;
      const distanceFromBottom = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight;
      const atBottom = distanceFromBottom <= threshold;
      isAtBottomRef.current = atBottom;
      setShowScrollBottom(!atBottom);
      if (atBottom) {
        setHasNewMessages(false);
      }
    };

    scroller.addEventListener('scroll', onScroll, { passive: true });
    return () => scroller.removeEventListener('scroll', onScroll);
  }, []);

  // Handle entries and busy updates without interrupting reading scroll
  useEffect(() => {
    const scroller = streamRef.current?.parentElement;
    if (!scroller) return;

    const prevLen = prevEntriesLengthRef.current;
    const currLen = entries.length;
    prevEntriesLengthRef.current = currLen;

    const isNewMessage = currLen > prevLen;
    const latest = entries.at(-1);

    if (isNewMessage) {
      if (latest?.role === 'user') {
        // User just sent a message -> always scroll to reveal
        scrollToBottom(true);
      } else if (isAtBottomRef.current) {
        // Assistant replied and user was already at bottom -> keep pinned to bottom
        scrollToBottom(true);
      } else {
        // User is reading history higher up -> DO NOT yank scroll, show new message pill
        setHasNewMessages(true);
      }
    } else if (busy && isAtBottomRef.current) {
      // Loading started while user was at bottom
      scrollToBottom(true);
    }
    // Background polling updates (currLen === prevLen) deliberately do NOT trigger scroll!
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
    const content = answerText;
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

  const handleFeedback = (key, type) => {
    setFeedback((prev) => ({
      ...prev,
      [key]: prev[key] === type ? null : type,
    }));
    onNotify?.(type === 'up' ? 'Cảm ơn phản hồi hữu ích của bạn!' : 'Cảm ơn góp ý, MedGuard sẽ cải thiện.');
  };

  const handleSpeak = (entry, key) => {
    if (!('speechSynthesis' in window)) {
      onNotify?.('Trình duyệt chưa hỗ trợ phát âm thanh');
      return;
    }
    if (speakingKey === key) {
      window.speechSynthesis.cancel();
      setSpeakingKey(null);
      return;
    }
    window.speechSynthesis.cancel();
    const textToRead = entry.answer?.summary || entry.text || '';
    const cleanText = textToRead.replace(/[#*`_]/g, '');
    const utter = new SpeechSynthesisUtterance(cleanText);
    utter.lang = 'vi-VN';
    utter.rate = 1.0;
    utter.onend = () => setSpeakingKey(null);
    utter.onerror = () => setSpeakingKey(null);
    setSpeakingKey(key);
    window.speechSynthesis.speak(utter);
    onNotify?.('Đang phát âm thanh giọng đọc');
  };

  return (
    <div className="conversation-stream" ref={streamRef}>
      {entries.map((entry, index) => {
        const key = entry.id || index;
        if (entry.role === 'user') {
          return (
            <article className="chat-user message-enter" key={key}>
              {entry.attachmentUrl && <img src={entry.attachmentUrl} alt="Ảnh đã đính kèm" />}
              <p>{entry.text}</p>
            </article>
          );
        }
        if (entry.role === 'error') return <ErrorResult error={entry.error} key={key} />;
        return (
          <article
            className="chat-assistant message-enter"
            ref={index === entries.length - 1 ? latestRef : null}
            key={key}
          >
            <img className="assistant-avatar" src="/static/brand-mark.svg" alt="" />
            <div className="assistant-content">
              <strong>MedGuard AI</strong>
              {entry.answer ? (
                <GroundedAnswer answer={entry.answer} result={entry.result} responseMeta={entry} />
              ) : (
                <p>{entry.text}</p>
              )}
              {entry.status === 'needs_information' && !entry.answer && (
                <span className="answer-state needs_information">Cần thêm thông tin</span>
              )}
              <div className="message-actions">
                <button
                  type="button"
                  title="Sao chép phản hồi"
                  aria-label={copied === key ? 'Đã sao chép' : 'Sao chép phản hồi'}
                  onClick={() => copyResponse(entry, key)}
                >
                  {copied === key ? <Check size={15} /> : <Copy size={15} />}
                </button>
                <button
                  type="button"
                  className={`action-icon-pill ${feedback[key] === 'up' ? 'active' : ''}`}
                  title="Hữu ích"
                  aria-label="Hữu ích"
                  onClick={() => handleFeedback(key, 'up')}
                >
                  <ThumbsUp size={14} />
                </button>
                <button
                  type="button"
                  className={`action-icon-pill ${feedback[key] === 'down' ? 'active' : ''}`}
                  title="Cần cải thiện"
                  aria-label="Cần cải thiện"
                  onClick={() => handleFeedback(key, 'down')}
                >
                  <ThumbsDown size={14} />
                </button>
                <button
                  type="button"
                  className={`action-icon-pill ${speakingKey === key ? 'active-speaking' : ''}`}
                  title={speakingKey === key ? 'Dừng đọc' : 'Nghe đọc to'}
                  aria-label="Nghe đọc to"
                  onClick={() => handleSpeak(entry, key)}
                >
                  <Volume2 size={14} />
                </button>
              </div>
            </div>
          </article>
        );
      })}

      {busy && (
        <article className="chat-assistant pending-premium message-enter">
          <div className="assistant-avatar-wrap">
            <img className="assistant-avatar pulse-glow" src="/static/brand-mark.svg" alt="" />
          </div>
          <div className="assistant-content">
            <strong>MedGuard AI</strong>
            <div className="premium-thinking-card" role="status" aria-live="polite">
              <div className="thinking-header">
                <div className="thinking-badge">
                  <span className="sr-only">MedGuard đang xử lý</span>
                  <span className="thinking-pulse-dot" />
                  <Sparkles className="spin-slow" size={14} />
                  <span className="thinking-phase-text">
                    {loadingPhase === 0 && 'Đang phân tích triệu chứng lâm sàng...'}
                    {loadingPhase === 1 && 'Đang đối chiếu phác đồ & cơ sở tri thức y khoa...'}
                    {loadingPhase >= 2 && 'Đang chạy kiểm định an toàn qua Gateway...'}
                  </span>
                </div>
                <div className="thinking-dots" aria-hidden="true">
                  <i /><i /><i />
                </div>
              </div>
              <div className="skeleton-container" aria-hidden="true">
                <div className="skeleton-line skeleton-title shimmer" />
                <div className="skeleton-line skeleton-p1 shimmer" />
                <div className="skeleton-line skeleton-p2 shimmer" />
                <div className="skeleton-line skeleton-p3 shimmer" />
                <div className="skeleton-tags">
                  <div className="skeleton-tag shimmer" />
                  <div className="skeleton-tag shimmer" />
                  <div className="skeleton-tag shimmer" />
                </div>
              </div>
            </div>
          </div>
        </article>
      )}

      {showScrollBottom && (
        <div className="scroll-bottom-container">
          <button
            type="button"
            className={`scroll-bottom-fab ${hasNewMessages ? 'has-new' : ''}`}
            title="Cuộn xuống tin mới nhất"
            aria-label="Cuộn xuống tin mới nhất"
            onClick={() => scrollToBottom(true)}
          >
            <ChevronDown size={15} />
            <span>{hasNewMessages ? 'Tin nhắn mới' : 'Cuộn xuống'}</span>
            {hasNewMessages && <span className="scroll-bottom-badge" />}
          </button>
        </div>
      )}
      <div />
    </div>
  );
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
          <input ref={fileRef} className="visually-hidden" aria-label="Chọn ảnh đính kèm" type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => { const file = event.target.files?.[0]; if (file) setAttachment({ file, url: URL.createObjectURL(file) }); event.target.value = ''; }} />
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

export default function App({ session, onLogout, onSession }) {
  const tenantId = session.account.tenant_id;
  const [conversationId, setConversationId] = useState(() => crypto.randomUUID());
  const [conversationTitle, setConversationTitle] = useState('Cuộc trò chuyện mới');
  const [conversations, setConversations] = useState([]);
  const [entries, setEntries] = useState([]);
  const [message, setMessage] = useState('');
  const [context, setContext] = useState(() => newContext(session.account.profile));
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
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsInitialTab, setSettingsInitialTab] = useState('general');
  const [readiness, setReadiness] = useState(null);
  const [view, setView] = useState('chat');
  const [historySearch, setHistorySearch] = useState('');
  const [toast, setToast] = useState(null);
  const toastTimerRef = useRef(null);
  const conversationGenerationRef = useRef(0);
  const api = useMemo(() => createApiClient({ csrfToken: session.csrf_token }), [session.csrf_token]);
  const hasPendingGatewayReview = entries.some(
    (entry) => entry.role === 'assistant' && entry.verification_status === 'shadow_pending',
  );

  const notify = (text) => {
    window.clearTimeout(toastTimerRef.current);
    setToast(text);
    toastTimerRef.current = window.setTimeout(() => setToast(null), 2200);
  };

  const clearAllConversations = async () => {
    try {
      for (const item of conversations) {
        await api.request(`/v1/chat/conversations/${encodeURIComponent(item.conversation_id)}`, { method: 'DELETE' });
      }
    } catch {
      notify('Chưa xóa được lịch sử. Vui lòng thử lại.');
      return;
    }
    startNew();
    setConversations([]);
    notify('Đã xóa toàn bộ lịch sử trò chuyện');
  };

  const exportClinicalData = () => {
    const exportPayload = {
      version: '1.0',
      exported_at: new Date().toISOString(),
      patient_profile: context,
      conversations_count: conversations.length,
      current_conversation: {
        id: conversationId,
        title: conversationTitle,
        messages: entries,
      },
    };
    const blob = new Blob([JSON.stringify(exportPayload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `medguard-data-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    notify('Đã xuất dữ liệu y bạ cá nhân');
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
    Promise.allSettled([api.request('/v1/health'), api.request('/v1/chat/conversations')]).then(([health, history]) => {
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
    setContext(newContext(session.account.profile));
  }, [tenantId]);

  useEffect(() => {
    try {
      localStorage.setItem('medguard.sidebar.collapsed', String(sidebarCollapsed));
    } catch {
      // The navigation state can remain session-only when storage is unavailable.
    }
  }, [sidebarCollapsed]);

  useEffect(() => {
    if (view !== 'chat' || busy || !hasPendingGatewayReview) return undefined;
    let refreshInFlight = false;
    const refreshGatewayStatuses = async () => {
      if (refreshInFlight) return;
      refreshInFlight = true;
      try {
        const data = await api.request(`/v1/chat/conversations/${encodeURIComponent(conversationId)}`);
        const assistantByRequest = new Map(
          data.messages
            .filter((item) => item.role === 'assistant' && item.request_id)
            .map((item) => [item.request_id, item]),
        );
        setEntries((current) => current.map((entry) => {
          if (entry.role !== 'assistant' || entry.verification_status !== 'shadow_pending') return entry;
          const persisted = assistantByRequest.get(entry.requestId);
          if (!persisted || persisted.verification_status === 'shadow_pending') return entry;
          return {
            ...entry,
            answer: persisted.answer || entry.answer,
            answer_origin: persisted.answer_origin,
            verification_status: persisted.verification_status,
          };
        }));
      } catch {
        // Keep the accepted/pending state visible. Read failures must not be
        // converted into a false gateway failure.
      } finally {
        refreshInFlight = false;
      }
    };
    const intervalId = window.setInterval(refreshGatewayStatuses, 2500);
    void refreshGatewayStatuses();
    return () => window.clearInterval(intervalId);
  }, [api, busy, conversationId, hasPendingGatewayReview, view]);

  useEffect(() => {
    const dismiss = (event) => {
      if (event.key === 'Escape') {
        setSidebarOpen(false);
        setCredentialsOpen(false);
        setPatientOpen(false);
        setQrOpen(false);
        setScheduleOpen(false);
        setSettingsOpen(false);
        return;
      }
      if (event.type === 'pointerdown') {
        if (!event.target.closest('.profile-anchor')) setPatientOpen(false);
        if (!event.target.closest('.account-menu')) setCredentialsOpen(false);
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
    conversationGenerationRef.current += 1;
    setBusy(false);
    setConversationId(crypto.randomUUID());
    setConversationTitle('Cuộc trò chuyện mới');
    setEntries([]);
    setMessage('');
    setAttachment(null);
    setSelectedTool('auto');
    setContext((current) => ({ ...current, last_result: null }));
    setView('chat');
  };

  const saveProfile = async (profile) => {
    try {
      const data = await api.request('/v1/auth/profile', { method: 'PUT', body: profile });
      setContext((current) => ({ ...newContext(data.profile), last_result: current.last_result }));
      setPatientOpen(false);
      notify('Đã lưu hồ sơ vào tài khoản');
      return true;
    } catch (error) { notify(error.message); return false; }
  };
  const clearProfile = () => saveProfile(emptyProfile);
  const updateConsent = async () => {
    try {
      const data = await api.request('/v1/auth/consent', { method: 'PUT', body: { consent: !session.account.consent } });
      onSession({ ...session, account: { ...session.account, consent: data.consent } });
      notify(data.consent ? 'Đã đồng ý xử lý thông tin sức khỏe' : 'Đã rút lại đồng ý. Dữ liệu đã lưu vẫn có thể xem và xóa.');
    } catch (error) { notify(error.message); }
  };

  const selectConversation = async (id) => {
    setBusy(true);
    setView('chat');
    try {
      const data = await api.request(`/v1/chat/conversations/${encodeURIComponent(id)}`);
      setConversationId(id);
      setConversationTitle(data.conversation.title);
      setContext((current) => ({ ...current, patient_ref: data.conversation.patient_ref || current.patient_ref }));
      setEntries(data.messages.map((item) => ({ id: item.message_id, requestId: item.request_id, role: item.role, text: item.content, intent: item.intent, status: item.status, result: item.result, answer: item.answer, answer_origin: item.answer_origin, verification_status: item.verification_status, knowledge_approval: item.knowledge_approval })));
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
    const generation = conversationGenerationRef.current;
    const text = (overrideText ?? message).trim();
    const currentAttachment = attachment;
    if ((!text && !currentAttachment) || busy) return;
    const effectiveIntent = overrideIntent || selectedTool;
    const isExplicitPrescriptionOcr = (
      effectiveIntent === 'ocr' ||
      (effectiveIntent === 'auto' && (
        /\b(đơn|toa)\s*thuốc\b/i.test(text) ||
        /\b(đọc\s*đơn|kê\s*đơn|trích\s*xuất\s*đơn|toa\s*bác\s*sĩ)\b/i.test(text)
      ))
    );
    const shownText = text || (currentAttachment ? (isExplicitPrescriptionOcr ? `Đọc đơn thuốc từ ảnh ${currentAttachment.file.name}` : `Đính kèm ảnh ${currentAttachment.file.name}`) : '');
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
      if (currentAttachment && isExplicitPrescriptionOcr) {
        const patientRef = context.patient_ref || shownText.match(/\b(?:BN|HS|P)[-_][A-Z0-9._-]+\b/i)?.[0]?.toUpperCase() || `BN-KHACH-${conversationId.slice(0, 6).toUpperCase()}`;
        const formData = new FormData();
        formData.append('image', currentAttachment.file);
        formData.append('patient_ref', patientRef);
        formData.append('conversation_id', conversationId);
        formData.append('message', shownText);
        const data = await api.request('/v1/prescription/extract', { method: 'POST', formData });
        if (generation !== conversationGenerationRef.current) return;
        const { answer: ocrAnswer, ...ocrResult } = data;
        responseEntry = { role: 'assistant', text: ocrAnswer?.summary || 'Đã tiếp nhận ảnh đơn thuốc. Kết quả nhận diện cần dược sĩ hoặc bác sĩ xác nhận trước khi tạo lịch thuốc.', intent: 'ocr', status: 'answered', result: ocrResult, answer: ocrAnswer };
      } else {
        const messages = previous.filter((item) => item.role === 'user' || item.role === 'assistant').slice(-18).map((item) => ({ role: item.role, content: item.text }));
        messages.push({ role: 'user', content: shownText });
        const data = await api.request('/v1/chat', {
          method: 'POST',
          body: { conversation_id: conversationId, messages, context: clinicalContext(context), intent_hint: effectiveIntent, locale: 'vi-VN' },
          timeoutMs: 9500,
        });
        if (generation !== conversationGenerationRef.current) return;
        responseEntry = { role: 'assistant', requestId: data.request_id, text: data.reply, intent: data.intent, status: data.status, result: data.result, answer: data.answer, suggestions: data.suggestions, answer_origin: data.answer_origin, verification_status: data.verification_status, knowledge_approval: data.knowledge_approval };
        if (data.extracted?.patient_ref) setContext((current) => ({ ...current, patient_ref: data.extracted.patient_ref }));
        if (data.result) setContext((current) => ({ ...current, last_result: data.result }));
        if (data.required_fields?.includes('patient_ref')) setPatientOpen(true);
      }
      if (refreshHistory) void loadConversations();
    } catch (error) {
      responseEntry = { role: 'error', error };
    } finally {
      const remaining = 350 - (performance.now() - processingStartedAt);
      if (remaining > 0) await new Promise((resolve) => window.setTimeout(resolve, remaining));
      if (generation === conversationGenerationRef.current) {
        if (responseEntry) setEntries((current) => [...current, responseEntry]);
        setBusy(false);
      }
    }
  };

  const filteredConversations = conversations.filter((item) => item.title.toLowerCase().includes(historySearch.toLowerCase()));
  return <div className={`app-shell chat-shell ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
    <Sidebar open={sidebarOpen} close={() => setSidebarOpen(false)} collapse={() => { setSidebarCollapsed(true); setSidebarOpen(false); }} conversations={filteredConversations} activeId={conversationId} onSelect={selectConversation} onNew={startNew} onDelete={deleteConversation} onSchedule={() => setView('medication')} onSchedulePage={() => setView('schedule')} onMedicationPage={() => setView('medication')} onSettings={() => { setSettingsInitialTab('general'); setSettingsOpen(true); }} onSystem={() => setView('system')} activeView={view} search={historySearch} setSearch={setHistorySearch} />
    <main className="main-shell chat-main">
      {!session.account.consent && <div className="consent-banner" role="status">Để tư vấn sức khỏe và lưu hồ sơ, cần sự đồng ý của bạn. <button type="button" onClick={updateConsent}>Tôi đồng ý</button></div>}
      <header className="topbar chat-topbar">
        <div className="topbar-title"><button className="icon-button menu-button" type="button" onClick={() => { setSidebarCollapsed(false); setSidebarOpen(true); }} title={sidebarCollapsed ? 'Mở thanh bên' : 'Mở menu'} aria-label={sidebarCollapsed ? 'Mở thanh bên' : 'Mở menu'}>{sidebarCollapsed ? <PanelLeftOpen size={20} /> : <Menu size={20} />}</button><div><h1>{view === 'system' ? 'System & audit' : view === 'schedule' ? 'Lịch khám' : view === 'medication' ? 'Lịch uống thuốc' : conversationTitle}</h1><span>{view === 'system' ? 'Trạng thái vận hành' : view === 'schedule' ? 'Thời khóa biểu ca khám bác sĩ' : view === 'medication' ? 'Thời khóa biểu nhắc thuốc cá nhân' : context.patient_ref || 'Có thể nhắn ngay không cần Profile'}</span></div></div>
        <div className="topbar-actions">

          <button className={`view-toggle-btn ${view === "medication" ? "active" : ""}`} type="button" onClick={() => setView(view === "medication" ? "chat" : "medication")} title={view === 'medication' ? 'Về phòng Chat' : 'Xem Lịch uống thuốc'}><Pill size={16} /><span>{view === 'medication' ? 'Trò chuyện' : 'Lịch uống thuốc'}</span></button>
          {view === 'chat' && <div className="profile-anchor"><button className={`patient-button ${context.patient_ref || context.display_name ? 'selected' : ''}`} type="button" aria-label="Mở Profile cá nhân" onClick={() => setPatientOpen(!patientOpen)}><span>{context.display_name ? context.display_name.trim().slice(0, 2).toUpperCase() : context.patient_ref ? context.patient_ref.slice(0, 2) : <UserRound size={15} />}</span><div><strong>{context.display_name || 'Profile cá nhân'}</strong><small>{context.patient_ref || 'Không bắt buộc'}</small></div><ChevronDown size={15} /></button>{patientOpen && <ProfileEditor context={context} onSave={saveProfile} onClear={clearProfile} close={() => setPatientOpen(false)} />}</div>}
          <button className="icon-button topbar-settings-btn" type="button" title="Cài đặt hệ thống" aria-label="Cài đặt" onClick={() => { setSettingsInitialTab('general'); setSettingsOpen(true); }}><Settings size={18} /></button>
          <div className="account-menu"><button className="patient-button" type="button" aria-expanded={credentialsOpen} onClick={() => setCredentialsOpen(!credentialsOpen)}><UserRound size={17} /><span>{session.account.display_name}</span><ChevronDown size={14} /></button>{credentialsOpen && <div className="account-dropdown"><strong>{session.account.display_name}</strong><small>{session.account.email}</small><button type="button" onClick={updateConsent}>{session.account.consent ? 'Rút lại đồng ý xử lý sức khỏe' : 'Đồng ý xử lý sức khỏe'}</button><button type="button" onClick={onLogout}>Đăng xuất</button></div>}</div>
        </div>
      </header>
      {view === 'system' ? (
        <div className="system-workspace"><SystemModule api={api} tenantId={tenantId} /></div>
      ) : view === 'schedule' ? (
        <div className="schedule-workspace">
          <SchedulePage
            api={api}
            onBackToChat={() => setView('chat')}
            onOpenMedicationPage={() => setView('medication')}
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
      ) : view === 'medication' ? (
        <div className="schedule-workspace">
          <MedicationPage
            api={api}
            patientRef={context.patient_ref}
            onBackToChat={() => setView('chat')}
            onOpenSchedulePage={() => notify('Chưa có cơ sở y tế liên kết để đặt lịch khám.')}
            onConsultMedicine={(med) => {
              setView('chat');
              setMessage(`Tư vấn thông tin và lưu ý dùng thuốc ${med.name || med.medicine_name} (${med.strength || med.dosage || ''}), dùng vào: ${med.timing || med.slot || 'trong ngày'}.`);
              requestAnimationFrame(() => document.querySelector('[aria-label="Tin nhắn"]')?.focus());
            }}
            onNotify={notify}
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
    <SchedulePanel open={scheduleOpen} onClose={() => setScheduleOpen(false)} api={api} patientRef={context.patient_ref} onOpenSchedulePage={() => notify('Chưa có cơ sở y tế liên kết để đặt lịch khám.')} onNotify={notify} />
    <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} initialTab={settingsInitialTab} context={context} onSaveProfile={saveProfile} onClearProfile={clearProfile} api={api} tenantId={tenantId} onClearAllChat={clearAllConversations} onExportData={exportClinicalData} onNotify={notify} />
    {toast && <div className="ui-toast" role="status"><Check size={16} /><span>{toast}</span></div>}
  </div>;
}
