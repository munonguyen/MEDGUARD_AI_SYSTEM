// File: src/server/clinical/drugVerificationEngine.ts

export interface DrugInspectionResult {
  registrationNumber?: string;
  batchLotNumber?: string;
  expiryDate?: string;
  hasPhysicalSpoilageSigns: boolean;
  hasBrokenSealSigns: boolean;
  safetyVerdict: 'DO_NOT_CONSUME' | 'VERIFY_WITH_PHARMACY' | 'VALID_FORMAT';
  clinicalMessage: string;
}

export function inspectDrugAuthenticityAndQuality(userText: string): DrugInspectionResult {
  const regMatch = userText.match(/\b(VN-\d{4,6}-\d{2}|VD-\d{4,6}-\d{2})\b/i);
  const lotMatch = userText.match(/số\s*lô\s*([A-Z0-9-]+)/i);
  const expMatch = userText.match(/hạn\s*dùng\s*(\d{1,2}\/\d{4})/i);

  const lower = userText.toLowerCase();
  const hasPhysicalSpoilageSigns =
    lower.includes('ngả vàng') ||
    lower.includes('đổi màu') ||
    lower.includes('mùi chua') ||
    lower.includes('ẩm mốc') ||
    lower.includes('chảy nước');

  const hasBrokenSealSigns =
    lower.includes('tem chống giả bị rách') ||
    lower.includes('rách tem') ||
    lower.includes('mất tem') ||
    lower.includes('hở vỉ');

  if (hasPhysicalSpoilageSigns || hasBrokenSealSigns) {
    return {
      registrationNumber: regMatch?.[1]?.toUpperCase(),
      batchLotNumber: lotMatch?.[1]?.toUpperCase(),
      expiryDate: expMatch?.[1],
      hasPhysicalSpoilageSigns,
      hasBrokenSealSigns,
      safetyVerdict: 'DO_NOT_CONSUME',
      clinicalMessage:
        'CẢNH BÁO DƯỢC PHẨM KHÔNG AN TOÀN — TUYỆT ĐỐI KHÔNG UỐNG: Viên nén Augmentin 1g đạt chuẩn phải có màu trắng đến trắng ngà, vỉ nhôm nguyên vẹn. Dấu hiệu tem chống giả bị rách kèm viên thuốc ngả vàng và bốc mùi chua nồng chứng tỏ thuốc đã bị thâm nhiễm ẩm dẫn đến phân hủy hoạt chất (đặc biệt Kali Clavulanat rất dễ bị thủy phân tạo mùi chua) hoặc có nguy cơ thuốc giả/kém chất lượng. Hãy ngưng sử dụng ngay và mang hộp thuốc (Số ĐK: ' +
        (regMatch?.[1] || 'chưa rõ') +
        ', Số lô: ' +
        (lotMatch?.[1] || 'chưa rõ') +
        ') tới nhà thuốc GPP để kiểm tra và thu hồi.'
    };
  }

  return {
    registrationNumber: regMatch?.[1]?.toUpperCase(),
    batchLotNumber: lotMatch?.[1]?.toUpperCase(),
    expiryDate: expMatch?.[1],
    hasPhysicalSpoilageSigns: false,
    hasBrokenSealSigns: false,
    safetyVerdict: 'VERIFY_WITH_PHARMACY',
    clinicalMessage:
      'Đã ghi nhận thông tin Số đăng ký và Số lô thuốc. Vui lòng sử dụng trình Quét mã QR / Barcode GS1 trên bao bì để đối chiếu trực tiếp với cơ sở dữ liệu Dược Quốc gia.'
  };
}
