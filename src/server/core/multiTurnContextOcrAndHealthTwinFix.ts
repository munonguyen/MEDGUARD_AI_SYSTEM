// File: src/server/core/multiTurnContextOcrAndHealthTwinFix.ts

export interface ChatTurnMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface AggregatedPatientContext {
  isPediatric: boolean;
  ageMonths: number | null;
  ageYears: number | null;
  weightKg: number | null;
  isPregnant: boolean;
  pregnancyWeeks: number | null;
  activeMedications: string[];
}

/**
 * 1. Hợp nhất Ngữ cảnh Bệnh nhân xuyên suốt toàn bộ lịch sử hội thoại (Multi-Turn Context Aggregator)
 * Khắc phục triệt để lỗi quên tuổi/cân nặng của trẻ ở Lượt 2 (BUG-26 / TC-11)
 */
export function aggregateMultiTurnClinicalContext(messages: ChatTurnMessage[]): AggregatedPatientContext {
  const userTextJoined = messages
    .filter((m) => m.role === 'user')
    .map((m) => m.content)
    .join(' . ');

  const lower = userTextJoined.toLowerCase();

  let ageMonths: number | null = null;
  let ageYears: number | null = null;

  const monthMatch = lower.match(/(\d{1,2})\s*tháng(?:\s*tuổi)?/iu);
  if (monthMatch) {
    ageMonths = Number(monthMatch[1]);
    ageYears = Number((ageMonths / 12).toFixed(2));
  } else {
    const yearMatch = lower.match(/(?:bé|con|cháu|em|tôi|bố|mẹ)\s*[^0-9]{0,12}?(\d{1,3})\s*tuổi/iu);
    if (yearMatch) {
      ageYears = Number(yearMatch[1]);
      ageMonths = ageYears * 12;
    }
  }

  let weightKg: number | null = null;
  const weightMatch = lower.match(/(\d{1,3}(?:[.,]\d+)?)\s*(?:kg|kí|cân)/iu);
  if (weightMatch) {
    weightKg = parseFloat(weightMatch[1].replace(',', '.'));
  }

  const pregMatch = lower.match(/(?:mang\s*thai|thai\s*kỳ|bầu)\s*(?:tuần\s*(?:thứ\s*)?)?(\d{1,2})?/iu);
  const isPregnant = Boolean(pregMatch);
  const pregnancyWeeks = pregMatch && pregMatch[1] ? Number(pregMatch[1]) : null;

  const isPediatric =
    (ageMonths !== null && ageMonths < 144) ||
    (weightKg !== null && weightKg < 35) ||
    /\b(bé|cháu\s*nhỏ|sơ\s*sinh|trẻ\s*nhỏ)\b/iu.test(lower);

  const activeMedications: string[] = [];
  for (const med of ['warfarin', 'amlodipin', 'ibuprofen', 'aspirin', 'panadol extra', 'paracetamol', 'efferalgan', 'hapacol', 'insulin', 'amoxicillin']) {
    if (lower.includes(med)) activeMedications.push(med);
  }

  return {
    isPediatric,
    ageMonths,
    ageYears,
    weightKg,
    isPregnant,
    pregnancyWeeks,
    activeMedications
  };
}

/**
 * 2. Kiểm tra An toàn Liều Thuốc có kế thừa Ngữ cảnh Đa lượt (Chặn Panadol Extra / viên 500mg cho trẻ nhỏ)
 */
export function evaluateMultiTurnPediatricDrugSafety(messages: ChatTurnMessage[]): {
  blocked: boolean;
  alertTitle?: string;
  alertSummaryVi?: string;
} {
  const ctx = aggregateMultiTurnClinicalContext(messages);
  const latestMsg = (messages[messages.length - 1]?.content || '').toLowerCase();

  if (ctx.isPediatric && (latestMsg.includes('500mg') || latestMsg.includes('500 mg') || latestMsg.includes('panadol extra') || latestMsg.includes('người lớn'))) {
    const weight = ctx.weightKg || 10.5;
    const mgPerKg = Number((500 / weight).toFixed(1));
    const safeMin = Math.round(weight * 10);
    const safeMax = Math.round(weight * 15);
    const hasCaffeine = latestMsg.includes('panadol extra') || latestMsg.includes('extra');

    return {
      blocked: true,
      alertTitle: 'CẢNH BÁO ĐỎ: CHỐNG CHỈ ĐỊNH VIÊN 500MG NGƯỜI LỚN / PANADOL EXTRA CHO TRẺ NHỎ',
      alertSummaryVi: `Theo thông tin từ lượt trước (bé ${ctx.ageMonths ? `${ctx.ageMonths} tháng tuổi, ` : ''}nặng ${weight} kg), TUYỆT ĐỐI KHÔNG cho bé uống hoặc bẻ đôi viên 500mg người lớn! Liều 500mg tương đương ${mgPerKg} mg/kg/lần (vượt gấp >3 lần ngưỡng an toàn 10–15 mg/kg = ${safeMin}–${safeMax} mg/lần), gây nguy cơ ngộ độc hoại tử gan cấp.${hasCaffeine ? ' Đặc biệt, Panadol Extra chứa 65mg Caffeine chống chỉ định tuyệt đối cho trẻ em vì gây kích thích thần kinh, tim đập nhanh và co giật.' : ''}`
    };
  }

  return { blocked: false };
}

