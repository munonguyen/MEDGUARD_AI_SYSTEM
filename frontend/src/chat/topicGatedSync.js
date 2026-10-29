/**
 * MedGuard AI - Topic-Gated Continuous Chat Synchronization Engine
 * 
 * Provides semantic routing, Wilson Score 95% CI computation, SpamReviewDetector NLP,
 * and strict topic-gated state mutations across Health Overview (3D Anatomical Twin)
 * and Healthcare Expense Hub.
 */

export const TOPIC_MODES = {
  HEALTH_OVERVIEW_ONLY: 'HEALTH_OVERVIEW_ONLY',
  EXPENSE_MANAGEMENT_ONLY: 'EXPENSE_MANAGEMENT_ONLY',
  DUAL_HEALTH_AND_EXPENSE: 'DUAL_HEALTH_AND_EXPENSE',
  UNRELATED_NO_STATE_MUTATION: 'UNRELATED_NO_STATE_MUTATION',
};

export const TOPIC_LABELS = {
  HEALTH_OVERVIEW_ONLY: 'Đồng bộ tự động với Bản đồ Cơ thể 3D',
  EXPENSE_MANAGEMENT_ONLY: 'Đồng bộ tự động với Sổ Chi Tiêu & BHYT',
  DUAL_HEALTH_AND_EXPENSE: 'Đồng bộ Bản đồ Cơ thể 3D & Sổ Chi Tiêu',
  UNRELATED_NO_STATE_MUTATION: 'Hội thoại thông thường',
};

/**
 * Computes Wilson Score lower bound for a 95% confidence interval (z = 1.96).
 * Used for unbiased rating aggregation under sparse reviews.
 * 
 * @param {number} positive - Number of positive ratings / endorsements
 * @param {number} total - Total number of reviews
 * @param {number} confidence - Confidence level (default: 0.95, z = 1.96)
 * @returns {number} Score between 0 and 1
 */
export function calculateWilsonScore(positive, total, confidence = 0.95) {
  if (total <= 0) return 0;
  const z = confidence === 0.95 ? 1.959964 : 1.644853;
  const p = Math.max(0, Math.min(1, positive / total));
  const z2 = z * z;
  const denominator = 1 + z2 / total;
  const center = p + z2 / (2 * total);
  const spread = z * Math.sqrt((p * (1 - p) + z2 / (4 * total)) / total);
  const lowerBound = (center - spread) / denominator;
  return Math.max(0, Math.min(1, Math.round(lowerBound * 1000) / 1000));
}

/**
 * SpamReviewDetector NLP - Evaluates comment authenticity, repetitive patterns,
 * bot syntax, and verified buyer markers.
 * 
 * @param {string} reviewText 
 * @param {Object} metadata 
 * @returns {Object} { isAuthentic, authenticityScore, isSpam, spamConfidence, flaggedReasons, spamFlag }
 */
export function detectSpamReviewNLP(reviewText, metadata = {}) {
  if (!reviewText || typeof reviewText !== 'string') {
    return {
      isAuthentic: false,
      authenticityScore: 0,
      isSpam: true,
      spamConfidence: 1,
      flaggedReasons: ['EMPTY_TEXT'],
      spamFlag: 'EMPTY_TEXT',
    };
  }
  const clean = reviewText.trim();
  if (clean.length < 8) {
    return {
      isAuthentic: false,
      authenticityScore: 0.3,
      isSpam: true,
      spamConfidence: 0.7,
      flaggedReasons: ['TOO_SHORT'],
      spamFlag: 'TOO_SHORT',
    };
  }

  const flaggedReasons = [];

  // Repetitive char check (e.g. "aaaaa", "!!!!!")
  if (/(.)\1{3,}/.test(clean) || (clean.match(/!/g) || []).length >= 3) {
    flaggedReasons.push('EXCESSIVE_PUNCTUATION_OR_REPETITION');
  }

  // Promotional spam patterns / buzzwords
  const spamKeywords = [
    'click link', 'telegram', 'inbox ngay', 'cho vay', 'cờ bạc', 'nhận quà',
    'giảm giá sốc', 'siêu rẻ', 'cam kết khỏi bệnh', 'inbox zalo', 'http://', 'https://'
  ];
  for (const kw of spamKeywords) {
    if (clean.toLowerCase().includes(kw)) {
      flaggedReasons.push(`SPAM_KEYWORD_${kw.toUpperCase().replace(/\s+/g, '_')}`);
    }
  }

  // Account age / unverified buyer check
  if (metadata.accountAgeDays !== undefined && metadata.accountAgeDays < 7) {
    flaggedReasons.push('NEW_UNVERIFIED_ACCOUNT');
  }
  if (metadata.isVerifiedBuyer === false) {
    flaggedReasons.push('UNVERIFIED_BUYER');
  }

  const isSpam = flaggedReasons.length > 0;
  let authenticityScore = 0.88;
  if (isSpam) {
    authenticityScore = Math.max(0.05, 0.45 - flaggedReasons.length * 0.1);
  } else {
    if (metadata.hasVerifiedPrescription || metadata.isVerifiedBuyer) authenticityScore += 0.08;
    if (metadata.hasDavInvoice) authenticityScore += 0.04;
    if (clean.length > 30) authenticityScore += 0.03;
  }
  authenticityScore = Math.min(1, Math.max(0, Math.round(authenticityScore * 100) / 100));
  const spamConfidence = Math.min(1, Math.max(0, Math.round((1 - authenticityScore) * 100) / 100));

  return {
    isAuthentic: !isSpam,
    authenticityScore,
    isSpam,
    spamConfidence,
    flaggedReasons,
    spamFlag: flaggedReasons[0] || null,
  };
}

