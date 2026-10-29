import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  AlarmClock,
  AlertTriangle,
  ArrowLeft,
  BadgeCheck,
  Braces,
  CalendarClock,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronDown,
  Copy,
  CreditCard,
  Droplet,
  FileScan,
  FileText,
  HeartPulse,
  ListOrdered,
  LoaderCircle,
  LocateFixed,
  LogIn,
  LogOut,
  MapPin,
  Menu,
  MessageSquare,
  MoreHorizontal,
  Paperclip,
  Navigation,
  PanelLeftClose,
  PanelLeftOpen,
  Phone,
  Pill,
  Plus,
  QrCode,
  Route,
  Search,
  Save,
  Scale,
  Send,
  Settings,
  Settings2,
  Shield,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  Store,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  UserCheck,
  UserRound,
  Volume2,
  WalletCards,
  Webhook,
  Workflow,
  X,
  XCircle,
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
import { GrokLiveCompanionPage } from './companion/GrokLiveCompanionPage';
import { NavigationPage } from './navigation/NavigationPage';
import { HealthTwinPage } from './health/HealthTwinPage';
import { HealthcareSpendingPage } from './spending/HealthcareSpendingPage';
import { PatientProfileModal } from './health/PatientProfileModal';
import { UserProfilePage } from './health/UserProfilePage';
import { SidebarUserCard } from './health/SidebarUserCard';
import { ProfileUpdateConfirmationCard } from './health/ProfileUpdateConfirmationCard';
import { extractUserProfileProposal } from './health/profileDisambiguation';
import {
  detectConversationalNavigation,
  extractMedicationProposal,
  extractAppointmentProposal,
  extractNavigationAction,
  extractSpendingProposal,
} from './chat/chatActionInteractions';
import { MedicationProposalCard } from './chat/MedicationProposalCard';
import { AppointmentProposalCard } from './chat/AppointmentProposalCard';
import { SpendingProposalCard } from './chat/SpendingProposalCard';
import { NavigationActionCard } from './chat/NavigationActionCard';
import { QuickNavActionCard } from './chat/QuickNavActionCard';
import { ActionPermissionConfirmationCard } from './chat/ActionPermissionConfirmationCard';
import { ErrorBoundary } from './common/ErrorBoundary';
import { DataManagementAuthGate } from './common/DataManagementAuthGate';
import { WORKSPACE_ROUTE_POLICIES } from './common/workspaceNavigationConfig';
import { processUnifiedTopicGatedChat, TOPIC_MODES } from './chat/topicGatedSync';
import {
  getSavedUserLocation,
  saveUserLocation,
  requestBrowserGeolocation,
  autoDetectLiveLocation,
  LOCATION_PRESETS,
  getLocationAuthorityLevel,
} from './locationState';

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
  {
    icon: Stethoscope,
    tag: 'Cấp cứu & Phân luồng',
    title: 'Tôi bị đau ngực và khó thở',
    desc: 'Đánh giá nguy cơ tim mạch và phản ứng sơ cấp cứu khẩn cấp',
    text: 'Tôi bị đau ngực lan tay trái và khó thở, cần hỗ trợ ngay.',
  },
  {
    icon: QrCode,
    tag: 'Chống hàng giả',
    title: 'Quét QR chống thuốc giả',
    desc: 'Đối chiếu mã số lô & serial với registry dược phẩm chính hãng',
    text: 'Kiểm tra QR hàng giả: product=MG-AMOX-500|lot=AMX2409|serial=VN24A001',
  },
  {
    icon: ShieldCheck,
    tag: 'An toàn dược học',
    title: 'Kiểm tra hai loại thuốc',
    desc: 'Rà soát nguy cơ tương tác, xuất huyết và đối kháng hoạt chất',
    text: 'Tôi đang dùng warfarin, dự định dùng aspirin. Kiểm tra an toàn thuốc.',
  },
  {
    icon: AlarmClock,
    tag: 'Nhắc lịch dùng thuốc',
    title: 'Đặt lịch uống thuốc',
    desc: 'Thiết lập thời khóa biểu nhắc liều dùng cá nhân hóa theo ca',
    text: '#lichthuoc uống amoxicillin lúc 8h và 20h mỗi ngày.',
  },
  {
    icon: HeartPulse,
    tag: 'Chỉ số sinh tồn',
    title: 'Đọc chỉ số tại nhà',
    desc: 'Phân tích SpO2, huyết áp, nhịp tim và cảnh báo dấu hiệu sớm',
    text: 'SpO2 của tôi là 94%, huyết áp 150/90, nhịp tim 105.',
  },
];

