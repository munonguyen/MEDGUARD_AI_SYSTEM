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

  // --- THÁNG 9/2026 ---
  {
    id: 'tx_09_01',
    date: '18/09/2026',
    raw_date: '2026-09-18',
    time: '09:30',
    title: 'Tái khám Tiêu Hóa & Nội soi đại trực tràng tầm soát',
    provider: 'Bệnh viện Chợ Rẫy TP.HCM',
    doctor: 'TS. BS Trần Văn Hùng',
    icd10: 'K58.0 - Hội chứng ruột kích thích',
    category: 'clinic',
    category_name: 'Khám chuyên khoa',
    source_type: 'hospital_clinic',
    amount_vnd: -1850000,
    bhyt_covered_vnd: 1480000,
    is_gpp: true,
    dav_compliant: true,
    dav_registration: 'BYT-CR-0129',
    bhyt_rate: 80,
    rx_code: 'RX-2026-0899',
    e_invoice_no: 'BV-CHORAY-44102',
    treatment_status: 'Kết quả nội soi an toàn • Không có polyp',
    clinical_notes: 'Thăm khám định kỳ theo phác đồ BHYT • Niêm mạc hồng hào, đáp ứng tốt với chế độ dinh dưỡng',
    items: [
      { name: 'Công khám & Gói nội soi đại trực tràng không đau', qty: '1 gói', unit_price: 1850000, dav_ceiling: 1850000, amount: 1850000 },
    ],
    verified: true,
  },
  {
    id: 'tx_09_02',
    date: '22/09/2026',
    raw_date: '2026-09-22',
    time: '15:10',
    title: 'Thuốc hạ mỡ máu Atorvastatin 20mg (Generic EU-GMP Sandoz)',
    provider: 'Nhà thuốc Long Châu - Chuẩn GPP',
    doctor: 'BS. CKII Phạm Hoàng Tâm',
    icd10: 'E78.0 - Tăng cholesterol máu nguyên phát',
    category: 'medication',
    category_name: 'Thuốc kê đơn GPP',
    source_type: 'gpp_pharmacy',
    amount_vnd: -380000,
    bhyt_covered_vnd: 304000,
    is_gpp: true,
    dav_compliant: true,
    dav_registration: 'VN-19340-15',
    bhyt_rate: 80,
    rx_code: 'RX-2026-0841',
    e_invoice_no: 'HD-LC-09188',
    treatment_status: 'Duy trì uống mỗi tối 1 viên',
    clinical_notes: 'Thuốc Generic Nhóm 1 chuẩn châu Âu • Tiết kiệm 42% so với biệt dược gốc Lipitor',
    items: [
      { name: 'Atorvastatin Sandoz 20mg (Hộp 30 viên)', qty: '1 hộp', unit_price: 380000, dav_ceiling: 400000, amount: 380000 },
    ],
    verified: true,
  },
  {
    id: 'tx_09_03',
    date: '10/09/2026',
    raw_date: '2026-09-10',
    time: '08:20',
    title: 'Xét nghiệm Sinh Hóa Máu: Lipid toàn phần, Ure & Creatinin',
    provider: 'Trung tâm Xét nghiệm Y khoa Diag',
    doctor: 'BS. Nguyễn Thị Thu Hà',
    icd10: 'Z01.7 - Khám xét nghiệm cận lâm sàng định kỳ',
    category: 'diagnostics',
    category_name: 'Xét nghiệm cận lâm sàng',
    source_type: 'hospital_clinic',
    amount_vnd: -450000,
    bhyt_covered_vnd: 225000,
    is_gpp: true,
    dav_compliant: true,
    dav_registration: 'ISO-15189-DIAG',
    bhyt_rate: 50,
    rx_code: 'LAB-7102',
    e_invoice_no: 'HD-DIAG-08102',
    treatment_status: 'Chỉ số gan thận trong giới hạn tối ưu',
    clinical_notes: 'Định lượng cholesterol HDL/LDL và chức năng lọc cầu thận eGFR = 92 ml/min',
    items: [
      { name: 'Bộ bilan Lipid máu 4 chỉ số', qty: '1 mẫu', unit_price: 250000, dav_ceiling: 260000, amount: 250000 },
      { name: 'Định lượng Ure & Creatinin huyết thanh', qty: '1 mẫu', unit_price: 200000, dav_ceiling: 210000, amount: 200000 },
    ],
    verified: true,
  },
  {
    id: 'tx_09_04',
    date: '05/09/2026',
    raw_date: '2026-09-05',
    time: '14:00',
    title: 'Hoàn Viện Phí Giám Định BHYT Quý 3/2026',
    provider: 'Bảo hiểm Xã hội TP.HCM (VssID)',
    doctor: 'Hệ thống liên thông BHXH Quốc gia',
    icd10: 'Z01.9 - Quyết toán BHYT',
    category: 'refund',
    category_name: 'BHYT chi trả',
    source_type: 'hospital_clinic',
    amount_vnd: 2100000,
    bhyt_covered_vnd: 2100000,
    is_gpp: true,
    dav_compliant: true,
    dav_registration: 'BHYT-QD-2026',
    bhyt_rate: 100,
    rx_code: 'BHYT-REF-7712',
    e_invoice_no: 'BHXH-QTOAN-0905',
    treatment_status: 'Đã hoàn tất thanh toán',
    clinical_notes: 'Chi trả chế độ đồng thanh toán BHYT 5 năm liên tục theo luật BHYT số 46/2014/QH13',
    items: [
      { name: 'Hoàn chi phí đồng thanh toán BHYT 5 năm liên tục', qty: '1 khoản', unit_price: 2100000, dav_ceiling: 2100000, amount: 2100000 },
    ],
    verified: true,
  },
  {
    id: 'tx_09_05',
    date: '02/09/2026',
    raw_date: '2026-09-02',
    time: '10:15',
    title: 'Thuốc hạ áp Amlodipine 5mg (Generic EU-GMP Stada)',
    provider: 'Nhà thuốc An Khang - Chuẩn GPP',
    doctor: 'BS. CKII Phạm Hoàng Tâm',
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
    rx_code: 'RX-2026-0802',
    e_invoice_no: 'HD-AK-33910',
    treatment_status: 'Thuốc mãn tính tháng 9',
    clinical_notes: 'Uống đều đặn mỗi sáng • Huyết áp mục tiêu < 120/80 mmHg',
    items: [
      { name: 'Amlodipine Stada 5mg (Hộp 30 viên)', qty: '1 hộp', unit_price: 165000, dav_ceiling: 180000, amount: 165000 },
    ],
    verified: true,
  },

  // --- THÁNG 8/2026 ---
  {
    id: 'tx_08_01',
    date: '24/08/2026',
    raw_date: '2026-08-24',
    time: '08:45',
    title: 'Khám chuyên khoa Hô Hấp & Điều trị Viêm Phế Quản Cấp',
    provider: 'Bệnh viện Phạm Ngọc Thạch',
    doctor: 'BS. CKI Vũ Hải Yến',
    icd10: 'J20.9 - Viêm phế quản cấp',
    category: 'clinic',
    category_name: 'Khám chuyên khoa',
    source_type: 'hospital_clinic',
    amount_vnd: -850000,
    bhyt_covered_vnd: 680000,
    is_gpp: true,
    dav_compliant: true,
    dav_registration: 'BYT-PNT-091',
    bhyt_rate: 80,
    rx_code: 'RX-2026-0792',
    e_invoice_no: 'BV-PNT-99120',
    treatment_status: 'Đã khỏi dứt điểm',
    clinical_notes: 'Khám chuyên sâu hô hấp đúng tuyến • Cắt cơn ho sốt sau 3 ngày điều trị',
    items: [
      { name: 'Khám chuyên khoa & Khí dung mũi họng', qty: '1 đợt', unit_price: 850000, dav_ceiling: 850000, amount: 850000 },
    ],
    verified: true,
  },
  {
    id: 'tx_08_02',
    date: '24/08/2026',
    raw_date: '2026-08-24',
    time: '09:30',
    title: 'Chụp X-quang Phổi Kỹ Thuật Số (DR) & Đo Chức Năng Hô Hấp',
    provider: 'Bệnh viện Phạm Ngọc Thạch',
    doctor: 'BS. CKI Vũ Hải Yến',
    icd10: 'R91 - Kết quả hình ảnh X-quang phổi',
    category: 'diagnostics',
    category_name: 'Xét nghiệm cận lâm sàng',
    source_type: 'hospital_clinic',
    amount_vnd: -450000,
    bhyt_covered_vnd: 360000,
    is_gpp: true,
    dav_compliant: true,
    dav_registration: 'BYT-XQ-2026',
    bhyt_rate: 80,
    rx_code: 'RAD-2026-084',
    e_invoice_no: 'BV-PNT-99125',
    treatment_status: 'Nhu mô phổi bình thường, không tổn thương',
    clinical_notes: 'Loại trừ viêm phổi thùy và tràn dịch màng phổi • Đạt tiêu chuẩn an toàn bức xạ',
    items: [
      { name: 'X-quang ngực thẳng kỹ thuật số DR', qty: '1 phim', unit_price: 250000, dav_ceiling: 250000, amount: 250000 },
      { name: 'Đo phế dung hô hấp ký', qty: '1 lần', unit_price: 200000, dav_ceiling: 200000, amount: 200000 },
    ],
    verified: true,
  },
  {
    id: 'tx_08_03',
    date: '02/08/2026',
    raw_date: '2026-08-02',
    time: '11:00',
    title: 'Thuốc hạ áp Amlodipine 5mg (Generic EU-GMP Stada)',
    provider: 'Nhà thuốc Long Châu - Chuẩn GPP',
    doctor: 'BS. CKII Phạm Hoàng Tâm',
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
    rx_code: 'RX-2026-0701',
    e_invoice_no: 'HD-LC-77401',
    treatment_status: 'Thuốc mãn tính tháng 8',
    clinical_notes: 'Uống duy trì đều đặn',
    items: [
      { name: 'Amlodipine Stada 5mg (Hộp 30 viên)', qty: '1 hộp', unit_price: 165000, dav_ceiling: 180000, amount: 165000 },
    ],
    verified: true,
  },

  // --- THÁNG 7/2026 ---
  {
    id: 'tx_07_01',
    date: '18/07/2026',
    raw_date: '2026-07-18',
    time: '09:00',
    title: 'Khám Tim Mạch Chuyên Sâu & Siêu Âm Tim Doppler Màu',
    provider: 'Bệnh viện Tim Tâm Đức TP.HCM',
    doctor: 'TS. BS Đỗ Nguyên Tín',
    icd10: 'I10 - Tăng huyết áp • Khám chức năng van tim',
    category: 'clinic',
    category_name: 'Khám chuyên khoa',
    source_type: 'hospital_clinic',
    amount_vnd: -1250000,
    bhyt_covered_vnd: 1000000,
    is_gpp: true,
    dav_compliant: true,
    dav_registration: 'BYT-TTD-071',
    bhyt_rate: 80,
    rx_code: 'RX-2026-0691',
    e_invoice_no: 'BV-TAMDUC-8812',
    treatment_status: 'Chức năng tâm thu thất trái EF = 64% bình thường',
    clinical_notes: 'Siêu âm tim định kỳ đánh giá cơ tim và buồng tim • Huyết áp kiểm soát tốt',
    items: [
      { name: 'Gói khám tim mạch & Siêu âm tim 4D Doppler màu', qty: '1 gói', unit_price: 1250000, dav_ceiling: 1250000, amount: 1250000 },
    ],
    verified: true,
  },
  {
    id: 'tx_07_02',
    date: '18/07/2026',
    raw_date: '2026-07-18',
    time: '10:30',
    title: 'Thuốc phối hợp Coversyl Plus & Amlodipine Generic EU-GMP',
    provider: 'Nhà thuốc Long Châu - Chuẩn GPP',
    doctor: 'TS. BS Đỗ Nguyên Tín',
    icd10: 'I10 - Tăng huyết áp phối hợp',
    category: 'medication',
    category_name: 'Thuốc kê đơn GPP',
    source_type: 'gpp_pharmacy',
    amount_vnd: -540000,
    bhyt_covered_vnd: 432000,
    is_gpp: true,
    dav_compliant: true,
    dav_registration: 'VN-18812-14',
    bhyt_rate: 80,
    rx_code: 'RX-2026-0692',
    e_invoice_no: 'HD-LC-66102',
    treatment_status: 'Duy trì liệu trình 30 ngày',
    clinical_notes: 'Bảo vệ thành mạch và ngăn ngừa phì đại thất trái',
    items: [
      { name: 'Thuốc Coversyl Plus 5mg/1.25mg Servier', qty: '1 hộp', unit_price: 375000, dav_ceiling: 380000, amount: 375000 },
      { name: 'Amlodipine Stada 5mg', qty: '1 hộp', unit_price: 165000, dav_ceiling: 180000, amount: 165000 },
    ],
    verified: true,
  },

  // --- THÁNG 6/2026 ---
  {
    id: 'tx_06_01',
    date: '12/06/2026',
    raw_date: '2026-06-12',
    time: '08:30',
    title: 'Khám Cấp Tính Đợt Loét Dạ Dày & Test Vi Khuẩn HP Hơi Thở C13',
    provider: 'Bệnh viện Đại học Y Dược TP.HCM',
    doctor: 'PGS. TS. BS Lê Quang Quốc Bảo',
    icd10: 'K25.3 - Loét dạ dày cấp tính có xuất huyết nhẹ',
    category: 'clinic',
    category_name: 'Khám chuyên khoa',
    source_type: 'hospital_clinic',
    amount_vnd: -1650000,
    bhyt_covered_vnd: 1320000,
    is_gpp: true,
    dav_compliant: true,
    dav_registration: 'BYT-CS-0081',
    bhyt_rate: 80,
    rx_code: 'BS-CKI-612',
    e_invoice_no: 'BV-YDUOC-55109',
    treatment_status: 'Kết quả test HP Âm tính • Phác đồ lành niêm mạc',
    clinical_notes: 'Cấp cứu nội khoa dạ dày đợt 1 • Can thiệp kịp thời bảo vệ thành dạ dày',
    items: [
      { name: 'Khám chuyên khoa & Test thở C13 chẩn đoán HP', qty: '1 gói', unit_price: 1650000, dav_ceiling: 1650000, amount: 1650000 },
    ],
    verified: true,
  },
  {
    id: 'tx_06_02',
    date: '12/06/2026',
    raw_date: '2026-06-12',
    time: '10:00',
    title: 'Thuốc Nexium 40mg (Esomeprazole AstraZeneca) & Thuốc băng dạ dày',
    provider: 'Nhà thuốc Long Châu - Chuẩn GPP',
    doctor: 'PGS. TS. BS Lê Quang Quốc Bảo',
    icd10: 'K25.3 - Loét dạ dày cấp tính',
    category: 'medication',
    category_name: 'Thuốc kê đơn GPP',
    source_type: 'gpp_pharmacy',
    amount_vnd: -480000,
    bhyt_covered_vnd: 384000,
    is_gpp: true,
    dav_compliant: true,
    dav_registration: 'VN-22145-19',
    bhyt_rate: 80,
    rx_code: 'RX-2026-0612',
    e_invoice_no: 'HD-LC-55190',
    treatment_status: 'Phác đồ 28 ngày dứt điểm',
    clinical_notes: 'Liều tấn công 40mg/ngày giúp tái tạo biểu mô thượng vị',
    items: [
      { name: 'Nexium 40mg AstraZeneca', qty: '14 viên', unit_price: 24000, dav_ceiling: 24500, amount: 336000 },
      { name: 'Phosphalugel gói 20g', qty: '12 gói', unit_price: 12000, dav_ceiling: 12500, amount: 144000 },
    ],
    verified: true,
  },

  // --- THÁNG 5/2026 ---
  {
    id: 'tx_05_01',
    date: '15/05/2026',
    raw_date: '2026-05-15',
    time: '08:00',
    title: 'Khám Sức Khỏe Tổng Quát & Tầm Soát Ung Thư Sớm Định Kỳ',
    provider: 'Bệnh viện Chợ Rẫy TP.HCM',
    doctor: 'Khoa Khám Bệnh Theo Yêu Cầu',
    icd10: 'Z00.0 - Khám sức khỏe tổng quát định kỳ',
    category: 'clinic',
    category_name: 'Khám chuyên khoa',
    source_type: 'hospital_clinic',
    amount_vnd: -1950000,
    bhyt_covered_vnd: 1560000,
    is_gpp: true,
    dav_compliant: true,
    dav_registration: 'BYT-CR-0051',
    bhyt_rate: 80,
    rx_code: 'RX-2026-0511',
    e_invoice_no: 'BV-CHORAY-33012',
    treatment_status: 'Hồ sơ sức khỏe định kỳ đầu năm',
    clinical_notes: 'Đầy đủ các chuyên khoa Mắt, Tai Mũi Họng, Răng Hàm Mặt, Nội Ngoại Tổng Quát',
    items: [
      { name: 'Gói khám lâm sàng tổng thể toàn diện', qty: '1 gói', unit_price: 1950000, dav_ceiling: 1950000, amount: 1950000 },
    ],
    verified: true,
  },
  {
    id: 'tx_05_02',
    date: '15/05/2026',
    raw_date: '2026-05-15',
    time: '09:15',
    title: 'Bộ Xét Nghiệm 18 Chỉ Số Máu, Nước Tiểu & Dấu Ấn Ung Thư',
    provider: 'Trung tâm Xét nghiệm Y khoa Diag',
    doctor: 'BS. Nguyễn Thị Thu Hà',
    icd10: 'Z01.7 - Xét nghiệm cận lâm sàng định kỳ',
    category: 'diagnostics',
    category_name: 'Xét nghiệm cận lâm sàng',
    source_type: 'hospital_clinic',
    amount_vnd: -890000,
    bhyt_covered_vnd: 445000,
    is_gpp: true,
    dav_compliant: true,
    dav_registration: 'ISO-15189-DIAG',
    bhyt_rate: 50,
    rx_code: 'LAB-5012',
    e_invoice_no: 'HD-DIAG-05012',
    treatment_status: 'Chỉ số bình thường, không phát hiện bệnh lý ác tính',
    clinical_notes: 'Tầm soát chỉ số CEA, AFP, CA 19-9 và xét nghiệm tổng phân tích nước tiểu 10 thông số',
    items: [
      { name: 'Gói xét nghiệm sinh hóa & huyết học tổng quát 18 thông số', qty: '1 gói', unit_price: 890000, dav_ceiling: 900000, amount: 890000 },
    ],
    verified: true,
  },
];

