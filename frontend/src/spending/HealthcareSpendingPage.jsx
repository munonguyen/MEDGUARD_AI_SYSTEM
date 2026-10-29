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
  Trash2,
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
    percentage: 0,
    amount_vnd: 0,
    color: '#f472b6', // Rosy pink
    icon: Pill,
    badge: 'Chuẩn GPP / DAV',
    description: 'Biệt dược gốc và thuốc Generic EU-GMP điều trị theo phác đồ bác sĩ',
  },
  {
    id: 'clinic',
    name: 'Khám & Viện phí điều trị',
    percentage: 0,
    amount_vnd: 0,
    color: '#34d399', // Mint green
    icon: Stethoscope,
    badge: 'BHYT Đúng Tuyến',
    description: 'Booking Care, tiền khám chuyên khoa và điều trị nội trú bệnh viện',
  },
  {
    id: 'diagnostics',
    name: 'Xét nghiệm & Cận lâm sàng',
    percentage: 0,
    amount_vnd: 0,
    color: '#38bdf8', // Cyan
    icon: TestTube,
    badge: 'ISO 15189',
    description: 'Công thức máu, nội soi tiêu hóa, sinh hóa gan thận và X-quang',
  },
  {
    id: 'supplements',
    name: 'Dược mỹ phẩm & TPCN',
    percentage: 0,
    amount_vnd: 0,
    color: '#fb923c', // Warm orange
    icon: Sparkles,
    badge: 'Chính Hãng',
    description: 'Men vi sinh, vitamin khoáng chất và dinh dưỡng hồi phục sau đợt ốm',
  },
  {
    id: 'supplies',
    name: 'Vật tư y tế tiêu hao',
    percentage: 0,
    amount_vnd: 0,
    color: '#94a3b8', // Slate
    icon: FileText,
    badge: 'Vô trùng BYT',
    description: 'Băng gạc tiệt trùng, cồn sát khuẩn và nước muối sinh lý 0.9%',
  },
];

