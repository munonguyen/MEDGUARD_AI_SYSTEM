// File: src/server/clinical/autoSyncExtractor.ts

export interface ExtractedMedicalExpense {
  amountVnd: number;
  categoryLabel: string;
  rawMatchedText: string;
}

export interface OrganImpactAssessment {
  organCode: 'NEURO_HEAD' | 'CARDIO_VASCULAR' | 'RESPIRATORY' | 'GI_STOMACH' | 'ENT_THROAT' | 'MUSCULO_JOINT';
  organNameVi: string;
  organHealthScore: number; // Thang chuẩn 40 - 95, không bao giờ trả về 0/100 hay 8/100 cho bệnh nhẹ!
  summaryReason: string;
}

/**
 * Chỉ trích xuất khoản chi y tế khi có ĐƠN VỊ TIỀN TỆ rõ ràng (đồng, đ, ₫, nghìn, ngàn, k, triệu, củ).
 * Tuyệt đối không bắt nhầm "2 vỉ thuốc", "14 tháng tuổi", "400mg", "1g"!
 */
export function extractValidMedicalExpense(userText: string): ExtractedMedicalExpense | null {
  const currencyRegex =
    /\b(\d+(?:[.,]\d+)?)\s*(đồng|đ|₫|nghìn|ngàn|k|triệu|tr|vnđ)\b/i;
  const match = userText.match(currencyRegex);
  if (!match) {
    return null; // Không tạo thẻ Sổ Chi Tiêu nếu người dùng không nhắc tới số tiền!
  }

  const rawNumber = parseFloat(match[1].replace(',', '.'));
  const unit = match[2].toLowerCase();

  let multiplier = 1;
  if (['nghìn', 'ngàn', 'k'].includes(unit)) multiplier = 1_000;
  if (['triệu', 'tr'].includes(unit)) multiplier = 1_000_000;

  const amountVnd = Math.round(rawNumber * multiplier);
  if (amountVnd < 5_000 || amountVnd > 5_000_000_000) {
    return null;
  }

  return {
    amountVnd,
    categoryLabel: 'Chi phí khám & mua thuốc theo khai báo',
    rawMatchedText: match[0]
  };
}

/**
 * Đánh giá duy nhất 1 cơ quan chính xác dựa trên triệu chứng thực của người bệnh,
 * dùng cùng một kết quả cho cả phần tóm tắt và thẻ xin quyền cập nhật Bản đồ Cơ thể 3D.
 */
export function assessSingleConsistentOrganImpact(userText: string): OrganImpactAssessment | null {
  const lower = userText.toLowerCase();

  if (lower.includes('đau thắt ngực') || lower.includes('khó thở')) {
    return {
      organCode: 'CARDIO_VASCULAR',
      organNameVi: 'Tim mạch & Tuần hoàn',
      organHealthScore: 42,
      summaryReason: 'Ghi nhận dấu hiệu đau ngực / khó thở cần đánh giá tim mạch khẩn cấp'
    };
  }

  if (lower.includes('mờ mắt') && (lower.includes('líu lưỡi') || lower.includes('rơi đũa'))) {
    return {
      organCode: 'NEURO_HEAD',
      organNameVi: 'Não bộ & Hệ Thần kinh Trung ương',
      organHealthScore: 35,
      summaryReason: 'Cảnh báo dấu hiệu thần kinh khu trú cấp tính (Nghi ngờ Đột quỵ / TIA)'
    };
  }

  if (lower.includes('đau đầu') || lower.includes('nhức đầu')) {
    return {
      organCode: 'NEURO_HEAD',
      organNameVi: 'Đầu & Thần kinh',
      organHealthScore: 76, // Không bao giờ chấm 8/100 hay 0/100 cho đau đầu âm ỉ!
      summaryReason: 'Theo dõi triệu chứng đau đầu và sốt nhẹ'
    };
  }

  if (lower.includes('khớp gối') || lower.includes('đau nhức khớp')) {
    return {
      organCode: 'MUSCULO_JOINT',
      organNameVi: 'Cơ Xương Khớp',
      organHealthScore: 74,
      summaryReason: 'Ghi nhận triệu chứng đau nhức khớp gối ở người cao tuổi'
    };
  }

  if (lower.includes('viêm họng') || lower.includes('đau họng')) {
    return {
      organCode: 'ENT_THROAT',
      organNameVi: 'Tai Mũi Họng',
      organHealthScore: 78,
      summaryReason: 'Theo dõi triệu chứng viêm đường hô hấp trên / đau họng'
    };
  }

  return null;
}