/**
 * EigenTrust normalized peer reputation rating.
 * Supports both 2D direct trust matrices (power iteration) and 1D trust arrays.
 * 
 * @param {Array<Array<number>>|Array<number>} trustInput 
 * @param {Array<number>|null} initialTrust 
 * @param {number} alpha 
 * @param {number} maxIterations 
 * @param {number} epsilon 
 * @returns {Array<number>|number}
 */
export function calculateEigenTrust(trustInput = [], initialTrust = null, alpha = 0.85, maxIterations = 25, epsilon = 1e-4) {
  // If passed a 2D matrix (direct trust matrix C)
  if (Array.isArray(trustInput) && Array.isArray(trustInput[0])) {
    const n = trustInput.length;
    if (n === 0) return [];

    const C = trustInput.map((row) => {
      const sum = row.reduce((acc, val) => acc + (typeof val === 'number' && val > 0 ? val : 0), 0);
      return sum > 0
        ? row.map((val) => (typeof val === 'number' && val > 0 ? val / sum : 0))
        : Array(n).fill(1 / n);
    });

    const p = initialTrust && Array.isArray(initialTrust) && initialTrust.length === n
      ? [...initialTrust]
      : Array(n).fill(1 / n);

    let t = [...p];

    for (let iter = 0; iter < maxIterations; iter++) {
      const nextT = Array(n).fill(0);
      for (let j = 0; j < n; j++) {
        let incoming = 0;
        for (let i = 0; i < n; i++) {
          incoming += C[i][j] * t[i];
        }
        nextT[j] = (1 - alpha) * p[j] + alpha * incoming;
      }

      let diff = 0;
      for (let k = 0; k < n; k++) {
        diff += Math.abs(nextT[k] - t[k]);
      }
      t = nextT;
      if (diff < epsilon) break;
    }

    const totalT = t.reduce((acc, v) => acc + v, 0);
    return totalT > 0 ? t.map((v) => Math.round((v / totalT) * 1000) / 1000) : t;
  }

  // If passed 1D array of scores or numbers
  if (!Array.isArray(trustInput) || trustInput.length === 0) return 0.5;
  const valid = trustInput.filter((v) => typeof v === 'number' && !isNaN(v) && v >= 0);
  if (valid.length === 0) return 0.5;
  const sum = valid.reduce((acc, v) => acc + v, 0);
  const avg = sum / valid.length;
  const dampened = Math.pow(avg, 0.85);
  return Math.min(1, Math.max(0, Math.round(dampened * 1000) / 1000));
}

/**
 * Classifies a user message into one of 4 topic gating categories.
 * 
 * @param {string} text - Message content
 * @returns {string} One of TOPIC_MODES
 */
