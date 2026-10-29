/**
 * Holistic Health Engine for MedGuard AI 3D (/view=health)
 * - Parses any patient symptom, disease, or subjective feeling in Vietnamese
 * - Synchronizes all 9 anatomical organs, 6 vitals, 4 wellbeing metrics, and clinical timeline
 * - Computes Episodic Health Analytics across 4 timeframes (HOUR, DAY, WEEK, MONTH) in 3 clinical batches (Đợt 1, Đợt 2, Đợt 3)
 * - Generates 4-Pillar Personalized Health Solutions focused on actionable care
 */

export const QUICK_FEELING_CHIPS = [
  {
    id: 'stress_insomnia',
    label: 'Đau đầu căng thẳng, mất ngủ & mỏi mắt',
    text: 'Hôm nay tôi thấy đau đầu âm ỉ, căng thẳng stress, mất ngủ cả đêm và mỏi mắt nhìn mờ',
  },
  {
    id: 'stomach_adr',
    label: 'Đau rát thượng vị dạ dày & buồn nôn sau uống thuốc',
    text: 'Tôi uống thuốc giảm đau xong thấy đau rát thượng vị dạ dày dữ dội, ợ chua và buồn nôn',
  },
  {
    id: 'fever_cough',
    label: 'Sốt 38.9°C, ho rát họng & tức ngực mệt lả',
    text: 'Tôi đang sốt 38.9 độ, ho đờm rát họng, hơi tức ngực khó thở nhẹ và người mệt lả kiệt sức',
  },
  {
    id: 'neck_back_fatigue',
    label: 'Đau mỏi vai gáy, nhức lưng & thiếu nước',
    text: 'Ngồi làm việc lâu cảm giác đau mỏi cổ vai gáy, nhức thắt lưng, khô miệng khát nước và uể oải',
  },
  {
    id: 'feeling_recovered',
    label: 'Cảm thấy khỏe hơn, hết đau & ngủ ngon',
    text: 'Hôm nay tôi cảm thấy khỏe hơn nhiều, đã cắt sốt, hết đau đầu, ăn uống tốt và ngủ sâu giấc',
  },
];

const ORGAN_ID_ALIASES = {
  brain: 'head',
  head: 'head',
  eyes: 'head',
  ent: 'ent',
  respiratory: 'lungs',
  lungs: 'lungs',
  cardiovascular: 'cardiovascular',
  heart: 'cardiovascular',
  stomach: 'stomach',
  liver: 'liver',
  kidney: 'kidneys',
  kidneys: 'kidneys',
  musculoskeletal: 'spine_joints',
  spine_joints: 'spine_joints',
  skin: 'skin',
};

export function normalizeOrgansArray(organsInput, fallbackOrgans = []) {
  if (Array.isArray(organsInput) && organsInput.length > 0) {
    return organsInput.map((o) => ({ ...o }));
  }
  if (organsInput && typeof organsInput === 'object') {
    const base = fallbackOrgans.map((o) => ({ ...o }));
    for (const [key, val] of Object.entries(organsInput)) {
      if (!val || typeof val !== 'object') continue;
      const mappedId = ORGAN_ID_ALIASES[key] || key;
      const idx = base.findIndex((o) => o.id === mappedId);
      if (idx !== -1) {
        base[idx] = {
          ...base[idx],
          health_score: val.health_score ?? base[idx].health_score,
          pain_level: val.vas_pain_score ?? val.pain_level ?? base[idx].pain_level,
          status:
            val.status === 'critical'
              ? 'adverse_reaction'
              : val.status === 'warning'
              ? 'inflamed'
              : val.status || base[idx].status,
          clinical_notes: val.clinical_notes || base[idx].clinical_notes,
        };
      }
    }
    return base;
  }
  return fallbackOrgans.map((o) => ({ ...o }));
}

