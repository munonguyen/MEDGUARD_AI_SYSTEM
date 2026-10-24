import { useEffect, useState, useCallback, useMemo } from 'react';
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BarChart2,
  Bot,
  Calendar,
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
  Headphones,
  Home,
  LayoutGrid,
  Monitor,
  PieChart,
  Pill,
  Plus,
  QrCode,
  RefreshCw,
  Search,
  ShieldCheck,
  Smartphone,
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

// 6 Medical Spending Categories adhering to Vietnam Ministry of Health & GPP Pharmacy Standards
const DEFAULT_CATEGORIES = [
  {
    id: 'medication',
    name: 'Thuốc kê đơn & GPP',
    percentage: 41,
    amount_vnd: 5070066,
    color: '#f472b6', // Rosy pink matching screenshot
    icon: Pill,
    badge: 'Chuẩn GPP / DAV',
    description: 'Biệt dược gốc và thuốc Generic EU-GMP điều trị theo phác đồ',
  },
  {
    id: 'clinic',
    name: 'Khám & Viện phí điều trị',
    percentage: 33,
    amount_vnd: 4080785,
    color: '#34d399', // Mint green matching screenshot
    icon: Stethoscope,
    badge: 'BHYT Đúng Tuyến',
    description: 'Booking Care, tiền khám chuyên khoa và nội trú bệnh viện',
  },
  {
    id: 'diagnostics',
    name: 'Xét nghiệm & Cận lâm sàng',
    percentage: 14,
    amount_vnd: 1731242,
    color: '#38bdf8', // Cyan matching screenshot
    icon: TestTube,
    badge: 'ISO 15189',
    description: 'Công thức máu, nội soi tiêu hóa, sinh hóa gan thận và X-quang',
  },
  {
    id: 'supplements',
    name: 'Dược mỹ phẩm & TPCN',
    percentage: 11,
    amount_vnd: 1360261,
    color: '#fb923c', // Warm orange matching screenshot
    icon: Sparkles,
    badge: 'Chính Hãng',
    description: 'Men vi sinh, vitamin khoáng chất và dinh dưỡng hồi phục sau ốm',
  },
  {
    id: 'supplies',
    name: 'Vật tư y tế tiêu hao',
    percentage: 1,
    amount_vnd: 123662,
    color: '#cbd5e1', // Slate/gray matching screenshot
    icon: FileText,
    badge: 'Vô trùng',
    description: 'Kim tiêm, băng gạc vô trùng, cồn sát khuẩn và nước muối sinh lý',
  },
];

