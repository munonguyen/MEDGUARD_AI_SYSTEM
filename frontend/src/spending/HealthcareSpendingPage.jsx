import { useEffect, useState, useMemo } from 'react';
import {
  Activity,
  AlertOctagon,
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
  Edit3,
  Eye,
  EyeOff,
  FilePlus2,
  FileScan,
  FileText,
  Filter,
  Folder,
  HeartPulse,
  HelpCircle,
  Info,
  LayoutGrid,
  PieChart,
  Pill,
  Plus,
  QrCode,
  Receipt,
  RefreshCw,
  Search,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Star,
  Stethoscope,
  Tag,
  Target,
  TestTube,
  TrendingDown,
  TrendingUp,
  UserCheck,
  WalletCards,
  X,
} from 'lucide-react';
import './HealthcareSpendingPage.css';
import { DataManagementAuthGate } from '../common/DataManagementAuthGate';
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
    color: '#f472b6', // Rosy pink
    icon: Pill,
    badge: 'Chuẩn GPP / DAV',
    description: 'Biệt dược gốc và thuốc Generic EU-GMP điều trị theo phác đồ bác sĩ',
  },
  {
    id: 'clinic',
    name: 'Khám & Viện phí điều trị',
    percentage: 33,
    amount_vnd: 4080785,
    color: '#34d399', // Mint green
    icon: Stethoscope,
    badge: 'BHYT Đúng Tuyến',
    description: 'Booking Care, tiền khám chuyên khoa và điều trị nội trú bệnh viện',
  },
  {
    id: 'diagnostics',
    name: 'Xét nghiệm & Cận lâm sàng',
    percentage: 14,
    amount_vnd: 1731242,
    color: '#38bdf8', // Cyan
    icon: TestTube,
    badge: 'ISO 15189',
    description: 'Công thức máu, nội soi tiêu hóa, sinh hóa gan thận và X-quang',
  },
  {
    id: 'supplements',
    name: 'Dược mỹ phẩm & TPCN',
    percentage: 11,
    amount_vnd: 1360261,
    color: '#fb923c', // Warm orange
    icon: Sparkles,
    badge: 'Chính Hãng',
    description: 'Men vi sinh, vitamin khoáng chất và dinh dưỡng hồi phục sau đợt ốm',
  },
  {
    id: 'supplies',
    name: 'Vật tư y tế tiêu hao',
    percentage: 1,
    amount_vnd: 123662,
    color: '#94a3b8', // Slate
    icon: FileText,
    badge: 'Vô trùng BYT',
    description: 'Băng gạc tiệt trùng, cồn sát khuẩn và nước muối sinh lý 0.9%',
  },
];

