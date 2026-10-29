/**
 * MedGuard AI - Conversational Action & Proposal Extraction Engine
 * 
 * Extracts interactive proposals for:
 * 1. Medication Scheduling (Tạo lịch uống thuốc, nhắc thuốc)
 * 2. Doctor Appointment Booking (Đặt lịch khám bệnh, hẹn bác sĩ)
 * 3. Navigation & Medical POIs (Chỉ đường, tìm bệnh viện / nhà thuốc GPP / trạm y tế)
 * 4. Conversational Screen Navigation (Điều hướng màn hình bằng chat)
 */

// =====================================================================
// 1. CONVERSATIONAL SCREEN NAVIGATION
// =====================================================================

export const NAV_COMMANDS = {
  HEALTH: 'health',
  SPENDING: 'spending',
  SCHEDULE: 'schedule',
  MEDICATION: 'medication',
  COMPANION: 'companion',
  NAVIGATION: 'navigation',
  PROFILE: 'profile',
  SETTINGS: 'settings',
};

export function detectConversationalNavigation(text = '') {
  if (!text || typeof text !== 'string') return null;
  const lower = text.toLowerCase().trim();

  // Health Twin / Cơ thể 3D
  if (
    /(?:mở|xem|chuyển|vào|bật)\s+(?:trang\s+|màn\s+hình\s+|tab\s+)?(?:cơ thể|sức khoẻ|sức khỏe|digital\s*twin|mô hình\s*3d|giải phẫu)/i.test(lower) ||
    lower === 'cơ thể & sức khoẻ' || lower === 'digital twin'
  ) {
    return {
      isNavCommand: true,
      targetView: NAV_COMMANDS.HEALTH,
      label: 'Cơ thể & Sức khoẻ (Digital Twin 3D)',
      reply: 'Đã mở mô-đun Cơ thể & Sức khoẻ 3D theo yêu cầu của bạn.',
    };
  }

  // Spending / Chi tiêu y tế
  if (
    /(?:mở|xem|chuyển|vào|bật)\s+(?:trang\s+|màn\s+hình\s+|tab\s+)?(?:chi tiêu|quản lý chi phí|tiết kiệm care|tài chính y tế|bảo hiểm chi trả)/i.test(lower) ||
    lower === 'chi tiêu y tế' || lower === 'quản lý chi tiêu'
  ) {
    return {
      isNavCommand: true,
      targetView: NAV_COMMANDS.SPENDING,
      label: 'Chi Tiêu Y Tế & Tiết Kiệm Care',
      reply: 'Đã chuyển sang mô-đun Quản lý Chi Tiêu Y Tế & Tiết Kiệm Care.',
    };
  }

  // Schedule / Lịch khám bệnh
  if (
    /(?:mở|xem|chuyển|vào|bật)\s+(?:trang\s+|màn\s+hình\s+|tab\s+)?(?:lịch khám|thời khóa biểu khám|danh sách ca khám|hẹn bác sĩ)/i.test(lower) ||
    lower === 'lịch khám' || lower === 'lịch khám bệnh'
  ) {
    return {
      isNavCommand: true,
      targetView: NAV_COMMANDS.SCHEDULE,
      label: 'Lịch Khám Bác Sĩ',
      reply: 'Đã mở trang Lịch khám bệnh của bác sĩ chuyên khoa.',
    };
  }

  // Medication / Lịch uống thuốc
  if (
    /(?:mở|xem|chuyển|vào|bật)\s+(?:trang\s+|màn\s+hình\s+|tab\s+)?(?:lịch thuốc|lịch uống thuốc|nhắc thuốc|thời khóa biểu thuốc)/i.test(lower) ||
    lower === 'lịch thuốc' || lower === 'lịch uống thuốc'
  ) {
    return {
      isNavCommand: true,
      targetView: NAV_COMMANDS.MEDICATION,
      label: 'Lịch Uống Thuốc & Nhắc Liều',
      reply: 'Đã mở bảng theo dõi Lịch uống thuốc cá nhân hóa.',
    };
  }

  // Companion / Bác sĩ 3D Live
  if (
    /(?:gặp|nói chuyện|tương tác|mở|vào|bật)\s+(?:bác sĩ\s*3d|bác sĩ ảo|live companion|trò chuyện 3d)/i.test(lower) ||
    lower === 'bác sĩ 3d live'
  ) {
    return {
      isNavCommand: true,
      targetView: NAV_COMMANDS.COMPANION,
      label: 'Bác Sĩ 3D Live',
      reply: 'Đang kết nối bạn với Bác sĩ 3D Live tương tác thời gian thực.',
    };
  }

  // Navigation / Chỉ đường Real-time
  if (
    /(?:mở|xem|chuyển|vào|bật)\s+(?:bản đồ|chỉ đường|định tuyến|tìm trạm y tế|tìm nhà thuốc)/i.test(lower) ||
    lower === 'bản đồ' || lower === 'chỉ đường'
  ) {
    return {
      isNavCommand: true,
      targetView: NAV_COMMANDS.NAVIGATION,
      label: 'Bản Đồ Chỉ Đường & Trạm Y Tế Real-time',
      reply: 'Đã mở Bản đồ Chỉ đường & Trạm Y tế Real-time.',
    };
  }

  // Profile / Hồ sơ bệnh nhân
  if (
    /(?:mở|xem|chỉnh sửa|cập nhật|sửa)\s+(?:trang\s+|màn\s+hình\s+|tab\s+)?(?:hồ sơ(?:\s*bệnh nhân|\s*cá nhân)?|profile(?:\s*cá nhân)?|thẻ\s*bhyt|thông tin cá nhân)/i.test(lower) ||
    lower === 'hồ sơ' ||
    lower === 'chỉnh sửa hồ sơ' ||
    lower === 'sửa hồ sơ'
  ) {
    return {
      isNavCommand: true,
      targetView: NAV_COMMANDS.PROFILE,
      label: 'Hồ Sơ Y Tế & Xác Thực Bảo Hiểm',
      reply: 'Đã mở trang Quản lý Hồ sơ Y tế & Xác thực Bảo hiểm.',
    };
  }

  // Settings / Cài đặt
  if (/(?:mở|vào)\s+(?:cài đặt|thiết lập|settings)/i.test(lower)) {
    return {
      isNavCommand: true,
      targetView: NAV_COMMANDS.SETTINGS,
      label: 'Cài Đặt Hệ Thống',
      reply: 'Đã mở bảng Cài đặt hệ thống MedGuard AI.',
    };
  }

  return null;
}

