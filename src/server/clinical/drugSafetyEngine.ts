// File: src/server/clinical/drugSafetyEngine.ts
import { PatientContext, normalizeTextKeepDiacritics, containsExactPhrase } from './clinicalRouter';

export interface NormalizedDrugMention {
  brandOrInputName: string;
  innActiveIngredient: string;
  strengthMg?: number;
}

const VIETNAMESE_BRAND_TO_INN: Record<string, string> = {
  hapacol: 'paracetamol',
  efferalgan: 'paracetamol',
  panadol: 'paracetamol',
  tylenol: 'paracetamol',
  paracetamol: 'paracetamol',
  acetaminophen: 'paracetamol',
  ibuprofen: 'ibuprofen',
  brufen: 'ibuprofen',
  advil: 'ibuprofen',
  aspirin: 'aspirin',
  warfarin: 'warfarin',
  coumadin: 'warfarin',
  amlodipin: 'amlodipine',
  amlodipine: 'amlodipine',
  norvasc: 'amlodipine',
  augmentin: 'amoxicillin_clavulanate',
  'nhân sâm': 'panax_ginseng',
  zolpidem: 'zolpidem',
  stilnox: 'zolpidem'
};

export interface DrugInteractionRule {
  pair: [string, string];
  severity: 'CONTRAINDICATED' | 'MAJOR' | 'MODERATE';
  clinicalEffect: string;
  recommendation: string;
}

const INTERACTION_MATRIX: DrugInteractionRule[] = [
  {
    pair: ['warfarin', 'ibuprofen'],
    severity: 'CONTRAINDICATED',
    clinicalEffect:
      'NSAID (Ibuprofen) ức chế kết tập tiểu cầu, gây loét niêm mạc dạ dày và cạnh tranh gắn protein huyết tương với Warfarin, làm tăng nguy cơ xuất huyết tiêu hóa và xuất huyết nội sọ nghiêm trọng gấp 3–6 lần.',
    recommendation:
      'TUYỆT ĐỐI KHÔNG tự ý uống Ibuprofen 400mg khi đang dùng Warfarin. Cần tham khảo bác sĩ điều trị để đổi sang giải pháp giảm đau khớp không thuộc nhóm NSAID.'
  },
  {
    pair: ['warfarin', 'aspirin'],
    severity: 'MAJOR',
    clinicalEffect:
      'Hiệp đồng chống huyết khối mạnh giữa kháng Vitamin K (Warfarin) và ức chế tiểu cầu không hồi phục (Aspirin), làm tăng vọt nguy cơ chảy máu nặng.',
    recommendation:
      'Chỉ phối hợp khi có chỉ định chuyên khoa Tim mạch nghiêm ngặt và phải theo dõi sát INR cùng dấu hiệu chảy máu.'
  },
  {
    pair: ['warfarin', 'panax_ginseng'],
    severity: 'MAJOR',
    clinicalEffect:
      'Nhân sâm (Panax ginseng) cảm ứng enzyme CYP và ảnh hưởng kết tập tiểu cầu, làm dao động chỉ số INR (có thể làm giảm hiệu lực chống đông hoặc tăng nguy cơ chảy máu thất thường).',
    recommendation:
      'Tránh tự ý dùng thêm nhân sâm Hàn Quốc khi đang điều trị duy trì bằng Warfarin.'
  },
  {
    pair: ['amlodipine', 'ibuprofen'],
    severity: 'MODERATE',
    clinicalEffect:
      'Ibuprofen gây giữ muối nước và ức chế prostaglandin thận, làm giảm tác dụng hạ huyết áp của Amlodipin và tăng nguy cơ suy giảm chức năng thận ở người cao tuổi (68 tuổi).',
    recommendation:
      'Theo dõi sát huyết áp và tránh dùng Ibuprofen kéo dài ở người cao tuổi tăng huyết áp.'
  }
];