export function evaluateHolisticHealthInput(currentProfile, rawMessage = '', fallbackDefaultProfile = null) {
  const base = currentProfile || fallbackDefaultProfile || {};
  const fallbackOrgans = fallbackDefaultProfile?.organs || base.organs || [];
  const organs = normalizeOrgansArray(base.organs, fallbackOrgans);

  const text = (rawMessage || '').trim();
  const lower = text.toLowerCase();
  if (!text) return { ...base, organs };

  const vitals = {
    heart_rate_bpm: base.vitals?.heart_rate_bpm ?? 74,
    blood_pressure_systolic: base.vitals?.blood_pressure_systolic ?? 118,
    blood_pressure_diastolic: base.vitals?.blood_pressure_diastolic ?? 76,
    temperature_celsius: base.vitals?.temperature_celsius ?? base.vitals?.body_temperature_c ?? 36.8,
    spo2_percent: base.vitals?.spo2_percent ?? 98,
    overall_pain_level: base.vitals?.overall_pain_level ?? base.vitals?.vas_pain_score ?? 0,
    vas_pain_score: base.vitals?.vas_pain_score ?? base.vitals?.overall_pain_level ?? 0,
  };

  const wellbeing = {
    sleep_quality_score: base.wellbeing?.sleep_quality_score ?? 88,
    stress_level_label: base.wellbeing?.stress_level_label ?? 'Thấp (Ổn định)',
    energy_battery_percent: base.wellbeing?.energy_battery_percent ?? 90,
    hydration_balance_percent: base.wellbeing?.hydration_balance_percent ?? 92,
    detected_feelings: [...(base.wellbeing?.detected_feelings || ['Thể trạng cân bằng'])],
  };

  const updateOrgan = (organId, patch) => {
    const idx = organs.findIndex((o) => o.id === organId);
    if (idx === -1) return;
    const prev = organs[idx];
    const mergedSymptoms = patch.symptoms
      ? Array.from(new Set([...(prev.symptoms || []), ...patch.symptoms]))
      : prev.symptoms || [];
    organs[idx] = {
      ...prev,
      ...patch,
      symptoms: mergedSymptoms,
    };
  };

  const matchedTags = [];
  const directives = new Set(base.clinical_directives || []);
  const activeMeds = new Set(base.active_medications || []);
  const stoppedMeds = new Set(base.discontinued_medications || []);
  let safeGuardrailAlert = base.safe_guardrail_alert || null;
  let adrAlert = base.adr_alert || null;
  let detectedEvent = 'holistic_update';

  // Extract explicit temperature if mentioned (e.g., 38.5, 39.2 độ)
  const tempMatch = lower.match(/(3[6-9](?:[.,]\d)?|40(?:[.,]\d)?)\s*(?:độ|°c|c\b)/i);
  if (tempMatch) {
    const parsedTemp = parseFloat(tempMatch[1].replace(',', '.'));
    if (!isNaN(parsedTemp)) {
      vitals.temperature_celsius = parsedTemp;
    }
  }

  // 1. Recovery / Positive feeling signals
  const isRecovery =
    /(khỏe hơn|đỡ nhiều|hết sốt|cắt sốt|hết đau|đỡ đau|hồi phục|ngủ ngon|ngủ sâu|dễ chịu hơn|khỏi bệnh|bình thường trở lại|hoàn toàn khỏe|khỏe mạnh|rất khỏe|không có triệu chứng|hết bệnh)/i.test(lower) &&
    !/(không đỡ|chưa đỡ|vẫn đau|vẫn sốt)/i.test(lower);

  const cleanWithoutNegation = lower.replace(
    /\b(không|chẳng|chưa|hết|đã hết|ko)\s+(?:hề\s+|còn\s+)?(?:bị\s+|có\s+|thấy\s+)?(đau\s+đầu|nhức\s+đầu|đau\s+dạ\s+dày|đau\s+bao\s+tử|đau\s+thượng\s+vị|đau\s+bụng|cồn\s+cào|ợ\s+chua|ợ\s+hơi|đầy\s+bụng|khó\s+tiêu|trào\s+ngược|viêm\s+dạ\s+dày|sốt|ho|khó\s+thở|đau\s+ngực)/giu,
    ' '
  );

  if (isRecovery) {
    detectedEvent = 'recovery';
    matchedTags.push('Hồi phục tích cực & cải thiện thể trạng');
    vitals.temperature_celsius = 36.7;
    vitals.heart_rate_bpm = 72;
    vitals.blood_pressure_systolic = 118;
    vitals.blood_pressure_diastolic = 76;
    vitals.spo2_percent = 99;
    vitals.overall_pain_level = 0;
    vitals.vas_pain_score = 0;

    wellbeing.sleep_quality_score = 92;
    wellbeing.stress_level_label = 'Thấp (Thư giãn)';
    wellbeing.energy_battery_percent = 94;
    wellbeing.hydration_balance_percent = 95;
    wellbeing.detected_feelings = ['Cảm thấy khỏe khoắn', 'Ngủ sâu giấc', 'Tinh thần minh mẫn'];

    organs.forEach((o, idx) => {
      organs[idx] = {
        ...o,
        status: 'normal',
        health_score: 96,
        pain_level: 0,
        inflammation_level: 'none',
        symptoms: [],
        warning: null,
        is_adverse_reaction: false,
        clinical_notes: 'Đã hồi phục ổn định theo ghi nhận mới nhất từ người bệnh.',
      };
    });

    safeGuardrailAlert = null;
    adrAlert = null;
    directives.clear();
    directives.add('Ngừng thuốc giảm đau/hạ sốt khi các triệu chứng cấp tính đã chấm dứt hoàn toàn');
    directives.add('Duy trì uống 2 - 2.5 lít nước ấm/ngày và vận động nhẹ 20 phút mỗi sáng');
    directives.add('Tiếp tục theo dõi biểu đồ sức khoẻ Đợt 3 để củng cố miễn dịch bền vững');
  } else {
    // 2. Head / Brain / Eyes / Sleep / Stress / Dizziness feelings
    if (/(đau đầu|nhức đầu|chóng mặt|hoa mắt|tiền đình|mất ngủ|khó ngủ|căng thẳng|stress|lo âu|mỏi mắt|nhìn mờ|nặng đầu)/i.test(cleanWithoutNegation)) {
      matchedTags.push('Thần kinh, Giấc ngủ & Thị giác');
      const isSevereHead = /(dữ dội|như búa bổ|không ngủ được cả đêm|choáng váng)/i.test(cleanWithoutNegation);
      updateOrgan('head', {
        status: isSevereHead ? 'inflamed' : 'monitoring',
        health_score: isSevereHead ? 64 : 75,
        pain_level: isSevereHead ? 6 : 4,
        inflammation_level: isSevereHead ? 'moderate' : 'mild',
        symptoms: [
          ...(cleanWithoutNegation.includes('đau đầu') || cleanWithoutNegation.includes('nhức đầu') ? ['Đau căng đầu'] : []),
          ...(cleanWithoutNegation.includes('chóng mặt') || cleanWithoutNegation.includes('hoa mắt') ? ['Chóng mặt / Choáng nhẹ'] : []),
          ...(cleanWithoutNegation.includes('mất ngủ') || cleanWithoutNegation.includes('khó ngủ') ? ['Rối loạn giấc ngủ'] : []),
          ...(cleanWithoutNegation.includes('mỏi mắt') || cleanWithoutNegation.includes('nhìn mờ') ? ['Mỏi điều tiết mắt'] : []),
        ],
        clinical_notes: 'Ghi nhận cảm giác đau đầu / căng thẳng thần kinh hoặc thiếu ngủ. Cần giảm tải ánh sáng xanh và nghỉ ngơi tĩnh dưỡng.',
        warning: isSevereHead ? 'Theo dõi sát cơn đau đầu kèm huyết áp; tránh thức khuya quá 23h.' : null,
      });
      vitals.overall_pain_level = Math.max(vitals.overall_pain_level, isSevereHead ? 6 : 4);
      vitals.vas_pain_score = vitals.overall_pain_level;
      vitals.heart_rate_bpm = Math.max(vitals.heart_rate_bpm, 84);
      wellbeing.sleep_quality_score = cleanWithoutNegation.includes('mất ngủ') || cleanWithoutNegation.includes('khó ngủ') ? 54 : 68;
      wellbeing.stress_level_label = 'Cao (Căng thẳng thần kinh)';
      wellbeing.energy_battery_percent = Math.min(wellbeing.energy_battery_percent, 62);
      wellbeing.detected_feelings = Array.from(
        new Set([...wellbeing.detected_feelings.filter((f) => f !== 'Thể trạng cân bằng'), 'Căng thẳng / Nặng đầu', 'Thiếu ngủ & mỏi mắt'])
      );
      directives.add('Thực hiện quy tắc 20-20-20 bảo vệ mắt, ngắt thiết bị điện tử 60 phút trước khi ngủ');
      directives.add('Uống trà hoa cúc ấm hoặc tập thở cơ hoành 4-7-8 để hạ nhịp giao cảm và dễ vào giấc ngủ');
    }

    // 3. Stomach / GI / ADR / Nausea / Reflux
    const hasStomachSymptom = /(dạ dày|thượng vị|ợ chua|ợ nóng|trào ngược|buồn nôn|đau bụng|cồn cào|đầy hơi|khó tiêu|tiêu chảy|viêm dạ dày)/i.test(cleanWithoutNegation);
    const mentionsIbuprofenTaken = /(uống\s+ibuprofen|dùng\s+ibuprofen|uống\s+thuốc\s+giảm\s+đau\s+xong|uống\s+nsaid|dùng\s+nsaid)/i.test(cleanWithoutNegation) ||
      (/(ibuprofen|nsaid)/i.test(cleanWithoutNegation) && /(uống|dùng|sau\s+khi)/i.test(cleanWithoutNegation));
    const isAdr = hasStomachSymptom && mentionsIbuprofenTaken;

    if (hasStomachSymptom) {
      matchedTags.push('Dạ dày & Hệ tiêu hoá');
      if (isAdr) detectedEvent = 'adr_detected';
      updateOrgan('stomach', {
        status: isAdr ? 'adverse_reaction' : 'inflamed',
        health_score: isAdr ? 42 : 62,
        pain_level: isAdr ? 7 : 5,
        inflammation_level: isAdr ? 'severe' : 'moderate',
        is_adverse_reaction: isAdr,
        symptoms: [
          ...(cleanWithoutNegation.includes('thượng vị') || cleanWithoutNegation.includes('dạ dày') ? ['Đau rát thượng vị dạ dày'] : []),
          ...(cleanWithoutNegation.includes('ợ chua') || cleanWithoutNegation.includes('ợ nóng') || cleanWithoutNegation.includes('trào ngược') ? ['Trào ngược axit / Ợ chua'] : []),
          ...(cleanWithoutNegation.includes('buồn nôn') ? ['Buồn nôn kích ứng niêm mạc'] : []),
          ...(cleanWithoutNegation.includes('đầy hơi') || cleanWithoutNegation.includes('khó tiêu') ? ['Chướng bụng khó tiêu'] : []),
        ],
        clinical_notes: isAdr
          ? 'CẢNH BÁO ADR: Tổn thương kích ứng niêm mạc dạ dày cấp tính liên quan thuốc giảm đau/kháng viêm.'
          : 'Đang có biểu hiện tăng tiết axit và viêm kích ứng niêm mạc dạ dày - tá tràng.',
        warning: isAdr ? 'NGỪNG NGAY thuốc giảm đau kháng viêm NSAID/Ibuprofen!' : 'Chia nhỏ bữa ăn, tránh đồ chua cay và cà phê khi bụng rỗng.',
      });
      vitals.overall_pain_level = Math.max(vitals.overall_pain_level, isAdr ? 7 : 5);
      vitals.vas_pain_score = vitals.overall_pain_level;
      wellbeing.energy_battery_percent = Math.min(wellbeing.energy_battery_percent, 58);
      wellbeing.detected_feelings = Array.from(
        new Set([...wellbeing.detected_feelings.filter((f) => f !== 'Thể trạng cân bằng'), 'Đau rát vùng thượng vị', 'Cồn cào & buồn nôn'])
      );
      if (isAdr) {
        stoppedMeds.add('Ibuprofen / NSAID (Ngừng khẩn cấp do gây kích ứng đau rát thượng vị dạ dày)');
        activeMeds.add('Esomeprazole 40mg / Hỗn dịch bao niêm mạc dạ dày (Theo chỉ định bảo vệ niêm mạc)');
        safeGuardrailAlert = {
          alert_level: 'danger',
          title: 'CẢNH BÁO AN TOÀN THUỐC (ADR): Đau rát thượng vị dạ dày cấp',
          cause_identified: 'Kích ứng niêm mạc dạ dày do hoạt chất kháng viêm hoặc tăng tiết axit cấp tính.',
          contraindicated_item: 'Thuốc giảm đau kháng viêm NSAID (Ibuprofen, Aspirin, Diclofenac) uống lúc đói',
          required_action: 'DỪNG NGAY liều thuốc kháng viêm cũ để ngăn nguy cơ xuất huyết tiêu hoá.',
          alternative_recommendation: 'Sử dụng gói trung hòa axit (Phosphalugel/Almagate) hoặc PPI (Esomeprazole) và ăn cháo ấm dễ tiêu.',
          seek_emergency: false,
        };
        adrAlert = {
          active: true,
          severity: 'CRITICAL',
          title: 'Phản ứng có hại của thuốc (ADR): Viêm rát thượng vị dạ dày',
          action_directive: 'DỪNG NGAY NSAID / IBUPROFEN',
          safe_alternative: 'Bảo vệ niêm mạc bằng Phosphalugel / Esomeprazole 40mg, chuyển sang Paracetamol nếu cần hạ sốt.',
        };
      }
      directives.add('Tuyệt đối không dùng thuốc giảm đau kháng viêm khi bụng đói; ưu tiên thức ăn mềm ấm');
      directives.add('Kê cao đầu giường 15-20cm và không nằm ngay trong vòng 2 giờ sau ăn để chống trào ngược');
    }

    // 4. ENT & Lungs / Respiratory / Fever / Cough
    if (/(ho|rát họng|đau họng|sổ mũi|nghẹt mũi|viêm xoang|khó thở|tức ngực|hụt hơi|khò khè|viêm phổi|sốt)/i.test(cleanWithoutNegation)) {
      matchedTags.push('Hô hấp & Tai Mũi Họng');
      const hasFever = cleanWithoutNegation.includes('sốt') || vitals.temperature_celsius >= 38.0;
      const hasDyspnea = /(khó thở|hụt hơi|tức ngực|khò khè)/i.test(cleanWithoutNegation);
    if (hasFever && vitals.temperature_celsius < 38.3) {
      vitals.temperature_celsius = lower.includes('sốt cao') ? 39.2 : 38.5;
    }
    if (hasDyspnea) {
      vitals.spo2_percent = Math.min(vitals.spo2_percent, 95);
      vitals.heart_rate_bpm = Math.max(vitals.heart_rate_bpm, 98);
    }
    if (/(ho|rát họng|đau họng|sổ mũi|nghẹt mũi|viêm xoang|sốt)/i.test(lower)) {
      updateOrgan('ent', {
        status: 'inflamed',
        health_score: 68,
        pain_level: 4,
        inflammation_level: 'moderate',
        symptoms: [
          ...(lower.includes('rát họng') || lower.includes('đau họng') ? ['Viêm rát niêm mạc họng'] : []),
          ...(lower.includes('sổ mũi') || lower.includes('nghẹt mũi') ? ['Sung huyết mũi xoang'] : []),
          ...(lower.includes('ho') ? ['Ho kích ứng đường thở trên'] : []),
        ],
        clinical_notes: 'Niêm mạc mũi họng đang sung huyết viêm cấp. Cần súc họng nước muối ấm 0.9% thường xuyên.',
      });
    }
    if (/(ho|khó thở|tức ngực|hụt hơi|khò khè|phổi|đờm)/i.test(lower)) {
      updateOrgan('lungs', {
        status: hasDyspnea ? 'critical' : 'monitoring',
        health_score: hasDyspnea ? 56 : 74,
        pain_level: hasDyspnea ? 6 : 3,
        inflammation_level: hasDyspnea ? 'severe' : 'mild',
        symptoms: [
          ...(lower.includes('ho') ? ['Ho phế quản / Tăng tiết đờm'] : []),
          ...(hasDyspnea ? ['Tức ngực / Khó thở khi gắng sức'] : []),
        ],
        clinical_notes: hasDyspnea
          ? 'Cảnh báo co thắt phế quản hoặc ứ đọng dịch tiết đường hô hấp dưới. Cần theo dõi sát SpO2.'
          : 'Phế quản nhạy cảm, cần giữ ấm vùng cổ ngực và uống nhiều nước ấm loãng đờm.',
        warning: hasDyspnea ? 'Theo dõi sát SpO2; nếu SpO2 < 94% hoặc khó thở tăng nhanh cần đến viện ngay.' : null,
      });
    }
    vitals.overall_pain_level = Math.max(vitals.overall_pain_level, hasDyspnea ? 6 : 4);
    vitals.vas_pain_score = vitals.overall_pain_level;
    wellbeing.hydration_balance_percent = Math.min(wellbeing.hydration_balance_percent, 72);
    wellbeing.energy_battery_percent = Math.min(wellbeing.energy_battery_percent, 55);
    wellbeing.detected_feelings = Array.from(
      new Set([...wellbeing.detected_feelings.filter((f) => f !== 'Thể trạng cân bằng'), ...(hasFever ? ['Nóng sốt & ớn lạnh'] : []), ...(hasDyspnea ? ['Tức ngực / Hụt hơi'] : ['Rát họng & ho'])])
    );
    directives.add('Súc họng nước muối sinh lý ấm 3-4 lần/ngày và bù dịch Oresol/nước ấm từng ngụm nhỏ');
    if (hasFever) {
      directives.add('Theo dõi thân nhiệt mỗi 4 giờ; chỉ dùng thuốc hạ sốt khi nhiệt độ >= 38.5°C');
    }
  }

  // 5. Cardiovascular / Palpitations / Blood pressure
  if (/(hồi hộp|đánh trống ngực|tim đập nhanh|tăng huyết áp|huyết áp cao|nhói tim|đau ngực trái)/i.test(lower)) {
    matchedTags.push('Tim mạch & Huyết áp');
    vitals.heart_rate_bpm = Math.max(vitals.heart_rate_bpm, 102);
    vitals.blood_pressure_systolic = Math.max(vitals.blood_pressure_systolic, 138);
    vitals.blood_pressure_diastolic = Math.max(vitals.blood_pressure_diastolic, 88);
    updateOrgan('cardiovascular', {
      status: 'monitoring',
      health_score: 70,
      pain_level: 4,
      inflammation_level: 'mild',
      symptoms: ['Tim đập nhanh / Hồi hộp đánh trống ngực', 'Dao động huyết áp tâm thu'],
      clinical_notes: 'Ghi nhận cảm giác hồi hộp, nhịp tim tăng phản xạ. Cần ngồi nghỉ tĩnh, hít thở sâu và đo lại huyết áp.',
      warning: 'Tránh dùng cà phê, trà đặc hoặc chất kích thích; theo dõi huyết áp 2 lần/ngày.',
    });
    wellbeing.detected_feelings = Array.from(
      new Set([...wellbeing.detected_feelings.filter((f) => f !== 'Thể trạng cân bằng'), 'Hồi hộp đánh trống ngực'])
    );
    directives.add('Ngồi nghỉ tư thế nửa nằm nửa ngồi, đo lại huyết áp sau 15 phút nghỉ tĩnh');
  }

  // 6. Musculoskeletal / Back / Neck / Shoulder / Fatigue / Exhaustion
  if (/(đau lưng|nhức lưng|thắt lưng|vai gáy|cổ vai gáy|đau khớp|mỏi cơ|nhức mỏi|ê ẩm|mệt mỏi|kiệt sức|uể oải|mệt lả)/i.test(lower)) {
    matchedTags.push('Cơ xương khớp & Năng lượng cơ thể');
    updateOrgan('spine_joints', {
      status: 'monitoring',
      health_score: 74,
      pain_level: 4,
      inflammation_level: 'mild',
      symptoms: [
        ...(lower.includes('vai gáy') ? ['Căng cứng cơ cổ vai gáy'] : []),
        ...(lower.includes('lưng') ? ['Đau mỏi cột sống thắt lưng'] : []),
        ...(lower.includes('mệt') || lower.includes('kiệt sức') || lower.includes('uể oải') ? ['Mỏi cơ toàn thân & giảm sức bền'] : []),
      ],
      clinical_notes: 'Căng cơ sinh học hoặc mệt mỏi thể chất. Khuyến nghị chườm ấm 15 phút và giãn cơ nhẹ nhàng.',
    });
    vitals.overall_pain_level = Math.max(vitals.overall_pain_level, 4);
    vitals.vas_pain_score = vitals.overall_pain_level;
    wellbeing.energy_battery_percent = Math.min(wellbeing.energy_battery_percent, 48);
    wellbeing.detected_feelings = Array.from(
      new Set([...wellbeing.detected_feelings.filter((f) => f !== 'Thể trạng cân bằng'), 'Đau mỏi cơ xương khớp', 'Mệt mỏi / Giảm năng lượng'])
    );
    directives.add('Chườm ấm vùng cổ vai gáy / thắt lưng 15 phút và thực hiện bài tập giãn cơ cột sống');
  }

  // 7. Liver / Kidneys / Dehydration / Skin allergy
  if (/(men gan|nóng gan|vàng da|đắng miệng|mẩn ngứa gan|viêm gan)/i.test(lower)) {
    matchedTags.push('Gan & Chuyển hoá');
    updateOrgan('liver', {
      status: 'monitoring',
      health_score: 72,
      pain_level: 2,
      inflammation_level: 'mild',
      symptoms: ['Quá tải chuyển hoá gan / Đắng miệng mệt mỏi'],
      clinical_notes: 'Cần hạn chế thuốc chuyển hoá qua gan và kiểm tra men gan AST/ALT định kỳ.',
    });
  }

  if (/(khát nước|khô miệng|tiểu buốt|tiểu rắt|nước tiểu sẫm|đau hông lưng|thận)/i.test(lower)) {
    matchedTags.push('Thận & Cân bằng nước');
    updateOrgan('kidneys', {
      status: 'monitoring',
      health_score: 76,
      pain_level: lower.includes('tiểu buốt') ? 4 : 2,
      inflammation_level: 'mild',
      symptoms: [
        ...(lower.includes('khát nước') || lower.includes('khô miệng') ? ['Thiếu dịch / Khô miệng khát nước'] : []),
        ...(lower.includes('tiểu buốt') || lower.includes('tiểu rắt') ? ['Kích ứng đường tiết niệu'] : []),
      ],
      clinical_notes: 'Cơ thể có dấu hiệu thiếu dịch hoặc kích ứng tiết niệu. Cần bù ngay 400-500ml nước ấm/điện giải.',
    });
    wellbeing.hydration_balance_percent = 64;
    directives.add('Uống bổ sung ngay 350-500ml nước ấm hoặc dung dịch điện giải Oresol chuẩn');
  }

  if (/(dị ứng|nổi mề đay|phát ban|ngứa da|nổi mẩn|sưng môi)/i.test(lower)) {
    matchedTags.push('Da liễu & Dị ứng miễn dịch');
    detectedEvent = 'adr_detected';
    updateOrgan('skin', {
      status: 'adverse_reaction',
      health_score: 48,
      pain_level: 5,
      inflammation_level: 'severe',
      is_adverse_reaction: true,
      symptoms: ['Nổi mề đay / Phát ban dị ứng cấp', 'Ngứa rát biểu bì'],
      clinical_notes: 'CẢNH BÁO PHẢN ỨNG DỊ ỨNG: Cần ngừng ngay tác nhân/thuốc nghi ngờ và theo dõi sát hô hấp.',
      warning: 'Nếu kèm khó thở, phù mặt hoặc tụt huyết áp cần gọi cấp cứu 115 ngay!',
    });
    directives.add('Ngừng ngay thuốc hoặc thực phẩm vừa dùng nghi gây dị ứng; theo dõi sát dấu hiệu phản vệ');
  }
  }

  // Fallback: if user typed a general feeling/condition not matching specific keywords above, still record it holistically!
  if (!isRecovery && matchedTags.length === 0) {
    matchedTags.push('Ghi nhận cảm giác & triệu chứng tổng quát');
    wellbeing.detected_feelings = Array.from(
      new Set([...wellbeing.detected_feelings.filter((f) => f !== 'Thể trạng cân bằng'), `Cảm nhận: "${text.slice(0, 48)}"`])
    );
    updateOrgan('head', {
      status: 'monitoring',
      health_score: Math.min(organs[0]?.health_score || 88, 82),
      symptoms: [`Ghi nhận từ bệnh nhân: ${text.slice(0, 60)}`],
      clinical_notes: `Đã đồng bộ tự động thông tin bệnh nhân cung cấp: "${text}". Đang theo dõi sát đáp ứng sinh học.`,
    });
    directives.add(`Theo dõi sát diễn tiến cảm giác "${text.slice(0, 50)}" trong 12-24 giờ tới và nghỉ ngơi hợp lý`);
  }

  // Recalculate overall health score from organs & wellbeing
  const avgOrganScore = Math.round(
    organs.reduce((sum, o) => sum + (o.health_score || 85), 0) / Math.max(1, organs.length)
  );
  const penalty = safeGuardrailAlert ? 12 : matchedTags.length >= 2 && !isRecovery ? 6 : 0;
  const overallHealthScore = isRecovery
    ? Math.max(92, avgOrganScore)
    : Math.max(38, Math.min(98, avgOrganScore - penalty));

  const healthTrend = isRecovery
    ? 'improving'
    : safeGuardrailAlert || overallHealthScore < 68
    ? 'deteriorating'
    : 'monitoring';

  const activeDiagnosis = isRecovery
    ? 'Giai đoạn hồi phục tích cực — Sinh hiệu & cảm giác cơ thể ổn định'
    : `Đang theo dõi: ${matchedTags.join(' • ')} (${text.slice(0, 65)}${text.length > 65 ? '...' : ''})`;

  const nowTime = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
  const newTimelinePoint = {
    id: `t_${Date.now()}`,
    timestamp: `Vừa xong (${nowTime})`,
    phase: isRecovery
      ? 'improved_recovering'
      : safeGuardrailAlert
      ? 'adverse_event_escalation'
      : 'symptom_monitoring',
    title: isRecovery
      ? 'Cập nhật Hồi phục & Cải thiện Thể trạng'
      : `Đồng bộ Triệu chứng & Cảm giác (${matchedTags[0] || 'Tổng quát'})`,
    trigger_message: text,
    health_score: overallHealthScore,
    status_label: isRecovery
      ? `Hồi phục tốt (${overallHealthScore}%)`
      : safeGuardrailAlert
      ? 'Cảnh báo An toàn Thuốc'
      : `Điểm thể trạng: ${overallHealthScore}%`,
    clinical_summary: `Hệ thống AI đã tự động phân tích "${text}" và cập nhật đồng bộ vào ${matchedTags.join(', ')}, chỉ số sinh hiệu và phác đồ giải pháp sức khoẻ.`,
    ai_directive: Array.from(directives)[0] || 'Nghỉ ngơi điều độ, uống đủ nước ấm và theo dõi biểu đồ sức khoẻ theo đợt.',
    medications_adjusted: safeGuardrailAlert ? ['Điều chỉnh phác đồ bảo vệ dạ dày / Ngừng NSAID'] : [],
  };

  const updatedTimeline = [newTimelinePoint, ...(base.timeline || [])].slice(0, 12);

  return {
    ...base,
    active_diagnosis: activeDiagnosis,
    overall_health_score: overallHealthScore,
    health_trend: healthTrend,
    vitals,
    wellbeing,
    organs,
    active_medications: Array.from(activeMeds),
    discontinued_medications: Array.from(stoppedMeds),
    clinical_directives: Array.from(directives).slice(0, 6),
    safe_guardrail_alert: safeGuardrailAlert,
    adr_alert: adrAlert,
    timeline: updatedTimeline,
    last_updated: `Vừa cập nhật lúc ${nowTime}`,
    last_sync_message: text,
    detected_event: detectedEvent,
  };
}