function Brand() {
  return (
    <div className="brand">
      <div className="brand-logo-wrap">
        <img src="/static/brand-mark.svg" alt="Biểu trưng MedGuard AI" width="34" height="34" />
        <span className="brand-live-pulse" />
      </div>
      <div className="brand-text">
        <div className="brand-title-row">
          <strong>MedGuard AI</strong>
          <span className="brand-pro-tag">PRO</span>
        </div>
        <span>Clinical Assistant</span>
      </div>
    </div>
  );
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
  dob: '',
  age: null,
  sex: null,
  phone: '',
  email: '',
  address: '',
  blood_type: '',
  height_cm: null,
  weight_kg: null,
  bmi: null,
  bhyt_number: '',
  bhyt_hospital: '',
  bhyt_rate: 80,
  bhxh_number: '',
  vssid_status: 'unlinked',
  life_insurance_provider: '',
  life_insurance_policy_no: '',
  coverage_limit_vnd: null,
  is_verified: false,
  current_medications: [],
  allergies: [],
  conditions: [],
  emergency_contact_name: '',
  emergency_contact_phone: '',
  emergency_contact_relation: '',
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

function Sidebar({
  open,
  close,
  collapse,
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onSchedule,
  onSchedulePage,
  onMedicationPage,
  onCompanionPage,
  onNavigationPage,
  onHealthPage,
  onSpendingPage,
  onProfilePage,
  onSettings,
  onSystem,
  activeView,
  search,
  setSearch,
  isGuest = false,
  context,
  account,
  onOpenProfile,
  onRequireAuth,
  onLogout,
}) {
  return <>
    {open && <button className="sidebar-scrim" type="button" aria-label="Đóng menu" onClick={close} />}
    <aside className={`sidebar ${open ? 'open' : ''}`}>
      <div className="sidebar-top"><Brand /><button className="icon-button sidebar-collapse" type="button" onClick={collapse} title="Thu gọn thanh bên" aria-label="Thu gọn thanh bên"><PanelLeftClose size={18} /></button><button className="icon-button sidebar-close" type="button" onClick={close} title="Đóng" aria-label="Đóng menu"><X size={18} /></button></div>
      <button className="new-chat" type="button" onClick={() => { onNew(); close(); }}><Plus size={17} /><span>Cuộc trò chuyện mới</span><span className="shortcut-badge">⌘K</span></button>
      <div className="history-search">
        <Search size={15} />
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          aria-label="Tìm kiếm lịch sử trò chuyện"
          placeholder="Tìm cuộc trò chuyện…"
          spellCheck="false"
          autoComplete="off"
        />
      </div>
      <div className="history-block"><span className="nav-label">Gần đây</span><nav aria-label="Lịch sử trò chuyện">
        {conversations.length ? conversations.map((item) => <div className={`history-row ${activeId === item.conversation_id && activeView === 'chat' ? 'active' : ''}`} key={item.conversation_id}><button type="button" onClick={() => { onSelect(item.conversation_id); close(); }}><MessageSquare size={15} /><span>{item.title}</span></button><button className="history-delete" type="button" title="Xóa cuộc trò chuyện" aria-label={`Xóa cuộc trò chuyện: ${item.title}`} onClick={() => onDelete(item.conversation_id)}><Trash2 size={14} /></button></div>) : <p className="history-empty">Chưa có cuộc trò chuyện</p>}
      </nav></div>
      <div className="sidebar-actions">
        <button type="button" className={`nav-link-btn ${activeView === 'health' ? 'active' : ''}`} onClick={() => { onHealthPage?.(); close(); }}>
          <HeartPulse size={17} />
          <span>Cơ thể & Sức khoẻ</span>
          {isGuest && <span className="sidebar-lock-tag" title="Yêu cầu đăng nhập">🔒</span>}
        </button>
        <button type="button" className={`nav-link-btn ${activeView === 'spending' ? 'active' : ''}`} onClick={() => { onSpendingPage?.(); close(); }}>
          <WalletCards size={17} />
          <span>Chi tiêu & Tiết kiệm Care</span>
          {isGuest && <span className="sidebar-lock-tag" title="Yêu cầu đăng nhập">🔒</span>}
        </button>
        <button type="button" className={`nav-link-btn ${activeView === 'profile' ? 'active' : ''}`} onClick={() => { onProfilePage?.(); close(); }}>
          <UserRound size={17} />
          <span>Hồ sơ & Bảo hiểm</span>
          {isGuest && <span className="sidebar-lock-tag" title="Yêu cầu đăng nhập">🔒</span>}
        </button>
        <button type="button" className={`nav-link-btn companion-nav-btn ${activeView === 'companion' ? 'active' : ''}`} onClick={() => { onCompanionPage?.(); close(); }}>
          <Sparkles size={17} />
          <span>Bác sĩ 3D Live</span>
          <span className="sidebar-live-tag">LIVE</span>
        </button>
        <button type="button" className={`nav-link-btn ${activeView === 'navigation' ? 'active' : ''}`} onClick={() => { onNavigationPage?.(); close(); }}><Route size={17} /><span>Bản đồ Cấp cứu & Google Places</span></button>
        <button type="button" className={`nav-link-btn ${activeView === 'schedule' ? 'active' : ''}`} onClick={() => { onSchedulePage(); close(); }}>
          <CalendarClock size={17} />
          <span>Lịch khám</span>
          {isGuest && <span className="sidebar-lock-tag" title="Yêu cầu đăng nhập">🔒</span>}
        </button>
        <button type="button" className={`nav-link-btn ${activeView === 'medication' ? 'active' : ''}`} onClick={() => { onMedicationPage(); close(); }}>
          <CalendarDays size={17} />
          <span>Lịch uống thuốc</span>
          {isGuest && <span className="sidebar-lock-tag" title="Yêu cầu đăng nhập">🔒</span>}
        </button>
        <button type="button" className="nav-link-btn" onClick={() => { onSettings(); close(); }}><Settings size={17} /><span>Cài đặt</span></button>
      </div>
      <div className="sidebar-foot-user">
        <SidebarUserCard
          context={context}
          account={account}
          isGuest={isGuest}
          onOpenProfile={() => { onProfilePage?.(); close(); }}
          onSettings={() => { onSettings(); close(); }}
          onLogout={onLogout}
          onRequireAuth={onRequireAuth}
          onNavigate={(target) => {
            if (target === 'health') onHealthPage?.();
            else if (target === 'spending') onSpendingPage?.();
            else if (target === 'companion') onCompanionPage?.();
            else if (target === 'profile') onProfilePage?.();
            close();
          }}
        />
      </div>
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
  return (
    <div className="welcome-view">
      <div className="welcome-hero-badge">
        <div className="welcome-avatar-aura">
          <img src="/static/brand-mark.svg" alt="Biểu trưng MedGuard AI" width="56" height="56" />
          <span className="welcome-aura-ring" />
        </div>
        <span className="welcome-pill-kicker">
          <Sparkles size={13} /> TRỢ LÝ Y KHOA LÂM SÀNG THÔNG MINH
        </span>
      </div>
      <h1>Bạn cần hỗ trợ gì hôm nay?</h1>
      <p className="welcome-subtitle">
        Phân luồng triệu chứng khẩn cấp, rà soát an toàn dược học và đối chiếu mã vạch chống thuốc giả theo chuẩn Bộ Y tế.
      </p>
      <div className="starter-grid">
        {starterPrompts.map((item) => {
          const Icon = item.icon;
          return (
            <button
              type="button"
              className="starter-card"
              key={item.title}
              onClick={() => onPrompt(item.text)}
              aria-label={item.title}
            >
              <div className="starter-card-icon-wrap">
                <Icon size={19} />
              </div>
              <div className="starter-card-content">
                <span className="starter-card-tag">{item.tag}</span>
                <strong className="starter-card-title">{item.title}</strong>
                <span className="starter-card-desc">{item.desc}</span>
              </div>
              <div className="starter-card-arrow" aria-hidden="true">
                <Send size={14} />
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function Conversation({
  entries,
  busy,
  onNotify,
  onSelectQuestion,
  speakingKey,
  setSpeakingKey,
  setSpeakingText,
  onAcceptProfileProposal,
  onDeclineProfileProposal,
  onOpenProfile,
  onAcceptMedicationProposal,
  onDeclineMedicationProposal,
  onAcceptAppointmentProposal,
  onDeclineAppointmentProposal,
  onAcceptSpendingProposal,
  onDeclineSpendingProposal,
  onOpenNavigation,
  onNavigate,
  onAcceptSyncProposal,
  onDeclineSyncProposal,
  autoSubmitUpdates = false,
  onToggleAutoSubmit,
}) {
  const streamRef = useRef(null);
  const latestRef = useRef(null);
  const [copied, setCopied] = useState(null);
  const [feedback, setFeedback] = useState({});

  // Smart scrolling states
  const [showScrollBottom, setShowScrollBottom] = useState(false);
  const [hasNewMessages, setHasNewMessages] = useState(false);
  const isAtBottomRef = useRef(true);
  const prevEntriesLengthRef = useRef(entries.length);

  // Dynamic clinical loading phases & elapsed timer
  const [loadingPhase, setLoadingPhase] = useState(0);
  const [loadingElapsed, setLoadingElapsed] = useState(0);

  useEffect(() => {
    if (!busy) {
      setLoadingPhase(0);
      setLoadingElapsed(0);
      return undefined;
    }
    const startTime = Date.now();
    const interval = setInterval(() => {
      setLoadingElapsed(+((Date.now() - startTime) / 1000).toFixed(1));
    }, 100);
    const timer1 = setTimeout(() => setLoadingPhase(1), 1400);
    const timer2 = setTimeout(() => setLoadingPhase(2), 3000);
    return () => {
      clearInterval(interval);
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
        if (latest?.profileProposal || latest?.medicationProposal || latest?.appointmentProposal || latest?.navigationAction || latest?.navCommand || latest?.syncProposal) {
          // An interactive proposal/navigation card is present -> scroll to reveal it immediately
          scrollToBottom(true);
        } else {
          // Show the start of a new answer. Pinning a long answer to its end
          // hides the emergency action on small screens.
          const replies = streamRef.current.querySelectorAll('.chat-assistant:not(.pending-premium)');
          const reply = replies[replies.length - 1];
          if (reply) {
            const top = scroller.scrollTop + reply.getBoundingClientRect().top - scroller.getBoundingClientRect().top - 12;
            scroller.scrollTo({ top: Math.max(0, top), behavior: 'instant' });
          }
        }
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
      setSpeakingText?.(null);
      return;
    }
    window.speechSynthesis.cancel();
    const textToRead = entry.answer?.summary || entry.text || '';
    const cleanText = textToRead.replace(/[#*`_]/g, '');
    const utter = new SpeechSynthesisUtterance(cleanText);
    utter.lang = 'vi-VN';
    utter.rate = 1.0;
    utter.onend = () => {
      setSpeakingKey(null);
      setSpeakingText?.(null);
    };
    utter.onerror = () => {
      setSpeakingKey(null);
      setSpeakingText?.(null);
    };
    setSpeakingKey(key);
    setSpeakingText?.(cleanText);
    window.speechSynthesis.speak(utter);
    onNotify?.('Bác sĩ ảo đang giải thích lâm sàng');
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
            <div className="assistant-avatar-wrap">
              <img className="assistant-avatar" src="/static/brand-mark.svg" alt="MedGuard AI" width="30" height="30" />
              <span className="avatar-online-dot" title="Hệ thống trực tuyến" />
            </div>
            <div className="assistant-content">
              <div className="assistant-header-meta">
                <div className="assistant-identity">
                  <strong>MedGuard AI</strong>
                  <span className="assistant-version-badge">Bác Sĩ Trợ Lý AI</span>
                  {entry.topic_label && (
                    <span
                      className={`assistant-topic-badge topic-${(entry.topic_mode || 'unrelated').toLowerCase().replace(/_/g, '-')}`}
                      title="Chế độ phân luồng đồng bộ chủ đề MedGuard AI"
                    >
                      {entry.topic_label}
                    </span>
                  )}
                  {entry.verification_status === 'verified' && (
                    <span className="assistant-verified-badge" title="Đã qua kiểm định an toàn y tế">
                      <ShieldCheck size={12} />
                      Đã đối soát an toàn y tế
                    </span>
                  )}
                </div>
              </div>
              {entry.answer ? (
                <GroundedAnswer
                  answer={entry.answer}
                  result={entry.result}
                  responseMeta={entry}
                  userQuery={entries[index - 1]?.text || entry.userQuery}
                  onSelectQuestion={onSelectQuestion}
                />
              ) : (
                <p>{entry.text}</p>
              )}
              {entry.suggestions?.length > 0 && index === entries.length - 1 && (
                <div className="assistant-suggestions-bar">
                  <span className="suggestions-lead">Gợi ý phản hồi nhanh:</span>
                  <div className="suggestion-chips-row">
                    {entry.suggestions.map((sug, sIdx) => (
                      <button
                        key={`${sug.label}-${sIdx}`}
                        type="button"
                        className="suggestion-chip-btn"
                        onClick={() => onSelectSuggestion ? onSelectSuggestion(sug.prompt || sug.label) : null}
                      >
                        {sug.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {entry.status === 'needs_information' && !entry.answer && (
                <span className="answer-state needs_information">Cần thêm thông tin</span>
              )}
              {entry.profileProposal && (
                <ProfileUpdateConfirmationCard
                  proposal={entry.profileProposal}
                  status={entry.profileProposalStatus || 'pending'}
                  onAccept={(prop) => onAcceptProfileProposal?.(prop, key)}
                  onDecline={() => onDeclineProfileProposal?.(key)}
                  onOpenProfile={onOpenProfile}
                  autoSubmit={autoSubmitUpdates}
                  onToggleAutoSubmit={onToggleAutoSubmit}
                />
              )}
              {entry.syncProposal && (
                <ActionPermissionConfirmationCard
                  proposal={entry.syncProposal}
                  status={entry.syncProposalStatus || 'pending'}
                  onAccept={(prop) => onAcceptSyncProposal?.(prop, key)}
                  onDecline={() => onDeclineSyncProposal?.(key)}
                  autoSubmit={autoSubmitUpdates}
                  onToggleAutoSubmit={onToggleAutoSubmit}
                  onNavigate={onNavigate}
                />
              )}
              {entry.medicationProposal && (
                <MedicationProposalCard
                  proposal={entry.medicationProposal}
                  status={entry.medicationProposalStatus || 'pending'}
                  onAccept={(prop) => onAcceptMedicationProposal?.(prop, key)}
                  onDecline={() => onDeclineMedicationProposal?.(key)}
                  onOpenMedication={() => onNavigate?.('medication')}
                  autoSubmit={autoSubmitUpdates}
                  onToggleAutoSubmit={onToggleAutoSubmit}
                />
              )}
              {entry.appointmentProposal && (
                <AppointmentProposalCard
                  proposal={entry.appointmentProposal}
                  status={entry.appointmentProposalStatus || 'pending'}
                  onAccept={(prop) => onAcceptAppointmentProposal?.(prop, key)}
                  onDecline={() => onDeclineAppointmentProposal?.(key)}
                  onOpenSchedule={() => onNavigate?.('schedule')}
                  autoSubmit={autoSubmitUpdates}
                  onToggleAutoSubmit={onToggleAutoSubmit}
                />
              )}
              {entry.spendingProposal && (
                <SpendingProposalCard
                  proposal={entry.spendingProposal}
                  status={entry.spendingProposalStatus || 'pending'}
                  onAccept={(prop) => onAcceptSpendingProposal?.(prop, key)}
                  onDecline={() => onDeclineSpendingProposal?.(key)}
                  onOpenSpending={() => onNavigate?.('spending')}
                  autoSubmit={autoSubmitUpdates}
                  onToggleAutoSubmit={onToggleAutoSubmit}
                />
              )}
              {entry.navigationAction && (
                <NavigationActionCard
                  action={entry.navigationAction}
                  onOpenNavigation={onOpenNavigation}
                />
              )}
              {entry.navCommand && (
                <QuickNavActionCard
                  navCommand={entry.navCommand}
                  onNavigate={onNavigate}
                />
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
                  {speakingKey === key ? (
                    <span className="speaking-wave-bars" aria-hidden="true">
                      <span className="wave-bar" />
                      <span className="wave-bar" />
                      <span className="wave-bar" />
                    </span>
                  ) : (
                    <Volume2 size={14} />
                  )}
                </button>
              </div>
            </div>
          </article>
        );
      })}

      {busy && (
        <article className="chat-assistant pending-premium message-enter">
          <div className="assistant-avatar-wrap">
            <div className="assistant-avatar-container pulse-glow">
              <img className="assistant-avatar" src="/static/brand-mark.svg" alt="MedGuard AI" width="30" height="30" />
              <span className="avatar-live-indicator" title="AI đang kết nối trực tiếp" />
            </div>
          </div>
          <div className="assistant-content">
            <div className="assistant-header-meta">
              <strong>MedGuard AI</strong>
              <span className="assistant-subtag">Bác Sĩ Trợ Lý AI • Clinical Intelligence</span>
            </div>

            <div className="premium-thinking-card" role="status" aria-live="polite">
              {/* Header: Phase Title & Live Timer */}
              <div className="thinking-header">
                <div className="thinking-badge">
                  <span className="sr-only">MedGuard đang xử lý</span>
                  <span className="thinking-pulse-dot" />
                  <Sparkles className="spin-slow" size={14} />
                  <span className="thinking-phase-text">
                    {loadingPhase === 0 && 'Phân tích ngữ cảnh & Nhận diện chủ đề…'}
                    {loadingPhase === 1 && 'Tổng hợp dữ liệu hồ sơ & Cơ sở tri thức lâm sàng…'}
                    {loadingPhase >= 2 && 'Kiểm định an toàn y khoa qua Clinical Safety Gate…'}
                  </span>
                </div>
                <div className="thinking-meta-right">
                  <div className="thinking-timer-pill">
                    <Activity size={12} className="ecg-pulse-icon" />
                    <span>{loadingElapsed > 0 ? `${loadingElapsed}s` : 'Đang xử lý'}</span>
                  </div>
                  <div className="thinking-dots" aria-hidden="true">
                    <i /><i /><i />
                  </div>
                </div>
              </div>

              {/* 3-Step Pipeline Breadcrumb */}
              <div className="thinking-pipeline-steps" aria-hidden="true">
                <div className={`pipeline-step ${loadingPhase >= 0 ? 'active' : ''} ${loadingPhase > 0 ? 'completed' : ''}`}>
                  <span className="step-num">{loadingPhase > 0 ? '✓' : '1'}</span>
                  <span className="step-text">Ngữ cảnh & Chủ đề</span>
                </div>
                <div className="pipeline-divider">
                  <span className={`pipeline-line-fill phase-${loadingPhase}`} />
                </div>
                <div className={`pipeline-step ${loadingPhase >= 1 ? 'active' : ''} ${loadingPhase > 1 ? 'completed' : ''}`}>
                  <span className="step-num">{loadingPhase > 1 ? '✓' : '2'}</span>
                  <span className="step-text">Tri thức & Hồ sơ</span>
                </div>
                <div className="pipeline-divider">
                  <span className={`pipeline-line-fill phase-${loadingPhase >= 2 ? '2' : '1'}`} />
                </div>
                <div className={`pipeline-step ${loadingPhase >= 2 ? 'active' : ''}`}>
                  <span className="step-num">3</span>
                  <span className="step-text">Cổng An toàn</span>
                </div>
              </div>

              {/* Animated ECG Pulse Waveform */}
              <div className="thinking-ecg-container" aria-hidden="true">
                <svg className="thinking-ecg-svg" viewBox="0 0 500 24" preserveAspectRatio="none">
                  <path
                    className="thinking-ecg-track"
                    d="M 0,12 L 120,12 L 130,12 L 138,4 L 145,20 L 152,1 L 158,16 L 164,12 L 280,12 L 290,12 L 298,4 L 305,20 L 312,1 L 318,16 L 324,12 L 500,12"
                    fill="none"
                    stroke="#e2e8f0"
                    strokeWidth="1.5"
                  />
                  <path
                    className="thinking-ecg-pulse"
                    d="M 0,12 L 120,12 L 130,12 L 138,4 L 145,20 L 152,1 L 158,16 L 164,12 L 280,12 L 290,12 L 298,4 L 305,20 L 312,1 L 318,16 L 324,12 L 500,12"
                    fill="none"
                    stroke="url(#ecg-gradient)"
                    strokeWidth="2"
                    strokeDasharray="90 410"
                  />
                  <defs>
                    <linearGradient id="ecg-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                      <stop offset="0%" stopColor="#0d9488" stopOpacity="0.1" />
                      <stop offset="50%" stopColor="#14b8a6" stopOpacity="1" />
                      <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.2" />
                    </linearGradient>
                  </defs>
                </svg>
              </div>

              {/* Shimmer Skeleton Placeholder */}
              <div className="skeleton-container" aria-hidden="true">
                <div className="skeleton-row-top">
                  <div className="skeleton-line skeleton-badge shimmer" />
                  <div className="skeleton-line skeleton-status shimmer" />
                </div>
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

function Composer({ value, setValue, onSend, busy, selectedTool, setSelectedTool, attachment, setAttachment, onQr, isGuestLocked = false, guestMax = 3, onRequireAuth = null }) {
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
    if (isGuestLocked || (!value.trim() && !attachment) || busy) return;
    onSend();
  };

  return <div className="composer-wrap">
    {isGuestLocked ? (
      <div className="guest-composer-locked">
        <div className="guest-locked-content">
          <div className="guest-locked-badge">Hết lượt hỏi dùng thử</div>
          <strong>Bạn đã hoàn thành {guestMax}/{guestMax} lượt hỏi miễn phí</strong>
          <p>Để tiếp tục nhận hướng dẫn lâm sàng cá nhân hóa và đồng bộ hồ sơ sức khỏe, vui lòng đăng nhập hoặc tạo tài khoản MedGuard AI.</p>
        </div>
        <button type="button" className="guest-locked-action-btn" onClick={onRequireAuth}>
          Đăng ký / Đăng nhập ngay →
        </button>
      </div>
    ) : (
      <form className="composer-box" onSubmit={(event) => { event.preventDefault(); submit(); }}>
        {attachment && <div className="attachment-preview"><img src={attachment.url} alt="Ảnh chuẩn bị gửi" width="48" height="48" /><div><strong>{attachment.file.name}</strong><span>{Math.ceil(attachment.file.size / 1024)} KB</span></div><button className="icon-button" type="button" title="Bỏ ảnh" aria-label="Bỏ ảnh" onClick={() => setAttachment(null)}><X size={16} /></button></div>}
        <textarea ref={textareaRef} rows="1" value={value} onChange={(event) => setValue(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); submit(); } }} placeholder="Nhắn cho MedGuard AI…" aria-label="Tin nhắn" />
        <div className="composer-tools">
          <div className="composer-left">
            <button className="icon-button" type="button" title="Đính kèm ảnh đơn thuốc hoặc kết quả khám" aria-label="Đính kèm ảnh" onClick={() => fileRef.current?.click()}><Paperclip size={19} /></button>
            <input ref={fileRef} className="visually-hidden" type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => { const file = event.target.files?.[0]; if (file) setAttachment({ file, url: URL.createObjectURL(file) }); event.target.value = ''; }} />
            <button className="icon-button" type="button" title="Quét QR sản phẩm" aria-label="Quét QR" onClick={onQr}><QrCode size={19} /></button>
            <div className="tool-anchor" ref={toolAnchorRef}><button className="mode-button" type="button" aria-haspopup="menu" aria-expanded={toolsOpen} onClick={() => setToolsOpen(!toolsOpen)}><ToolIcon size={16} /><span>{tool.label}</span><ChevronDown size={14} /></button><ToolMenu open={toolsOpen} selected={selectedTool} onSelect={(id) => { setSelectedTool(id); setToolsOpen(false); }} /></div>
          </div>
          <button className="send-button" type="submit" title="Gửi" aria-label="Gửi tin nhắn" disabled={busy || (!value.trim() && !attachment)}>{busy ? <LoaderCircle className="spin" size={18} /> : <Send size={18} />}</button>
        </div>
      </form>
    )}
    <p className="composer-disclaimer">MedGuard AI có thể mắc lỗi. Quyết định lâm sàng cần người có thẩm quyền xác nhận.</p>
  </div>;
}

const newContext = (profile = emptyProfile) => ({ ...emptyProfile, ...profile, last_result: null });

function clinicalContext(context, userLocation = null) {
  const normalizedSex = (context.sex === 'male' || context.sex === 'female' || context.sex === 'other') ? context.sex : null;
  return {
    patient_ref: context.patient_ref || null,
    display_name: context.display_name || null,
    age: context.age ? Number(context.age) : null,
    dob: context.dob || null,
    sex: normalizedSex,
    blood_type: context.blood_type || null,
    height_cm: context.height_cm ? Number(context.height_cm) : null,
    weight_kg: context.weight_kg ? Number(context.weight_kg) : null,
    bmi: context.bmi ? Number(context.bmi) : null,
    bhyt_number: context.bhyt_number || null,
    bhyt_hospital: context.bhyt_hospital || null,
    bhyt_rate: context.bhyt_rate || 80,
    bhxh_number: context.bhxh_number || null,
    life_insurance_provider: context.life_insurance_provider || null,
    coverage_limit_vnd: context.coverage_limit_vnd ? Number(context.coverage_limit_vnd) : null,
    is_verified: Boolean(context.is_verified),
    current_medications: Array.isArray(context.current_medications) ? context.current_medications : [],
    allergies: Array.isArray(context.allergies) ? context.allergies : [],
    conditions: Array.isArray(context.conditions) ? context.conditions : [],
    emergency_contact_name: context.emergency_contact_name || null,
    last_result: context.last_result || null,
    user_location: userLocation || context.user_location || null,
  };
}

const getTwinKey = (acc) => {
  const uid = acc?.user_id || acc?.id || acc?.email;
  return uid ? `medguard_health_twin_profile_${uid}` : 'medguard_health_twin_profile_guest';
};

const getFinKey = (acc) => {
  const uid = acc?.user_id || acc?.id || acc?.email;
  return uid ? `medguard_financial_assessment_${uid}` : 'medguard_financial_assessment_guest';
};

export default function App({
  account = null,
  isGuest = false,
  guestCount = 0,
  guestMax = 3,
  onGuestQuestionAsked = null,
  onRequireAuth = null,
  onManageAccount = null,
  onLogout = null,
}) {
  const guestRemaining = Math.max(0, guestMax - guestCount);
  const isGuestLocked = isGuest && guestRemaining <= 0;
  const [tenantId, setTenantId] = useState(account?.scope || 'tenant-demo');
  const [apiKey, setApiKey] = useState(account ? '' : 'demo-key');
  const [consentToken, setConsentToken] = useState('consent-valid-ui');
  const [conversationId, setConversationId] = useState(() => crypto.randomUUID());
  const [conversationTitle, setConversationTitle] = useState('Cuộc trò chuyện mới');
  const [conversations, setConversations] = useState([]);
  const [entries, setEntries] = useState([]);
  const [message, setMessage] = useState('');
  const [context, setContext] = useState(() => newContext(account ? {} : loadProfile('tenant-demo')));
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
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [qrOpen, setQrOpen] = useState(false);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsInitialTab, setSettingsInitialTab] = useState('general');
  const [speakingKey, setSpeakingKey] = useState(null);
  const [speakingText, setSpeakingText] = useState(null);
  const [autoSpeak, setAutoSpeak] = useState(false);
  const [readiness, setReadiness] = useState(null);
  const [view, setView] = useState(() => {
    try {
      const sp = new URLSearchParams(window.location.search);
      const hash = window.location.hash.replace(/^#\/?/, '');
      const initial = sp.get('view') || hash;
      if (['chat', 'companion', 'schedule', 'medication', 'navigation', 'health', 'spending', 'system', 'profile'].includes(initial)) {
        return initial;
      }
    } catch {}
    return 'chat';
  });
  const [historySearch, setHistorySearch] = useState('');
  const [toast, setToast] = useState(null);
  const [chatTimeoutMs, setChatTimeoutMs] = useState(35000);
  const [userLocation, setUserLocation] = useState(() => getSavedUserLocation());
  const [locationPromptOpen, setLocationPromptOpen] = useState(false);
  const [requestingGps, setRequestingGps] = useState(false);
  const [navigationContext, setNavigationContext] = useState(null);
  const toastTimerRef = useRef(null);

  // Global Auto-Submit Setting (ChatGPT Action Permission)
  const [autoSubmitUpdates, setAutoSubmitUpdates] = useState(() => {
    try {
      return localStorage.getItem('medguard_auto_apply_sync_updates') === 'true';
    } catch {
      return false;
    }
  });

  useEffect(() => {
    const handleAutoSubmitChange = (e) => {
      setAutoSubmitUpdates(!!e.detail);
    };
    window.addEventListener('medguard:auto-submit-changed', handleAutoSubmitChange);

    // Global sanitizer: Purge any legacy mock records from localStorage
    try {
      const rawAssessment = localStorage.getItem('medguard_financial_assessment');
      if (rawAssessment && (rawAssessment.includes('22450') || rawAssessment.includes('8531') || rawAssessment.includes('2450000'))) {
        localStorage.removeItem('medguard_financial_assessment');
      }
      const rawShifts = localStorage.getItem('medguard.shifts.data');
      if (rawShifts && (rawShifts.includes('Nguyễn Văn An') || rawShifts.includes('Trần Thị Mai'))) {
        localStorage.removeItem('medguard.shifts.data');
      }
      const rawSpending = localStorage.getItem('medguard_spending_transactions');
      localStorage.removeItem('medguard_health_twin_profile');
      localStorage.removeItem('medguard_financial_assessment');
      localStorage.removeItem('medguard_spending_transactions');
    } catch {}

    return () => window.removeEventListener('medguard:auto-submit-changed', handleAutoSubmitChange);
  }, []);

  useEffect(() => {
    const handleCustomNavigate = (e) => {
      const detail = e.detail;
      let target = typeof detail === 'string' ? detail : detail?.view;
      if (target === 'twin') target = 'health';
      if (target === 'appointments') target = 'schedule';
      if (target === 'medications') target = 'medication';
      if (['chat', 'companion', 'schedule', 'medication', 'navigation', 'health', 'spending', 'system', 'profile'].includes(target)) {
        if (detail && typeof detail === 'object' && detail.navigationContext) {
          setNavigationContext(detail.navigationContext);
        }
        setView(target);
      }
    };
    window.addEventListener('medguard:navigate', handleCustomNavigate);
    return () => window.removeEventListener('medguard:navigate', handleCustomNavigate);
  }, []);

  useEffect(() => {
    try {
      const sp = new URLSearchParams(window.location.search);
      if (sp.get('view') !== view) {
        sp.set('view', view);
        const newUrl = `${window.location.pathname}?${sp.toString()}${window.location.hash}`;
        window.history.replaceState(null, '', newUrl);
      }
    } catch {}
  }, [view]);

  useEffect(() => {
    const handleLocChange = (e) => {
      if (e.detail && typeof e.detail.lat === 'number') {
        setUserLocation((prev) => {
          if (
            prev &&
            prev.name === e.detail.name &&
            Math.abs(prev.lat - e.detail.lat) < 0.00008 &&
            Math.abs(prev.lng - e.detail.lng) < 0.00008
          ) {
            return prev;
          }
          const prevAuth = getLocationAuthorityLevel(prev);
          const newAuth = getLocationAuthorityLevel(e.detail);
          if (newAuth < prevAuth) {
            return prev;
          }
          return e.detail;
        });
      }
    };
    window.addEventListener('medguard:location-changed', handleLocChange);
    return () => window.removeEventListener('medguard:location-changed', handleLocChange);
  }, []);

  useEffect(() => {
    // Automatically detect user's live position (GPS or IP network) on startup
    autoDetectLiveLocation().then((loc) => {
      if (loc && typeof loc.lat === 'number' && typeof loc.lng === 'number') {
        setUserLocation((prev) => {
          const prevAuth = getLocationAuthorityLevel(prev);
          const newAuth = getLocationAuthorityLevel(loc);
          if (newAuth < prevAuth) return prev;
          return loc;
        });
      }
    });
  }, []);

  const handleRequestGps = async () => {
    setRequestingGps(true);
    try {
      const loc = await requestBrowserGeolocation();
      setUserLocation(loc);
      notify(`Đã cập nhật GPS thực tế: ${loc.address?.slice(0, 45) || 'Vị trí hiện tại'}...`);
      setLocationPromptOpen(false);
    } catch (err) {
      notify(err.message || 'Không thể lấy GPS. Vui lòng cho phép quyền truy cập vị trí trên trình duyệt.');
    } finally {
      setRequestingGps(false);
    }
  };

  const handleSelectPreset = (preset) => {
    const loc = { ...preset, is_gps: false, permission_status: 'custom' };
    saveUserLocation(loc);
    setUserLocation(loc);
    notify(`Đã chọn vị trí: ${preset.name}`);
    setLocationPromptOpen(false);
  };

  const api = useMemo(() => createApiClient({ tenantId, apiKey, consentToken }), [tenantId, apiKey, consentToken]);
  const hasPendingGatewayReview = entries.some(
    (entry) => entry.role === 'assistant' && entry.verification_status === 'shadow_pending',
  );

  const notify = (arg1, arg2) => {
    window.clearTimeout(toastTimerRef.current);
    let msg = '';
    const knownTypes = new Set(['success', 'error', 'info', 'warning', 'danger']);
    if (typeof arg1 === 'string' && knownTypes.has(arg1.toLowerCase()) && arg2) {
      msg = arg2;
    } else if (typeof arg2 === 'string' && knownTypes.has(arg2.toLowerCase()) && arg1) {
      msg = arg1;
    } else {
      msg = arg1 || arg2;
    }
    if (typeof msg !== 'string') {
      msg = msg?.message || msg?.text || (msg ? String(msg) : null);
    }
    if (!msg) return;
    setToast(msg);
    toastTimerRef.current = window.setTimeout(() => setToast(null), 2800);
  };

  const clearAllConversations = async () => {
    try {
      for (const item of conversations) {
        await api.request(`/v1/chat/conversations/${encodeURIComponent(item.conversation_id)}`, { method: 'DELETE' });
      }
    } catch {
      // Fallback local cleanup
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
    Promise.allSettled([
      api.request('/v1/health/readiness'),
      api.request('/v1/chat/conversations'),
      api.request('/v1/companion/status', { timeoutMs: 5000 }),
    ]).then(([health, history, compStatus]) => {
      if (!mounted) return;
      setReadiness(health.status === 'fulfilled' ? health.value : null);
      const convList = history.status === 'fulfilled' ? history.value.conversations || [] : [];
      setConversations(convList);
      if (compStatus.status === 'fulfilled' && compStatus.value?.chat_timeout_ms) {
        setChatTimeoutMs(Math.max(compStatus.value.chat_timeout_ms, 35000));
      }
      try {
        const lastActiveId = sessionStorage.getItem('medguard_active_conversation_id');
        const targetId = (lastActiveId && convList.some((c) => c.conversation_id === lastActiveId))
          ? lastActiveId
          : (convList.length > 0 ? convList[0].conversation_id : null);
        if (targetId) {
          selectConversation(targetId);
        }
      } catch {}
    });
    return () => { mounted = false; };
  }, [api]);

  useEffect(() => {
    let activeId = null;
    try { activeId = sessionStorage.getItem('medguard_active_conversation_id'); } catch {}
    if (!activeId) {
      setConversationId(crypto.randomUUID());
      setConversationTitle('Cuộc trò chuyện mới');
      setEntries([]);
    }
    let mounted = true;
    if (account) api.request('/v1/auth/profile').then(d => { if (mounted) setContext(newContext(d.profile)); }).catch(() => {});
    else setContext(newContext(loadProfile(tenantId)));
    return () => { mounted = false; };
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
    try { sessionStorage.removeItem('medguard_active_conversation_id'); } catch {}
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
    if (account) {
      try { await api.request('/v1/auth/profile', { method: 'PUT', body: profile }); }
      catch (e) { notify(e.message); return; }
    }
    try {
      localStorage.setItem(`medguard.profile.${tenantId}`, JSON.stringify(profile));
      localStorage.setItem('medguard_verified_patient_profile', JSON.stringify(profile));
    } catch {
      // The profile still applies to the current tab when browser storage is unavailable.
    }
    setContext((current) => ({ ...current, ...profile }));
    window.dispatchEvent(new CustomEvent('medguard:profile-updated', { detail: profile }));
    setPatientOpen(false);
    notify('Đã lưu Hồ sơ y tế & Xác thực bảo hiểm');
  };

  const handleAcceptProfileProposal = async (proposal, entryKey) => {
    if (!proposal?.fields) return;
    const updated = {
      ...context,
      ...proposal.fields,
    };
    await saveProfile(updated);
    setEntries((prev) =>
      prev.map((item, idx) => {
        const key = item.id || idx;
        if (key === entryKey || (item.profileProposal && item.profileProposal.proposalId === proposal.proposalId)) {
          return { ...item, profileProposalStatus: 'accepted' };
        }
        return item;
      })
    );
    notify('Đã tự động cập nhật Hồ sơ cá nhân & Bảo hiểm thành công!');
  };

  const handleDeclineProfileProposal = (entryKey) => {
    setEntries((prev) =>
      prev.map((item, idx) => {
        const key = item.id || idx;
        if (key === entryKey) {
          return { ...item, profileProposalStatus: 'declined' };
        }
        return item;
      })
    );
    notify('Đã hủy bỏ cập nhật theo yêu cầu');
  };

  const handleAcceptSyncProposal = (proposal, entryKey) => {
    if (!proposal) return;
    if (proposal.rememberAutoSubmit) {
      setAutoSubmitUpdates(true);
      try {
        localStorage.setItem('medguard_auto_apply_sync_updates', 'true');
      } catch {}
    }

    if (proposal.healthMutation) {
      try {
        localStorage.setItem(getTwinKey(account), JSON.stringify(proposal.healthMutation));
      } catch {}
      window.dispatchEvent(
        new CustomEvent('medguard:health-twin-updated', {
          detail: { healthMutation: proposal.healthMutation },
        })
      );
    }

    if (proposal.expenseMutation) {
      try {
        localStorage.setItem(getFinKey(account), JSON.stringify(proposal.expenseMutation));
        if (proposal.expenseMutation.monthly_budget_target_vnd) {
          const budgetKey = account ? `medguard_budget_target_vnd_${account.user_id || account.id || account.email}` : 'medguard_budget_target_vnd';
          localStorage.setItem(budgetKey, String(proposal.expenseMutation.monthly_budget_target_vnd));
        }
      } catch {}
      if (api && proposal.expenseMutation.recent_transactions?.length) {
        for (const tx of proposal.expenseMutation.recent_transactions) {
          api.request('/v1/user/spending', {
            method: 'POST',
            body: {
              title: tx.title,
              amount_vnd: Math.abs(tx.amount_vnd || 480000),
              category: tx.category || 'medication',
              provider: 'Nhà thuốc Long Châu',
              doctor: 'Dược sĩ lâm sàng',
              is_gpp: true,
              bhyt_covered_vnd: Math.round((tx.amount_vnd || 480000) * 0.8),
            },
          }).catch((err) => console.warn('Could not sync expense to DB:', err));
        }
      }
      window.dispatchEvent(
        new CustomEvent('medguard:financial-updated', {
          detail: { expenseMutation: proposal.expenseMutation },
        })
      );
    }

    setEntries((prev) =>
      prev.map((item, idx) => {
        const key = item.id || idx;
        if (key === entryKey) {
          return { ...item, syncProposalStatus: 'accepted' };
        }
        return item;
      })
    );
    notify(`Đã cấp quyền & cập nhật dữ liệu thành công vào ${proposal.moduleTitle || 'hệ sinh thái'}!`);
  };

  const handleDeclineSyncProposal = (entryKey) => {
    setEntries((prev) =>
      prev.map((item, idx) => {
        const key = item.id || idx;
        if (key === entryKey) {
          return { ...item, syncProposalStatus: 'declined' };
        }
        return item;
      })
    );
    notify('Đã từ chối cấp quyền cập nhật dữ liệu.');
  };

  const handleAcceptMedicationProposal = async (proposal, entryKey) => {
    if (!proposal?.medication) return;
    const med = proposal.medication;
    try {
      const raw = localStorage.getItem('medguard.user_meds.data');
      let currentMeds = raw ? JSON.parse(raw) : [];
      currentMeds = [med, ...currentMeds.filter((m) => m.name.toLowerCase() !== med.name.toLowerCase())];
      localStorage.setItem('medguard.user_meds.data', JSON.stringify(currentMeds));
      window.dispatchEvent(new CustomEvent('medguard:medication-added', { detail: med }));
    } catch (e) {
      console.warn('Error saving medication to localStorage', e);
    }
    if (api) {
      try {
        await api.request('/v1/medication/regimen', {
          method: 'POST',
          body: med,
        });
      } catch (err) {
        console.warn('Could not sync medication to DB:', err);
      }
    }
    setEntries((prev) =>
      prev.map((item, idx) => {
        const key = item.id || idx;
        if (key === entryKey || (item.medicationProposal && item.medicationProposal.proposalId === proposal.proposalId)) {
          return { ...item, medicationProposalStatus: 'accepted' };
        }
        return item;
      })
    );
    notify(`Đã thêm ${med.name} vào Lịch uống thuốc thành công!`);
  };

  const handleDeclineMedicationProposal = (entryKey) => {
    setEntries((prev) =>
      prev.map((item, idx) => {
        const key = item.id || idx;
        if (key === entryKey) {
          return { ...item, medicationProposalStatus: 'declined' };
        }
        return item;
      })
    );
    notify('Đã bỏ qua lịch uống thuốc');
  };

  const handleAcceptAppointmentProposal = async (proposal, entryKey) => {
    if (!proposal?.appointment) return;
    const appt = proposal.appointment;
    try {
      const raw = localStorage.getItem('medguard.shifts.data');
      let currentShifts = raw ? JSON.parse(raw) : [];
      currentShifts = [appt, ...currentShifts.filter((s) => s.id !== appt.id)];
      localStorage.setItem('medguard.shifts.data', JSON.stringify(currentShifts));
      window.dispatchEvent(new CustomEvent('medguard:appointment-booked', { detail: appt }));
    } catch (e) {
      console.warn('Error saving appointment to localStorage', e);
    }
    if (api) {
      try {
        await api.request('/v1/schedule/shifts', {
          method: 'POST',
          body: appt,
        });
      } catch (err) {
        console.warn('Could not sync appointment to DB:', err);
      }
    }
    setEntries((prev) =>
      prev.map((item, idx) => {
        const key = item.id || idx;
        if (key === entryKey || (item.appointmentProposal && item.appointmentProposal.proposalId === proposal.proposalId)) {
          return { ...item, appointmentProposalStatus: 'accepted' };
        }
        return item;
      })
    );
    notify(`Đã xác nhận đặt lịch khám với ${appt.doctor} thành công!`);
  };

  const handleDeclineAppointmentProposal = (entryKey) => {
    setEntries((prev) =>
      prev.map((item, idx) => {
        const key = item.id || idx;
        if (key === entryKey) {
          return { ...item, appointmentProposalStatus: 'declined' };
        }
        return item;
      })
    );
    notify('Đã hủy lịch hẹn khám');
  };

  const handleAcceptSpendingProposal = async (proposal, entryKey) => {
    if (!proposal?.spending) return;
    const spend = proposal.spending;
    if (api) {
      try {
        await api.request('/v1/user/spending', {
          method: 'POST',
          body: spend,
        });
      } catch (err) {
        console.warn('Could not sync spending to DB:', err);
      }
    }
    setEntries((prev) =>
      prev.map((item, idx) => {
        const key = item.id || idx;
        if (key === entryKey || (item.spendingProposal && item.spendingProposal.proposalId === proposal.proposalId)) {
          return { ...item, spendingProposalStatus: 'accepted' };
        }
        return item;
      })
    );
    window.dispatchEvent(new CustomEvent('medguard:spending-added', { detail: spend }));
    notify(`Đã lưu khoản chi ${Math.abs(spend.amount_vnd).toLocaleString('vi-VN')} ₫ vào Sổ chi tiêu y tế!`);
  };

  const handleDeclineSpendingProposal = (entryKey) => {
    setEntries((prev) =>
      prev.map((item, idx) => {
        const key = item.id || idx;
        if (key === entryKey) {
          return { ...item, spendingProposalStatus: 'declined' };
        }
        return item;
      })
    );
    notify('Đã bỏ qua khoản chi tiêu');
  };

  const handleOpenNavigationAction = (navData) => {
    setNavigationContext({
      destinationName: navData.poiName,
      category: navData.category,
      address: navData.address,
      coordinates: navData.coordinates,
    });
    setView('navigation');
    notify(`Đang mở chỉ đường đến ${navData.poiName}...`);
  };

  const clearProfile = async () => {
    if (account) {
      try { await api.request('/v1/auth/profile', { method: 'PUT', body: emptyProfile }); }
      catch (e) { notify(e.message); return; }
    }
    try {
      localStorage.removeItem(`medguard.profile.${tenantId}`);
      localStorage.removeItem('medguard_verified_patient_profile');
    } catch {
      // Keep the clear action functional for the current tab.
    }
    setContext(newContext());
    window.dispatchEvent(new CustomEvent('medguard:profile-updated', { detail: emptyProfile }));
    setPatientOpen(false);
    notify('Đã xóa Profile');
  };

  const selectConversation = async (id) => {
    try { sessionStorage.setItem('medguard_active_conversation_id', id); } catch {}
    setBusy(true);
    setView('chat');
    try {
      const data = await api.request(`/v1/chat/conversations/${encodeURIComponent(id)}`);
      if (data && data.conversation) {
        setConversationId(id);
        setConversationTitle(data.conversation.title || 'Cuộc trò chuyện');
        setContext((current) => ({ ...current, patient_ref: data.conversation.patient_ref || current.patient_ref }));
        setEntries((data.messages || []).map((item) => ({
          id: item.message_id,
          requestId: item.request_id,
          role: item.role,
          text: item.content,
          intent: item.intent,
          status: item.status,
          result: item.result,
          answer: item.answer,
          answer_origin: item.answer_origin,
          verification_status: item.verification_status,
          knowledge_approval: item.knowledge_approval
        })));
      } else {
        setConversationId(id);
        setConversationTitle('Cuộc trò chuyện');
        setEntries([]);
      }
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
    if (isGuest && guestRemaining <= 0) {
      notify('Bạn đã dùng hết 3 lượt hỏi dùng thử. Vui lòng đăng nhập để tiếp tục.');
      return;
    }
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

    const profileProposal = extractUserProfileProposal(shownText, context);
    const navCommand = detectConversationalNavigation(shownText);
    const medProposal = extractMedicationProposal(shownText);
    const apptProposal = extractAppointmentProposal(shownText, context);
    const spendProposal = extractSpendingProposal(shownText, context, currentAttachment);
    const navAction = extractNavigationAction(shownText);

    try {
      if (currentAttachment && isExplicitPrescriptionOcr) {
        const patientRef = context.patient_ref || shownText.match(/\b(?:BN|HS|P)[-_][A-Z0-9._-]+\b/i)?.[0]?.toUpperCase() || `BN-KHACH-${conversationId.slice(0, 6).toUpperCase()}`;
        const formData = new FormData();
        formData.append('image', currentAttachment.file);
        formData.append('patient_ref', patientRef);
        formData.append('conversation_id', conversationId);
        formData.append('message', shownText);
        const data = await api.request('/v1/prescription/extract', { method: 'POST', formData });
        let finalOcrData = data;
        if (data?.poll_url || data?.status === 'accepted' || data?.status === 'processing') {
          const pollUrl = data.poll_url || `/v1/jobs/${data.job_id}`;
          for (let attempt = 0; attempt < 12; attempt++) {
            await new Promise((res) => setTimeout(res, 1500));
            try {
              const pollRes = await api.request(pollUrl, { method: 'GET' });
              if (pollRes?.status === 'completed' || pollRes?.status === 'succeeded' || pollRes?.status === 'answered' || pollRes?.answer) {
                finalOcrData = pollRes;
                break;
              }
              if (pollRes?.status === 'failed' || pollRes?.status === 'error') {
                break;
              }
            } catch {
              break;
            }
          }
        }
        const { answer: ocrAnswer, ...ocrResult } = finalOcrData;
        responseEntry = { role: 'assistant', text: ocrAnswer?.summary || 'Đã tiếp nhận ảnh đơn thuốc. Kết quả nhận diện cần dược sĩ hoặc bác sĩ xác nhận trước khi tạo lịch thuốc.', intent: 'ocr', status: 'answered', result: ocrResult, answer: ocrAnswer };
        if (profileProposal && profileProposal.hasProposal) {
          responseEntry.profileProposal = profileProposal;
          responseEntry.profileProposalStatus = 'pending';
        }
        if (medProposal && medProposal.hasProposal) {
          responseEntry.medicationProposal = medProposal;
          responseEntry.medicationProposalStatus = 'pending';
        }
        if (spendProposal && spendProposal.hasProposal) {
          responseEntry.spendingProposal = spendProposal;
          if (autoSubmitUpdates) {
            responseEntry.spendingProposalStatus = 'accepted';
            handleAcceptSpendingProposal(spendProposal, responseEntry.id);
          } else {
            responseEntry.spendingProposalStatus = 'pending';
          }
        }
      } else {
        const messages = previous.filter((item) => item.role === 'user' || item.role === 'assistant').slice(-18).map((item) => ({ role: item.role, content: item.text }));
        messages.push({ role: 'user', content: shownText });
        const data = await api.request('/v1/chat', {
          method: 'POST',
          body: { conversation_id: conversationId, messages, context: clinicalContext(context, userLocation), intent_hint: effectiveIntent, locale: 'vi-VN' },
          timeoutMs: chatTimeoutMs || 35000,
        });
        let savedHealth = null;
        try {
          const raw = localStorage.getItem(getTwinKey(account));
          if (raw) savedHealth = JSON.parse(raw);
        } catch {}
        let savedFin = null;
        try {
          const raw = localStorage.getItem(getFinKey(account));
          if (raw) savedFin = JSON.parse(raw);
        } catch {}

        const syncResult = processUnifiedTopicGatedChat(shownText, {
          healthProfile: savedHealth,
          financialAssessment: savedFin,
        });

        responseEntry = {
          role: 'assistant',
          requestId: data.request_id,
          text: data.reply,
          intent: data.intent,
          status: data.status,
          result: data.result,
          answer: data.answer,
          suggestions: data.suggestions,
          answer_origin: data.answer_origin,
          verification_status: data.verification_status,
          knowledge_approval: data.knowledge_approval,
          topic_mode: syncResult.topicMode,
          topic_label: syncResult.label,
        };
        if (profileProposal && profileProposal.hasProposal) {
          responseEntry.profileProposal = profileProposal;
          if (autoSubmitUpdates) {
            responseEntry.profileProposalStatus = 'accepted';
            try {
              const rawProfile = localStorage.getItem('medguard_patient_demographics') || localStorage.getItem(`medguard.profile.${tenantId}`) || '{}';
              let baseProfile = {};
              try { baseProfile = JSON.parse(rawProfile); } catch {}
              const updates = profileProposal.fields || profileProposal.updates || {};
              const updated = { ...context, ...baseProfile, ...updates };
              setContext((prev) => ({ ...prev, ...updates }));
              localStorage.setItem('medguard_patient_demographics', JSON.stringify(updated));
              localStorage.setItem(`medguard.profile.${tenantId}`, JSON.stringify(updated));
            } catch (e) {
              console.warn('Auto-submit profile failed', e);
            }
          } else {
            responseEntry.profileProposalStatus = 'pending';
          }
        }
        if (medProposal && medProposal.hasProposal) {
          responseEntry.medicationProposal = medProposal;
          if (autoSubmitUpdates) {
            responseEntry.medicationProposalStatus = 'accepted';
            try {
              const med = medProposal.medication;
              const raw = localStorage.getItem('medguard.user_meds.data');
              let currentMeds = raw ? JSON.parse(raw) : [];
              currentMeds = [med, ...currentMeds.filter((m) => m.name.toLowerCase() !== med.name.toLowerCase())];
              localStorage.setItem('medguard.user_meds.data', JSON.stringify(currentMeds));
              window.dispatchEvent(new CustomEvent('medguard:medication-added', { detail: med }));
            } catch (e) {
              console.warn('Auto-submit medication failed', e);
            }
          } else {
            responseEntry.medicationProposalStatus = 'pending';
          }
        }
        if (apptProposal && apptProposal.hasProposal) {
          responseEntry.appointmentProposal = apptProposal;
          if (autoSubmitUpdates) {
            responseEntry.appointmentProposalStatus = 'accepted';
            try {
              const appt = apptProposal.appointment;
              const raw = localStorage.getItem('medguard.shifts.data');
              let currentShifts = raw ? JSON.parse(raw) : [];
              currentShifts = [appt, ...currentShifts.filter((s) => s.id !== appt.id)];
              localStorage.setItem('medguard.shifts.data', JSON.stringify(currentShifts));
              window.dispatchEvent(new CustomEvent('medguard:appointment-booked', { detail: appt }));
            } catch (e) {
              console.warn('Auto-submit appointment failed', e);
            }
          } else {
            responseEntry.appointmentProposalStatus = 'pending';
          }
        }
        if (spendProposal && spendProposal.hasProposal) {
          responseEntry.spendingProposal = spendProposal;
          if (autoSubmitUpdates) {
            responseEntry.spendingProposalStatus = 'accepted';
            handleAcceptSpendingProposal(spendProposal, responseEntry.id);
          } else {
            responseEntry.spendingProposalStatus = 'pending';
          }
        }
        if (navAction && navAction.hasAction) {
          responseEntry.navigationAction = navAction;
        }
        if (navCommand && navCommand.isNavCommand) {
          responseEntry.navCommand = navCommand;
          if (navCommand.targetView === 'settings') {
            setSettingsOpen(true);
          } else if (navCommand.targetView) {
            setView(navCommand.targetView);
            notify('success', `Đã chuyển sang ${navCommand.label}`);
          }
        }
        if (data.extracted?.patient_ref) setContext((current) => ({ ...current, patient_ref: data.extracted.patient_ref }));
        if (data.result) setContext((current) => ({ ...current, last_result: data.result }));
        if (
          data.required_fields?.includes('patient_ref') &&
          !medProposal?.hasProposal &&
          !apptProposal?.hasProposal &&
          !profileProposal?.hasProposal &&
          !navAction?.hasAction
        ) {
          setPatientOpen(true);
        }

        // Build ChatGPT-Style Action & Permission Proposal if data mutations were detected
        if (syncResult.healthMutation || syncResult.expenseMutation) {
          const isDual = !!(syncResult.healthMutation && syncResult.expenseMutation);
          const isHealth = !!syncResult.healthMutation && !syncResult.expenseMutation;

          const moduleType = isDual ? 'dual' : isHealth ? 'health_twin' : 'spending';
          const moduleTitle = isDual
            ? 'Bản đồ Cơ thể 3D & Sổ Chi Tiêu'
            : isHealth
            ? 'Bản đồ Cơ thể 3D'
            : 'Sổ Chi Tiêu & Quyền lợi BHYT';

          const extractedItems = [];

          if (syncResult.healthMutation) {
            const h = syncResult.healthMutation;
            let organName = h.detected_organ?.name || 'Não bộ & Thần kinh';
            let organStatus = h.detected_organ?.notes || 'Cần theo dõi và đánh giá lâm sàng';
            if (h.organs) {
              const keys = Object.keys(h.organs);
              for (const k of keys) {
                if (h.organs[k]?.status && h.organs[k].status !== 'normal') {
                  organName = h.organs[k].vietnamese_name || h.organs[k].name || (k === 'stomach' ? 'Dạ dày' : k);
                  organStatus = h.organs[k].clinical_notes || h.organs[k].status;
                  break;
                }
              }
            }
            extractedItems.push({
              icon: 'organ',
              label: 'Cơ quan cập nhật',
              value: organName,
              subHint: organStatus,
              tone: 'warning',
            });
            if (h.vitals?.vas_pain_score) {
              extractedItems.push({
                icon: 'pain',
                label: 'Mức độ đau nhức',
                value: `${h.vitals.vas_pain_score}/10 (${h.vitals.vas_pain_score >= 6 ? 'Đau dữ dội' : 'Đau vừa'})`,
                tone: 'danger',
              });
            }
            if (h.overall_health_score) {
              extractedItems.push({
                icon: 'shield',
                label: 'Điểm thể trạng',
                value: `${h.overall_health_score}/100`,
                tone: 'neutral',
              });
            }
          }

          if (syncResult.expenseMutation) {
            const exp = syncResult.expenseMutation;
            const recentTx = exp.recent_transactions?.[0];
            const validAmount = recentTx?.amount_vnd ? Math.abs(recentTx.amount_vnd) : null;
            if (recentTx && recentTx.id?.startsWith('tx_') && validAmount && validAmount > 0) {
              extractedItems.push({
                icon: 'money',
                label: 'Khoản chi y tế',
                value: `${validAmount.toLocaleString('vi-VN')} ₫`,
                subHint: recentTx?.title || 'Đơn thuốc / Khám chữa bệnh',
                tone: 'success',
              });
              extractedItems.push({
                icon: 'shield',
                label: 'Ước tính BHYT',
                value: 'BHYT chi trả ~80%',
                subHint: 'Theo danh mục BHYT đúng tuyến',
                tone: 'neutral',
              });
            } else if (exp.monthly_budget_target_vnd) {
              extractedItems.push({
                icon: 'money',
                label: 'Hạn mức ngân sách y tế',
                value: `${exp.monthly_budget_target_vnd.toLocaleString('vi-VN')} ₫`,
                subHint: 'Thiết lập hạn mức ngân sách tháng 10/2026',
                tone: 'success',
              });
              extractedItems.push({
                icon: 'shield',
                label: 'Cơ cấu phân bổ (45 - 35 - 20)',
                value: 'BHYT • Thuốc GPP • Dự phòng',
                subHint: 'Tối ưu hóa kinh tế y tế & Dược lâm sàng',
                tone: 'neutral',
              });
            }
          }

          const syncProposal = {
            moduleType,
            moduleTitle,
            summaryText: isDual
              ? 'Phát hiện dữ liệu lâm sàng về cơ thể và chi phí y tế. Cần sự cho phép của bạn để cập nhật cả 2 hệ thống:'
              : isHealth
              ? 'Phát hiện triệu chứng mới ảnh hưởng đến cơ thể. Cần sự cho phép của bạn để đồng bộ vào Bản đồ Cơ thể 3D:'
              : 'Phát hiện thông tin chi phí y tế / đơn thuốc. Cần sự cho phép của bạn để ghi nhận vào Sổ Chi Tiêu:',
            extractedItems,
            healthMutation: syncResult.healthMutation,
            expenseMutation: syncResult.expenseMutation,
          };

          responseEntry.syncProposal = syncProposal;

          if (autoSubmitUpdates) {
            // User enabled auto-submit: apply immediately
            if (syncResult.healthMutation) {
              try {
                localStorage.setItem(getTwinKey(account), JSON.stringify(syncResult.healthMutation));
              } catch {}
              window.dispatchEvent(new CustomEvent('medguard:health-twin-updated', { detail: { ...data, healthMutation: syncResult.healthMutation } }));
            }
            if (syncResult.expenseMutation) {
              try {
                localStorage.setItem(getFinKey(account), JSON.stringify(syncResult.expenseMutation));
                if (syncResult.expenseMutation.monthly_budget_target_vnd) {
                  const budgetKey = account ? `medguard_budget_target_vnd_${account.user_id || account.id || account.email}` : 'medguard_budget_target_vnd';
                  localStorage.setItem(budgetKey, String(syncResult.expenseMutation.monthly_budget_target_vnd));
                }
              } catch {}
              window.dispatchEvent(new CustomEvent('medguard:financial-updated', { detail: { ...data, expenseMutation: syncResult.expenseMutation } }));
            }
            responseEntry.syncProposalStatus = 'accepted';
            window.dispatchEvent(new CustomEvent('medguard:unified-chat-sync', { detail: syncResult }));
          } else {
            // Require user explicit permission
            responseEntry.syncProposalStatus = 'pending';
          }
        } else {
          // UNRELATED_NO_STATE_MUTATION: 100% metrics in both modules strictly preserved!
          window.dispatchEvent(new CustomEvent('medguard:unified-chat-sync', { detail: syncResult }));
        }
      }
      if (refreshHistory) void loadConversations();
    } catch (error) {
      responseEntry = { role: 'error', error };
    } finally {
      const remaining = 350 - (performance.now() - processingStartedAt);
      if (remaining > 0) await new Promise((resolve) => window.setTimeout(resolve, remaining));
      if (responseEntry) {
        setEntries((current) => [...current, responseEntry]);
        if (responseEntry.role !== 'error' && isGuest && onGuestQuestionAsked) {
          onGuestQuestionAsked();
        }
        if (responseEntry.role !== 'error' && autoSpeak && 'speechSynthesis' in window) {
          const textToRead = responseEntry.answer?.summary || responseEntry.text || '';
          if (textToRead) {
            window.speechSynthesis.cancel();
            const cleanText = textToRead.replace(/[#*`_]/g, '');
            const utter = new SpeechSynthesisUtterance(cleanText);
            utter.lang = 'vi-VN';
            utter.rate = 1.0;
            const key = responseEntry.id || Date.now();
            utter.onend = () => {
              setSpeakingKey(null);
              setSpeakingText(null);
            };
            utter.onerror = () => {
              setSpeakingKey(null);
              setSpeakingText(null);
            };
            setSpeakingKey(key);
            setSpeakingText(cleanText);
            window.speechSynthesis.speak(utter);
          }
        }
      }
      setBusy(false);
    }
  };

  const filteredConversations = conversations.filter((item) => item.title.toLowerCase().includes(historySearch.toLowerCase()));
  return <div className={`app-shell chat-shell ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
    <Sidebar
      open={sidebarOpen}
      close={() => setSidebarOpen(false)}
      collapse={() => { setSidebarCollapsed(true); setSidebarOpen(false); }}
      conversations={filteredConversations}
      activeId={conversationId}
      onSelect={selectConversation}
      onNew={startNew}
      onDelete={deleteConversation}
      onSchedule={() => setView('medication')}
      onSchedulePage={() => setView('schedule')}
      onMedicationPage={() => setView('medication')}
      onCompanionPage={() => setView('companion')}
      onNavigationPage={() => setView('navigation')}
      onHealthPage={() => setView('health')}
      onSpendingPage={() => setView('spending')}
      onProfilePage={() => setView('profile')}
      onSettings={() => { setSettingsInitialTab('general'); setSettingsOpen(true); }}
      onSystem={() => { if (!account || account.role === 'admin') setView('system'); }}
      activeView={view}
      search={historySearch}
      setSearch={setHistorySearch}
      isGuest={isGuest || !account}
      context={context}
      account={account}
      onOpenProfile={() => setView('profile')}
      onRequireAuth={onRequireAuth}
      onLogout={onLogout}
    />
    <main className="main-shell chat-main" id="main-content" tabIndex={-1}>
      <header className="topbar chat-topbar">
        <div className="topbar-title">
          <button
            className="icon-button menu-button"
            type="button"
            onClick={() => { setSidebarCollapsed(false); setSidebarOpen(true); }}
            title={sidebarCollapsed ? 'Mở thanh bên' : 'Mở menu'}
            aria-label={sidebarCollapsed ? 'Mở thanh bên' : 'Mở menu'}
          >
            {sidebarCollapsed ? <PanelLeftOpen size={20} /> : <Menu size={20} />}
          </button>
          <div>
            <h1>{view === 'system' ? 'Hệ thống & Kiểm toán' : view === 'spending' ? 'Chi Tiêu Y Tế & Tiết Kiệm Care' : view === 'schedule' ? 'Lịch khám bệnh' : view === 'medication' ? 'Lịch uống thuốc' : view === 'companion' ? 'Bác sĩ 3D Live' : view === 'navigation' ? 'Bản đồ Cấp cứu, Tìm Thuốc & Google Places' : view === 'profile' ? 'Hồ Sơ Y Tế & Bảo Hiểm' : conversationTitle}</h1>
            <span>{view === 'system' ? 'Trạng thái vận hành lâm sàng' : view === 'spending' ? 'Tối ưu hóa kinh tế y khoa, thuốc chuẩn GPP & Booking Care' : view === 'schedule' ? 'Thời khóa biểu ca khám bác sĩ' : view === 'medication' ? 'Thời khóa biểu nhắc thuốc cá nhân' : view === 'companion' ? 'Bác sĩ ảo 3D tư vấn trực tiếp qua giọng nói & cử chỉ' : view === 'navigation' ? 'Google Maps Places API Reputation • Cổng Cấp cứu A9 Bạch Mai • Dẫn đường 2 giai đoạn' : view === 'profile' ? 'Quản lý thông tin cá nhân, thể trạng, BHYT, BHXH & tiền sử bệnh' : (context.display_name ? `Bệnh nhân: ${context.display_name}` : context.patient_ref || 'Hỗ trợ y khoa 24/7')}</span>
          </div>
        </div>
        <div className="topbar-actions">
          {isGuest && (
            <div className="guest-topbar-indicator" title="Chế độ khách dùng thử">
              <span className={`guest-indicator-dot ${guestRemaining > 0 ? 'active' : 'exhausted'}`} />
              <span>Khách: <strong>{guestRemaining}/{guestMax}</strong> lượt</span>
              <button type="button" className="guest-topbar-btn" onClick={onRequireAuth}>
                Đăng nhập
              </button>
            </div>
          )}


          <div className="topbar-active-context">
            <span className="topbar-active-badge">Phân hệ:</span>
            <strong className="topbar-active-title">
              {WORKSPACE_ROUTE_POLICIES[view]?.label || 'Hội thoại'}
            </strong>
            {view !== 'chat' && (
              <button
                type="button"
                className="topbar-return-chat-btn"
                onClick={() => setView('chat')}
                title="Quay lại Phòng Hội Thoại"
              >
                <ArrowLeft size={12} />
                <span>Về Chat</span>
              </button>
            )}
          </div>

          {view !== 'navigation' && (
            <div className="location-anchor">
              <button
                className={`location-topbar-pill ${userLocation.is_gps ? 'gps-active' : ''}`}
                type="button"
                aria-label="Cài đặt vị trí & chỉ đường"
                onClick={() => setLocationPromptOpen(!locationPromptOpen)}
                title={`Vị trí: ${userLocation.name} (${userLocation.address})`}
              >
                <MapPin size={14} className="location-pin-icon" />
                <div className="location-pill-text">
                  <strong>{userLocation.name || 'Vị trí'}</strong>
                  <small>{userLocation.city === 'hanoi' ? 'Hà Nội' : userLocation.city === 'hcm' ? 'TP.HCM' : 'Đà Nẵng'}</small>
                </div>
                <ChevronDown size={13} className="location-chevron" />
              </button>
              {locationPromptOpen && (
                <div className="location-popover" role="dialog" aria-label="Định vị & Chỉ đường">
                  <div className="location-popover-header">
                    <div className="loc-title-row">
                      <LocateFixed size={16} />
                      <strong>Vị trí & Chỉ đường Real-time</strong>
                    </div>
                    <p>Hệ thống tự động quét quầy thuốc GPP và vẽ lộ trình thời gian thực quanh điểm này.</p>
                  </div>

                  <div className="location-current-status">
                    <div className="current-status-badge">
                      <span className={`status-dot ${userLocation.is_gps ? 'gps' : 'preset'}`} />
                      <span>{userLocation.is_gps ? 'GPS Trực tiếp (Chính xác)' : 'Địa điểm chỉ định'}</span>
                    </div>
                    <p className="current-address-text">{userLocation.address}</p>
                    <span className="current-coords">Tọa độ: {userLocation.lat.toFixed(4)}, {userLocation.lng.toFixed(4)}</span>
                  </div>

                  {userLocation.permission_status === 'denied' && (
                    <div className="location-denied-alert">
                      <AlertTriangle size={15} />
                      <span>Trình duyệt đang chặn quyền vị trí. Vui lòng cấp quyền trong cài đặt trình duyệt hoặc chọn cơ sở bên dưới.</span>
                    </div>
                  )}

                  <button
                    type="button"
                    className="gps-acquire-btn"
                    disabled={requestingGps}
                    onClick={handleRequestGps}
                  >
                    {requestingGps ? (
                      <>
                        <LoaderCircle size={15} className="spin" />
                        <span>Đang xin quyền & lấy GPS...</span>
                      </>
                    ) : (
                      <>
                        <LocateFixed size={15} />
                        <span>Cấp quyền & Lấy vị trí GPS của tôi</span>
                      </>
                    )}
                  </button>

                  <div className="location-divider"><span>HOẶC CHỌN KHU VỰC SẴN CÓ</span></div>

                  <div className="location-presets-list">
                    {LOCATION_PRESETS.map((p) => {
                      const isSelected = !userLocation.is_gps && userLocation.name === p.name;
                      return (
                        <button
                          key={p.id}
                          type="button"
                          className={`preset-item-btn ${isSelected ? 'selected' : ''}`}
                          onClick={() => handleSelectPreset(p)}
                        >
                          <div className="preset-item-icon">
                            <MapPin size={14} />
                          </div>
                          <div className="preset-item-info">
                            <strong>{p.name}</strong>
                            <span>{p.address}</span>
                          </div>
                          {isSelected && <Check size={14} className="preset-check" />}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}

          {view === 'chat' && (
            <div className="profile-anchor">
              <button
                className={`patient-button ${context.patient_ref || context.display_name ? 'selected' : ''}`}
                type="button"
                aria-label="Mở Profile cá nhân"
                onClick={() => setView('profile')}
              >
                <span>{context.display_name ? context.display_name.trim().slice(0, 2).toUpperCase() : context.patient_ref ? context.patient_ref.slice(0, 2) : <UserRound size={15} />}</span>
                <div>
                  <strong>{context.display_name || 'Hồ sơ bệnh nhân'}</strong>
                  <small>{context.bhyt_number ? `BHYT: ${context.bhyt_number.slice(0, 8)}...` : context.patient_ref || 'Chưa liên kết BHYT'}</small>
                </div>
                <ChevronDown size={14} />
              </button>
            </div>
          )}

          <button
            className="readiness-button"
            type="button"
            title="Trạng thái hệ thống"
            onClick={() => { setSettingsInitialTab(account?.role === 'patient' ? 'general' : 'system'); setSettingsOpen(true); }}
          >
            <span className={`health-dot ${readiness?.production_ready ? 'ready' : (readiness?.environment === 'development' ? 'dev-ready' : '')}`} />
            {readiness?.production_ready ? 'Ready' : (readiness?.environment === 'development' ? 'Online (Dev)' : (readiness?.status || 'offline'))}
          </button>

          <button
            className="icon-button topbar-settings-btn"
            type="button"
            title="Cài đặt hệ thống"
            aria-label="Cài đặt"
            onClick={() => { setSettingsInitialTab('general'); setSettingsOpen(true); }}
          >
            <Settings size={18} />
          </button>

          {account && (
            <div className="account-anchor">
              <button
                className="account-topbar-pill"
                type="button"
                title="Tài khoản & bảo mật"
                onClick={() => setAccountMenuOpen(!accountMenuOpen)}
              >
                <span className="account-avatar-badge">{(account.email || 'U').slice(0, 2).toUpperCase()}</span>
                <div className="account-pill-text">
                  <strong>{account.email.split('@')[0]}</strong>
                  <small>{account.mfa_enabled ? 'MFA Bật' : 'Tài khoản'}</small>
                </div>
                <ChevronDown size={13} className="account-chevron" />
              </button>
              {accountMenuOpen && (
                <div className="account-popover">
                  <div className="account-popover-user">
                    <strong>{account.email}</strong>
                    <span>{account.mfa_enabled ? 'Bảo mật 2 lớp: ĐÃ BẬT' : 'Chưa kích hoạt MFA'}</span>
                  </div>
                  <div className="account-popover-divider" />
                  <button
                    type="button"
                    className="account-popover-item"
                    onClick={() => {
                      setAccountMenuOpen(false);
                      onManageAccount?.();
                    }}
                  >
                    <Shield size={15} />
                    <span>Tài khoản & bảo mật</span>
                  </button>
                  <button
                    type="button"
                    className="account-popover-item danger"
                    onClick={() => {
                      setAccountMenuOpen(false);
                      onLogout?.();
                    }}
                  >
                    <LogOut size={15} />
                    <span>Đăng xuất</span>
                  </button>
                </div>
              )}
            </div>
          )}

          {!account && !isGuest && (
            <div className="credentials-anchor">
              <button
                className="tenant-button"
                type="button"
                title="Cấu hình kết nối"
                aria-label="Cấu hình kết nối"
                onClick={() => setCredentialsOpen(!credentialsOpen)}
              >
                <span>{tenantId.slice(0, 1).toUpperCase()}</span>
                <div>
                  <strong>{tenantId}</strong>
                  <small>{readiness?.environment || 'Environment'}</small>
                </div>
                <Settings2 size={16} />
              </button>
              {credentialsOpen && <Credentials tenantId={tenantId} setTenantId={setTenantId} apiKey={apiKey} setApiKey={setApiKey} consentToken={consentToken} setConsentToken={setConsentToken} close={() => setCredentialsOpen(false)} />}
            </div>
          )}
        </div>
      </header>
      {view === 'system' ? (
        account?.role === 'admin' ? (
          <div className="system-workspace"><SystemModule api={api} tenantId={tenantId} /></div>
        ) : (
          <DataManagementAuthGate
            moduleTitle="Hệ Thống & Kiểm Toán Lâm Sàng dành cho Quản Trị Viên"
            moduleType="profile"
            onRequireAuth={onRequireAuth}
            onBackToChat={() => setView('chat')}
          />
        )
      ) : view === 'schedule' ? (
        <div className="schedule-workspace">
          {(isGuest || !account) ? (
            <DataManagementAuthGate
              moduleTitle="Quản Lý Lịch Khám Bác Sĩ & Đặt Hẹn Chuyên Khoa"
              moduleType="schedule"
              onRequireAuth={onRequireAuth}
              onBackToChat={() => setView('chat')}
            />
          ) : (
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
          )}
        </div>
      ) : view === 'medication' ? (
        <div className="schedule-workspace">
          {(isGuest || !account) ? (
            <DataManagementAuthGate
              moduleTitle="Quản Lý Lịch Uống Thuốc & Kiểm Soát Tương Tác Dược"
              moduleType="medication"
              onRequireAuth={onRequireAuth}
              onBackToChat={() => setView('chat')}
            />
          ) : (
            <MedicationPage
              api={api}
              patientRef={context.patient_ref}
              onBackToChat={() => setView('chat')}
              onOpenSchedulePage={() => setView('schedule')}
              onConsultMedicine={(med) => {
                setView('chat');
                setMessage(`Tư vấn thông tin và lưu ý dùng thuốc ${med.name || med.medicine_name} (${med.strength || med.dosage || ''}), dùng vào: ${med.timing || med.slot || 'trong ngày'}.`);
                requestAnimationFrame(() => document.querySelector('[aria-label="Tin nhắn"]')?.focus());
              }}
              onNotify={notify}
            />
          )}
        </div>
      ) : view === 'health' ? (
        <div className="health-workspace-container">
          <ErrorBoundary title="Mô-đun Cơ thể & Sức khoẻ Thời gian thực" onBackToChat={() => setView('chat')}>
            {(isGuest || !account) ? (
              <DataManagementAuthGate
                moduleTitle="Hồ Sơ Cơ Thể & Thống Kê Sức Khoẻ Đa Biểu Đồ"
                moduleType="health"
                onRequireAuth={onRequireAuth}
                onBackToChat={() => setView('chat')}
              />
            ) : (
              <HealthTwinPage
                api={api}
                account={account}
                isGuest={isGuest}
                onRequireAuth={onRequireAuth}
                onBackToChat={() => setView('chat')}
                onNavigate={(target) => setView(target)}
                onNotify={notify}
              />
            )}
          </ErrorBoundary>
        </div>
      ) : view === 'spending' ? (
        <div className="health-workspace-container">
          <ErrorBoundary title="Mô-đun Đánh giá Chi Tiêu Y Tế & Tiết Kiệm Care" onBackToChat={() => setView('chat')}>
            {(isGuest || !account) ? (
              <DataManagementAuthGate
                moduleTitle="Quản Trị Chi Phí Y Tế, BHYT & Lộ Trình Tiết Kiệm Care"
                moduleType="spending"
                onRequireAuth={onRequireAuth}
                onBackToChat={() => setView('chat')}
              />
            ) : (
              <HealthcareSpendingPage
                api={api}
                account={account}
                isGuest={isGuest}
                onRequireAuth={onRequireAuth}
                patientRef={context.patient_ref}
                onBackToChat={() => setView('chat')}
                onNavigate={(target) => setView(target)}
                onNotify={notify}
              />
            )}
          </ErrorBoundary>
        </div>
      ) : view === 'companion' ? (
        <GrokLiveCompanionPage
          api={api}
          context={context}
          onBackToChat={() => setView('chat')}
          onNotify={notify}
        />
      ) : view === 'navigation' ? (
        <NavigationPage
          api={api}
          userLocation={userLocation}
          onUpdateLocation={(loc) => {
            setUserLocation(loc);
            saveUserLocation(loc);
          }}
          navigationContext={navigationContext}
          onBackToChat={() => setView('chat')}
          onNotify={notify}
        />
      ) : view === 'profile' ? (
        <ErrorBoundary title="Hồ Sơ Y Tế & Xác Thực Bảo Hiểm" onBackToChat={() => setView('chat')}>
          {(isGuest || !account) ? (
            <DataManagementAuthGate
              moduleTitle="Hồ Sơ Định Danh Bệnh Nhân & Thẻ BHYT"
              moduleType="profile"
              onRequireAuth={onRequireAuth}
              onBackToChat={() => setView('chat')}
            />
          ) : (
            <UserProfilePage
              context={context}
              account={account}
              onSave={saveProfile}
              onClear={clearProfile}
              onBackToChat={() => setView('chat')}
              onNotify={notify}
            />
          )}
        </ErrorBoundary>
      ) : (
        <section id="main-chat-workspace" className={`chat-workspace ${entries.length ? 'has-messages' : ''}`} aria-live="polite">
          <div className="location-context-bar">
            <div className="loc-context-info">
              <span className={`loc-status-indicator ${userLocation.is_gps ? 'gps-live' : 'preset-fixed'}`} />
              <MapPin size={13} className="loc-bar-icon" />
              <span className="loc-bar-label">Vị trí của bạn:</span>
              <strong className="loc-bar-name">{userLocation.name}</strong>
              <span className="loc-bar-addr">— {userLocation.address}</span>
            </div>
            <div className="loc-bar-actions" style={{ display: 'flex', gap: '8px' }}>
              <button
                type="button"
                className="loc-context-change-btn"
                onClick={() => setView('navigation')}
                title="Mở trang chỉ đường Real-time toàn màn hình"
                style={{ borderColor: '#bae6fd', color: '#0284c7', background: '#f0f9ff' }}
              >
                <Route size={12} />
                <span>Bản đồ Chỉ đường</span>
              </button>
              <button
                type="button"
                className="loc-context-change-btn"
                onClick={() => setLocationPromptOpen(true)}
              >
                <LocateFixed size={12} />
                <span>{userLocation.is_gps ? 'GPS đang bật' : 'Cấp quyền GPS / Đổi vị trí'}</span>
              </button>
            </div>
          </div>
          <div className="chat-scroll">
            {entries.length ? (
              <Conversation
                entries={entries}
                busy={busy}
                onNotify={notify}
                onSelectQuestion={(q) => sendText(q)}
                speakingKey={speakingKey}
                setSpeakingKey={setSpeakingKey}
                setSpeakingText={setSpeakingText}
                onAcceptProfileProposal={handleAcceptProfileProposal}
                onDeclineProfileProposal={handleDeclineProfileProposal}
                onOpenProfile={() => setView('profile')}
                onAcceptMedicationProposal={handleAcceptMedicationProposal}
                onDeclineMedicationProposal={handleDeclineMedicationProposal}
                onAcceptAppointmentProposal={handleAcceptAppointmentProposal}
                onDeclineAppointmentProposal={handleDeclineAppointmentProposal}
                onAcceptSpendingProposal={handleAcceptSpendingProposal}
                onDeclineSpendingProposal={handleDeclineSpendingProposal}
                onAcceptSyncProposal={handleAcceptSyncProposal}
                onDeclineSyncProposal={handleDeclineSyncProposal}
                autoSubmitUpdates={autoSubmitUpdates}
                onToggleAutoSubmit={(val) => {
                  setAutoSubmitUpdates(val);
                  try {
                    localStorage.setItem('medguard_auto_apply_sync_updates', String(val));
                  } catch {}
                }}
                onOpenNavigation={handleOpenNavigationAction}
                onNavigate={(target) => {
                  if (target === 'profile') setView('profile');
                  else if (target === 'settings') setSettingsOpen(true);
                  else setView(target);
                }}
              />
            ) : (
              <Welcome
                onPrompt={(text) => {
                  setMessage(text);
                  requestAnimationFrame(() => document.querySelector('[aria-label="Tin nhắn"]')?.focus());
                }}
              />
            )}
          </div>
          <Composer
            value={message}
            setValue={setMessage}
            onSend={() => sendText()}
            busy={busy}
            selectedTool={selectedTool}
            setSelectedTool={setSelectedTool}
            attachment={attachment}
            setAttachment={setAttachment}
            onQr={() => setQrOpen(true)}
            isGuestLocked={isGuestLocked}
            guestMax={guestMax}
            onRequireAuth={onRequireAuth}
          />
        </section>
      )}
    </main>
    <QrScanner open={qrOpen} onClose={() => setQrOpen(false)} onDetected={(raw) => { setQrOpen(false); sendText(`Kiểm tra QR hàng giả: ${raw}`, 'authenticity'); }} />
    <SchedulePanel open={scheduleOpen} onClose={() => setScheduleOpen(false)} api={api} patientRef={context.patient_ref} onOpenSchedulePage={() => setView('schedule')} onNotify={notify} />
    <SettingsModal allowSystem={Boolean(account && account.role === 'admin')} open={settingsOpen} onClose={() => setSettingsOpen(false)} initialTab={settingsInitialTab} context={context} onSaveProfile={saveProfile} onClearProfile={clearProfile} api={api} tenantId={tenantId} onClearAllChat={clearAllConversations} onExportData={exportClinicalData} onNotify={notify} />
    <PatientProfileModal open={patientOpen} context={context} onSave={saveProfile} onClear={clearProfile} onClose={() => setPatientOpen(false)} />
    {toast && <div className="ui-toast" role="status" aria-live="polite" aria-atomic="true"><Check size={16} /><span>{typeof toast === 'string' ? toast : toast?.message || String(toast)}</span></div>}
  </div>;
}
