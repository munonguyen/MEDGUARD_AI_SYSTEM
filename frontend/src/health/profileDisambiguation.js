/**
 * MedGuard AI - Patient Profile & Insurance NLP Disambiguation Engine
 * 
 * Features:
 * 1. Strict Self vs Third-Party Disambiguation:
 *    - Detects if medical statements refer to relatives/third-parties (bố, mẹ, con, bác, bạn...)
 *    - Strictly prevents updating user's personal profile if third-party is detected.
 * 2. Self Profile & Insurance Extraction:
 *    - Demographics: Name, DOB, Age, Biological Sex, Phone, Email, Address, Blood Group.
 *    - Vitals: Height, Weight, live BMI calculation (Asian WHO standard).
 *    - Insurance: BHYT number (15 or 10-char), Primary Care Hospital, BHYT Rate (80/95/100%),
 *      BHXH/VssID code, Life Insurance Provider (Prudential, Manulife, Bao Viet, etc.),
 *      Coverage Limit VND.
 *    - Clinical Baseline: Allergies, Chronic Conditions, Regular Medications.
 * 3. Structured Proposal Generation for In-Chat Interactive Confirmation.
 */

// Relative & Third-Party Markers in Vietnamese (Robust unicode word-matching)
const THIRD_PARTY_SUBJECT_PATTERNS = [
  /(?:bố|ba|cha|tía|mẹ|má|ông|bà|cụ|con|con gái|con trai|cháu|bé nhà|anh trai|chị gái|em gái|em trai|chồng|ông xã|vợ|bà xã|bác|chú|cô|dì|thím|dượng)\s+(?:tôi|mình|em|của tôi|của mình|nhà tôi|nhà mình)\b/iu,
  /(?:cho|của)\s+(?:bố|ba|cha|mẹ|má|ông|bà|cụ|con|cháu|anh trai|chị gái|em gái|em trai|chồng|vợ|bác|chú|cô|dì)\b/iu,
  /(?:ông ấy|bà ấy|anh ấy|chị ấy|cô ấy|chú ấy|bác ấy|cháu nó|bé nó|người nhà tôi|người thân tôi|bệnh nhân này|bệnh nhân khác|bạn tôi|đồng nghiệp tôi)\b/iu,
  /\b(?:khám|tư vấn|hỏi|mua thuốc)\s+cho\s+(?:bố|ba|mẹ|má|ông|bà|con|cháu|anh|chị|chồng|vợ|bác|chú|cô|dì)\b/iu
];

// Insurance providers in Vietnam
const LIFE_INSURANCE_PROVIDERS = [
  { name: 'Prudential', regex: /\b(?:prudential)\b/i },
  { name: 'Manulife', regex: /\b(?:manulife)\b/i },
  { name: 'Bảo Việt Nhân Thọ', regex: /\b(?:bảo việt|baoviet)\b/i },
  { name: 'Dai-ichi Life', regex: /\b(?:dai-ichi|daiichi)\b/i },
  { name: 'AIA', regex: /\b(?:aia)\b/i },
  { name: 'Generali', regex: /\b(?:generali)\b/i },
  { name: 'MB Ageas Life', regex: /\b(?:mb ageas|mbageas)\b/i },
  { name: 'Chubb Life', regex: /\b(?:chubb life|chubb)\b/i },
  { name: 'FWD', regex: /\b(?:fwd)\b/i },
  { name: 'Sun Life', regex: /\b(?:sun life|sunlife)\b/i },
  { name: 'PVI Care', regex: /\b(?:pvi|pvi care)\b/i },
  { name: 'Bảo Minh', regex: /\b(?:bảo minh|baominh)\b/i },
  { name: 'Liberty', regex: /\b(?:liberty)\b/i }
];

/**
 * Checks if the message is talking about someone else (relatives/third party).
 */
export function isThirdPartyMessage(text) {
  if (!text || typeof text !== 'string') return { isThirdParty: false };
  const clean = text.trim();

  for (const pattern of THIRD_PARTY_SUBJECT_PATTERNS) {
    const match = clean.match(pattern);
    if (match) {
      return {
        isThirdParty: true,
        matchedSubject: match[0].trim(),
        reason: `Tin nhắn đề cập đến ${match[0].trim()}, không áp dụng cập nhật hồ sơ cá nhân của người dùng.`
      };
    }
  }

  return { isThirdParty: false };
}

/**
 * Calculate Asian WHO BMI Standard
 */