/**
 * Generates multi-timeframe episodic health statistics (HOUR, DAY, WEEK, MONTH)
 * grouped into 3 distinct clinical batches (Đợt 1, Đợt 2, Đợt 3 - Hiện tại).
 */
export function computeEpisodicHealthAnalytics(profile, timeframe = 'DAY') {
  const organs = Array.isArray(profile?.organs) ? profile.organs : [];
  const isUnassessed =
    profile?.overall_health_score == null ||
    profile?.overall_health_score === 0 ||
    profile?.health_trend === 'unassessed' ||
    (organs.length > 0 && organs.every((o) => o.status === 'unassessed' || o.health_score == null));

  const configs = {
    HOUR: {
      label: 'Theo Giờ (24h qua)',
      unit: 'Giờ',
      batches: [
        {
          id: 'batch_1',
          code: 'ĐỢT 1',
          name: 'Đợt 1: Khởi phát & Dao động sinh học (00:00 - 08:00)',
          period: '00:00 - 08:00',
          focus: 'Phát hiện sớm triệu chứng về đêm & đánh giá chất lượng giấc ngủ nền',
          solutionSummary: 'Ổn định thân nhiệt ban đêm, kê cao gối và bù 250ml nước ấm ngay khi thức dậy.',
        },
        {
          id: 'batch_2',
          code: 'ĐỢT 2',
          name: 'Đợt 2: Can thiệp & Điều chỉnh thuốc (08:00 - 16:00)',
          period: '08:00 - 16:00',
          focus: 'Đáp ứng thuốc ban ngày, kiểm soát phản ứng phụ dạ dày & giảm căng thẳng',
          solutionSummary: 'Bảo vệ niêm mạc dạ dày sau ăn, nghỉ mắt 20-20-20 và tránh lạm dụng NSAID.',
        },
        {
          id: 'batch_3',
          code: 'ĐỢT 3 (HIỆN TẠI)',
          name: 'Đợt 3: Đánh giá Đáp ứng & Phục hồi (16:00 - Hiện tại)',
          period: '16:00 - Hiện tại',
          focus: 'Tổng hợp triệu chứng/cảm giác mới nhất từ người bệnh & tối ưu phác đồ tối',
          solutionSummary: 'Thực hiện phác đồ giải pháp cá nhân hoá theo đúng triệu chứng vừa khai báo.',
        },
      ],
      labels: ['02:00', '06:00', '10:00', '14:00', '18:00', 'Hiện tại'],
    },
    DAY: {
      label: 'Theo Ngày (7 ngày)',
      unit: 'Ngày',
      batches: [
        {
          id: 'batch_1',
          code: 'ĐỢT 1',
          name: 'Đợt 1: Giai đoạn Khởi phát cấp (Ngày 1 - Ngày 2)',
          period: 'Ngày 1 - 2',
          focus: 'Ghi nhận triệu chứng ban đầu (sốt, đau mỏi, rối loạn tiêu hoá/giấc ngủ)',
          solutionSummary: 'Nghỉ ngơi cách ly tương đối, bù điện giải Oresol và theo dõi sát ngưỡng sốt 38.5°C.',
        },
        {
          id: 'batch_2',
          code: 'ĐỢT 2',
          name: 'Đợt 2: Giai đoạn Can thiệp & Sàng lọc ADR (Ngày 3 - Ngày 5)',
          period: 'Ngày 3 - 5',
          focus: 'Đánh giá hiệu quả đơn thuốc, loại bỏ thuốc gây kích ứng thượng vị dạ dày',
          solutionSummary: 'Ngừng thuốc kháng viêm gây đau dạ dày, chuyển sang phác đồ bảo vệ niêm mạc an toàn.',
        },
        {
          id: 'batch_3',
          code: 'ĐỢT 3 (HIỆN TẠI)',
          name: 'Đợt 3: Giai đoạn Hiện tại & Củng cố (Ngày 6 - Hôm nay)',
          period: 'Ngày 6 - Hôm nay',
          focus: 'Đồng bộ thời gian thực mọi cảm giác/triệu chứng mới nhất của bệnh nhân',
          solutionSummary: 'Duy trì phác đồ 4 trụ cột giải pháp để đẩy nhanh tốc độ phục hồi toàn diện.',
        },
      ],
      labels: ['Ngày 1', 'Ngày 2', 'Ngày 3', 'Ngày 5', 'Ngày 6', 'Hôm nay'],
    },
    WEEK: {
      label: 'Theo Tuần (4 tuần)',
      unit: 'Tuần',
      batches: [
        {
          id: 'batch_1',
          code: 'ĐỢT 1',
          name: 'Đợt 1: Đợt Cấp tính & Biến động Sinh hiệu (Tuần 1 - Tuần 2)',
          period: 'Tuần 1 - 2',
          focus: 'Kiểm soát ổ viêm cấp tính và ngăn ngừa biến chứng đa cơ quan',
          solutionSummary: 'Tuân thủ phác đồ điều trị nguyên nhân và kiểm soát thang đau VAS < 3/10.',
        },
        {
          id: 'batch_2',
          code: 'ĐỢT 2',
          name: 'Đợt 2: Đợt Phục hồi Chức năng Cơ quan (Tuần 3)',
          period: 'Tuần 3',
          focus: 'Tái tạo niêm mạc tiêu hoá, hô hấp và cân bằng nhịp sinh học giấc ngủ',
          solutionSummary: 'Bổ sung dinh dưỡng giàu kẽm/vitamin C, tập thở phục hồi dung tích phổi.',
        },
        {
          id: 'batch_3',
          code: 'ĐỢT 3 (HIỆN TẠI)',
          name: 'Đợt 3: Đợt Đánh giá Tổng quan & Dự phòng (Tuần 4 - Nay)',
          period: 'Tuần 4 - Nay',
          focus: 'Đánh giá tổng thể sức khoẻ hiện tại và lên lịch tiêm chủng/tầm soát',
          solutionSummary: 'Hoàn thành tầm soát định kỳ (Gan, Dạ dày HP, Tim mạch) và tiêm nhắc vắc-xin.',
        },
      ],
      labels: ['Tuần 1 (Đầu)', 'Tuần 1 (Cuối)', 'Tuần 2', 'Tuần 3', 'Tuần 4 (Đầu)', 'Tuần 4 (Nay)'],
    },
    MONTH: {
      label: 'Theo Tháng (6 tháng)',
      unit: 'Tháng',
      batches: [
        {
          id: 'batch_1',
          code: 'ĐỢT 1',
          name: 'Đợt 1: Chu kỳ Nền tảng & Tầm soát Ban đầu (Tháng 1 - Tháng 2)',
          period: 'Tháng 1 - 2',
          focus: 'Thiết lập hồ sơ giải phẫu 9 cơ quan và phát hiện yếu tố nguy cơ tiềm ẩn',
          solutionSummary: 'Xét nghiệm máu tổng quát, men gan AST/ALT và kháng thể Viêm gan B (Anti-HBs).',
        },
        {
          id: 'batch_2',
          code: 'ĐỢT 2',
          name: 'Đợt 2: Chu kỳ Điều chỉnh Lối sống & Miễn dịch (Tháng 3 - Tháng 4)',
          period: 'Tháng 3 - 4',
          focus: 'Giảm tần suất tái phát triệu chứng dạ dày, hô hấp và đau mỏi cột sống',
          solutionSummary: 'Tiêm chủng chủ động, chuẩn hoá công thái học làm việc và chế độ ăn giảm axit.',
        },
        {
          id: 'batch_3',
          code: 'ĐỢT 3 (HIỆN TẠI)',
          name: 'Đợt 3: Chu kỳ Tối ưu Hoá Sức khoẻ Toàn diện (Tháng 5 - Tháng 6)',
          period: 'Tháng 5 - 6 (Hiện tại)',
          focus: 'Theo dõi linh hoạt mọi biểu hiện cơ thể hàng ngày để duy trì thể trạng đỉnh cao',
          solutionSummary: 'Duy trì điểm sức khoẻ mục tiêu > 90% và tái khám định kỳ mỗi 6 tháng.',
        },
      ],
      labels: ['Tháng 1', 'Tháng 2', 'Tháng 3', 'Tháng 4', 'Tháng 5', 'Tháng 6 (Nay)'],
    },
  };

  const cfg = configs[timeframe] || configs.DAY;

  if (isUnassessed) {
    return {
      isUnassessed: true,
      timeframeLabel: cfg.label,
      timeframeUnit: cfg.unit,
      overallDelta: 0,
      batches: [],
      chartSeries: [],
      summary: 'Tài khoản mới: Chưa ghi nhận triệu chứng lâm sàng hoặc chỉ số sinh tồn để lập biểu đồ diễn tiến theo đợt.',
    };
  }

  const currentScore = profile?.overall_health_score ?? 86;
  const currentPain = profile?.vitals?.vas_pain_score ?? profile?.vitals?.overall_pain_level ?? 2;
  const currentTemp = profile?.vitals?.temperature_celsius ?? profile?.vitals?.body_temperature_c ?? 36.8;
  const currentHr = profile?.vitals?.heart_rate_bpm ?? 76;
  const currentSleep = profile?.wellbeing?.sleep_quality_score ?? 84;

  const b1Score = Math.max(45, Math.min(92, currentScore - 12));
  const b2Score = Math.max(50, Math.min(95, Math.round((b1Score + currentScore) / 2) + 2));
  const b3Score = currentScore;

  const series = [
    {
      label: cfg.labels[0],
      batchId: 'batch_1',
      batchCode: 'ĐỢT 1',
      healthScore: Math.max(42, b1Score - 3),
      painScore: Math.min(9, currentPain + 2),
      temperature: Number(Math.min(39.4, currentTemp + 0.6).toFixed(1)),
      heartRate: Math.min(115, currentHr + 10),
      sleepScore: Math.max(45, currentSleep - 16),
    },
    {
      label: cfg.labels[1],
      batchId: 'batch_1',
      batchCode: 'ĐỢT 1',
      healthScore: b1Score,
      painScore: Math.min(9, currentPain + 1),
      temperature: Number(Math.min(39.2, currentTemp + 0.4).toFixed(1)),
      heartRate: Math.min(112, currentHr + 8),
      sleepScore: Math.max(50, currentSleep - 12),
    },
    {
      label: cfg.labels[2],
      batchId: 'batch_2',
      batchCode: 'ĐỢT 2',
      healthScore: Math.max(48, b2Score - 2),
      painScore: Math.max(0, currentPain + 1),
      temperature: Number(Math.min(38.9, currentTemp + 0.2).toFixed(1)),
      heartRate: Math.min(108, currentHr + 5),
      sleepScore: Math.max(55, currentSleep - 8),
    },
    {
      label: cfg.labels[3],
      batchId: 'batch_2',
      batchCode: 'ĐỢT 2',
      healthScore: b2Score,
      painScore: Math.max(0, currentPain),
      temperature: Number(currentTemp.toFixed(1)),
      heartRate: Math.min(105, currentHr + 2),
      sleepScore: Math.max(60, currentSleep - 4),
    },
    {
      label: cfg.labels[4],
      batchId: 'batch_3',
      batchCode: 'ĐỢT 3',
      healthScore: Math.round((b2Score + b3Score) / 2),
      painScore: currentPain,
      temperature: Number(currentTemp.toFixed(1)),
      heartRate: currentHr,
      sleepScore: currentSleep,
    },
    {
      label: cfg.labels[5],
      batchId: 'batch_3',
      batchCode: 'ĐỢT 3',
      healthScore: b3Score,
      painScore: currentPain,
      temperature: Number(currentTemp.toFixed(1)),
      heartRate: currentHr,
      sleepScore: currentSleep,
    },
  ];

  const batches = cfg.batches.map((b, idx) => {
    const pts = series.filter((p) => p.batchId === b.id);
    const avgScore = Math.round(pts.reduce((s, p) => s + p.healthScore, 0) / pts.length);
    const avgPain = Number((pts.reduce((s, p) => s + p.painScore, 0) / pts.length).toFixed(1));
    const avgTemp = Number((pts.reduce((s, p) => s + p.temperature, 0) / pts.length).toFixed(1));
    const avgHr = Math.round(pts.reduce((s, p) => s + p.heartRate, 0) / pts.length);
    const prevAvg = idx === 0 ? avgScore : idx === 1 ? b1Score : b2Score;
    const delta = avgScore - prevAvg;
    return {
      ...b,
      avgScore,
      avgPain,
      avgTemp,
      avgHr,
      delta,
      status: avgScore >= 85 ? 'optimal' : avgScore >= 70 ? 'monitoring' : 'warning',
    };
  });

  return {
    timeframe,
    timeframeLabel: cfg.label,
    series,
    batches,
    overallDelta: b3Score - b1Score,
  };
}