export function classifyTopic(text = '') {
  if (!text || typeof text !== 'string') return TOPIC_MODES.UNRELATED_NO_STATE_MUTATION;
  const lower = text.toLowerCase();

  // 1. Active Symptom / Clinical Signals:
  const activeSymptomSignals = [
    'đau', 'rát', 'sốt', 'nhức đầu', 'đau đầu', 'chóng mặt', 'buồn nôn', 'ợ chua',
    'ợ nóng', 'ho', 'khó thở', 'tức ngực', 'nhịp tim', 'huyết áp', 'thân nhiệt',
    'spo2', 'uống thuốc bị', 'tác dụng phụ', 'dị ứng', 'cấp cứu', '115', 'thượng vị',
    'chấn thương', 'mệt mỏi', 'buốt', 'mất ngủ', 'khó ngủ', 'căng thẳng', 'stress', 'lo âu',
    'mỏi mắt', 'nhìn mờ', 'nặng đầu', 'đau lưng', 'vai gáy', 'kiệt sức', 'uể oải', 'hồi hộp',
    'đánh trống ngực', 'khát nước', 'khô miệng', 'tiểu buốt', 'vàng da', 'men gan', 'nổi mề đay',
    'ngứa', 'khỏe hơn', 'đỡ nhiều', 'hết sốt', 'cắt sốt', 'hết đau', 'sổ mũi', 'nghẹt mũi'
  ];

  // 2. Anatomical / Medical mentions:
  const medicalEntitySignals = [
    'dạ dày', 'gan', 'thận', 'phổi', 'mắt', 'não', 'xương khớp', 'tai mũi họng',
    'tiêu hóa', 'viêm', 'kháng viêm', 'ibuprofen', 'paracetamol'
  ];

  // 3. Expense Intent Signals (MUST NOT include plain 'mua' which causes questions like "mình vừa mua thuốc augmentin..." to trigger expense sync!)
  const expenseKeywords = [
    'mua thuốc hết', 'mua hết', 'hóa đơn', 'hoá đơn', 'ảnh hoá đơn', 'ảnh hóa đơn', 'chụp hoá đơn', 'chụp hóa đơn',
    'phiếu thu', 'biên lai', 'ngân sách', 'tiền thuốc', 'thanh toán',
    'bảo hiểm', 'bhyt', 'tiết kiệm care', 'đơn giá', 'tổng chi', 'chi tiêu y tế'
  ];

  // Regex patterns for financial values e.g. "480.000đ", "12 triệu", "500k"
  // MUST require an actual currency token (đ, đồng, ₫, vnd, vnđ, k, triệu, tr, ngàn, nghìn)
  const moneyPattern = /\b\d+(?:[.,]\d+)?\s*(?:đ|đồng|₫|vnd|vnđ|triệu|nghìn|ngàn|tr|k)\b/i;
  const hasExpense = moneyPattern.test(lower) || (expenseKeywords.some((sig) => lower.includes(sig)) && /\d+/.test(lower));

  const hasActiveSymptom = activeSymptomSignals.some((sig) => lower.includes(sig));
  const hasMedicalEntity = medicalEntitySignals.some((sig) => lower.includes(sig));

  // If it's a purchase/expense statement without active symptoms, it's strictly EXPENSE_MANAGEMENT_ONLY
  // (e.g. "Vừa mua thuốc dạ dày Nexium tại nhà thuốc hết 480.000đ")
  if (hasExpense && !hasActiveSymptom) {
    return TOPIC_MODES.EXPENSE_MANAGEMENT_ONLY;
  }

  // If it combines active clinical symptoms AND expense (e.g. "Hôm nay tôi vẫn còn đau rát thượng vị dạ dày nên đi khám và mua thuốc hết 650.000đ")
  if (hasExpense && hasActiveSymptom) {
    return TOPIC_MODES.DUAL_HEALTH_AND_EXPENSE;
  }

  // If it has clinical symptoms or medical entities without expense
  if (hasActiveSymptom || hasMedicalEntity) {
    return TOPIC_MODES.HEALTH_OVERVIEW_ONLY;
  }

  return TOPIC_MODES.UNRELATED_NO_STATE_MUTATION;
}


/**
 * Intelligent Symptom-to-Organ Anatomical Classifier.
 * Maps patient reported symptoms to one of the 9 official MedGuard systems.
 *
 * @param {string} message
 * @returns {Object|null}
 */