// =====================================================================
// 2. CONVERSATIONAL MEDICATION PROPOSAL EXTRACTION
// =====================================================================

export function extractMedicationProposal(text = '') {
  if (!text || typeof text !== 'string') return null;
  const lower = text.toLowerCase();

  // SAFETY GUARDRAIL (Module 1, 2, 11):
  // Suppress medication reminder proposals on questions ('?'), adverse reactions,
  // interactions, anaphylaxis, preeclampsia, or crisis overdose.
  if (
    text.includes('?') ||
    /(?:được không|sao không|có nên|nguy hiểm|tác dụng phụ|tương tác|dị ứng|quá liều|tự tử|tự sát|ngủ mãi|mờ mắt|líu lưỡi|sưng môi|thở rít|nghẹn cổ|huyết áp|đường huyết|tiền sản giật|phản vệ)/i.test(lower)
  ) {
    return null;
  }

  // Trigger keywords for medication scheduling (must be an affirmative scheduling command)
  const isMedIntent =
    /(?:lên\s*lịch|tạo\s*lịch|đặt\s*lịch|thêm\s*lịch|nhắc\s*(?:tôi\s*)?uống|kê\s*lịch|nhắc\s*liều)\b/i.test(text) ||
    (/(?:uống|dùng)\s+thuốc\s+(?:hàng ngày|mỗi ngày|cữ|vào lúc|đều đặn)\b/i.test(lower) && !lower.includes('không'));

  if (!isMedIntent) return null;

  // Extract Medication Name
  // Common medications or patterns like "[Thuốc] [Strength]"
  let medName = '';
  const commonMeds = [
    'Nexium', 'Esomeprazole', 'Paracetamol', 'Panadol', 'Amlodipine', 'Amoxicillin',
    'Metformin', 'Aspirin', 'Ibuprofen', 'Augmentin', 'Glucophage', 'Lipitor',
    'Atorvastatin', 'Crestor', 'Rosuvastatin', 'Concor', 'Bisoprolol', 'Phosphalugel',
    'Omeprazole', 'Berberin', 'Efferalgan', 'Hapacol', 'Gaviscon', 'Telfast', 'Cetirizine'
  ];

  for (const m of commonMeds) {
    const rx = new RegExp(`\\b${m}(?:\\s*(?:Extra|Forte|Plus|Rapid|MR|XR|XL))?(?:\\s*\\d+(?:mg|g|ml))?`, 'i');
    const match = text.match(rx);
    if (match) {
      medName = match[0].trim();
      break;
    }
  }

  if (!medName) {
    // Generic regex for: [thuốc] [Tên] [Strength]
    const genericMatch = text.match(/(?:thuốc|uống|dùng)\s+([A-ZÀ-Ỹa-zà-ỹ0-9_-]{3,20}(?:\s+\d+\s*(?:mg|g|ml))?)/i);
    if (genericMatch && genericMatch[1] && !['lúc', 'vào', 'khi', 'sau', 'trước', 'ngày'].includes(genericMatch[1].toLowerCase())) {
      medName = genericMatch[1].trim();
    }
  }

  if (!medName) return null; // Can't schedule without a medication name

  // Extract Dosage
  let dosage = '1 viên';
  const dosageMatch = text.match(/(\d+)\s*(viên|gói|ống|muỗng|ml|giọt|viên nén|viên nang)/i);
  if (dosageMatch) {
    dosage = `${dosageMatch[1]} ${dosageMatch[2]}`;
  }

  // Extract Strength
  let strength = '';
  const strengthMatch = text.match(/(\d+(?:\.\d+)?\s*(?:mg|g|mcg|ml))/i);
  if (strengthMatch) {
    strength = strengthMatch[1].replace(/\s+/g, '');
  } else if (/40mg/i.test(medName)) strength = '40mg';
  else if (/500mg/i.test(medName)) strength = '500mg';
  else if (/5mg/i.test(medName)) strength = '5mg';

  // Extract Timing & Slot
  let timing = '08:00';
  let slot = 'morning';
  const times = [];

  // Check specific hour mentions e.g. "lúc 8h", "8:30", "20h"
  const timeMatches = [...text.matchAll(/(\d{1,2})(?:h|:)(\d{2})?|(\d{1,2})\s*giờ/gi)];
  if (timeMatches.length > 0) {
    for (const tm of timeMatches) {
      const hour = parseInt(tm[1] || tm[3], 10);
      const min = tm[2] ? parseInt(tm[2], 10) : 0;
      if (hour >= 0 && hour <= 23) {
        times.push(`${String(hour).padStart(2, '0')}:${String(min).padStart(2, '0')}`);
      }
    }
  }

  if (times.length > 0) {
    timing = times[0];
    const hourVal = parseInt(timing.split(':')[0], 10);
    if (hourVal < 11) slot = 'morning';
    else if (hourVal < 14) slot = 'noon';
    else if (hourVal < 20) slot = 'evening';
    else slot = 'night';
  } else {
    // Relative slot check
    if (/(?:trước khi ngủ|khuya|đêm)\b/i.test(lower)) {
      timing = '21:30';
      slot = 'night';
    } else if (/(?:tối)\b/i.test(lower)) {
      timing = '18:00';
      slot = 'evening';
    } else if (/(?:trưa)\b/i.test(lower)) {
      timing = '12:00';
      slot = 'noon';
    } else {
      timing = '08:00';
      slot = 'morning';
    }
  }

  // Extract Instruction
  let instruction = 'Uống cùng một cốc nước lọc ấm';
  if (/sau\s*(?:khi\s*)?ăn/i.test(lower)) {
    instruction = 'Uống sau bữa ăn 30 phút, nuốt nguyên viên';
  } else if (/trước\s*(?:khi\s*)?ăn/i.test(lower)) {
    instruction = 'Uống trước bữa ăn 30 - 60 phút khi bụng đói';
  } else if (/trong\s*(?:khi\s*)?ăn/i.test(lower)) {
    instruction = 'Uống ngay trong bữa ăn để bảo vệ dạ dày';
  }

  // Color theme by slot
  const colorTheme = slot === 'morning' ? 'blue' : slot === 'noon' ? 'teal' : slot === 'evening' ? 'purple' : 'amber';

  return {
    hasProposal: true,
    proposalId: `med_prop_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
    medication: {
      id: `MED-USER-${Date.now().toString().slice(-4)}`,
      name: medName.charAt(0).toUpperCase() + medName.slice(1),
      strength: strength || 'Chuẩn đơn',
      dosage,
      slot,
      timing,
      times: times.length > 1 ? times : [timing],
      instruction,
      purpose: `Nhắc liều điều trị theo phác đồ cá nhân hóa`,
      warnings: 'Uống đúng liều lượng chỉ định, không tự ý tăng giảm liều.',
      doctor: 'BS. Tư vấn MedGuard AI',
      colorTheme,
      createdAt: new Date().toISOString(),
    },
  };
}

// =====================================================================
// 3. CONVERSATIONAL DOCTOR APPOINTMENT BOOKING EXTRACTION
// =====================================================================

export function extractAppointmentProposal(text = '', context = {}) {
  if (!text || typeof text !== 'string') return null;
  const lower = text.toLowerCase();

  // Trigger keywords for doctor booking
  const isBookingIntent = /(?:đặt\s*lịch|hẹn\s*(?:lịch|khám|bác\s*sĩ)|đăng\s*ký\s*khám|muốn\s*khám|cần\s*khám|khám\s*(?:với|tại|ở)|tái\s*khám)\b/i.test(lower);

  if (!isBookingIntent) return null;

  // Extract Department / Specialty
  let department = 'Nội Tổng quát';
  let room = 'Phòng 102 - Tầng 1';
  let defaultDoctor = 'BS. CKII Lê Văn Cường';

  if (/(?:tim\s*mạch|huyết\s*áp|mạch\s*vành|đau\s*ngực)/i.test(lower)) {
    department = 'Nội Tim mạch';
    room = 'Phòng 204 - Tầng 2';
    defaultDoctor = 'BS. CKII Trần Quốc Huy';
  } else if (/(?:tiêu\s*hóa|dạ\s*dày|đại\s*tràng|gan\s*mật|thượng\s*vị)/i.test(lower)) {
    department = 'Nội Tiêu hóa & Gan Mật';
    room = 'Phòng 208 - Tầng 2';
    defaultDoctor = 'ThS. BS Đỗ Hoàng Long';
  } else if (/(?:nội\s*tiết|đường\s*huyết|tiểu\s*đường|tuyến\s*giáp)/i.test(lower)) {
    department = 'Nội tiết - Đái tháo đường';
    room = 'Phòng 108 - Tầng 1';
    defaultDoctor = 'ThS. BS Lê Hoàng Mai';
  } else if (/(?:tai\s*mũi\s*họng|viêm\s*họng|xoang|amidan)/i.test(lower)) {
    department = 'Tai Mũi Họng';
    room = 'Phòng 301 - Tầng 3';
    defaultDoctor = 'BS. CKI Nguyễn Minh Tuấn';
  } else if (/(?:thần\s*kinh|đau\s*đầu|mất\s*ngủ|chóng\s*mặt)/i.test(lower)) {
    department = 'Nội Thần kinh';
    room = 'Phòng 205 - Tầng 2';
    defaultDoctor = 'BS. CKII Phạm Thu Hà';
  }

  // Doctor Name Extraction if explicitly stated
  const docMatch = text.match(/(?:bác\s*sĩ|bs\.?)\s+([A-ZÀ-Ỹa-zà-ỹ\s]{3,25})/i);
  if (docMatch && docMatch[1]) {
    const rawDoc = docMatch[1].trim();
    if (!['chuyên khoa', 'nào', 'gì', 'khám', 'trực'].includes(rawDoc.toLowerCase())) {
      defaultDoctor = `BS. ${rawDoc}`;
    }
  }

  // Hospital Name Extraction
  let hospital = 'Bệnh viện Chợ Rẫy (KCB Ban đầu)';
  if (/bạch\s*mai/i.test(lower)) hospital = 'Bệnh viện Bạch Mai';
  else if (/đại\s*học\s*y\s*dược/i.test(lower)) hospital = 'Bệnh viện Đại học Y Dược TP.HCM';
  else if (/việt\s*đức/i.test(lower)) hospital = 'Bệnh viện Hữu nghị Việt Đức';
  else if (/quân\s*y\s*175/i.test(lower)) hospital = 'Bệnh viện Quân Y 175';
  else if (context?.bhyt_hospital) hospital = context.bhyt_hospital;

  // Date Calculation
  const now = new Date();
  let targetDate = new Date();

  if (/(?:ngày\s*mai|hôm\s*sau|mai)\b/i.test(lower)) {
    targetDate.setDate(now.getDate() + 1);
  } else if (/(?:ngày\s*kia|mốt)\b/i.test(lower)) {
    targetDate.setDate(now.getDate() + 2);
  } else if (/(?:hôm\s*nay)\b/i.test(lower)) {
    targetDate = now;
  } else {
    // Check specific days of week e.g. "thứ 2", "thứ 3", "thứ 4"...
    const dayMatch = lower.match(/thứ\s*([2-7]|hai|ba|tư|bốn|năm|sáu|bảy)/);
    if (dayMatch) {
      const map = { '2': 1, 'hai': 1, '3': 2, 'ba': 2, '4': 3, 'tư': 3, 'bốn': 3, '5': 4, 'năm': 4, '6': 5, 'sáu': 5, '7': 6, 'bảy': 6 };
      const targetDay = map[dayMatch[1]];
      if (targetDay !== undefined) {
        const currentDay = now.getDay() === 0 ? 7 : now.getDay();
        let diff = targetDay - currentDay;
        if (diff <= 0) diff += 7; // Next week
        targetDate.setDate(now.getDate() + diff);
      }
    } else {
      // Default to tomorrow
      targetDate.setDate(now.getDate() + 1);
    }
  }

  const dateStr = targetDate.toISOString().slice(0, 10);

  // Time Slot Calculation
  let timeSlot = '08:30 - 09:00';
  let shiftType = 'morning';
  let shiftName = 'Ca Sáng (07:30 - 11:30)';

  const timeMatch = text.match(/(\d{1,2})(?:h|:)(\d{2})?/i);
  if (timeMatch) {
    const h = parseInt(timeMatch[1], 10);
    const m = timeMatch[2] ? parseInt(timeMatch[2], 10) : 0;
    const endH = m >= 30 ? h + 1 : h;
    const endM = (m + 30) % 60;
    timeSlot = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')} - ${String(endH).padStart(2, '0')}:${String(endM).padStart(2, '0')}`;
    if (h >= 12) {
      shiftType = 'afternoon';
      shiftName = 'Ca Chiều (13:30 - 17:00)';
    }
  }

  return {
    hasProposal: true,
    proposalId: `appt_prop_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
    appointment: {
      id: `SHIFT-CHAT-${Date.now().toString().slice(-4)}`,
      shiftType,
      shiftName,
      timeSlot,
      date: dateStr,
      patientRef: context.patient_ref || 'BN-ONLINE-CARE',
      patientName: context.display_name || 'Bệnh nhân MedGuard',
      age: context.age || null,
      sex: context.sex === 'female' ? 'Nữ' : (context.sex === 'male' ? 'Nam' : 'Chưa cập nhật'),
      phone: context.phone || '',
      doctor: defaultDoctor,
      department,
      room,
      hospital,
      purpose: `Khám & Hội chẩn chuyên khoa ${department} theo hẹn trực tuyến MedGuard AI`,
      vitals: context.vitals || { bp: '--', hr: '--', spo2: '--', temp: '--' },
      prepNotes: 'Có mặt trước giờ khám 15 phút. Xuất trình thẻ BHYT / CCCD tại quầy tiếp đón.',
      status: 'scheduled',
      priority: 'high',
      currentMeds: context.current_medications || [],
      bhytCovered: Boolean(context.bhyt_number),
      bhytRate: context.bhyt_rate || 80,
      createdAt: new Date().toISOString(),
    },
  };
}

// =====================================================================
// 4. CONVERSATIONAL NAVIGATION & MEDICAL POI EXTRACTION
// =====================================================================

export function extractNavigationAction(text = '') {
  if (!text || typeof text !== 'string') return null;
  const lower = text.toLowerCase();

  const isNavIntent = /(?:chỉ\s*đường|dẫn\s*đường|tìm\s*(?:đường|nhà\s*thuốc|bệnh\s*viện|trạm\s*y\s*tế|phòng\s*khám|cấp\s*cứu)|đi\s*đến|đường\s*đến|gần\s*nhất|gọi\s*cấp\s*cứu|cấp\s*cứu\s*115|xe\s*cứu\s*thương)\b/i.test(lower);

  if (!isNavIntent) return null;

  let poiName = 'Bệnh viện Chợ Rẫy (Trung tâm Y tế Tuyến 1)';
  let category = 'hospital';
  let categoryLabel = 'Bệnh viện Đa khoa Trung ương';
  let distance = '1.8 km';
  let duration = '6 phút';
  let address = '201B Nguyễn Chí Thanh, Phường 12, Quận 5, TP. Hồ Chí Minh';
  let coordinates = [106.6596, 10.7554];

  if (/(?:nhà\s*thuốc|tiệm\s*thuốc|gpp|mua\s*thuốc)/i.test(lower)) {
    poiName = 'Nhà thuốc Chuẩn GPP MedGuard - Long Châu';
    category = 'pharmacy';
    categoryLabel = 'Nhà thuốc Đạt Chuẩn GPP Bộ Y Tế';
    distance = '450 m';
    duration = '2 phút đi bộ';
    address = '142 Sư Vạn Hạnh, Phường 9, Quận 10, TP. Hồ Chí Minh';
    coordinates = [106.6695, 10.7672];
  } else if (/(?:cấp\s*cứu|115|nguy\s*kịch|khẩn\s*cấp)/i.test(lower)) {
    poiName = 'Khoa Cấp cứu 115 - Bệnh viện Nhân dân 115';
    category = 'emergency';
    categoryLabel = 'Khoa Cấp Cứu 24/7 (Hotline 115)';
    distance = '1.1 km';
    duration = '3 phút xe cứu thương';
    address = '527 Sư Vạn Hạnh, Phường 12, Quận 10, TP. Hồ Chí Minh';
    coordinates = [106.6664, 10.7725];
  } else if (/(?:bạch\s*mai)/i.test(lower)) {
    poiName = 'Bệnh viện Bạch Mai';
    category = 'hospital';
    categoryLabel = 'Bệnh viện Hạng Đặc biệt';
    distance = '2.4 km';
    duration = '8 phút';
    address = '78 Giải Phóng, Phương Mai, Đống Đa, Hà Nội';
    coordinates = [105.8408, 20.9996];
  }

  return {
    hasAction: true,
    actionId: `nav_act_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
    navigation: {
      poiName,
      category,
      categoryLabel,
      distance,
      duration,
      address,
      coordinates,
    },
  };
}

