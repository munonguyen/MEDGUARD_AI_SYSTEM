// File: src/server/triage/obstetricAnaphylaxisAndPanicLabEngine.ts

export interface CriticalEdgeCaseDecision {
  triggered: boolean;
  code:
    | 'P0_SEVERE_PREECLAMPSIA_HELLP'
    | 'P0_ANAPHYLAXIS_GRADE_2_3'
    | 'P0_SEVERE_HYPOGLYCEMIA_INSULIN'
    | 'P0_CRITICAL_PANIC_LAB_HYPERKALEMIA'
    | 'NONE';
  urgency: 'EMERGENCY';
  specialtyCode: 'OBGYN_ER' | 'EMERGENCY_RESUSCITATION' | 'ENDOCRINE_ER' | 'NEPHRO_CARDIAC_ER';
  specialtyLabel: string;
  clinicalSummaryVi: string;
  immediateActionsVi: string[];
  blockMedicationScheduler: boolean;
  hideKeepTakingDrugBanner: boolean;
}

/**
 * 1. Khử các cụm từ phủ định tiếng Việt ("không bị sốt", "chưa từng đau bụng")
 * trước khi đưa vào bộ quét triệu chứng để tránh bắt nhầm từ khóa sau chữ "không".
 */
export function stripVietnameseNegatedClauses(rawMessage: string): string {
  return rawMessage.replace(
    /\b(không|chẳng|chưa|ko)\s+(?:hề\s+)?(?:bị|có|thấy|còn)?\s*(sốt|đau\s+bụng|ho|nôn|tiêu\s+chảy|đau\s+đầu|khó\s+thở)/giu,
    ' [NEGATED_SYMPTOM] '
  );
}

/**
 * 2. Bộ sàng lọc 4 kịch bản Cấp cứu Lâm sàng & Cận lâm sàng Hóc búa (Chạy ở Tầng P0)
 */