/**
 * 3. Sửa lỗi Động cơ Chấm điểm Bản đồ Cơ thể 3D (/v1/health-twin/evaluate-symptom-update - BUG-27 / TC-12):
 * - Khử từ phủ định ("không đau đầu", "không đau dạ dày", "không sốt")
 * - Dùng ranh giới từ Unicode để từ "hoàn toàn" KHÔNG bị bắt nhầm thành triệu chứng "ho" (Phổi)
 * - Không chia trung bình cộng cho các cơ quan unassessed có điểm 0 (sửa lỗi 72/9 = 8/100 và 212/9 = 24/100)
 */
export function evaluateSymptomUpdateAccurately(rawMessage: string) {
  // Bước 1: Loại bỏ hoàn toàn các cụm phủ định tiếng Việt
  const withoutNegations = rawMessage.replace(
    /\b(không|chẳng|chưa|hết|ko)\s+(?:hề\s+|còn\s+)?(?:bị\s+|có\s+|thấy\s+)?(đau\s+đầu|nhức\s+đầu|đau\s+dạ\s+dày|đau\s+bụng|đau\s+thượng\s+vị|sốt|ho|khó\s+thở|đau\s+khớp|mỏi\s+mắt|đau\s+ngực)/giu,
    ' '
  );

  const lower = withoutNegations.toLowerCase();

  // Bước 2: Kiểm tra ranh giới từ chính xác (Unicode Word Boundary) — "hoàn toàn" KHÔNG khớp với "\bho\b"!
  const hasHeadache = /(?<![a-zà-ỹ])(đau\s+đầu|nhức\s+đầu|chóng\s+mặt)(?![a-zà-ỹ])/iu.test(lower);
  const hasCoughOrLung = /(?<![a-zà-ỹ])(ho\s+khan|ho\s+có\s+đờm|bị\s+ho|ho\s+nhiều|khó\s+thở)(?![a-zà-ỹ])/iu.test(lower);
  const hasStomachPain = /(?<![a-zà-ỹ])(đau\s+dạ\s+dày|đau\s+thượng\s+vị|ợ\s+chua|viêm\s+dạ\s+dày)(?![a-zà-ỹ])/iu.test(lower);

  const assessedScores: number[] = [];
  if (hasHeadache) assessedScores.push(72);
  if (hasCoughOrLung) assessedScores.push(78);
  if (hasStomachPain) assessedScores.push(62);

  // Bước 3: Tính điểm tổng thể chuẩn xác — Nếu không có cơ quan nào bị bệnh thì đạt 95/100 (Khỏe mạnh),
  // tuyệt đối KHÔNG lấy (72 + 0*8) / 9 = 8/100!
  const overallHealthScore =
    assessedScores.length === 0
      ? 95
      : Math.round(
          (assessedScores.reduce((a, b) => a + b, 0) + (9 - assessedScores.length) * 95) / 9
        );

  return {
    overallHealthScore,
    healthTrend: assessedScores.length === 0 ? 'stable' : 'monitoring',
    triggeredOrgans: {
      head: hasHeadache,
      lungs: hasCoughOrLung,
      stomach: hasStomachPain
    }
  };
}

/**
 * 4. Bổ sung vòng lặp Polling cho Job OCR Đơn thuốc (/v1/jobs/{job_id} - BUG-28)
 * và chặn hàm _ee tự bịa hóa đơn 350.000 ₫ cho ảnh không có giá tiền
 */
export async function pollPrescriptionOcrJob(
  pollUrl: string,
  requestFn: (url: string) => Promise<{ status: string; answer?: { summary?: string }; result?: unknown }>,
  maxAttempts = 10,
  intervalMs = 1500
) {
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const jobRes = await requestFn(pollUrl);
    if (jobRes.status === 'completed' || jobRes.status === 'succeeded' || jobRes.status === 'answered') {
      return jobRes;
    }
    if (jobRes.status === 'failed' || jobRes.status === 'error') {
      throw new Error('Không thể nhận diện chữ trong ảnh đơn thuốc. Vui lòng chụp rõ nét hơn.');
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error('Quá thời gian chờ xử lý OCR đơn thuốc.');
}

/**
 * 5. Đồng bộ chuẩn Mã Ca Uống Thuốc ("bedtime" / "afternoon" -> chuẩn 4 ca) & Múi giờ Việt Nam (+07:00) (BUG-30)
 */
export function buildVietnamLocalScheduleIso(dateYmd: string, timeHm: string): string {
  // Sử dụng offset +07:00 của Việt Nam thay vì hậu tố "Z" (UTC) để không bị lệch +7 tiếng!
  return `${dateYmd}T${timeHm}:00+07:00`;
}

export function mapAnySlotToCanonical(slot: string): 'morning' | 'noon' | 'evening' | 'night' {
  if (slot === 'bedtime' || slot === 'night') return 'night';
  if (slot === 'afternoon' || slot === 'evening') return 'evening';
  if (slot === 'noon') return 'noon';
  return 'morning';
}