/**
 * Computes 4-Pillar Personalized Health Solutions focused on solving the patient's active problems.
 */
export function computePersonalizedHealthSolutions(profile) {
  const organs = Array.isArray(profile?.organs) ? profile.organs : [];
  const affectedOrgans = organs.filter(
    (o) =>
      o.status !== 'unassessed' &&
      o.health_score !== null &&
      (o.status !== 'normal' || o.health_score < 88)
  );
  const hasAdr = Boolean(profile?.safe_guardrail_alert || profile?.adr_alert?.active || organs.some((o) => o.status === 'adverse_reaction'));
  const temp = profile?.vitals?.temperature_celsius ?? profile?.vitals?.body_temperature_c ?? 36.8;
  const pain = profile?.vitals?.vas_pain_score ?? profile?.vitals?.overall_pain_level ?? 0;
  const sleepScore = profile?.wellbeing?.sleep_quality_score ?? 86;

  const primaryOrganName =
    affectedOrgans[0]?.vietnamese_name || 'Toàn cơ thể & Hệ miễn dịch';

  return [
    {
      id: 'sol_medical_care',
      pillar: '1. Xử Trí Y Khoa & Giảm Triệu Chứng Cấp',
      priority: hasAdr || temp >= 38.5 || pain >= 6 ? 'KHẨN CẤP' : affectedOrgans.length > 0 ? 'ƯU TIÊN CAO' : 'DUY TRÌ',
      priorityLevel: hasAdr || temp >= 38.5 || pain >= 6 ? 'high' : affectedOrgans.length > 0 ? 'medium' : 'normal',
      targetOrgan: primaryOrganName,
      title:
        hasAdr
          ? 'Bảo vệ niêm mạc tiêu hoá & Cắt cơn kích ứng cấp tính'
          : temp >= 38.2
          ? `Kiểm soát thân nhiệt (${temp}°C) & Giảm viêm đường hô hấp`
          : affectedOrgans.length > 0
          ? `Phác đồ giảm đau mỏi & phục hồi chức năng ${primaryOrganName}`
          : 'Duy trì cân bằng sinh hiệu & phòng ngừa bệnh lý theo mùa',
      rationale:
        affectedOrgans[0]?.clinical_notes ||
        'Dựa trên triệu chứng và cảm giác thực tế bạn vừa cập nhật vào hồ sơ sức khoẻ.',
      actionSteps: [
        ...(hasAdr
          ? [
              'Uống ngay gói hỗn dịch bao niêm mạc dạ dày (Phosphalugel/Almagate) hoặc thuốc ức chế bơm proton theo chỉ định.',
              'Chườm ấm nhẹ vùng thượng vị và tuyệt đối không nằm ngay sau khi ăn trong 2 giờ.',
            ]
          : []),
        ...(temp >= 38.0
          ? [
              'Lau mát vùng cổ, nách, bẹn bằng khăn ấm và bù ngay 500ml dung dịch điện giải Oresol.',
              'Súc họng nước muối sinh lý ấm 0.9% tối thiểu 3-4 lần/ngày để giảm tải lượng vi sinh vật.',
            ]
          : []),
        ...( !hasAdr && temp < 38.0
          ? [
              `Nghỉ ngơi tĩnh dưỡng vùng ${primaryOrganName}, thực hiện chườm ấm/giãn cơ nhẹ 15 phút mỗi tối.`,
              'Theo dõi sát thang điểm đau VAS và nhiệt độ cơ thể trong Đợt 3 hiện tại.',
            ]
          : []),
      ],
      expectedOutcome: 'Giảm 50-70% mức độ khó chịu trong 12 - 24 giờ tới',
    },
    {
      id: 'sol_medication_safety',
      pillar: '2. An Toàn Thuốc & Điều Chỉnh Phác Đồ',
      priority: hasAdr ? 'BẮT BUỘC DỪNG CÁCH CŨ' : 'KIỂM SOÁT AN TOÀN',
      priorityLevel: hasAdr ? 'high' : 'medium',
      targetOrgan: 'Dạ dày, Gan & Thận (Đào thải thuốc)',
      title: hasAdr
        ? 'Ngừng ngay thuốc kháng viêm NSAID gây kích ứng & Chuyển thuốc an toàn'
        : 'Tối ưu liều dùng & Phòng ngừa tương tác thuốc đa cơ quan',
      rationale: hasAdr
        ? 'Hệ thống phát hiện dấu hiệu phản ứng phụ (ADR) trên đường tiêu hoá/da liễu.'
        : 'Bảo vệ tế bào gan và cầu thận khỏi quá tải chuyển hoá hoạt chất.',
      actionSteps: [
        hasAdr
          ? 'DỪNG NGAY Ibuprofen / Aspirin / Diclofenac uống lúc đói; chỉ dùng Paracetamol (cách tối thiểu 4-6h) nếu thật sự sốt >= 38.5°C.'
          : 'Không tự ý phối hợp nhiều thuốc giảm đau hạ sốt cùng hoạt chất Paracetamol (> 3000mg/24h gây độc gan).',
        'Uống thuốc với tối thiểu 200ml nước lọc ấm; tránh uống thuốc cùng trà đặc, cà phê hoặc sữa.',
      ],
      expectedOutcome: 'Loại trừ 95% nguy cơ loét xuất huyết dạ dày và tăng men gan do thuốc',
    },
    {
      id: 'sol_lifestyle_recovery',
      pillar: '3. Phục Hồi Thể Trạng, Giấc Ngủ & Dinh Dưỡng',
      priority: sleepScore < 75 ? 'CẦN CẢI THIỆN NGAY' : 'TỐI ƯU HÓA',
      priorityLevel: sleepScore < 75 ? 'medium' : 'normal',
      targetOrgan: 'Thần kinh Trung ương & Năng lượng Cơ thể',
      title:
        sleepScore < 75
          ? 'Phác đồ phục hồi giấc ngủ sâu & Giảm căng thẳng thần kinh'
          : 'Chế độ dinh dưỡng kháng viêm & Bù nước - Điện giải chuẩn y khoa',
      rationale: `Chất lượng giấc ngủ hiện tại (${sleepScore}/100) và mức năng lượng cơ thể tác động trực tiếp tới tốc độ lành bệnh.`,
      actionSteps: [
        'Ưu tiên thức ăn mềm ấm dễ tiêu (cháo yến mạch, súp gà, rau xanh đậm), chia nhỏ 4-5 bữa/ngày.',
        'Uống đủ 2.0 - 2.5 lít nước ấm/ngày; ngắt màn hình xanh 45 phút trước khi ngủ và tập thở cơ hoành 4-7-8.',
      ],
      expectedOutcome: 'Nâng điểm giấc ngủ & năng lượng cơ thể thêm +15% sau 3 ngày',
    },
    {
      id: 'sol_next_batch_screening',
      pillar: '4. Lộ Trình Theo Dõi & Tầm Soát Đợt Kế Tiếp',
      priority: 'CHỦ ĐỘNG DỰ PHÒNG',
      priorityLevel: 'normal',
      targetOrgan: 'Gan, Dạ dày & Hệ Tim Phổi',
      title: 'Kế hoạch kiểm tra đánh giá lại sau 48h & Tầm soát rủi ro dài hạn',
      rationale: 'Kết nối dữ liệu thống kê giữa các Đợt (Giờ / Ngày / Tuần / Tháng) để ngăn bệnh tái phát.',
      actionSteps: [
        'Cập nhật lại cảm giác cơ thể vào khung khai báo hoặc phòng Chat sau 12 - 24 giờ để AI so sánh tiến độ Đợt 3.',
        'Thực hiện tiêm phòng vắc-xin Viêm gan B (nếu Anti-HBs âm tính) và tầm soát vi khuẩn HP dạ dày định kỳ.',
      ],
      expectedOutcome: 'Thiết lập lá chắn miễn dịch chủ động & ngăn ngừa biến chứng mạn tính',
    },
  ];
}

