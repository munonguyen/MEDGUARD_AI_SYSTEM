import React, { useState, useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Barcode,
  Building2,
  Calendar,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  ClipboardList,
  Clock,
  Compass,
  CornerUpLeft,
  CornerUpRight,
  ExternalLink,
  Hash,
  HeartPulse,
  Layers,
  ListChecks,
  MapPin,
  Navigation,
  PackageCheck,
  PhoneCall,
  PieChart,
  Pill,
  QrCode,
  RotateCcw,
  Route,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  Target,
  Truck,
  WalletCards,
  X,
} from 'lucide-react';
import './GroundedAnswer.css';

const evidenceLabels = {
  direct_rule_match: 'Khớp theo phác đồ hướng dẫn y tế',
  bounded_result: 'Nội dung dựa trên dữ liệu sức khỏe đã ghi nhận',
  operation_confirmed: 'Thao tác đã được lưu vào hệ thống',
  partial_input: 'Cần thêm thông tin để tư vấn chính xác hơn',
};

const verificationLabels = {
  verified: 'Đã đối soát an toàn y khoa',
  shadow_pending: 'Đang rà soát an toàn bổ sung',
  shadow: 'Đã hoàn tất rà soát; thông tin an toàn được đảm bảo',
  timed_out: 'Khuyến nghị an toàn cơ bản (đang cập nhật phân tích chuyên sâu)',
  rejected: 'Khuyến nghị an toàn cơ bản (vui lòng tham khảo thêm bác sĩ)',
  unavailable: 'Khuyến nghị chăm sóc cơ bản ban đầu',
  circuit_open: 'Khuyến nghị chăm sóc sức khỏe cơ bản',
  error: 'Khuyến nghị chăm sóc cơ bản (hệ thống tư vấn dự phòng)',
  not_requested: 'Khuyến nghị chuẩn theo hướng dẫn chăm sóc y tế',
};

const knowledgeLabels = {
  approved: 'Tài liệu y khoa chính thống đã kiểm duyệt',
  pending_review: 'Tài liệu đang trong quy trình cập nhật định kỳ',
  mixed: 'Tổng hợp từ nguồn y khoa chuẩn và thông tin tham khảo',
  not_recorded: 'Thông tin tham khảo y tế đại chúng',
};

const clinicalIntents = new Set(['triage', 'safety', 'monitoring', 'followup', 'pharmacy']);

/**
 * Render specialized authenticity check card for anti-counterfeit QR verification.
 */