// =====================================================================
// 5. CONVERSATIONAL HEALTHCARE SPENDING EXTRACTION
// =====================================================================

export function extractSpendingProposal(text = '', context = {}, attachment = null) {
  if ((!text || typeof text !== 'string') && !attachment) return null;
  const lower = (text || '').toLowerCase();

  // Trigger keywords for medical expense and invoice images
  const isSpendingIntent =
    /(?:mua\s*thuốc|tiền\s*thuốc|viện\s*phí|tiền\s*khám|khám\s*hết|mua\s*hết|chi\s*phí|thanh\s*toán|hóa\s*đơn|hoá\s*đơn|chi\s*tiêu\s*y\s*tế|phiếu\s*thu|biên\s*lai|toa\s*thuốc|đơn\s*thuốc|ảnh\s*hoá\s*đơn|ảnh\s*hóa\s*đơn|chụp\s*hóa\s*đơn|chụp\s*hoá\s*đơn)\b/i.test(lower) ||
    Boolean(
      attachment &&
      (attachment.file?.name?.match(/(?:hoa_don|hoadon|invoice|receipt|bill|thuoc|don_thuoc)/i) ||
       lower.includes('hóa đơn') ||
       lower.includes('hoá đơn') ||
       lower.includes('ảnh') ||
       lower.includes('chụp') ||
       lower.includes('đơn thuốc'))
    );

  if (!isSpendingIntent) return null;

  // Extract amount in VND
  let amount = 0;
  const amountMatch = lower.match(/(?:hết|mất|khoảng|chi|tiêu|giá|thuốc|đơn|toán)?\s*(\d+[\d\.,]*)\s*(tr(?:iệu)?|k|nghìn|ngàn|đ|vnd|đồng)?/i);
  if (amountMatch) {
    let numStr = amountMatch[1].replace(/\./g, '').replace(/,/g, '.');
    let val = parseFloat(numStr);
    const unit = (amountMatch[2] || '').toLowerCase();
    if (unit === 'k' || unit === 'nghìn' || unit === 'ngàn') {
      amount = Math.round(val * 1000);
    } else if (unit.startsWith('tr')) {
      amount = Math.round(val * 1000000);
    } else {
      amount = Math.round(val);
      if (amount > 0 && amount < 2000) {
        amount *= 1000;
      }
    }
  }

  // If amount was not typed in text:
  if (!amount || amount <= 0) {
    return null; // Never fabricate a draft 350.000 ₫ invoice without explicit monetary amounts
  }

  // Determine category & provider
  let category = 'medication';
  let categoryName = 'Thuốc kê đơn GPP';
  let title = attachment || lower.includes('hóa đơn') || lower.includes('hoá đơn')
    ? 'Hóa đơn thuốc từ ảnh chụp'
    : 'Mua thuốc điều trị';
  let provider = 'Nhà thuốc đạt chuẩn GPP';

  if (/(?:khám|bệnh\s*viện|phòng\s*khám|bác\s*sĩ)/i.test(lower)) {
    category = 'clinic';
    categoryName = 'Khám chuyên khoa';
    title = 'Khám & Viện phí điều trị';
    provider = 'Bệnh viện / Cơ sở y tế';
  } else if (/(?:xét\s*nghiệm|nội\s*soi|siêu\s*âm|chụp\s*x-quang|máu)/i.test(lower)) {
    category = 'diagnostics';
    categoryName = 'Xét nghiệm cận lâm sàng';
    title = 'Xét nghiệm y khoa';
    provider = 'Trung tâm xét nghiệm y khoa';
  }

  if (lower.includes('long châu')) provider = 'Nhà thuốc Long Châu - Chuẩn GPP';
  else if (lower.includes('pharmacity')) provider = 'Nhà thuốc Pharmacity - Chuẩn GPP';
  else if (lower.includes('an khang')) provider = 'Nhà thuốc An Khang - Chuẩn GPP';
  else if (lower.includes('bạch mai')) provider = 'Bệnh viện Bạch Mai';
  else if (lower.includes('đại học y dược')) provider = 'BV Đại học Y Dược TP.HCM';

  let bhytCovered = 0;
  if (lower.includes('bhyt') || lower.includes('bảo hiểm')) {
    bhytCovered = Math.round(amount * 0.8);
  }

  return {
    hasProposal: true,
    proposalId: `spend_prop_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
    spending: {
      id: `tx_${Date.now().toString().slice(-4)}`,
      raw_date: new Date().toISOString().slice(0, 10),
      title,
      category,
      category_name: categoryName,
      provider,
      doctor: 'BS. Tư vấn MedGuard AI',
      amount_vnd: -Math.abs(amount),
      bhyt_covered_vnd: bhytCovered,
      is_gpp: category === 'medication',
      verified: true,
    },
  };
}
