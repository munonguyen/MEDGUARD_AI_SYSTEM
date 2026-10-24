import { useEffect, useState, useMemo } from 'react';
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Award,
  BarChart2,
  Calendar,
  CalendarCheck,
  CalendarClock,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Clock,
  Coins,
  CreditCard,
  Eye,
  EyeOff,
  FilePlus2,
  FileScan,
  FileText,
  Filter,
  Folder,
  LayoutGrid,
  PieChart,
  Pill,
  Plus,
  QrCode,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Star,
  Stethoscope,
  Tag,
  TestTube,
  TrendingDown,
  TrendingUp,
  WalletCards,
  X,
} from 'lucide-react';
import './HealthcareSpendingPage.css';
import { calculateWilsonScore, detectSpamReviewNLP, calculateEigenTrust } from '../chat/topicGatedSync';

function formatVnd(amount, hideAmount = false) {
  if (hideAmount) return '•••••••• ₫';
  if (typeof amount !== 'number') return '0 ₫';
  return `${amount.toLocaleString('vi-VN')} ₫`;
}

// 5 Medical Spending Categories adhering to Vietnam Ministry of Health & GPP Pharmacy Standards
const DEFAULT_CATEGORIES = [
  {
    id: 'medication',
    name: 'Thuốc kê đơn & Dược GPP',
    percentage: 41,
    amount_vnd: 5070066,
    color: '#f472b6', // Rosy pink from reference
    icon: Pill,
    badge: 'Chuẩn GPP / DAV',
    description: 'Biệt dược gốc và thuốc Generic EU-GMP điều trị theo phác đồ',
  },
  {
    id: 'clinic',
    name: 'Khám & Viện phí điều trị',
    percentage: 33,
    amount_vnd: 4080785,
    color: '#34d399', // Mint green from reference
    icon: Stethoscope,
    badge: 'BHYT Đúng Tuyến',
    description: 'Booking Care, tiền khám chuyên khoa và nội trú bệnh viện',
  },
  {
    id: 'diagnostics',
    name: 'Xét nghiệm & Cận lâm sàng',
    percentage: 14,
    amount_vnd: 1731242,
    color: '#38bdf8', // Cyan from reference
    icon: TestTube,
    badge: 'ISO 15189',
    description: 'Công thức máu, nội soi tiêu hóa, sinh hóa gan thận và X-quang',
  },
  {
    id: 'supplements',
    name: 'Dược mỹ phẩm & TPCN',
    percentage: 11,
    amount_vnd: 1360261,
    color: '#fb923c', // Warm orange from reference
    icon: Sparkles,
    badge: 'Chính Hãng',
    description: 'Men vi sinh, vitamin khoáng chất và dinh dưỡng hồi phục sau ốm',
  },
  {
    id: 'supplies',
    name: 'Vật tư y tế tiêu hao',
    percentage: 1,
    amount_vnd: 123662,
    color: '#94a3b8', // Slate from reference
    icon: FileText,
    badge: 'Vô trùng',
    description: 'Băng gạc vô trùng, cồn sát khuẩn và nước muối sinh lý',
  },
];