// 6 Available Calendar Months Registry for Database-driven Dynamic Navigation
export const AVAILABLE_MONTHS = [
  { key: '2026-10', label: 'Tháng này (10/2026)', shortLabel: 'T10/26', defaultSpend: 12366016, defaultBhyt: 8540000, genericSaved: 4.8 },
  { key: '2026-09', label: 'Tháng 9/2026', shortLabel: 'T9/26', defaultSpend: 12900000, defaultBhyt: 7900000, genericSaved: 4.1 },
  { key: '2026-08', label: 'Tháng 8/2026', shortLabel: 'T8/26', defaultSpend: 15100000, defaultBhyt: 7500000, genericSaved: 3.6 },
  { key: '2026-07', label: 'Tháng 7/2026', shortLabel: 'T7/26', defaultSpend: 13800000, defaultBhyt: 7100000, genericSaved: 3.2 },
  { key: '2026-06', label: 'Tháng 6/2026', shortLabel: 'T6/26', defaultSpend: 16500000, defaultBhyt: 6400000, genericSaved: 2.8 },
  { key: '2026-05', label: 'Tháng 5/2026', shortLabel: 'T5/26', defaultSpend: 14200000, defaultBhyt: 5800000, genericSaved: 2.1 },
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
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          const hasPriorMonths = parsed.some((tx) => tx.raw_date && !tx.raw_date.startsWith('2026-10'));
          if (!hasPriorMonths) {
            const priorTxs = INITIAL_TRANSACTIONS.filter((tx) => tx.raw_date && !tx.raw_date.startsWith('2026-10'));
            return [...parsed, ...priorTxs];
          }
          return parsed;
        }
      }
      return INITIAL_TRANSACTIONS;
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

  // Assessment state from unified chat sync
  const [assessment, setAssessment] = useState(() => {
    try {
      const saved = localStorage.getItem('medguard_financial_assessment');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

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

  // Dynamic calculations for the selected month according to transactions database
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

    // Default or transaction-derived figures
    let actualSpend = txSpend > 0 ? txSpend : currentMonthMeta.defaultSpend;
    let bhytCovered = txBhyt > 0 ? txBhyt : currentMonthMeta.defaultBhyt;

    // For current month (T10), if assessment from chat sync exists, respect assessment
    if (selectedMonthIndex === 0) {
      if (assessment?.total_actual_spend_vnd) {
        actualSpend = assessment.total_actual_spend_vnd;
      }
      if (assessment?.bhyt_paid_vnd) {
        bhytCovered = assessment.bhyt_paid_vnd;
      }
    }

    return {
      mTransactions,
      actualSpend,
      bhytCovered,
    };
  }, [transactions, selectedMonthKey, selectedMonthIndex, assessment, currentMonthMeta]);

  // Total actual monthly spend for selected month
  const totalActualSpend = selectedMonthData.actualSpend;

  // Total BHYT paid or supplementary inflow for selected month
  const totalBhytCovered = selectedMonthData.bhytCovered;

  // Budget calculations for selected month
  const remainingBudget = Math.max(0, budgetTarget - totalActualSpend);
  const budgetUtilizationPct = Math.min(100, Math.round((totalActualSpend / budgetTarget) * 100));

  // MedGuard 45-35-20 Care Allocation for selected month
  const allocation45 = Math.round(budgetTarget * 0.45);
  const allocation35 = Math.round(budgetTarget * 0.35);
  const allocation20 = Math.round(budgetTarget * 0.20);

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
      let amount = baseCat.amount_vnd;
      let pct = baseCat.percentage;

      if (hasTxData && actualSpend > 0) {
        amount = categoryTotals[baseCat.id] || 0;
        pct = Math.max(1, Math.round((amount / actualSpend) * 100));
      } else if (selectedMonthIndex !== 0) {
        amount = Math.round((baseCat.percentage / 100) * actualSpend);
      }

      return {
        ...baseCat,
        amount_vnd: amount,
        percentage: pct,
      };
    });
  }, [selectedMonthData, selectedMonthIndex]);

  // Dynamic Donut SVG Arcs for selected month
  const dynamicDonutArcs = useMemo(() => {
    let currentOffset = 0;
    const circumference = 439.82;
    return currentCategories.map((cat) => {
      const pct = Math.max(1, cat.percentage);
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
  }, [currentCategories]);

  // Dynamic Comparison with Prior Month
  const monthComparison = useMemo(() => {
    const priorMonthIndex = selectedMonthIndex + 1;
    if (priorMonthIndex < AVAILABLE_MONTHS.length) {
      const prior = AVAILABLE_MONTHS[priorMonthIndex];
      const diff = totalActualSpend - prior.defaultSpend;
      const isReduction = diff <= 0;
      const absDiff = Math.abs(diff);
      const pct = Math.abs(Math.round((diff / prior.defaultSpend) * 100));
      return {
        hasPrior: true,
        isReduction,
        absDiff,
        pct,
        priorLabel: prior.label,
        text: isReduction
          ? `Giảm ${formatVnd(absDiff)} so với ${prior.label}`
          : `Tăng ${formatVnd(absDiff)} so với ${prior.label}`,
        subText: isReduction
          ? `Tiết kiệm ${pct}% chi phí y tế nhờ dùng thuốc Generic EU-GMP nhóm 1 đạt tương đương sinh học đúng trần DAV.`
          : `Chi phí tăng ${pct}% do phát sinh các đợt khám chuyên khoa hoặc xét nghiệm cận lâm sàng bổ sung.`,
      };
    }
    return {
      hasPrior: false,
      isReduction: true,
      text: `Số liệu ghi nhận đầy đủ cho ${currentMonthMeta.label}`,
      subText: 'Toàn bộ khoản chi đều được giám định theo danh mục BHYT và trần giá Cục Quản Lý Dược (DAV).',
    };
  }, [selectedMonthIndex, totalActualSpend, currentMonthMeta]);

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
              <span className="sc-save-pill">Tiết kiệm 38% – 40%</span>
            </div>
            <div className="dav-visual-bars-list">
              {[
                { name: "Esomeprazole 40mg (Dạ dày)", brand: 24000, generic: 14500, savePct: 40 },
                { name: "Augmentin 1g (Kháng sinh)", brand: 21000, generic: 13200, savePct: 37 },
                { name: "Amlodipine 5mg (Huyết áp)", brand: 5500, generic: 3400, savePct: 38 },
              ].map((d, idx) => (
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
              ))}
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
            <p className="alloc-card-desc">
              Khám chuyên khoa sớm đúng tuyến tại BV Đại học Y Dược giúp quỹ BHYT chi trả 80–100%, dứt điểm bệnh ban đầu tránh biến chứng tốn kém.
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
            <p className="alloc-card-desc">
              Mua thuốc tại chuỗi GPP uy tín (Long Châu, An Khang), ưu tiên biệt dược Generic Nhóm 1 EU-GMP có sinh khả dụng đạt nồng độ ức chế MIC.
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
                          <span className="donut-core-pct-badge neutral">100% Thực chi</span>
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
                <span className="trust-pill-name">Độ uy tín cộng đồng:</span>
                <strong className="text-pink">94.5%</strong>
                <span className="trust-pill-hint">Từ hàng ngàn người bệnh đánh giá</span>
              </div>
              <div className="trust-pill-item">
                <span className="trust-pill-name">Xác thực đánh giá thật:</span>
                <strong className="text-emerald">98.6%</strong>
                <span className="trust-pill-hint">Đã loại bỏ tin rác & đánh giá ảo</span>
              </div>
              <div className="trust-pill-item">
                <span className="trust-pill-name">Độ tin cậy nhà thuốc:</span>
                <strong className="text-cyan">0.96 / 1.0</strong>
                <span className="trust-pill-hint">Chuỗi nhà thuốc GPP niêm yết giá</span>
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
              <span className="saving-highlight-pill">Tiết kiệm ~420.000 ₫ / tháng</span>
            </div>
            <h4 className="rec-card-title">Chuyển sang Generic Nhóm 1 EU-GMP cho Thuốc Dạ Dày</h4>
            <p className="rec-card-body">
              Biệt dược Esomeprazole Stada 40mg đạt chuẩn tương đương sinh học 99.2% so với Nexium 40mg của AstraZeneca nhưng giá thành thấp hơn 40%.
            </p>
            <div className="rec-card-rationale">
              <strong>Cơ sở y khoa: </strong>
              <span>Được Cục Quản lý Dược cấp phép lưu hành Nhóm 1, nồng độ ức chế acid dạ dày tương đương, hiệu quả điều trị an toàn như nhau.</span>
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
              <span className="saving-highlight-pill">Tiết kiệm ~680.000 ₫ / đợt</span>
            </div>
            <h4 className="rec-card-title">Sử Dụng Giấy Chuyển Tuyến BHYT Khám Tiêu Hóa</h4>
            <p className="rec-card-body">
              Khi có giấy chuyển tuyến từ trung tâm y tế quận lên BV Đại học Y Dược, chi phí nội soi và tiền khám chuyên khoa được Quỹ BHYT chi trả 80%.
            </p>
            <div className="rec-card-rationale">
              <strong>Quyền lợi bảo hiểm: </strong>
              <span>Áp dụng quy định thông tuyến BHYT theo Luật Bảo hiểm Y tế và Thông tư 20/2022/TT-BYT giúp giảm chi phí khám và xét nghiệm.</span>
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
              <span className="saving-highlight-pill">Tránh tái phát & Kháng thuốc</span>
            </div>
            <h4 className="rec-card-title">Tuyệt Đối Chấm Dứt Mua Liều Lẻ Tại Tiệm Tự Do</h4>
            <p className="rec-card-body">
              Dùng kháng sinh cắt liều lẻ 2–3 ngày không đủ nồng độ ức chế MIC gây vi khuẩn kháng thuốc (AMR), dẫn đến bệnh tái phát 3–4 lần tốn kém hơn 500.000 ₫.
            </p>
            <div className="rec-card-rationale">
              <strong>Lời khuyên dược sĩ: </strong>
              <span>100% Thuốc điều trị cần mua đủ phác đồ tại chuỗi GPP có hóa đơn VAT và tư vấn của dược sĩ lâm sàng.</span>
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