export function extractNormalizedDrugs(text: string): NormalizedDrugMention[] {
  const norm = normalizeTextKeepDiacritics(text);
  const found: NormalizedDrugMention[] = [];

  for (const [brand, inn] of Object.entries(VIETNAMESE_BRAND_TO_INN)) {
    if (containsExactPhrase(norm, brand)) {
      const regex = new RegExp(`${brand}\\s*(\\d+(?:[.,]\\d+)?)\\s*mg`, 'i');
      const match = norm.match(regex);
      const strengthMg = match ? parseFloat(match[1].replace(',', '.')) : undefined;
      found.push({
        brandOrInputName: brand,
        innActiveIngredient: inn,
        strengthMg
      });
    }
  }
  return found;
}

export function evaluateDrugSafetyAndPediatricDose(
  userText: string,
  patient: PatientContext
) {
  const mentions = extractNormalizedDrugs(userText);
  const warnings: string[] = [];
  let isUnsafe = false;

  // 1. Kiểm tra trùng lặp hoạt chất Paracetamol & Quá liều Nhi khoa (Ca 4: Hapacol 250mg + Efferalgan 150mg)
  const paracetamolMentions = mentions.filter((m) => m.innActiveIngredient === 'paracetamol');
  if (paracetamolMentions.length >= 2) {
    isUnsafe = true;
    const brandList = paracetamolMentions.map((m) => m.brandOrInputName.toUpperCase()).join(' + ');
    warnings.push(
      `CẢNH BÁO TRÙNG HOẠT CHẤT (DUPLICATE THERAPY): Cả ${brandList} đều chứa cùng hoạt chất là Paracetamol (Acetaminophen). Tuyệt đối không dùng gộp cùng lúc!`
    );
  }

  if (patient.isPediatric && paracetamolMentions.length > 0 && patient.weightKg) {
    const minSafeMg = Math.round(patient.weightKg * 10);
    const maxSafeMg = Math.round(patient.weightKg * 15);

    // Ví dụ: Viên đặt 150mg + nửa gói 250mg (125mg) = 275mg cho bé 10kg
    const norm = normalizeTextKeepDiacritics(userText);
    const hasHalf250 = norm.includes('nửa gói 250') && norm.includes('150');
    const estimatedTotalMg = hasHalf250
      ? 275
      : paracetamolMentions.reduce((sum, m) => sum + (m.strengthMg || 0), 0);

    if (estimatedTotalMg > maxSafeMg) {
      isUnsafe = true;
      const mgPerKg = (estimatedTotalMg / patient.weightKg).toFixed(1);
      warnings.push(
        `NGUY CƠ NGỘ ĐỘC GAN DO QUÁ LIỀU NHI KHOA: Tổng liều dự kiến (${estimatedTotalMg}mg = ${mgPerKg} mg/kg/lần) vượt quá ngưỡng an toàn cho trẻ nặng ${patient.weightKg}kg. Liều Paracetamol chuẩn cho bé ${patient.weightKg}kg chỉ từ ${minSafeMg}mg đến ${maxSafeMg}mg mỗi 4–6 giờ (tối đa 5 lần/24h).`
      );
    }
  }

  // 2. Kiểm tra Ma trận Tương tác Đa thuốc (Ca 2: Warfarin + Ibuprofen + Nhân sâm + Amlodipin)
  const uniqueInns = Array.from(new Set(mentions.map((m) => m.innActiveIngredient)));
  for (const rule of INTERACTION_MATRIX) {
    const [a, b] = rule.pair;
    if (uniqueInns.includes(a) && uniqueInns.includes(b)) {
      isUnsafe = true;
      warnings.push(`[${rule.severity}] ${rule.clinicalEffect} -> ${rule.recommendation}`);
    }
  }

  // 3. Khóa hoàn toàn danh mục OTC người lớn 500mg nếu bệnh nhân là trẻ em hoặc đang có cảnh báo tương tác
  const allowAdultOtc500mgBox = !patient.isPediatric && !isUnsafe;

  return {
    mentions,
    isUnsafe,
    warnings,
    allowAdultOtc500mgBox,
    allowAddMedicationReminderCard: !isUnsafe && !userText.includes('?')
  };
}