// Rich, Clinical Transactions adhering to Ministry of Health EMR & GPP standards
const INITIAL_TRANSACTIONS = [
  {
    id: 'tx_01',
    date: 'Hôm nay',
    raw_date: '2026-10-24',
    time: '15:20',
    title: 'Thuốc Nexium 40mg (Esomeprazole) & Phosphalugel Gel',
    provider: 'Nhà thuốc Long Châu - Chuẩn GPP',
    doctor: 'BS. CKI Trần Minh Đức (Khoa Tiêu Hóa)',
    icd10: 'K29.7 - Viêm dạ dày tá tràng cấp do NSAID',
    category: 'medication',
    category_name: 'Thuốc kê đơn GPP',
    source_type: 'gpp_pharmacy',
    amount_vnd: -480000,
    bhyt_covered_vnd: 384000,
    is_gpp: true,
    dav_compliant: true,
    dav_registration: 'VN-22145-19',
    bhyt_rate: 80,
    rx_code: 'RX-2026-1049',
    e_invoice_no: 'HD-2026-004918',
    treatment_status: 'Đang dùng (còn 12 ngày thuốc)',
    clinical_notes: 'Uống trước ăn sáng 30 phút • Giảm đau rát thượng vị dạ dày • Tuyệt đối không uống kèm NSAID khi đói',
    items: [
      { name: 'Nexium 40mg (Esomeprazole AstraZeneca)', qty: '14 viên', unit_price: 24000, dav_ceiling: 24500, amount: 336000 },
      { name: 'Phosphalugel (Gel Nhôm Phosphat 20%)', qty: '12 gói', unit_price: 12000, dav_ceiling: 12500, amount: 144000 },
    ],
    verified: true,
  },
  {
    id: 'tx_02',
    date: 'Hôm nay',
    raw_date: '2026-10-24',
    time: '09:15',
    title: 'Khám Chuyên khoa Nội Tiêu Hóa & Nội soi Dạ Dày',
    provider: 'Bệnh viện Đại học Y Dược TP.HCM',
    doctor: 'PGS. TS. BS Lê Quang Quốc Bảo',
    icd10: 'K29.7 - Viêm trợt niêm mạc thượng vị',
    category: 'clinic',
    category_name: 'Khám chuyên khoa',
    source_type: 'hospital_clinic',
    amount_vnd: -150000,
    bhyt_covered_vnd: 120000,
    is_gpp: true,
    dav_compliant: true,
    dav_registration: 'BYT-CS-0081',
    bhyt_rate: 80,
    rx_code: 'BS-CKI-892',
    e_invoice_no: 'BV-YDUOC-88912',
    treatment_status: 'Hẹn tái khám sau 14 ngày (07/11/2026)',
    clinical_notes: 'Nội soi tầm soát loét niêm mạc sau biến cố ADR Ibuprofen • Kê đơn phối hợp PPI bảo vệ dạ dày',
    items: [
      { name: 'Công khám chuyên khoa Tiêu hóa (Booking Care)', qty: '1 lượt', unit_price: 150000, dav_ceiling: 150000, amount: 150000 },
    ],
    verified: true,
  },
  {
    id: 'tx_03',
    date: 'Hôm qua',
    raw_date: '2026-10-23',
    time: '14:30',
    title: 'Xét nghiệm Men Gan (AST/ALT) & Sinh hóa Máu toàn phần',
    provider: 'Trung tâm Xét nghiệm Y khoa Diag',
    doctor: 'BS. Nguyễn Thị Thu Hà',
    icd10: 'R74.0 - Tăng nồng độ enzym gan nhẹ',
    category: 'diagnostics',
    category_name: 'Xét nghiệm cận lâm sàng',
    source_type: 'hospital_clinic',
    amount_vnd: -320000,
    bhyt_covered_vnd: 160000,
    is_gpp: true,
    dav_compliant: true,
    dav_registration: 'ISO-15189-DIAG',
    bhyt_rate: 50,
    rx_code: 'LAB-7741',
    e_invoice_no: 'HD-DIAG-09923',
    treatment_status: 'Kết quả bình thường (Men gan ổn định)',
    clinical_notes: 'Đánh giá chức năng tế bào gan và mức độ chuyển hóa thuốc an toàn trước đợt điều trị dài ngày',
    items: [
      { name: 'Xét nghiệm AST/ALT (Men gan)', qty: '1 mẫu', unit_price: 120000, dav_ceiling: 130000, amount: 120000 },
      { name: 'Tổng phân tích tế bào máu ngoại vi bằng laser', qty: '1 mẫu', unit_price: 200000, dav_ceiling: 210000, amount: 200000 },
    ],
    verified: true,
  },
  {
    id: 'tx_04',
    date: 'Hôm qua',
    raw_date: '2026-10-23',
    time: '10:05',
    title: 'Thuốc hạ áp Amlodipine 5mg (Generic EU-GMP Stada)',
    provider: 'Nhà thuốc An Khang - Chuẩn GPP',
    doctor: 'BS. CKII Phạm Hoàng Tâm (Khoa Tim Mạch)',
    icd10: 'I10 - Tăng huyết áp vô căn (Mãn tính)',
    category: 'medication',
    category_name: 'Thuốc mãn tính',
    source_type: 'gpp_pharmacy',
    amount_vnd: -165000,
    bhyt_covered_vnd: 132000,
    is_gpp: true,
    dav_compliant: true,
    dav_registration: 'VD-28491-17',
    bhyt_rate: 80,
    rx_code: 'RX-2026-0955',
    e_invoice_no: 'HD-AK-44019',
    treatment_status: 'Thuốc mãn tính • Uống cố định 8h sáng',
    clinical_notes: 'Biệt dược tương đương sinh học Norvasc 5mg • Tiết kiệm 38% chi phí hàng tháng mà huyết áp giữ vững 118/78 mmHg',
    items: [
      { name: 'Amlodipine Stada 5mg (Hộp 30 viên)', qty: '1 hộp', unit_price: 165000, dav_ceiling: 180000, amount: 165000 },
    ],
    verified: true,
  },
  {
    id: 'tx_05',
    date: '20/10/2026',
    raw_date: '2026-10-20',
    time: '16:40',
    title: 'Men vi sinh Enterogermina 5ml & Bổ sung Kẽm sinh học',
    provider: 'Nhà thuốc Pharmacity chuẩn GPP',
    doctor: 'Dược sĩ lâm sàng tư vấn tại quầy GPP',
    icd10: 'K59.9 - Rối loạn chức năng tiêu hóa nhẹ',
    category: 'supplements',
    category_name: 'Dược mỹ phẩm & TPCN',
    source_type: 'gpp_pharmacy',
    amount_vnd: -295000,
    bhyt_covered_vnd: 0,
    is_gpp: true,
    dav_compliant: true,
    dav_registration: 'VN-19942-16',
    bhyt_rate: 0,
    rx_code: 'TPCN-4410',
    e_invoice_no: 'HD-PMC-88120',
    treatment_status: 'Bổ trợ sau đợt kháng sinh',
    clinical_notes: 'Cân bằng hệ vi sinh đường ruột và tăng sức đề kháng niêm mạc tiêu hóa • Uống cách kháng sinh 2 tiếng',
    items: [
      { name: 'Enterogermina 5ml (Hộp 20 ống Sanofi)', qty: '1 hộp', unit_price: 295000, dav_ceiling: 300000, amount: 295000 },
    ],
    verified: true,
  },
  {
    id: 'tx_06',
    date: '18/10/2026',
    raw_date: '2026-10-18',
    time: '11:20',
    title: 'Bảo hiểm Xã hội TP.HCM Hoàn Viện Phí BHYT Đợt 2',
    provider: 'Bảo hiểm Xã hội TP.HCM (VssID Điện tử)',
    doctor: 'Hệ thống liên thông giám định BHYT Quốc gia',
    icd10: 'Z01.9 - Quyết toán giám định BHYT',
    category: 'refund',
    category_name: 'BHYT chi trả',
    source_type: 'hospital_clinic',
    amount_vnd: 1450000, // Inflow
    bhyt_covered_vnd: 1450000,
    is_gpp: true,
    dav_compliant: true,
    dav_registration: 'BHYT-QD-2026',
    bhyt_rate: 100,
    rx_code: 'BHYT-REF-8841',
    e_invoice_no: 'BHXH-QTOAN-1029',
    treatment_status: 'Đã hoàn tất thanh toán vào tài khoản',
    clinical_notes: 'Quyết toán trợ cấp BHYT đúng tuyến điều trị nội trú và cận lâm sàng theo Thông tư 20/2022/TT-BYT',
    items: [
      { name: 'Hoàn chi phí đồng thanh toán BHYT vượt mức quy định', qty: '1 khoản', unit_price: 1450000, dav_ceiling: 1450000, amount: 1450000 },
    ],
    verified: true,
  },
  {
    id: 'tx_07',
    date: '15/10/2026',
    raw_date: '2026-10-15',
    time: '08:50',
    title: 'Kháng sinh Augmentin 1g (Amoxicillin/Acid clavulanic GSK)',
    provider: 'Nhà thuốc Long Châu - Chuẩn GPP',
    doctor: 'BS. CKI Vũ Hải Yến (Khoa Hô Hấp)',
    icd10: 'J20.9 - Viêm phế quản cấp tính',
    category: 'medication',
    category_name: 'Thuốc kê đơn GPP',
    source_type: 'gpp_pharmacy',
    amount_vnd: -294000,
    bhyt_covered_vnd: 235200,
    is_gpp: true,
    dav_compliant: true,
    dav_registration: 'VN-18239-14',
    bhyt_rate: 80,
    rx_code: 'RX-2026-0912',
    e_invoice_no: 'HD-LC-00192',
    treatment_status: 'Đã khỏi dứt điểm sau phác đồ 7 ngày',
    clinical_notes: 'Kháng sinh đường hô hấp chính hãng GSK • Đạt nồng độ ức chế MIC tiêu diệt mầm bệnh dứt điểm 1 lần, không tái phát',
    items: [
      { name: 'Augmentin 1g (Hộp 14 viên GSK)', qty: '1 hộp', unit_price: 294000, dav_ceiling: 300000, amount: 294000 },
    ],
    verified: true,
  },
  {
    id: 'tx_08',
    date: '12/10/2026',
    raw_date: '2026-10-12',
    time: '17:15',
    title: 'Băng gạc tiệt trùng y tế & Nước muối sinh lý 0.9%',
    provider: 'Nhà thuốc Bệnh viện ĐHYD',
    doctor: 'Khoa Kiểm soát Nhiễm khuẩn',
    icd10: 'Z48.0 - Chăm sóc và thay băng vết thương',
    category: 'supplies',
    category_name: 'Vật tư y tế',
    source_type: 'hospital_clinic',
    amount_vnd: -65000,
    bhyt_covered_vnd: 0,
    is_gpp: true,
    dav_compliant: true,
    dav_registration: 'VT-BYT-2026',
    bhyt_rate: 0,
    rx_code: 'VT-0091',
    e_invoice_no: 'HD-BV-00441',
    treatment_status: 'Vết thương lành tốt',
    clinical_notes: 'Dụng cụ tiệt trùng thay băng vết mổ tại nhà • Đảm bảo vô khuẩn tuyệt đối tránh nhiễm trùng thứ phát',
    items: [
      { name: 'Gạc tiệt trùng 10x10cm (Gói 10 miếng)', qty: '2 gói', unit_price: 25000, dav_ceiling: 25000, amount: 50000 },
      { name: 'Nước muối sinh lý Natri Clorid 0.9% 500ml', qty: '1 chai', unit_price: 15000, dav_ceiling: 15000, amount: 15000 },
    ],
    verified: true,
  },
];