export function detectAffectedOrgan(message = '') {
  const lower = (message || '')
    .toLowerCase()
    .replace(/\b(không|chẳng|chưa|hết|đã hết|ko)\s+(?:hề\s+|còn\s+)?(?:bị\s+|có\s+|thấy\s+)?(đau\s+đầu|nhức\s+đầu|đau\s+dạ\s+dày|đau\s+bao\s+tử|đau\s+thượng\s+vị|đau\s+bụng|cồn\s+cào|ợ\s+chua|ợ\s+hơi|đầy\s+bụng|khó\s+tiêu|trào\s+ngược|viêm\s+dạ\s+dày|sốt|ho|khó\s+thở|đau\s+ngực)/giu, ' ');

  // 0. Acute Focal Neurological Deficits / FAST Stroke -> Brain & Central Nervous System
  if (
    (lower.includes('mờ mắt') || lower.includes('nhìn mờ')) &&
    (lower.includes('líu lưỡi') || lower.includes('nói khó') || lower.includes('nói đớ') || lower.includes('rơi đũa') || lower.includes('yếu tay') || lower.includes('méo miệng') || lower.includes('liệt'))
  ) {
    return {
      key: 'brain',
      name: 'Não bộ & Hệ Thần Kinh',
      notes: 'Cảnh báo dấu hiệu thần kinh khu trú cấp tính (Nghi ngờ Đột quỵ Não / TIA)',
      defaultScore: 35,
      painScore: 7,
    };
  }

  // Acute cardiac chest pain
  if (lower.includes('đau thắt ngực') || lower.includes('đau ngực trái') || (lower.includes('đau ngực') && (lower.includes('lan lên hàm') || lower.includes('khó thở')))) {
    return {
      key: 'cardiovascular',
      name: 'Tim mạch & Tuần hoàn',
      notes: 'Cảnh báo đau ngực cấp tính nghi ngờ Hội chứng Vành Cấp (ACS)',
      defaultScore: 40,
      painScore: 8,
    };
  }

  // 1. Brain & Neurology (Đầu & Thần kinh)

  if (/(đau đầu|nhức đầu|nửa đầu|chóng mặt|choáng|tiền đình|mất ngủ|khó ngủ|căng thẳng|stress|lo âu|co giật|ngất|tai biến|não|thần kinh)/i.test(lower)) {
    return {
      key: 'brain',
      name: 'Não bộ & Thần kinh',
      notes: 'Triệu chứng đau đầu / căng thẳng thần kinh cần theo dõi và nghỉ ngơi',
      defaultScore: 74,
      painScore: 5,
    };
  }

  // 2. Eyes & Vision (Mắt & Thị giác)
  if (/(mắt|mỏi mắt|nhìn mờ|chảy nước mắt|đỏ mắt|thị lực|hoa mắt)/i.test(lower)) {
    return {
      key: 'eyes',
      name: 'Mắt & Thị giác',
      notes: 'Kích ứng / mỏi điều tiết mắt cần giảm căng thẳng màn hình',
      defaultScore: 80,
      painScore: 3,
    };
  }

  // 3. ENT (Tai Mũi Họng)
  if (/(họng|viêm họng|đau họng|rát họng|nuốt đau|ho|sổ mũi|nghẹt mũi|chảy mũi|viêm xoang|tai|ù tai)/i.test(lower)) {
    return {
      key: 'ent',
      name: 'Tai Mũi Họng',
      notes: 'Biểu hiện viêm đường hô hấp trên / nhiễm khuẩn tai mũi họng',
      defaultScore: 70,
      painScore: 4,
    };
  }

  // 4. Cardiovascular (Tim mạch)
  if (/(tim|đau ngực|thắt ngực|hồi hộp|đánh trống ngực|huyết áp|mạch nhanh|nhồi máu)/i.test(lower)) {
    return {
      key: 'cardiovascular',
      name: 'Tim mạch & Tuần hoàn',
      notes: 'Dấu hiệu tim mạch cần theo dõi huyết áp và kiểm tra chuyên khoa',
      defaultScore: 60,
      painScore: 7,
    };
  }

  // 5. Respiratory (Phổi & Hô hấp)
  if (/(phổi|khó thở|hụt hơi|thở khò khè|viêm phế quản|ho đờm|tức ngực khi thở)/i.test(lower)) {
    return {
      key: 'respiratory',
      name: 'Phổi & Hô hấp',
      notes: 'Dấu hiệu kích ứng hoặc viêm đường hô hấp dưới',
      defaultScore: 68,
      painScore: 5,
    };
  }

  // 6. Stomach & Digestive (Dạ dày & Tiêu hóa)
  if (/(dạ dày|thượng vị|ợ chua|ợ nóng|trào ngược|buồn nôn|nôn|đau bụng|tiêu chảy|táo bón|cồn cào|đầy bụng|khó tiêu|tiêu hóa)/i.test(lower)) {
    return {
      key: 'stomach',
      name: 'Dạ Dày & Tiêu Hóa',
      notes: 'Kích ứng niêm mạc dạ dày - tiêu hóa cần điều chỉnh phác đồ',
      defaultScore: 65,
      painScore: 6,
    };
  }

  // 7. Liver (Gan & Mật)
  if (/(gan|men gan|vàng da|vàng mắt|hạ sườn phải|mật|giải độc gan)/i.test(lower)) {
    return {
      key: 'liver',
      name: 'Gan & Mật',
      notes: 'Cần chú ý men gan và đào thải độc chất qua gan',
      defaultScore: 72,
      painScore: 3,
    };
  }

  // 8. Kidney (Thận & Tiết niệu)
  if (/(thận|tiết niệu|tiểu buốt|tiểu rắt|tiểu đêm|đau hông lưng|nước tiểu sẫm)/i.test(lower)) {
    return {
      key: 'kidney',
      name: 'Thận & Tiết Niệu',
      notes: 'Kích ứng hệ tiết niệu cần uống đủ nước và kiểm tra chức năng thận',
      defaultScore: 74,
      painScore: 4,
    };
  }

  // 9. Musculoskeletal (Cơ Xương Khớp)
  if (/(xương|khớp|đau lưng|mỏi gáy|vai gáy|cột sống|thoát vị|thoái hóa|gối|đau cơ)/i.test(lower)) {
    return {
      key: 'musculoskeletal',
      name: 'Cơ Xương Khớp',
      notes: 'Căng cơ hoặc đau mỏi hệ vận động cần giãn cơ và nghỉ ngơi',
      defaultScore: 76,
      painScore: 4,
    };
  }

  // 10. General Systemic / Fever (Toàn thân / Sốt)
  if (/(sốt|nhiệt độ|nóng sốt|mệt mỏi|uể oải|kiệt sức)/i.test(lower)) {
    return {
      key: 'brain',
      name: 'Toàn thân & Thần kinh',
      notes: 'Phản ứng sốt / suy nhược toàn thân cần theo dõi thân nhiệt và bù nước',
      defaultScore: 75,
      painScore: 3,
    };
  }

  return null;
}

/**
 * Extracts numeric VND amount from a sentence.
 * Handles strings like "480.000đ", "12 triệu", "650.000", "50k", "2.5tr"
 * 
 * @param {string} text 
 * @returns {number|null} Amount in VND
 */
