import { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock,
  Droplet,
  Eye,
  FileText,
  Flame,
  Heart,
  HeartPulse,
  Info,
  Pill,
  Plus,
  RefreshCw,
  RotateCcw,
  Send,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  Thermometer,
  TrendingDown,
  TrendingUp,
  User,
  X,
  Zap,
} from 'lucide-react';
import './HealthTwinPage.css';

const SCENARIOS = [
  {
    id: 'initial_flu',
    label: 'Khởi phát cúm (Sốt, đau đầu)',
    icon: Flame,
    color: '#f59e0b',
    desc: 'Bệnh nhân bắt đầu cảm cúm, đau đầu, sổ mũi, rát họng',
  },
  {
    id: 'recovered_headache',
    label: 'Hồi phục (Hết đau đầu, sổ mũi)',
    icon: CheckCircle2,
    color: '#10b981',
    desc: 'Triệu chứng thuyên giảm, hết sốt, khuyên ngừng Paracetamol',
  },
  {
    id: 'adr_stomach_nsaid',
    label: 'Tác dụng phụ: Đau dạ dày do thuốc',
    icon: ShieldAlert,
    color: '#ef4444',
    desc: 'Uống thuốc bị đau dạ dày dữ dội, AI ra lệnh dừng cách cũ!',
  },
  {
    id: 'severe_fever_progression',
    label: 'Tiến triển nặng: Sốt cao 39.5°C',
    icon: AlertTriangle,
    color: '#dc2626',
    desc: 'Sốt cao kịch phát, khó thở, báo động đến bệnh viện',
  },
  {
    id: 'healthy_baseline',
    label: 'Thể trạng bình thường (Khỏe mạnh)',
    icon: Sparkles,
    color: '#00e5ff',
    desc: 'Tất cả cơ quan hoạt động tối ưu, không có bệnh lý',
  },
];