/**
 * Role-based Access Control (RBAC) for Personal Data Management Pages.
 * Only authenticated users (!isGuest && Boolean(account)) can access personal health/spending/schedule/medication management.
 */
export function checkDataPageAccess(account, isGuest = false, view = 'health') {
  const protectedViews = new Set(['health', 'spending', 'schedule', 'medication']);
  const isProtected = protectedViews.has(String(view || '').toLowerCase());
  const isAuthenticated = Boolean(account && (account.id || account.email)) && !isGuest;
  return {
    view,
    isProtected,
    allowed: !isProtected || isAuthenticated,
    requiresLogin: isProtected && !isAuthenticated,
    memberLabel: isAuthenticated
      ? account.email || account.display_name || 'Thành viên Đã xác thực'
      : 'Khách (Chưa đăng nhập)',
  };
}

/**
 * Computes multi-chart visual datasets for every section of the Health Twin dashboard:
 * - Section 1: 6-Axis Spider/Radar Bio-Balance + 4 Circular Radial Rings
 * - Section 2: Dual-Spline Area Curve + VAS/Temp Combo Bar-Line coordinates
 * - Section 3: 9-Organ Horizontal Score Ranking + Organ Status Donut Distribution + Semi-circular Future Risk Gauge
 * - Section 4: 4-Pillar Solutions Completion Donut + Expected Recovery Impact Bars
 */