export function extractVndAmount(text = '') {
  if (!text) return null;
  const lower = text.toLowerCase();

  // Pattern: "12 triệu" or "12 tr" or "12.5 triệu"
  const millionMatch = lower.match(/\b(\d+(?:[.,]\d+)?)\s*(?:triệu|tr)\b/i);
  if (millionMatch) {
    const val = parseFloat(millionMatch[1].replace(',', '.'));
    return Math.round(val * 1000000);
  }

  // Pattern: "480.000đ" or "480,000 đ" or "480.000 đồng"
  const formattedMatch = lower.match(/\b(\d{1,3}(?:[.,]\d{3})+)\s*(?:đ|đồng|₫|vnd|vnđ)\b/i);
  if (formattedMatch) {
    const rawDigits = formattedMatch[1].replace(/[.,]/g, '');
    return parseInt(rawDigits, 10);
  }

  // Pattern: "480k" or "150 k" or "480 nghìn" or "150 ngàn"
  const thousandMatch = lower.match(/\b(\d+(?:[.,]\d+)?)\s*(?:k|nghìn|ngàn)\b/i);
  if (thousandMatch) {
    const val = parseFloat(thousandMatch[1].replace(',', '.'));
    return Math.round(val * 1000);
  }

  // Pattern: "50000 đ" or "50000 đồng"
  const directMatch = lower.match(/\b(\d{4,9})\s*(?:đ|đồng|₫|vnd|vnđ)\b/i);
  if (directMatch) {
    return parseInt(directMatch[1], 10);
  }

  // Strictly DO NOT extract bare numbers without currency units (prevents "2 vỉ", "14 tháng", "10kg", "1g" false captures)
  return null;
}


/**
 * Core Orchestrator: processUnifiedTopicGatedChat
 * 
 * Takes incoming user text and current application states, classifies the topic,
 * and produces strictly gated mutations ensuring 100% isolation when appropriate.
 * 
 * @param {string} message - User message
 * @param {Object} currentContext - { healthProfile, financialAssessment }
 * @returns {Object} Gated execution outcome with mutated states and audit label
 */