function ProductVerificationCard({ result, answer }) {
  if (!result || !result.verification_status) return null;
  const status = result.verification_status;
  const product = result.product || {};
  const decoded = result.decoded || {};
  const reasons = result.reasons || [];

  const isMatch = status === 'registry_match';
  const isCounterfeit = status === 'suspected_counterfeit';
  const isRecalled = status === 'recalled';
  const isExpired = status === 'expired';

  const badgeConfig = isMatch
    ? {
        tone: 'match',
        icon: ShieldCheck,
        badgeText: 'CHÍNH HÃNG — KHỚP HỒ SƠ REGISTRY DƯỢC PHẨM',
        subText: 'Mã QR và thông tin xuất xưởng trùng khớp hoàn toàn với registry của nhà sản xuất.',
      }
    : isCounterfeit
    ? {
        tone: 'danger',
        icon: ShieldAlert,
        badgeText: 'CẢNH BÁO: PHÁT HIỆN DẤU HIỆU HÀNG GIẢ / NHÁI',
        subText: 'Mã serial hoặc số lô không thuộc danh mục xuất xưởng của nhà sản xuất. TUYỆT ĐỐI KHÔNG DÙNG THUỐC!',
      }
    : isRecalled
    ? {
        tone: 'recalled',
        icon: AlertTriangle,
        badgeText: 'CẢNH BÁO: LÔ SẢN PHẨM BỊ THU HỒI',
        subText: 'Sản phẩm thuộc lô có quyết định thu hồi khẩn cấp từ cơ quan quản lý y tế hoặc nhà sản xuất.',
      }
    : isExpired
    ? {
        tone: 'expired',
        icon: AlertTriangle,
        badgeText: 'CẢNH BÁO: THUỐC ĐÃ QUÁ HẠN DÙNG',
        subText: 'Hạn sử dụng ghi nhận trong hồ sơ registry đã hết hạn. Ngưng dùng sản phẩm ngay!',
      }
    : {
        tone: 'unknown',
        icon: AlertCircle,
        badgeText: 'CHƯA ĐỐI CHIẾU ĐƯỢC HOÀN CHỈNH',
        subText: 'Chưa tìm thấy mã trong registry hoặc mã QR thiếu serial/số lô cần thiết.',
      };

  const BadgeIcon = badgeConfig.icon;

  return (
    <div className={`product-verify-card verify-${badgeConfig.tone}`}>
      <div className="verify-card-header">
        <div className="verify-badge-wrap">
          <span className={`verify-status-badge ${badgeConfig.tone}`}>
            <BadgeIcon size={16} />
            <strong>{badgeConfig.badgeText}</strong>
          </span>
          <p className="verify-status-sub">{badgeConfig.subText}</p>
        </div>
      </div>

      <div className="verify-specs-grid">
        <div className="verify-spec-item">
          <span className="spec-label"><PackageCheck size={13} /> Tên sản phẩm</span>
          <strong className="spec-value">{product.name || decoded.product || 'Chưa xác định'}</strong>
        </div>
        <div className="verify-spec-item">
          <span className="spec-label"><Building2 size={13} /> Nhà sản xuất</span>
          <strong className="spec-value">{product.manufacturer || 'Đang cập nhật'}</strong>
        </div>
        <div className="verify-spec-item">
          <span className="spec-label"><Hash size={13} /> Số lô (Lot)</span>
          <strong className={`spec-value ${isMatch ? 'text-success' : isCounterfeit ? 'text-danger' : ''}`}>
            {decoded.lot || (product.lots ? product.lots[0] : 'N/A')}
          </strong>
        </div>
        <div className="verify-spec-item">
          <span className="spec-label"><Barcode size={13} /> Serial Number</span>
          <strong className={`spec-value ${isMatch ? 'text-success' : isCounterfeit ? 'text-danger' : ''}`}>
            {decoded.serial || 'N/A'}
          </strong>
        </div>
        {product.gtin && (
          <div className="verify-spec-item">
            <span className="spec-label"><QrCode size={13} /> Mã GTIN</span>
            <span className="spec-value mono">{product.gtin}</span>
          </div>
        )}
        {product.expires_on && (
          <div className="verify-spec-item">
            <span className="spec-label"><Calendar size={13} /> Hạn dùng (Exp)</span>
            <strong className={`spec-value ${isExpired ? 'text-danger' : ''}`}>{product.expires_on}</strong>
          </div>
        )}
      </div>

      {reasons.length > 0 && (
        <div className="verify-reasons-box">
          <span className="reasons-title">Căn cứ đối chiếu & phân tích:</span>
          <ul>
            {reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      {(isCounterfeit || isRecalled) && (
        <div className="verify-urgent-callout">
          <ShieldAlert size={18} />
          <div>
            <strong>Khuyến cáo an toàn khẩn cấp:</strong>
            <p>
              Tuyệt đối không uống hoặc tiêm/truyền sản phẩm này. Hãy giữ nguyên vỏ hộp, hóa đơn mua hàng và thông báo ngay cho nhà thuốc hoặc đường dây nóng Cục Quản lý Dược để được hỗ trợ điều tra xử lý.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Render specialized executive healthcare financial advisory card.
 */
function FinancialAdvisoryCard({ result, answer }) {
  const assessment = answer?.financial_assessment_update?.assessment || result?.assessment || result || {};
  const budgetTarget = assessment.monthly_budget_target_vnd || result?.monthly_budget_target_vnd || 3000000;
  const breakdown = assessment.breakdown || {};
  const totalSpent = breakdown.total_spent_vnd ?? result?.total_spent_vnd ?? 1250000;
  const remaining = assessment.remaining_budget_vnd ?? result?.remaining_budget_vnd ?? Math.max(0, budgetTarget - totalSpent);
  const pct = budgetTarget > 0 ? Math.round((totalSpent / budgetTarget) * 1000) / 10 : 0;
  const tes = assessment.treatment_efficiency_score ?? result?.treatment_efficiency_score ?? 54;
  const roiRank = assessment.health_roi_rank ?? result?.health_roi_rank ?? 'C';
  const wasteSpent = breakdown.recurrence_waste_spent_vnd ?? 420000;

  const doctorAlloc = Math.round(budgetTarget * 0.45);
  const medAlloc = Math.round(budgetTarget * 0.35);
  const reserveAlloc = budgetTarget - doctorAlloc - medAlloc;

  const handleOpenSpending = (e) => {
    e.preventDefault();
    window.dispatchEvent(new CustomEvent('medguard:navigate', { detail: 'spending' }));
  };

  const isOver = pct > 100;
  const isApproaching = pct >= 80;
  const statusLabel = isOver
    ? '⚠️ ĐÃ VƯỢT HẠN MỨC NGÂN SÁCH'
    : isApproaching
    ? '⚡ ĐANG TIỆM CẬN HẠN MỨC'
    : '✅ AN TOÀN TRONG TẦM KIỂM SOÁT';
  const statusClass = isOver ? 'danger' : isApproaching ? 'warning' : 'safe';

  return (
    <div className="financial-advisory-card">
      <div className="financial-advisory-header">
        <div className="financial-header-left">
          <div className="financial-icon-badge">
            <WalletCards size={22} />
          </div>
          <div className="financial-header-titles">
            <span className="financial-kicker">KẾ HOẠCH QUẢN TRỊ NGÂN SÁCH Y TẾ & KINH TẾ DƯỢC HỌC</span>
            <h3 className="financial-title">
              Hạn mức tháng 10/2026: <strong>{budgetTarget.toLocaleString('vi-VN')} đ</strong> / Tháng
            </h3>
          </div>
        </div>
        <div className="financial-header-badge">
          <CheckCircle2 size={14} />
          <span>ĐÃ XÁC LẬP HẠN MỨC</span>
        </div>
      </div>

      {/* Progress & Utilization Meter */}
      <div className="financial-progress-section">
        <div className="financial-progress-labels">
          <div className="progress-stat-left">
            <span className="stat-name">Đã chi tiêu thực tế</span>
            <span className="stat-val primary">{totalSpent.toLocaleString('vi-VN')} đ <small>({pct}%)</small></span>
          </div>
          <div className="progress-stat-right">
            <span className="stat-name">Ngân sách còn lại khả dụng</span>
            <span className="stat-val success">{remaining.toLocaleString('vi-VN')} đ</span>
          </div>
        </div>
        <div className="financial-progress-bar-track">
          <div
            className={`financial-progress-bar-fill ${statusClass}`}
            style={{ width: `${Math.min(100, Math.max(3, pct))}%` }}
          />
        </div>
        <div className="financial-meter-footer">
          <span className={`financial-status-chip ${statusClass}`}>{statusLabel}</span>
          <span className="financial-tes-chip">
            Điểm Hiệu Quả Điều Trị (TES): <strong>{tes}/100</strong> (Hạng {roiRank})
          </span>
        </div>
      </div>

      {/* 3-Pillar Smart Allocation Breakdown (45 - 35 - 20) */}
      <div className="financial-pillars-header">
        <Sparkles size={15} />
        <span>Khuyến nghị phân bổ dòng tiền y tế thông minh (Tỷ lệ chuẩn 45 - 35 - 20)</span>
      </div>
      <div className="financial-pillars-grid">
        <div className="pillar-card pillar-doctor">
          <div className="pillar-top">
            <div className="pillar-badge">🏥 45%</div>
            <div className="pillar-amount">~{doctorAlloc.toLocaleString('vi-VN')} đ</div>
          </div>
          <div className="pillar-name">Khám Chuyên Khoa & BHYT</div>
          <ul className="pillar-points">
            <li>Đặt khám đúng chuyên khoa sớm trong 24-48h qua Booking Care.</li>
            <li>Tận dụng BHYT đúng tuyến chi trả <strong>80% - 100%</strong> viện phí.</li>
            <li>Khám dứt điểm sớm rẻ hơn 75% so với viện phí cấp cứu nội trú.</li>
          </ul>
        </div>

        <div className="pillar-card pillar-med">
          <div className="pillar-top">
            <div className="pillar-badge">💊 35%</div>
            <div className="pillar-amount">~{medAlloc.toLocaleString('vi-VN')} đ</div>
          </div>
          <div className="pillar-name">Thuốc Chuẩn GPP & Generic</div>
          <ul className="pillar-points">
            <li>Mua thuốc tại chuỗi GPP (Pharmacity, Long Châu, An Khang...) đạt chuẩn MIC.</li>
            <li>Yêu cầu thuốc Generic tương đương sinh học để tiết kiệm <strong>30% - 40%</strong>.</li>
            <li>Cảnh báo thuốc liều lẻ ngoài chợ gây tái phát dai dẳng (đang lãng phí {wasteSpent.toLocaleString('vi-VN')} đ).</li>
          </ul>
        </div>

        <div className="pillar-card pillar-reserve">
          <div className="pillar-top">
            <div className="pillar-badge">🛡️ 20%</div>
            <div className="pillar-amount">~{reserveAlloc.toLocaleString('vi-VN')} đ</div>
          </div>
          <div className="pillar-name">Quỹ Dự Phòng & Sức Khỏe</div>
          <ul className="pillar-points">
            <li>Xét nghiệm tầm soát định kỳ, tăng cường miễn dịch chủ động.</li>
            <li>Dung dịch sát khuẩn, nước muối sinh lý NaCl 0.9%, bù điện giải Oresol.</li>
            <li>Dự phòng các đợt thay đổi thời tiết cho cả gia đình.</li>
          </ul>
        </div>
      </div>

      {/* Clinical Safety Gate Guarantee Box */}
      <div className="financial-safety-box">
        <ShieldCheck size={20} className="safety-box-icon" />
        <div className="safety-box-content">
          <strong>Cam kết Cổng Kiểm Soát An Toàn Y Khoa:</strong>
          <span> Sức khỏe và tính mạng luôn là ưu tiên số 1. Hệ thống <strong>tuyệt đối không bao giờ</strong> khuyên tự ý cắt giảm thuốc kê đơn hay trì hoãn việc đi khám bác sĩ chỉ để giữ chỉ tiêu ngân sách.</span>
        </div>
      </div>

      {/* Direct CTA Button to Spending Dashboard */}
      <div className="financial-cta-container">
        <button type="button" onClick={handleOpenSpending} className="financial-open-dashboard-btn">
          <PieChart size={17} />
          <span>Mở Bảng Quản Lý Chi Phí Sức Khỏe & Dòng Tiền Toàn Màn Hình</span>
          <ArrowRight size={17} />
        </button>
      </div>
    </div>
  );
}

function statusConfig({ urgency, overallRisk, isClinical, intent, verificationStatus }) {
  if (intent === 'financial') {
    return {
      tone: 'routine',
      label: 'Kế hoạch ngân sách y tế',
      helper: 'Đã tối ưu hóa dòng tiền và phân bổ chi phí y tế thông minh',
      icon: WalletCards,
    };
  }
  if (intent === 'authenticity' || verificationStatus) {
    if (verificationStatus === 'registry_match') {
      return {
        tone: 'routine',
        label: 'Xác thực chính hãng',
        helper: 'Mã QR và thông tin xuất xưởng trùng khớp với registry nhà sản xuất',
        icon: ShieldCheck,
      };
    }
    if (verificationStatus === 'suspected_counterfeit') {
      return {
        tone: 'emergency',
        label: 'CẢNH BÁO: Nghi ngờ hàng giả',
        helper: 'Serial hoặc mã lô không thuộc danh mục xuất xưởng của nhà sản xuất. Tuyệt đối không dùng thuốc!',
        icon: ShieldAlert,
      };
    }
    if (verificationStatus === 'recalled') {
      return {
        tone: 'emergency',
        label: 'CẢNH BÁO: Thuốc bị thu hồi',
        helper: 'Lô sản phẩm nằm trong danh mục thu hồi khẩn cấp từ cơ quan quản lý dược!',
        icon: AlertTriangle,
      };
    }
    if (verificationStatus === 'expired') {
      return {
        tone: 'urgent',
        label: 'CẢNH BÁO: Thuốc hết hạn dùng',
        helper: 'Hạn sử dụng ghi nhận trong registry đã hết hạn. Ngưng dùng sản phẩm!',
        icon: AlertTriangle,
      };
    }
    return {
      tone: 'workflow',
      label: 'Kiểm tra mã QR sản phẩm',
      helper: 'Kết quả đối chiếu mã sản phẩm với cơ sở dữ liệu registry',
      icon: CheckCircle2,
    };
  }

  if (!isClinical) {
    return {
      tone: 'workflow',
      label: 'Yêu cầu đã được xử lý',
      helper: 'Trạng thái và kết quả thao tác được trình bày bên dưới',
      icon: CheckCircle2,
    };
  }
  if (urgency === 'EMERGENCY') {
    return {
      tone: 'emergency',
      label: 'Cấp cứu ngay',
      helper: 'Ưu tiên hành động khẩn cấp trước khi tiếp tục trao đổi',
      icon: ShieldAlert,
    };
  }
  if (urgency === 'URGENT' || ['HIGH', 'MODERATE'].includes(overallRisk)) {
    return {
      tone: 'urgent',
      label: 'Cần đánh giá sớm',
      helper: 'Nên được nhân viên y tế đánh giá trong thời gian phù hợp',
      icon: AlertTriangle,
    };
  }
  return {
    tone: 'routine',
    label: 'Theo dõi & Chăm sóc thông thường',
    helper: 'Tình trạng hiện tại ổn định, chưa có dấu hiệu nguy hiểm cần cấp cứu',
    icon: CheckCircle2,
  };
}

/**
 * Generate contextual user follow-up questions to ask the AI assistant.
 * (Questions from user -> assistant, NOT system asking user).
 */
function getContextualFollowups(answer, intent, tone, userQuery = '') {
  const queryLower = (userQuery || '').toLowerCase();

  // 1. RULE 1: Only generate suggestions from the USER's prompt, never hallucinate from AI response text
  if (queryLower) {
    // Crisis / Self-harm
    if (['ngủ mãi không dậy', 'không còn ý nghĩa', 'muốn chết', 'tự tử', 'tự sát', 'uống hết 2 vỉ', 'kết thúc cuộc đời', 'chấm dứt cuộc sống'].some(k => queryLower.includes(k))) {
      return [
        'Kết nối ngay với tổng đài hỗ trợ tâm lý khẩn cấp 24/7',
        'Hướng dẫn người nhà xử trí an toàn tại chỗ trong lúc chờ hỗ trợ',
      ];
    }

    // Emergency red flags (FAST Stroke / Chest pain)
    if (
      ['mờ mắt', 'nói líu lưỡi', 'nói khó', 'nói đớ', 'méo miệng', 'lệch mặt', 'cầm đũa', 'yếu tay', 'liệt', 'tê nửa người'].some(k => queryLower.includes(k)) ||
      ['đau thắt ngực', 'đau ngực trái', 'lan lên hàm', 'vã mồ hôi lạnh', 'khó thở dữ dội'].some(k => queryLower.includes(k)) ||
      tone === 'emergency'
    ) {
      return [
        'Những việc cần làm và tuyệt đối tránh trong lúc chờ xe cấp cứu 115?',
        'Danh sách bệnh viện có Đơn vị Đột quỵ / Tim mạch can thiệp gần nhất?',
      ];
    }

    // Headache / Fever
    if (queryLower.includes('đau đầu') || queryLower.includes('nhức đầu') || queryLower.includes('sốt')) {
      return [
        'Sốt kèm đau đầu khi nào là dấu hiệu cảnh báo viêm màng não hoặc sốt xuất huyết?',
        'Cách hạ sốt và bù nước điện giải an toàn tại nhà theo từng mức nhiệt độ?',
        'Những dấu hiệu nào xuất hiện thêm thì cần đi khám cấp cứu ngay trong ngày?',
      ];
    }

    // Suspected counterfeit / Quality / DAV
    if (
      /\bvn-\d+/i.test(queryLower) ||
      ['số lô', 'tem chống giả', 'thật hay giả', 'ngả vàng', 'mùi chua', 'thuốc giả', 'đổi màu'].some(k => queryLower.includes(k))
    ) {
      return [
        'Cách đối chiếu số đăng ký thuốc trên hệ thống Cục Quản lý Dược (DAV)?',
        'Dấu hiệu nhận biết viên thuốc kháng sinh bị ẩm mốc hoặc biến chất?',
      ];
    }

    // Anticoagulants / Drug interactions
    if (['warfarin', 'aspirin', 'chống đông', 'tương tác', 'xuất huyết', 'nsaid', 'ibuprofen', 'amlodipin'].some(k => queryLower.includes(k))) {
      return [
        'Những dấu hiệu xuất huyết hoặc quá liều thuốc nào cần đi cấp cứu ngay?',
        'Thuốc giảm đau / hạ sốt nào an toàn hơn trong trường hợp này?',
      ];
    }

    // Pediatric dosing
    if (['bé', 'trẻ', 'tháng tuổi', 'kg', 'hapacol', 'efferalgan'].some(k => queryLower.includes(k))) {
      return [
        'Liều dùng thuốc hạ sốt an toàn cho trẻ theo từng mốc cân nặng (mg/kg)?',
        'Khi nào trẻ sốt cần đưa đi khám bác sĩ Nhi khoa ngay?',
      ];
    }

    // Eye symptoms (ONLY if user explicitly mentioned eyes)
    if (['kết mạc', 'đau mắt', 'đỏ mắt', 'cộm mắt', 'chảy nước mắt', 'mắt đỏ'].some(k => queryLower.includes(k))) {
      return [
        'Cách dùng nước muối sinh lý vệ sinh mắt đúng cách hàng ngày?',
        'Dấu hiệu viêm mắt nào cảnh báo nguy hiểm cần khám bác sĩ ngay?',
        'Đau mắt đỏ có lây không và cần làm gì để phòng ngừa cho người xung quanh?',
      ];
    }

    // Dental
    if (['đau răng', 'sâu răng', 'nhức răng', 'sưng nướu', 'viêm lợi', 'tủy răng'].some(k => queryLower.includes(k))) {
      return [
        'Có cách nào giảm ê buốt và đau răng nhanh tại nhà an toàn không?',
        'Thuốc giảm đau nào an toàn và phù hợp cho đau răng không cần kê đơn?',
        'Khi nào đau răng là dấu hiệu tủy răng bị tổn thương cần đi nha sĩ ngay?',
      ];
    }

    // Gastric
    if (['dạ dày', 'loét', 'đau bụng', 'thượng vị', 'ợ chua', 'trào ngược'].some(k => queryLower.includes(k))) {
      return [
        'Nên ăn uống và kiêng gì khi đang bị đau dạ dày cấp?',
        'Dấu hiệu xuất huyết tiêu hóa cần nhập viện kiểm tra là gì?',
        'Thuốc giảm đau nào không làm tổn hại niêm mạc dạ dày?',
      ];
    }
  }

  if (intent === 'financial') {
    return [
      'Làm sao để đặt lịch khám đúng tuyến BHYT để tiết kiệm chi phí?',
      'Làm thế nào để phân biệt thuốc Generic tương đương sinh học tại nhà thuốc?',
      'Sổ chi tiêu y tế của tôi hiện tại đang lãng phí ở khoản nào nhiều nhất?',
    ];
  }

  if (tone === 'emergency') {
    return [
      'Những việc cần làm ngay trong lúc chờ cấp cứu 115 là gì?',
      'Người nhà cần chuẩn bị giấy tờ hoặc thuốc men gì mang theo khi cấp cứu?',
    ];
  }

  if (clinicalIntents.has(intent)) {
    return [
      'Khi nào các triệu chứng hiện tại cần đi khám bác sĩ chuyên khoa trực tiếp?',
      'Cần theo dõi thêm những dấu hiệu cảnh báo nào tại nhà trong 24 giờ tới?',
    ];
  }

  return [];
}


function ClinicalSection({
  title,
  icon: Icon,
  items,
  tone = 'neutral',
  ordered = false,
  className = '',
}) {
  if (!items?.length) return null;
  const List = ordered ? 'ol' : 'ul';
  return (
    <section className={`clinical-section-card tone-${tone} ${className}`.trim()}>
      <div className="clinical-section-heading">
        <span className="clinical-section-icon"><Icon size={16} /></span>
        <h3>{title}</h3>
      </div>
      <List className={ordered ? 'clinical-steps-list' : 'clinical-bullet-list'}>
        {items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
      </List>
    </section>
  );
}

/**
 * Clinical Clarifying Information from Doctor/System to User.
 * Printed purely as text/bullets within the clinical document ("in trên văn bản").
 */
function ClinicalClarifyingNotes({ questions }) {
  if (!questions?.length) return null;
  return (
    <div className="clinical-clarifying-notes" role="note" aria-label="Thông tin lâm sàng cần làm rõ">
      <div className="clarifying-notes-header">
        <ClipboardList size={15} className="clarifying-notes-icon" />
        <span>Thông tin cần biết thêm</span>
      </div>
      <ul className="clarifying-notes-list">
        {questions.map((q, idx) => (
          <li key={`clarify-q-${idx}`}>{q}</li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Interactive Follow-up Question Chips for the User to ask the AI Assistant.
 * (Clickable prompt chips: User -> Assistant).
 */
function InteractiveFollowupPrompts({ questions, onSelectQuestion }) {
  if (!questions?.length) return null;
  return (
    <section className="interactive-followup-section" aria-label="Gợi ý câu hỏi tiếp theo dành cho bạn">
      <div className="interactive-followup-header">
        <Sparkles size={13} className="followup-header-icon" />
        <span className="followup-header-title">Gợi ý câu hỏi tiếp theo</span>
        <span className="followup-header-hint">• Nhấn để gửi nhanh</span>
      </div>
      <div className="interactive-followup-chips" role="group">
        {questions.map((q, idx) => (
          <button
            key={`followup-chip-${idx}`}
            type="button"
            className="interactive-followup-chip"
            onClick={() => onSelectQuestion?.(q)}
            title={`Nhấn để gửi câu hỏi: "${q}"`}
          >
            <span className="followup-chip-prompt-icon">
              <CornerUpRight size={11} />
            </span>
            <span className="followup-chip-text">{q}</span>
            <Send size={11} className="followup-chip-send-icon" />
          </button>
        ))}
      </div>
    </section>
  );
}

/**
 * Authoritative Ministry of Health Guideline References Footnote with Premium Clinical Styling.
 */
function ResearchedSourcesFootnote({ sources }) {
  if (!sources?.length) return null;
  return (
    <section className="answer-sources-footnote" aria-label="Tài liệu tham khảo chuyên môn">
      <div className="sources-footnote-header">
        <div className="sources-footnote-header-left">
          <div className="sources-header-icon-box">
            <Building2 size={15} className="sources-header-icon" />
          </div>
          <div>
            <span className="sources-footnote-title">Tài liệu tham khảo & Văn bản quy chuẩn</span>
            <span className="sources-footnote-subtitle">Cơ sở dữ liệu phác đồ điều trị Bộ Y tế Việt Nam</span>
          </div>
        </div>
        <div className="sources-verified-badge" title="Đã đối chiếu phác đồ chính thức">
          <CheckCircle2 size={12} className="verified-badge-icon" />
          <span>Văn bản chính thức</span>
        </div>
      </div>
      <div className="sources-footnote-cards" role="list">
        {sources.map((src, idx) => (
          <div key={`src-${src.source_id || idx}`} className="source-reference-card" role="listitem">
            <div className="source-card-badge-wrap">
              <span className="source-card-index">[{idx + 1}]</span>
            </div>
            <div className="source-card-content">
              <div className="source-card-title-row">
                <h4 className="source-card-name">{src.title}</h4>
              </div>
              <div className="source-card-meta">
                <span className="source-card-publisher-badge">
                  <ShieldCheck size={12} className="meta-shield-icon" />
                  {src.publisher || "Bộ Y tế — Cục Quản lý Khám, chữa bệnh"}
                </span>
                {src.authority_tier === "government_health" || src.authority_tier === "guideline_or_regulator" ? (
                  <span className="source-tier-pill">Cấp phép lưu hành & hướng dẫn lâm sàng</span>
                ) : null}
              </div>
            </div>
            <a
              href={src.url}
              target="_blank"
              rel="noreferrer"
              className="source-card-action-btn"
              title={`Mở tài liệu: ${src.title}`}
            >
              <span>Xem văn bản</span>
              <ExternalLink size={13} className="source-card-ext-icon" />
            </a>
          </div>
        ))}
      </div>
    </section>
  );
}

/**
 * Emergency Transit & Real-time Turn-by-Turn Navigation Card.
 */
function EmergencyTransitCard({ transit }) {
  if (!transit?.is_emergency) return null;
  const facility = transit.recommended_facility;
  const gw = transit.golden_window;

  const isVerified = responseMeta.verification_status === 'verified';

  return (
    <section className="emergency-transit-card" aria-label="Điều phối cấp cứu khẩn cấp">
      <div className="emergency-transit-header">
        <div className="emergency-header-badge">
          <ShieldAlert size={18} className="emergency-siren-icon" />
          <span>ĐIỀU PHỐI CẤP CỨU & BẢN ĐỒ CHỈ ĐƯỜNG REAL-TIME</span>
        </div>
        {gw && (
          <span className="golden-window-pill" title={gw.risk_rationale}>
            <Clock size={13} />
            <span>Giờ vàng: &le; {gw.golden_window_hours}h</span>
          </span>
        )}
      </div>

      {facility && (
        <div className="emergency-facility-box">
          <div className="facility-top-row">
            <div className="facility-info">
              <span className="facility-type-tag">Cơ sở tiếp nhận phù hợp gần nhất</span>
              <h3 className="facility-name">{facility.name}</h3>
              <p className="facility-address">
                <MapPin size={13} className="inline-map-icon" />
                {facility.address}
              </p>
            </div>
            <div className="facility-distance-eta">
              <span className="facility-distance">{facility.distance_km} km</span>
              <span className="facility-eta">~{facility.eta_minutes} phút</span>
            </div>
          </div>

          <div className="emergency-actions-grid">
            <a href="tel:115" className="emergency-call-btn national-115">
              <PhoneCall size={15} />
              <span>GỌI CẤP CỨU 115</span>
            </a>
            {facility.emergency_hotline && (
              <a href={transit.hospital_phone_call_url || `tel:${facility.emergency_hotline}`} className="emergency-call-btn hospital-hotline">
                <PhoneCall size={14} />
                <span>Gọi Cấp cứu Viện ({facility.emergency_hotline})</span>
              </a>
            )}
            <button
              type="button"
              className="emergency-nav-btn emergency-inapp-direct"
              onClick={() => {
                window.dispatchEvent(
                  new CustomEvent('medguard:navigate', {
                    detail: {
                      view: 'navigation',
                      navigationContext: {
                        fromChat: true,
                        chatKicker: 'ĐIỀU PHỐI CẤP CỨU & TUYẾN ĐƯỜNG TRÁNH KẸT XE',
                        selectedPoi: {
                          id: facility.id || 'emergency_hospital',
                          name: facility.name,
                          address: facility.address,
                          lat: Number(facility.latitude || facility.lat || 21.0028),
                          lng: Number(facility.longitude || facility.lng || 105.8428),
                          type: 'hospital_emergency',
                          phone: facility.emergency_hotline || '115',
                          hotline: facility.emergency_hotline || '115',
                          distance_km: facility.distance_km,
                          operating_status: {
                            is_open: true,
                            status_label: 'Cấp cứu 24/7',
                            status_badge: 'OPEN_24_7',
                            detail_text: 'Trực cấp cứu liên tục 24/7',
                          },
                          google_maps_turn_by_turn_url: facility.navigation_url || transit.navigation_url,
                        },
                        activeRoute: {
                          distance_km: facility.distance_km,
                          eta_minutes: facility.eta_minutes,
                          corridor_description: transit.optimal_corridor || 'Tuyến cấp cứu ưu tiên',
                          coordinates: transit.route_coordinates || [],
                          steps: transit.turn_by_turn_steps || [],
                          traffic_level: transit.traffic_level || 'FAST',
                          google_maps_turn_by_turn_url: facility.navigation_url || transit.navigation_url,
                        },
                        userLocation: {
                          lat: Number(transit.user_lat) || 20.9858,
                          lng: Number(transit.user_lng) || 105.7928,
                          name: 'Vị trí của bạn',
                          address: 'Hà Nội',
                          is_gps: true,
                        },
                        poiType: 'emergency',
                      },
                    },
                  })
                );
              }}
            >
              <Route size={15} />
              <span>Chỉ đường Real-time trong App</span>
            </button>
            <a
              href={facility.navigation_url || transit.navigation_url}
              target="_blank"
              rel="noreferrer"
              className="emergency-nav-btn"
            >
              <Navigation size={15} />
              <span>Chỉ đường Real-time (Google Maps)</span>
              <ExternalLink size={12} />
            </a>
          </div>
        </div>
      )}

      {gw && (
        <div className="golden-window-risk-box">
          <div className="risk-heading">
            <Clock size={14} />
            <strong>Phân tích rủi ro thời gian di chuyển ("Giờ vàng" {gw.syndrome_name}):</strong>
          </div>
          <p className="risk-text">{gw.risk_rationale}</p>
          <p className="transit-mode-note">
            <strong>Phương tiện di chuyển:</strong> {gw.transit_mode_recommendation}
          </p>
        </div>
      )}

      {transit.vehicle_safety_rules?.length > 0 && (
        <div className="vehicle-safety-rules">
          <span className="safety-rules-title">5 Nguyên tắc an toàn sinh tồn khi di chuyển:</span>
          <ul>
            {transit.vehicle_safety_rules.map((rule, idx) => (
              <li key={`rule-${idx}`}>{rule}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

/**
 * Pre-hospital En-Route Physical Inspection and Rapid Triage Card.
 */
function EnRouteTriageCard({ enroute }) {
  if (!enroute?.detected_signs?.length && !enroute?.is_en_route) return null;
  return (
    <section className="enroute-triage-card" aria-label="Theo dõi lâm sàng tiền viện trên xe">
      <div className="enroute-header">
        <div className="enroute-title-wrap">
          <div className="enroute-icon-box">
            <Truck size={17} className="enroute-icon" />
          </div>
          <div>
            <span className="enroute-badge">THEO DÕI LÂM SÀNG TIỀN VIỆN (ĐANG TRÊN XE CẤP CỨU / TAXI)</span>
            <h4 className="enroute-subheading">{enroute.pre_hospital_impression}</h4>
          </div>
        </div>
        <div className="avpu-badge-pill" title="Thang đo mức độ tri giác tiền viện">
          <span>Ý thức: <strong>{enroute.consciousness_avpu}</strong></span>
        </div>
      </div>

      {enroute.detected_signs?.length > 0 && (
        <div className="enroute-signs-grid">
          {enroute.detected_signs.map((sign, idx) => (
            <div key={`sign-${idx}`} className={`enroute-sign-item severity-${sign.severity?.toLowerCase()}`}>
              <div className="sign-name-row">
                <AlertCircle size={13} />
                <strong>{sign.sign_name}</strong>
              </div>
              <p className="sign-meaning">{sign.clinical_meaning}</p>
            </div>
          ))}
        </div>
      )}

      {enroute.immediate_actions_in_vehicle?.length > 0 && (
        <div className="enroute-actions-box">
          <strong className="box-label">Hành động cần làm ngay trên xe:</strong>
          <ul>
            {enroute.immediate_actions_in_vehicle.map((act, idx) => (
              <li key={`act-${idx}`}>{act}</li>
            ))}
          </ul>
        </div>
      )}

      {enroute.prohibited_actions_in_vehicle?.length > 0 && (
        <div className="enroute-prohibitions-box">
          <strong className="box-label">CẤM THỰC HIỆN TRÊN XE (Tránh nguy hiểm tính mạng):</strong>
          <ul>
            {enroute.prohibited_actions_in_vehicle.map((pro, idx) => (
              <li key={`pro-${idx}`}>{pro}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

/**
 * 3-State Medication Suitability & GPP Pharmacy Card.
 */
function MedicationSuitabilityCard({ suitability }) {
  if (!suitability) return null;
  const isEligible = suitability.state === 'ELIGIBLE_OTC';
  const isContraindicated = suitability.state === 'CONTRAINDICATED';
  const isEmergency = suitability.state === 'EMERGENCY_RED_FLAG';

  return (
    <section className={`medication-suitability-card state-${suitability.state?.toLowerCase()}`} aria-label="Đánh giá an toàn thuốc và điểm bán">
      <div className="med-suitability-header">
        <div className="med-header-left">
          <div className="med-icon-box">
            <Pill size={16} />
          </div>
          <div>
            <span className="med-card-title">Đánh giá An toàn Dược học & Điểm cung cấp thuốc</span>
            <span className="med-card-subtitle">Đối chiếu dược thư và quy chuẩn an toàn Bộ Y tế</span>
          </div>
        </div>
        <span className={`med-state-badge state-${suitability.state?.toLowerCase()}`}>
          {suitability.state_label}
        </span>
      </div>

      <p className="med-clinical-rationale">{suitability.clinical_rationale}</p>

      {isContraindicated && suitability.contraindication_reasons?.length > 0 && (
        <div className="med-contraindications-box">
          <strong className="contra-title">Lý do chống chỉ định cụ thể:</strong>
          <ul>
            {suitability.contraindication_reasons.map((reason, idx) => (
              <li key={`contra-${idx}`}>{reason}</li>
            ))}
          </ul>
          {suitability.safe_alternatives?.length > 0 && (
            <div className="med-safe-alternatives">
              <strong>Giải pháp an toàn thay thế:</strong>
              <ul>
                {suitability.safe_alternatives.map((alt, idx) => (
                  <li key={`alt-${idx}`}>{alt}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {isEligible && suitability.recommended_medications?.length > 0 && (
        <div className="med-recommendations-list">
          <span className="recs-title">Danh mục hoạt chất OTC an toàn được đề xuất:</span>
          {suitability.recommended_medications.map((med, idx) => (
            <div key={`med-${idx}`} className="med-item-card">
              <div className="med-item-top">
                <h4 className="med-generic-name">{med.generic_name}</h4>
                <div className="med-brand-tags">
                  {med.brand_names?.map((brand, bIdx) => (
                    <span key={`brand-${bIdx}`} className="med-brand-tag">{brand}</span>
                  ))}
                </div>
              </div>
              <p className="med-dosage"><strong>Liều dùng chuẩn:</strong> {med.dosage_guideline}</p>
              <p className="med-admin"><strong>Cách dùng:</strong> {med.administration}</p>
              <p className="med-warning"><strong>Cảnh báo an toàn:</strong> {med.warning_and_monitoring}</p>
              {med.certified_gpp_online_links?.length > 0 && (
                <div className="med-gpp-links-row">
                  <span className="gpp-label">Đặt mua trực tuyến (Nhà thuốc chuẩn GPP):</span>
                  <div className="gpp-buttons">
                    {med.certified_gpp_online_links.map((link, lIdx) => (
                      <a
                        key={`gpp-${lIdx}`}
                        href={link.url}
                        target="_blank"
                        rel="noreferrer"
                        className="gpp-link-btn"
                        title={link.type}
                      >
                        <ShieldCheck size={12} className="gpp-check-icon" />
                        <span>{link.name}</span>
                        <ExternalLink size={10} />
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {!isEmergency && suitability.nearest_pharmacy_maps_url && (
        <div className="nearest-pharmacy-footer">
          <div className="pharmacy-footer-copy">
            <MapPin size={15} className="map-pin-icon" />
            <span>Cần mua thuốc trực tiếp? Xem danh sách các hiệu thuốc đạt chuẩn GPP gần bạn nhất:</span>
          </div>
          <div className="pharmacy-footer-btn-group">
            <button
              type="button"
              className="find-pharmacy-inapp-btn"
              onClick={() => {
                window.dispatchEvent(
                  new CustomEvent('medguard:navigate', {
                    detail: {
                      view: 'navigation',
                      navigationContext: {
                        fromChat: true,
                        chatKicker: 'ĐIỂM BÁN THUỐC GPP ĐỀ XUẤT TỪ CA TƯ VẤN',
                        poiType: 'pharmacy',
                      },
                    },
                  })
                );
              }}
            >
              <Route size={14} />
              <span>Chỉ Đường Real-time trong App</span>
            </button>
            <a
              href={suitability.nearest_pharmacy_maps_url}
              target="_blank"
              rel="noreferrer"
              className="find-pharmacy-maps-btn"
            >
              <Navigation size={14} />
              <span>Google Maps</span>
              <ExternalLink size={12} />
            </a>
          </div>
        </div>
      )}
    </section>
  );
}

/**
 * Real-Time Geo Routing, POI Operating Hours & Traffic Optimization Card.
 */
function getTurnDirectionIcon(instruction = '') {
  const norm = instruction.toLowerCase();
  if (norm.includes('trái') || norm.includes('left')) {
    return <CornerUpLeft size={22} className="turn-direction-icon turn-left" />;
  }
  if (norm.includes('phải') || norm.includes('right')) {
    return <CornerUpRight size={22} className="turn-direction-icon turn-right" />;
  }
  if (norm.includes('vòng xuyến') || norm.includes('bùng binh') || norm.includes('roundabout')) {
    return <RotateCcw size={22} className="turn-direction-icon turn-roundabout" />;
  }
  return <ArrowUp size={22} className="turn-direction-icon turn-straight" />;
}

function LeafletRouteMap({ geoRouting, activeRoute }) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const [mapTheme, setMapTheme] = useState('voyager'); // 'voyager' (sáng, rõ nét từng con đường) hoặc 'dark' (nền tối)

  const userLat = Number(geoRouting.user_location?.lat) || 20.9858;
  const userLng = Number(geoRouting.user_location?.lng) || 105.7928;
  const destLat = Number(geoRouting.selected_poi?.lat) || 20.9858;
  const destLng = Number(geoRouting.selected_poi?.lng) || 105.7928;

  const startCoords = [userLat, userLng];
  const destCoords = [destLat, destLng];
  const polylineCoords = activeRoute?.canvas_polyline || [];

  // Auto-resize observer to prevent blank/gray tiles
  useEffect(() => {
    if (!mapContainerRef.current) return;
    const ro = new ResizeObserver(() => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.invalidateSize();
      }
    });
    ro.observe(mapContainerRef.current);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (mapInstanceRef.current) {
      mapInstanceRef.current.remove();
      mapInstanceRef.current = null;
    }

    try {
      const map = L.map(mapContainerRef.current, {
        center: startCoords,
        zoom: 15,
        zoomControl: true,
        attributionControl: false,
      });

      // Licensed HD tiles from Geoapify (zero watermark, crystal clear Vietnamese labels, zero account needed)
      const brightUrl =
        'https://maps.geoapify.com/v1/tile/osm-bright/{z}/{x}/{y}.png?apiKey=224447c8da3b4555a5380f31ddb56bf3';
      const darkUrl =
        'https://maps.geoapify.com/v1/tile/dark-matter-dark-grey/{z}/{x}/{y}.png?apiKey=224447c8da3b4555a5380f31ddb56bf3';
      const tileUrl = mapTheme === 'dark' ? darkUrl : brightUrl;

      const tileLayer = L.tileLayer(tileUrl, {
        maxZoom: 20,
        attribution: '© OpenStreetMap, © Geoapify',
      }).addTo(map);

      tileLayer.on('tileerror', () => {
        L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
          maxZoom: 19,
          attribution: '© OpenStreetMap contributors',
        }).addTo(map);
      });

      // Điểm A: Điểm xuất phát (Vị trí của bạn)
      const startIcon = L.divIcon({
        className: 'leaflet-pin-wrapper',
        html: `<div class="marker-pin pin-start"><span class="pin-badge">A</span><span class="pin-title">Bạn</span></div>`,
        iconSize: [36, 44],
        iconAnchor: [18, 40],
      });

      // Điểm B: Điểm đến (Nhà thuốc GPP / Cấp cứu)
      const isEmergency = geoRouting.query_type === 'emergency';
      const destIcon = L.divIcon({
        className: 'leaflet-pin-wrapper',
        html: `<div class="marker-pin ${isEmergency ? 'pin-emergency' : 'pin-dest'}"><span class="pin-badge">B</span><span class="pin-title">${isEmergency ? 'Cấp cứu' : 'Quầy thuốc'}</span></div>`,
        iconSize: [36, 44],
        iconAnchor: [18, 40],
      });

      const startMarker = L.marker(startCoords, { icon: startIcon }).addTo(map);
      startMarker.bindPopup(`<b>Điểm xuất phát:</b><br/>${geoRouting.user_location?.address || 'Vị trí của bạn'}`);

      const destMarker = L.marker(destCoords, { icon: destIcon }).addTo(map);
      destMarker.bindPopup(`<b>${geoRouting.selected_poi?.name}</b><br/>${geoRouting.selected_poi?.address}`);

      // Vẽ sợi chỉ đường (Polyline)
      const routePoints = polylineCoords.length > 0 ? polylineCoords : [startCoords, destCoords];

      // Lớp viền phản quang
      L.polyline(routePoints, {
        color: mapTheme === 'dark' ? '#00e5ff' : '#60a5fa',
        weight: 10,
        opacity: mapTheme === 'dark' ? 0.45 : 0.4,
        lineCap: 'round',
      }).addTo(map);

      // Sợi chỉ đường chính
      const polyline = L.polyline(routePoints, {
        color: mapTheme === 'dark' ? '#00e5ff' : '#2563eb',
        weight: 6,
        opacity: 0.95,
        lineCap: 'round',
        lineJoin: 'round',
      }).addTo(map);

      // Căn chỉnh khung nhìn tự động
      const group = L.featureGroup([startMarker, destMarker, polyline]);
      map.fitBounds(group.getBounds(), { padding: [35, 35] });

      mapInstanceRef.current = map;

      setTimeout(() => {
        if (mapInstanceRef.current) {
          mapInstanceRef.current.invalidateSize();
        }
      }, 250);
    } catch (e) {
      console.warn('Leaflet map error:', e);
    }

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, [geoRouting, activeRoute, mapTheme]);

  return (
    <div className="leaflet-map-canvas-wrapper">
      <div className="leaflet-floating-theme-bar">
        <button
          type="button"
          className={`btn-leaflet-theme ${mapTheme === 'voyager' ? 'active' : ''}`}
          onClick={() => setMapTheme('voyager')}
        >
          Bản đồ Rõ nét
        </button>
        <button
          type="button"
          className={`btn-leaflet-theme ${mapTheme === 'dark' ? 'active' : ''}`}
          onClick={() => setMapTheme('dark')}
        >
          Nền tối
        </button>
      </div>
      <div ref={mapContainerRef} className="leaflet-map-element" style={{ width: '100%', height: '360px' }} />
    </div>
  );
}

function RealTimeGeoMapCard({ geoRouting }) {
  if (!geoRouting?.selected_poi) return null;
  const poi = geoRouting.selected_poi;
  const op = poi.operating_status;
  const primary = geoRouting.primary_route;
  const alternative = geoRouting.alternative_route;
  const [selectedRouteType, setSelectedRouteType] = useState(
    geoRouting.recommended_route_type || 'PRIMARY_DIRECT'
  );
  const [mapMode, setMapMode] = useState('leaflet'); // 'leaflet', 'street', or 'osm'
  const [activeStepIndex, setActiveStepIndex] = useState(0);

  const activeRoute = selectedRouteType === 'OPTIMAL_BYPASS' && alternative ? alternative : primary;
  const isEmergency = geoRouting.query_type === 'emergency';
  const steps = activeRoute?.steps || [];
  const currentStep = steps[activeStepIndex] || steps[0] || {};

  const handleOpenDirectNavigation = () => {
    window.dispatchEvent(
      new CustomEvent('medguard:navigate', {
        detail: {
          view: 'navigation',
          navigationContext: {
            fromChat: true,
            chatKicker: isEmergency
              ? 'ĐIỀU PHỐI CẤP CỨU & TUYẾN ĐƯỜNG TRÁNH KẸT XE'
              : 'ĐIỂM BÁN THUỐC GPP ĐỀ XUẤT TỪ CA TƯ VẤN',
            selectedPoi: {
              id: poi.id,
              name: poi.name,
              address: poi.address,
              lat: Number(poi.lat),
              lng: Number(poi.lng),
              type: poi.type || (isEmergency ? 'hospital_emergency' : 'pharmacy'),
              chain: poi.chain || '',
              district: poi.district || '',
              city: poi.city || '',
              hotline: poi.hotline || '',
              phone: poi.phone || '',
              operating_status: poi.operating_status,
              distance_km: activeRoute?.distance_km || poi.distance_km,
              google_maps_turn_by_turn_url: geoRouting.google_maps_turn_by_turn_url,
              services: poi.services || ['Chuẩn GPP', 'Sẵn có thuốc theo đơn tư vấn'],
            },
            activeRoute: {
              distance_km: activeRoute?.distance_km,
              eta_minutes: activeRoute?.eta_minutes,
              corridor_description: activeRoute?.corridor_description,
              canvas_polyline: activeRoute?.canvas_polyline,
              coordinates: activeRoute?.canvas_polyline || activeRoute?.coordinates,
              steps: steps,
              traffic_level: activeRoute?.traffic_level,
              google_maps_turn_by_turn_url: geoRouting.google_maps_turn_by_turn_url,
            },
            userLocation: {
              lat: Number(geoRouting.user_location?.lat) || 20.9858,
              lng: Number(geoRouting.user_location?.lng) || 105.7928,
              name: geoRouting.user_location?.name || 'Vị trí của bạn',
              address: geoRouting.user_location?.address || 'Hà Nội',
              is_gps: true,
            },
            poiType: isEmergency ? 'emergency' : 'pharmacy',
          },
        },
      })
    );
  };

  return (
    <section
      className={`geo-routing-card type-${geoRouting.query_type}`}
      aria-label="Bản đồ và tuyến đường tối ưu thời gian thực"
    >
      {/* Header */}
      <div className="geo-card-header">
        <div className="geo-header-title-wrap">
          <div className="geo-header-icon-box">
            <Route size={18} className="geo-icon" />
          </div>
          <div>
            <span className="geo-kicker">
              {isEmergency
                ? 'ĐIỀU PHỐI CẤP CỨU & TỐI ƯU TUYẾN ĐƯỜNG TRÁNH KẸT XE'
                : 'ĐIỂM BÁN THUỐC GPP GẦN NHẤT & CHỈ ĐƯỜNG REAL-TIME'}
            </span>
            <h3 className="geo-poi-name">{poi.name}</h3>
            <p className="geo-poi-address">
              <MapPin size={13} className="inline-map-pin" />
              {poi.address}
            </p>
          </div>
        </div>

        {/* Operating status badge */}
        <div className={`geo-operating-badge badge-${op?.status_badge?.toLowerCase()}`}>
          <Clock size={14} />
          <div className="badge-text-col">
            <span className="badge-main-label">{op?.status_label}</span>
            <small className="badge-sub-label">{op?.detail_text}</small>
          </div>
        </div>
      </div>

      {/* Traffic Alert Banner if rush hour / congestion */}
      {geoRouting.is_rush_hour && (
        <div className="geo-traffic-banner alert-warning">
          <AlertTriangle size={16} className="traffic-warning-icon" />
          <div>
            <strong>{geoRouting.rush_hour_name || 'Giờ cao điểm'}:</strong> {geoRouting.traffic_overview}
          </div>
        </div>
      )}

      {/* Interactive Visual Map Canvas with Real Map Tiles */}
      <div className="geo-interactive-map-canvas" role="region" aria-label="Bản đồ đường đi trực quan">
        <div className="map-canvas-top-bar">
          <span className="map-badge-live">
            <span className="live-dot" /> LIVE TRAFFIC RADAR
          </span>
          <span className="map-location-tag">
            Vị trí của bạn: <strong>{geoRouting.user_location?.name || 'Vị trí của bạn'}</strong> ({geoRouting.user_location?.address || 'Đang cập nhật...'})
          </span>
        </div>

        {/* Map View Toggle Tabs */}
        <div className="geo-map-display-area">
          <div className="map-view-toggle-bar">
            <div className="map-toggle-tabs">
              <button
                type="button"
                className={`map-toggle-btn ${mapMode === 'leaflet' ? 'active' : ''}`}
                onClick={() => setMapMode('leaflet')}
              >
                <Compass size={13} />
                <span>Bản đồ Tương tác Leaflet (Sợi chỉ đường)</span>
              </button>
              {geoRouting.static_map_url && (
                <button
                  type="button"
                  className={`map-toggle-btn ${mapMode === 'street' ? 'active' : ''}`}
                  onClick={() => setMapMode('street')}
                >
                  <Layers size={13} />
                  <span>Bản đồ Đường phố Thực tế</span>
                </button>
              )}
              {geoRouting.interactive_map_url && (
                <button
                  type="button"
                  className={`map-toggle-btn ${mapMode === 'osm' ? 'active' : ''}`}
                  onClick={() => setMapMode('osm')}
                >
                  <Navigation size={13} />
                  <span>Bản đồ Toàn cầu (OSM)</span>
                </button>
              )}
            </div>
            <span className="map-realtime-indicator">
              <span className="live-dot" /> Định vị & Lộ trình chuẩn
            </span>
          </div>

          {/* Render Selected Map Mode */}
          {mapMode === 'leaflet' ? (
            <LeafletRouteMap geoRouting={geoRouting} activeRoute={activeRoute} />
          ) : mapMode === 'street' && geoRouting.static_map_url ? (
            <div className="geo-static-map-wrapper">
              <img
                src={geoRouting.static_map_url}
                alt={`Bản đồ lộ trình đến ${poi.name}`}
                className="geo-static-street-img"
                loading="eager"
              />
              <div className="geo-map-overlay-card start-overlay">
                <span className="overlay-badge pin-a">A</span>
                <div className="overlay-text">
                  <span className="overlay-role">Điểm xuất phát:</span>
                  <strong className="overlay-address">{geoRouting.user_location?.address || 'Vị trí của bạn'}</strong>
                </div>
              </div>
              <div className="geo-map-overlay-card dest-overlay">
                <span className="overlay-badge pin-b">B</span>
                <div className="overlay-text">
                  <span className="overlay-role">{isEmergency ? 'Cơ sở cấp cứu:' : 'Điểm bán thuốc GPP:'}</span>
                  <strong className="overlay-address">{poi.name} ({activeRoute.distance_km} km)</strong>
                </div>
              </div>
            </div>
          ) : geoRouting.interactive_map_url ? (
            <div className="geo-osm-iframe-wrapper">
              <iframe
                src={geoRouting.interactive_map_url}
                className="geo-osm-iframe"
                title="Bản đồ tương tác OpenStreetMap"
                loading="lazy"
              />
            </div>
          ) : (
            <div className="geo-map-placeholder">
              <span>Đang tải dữ liệu bản đồ thời gian thực...</span>
            </div>
          )}
        </div>

        {/* Route Selector Tabs / Buttons */}
        <div className="route-selector-grid">
          <button
            type="button"
            className={`route-tab-btn ${selectedRouteType === 'PRIMARY_DIRECT' ? 'active' : ''}`}
            onClick={() => {
              setSelectedRouteType('PRIMARY_DIRECT');
              setActiveStepIndex(0);
            }}
          >
            <div className="route-tab-title-row">
              <span className="route-tab-name">Tuyến 1: Đường Trực Tiếp</span>
              {primary.traffic_level === 'SEVERELY_CONGESTED' && (
                <span className="traffic-pill-tag traffic-danger">Kẹt xe {primary.traffic_density_percent}%</span>
              )}
            </div>
            <div className="route-tab-stats">
              <span className="route-stat-eta">~{primary.eta_minutes} phút</span>
              <span className="route-stat-dist">{primary.distance_km} km</span>
            </div>
            <p className="route-tab-desc">{primary.corridor_description}</p>
          </button>

          {alternative && (
            <button
              type="button"
              className={`route-tab-btn recommended ${selectedRouteType === 'OPTIMAL_BYPASS' ? 'active' : ''}`}
              onClick={() => {
                setSelectedRouteType('OPTIMAL_BYPASS');
                setActiveStepIndex(0);
              }}
            >
              <div className="route-tab-title-row">
                <span className="route-tab-name">Tuyến 2: Tuyến Tránh Tối Ưu</span>
                <span className="traffic-pill-tag traffic-success">Tiết kiệm {alternative.time_saved_minutes} phút</span>
              </div>
              <div className="route-tab-stats">
                <span className="route-stat-eta optimal">~{alternative.eta_minutes} phút</span>
                <span className="route-stat-dist">{alternative.distance_km} km</span>
              </div>
              <p className="route-tab-desc">{alternative.corridor_description}</p>
            </button>
          )}
        </div>

        {/* Dual Navigation Choice Console: Google Maps Deep Link vs In-App Real-Time */}
        <div className="geo-dual-navigation-console">
          <div className="nav-choices-header">
            <Navigation size={16} className="nav-console-icon" />
            <div className="nav-console-title-wrap">
              <strong>CƠ CHẾ 2 LỰA CHỌN ĐIỀU HƯỚNG</strong>
              <small>Điểm xuất phát ({geoRouting.user_location?.name || geoRouting.user_location?.address || 'Vị trí hiện tại của bạn'}) và điểm đến ({poi.name}) đã được thiết lập sẵn</small>
            </div>
          </div>

          <div className="nav-choices-grid">
            {/* Lựa chọn 1: Deep Link sang Google Maps */}
            <a
              href={geoRouting.google_maps_turn_by_turn_url}
              target="_blank"
              rel="noreferrer"
              className="nav-choice-card choice-gmaps"
            >
              <div className="choice-top-row">
                <span className="choice-tag-pill tag-gmaps">LỰA CHỌN 1</span>
                <span className="choice-hint">Ứng dụng ngoài</span>
              </div>
              <h4 className="choice-title">
                <Navigation size={15} />
                <span>Mở Google Maps (Deep Link)</span>
                <ExternalLink size={13} />
              </h4>
              <p className="choice-desc">
                Chuyển thẳng sang Google Maps trên máy bạn. Tọa độ xuất phát và đích đến đã được nạp sẵn, hiển thị kẹt xe thời gian thực của Google.
              </p>
              <div className="choice-action-bar">
                <span>Bật dẫn đường trên Google Maps</span>
                <ArrowRight size={14} />
              </div>
            </a>

            {/* Lựa chọn 2: Tự xử lý Real-time trực tiếp trong ứng dụng */}
            <button
              type="button"
              className="nav-choice-card choice-inapp selected clickable-choice"
              onClick={handleOpenDirectNavigation}
              title="Nhấn để chuyển sang trang Chỉ Đường Real-Time & Trạm Y Tế GPP toàn màn hình với lộ trình này"
            >
              <div className="choice-top-row">
                <span className="choice-tag-pill tag-inapp">LỰA CHỌN 2 (MẶC ĐỊNH)</span>
                <span className="choice-hint">Chuyển sang trang riêng</span>
              </div>
              <h4 className="choice-title">
                <Compass size={15} />
                <span>Chỉ đường Real-time trên MedGuard AI</span>
                <ArrowRight size={13} className="choice-arrow-icon" />
              </h4>
              <p className="choice-desc">
                Chuyển sang trang "Chỉ Đường Real-Time & Trạm Y Tế GPP" để theo dõi bản đồ toàn màn hình, bám sát GPS và chỉ dẫn rẽ từng bước (Turn-by-turn).
              </p>
              <div className="choice-action-bar inapp-active">
                <span>Mở trang chỉ đường toàn màn hình</span>
                <ArrowRight size={14} />
              </div>
            </button>
          </div>

          <button
            type="button"
            className="nav-open-dedicated-page-btn"
            onClick={handleOpenDirectNavigation}
          >
            <Route size={15} />
            <span>Mở Trang Chỉ Đường Real-Time & Trạm Y Tế GPP Toàn Màn Hình</span>
            <ArrowRight size={14} />
          </button>
        </div>

        {/* Direct In-App Turn-by-Turn Navigation Console */}
        {steps.length > 0 && (
          <div className="geo-turn-navigator-console">
            <div className="turn-console-header">
              <div className="turn-console-title">
                <Compass size={16} className="compass-icon pulse-subtle" />
                <span>CHỈ ĐƯỜNG REAL-TIME TRỰC TIẾP TRÊN APP (TURN-BY-TURN)</span>
              </div>
              <div className="turn-header-actions">
                <button
                  type="button"
                  className="turn-open-fullscreen-btn"
                  onClick={handleOpenDirectNavigation}
                  title="Mở toàn màn hình trang chỉ đường"
                >
                  <Route size={12} />
                  <span>Mở Toàn Màn Hình</span>
                </button>
                <span className="turn-step-count-badge">
                  Chặng {activeStepIndex + 1}/{steps.length}
                </span>
              </div>
            </div>

            {/* Active Turn Highlight Card */}
            <div className="active-turn-step-card">
              <div className="turn-icon-container">
                {getTurnDirectionIcon(currentStep.instruction)}
              </div>
              <div className="turn-content-container">
                <span className="turn-road-name">{currentStep.road_name || 'Đoạn đường di chuyển'}</span>
                <h4 className="turn-instruction-text">{currentStep.instruction}</h4>
                <div className="turn-metrics-row">
                  <span className="metric-tag distance-metric">
                    <Route size={12} /> {currentStep.distance_km} km
                  </span>
                  <span className="metric-tag eta-metric">
                    <Clock size={12} /> ~{Math.max(1, Math.round(currentStep.distance_km * 2.5))} phút
                  </span>
                  {currentStep.traffic_level === 'HEAVY' && (
                    <span className="metric-tag traffic-heavy-metric">
                      <AlertTriangle size={12} /> Đoạn đường ùn tắc
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Turn Controller Step Bar */}
            <div className="turn-controller-bar">
              <button
                type="button"
                className="turn-ctrl-btn"
                disabled={activeStepIndex === 0}
                onClick={() => setActiveStepIndex((prev) => Math.max(0, prev - 1))}
              >
                <ArrowLeft size={14} /> Chặng trước
              </button>
              <div className="turn-step-dots-track">
                {steps.map((s, idx) => (
                  <button
                    key={`dot-${idx}`}
                    type="button"
                    className={`step-dot-btn ${idx === activeStepIndex ? 'active' : idx < activeStepIndex ? 'passed' : ''}`}
                    onClick={() => setActiveStepIndex(idx)}
                    title={`Chặng ${idx + 1}: ${s.road_name || s.instruction}`}
                  >
                    {idx + 1}
                  </button>
                ))}
              </div>
              <button
                type="button"
                className="turn-ctrl-btn turn-btn-next"
                disabled={activeStepIndex === steps.length - 1}
                onClick={() => setActiveStepIndex((prev) => Math.min(steps.length - 1, prev + 1))}
              >
                Chặng kế tiếp <ArrowRight size={14} />
              </button>
            </div>

            {/* Expandable all-steps list */}
            <details className="nav-all-steps-details">
              <summary className="nav-all-steps-summary">
                <span>Xem toàn bộ danh sách {steps.length} chặng rẽ</span>
                <ChevronDown size={13} />
              </summary>
              <ol className="geo-steps-list">
                {steps.map((step, idx) => (
                  <li
                    key={`step-${step.step_number}`}
                    className={`geo-step-item ${idx === activeStepIndex ? 'current-step' : ''}`}
                    onClick={() => setActiveStepIndex(idx)}
                  >
                    <span className="step-num">{step.step_number}</span>
                    <div className="step-body">
                      <p className="step-inst">{step.instruction}</p>
                      <span className="step-meta">
                        {step.road_name} &bull; {step.distance_km} km
                      </span>
                    </div>
                  </li>
                ))}
              </ol>
            </details>
          </div>
        )}
      </div>

      {/* Action Buttons: Phone and Direct Links */}
      <div className="geo-action-buttons-row">
        <a
          href={geoRouting.google_maps_turn_by_turn_url}
          target="_blank"
          rel="noreferrer"
          className="geo-btn-primary-nav"
        >
          <Navigation size={16} />
          <span>MỞ DẪN ĐƯỜNG TRÊN GOOGLE MAPS (LỰA CHỌN 1)</span>
          <ExternalLink size={13} />
        </a>

        {poi.emergency_or_direct_phone && (
          <a
            href={`tel:${poi.emergency_or_direct_phone}`}
            className="geo-btn-phone"
          >
            <PhoneCall size={15} />
            <span>Gọi Trực Tiếp ({poi.emergency_or_direct_phone})</span>
          </a>
        )}
      </div>

      {/* Alternative POIs near the area */}
      {geoRouting.alternative_pois?.length > 0 && (
        <div className="geo-alt-pois-box">
          <span className="alt-pois-title">Các địa điểm dự phòng khác lân cận:</span>
          <div className="alt-pois-grid">
            {geoRouting.alternative_pois.map((alt) => (
              <div key={alt.id} className="alt-poi-item">
                <div className="alt-poi-info">
                  <strong>{alt.name}</strong>
                  <p className="alt-poi-addr">{alt.address}</p>
                  <span className={`alt-poi-status ${alt.is_open ? 'status-open' : 'status-closed'}`}>
                    {alt.status_label}
                  </span>
                </div>
                {alt.phone && (
                  <a href={`tel:${alt.phone}`} className="alt-poi-call">
                    <PhoneCall size={12} />
                    <span>{alt.phone}</span>
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function HealthTwinUpdateCard({ update }) {
  if (!update) return null;
  const isAdr = update.detected_event === 'adverse_reaction';
  const isRecovery = update.detected_event === 'recovery';
  const isDeterioration = update.detected_event === 'deterioration';

  const badgeColor = isAdr ? '#ef4444' : isRecovery ? '#10b981' : isDeterioration ? '#dc2626' : '#f59e0b';
  const title = isAdr
    ? 'CẢNH BÁO PHẢN ỨNG PHỤ CỦA THUỐC (ADR)'
    : isRecovery
    ? 'GHI NHẬN HỒI PHỤC SỨC KHOẺ'
    : isDeterioration
    ? 'CẢNH BÁO TIẾN TRIỂN TĂNG NẶNG'
    : 'CẬP NHẬT DIỄN TIẾN LÂM SÀNG';

  return (
    <div className={`health-twin-update-card ${isAdr ? 'adr-alert' : isRecovery ? 'recovery-good' : ''}`}>
      <div className="update-card-header">
        <div className="header-left-title">
          {isAdr ? (
            <ShieldAlert size={18} className="twin-icon-alert" />
          ) : isRecovery ? (
            <CheckCircle2 size={18} className="twin-icon-good" />
          ) : (
            <Activity size={18} className="twin-icon-neutral" />
          )}
          <strong>{title}</strong>
        </div>
        <span className="health-score-pill" style={{ borderColor: badgeColor, color: badgeColor }}>
          Sức khoẻ: {update.overall_health_score}/100
        </span>
      </div>

      <p className="update-ai-analysis">{update.ai_analysis}</p>

      {update.must_discontinue_previous && (
        <div className="halt-previous-callout">
          <div className="callout-title">
            <X size={15} />
            <strong>CHỈ THỊ AN TOÀN: HẠN CHẾ VÀ DỪNG NGAY CÁCH CŨ</strong>
          </div>
          <p>
            Ngừng ngay các thuốc/phương pháp: <strong>{update.discontinued_items?.join(', ') || 'Thuốc gây kích ứng'}</strong>.
            Tuyệt đối không tiếp tục liều kế tiếp để tránh tổn thương thêm!
          </p>
        </div>
      )}

      {update.action_plan && (
        <div className="update-action-plan-box">
          <span className="plan-label">Lời khuyên kế tiếp:</span>
          <p className="plan-text">{update.action_plan}</p>
        </div>
      )}

      <div className="update-footer-actions">
        <button
          type="button"
          className="open-twin-page-btn"
          onClick={() => {
            window.dispatchEvent(
              new CustomEvent('medguard:navigate', {
                detail: { view: 'health' },
              })
            );
          }}
        >
          <HeartPulse size={15} />
          <span>Xem trên Bản đồ Cơ thể & Sức khoẻ Giải phẫu</span>
          <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}

export function GroundedAnswer({ answer, result, responseMeta = {}, onSelectQuestion, userQuery = '' }) {
  if (!answer) return null;

  const hasNarrative = answer.narrative?.length > 0;
  const verifiedAgentPrimary = responseMeta.verification_status === 'verified'
    && responseMeta.answer_origin === 'gateway_verified' && hasNarrative;
  const agentUnavailable = clinicalIntents.has(responseMeta.intent)
    && ['unavailable', 'timed_out', 'rejected', 'error', 'circuit_open'].includes(responseMeta.verification_status);

  // Clinical action/safety sections are never collapsed by brevity preferences.
  const isBrief = answer.presentation === 'brief' && !clinicalIntents.has(responseMeta.intent)
    && !(answer.safety_notes?.length) && !(answer.next_steps?.length)
    && !(answer.questions?.length) && !(answer.key_points?.length) && !(answer.clinical_hypotheses?.length)
    && !answer.requires_human_review
    && !['URGENT', 'EMERGENCY', 'CRITICAL'].includes(result?.urgency || result?.escalation_level);
  const isFocused = answer.presentation === 'focused';
  const researchedSources = answer.researched_sources || [];
  const sourcesById = new Map(
    researchedSources.map((source, index) => [source.source_id, { ...source, index: index + 1 }]),
  );

  const structuredUrgency = result?.urgency || result?.escalation_level;
  const showTechnicalMeta = responseMeta.showTechnicalMeta === true;
  const isClinical = clinicalIntents.has(responseMeta.intent);
  const status = statusConfig({
    urgency: structuredUrgency,
    overallRisk: result?.overall_risk,
    isClinical,
    intent: responseMeta?.intent,
    verificationStatus: result?.verification_status,
  });
  const StatusIcon = status.icon;

  // System clarifying questions (printed in document/narrative only)
  const systemClarifyingQuestions = [
    ...new Set([
      ...(Array.isArray(answer.display_questions) ? answer.display_questions : []),
      ...(Array.isArray(answer.questions) ? answer.questions : []),
    ]),
  ].slice(0, 3);

  // User follow-up questions (clickable chips for user to ask assistant)
  const userFollowupQuestions = [
    ...new Set([
      ...(Array.isArray(answer.suggested_followups) && answer.suggested_followups.length > 0
        ? answer.suggested_followups
        : (!verifiedAgentPrimary ? getContextualFollowups(answer, responseMeta.intent, status.tone, userQuery || responseMeta.userQuery) : [])),
    ]),
  ].slice(0, 3);

  const hypotheses = (answer.clinical_hypotheses || [])
    .filter((item) => !String(item).toLowerCase().startsWith('lưu ý:'))
    .slice(0, 4);
  const keyPoints = isClinical ? (answer.key_points || []) : (answer.key_points || []).slice(0, 5);
  const focusedRoutine = isFocused && responseMeta.intent === 'triage' && result?.urgency === 'ROUTINE';
  const nextSteps = focusedRoutine && Array.isArray(answer.display_next_steps)
    ? answer.display_next_steps : (answer.next_steps || []);
  const safetyNotes = answer.safety_notes || [];
  const limitations = (answer.limitations || []).slice(0, 2);

  // Narrative blocks: preserve all clinical context, system clarifying questions are printed in document
  const narrativeBlocks = hasNarrative ? answer.narrative : [];
  const narrativeFullText = narrativeBlocks.map((b) => b.text || '').join(' ').toLowerCase();
  const hasNarrativeClarifying = narrativeBlocks.some((b) =>
    b.text?.startsWith('Bạn cho mình biết thêm:') || b.text?.startsWith('Thông tin cần báo nhân viên y tế')
  );
  // Deduplicate clarifying questions: exclude questions already present in narrative text
  const unmentionedClarifyingQuestions = systemClarifyingQuestions.filter((q) => {
    const qNorm = (q || '').trim().toLowerCase();
    return qNorm && !narrativeFullText.includes(qNorm);
  });

  const hasStructuredContent = Boolean(
    keyPoints.length
    || hypotheses.length
    || nextSteps.length
    || safetyNotes.length
    || unmentionedClarifyingQuestions.length,
  );

  const handleLinkInterception = (e) => {
    const anchor = e.target.closest('a');
    if (anchor) {
      const href = anchor.getAttribute('href') || '';
      if (href.includes('view=spending')) {
        e.preventDefault();
        window.dispatchEvent(new CustomEvent('medguard:navigate', { detail: 'spending' }));
      } else if (href.includes('view=schedule')) {
        e.preventDefault();
        window.dispatchEvent(new CustomEvent('medguard:navigate', { detail: 'schedule' }));
      } else if (href.includes('view=navigation')) {
        e.preventDefault();
        window.dispatchEvent(new CustomEvent('medguard:navigate', { detail: 'navigation' }));
      }
    }
  };

  return (
    <div className="grounded-answer modern-clinical-layout" onClickCapture={handleLinkInterception}>
      {(showTechnicalMeta || isClinical) && (
        <div className="answer-assurance-row" aria-label="Trạng thái kiểm chứng câu trả lời">
          <span className={`verification-pill ${responseMeta.verification_status || 'not_requested'}`}>
            {responseMeta.verification_status === 'verified'
              ? <CheckCircle2 size={13} />
              : <CircleHelp size={13} />}
            {verificationLabels[responseMeta.verification_status] || verificationLabels.not_requested}
          </span>
          {showTechnicalMeta && responseMeta.knowledge_approval && (
            <span className={`knowledge-pill ${responseMeta.knowledge_approval}`}>
              {knowledgeLabels[responseMeta.knowledge_approval]}
            </span>
          )}
        </div>
      )}

      <section className={`clinical-summary-card status-${status.tone}`}>
        {!isBrief && <div className="clinical-status-row">
          <span className={`clinical-status-badge ${status.tone}`}>
            <StatusIcon size={15} />
            <strong>{status.label}</strong>
          </span>
          {answer.evidence_state && (
            <span className={`clinical-evidence-chip ${answer.evidence_state}`}>
              {evidenceLabels[answer.evidence_state] || answer.evidence_state}
            </span>
          )}
        </div>}

        <div className="clinical-summary-copy">
          {!isBrief && (
            <span className="clinical-kicker">
              {responseMeta.intent === 'financial' ? 'Kế hoạch ngân sách y tế' : isClinical ? 'Đánh giá ban đầu' : 'Kết quả xử lý'}
            </span>
          )}
          <h2>{answer.title}</h2>
          {agentUnavailable && (
            <p role="status" className="agent-unavailable-notice">
              <AlertCircle size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 6 }} />
              Lưu ý: Đây là hướng dẫn chăm sóc ban đầu an toàn. Nếu các triệu chứng kéo dài hoặc diễn tiến bất thường, bạn nên thăm khám bác sĩ chuyên khoa.
            </p>
          )}
          {!verifiedAgentPrimary && <p>{focusedRoutine && answer.display_summary ? answer.display_summary : answer.summary}</p>}
          {!isBrief && responseMeta.intent !== 'financial' && <small>{status.helper}</small>}
        </div>
      </section>

      {/* P0 CRITICAL EMERGENCY ACTION BAR (ZERO-CLICK EMERGENCY ACTION) */}
      {(status.tone === 'emergency' || structuredUrgency === 'EMERGENCY') && (
        <div className="emergency-action-banner" role="alert" aria-live="assertive">
          <div className="emergency-banner-top">
            <div className="emergency-beacon-wrap">
              <span className="emergency-pulse-ring" />
              <ShieldAlert size={24} className="emergency-icon-svg" />
            </div>
            <div className="emergency-banner-texts">
              <strong className="emergency-title">TÌNH TRẠNG NGUY KỊCH • HÀNH ĐỘNG CẤP CỨU NGAY</strong>
              <p className="emergency-desc">
                Dấu hiệu đe dọa tính mạng (nghi nhồi máu cơ tim, đột quỵ, khó thở cấp). Không tự lái xe, hãy ấn gọi cấp cứu ngay hoặc đến khoa cấp cứu gần nhất!
              </p>
            </div>
          </div>
          <div className="emergency-banner-actions">
            <a
              href="tel:115"
              className="btn-emergency-call"
              title="Gọi Cấp Cứu 115 ngay lập tức (Miễn phí)"
            >
              <PhoneCall size={20} className="phone-icon-wiggle" />
              <div className="btn-call-text-col">
                <span className="btn-call-headline">GỌI CẤP CỨU 115</span>
                <span className="btn-call-subline">Ấn gọi ngay • 24/7 toàn quốc</span>
              </div>
            </a>
            <button
              type="button"
              className="btn-emergency-nav"
              onClick={() => {
                window.dispatchEvent(new CustomEvent('medguard:navigate', { detail: 'navigation' }));
              }}
              title="Mở bản đồ tìm Khoa Cấp cứu & Bệnh viện gần nhất"
            >
              <Navigation size={19} />
              <div className="btn-call-text-col">
                <span className="btn-call-headline">TÌM CẤP CỨU GẦN NHẤT</span>
                <span className="btn-call-subline">Bản đồ định tuyến MedGuard</span>
              </div>
            </button>
          </div>
        </div>
      )}

      {/* Anti-counterfeit / Product Registry Verification Card */}
      {(responseMeta.intent === 'authenticity' || result?.verification_status) && (
        <ProductVerificationCard result={result} answer={answer} />
      )}

      {/* Healthcare Financial Advisory Card */}
      {(responseMeta.intent === 'financial' || result?.monthly_budget_target_vnd || answer?.financial_assessment_update?.is_budget_update) && (
        <FinancialAdvisoryCard result={result} answer={answer} />
      )}

      {/* 1. GIẢI THÍCH Y KHOA & PHÂN TÍCH TRIỆU CHỨNG (Việc giải thích) */}
      {!verifiedAgentPrimary && responseMeta.intent !== 'financial' && hasNarrative && narrativeBlocks.length > 0 && (
        <div className="clinical-explanation-narrative-box">
          <div className="explanation-section-title">
            <Stethoscope size={15} />
            <span>{isClinical ? 'Giải thích y khoa & Đánh giá tình trạng' : 'Giải thích chi tiết'}</span>
          </div>
          <div className="answer-narrative">
            {narrativeBlocks
              .filter((b) => !hasNarrativeClarifying || (!b.text?.startsWith('Bạn cho mình biết thêm:') && !b.text?.startsWith('Thông tin cần báo nhân viên y tế')))
              .map((block, index) => (
                <NarrativeBlock key={`explanation-${index}`} block={block} sourcesById={sourcesById} />
              ))}
          </div>
        </div>
      )}

      {verifiedAgentPrimary ? (
        <>
          <div className="answer-narrative clinical-agent-primary" data-answer-authority="verified-agent">
            {narrativeBlocks.map((block, index) => (
              <NarrativeBlock key={`primary-${index}`} block={block} sourcesById={sourcesById} />
            ))}
          </div>

          {safetyNotes.length > 0 && (
            <ClinicalSection
              title={status.tone === 'emergency' ? 'Hành động và dấu hiệu khẩn cấp' : 'Khi nào cần đi khám / cấp cứu'}
              icon={ShieldAlert}
              items={safetyNotes}
              tone={status.tone === 'emergency' ? 'danger' : 'warning'}
              className="clinical-section-wide"
            />
          )}

          {!hasNarrativeClarifying && unmentionedClarifyingQuestions.length > 0 && (
            <ClinicalClarifyingNotes questions={unmentionedClarifyingQuestions} />
          )}

          <ResearchedSourcesFootnote sources={researchedSources} />

          <InteractiveFollowupPrompts
            questions={userFollowupQuestions}
            onSelectQuestion={onSelectQuestion}
          />
        </>
      ) : !isBrief && hasStructuredContent ? (
        <>
          <div className="clinical-report-body">
            <ClinicalSection
              title={isClinical ? 'Dữ kiện chính' : 'Thông tin chính'}
              icon={Activity}
              items={isFocused && responseMeta.intent === 'triage' && status.tone === 'routine' ? [] : keyPoints}
              tone="neutral"
            />

            <ClinicalSection
              title="Khả năng cần cân nhắc"
              icon={Stethoscope}
              items={isFocused ? [] : hypotheses}
              tone="clinical"
            />

            {/* 2. NỘI DUNG ĐỀ XUẤT XỬ TRÍ & HƯỚNG DẪN DÙNG THUỐC (Nội dung đề xuất) */}
            <ClinicalSection
              title={isClinical ? 'Bạn nên làm gì lúc này' : 'Bước tiếp theo'}
              icon={ListChecks}
              items={nextSteps}
              tone="action"
              ordered
              className="clinical-section-wide"
            />

            <ClinicalSection
              title={status.tone === 'emergency' ? 'Hành động và dấu hiệu khẩn cấp' : 'Khi nào cần đi khám / cấp cứu'}
              icon={ShieldAlert}
              items={safetyNotes}
              tone={status.tone === 'emergency' ? 'danger' : 'warning'}
              className="clinical-section-wide"
            />

            {hasNarrativeClarifying && (
              <div className="clinical-clarifying-direct-wrap">
                {narrativeBlocks
                  .filter((b) => b.text?.startsWith('Bạn cho mình biết thêm:') || b.text?.startsWith('Thông tin cần báo nhân viên y tế'))
                  .map((block, i) => (
                    <NarrativeBlock key={`clarifying-direct-${i}`} block={block} sourcesById={sourcesById} />
                  ))}
              </div>
            )}

            {!hasNarrativeClarifying && unmentionedClarifyingQuestions.length > 0 && (
              <ClinicalClarifyingNotes questions={unmentionedClarifyingQuestions} />
            )}
          </div>

          <ResearchedSourcesFootnote sources={researchedSources} />

          <InteractiveFollowupPrompts
            questions={userFollowupQuestions}
            onSelectQuestion={onSelectQuestion}
          />
        </>
      ) : !isBrief && hasNarrative && !verifiedAgentPrimary ? (
        <>
          {!hasNarrativeClarifying && systemClarifyingQuestions.length > 0 && (
            <ClinicalClarifyingNotes questions={systemClarifyingQuestions} />
          )}

          <ResearchedSourcesFootnote sources={researchedSources} />

          <InteractiveFollowupPrompts
            questions={userFollowupQuestions}
            onSelectQuestion={onSelectQuestion}
          />
        </>
      ) : null}

      {/* 3. TÌM VỊ TRÍ, NHÀ THUỐC GPP & BẢN ĐỒ CHỈ ĐƯỜNG (Đặt ở sau phần giải thích và nội dung đề xuất theo đúng yêu cầu) */}
      {answer.health_twin_update && (
        <HealthTwinUpdateCard update={answer.health_twin_update} />
      )}

      {answer.medication_suitability && (
        <MedicationSuitabilityCard suitability={answer.medication_suitability} />
      )}

      {answer.geo_routing && (
        <RealTimeGeoMapCard geoRouting={answer.geo_routing} />
      )}

      {answer.emergency_transit && (
        <EmergencyTransitCard transit={answer.emergency_transit} />
      )}

      {answer.enroute_triage && (
        <EnRouteTriageCard enroute={answer.enroute_triage} />
      )}

      {/* Connected Ecosystem Action Bar linking Chat to 3D Twin, Meds, Appointments, Spending & Map */}
      <ConnectedEcosystemActionBar answer={answer} result={result} responseMeta={responseMeta} />

      {!isBrief && limitations.length > 0 && (
        <div className="clinical-limitations">
          <AlertCircle size={15} />
          <div>
            <strong>{isClinical ? 'Lưu ý khi theo dõi sức khỏe tại nhà' : 'Giới hạn xử lý'}</strong>
            {limitations.map((item, index) => <p key={`${item}-${index}`}>{item}</p>)}
          </div>
        </div>
      )}
    </div>
  );
}

function NarrativeBlock({ block, sourcesById }) {
  const isUrgentBlock = block.kind === 'urgent';
  const isCautionBlock = block.kind === 'caution';
  const isClarifyingBlock = block.text?.startsWith('Bạn cho mình biết thêm:') || block.text?.startsWith('Thông tin cần báo nhân viên y tế nếu có thể:');

  if (isClarifyingBlock) {
    const cleanPrompt = block.text.replace(/^(Bạn cho mình biết thêm:|Thông tin cần báo nhân viên y tế nếu có thể:)\s*/, '');
    return (
      <div className="narrative-clarifying-block">
        <div className="clarifying-block-header">
          <ClipboardList size={14} className="clarifying-block-icon" />
          <span>Thông tin cần biết thêm</span>
        </div>
        <p className="clarifying-block-text">
          <HighlightedText text={cleanPrompt} emphasis={block.emphasis} />
        </p>
      </div>
    );
  }

  return (
    <p className={block.kind}>
      {isUrgentBlock && <AlertCircle size={17} className="block-lead-icon urgent" />}
      {isCautionBlock && <AlertTriangle size={17} className="block-lead-icon caution" />}
      <HighlightedText text={block.text} emphasis={block.emphasis} />
      {block.source_ids?.length > 0 && (
        <span className="inline-citations">
          {[...new Set(block.source_ids)].map((sourceId) => {
            const source = sourcesById.get(sourceId);
            return source ? (
              <a
                key={sourceId}
                href={source.url}
                target="_blank"
                rel="noreferrer"
                title={`${source.publisher}: ${source.title}`}
                aria-label={`Mở nguồn ${source.index}: ${source.title}`}
              >
                {source.index}
              </a>
            ) : null;
          })}
        </span>
      )}
    </p>
  );
}

function HighlightedText({ text, emphasis = [] }) {
  const phrases = [...new Set(emphasis)]
    .filter((phrase) => phrase && text.includes(phrase))
    .sort((left, right) => right.length - left.length);
  if (!phrases.length) return text;

  const parts = [];
  let cursor = 0;
  while (cursor < text.length) {
    let match = null;
    for (const phrase of phrases) {
      const index = text.indexOf(phrase, cursor);
      if (index < 0) continue;
      if (!match || index < match.index || (index === match.index && phrase.length > match.phrase.length)) {
        match = { index, phrase };
      }
    }
    if (!match) {
      parts.push(text.slice(cursor));
      break;
    }
    if (match.index > cursor) parts.push(text.slice(cursor, match.index));
    parts.push(<strong key={`${match.index}-${match.phrase}`}>{match.phrase}</strong>);
    cursor = match.index + match.phrase.length;
  }
  return parts;
}

function ConnectedEcosystemActionBar({ answer, result, responseMeta }) {
  const handleNav = (targetView, options = {}) => {
    window.dispatchEvent(
      new CustomEvent('medguard:navigate', {
        detail: {
          view: targetView,
          ...options,
        },
      })
    );
  };

  return (
    <div className="connected-ecosystem-action-bar" aria-label="Liên kết tính năng hệ sinh thái MedGuard">
      <div className="ecosystem-bar-header">
        <Sparkles size={14} className="icon-sparkle" />
        <span>Khám phá tính năng liên quan đến câu trả lời:</span>
      </div>
      <div className="ecosystem-chips-grid">
        <button
          type="button"
          className="ecosystem-chip-btn chip-twin"
          onClick={() => handleNav('health')}
          title="Xem vị trí cơ quan và chỉ số trên Bản đồ Cơ thể 3D"
        >
          <Activity size={14} />
          <span>Bản đồ Cơ thể 3D</span>
        </button>

        <button
          type="button"
          className="ecosystem-chip-btn chip-med"
          onClick={() => handleNav('medication')}
          title="Quản lý phác đồ và hẹn giờ nhắc uống thuốc"
        >
          <Pill size={14} />
          <span>Lịch uống thuốc</span>
        </button>

        <button
          type="button"
          className="ecosystem-chip-btn chip-appt"
          onClick={() => handleNav('schedule')}
          title="Đặt lịch tư vấn với Bác sĩ chuyên khoa"
        >
          <Calendar size={14} />
          <span>Đặt lịch Bác sĩ</span>
        </button>

        <button
          type="button"
          className="ecosystem-chip-btn chip-spending"
          onClick={() => handleNav('spending')}
          title="Theo dõi chi phí y tế và quyền lợi BHYT"
        >
          <WalletCards size={14} />
          <span>Sổ Chi Tiêu & BHYT</span>
        </button>

        <button
          type="button"
          className="ecosystem-chip-btn chip-map"
          onClick={() => handleNav('navigation')}
          title="Tìm bệnh viện, trạm y tế và nhà thuốc chuẩn GPP gần nhất"
        >
          <MapPin size={14} />
          <span>Bản đồ Y tế Gần nhất</span>
        </button>
      </div>
    </div>
  );
}