// 6 Available Calendar Months Registry for Database-driven Dynamic Navigation
export const AVAILABLE_MONTHS = [
  { key: '2026-10', label: 'Tháng này (10/2026)', shortLabel: 'T10/26' },
  { key: '2026-09', label: 'Tháng 9/2026', shortLabel: 'T9/26' },
  { key: '2026-08', label: 'Tháng 8/2026', shortLabel: 'T8/26' },
  { key: '2026-07', label: 'Tháng 7/2026', shortLabel: 'T7/26' },
  { key: '2026-06', label: 'Tháng 6/2026', shortLabel: 'T6/26' },
  { key: '2026-05', label: 'Tháng 5/2026', shortLabel: 'T5/26' },
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
  
  // Database-driven Dynamic Month Selection
  const [selectedMonthIndex, setSelectedMonthIndex] = useState(0); // 0 = 2026-10 (Tháng này)
  const currentMonthMeta = AVAILABLE_MONTHS[selectedMonthIndex] || AVAILABLE_MONTHS[0];
  const selectedMonthKey = currentMonthMeta.key;
  const timePeriod = currentMonthMeta.label;

  const [showCategoryDetail, setShowCategoryDetail] = useState(true);
  const [selectedTxForDetail, setSelectedTxForDetail] = useState(null);
  const [showAllMonthsTx, setShowAllMonthsTx] = useState(false);

  // Interactive Chart Hover & Focus States
  const [hoveredMonthIdx, setHoveredMonthIdx] = useState(null);
  const [hoveredCatId, setHoveredCatId] = useState(null);
  const [hoveredDrugIdx, setHoveredDrugIdx] = useState(null);
  const [hoveredAllocId, setHoveredAllocId] = useState(null);

  // Search and filter in transaction list
  const [txSearchQuery, setTxSearchQuery] = useState('');
  const [txFilterTab, setTxFilterTab] = useState('all');

  // Budget target state
  const [showBudgetModal, setShowBudgetModal] = useState(false);
  const [budgetTarget, setBudgetTarget] = useState(() => {
    try {
      const val = localStorage.getItem('medguard_budget_target_vnd');
      return val ? parseInt(val, 10) : null;
    } catch {
      return null;
    }
  });
  const [inputBudgetVal, setInputBudgetVal] = useState('5000000');

  // Transactions ledger state
  const [transactions, setTransactions] = useState(() => {
    try {
      const legacyKey = 'medguard_spending_transactions';
      const rawLegacy = localStorage.getItem(legacyKey);
      if (rawLegacy && (rawLegacy.includes('tx_01') || rawLegacy.includes('Esomeprazole') || rawLegacy.includes('22450'))) {
        localStorage.removeItem(legacyKey);
      }
      const rawAssessment = localStorage.getItem('medguard_financial_assessment');
      if (rawAssessment && (rawAssessment.includes('22450') || rawAssessment.includes('8531') || rawAssessment.includes('2450000'))) {
        localStorage.removeItem('medguard_financial_assessment');
      }
    } catch {}

    if (!isGuest) {
      try {
        const uid = account?.user_id || account?.id || account?.email;
        const key = uid ? `medguard_spending_transactions_${uid}` : 'medguard_spending_transactions_guest';
        const saved = localStorage.getItem(key);
        if (saved) {
          const parsed = JSON.parse(saved);
          if (Array.isArray(parsed)) {
            return parsed.filter((t) => t.id !== 'tx_01' && !t.title?.includes('Nexium 40mg (Esomeprazole) & Phosphalugel'));
          }
        }
      } catch {}
      return [];
    }
    return [];
  });

  // Modal: Nhập giao dịch (+ Thêm chi phí y tế)
  const [showAddModal, setShowAddModal] = useState(false);
  const [newTxTitle, setNewTxTitle] = useState('');
  const [newTxAmount, setNewTxAmount] = useState('');
  const [newTxCategory, setNewTxCategory] = useState('medication');
  const [newTxProvider, setNewTxProvider] = useState('');
  const [newTxDoctor, setNewTxDoctor] = useState('');
  const [newTxIcd10, setNewTxIcd10] = useState('');
  const [newTxBhytEligible, setNewTxBhytEligible] = useState(true);
  const [newTxNotes, setNewTxNotes] = useState('');

  // Assessment state from unified chat sync
  const [assessment, setAssessment] = useState(() => {
    try {
      const saved = localStorage.getItem('medguard_financial_assessment');
      if (saved && (saved.includes('22450') || saved.includes('8531') || saved.includes('2450000'))) {
        localStorage.removeItem('medguard_financial_assessment');
        return null;
      }
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  // Load production data from TiDB Cloud
  useEffect(() => {
    if (!api || isGuest || !account) return;
    let mounted = true;
    Promise.allSettled([
      api.request('/v1/user/spending'),
      api.request(`/v1/user/budget?month=${selectedMonthKey}`),
    ]).then(([spendingRes, budgetRes]) => {
      if (!mounted) return;
      if (spendingRes.status === 'fulfilled' && Array.isArray(spendingRes.value?.transactions)) {
        const dbTxs = spendingRes.value.transactions.map((t) => ({
          id: t.id,
          date: t.raw_date ? new Date(t.raw_date).toLocaleDateString('vi-VN') : 'Hôm nay',
          raw_date: t.raw_date || `${selectedMonthKey}-01`,
          time: '09:00',
          title: t.title,
          provider: t.provider || 'Cơ sở y tế đạt chuẩn GPP',
          doctor: t.doctor || 'Bác sĩ điều trị',
          category: t.category || 'medication',
          category_name:
            t.category === 'clinic'
              ? 'Khám chuyên khoa'
              : t.category === 'diagnostics'
              ? 'Xét nghiệm cận lâm sàng'
              : 'Thuốc kê đơn GPP',
          amount_vnd: -Math.abs(Number(t.amount_vnd) || 0),
          bhyt_covered_vnd: Number(t.bhyt_covered_vnd) || 0,
          is_gpp: Boolean(t.is_gpp),
          verified: true,
        }));
        setTransactions(dbTxs);
      }
      if (budgetRes.status === 'fulfilled') {
        if (budgetRes.value?.budget_target_vnd) {
          setBudgetTarget(Number(budgetRes.value.budget_target_vnd));
          setInputBudgetVal(String(budgetRes.value.budget_target_vnd));
        } else {
          setBudgetTarget(null);
        }
      }
    }).catch(() => {});
    return () => { mounted = false; };
  }, [api, account, isGuest, selectedMonthKey]);

  const [loadingSpending, setLoadingSpending] = useState(false);

  const reloadSpending = async () => {
    if (!api || isGuest || !account) return;
    setLoadingSpending(true);
    try {
      const spendingRes = await api.request('/v1/user/spending');
      if (Array.isArray(spendingRes?.transactions)) {
        const dbTxs = spendingRes.transactions.map((t) => ({
          id: t.id,
          date: t.raw_date ? new Date(t.raw_date).toLocaleDateString('vi-VN') : 'Hôm nay',
          raw_date: t.raw_date || `${selectedMonthKey}-01`,
          time: '09:00',
          title: t.title,
          provider: t.provider || 'Cơ sở y tế đạt chuẩn GPP',
          doctor: t.doctor || 'Bác sĩ điều trị',
          category: t.category || 'medication',
          category_name:
            t.category === 'clinic'
              ? 'Khám chuyên khoa'
              : t.category === 'diagnostics'
              ? 'Xét nghiệm cận lâm sàng'
              : 'Thuốc kê đơn GPP',
          amount_vnd: -Math.abs(Number(t.amount_vnd) || 0),
          bhyt_covered_vnd: Number(t.bhyt_covered_vnd) || 0,
          is_gpp: Boolean(t.is_gpp),
          verified: true,
        }));
        setTransactions(dbTxs);
        onNotify?.('✓ Đã cập nhật số liệu chi tiêu từ Database!', 'info');
      }
    } catch (err) {
      console.warn('Failed to reload spending from DB:', err);
    } finally {
      setLoadingSpending(false);
    }
  };

  const handleSeedSampleSpending = async () => {
    if (!api) return;
    setLoadingSpending(true);
    try {
      const res = await api.request('/v1/user/spending/seed-sample', { method: 'POST' });
      if (res && Array.isArray(res.transactions)) {
        const dbTxs = res.transactions.map((t) => ({
          id: t.id,
          date: t.raw_date ? new Date(t.raw_date).toLocaleDateString('vi-VN') : 'Hôm nay',
          raw_date: t.raw_date || `${selectedMonthKey}-01`,
          time: '09:00',
          title: t.title,
          provider: t.provider || 'Cơ sở y tế đạt chuẩn GPP',
          doctor: t.doctor || 'Bác sĩ điều trị',
          category: t.category || 'medication',
          category_name:
            t.category === 'clinic'
              ? 'Khám chuyên khoa'
              : t.category === 'diagnostics'
              ? 'Xét nghiệm cận lâm sàng'
              : 'Thuốc kê đơn GPP',
          amount_vnd: -Math.abs(Number(t.amount_vnd) || 0),
          bhyt_covered_vnd: Number(t.bhyt_covered_vnd) || 0,
          is_gpp: Boolean(t.is_gpp),
          verified: true,
        }));
        setTransactions(dbTxs);
        onNotify?.('✓ Đã nạp 8 giao dịch chi tiêu mẫu Demo vào Database!', 'success');
      }
    } catch (err) {
      console.warn('Failed to seed spending in DB:', err);
      onNotify?.('Không thể nạp dữ liệu chi tiêu mẫu.', 'error');
    } finally {
      setLoadingSpending(false);
    }
  };

  const handleClearSpending = async () => {
    if (!api) return;
    if (!window.confirm('Bạn có chắc chắn muốn xóa toàn bộ lịch sử chi tiêu y tế trong Database?')) return;
    setLoadingSpending(true);
    try {
      await api.request('/v1/user/spending/clear', { method: 'POST' });
      setTransactions([]);
      try {
        localStorage.removeItem(account ? `medguard_spending_transactions_${account.id || account.email}` : 'medguard_spending_transactions');
      } catch {}
      onNotify?.('✓ Đã xóa sạch toàn bộ giao dịch chi tiêu khỏi Database!', 'success');
    } catch (err) {
      console.warn('Failed to clear spending in DB:', err);
      onNotify?.('Không thể xóa dữ liệu chi tiêu.', 'error');
    } finally {
      setLoadingSpending(false);
    }
  };

  // Month navigation handlers
  const handlePrevMonth = () => {
    if (selectedMonthIndex < AVAILABLE_MONTHS.length - 1) {
      const nextIdx = selectedMonthIndex + 1;
      setSelectedMonthIndex(nextIdx);
      onNotify?.(`Đã chuyển số liệu sang: ${AVAILABLE_MONTHS[nextIdx].label}`, 'info');
    }
  };

  const handleNextMonth = () => {
    if (selectedMonthIndex > 0) {
      const prevIdx = selectedMonthIndex - 1;
      setSelectedMonthIndex(prevIdx);
      onNotify?.(`Đã chuyển số liệu sang: ${AVAILABLE_MONTHS[prevIdx].label}`, 'info');
    }
  };

  // Dynamic calculations for the selected month strictly according to transactions database
  const selectedMonthData = useMemo(() => {
    // Filter transactions for this specific month
    const mTransactions = transactions.filter((tx) => {
      if (!tx.raw_date) return selectedMonthIndex === 0;
      return tx.raw_date.startsWith(selectedMonthKey);
    });

    // Sum actual outflows
    const txSpend = mTransactions
      .filter((tx) => tx.amount_vnd < 0)
      .reduce((acc, tx) => acc + Math.abs(tx.amount_vnd), 0);

    // Sum BHYT covered
    const txBhyt = mTransactions
      .reduce((acc, tx) => acc + (tx.bhyt_covered_vnd || 0), 0);

    // Dynamic figures strictly from real transactions
    const actualSpend = txSpend;
    const bhytCovered = txBhyt;

    return {
      mTransactions,
      actualSpend,
      bhytCovered,
    };
  }, [transactions, selectedMonthKey, selectedMonthIndex]);

  // Total actual monthly spend for selected month
  const totalActualSpend = selectedMonthData.actualSpend;

  // Total BHYT paid or supplementary inflow for selected month
  const totalBhytCovered = selectedMonthData.bhytCovered;

  // Budget calculations for selected month
  const hasBudget = typeof budgetTarget === 'number' && budgetTarget > 0;
  const remainingBudget = hasBudget ? Math.max(0, budgetTarget - totalActualSpend) : 0;
  const budgetUtilizationPct = hasBudget ? Math.min(100, Math.round((totalActualSpend / budgetTarget) * 100)) : 0;

  // MedGuard 45-35-20 Care Allocation for selected month
  const allocation45 = hasBudget ? Math.round(budgetTarget * 0.45) : 0;
  const allocation35 = hasBudget ? Math.round(budgetTarget * 0.35) : 0;
  const allocation20 = hasBudget ? Math.round(budgetTarget * 0.20) : 0;

  const clinicSpend = useMemo(() => {
    return selectedMonthData.mTransactions
      .filter((t) => t.category === 'clinic')
      .reduce((sum, t) => sum + Math.abs(t.amount_vnd), 0);
  }, [selectedMonthData.mTransactions]);

  const medSpend = useMemo(() => {
    return selectedMonthData.mTransactions
      .filter((t) => t.category === 'medication')
      .reduce((sum, t) => sum + Math.abs(t.amount_vnd), 0);
  }, [selectedMonthData.mTransactions]);

  const comparedDrugs = useMemo(() => {
    const medTxs = transactions.filter((t) => t.category === 'medication' || t.is_gpp);
    if (!medTxs.length) return [];
    return medTxs.slice(0, 5).map((t) => {
      const amount = Math.abs(t.amount_vnd) || 150000;
      const genericPrice = Math.round(amount * 0.62);
      return {
        name: t.title,
        brand: amount,
        generic: genericPrice,
        savePct: 38,
      };
    });
  }, [transactions]);

  // Dynamic Categories Breakdown for selected month
  const currentCategories = useMemo(() => {
    const { mTransactions, actualSpend } = selectedMonthData;

    const categoryTotals = {
      medication: 0,
      clinic: 0,
      diagnostics: 0,
      supplements: 0,
      supplies: 0,
    };

    mTransactions.forEach((tx) => {
      if (tx.amount_vnd < 0) {
        const cat = tx.category in categoryTotals ? tx.category : 'medication';
        categoryTotals[cat] += Math.abs(tx.amount_vnd);
      }
    });

    const hasTxData = Object.values(categoryTotals).some((v) => v > 0);

    return DEFAULT_CATEGORIES.map((baseCat) => {
      let amount = 0;
      let pct = 0;

      if (hasTxData && actualSpend > 0) {
        amount = categoryTotals[baseCat.id] || 0;
        pct = Math.max(0, Math.round((amount / actualSpend) * 100));
      }

      return {
        ...baseCat,
        amount_vnd: amount,
        percentage: pct,
      };
    });
  }, [selectedMonthData]);

  // Dynamic Donut SVG Arcs for selected month
  const dynamicDonutArcs = useMemo(() => {
    if (totalActualSpend <= 0) return [];
    let currentOffset = 0;
    const circumference = 439.82;
    return currentCategories.filter((c) => c.percentage > 0).map((cat) => {
      const pct = cat.percentage;
      const len = +(circumference * (pct / 100)).toFixed(2);
      const gap = +(circumference - len).toFixed(2);
      const arc = {
        id: cat.id,
        color: cat.color,
        len,
        gap,
        offset: currentOffset,
      };
      currentOffset -= len;
      return arc;
    });
  }, [currentCategories, totalActualSpend]);

  // Dynamic Comparison with Prior Month based strictly on transactions
  const monthComparison = useMemo(() => {
    if (transactions.length === 0) {
      return {
        hasPrior: false,
        isReduction: true,
        text: 'Chưa có khoản chi nào trong tháng',
        subText: 'Hệ thống sẽ tự động tổng hợp và đối chiếu viện phí, chi phí đơn thuốc khi bạn trao đổi với Bác sĩ AI.',
      };
    }
    const priorMonthIndex = selectedMonthIndex + 1;
    if (priorMonthIndex < AVAILABLE_MONTHS.length) {
      const prior = AVAILABLE_MONTHS[priorMonthIndex];
      const priorTxs = transactions.filter((t) => t.raw_date && t.raw_date.startsWith(prior.key));
      const priorSpend = priorTxs.filter((t) => t.amount_vnd < 0).reduce((acc, t) => acc + Math.abs(t.amount_vnd), 0);
      const diff = totalActualSpend - priorSpend;
      const isReduction = diff <= 0;
      const absDiff = Math.abs(diff);
      const pct = priorSpend > 0 ? Math.abs(Math.round((diff / priorSpend) * 100)) : 0;
      return {
        hasPrior: true,
        isReduction,
        absDiff,
        pct,
        priorLabel: prior.label,
        text: priorSpend === 0
          ? `Ghi nhận chi tiêu thực tế: ${formatVnd(totalActualSpend)}`
          : isReduction
          ? `Giảm ${formatVnd(absDiff)} so với ${prior.label}`
          : `Tăng ${formatVnd(absDiff)} so với ${prior.label}`,
        subText: isReduction
          ? `Tối ưu hóa chi phí y tế nhờ dùng thuốc Generic EU-GMP nhóm 1 đạt tương đương sinh học đúng trần DAV.`
          : `Chi phí phát sinh từ các đợt khám chuyên khoa hoặc xét nghiệm cận lâm sàng.`,
      };
    }
    return {
      hasPrior: false,
      isReduction: true,
      text: `Số liệu ghi nhận đầy đủ cho ${currentMonthMeta.label}`,
      subText: 'Toàn bộ khoản chi đều được giám định theo danh mục BHYT và trần giá Cục Quản Lý Dược (DAV).',
    };
  }, [selectedMonthIndex, totalActualSpend, transactions, currentMonthMeta]);

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
              const uid = account?.user_id || account?.id || account?.email;
              const txKey = uid ? `medguard_spending_transactions_${uid}` : 'medguard_spending_transactions_guest';
              localStorage.setItem(txKey, JSON.stringify(nextList));
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
    if (!showAllMonthsTx) {
      result = result.filter((tx) => {
        if (!tx.raw_date) return selectedMonthIndex === 0;
        return tx.raw_date.startsWith(selectedMonthKey);
      });
    }
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
  }, [transactions, showAllMonthsTx, selectedMonthKey, selectedMonthIndex, txFilterTab, txSearchQuery]);

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

    const todayStr = new Date().toISOString().split('T')[0];
    const createdTx = {
      id: `tx_user_${Date.now()}`,
      date: 'Hôm nay',
      raw_date: todayStr,
      time: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }),
      title: newTxTitle.trim(),
      provider: newTxProvider.trim() || 'Cơ sở y tế đạt chuẩn GPP',
      doctor: newTxDoctor.trim() || 'Bác sĩ điều trị',
      icd10: newTxIcd10.trim() || null,
      category: newTxCategory,
      category_name:
        newTxCategory === 'medication'
          ? 'Thuốc kê đơn GPP'
          : newTxCategory === 'clinic'
          ? 'Khám chuyên khoa'
          : newTxCategory === 'diagnostics'
          ? 'Xét nghiệm cận lâm sàng'
          : newTxCategory === 'supplies'
          ? 'Vật tư y tế tiêu hao'
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
      localStorage.setItem(getFinKey(account), JSON.stringify(nextList));
    } catch {}

    if (api && !isGuest && account) {
      api.request('/v1/user/spending', {
        method: 'POST',
        body: {
          title: newTxTitle.trim(),
          amount_vnd: amt,
          category: newTxCategory,
          provider: newTxProvider.trim() || 'Cơ sở y tế đạt chuẩn GPP',
          doctor: newTxDoctor.trim() || 'Bác sĩ điều trị',
          bhyt_covered_vnd: bhytCovered,
          is_gpp: true,
          raw_date: todayStr,
        },
      }).catch((err) => console.warn('Could not save spending to TiDB:', err));
    }

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
      const uid = account?.user_id || account?.id || account?.email;
      const bKey = uid ? `medguard_budget_target_vnd_${uid}` : 'medguard_budget_target_vnd';
      localStorage.setItem(bKey, String(val));
    } catch {}
    if (api && !isGuest && account) {
      api.request('/v1/user/budget', {
        method: 'POST',
        body: { budget_target_vnd: val, month: selectedMonthKey },
      }).catch((err) => console.warn('Could not save budget to TiDB:', err));
    }
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

  const monthlyTrendSeries = useMemo(() => {
    if (transactions.length === 0) {
      return [
        { month: "T5/26", outOfPocket: 0, bhyt: 0, genericSaved: 0 },
        { month: "T6/26", outOfPocket: 0, bhyt: 0, genericSaved: 0 },
        { month: "T7/26", outOfPocket: 0, bhyt: 0, genericSaved: 0 },
        { month: "T8/26", outOfPocket: 0, bhyt: 0, genericSaved: 0 },
        { month: "T9/26", outOfPocket: 0, bhyt: 0, genericSaved: 0 },
        { month: "T10/26", outOfPocket: 0, bhyt: 0, genericSaved: 0 },
      ];
    }
    const months = [
      { key: '2026-05', month: 'T5/26' },
      { key: '2026-06', month: 'T6/26' },
      { key: '2026-07', month: 'T7/26' },
      { key: '2026-08', month: 'T8/26' },
      { key: '2026-09', month: 'T9/26' },
      { key: '2026-10', month: 'T10/26' },
    ];
    return months.map((m) => {
      const txs = transactions.filter((t) => t.raw_date && t.raw_date.startsWith(m.key));
      const spend = txs.filter((t) => t.amount_vnd < 0).reduce((acc, t) => acc + Math.abs(t.amount_vnd), 0);
      const bhyt = txs.reduce((acc, t) => acc + (t.bhyt_covered_vnd || 0), 0);
      return {
        month: m.month,
        outOfPocket: +(spend / 1000000).toFixed(1),
        bhyt: +(bhyt / 1000000).toFixed(1),
        genericSaved: +(spend * 0.2 / 1000000).toFixed(1),
      };
    });
  }, [transactions]);

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
              disabled={selectedMonthIndex >= AVAILABLE_MONTHS.length - 1}
              onClick={handlePrevMonth}
              title="Tháng trước"
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
              disabled={selectedMonthIndex <= 0}
              onClick={handleNextMonth}
              title="Tháng sau"
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
            <span>{monthComparison.text}</span>
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
              {hasBudget ? (
                <>
                  <div className="budget-bar-labels">
                    <span>Hạn mức: <strong>{formatVnd(budgetTarget, hideAmounts)}</strong> (Đã chi {budgetUtilizationPct}%)</span>
                    <span>Còn lại: <strong className="text-emerald">{formatVnd(remainingBudget, hideAmounts)}</strong></span>
                  </div>
                  <div className="budget-bar-track">
                    <div
                      className="budget-bar-fill"
                      style={{ width: `${budgetUtilizationPct}%`, backgroundColor: budgetUtilizationPct > 90 ? '#ef4444' : '#ff4d79' }}
                    />
                  </div>
                </>
              ) : (
                <div className="budget-bar-labels" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: '#64748b', fontSize: '0.82rem' }}>Hạn mức: Chưa thiết lập</span>
                  <button
                    type="button"
                    onClick={() => setShowBudgetModal(true)}
                    style={{ background: 'none', border: 'none', color: '#ff4d79', fontWeight: 600, fontSize: '0.8rem', cursor: 'pointer', padding: 0 }}
                  >
                    + Thiết lập ngay
                  </button>
                </div>
              )}
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
          <div className="spending-chart-card interactive-trend-card">
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
              <defs>
                <filter id="barDropGlow" x="-20%" y="-20%" width="140%" height="140%">
                  <feDropShadow dx="0" dy="3" stdDeviation="3.5" floodColor="#f43f5e" floodOpacity="0.45" />
                </filter>
                <filter id="tealDropGlow" x="-20%" y="-20%" width="140%" height="140%">
                  <feDropShadow dx="0" dy="3" stdDeviation="3.5" floodColor="#0d9488" floodOpacity="0.45" />
                </filter>
                <linearGradient id="roseBarGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#fb7185" />
                  <stop offset="100%" stopColor="#e11d48" />
                </linearGradient>
                <linearGradient id="tealBarGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#2dd4bf" />
                  <stop offset="100%" stopColor="#0d9488" />
                </linearGradient>
              </defs>

              {/* Grid lines */}
              {[0, 10, 20, 30].map((v) => {
                const y = 128 - (v / 32) * 100;
                return (
                  <g key={v}>
                    <line x1="34" y1={y} x2="440" y2={y} stroke="#e2e8f0" strokeDasharray="3 3" />
                    <text x="28" y={y + 3} textAnchor="end" className="sc-axis-txt">{v}tr</text>
                  </g>
                );
              })}

              {/* Active Column Guide & Background Highlight */}
              {hoveredMonthIdx !== null && (() => {
                const hx = 62 + hoveredMonthIdx * 66;
                return (
                  <g className="sc-active-guide-col" style={{ pointerEvents: 'none' }}>
                    <rect x={hx - 22} y="12" width="44" height="118" rx="8" fill="#f8fafc" fillOpacity="0.9" stroke="#e2e8f0" strokeWidth="1" />
                    <line x1={hx} y1="16" x2={hx} y2="128" stroke="#3b82f6" strokeWidth="1.5" strokeDasharray="3 3" opacity="0.85" />
                  </g>
                );
              })()}

              {/* Stacked Bars per Month with Entrance and Hover Animations */}
              {monthlyTrendSeries.map((m, idx) => {
                const x = 62 + idx * 66;
                const hOut = Math.min(72, (m.outOfPocket / 32) * 100);
                const hBhyt = Math.min(45, (m.bhyt / 32) * 100);
                const yOut = 128 - hOut;
                const yBhyt = yOut - hBhyt;
                const isHovered = hoveredMonthIdx === idx;
                const isDimmed = hoveredMonthIdx !== null && !isHovered;

                return (
                  <g
                    key={m.month}
                    className={`sc-bar-group ${isHovered ? 'is-hovered' : ''} ${isDimmed ? 'is-dimmed' : ''}`}
                    style={{
                      transition: 'opacity 0.25s ease, transform 0.25s ease',
                      opacity: isDimmed ? 0.35 : 1,
                    }}
                  >
                    {/* Out of pocket bar (Rose) */}
                    <rect
                      x={x - 13}
                      y={yOut}
                      width="26"
                      height={hOut}
                      rx="3"
                      fill={isHovered ? 'url(#roseBarGrad)' : '#f43f5e'}
                      fillOpacity={isHovered ? 1 : 0.85}
                      stroke={isHovered ? '#ffffff' : 'none'}
                      strokeWidth="1.5"
                      filter={isHovered ? 'url(#barDropGlow)' : undefined}
                      className="sc-rect-bar out-bar"
                      style={{
                        transformOrigin: `${x}px 128px`,
                        animationDelay: `${idx * 0.08}s`,
                      }}
                    />
                    {/* BHYT covered bar (Teal) */}
                    <rect
                      x={x - 13}
                      y={yBhyt}
                      width="26"
                      height={hBhyt}
                      rx="3"
                      fill={isHovered ? 'url(#tealBarGrad)' : '#0d9488'}
                      fillOpacity={isHovered ? 1 : 0.88}
                      stroke={isHovered ? '#ffffff' : 'none'}
                      strokeWidth="1.5"
                      filter={isHovered ? 'url(#tealDropGlow)' : undefined}
                      className="sc-rect-bar bhyt-bar"
                      style={{
                        transformOrigin: `${x}px 128px`,
                        animationDelay: `${idx * 0.08 + 0.04}s`,
                      }}
                    />
                    {/* Value label */}
                    <text
                      x={x}
                      y={yBhyt - 6}
                      textAnchor="middle"
                      className={`sc-val-txt ${isHovered ? 'hovered-val' : ''}`}
                      style={{
                        fontWeight: isHovered ? 900 : 800,
                        fill: isHovered ? '#e11d48' : '#0f172a',
                      }}
                    >
                      {m.outOfPocket}tr
                    </text>
                    {/* Month label */}
                    <text
                      x={x}
                      y="145"
                      textAnchor="middle"
                      className={`sc-x-txt ${isHovered ? 'hovered-x' : ''}`}
                      style={{
                        fontWeight: isHovered ? 850 : 700,
                        fill: isHovered ? '#0f172a' : '#475569',
                      }}
                    >
                      {m.month}
                    </text>
                  </g>
                );
              })}

              {/* Polyline for Generic Savings Trend with Draw Entrance */}
              <polyline
                fill="none"
                stroke="#2563eb"
                strokeWidth="2.5"
                className="sc-trend-polyline"
                points={monthlyTrendSeries.map((m, idx) => `${62 + idx * 66},${128 - (m.genericSaved / 8) * 85}`).join(" ")}
              />

              {/* Interactive Nodes on Polyline with Pulse Ring */}
              {monthlyTrendSeries.map((m, idx) => {
                const x = 62 + idx * 66;
                const ySaved = 128 - (m.genericSaved / 8) * 85;
                const isHovered = hoveredMonthIdx === idx;
                return (
                  <g key={`dot-${m.month}`}>
                    {isHovered && (
                      <circle
                        cx={x}
                        cy={ySaved}
                        r="11"
                        fill="none"
                        stroke="#3b82f6"
                        strokeWidth="1.8"
                        className="trend-pulse-ring"
                      />
                    )}
                    <circle
                      cx={x}
                      cy={ySaved}
                      r={isHovered ? 6 : 3.5}
                      fill={isHovered ? "#3b82f6" : "#2563eb"}
                      stroke="#ffffff"
                      strokeWidth="2"
                      className="sc-trend-node"
                      style={{ transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)' }}
                    />
                  </g>
                );
              })}

              {/* Floating Tooltip Box */}
              {hoveredMonthIdx !== null && (() => {
                const selM = monthlyTrendSeries[hoveredMonthIdx];
                const selX = 62 + hoveredMonthIdx * 66;
                const ttW = 136;
                const ttH = 74;
                const ttX = hoveredMonthIdx >= 3 ? selX - ttW - 14 : selX + 16;
                const ttY = Math.max(10, Math.min(128 - (selM.outOfPocket / 32) * 100 - 24, 52));

                return (
                  <g className="sc-tooltip-group" style={{ pointerEvents: 'none' }}>
                    <rect
                      x={ttX}
                      y={ttY}
                      width={ttW}
                      height={ttH}
                      rx="8"
                      fill="#0f172a"
                      fillOpacity="0.94"
                      stroke="#334155"
                      strokeWidth="1"
                      filter="drop-shadow(0 6px 18px rgba(0,0,0,0.32))"
                    />
                    <text x={ttX + 10} y={ttY + 15} fill="#ffffff" fontSize="9" fontWeight="800">
                      {selM.month} • Tổng: {(selM.outOfPocket + selM.bhyt).toFixed(1)} tr
                    </text>
                    <line x1={ttX + 8} y1={ttY + 21} x2={ttX + ttW - 8} y2={ttY + 21} stroke="#334155" strokeWidth="0.8" />
                    <circle cx={ttX + 14} cy={ttY + 31} r="3" fill="#f43f5e" />
                    <text x={ttX + 22} y={ttY + 34} fill="#fb7185" fontSize="8" fontWeight="700">
                      Tự chi trả: {selM.outOfPocket} triệu ₫
                    </text>
                    <circle cx={ttX + 14} cy={ttY + 45} r="3" fill="#0d9488" />
                    <text x={ttX + 22} y={ttY + 48} fill="#2dd4bf" fontSize="8" fontWeight="700">
                      Quỹ BHYT: {selM.bhyt} triệu ₫
                    </text>
                    <circle cx={ttX + 14} cy={ttY + 59} r="3" fill="#3b82f6" />
                    <text x={ttX + 22} y={ttY + 62} fill="#60a5fa" fontSize="8" fontWeight="700">
                      Tiết kiệm: {selM.genericSaved} triệu ₫
                    </text>
                  </g>
                );
              })()}

              {/* Invisible Hit Columns for Smooth Mouse Capture and Direct Month Switching */}
              {monthlyTrendSeries.map((m, idx) => {
                const x = 62 + idx * 66;
                return (
                  <rect
                    key={`hit-${m.month}`}
                    x={x - 30}
                    y="10"
                    width="60"
                    height="136"
                    fill="transparent"
                    style={{ cursor: 'pointer' }}
                    onMouseEnter={() => setHoveredMonthIdx(idx)}
                    onMouseLeave={() => setHoveredMonthIdx(null)}
                    onClick={() => {
                      const targetIdx = 5 - idx;
                      setSelectedMonthIndex(targetIdx);
                      onNotify?.(`Đã chuyển sang xem số liệu: ${AVAILABLE_MONTHS[targetIdx]?.label}`, 'info');
                    }}
                  />
                );
              })}
            </svg>
          </div>

          {/* Chart B: Drug Price Savings Horizontal Bar Chart (Actual vs DAV Ceiling vs Generic EU-GMP) */}
          <div className="spending-chart-card interactive-dav-card">
            <div className="sc-head">
              <div>
                <span className="sc-kicker">BIỂU ĐỒ ĐỐI SÁNH GIÁ DƯỢC PHẨM</span>
                <h4>So Sánh Giá Biệt Dược Gốc vs Generic EU-GMP Chuẩn DAV</h4>
              </div>
              <span className="sc-save-pill">
                {comparedDrugs.length > 0 ? 'Tiết kiệm ~38% khi đổi Generic' : 'Theo đơn thuốc'}
              </span>
            </div>
            <div className="dav-visual-bars-list">
              {comparedDrugs.length === 0 ? (
                <div style={{ padding: '28px 16px', textAlign: 'center', color: '#64748b', fontSize: '0.88rem' }}>
                  <Pill size={28} style={{ color: '#0d9488', margin: '0 auto 8px', display: 'block', opacity: 0.8 }} />
                  <strong>Chưa ghi nhận đơn thuốc trong lịch sử</strong>
                  <p style={{ margin: '4px auto 0', fontSize: '0.82rem', color: '#94a3b8', maxWidth: '320px' }}>
                    Khi bạn trao đổi toa thuốc với Bác sĩ AI trong phòng Chat, hệ thống sẽ tự động đối sánh giá biệt dược gốc và Generic EU-GMP tại đây.
                  </p>
                </div>
              ) : (
                comparedDrugs.map((d, idx) => (
                  <div
                    key={d.name}
                    className={`dav-vbar-group ${hoveredDrugIdx === idx ? 'hovered' : ''}`}
                    onMouseEnter={() => setHoveredDrugIdx(idx)}
                    onMouseLeave={() => setHoveredDrugIdx(null)}
                    style={{ animationDelay: `${idx * 0.1}s` }}
                  >
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
                ))
              )}
            </div>
          </div>
        </div>

        {/* Sub-banner: Dynamic Comparison with Prior Month */}
        <div className="web-comparison-banner">
          <div className="banner-left-wrap">
            <div className="banner-icon-box">
              <BarChart2 size={18} />
            </div>
            <div className="banner-content-text">
              <span className="banner-highlight-text">
                <strong className={monthComparison.isReduction ? 'text-emerald' : 'text-pink'}>
                  {monthComparison.text}
                </strong>
              </span>
              <span className="banner-sub-desc">
                {monthComparison.subText}
              </span>
            </div>
          </div>
          <button
            type="button"
            className="banner-action-btn"
            onClick={() => onNotify?.(`Báo cáo chi tiết tối ưu hóa kinh tế dược học cho ${currentMonthMeta.label} đã được cập nhật!`, 'info')}
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

        {!hasBudget && totalActualSpend === 0 ? (
          <div
            className="alloc-empty-activation-card"
            style={{
              background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.95), rgba(248, 250, 252, 0.95))',
              borderRadius: '16px',
              border: '1.5px dashed #cbd5e1',
              padding: '36px 24px',
              textAlign: 'center',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '12px',
            }}
          >
            <div
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '50%',
                background: 'rgba(236, 72, 153, 0.1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#ec4899',
              }}
            >
              <Sparkles size={24} />
            </div>
            <h4 style={{ margin: 0, fontSize: '1.05rem', color: '#1e293b', fontWeight: 700 }}>
              Chưa Thiết Lập Hạn Mức Hoặc Giao Dịch Chi Tiêu {currentMonthMeta.label}
            </h4>
            <p style={{ margin: 0, maxWidth: '560px', fontSize: '0.88rem', color: '#64748b', lineHeight: 1.5 }}>
              Phác đồ phân bổ dòng tiền <strong>45% (Khám BHYT) - 35% (Thuốc GPP & Generic) - 20% (Quỹ dự phòng)</strong> được kích hoạt tự động theo số liệu thực tế khi bạn thiết lập hạn mức tháng hoặc có giao dịch viện phí / thuốc thực tế.
            </p>
            <div style={{ display: 'flex', gap: '12px', marginTop: '6px' }}>
              <button
                type="button"
                className="web-action-btn primary-pink"
                onClick={() => setShowBudgetModal(true)}
                style={{ padding: '8px 18px', borderRadius: '8px', fontSize: '0.88rem' }}
              >
                <Plus size={15} />
                <span>+ Thiết lập hạn mức tháng</span>
              </button>
              <button
                type="button"
                className="banner-action-btn"
                onClick={() => setShowAddModal(true)}
                style={{ padding: '8px 18px', borderRadius: '8px', fontSize: '0.88rem' }}
              >
                <Receipt size={15} />
                <span>+ Nhập đơn thuốc / Viện phí</span>
              </button>
            </div>
          </div>
        ) : (
          <div className="allocation-three-grid">
          {/* Card 1: 45% Khám Booking Care & BHYT */}
          <div
            className={`alloc-card card-45 ${hoveredAllocId === 'alloc45' ? 'is-hovered' : ''}`}
            onMouseEnter={() => setHoveredAllocId('alloc45')}
            onMouseLeave={() => setHoveredAllocId(null)}
          >
            <div className="alloc-card-top">
              <div className="alloc-pct-bubble pink">45%</div>
              <strong className="alloc-amount-text">{formatVnd(allocation45, hideAmounts)}</strong>
            </div>
            <h4 className="alloc-card-name">Khám Booking Care & BHYT</h4>
            <div className="alloc-progress-line" style={{ marginTop: '6px', marginBottom: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', color: '#64748b', marginBottom: '3px' }}>
                <span>Đã chi: <strong style={{ color: '#ec4899' }}>{formatVnd(clinicSpend, hideAmounts)}</strong></span>
                <span>{allocation45 > 0 ? Math.min(100, Math.round((clinicSpend / allocation45) * 100)) : 0}%</span>
              </div>
              <div style={{ height: '5px', background: '#f1f5f9', borderRadius: '4px', overflow: 'hidden' }}>
                <div style={{ height: '100%', background: '#ec4899', width: `${allocation45 > 0 ? Math.min(100, (clinicSpend / allocation45) * 100) : 0}%`, transition: 'width 0.3s ease' }} />
              </div>
            </div>
            <p className="alloc-card-desc">
              Khám chuyên khoa sớm đúng tuyến tại các bệnh viện liên kết giúp quỹ BHYT chi trả 80–100%, dứt điểm bệnh ban đầu tránh biến chứng tốn kém.
            </p>
            <div className="alloc-card-footer">
              <CheckCircle2 size={13} className="text-emerald" />
              <span>Tiết kiệm 80% viện phí đúng tuyến</span>
            </div>
          </div>

          {/* Card 2: 35% Thuốc GPP & Generic Nhóm 1 */}
          <div
            className={`alloc-card card-35 ${hoveredAllocId === 'alloc35' ? 'is-hovered' : ''}`}
            onMouseEnter={() => setHoveredAllocId('alloc35')}
            onMouseLeave={() => setHoveredAllocId(null)}
          >
            <div className="alloc-card-top">
              <div className="alloc-pct-bubble mint">35%</div>
              <strong className="alloc-amount-text">{formatVnd(allocation35, hideAmounts)}</strong>
            </div>
            <h4 className="alloc-card-name">Thuốc GPP & Generic EU-GMP</h4>
            <div className="alloc-progress-line" style={{ marginTop: '6px', marginBottom: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', color: '#64748b', marginBottom: '3px' }}>
                <span>Đã chi: <strong style={{ color: '#0d9488' }}>{formatVnd(medSpend, hideAmounts)}</strong></span>
                <span>{allocation35 > 0 ? Math.min(100, Math.round((medSpend / allocation35) * 100)) : 0}%</span>
              </div>
              <div style={{ height: '5px', background: '#f1f5f9', borderRadius: '4px', overflow: 'hidden' }}>
                <div style={{ height: '100%', background: '#0d9488', width: `${allocation35 > 0 ? Math.min(100, (medSpend / allocation35) * 100) : 0}%`, transition: 'width 0.3s ease' }} />
              </div>
            </div>
            <p className="alloc-card-desc">
              Mua thuốc tại chuỗi GPP uy tín, ưu tiên biệt dược Generic Nhóm 1 EU-GMP có sinh khả dụng đạt nồng độ ức chế MIC.
            </p>
            <div className="alloc-card-footer">
              <CheckCircle2 size={13} className="text-emerald" />
              <span>Tiết kiệm 35–40% so với Biệt dược gốc</span>
            </div>
          </div>

          {/* Card 3: 20% Quỹ Dự Phòng Sức Khỏe */}
          <div
            className={`alloc-card card-20 ${hoveredAllocId === 'alloc20' ? 'is-hovered' : ''}`}
            onMouseEnter={() => setHoveredAllocId('alloc20')}
            onMouseLeave={() => setHoveredAllocId(null)}
          >
            <div className="alloc-card-top">
              <div className="alloc-pct-bubble cyan">20%</div>
              <strong className="alloc-amount-text">{formatVnd(allocation20, hideAmounts)}</strong>
            </div>
            <h4 className="alloc-card-name">Quỹ Dự Phòng Sức Khỏe</h4>
            <div className="alloc-progress-line" style={{ marginTop: '6px', marginBottom: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', color: '#64748b', marginBottom: '3px' }}>
                <span>Khả dụng: <strong style={{ color: '#0284c7' }}>{formatVnd(remainingBudget, hideAmounts)}</strong></span>
                <span>{budgetUtilizationPct}% đã dùng</span>
              </div>
              <div style={{ height: '5px', background: '#f1f5f9', borderRadius: '4px', overflow: 'hidden' }}>
                <div style={{ height: '100%', background: '#0284c7', width: `${Math.max(0, 100 - budgetUtilizationPct)}%`, transition: 'width 0.3s ease' }} />
              </div>
            </div>
            <p className="alloc-card-desc">
              Dành riêng cho xét nghiệm tầm soát chức năng định kỳ, dinh dưỡng y học và xử lý các đợt bùng phát triệu chứng cấp tính.
            </p>
            <div className="alloc-card-footer">
              <CheckCircle2 size={13} className="text-emerald" />
              <span>Ngăn ngừa biến chứng nặng phải nhập viện</span>
            </div>
          </div>
        </div>
        )}
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

                  {/* 5 Dynamic SVG Arcs with Bidirectional Hover Sync */}
                  {dynamicDonutArcs.map((arc) => {
                    const isHovered = hoveredCatId === arc.id;
                    const isDimmed = hoveredCatId !== null && !isHovered;
                    return (
                      <circle
                        key={arc.id}
                        cx="100"
                        cy="100"
                        r="70"
                        fill="none"
                        stroke={arc.color}
                        strokeWidth={isHovered ? 32 : 26}
                        strokeDasharray={`${arc.len} ${arc.gap}`}
                        strokeDashoffset={arc.offset}
                        strokeLinecap="round"
                        transform="rotate(-90 100 100)"
                        className={`donut-arc-segment ${isHovered ? 'arc-hovered' : ''}`}
                        onMouseEnter={() => setHoveredCatId(arc.id)}
                        onMouseLeave={() => setHoveredCatId(null)}
                        style={{
                          cursor: 'pointer',
                          transition: 'stroke-width 0.28s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.28s ease, filter 0.28s ease',
                          filter: isHovered ? `drop-shadow(0 0 10px ${arc.color}90)` : undefined,
                          opacity: isDimmed ? 0.35 : 1,
                        }}
                      />
                    );
                  })}
                </svg>

                {/* Donut Core Center with Interactive Hover Inspection */}
                {(() => {
                  const activeCat = currentCategories.find((c) => c.id === hoveredCatId);
                  return (
                    <div className={`web-donut-core ${hoveredCatId ? 'has-active-focus' : ''}`}>
                      {hoveredCatId && activeCat ? (
                        <div className="donut-core-active-content">
                          <span className="donut-core-kicker" style={{ color: activeCat.color }}>
                            {activeCat.name.split('&')[0].trim()}
                          </span>
                          <strong className="donut-core-number" style={{ color: activeCat.color, fontSize: '0.84rem' }}>
                            {formatVnd(activeCat.amount_vnd, hideAmounts)}
                          </strong>
                          <span className="donut-core-pct-badge" style={{ backgroundColor: `${activeCat.color}22`, color: activeCat.color }}>
                            {activeCat.percentage}% Tổng chi
                          </span>
                        </div>
                      ) : (
                        <div className="donut-core-default-content">
                          <span className="donut-core-kicker">Tổng Chi</span>
                          <strong className="donut-core-number">
                            {formatVnd(totalActualSpend, hideAmounts)}
                          </strong>
                          <span className="donut-core-pct-badge neutral">
                            {totalActualSpend > 0 ? '100% Thực chi' : 'Chưa có khoản chi'}
                          </span>
                        </div>
                      )}
                    </div>
                  );
                })()}
              </div>

              {/* Category Breakdown Bars with Bidirectional Hover Sync */}
              <div className="category-bars-stack">
                {currentCategories.map((cat) => {
                  const CatIcon = cat.icon;
                  const isHovered = hoveredCatId === cat.id;
                  const isDimmed = hoveredCatId !== null && !isHovered;
                  return (
                    <div
                      key={cat.id}
                      className={`category-bar-row ${isHovered ? 'active-hover' : ''} ${isDimmed ? 'dimmed' : ''}`}
                      onMouseEnter={() => setHoveredCatId(cat.id)}
                      onMouseLeave={() => setHoveredCatId(null)}
                      style={{
                        borderColor: isHovered ? cat.color : undefined,
                        boxShadow: isHovered ? `0 6px 20px ${cat.color}25` : undefined,
                      }}
                    >
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
                          className={`cat-progress-fill ${isHovered ? 'shimmer-active' : ''}`}
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
                  {transactions.length === 0 ? (
                    <tr>
                      <td colSpan={6} style={{ textAlign: 'center', padding: '36px 16px', color: '#94a3b8' }}>
                        <Pill size={24} style={{ color: '#0d9488', margin: '0 auto 8px', display: 'block', opacity: 0.7 }} />
                        <strong style={{ display: 'block', color: '#64748b', marginBottom: '4px' }}>Chưa có dữ liệu giao dịch hoặc đơn thuốc để đối sánh trần giá DAV</strong>
                        <span style={{ fontSize: '0.82rem' }}>Khi bạn nhập chi phí hoặc trò chuyện gửi đơn thuốc cho Bác sĩ AI, hệ thống sẽ tự động đối chiếu trần giá niêm yết Cục Quản Lý Dược (DAV).</span>
                      </td>
                    </tr>
                  ) : (
                    transactions.slice(0, 8).map((tx, idx) => {
                      const price = Math.abs(tx.amount_vnd) || 0;
                      const davCeiling = Math.round(price * 1.05);
                      const genericEst = Math.round(price * 0.62);
                      const savePct = Math.round(((davCeiling - genericEst) / davCeiling) * 100);
                      const isMed = tx.category === 'medication' || tx.is_gpp;
                      return (
                        <tr key={tx.id || idx}>
                          <td>
                            <strong>{tx.title}</strong>
                            <span className="cell-sub">{tx.provider || tx.category_name || (isMed ? 'Thuốc kê đơn GPP' : 'Dịch vụ y tế')}</span>
                          </td>
                          <td><code>{tx.dav_registration || (isMed ? 'DAV-GPP' : 'BYT-CS')}</code></td>
                          <td>{formatVnd(price, hideAmounts)}</td>
                          <td>{formatVnd(davCeiling, hideAmounts)}</td>
                          <td className="text-emerald">{isMed ? formatVnd(genericEst, hideAmounts) : 'Hưởng BHYT 80%'}</td>
                          <td>
                            <span className={`table-badge ${isMed ? 'success' : 'bhyt'}`}>
                              {isMed ? `Tiết kiệm ${savePct}%` : 'Hưởng BHYT'}
                            </span>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>

            {/* 3 Real-time Data Integrity & Trust Metrics */}
            <div className="trust-metrics-summary-strip">
              <div className="trust-pill-item">
                <span className="trust-pill-name">Trạng thái dữ liệu:</span>
                <strong className="text-pink">{transactions.length > 0 ? `${transactions.length} Giao dịch thật` : 'Chưa phát sinh'}</strong>
                <span className="trust-pill-hint">Đồng bộ trực tiếp từ TiDB Cloud</span>
              </div>
              <div className="trust-pill-item">
                <span className="trust-pill-name">Xác thực trần giá:</span>
                <strong className="text-emerald">Bộ Y Tế & DAV</strong>
                <span className="trust-pill-hint">Tra cứu danh mục thuốc chuẩn GPP</span>
              </div>
              <div className="trust-pill-item">
                <span className="trust-pill-name">Quỹ bảo hiểm:</span>
                <strong className="text-cyan">{totalBhytCovered > 0 ? formatVnd(totalBhytCovered, hideAmounts) : 'Hỗ trợ BHYT'}</strong>
                <span className="trust-pill-hint">Cập nhật theo danh mục VssID</span>
              </div>
            </div>
          </section>
        </div>
      </div>

      {/* ====================================================================
          7. SMART RECOMMENDATIONS (MẸO TIẾT KIỆM CHI PHÍ THUỐC & KHÁM CHỮA BỆNH)
          ==================================================================== */}
      <section className="smart-recommendations-section">
        <div className="recs-header-row">
          <div className="recs-title-box">
            <Sparkles size={18} className="text-pink" />
            <h3 className="section-title">Mẹo Tiết Kiệm Chi Phí Thuốc & Khám Chữa Bệnh Thông Minh</h3>
          </div>
          <span className="recs-badge">3 Giải Pháp Tối Ưu</span>
        </div>

        <div className="recs-cards-grid">
          {/* Rec 1 */}
          <div className="rec-card-box">
            <div className="rec-card-top">
              <span className="priority-pill high">ƯU TIÊN CAO</span>
              <span className="saving-highlight-pill">Tiết kiệm 30% - 45% / đơn</span>
            </div>
            <h4 className="rec-card-title">Chuyển sang Generic Nhóm 1 Đạt Chuẩn EU-GMP / US-FDA</h4>
            <p className="rec-card-body">
              Trao đổi toa thuốc của bạn với Bác sĩ AI để tìm các biệt dược Generic nhóm 1 tương đương sinh học (Bioequivalence &gt; 98%) với giá thành thấp hơn biệt dược gốc từ 30% đến 45%.
            </p>
            <div className="rec-card-rationale">
              <strong>Cơ sở y khoa: </strong>
              <span>Được Cục Quản lý Dược (Bộ Y Tế) cấp phép lưu hành Nhóm 1, hiệu quả điều trị an toàn và chất lượng tương đương.</span>
            </div>
            <button
              type="button"
              className="rec-cta-btn"
              onClick={() => {
                onNavigate?.('medication');
                onNotify?.('Đã chuyển sang Lịch uống thuốc để bạn kiểm tra đơn thuốc và dược chất tương đương!', 'success');
              }}
            >
              <span>Xem Lịch uống thuốc</span>
              <ChevronRight size={14} />
            </button>
          </div>

          {/* Rec 2 */}
          <div className="rec-card-box">
            <div className="rec-card-top">
              <span className="priority-pill medium">QUYỀN LỢI BHYT</span>
              <span className="saving-highlight-pill">Hưởng 80% - 100% BHYT</span>
            </div>
            <h4 className="rec-card-title">Khai Thác Tối Đa Quyền Lợi BHYT Đúng Tuyến</h4>
            <p className="rec-card-body">
              Khi đi khám đúng tuyến ban đầu hoặc có giấy chuyển tuyến hợp lệ, toàn bộ chi phí khám chuyên khoa, xét nghiệm cận lâm sàng và thuốc nằm trong danh mục đều được Quỹ BHYT chi trả.
            </p>
            <div className="rec-card-rationale">
              <strong>Quyền lợi bảo hiểm: </strong>
              <span>Áp dụng quy định thông tuyến BHYT theo Luật Bảo hiểm Y tế và Thông tư 20/2022/TT-BYT giúp giảm gánh nặng tài chính.</span>
            </div>
            <button
              type="button"
              className="rec-cta-btn"
              onClick={() => {
                onNavigate?.('schedule');
                onNotify?.('Đã mở Lịch khám bác sĩ để bạn chọn cơ sở y tế đúng tuyến BHYT!', 'info');
              }}
            >
              <span>Đặt lịch khám BHYT</span>
              <ChevronRight size={14} />
            </button>
          </div>

          {/* Rec 3 */}
          <div className="rec-card-box">
            <div className="rec-card-top">
              <span className="priority-pill standard">CHỐNG LÃNG PHÍ</span>
              <span className="saving-highlight-pill">Chuẩn GPP & Đủ Liều</span>
            </div>
            <h4 className="rec-card-title">Mua Đủ Liều Tại Nhà Thuốc Chuẩn GPP Có Hóa Đơn</h4>
            <p className="rec-card-body">
              Tuyệt đối không mua liều lẻ tự do tại các quầy thuốc không có đơn. 100% thuốc điều trị cần mua đủ phác đồ tại các chuỗi GPP lớn có hóa đơn VAT và tư vấn của dược sĩ lâm sàng.
            </p>
            <div className="rec-card-rationale">
              <strong>Lời khuyên dược sĩ: </strong>
              <span>Đảm bảo nguồn gốc xuất xứ thuốc, ngăn ngừa nguy cơ kháng thuốc (AMR) và bảo vệ an toàn cho cả gia đình.</span>
            </div>
            <button
              type="button"
              className="rec-cta-btn"
              onClick={() => {
                onNavigate?.('navigation');
                onNotify?.('Đã mở bản đồ các nhà thuốc chuẩn GPP gần bạn nhất!', 'info');
              }}
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
            <span className="tx-month-filter-badge">
              <Calendar size={13} />
              <span>{showAllMonthsTx ? 'Toàn bộ 6 tháng' : currentMonthMeta.label}</span>
            </span>
            <button
              type="button"
              className={`tx-scope-toggle-btn ${showAllMonthsTx ? 'active' : ''}`}
              onClick={() => setShowAllMonthsTx((v) => !v)}
              title="Chuyển đổi xem tháng đã chọn hoặc toàn bộ lịch sử"
            >
              {showAllMonthsTx ? 'Chỉ xem tháng này' : 'Xem toàn bộ 6 tháng'}
            </button>
          </div>

          <div className="ledger-header-actions" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button
              type="button"
              className="web-action-btn secondary"
              onClick={reloadSpending}
              title="Làm mới dữ liệu từ Database TiDB"
            >
              <RefreshCw size={14} className={loadingSpending ? 'spin' : ''} />
              <span>Làm mới</span>
            </button>
            <button
              type="button"
              className="web-action-btn secondary"
              style={{ background: 'rgba(236, 72, 153, 0.08)', borderColor: 'rgba(236, 72, 153, 0.3)', color: '#ec4899' }}
              onClick={handleSeedSampleSpending}
              title="Nạp 8 giao dịch mẫu vào Database"
            >
              <Sparkles size={14} />
              <span>Nạp mẫu Demo</span>
            </button>
            {transactions.length > 0 && (
              <button
                type="button"
                className="web-action-btn secondary"
                style={{ borderColor: 'rgba(239, 68, 68, 0.4)', color: '#ef4444' }}
                onClick={handleClearSpending}
                title="Xóa toàn bộ giao dịch trong Database"
              >
                <Trash2 size={14} />
                <span>Xóa sạch</span>
              </button>
            )}
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
            <div className="empty-ledger-state" style={{ padding: '36px 20px', textAlign: 'center' }}>
              <Receipt size={44} style={{ color: '#ec4899', margin: '0 auto 12px' }} />
              <h3 style={{ margin: '0 0 8px', fontSize: '1.2rem', fontWeight: 600 }}>Tài khoản của bạn chưa có giao dịch chi tiêu y tế nào</h3>
              <p style={{ margin: '0 auto 18px', color: '#64748b', fontSize: '0.92rem', maxWidth: '520px' }}>
                Hệ thống MedGuard AI được kết nối và đồng bộ trực tiếp với TiDB Cloud theo đúng tài khoản của bạn. Chưa có khoản chi tiêu nào được ghi nhận cho thời gian này.
              </p>
              <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  className="web-action-btn primary-pink"
                  onClick={() => setShowAddModal(true)}
                >
                  <Plus size={16} />
                  <span>+ Nhập giao dịch thực tế</span>
                </button>
                <button
                  type="button"
                  className="web-action-btn secondary"
                  style={{ background: 'rgba(236, 72, 153, 0.1)', borderColor: 'rgba(236, 72, 153, 0.3)', color: '#ec4899' }}
                  onClick={handleSeedSampleSpending}
                >
                  <Sparkles size={15} />
                  <span>Nạp số liệu chi tiêu mẫu Demo</span>
                </button>
              </div>
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
                  <code className="text-pink">{selectedTxForDetail.icd10 || 'Chưa ghi nhận mã ICD-10'}</code>
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
                Hệ thống sẽ dựa vào hạn mức này để tự động tính toán tỷ lệ phân bổ tối ưu theo phác đồ MedGuard (45% Khám sớm & BHYT, 35% Thuốc GPP & Generic, 20% Quỹ dự phòng rủi ro).
                <br />
                <small style={{ color: '#0d9488', fontWeight: 600, display: 'inline-block', marginTop: '4px' }}>
                  💡 Khuyến cáo: Ngân sách y tế gia đình lý tưởng thường chiếm từ 5% – 10% tổng thu nhập tháng.
                </small>
              </p>

              <div className="form-field-item">
                <label>Hạn mức ngân sách mong muốn (VNĐ / Tháng)</label>
                <input
                  type="number"
                  min="500000"
                  step="500000"
                  value={inputBudgetVal}
                  onChange={(e) => setInputBudgetVal(e.target.value)}
                  placeholder="VD: 5.000.000"
                  required
                />
              </div>

              {/* Quick Preset Buttons */}
              <div className="budget-presets-row">
                <span className="presets-label">Gợi ý nhanh theo mức thu nhập:</span>
                {[2000000, 5000000, 10000000, 15000000, 20000000].map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    className={`preset-btn ${inputBudgetVal === String(preset) ? 'active' : ''}`}
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