export function processUnifiedTopicGatedChat(message = '', currentContext = {}) {
  const topicMode = classifyTopic(message);
  const label = TOPIC_LABELS[topicMode];
  const lowerMsg = message.toLowerCase();

  const prevHealth = currentContext.healthProfile ? { ...currentContext.healthProfile } : null;
  const prevExpense = currentContext.financialAssessment ? { ...currentContext.financialAssessment } : null;

  let healthMutation = null;
  let expenseMutation = null;
  let explanation = '';

  switch (topicMode) {
    case TOPIC_MODES.HEALTH_OVERVIEW_ONLY: {
      explanation = 'Tin nhắn chỉ liên quan đến tình trạng lâm sàng & cơ thể. Cập nhật Tổng Quan Sức Khoẻ; bảo toàn 100% dữ liệu chi tiêu.';
      // Perform health mutation
      const baseHealth = prevHealth || getDefaultHealthProfile();
      const updatedOrgans = { ...(baseHealth.organs || {}) };
      const updatedVitals = { ...(baseHealth.vitals || {}) };
      let newOverallScore = baseHealth.overall_health_score || 81;
      let adrAlert = baseHealth.adr_alert || null;

      // 1. Detect body temperature if mentioned (e.g., "sốt 38 độ C", "38.5 độ")
      const tempMatch = lowerMsg.match(/(?:sốt|thân nhiệt|nhiệt độ)?\s*([34]\d(?:[.,]\d+)?)\s*(?:độ|°c|c\b)/i);
      if (tempMatch) {
        const tVal = parseFloat(tempMatch[1].replace(',', '.'));
        if (tVal >= 35 && tVal <= 43) {
          updatedVitals.body_temperature_c = tVal;
        }
      }

      // 1. Khử toàn bộ cụm phủ định trước khi kiểm tra từ khóa cơ quan
      const cleanTextWithoutNegation = lowerMsg
        .replace(/\b(không|chẳng|chưa|hết|đã hết|ko)\s+(?:hề\s+|còn\s+)?(?:bị\s+|có\s+|thấy\s+)?(đau\s+đầu|nhức\s+đầu|đau\s+dạ\s+dày|đau\s+bao\s+tử|đau\s+thượng\s+vị|đau\s+bụng|cồn\s+cào|ợ\s+chua|ợ\s+hơi|đầy\s+bụng|khó\s+tiêu|trào\s+ngược|viêm\s+dạ\s+dày|sốt|ho|khó\s+thở|đau\s+ngực)/giu, ' ');

      // 2. Nhận diện trạng thái hoàn toàn khỏe mạnh / hồi phục
      const isHealthyClaim = /\b(hoàn\s+toàn\s+khỏe|khỏe\s+mạnh|hết\s+bệnh|bình\s+thường\s+rồi|khỏi\s+hẳn|không\s+còn\s+triệu\s+chứng|rất\s+khỏe)\b/iu.test(lowerMsg) ||
        (/\b(khỏe|bình\s+thường)\b/iu.test(lowerMsg) && /\b(không\s+đau|không\s+sốt|không\s+bị)\b/iu.test(lowerMsg));

      // 3. Tách riêng trường hợp ADR do Ibuprofen (phải thực sự có từ "ibuprofen" hoặc "nsaid" và đã uống)
      // với trường hợp đau dạ dày thông thường:
      const hasStomachSymptom = /\b(đau\s+dạ\s+dày|đau\s+bao\s+tử|đau\s+thượng\s+vị|ợ\s+chua|viêm\s+dạ\s+dày|cồn\s+cào)\b/iu.test(cleanTextWithoutNegation);
      const mentionsIbuprofenTaken = /\b(uống\s+ibuprofen|dùng\s+ibuprofen|uống\s+thuốc\s+giảm\s+đau\s+xong|uống\s+nsaid|dùng\s+nsaid)\b/iu.test(cleanTextWithoutNegation) ||
        (/\b(ibuprofen|nsaid)\b/iu.test(cleanTextWithoutNegation) && /\b(uống|dùng|sau\s+khi)\b/iu.test(cleanTextWithoutNegation));

      const affected = isHealthyClaim ? null : detectAffectedOrgan(cleanTextWithoutNegation);
      let detectedOrganMeta = null;

      if (isHealthyClaim) {
        newOverallScore = 96;
        updatedVitals.body_temperature_c = 36.6;
        updatedVitals.vas_pain_score = 0;
        updatedVitals.heart_rate_bpm = 72;
        adrAlert = null;
        Object.keys(updatedOrgans).forEach((k) => {
          updatedOrgans[k] = {
            ...updatedOrgans[k],
            health_score: 96,
            vas_pain_score: 0,
            status: 'normal',
            clinical_notes: 'Khỏe mạnh bình thường. Không ghi nhận triệu chứng bệnh lý.',
          };
        });
        detectedOrganMeta = null;
      } else if (hasStomachSymptom && mentionsIbuprofenTaken) {
        // Chỉ bật cảnh báo ADR Ibuprofen khi bệnh nhân thực sự uống Ibuprofen kèm đau dạ dày
        if (updatedOrgans.stomach) {
          updatedOrgans.stomach = {
            ...updatedOrgans.stomach,
            health_score: 38,
            vas_pain_score: 7,
            status: 'critical',
            clinical_notes: 'Tác dụng phụ NSAID (Ibuprofen) gây viêm niêm mạc thượng vị dạ dày cấp tính.',
          };
        }
        newOverallScore = 66; // 81 -> 66
        updatedVitals.heart_rate_bpm = 96;
        updatedVitals.blood_pressure_systolic = 135;
        updatedVitals.blood_pressure_diastolic = 88;
        updatedVitals.vas_pain_score = 7;
        detectedOrganMeta = { key: 'stomach', name: 'Dạ Dày & Tiêu Hóa', notes: 'Kích ứng niêm mạc thượng vị do thuốc' };
        adrAlert = {
          active: true,
          level: 'danger',
          culprit_drug: 'Ibuprofen (NSAID 400mg)',
          adverse_reaction: 'Đau rát thượng vị cấp, nguy cơ loét hoặc xuất huyết tiêu hóa do uống thuốc lúc đói',
          action_directive: 'DỪNG NGAY IBUPROFEN',
          safe_alternative: 'Uống Esomeprazole (Nexium 40mg) hoặc Phosphalugel gói bảo vệ niêm mạc; dùng Paracetamol nếu còn sốt',
          transfer_emergency_suggested: true,
          detected_at: new Date().toISOString(),
        };
      } else if (hasStomachSymptom) {
        // Đau dạ dày thông thường -> cập nhật cơ quan stomach, KHÔNG gán giả culprit_drug = "Ibuprofen"!
        if (updatedOrgans.stomach) {
          updatedOrgans.stomach = {
            ...updatedOrgans.stomach,
            health_score: 65,
            vas_pain_score: 4,
            status: 'attention',
            clinical_notes: 'Ghi nhận dấu hiệu đau thượng vị dạ dày / ợ chua.',
          };
        }
        newOverallScore = Math.min(newOverallScore, 68);
        updatedVitals.vas_pain_score = 4;
        detectedOrganMeta = { key: 'stomach', name: 'Dạ Dày & Tiêu Hóa', notes: 'Theo dõi đau rát thượng vị' };
      } else if (cleanTextWithoutNegation.includes('sốt cao') || cleanTextWithoutNegation.includes('39.5')) {
        newOverallScore = 55;
        updatedVitals.body_temperature_c = 39.5;
        updatedVitals.heart_rate_bpm = 112;
        detectedOrganMeta = { key: 'brain', name: 'Não bộ & Thần kinh', notes: 'Sốt cao co giật / suy nhược toàn thân' };
      } else if (affected) {
        const k = affected.key;
        if (updatedOrgans[k]) {
          updatedOrgans[k] = {
            ...updatedOrgans[k],
            health_score: affected.defaultScore,
            vas_pain_score: affected.painScore,
            status: 'attention',
            clinical_notes: affected.notes,
          };
        }
        detectedOrganMeta = affected;
        updatedVitals.vas_pain_score = affected.painScore;
        newOverallScore = Math.min(newOverallScore, affected.defaultScore + 2);
      }

      // Safeguard against unrealistic health score collapses:
      // Mild or common symptoms must never drop health score to 0/100 or 8/100
      if (newOverallScore < 35 && !lowerMsg.includes('ngừng tim') && !lowerMsg.includes('hôn mê')) {
        newOverallScore = Math.max(35, newOverallScore);
      }

      healthMutation = {
        ...baseHealth,
        overall_health_score: newOverallScore,
        organs: updatedOrgans,
        vitals: updatedVitals,
        detected_organ: detectedOrganMeta,
        adr_alert: adrAlert,
        raw_message: message,
        last_updated: new Date().toISOString(),
      };
      expenseMutation = null; // 100% unchanged
      break;
    }

    case TOPIC_MODES.EXPENSE_MANAGEMENT_ONLY: {
      explanation = 'Tin nhắn chỉ liên quan đến tài chính, mua thuốc hoặc hạn mức. Cập nhật Quản Lý Chi Tiêu; bảo toàn 100% điểm hệ cơ quan.';
      const baseExpense = prevExpense || {
        total_actual_spend_vnd: 0,
        monthly_budget_target_vnd: 10000000,
        recent_transactions: [],
      };
      const extractedAmount = extractVndAmount(message);
      if (!extractedAmount) {
        // No valid amount with currency unit found; cancel expense mutation
        expenseMutation = null;
        healthMutation = null;
        break;
      }

      let updatedTotalSpend = baseExpense.total_actual_spend_vnd || 0;
      let updatedBudget = baseExpense.monthly_budget_target_vnd || 10000000;
      const updatedTx = [...(baseExpense.recent_transactions || [])];

      // Check for budget declaration vs actual outflow
      const isBudgetDeclaration =
        lowerMsg.includes('ngân sách') ||
        lowerMsg.includes('chỉ tiêu') ||
        lowerMsg.includes('chi tiêu khoảng') ||
        lowerMsg.includes('tiêu khoảng') ||
        lowerMsg.includes('hạn mức') ||
        lowerMsg.includes('kế hoạch') ||
        lowerMsg.includes('mục tiêu') ||
        lowerMsg.includes('dự trù') ||
        lowerMsg.includes('dự định') ||
        (lowerMsg.includes('khoảng') && (lowerMsg.includes('triệu') || lowerMsg.includes('tr')));

      const isActualPurchase =
        lowerMsg.includes('mua') ||
        lowerMsg.includes('hóa đơn') ||
        lowerMsg.includes('thanh toán') ||
        lowerMsg.includes('đã chi') ||
        lowerMsg.includes('hết ') ||
        lowerMsg.includes('vừa mua');

      if (isBudgetDeclaration && extractedAmount) {
        updatedBudget = extractedAmount;
      } else if (isActualPurchase && extractedAmount) {
        // New medicine purchase / invoice
        updatedTotalSpend += extractedAmount;
        const itemName = lowerMsg.includes('nexium') ? 'Thuốc dạ dày Nexium 40mg (GPP)' : 'Hóa đơn chi tiêu y tế GPP';
        updatedTx.unshift({
          id: `tx_${Date.now()}`,
          title: itemName,
          amount_vnd: extractedAmount,
          category: 'medication',
          timestamp: new Date().toISOString(),
          dav_compliant: true,
          bhyt_eligible: lowerMsg.includes('nexium'),
        });
      } else {
        expenseMutation = null;
        healthMutation = null;
        break;
      }

      // Recalculate breakdown
      expenseMutation = {
        ...baseExpense,
        total_actual_spend_vnd: updatedTotalSpend,
        monthly_budget_target_vnd: updatedBudget,
        recent_transactions: updatedTx.slice(0, 20),
        market_optimization_score: 95,
        bhyt_paid_vnd: Math.round(updatedTotalSpend * 0.35),
        eu_gmp_saving_potential_vnd: Math.round(updatedBudget * 0.15),
        last_updated: new Date().toISOString(),
      };

      healthMutation = null; // 100% unchanged
      break;
    }

    case TOPIC_MODES.DUAL_HEALTH_AND_EXPENSE: {
      explanation = 'Tin nhắn kết hợp cả triệu chứng bệnh và chi phí. Đồng bộ kép vào cả 2 phân hệ cùng lúc.';
      // 1. Health update
      const baseHealth = prevHealth || getDefaultHealthProfile();
      const updatedOrgans = { ...(baseHealth.organs || {}) };
      const updatedVitals = { ...(baseHealth.vitals || {}) };
      let newOverallScore = baseHealth.overall_health_score || 81;
      let adrAlert = baseHealth.adr_alert || null;

      if (lowerMsg.includes('thượng vị') || lowerMsg.includes('dạ dày')) {
        if (updatedOrgans.stomach) {
          updatedOrgans.stomach = {
            ...updatedOrgans.stomach,
            health_score: 45,
            vas_pain_score: 6,
            status: 'warning',
            clinical_notes: 'Đang điều trị viêm dạ dày thượng vị kèm theo dõi đáp ứng thuốc.',
          };
        }
        newOverallScore = 70;
        updatedVitals.vas_pain_score = 6;
      }

      healthMutation = {
        ...baseHealth,
        overall_health_score: newOverallScore,
        organs: updatedOrgans,
        vitals: updatedVitals,
        adr_alert: adrAlert,
        last_updated: new Date().toISOString(),
      };

      // 2. Expense update: Strictly requires extracted currency amount; NO arbitrary 650.000đ fallback!
      const baseExpense = prevExpense || getDefaultFinancialAssessment();
      const extractedAmount = extractVndAmount(message);
      if (extractedAmount && extractedAmount > 0) {
        const updatedTotalSpend = (baseExpense.total_actual_spend_vnd || 0) + extractedAmount;
        const updatedTx = [...(baseExpense.recent_transactions || [])];
        updatedTx.unshift({
          id: `tx_${Date.now()}`,
          title: 'Chi phí khám & mua thuốc theo khai báo',
          amount_vnd: extractedAmount,
          category: 'medication',
          timestamp: new Date().toISOString(),
          dav_compliant: true,
          bhyt_eligible: true,
        });

        expenseMutation = {
          ...baseExpense,
          total_actual_spend_vnd: updatedTotalSpend,
          recent_transactions: updatedTx.slice(0, 20),
          bhyt_paid_vnd: Math.round(updatedTotalSpend * 0.38),
          last_updated: new Date().toISOString(),
        };
      } else {
        expenseMutation = null;
      }
      break;
    }

    case TOPIC_MODES.UNRELATED_NO_STATE_MUTATION:
    default: {
      explanation = 'Hội thoại thông thường không chứa triệu chứng hay giao dịch tài chính. Bảo toàn nguyên vẹn 100% mọi chỉ số.';
      healthMutation = null; // No mutation
      expenseMutation = null; // No mutation
      break;
    }
  }

  return {
    topicMode,
    label,
    explanation,
    healthMutation,
    expenseMutation,
    timestamp: new Date().toISOString(),
  };
}