export function computeHolisticVisualChartSuite(profile, completedSolutions = {}) {
  const organs = Array.isArray(profile?.organs) ? profile.organs : [];
  const isUnassessed =
    profile?.overall_health_score == null ||
    profile?.overall_health_score === 0 ||
    profile?.health_trend === 'unassessed' ||
    (organs.length > 0 && organs.every((o) => o.status === 'unassessed' || o.health_score == null));

  const cx = 110;
  const cy = 110;
  const maxR = 72;

  if (isUnassessed) {
    const rawAxes = [
      { id: 'sleep', label: 'Giấc ngủ', shortLabel: 'Giấc ngủ', value: 0, color: '#94a3b8' },
      { id: 'neuro', label: 'An thần', shortLabel: 'Thần kinh', value: 0, color: '#94a3b8' },
      { id: 'energy', label: 'Năng lượng', shortLabel: 'Pin cơ thể', value: 0, color: '#94a3b8' },
      { id: 'hydration', label: 'Điện giải', shortLabel: 'Bù nước', value: 0, color: '#94a3b8' },
      { id: 'immunity', label: 'Miễn dịch', shortLabel: 'Đề kháng', value: 0, color: '#94a3b8' },
      { id: 'circulation', label: 'Tuần hoàn', shortLabel: 'Tim phổi', value: 0, color: '#94a3b8' },
    ];

    const radarAxes = rawAxes.map((axis, idx) => {
      const angle = -Math.PI / 2 + (idx * 2 * Math.PI) / rawAxes.length;
      const x = cx;
      const y = cy;
      const outerX = +(cx + maxR * Math.cos(angle)).toFixed(1);
      const outerY = +(cy + maxR * Math.sin(angle)).toFixed(1);
      const labelX = +(cx + (maxR + 24) * Math.cos(angle)).toFixed(1);
      const labelY = +(cy + (maxR + 20) * Math.sin(angle)).toFixed(1);
      return { ...axis, angle, x, y, outerX, outerY, labelX, labelY, displayValue: '--' };
    });

    const organRanking = [...organs].map((o) => ({
      id: o.id,
      name: o.vietnamese_name || o.name,
      score: null,
      pain: o.pain_level ?? 0,
      status: o.status || 'unassessed',
      color: '#94a3b8',
      riskLevel: 'unassessed',
      riskPct: 0,
    }));

    return {
      isUnassessed: true,
      radarAxes,
      radarPolygonPoints: '',
      radarAverage: null,
      organRanking,
      organDistribution: {
        total: organRanking.length || 9,
        normal: 0,
        warning: 0,
        critical: 0,
        unassessed: organRanking.length || 9,
      },
      solutionsSummary: {
        total: 0,
        completedCount: 0,
        completionPct: 0,
        projectedGain: 0,
        items: [],
      },
    };
  }

  const sleep = Math.max(20, Math.min(100, profile?.wellbeing?.sleep_quality_score ?? 88));
  const energy = Math.max(20, Math.min(100, profile?.wellbeing?.energy_battery_percent ?? 90));
  const hydration = Math.max(20, Math.min(100, profile?.wellbeing?.hydration_balance_percent ?? 92));
  const stressText = String(profile?.wellbeing?.stress_level_label || 'Thấp');
  const neuroCalm = stressText.includes('Cao') ? 52 : stressText.includes('Trung bình') ? 74 : 92;

  const temp = profile?.vitals?.temperature_celsius ?? profile?.vitals?.body_temperature_c ?? 36.6;
  const spo2 = profile?.vitals?.spo2_percent ?? 98;
  const hr = profile?.vitals?.heart_rate_bpm ?? 74;
  const pain = profile?.vitals?.vas_pain_score ?? profile?.vitals?.overall_pain_level ?? 0;

  const immunity = Math.max(35, Math.min(100, Math.round(100 - Math.max(0, temp - 37.0) * 18 - pain * 3)));
  const circulation = Math.max(45, Math.min(100, Math.round(spo2 - Math.max(0, Math.abs(hr - 72) * 0.4))));

  // 1. 6-Axis Radar Chart (center 110, 110, radius 76)
  const rawAxes = [
    { id: 'sleep', label: 'Giấc ngủ', shortLabel: 'Giấc ngủ', value: sleep, color: '#0d9488' },
    { id: 'neuro', label: 'An thần', shortLabel: 'Thần kinh', value: neuroCalm, color: '#2563eb' },
    { id: 'energy', label: 'Năng lượng', shortLabel: 'Pin cơ thể', value: energy, color: '#d97706' },
    { id: 'hydration', label: 'Điện giải', shortLabel: 'Bù nước', value: hydration, color: '#0284c7' },
    { id: 'immunity', label: 'Miễn dịch', shortLabel: 'Đề kháng', value: immunity, color: '#7c3aed' },
    { id: 'circulation', label: 'Tuần hoàn', shortLabel: 'Tim phổi', value: circulation, color: '#10b981' },
  ];

  const radarAxes = rawAxes.map((axis, idx) => {
    const angle = -Math.PI / 2 + (idx * 2 * Math.PI) / rawAxes.length;
    const r = (axis.value / 100) * maxR;
    const x = +(cx + r * Math.cos(angle)).toFixed(1);
    const y = +(cy + r * Math.sin(angle)).toFixed(1);
    const outerX = +(cx + maxR * Math.cos(angle)).toFixed(1);
    const outerY = +(cy + maxR * Math.sin(angle)).toFixed(1);
    const labelX = +(cx + (maxR + 24) * Math.cos(angle)).toFixed(1);
    const labelY = +(cy + (maxR + 20) * Math.sin(angle)).toFixed(1);
    return { ...axis, angle, x, y, outerX, outerY, labelX, labelY, displayValue: axis.value };
  });

  const radarPolygonPoints = radarAxes.map((a) => `${a.x},${a.y}`).join(' ');
  const radarAverage = Math.round(rawAxes.reduce((acc, a) => acc + a.value, 0) / rawAxes.length);

  // 2. 9-Organ Ranking & Status Distribution
  const organRanking = [...organs]
    .map((o) => {
      const score = o.health_score ?? 95;
      const tone =
        o.status === 'adverse_reaction' || score < 60
          ? '#e11d48'
          : o.status === 'inflamed' || score < 85
          ? '#d97706'
          : '#0d9488';
      const riskLevel = o.future_risk?.risk_level || 'low';
      const riskPct = riskLevel === 'high' ? 82 : riskLevel === 'moderate' ? 52 : 22;
      return {
        id: o.id,
        name: o.vietnamese_name || o.name,
        score,
        pain: o.pain_level ?? 0,
        status: o.status || 'normal',
        color: tone,
        riskLevel,
        riskPct,
      };
    })
    .sort((a, b) => a.score - b.score); // lowest score first for immediate attention

  const normalOrgans = organRanking.filter((o) => o.status === 'normal' && o.score >= 85).length;
  const warningOrgans = organRanking.filter((o) => o.status === 'inflamed' || (o.score >= 60 && o.score < 85)).length;
  const criticalOrgans = Math.max(0, organRanking.length - normalOrgans - warningOrgans);

  // 3. 4-Pillar Solutions Progress & Impact Chart
  const solutions = computePersonalizedHealthSolutions(profile);
  const impactWeights = [94, 89, 84, 78];
  const enrichedSolutions = solutions.map((sol, idx) => ({
    ...sol,
    impactScore: impactWeights[idx] || 82,
    completed: Boolean(completedSolutions?.[sol.id]),
  }));
  const completedCount = enrichedSolutions.filter((s) => s.completed).length;
  const completionPct = Math.round((completedCount / Math.max(1, enrichedSolutions.length)) * 100);
  const projectedGain = 8 + completedCount * 4;

  return {
    radarAxes,
    radarPolygonPoints,
    radarAverage,
    organRanking,
    organDistribution: {
      total: organRanking.length || 9,
      normal: normalOrgans,
      warning: warningOrgans,
      critical: criticalOrgans,
    },
    solutionsSummary: {
      total: enrichedSolutions.length,
      completedCount,
      completionPct,
      projectedGain,
      items: enrichedSolutions,
    },
  };
}