export function evaluateCriticalEdgeCases(rawMessage: string): CriticalEdgeCaseDecision | null {
  const cleaned = stripVietnameseNegatedClauses(rawMessage);
  const lower = cleaned.toLowerCase();

  // KỊCH BẢN A: TIỀN SẢN GIẬT NẶNG / HỘI CHỨNG HELLP Ở THAI PHỤ
  const isPregnant = /(mang\s*thai|bầu\s*bí|thai\s*kỳ|tuần\s*thứ\s*\d+|thai\s*\d+\s*tuần)/iu.test(lower);
  const bpMatch = lower.match(/(\d{2,3})\s*\/\s*(\d{2,3})/);
  const sysBp = bpMatch ? Number(bpMatch[1]) : 0;
  const diaBp = bpMatch ? Number(bpMatch[2]) : 0;
  const hasPreeclampsiaSigns =
    sysBp >= 140 ||
    diaBp >= 90 ||
    /(đau\s*(?:tức\s*)?thượng\s*vị|hoa\s*mắt|nhìn\s*mờ|phù\s*(?:hai\s*)?chân|phù\s*mặt)/iu.test(lower);

  if (isPregnant && hasPreeclampsiaSigns) {
    return {
      triggered: true,
      code: 'P0_SEVERE_PREECLAMPSIA_HELLP',
      urgency: 'EMERGENCY',
      specialtyCode: 'OBGYN_ER',
      specialtyLabel: 'Cấp cứu Sản phụ khoa',
      clinicalSummaryVi:
        'CẢNH BÁO ĐỎ SẢN KHOA (NGHI NGỜ TIỀN SẢN GIẬT NẶNG / HỘI CHỨNG HELLP): Đau vùng thượng vị kèm tăng huyết áp (≥ 140/90 mmHg), nhìn hoa mắt và phù chân ở nửa sau thai kỳ là dấu hiệu nguy kịch đe dọa cả mẹ và thai nhi, tuyệt đối KHÔNG PHẢI đau dạ dày hay hạ huyết áp tư thế!',
      immediateActionsVi: [
        'TUYỆT ĐỐI KHÔNG tự uống thuốc dạ dày (Phosphalugel) rồi nằm chờ ở nhà và KHÔNG uống nước đường.',
        'Đưa thai phụ đến ngay Khoa Cấp cứu Sản khoa gần nhất để kiểm soát huyết áp, dự phòng co giật (Magnesium sulfate) và xét nghiệm men gan / tiểu cầu.',
        'Cho thai phụ nằm nghiêng trái trong lúc di chuyển.'
      ],
      blockMedicationScheduler: true,
      hideKeepTakingDrugBanner: true
    };
  }

  // KỊCH BẢN B: PHẢN VỆ ĐỘ II–III SAU UỐNG THUỐC (SƯNG MÔI, THỞ RÍT, NGHẸN CỔ)
  const hasDrugExposure = /(vừa\s*uống|mới\s*uống|sau\s*khi\s*uống|dùng\s*thuốc|kháng\s*sinh|amoxicillin|augmentin|cefuroxim|ibuprofen)/iu.test(lower);
  const hasAnaphylaxisAirwayOrAngioedema =
    /(thở\s*rít|nghẹn\s*(?:ở\s*)?cổ|sưng\s*môi|phù\s*môi|sưng\s*mắt|khó\s*thở|tụt\s*huyết\s*áp)/iu.test(lower);

  if (hasDrugExposure && hasAnaphylaxisAirwayOrAngioedema) {
    return {
      triggered: true,
      code: 'P0_ANAPHYLAXIS_GRADE_2_3',
      urgency: 'EMERGENCY',
      specialtyCode: 'EMERGENCY_RESUSCITATION',
      specialtyLabel: 'Hồi sức Cấp cứu (Xử trí Phản vệ)',
      clinicalSummaryVi:
        'CẢNH BÁO ĐỎ PHẢN VỆ CẤP TÍNH (ĐỘ II–III): Sưng phù môi, ngứa lòng bàn tay kèm thở rít / nghẹn cổ họng xuất hiện nhanh sau khi uống kháng sinh là dấu hiệu phù nề thanh quản & phản vệ nguy kịch!',
      immediateActionsVi: [
        'NGƯNG NGAY LẬP TỨC thuốc vừa uống (Amoxicillin) — giữ lại vỏ thuốc để mang tới bệnh viện.',
        'TUYỆT ĐỐI KHÔNG uống Cetirizine rồi đi ngủ vì kháng histamin đường uống không chặn được co thắt thanh quản cấp (cần tiêm bắp Adrenalin ngay).',
        'Gọi 115 hoặc đưa ngay tới Khoa Cấp cứu / Trạm Y tế gần nhất trong vòng vài phút.'
      ],
      blockMedicationScheduler: true, // Chặn hàm mee() tạo lịch nhắc uống Amoxicillin!
      hideKeepTakingDrugBanner: true  // Ẩn câu mẫu "Tuyệt đối không tự ý cắt giảm thuốc"!
    };
  }

  // KỊCH BẢN C: HẠ ĐƯỜNG HUYẾT NẶNG DO INSULIN (< 3.9 mmol/L)
  const glucoseMatch = lower.match(/đường\s*huyết[^0-9]*(\d+(?:[.,]\d+)?)\s*mmol\/l/iu);
  const glucoseVal = glucoseMatch ? parseFloat(glucoseMatch[1].replace(',', '.')) : null;
  if (
    (glucoseVal !== null && glucoseVal < 3.9) ||
    (lower.includes('insulin') && /(vã\s*mồ\s*hôi\s*lạnh|run\s*tay|lẫn\s*lộn|lơ\s*mơ)/iu.test(lower))
  ) {
    return {
      triggered: true,
      code: 'P0_SEVERE_HYPOGLYCEMIA_INSULIN',
      urgency: 'EMERGENCY',
      specialtyCode: 'ENDOCRINE_ER',
      specialtyLabel: 'Cấp cứu Nội tiết',
      clinicalSummaryVi: `CẢNH BÁO ĐỎ HẠ ĐƯỜNG HUYẾT NẶNG CẤP TÍNH${glucoseVal ? ` (Đường huyết: ${glucoseVal} mmol/L < 3.9 mmol/L)` : ''}: Vã mồ hôi lạnh, run tay chân và lú lẫn sau tiêm Insulin là tình trạng cấp cứu sinh mạng!`,
      immediateActionsVi: [
        'TUYỆT ĐỐI KHÔNG TIÊM THÊM INSULIN (tiêm thêm sẽ gây hôn mê hạ đường huyết tử vong).',
        'Nếu người bệnh còn tỉnh và nuốt được: Cho uống ngay 15–20g đường hấp thu nhanh (3–4 thìa đường pha nước ấm, mật ong hoặc nửa lon nước ngọt có đường).',
        'Nếu người bệnh lơ mơ / không nuốt được: Tuyệt đối không đổ nước vào miệng tránh sặc phổi; gọi 115 đưa đi truyền Glucose tĩnh mạch ngay.'
      ],
      blockMedicationScheduler: true,
      hideKeepTakingDrugBanner: true
    };
  }

  // KỊCH BẢN D: XÉT NGHIỆM NGUY KỊCH (PANIC LAB VALUES: KALI MÁU >= 6.0 mmol/L, eGFR < 15, NHỊP CHẬM < 45)
  const potassiumMatch = lower.match(/kali(?:\s*máu)?\s*[=:]?\s*(\d+(?:[.,]\d+)?)\s*mmol\/l/iu);
  const potassiumVal = potassiumMatch ? parseFloat(potassiumMatch[1].replace(',', '.')) : null;
  const egfrMatch = lower.match(/egfr\s*[=:]?\s*(\d+(?:[.,]\d+)?)/iu);
  const egfrVal = egfrMatch ? parseFloat(egfrMatch[1].replace(',', '.')) : null;
  const bradycardiaMatch = lower.match(/nhịp\s*tim[^0-9]*(\d{2,3})\s*lần\/phút/iu);
  const hrVal = bradycardiaMatch ? Number(bradycardiaMatch[1]) : null;

  if ((potassiumVal !== null && potassiumVal >= 6.0) || (egfrVal !== null && egfrVal < 15 && hrVal !== null && hrVal < 50)) {
    return {
      triggered: true,
      code: 'P0_CRITICAL_PANIC_LAB_HYPERKALEMIA',
      urgency: 'EMERGENCY',
      specialtyCode: 'NEPHRO_CARDIAC_ER',
      specialtyLabel: 'Cấp cứu Hồi sức Tim mạch & Thận nhân tạo',
      clinicalSummaryVi: `CẢNH BÁO ĐỎ XÉT NGHIỆM NGUY KỊCH (Kali máu ${potassiumVal ?? '>= 6.0'} mmol/L${hrVal ? `, Nhịp tim chậm ${hrVal} lần/phút` : ''}${egfrVal ? `, eGFR ${egfrVal} ml/phút` : ''}): Tăng Kali máu mức độ tối cấp đã gây nhiễm độc dẫn truyền cơ tim, có nguy cơ ngừng tim đột ngột bất cứ lúc nào!`,
      immediateActionsVi: [
        'PHẢI NHẬP VIỆN CẤP CỨU NGAY LẬP TỨC — Tuyệt đối không chờ tới tuần sau tái khám!',
        'Gọi 115 hoặc nhờ người thân đưa ngay tới Bệnh viện đa khoa có đơn vị Thận nhân tạo / Hồi sức tích cực để tiêm Calci tĩnh mạch bảo vệ cơ tim và hạ Kali máu cấp cứu.',
        'Ngưng ngay các thuốc giữ Kali (Spironolacton, ức chế men chuyển, ARB) và thực phẩm giàu Kali.'
      ],
      blockMedicationScheduler: true,
      hideKeepTakingDrugBanner: true
    };
  }

  return null;
}

/**
 * 3. Sửa lỗi Crash ReferenceError: patientProfile is not defined khi bật Auto-submit trong X9 (/static/app.js)
 */
export function applySafeAutoSubmitProfileUpdate<T extends Record<string, unknown>>(
  currentProfileState: T,
  setProfileState: (updater: (prev: T) => T) => void,
  proposal: { hasProposal?: boolean; fields?: Partial<T> } | null
) {
  if (!proposal || !proposal.hasProposal || !proposal.fields) return;
  const merged = { ...currentProfileState, ...proposal.fields };
  setProfileState(() => merged);
  try {
    localStorage.setItem('medguard_verified_patient_profile', JSON.stringify(merged));
  } catch {
    // Bỏ qua lỗi bộ nhớ đầy trên trình duyệt
  }
}