/**
 * Default fallback health profile adhering to 9 anatomical systems with full Vietnamese names.
 */
export function getDefaultHealthProfile() {
  return {
    overall_health_score: 81,
    health_trend: 'improving',
    active_diagnosis: 'Hồi phục sau sốt virus & kích ứng dạ dày nhẹ',
    adr_alert: null,
    vitals: {
      heart_rate_bpm: 78,
      blood_pressure_systolic: 118,
      blood_pressure_diastolic: 78,
      body_temperature_c: 36.8,
      spo2_percent: 98,
      vas_pain_score: 2,
    },
    organs: {
      brain: { id: 'brain', name: 'Não bộ & Thần kinh', health_score: 96, vas_pain_score: 1, status: 'normal' },
      eyes: { id: 'eyes', name: 'Mắt & Thị giác', health_score: 94, vas_pain_score: 0, status: 'normal' },
      ent: { id: 'ent', name: 'Tai Mũi Họng', health_score: 88, vas_pain_score: 2, status: 'normal' },
      cardiovascular: { id: 'cardiovascular', name: 'Tim mạch & Tuần hoàn', health_score: 92, vas_pain_score: 0, status: 'normal' },
      respiratory: { id: 'respiratory', name: 'Phổi & Hô hấp', health_score: 95, vas_pain_score: 1, status: 'normal' },
      stomach: { id: 'stomach', name: 'Dạ Dày & Tiêu Hóa', health_score: 95, vas_pain_score: 2, status: 'normal' },
      liver: { id: 'liver', name: 'Gan & Mật', health_score: 90, vas_pain_score: 0, status: 'normal' },
      kidney: { id: 'kidney', name: 'Thận & Tiết Niệu', health_score: 93, vas_pain_score: 0, status: 'normal' },
      musculoskeletal: { id: 'musculoskeletal', name: 'Cơ Xương Khớp', health_score: 89, vas_pain_score: 2, status: 'normal' },
    },
  };
}