export function calculateBmi(heightCm, weightKg) {
  if (!heightCm || !weightKg || heightCm <= 0 || weightKg <= 0) return null;
  const hM = heightCm / 100;
  const bmi = Number((weightKg / (hM * hM)).toFixed(1));
  let category = 'Bình thường';
  let badgeColor = '#10b981';

  if (bmi < 18.5) {
    category = 'Thiếu cân (Gầy)';
    badgeColor = '#38bdf8';
  } else if (bmi <= 22.9) {
    category = 'Thể trạng cân đối (Chuẩn Châu Á)';
    badgeColor = '#10b981';
  } else if (bmi <= 24.9) {
    category = 'Tiền béo phì (Thừa cân nhẹ)';
    badgeColor = '#f59e0b';
  } else {
    category = 'Béo phì';
    badgeColor = '#ef4444';
  }

  return { bmi, category, badgeColor };
}

/**
 * Parse comma/list string into clean array
 */
function cleanList(val) {
  if (Array.isArray(val)) return val;
  if (!val || typeof val !== 'string') return [];
  return val
    .split(/[,;\n+và]/i)
    .map((s) => s.trim())
    .filter((s) => s && !['không', 'khong', 'none', 'chưa có'].includes(s.toLowerCase()));
}

/**
 * Main Profile & Insurance Intent Extractor & Disambiguator
 * @param {string} text User's message
 * @param {object} currentProfile Existing user profile context
 * @returns {object|null}
 */
