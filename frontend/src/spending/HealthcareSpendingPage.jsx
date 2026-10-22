import { useEffect, useState, useCallback, useMemo } from 'react';
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  BadgeCheck,
  CalendarCheck,
  CheckCircle2,
  ChevronRight,
  Coins,
  DollarSign,
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
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  Target,
  TrendingDown,
  TrendingUp,
  WalletCards,
  Edit3,
  X,
} from 'lucide-react';
import './HealthcareSpendingPage.css';

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
  const [assessment, setAssessment] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filterType, setFilterType] = useState('all'); // 'all', 'gpp', 'waste', 'doctor'

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
  const [budgetValue, setBudgetValue] = useState('3000000');
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
        const data = await makeRequest(`/v1/financial/assessment?patient_ref=${encodeURIComponent(patientRef)}`);
        setAssessment(data);
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
      if (chatData?.answer?.financial_assessment_update?.assessment) {
        setAssessment(chatData.answer.financial_assessment_update.assessment);
        if (onNotify) {
          onNotify('Đã tự động cập nhật sổ chi tiêu từ hội thoại chat!', 'info');
        }
      } else {
        void fetchAssessment(true);
      }
    };

    window.addEventListener('medguard:financial-updated', handleFinancialUpdate);
    return () => {
      window.removeEventListener('medguard:financial-updated', handleFinancialUpdate);
    };
  }, [fetchAssessment, onNotify]);

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
      const updated = await makeRequest('/v1/financial/set-budget', {
        method: 'POST',
        body: {
          patient_ref: patientRef,
          budget_target_vnd: amt,
        },
      });
      setAssessment(updated);
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
          3. HIGH-IMPACT DASHBOARD KPI METRIC CARDS
          -------------------------------------------------------------------- */}
      <section className="kpi-metrics-grid">
        {/* KPI 1: Total Spent */}
        <div className="kpi-card">
          <div className="kpi-card-header">
            <span className="kpi-label">Tổng Chi Y Tế Tháng</span>
            <div className="kpi-icon-container total">
              <WalletCards size={18} />
            </div>
          </div>
          <div className="kpi-number-row">
            <span className="kpi-main-val">{formatVnd(breakdown.total_spent_vnd)}</span>
          </div>
          <p className="kpi-footnote">Đã chi cho thuốc, khám bác sĩ Booking Care và xét nghiệm trong kỳ.</p>
        </div>

        {/* KPI 2: Recurrence Waste (The core problem in Vietnam) */}
        <div className="kpi-card">
          <div className="kpi-card-header">
            <span className="kpi-label">Lãng Phí Do Bệnh Tái Phát</span>
            <div className="kpi-icon-container waste">
              <TrendingDown size={18} />
            </div>
          </div>
          <div className="kpi-number-row">
            <span className="kpi-main-val" style={{ color: '#fb7185' }}>
              {formatVnd(breakdown.recurrence_waste_spent_vnd)}
            </span>
            <span className="kpi-pill danger">{breakdown.recurrence_waste_percentage}% Nguy cơ</span>
          </div>
          <p className="kpi-footnote">Tiền mua thuốc lẻ nhiều đợt không dứt điểm, vi khuẩn kháng thuốc (AMR).</p>
        </div>

        {/* KPI 3: Treatment Efficiency Score (TES) */}
        <div className="kpi-card">
          <div className="kpi-card-header">
            <span className="kpi-label">Điểm Hiệu Quả Điều Trị (TES)</span>
            <div className="kpi-icon-container tes">
              <Activity size={18} />
            </div>
          </div>
          <div className="kpi-number-row">
            <span className="kpi-main-val" style={{ color: '#d8b4fe' }}>
              {tes} <span style={{ fontSize: '0.95rem', color: '#94a3b8' }}>/ 100</span>
            </span>
            <span className="kpi-pill rank">Hạng {roiRank}</span>
          </div>
          <p className="kpi-footnote">Tỷ lệ khỏi bệnh dứt điểm ngay từ đầu bằng nguồn thuốc chính hãng chuẩn GPP.</p>
        </div>

        {/* KPI 4: Projected Monthly Savings */}
        <div className="kpi-card">
          <div className="kpi-card-header">
            <span className="kpi-label">Tiết Kiệm Khả Thi / Tháng</span>
            <div className="kpi-icon-container savings">
              <TrendingUp size={18} />
            </div>
          </div>
          <div className="kpi-number-row">
            <span className="kpi-main-val" style={{ color: '#34d399' }}>
              +{formatVnd(assessment?.projected_monthly_savings_vnd)}
            </span>
            <span className="kpi-pill success">Khả thi cao</span>
          </div>
          <p className="kpi-footnote">Tiết kiệm được khi dứt điểm bệnh đợt 1 và khám BHYT đúng tuyến cơ sở.</p>
        </div>
      </section>

      {/* --------------------------------------------------------------------
          4. CASHFLOW BREAKDOWN STRIP (VISUAL BUDGET BAR)
          -------------------------------------------------------------------- */}
      <section className="cashflow-strip-card">
        <div className="cashflow-strip-header">
          <div className="cashflow-title">
            <PieChart size={16} style={{ color: '#00e5ff' }} />
            <span>Cơ cấu phân bổ dòng tiền y tế tháng 10/2026</span>
          </div>
          <div className="cashflow-stats">
            <span>Tổng chi: <strong>{formatVnd(breakdown.total_spent_vnd)}</strong></span>
          </div>
        </div>

        {/* Segmented Progress Bar */}
        <div className="cashflow-progress-bar" title="Cơ cấu chi tiêu y tế">
          <div
            className="cashflow-segment gpp"
            style={{ width: `${Math.max(15, gppPct)}%` }}
            title={`Thuốc GPP Chuẩn: ${formatVnd(breakdown.gpp_official_spent_vnd)}`}
          />
          <div
            className="cashflow-segment waste"
            style={{ width: `${Math.max(10, wastePct)}%` }}
            title={`Lãng phí do mua lẻ tái phát: ${formatVnd(breakdown.recurrence_waste_spent_vnd)}`}
          />
          <div
            className="cashflow-segment booking"
            style={{ width: `${Math.max(10, bookingPct)}%` }}
            title={`Khám chuyên khoa & Xét nghiệm: ${formatVnd(breakdown.doctor_booking_spent_vnd)}`}
          />
        </div>

        {/* Legend */}
        <div className="cashflow-legend">
          <div className="legend-item">
            <span className="legend-color-dot gpp" />
            <span>Chuỗi GPP chính hãng: <strong>{formatVnd(breakdown.gpp_official_spent_vnd)}</strong></span>
          </div>
          <div className="legend-item">
            <span className="legend-color-dot waste" />
            <span style={{ color: '#fb7185' }}>
              Lãng phí mua lẻ tái phát: <strong>{formatVnd(breakdown.recurrence_waste_spent_vnd)}</strong>
            </span>
          </div>
          <div className="legend-item">
            <span className="legend-color-dot booking" />
            <span>Khám Booking Care & BHYT: <strong>{formatVnd(breakdown.doctor_booking_spent_vnd)}</strong></span>
          </div>
        </div>
      </section>

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