/**
 * Default fallback financial assessment adhering to DAV, BHYT and Generic EU-GMP specs.
 */
export function getDefaultFinancialAssessment() {
  return {
    total_actual_spend_vnd: 2450000,
    monthly_budget_target_vnd: 10000000,
    bhyt_paid_vnd: 1960000,
    bhyt_coverage_rate: 0.8,
    market_optimization_score: 92,
    eu_gmp_saving_potential_vnd: 420000,
    spending_breakdown: [
      { name: 'Thuốc kê đơn & GPP', value: 45, amount_vnd: 1102500, color: '#10b981' },
      { name: 'Khám & Tư vấn chuyên khoa', value: 35, amount_vnd: 857500, color: '#06b6d4' },
      { name: 'Xét nghiệm & Cận lâm sàng', value: 12, amount_vnd: 294000, color: '#f59e0b' },
      { name: 'Vật tư y tế & Khác', value: 8, amount_vnd: 196000, color: '#8b5cf6' },
    ],
    recent_transactions: [
      { id: 'tx_01', title: 'Khám tổng quát Bệnh viện Đại học Y Dược', amount_vnd: 450000, category: 'doctor', timestamp: '2026-10-23T08:30:00Z', dav_compliant: true, bhyt_eligible: true },
      { id: 'tx_02', title: 'Thuốc Nexium 40mg (Nhà thuốc Long Châu)', amount_vnd: 480000, category: 'medication', timestamp: '2026-10-22T15:20:00Z', dav_compliant: true, bhyt_eligible: true },
      { id: 'tx_03', title: 'Xét nghiệm công thức máu & Men gan', amount_vnd: 520000, category: 'lab', timestamp: '2026-10-20T10:15:00Z', dav_compliant: true, bhyt_eligible: true },
    ],
  };
}