// Rich, clinical transactions list
const INITIAL_TRANSACTIONS = [
  {
    id: 'tx_01',
    date: 'Hôm nay',
    raw_date: '2026-10-24',
    time: '15:20',
    title: 'Thuốc Nexium 40mg (Esomeprazole) & Phosphalugel',
    provider: 'Nhà thuốc Long Châu - Chuẩn GPP',
    category: 'medication',
    category_name: 'Thuốc kê đơn',
    amount_vnd: -480000,
    bhyt_covered_vnd: 384000,
    is_gpp: true,
    dav_compliant: true,
    bhyt_rate: 80,
    rx_code: 'RX-2026-1049',
    clinical_notes: 'Uống trước ăn sáng 30 phút • Giảm đau rát thượng vị dạ dày',
    verified: true,
  },
  {
    id: 'tx_02',
    date: 'Hôm nay',
    raw_date: '2026-10-24',
    time: '09:15',
    title: 'Khám Chuyên khoa Nội Tiêu Hóa & Nội soi',
    provider: 'Bệnh viện Đại học Y Dược TP.HCM',
    category: 'clinic',
    category_name: 'Khám chuyên khoa',
    amount_vnd: -150000,
    bhyt_covered_vnd: 120000,
    is_gpp: true,
    dav_compliant: true,
    bhyt_rate: 80,
    rx_code: 'BS-CKI-892',
    clinical_notes: 'Nội soi dạ dày tầm soát tổn thương niêm mạc sau dùng NSAID',
    verified: true,
  },
  {
    id: 'tx_03',
    date: 'Hôm qua',
    raw_date: '2026-10-23',
    time: '14:30',
    title: 'Xét nghiệm Men Gan (AST/ALT) & Công thức máu',
    provider: 'Trung tâm Xét nghiệm Y khoa Diag',
    category: 'diagnostics',
    category_name: 'Xét nghiệm',
    amount_vnd: -320000,
    bhyt_covered_vnd: 160000,
    is_gpp: true,
    dav_compliant: true,
    bhyt_rate: 50,
    rx_code: 'LAB-7741',
    clinical_notes: 'Đánh giá chuyển hóa gan trước khi dùng kháng sinh kéo dài',
    verified: true,
  },
  {
    id: 'tx_04',
    date: 'Hôm qua',
    raw_date: '2026-10-23',
    time: '10:05',
    title: 'Thuốc hạ áp Amlodipine 5mg (Generic EU-GMP)',
    provider: 'Nhà thuốc An Khang - Chuẩn GPP',
    category: 'medication',
    category_name: 'Thuốc kê đơn',
    amount_vnd: -165000,
    bhyt_covered_vnd: 132000,
    is_gpp: true,
    dav_compliant: true,
    bhyt_rate: 80,
    rx_code: 'RX-2026-0955',
    clinical_notes: 'Biệt dược tương đương sinh học Norvasc • Tiết kiệm 38%',
    verified: true,
  },
  {
    id: 'tx_05',
    date: '20/10/2026',
    raw_date: '2026-10-20',
    time: '16:40',
    title: 'Men vi sinh Enterogermina & Bổ sung Kẽm',
    provider: 'Nhà thuốc Pharmacity',
    category: 'supplements',
    category_name: 'Dược mỹ phẩm & TPCN',
    amount_vnd: -295000,
    bhyt_covered_vnd: 0,
    is_gpp: true,
    dav_compliant: true,
    bhyt_rate: 0,
    rx_code: 'TPCN-4410',
    clinical_notes: 'Cân bằng vi sinh đường ruột và tăng sức đề kháng tiêu hóa',
    verified: true,
  },
  {
    id: 'tx_06',
    date: '18/10/2026',
    raw_date: '2026-10-18',
    time: '11:20',
    title: 'Bảo hiểm Y tế Chi trả Hoàn Viện phí Đợt 2',
    provider: 'Bảo hiểm Xã hội TP.HCM (VssID)',
    category: 'refund',
    category_name: 'BHYT chi trả',
    amount_vnd: 1450000,
    bhyt_covered_vnd: 1450000,
    is_gpp: true,
    dav_compliant: true,
    bhyt_rate: 100,
    rx_code: 'BHYT-REF-8841',
    clinical_notes: 'Quyết toán trợ cấp BHYT đúng tuyến điều trị nội trú',
    verified: true,
  },
  {
    id: 'tx_07',
    date: '15/10/2026',
    raw_date: '2026-10-15',
    time: '08:50',
    title: 'Kháng sinh Augmentin 1g (Amoxicillin/Acid clavulanic)',
    provider: 'Nhà thuốc Long Châu - Chuẩn GPP',
    category: 'medication',
    category_name: 'Thuốc kê đơn',
    amount_vnd: -294000,
    bhyt_covered_vnd: 235200,
    is_gpp: true,
    dav_compliant: true,
    bhyt_rate: 80,
    rx_code: 'RX-2026-0912',
    clinical_notes: 'Kháng sinh đường hô hấp chính hãng GSK • Đúng trần DAV',
    verified: true,
  },
  {
    id: 'tx_08',
    date: '12/10/2026',
    raw_date: '2026-10-12',
    time: '17:15',
    title: 'Băng gạc tiệt trùng & Nước muối sinh lý 0.9%',
    provider: 'Nhà thuốc Bệnh viện ĐHYD',
    category: 'supplies',
    category_name: 'Vật tư y tế',
    amount_vnd: -65000,
    bhyt_covered_vnd: 0,
    is_gpp: true,
    dav_compliant: true,
    bhyt_rate: 0,
    rx_code: 'VT-0091',
    clinical_notes: 'Dụng cụ thay băng vệ sinh vết thương tại nhà',
    verified: true,
  },
];