// Rich, clinical mock transactions
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
    amount_vnd: 1450000, // Positive inflow
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
  // Main view state
  const [deviceFrameMode, setDeviceFrameMode] = useState('mobile'); // 'mobile' | 'fullscreen'
  const [bottomTab, setBottomTab] = useState('overview'); // 'overview', 'calendar', 'recurring', 'moni', 'utilities'
  const [hideAmounts, setHideAmounts] = useState(false);
  const [timePeriod, setTimePeriod] = useState('Tháng này');
  const [showCategoryDetail, setShowCategoryDetail] = useState(false);
  const [selectedTxForDetail, setSelectedTxForDetail] = useState(null);

  // Search and filter in transaction list
  const [txSearchQuery, setTxSearchQuery] = useState('');
  const [txFilterTab, setTxFilterTab] = useState('all'); // 'all', 'medication', 'clinic', 'diagnostics', 'refund'

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
    <div className={`spending-viewport-wrapper ${deviceFrameMode}`}>
      {/* Top Device Switcher Toolbar */}
      <div className="view-mode-toolbar">
        <div className="toolbar-branding">
          <ShieldCheck size={16} className="text-emerald" />
          <span>MEDGUARD HEALTHCARE ECONOMICS • QUẢN LÝ CHI TIÊU</span>
        </div>
        <div className="toolbar-toggle-group">
          <button
            type="button"
            className={`toolbar-btn ${deviceFrameMode === 'mobile' ? 'active' : ''}`}
            onClick={() => setDeviceFrameMode('mobile')}
            title="Xem giao diện chuẩn App Điện Thoại (như hình mẫu)"
          >
            <Smartphone size={14} />
            <span>App Mobile (Khuyên dùng)</span>
          </button>
          <button
            type="button"
            className={`toolbar-btn ${deviceFrameMode === 'fullscreen' ? 'active' : ''}`}
            onClick={() => setDeviceFrameMode('fullscreen')}
            title="Mở rộng toàn màn hình Desktop"
          >
            <Monitor size={14} />
            <span>Toàn màn hình</span>
          </button>
        </div>
      </div>

      {/* Main App Container (Matches Smartphone Dashboard in user image) */}
      <div className="phone-mockup-frame">
        {/* Smartphone Speaker / Camera Notch */}
        {deviceFrameMode === 'mobile' && (
          <div className="phone-notch-area">
            <span className="phone-time-indicator">16:57</span>
            <div className="phone-camera-island">
              <span className="camera-dot" />
              <span className="speaker-slit" />
            </div>
            <div className="phone-status-icons">
              <span className="signal-bar">5G</span>
              <span className="battery-icon">98%</span>
            </div>
          </div>
        )}

        {/* ====================================================================
            1. TOP APP HEADER BAR
            ==================================================================== */}
        <header className="mobile-app-header">
          <button
            type="button"
            className="header-icon-btn back-btn"
            onClick={onBackToChat}
            title="Quay lại hội thoại y tế"
          >
            <ArrowLeft size={20} />
          </button>

          <h2 className="header-app-title">Quản lý chi tiêu</h2>

          <div className="header-actions-right">
            <button
              type="button"
              className="header-icon-btn star-btn"
              title="Ghim chi tiêu ưu tiên"
              onClick={() => onNotify?.('Đã lưu bảng chi tiêu vào danh mục ưu tiên theo dõi!', 'info')}
            >
              <Star size={18} />
            </button>
            <button
              type="button"
              className="header-icon-btn headset-btn"
              title="Hỏi trợ lý kinh tế dược học Moni AI"
              onClick={() => {
                onNavigate?.('chat');
                window.dispatchEvent(
                  new CustomEvent('medguard:navigate', {
                    detail: { view: 'chat', message: 'Tư vấn tối ưu hóa chi phí thuốc và viện phí BHYT tháng này.' },
                  })
                );
              }}
            >
              <Headphones size={18} />
            </button>
            <button
              type="button"
              className="header-icon-btn home-btn"
              title="Về trang chủ"
              onClick={onBackToChat}
            >
              <Home size={18} />
            </button>
          </div>
        </header>

        {/* Scrollable Body Content */}
        <main className="mobile-app-body">
          {/* ====================================================================
              2. 4 TIỆN ÍCH THAO TÁC NHANH (MINT / TEAL TILES - AS IN IMAGE)
              ==================================================================== */}
          <section className="quick-actions-four-grid">
            {/* Tile 1: Nhập giao dịch */}
            <button
              type="button"
              className="quick-action-tile"
              onClick={() => setShowAddModal(true)}
            >
              <div className="tile-icon-box mint">
                <FilePlus2 size={24} />
              </div>
              <span className="tile-label">Nhập giao dịch</span>
            </button>

            {/* Tile 2: Biến động thu chi */}
            <button
              type="button"
              className="quick-action-tile"
              onClick={() => {
                onNotify?.('Xu hướng chi tiêu y tế tháng 10 giảm 28.5% so với tháng trước nhờ dùng thuốc Generic!', 'info');
              }}
            >
              <div className="tile-icon-box mint">
                <TrendingUp size={24} />
              </div>
              <span className="tile-label">Biến động thu chi</span>
            </button>

            {/* Tile 3: Quản lý danh mục */}
            <button
              type="button"
              className="quick-action-tile"
              onClick={() => setShowCategoryDetail((v) => !v)}
            >
              <div className="tile-icon-box mint">
                <Folder size={24} />
              </div>
              <span className="tile-label">Quản lý danh mục</span>
            </button>

            {/* Tile 4: Tiện ích khác */}
            <button
              type="button"
              className="quick-action-tile"
              onClick={() => {
                setBottomTab('utilities');
                onNotify?.('Đã mở phân hệ Tiện ích y tế: Đối soát giá DAV & Thẩm định BHYT', 'info');
              }}
            >
              <div className="tile-icon-box mint">
                <LayoutGrid size={24} />
              </div>
              <span className="tile-label">Tiện ích khác</span>
            </button>
          </section>

          {/* ====================================================================
              3. TIÊU ĐỀ "TÌNH HÌNH THU CHI" & BỘ LỌC THỜI GIAN
              ==================================================================== */}
          <section className="cashflow-status-header-section">
            <div className="cashflow-title-row">
              <div className="title-with-eye">
                <h3 className="section-heading">Tình hình thu chi</h3>
                <button
                  type="button"
                  className="eye-toggle-btn"
                  onClick={() => setHideAmounts((v) => !v)}
                  title={hideAmounts ? 'Hiện số tiền' : 'Ẩn số tiền bảo mật'}
                >
                  {hideAmounts ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>

              <div className="cashflow-pills-right">
                <button type="button" className="pill-btn pink-pill active">
                  <PieChart size={14} />
                  <span>Phân bổ</span>
                </button>
                <button
                  type="button"
                  className="chart-toggle-icon-btn"
                  title="Chuyển chế độ xem cột"
                  onClick={() => onNotify?.('Đang xem chế độ phân bổ vành khuyên Donut', 'info')}
                >
                  <BarChart2 size={18} />
                </button>
              </div>
            </div>

            {/* Time Filter Row: < [Calendar] Tháng này > */}
            <div className="month-selector-bar">
              <button
                type="button"
                className="month-nav-arrow"
                onClick={() => {
                  setTimePeriod('Tháng 9/2026');
                  onNotify?.('Đã chuyển sang xem số liệu: Tháng 9/2026', 'info');
                }}
              >
                <ChevronLeft size={18} />
              </button>

              <div className="month-display-pill">
                <Calendar size={15} />
                <span>{timePeriod} (10/2026)</span>
              </div>

              <button
                type="button"
                className="month-nav-arrow"
                onClick={() => {
                  setTimePeriod('Tháng này');
                  onNotify?.('Đang xem số liệu: Tháng này (10/2026)', 'info');
                }}
              >
                <ChevronRight size={18} />
              </button>
            </div>
          </section>

          {/* ====================================================================
              4. CẶP THẺ TỔNG HỢP (DUAL BALANCE CARD - AS IN IMAGE)
              ==================================================================== */}
          <section className="dual-summary-cards-section">
            <div className="dual-cards-container">
              {/* Card 1: Chi tiêu (Hồng active) */}
              <div className="summary-card expense-card active-pink">
                <div className="summary-card-top">
                  <span className="summary-card-icon-circle pink">
                    <TrendingDown size={14} />
                  </span>
                  <span className="summary-card-label">Chi tiêu</span>
                  <span className="trend-arrow-tag down">↓</span>
                </div>
                <div className="summary-card-amount pink">
                  {formatVnd(totalActualSpend, hideAmounts)}
                </div>
              </div>

              {/* Card 2: Thu nhập / Quỹ BHYT chi trả */}
              <div className="summary-card income-card">
                <div className="summary-card-top">
                  <span className="summary-card-icon-circle green">
                    <TrendingUp size={14} />
                  </span>
                  <span className="summary-card-label">BHYT & Thu</span>
                  <span className="trend-arrow-tag up">↑</span>
                </div>
                <div className="summary-card-amount dark">
                  {formatVnd(totalBhytCovered, hideAmounts)}
                </div>
              </div>
            </div>

            {/* Sub-banner: Giảm 941.854 đ so với cùng kỳ tháng trước */}
            <div
              className="comparison-sub-banner"
              onClick={() => onNotify?.('Tiết kiệm 941.854 ₫ chủ yếu nhờ chuyển đổi sang thuốc Generic EU-GMP đúng trần DAV.', 'info')}
            >
              <div className="sub-banner-left">
                <div className="mini-chart-icon-box">
                  <BarChart2 size={16} />
                </div>
                <span className="sub-banner-text">
                  <strong className="text-emerald">Giảm 941.854 ₫</strong> so với cùng kỳ tháng trước
                </span>
              </div>
              <ChevronRight size={16} className="sub-banner-chevron" />
            </div>
          </section>

          {/* ====================================================================
              5. BIỂU ĐỒ DONUT CHART SVG VÀNH KHUYÊN & CALLOUT POINTERS (AS IN IMAGE)
              ==================================================================== */}
          <section className="donut-chart-and-callouts-section">
            <div className="donut-illustration-wrapper">
              {/* Left Callouts */}
              <div className="callouts-column left-callouts">
                <div className="callout-item callout-1">
                  <div className="callout-pill-tag">
                    <span className="callout-dot gray" />
                    <span className="callout-pct">1%</span>
                  </div>
                  <span className="callout-name">Còn lại</span>
                  <div className="dotted-guide-line guide-left-1" />
                </div>

                <div className="callout-item callout-2">
                  <div className="callout-pill-tag">
                    <span className="callout-dot orange" />
                    <span className="callout-pct">11%</span>
                  </div>
                  <span className="callout-name">TPCN / Ăn uống</span>
                  <div className="dotted-guide-line guide-left-2" />
                </div>

                <div className="callout-item callout-3">
                  <div className="callout-pill-tag">
                    <span className="callout-dot cyan" />
                    <span className="callout-pct">14%</span>
                  </div>
                  <span className="callout-name">Xét nghiệm định kỳ</span>
                  <div className="dotted-guide-line guide-left-3" />
                </div>

                <div className="callout-item callout-4">
                  <div className="callout-pill-tag">
                    <span className="callout-dot mint" />
                    <span className="callout-pct">33%</span>
                  </div>
                  <span className="callout-name">Viện phí / Hóa đơn</span>
                  <div className="dotted-guide-line guide-left-4" />
                </div>
              </div>

              {/* Center Donut SVG Ring */}
              <div className="donut-svg-center">
                <svg
                  width="180"
                  height="180"
                  viewBox="0 0 180 180"
                  className="donut-svg-graphic"
                >
                  {/* Background Track */}
                  <circle
                    cx="90"
                    cy="90"
                    r="62"
                    fill="none"
                    stroke="#f1f5f9"
                    strokeWidth="24"
                  />

                  {/* Arc 1: Thuốc kê đơn & GPP (Pink 41%)
                      Circumference = 2 * PI * 62 = 389.56
                      41% = 159.72
                  */}
                  <circle
                    cx="90"
                    cy="90"
                    r="62"
                    fill="none"
                    stroke="#f472b6"
                    strokeWidth="24"
                    strokeDasharray="159.72 229.84"
                    strokeDashoffset="0"
                    strokeLinecap="round"
                    transform="rotate(-90 90 90)"
                  />

                  {/* Arc 2: Viện phí & Khám bệnh (Mint Green 33%)
                      33% = 128.55, offset = -159.72
                  */}
                  <circle
                    cx="90"
                    cy="90"
                    r="62"
                    fill="none"
                    stroke="#34d399"
                    strokeWidth="24"
                    strokeDasharray="128.55 261.01"
                    strokeDashoffset="-159.72"
                    strokeLinecap="round"
                    transform="rotate(-90 90 90)"
                  />

                  {/* Arc 3: Xét nghiệm Cận lâm sàng (Cyan 14%)
                      14% = 54.54, offset = -288.27
                  */}
                  <circle
                    cx="90"
                    cy="90"
                    r="62"
                    fill="none"
                    stroke="#38bdf8"
                    strokeWidth="24"
                    strokeDasharray="54.54 335.02"
                    strokeDashoffset="-288.27"
                    strokeLinecap="round"
                    transform="rotate(-90 90 90)"
                  />

                  {/* Arc 4: TPCN Dinh dưỡng (Orange 11%)
                      11% = 42.85, offset = -342.81
                  */}
                  <circle
                    cx="90"
                    cy="90"
                    r="62"
                    fill="none"
                    stroke="#fb923c"
                    strokeWidth="24"
                    strokeDasharray="42.85 346.71"
                    strokeDashoffset="-342.81"
                    strokeLinecap="round"
                    transform="rotate(-90 90 90)"
                  />

                  {/* Arc 5: Vật tư khác (Gray 1%)
                      1% = 3.90, offset = -385.66
                  */}
                  <circle
                    cx="90"
                    cy="90"
                    r="62"
                    fill="none"
                    stroke="#cbd5e1"
                    strokeWidth="24"
                    strokeDasharray="3.9 385.66"
                    strokeDashoffset="-385.66"
                    transform="rotate(-90 90 90)"
                  />
                </svg>

                {/* Donut Center Core */}
                <div className="donut-core-circle">
                  <span className="donut-core-tag">Tổng Chi</span>
                  <strong className="donut-core-sum">
                    {formatVnd(totalActualSpend, hideAmounts)}
                  </strong>
                </div>
              </div>

              {/* Right Callouts */}
              <div className="callouts-column right-callouts">
                <div className="callout-item callout-right-main">
                  <div className="dotted-guide-line guide-right-1" />
                  <div className="callout-pill-tag pink">
                    <span className="callout-dot pink" />
                    <span className="callout-pct">41%</span>
                  </div>
                  <span className="callout-name">Thuốc kê đơn</span>
                </div>
              </div>
            </div>

            {/* Expandable Toggle: Chi tiết từng danh mục (6) ⌵ */}
            <div className="category-detail-expand-row">
              <button
                type="button"
                className="category-detail-toggle-btn"
                onClick={() => setShowCategoryDetail((v) => !v)}
              >
                <span>Chi tiết từng danh mục (5 nhóm)</span>
                {showCategoryDetail ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </button>
            </div>

            {/* Expanded Category Breakdown Table */}
            {showCategoryDetail && (
              <div className="expanded-category-panel">
                <div className="category-list-stack">
                  {DEFAULT_CATEGORIES.map((cat) => {
                    const CatIcon = cat.icon;
                    return (
                      <div key={cat.id} className="category-row-card">
                        <div className="cat-row-left">
                          <div className="cat-icon-badge" style={{ backgroundColor: `${cat.color}20`, color: cat.color }}>
                            <CatIcon size={18} />
                          </div>
                          <div className="cat-text-group">
                            <div className="cat-title-line">
                              <strong>{cat.name}</strong>
                              <span className="cat-badge-pill">{cat.badge}</span>
                            </div>
                            <span className="cat-desc-sub">{cat.description}</span>
                          </div>
                        </div>
                        <div className="cat-row-right">
                          <span className="cat-amount-val" style={{ color: cat.color }}>
                            {formatVnd(cat.amount_vnd, hideAmounts)}
                          </span>
                          <span className="cat-percent-tag">{cat.percentage}% tổng chi</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </section>

          {/* ====================================================================
              6. LỊCH SỬ CHI TIÊU Y TẾ CHI TIẾT (DETAILED CLINICAL LEDGER)
              ==================================================================== */}
          <section className="detailed-ledger-section">
            <div className="ledger-header-row">
              <div className="ledger-title-wrap">
                <h3 className="section-heading">Lịch sử chi tiêu y tế</h3>
                <span className="ledger-count-badge">{filteredTransactions.length} giao dịch</span>
              </div>
              <button
                type="button"
                className="add-tx-link-btn"
                onClick={() => setShowAddModal(true)}
              >
                <Plus size={14} />
                <span>Thêm khoản chi</span>
              </button>
            </div>

            {/* Filter Tabs & Search Bar */}
            <div className="ledger-controls-bar">
              <div className="ledger-search-box">
                <Search size={15} className="search-icon" />
                <input
                  type="text"
                  placeholder="Tìm thuốc, bệnh viện, mã toa..."
                  value={txSearchQuery}
                  onChange={(e) => setTxSearchQuery(e.target.value)}
                />
                {txSearchQuery && (
                  <button type="button" className="search-clear-btn" onClick={() => setTxSearchQuery('')}>
                    <X size={13} />
                  </button>
                )}
              </div>

              {/* Filter Chips */}
              <div className="ledger-filter-chips-scroller">
                {[
                  { id: 'all', label: 'Tất cả' },
                  { id: 'medication', label: 'Thuốc kê đơn' },
                  { id: 'clinic', label: 'Khám & Viện phí' },
                  { id: 'diagnostics', label: 'Xét nghiệm' },
                  { id: 'supplements', label: 'TPCN' },
                  { id: 'refund', label: 'BHYT chi trả' },
                ].map((chip) => (
                  <button
                    key={chip.id}
                    type="button"
                    className={`filter-chip-btn ${txFilterTab === chip.id ? 'active' : ''}`}
                    onClick={() => setTxFilterTab(chip.id)}
                  >
                    {chip.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Grouped Transaction List */}
            <div className="grouped-transactions-stack">
              {Object.keys(groupedTransactions).length === 0 ? (
                <div className="empty-tx-box">
                  <FileScan size={32} />
                  <p>Không tìm thấy giao dịch y tế phù hợp với bộ lọc.</p>
                </div>
              ) : (
                Object.entries(groupedTransactions).map(([dateLabel, txList]) => (
                  <div key={dateLabel} className="tx-date-group">
                    <div className="date-group-divider">
                      <span>{dateLabel}</span>
                    </div>

                    <div className="tx-items-list">
                      {txList.map((tx) => {
                        const isIncome = tx.amount_vnd > 0;
                        return (
                          <div
                            key={tx.id}
                            className="tx-item-card"
                            onClick={() => setSelectedTxForDetail(tx)}
                          >
                            <div className="tx-item-left">
                              <div className={`tx-icon-circle ${tx.category}`}>
                                {tx.category === 'medication' ? (
                                  <Pill size={18} />
                                ) : tx.category === 'clinic' ? (
                                  <Stethoscope size={18} />
                                ) : tx.category === 'diagnostics' ? (
                                  <TestTube size={18} />
                                ) : tx.category === 'refund' ? (
                                  <ShieldCheck size={18} />
                                ) : (
                                  <Sparkles size={18} />
                                )}
                              </div>

                              <div className="tx-info-content">
                                <h4 className="tx-title">{tx.title}</h4>
                                <span className="tx-provider-name">{tx.provider}</span>

                                {/* Clinical & Regulatory Badges */}
                                <div className="tx-badges-row">
                                  {tx.is_gpp && <span className="tx-pill gpp">Chuẩn GPP</span>}
                                  {tx.dav_compliant && <span className="tx-pill dav">Đúng trần DAV</span>}
                                  {tx.bhyt_rate > 0 && (
                                    <span className="tx-pill bhyt">BHYT {tx.bhyt_rate}%</span>
                                  )}
                                  {tx.rx_code && <span className="tx-pill rx">{tx.rx_code}</span>}
                                </div>

                                {tx.clinical_notes && (
                                  <p className="tx-clinical-note">{tx.clinical_notes}</p>
                                )}
                              </div>
                            </div>

                            <div className="tx-item-right">
                              <span className={`tx-amount-text ${isIncome ? 'income' : 'expense'}`}>
                                {isIncome ? '+' : ''}
                                {formatVnd(tx.amount_vnd, hideAmounts)}
                              </span>

                              {tx.bhyt_covered_vnd > 0 && !isIncome && (
                                <span className="tx-bhyt-tag">
                                  +{formatVnd(tx.bhyt_covered_vnd, hideAmounts)} BHYT
                                </span>
                              )}

                              <span className="tx-time-text">{tx.time}</span>
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
              7. TIỆN ÍCH Y TẾ BỔ TRỢ (DAV BENCHMARK & OPEN-SOURCE REPUTATION)
              ==================================================================== */}
          {bottomTab === 'utilities' && (
            <section className="utilities-embedded-section">
              <div className="section-title-box">
                <Tag size={18} className="text-emerald" />
                <h4>Bảng Đối Sánh Trần Giá Dược (Cục Quản Lý Dược - DAV)</h4>
              </div>
              <div className="dav-table-mini-card">
                <table className="mini-dav-table">
                  <thead>
                    <tr>
                      <th>Tên Thuốc / Dịch Vụ</th>
                      <th>Giá Mua</th>
                      <th>Trần DAV</th>
                      <th>Generic Thay Thế</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>Esomeprazole 40mg</td>
                      <td>24.000 ₫</td>
                      <td>24.500 ₫</td>
                      <td className="text-emerald">14.500 ₫ (-40%)</td>
                    </tr>
                    <tr>
                      <td>Augmentin 1g</td>
                      <td>21.000 ₫</td>
                      <td>21.800 ₫</td>
                      <td className="text-emerald">13.200 ₫ (-39%)</td>
                    </tr>
                    <tr>
                      <td>Amlodipine 5mg</td>
                      <td>5.500 ₫</td>
                      <td>6.000 ₫</td>
                      <td className="text-emerald">3.400 ₫ (-38%)</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </main>

        {/* ====================================================================
            8. THANH ĐIỀU HƯỚNG ĐÁY (BOTTOM APP NAVBAR - AS IN IMAGE)
            ==================================================================== */}
        <nav className="mobile-app-bottom-bar">
          <button
            type="button"
            className={`bottom-tab-btn ${bottomTab === 'overview' ? 'active' : ''}`}
            onClick={() => setBottomTab('overview')}
          >
            <div className="tab-icon-wrapper">
              <WalletCards size={20} />
            </div>
            <span className="tab-label">Tổng quan</span>
          </button>

          <button
            type="button"
            className={`bottom-tab-btn ${bottomTab === 'calendar' ? 'active' : ''}`}
            onClick={() => {
              setBottomTab('calendar');
              onNotify?.('Lịch khám BHYT định kỳ và thời gian uống thuốc đã được đồng bộ!', 'info');
            }}
          >
            <div className="tab-icon-wrapper">
              <CalendarDays size={20} />
            </div>
            <span className="tab-label">Lịch</span>
          </button>

          <button
            type="button"
            className={`bottom-tab-btn ${bottomTab === 'recurring' ? 'active' : ''}`}
            onClick={() => {
              setBottomTab('recurring');
              onNotify?.('Danh mục đơn thuốc mãn tính định kỳ (Tự động nhắc mua hàng tháng)', 'info');
            }}
          >
            <div className="tab-icon-wrapper">
              <CalendarClock size={20} />
            </div>
            <span className="tab-label">GD định kỳ</span>
          </button>

          <button
            type="button"
            className={`bottom-tab-btn ${bottomTab === 'moni' ? 'active' : ''}`}
            onClick={() => {
              onNavigate?.('chat');
              window.dispatchEvent(
                new CustomEvent('medguard:navigate', {
                  detail: { view: 'chat', message: 'Trợ lý Moni AI: Hãy phân tích cách tiết kiệm chi phí thuốc dạ dày và tối ưu BHYT cho tôi.' },
                })
              );
            }}
          >
            <div className="tab-icon-wrapper">
              <Bot size={20} />
            </div>
            <span className="tab-label">Moni AI</span>
          </button>

          <button
            type="button"
            className={`bottom-tab-btn ${bottomTab === 'utilities' ? 'active' : ''}`}
            onClick={() => setBottomTab('utilities')}
          >
            <div className="tab-icon-wrapper">
              <LayoutGrid size={20} />
            </div>
            <span className="tab-label">Tiện ích</span>
          </button>
        </nav>
      </div>

      {/* ====================================================================
          MODAL 1: NHẬP GIAO DỊCH CHI TIÊU Y TẾ (+ ADD TRANSACTION)
          ==================================================================== */}
      {showAddModal && (
        <div className="modal-backdrop-overlay" onClick={() => setShowAddModal(false)}>
          <div className="modal-sheet-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-dialog-header">
              <div className="modal-title-left">
                <FilePlus2 size={20} className="text-rose" />
                <h3>Nhập Giao Dịch Chi Tiêu Y Tế</h3>
              </div>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setShowAddModal(false)}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleAddNewTxSubmit} className="modal-form-content">
              <div className="form-group-block">
                <label>Tên khoản chi / Tên thuốc & dịch vụ</label>
                <input
                  type="text"
                  placeholder="Ví dụ: Thuốc Nexium 40mg, Khám Tiêu Hóa..."
                  value={newTxTitle}
                  onChange={(e) => setNewTxTitle(e.target.value)}
                  required
                />
              </div>

              <div className="form-group-row">
                <div className="form-group-block">
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

                <div className="form-group-block">
                  <label>Nhóm danh mục</label>
                  <select
                    value={newTxCategory}
                    onChange={(e) => setNewTxCategory(e.target.value)}
                  >
                    <option value="medication">Thuốc kê đơn & GPP</option>
                    <option value="clinic">Khám & Viện phí</option>
                    <option value="diagnostics">Xét nghiệm & Chẩn đoán</option>
                    <option value="supplements">Dược mỹ phẩm & TPCN</option>
                    <option value="supplies">Vật tư y tế</option>
                  </select>
                </div>
              </div>

              <div className="form-group-block">
                <label>Nơi thực hiện / Cơ sở y tế</label>
                <input
                  type="text"
                  placeholder="Nhà thuốc Long Châu, BV Đại học Y Dược..."
                  value={newTxProvider}
                  onChange={(e) => setNewTxProvider(e.target.value)}
                />
              </div>

              <div className="form-checkbox-row">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={newTxBhytEligible}
                    onChange={(e) => setNewTxBhytEligible(e.target.checked)}
                  />
                  <span>Được quỹ BHYT chi trả đồng thanh toán (80%)</span>
                </label>
              </div>

              <div className="form-group-block">
                <label>Ghi chú lâm sàng / Hướng dẫn bác sĩ</label>
                <input
                  type="text"
                  placeholder="Uống trước ăn 30p, theo dõi đau thượng vị..."
                  value={newTxNotes}
                  onChange={(e) => setNewTxNotes(e.target.value)}
                />
              </div>

              <div className="modal-actions-bar">
                <button
                  type="button"
                  className="modal-btn secondary"
                  onClick={() => setShowAddModal(false)}
                >
                  Hủy
                </button>
                <button type="submit" className="modal-btn primary-pink">
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
        <div className="modal-backdrop-overlay" onClick={() => setSelectedTxForDetail(null)}>
          <div className="modal-sheet-dialog detail-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-dialog-header">
              <div className="modal-title-left">
                <FileText size={20} className="text-emerald" />
                <h3>Chi Tiết Chứng Từ Y Tế & Hóa Đơn</h3>
              </div>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setSelectedTxForDetail(null)}
              >
                <X size={18} />
              </button>
            </div>

            <div className="tx-detail-modal-body">
              <div className="detail-hero-box">
                <span className="hero-category-badge">{selectedTxForDetail.category_name}</span>
                <h4 className="hero-tx-title">{selectedTxForDetail.title}</h4>
                <div className="hero-amount-highlight">
                  {formatVnd(selectedTxForDetail.amount_vnd, hideAmounts)}
                </div>
                {selectedTxForDetail.bhyt_covered_vnd > 0 && (
                  <span className="hero-bhyt-support">
                    Bảo hiểm Y tế hỗ trợ chi trả: {formatVnd(selectedTxForDetail.bhyt_covered_vnd, hideAmounts)}
                  </span>
                )}
              </div>

              <div className="detail-meta-grid">
                <div className="meta-card-item">
                  <span className="meta-item-label">Cơ sở y tế</span>
                  <strong>{selectedTxForDetail.provider}</strong>
                </div>
                <div className="meta-card-item">
                  <span className="meta-item-label">Thời gian giao dịch</span>
                  <strong>{selectedTxForDetail.date} • {selectedTxForDetail.time}</strong>
                </div>
                <div className="meta-card-item">
                  <span className="meta-item-label">Mã đơn thuốc / Hồ sơ</span>
                  <code>{selectedTxForDetail.rx_code || 'Chưa định danh'}</code>
                </div>
                <div className="meta-card-item">
                  <span className="meta-item-label">Chuẩn Cục Dược (DAV)</span>
                  <strong className="text-emerald">Đạt chuẩn trần giá niêm yết</strong>
                </div>
              </div>

              {selectedTxForDetail.clinical_notes && (
                <div className="detail-notes-card">
                  <strong>Chỉ dẫn lâm sàng & Liều lượng:</strong>
                  <p>{selectedTxForDetail.clinical_notes}</p>
                </div>
              )}

              <div className="detail-qr-receipt-card">
                <QrCode size={48} className="qr-preview-icon" />
                <div className="qr-receipt-info">
                  <strong>Hóa đơn điện tử có mã xác thực QR</strong>
                  <span>Đã kiểm tra tem chống hàng giả và liên thông hồ sơ sức khỏe điện tử VNeID.</span>
                </div>
              </div>

              <button
                type="button"
                className="modal-btn primary-pink full"
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
