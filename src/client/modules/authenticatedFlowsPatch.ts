// File: src/client/modules/authenticatedFlowsPatch.ts

// 1. Chuẩn hóa duy nhất 4 khung giờ uống thuốc cho cả trang Lịch khám (Wa) và Lịch thuốc (Xa)
export type CanonicalMedicationSlot = 'morning' | 'noon' | 'evening' | 'night';

export const CANONICAL_MEDICATION_SLOTS: Array<{
  id: CanonicalMedicationSlot;
  label: string;
  timeRange: string;
  defaultTime: string;
}> = [
  { id: 'morning', label: '🌅 Cữ Sáng', timeRange: '06:00 - 09:00', defaultTime: '08:00' },
  { id: 'noon', label: '☀️ Cữ Trưa', timeRange: '11:30 - 13:00', defaultTime: '12:00' },
  { id: 'evening', label: '🌇 Cữ Chiều / Tối', timeRange: '17:30 - 19:30', defaultTime: '18:00' },
  { id: 'night', label: '🌙 Cữ Khuya (Trước ngủ)', timeRange: '20:30 - 22:00', defaultTime: '21:30' }
];

// Ánh xạ tương thích ngược cho dữ liệu cũ dùng slot "afternoon"
export function normalizeMedicationSlot(rawSlot?: string): CanonicalMedicationSlot {
  if (rawSlot === 'afternoon') return 'evening';
  if (rawSlot === 'morning' || rawSlot === 'noon' || rawSlot === 'evening' || rawSlot === 'night') {
    return rawSlot;
  }
  return 'morning';
}

// 2. Sửa lỗi hàm r9(e) trong trang Cơ thể & Sức khoẻ (?view=health):
// Loại trừ các cơ quan có status === 'unassessed' để tài khoản mới không bị báo bệnh giả
export interface OrganState {
  id: string;
  vietnamese_name: string;
  status: 'normal' | 'unassessed' | 'inflamed' | 'warning' | 'critical' | 'adverse_reaction';
  health_score: number | null;
  clinical_notes?: string;
}

export function getAbnormalAssessedOrgans(organs: OrganState[] = []): OrganState[] {
  return organs.filter(
    (organ) =>
      organ.status !== 'unassessed' &&
      organ.health_score !== null &&
      (organ.status !== 'normal' || organ.health_score < 88)
  );
}

// 3. Sửa lỗi ReferenceError: todayStr is not defined & xóa mã ICD-10 giả định K29.7 khi lưu Chi tiêu
export interface NewSpendingFormInput {
  title: string;
  amountVnd: number;
  category: 'medication' | 'clinic' | 'diagnostics' | 'supplements' | 'supplies';
  provider?: string;
  doctor?: string;
  icd10?: string;
  clinicalNotes?: string;
  bhytEligible: boolean;
}

export function buildValidatedSpendingRecord(input: NewSpendingFormInput) {
  const todayStr = new Date().toISOString().slice(0, 10); // Sửa lỗi thiếu khai báo todayStr!
  const cleanAmount = Math.max(0, Math.round(Number(input.amountVnd) || 0));
  if (!input.title.trim() || cleanAmount <= 0) {
    throw new Error('Vui lòng nhập tên khoản chi và số tiền lớn hơn 0 VNĐ.');
  }

  const categoryLabels: Record<NewSpendingFormInput['category'], string> = {
    medication: 'Thuốc kê đơn GPP',
    clinic: 'Khám chuyên khoa',
    diagnostics: 'Xét nghiệm cận lâm sàng',
    supplements: 'Dược phẩm & TPCN',
    supplies: 'Vật tư y tế tiêu hao' // Bổ sung đầy đủ nhãn cho danh mục Vật tư y tế!
  };

  const bhytRate = input.bhytEligible ? 80 : 0;
  const bhytCoveredVnd = Math.round((cleanAmount * bhytRate) / 100);

  return {
    id: `tx_user_${Date.now()}`,
    raw_date: todayStr,
    title: input.title.trim(),
    category: input.category,
    category_name: categoryLabels[input.category],
    provider: input.provider?.trim() || 'Cơ sở y tế / Nhà thuốc',
    doctor: input.doctor?.trim() || null,
    // Tuyệt đối không gán cứng "K29.7 - Chẩn đoán lâm sàng" khi người dùng để trống!
    icd10: input.icd10?.trim() || null,
    amount_vnd: -cleanAmount,
    bhyt_rate: bhytRate,
    bhyt_covered_vnd: bhytCoveredVnd,
    clinical_notes: input.clinicalNotes?.trim() || null
  };
}

// 4. Kiểm tra định dạng Thẻ BHYT (10 số hoặc 15 ký tự) & CCCD (12 số) tại trang Hồ sơ cá nhân
export function validateVietnamHealthIdentity(bhytNumber: string, citizenId: string) {
  const cleanBhyt = bhytNumber.trim().toUpperCase();
  const cleanCccd = citizenId.trim();

  const isBhytFormatValid = cleanBhyt === '' || /^([A-Z]{2}\d{13}|\d{10})$/.test(cleanBhyt);
  const isCccdFormatValid = cleanCccd === '' || /^\d{12}$/.test(cleanCccd);

  return {
    isBhytFormatValid,
    isCccdFormatValid,
    // Chỉ đánh dấu đã khai báo hợp lệ, không tự đóng dấu "ĐÃ XÁC THỰC BHYT" khi nhập chuỗi rác
    verificationStatus:
      isBhytFormatValid && cleanBhyt.length >= 10 ? 'DECLARED_VALID_FORMAT' : 'UNVERIFIED'
  };
}
