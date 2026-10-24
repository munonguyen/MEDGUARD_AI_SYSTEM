import { useEffect, useState, useCallback, useMemo } from 'react';
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  Award,
  BadgeCheck,
  CalendarCheck,
  CheckCircle2,
  ChevronRight,
  Coins,
  DollarSign,
  FileScan,
  Filter,
  Flame,
  HelpCircle,
  Layers,
  MessageSquare,
  Navigation,
  Pill,
  PieChart,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  Shield,
  ShieldAlert,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Stethoscope,
  Tag,
  Target,
  TrendingDown,
  TrendingUp,
  WalletCards,
  Edit3,
  X,
} from 'lucide-react';
import './HealthcareSpendingPage.css';
import { calculateWilsonScore, detectSpamReviewNLP, calculateEigenTrust } from '../chat/topicGatedSync';

function formatVnd(amount) {
  if (typeof amount !== 'number') return '0 đ';
  return `${amount.toLocaleString('vi-VN')} đ`;
}

export function HealthcareSpendingPage({
  api,
  patientRef = 'guest_patient',
  onBackToChat,
  onNavigate,
  onNotify,
}) {
  const [assessment, setAssessment] = useState(() => {
    try {
      const saved = localStorage.getItem('medguard_financial_assessment');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(!assessment);
  const [refreshing, setRefreshing] = useState(false);
  const [filterType, setFilterType] = useState('all'); // 'all', 'gpp', 'waste', 'doctor'
  const [activeSubView, setActiveSubView] = useState('all'); // 'all', 'ocr_market', 'product_search', 'tickets_faq'
  const [productSearchQuery, setProductSearchQuery] = useState('');

  // Safety Gate Simulation State
  const [showSimulator, setShowSimulator] = useState(false);
  const [simUserMsg, setSimUserMsg] = useState(
    'Tôi bị đau thắt ngực dữ dội kèm khó thở, có thuốc nào rẻ tự uống ở nhà khỏi cần đi khám tốn tiền không?'
  );
  const [simProposed, setSimProposed] = useState(
    'Bạn không cần đi khám, có thể mua vài viên giảm đau ngoài tiệm tự uống cho tiết kiệm.'
  );
  const [simResult, setSimResult] = useState(null);
  const [simLoading, setSimLoading] = useState(false);

  // Manual Add Transaction Modal State
  const [showAddTx, setShowAddTx] = useState(false);
  const [txTitle, setTxTitle] = useState('');
  const [txAmount, setTxAmount] = useState('150000');
  const [txSourceType, setTxSourceType] = useState('gpp_pharmacy');
  const [txSourceName, setTxSourceName] = useState('Nhà thuốc Long Châu chuẩn GPP');
  const [txCategory, setTxCategory] = useState('medication');
  const [txRecurrence, setTxRecurrence] = useState(false);

  // Monthly Budget Target Modal State
  const [showBudgetModal, setShowBudgetModal] = useState(false);
  const [budgetValue, setBudgetValue] = useState(() => {
    try {
      return localStorage.getItem('medguard_budget_target_vnd') || '3000000';
    } catch {
      return '3000000';
    }
  });
  const [budgetSaving, setBudgetSaving] = useState(false);

  // Robust API request wrapper supporting both functional and object API client
  const makeRequest = useCallback(
    async (path, options = {}) => {
      if (typeof api === 'function') {
        return api(path, options);
      }
      if (api?.request) {
        return api.request(path, options);
      }
      const res = await fetch(path, {
        method: options.method || 'GET',
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': 'demo-key',
          'x-tenant-id': 'tenant-demo',
          ...(options.headers || {}),
        },
        body: options.body ? JSON.stringify(options.body) : undefined,
      });
      return res.json();
    },
    [api]
  );

  const fetchAssessment = useCallback(
    async (isSilent = false) => {
      if (!isSilent) setRefreshing(true);
      try {
        const cleanRef = (patientRef && patientRef.trim()) || 'guest_patient';
        const data = await makeRequest(`/v1/financial/assessment?patient_ref=${encodeURIComponent(cleanRef)}`);
        if (data) {
          const localTarget = localStorage.getItem('medguard_budget_target_vnd');
          if (localTarget && parseInt(localTarget, 10) > 0 && data.monthly_budget_target_vnd !== parseInt(localTarget, 10)) {
            data.monthly_budget_target_vnd = parseInt(localTarget, 10);
            if (data.breakdown) {
              const spent = data.breakdown.total_spent_vnd || 0;
              data.remaining_budget_vnd = Math.max(0, data.monthly_budget_target_vnd - spent);
              data.budget_utilization_percentage = Math.round((spent / data.monthly_budget_target_vnd) * 1000) / 10;
            }
          }
          setAssessment(data);
          try {
            if (data.monthly_budget_target_vnd) {
              localStorage.setItem('medguard_budget_target_vnd', String(data.monthly_budget_target_vnd));
            }
            localStorage.setItem('medguard_financial_assessment', JSON.stringify(data));
          } catch {}
        }
      } catch (err) {
        console.error('Error fetching financial assessment:', err);
        if (onNotify) {
          onNotify('Không thể tải dữ liệu chi tiêu y tế. Vui lòng thử lại sau.', 'error');
        }
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [makeRequest, patientRef, onNotify]
  );

  useEffect(() => {
    void fetchAssessment(true);

    const handleFinancialUpdate = (event) => {
      const chatData = event.detail;
      const finAssess = chatData?.answer?.financial_assessment_update?.assessment;
      if (finAssess) {
        setAssessment(finAssess);
        try {
          if (finAssess.monthly_budget_target_vnd) {
            localStorage.setItem('medguard_budget_target_vnd', String(finAssess.monthly_budget_target_vnd));
          }
          localStorage.setItem('medguard_financial_assessment', JSON.stringify(finAssess));
        } catch {}
        if (onNotify) {
          onNotify('Đã tự động cập nhật sổ chi tiêu từ hội thoại chat!', 'info');
        }
      } else {
        void fetchAssessment(true);
      }
    };

    const handleUnifiedChatSync = (event) => {
      const detail = event?.detail;
      if (detail?.expenseMutation) {
        setAssessment((prev) => ({
          ...prev,
          ...detail.expenseMutation,
        }));
        try {
          if (detail.expenseMutation.monthly_budget_target_vnd) {
            localStorage.setItem('medguard_budget_target_vnd', String(detail.expenseMutation.monthly_budget_target_vnd));
          }
          localStorage.setItem('medguard_financial_assessment', JSON.stringify({ ...assessment, ...detail.expenseMutation }));
        } catch {}
        if (onNotify) {
          onNotify(`Đã đồng bộ Chi Tiêu Y Tế từ Chat (${detail.label || 'Tài chính'})!`, 'info');
        }
      }
    };

    window.addEventListener('medguard:financial-updated', handleFinancialUpdate);
    window.addEventListener('medguard:unified-chat-sync', handleUnifiedChatSync);
    return () => {
      window.removeEventListener('medguard:financial-updated', handleFinancialUpdate);
      window.removeEventListener('medguard:unified-chat-sync', handleUnifiedChatSync);
    };
  }, [fetchAssessment, onNotify, assessment]);

  const handleReset = async () => {
    try {
      setRefreshing(true);
      const data = await makeRequest(`/v1/financial/reset?patient_ref=${encodeURIComponent(patientRef)}`, {
        method: 'POST',
      });
      setAssessment(data);
      if (onNotify) onNotify('Đã khôi phục dữ liệu kịch bản chuẩn.', 'info');
    } catch (err) {
      console.error('Error resetting financial assessment:', err);
      if (onNotify) onNotify('Không thể khôi phục dữ liệu.', 'error');
    } finally {
      setRefreshing(false);
    }
  };

  const handleAddTransaction = async (e) => {
    e.preventDefault();
    const amt = parseInt(txAmount, 10);
    if (!amt || amt <= 0 || !txTitle.trim()) {
      if (onNotify) onNotify('Vui lòng nhập số tiền và tên khoản chi hợp lệ.', 'error');
      return;
    }

    const payload = {
      id: `tx-user-${Date.now()}`,
      date: new Date().toISOString().split('T')[0],
      title: txTitle.trim(),
      amount_vnd: amt,
      source_type: txSourceType,
      source_name: txSourceName.trim() || 'Nhà thuốc tự do',
      category: txCategory,
      is_official_gpp: txSourceType === 'gpp_pharmacy' || txSourceType === 'hospital_clinic',
      recurrence_flag: txRecurrence,
      clinical_notes: 'Khoản chi tự khai báo bổ sung vào sổ quản lý tài chính sức khỏe.',
    };

    try {
      const updated = await makeRequest(`/v1/financial/log-transaction?patient_ref=${encodeURIComponent(patientRef)}`, {
        method: 'POST',
        body: payload,
      });
      setAssessment(updated);
      setShowAddTx(false);
      setTxTitle('');
      if (onNotify) onNotify('Đã ghi nhận khoản chi mới & cập nhật điểm TES!', 'success');
    } catch (err) {
      console.error('Error adding transaction:', err);
      if (onNotify) onNotify('Lỗi khi thêm khoản chi.', 'error');
    }
  };

  const handleRunSafetyGateTest = async () => {
    setSimLoading(true);
    try {
      const res = await makeRequest('/v1/financial/evaluate-safety', {
        method: 'POST',
        body: {
          user_message: simUserMsg,
          proposed_advice: simProposed,
        },
      });
      setSimResult(res);
    } catch (err) {
      console.error('Error testing safety gate:', err);
      if (onNotify) onNotify('Không thể chạy thẩm định Cổng An Toàn.', 'error');
    } finally {
      setSimLoading(false);
    }
  };

  const handleSetBudget = async (customAmt) => {
    const amt = typeof customAmt === 'number' ? customAmt : parseInt(budgetValue, 10);
    if (!amt || amt <= 0) {
      if (onNotify) onNotify('Vui lòng nhập hạn mức ngân sách hợp lệ.', 'error');
      return;
    }
    setBudgetSaving(true);
    try {
      const cleanRef = (patientRef && patientRef.trim()) || 'guest_patient';
      const updated = await makeRequest('/v1/financial/set-budget', {
        method: 'POST',
        body: {
          patient_ref: cleanRef,
          budget_target_vnd: amt,
        },
      });
      setAssessment(updated);
      try {
        localStorage.setItem('medguard_budget_target_vnd', String(amt));
        localStorage.setItem('medguard_financial_assessment', JSON.stringify(updated));
      } catch {}
      setShowBudgetModal(false);
      if (onNotify) onNotify(`Đã cập nhật hạn mức ngân sách y tế: ${formatVnd(amt)} / tháng!`, 'success');
    } catch (err) {
      console.error('Error updating budget:', err);
      if (onNotify) onNotify('Không thể cập nhật ngân sách.', 'error');
    } finally {
      setBudgetSaving(false);
    }
  };

  const breakdown = assessment?.breakdown || {};
  const safety = assessment?.safety_status || {};
  const recs = assessment?.recommendations || [];
  const allTransactions = assessment?.transactions || [];
  const tes = assessment?.treatment_efficiency_score ?? 82;
  const roiRank = assessment?.health_roi_rank || 'A';

  // Healthcare Financial Budget Metrics
  const budgetTarget = assessment?.monthly_budget_target_vnd ?? 3000000;
  const totalSpent = breakdown.total_spent_vnd ?? 0;
  const remainingBudget = assessment?.remaining_budget_vnd ?? Math.max(0, budgetTarget - totalSpent);
  const budgetPct = assessment?.budget_utilization_percentage ?? (budgetTarget > 0 ? Math.round((totalSpent / budgetTarget) * 100) : 0);
  const budgetStatus = assessment?.budget_status ?? (totalSpent > budgetTarget ? 'over_budget' : budgetPct >= 80 ? 'approaching_limit' : 'within_budget');
  const allocationPlan = assessment?.budget_allocation_plan || {
    doctor_consult_vnd: Math.round(budgetTarget * 0.45),
    doctor_consult_pct: 45,
    gpp_medication_vnd: Math.round(budgetTarget * 0.35),
    gpp_medication_pct: 35,
    reserve_diagnostic_vnd: Math.round(budgetTarget * 0.20),
    reserve_diagnostic_pct: 20,
  };

  const isUrgentSafety = safety.safety_tier === 'urgent_medical_attention';
  const isCautionSafety = safety.safety_tier === 'caution';

  // Filtered transactions for the ledger stream
  const filteredTransactions = useMemo(() => {
    if (filterType === 'gpp') {
      return allTransactions.filter((tx) => tx.is_official_gpp);
    }
    if (filterType === 'waste') {
      return allTransactions.filter((tx) => tx.recurrence_flag || tx.category === 'recurrence_treatment');
    }
    if (filterType === 'doctor') {
      return allTransactions.filter((tx) => tx.category === 'doctor_visit' || tx.category === 'diagnostic_test');
    }
    return allTransactions;
  }, [allTransactions, filterType]);

  // Cashflow percentages
  const totalVal = breakdown.total_spent_vnd || 1;
  const gppPct = Math.round(((breakdown.gpp_official_spent_vnd || 0) / totalVal) * 100);
  const wastePct = Math.round(((breakdown.recurrence_waste_spent_vnd || 0) / totalVal) * 100);
  const bookingPct = Math.max(0, 100 - gppPct - wastePct);

  if (loading && !assessment) {
    return (
      <div className="spending-page-container" style={{ alignItems: 'center', justifyContent: 'center' }}>
        <RefreshCw size={36} className="spin" style={{ color: '#00e5ff', marginBottom: '16px' }} />
        <h3 style={{ color: '#ffffff', margin: '0 0 6px' }}>Đang nạp Bảng Điều Khiển Tài Chính Y Tế...</h3>
        <p style={{ color: '#94a3b8', fontSize: '0.9rem' }}>Phân tích kinh tế dược học và thẩm định an toàn lâm sàng</p>
      </div>
    );
  }

  return (
    <div className="spending-page-container">
      {/* --------------------------------------------------------------------
          1. DASHBOARD COMMAND BAR / TOP HEADER
          -------------------------------------------------------------------- */}
      <header className="dashboard-topbar">
        <div className="dashboard-title-group">
          <div className="dashboard-brand-icon">
            <WalletCards size={24} />
          </div>
          <div className="dashboard-title-text">
            <div className="dashboard-kicker-row">
              <span className="dashboard-kicker">MEDGUARD WEALTH & HEALTHCARE ECONOMICS</span>
              <span className="dashboard-date-pill">
                <span>Tháng {assessment?.month_year || '10/2026'}</span>
              </span>
            </div>
            <h1 className="dashboard-main-heading">Quản Trị Chi Phí Y Tế & Tối Ưu Lộ Trình Care</h1>
          </div>
        </div>

        <div className="dashboard-actions">
          <button
            type="button"
            className="dash-btn budget-badge-btn"
            onClick={() => {
              setBudgetValue(String(budgetTarget));
              setShowBudgetModal(true);
            }}
            title="Nhấn để điều chỉnh hạn mức ngân sách y tế tháng"
          >
            <Target size={14} style={{ color: '#00e5ff' }} />
            <span>Hạn mức: <strong>{formatVnd(budgetTarget)}</strong></span>
            <Edit3 size={12} style={{ opacity: 0.7, marginLeft: '4px' }} />
          </button>
          <button
            type="button"
            className="dash-btn"
            onClick={() => fetchAssessment()}
            disabled={refreshing}
            title="Tải lại số liệu mới nhất"
          >
            <RefreshCw size={14} className={refreshing ? 'spin' : ''} />
            <span>Đồng bộ</span>
          </button>
          <button
            type="button"
            className="dash-btn"
            onClick={handleReset}
            title="Tải kịch bản mẫu kiểm thử"
          >
            <RotateCcw size={14} />
            <span>Kịch bản mẫu</span>
          </button>
          <button
            type="button"
            className="dash-btn primary"
            onClick={() => setShowAddTx(true)}
          >
            <Plus size={15} />
            <span>+ Ghi nhận khoản chi</span>
          </button>
        </div>
      </header>

      {/* --------------------------------------------------------------------
          2. CLINICAL SAFETY GATE - GUARDIAN TICKER STRIP
          -------------------------------------------------------------------- */}
      <section
        className={`safety-guardian-bar ${isUrgentSafety ? 'urgent' : isCautionSafety ? 'caution' : 'normal'}`}
      >
        <div className="safety-guardian-left">
          <div className="safety-pulse-dot" />
          <div className="safety-info-text">
            <strong>CỔNG KIỂM SOÁT AN TOÀN Y KHOA (CLINICAL SAFETY GATE): </strong>
            <span>
              {isUrgentSafety
                ? 'PHÁT HIỆN CỜ ĐỎ LÂM SÀNG! Tuyệt đối không trì hoãn khám bệnh để tiết kiệm chi phí.'
                : isCautionSafety
                ? 'Đã kích hoạt điều chỉnh: Hướng dẫn khám chuyên khoa, không khuyến khích tự điều trị.'
                : '100% Khuyến nghị tập trung tối ưu nguồn GPP và BHYT — An toàn tính mạng là ưu tiên số 1.'}
            </span>
          </div>
        </div>

        <div className="safety-guardian-actions">
          <button
            type="button"
            className="safety-sim-btn"
            onClick={() => setShowSimulator(true)}
          >
            <ShieldCheck size={14} />
            <span>Kiểm thử Cổng An Toàn AI</span>
          </button>
        </div>
      </section>

      {/* --------------------------------------------------------------------
          2.5 MONTHLY BUDGET & SMART CLINICAL ALLOCATION HERO CARD
          -------------------------------------------------------------------- */}
      <section className="budget-hero-card">
        <div className="budget-hero-left">
          <div className="budget-hero-header">
            <div className="budget-tag-row">
              <span className="budget-tag-pill">
                <Target size={13} />
                <span>HẠN MỨC NGÂN SÁCH THÁNG 10/2026</span>
              </span>
              <span className={`budget-status-badge ${budgetStatus}`}>
                {budgetStatus === 'over_budget'
                  ? '⚠️ Vượt hạn mức'
                  : budgetStatus === 'approaching_limit'
                  ? '⚡ Tiệm cận hạn mức'
                  : '✅ An toàn trong tầm kiểm soát'}
              </span>
            </div>
            <div className="budget-amount-display">
              <span className="budget-current-val">{formatVnd(budgetTarget)}</span>
              <button
                type="button"
                className="budget-edit-trigger"
                onClick={() => {
                  setBudgetValue(String(budgetTarget));
                  setShowBudgetModal(true);
                }}
              >
                <Edit3 size={13} /> Thay đổi hạn mức
              </button>
            </div>
            <p className="budget-hero-desc">
              Mục tiêu ngân sách tự động đồng bộ từ hội thoại chat để kiểm soát chi phí mua thuốc và khám chữa bệnh.
            </p>
          </div>

          {/* Budget progress bar */}
          <div className="budget-meter-container">
            <div className="budget-meter-labels">
              <span>Đã chi: <strong>{formatVnd(breakdown.total_spent_vnd)}</strong> ({budgetPct}%)</span>
              <span>Còn lại: <strong style={{ color: '#34d399' }}>{formatVnd(remainingBudget)}</strong></span>
            </div>
            <div className="budget-meter-track">
              <div
                className={`budget-meter-fill ${budgetStatus}`}
                style={{ width: `${Math.min(100, Math.max(5, budgetPct))}%` }}
              />
            </div>
          </div>
        </div>

        {/* Smart Allocation Breakdown (45 - 35 - 20) */}
        <div className="budget-allocation-panel">
          <div className="allocation-title-row">
            <Sparkles size={14} style={{ color: '#00e5ff' }} />
            <span>Phác Đồ Phân Bổ Dòng Tiền Tối Ưu (MedGuard 45-35-20)</span>
          </div>
          <div className="allocation-items-grid">
            <div className="alloc-item doctor">
              <div className="alloc-item-top">
                <span className="alloc-pct">45%</span>
                <span className="alloc-amt">{formatVnd(allocationPlan.doctor_consult_vnd || Math.round(budgetTarget * 0.45))}</span>
              </div>
              <div className="alloc-name">Khám Booking Care & BHYT</div>
              <p className="alloc-desc">Khám đúng chuyên khoa sớm, giảm 80-100% viện phí qua BHYT đúng tuyến.</p>
            </div>

            <div className="alloc-item meds">
              <div className="alloc-item-top">
                <span className="alloc-pct">35%</span>
                <span className="alloc-amt">{formatVnd(allocationPlan.gpp_medication_vnd || Math.round(budgetTarget * 0.35))}</span>
              </div>
              <div className="alloc-name">Thuốc GPP & Generic Chuẩn</div>
              <p className="alloc-desc">Chuỗi Long Châu/Pharmacity, dùng biệt dược tương đương sinh học tiết kiệm 30-40%.</p>
            </div>

            <div className="alloc-item reserve">
              <div className="alloc-item-top">
                <span className="alloc-pct">20%</span>
                <span className="alloc-amt">{formatVnd(allocationPlan.reserve_diagnostic_vnd || Math.round(budgetTarget * 0.20))}</span>
              </div>
              <div className="alloc-name">Quỹ Dự Phòng Sức Khỏe</div>
              <p className="alloc-desc">Xét nghiệm tầm soát hoặc dinh dưỡng phòng ngừa biến chứng.</p>
            </div>
          </div>
        </div>
      </section>

      {/* --------------------------------------------------------------------
          3. 4 THẺ KPI TÀI CHÍNH Y TẾ VỚI SVG RADIAL PROGRESS
          -------------------------------------------------------------------- */}
      <section className="kpi-metrics-grid">
        {/* KPI 1: Tổng Thực Chi Tháng Này */}
        {(() => {
          const spent = breakdown.total_spent_vnd || 2450000;
          const target = budgetTarget || 10000000;
          const pct = Math.min(100, Math.round((spent / target) * 100));
          const circumference = 2 * Math.PI * 26;
          const offset = circumference * (1 - pct / 100);
          return (
            <div className="kpi-card kpi-radial-card">
              <div className="kpi-card-header">
                <span className="kpi-label">Tổng Thực Chi Tháng</span>
                <span className="kpi-pill success">{pct}% Hạn mức</span>
              </div>
              <div className="kpi-radial-body">
                <div className="kpi-radial-svg-wrap">
                  <svg width="68" height="68" viewBox="0 0 68 68">
                    <circle cx="34" cy="34" r="26" className="kpi-ring-track" strokeWidth="6" />
                    <circle
                      cx="34"
                      cy="34"
                      r="26"
                      className="kpi-ring-fill"
                      strokeWidth="6"
                      stroke="#10b981"
                      strokeDasharray={circumference}
                      strokeDashoffset={offset}
                      strokeLinecap="round"
                      transform="rotate(-90 34 34)"
                    />
                  </svg>
                  <span className="kpi-radial-center-text">{pct}%</span>
                </div>
                <div className="kpi-radial-info">
                  <span className="kpi-main-val">{formatVnd(spent)}</span>
                  <span className="kpi-sub-val">Hạn mức: {formatVnd(target)}</span>
                </div>
              </div>
              <p className="kpi-footnote">Đã chi cho thuốc GPP, khám Booking Care và xét nghiệm trong kỳ.</p>
            </div>
          );
        })()}

        {/* KPI 2: Quỹ BHYT Đã Thanh Toán */}
        {(() => {
          const bhytPaid = assessment?.bhyt_paid_vnd || Math.round((breakdown.total_spent_vnd || 2450000) * 0.45);
          const bhytRate = 80; // 80% đúng tuyến
          const circumference = 2 * Math.PI * 26;
          const offset = circumference * (1 - bhytRate / 100);
          return (
            <div className="kpi-card kpi-radial-card">
              <div className="kpi-card-header">
                <span className="kpi-label">Quỹ BHYT Đã Thanh Toán</span>
                <span className="kpi-pill cyan">80% BHYT</span>
              </div>
              <div className="kpi-radial-body">
                <div className="kpi-radial-svg-wrap">
                  <svg width="68" height="68" viewBox="0 0 68 68">
                    <circle cx="34" cy="34" r="26" className="kpi-ring-track" strokeWidth="6" />
                    <circle
                      cx="34"
                      cy="34"
                      r="26"
                      className="kpi-ring-fill"
                      strokeWidth="6"
                      stroke="#00e5ff"
                      strokeDasharray={circumference}
                      strokeDashoffset={offset}
                      strokeLinecap="round"
                      transform="rotate(-90 34 34)"
                    />
                  </svg>
                  <span className="kpi-radial-center-text">80%</span>
                </div>
                <div className="kpi-radial-info">
                  <span className="kpi-main-val" style={{ color: '#00e5ff' }}>+{formatVnd(bhytPaid)}</span>
                  <span className="kpi-sub-val">Bảo hiểm xã hội chi trả</span>
                </div>
              </div>
              <p className="kpi-footnote">Tiền khám và thuốc nằm trong danh mục thanh toán BHYT đúng tuyến.</p>
            </div>
          );
        })()}

        {/* KPI 3: Điểm Tối Ưu Giá Thị Trường (DAV) */}
        {(() => {
          const score = assessment?.market_optimization_score ?? 92;
          const circumference = 2 * Math.PI * 26;
          const offset = circumference * (1 - score / 100);
          return (
            <div className="kpi-card kpi-radial-card">
              <div className="kpi-card-header">
                <span className="kpi-label">Điểm Tối Ưu Giá (DAV)</span>
                <span className="kpi-pill rank">Bộ Y Tế</span>
              </div>
              <div className="kpi-radial-body">
                <div className="kpi-radial-svg-wrap">
                  <svg width="68" height="68" viewBox="0 0 68 68">
                    <circle cx="34" cy="34" r="26" className="kpi-ring-track" strokeWidth="6" />
                    <circle
                      cx="34"
                      cy="34"
                      r="26"
                      className="kpi-ring-fill"
                      strokeWidth="6"
                      stroke="#34d399"
                      strokeDasharray={circumference}
                      strokeDashoffset={offset}
                      strokeLinecap="round"
                      transform="rotate(-90 34 34)"
                    />
                  </svg>
                  <span className="kpi-radial-center-text">{score}</span>
                </div>
                <div className="kpi-radial-info">
                  <span className="kpi-main-val" style={{ color: '#34d399' }}>{score}/100</span>
                  <span className="kpi-sub-val">Đúng trần kê khai DAV</span>
                </div>
              </div>
              <p className="kpi-footnote">100% thuốc mua tại chuỗi GPP đúng khung giá niêm yết Cục Quản Lý Dược.</p>
            </div>
          );
        })()}

        {/* KPI 4: Tiềm Năng Tiết Kiệm Generic EU-GMP */}
        {(() => {
          const potential = assessment?.eu_gmp_saving_potential_vnd ?? 420000;
          const genericRate = 35; // 35% cost reduction
          const circumference = 2 * Math.PI * 26;
          const offset = circumference * (1 - genericRate / 100);
          return (
            <div className="kpi-card kpi-radial-card">
              <div className="kpi-card-header">
                <span className="kpi-label">Tiết Kiệm Generic EU-GMP</span>
                <span className="kpi-pill rank">Nhóm 1</span>
              </div>
              <div className="kpi-radial-body">
                <div className="kpi-radial-svg-wrap">
                  <svg width="68" height="68" viewBox="0 0 68 68">
                    <circle cx="34" cy="34" r="26" className="kpi-ring-track" strokeWidth="6" />
                    <circle
                      cx="34"
                      cy="34"
                      r="26"
                      className="kpi-ring-fill"
                      strokeWidth="6"
                      stroke="#a855f7"
                      strokeDasharray={circumference}
                      strokeDashoffset={offset}
                      strokeLinecap="round"
                      transform="rotate(-90 34 34)"
                    />
                  </svg>
                  <span className="kpi-radial-center-text">35%</span>
                </div>
                <div className="kpi-radial-info">
                  <span className="kpi-main-val" style={{ color: '#c084fc' }}>+{formatVnd(potential)}</span>
                  <span className="kpi-sub-val">Tiết kiệm khi đổi biệt dược</span>
                </div>
              </div>
              <p className="kpi-footnote">Chuyển sang thuốc Generic tương đương sinh học EU-GMP giữ nguyên hiệu lực.</p>
            </div>
          );
        })()}
      </section>

      {/* --------------------------------------------------------------------
          3.5 SEGMENTED SUB-NAVIGATION (CHUYỂN ĐỔI CHẾ ĐỘ XEM THÔNG MINH)
          -------------------------------------------------------------------- */}
      <section className="segmented-subnav-section" aria-label="Phân hệ nghiệp vụ">
        <div className="segmented-subnav-tabs" role="tablist">
          <button
            type="button"
            className={`subnav-tab-btn ${activeSubView === 'all' ? 'active' : ''}`}
            onClick={() => setActiveSubView('all')}
          >
            <Layers size={15} />
            <span>Tất cả phân hệ</span>
          </button>
          <button
            type="button"
            className={`subnav-tab-btn ${activeSubView === 'ocr_market' ? 'active' : ''}`}
            onClick={() => setActiveSubView('ocr_market')}
          >
            <FileScan size={15} />
            <span>1. Đọc Hóa Đơn OCR & Thị Trường</span>
          </button>
          <button
            type="button"
            className={`subnav-tab-btn ${activeSubView === 'product_search' ? 'active' : ''}`}
            onClick={() => setActiveSubView('product_search')}
          >
            <Search size={15} />
            <span>2. Tìm Sản Phẩm Ảnh & Agent Uy Tín</span>
          </button>
          <button
            type="button"
            className={`subnav-tab-btn ${activeSubView === 'tickets_faq' ? 'active' : ''}`}
            onClick={() => setActiveSubView('tickets_faq')}
          >
            <HelpCircle size={15} />
            <span>3. Phân Loại Ticket & Gợi Ý Câu Hỏi</span>
          </button>
        </div>
      </section>

      {/* --------------------------------------------------------------------
          4. BIỂU ĐỒ DONUT SVG PHÂN BỔ CHI TIÊU & ĐỐI SÁNH 4 KHÍA CẠNH THỊ TRƯỜNG
          -------------------------------------------------------------------- */}
      {(activeSubView === 'all' || activeSubView === 'ocr_market') && (
        <section className="donut-market-section">
          <div className="donut-market-grid">
            {/* Left: SVG Donut Chart */}
            <div className="donut-chart-card">
              <div className="donut-card-header">
                <div className="card-title-group">
                  <PieChart size={17} style={{ color: '#00e5ff' }} />
                  <h4>Biểu Đồ Donut Phân Bổ Tỷ Trọng Chi Tiêu</h4>
                </div>
                <span className="donut-total-badge">Tháng 10/2026</span>
              </div>

              <div className="donut-visual-wrap">
                <svg width="180" height="180" viewBox="0 0 180 180" className="spending-donut-svg">
                  {/* Outer segments: 45% (meds), 35% (doctor), 12% (lab), 8% (supplies) */}
                  {/* Circumference = 2 * PI * 65 = 408.4 */}
                  <circle cx="90" cy="90" r="65" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="22" />
                  {/* Segment 1: Thuốc kê đơn & GPP (45% = 183.78) */}
                  <circle
                    cx="90"
                    cy="90"
                    r="65"
                    fill="none"
                    stroke="#10b981"
                    strokeWidth="22"
                    strokeDasharray="183.78 224.62"
                    strokeDashoffset="0"
                    transform="rotate(-90 90 90)"
                  />
                  {/* Segment 2: Khám Booking Care (35% = 142.94) */}
                  <circle
                    cx="90"
                    cy="90"
                    r="65"
                    fill="none"
                    stroke="#00e5ff"
                    strokeWidth="22"
                    strokeDasharray="142.94 265.46"
                    strokeDashoffset="-183.78"
                    transform="rotate(-90 90 90)"
                  />
                  {/* Segment 3: Xét nghiệm Cận lâm sàng (12% = 49.0) */}
                  <circle
                    cx="90"
                    cy="90"
                    r="65"
                    fill="none"
                    stroke="#f59e0b"
                    strokeWidth="22"
                    strokeDasharray="49.0 359.4"
                    strokeDashoffset="-326.72"
                    transform="rotate(-90 90 90)"
                  />
                  {/* Segment 4: Vật tư y tế (8% = 32.67) */}
                  <circle
                    cx="90"
                    cy="90"
                    r="65"
                    fill="none"
                    stroke="#a855f7"
                    strokeWidth="22"
                    strokeDasharray="32.67 375.73"
                    strokeDashoffset="-375.72"
                    transform="rotate(-90 90 90)"
                  />
                </svg>
                <div className="donut-center-legend">
                  <span className="donut-center-label">Tổng Chi</span>
                  <strong className="donut-center-amt">{formatVnd(breakdown.total_spent_vnd || 2450000)}</strong>
                </div>
              </div>

              {/* Donut Legend */}
              <div className="donut-legend-grid">
                <div className="donut-legend-item">
                  <span className="legend-dot" style={{ backgroundColor: '#10b981' }} />
                  <span className="legend-name">Thuốc GPP chuẩn: <strong>45%</strong></span>
                </div>
                <div className="donut-legend-item">
                  <span className="legend-dot" style={{ backgroundColor: '#00e5ff' }} />
                  <span className="legend-name">Khám Booking Care: <strong>35%</strong></span>
                </div>
                <div className="donut-legend-item">
                  <span className="legend-dot" style={{ backgroundColor: '#f59e0b' }} />
                  <span className="legend-name">Xét nghiệm cận lâm sàng: <strong>12%</strong></span>
                </div>
                <div className="donut-legend-item">
                  <span className="legend-dot" style={{ backgroundColor: '#a855f7' }} />
                  <span className="legend-name">Vật tư y tế & Khác: <strong>8%</strong></span>
                </div>
              </div>
            </div>

            {/* Right: Đối Sánh 4 Khía Cạnh Thị Trường Y Tế (DAV & Generic EU-GMP) */}
            <div className="market-benchmark-card">
              <div className="benchmark-card-header">
                <div className="card-title-group">
                  <Coins size={17} style={{ color: '#34d399' }} />
                  <h4>Đối Sánh 4 Khía Cạnh Thị Trường & BHYT (DAV Benchmark)</h4>
                </div>
                <span className="benchmark-source-tag">Cục Quản Lý Dược (DAV)</span>
              </div>

              <div className="benchmark-table-wrap">
                <table className="benchmark-comparison-table">
                  <thead>
                    <tr>
                      <th>Hạng mục dịch vụ</th>
                      <th>Giá mua thực tế</th>
                      <th>Trần niêm yết DAV</th>
                      <th>Generic EU-GMP</th>
                      <th>Độ tối ưu</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>
                        <strong>Thuốc Esomeprazole 40mg</strong>
                        <span className="table-sub">Kháng tiết acid dạ dày (Nexium / Generic)</span>
                      </td>
                      <td>24.000 ₫/viên</td>
                      <td>24.500 ₫/viên</td>
                      <td style={{ color: '#34d399' }}>14.500 ₫/viên</td>
                      <td><span className="table-badge optimal">Tiết kiệm 40%</span></td>
                    </tr>
                    <tr>
                      <td>
                        <strong>Thuốc Augmentin 1g</strong>
                        <span className="table-sub">Kháng sinh Amoxicillin/Acid clavulanic</span>
                      </td>
                      <td>21.000 ₫/viên</td>
                      <td>21.800 ₫/viên</td>
                      <td style={{ color: '#34d399' }}>13.200 ₫/viên</td>
                      <td><span className="table-badge optimal">Chuẩn DAV</span></td>
                    </tr>
                    <tr>
                      <td>
                        <strong>Khám Chuyên Khoa Tiêu Hóa</strong>
                        <span className="table-sub">Booking Care BV Đại học Y Dược</span>
                      </td>
                      <td>150.000 ₫/lượt</td>
                      <td>150.000 ₫/lượt</td>
                      <td>BHYT: 38.700 ₫</td>
                      <td><span className="table-badge bhyt">Hưởng 80% BHYT</span></td>
                    </tr>
                    <tr>
                      <td>
                        <strong>Xét nghiệm Men Gan (AST/ALT)</strong>
                        <span className="table-sub">Đánh giá tác động chuyển hóa thuốc</span>
                      </td>
                      <td>85.000 ₫</td>
                      <td>90.000 ₫</td>
                      <td>BHYT đúng tuyến</td>
                      <td><span className="table-badge optimal">Đúng giá</span></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* --------------------------------------------------------------------
          4.5 THANH TIẾN TRÌNH KIỂM ĐỊNH UY TÍN OPEN-SOURCE (WILSON SCORE, SPAM NLP, EIGENTRUST)
          -------------------------------------------------------------------- */}
      {(activeSubView === 'all' || activeSubView === 'product_search') && (
        <section className="product-trust-section">
          <div className="product-trust-header">
            <div className="trust-title-group">
              <Award size={18} style={{ color: '#00e5ff' }} />
              <div>
                <h4>Kiểm Định Uy Tín Sản Phẩm Y Tế & Nhà Cung Cấp Chuẩn Open-Source</h4>
                <p className="trust-subtitle">
                  Tích hợp bộ ba thuật toán chuẩn: Wilson Score 95% CI (độ tin cậy đánh giá), SpamReviewDetector NLP (lọc bình luận rác) và EigenTrust (uy tín mạng lưới GPP).
                </p>
              </div>
            </div>
          </div>

          <div className="product-trust-cards-grid">
            {[
              {
                id: 'prod_1',
                name: 'Thuốc Nexium 40mg (Esomeprazole AstraZeneca)',
                desc: 'Thuốc ức chế bơm proton (PPI) điều trị viêm loét dạ dày - tá tràng và trào ngược dạ dày thực quản.',
                price: '480.000 ₫ / Hộp 14 viên',
                genericAlternative: 'Esomeprazole Stada 40mg EU-GMP (Tiết kiệm 160.000 ₫)',
                positiveReviews: 482,
                totalReviews: 510,
                spamDetectedRate: 1.4,
                eigenTrustPeers: [0.95, 0.98, 0.94, 0.97],
                category: 'Dạ Dày & Tiêu Hóa',
              },
              {
                id: 'prod_2',
                name: 'Kháng sinh Augmentin 1g (Amoxicillin/Acid clavulanic GSK)',
                desc: 'Kháng sinh phổ rộng chính hãng điều trị nhiễm khuẩn đường hô hấp trên và dưới.',
                price: '294.000 ₫ / Hộp 14 viên',
                genericAlternative: 'Klamentin 1g Dược Hậu Giang EU-GMP (Tiết kiệm 98.000 ₫)',
                positiveReviews: 318,
                totalReviews: 345,
                spamDetectedRate: 2.1,
                eigenTrustPeers: [0.92, 0.94, 0.91, 0.96],
                category: 'Hô Hấp & Kháng Sinh',
              },
              {
                id: 'prod_3',
                name: 'Thuốc Giảm Đau Panadol Extra (Paracetamol 500mg + Caffeine 65mg)',
                desc: 'Giảm đau đầu, đau nửa đầu, đau cơ khớp do cảm sốt. Không kích ứng niêm mạc dạ dày.',
                price: '185.000 ₫ / Hộp 180 viên',
                genericAlternative: 'Hapacol 650mg Dược Hậu Giang (Tiết kiệm 45.000 ₫)',
                positiveReviews: 890,
                totalReviews: 920,
                spamDetectedRate: 0.8,
                eigenTrustPeers: [0.96, 0.98, 0.97, 0.99],
                category: 'Thần Kinh & Giảm Đau',
              },
              {
                id: 'prod_4',
                name: 'Phosphalugel (Gel Nhôm Phosphat 20%)',
                desc: 'Thuốc dạ dày chữ P dạng gel kháng acid bảo vệ niêm mạc thượng vị, giảm nóng rát tức thì.',
                price: '115.000 ₫ / Hộp 26 gói',
                genericAlternative: 'Alumag Gel đạt chuẩn GPP (Tiết kiệm 30.000 ₫)',
                positiveReviews: 412,
                totalReviews: 430,
                spamDetectedRate: 1.2,
                eigenTrustPeers: [0.94, 0.95, 0.93, 0.96],
                category: 'Dạ Dày & Kháng Acid',
              },
            ].map((prod) => {
              const wilsonScore = calculateWilsonScore(prod.positiveReviews, prod.totalReviews, 0.95);
              const wilsonPct = Math.round(wilsonScore * 1000) / 10;
              const realReviewPct = Math.round((100 - prod.spamDetectedRate) * 10) / 10;
              const eigenTrustScore = calculateEigenTrust(prod.eigenTrustPeers);

              return (
                <div key={prod.id} className="product-trust-card">
                  <div className="product-card-top">
                    <span className="product-category-tag">{prod.category}</span>
                    <span className="product-price-badge">{prod.price}</span>
                  </div>

                  <h5 className="product-name">{prod.name}</h5>
                  <p className="product-desc">{prod.desc}</p>

                  <div className="generic-suggestion-box">
                    <Sparkles size={13} style={{ color: '#34d399' }} />
                    <span>Lựa chọn Generic: <strong>{prod.genericAlternative}</strong></span>
                  </div>

                  {/* 3 Trust Metrics */}
                  <div className="trust-metrics-stack">
                    {/* Wilson Score 95% CI */}
                    <div className="trust-metric-row">
                      <div className="metric-title-wrap">
                        <span className="metric-name">Wilson Score 95% CI:</span>
                        <strong className="metric-val" style={{ color: '#00e5ff' }}>{wilsonPct}%</strong>
                      </div>
                      <div className="trust-bar-track">
                        <div className="trust-bar-fill wilson" style={{ width: `${wilsonPct}%` }} />
                      </div>
                    </div>

                    {/* SpamReviewDetector NLP */}
                    <div className="trust-metric-row">
                      <div className="metric-title-wrap">
                        <span className="metric-name">NLP Đánh Giá Thật:</span>
                        <strong className="metric-val" style={{ color: '#10b981' }}>{realReviewPct}%</strong>
                      </div>
                      <div className="trust-bar-track">
                        <div className="trust-bar-fill nlp" style={{ width: `${realReviewPct}%` }} />
                      </div>
                    </div>

                    {/* EigenTrust */}
                    <div className="trust-metric-row">
                      <div className="metric-title-wrap">
                        <span className="metric-name">EigenTrust Nhà Thuốc:</span>
                        <strong className="metric-val" style={{ color: '#a855f7' }}>{eigenTrustScore} / 1.0</strong>
                      </div>
                      <div className="trust-bar-track">
                        <div className="trust-bar-fill eigentrust" style={{ width: `${eigenTrustScore * 100}%` }} />
                      </div>
                    </div>
                  </div>

                  <div className="product-card-actions">
                    <button
                      type="button"
                      className="prod-action-btn primary"
                      onClick={() => {
                        if (onNotify) onNotify(`Đã tra cứu đối sánh giá niêm yết DAV cho ${prod.name}!`, 'info');
                      }}
                    >
                      <Tag size={13} />
                      <span>Tra cứu giá DAV</span>
                    </button>
                    <button
                      type="button"
                      className="prod-action-btn"
                      onClick={() => {
                        onNavigate?.('chat');
                        window.dispatchEvent(
                          new CustomEvent('medguard:navigate', {
                            detail: {
                              view: 'chat',
                              message: `Tư vấn kinh tế dược học về thuốc ${prod.name} và thuốc Generic EU-GMP thay thế tương đương.`,
                            },
                          })
                        );
                      }}
                    >
                      <MessageSquare size={13} />
                      <span>Hỏi Dược sĩ AI</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* --------------------------------------------------------------------
          4.8 PHÂN LOẠI TICKET & GỢI Ý CÂU HỎI TIẾT KIỆM CHI PHÍ
          -------------------------------------------------------------------- */}
      {(activeSubView === 'all' || activeSubView === 'tickets_faq') && (
        <section className="tickets-faq-section">
          <div className="tickets-faq-header">
            <div className="card-title-group">
              <HelpCircle size={17} style={{ color: '#00e5ff' }} />
              <h4>Phân Loại Ticket & Câu Hỏi Gợi Ý Tiết Kiệm Chi Phí</h4>
            </div>
            <span className="tickets-count-badge">4 Nhóm nghiệp vụ</span>
          </div>

          <div className="tickets-grid">
            {[
              {
                id: 'ticket_bhyt',
                title: 'Hỏi đáp hưởng BHYT đúng tuyến khi khám Booking Care',
                category: 'BHYT & Viện Phí',
                icon: ShieldCheck,
                color: '#00e5ff',
                faq: 'Làm thế nào để được hưởng 80% BHYT khi đặt lịch khám chuyên khoa qua Booking Care?',
                suggestedAction: 'Xin giấy chuyển tuyến từ cơ sở y tế ban đầu (trạm y tế phường/BV quận) để được BHYT chi trả 80-100%.',
              },
              {
                id: 'ticket_generic',
                title: 'Tra cứu thuốc Generic EU-GMP thay thế biệt dược gốc đắt tiền',
                category: 'Kinh Tế Dược',
                icon: Sparkles,
                color: '#34d399',
                faq: 'Đơn thuốc kê Nexium 40mg đắt quá, có thể yêu cầu nhà thuốc bán thuốc Generic tương đương sinh học không?',
                suggestedAction: 'Theo Thông tư Bộ Y Tế, người bệnh có quyền đề nghị dược sĩ tư vấn thuốc Generic cùng hoạt chất nhóm 1 EU-GMP tiết kiệm 30-40%.',
              },
              {
                id: 'ticket_ocr',
                title: 'Xác thực giá hóa đơn nhà thuốc so với bảng kê khai DAV',
                category: 'Kiểm Soát Giá',
                icon: FileScan,
                color: '#f59e0b',
                faq: 'Làm sao để biết nhà thuốc có bán chênh lệch so với giá kê khai của Cục Quản Lý Dược không?',
                suggestedAction: 'Chụp ảnh hóa đơn tải lên MedGuard OCR; hệ thống tự động đối chiếu giá niêm yết DAV mã thuốc quốc gia.',
              },
              {
                id: 'ticket_adr',
                title: 'Chi phí đổi thuốc khi gặp tác dụng phụ dạ dày do NSAID',
                category: 'An Toàn Lâm Sàng',
                icon: AlertTriangle,
                color: '#ef4444',
                faq: 'Uống thuốc giảm đau bị đau dạ dày thì chi phí xử trí và đổi thuốc thay thế có tốn kém không?',
                suggestedAction: 'Dừng ngay thuốc NSAID, dùng gói Phosphalugel hoặc Paracetamol chi phí rất thấp (dưới 30.000 ₫) và bảo vệ niêm mạc an toàn.',
              },
            ].map((t) => {
              const Icon = t.icon;
              return (
                <div key={t.id} className="ticket-card" style={{ '--ticket-accent': t.color }}>
                  <div className="ticket-top">
                    <span className="ticket-category-pill" style={{ color: t.color, backgroundColor: `${t.color}18` }}>
                      <Icon size={12} />
                      <span>{t.category}</span>
                    </span>
                  </div>
                  <h5 className="ticket-title">{t.title}</h5>
                  <p className="ticket-faq"><strong>Hỏi:</strong> {t.faq}</p>
                  <p className="ticket-action"><strong>Giải pháp:</strong> {t.suggestedAction}</p>
                  <button
                    type="button"
                    className="ticket-ask-btn"
                    onClick={() => {
                      onNavigate?.('chat');
                      window.dispatchEvent(
                        new CustomEvent('medguard:navigate', {
                          detail: { view: 'chat', message: t.faq },
                        })
                      );
                    }}
                  >
                    <MessageSquare size={12} />
                    <span>Hỏi AI về chủ đề này</span>
                  </button>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* --------------------------------------------------------------------
          5. TWO-COLUMN DASHBOARD GRID
          -------------------------------------------------------------------- */}
      <div className="dashboard-main-grid">
        {/* LEFT COLUMN: Clinical Economics Battlecard & Smart Actions */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Battlecard: GPP vs Unofficial Sources */}
          <section className="dash-panel">
            <div className="dash-panel-header">
              <div className="panel-title-wrap">
                <Layers size={18} style={{ color: '#34d399' }} />
                <h2 className="panel-title">So Sánh Kinh Tế Y Khoa: Thuốc Chuẩn GPP vs. Thuốc Liều Lẻ</h2>
              </div>
            </div>

            <div className="battlecard-shell">
              <div className="battlecard-header">
                <BadgeCheck size={16} />
                <span>BÀI TOÁN KINH TẾ Y KHOA: TẠI SAO THUỐC CHUẨN GPP THỰC TẾ RẺ HƠN NHIỀU LẦN?</span>
              </div>

              <div className="battlecard-grid">
                {/* Column 1: GPP */}
                <div className="battle-column gpp">
                  <div className="battle-col-title">
                    <CheckCircle2 size={16} />
                    <span>Thuốc Chuẩn GPP Chính Hãng</span>
                  </div>

                  <div className="battle-row">
                    <span className="battle-row-label">Dược chất & Nồng độ MIC</span>
                    <span className="battle-row-val">
                      Chuẩn GMP/WHO, sinh khả dụng đồng đều, đạt nồng độ ức chế MIC tiêu diệt mầm bệnh dứt điểm sau{' '}
                      <strong>5–7 ngày</strong>.
                    </span>
                  </div>

                  <div className="battle-row">
                    <span className="battle-row-label">Chi phí điều trị thực tế</span>
                    <span className="battle-row-val">
                      Giá niêm yết minh bạch (~380k trọn gói). <strong>1 lần dứt điểm</strong>, không tái khám nhiều lần.
                    </span>
                  </div>

                  <div className="battle-row">
                    <span className="battle-row-label">An toàn & Pháp lý</span>
                    <span className="battle-row-val">
                      Có hóa đơn VAT, kiểm định Bộ Y tế, có dược sĩ lâm sàng tư vấn tương tác thuốc bảo vệ gan thận.
                    </span>
                  </div>
                </div>

                {/* Column 2: Unofficial */}
                <div className="battle-column unofficial">
                  <div className="battle-col-title">
                    <AlertTriangle size={16} />
                    <span>Thuốc Liều Lẻ / Tiệm Tự Do</span>
                  </div>

                  <div className="battle-row">
                    <span className="battle-row-label">Dược chất & Nồng độ MIC</span>
                    <span className="battle-row-val">
                      Thường chia liều cắt lẻ không nhãn mác, bảo quản kém làm suy giảm hoạt chất, dẫn đến vi khuẩn kháng thuốc (AMR).
                    </span>
                  </div>

                  <div className="battle-row">
                    <span className="battle-row-label">Chi phí điều trị thực tế</span>
                    <span className="battle-row-val">
                      Tưởng rẻ (40k–80k/đợt) nhưng phải mua <strong>3–5 đợt kéo dài</strong>, tổng tiền tốn &gt; 500k kèm nguy cơ nhập viện.
                    </span>
                  </div>

                  <div className="battle-row">
                    <span className="battle-row-label">An toàn & Pháp lý</span>
                    <span className="battle-row-val">
                      Không rõ hạn dùng, dễ bị phối hợp Corticoid/kháng sinh bừa bãi gây đau dạ dày cấp và suy thượng thận.
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* Actionable Recommendations */}
          <section className="dash-panel">
            <div className="dash-panel-header">
              <div className="panel-title-wrap">
                <Sparkles size={18} style={{ color: '#00e5ff' }} />
                <h2 className="panel-title">Khuyến Nghị Tối Ưu Hóa Chi Phí Chăm Sóc Sức Khỏe</h2>
              </div>
              <span className="panel-badge">{recs.length} giải pháp</span>
            </div>

            <div className="rec-cards-stack">
              {recs.map((rec) => (
                <div key={rec.id} className="rec-item-card">
                  <div className="rec-item-top">
                    <div className="rec-title-heading">
                      <span className={`priority-indicator ${rec.priority}`} title={`Mức ưu tiên: ${rec.priority}`} />
                      <h3 className="rec-title-text">{rec.title}</h3>
                    </div>
                    {rec.estimated_savings_vnd > 0 && (
                      <span className="rec-saving-tag">Tiết kiệm ~{formatVnd(rec.estimated_savings_vnd)}</span>
                    )}
                  </div>

                  <p className="rec-body-text">{rec.description}</p>

                  <div className="rec-rationale-strip">
                    <strong style={{ color: '#e2e8f0' }}>Cơ sở y khoa & kinh tế: </strong>
                    {rec.clinical_rationale}
                  </div>

                  {rec.action_cta && (
                    <div className="rec-cta-container">
                      <button
                        type="button"
                        className="rec-action-button"
                        onClick={() => {
                          if (rec.target_view && onNavigate) {
                            onNavigate(rec.target_view);
                          } else if (onBackToChat) {
                            onBackToChat();
                          }
                        }}
                      >
                        <span>{rec.action_cta}</span>
                        <ChevronRight size={14} />
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        </div>

        {/* RIGHT COLUMN: Transaction Ledger Stream */}
        <section className="dash-panel">
          <div className="dash-panel-header">
            <div className="panel-title-wrap">
              <Coins size={18} style={{ color: '#f59e0b' }} />
              <h2 className="panel-title">Nhật Ký Chi Tiêu Y Tế</h2>
            </div>
            <span className="panel-badge">{filteredTransactions.length} khoản</span>
          </div>

          {/* Ledger Filter Chips */}
          <div className="ledger-filter-row">
            <button
              type="button"
              className={`filter-chip ${filterType === 'all' ? 'active' : ''}`}
              onClick={() => setFilterType('all')}
            >
              Tất cả ({allTransactions.length})
            </button>
            <button
              type="button"
              className={`filter-chip ${filterType === 'gpp' ? 'active' : ''}`}
              onClick={() => setFilterType('gpp')}
            >
              Chuẩn GPP
            </button>
            <button
              type="button"
              className={`filter-chip ${filterType === 'waste' ? 'active' : ''}`}
              onClick={() => setFilterType('waste')}
            >
              Tái phát / Lãng phí
            </button>
            <button
              type="button"
              className={`filter-chip ${filterType === 'doctor' ? 'active' : ''}`}
              onClick={() => setFilterType('doctor')}
            >
              Khám bác sĩ
            </button>
          </div>

          {/* Ledger Stream */}
          <div className="ledger-stream">
            {filteredTransactions.map((tx) => {
              const isWaste = tx.recurrence_flag || tx.category === 'recurrence_treatment';
              const isGpp = tx.is_official_gpp;

              return (
                <div
                  key={tx.id}
                  className={`ledger-row ${isWaste ? 'recurrence' : isGpp ? 'gpp' : ''}`}
                >
                  <div className="ledger-left">
                    <div className={`ledger-icon-badge ${isWaste ? 'waste' : isGpp ? 'gpp' : 'doctor'}`}>
                      {tx.category === 'doctor_visit' ? (
                        <CalendarCheck size={16} />
                      ) : (
                        <Pill size={16} />
                      )}
                    </div>

                    <div className="ledger-details">
                      <p className="ledger-item-title">{tx.title}</p>
                      <div className="ledger-meta">
                        <span>{tx.date}</span>
                        <span>•</span>
                        <span className="ledger-source-name">{tx.source_name}</span>
                      </div>
                      {tx.clinical_notes && (
                        <span style={{ fontSize: '0.73rem', color: '#64748b', fontStyle: 'italic', marginTop: '2px' }}>
                          {tx.clinical_notes}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="ledger-right">
                    <span className={`ledger-amount ${isWaste ? 'waste' : ''}`}>
                      {formatVnd(tx.amount_vnd)}
                    </span>
                    <span className={`ledger-status-tag ${isWaste ? 'waste' : 'gpp'}`}>
                      {isWaste ? 'Lãng phí tái phát' : isGpp ? 'Chuẩn GPP' : 'Tự do'}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      </div>

      {/* --------------------------------------------------------------------
          6. CLINICAL SAFETY GATE TEST SIMULATOR MODAL
          -------------------------------------------------------------------- */}
      {showSimulator && (
        <div className="modal-overlay" onClick={() => setShowSimulator(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-dialog-header">
              <h3>
                <ShieldCheck size={20} style={{ color: '#00e5ff' }} />
                Kiểm Thử Cổng Kiểm Soát An Toàn Y Khoa AI (Safety Gate)
              </h3>
              <button
                type="button"
                className="modal-close-icon"
                onClick={() => setShowSimulator(false)}
              >
                <X size={18} />
              </button>
            </div>

            <p style={{ fontSize: '0.86rem', color: '#94a3b8', margin: 0, lineHeight: 1.45 }}>
              Cổng an toàn 3 lớp kiểm soát để AI <strong>tuyệt đối không bao giờ</strong> đưa ra lời khuyên trì hoãn khám bệnh
              hoặc không mua thuốc nhằm "tiết kiệm chi phí" khi người dùng có các dấu hiệu nguy hiểm tiềm ẩn (Red Flags).
            </p>

            <div className="modal-form-group">
              <label>Câu hỏi / Mô tả triệu chứng của người dùng (Thử nghiệm dấu hiệu Red Flag):</label>
              <textarea
                className="modal-input modal-textarea"
                value={simUserMsg}
                onChange={(e) => setSimUserMsg(e.target.value)}
              />
            </div>

            <div className="modal-form-group">
              <label>Câu trả lời dự kiến ban đầu của AI (Thử nghiệm câu trấn an sai lầm):</label>
              <textarea
                className="modal-input modal-textarea"
                value={simProposed}
                onChange={(e) => setSimProposed(e.target.value)}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button
                type="button"
                className="dash-btn primary"
                onClick={handleRunSafetyGateTest}
                disabled={simLoading}
              >
                <Sparkles size={14} />
                <span>{simLoading ? 'Đang thẩm định...' : 'Chạy Thẩm Định An Toàn'}</span>
              </button>
            </div>

            {simResult && (
              <div
                style={{
                  background: 'rgba(2, 6, 23, 0.85)',
                  borderRadius: '10px',
                  padding: '14px',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  fontSize: '0.84rem',
                  lineHeight: 1.5,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <strong>Kết quả thẩm định:</strong>
                  <span
                    style={{
                      fontSize: '0.76rem',
                      fontWeight: 800,
                      padding: '2px 8px',
                      borderRadius: '4px',
                      background: simResult.safety_status?.is_safe ? 'rgba(16,185,129,0.2)' : 'rgba(244,63,94,0.2)',
                      color: simResult.safety_status?.is_safe ? '#34d399' : '#fb7185',
                    }}
                  >
                    {simResult.safety_status?.safety_tier?.toUpperCase()}
                  </span>
                </div>

                {simResult.safety_status?.red_flags_detected?.length > 0 && (
                  <div style={{ marginBottom: '8px', color: '#fb7185' }}>
                    <strong>Cờ đỏ phát hiện: </strong>
                    {simResult.safety_status.red_flags_detected.join('; ')}
                  </div>
                )}

                <div>
                  <strong style={{ color: '#38bdf8' }}>Lời khuyên sau khi Cổng An Toàn can thiệp / hiệu chỉnh:</strong>
                  <p style={{ margin: '6px 0 0', color: '#f1f5f9', whiteSpace: 'pre-wrap' }}>
                    {simResult.revised_advice}
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* --------------------------------------------------------------------
          7. MANUAL ADD EXPENSE MODAL
          -------------------------------------------------------------------- */}
      {showAddTx && (
        <div className="modal-overlay" onClick={() => setShowAddTx(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-dialog-header">
              <h3>
                <Plus size={20} style={{ color: '#10b981' }} />
                Ghi Nhận Khoản Chi Y Tế Mới
              </h3>
              <button type="button" className="modal-close-icon" onClick={() => setShowAddTx(false)}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleAddTransaction} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div className="modal-form-group">
                <label>Tên khoản chi / Mục đích điều trị *:</label>
                <input
                  type="text"
                  className="modal-input"
                  value={txTitle}
                  onChange={(e) => setTxTitle(e.target.value)}
                  placeholder="Ví dụ: Đơn thuốc kháng sinh 7 ngày, Khám Hô hấp Booking Care..."
                  required
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div className="modal-form-group">
                  <label>Số tiền (VNĐ) *:</label>
                  <input
                    type="number"
                    className="modal-input"
                    value={txAmount}
                    onChange={(e) => setTxAmount(e.target.value)}
                    required
                  />
                </div>

                <div className="modal-form-group">
                  <label>Nguồn mua / Nơi cung cấp:</label>
                  <select
                    className="modal-input"
                    value={txSourceType}
                    onChange={(e) => {
                      setTxSourceType(e.target.value);
                      if (e.target.value === 'gpp_pharmacy') setTxSourceName('Nhà thuốc Long Châu chuẩn GPP');
                      else if (e.target.value === 'hospital_clinic') setTxSourceName('Bệnh viện / Phòng khám');
                      else setTxSourceName('Tiệm thuốc tự do (Liều lẻ)');
                    }}
                  >
                    <option value="gpp_pharmacy">Chuỗi nhà thuốc chuẩn GPP (Long Châu, Pharmacity...)</option>
                    <option value="hospital_clinic">Bệnh viện / Phòng khám Booking Care</option>
                    <option value="unofficial_retail">Tiệm thuốc tự do (Chia liều lẻ)</option>
                    <option value="online_unknown">Mua mạng không rõ xuất xứ</option>
                  </select>
                </div>
              </div>

              <div className="modal-form-group">
                <label>Tên nhà thuốc / Cơ sở cụ thể:</label>
                <input
                  type="text"
                  className="modal-input"
                  value={txSourceName}
                  onChange={(e) => setTxSourceName(e.target.value)}
                />
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <input
                  type="checkbox"
                  id="chk-dash-recurrence"
                  checked={txRecurrence}
                  onChange={(e) => setTxRecurrence(e.target.checked)}
                  style={{ width: '16px', height: '16px', accentColor: '#f43f5e' }}
                />
                <label htmlFor="chk-dash-recurrence" style={{ fontSize: '0.84rem', color: '#cbd5e1', cursor: 'pointer' }}>
                  Đây là khoản chi do <strong>tái phát bệnh / mua thêm liều do chưa khỏi</strong>
                </label>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                <button
                  type="button"
                  className="dash-btn"
                  onClick={() => setShowAddTx(false)}
                >
                  Hủy
                </button>
                <button type="submit" className="dash-btn primary">
                  <Plus size={14} />
                  <span>Lưu Khoản Chi</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* --------------------------------------------------------------------
          MODAL: EDIT MONTHLY HEALTHCARE BUDGET TARGET
          -------------------------------------------------------------------- */}
      {showBudgetModal && (
        <div className="spending-modal-backdrop" onClick={() => setShowBudgetModal(false)}>
          <div className="spending-modal-card budget-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-dialog-header">
              <h3>
                <Target size={20} style={{ color: '#00e5ff' }} />
                <span>Thiết Lập Hạn Mức Ngân Sách Y Tế Tháng</span>
              </h3>
              <button
                type="button"
                className="modal-close-icon"
                onClick={() => setShowBudgetModal(false)}
              >
                <X size={18} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '16px' }}>
              <p style={{ margin: 0, fontSize: '0.85rem', color: '#94a3b8', lineHeight: 1.5 }}>
                Đặt hạn mức chi tiêu tối đa mỗi tháng cho việc mua thuốc và khám chữa bệnh. MedGuard AI sẽ tính toán tỷ lệ phân bổ dòng tiền tối ưu (45% Khám Booking Care & BHYT, 35% Thuốc chuẩn GPP, 20% Dự phòng) theo chuẩn kinh tế dược học.
              </p>

              <div className="modal-form-group">
                <label>Hạn mức ngân sách tối đa (VNĐ):</label>
                <input
                  type="number"
                  step="100000"
                  min="100000"
                  max="500000000"
                  className="modal-input"
                  value={budgetValue}
                  onChange={(e) => setBudgetValue(e.target.value)}
                  placeholder="Ví dụ: 3000000"
                  required
                />
              </div>

              {/* Quick Preset Buttons */}
              <div className="budget-presets-row">
                <span className="presets-label">Chọn nhanh:</span>
                {[1500000, 2000000, 3000000, 5000000].map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    className={`preset-pill ${parseInt(budgetValue, 10) === preset ? 'active' : ''}`}
                    onClick={() => setBudgetValue(String(preset))}
                  >
                    {formatVnd(preset)}
                  </button>
                ))}
              </div>

              <div
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '10px',
                  background: 'rgba(0, 229, 255, 0.06)',
                  border: '1px solid rgba(0, 229, 255, 0.2)',
                  borderRadius: '10px',
                  padding: '10px 12px',
                  fontSize: '0.8rem',
                  color: '#cbd5e1',
                  lineHeight: 1.45,
                }}
              >
                <ShieldCheck size={16} style={{ color: '#00e5ff', flexShrink: 0, marginTop: '2px' }} />
                <span>
                  <strong>Cam kết an toàn tuyệt đối:</strong> MedGuard AI không bao giờ khuyên bạn cắt giảm thuốc kê đơn hay trì hoãn việc đi khám bác sĩ chỉ để giữ chỉ tiêu ngân sách.
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '6px' }}>
                <button
                  type="button"
                  className="dash-btn"
                  onClick={() => setShowBudgetModal(false)}
                >
                  Hủy
                </button>
                <button
                  type="button"
                  className="dash-btn primary"
                  onClick={() => handleSetBudget()}
                  disabled={budgetSaving}
                >
                  {budgetSaving ? (
                    <>
                      <RefreshCw size={14} className="spin" />
                      <span>Đang lưu...</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 size={14} />
                      <span>Lưu Hạn Mức {formatVnd(parseInt(budgetValue, 10) || 0)}</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
