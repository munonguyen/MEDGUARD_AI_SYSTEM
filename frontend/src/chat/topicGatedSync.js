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
  HEALTH_OVERVIEW_ONLY: 'TỔNG QUAN SỨC KHOẺ • ĐỒNG BỘ CƠ THỂ 3D',
  EXPENSE_MANAGEMENT_ONLY: 'QUẢN LÝ CHI TIÊU • ĐỒNG BỘ HÓA ĐƠN & BHYT',
  DUAL_HEALTH_AND_EXPENSE: 'ĐỒNG BỘ KÉP • SỨC KHOẺ & CHI TIÊU Y TẾ',
  UNRELATED_NO_STATE_MUTATION: 'HỘI THOẠI CHUNG • KHÔNG CẬP NHẬT DỮ LIỆU',
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

  // 3. Expense Intent Signals:
  const expenseKeywords = [
    'mua thuốc', 'mua', 'chi phí', 'hóa đơn', 'ngân sách', 'tiền thuốc', 'thanh toán',
    'nhà thuốc', 'bảo hiểm', 'bhyt', 'tiết kiệm', 'generic', 'eu-gmp',
    'dav', 'kê khai', 'hạn mức', 'đơn giá', 'tổng chi', 'chi tiêu', 'long châu', 'pharmacity', 'an khang'
  ];

  // Regex patterns for financial values e.g. "480.000đ", "12 triệu", "650.000", "500k", "hết 480"
  const moneyPattern = /(?:\d+[\d.,]*\s*(?:đ|đồng|₫|vnd|triệu|nghìn|tr|k)\b|hết\s+\d+|ngân\s+sách|chi\s+\d+)/i;
  const hasExpense = moneyPattern.test(lower) || expenseKeywords.some((sig) => lower.includes(sig));

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
  const millionMatch = lower.match(/(\d+(?:[.,]\d+)?)\s*(?:triệu|tr\b)/i);
  if (millionMatch) {
    const val = parseFloat(millionMatch[1].replace(',', '.'));
    return Math.round(val * 1000000);
  }

  // Pattern: "480.000đ" or "480,000 đ" or "650.000"
  const formattedMatch = lower.match(/(\d{1,3}(?:[.,]\d{3})+)(?:\s*(?:đ|đồng|₫|vnd))?/i);
  if (formattedMatch) {
    const rawDigits = formattedMatch[1].replace(/[.,]/g, '');
    return parseInt(rawDigits, 10);
  }

  // Pattern: "480k" or "150 k"
  const kMatch = lower.match(/(\d+)\s*k\b/i);
  if (kMatch) {
    return parseInt(kMatch[1], 10) * 1000;
  }

  // Fallback: look for "hết X"
  const hetMatch = lower.match(/hết\s+(\d+)(?:\s*(?:đ|đồng|₫|vnd))?/i);
  if (hetMatch) {
    const num = parseInt(hetMatch[1], 10);
    return num < 10000 ? num * 1000 : num;
  }

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

      // Case: Ibuprofen / NSAID gastric pain
      if (lowerMsg.includes('ibuprofen') || (lowerMsg.includes('dạ dày') && (lowerMsg.includes('đau') || lowerMsg.includes('ợ chua')))) {
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
      } else if (lowerMsg.includes('sốt cao') || lowerMsg.includes('39.5')) {
        newOverallScore = 55;
        updatedVitals.body_temperature_c = 39.5;
        updatedVitals.heart_rate_bpm = 112;
      }

      healthMutation = {
        ...baseHealth,
        overall_health_score: newOverallScore,
        organs: updatedOrgans,
        vitals: updatedVitals,
        adr_alert: adrAlert,
        raw_message: message,
        last_updated: new Date().toISOString(),
      };
      expenseMutation = null; // 100% unchanged
      break;
    }

    case TOPIC_MODES.EXPENSE_MANAGEMENT_ONLY: {
      explanation = 'Tin nhắn chỉ liên quan đến tài chính, mua thuốc hoặc hạn mức. Cập nhật Quản Lý Chi Tiêu; bảo toàn 100% điểm hệ cơ quan.';
      const baseExpense = prevExpense || getDefaultFinancialAssessment();
      const extractedAmount = extractVndAmount(message);

      let updatedTotalSpend = baseExpense.total_actual_spend_vnd || 2450000;
      let updatedBudget = baseExpense.monthly_budget_target_vnd || 10000000;
      const updatedTx = [...(baseExpense.recent_transactions || [])];

      // Check for budget setting
      if (lowerMsg.includes('ngân sách') && extractedAmount) {
        updatedBudget = extractedAmount;
      } else if (extractedAmount) {
        // New medicine purchase / invoice
        updatedTotalSpend += extractedAmount;
        const itemName = lowerMsg.includes('nexium') ? 'Thuốc dạ dày Nexium 40mg (GPP)' : 'Hóa đơn nhà thuốc GPP';
        updatedTx.unshift({
          id: `tx_${Date.now()}`,
          title: itemName,
          amount_vnd: extractedAmount,
          category: 'medication',
          timestamp: new Date().toISOString(),
          dav_compliant: true,
          bhyt_eligible: lowerMsg.includes('nexium'),
        });
      }

      // Recalculate breakdown
      expenseMutation = {
        ...baseExpense,
        total_actual_spend_vnd: updatedTotalSpend,
        monthly_budget_target_vnd: updatedBudget,
        recent_transactions: updatedTx.slice(0, 20),
        market_optimization_score: 92,
        bhyt_paid_vnd: Math.round(updatedTotalSpend * 0.35),
        eu_gmp_saving_potential_vnd: 420000,
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

      // 2. Expense update
      const baseExpense = prevExpense || getDefaultFinancialAssessment();
      const extractedAmount = extractVndAmount(message) || 650000;
      const updatedTotalSpend = (baseExpense.total_actual_spend_vnd || 2450000) + extractedAmount;
      const updatedTx = [...(baseExpense.recent_transactions || [])];
      updatedTx.unshift({
        id: `tx_${Date.now()}`,
        title: 'Khám thượng vị dạ dày & Mua thuốc điều trị',
        amount_vnd: extractedAmount,
        category: 'doctor',
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