export function extractUserProfileProposal(text, currentProfile = {}) {
  if (!text || typeof text !== 'string') return null;
  const clean = text.trim();

  // 1. Strict Third-Party Check
  const tpCheck = isThirdPartyMessage(clean);
  if (tpCheck.isThirdParty) {
    return {
      isThirdParty: true,
      hasProposal: false,
      reason: tpCheck.reason,
      matchedSubject: tpCheck.matchedSubject
    };
  }

  const proposed = {};
  const previewItems = [];
  let foundAny = false;

  // 2. Full Name / Display Name
  // e.g. "Tôi tên là Nguyễn Văn An", "Tên tôi là Trần Thị Mai", "Tên mình: Lê Văn C", "Tôi là Nguyễn An"
  const nameMatch = clean.match(/(?:tôi tên là|tên tôi là|tên mình là|mình tên là|đổi tên(?: tôi)? thành|tôi là)\s+([A-ZÀ-Ỹa-zà-ỹ\s]{2,35})(?:[,.\n]|$|\s+sinh|\s+năm|\s+tuổi|\s+ở|\s+sđt)/iu);
  if (nameMatch && nameMatch[1]) {
    const rawName = nameMatch[1].trim();
    if (!['bác sĩ', 'bác sy', 'bệnh nhân', 'nam', 'nữ', 'người dùng'].includes(rawName.toLowerCase()) && rawName.split(/\s+/).length >= 2) {
      const capName = rawName.split(/\s+/).map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ');
      proposed.display_name = capName;
      previewItems.push({ field: 'display_name', label: 'Họ và tên', value: capName, icon: 'UserRound' });
      foundAny = true;
    }
  }

  // 3. Date of Birth or Age
  // e.g. "sinh ngày 15/08/1990", "sinh ngày 15-08-1990", "sinh năm 1988", "tôi 35 tuổi"
  const dobMatch = clean.match(/(?:sinh ngày|ngày sinh)\s*[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{4})/i);
  if (dobMatch) {
    const parts = dobMatch[1].replace(/-/g, '/').split('/');
    const d = parts[0].padStart(2, '0');
    const m = parts[1].padStart(2, '0');
    const y = parts[2];
    const isoDate = `${y}-${m}-${d}`;
    proposed.dob = isoDate;
    const computedAge = 2026 - parseInt(y, 10);
    proposed.age = computedAge > 0 && computedAge < 130 ? computedAge : null;
    previewItems.push({ field: 'dob', label: 'Ngày sinh & Tuổi', value: `${d}/${m}/${y} (${computedAge} tuổi)`, icon: 'CalendarDays' });
    foundAny = true;
  } else {
    const birthYearMatch = clean.match(/(?:sinh năm|năm sinh)\s*[:\s]*(\d{4})/i);
    if (birthYearMatch) {
      const y = parseInt(birthYearMatch[1], 10);
      const computedAge = 2026 - y;
      if (computedAge > 0 && computedAge < 130) {
        proposed.age = computedAge;
        proposed.dob = `${y}-01-01`;
        previewItems.push({ field: 'age', label: 'Năm sinh / Tuổi', value: `Năm ${y} (${computedAge} tuổi)`, icon: 'CalendarDays' });
        foundAny = true;
      }
    } else {
      const ageMatch = clean.match(/(?:tôi|mình|em)\s+(\d{1,3})\s*tuổi/i);
      if (ageMatch) {
        const ageNum = parseInt(ageMatch[1], 10);
        if (ageNum > 0 && ageNum < 130) {
          proposed.age = ageNum;
          previewItems.push({ field: 'age', label: 'Tuổi', value: `${ageNum} tuổi`, icon: 'CalendarDays' });
          foundAny = true;
        }
      }
    }
  }

  // 4. Biological Sex
  // e.g. "tôi là nam", "giới tính: nữ", "mình là nữ"
  const sexMatch = clean.match(/(?:tôi là|mình là|giới tính(?: là)?)\s*[:\s]*(nam|nữ|nu|khác)/iu);
  if (sexMatch) {
    const rawSex = sexMatch[1].toLowerCase();
    const sexVal = (rawSex === 'nữ' || rawSex === 'nu') ? 'female' : rawSex === 'nam' ? 'male' : 'other';
    proposed.sex = sexVal;
    previewItems.push({ field: 'sex', label: 'Giới tính', value: sexVal === 'female' ? 'Nữ' : sexVal === 'male' ? 'Nam' : 'Khác', icon: 'UserCheck' });
    foundAny = true;
  }

  // 5. Height & Weight (Vitals) & Live BMI
  // e.g. "tôi cao 1m75", "cao 172cm", "nặng 68kg", "cân nặng 70 kg"
  const heightMatch = clean.match(/(?:cao|chiều cao)\s*[:\s]*(1[m|,]?\d{2}|\d{2,3}\s*cm)/i);
  if (heightMatch) {
    let rawH = heightMatch[1].toLowerCase().replace('cm', '').trim();
    if (rawH.includes('m') || rawH.includes(',')) {
      const parts = rawH.replace(',', '.').replace('m', '.').split('.');
      rawH = parseInt(parts[0], 10) * 100 + parseInt(parts[1] || '0', 10);
    } else {
      rawH = parseInt(rawH, 10);
    }
    if (rawH >= 50 && rawH <= 250) {
      proposed.height_cm = rawH;
      foundAny = true;
    }
  }

  const weightMatch = clean.match(/(?:nặng|cân nặng)\s*[:\s]*(\d{2,3}(?:\.\d+)?)\s*(?:kg|kí|cân)?/i);
  if (weightMatch) {
    const rawW = parseFloat(weightMatch[1]);
    if (rawW >= 10 && rawW <= 300) {
      proposed.weight_kg = rawW;
      foundAny = true;
    }
  }

  const finalHeight = proposed.height_cm || currentProfile.height_cm;
  const finalWeight = proposed.weight_kg || currentProfile.weight_kg;
  if (finalHeight && finalWeight) {
    const bmiData = calculateBmi(finalHeight, finalWeight);
    if (bmiData) {
      proposed.bmi = bmiData.bmi;
      previewItems.push({
        field: 'vitals_bmi',
        label: 'Thể trạng & Chỉ số BMI',
        value: `${finalHeight} cm | ${finalWeight} kg (BMI: ${bmiData.bmi} • ${bmiData.category})`,
        icon: 'Scale',
        color: bmiData.badgeColor
      });
    }
  } else if (proposed.height_cm) {
    previewItems.push({ field: 'height_cm', label: 'Chiều cao', value: `${proposed.height_cm} cm`, icon: 'Scale' });
  } else if (proposed.weight_kg) {
    previewItems.push({ field: 'weight_kg', label: 'Cân nặng', value: `${proposed.weight_kg} kg`, icon: 'Scale' });
  }

  // 6. Blood Group
  // e.g. "nhóm máu O+", "tôi nhóm máu B", "nhóm máu AB"
  const bloodMatch = clean.match(/(?:nhóm máu|nhom mau)\s*[:\s]*([ABO][+-]?|AB[+-]?)/i);
  if (bloodMatch) {
    const bType = bloodMatch[1].toUpperCase();
    proposed.blood_type = bType;
    previewItems.push({ field: 'blood_type', label: 'Nhóm máu', value: bType, icon: 'Droplet' });
    foundAny = true;
  }

  // 7. Phone number
  // e.g. "sđt: 0912345678", "số điện thoại của tôi là 0987654321"
  const phoneMatch = clean.match(/(?:sđt|số điện thoại|sdt|phone|liên hệ)\s*[:\s]*(0[35789]\d{8})\b/i);
  if (phoneMatch) {
    proposed.phone = phoneMatch[1];
    previewItems.push({ field: 'phone', label: 'Số điện thoại', value: phoneMatch[1], icon: 'Phone' });
    foundAny = true;
  }

  // 8. BHYT Number (Bảo hiểm Y tế Việt Nam)
  // Format: 15-character code (e.g. DN 4 79 79 12345678, GD 4 01 01 20456789) or 10-digit BHXH number
  const bhytCodeMatch = clean.match(/(?:thẻ\s+)?bhyt(?:\s+của\s+tôi)?(?:\s+là|\s*:\s*|\s+số\s+)?\s*([A-Za-z]{2}\s*\d\s*\d{2}\s*\d{2}\s*\d{8}|\b\d{10}\b)/iu);
  if (bhytCodeMatch) {
    const cleanBhyt = bhytCodeMatch[1].replace(/\s+/g, '').toUpperCase();
    proposed.bhyt_number = cleanBhyt;
    proposed.is_verified = true;
    foundAny = true;
  }

  // BHYT Hospital / Nơi KCB ban đầu
  // e.g. "khám ban đầu tại BV Chợ Rẫy", "KCB ban đầu ở Bệnh viện Bạch Mai"
  const hospMatch = clean.match(/(?:kcb ban đầu|khám ban đầu|nơi kcb|bệnh viện ban đầu|đăng ký tại|tại)\s*[:\s]*([A-ZÀ-Ỹa-zà-ỹ0-9\s.,-]+?)(?:[,.\n]|$|\s+mức hưởng|\s+tỷ lệ|\s+hạn mức)/iu);
  if (hospMatch) {
    let hName = hospMatch[1].trim().replace(/^(?:tại|ở)\s+/i, '').trim();
    if (hName.length >= 3 && !['chưa', 'không'].includes(hName.toLowerCase())) {
      proposed.bhyt_hospital = hName;
      foundAny = true;
    }
  }

  // BHYT Rate (Mức hưởng 80%, 95%, 100%)
  const rateMatch = clean.match(/(?:mức hưởng|tỷ lệ hưởng|hưởng)\s*(\d{2,3})%/iu);
  if (rateMatch) {
    const rateVal = parseInt(rateMatch[1], 10);
    if ([80, 95, 100].includes(rateVal)) {
      proposed.bhyt_rate = rateVal;
      foundAny = true;
    }
  }

  if (proposed.bhyt_number) {
    let bhytDesc = proposed.bhyt_number;
    if (proposed.bhyt_hospital) bhytDesc += ` • ${proposed.bhyt_hospital}`;
    if (proposed.bhyt_rate) bhytDesc += ` (Hưởng ${proposed.bhyt_rate}%)`;
    previewItems.push({ field: 'bhyt_number', label: 'Thẻ BHYT & Nơi KCB', value: bhytDesc, icon: 'CreditCard', verified: true });
  }

  // 9. BHXH / VssID Code (10 digits)
  // e.g. "mã BHXH là 0790901234", "sổ BHXH 0123456789", "VssID 0790901234"
  const bhxhMatch = clean.match(/(?:mã\s+)?bhxh(?:\s+của\s+tôi)?(?:\s+là|\s*:\s*|\s+số\s+)?\s*(\d{10})/iu) ||
                    clean.match(/(?:vssid|sổ bhxh)\s*[:\s]*(\d{10})/iu);
  if (bhxhMatch && bhxhMatch[1] !== proposed.bhyt_number) {
    proposed.bhxh_number = bhxhMatch[1];
    proposed.vssid_status = 'verified';
    previewItems.push({ field: 'bhxh_number', label: 'Mã số BHXH / VssID', value: `${bhxhMatch[1]} (Đã liên kết VssID)`, icon: 'BadgeCheck', verified: true });
    foundAny = true;
  }

  // 10. Commercial / Life Insurance (Bảo hiểm nhân thọ)
  for (const prov of LIFE_INSURANCE_PROVIDERS) {
    if (prov.regex.test(clean)) {
      proposed.life_insurance_provider = prov.name;
      foundAny = true;
      break;
    }
  }

  // Insurance limit / Hạn mức bảo vệ
  // e.g. "hạn mức 300 triệu", "hạn mức 500tr", "hạn mức 1 tỷ"
  const limitMatch = clean.match(/(?:hạn mức|mức bảo vệ|hạn mức bảo lãnh|bảo hiểm)\s*[:\s]*(\d+(?:\.\d+)?)\s*(triệu|tỷ|tr|ty|vnd|đ)/iu);
  if (limitMatch) {
    const num = parseFloat(limitMatch[1]);
    const unit = limitMatch[2].toLowerCase();
    let vndVal = num;
    if (unit.startsWith('triệu') || unit === 'tr') vndVal = num * 1000000;
    else if (unit.startsWith('tỷ') || unit === 'ty') vndVal = num * 1000000000;
    proposed.coverage_limit_vnd = vndVal;
    foundAny = true;
  }

  if (proposed.life_insurance_provider) {
    let insDesc = proposed.life_insurance_provider;
    if (proposed.coverage_limit_vnd) {
      insDesc += ` • Hạn mức ${proposed.coverage_limit_vnd.toLocaleString('vi-VN')} đ/năm`;
    }
    previewItems.push({ field: 'life_insurance', label: 'Bảo hiểm nhân thọ & Sức khỏe', value: insDesc, icon: 'ShieldCheck' });
  }

  // 11. Allergies (Dị ứng thuốc / thức ăn)
  // e.g. "tôi bị dị ứng Penicillin và Paracetamol", "tôi dị ứng với hải sản"
  const allergyMatch = clean.match(/(?:tôi|mình|em)\s+(?:bị\s+)?dị ứng(?:\s+với)?\s+([^.,;\n]+)/iu);
  if (allergyMatch) {
    const allergyList = cleanList(allergyMatch[1]);
    if (allergyList.length > 0) {
      proposed.allergies = allergyList;
      previewItems.push({ field: 'allergies', label: 'Dị ứng thuốc & Dị nguyên', value: allergyList.join(', '), icon: 'AlertTriangle', alert: true });
      foundAny = true;
    }
  }

  // 12. Chronic Conditions (Bệnh nền)
  // e.g. "bệnh nền tăng huyết áp", "tôi có tiền sử đau dạ dày", "tiền sử tăng huyết áp"
  const condMatch = clean.match(/(?:bệnh nền|tiền sử|tiền căn|mắc bệnh|bị bệnh)\s*[:\s]*([^.,;\n]+)/iu) ||
                    clean.match(/(?:tôi|mình|em)\s+(?:bị|có)\s+([^.,;\n]*?(?:tăng huyết áp|tiểu đường|đái tháo đường|dạ dày|hen|tim mạch)[^.,;\n]*)/iu);
  if (condMatch) {
    const condList = cleanList(condMatch[1]);
    if (condList.length > 0) {
      proposed.conditions = condList;
      previewItems.push({ field: 'conditions', label: 'Bệnh nền mãn tính', value: condList.join(', '), icon: 'Activity' });
      foundAny = true;
    }
  }

  // 13. Current Medications
  // e.g. "tôi đang uống thuốc Amlodipine 5mg", "đang dùng Metformin 500mg"
  const medMatch = clean.match(/(?:tôi|mình|em)\s+(?:đang|có)\s+(?:uống|dùng|sử dụng)\s+(?:thuốc\s+)?([^.,;\n]+)/iu);
  if (medMatch) {
    const medList = cleanList(medMatch[1]);
    if (medList.length > 0 && !medMatch[1].includes('rượu') && !medMatch[1].includes('bia')) {
      proposed.current_medications = medList;
      previewItems.push({ field: 'current_medications', label: 'Thuốc đang điều trị', value: medList.join(', '), icon: 'Pill' });
      foundAny = true;
    }
  }

  // 14. Address / City
  // e.g. "địa chỉ ở Quận 1 TP.HCM", "ở Hà Nội"
  const addrMatch = clean.match(/(?:địa chỉ(?: của tôi)?|nhà ở|cư trú tại)\s*[:\s]*([A-ZÀ-Ỹa-zà-ỹ0-9\s,.-]{4,60})/iu);
  if (addrMatch) {
    proposed.address = addrMatch[1].trim();
    previewItems.push({ field: 'address', label: 'Địa chỉ cư trú', value: proposed.address, icon: 'MapPin' });
    foundAny = true;
  }

  if (!foundAny || previewItems.length === 0) {
    return null;
  }

  return {
    isThirdParty: false,
    hasProposal: true,
    proposalId: 'prop_' + Date.now() + '_' + Math.random().toString(36).slice(2, 7),
    timestamp: new Date().toISOString(),
    fields: proposed,
    previewItems,
    summary: `Phát hiện ${previewItems.length} mục thông tin hồ sơ & bảo hiểm.`
  };
}