export function HealthcareSpendingPage({
  api,
  account = null,
  isGuest = false,
  onRequireAuth = null,
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

  // Budget target state
  const [showBudgetModal, setShowBudgetModal] = useState(false);
  const [budgetTarget, setBudgetTarget] = useState(() => {
    try {
      const val = localStorage.getItem('medguard_budget_target_vnd');
      return val ? parseInt(val, 10) : 15000000;
    } catch {
      return 15000000;
    }
  });
  const [inputBudgetVal, setInputBudgetVal] = useState('15000000');

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
  const [newTxDoctor, setNewTxDoctor] = useState('BS. CKI Trần Minh Đức');
  const [newTxIcd10, setNewTxIcd10] = useState('K29.7 - Viêm dạ dày tá tràng');
  const [newTxBhytEligible, setNewTxBhytEligible] = useState(true);
  const [newTxNotes, setNewTxNotes] = useState('');

  // Assessment state
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
    return 12366016; // Exact number from reference
  }, [assessment]);

  // Total BHYT paid or supplementary inflow
  const totalBhytCovered = useMemo(() => {
    if (assessment?.bhyt_paid_vnd) {
      return assessment.bhyt_paid_vnd;
    }
    return 8540000;
  }, [assessment]);

  // Budget calculations
  const remainingBudget = Math.max(0, budgetTarget - totalActualSpend);
  const budgetUtilizationPct = Math.min(100, Math.round((totalActualSpend / budgetTarget) * 100));

  // MedGuard 45-35-20 Care Allocation
  const allocation45 = Math.round(budgetTarget * 0.45);
  const allocation35 = Math.round(budgetTarget * 0.35);
  const allocation20 = Math.round(budgetTarget * 0.20);

  // Synchronize when unified chat events trigger
  useEffect(() => {
    const handleUnifiedChatSync = (event) => {
      const detail = event?.detail;
      if (detail?.expenseMutation) {
        setAssessment((prev) => ({
          ...prev,
          ...detail.expenseMutation,
        }));
        if (detail.expenseMutation.monthly_budget_target_vnd) {
          setBudgetTarget(detail.expenseMutation.monthly_budget_target_vnd);
        }
        if (detail.expenseMutation.recent_transactions?.length) {
          const formatted = detail.expenseMutation.recent_transactions.map((tx, idx) => ({
            id: tx.id || `tx_chat_${Date.now()}_${idx}`,
            date: 'Hôm nay',
            raw_date: new Date().toISOString().split('T')[0],
            time: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }),
            title: tx.title || 'Khoản chi y tế mới',
            provider: 'Nhà thuốc Long Châu - Chuẩn GPP',
            doctor: 'Dược sĩ lâm sàng tư vấn GPP',
            icd10: 'K29.7 - Viêm dạ dày cấp',
            category: tx.category || 'medication',
            category_name: tx.category === 'doctor' ? 'Khám chuyên khoa' : 'Thuốc kê đơn GPP',
            source_type: 'gpp_pharmacy',
            amount_vnd: -(Math.abs(tx.amount_vnd || 480000)),
            bhyt_covered_vnd: Math.round((tx.amount_vnd || 480000) * 0.8),
            is_gpp: true,
            dav_compliant: true,
            dav_registration: 'VN-22145-19',
            bhyt_rate: 80,
            rx_code: 'RX-SYNC-CHAT',
            e_invoice_no: `HD-CHAT-${Date.now()}`,
            treatment_status: 'Đồng bộ từ trợ lý lâm sàng MedGuard AI',
            clinical_notes: 'Đồng bộ tự động từ hội thoại tư vấn y tế MedGuard AI',
            items: [
              { name: tx.title || 'Thuốc kê đơn GPP', qty: '1 liệu trình', unit_price: Math.abs(tx.amount_vnd || 480000), dav_ceiling: Math.abs(tx.amount_vnd || 480000), amount: Math.abs(tx.amount_vnd || 480000) }
            ],
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
    if (txFilterTab === 'medication') {
      result = result.filter((tx) => tx.category === 'medication');
    } else if (txFilterTab === 'clinic') {
      result = result.filter((tx) => tx.category === 'clinic');
    } else if (txFilterTab === 'diagnostics') {
      result = result.filter((tx) => tx.category === 'diagnostics');
    } else if (txFilterTab === 'supplements') {
      result = result.filter((tx) => tx.category === 'supplements');
    } else if (txFilterTab === 'refund') {
      result = result.filter((tx) => tx.category === 'refund');
    } else if (txFilterTab === 'chronic') {
      result = result.filter((tx) => tx.category === 'medication' && tx.treatment_status?.includes('mãn tính'));
    }
    if (txSearchQuery.trim()) {
      const q = txSearchQuery.toLowerCase();
      result = result.filter(
        (tx) =>
          tx.title.toLowerCase().includes(q) ||
          tx.provider.toLowerCase().includes(q) ||
          (tx.doctor && tx.doctor.toLowerCase().includes(q)) ||
          (tx.icd10 && tx.icd10.toLowerCase().includes(q)) ||
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
      provider: newTxProvider.trim() || 'Cơ sở y tế đạt chuẩn GPP',
      doctor: newTxDoctor.trim() || 'Bác sĩ điều trị',
      icd10: newTxIcd10.trim() || 'K29.7 - Chẩn đoán lâm sàng',
      category: newTxCategory,
      category_name:
        newTxCategory === 'medication'
          ? 'Thuốc kê đơn GPP'
          : newTxCategory === 'clinic'
          ? 'Khám chuyên khoa'
          : newTxCategory === 'diagnostics'
          ? 'Xét nghiệm cận lâm sàng'
          : 'Dược phẩm & TPCN',
      source_type: 'gpp_pharmacy',
      amount_vnd: -amt,
      bhyt_covered_vnd: bhytCovered,
      is_gpp: true,
      dav_compliant: true,
      dav_registration: 'VN-BYT-2026',
      bhyt_rate: bhytRate,
      rx_code: `RX-${Math.floor(1000 + Math.random() * 9000)}`,
      e_invoice_no: `HD-APP-${Math.floor(10000 + Math.random() * 90000)}`,
      treatment_status: 'Giao dịch mới tạo',
      clinical_notes: newTxNotes.trim() || 'Khoản chi y tế do bệnh nhân tự khai báo bổ sung',
      items: [
        { name: newTxTitle.trim(), qty: '1 liệu trình', unit_price: amt, dav_ceiling: amt, amount: amt }
      ],
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

  // Handle budget update
  const handleUpdateBudgetSubmit = (e) => {
    e.preventDefault();
    const val = parseInt(inputBudgetVal, 10);
    if (!val || val <= 0) {
      onNotify?.('Vui lòng nhập hạn mức ngân sách hợp lệ.', 'error');
      return;
    }
    setBudgetTarget(val);
    try {
      localStorage.setItem('medguard_budget_target_vnd', String(val));
    } catch {}
    setShowBudgetModal(false);
    onNotify?.(`Đã cập nhật hạn mức ngân sách y tế tháng: ${formatVnd(val)}`, 'success');
  };

  if (isGuest) {
    return (
      <DataManagementAuthGate
        moduleTitle="Quản Trị Chi Phí Y Tế, BHYT & Lộ Trình Tiết Kiệm Care"
        moduleType="spending"
        onRequireAuth={onRequireAuth}
        onBackToChat={onBackToChat}
      />
    );
  }

  const monthlyTrendSeries = [
    { month: "T5/26", outOfPocket: 14.2, bhyt: 5.8, genericSaved: 2.1 },
    { month: "T6/26", outOfPocket: 16.5, bhyt: 6.4, genericSaved: 2.8 },
    { month: "T7/26", outOfPocket: 13.8, bhyt: 7.1, genericSaved: 3.2 },
    { month: "T8/26", outOfPocket: 15.1, bhyt: 7.5, genericSaved: 3.6 },
    { month: "T9/26", outOfPocket: 12.9, bhyt: 7.9, genericSaved: 4.1 },
    { month: "T10/26", outOfPocket: +(totalActualSpend / 1000000).toFixed(1), bhyt: +(totalBhytCovered / 1000000).toFixed(1), genericSaved: 4.8 },
  ];

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
            <ArrowLeft size={16} />
            <span>Hội thoại lâm sàng</span>
          </button>
          <div className="header-title-box">
            <div className="header-subtitle-tag">
              <span className="live-dot" />
              <span>MEDGUARD WEALTH & CLINICAL PHARMACOECONOMICS • HỆ THỐNG QUẢN LÝ CHI TIÊU</span>
            </div>
            <h1 className="header-main-title">Quản Trị Chi Phí Y Tế & Lộ Trình Tiết Kiệm Care</h1>
          </div>
        </div>

        <div className="header-right-col">
          {/* Budget Setting Trigger */}
          <button
            type="button"
            className="budget-pill-trigger-btn"
            onClick={() => {
              setInputBudgetVal(String(budgetTarget));
              setShowBudgetModal(true);
            }}
            title="Điều chỉnh hạn mức ngân sách y tế tháng"
          >
            <Target size={15} className="text-pink" />
            <span>Hạn mức: <strong>{formatVnd(budgetTarget)}</strong></span>
            <Edit3 size={13} className="edit-icon" />
          </button>

          {/* Month Selector */}
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
          2. CLINICAL SAFETY GATE & TREATMENT EFFICIENCY SCORE (TES) BANNER
          ==================================================================== */}
      <section className="clinical-safety-gate-banner">
        <div className="safety-gate-left">
          <div className="safety-shield-icon-box">
            <ShieldCheck size={24} />
          </div>
          <div className="safety-text-group">
            <div className="safety-title-line">
              <span className="safety-gate-badge">CỔNG AN TOÀN Y KHOA (CLINICAL SAFETY GATE)</span>
              <strong>100% Khuyến Nghị Đạt Chuẩn Dược Lâm Sàng</strong>
            </div>
            <p className="safety-guideline-desc">
              Ưu tiên an toàn tuyệt đối cho người bệnh. Tiết kiệm tài chính là tối ưu hóa phương thức (mua đúng thuốc chuẩn GPP, dùng BHYT đúng tuyến, thay thế Generic EU-GMP), tuyệt đối không trì hoãn khám bệnh khi có dấu hiệu cờ đỏ.
            </p>
          </div>
        </div>

        <div className="safety-gate-right-tes">
          <div className="tes-score-card">
            <div className="tes-score-top">
              <span className="tes-label">Chỉ Số Hiệu Quả Điều Trị (TES):</span>
              <strong className="tes-rank-tag rank-a">HẠNG A (86/100)</strong>
            </div>
            <div className="tes-progress-track">
              <div className="tes-progress-fill" style={{ width: '86%' }} />
            </div>
            <span className="tes-subtext">91.8% Chi tiêu chuẩn GPP & BHYT • Chỉ 8.2% chi phí lãng phí</span>
          </div>
        </div>
      </section>

      {/* ====================================================================
          3. 4 QUICK ACTION TILES (MINT/TEAL STYLE AS IN REFERENCE)
          ==================================================================== */}
      <section className="web-quick-actions-bar">
        <button
          type="button"
          className="web-action-tile-btn"
          onClick={() => setShowAddModal(true)}
        >
          <div className="tile-mint-icon">
            <FilePlus2 size={24} />
          </div>
          <div className="tile-info-text">
            <strong>Nhập giao dịch y tế</strong>
            <span>Ghi nhận đơn thuốc & Quét hóa đơn OCR</span>
          </div>
        </button>

        <button
          type="button"
          className="web-action-tile-btn"
          onClick={() => {
            onNotify?.('Xu hướng chi tiêu y tế tháng 10 giảm 28.5% nhờ dùng thuốc Generic EU-GMP đúng trần DAV!', 'info');
          }}
        >
          <div className="tile-mint-icon">
            <TrendingUp size={24} />
          </div>
          <div className="tile-info-text">
            <strong>Biến động thu chi</strong>
            <span>Giảm 941.854 ₫ so với cùng kỳ tháng trước</span>
          </div>
        </button>

        <button
          type="button"
          className="web-action-tile-btn"
          onClick={() => setShowCategoryDetail((v) => !v)}
        >
          <div className="tile-mint-icon">
            <Folder size={24} />
          </div>
          <div className="tile-info-text">
            <strong>Quản lý danh mục</strong>
            <span>5 nhóm chi phí y tế & Tỷ lệ BHYT 80%</span>
          </div>
        </button>

        <button
          type="button"
          className="web-action-tile-btn"
          onClick={() => {
            onNotify?.('Đã mở bảng tra cứu trần giá niêm yết Cục Quản Lý Dược (DAV)', 'info');
          }}
        >
          <div className="tile-mint-icon">
            <LayoutGrid size={24} />
          </div>
          <div className="tile-info-text">
            <strong>Tiện ích Cục Dược DAV</strong>
            <span>Tra giá trần thuốc & Tiết kiệm Generic</span>
          </div>
        </button>
      </section>

      {/* ====================================================================
          4. DUAL SUMMARY CARDS & BUDGET PROGRESS
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
                <span className="kpi-label-text">Chi tiêu thực tế</span>
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
            <div className="kpi-budget-progress-wrap">
              <div className="budget-bar-labels">
                <span>Chi {budgetUtilizationPct}% hạn mức</span>
                <span>Còn lại: <strong className="text-emerald">{formatVnd(remainingBudget, hideAmounts)}</strong></span>
              </div>
              <div className="budget-bar-track">
                <div
                  className="budget-bar-fill"
                  style={{ width: `${budgetUtilizationPct}%`, backgroundColor: budgetUtilizationPct > 90 ? '#ef4444' : '#ff4d79' }}
                />
              </div>
            </div>
          </div>

          {/* Card 2: BHYT & Thu ⬆ (Emerald green badge matching reference) */}
          <div className="web-kpi-card income-kpi-card">
            <div className="kpi-card-head">
              <div className="kpi-badge-wrap">
                <span className="kpi-icon-bubble green">
                  <TrendingUp size={16} />
                </span>
                <span className="kpi-label-text">Quỹ BHYT & Trợ cấp Care</span>
                <span className="kpi-arrow-tag up">↑</span>
              </div>
              <span className="kpi-source-pill">Bảo hiểm Xã hội VssID</span>
            </div>
            <div className="kpi-large-amount text-emerald">
              {formatVnd(totalBhytCovered, hideAmounts)}
            </div>
            <div className="kpi-allocation-summary-box">
              <span className="alloc-pill-tag">Phác đồ tối ưu 45 - 35 - 20</span>
              <div className="alloc-ratios-mini">
                <span>Khám BHYT: <strong>45%</strong></span>
                <span>Thuốc GPP: <strong>35%</strong></span>
                <span>Dự phòng: <strong>20%</strong></span>
              </div>
            </div>
          </div>
        </div>

        {/* MULTI-CHART SUITE FOR SPENDING: 6-Month Stacked Bar/Line + 5-Axis TES Radar + DAV Price Bars */}
        <div className="spending-multi-charts-suite">
          {/* Chart A: 6-Month Stacked Bar & Savings Trend SVG Chart */}
          <div className="spending-chart-card">
            <div className="sc-head">
              <div>
                <span className="sc-kicker">BIỂU ĐỒ CỘT CHỒNG & XU HƯỚNG 6 THÁNG</span>
                <h4>Biến Động Chi Trả Thực Tế, Quỹ BHYT & Tiết Kiệm Generic (Triệu ₫)</h4>
              </div>
              <div className="sc-legend">
                <span className="sc-leg rose">■ Tự chi trả</span>
                <span className="sc-leg teal">■ Quỹ BHYT</span>
                <span className="sc-leg blue">● Tiết kiệm Generic</span>
              </div>
            </div>
            <svg viewBox="0 0 460 155" className="spending-trend-svg" role="img" aria-label="Biểu đồ xu hướng chi tiêu y tế 6 tháng">
              {[0, 10, 20, 30].map((v) => {
                const y = 128 - (v / 32) * 100;
                return (
                  <g key={v}>
                    <line x1="34" y1={y} x2="440" y2={y} stroke="#e2e8f0" strokeDasharray="3 3" />
                    <text x="28" y={y + 3} textAnchor="end" className="sc-axis-txt">{v}tr</text>
                  </g>
                );
              })}
              {monthlyTrendSeries.map((m, idx) => {
                const x = 62 + idx * 66;
                const hOut = Math.min(72, (m.outOfPocket / 32) * 100);
                const hBhyt = Math.min(45, (m.bhyt / 32) * 100);
                const yOut = 128 - hOut;
                const yBhyt = yOut - hBhyt;
                return (
                  <g key={m.month}>
                    <rect x={x - 13} y={yOut} width="26" height={hOut} rx="3" fill="#f43f5e" fillOpacity="0.82" />
                    <rect x={x - 13} y={yBhyt} width="26" height={hBhyt} rx="3" fill="#0d9488" fillOpacity="0.88" />
                    <text x={x} y={yBhyt - 5} textAnchor="middle" className="sc-val-txt">{m.outOfPocket}tr</text>
                    <text x={x} y="145" textAnchor="middle" className="sc-x-txt">{m.month}</text>
                  </g>
                );
              })}
              <polyline
                fill="none"
                stroke="#2563eb"
                strokeWidth="2.5"
                points={monthlyTrendSeries.map((m, idx) => `${62 + idx * 66},${128 - (m.genericSaved / 8) * 85}`).join(" ")}
              />
            </svg>
          </div>

          {/* Chart B: Drug Price Savings Horizontal Bar Chart (Actual vs DAV Ceiling vs Generic EU-GMP) */}
          <div className="spending-chart-card">
            <div className="sc-head">
              <div>
                <span className="sc-kicker">BIỂU ĐỒ ĐỐI SÁNH GIÁ DƯỢC PHẨM</span>
                <h4>So Sánh Giá Biệt Dược Gốc vs Generic EU-GMP Chuẩn DAV</h4>
              </div>
              <span className="sc-save-pill">Tiết kiệm 38% – 40%</span>
            </div>
            <div className="dav-visual-bars-list">
              {[
                { name: "Esomeprazole 40mg (Dạ dày)", brand: 24000, generic: 14500, savePct: 40 },
                { name: "Augmentin 1g (Kháng sinh)", brand: 21000, generic: 13200, savePct: 37 },
                { name: "Amlodipine 5mg (Huyết áp)", brand: 5500, generic: 3400, savePct: 38 },
              ].map((d) => (
                <div key={d.name} className="dav-vbar-group">
                  <div className="dav-vbar-top">
                    <strong>{d.name}</strong>
                    <span className="dav-vbar-save">Tiết kiệm {d.savePct}% khi đổi Generic EU-GMP</span>
                  </div>
                  <div className="dav-vbar-Dual">
                    <div className="dav-vbar-line">
                      <span>Biệt dược</span>
                      <div className="dav-vbar-track">
                        <div className="dav-vbar-fill brand" style={{ width: "92%" }} />
                      </div>
                      <b>{d.brand.toLocaleString("vi-VN")} ₫</b>
                    </div>
                    <div className="dav-vbar-line">
                      <span>Generic EU</span>
                      <div className="dav-vbar-track">
                        <div className="dav-vbar-fill generic" style={{ width: `${100 - d.savePct}%` }} />
                      </div>
                      <b className="text-emerald">{d.generic.toLocaleString("vi-VN")} ₫</b>
                    </div>
                  </div>
                </div>
              ))}
            </div>
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
                Tiết kiệm 28.5% chi phí dược phẩm nhờ dùng thuốc Generic EU-GMP nhóm 1 đạt tương đương sinh học đúng trần DAV.
              </span>
            </div>
          </div>
          <button
            type="button"
            className="banner-action-btn"
            onClick={() => onNotify?.('Báo cáo chi tiết tối ưu hóa kinh tế dược học đã được cập nhật!', 'info')}
          >
            <span>Xem phân tích dược học</span>
            <ChevronRight size={14} />
          </button>
        </div>
      </section>

      {/* ====================================================================
          5. PHÁC ĐỒ PHÂN BỔ DÒNG TIỀN TỐI ƯU (MEDGUARD 45 - 35 - 20)
          ==================================================================== */}
      <section className="medguard-allocation-45-35-20-section">
        <div className="allocation-header-row">
          <div className="alloc-header-left">
            <Sparkles size={18} className="text-pink" />
            <h3 className="section-title">Phác Đồ Phân Bổ Dòng Tiền Y Tế Tối Ưu (MedGuard 45 - 35 - 20)</h3>
          </div>
          <span className="alloc-tag-badge">Khuyến Nghị Chuyên Gia Y Khoa</span>
        </div>

        <div className="allocation-three-grid">
          {/* Card 1: 45% Khám Booking Care & BHYT */}
          <div className="alloc-card card-45">
            <div className="alloc-card-top">
              <div className="alloc-pct-bubble pink">45%</div>
              <strong className="alloc-amount-text">{formatVnd(allocation45, hideAmounts)}</strong>
            </div>
            <h4 className="alloc-card-name">Khám Booking Care & BHYT</h4>
            <p className="alloc-card-desc">
              Khám chuyên khoa sớm đúng tuyến tại BV Đại học Y Dược giúp quỹ BHYT chi trả 80–100%, dứt điểm bệnh ban đầu tránh biến chứng tốn kém.
            </p>
            <div className="alloc-card-footer">
              <CheckCircle2 size={13} className="text-emerald" />
              <span>Tiết kiệm 80% viện phí đúng tuyến</span>
            </div>
          </div>

          {/* Card 2: 35% Thuốc GPP & Generic Nhóm 1 */}
          <div className="alloc-card card-35">
            <div className="alloc-card-top">
              <div className="alloc-pct-bubble mint">35%</div>
              <strong className="alloc-amount-text">{formatVnd(allocation35, hideAmounts)}</strong>
            </div>
            <h4 className="alloc-card-name">Thuốc GPP & Generic EU-GMP</h4>
            <p className="alloc-card-desc">
              Mua thuốc tại chuỗi GPP uy tín (Long Châu, An Khang), ưu tiên biệt dược Generic Nhóm 1 EU-GMP có sinh khả dụng đạt nồng độ ức chế MIC.
            </p>
            <div className="alloc-card-footer">
              <CheckCircle2 size={13} className="text-emerald" />
              <span>Tiết kiệm 35–40% so với Biệt dược gốc</span>
            </div>
          </div>

          {/* Card 3: 20% Quỹ Dự Phòng Sức Khỏe */}
          <div className="alloc-card card-20">
            <div className="alloc-card-top">
              <div className="alloc-pct-bubble cyan">20%</div>
              <strong className="alloc-amount-text">{formatVnd(allocation20, hideAmounts)}</strong>
            </div>
            <h4 className="alloc-card-name">Quỹ Dự Phòng Sức Khỏe</h4>
            <p className="alloc-card-desc">
              Dành riêng cho xét nghiệm tầm soát chức năng gan thận định kỳ, dinh dưỡng y học và xử lý các đợt bùng phát triệu chứng cấp tính.
            </p>
            <div className="alloc-card-footer">
              <CheckCircle2 size={13} className="text-emerald" />
              <span>Ngăn ngừa biến chứng nặng phải nhập viện</span>
            </div>
          </div>
        </div>
      </section>

      {/* ====================================================================
          6. 2-COLUMN MAIN DASHBOARD (DONUT CHART & DAV BENCHMARK)
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
                5 Nhóm Danh Mục
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
                    <th>Số ĐK / Phân nhóm</th>
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
                      <span className="cell-sub">Kháng tiết acid dạ dày (Nexium)</span>
                    </td>
                    <td><code>VN-22145-19</code></td>
                    <td>24.000 ₫/viên</td>
                    <td>24.500 ₫/viên</td>
                    <td className="text-emerald">14.500 ₫/viên</td>
                    <td><span className="table-badge success">Tiết kiệm 40%</span></td>
                  </tr>
                  <tr>
                    <td>
                      <strong>Thuốc Augmentin 1g</strong>
                      <span className="cell-sub">Kháng sinh Amoxicillin/Acid clavulanic</span>
                    </td>
                    <td><code>VN-18239-14</code></td>
                    <td>21.000 ₫/viên</td>
                    <td>21.800 ₫/viên</td>
                    <td className="text-emerald">13.200 ₫/viên</td>
                    <td><span className="table-badge info">Chuẩn trần DAV</span></td>
                  </tr>
                  <tr>
                    <td>
                      <strong>Thuốc hạ áp Amlodipine 5mg</strong>
                      <span className="cell-sub">Generic EU-GMP Stada</span>
                    </td>
                    <td><code>VD-28491-17</code></td>
                    <td>5.500 ₫/viên</td>
                    <td>6.000 ₫/viên</td>
                    <td className="text-emerald">3.400 ₫/viên</td>
                    <td><span className="table-badge success">Tiết kiệm 38%</span></td>
                  </tr>
                  <tr>
                    <td>
                      <strong>Khám Nội Tiêu Hóa</strong>
                      <span className="cell-sub">Booking Care BV Đại học Y Dược</span>
                    </td>
                    <td><code>BYT-CS-0081</code></td>
                    <td>150.000 ₫/lượt</td>
                    <td>150.000 ₫/lượt</td>
                    <td className="text-emerald">BHYT trả 80%</td>
                    <td><span className="table-badge bhyt">Hưởng 80% BHYT</span></td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* 3 Open-Source Trust Metrics */}
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
          7. SMART RECOMMENDATIONS (KHUYẾN NGHỊ KINH TẾ DƯỢC HỌC THÔNG MINH)
          ==================================================================== */}
      <section className="smart-recommendations-section">
        <div className="recs-header-row">
          <div className="recs-title-box">
            <Sparkles size={18} className="text-pink" />
            <h3 className="section-title">Khuyến Nghị Kinh Tế Dược Học Thông Minh (MedGuard AI)</h3>
          </div>
          <span className="recs-badge">3 Giải Pháp Tối Ưu</span>
        </div>

        <div className="recs-cards-grid">
          {/* Rec 1 */}
          <div className="rec-card-box">
            <div className="rec-card-top">
              <span className="priority-pill high">ƯU TIÊN CAO</span>
              <span className="saving-highlight-pill">Tiết kiệm ~420.000 ₫ / tháng</span>
            </div>
            <h4 className="rec-card-title">Chuyển sang Generic Nhóm 1 EU-GMP cho Thuốc Dạ Dày</h4>
            <p className="rec-card-body">
              Biệt dược Esomeprazole Stada 40mg đạt chuẩn tương đương sinh học 99.2% so với Nexium 40mg của AstraZeneca nhưng giá thành thấp hơn 40%.
            </p>
            <div className="rec-card-rationale">
              <strong>Cơ sở lâm sàng: </strong>
              <span>Được Cục Quản lý Dược cấp phép lưu hành Nhóm 1, nồng độ ức chế acid dạ dày tương đương, không gây tác dụng phụ.</span>
            </div>
            <button
              type="button"
              className="rec-cta-btn"
              onClick={() => onNotify?.('Đã lưu đề xuất thuốc Generic EU-GMP vào danh mục gợi ý khi đi nhà thuốc!', 'success')}
            >
              <span>Xem biệt dược thay thế</span>
              <ChevronRight size={14} />
            </button>
          </div>

          {/* Rec 2 */}
          <div className="rec-card-box">
            <div className="rec-card-top">
              <span className="priority-pill medium">QUYỀN LỢI BHYT</span>
              <span className="saving-highlight-pill">Tiết kiệm ~680.000 ₫ / đợt</span>
            </div>
            <h4 className="rec-card-title">Sử Dụng Giấy Chuyển Tuyến BHYT Khám Tiêu Hóa</h4>
            <p className="rec-card-body">
              Khi có giấy chuyển tuyến từ trung tâm y tế quận lên BV Đại học Y Dược, chi phí nội soi và tiền khám chuyên khoa được Quỹ BHYT chi trả 80%.
            </p>
            <div className="rec-card-rationale">
              <strong>Cơ sở pháp lý: </strong>
              <span>Áp dụng quy định thông tuyến BHYT theo Luật Bảo hiểm Y tế và Thông tư 20/2022/TT-BYT.</span>
            </div>
            <button
              type="button"
              className="rec-cta-btn"
              onClick={() => onNotify?.('Đã mở hướng dẫn xin giấy chuyển tuyến BHYT đúng quy định!', 'info')}
            >
              <span>Hướng dẫn thủ tục BHYT</span>
              <ChevronRight size={14} />
            </button>
          </div>

          {/* Rec 3 */}
          <div className="rec-card-box">
            <div className="rec-card-top">
              <span className="priority-pill standard">CHỐNG LÃNG PHÍ</span>
              <span className="saving-highlight-pill">Tránh tái phát & Kháng thuốc</span>
            </div>
            <h4 className="rec-card-title">Tuyệt Đối Chấm Dứt Mua Liều Lẻ Tại Tiệm Tự Do</h4>
            <p className="rec-card-body">
              Dùng kháng sinh cắt liều lẻ 2–3 ngày không đủ nồng độ ức chế MIC gây vi khuẩn kháng thuốc (AMR), dẫn đến bệnh tái phát 3–4 lần tốn kém hơn 500.000 ₫.
            </p>
            <div className="rec-card-rationale">
              <strong>Cảnh báo y khoa: </strong>
              <span>100% Thuốc điều trị cần mua đủ phác đồ tại chuỗi GPP có hóa đơn VAT và tư vấn của dược sĩ lâm sàng.</span>
            </div>
            <button
              type="button"
              className="rec-cta-btn"
              onClick={() => onNotify?.('Đã mở bản đồ các nhà thuốc chuẩn GPP gần bạn nhất!', 'info')}
            >
              <span>Tìm nhà thuốc chuẩn GPP</span>
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      </section>

      {/* ====================================================================
          8. FULL-WIDTH DETAILED CLINICAL EXPENSE HISTORY
          ==================================================================== */}
      <section className="web-panel-card full-width-ledger-section">
        <div className="ledger-header-bar">
          <div className="ledger-title-left">
            <Coins size={20} className="text-pink" />
            <h2 className="ledger-heading-title">Lịch Sử Chi Tiêu Y Tế Chi Tiết & Toa Thuốc</h2>
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
              <span>Đồng bộ EMR</span>
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
              placeholder="Tìm kiếm theo tên thuốc, bác sĩ, bệnh viện, mã chẩn đoán ICD-10, mã toa thuốc (ví dụ: Nexium, K29.7, Long Châu, RX-1049)..."
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
              { id: 'medication', label: 'Thuốc kê đơn GPP' },
              { id: 'clinic', label: 'Khám & Viện phí' },
              { id: 'diagnostics', label: 'Xét nghiệm' },
              { id: 'supplements', label: 'TPCN & Dinh dưỡng' },
              { id: 'refund', label: 'BHYT chi trả' },
              { id: 'chronic', label: 'Thuốc mãn tính' },
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
                              {tx.doctor && (
                                <span className="tx-card-doctor">
                                  <UserCheck size={12} />
                                  <span>{tx.doctor}</span>
                                </span>
                              )}
                            </div>

                            {/* Clinical & Regulatory Badges */}
                            <div className="tx-card-badges-row">
                              {tx.is_gpp && <span className="reg-badge gpp">Chuẩn GPP</span>}
                              {tx.dav_compliant && <span className="reg-badge dav">Đúng trần DAV</span>}
                              {tx.bhyt_rate > 0 && (
                                <span className="reg-badge bhyt">Hưởng BHYT {tx.bhyt_rate}%</span>
                              )}
                              {tx.icd10 && <span className="reg-badge icd">{tx.icd10}</span>}
                              {tx.rx_code && <span className="reg-badge rx">{tx.rx_code}</span>}
                              {tx.dav_registration && (
                                <span className="reg-badge sdk">SĐK: {tx.dav_registration}</span>
                              )}
                            </div>

                            {tx.clinical_notes && (
                              <p className="tx-card-clinical-notes">
                                <strong>Chỉ dẫn lâm sàng: </strong>{tx.clinical_notes}
                              </p>
                            )}

                            {tx.treatment_status && (
                              <span className="tx-treatment-status-tag">
                                <Clock size={11} />
                                <span>{tx.treatment_status}</span>
                              </span>
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

                          <button type="button" className="view-receipt-link-btn">
                            <Receipt size={12} />
                            <span>Xem hóa đơn VAT</span>
                          </button>
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

              <div className="form-fields-two-col">
                <div className="form-field-item">
                  <label>Cơ sở y tế / Nhà thuốc thực hiện</label>
                  <input
                    type="text"
                    placeholder="Nhà thuốc Long Châu, BV Đại học Y Dược..."
                    value={newTxProvider}
                    onChange={(e) => setNewTxProvider(e.target.value)}
                  />
                </div>

                <div className="form-field-item">
                  <label>Bác sĩ / Dược sĩ chỉ định</label>
                  <input
                    type="text"
                    placeholder="BS. CKI Trần Minh Đức..."
                    value={newTxDoctor}
                    onChange={(e) => setNewTxDoctor(e.target.value)}
                  />
                </div>
              </div>

              <div className="form-field-item">
                <label>Mã chẩn đoán bệnh ICD-10</label>
                <input
                  type="text"
                  placeholder="Ví dụ: K29.7 - Viêm dạ dày; I10 - Tăng huyết áp..."
                  value={newTxIcd10}
                  onChange={(e) => setNewTxIcd10(e.target.value)}
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
                <h3>Chi Tiết Chứng Từ Hóa Đơn & Đơn Thuốc Điện Tử</h3>
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
                <div className="hero-top-badges">
                  <span className="hero-cat-pill">{selectedTxForDetail.category_name}</span>
                  {selectedTxForDetail.rx_code && (
                    <span className="hero-rx-pill">Mã toa: {selectedTxForDetail.rx_code}</span>
                  )}
                  {selectedTxForDetail.e_invoice_no && (
                    <span className="hero-invoice-pill">HĐ: {selectedTxForDetail.e_invoice_no}</span>
                  )}
                </div>

                <h4 className="hero-tx-name">{selectedTxForDetail.title}</h4>
                <div className="hero-tx-amount">
                  {formatVnd(selectedTxForDetail.amount_vnd, hideAmounts)}
                </div>
                {selectedTxForDetail.bhyt_covered_vnd > 0 && (
                  <span className="hero-bhyt-tag">
                    Bảo hiểm Y tế hỗ trợ chi trả: {formatVnd(selectedTxForDetail.bhyt_covered_vnd, hideAmounts)} ({selectedTxForDetail.bhyt_rate}%)
                  </span>
                )}
              </div>

              {/* Items Breakdown Table */}
              {selectedTxForDetail.items?.length > 0 && (
                <div className="detail-items-table-card">
                  <div className="table-caption-line">
                    <Receipt size={14} className="text-emerald" />
                    <strong>Chi tiết các thuốc & dịch vụ trong đơn:</strong>
                  </div>
                  <table className="detail-items-table">
                    <thead>
                      <tr>
                        <th>Tên thuốc / Hoạt chất</th>
                        <th>Số lượng</th>
                        <th>Đơn giá</th>
                        <th>Trần DAV</th>
                        <th>Thành tiền</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedTxForDetail.items.map((it, idx) => (
                        <tr key={idx}>
                          <td><strong>{it.name}</strong></td>
                          <td>{it.qty}</td>
                          <td>{formatVnd(it.unit_price, hideAmounts)}</td>
                          <td className="text-emerald">{formatVnd(it.dav_ceiling, hideAmounts)}</td>
                          <td><strong>{formatVnd(it.amount, hideAmounts)}</strong></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <div className="detail-meta-two-col">
                <div className="meta-info-card">
                  <span className="meta-lbl">Cơ sở khám chữa bệnh / Nhà thuốc</span>
                  <strong>{selectedTxForDetail.provider}</strong>
                </div>
                <div className="meta-info-card">
                  <span className="meta-lbl">Bác sĩ / Dược sĩ phụ trách</span>
                  <strong>{selectedTxForDetail.doctor || 'Bác sĩ chuyên khoa'}</strong>
                </div>
                <div className="meta-info-card">
                  <span className="meta-lbl">Chẩn đoán y khoa ICD-10</span>
                  <code className="text-pink">{selectedTxForDetail.icd10 || 'K29.7'}</code>
                </div>
                <div className="meta-info-card">
                  <span className="meta-lbl">Kiểm soát trần giá DAV (Cục Quản Lý Dược)</span>
                  <strong className="text-emerald">Đạt chuẩn trần giá niêm yết 100%</strong>
                </div>
              </div>

              {selectedTxForDetail.clinical_notes && (
                <div className="detail-clinical-notes-card">
                  <strong>Chỉ dẫn lâm sàng & Liều dùng:</strong>
                  <p>{selectedTxForDetail.clinical_notes}</p>
                </div>
              )}

              <div className="qr-verification-box">
                <QrCode size={48} className="qr-code-icon" />
                <div className="qr-info-text">
                  <strong>Hóa đơn điện tử y tế có mã xác thực QR</strong>
                  <span>
                    Đã kiểm thực tem chống hàng giả, đạt chuẩn GPP và liên thông Hệ thống Đơn thuốc Quốc gia (donthuocquocgia.vn) & Hồ sơ sức khỏe VNeID.
                  </span>
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

      {/* ====================================================================
          MODAL 3: CẬP NHẬT HẠN MỨC NGÂN SÁCH THÁNG
          ==================================================================== */}
      {showBudgetModal && (
        <div className="web-modal-backdrop" onClick={() => setShowBudgetModal(false)}>
          <div className="web-modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header-line">
              <div className="modal-title-left">
                <Target size={20} className="text-pink" />
                <h3>Thiết Lập Hạn Mức Ngân Sách Y Tế Tháng</h3>
              </div>
              <button
                type="button"
                className="close-modal-btn"
                onClick={() => setShowBudgetModal(false)}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleUpdateBudgetSubmit} className="modal-form-body">
              <p className="modal-intro-text">
                Hệ thống sẽ dựa vào hạn mức này để tự động tính toán tỷ lệ phân bổ tối ưu theo phác đồ MedGuard (45% Khám sớm & BHYT, 35% Thuốc GPP, 20% Quỹ dự phòng).
              </p>

              <div className="form-field-item">
                <label>Hạn mức ngân sách mong muốn (VNĐ / Tháng)</label>
                <input
                  type="number"
                  min="500000"
                  step="500000"
                  value={inputBudgetVal}
                  onChange={(e) => setInputBudgetVal(e.target.value)}
                  required
                />
              </div>

              {/* Quick Preset Buttons */}
              <div className="budget-presets-row">
                <span className="presets-label">Gợi ý nhanh:</span>
                {[5000000, 10000000, 15000000, 20000000].map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    className="preset-btn"
                    onClick={() => setInputBudgetVal(String(preset))}
                  >
                    {formatVnd(preset)}
                  </button>
                ))}
              </div>

              <div className="modal-buttons-row">
                <button
                  type="button"
                  className="modal-action-btn cancel"
                  onClick={() => setShowBudgetModal(false)}
                >
                  Hủy
                </button>
                <button type="submit" className="modal-action-btn submit-pink">
                  Lưu hạn mức
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