export function HealthTwinPage({ api, onBackToChat, onNavigate, onNotify }) {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [selectedOrganId, setSelectedOrganId] = useState('stomach');
  const [hoveredOrganId, setHoveredOrganId] = useState(null);
  const [inputMessage, setInputMessage] = useState('');
  const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'timeline' | 'meds'
  const [actionNotice, setActionNotice] = useState(null);

  // Load initial health profile
  const fetchProfile = async () => {
    try {
      setLoading(true);
      const data = await api.request('/v1/health-twin/profile');
      setProfile(data);
    } catch (err) {
      console.error('Failed to load health profile:', err);
      onNotify?.({ kind: 'error', message: 'Không thể tải hồ sơ sức khoẻ bệnh nhân.' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, []);

  // Quick scenario switcher
  const handleSwitchScenario = async (scenarioId) => {
    try {
      setLoading(true);
      const updated = await api.request('/v1/health-twin/scenario', {
        method: 'POST',
        body: { scenario_id: scenarioId },
      });
      setProfile(updated);
      const sc = SCENARIOS.find((s) => s.id === scenarioId);
      setActionNotice(`Đã chuyển kịch bản: ${sc?.label}`);
      setTimeout(() => setActionNotice(null), 4000);
    } catch (err) {
      console.error('Failed to switch scenario:', err);
      onNotify?.({ kind: 'error', message: 'Lỗi chuyển đổi kịch bản.' });
    } finally {
      setLoading(false);
    }
  };

  // Submit patient progress message (e.g. "hôm nay tôi đã hết đau đầu sổ mũi" or "uống thuốc vào bị đau dạ dày")
  const handleEvaluateProgress = async (textToEvaluate) => {
    const text = textToEvaluate || inputMessage;
    if (!text || !text.trim()) return;

    try {
      setEvaluating(true);
      const res = await api.request('/v1/health-twin/evaluate-symptom-update', {
        method: 'POST',
        body: { message: text },
      });
      setProfile(res.profile);
      setInputMessage('');

      if (res.must_discontinue_previous) {
        onNotify?.({
          kind: 'warning',
          message: 'AI PHÁT HIỆN TÁC DỤNG PHỤ: Đã kích hoạt lệnh dừng ngay thuốc cũ gây hại!',
        });
      } else if (res.detected_event === 'recovery') {
        onNotify?.({
          kind: 'success',
          message: 'Ghi nhận hồi phục tích cực: Đã cập nhật trạng thái cơ thể khoẻ mạnh.',
        });
      } else {
        onNotify?.({ kind: 'info', message: 'Đã cập nhật diễn tiến sức khoẻ vào hồ sơ.' });
      }
    } catch (err) {
      console.error('Failed to evaluate symptom update:', err);
      onNotify?.({ kind: 'error', message: 'Không thể phân tích diễn tiến sức khoẻ.' });
    } finally {
      setEvaluating(false);
    }
  };

  const activeOrgan = useMemo(() => {
    if (!profile?.organs) return null;
    const targetId = hoveredOrganId || selectedOrganId;
    return profile.organs.find((o) => o.id === targetId) || profile.organs[0];
  }, [profile, selectedOrganId, hoveredOrganId]);

  const getStatusColor = (status, score) => {
    if (status === 'adverse_reaction' || status === 'critical') return '#ef4444';
    if (status === 'inflamed') return '#f97316';
    if (status === 'monitoring') return '#eab308';
    if (score < 50) return '#ef4444';
    if (score < 80) return '#f59e0b';
    return '#10b981';
  };

  const getStatusBadgeText = (status) => {
    switch (status) {
      case 'adverse_reaction':
        return 'TÁC DỤNG PHỤ (ADR)';
      case 'critical':
        return 'BÁO ĐỘNG ĐỎ';
      case 'inflamed':
        return 'ĐANG VIÊM / TỔN THƯƠNG';
      case 'monitoring':
        return 'ĐANG THEO DÕI';
      default:
        return 'ỔN ĐỊNH / BÌNH THƯỜNG';
    }
  };

  return (
    <div className="health-twin-container" role="main" aria-label="Bản đồ Cơ thể & Sức khoẻ Thời gian thực">
      {/* Top Banner & Header */}
      <header className="health-twin-topbar">
        <div className="topbar-left">
          <button
            type="button"
            className="back-btn"
            onClick={onBackToChat}
            title="Quay lại phòng chat hội thoại"
          >
            <ArrowLeft size={16} />
            <span>Quay lại Chat</span>
          </button>
          <div className="twin-title-group">
            <div className="twin-brand-badge">
              <Activity size={18} className="twin-pulse-icon" />
              <h1>Anatomical Health Twin</h1>
              <span className="live-tag">REAL-TIME</span>
            </div>
            <p className="twin-subtitle">
              Chuẩn đoán & Theo dõi Diễn tiến Sức khoẻ Giải phẫu học — Cảnh báo An toàn & Điều chỉnh Phác đồ AI
            </p>
          </div>
        </div>

        <div className="topbar-right">
          <div className="patient-meta-pill">
            <User size={14} />
            <strong>{profile?.patient_name || 'Bệnh nhân'}</strong>
            <span className="meta-sep">•</span>
            <span>{profile?.age || 34} tuổi</span>
            <span className="meta-sep">•</span>
            <span>{profile?.gender || 'Nam'}</span>
          </div>

          <button
            type="button"
            className="refresh-btn"
            onClick={fetchProfile}
            disabled={loading}
            title="Tải lại dữ liệu"
          >
            <RefreshCw size={14} className={loading ? 'spinning' : ''} />
          </button>
        </div>
      </header>

      {/* Action Notification Toast */}
      {actionNotice && (
        <div className="health-action-toast">
          <Sparkles size={16} />
          <span>{actionNotice}</span>
        </div>
      )}

      {/* Clinical Scenario Quick Bar */}
      <section className="scenario-quick-bar" aria-label="Bộ chọn kịch bản lâm sàng mẫu">
        <div className="scenario-bar-title">
          <Stethoscope size={15} />
          <span>Thử nghiệm diễn tiến lâm sàng nhanh:</span>
        </div>
        <div className="scenario-chips-row">
          {SCENARIOS.map((sc) => {
            const Icon = sc.icon;
            return (
              <button
                key={sc.id}
                type="button"
                className="scenario-chip-btn"
                style={{ '--sc-color': sc.color }}
                onClick={() => handleSwitchScenario(sc.id)}
                title={sc.desc}
              >
                <Icon size={14} />
                <span>{sc.label}</span>
              </button>
            );
          })}
        </div>
      </section>

      {/* AI Safe Guardrail Alert Banner (If Harmful Medication Detected) */}
      {profile?.safe_guardrail_alert && (
        <section className={`guardrail-alert-banner level-${profile.safe_guardrail_alert.alert_level}`}>
          <div className="alert-banner-header">
            <div className="alert-title-wrap">
              <ShieldAlert size={22} className="alert-beacon-icon" />
              <div>
                <h2>{profile.safe_guardrail_alert.title}</h2>
                <span className="alert-cause">Nguyên nhân: {profile.safe_guardrail_alert.cause_identified}</span>
              </div>
            </div>
            {profile.safe_guardrail_alert.seek_emergency && (
              <button
                type="button"
                className="alert-emergency-nav-btn"
                onClick={() => {
                  window.dispatchEvent(
                    new CustomEvent('medguard:navigate', {
                      detail: { view: 'navigation' },
                    })
                  );
                }}
              >
                <AlertTriangle size={15} />
                <span>CHỈ ĐƯỜNG ĐẾN CƠ SỞ CẤP CỨU GẦN NHẤT</span>
              </button>
            )}
          </div>

          <div className="guardrail-grid">
            <div className="guardrail-col stop-col">
              <div className="col-label">
                <X size={15} />
                <strong>CHỈ THỊ: DỪNG CÁCH CŨ GÂY HẠI</strong>
              </div>
              <p className="col-desc highlight-stop">{profile.safe_guardrail_alert.required_action}</p>
              <div className="contra-badge">
                <span>Chống chỉ định:</span>
                <strong>{profile.safe_guardrail_alert.contraindicated_item}</strong>
              </div>
            </div>

            <div className="guardrail-col alt-col">
              <div className="col-label">
                <ShieldCheck size={15} />
                <strong>PHƯƠNG ÁN AN TOÀN THAY THẾ</strong>
              </div>
              <p className="col-desc">{profile.safe_guardrail_alert.alternative_recommendation}</p>
            </div>
          </div>
        </section>
      )}

      {/* Main Interactive Twin Workspace */}
      <div className="twin-main-grid">
        {/* Left Column: Interactive Human Body Anatomical Silhouette */}
        <section className="body-silhouette-card" aria-label="Sơ đồ Giải phẫu Cơ thể">
          <div className="silhouette-header">
            <div className="header-badge">
              <HeartPulse size={16} />
              <span>Sơ đồ Giải phẫu Số (Digital Twin)</span>
            </div>
            <span className="hint-pill">Rê chuột hoặc nhấp để xem chi tiết cơ quan</span>
          </div>

          <div className="human-canvas-wrapper">
            {/* Ambient Hologram Grid Background */}
            <div className="hologram-grid-bg" />
            <div className="hologram-scan-bar" />

            {/* SVG Anatomical Human Silhouette */}
            <svg
              className="human-svg-body"
              viewBox="0 0 320 540"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <defs>
                <linearGradient id="bodyGlowGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#00e5ff" stopOpacity="0.25" />
                  <stop offset="50%" stopColor="#3b82f6" stopOpacity="0.15" />
                  <stop offset="100%" stopColor="#1e1b4b" stopOpacity="0.08" />
                </linearGradient>
                <radialGradient id="organGlow" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="#00e5ff" stopOpacity="0.8" />
                  <stop offset="100%" stopColor="#00e5ff" stopOpacity="0" />
                </radialGradient>
                <filter id="neonGlowFilter" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="3" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
              </defs>

              {/* Head & Cranium */}
              <ellipse cx="160" cy="65" rx="36" ry="44" className="body-outline-path" />
              {/* Neck */}
              <path d="M148 106 L148 126 L172 126 L172 106" className="body-outline-path" />
              {/* Shoulders & Torso */}
              <path
                d="M148 126 C120 130 90 148 76 170 C66 186 64 220 62 270 C60 300 70 330 76 340 L84 340 C88 280 92 230 102 205 L112 370 C120 376 138 380 160 380 C182 380 200 376 208 370 L218 205 C228 230 232 280 236 340 L244 340 C250 330 260 300 258 270 C256 220 254 186 244 170 C230 148 200 130 172 126 Z"
                className="body-outline-path body-fill"
              />
              {/* Arms */}
              {/* Left Arm */}
              <path d="M76 170 L52 270 L42 340 L54 345 L68 280 L84 210" className="body-outline-path" />
              {/* Right Arm */}
              <path d="M244 170 L268 270 L278 340 L266 345 L252 280 L236 210" className="body-outline-path" />

              {/* Legs */}
              {/* Pelvis to Knees */}
              <path d="M124 376 L118 450 L144 450 L152 380" className="body-outline-path" />
              <path d="M196 376 L202 450 L176 450 L168 380" className="body-outline-path" />
              {/* Lower Legs & Feet */}
              <path d="M118 450 L114 520 L136 520 L142 450" className="body-outline-path" />
              <path d="M202 450 L206 520 L184 520 L178 450" className="body-outline-path" />

              {/* Internal Organ Subtle Contours */}
              {/* Brain subtle grid */}
              <ellipse cx="160" cy="62" rx="22" ry="26" className="organ-wireframe" />
              {/* Lungs pair */}
              <path d="M130 155 C120 165 118 190 126 210 C134 220 144 216 148 200 C150 180 145 160 130 155 Z" className="organ-wireframe" />
              <path d="M190 155 C200 165 202 190 194 210 C186 220 176 216 172 200 C170 180 175 160 190 155 Z" className="organ-wireframe" />
              {/* Heart contour */}
              <ellipse cx="170" cy="180" rx="14" ry="16" className="organ-wireframe" />
              {/* Stomach contour */}
              <path d="M145 220 C135 230 140 260 162 258 C176 256 180 236 172 226 Z" className="organ-wireframe" />
              {/* Liver contour */}
              <path d="M130 226 C118 235 124 258 142 255 Z" className="organ-wireframe" />
              {/* Spine line */}
              <line x1="160" y1="126" x2="160" y2="370" stroke="rgba(0, 229, 255, 0.2)" strokeDasharray="3 3" />
            </svg>

            {/* Hotspots: Interactive Organ Pins */}
            {profile?.organs?.map((organ) => {
              const isSelected = selectedOrganId === organ.id;
              const isHovered = hoveredOrganId === organ.id;
              const statusColor = getStatusColor(organ.status, organ.health_score);
              const isAlert = organ.status === 'adverse_reaction' || organ.status === 'critical';

              return (
                <div
                  key={organ.id}
                  className={`organ-hotspot-marker ${isSelected ? 'selected' : ''} ${isHovered ? 'hovered' : ''} ${isAlert ? 'is-alert' : ''}`}
                  style={{
                    left: `${organ.coordinates.x}%`,
                    top: `${organ.coordinates.y}%`,
                    '--organ-color': statusColor,
                  }}
                  onMouseEnter={() => setHoveredOrganId(organ.id)}
                  onMouseLeave={() => setHoveredOrganId(null)}
                  onClick={() => setSelectedOrganId(organ.id)}
                  role="button"
                  tabIndex={0}
                  aria-label={`Cơ quan: ${organ.vietnamese_name}, Trạng thái: ${organ.status}`}
                >
                  {/* Outer pulsating wave */}
                  <span className="pulse-wave" />
                  {/* Inner glowing pin */}
                  <span className="pin-core">
                    <span className="pin-inner-dot" />
                  </span>
                  {/* Pin label tag */}
                  <span className="pin-title-label">{organ.vietnamese_name}</span>
                </div>
              );
            })}
          </div>

          {/* Quick Body Status Footer */}
          <div className="silhouette-footer-legend">
            <div className="legend-item"><span className="legend-dot normal" /> Ổn định (90-100%)</div>
            <div className="legend-item"><span className="legend-dot monitor" /> Theo dõi (70-89%)</div>
            <div className="legend-item"><span className="legend-dot inflamed" /> Đang viêm (50-69%)</div>
            <div className="legend-item"><span className="legend-dot alert" /> Báo động / ADR (&lt;50%)</div>
          </div>
        </section>

        {/* Right Column: Detailed Organ Inspector Card & Live Controls */}
        <div className="inspector-column">
          {activeOrgan && (
            <div
              className={`organ-inspector-card ${activeOrgan.status === 'adverse_reaction' ? 'has-adr' : ''}`}
              style={{ '--organ-accent': getStatusColor(activeOrgan.status, activeOrgan.health_score) }}
            >
              <div className="inspector-header">
                <div className="inspector-organ-title">
                  <div className="organ-icon-circle">
                    {activeOrgan.id === 'head' && <Zap size={20} />}
                    {activeOrgan.id === 'ent' && <Eye size={20} />}
                    {activeOrgan.id === 'cardiovascular' && <Heart size={20} />}
                    {activeOrgan.id === 'lungs' && <Droplet size={20} />}
                    {activeOrgan.id === 'stomach' && <Flame size={20} />}
                    {activeOrgan.id === 'liver' && <Activity size={20} />}
                    {activeOrgan.id === 'kidneys' && <Droplet size={20} />}
                    {activeOrgan.id === 'spine_joints' && <Activity size={20} />}
                    {activeOrgan.id === 'skin' && <Shield size={20} />}
                  </div>
                  <div>
                    <h3>{activeOrgan.vietnamese_name}</h3>
                    <span className="organ-en-name">{activeOrgan.name}</span>
                  </div>
                </div>

                <div className="status-badge-wrap">
                  <span className={`status-pill ${activeOrgan.status}`}>
                    {getStatusBadgeText(activeOrgan.status)}
                  </span>
                </div>
              </div>

              {/* Organ Health Metrics Grid */}
              <div className="organ-metrics-row">
                <div className="metric-box">
                  <span className="metric-label">Điểm sức khoẻ</span>
                  <div className="metric-value-row">
                    <strong style={{ color: getStatusColor(activeOrgan.status, activeOrgan.health_score) }}>
                      {activeOrgan.health_score}
                    </strong>
                    <span className="metric-unit">/100</span>
                  </div>
                  <div className="score-mini-bar">
                    <div
                      className="score-mini-fill"
                      style={{
                        width: `${activeOrgan.health_score}%`,
                        backgroundColor: getStatusColor(activeOrgan.status, activeOrgan.health_score),
                      }}
                    />
                  </div>
                </div>

                <div className="metric-box">
                  <span className="metric-label">Mức độ đau (0-10)</span>
                  <div className="metric-value-row">
                    <strong className={activeOrgan.pain_level >= 5 ? 'pain-high' : ''}>
                      {activeOrgan.pain_level}
                    </strong>
                    <span className="metric-unit">
                      {activeOrgan.pain_level === 0 ? 'Không đau' : activeOrgan.pain_level <= 3 ? 'Nhẹ' : activeOrgan.pain_level <= 6 ? 'Vừa' : 'Dữ dội'}
                    </span>
                  </div>
                  <span className="metric-sub">Thang đo lâm sàng VAS</span>
                </div>

                <div className="metric-box">
                  <span className="metric-label">Mức độ viêm</span>
                  <div className="metric-value-row">
                    <strong className="text-capital">{activeOrgan.inflammation_level}</strong>
                  </div>
                  <span className="metric-sub">Đánh giá phản ứng mô</span>
                </div>
              </div>

              {/* Symptoms Recorded */}
              {activeOrgan.symptoms && activeOrgan.symptoms.length > 0 && (
                <div className="inspector-section">
                  <span className="section-title">Triệu chứng ghi nhận tại vị trí này:</span>
                  <div className="symptom-tag-list">
                    {activeOrgan.symptoms.map((s, idx) => (
                      <span key={idx} className="symptom-tag-item">
                        <AlertCircle size={12} />
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Warning or ADR callout */}
              {activeOrgan.warning && (
                <div className="inspector-warning-box">
                  <AlertTriangle size={16} />
                  <span>{activeOrgan.warning}</span>
                </div>
              )}

              {/* Contraindicated Actions (Cấm tiếp tục) */}
              {activeOrgan.contraindicated_actions && activeOrgan.contraindicated_actions.length > 0 && (
                <div className="contra-actions-box">
                  <div className="contra-title">
                    <X size={14} />
                    <span>HẠN CHẾ TIẾP TỤC / CHỐNG CHỈ ĐỊNH:</span>
                  </div>
                  <ul>
                    {activeOrgan.contraindicated_actions.map((act, idx) => (
                      <li key={idx}><strong>{act}</strong></li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Clinical Notes & Recommendations */}
              <div className="inspector-section notes-section">
                <span className="section-title">Ghi chú lâm sàng & Khuyến nghị:</span>
                <p className="clinical-notes-p">{activeOrgan.clinical_notes || 'Cơ quan ở trạng thái ổn định bình thường.'}</p>
              </div>

              {/* Related Medications */}
              {activeOrgan.related_medications && activeOrgan.related_medications.length > 0 && (
                <div className="inspector-section meds-section">
                  <span className="section-title">Thuốc liên quan cơ quan này:</span>
                  <div className="meds-badge-row">
                    {activeOrgan.related_medications.map((m, idx) => (
                      <span key={idx} className="med-badge">
                        <Pill size={12} />
                        {m}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Quick Chat Symptom Updater for this patient */}
          <div className="symptom-update-widget">
            <div className="widget-header">
              <Sparkles size={16} />
              <h4>Cập nhật diễn tiến triệu chứng mới</h4>
            </div>
            <p className="widget-desc">
              Nhập thay đổi thể trạng (Ví dụ: <em>&quot;hôm nay tôi đã hết đau đầu sổ mũi&quot;</em> hoặc <em>&quot;uống thuốc xong bị đau dạ dày dữ dội&quot;</em>):
            </p>

            <form
              className="update-form"
              onSubmit={(e) => {
                e.preventDefault();
                handleEvaluateProgress();
              }}
            >
              <input
                type="text"
                className="symptom-input"
                placeholder="Nhập triệu chứng thuyên giảm hoặc tăng nặng..."
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                disabled={evaluating}
              />
              <button
                type="submit"
                className="submit-eval-btn"
                disabled={evaluating || !inputMessage.trim()}
              >
                {evaluating ? (
                  <RefreshCw size={14} className="spinning" />
                ) : (
                  <>
                    <span>AI Đánh giá</span>
                    <Send size={14} />
                  </>
                )}
              </button>
            </form>

            <div className="quick-suggestions-row">
              <button
                type="button"
                className="quick-sugg-chip green"
                onClick={() => handleEvaluateProgress('Hôm nay tôi đã hết đau đầu và sổ mũi, cảm thấy khỏe khoắn')}
              >
                + Báo khỏi: &quot;Hết đau đầu sổ mũi&quot;
              </button>
              <button
                type="button"
                className="quick-sugg-chip red"
                onClick={() => handleEvaluateProgress('Uống thuốc vào bỗng bị đau dạ dày dữ dội, cồn cào buồn nôn')}
              >
                + Báo tác dụng phụ: &quot;Đau dạ dày sau uống&quot;
              </button>
              <button
                type="button"
                className="quick-sugg-chip orange"
                onClick={() => handleEvaluateProgress('Sốt cao hơn 39.5 độ, rét run và khó thở')}
              >
                + Báo tăng nặng: &quot;Sốt 39.5 độ&quot;
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Section: Overall Health Dashboard, Vitals HUD & Recovery Timeline */}
      <section className="overall-health-dashboard">
        <div className="dashboard-tabs-bar" role="tablist">
          <button
            role="tab"
            aria-selected={activeTab === 'overview'}
            className={`dash-tab ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            <Activity size={16} />
            <span>Tổng quan Chỉ số Sức khoẻ</span>
          </button>
          <button
            role="tab"
            aria-selected={activeTab === 'timeline'}
            className={`dash-tab ${activeTab === 'timeline' ? 'active' : ''}`}
            onClick={() => setActiveTab('timeline')}
          >
            <Clock size={16} />
            <span>Thời gian Thăm dò & Hồi phục ({profile?.timeline?.length || 0})</span>
          </button>
          <button
            role="tab"
            aria-selected={activeTab === 'meds'}
            className={`dash-tab ${activeTab === 'meds' ? 'active' : ''}`}
            onClick={() => setActiveTab('meds')}
          >
            <Pill size={16} />
            <span>Đơn thuốc & Phác đồ ({profile?.active_medications?.length || 0})</span>
          </button>
        </div>

        {/* Tab 1: Overview & Vitals */}
        {activeTab === 'overview' && (
          <div className="overview-tab-content">
            {/* Health Score & Vitals Row */}
            <div className="vitals-hud-grid">
              {/* Overall Recovery Score Dial */}
              <div className="hud-card recovery-score-card">
                <span className="card-subtitle">Điểm Hồi phục Sức khoẻ</span>
                <div className="dial-wrap">
                  <div
                    className="dial-circle"
                    style={{
                      background: `conic-gradient(${getStatusColor(profile?.health_trend === 'critical_alert' ? 'critical' : 'normal', profile?.overall_health_score || 80)} ${(profile?.overall_health_score || 80) * 3.6}deg, rgba(255,255,255,0.06) 0deg)`,
                    }}
                  >
                    <div className="dial-inner">
                      <strong className="dial-num">{profile?.overall_health_score || 82}</strong>
                      <span className="dial-max">/100</span>
                    </div>
                  </div>
                </div>

                <div className="trend-indicator-row">
                  {profile?.health_trend === 'improving' ? (
                    <span className="trend-badge improving">
                      <TrendingUp size={14} /> Đang hồi phục tốt
                    </span>
                  ) : profile?.health_trend === 'critical_alert' ? (
                    <span className="trend-badge alert">
                      <TrendingDown size={14} /> Báo động cần can thiệp
                    </span>
                  ) : (
                    <span className="trend-badge stable">
                      <Activity size={14} /> Đang theo dõi ổn định
                    </span>
                  )}
                </div>
                <p className="diagnosis-text">{profile?.active_diagnosis}</p>
              </div>

              {/* Vitals HUD Cards */}
              <div className="hud-card vital-card">
                <div className="vital-header">
                  <Heart size={16} className="vital-icon heart" />
                  <span>Nhịp tim</span>
                </div>
                <div className="vital-val-row">
                  <strong className="vital-num">{profile?.vitals?.heart_rate_bpm || 78}</strong>
                  <span className="vital-unit">bpm</span>
                </div>
                <span className="vital-status-text">
                  {(profile?.vitals?.heart_rate_bpm || 78) > 100 ? 'Nhịp tim nhanh' : 'Nhịp đều bình thường'}
                </span>
              </div>

              <div className="hud-card vital-card">
                <div className="vital-header">
                  <Activity size={16} className="vital-icon bp" />
                  <span>Huyết áp</span>
                </div>
                <div className="vital-val-row">
                  <strong className="vital-num">
                    {profile?.vitals?.blood_pressure_systolic || 120}/{profile?.vitals?.blood_pressure_diastolic || 80}
                  </strong>
                  <span className="vital-unit">mmHg</span>
                </div>
                <span className="vital-status-text">Ngưỡng tối ưu</span>
              </div>

              <div className="hud-card vital-card">
                <div className="vital-header">
                  <Thermometer size={16} className="vital-icon temp" />
                  <span>Thân nhiệt</span>
                </div>
                <div className="vital-val-row">
                  <strong
                    className={`vital-num ${(profile?.vitals?.temperature_celsius || 37) >= 38.5 ? 'vital-hot' : ''}`}
                  >
                    {profile?.vitals?.temperature_celsius || 37.0}°C
                  </strong>
                </div>
                <span className="vital-status-text">
                  {(profile?.vitals?.temperature_celsius || 37) >= 38.5
                    ? 'Sốt cao cần hạ sốt'
                    : (profile?.vitals?.temperature_celsius || 37) > 37.5
                    ? 'Sốt nhẹ'
                    : 'Thân nhiệt bình thường'}
                </span>
              </div>

              <div className="hud-card vital-card">
                <div className="vital-header">
                  <Droplet size={16} className="vital-icon spo2" />
                  <span>SpO2 Khí máu</span>
                </div>
                <div className="vital-val-row">
                  <strong className="vital-num">{profile?.vitals?.spo2_percent || 98}%</strong>
                </div>
                <span className="vital-status-text">
                  {(profile?.vitals?.spo2_percent || 98) < 95 ? 'Nguy cơ suy hô hấp' : 'Nồng độ oxy tối ưu'}
                </span>
              </div>

              <div className="hud-card vital-card">
                <div className="vital-header">
                  <Flame size={16} className="vital-icon pain" />
                  <span>Mức đau toàn thân</span>
                </div>
                <div className="vital-val-row">
                  <strong className={`vital-num ${(profile?.vitals?.overall_pain_level || 0) >= 5 ? 'vital-pain' : ''}`}>
                    {profile?.vitals?.overall_pain_level || 0}/10
                  </strong>
                </div>
                <span className="vital-status-text">
                  {(profile?.vitals?.overall_pain_level || 0) === 0 ? 'Không đau' : 'Đau có đáp ứng'}
                </span>
              </div>
            </div>

            {/* Directives & Action Recommendations */}
            <div className="directives-row">
              <div className="directives-box">
                <div className="box-title">
                  <Stethoscope size={16} />
                  <span>Chỉ thị Y tế & Lời khuyên Điều trị</span>
                </div>
                <ul className="directives-list">
                  {profile?.clinical_directives?.map((d, i) => (
                    <li key={i}>
                      <CheckCircle2 size={15} className="directive-check-icon" />
                      <span>{d}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Safety Discontinued Items Warning */}
              {profile?.discontinued_medications && profile.discontinued_medications.length > 0 && (
                <div className="discontinued-alert-box">
                  <div className="box-title danger">
                    <ShieldAlert size={16} />
                    <span>Thuốc & Cách cũ ĐÃ BỊ ĐÌNH CHỈ (Dừng Ngay)</span>
                  </div>
                  <p className="disc-sub">
                    Để bảo vệ bệnh nhân, AI đã gắn cờ cấm tiếp tục sử dụng các mục sau do phát hiện phản ứng bất lợi:
                  </p>
                  <ul className="disc-list">
                    {profile.discontinued_medications.map((item, idx) => (
                      <li key={idx}>
                        <X size={14} className="disc-cross" />
                        <strong>{item}</strong>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tab 2: Recovery Timeline */}
        {activeTab === 'timeline' && (
          <div className="timeline-tab-content">
            <div className="timeline-header-info">
              <Clock size={16} />
              <span>Tiến trình Diễn biến Lâm sàng & Các lần Tương tác Thăm dò</span>
            </div>

            <div className="timeline-vertical-flow">
              {profile?.timeline?.map((point, idx) => (
                <div key={point.id || idx} className={`timeline-entry-node ${point.phase}`}>
                  <div className="timeline-node-marker">
                    <span className="node-dot" />
                    {idx < profile.timeline.length - 1 && <span className="node-line" />}
                  </div>

                  <div className="timeline-entry-card">
                    <div className="entry-card-top">
                      <div className="entry-title-wrap">
                        <h4>{point.title}</h4>
                        <span className="entry-time">{point.timestamp}</span>
                      </div>
                      <span className={`phase-badge ${point.phase}`}>{point.status_label}</span>
                    </div>

                    <div className="trigger-quote-box">
                      <span className="quote-label">Tin nhắn bệnh nhân:</span>
                      <p>&ldquo;{point.trigger_message}&rdquo;</p>
                    </div>

                    <p className="clinical-summary-p">{point.clinical_summary}</p>

                    <div className="ai-directive-quote">
                      <Sparkles size={14} />
                      <div>
                        <strong>Chỉ dẫn AI Bác sĩ:</strong>
                        <p>{point.ai_directive}</p>
                      </div>
                    </div>

                    {point.medications_adjusted && point.medications_adjusted.length > 0 && (
                      <div className="med-adjust-row">
                        {point.medications_adjusted.map((m, i) => (
                          <span key={i} className="med-adjust-tag">
                            <Pill size={11} /> {m}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tab 3: Medications & Regimens */}
        {activeTab === 'meds' && (
          <div className="meds-tab-content">
            <div className="meds-columns-grid">
              <div className="meds-col active-meds">
                <div className="meds-col-header">
                  <CheckCircle2 size={16} />
                  <h3>Thuốc đang được sử dụng an toàn</h3>
                </div>
                {profile?.active_medications && profile.active_medications.length > 0 ? (
                  <ul className="meds-card-list">
                    {profile.active_medications.map((m, idx) => (
                      <li key={idx} className="med-item-card safe">
                        <Pill size={16} />
                        <div>
                          <strong>{m}</strong>
                          <span>Đang đáp ứng theo dõi tốt</span>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="empty-meds">Hiện không có thuốc kê thêm.</p>
                )}
              </div>

              <div className="meds-col stopped-meds">
                <div className="meds-col-header danger">
                  <ShieldAlert size={16} />
                  <h3>Thuốc đã bị dừng / Chống chỉ định</h3>
                </div>
                {profile?.discontinued_medications && profile.discontinued_medications.length > 0 ? (
                  <ul className="meds-card-list">
                    {profile.discontinued_medications.map((m, idx) => (
                      <li key={idx} className="med-item-card stopped">
                        <X size={16} />
                        <div>
                          <strong>{m}</strong>
                          <span className="stopped-warn">Ngừng khẩn cấp do gây phản ứng bất lợi</span>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="empty-meds">Chưa ghi nhận thuốc nào bị chống chỉ định.</p>
                )}
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
