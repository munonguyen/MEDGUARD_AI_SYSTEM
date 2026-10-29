// File: src/server/clinical/clinicalRouter.ts

export type ClinicalIntentPriority =
  | 'P0_CRISIS_SELF_HARM'
  | 'P0_EMERGENCY_RED_FLAG'
  | 'P1_DRUG_QUALITY_COUNTERFEIT'
  | 'P1_DRUG_INTERACTION_AND_DOSING'
  | 'P2_SYMPTOM_TRIAGE'
  | 'P3_VITALS_TRACKING';

export interface PatientContext {
  ageYears?: number;
  ageMonths?: number;
  weightKg?: number;
  isPediatric: boolean;
}

export interface ClinicalRouteDecision {
  priority: ClinicalIntentPriority;
  suppressOtcRecommendations: boolean;
  suppressExpenseAutoSync: boolean;
  suppressMedicationScheduleCard: boolean;
  emergencyCode?: 'STROKE_FAST' | 'ACS_CHEST_PAIN' | 'ANAPHYLAXIS' | 'SELF_HARM_OVERDOSE';
  redFlagSymptoms: string[];
  followUpQuestions: string[];
}

// Chuẩn hóa tiếng Việt giữ nguyên từ có dấu để tránh lỗi khớp nhầm "ngã" trong chuỗi không dấu
export function normalizeTextKeepDiacritics(input: string): string {
  return input
    .toLowerCase()
    .replace(/[.,!?;:()"'«»]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

// Kiểm tra từ khóa theo ranh giới từ (Word Boundary cho tiếng Việt)
export function containsExactPhrase(text: string, phrase: string): boolean {
  const normText = ` ${normalizeTextKeepDiacritics(text)} `;
  const normPhrase = ` ${normalizeTextKeepDiacritics(phrase)} `;
  return normText.includes(normPhrase);
}

const SELF_HARM_PATTERNS = [
  'ngủ mãi không dậy',
  'không còn ý nghĩa',
  'muốn chết',
  'tự tử',
  'tự sát',
  'uống hết 2 vỉ',
  'uống hết vỉ thuốc',
  'kết thúc cuộc đời',
  'chấm dứt cuộc sống'
];

const STROKE_FAST_SYMPTOMS = [
  'mờ mắt',
  'nhìn mờ hẳn',
  'màn sương che',
  'nói hơi líu lưỡi',
  'nói líu lưỡi',
  'nói khó',
  'nói đớ',
  'méo miệng',
  'lệch mặt',
  'cầm đũa bị rơi',
  'yếu tay',
  'tê nửa người',
  'liệt nửa người'
];

const ACS_CARDIAC_SYMPTOMS = [
  'đau thắt ngực',
  'đau ngực trái',
  'lan lên hàm',
  'lan ra tay trái',
  'vã mồ hôi lạnh',
  'khó thở dữ dội'
];

export function extractPatientContext(text: string): PatientContext {
  const norm = normalizeTextKeepDiacritics(text);
  const monthsMatch = norm.match(/(\d+)\s*tháng\s*tuổi/);
  const yearsMatch = norm.match(/(\d+)\s*tuổi/);
  const weightMatch = norm.match(/(\d+(?:[.,]\d+)?)\s*kg\b/);

  const ageMonths = monthsMatch ? parseInt(monthsMatch[1], 10) : undefined;
  const ageYears = yearsMatch ? parseInt(yearsMatch[1], 10) : ageMonths ? Math.floor(ageMonths / 12) : undefined;
  const weightKg = weightMatch ? parseFloat(weightMatch[1].replace(',', '.')) : undefined;

  const isPediatric =
    Boolean(ageMonths && ageMonths < 144) ||
    Boolean(ageYears !== undefined && ageYears < 12) ||
    Boolean(weightKg !== undefined && weightKg < 35) ||
    containsExactPhrase(norm, 'bé nhà mình') ||
    containsExactPhrase(norm, 'con tôi');

  return { ageYears, ageMonths, weightKg, isPediatric };
}

/**
 * QUY TẮC SỐ 1: Chỉ sinh câu hỏi gợi ý từ văn bản của NGƯỜI DÙNG (userText),
 * TUYỆT ĐỐI KHÔNG quét trên văn bản trả lời mẫu của AI (tránh lỗi chữ "mỏi mắt" -> gợi ý "đau mắt đỏ").
 */
export function buildContextualFollowUpQuestions(
  userText: string,
  priority: ClinicalIntentPriority
): string[] {
  if (priority === 'P0_CRISIS_SELF_HARM') {
    return [
      'Kết nối ngay với tổng đài hỗ trợ tâm lý khẩn cấp 24/7',
      'Hướng dẫn người nhà xử trí an toàn tại chỗ trong lúc chờ hỗ trợ'
    ];
  }
  if (priority === 'P0_EMERGENCY_RED_FLAG') {
    return [
      'Những việc cần làm và tuyệt đối tránh trong lúc chờ xe cấp cứu 115?',
      'Danh sách bệnh viện có Đơn vị Đột quỵ / Tim mạch can thiệp gần nhất?'
    ];
  }
  const norm = normalizeTextKeepDiacritics(userText);
  if (containsExactPhrase(norm, 'đau đầu') || containsExactPhrase(norm, 'sốt')) {
    return [
      'Sốt kèm đau đầu khi nào là dấu hiệu cảnh báo viêm màng não hoặc sốt xuất huyết?',
      'Cách hạ sốt và bù nước điện giải an toàn tại nhà theo từng mức nhiệt độ?',
      'Những dấu hiệu nào xuất hiện thêm thì cần đi khám cấp cứu ngay trong ngày?'
    ];
  }
  return [
    'Khi nào các triệu chứng hiện tại cần đi khám bác sĩ chuyên khoa trực tiếp?',
    'Cần theo dõi thêm những dấu hiệu cảnh báo nào tại nhà trong 24 giờ tới?'
  ];
}

export function classifyClinicalIntent(userText: string): ClinicalRouteDecision {
  const norm = normalizeTextKeepDiacritics(userText);

  // BƯỚC 1 (P0): Kiểm tra Khủng hoảng Tâm lý & Ý định Tự hại / Uống quá liều
  const matchedSelfHarm = SELF_HARM_PATTERNS.filter((p) => containsExactPhrase(norm, p));
  if (matchedSelfHarm.length > 0) {
    return {
      priority: 'P0_CRISIS_SELF_HARM',
      suppressOtcRecommendations: true,
      suppressExpenseAutoSync: true,
      suppressMedicationScheduleCard: true,
      emergencyCode: 'SELF_HARM_OVERDOSE',
      redFlagSymptoms: matchedSelfHarm,
      followUpQuestions: buildContextualFollowUpQuestions(userText, 'P0_CRISIS_SELF_HARM')
    };
  }

  // BƯỚC 2 (P0): Kiểm tra Cờ đỏ Đột quỵ (FAST) & Tim mạch cấp
  // QUAN TRỌNG: Chạy TRƯỚC mọi bộ đọc chỉ số để không bị "36.8 độ C" hay "120/80" đánh lừa!
  const matchedStroke = STROKE_FAST_SYMPTOMS.filter((s) => containsExactPhrase(norm, s));
  if (matchedStroke.length > 0) {
    return {
      priority: 'P0_EMERGENCY_RED_FLAG',
      suppressOtcRecommendations: true,
      suppressExpenseAutoSync: true,
      suppressMedicationScheduleCard: true,
      emergencyCode: 'STROKE_FAST',
      redFlagSymptoms: matchedStroke,
      followUpQuestions: buildContextualFollowUpQuestions(userText, 'P0_EMERGENCY_RED_FLAG')
    };
  }

  const matchedCardiac = ACS_CARDIAC_SYMPTOMS.filter((s) => containsExactPhrase(norm, s));
  if (matchedCardiac.length > 0) {
    return {
      priority: 'P0_EMERGENCY_RED_FLAG',
      suppressOtcRecommendations: true,
      suppressExpenseAutoSync: true,
      suppressMedicationScheduleCard: true,
      emergencyCode: 'ACS_CHEST_PAIN',
      redFlagSymptoms: matchedCardiac,
      followUpQuestions: buildContextualFollowUpQuestions(userText, 'P0_EMERGENCY_RED_FLAG')
    };
  }

  // BƯỚC 3 (P1): Kiểm tra Chất lượng Thuốc / Thuốc giả / Số đăng ký / Số lô
  if (
    /\bvn-\d+/i.test(norm) ||
    containsExactPhrase(norm, 'số lô') ||
    containsExactPhrase(norm, 'tem chống giả') ||
    containsExactPhrase(norm, 'thật hay giả') ||
    containsExactPhrase(norm, 'ngả vàng') ||
    containsExactPhrase(norm, 'mùi chua')
  ) {
    return {
      priority: 'P1_DRUG_QUALITY_COUNTERFEIT',
      suppressOtcRecommendations: true,
      suppressExpenseAutoSync: true,
      suppressMedicationScheduleCard: true,
      redFlagSymptoms: [],
      followUpQuestions: [
        'Cách đối chiếu số đăng ký thuốc trên hệ thống Cục Quản lý Dược (DAV)?',
        'Dấu hiệu nhận biết viên thuốc kháng sinh bị ẩm mốc hoặc biến chất?'
      ]
    };
  }

  // BƯỚC 4 (P1): Kiểm tra Tương tác Thuốc & Liều dùng Nhi khoa
  if (
    containsExactPhrase(norm, 'warfarin') ||
    containsExactPhrase(norm, 'ibuprofen') ||
    containsExactPhrase(norm, 'amlodipin') ||
    containsExactPhrase(norm, 'aspirin') ||
    containsExactPhrase(norm, 'hapacol') ||
    containsExactPhrase(norm, 'efferalgan') ||
    containsExactPhrase(norm, 'paracetamol')
  ) {
    return {
      priority: 'P1_DRUG_INTERACTION_AND_DOSING',
      suppressOtcRecommendations: true,
      suppressExpenseAutoSync: true,
      suppressMedicationScheduleCard: true, // Chặn tự động tạo lịch uống khi đang hỏi tương tác/liều dùng!
      redFlagSymptoms: [],
      followUpQuestions: [
        'Những dấu hiệu xuất huyết hoặc quá liều thuốc nào cần đi cấp cứu ngay?',
        'Thuốc giảm đau / hạ sốt nào an toàn hơn trong trường hợp này?'
      ]
    };
  }

  // BƯỚC 5 (P2): Phân luồng triệu chứng lâm sàng (ưu tiên hơn đọc chỉ số đơn thuần nếu có triệu chứng đau/sốt)
  return {
    priority: 'P2_SYMPTOM_TRIAGE',
    suppressOtcRecommendations: false,
    suppressExpenseAutoSync: false,
    suppressMedicationScheduleCard: false,
    redFlagSymptoms: [],
    followUpQuestions: buildContextualFollowUpQuestions(userText, 'P2_SYMPTOM_TRIAGE')
  };
}