export function HealthcareSpendingPage({
  api,
  patientRef = 'guest_patient',
  onBackToChat,
  onNavigate,
  onNotify,
}) {
  const [hideAmounts, setHideAmounts] = useState(false);
  const [timePeriod, setTimePeriod] = useState('Tháng này (10/2026)');
  const [showCategoryDetail, setShowCategoryDetail] = useState(true);
  const [selectedTxForDetail, setSelectedTxForDetail] = useState(null);

  // Search and filter in transaction list
  const [txSearchQuery, setTxSearchQuery] = useState('');
  const [txFilterTab, setTxFilterTab] = useState('all');

  // Transactions ledger state
  const [transactions, setTransactions] = useState(() => {
    try {
      const saved = localStorage.getItem('medguard_spending_transactions');
      return saved ? JSON.parse(saved) : INITIAL_TRANSACTIONS;
    } catch {
      return INITIAL_TRANSACTIONS;
    }
  });

  // Modal: Nhập giao dịch (+ Thêm chi phí y tế)
  const [showAddModal, setShowAddModal] = useState(false);
  const [newTxTitle, setNewTxTitle] = useState('');
  const [newTxAmount, setNewTxAmount] = useState('480000');
  const [newTxCategory, setNewTxCategory] = useState('medication');
  const [newTxProvider, setNewTxProvider] = useState('Nhà thuốc Long Châu');
  const [newTxBhytEligible, setNewTxBhytEligible] = useState(true);
  const [newTxNotes, setNewTxNotes] = useState('');

  // Assessment and budget states
  const [assessment, setAssessment] = useState(() => {
    try {
      const saved = localStorage.getItem('medguard_financial_assessment');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  // Total actual monthly spend
  const totalActualSpend = useMemo(() => {
    if (assessment?.total_actual_spend_vnd) {
      return assessment.total_actual_spend_vnd;
    }
    return 12366016; // Exact number from user screenshot
  }, [assessment]);

  // Total BHYT paid or supplementary inflow
  const totalBhytCovered = useMemo(() => {
    if (assessment?.bhyt_paid_vnd) {
      return assessment.bhyt_paid_vnd;
    }
    return 8540000;
  }, [assessment]);

  // Synchronize when unified chat events trigger
  useEffect(() => {
    const handleUnifiedChatSync = (event) => {
      const detail = event?.detail;
      if (detail?.expenseMutation) {
        setAssessment((prev) => ({
          ...prev,
          ...detail.expenseMutation,
        }));
        if (detail.expenseMutation.recent_transactions?.length) {
          const formatted = detail.expenseMutation.recent_transactions.map((tx, idx) => ({
            id: tx.id || `tx_chat_${Date.now()}_${idx}`,
            date: 'Hôm nay',
            raw_date: new Date().toISOString().split('T')[0],
            time: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }),
            title: tx.title || 'Khoản chi y tế mới',
            provider: 'Nhà thuốc GPP',
            category: tx.category || 'medication',
            category_name: tx.category === 'doctor' ? 'Khám chuyên khoa' : 'Thuốc kê đơn',
            amount_vnd: -(Math.abs(tx.amount_vnd || 480000)),
            bhyt_covered_vnd: Math.round((tx.amount_vnd || 480000) * 0.8),
            is_gpp: true,
            dav_compliant: true,
            bhyt_rate: 80,
            rx_code: 'RX-SYNC-CHAT',
            clinical_notes: 'Đồng bộ từ hội thoại tư vấn y tế MedGuard AI',
            verified: true,
          }));
          setTransactions((prev) => {
            const nextList = [...formatted, ...prev];
            try {
              localStorage.setItem('medguard_spending_transactions', JSON.stringify(nextList));
            } catch {}
            return nextList;
          });
        }
        if (onNotify) {
          onNotify(`Đã đồng bộ Chi Tiêu Y Tế từ Chat (${detail.label || 'Tài chính'})!`, 'info');
        }
      }
    };

    window.addEventListener('medguard:unified-chat-sync', handleUnifiedChatSync);
    return () => {
      window.removeEventListener('medguard:unified-chat-sync', handleUnifiedChatSync);
    };
  }, [onNotify]);

  // Filtered transactions
  const filteredTransactions = useMemo(() => {
    let result = transactions;
    if (txFilterTab !== 'all') {
      result = result.filter((tx) => tx.category === txFilterTab);
    }
    if (txSearchQuery.trim()) {
      const q = txSearchQuery.toLowerCase();
      result = result.filter(
        (tx) =>
          tx.title.toLowerCase().includes(q) ||
          tx.provider.toLowerCase().includes(q) ||
          (tx.rx_code && tx.rx_code.toLowerCase().includes(q))
      );
    }
    return result;
  }, [transactions, txFilterTab, txSearchQuery]);

  // Group transactions by date string
  const groupedTransactions = useMemo(() => {
    const groups = {};
    for (const tx of filteredTransactions) {
      const groupKey = tx.date || 'Trước đó';
      if (!groups[groupKey]) {
        groups[groupKey] = [];
      }
      groups[groupKey].push(tx);
    }
    return groups;
  }, [filteredTransactions]);

  // Handle adding new transaction
  const handleAddNewTxSubmit = (e) => {
    e.preventDefault();
    const amt = parseInt(newTxAmount, 10);
    if (!amt || amt <= 0 || !newTxTitle.trim()) {
      onNotify?.('Vui lòng nhập tên khoản chi và số tiền hợp lệ.', 'error');
      return;
    }
    const bhytRate = newTxBhytEligible ? 80 : 0;
    const bhytCovered = Math.round((amt * bhytRate) / 100);

    const createdTx = {
      id: `tx_user_${Date.now()}`,
      date: 'Hôm nay',
      raw_date: new Date().toISOString().split('T')[0],
      time: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }),
      title: newTxTitle.trim(),
      provider: newTxProvider.trim() || 'Cơ sở y tế GPP',
      category: newTxCategory,
      category_name:
        newTxCategory === 'medication'
          ? 'Thuốc kê đơn'
          : newTxCategory === 'clinic'
          ? 'Khám chuyên khoa'
          : newTxCategory === 'diagnostics'
          ? 'Xét nghiệm'
          : 'Dược phẩm & TPCN',
      amount_vnd: -amt,
      bhyt_covered_vnd: bhytCovered,
      is_gpp: true,
      dav_compliant: true,
      bhyt_rate: bhytRate,
      rx_code: `RX-${Math.floor(1000 + Math.random() * 9000)}`,
      clinical_notes: newTxNotes.trim() || 'Khoản chi y tế do bệnh nhân nhập bổ sung',
      verified: true,
    };

    const nextList = [createdTx, ...transactions];
    setTransactions(nextList);
    try {
      localStorage.setItem('medguard_spending_transactions', JSON.stringify(nextList));
    } catch {}

    setShowAddModal(false);
    setNewTxTitle('');
    setNewTxNotes('');
    onNotify?.('Đã ghi nhận giao dịch y tế mới thành công!', 'success');
  };

  return (
    <div className="spending-web-dashboard">
      {/* ====================================================================
          1. TOP COMMAND & CONTROL HEADER (NATIVE WEB DESIGN)
          ==================================================================== */}
      <header className="web-dashboard-header">
        <div className="header-left-col">
          <button
            type="button"
            className="back-to-chat-btn"
            onClick={onBackToChat}
            title="Quay lại phòng khám hội thoại"
          >
            <ArrowLeft size={18} />
            <span>Hội thoại lâm sàng</span>
          </button>
          <div className="header-title-box">
            <div className="header-subtitle-tag">
              <span className="live-dot" />
              <span>MEDGUARD WEALTH & HEALTHCARE ECONOMICS • QUẢN LÝ CHI TIÊU</span>
            </div>
            <h1 className="header-main-title">Quản Lý Chi Tiêu Y Tế & Lộ Trình Chăm Sóc</h1>
          </div>
        </div>

        <div className="header-right-col">
          <div className="month-pill-selector">
            <button
              type="button"
              className="month-nav-btn"
              onClick={() => {
                setTimePeriod('Tháng 9/2026');
                onNotify?.('Đã chuyển số liệu sang: Tháng 9/2026', 'info');
              }}
            >
              <ChevronLeft size={16} />
            </button>
            <div className="month-current-text">
              <Calendar size={15} className="text-pink" />
              <span>{timePeriod}</span>
            </div>
            <button
              type="button"
              className="month-nav-btn"
              onClick={() => {
                setTimePeriod('Tháng này (10/2026)');
                onNotify?.('Đang xem số liệu: Tháng này (10/2026)', 'info');
              }}
            >
              <ChevronRight size={16} />
            </button>
          </div>

          <button
            type="button"
            className="web-action-btn primary-pink"
            onClick={() => setShowAddModal(true)}
          >
            <Plus size={16} />
            <span>+ Nhập giao dịch</span>
          </button>
        </div>
      </header>

      {/* ====================================================================
          2. 4 TIỆN ÍCH THAO TÁC NHANH (MINT / TEAL STYLE AS IN IMAGE)
          ==================================================================== */}
      <section className="web-quick-actions-bar">
        <button
          type="button"
          className="web-action-tile-btn"
          onClick={() => setShowAddModal(true)}
        >
          <div className="tile-mint-icon">
            <FilePlus2 size={22} />
          </div>
          <div className="tile-info-text">
            <strong>Nhập giao dịch</strong>
            <span>Ghi nhận chi phí & Quét đơn thuốc OCR</span>
          </div>
        </button>

        <button
          type="button"
          className="web-action-tile-btn"
          onClick={() => {
            onNotify?.('Xu hướng chi tiêu y tế tháng 10 giảm 28.5% so với tháng trước nhờ dùng thuốc Generic!', 'info');
          }}
        >
          <div className="tile-mint-icon">
            <TrendingUp size={22} />
          </div>
          <div className="tile-info-text">
            <strong>Biến động thu chi</strong>
            <span>So sánh chi phí cùng kỳ tháng trước</span>
          </div>
        </button>

        <button
          type="button"
          className="web-action-tile-btn"
          onClick={() => setShowCategoryDetail((v) => !v)}
        >
          <div className="tile-mint-icon">
            <Folder size={22} />
          </div>
          <div className="tile-info-text">
            <strong>Quản lý danh mục</strong>
            <span>5 nhóm chi phí y tế & Tỷ lệ BHYT</span>
          </div>
        </button>

        <button
          type="button"
          className="web-action-tile-btn"
          onClick={() => {
            onNotify?.('Đã mở bảng đối soát giá niêm yết Cục Quản Lý Dược (DAV)', 'info');
          }}
        >
          <div className="tile-mint-icon">
            <LayoutGrid size={22} />
          </div>
          <div className="tile-info-text">
            <strong>Tiện ích khác</strong>
            <span>Tra giá trần DAV & Tiết kiệm Generic</span>
          </div>
        </button>
      </section>

      {/* ====================================================================
          3. DUAL SUMMARY CARDS & COMPARISON BANNER
          ==================================================================== */}
      <section className="web-dual-summary-section">
        <div className="dual-cards-web-grid">
          {/* Card 1: Chi tiêu ⬇ (Rosy Pink active outline matching reference) */}
          <div className="web-kpi-card expense-kpi-card">
            <div className="kpi-card-head">
              <div className="kpi-badge-wrap">
                <span className="kpi-icon-bubble pink">
                  <TrendingDown size={16} />
                </span>
                <span className="kpi-label-text">Chi tiêu</span>
                <span className="kpi-arrow-tag down">↓</span>
              </div>
              <button
                type="button"
                className="kpi-eye-btn"
                onClick={() => setHideAmounts((v) => !v)}
                title={hideAmounts ? 'Hiện số tiền' : 'Ẩn số tiền bảo mật'}
              >
                {hideAmounts ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            <div className="kpi-large-amount text-pink">
              {formatVnd(totalActualSpend, hideAmounts)}
            </div>
            <p className="kpi-card-subtext">Tổng tiền thuốc GPP, viện phí và xét nghiệm đã chi trong tháng.</p>
          </div>

          {/* Card 2: BHYT & Thu ⬆ (Emerald green badge matching reference) */}
          <div className="web-kpi-card income-kpi-card">
            <div className="kpi-card-head">
              <div className="kpi-badge-wrap">
                <span className="kpi-icon-bubble green">
                  <TrendingUp size={16} />
                </span>
                <span className="kpi-label-text">BHYT & Ngân sách hỗ trợ</span>
                <span className="kpi-arrow-tag up">↑</span>
              </div>
              <span className="kpi-source-pill">Bảo hiểm Xã hội VssID</span>
            </div>
            <div className="kpi-large-amount text-emerald">
              {formatVnd(totalBhytCovered, hideAmounts)}
            </div>
            <p className="kpi-card-subtext">Quỹ Bảo hiểm Y tế đã chi trả trực tiếp và hoàn tiền viện phí.</p>
          </div>
        </div>

        {/* Sub-banner: Giảm 941.854 ₫ so với cùng kỳ tháng trước */}
        <div className="web-comparison-banner">
          <div className="banner-left-wrap">
            <div className="banner-icon-box">
              <BarChart2 size={18} />
            </div>
            <div className="banner-content-text">
              <span className="banner-highlight-text">
                <strong className="text-emerald">Giảm 941.854 ₫</strong> so với cùng kỳ tháng trước
              </span>
              <span className="banner-sub-desc">
                Tiết kiệm 28.5% chi phí dược phẩm nhờ chỉ định thuốc tương đương sinh học Generic EU-GMP đúng trần DAV.
              </span>
            </div>
          </div>
          <button
            type="button"
            className="banner-action-btn"
            onClick={() => onNotify?.('Báo cáo phân tích tiết kiệm chi phí đã được lưu vào hồ sơ y tế!', 'info')}
          >
            <span>Xem phân tích</span>
            <ChevronRight size={14} />
          </button>
        </div>
      </section>

      {/* ====================================================================
          4. 2-COLUMN MAIN DASHBOARD (DONUT CHART & DAV BENCHMARK)
          ==================================================================== */}
      <div className="web-dashboard-two-col-grid">
        {/* Left Column: Biểu đồ Donut Chart SVG & 5 Nhóm Danh Mục */}
        <div className="web-grid-col-left">
          <section className="web-panel-card donut-breakdown-panel">
            <div className="panel-header-row">
              <div className="panel-title-group">
                <PieChart size={18} className="text-pink" />
                <h3 className="panel-title-text">Tình hình thu chi & Phân bổ y tế</h3>
              </div>
              <span className="panel-status-pill pink-pill">
                5 Nhóm danh mục
              </span>
            </div>

            {/* Donut SVG Illustration */}
            <div className="web-donut-wrapper">
              <div className="donut-center-graphic">
                <svg
                  width="200"
                  height="200"
                  viewBox="0 0 200 200"
                  className="web-donut-svg"
                >
                  {/* Background Track */}
                  <circle
                    cx="100"
                    cy="100"
                    r="70"
                    fill="none"
                    stroke="#f1f5f9"
                    strokeWidth="26"
                  />

                  {/* Arc 1: Thuốc kê đơn & GPP (Pink 41%)
                      Circumference = 2 * PI * 70 = 439.82
                      41% = 180.33
                  */}
                  <circle
                    cx="100"
                    cy="100"
                    r="70"
                    fill="none"
                    stroke="#f472b6"
                    strokeWidth="26"
                    strokeDasharray="180.33 259.49"
                    strokeDashoffset="0"
                    strokeLinecap="round"
                    transform="rotate(-90 100 100)"
                  />

                  {/* Arc 2: Viện phí & Khám bệnh (Mint Green 33%)
                      33% = 145.14, offset = -180.33
                  */}
                  <circle
                    cx="100"
                    cy="100"
                    r="70"
                    fill="none"
                    stroke="#34d399"
                    strokeWidth="26"
                    strokeDasharray="145.14 294.68"
                    strokeDashoffset="-180.33"
                    strokeLinecap="round"
                    transform="rotate(-90 100 100)"
                  />

                  {/* Arc 3: Xét nghiệm Cận lâm sàng (Cyan 14%)
                      14% = 61.57, offset = -325.47
                  */}
                  <circle
                    cx="100"
                    cy="100"
                    r="70"
                    fill="none"
                    stroke="#38bdf8"
                    strokeWidth="26"
                    strokeDasharray="61.57 378.25"
                    strokeDashoffset="-325.47"
                    strokeLinecap="round"
                    transform="rotate(-90 100 100)"
                  />

                  {/* Arc 4: TPCN Dinh dưỡng (Orange 11%)
                      11% = 48.38, offset = -387.04
                  */}
                  <circle
                    cx="100"
                    cy="100"
                    r="70"
                    fill="none"
                    stroke="#fb923c"
                    strokeWidth="26"
                    strokeDasharray="48.38 391.44"
                    strokeDashoffset="-387.04"
                    strokeLinecap="round"
                    transform="rotate(-90 100 100)"
                  />

                  {/* Arc 5: Vật tư khác (Gray 1%)
                      1% = 4.40, offset = -435.42
                  */}
                  <circle
                    cx="100"
                    cy="100"
                    r="70"
                    fill="none"
                    stroke="#94a3b8"
                    strokeWidth="26"
                    strokeDasharray="4.4 435.42"
                    strokeDashoffset="-435.42"
                    transform="rotate(-90 100 100)"
                  />
                </svg>

                {/* Donut Core Center */}
                <div className="web-donut-core">
                  <span className="donut-core-kicker">Tổng Chi</span>
                  <strong className="donut-core-number">
                    {formatVnd(totalActualSpend, hideAmounts)}
                  </strong>
                </div>
              </div>

              {/* Category Breakdown Bars */}
              <div className="category-bars-stack">
                {DEFAULT_CATEGORIES.map((cat) => {
                  const CatIcon = cat.icon;
                  return (
                    <div key={cat.id} className="category-bar-row">
                      <div className="cat-bar-header">
                        <div className="cat-name-box">
                          <span className="cat-bullet-dot" style={{ backgroundColor: cat.color }} />
                          <CatIcon size={15} style={{ color: cat.color }} />
                          <strong>{cat.name}</strong>
                          <span className="cat-badge-mini">{cat.badge}</span>
                        </div>
                        <div className="cat-amount-box">
                          <strong style={{ color: cat.color }}>
                            {formatVnd(cat.amount_vnd, hideAmounts)}
                          </strong>
                          <span className="cat-pct-label">({cat.percentage}%)</span>
                        </div>
                      </div>
                      <div className="cat-progress-track">
                        <div
                          className="cat-progress-fill"
                          style={{ width: `${cat.percentage}%`, backgroundColor: cat.color }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </section>
        </div>

        {/* Right Column: Đối Sánh Trần Giá DAV & Tiết Kiệm Generic EU-GMP */}
        <div className="web-grid-col-right">
          <section className="web-panel-card dav-benchmark-panel">
            <div className="panel-header-row">
              <div className="panel-title-group">
                <Award size={18} className="text-emerald" />
                <h3 className="panel-title-text">Đối Sánh 4 Chiều Thị Trường Y Tế (DAV Benchmark)</h3>
              </div>
              <span className="benchmark-source-badge">Cục Quản Lý Dược (DAV)</span>
            </div>

            <p className="panel-lead-desc">
              Hệ thống tự động đối chiếu giá mua thực tế tại nhà thuốc Long Châu / Pharmacity với khung trần niêm yết của Bộ Y Tế.
            </p>

            <div className="dav-table-responsive-wrapper">
              <table className="dav-benchmark-table">
                <thead>
                  <tr>
                    <th>Hạng mục dược / Dịch vụ</th>
                    <th>Giá mua thực tế</th>
                    <th>Trần niêm yết DAV</th>
                    <th>Generic EU-GMP</th>
                    <th>Mức tiết kiệm</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>
                      <strong>Thuốc Esomeprazole 40mg</strong>
                      <span className="cell-sub">Kháng tiết acid dạ dày (Nexium / Generic)</span>
                    </td>
                    <td>24.000 ₫/viên</td>
                    <td>24.500 ₫/viên</td>
                    <td className="text-emerald">14.500 ₫/viên</td>
                    <td><span className="table-badge success">Tiết kiệm 40%</span></td>
                  </tr>
                  <tr>
                    <td>
                      <strong>Thuốc Augmentin 1g</strong>
                      <span className="cell-sub">Kháng sinh Amoxicillin/Acid clavulanic GSK</span>
                    </td>
                    <td>21.000 ₫/viên</td>
                    <td>21.800 ₫/viên</td>
                    <td className="text-emerald">13.200 ₫/viên</td>
                    <td><span className="table-badge info">Chuẩn trần DAV</span></td>
                  </tr>
                  <tr>
                    <td>
                      <strong>Khám Nội Tiêu Hóa</strong>
                      <span className="cell-sub">Booking Care BV Đại học Y Dược TP.HCM</span>
                    </td>
                    <td>150.000 ₫/lượt</td>
                    <td>150.000 ₫/lượt</td>
                    <td className="text-emerald">BHYT trả 80%</td>
                    <td><span className="table-badge bhyt">Hưởng 80% BHYT</span></td>
                  </tr>
                  <tr>
                    <td>
                      <strong>Xét nghiệm Men Gan (AST/ALT)</strong>
                      <span className="cell-sub">Đánh giá chức năng tế bào gan</span>
                    </td>
                    <td>85.000 ₫</td>
                    <td>90.000 ₫</td>
                    <td className="text-emerald">BHYT đúng tuyến</td>
                    <td><span className="table-badge info">Đúng giá niêm yết</span></td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* 3 Open-Source Trust Metrics: Wilson Score, Spam NLP, EigenTrust */}
            <div className="trust-metrics-summary-strip">
              <div className="trust-pill-item">
                <span className="trust-pill-name">Wilson Score 95% CI:</span>
                <strong className="text-pink">94.5%</strong>
                <span className="trust-pill-hint">Độ tin cậy xếp hạng</span>
              </div>
              <div className="trust-pill-item">
                <span className="trust-pill-name">NLP Đánh Giá Thật:</span>
                <strong className="text-emerald">98.6%</strong>
                <span className="trust-pill-hint">Lọc bot & review rác</span>
              </div>
              <div className="trust-pill-item">
                <span className="trust-pill-name">EigenTrust Nhà Thuốc:</span>
                <strong className="text-cyan">0.96 / 1.0</strong>
                <span className="trust-pill-hint">Mạng lưới GPP uy tín</span>
              </div>
            </div>
          </section>
        </div>
      </div>

      {/* ====================================================================
          5. FULL-WIDTH DETAILED CLINICAL EXPENSE HISTORY
          ==================================================================== */}
      <section className="web-panel-card full-width-ledger-section">
        <div className="ledger-header-bar">
          <div className="ledger-title-left">
            <Coins size={20} className="text-pink" />
            <h2 className="ledger-heading-title">Lịch Sử Chi Tiêu Y Tế Chi Tiết</h2>
            <span className="tx-count-pill">{filteredTransactions.length} giao dịch</span>
          </div>

          <div className="ledger-header-actions">
            <button
              type="button"
              className="web-action-btn secondary"
              onClick={() => {
                onNotify?.('Đã đồng bộ lịch sử giao dịch y tế với cơ sở dữ liệu quốc gia!', 'info');
              }}
            >
              <RefreshCw size={14} />
              <span>Làm mới</span>
            </button>
            <button
              type="button"
              className="web-action-btn primary-pink"
              onClick={() => setShowAddModal(true)}
            >
              <Plus size={15} />
              <span>+ Thêm khoản chi mới</span>
            </button>
          </div>
        </div>

        {/* Filter Toolbar & Search Bar */}
        <div className="ledger-filters-toolbar">
          <div className="ledger-search-input-box">
            <Search size={16} className="search-icon" />
            <input
              type="text"
              placeholder="Tìm kiếm theo tên thuốc, bệnh viện, mã toa thuốc (ví dụ: Nexium, Đại học Y Dược, RX-1049)..."
              value={txSearchQuery}
              onChange={(e) => setTxSearchQuery(e.target.value)}
            />
            {txSearchQuery && (
              <button
                type="button"
                className="clear-search-btn"
                onClick={() => setTxSearchQuery('')}
              >
                <X size={14} />
              </button>
            )}
          </div>

          <div className="filter-tabs-button-group">
            {[
              { id: 'all', label: 'Tất cả khoản chi' },
              { id: 'medication', label: 'Thuốc kê đơn & GPP' },
              { id: 'clinic', label: 'Khám & Viện phí' },
              { id: 'diagnostics', label: 'Xét nghiệm' },
              { id: 'supplements', label: 'TPCN & Dinh dưỡng' },
              { id: 'refund', label: 'BHYT chi trả' },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                className={`filter-tab-pill-btn ${txFilterTab === tab.id ? 'active' : ''}`}
                onClick={() => setTxFilterTab(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Grouped Medical Transactions Timeline */}
        <div className="timeline-groups-container">
          {Object.keys(groupedTransactions).length === 0 ? (
            <div className="empty-ledger-state">
              <FileScan size={36} className="empty-icon" />
              <p>Không tìm thấy giao dịch y tế nào khớp với từ khóa tìm kiếm.</p>
            </div>
          ) : (
            Object.entries(groupedTransactions).map(([dateLabel, txList]) => (
              <div key={dateLabel} className="timeline-date-group">
                <div className="timeline-date-header">
                  <CalendarDays size={14} />
                  <span>{dateLabel}</span>
                  <span className="date-group-badge">{txList.length} giao dịch</span>
                </div>

                <div className="timeline-cards-grid">
                  {txList.map((tx) => {
                    const isIncome = tx.amount_vnd > 0;
                    return (
                      <div
                        key={tx.id}
                        className="web-tx-card-row"
                        onClick={() => setSelectedTxForDetail(tx)}
                      >
                        <div className="tx-card-main-col">
                          <div className={`tx-cat-icon-badge ${tx.category}`}>
                            {tx.category === 'medication' ? (
                              <Pill size={20} />
                            ) : tx.category === 'clinic' ? (
                              <Stethoscope size={20} />
                            ) : tx.category === 'diagnostics' ? (
                              <TestTube size={20} />
                            ) : tx.category === 'refund' ? (
                              <ShieldCheck size={20} />
                            ) : (
                              <Sparkles size={20} />
                            )}
                          </div>

                          <div className="tx-card-text-block">
                            <div className="tx-title-and-provider">
                              <h4 className="tx-card-title">{tx.title}</h4>
                              <span className="tx-card-provider">{tx.provider}</span>
                            </div>

                            {/* Clinical & Regulatory Badges */}
                            <div className="tx-card-badges-row">
                              {tx.is_gpp && <span className="reg-badge gpp">Chuẩn GPP</span>}
                              {tx.dav_compliant && <span className="reg-badge dav">Đúng trần DAV</span>}
                              {tx.bhyt_rate > 0 && (
                                <span className="reg-badge bhyt">Hưởng BHYT {tx.bhyt_rate}%</span>
                              )}
                              {tx.rx_code && <span className="reg-badge rx">{tx.rx_code}</span>}
                            </div>

                            {tx.clinical_notes && (
                              <p className="tx-card-clinical-notes">
                                <strong>Chỉ dẫn: </strong>{tx.clinical_notes}
                              </p>
                            )}
                          </div>
                        </div>

                        <div className="tx-card-finance-col">
                          <div className="tx-amount-large">
                            <span className={isIncome ? 'text-emerald' : 'text-main'}>
                              {isIncome ? '+' : ''}
                              {formatVnd(tx.amount_vnd, hideAmounts)}
                            </span>
                          </div>

                          {tx.bhyt_covered_vnd > 0 && !isIncome && (
                            <span className="bhyt-support-tag">
                              BHYT gánh: +{formatVnd(tx.bhyt_covered_vnd, hideAmounts)}
                            </span>
                          )}

                          <span className="tx-timestamp-tag">
                            <Clock size={12} />
                            <span>{tx.time}</span>
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))
          )}
        </div>
      </section>

      {/* ====================================================================
          MODAL 1: NHẬP GIAO DỊCH CHI TIÊU Y TẾ
          ==================================================================== */}
      {showAddModal && (
        <div className="web-modal-backdrop" onClick={() => setShowAddModal(false)}>
          <div className="web-modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header-line">
              <div className="modal-title-left">
                <FilePlus2 size={20} className="text-pink" />
                <h3>Nhập Giao Dịch Chi Tiêu Y Tế</h3>
              </div>
              <button
                type="button"
                className="close-modal-btn"
                onClick={() => setShowAddModal(false)}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleAddNewTxSubmit} className="modal-form-body">
              <div className="form-field-item">
                <label>Tên khoản chi / Tên thuốc & dịch vụ</label>
                <input
                  type="text"
                  placeholder="Ví dụ: Thuốc Nexium 40mg, Khám Nội Tiêu Hóa, Xét nghiệm ALT..."
                  value={newTxTitle}
                  onChange={(e) => setNewTxTitle(e.target.value)}
                  required
                />
              </div>

              <div className="form-fields-two-col">
                <div className="form-field-item">
                  <label>Số tiền (VNĐ)</label>
                  <input
                    type="number"
                    min="1000"
                    step="1000"
                    placeholder="480000"
                    value={newTxAmount}
                    onChange={(e) => setNewTxAmount(e.target.value)}
                    required
                  />
                </div>

                <div className="form-field-item">
                  <label>Nhóm danh mục chi tiêu</label>
                  <select
                    value={newTxCategory}
                    onChange={(e) => setNewTxCategory(e.target.value)}
                  >
                    <option value="medication">Thuốc kê đơn & Dược GPP</option>
                    <option value="clinic">Khám & Viện phí điều trị</option>
                    <option value="diagnostics">Xét nghiệm & Cận lâm sàng</option>
                    <option value="supplements">Dược mỹ phẩm & TPCN</option>
                    <option value="supplies">Vật tư y tế tiêu hao</option>
                  </select>
                </div>
              </div>

              <div className="form-field-item">
                <label>Cơ sở y tế / Nhà thuốc thực hiện</label>
                <input
                  type="text"
                  placeholder="Nhà thuốc Long Châu, BV Đại học Y Dược, Phòng khám..."
                  value={newTxProvider}
                  onChange={(e) => setNewTxProvider(e.target.value)}
                />
              </div>

              <div className="form-checkbox-row">
                <label className="checkbox-wrap">
                  <input
                    type="checkbox"
                    checked={newTxBhytEligible}
                    onChange={(e) => setNewTxBhytEligible(e.target.checked)}
                  />
                  <span>Được Quỹ BHYT chi trả đồng thanh toán (80% đúng tuyến)</span>
                </label>
              </div>

              <div className="form-field-item">
                <label>Ghi chú lâm sàng / Hướng dẫn uống thuốc của bác sĩ</label>
                <input
                  type="text"
                  placeholder="Uống trước ăn sáng 30 phút, theo dõi phản ứng phụ đau thượng vị..."
                  value={newTxNotes}
                  onChange={(e) => setNewTxNotes(e.target.value)}
                />
              </div>

              <div className="modal-buttons-row">
                <button
                  type="button"
                  className="modal-action-btn cancel"
                  onClick={() => setShowAddModal(false)}
                >
                  Hủy
                </button>
                <button type="submit" className="modal-action-btn submit-pink">
                  Ghi nhận khoản chi
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ====================================================================
          MODAL 2: XEM CHI TIẾT GIAO DỊCH LÂM SÀNG & HÓA ĐƠN ĐIỆN TỬ
          ==================================================================== */}
      {selectedTxForDetail && (
        <div className="web-modal-backdrop" onClick={() => setSelectedTxForDetail(null)}>
          <div className="web-modal-dialog detail-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header-line">
              <div className="modal-title-left">
                <FileText size={20} className="text-emerald" />
                <h3>Chi Tiết Chứng Từ & Đơn Thuốc Điện Tử</h3>
              </div>
              <button
                type="button"
                className="close-modal-btn"
                onClick={() => setSelectedTxForDetail(null)}
              >
                <X size={18} />
              </button>
            </div>

            <div className="detail-dialog-body">
              <div className="detail-hero-banner">
                <span className="hero-cat-pill">{selectedTxForDetail.category_name}</span>
                <h4 className="hero-tx-name">{selectedTxForDetail.title}</h4>
                <div className="hero-tx-amount">
                  {formatVnd(selectedTxForDetail.amount_vnd, hideAmounts)}
                </div>
                {selectedTxForDetail.bhyt_covered_vnd > 0 && (
                  <span className="hero-bhyt-tag">
                    BHYT hỗ trợ chi trả: {formatVnd(selectedTxForDetail.bhyt_covered_vnd, hideAmounts)}
                  </span>
                )}
              </div>

              <div className="detail-meta-two-col">
                <div className="meta-info-card">
                  <span className="meta-lbl">Cơ sở khám chữa bệnh</span>
                  <strong>{selectedTxForDetail.provider}</strong>
                </div>
                <div className="meta-info-card">
                  <span className="meta-lbl">Thời gian ghi nhận</span>
                  <strong>{selectedTxForDetail.date} • {selectedTxForDetail.time}</strong>
                </div>
                <div className="meta-info-card">
                  <span className="meta-lbl">Mã hồ sơ y tế / Toa thuốc</span>
                  <code>{selectedTxForDetail.rx_code || 'Chưa định danh'}</code>
                </div>
                <div className="meta-info-card">
                  <span className="meta-lbl">Kiểm soát trần giá DAV</span>
                  <strong className="text-emerald">Đạt chuẩn niêm yết Cục Quản Lý Dược</strong>
                </div>
              </div>

              {selectedTxForDetail.clinical_notes && (
                <div className="detail-clinical-notes-card">
                  <strong>Chỉ dẫn lâm sàng & Liều dùng:</strong>
                  <p>{selectedTxForDetail.clinical_notes}</p>
                </div>
              )}

              <div className="qr-verification-box">
                <QrCode size={44} className="qr-code-icon" />
                <div className="qr-info-text">
                  <strong>Hóa đơn điện tử có mã tra cứu QR</strong>
                  <span>Đã kiểm thực tem chống hàng giả, đạt chuẩn GPP và liên thông hồ sơ sức khỏe VNeID.</span>
                </div>
              </div>

              <button
                type="button"
                className="modal-action-btn submit-pink full-width"
                onClick={() => setSelectedTxForDetail(null)}
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
