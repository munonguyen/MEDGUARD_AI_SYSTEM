// File: src/client/navigation/googlePlacesReputationAndRealtimeNav.ts

export interface GooglePlaceReputation {
  placeId: string;
  rating: number;              // Điểm đánh giá Google Maps (1.0 - 5.0)
  userRatingCount: number;     // Tổng số lượt đánh giá thực tế trên Google Maps
  openNow: boolean;            // Trạng thái mở cửa thời gian thực từ currentOpeningHours.openNow
  is24Hours: boolean;          // Trực 24/7
  verifiedPhone: string | null;// Số điện thoại thực từ nationalPhoneNumber (Không gắn cứng 1800 6928!)
  googleMapsUri: string;
  topReviews: Array<{
    authorName: string;
    rating: number;
    relativeTime: string;
    text: string;
  }>;
}

export interface MedicalFacilityCandidate {
  id: string;
  name: string;
  facilityType: 'pharmacy' | 'emergency_hospital';
  distanceKm: number;
  etaMinutes: number;
  lat: number;
  lng: number;
  emergencyGateName?: string;  // VD: "Cổng Cấp cứu A9 — 78 Giải Phóng"
  hospitalTier?: 'SPECIAL' | 'TIER_1' | 'PRIVATE_INTL' | 'SPECIALTY_GERIATRIC' | 'GPP_CHAIN';
  capabilities: string[];      // VD: ['STROKE_CENTER', 'PCI_24_7', 'PEDIATRIC_ER', 'TRAUMA_LEVEL_1']
  gppVerified: boolean;
  reputation: GooglePlaceReputation;
}

/**
 * 1. Tính điểm Uy tín Bayesian (Bayesian Weighted Rating) kết hợp Năng lực Cấp cứu & Trạng thái Mở cửa 24/7
 * Công thức Bayesian: WR = (v / (v + m)) * R + (m / (v + m)) * C
 * Trong đó: R = rating hiện tại, v = userRatingCount, m = 150 (ngưỡng tin cậy tối thiểu), C = 4.1 (điểm trung bình ngành)
 */
export function computeMedicalTrustScore(
  facility: MedicalFacilityCandidate,
  requiredCapability?: string
): {
  bayesianRating: number;
  trustScore100: number;
  trustBadge: string;
  isRecommendedForCase: boolean;
} {
  const { rating, userRatingCount, openNow, is24Hours } = facility.reputation;
  const m = 150;
  const C = 4.1;
  const bayesianRating = Number(
    ((userRatingCount / (userRatingCount + m)) * rating + (m / (userRatingCount + m)) * C).toFixed(2)
  );

  // Trọng số 1: Điểm Google Maps Bayesian (tối đa 40 điểm)
  const ratingComponent = (bayesianRating / 5.0) * 40;

  // Trọng số 2: Trạng thái mở cửa thực tế lúc khẩn cấp (tối đa 25 điểm)
  const availabilityComponent = openNow ? (is24Hours ? 25 : 18) : 0;

  // Trọng số 3: Khoảng cách & ETA (tối đa 20 điểm)
  const distanceComponent = Math.max(0, 20 - facility.distanceKm * 6);

  // Trọng số 4: Phân hạng bệnh viện / Chuỗi GPP xác thực & Khớp chuyên khoa cấp cứu (tối đa 15 điểm)
  let clinicalCapabilityComponent = 0;
  if (facility.hospitalTier === 'SPECIAL') clinicalCapabilityComponent += 15;
  else if (facility.hospitalTier === 'TIER_1' || facility.gppVerified) clinicalCapabilityComponent += 12;
  else if (facility.hospitalTier === 'PRIVATE_INTL') clinicalCapabilityComponent += 10;

  // Phạt nặng nếu cơ sở không có chuyên khoa cấp cứu mà ca bệnh yêu cầu (VD: Trẻ em vào BV Lão khoa)
  const matchesCapability = !requiredCapability || facility.capabilities.includes(requiredCapability);
  if (!matchesCapability) {
    clinicalCapabilityComponent -= 35;
  }

  const trustScore100 = Math.max(
    5,
    Math.min(99, Math.round(ratingComponent + availabilityComponent + distanceComponent + clinicalCapabilityComponent))
  );

  let trustBadge = 'Chưa xác thực GPP';
  if (trustScore100 >= 90) trustBadge = 'Uy tín Hàng đầu · Khuyên đến';
  else if (trustScore100 >= 75) trustBadge = 'Đạt chuẩn GPP / Cấp cứu xác thực';
  else if (!matchesCapability) trustBadge = 'Trái chuyên khoa cấp cứu';

  return {
    bayesianRating,
    trustScore100,
    trustBadge,
    isRecommendedForCase: trustScore100 >= 80 && openNow && matchesCapability
  };
}

/**
 * 2. Lọc bỏ các node đường giao thông vô danh từ OpenStreetMap ("Nhà thuốc Giai Phong Road")
 */
export function isValidVerifiedMedicalPoiName(rawName: string): boolean {
  const lower = rawName.toLowerCase().trim();
  if (!lower) return false;
  // Loại bỏ các node OSM chỉ ghép tiền tố "Nhà thuốc" với tên đường tiếng Anh ("... Road", "... Street")
  if (/^nhà thuốc\s+[a-z0-9\s]+(road|street|lane|alley|avenue)$/i.test(lower)) {
    return false;
  }
  return true;
}

/**
 * 3. Chuẩn hóa chỉ dẫn điều hướng Turn-by-Turn tiếng Việt 100%
 * Khắc phục triệt để lỗi "Turn left." và "Rẽ trái vào Đoạn đường di chuyển" trong hàm K7 của /static/app.js
 */
export function formatVietnameseManeuverStep(rawInstruction: string, rawRoadName?: string): string {
  const cleanRoad =
    rawRoadName &&
    rawRoadName.trim() !== '' &&
    rawRoadName.trim() !== 'Đoạn đường di chuyển' &&
    rawRoadName.trim() !== 'Unnamed road'
      ? rawRoadName.trim()
      : null;

  let text = (rawInstruction || '').trim();

  const replacements: Array<[RegExp, string]> = [
    [/^Head\s+north/i, 'Đi thẳng về hướng Bắc'],
    [/^Head\s+south/i, 'Đi thẳng về hướng Nam'],
    [/^Head\s+east/i, 'Đi thẳng về hướng Đông'],
    [/^Head\s+west/i, 'Đi thẳng về hướng Tây'],
    [/^Turn\s+left\.?$/i, 'Rẽ trái'],
    [/^Turn\s+right\.?$/i, 'Rẽ phải'],
    [/^Turn\s+slight\s+left\.?$/i, 'Chếch nhẹ sang trái'],
    [/^Turn\s+slight\s+right\.?$/i, 'Chếch nhẹ sang phải'],
    [/^Turn\s+sharp\s+left\.?$/i, 'Rẽ ngoặt sang trái'],
    [/^Turn\s+sharp\s+right\.?$/i, 'Rẽ ngoặt sang phải'],
    [/^Keep\s+left\.?$/i, 'Đi sát làn bên trái'],
    [/^Keep\s+right\.?$/i, 'Đi sát làn bên phải'],
    [/^Make\s+a\s+U-turn\.?$/i, 'Quay đầu xe tại điểm mở dải phân cách'],
    [/^Continue\s+straight\.?$/i, 'Tiếp tục đi thẳng'],
    [/^You\s+have\s+arrived.*/i, 'Đã đến cổng cơ sở y tế bên tay phải']
  ];

  for (const [pattern, viText] of replacements) {
    if (pattern.test(text)) {
      text = text.replace(pattern, viText);
      break;
    }
  }

  // Xóa cụm "vào Đoạn đường di chuyển" vô nghĩa
  text = text.replace(/\s*vào\s+Đoạn đường di chuyển\.?/gi, '');

  if (cleanRoad && !text.toLowerCase().includes(cleanRoad.toLowerCase())) {
    return `${text.replace(/\.$/, '')} vào ${cleanRoad}`;
  }

  return text;
}

/**
 * 4. Luồng Bản đồ Quét Theo Lệnh (On-Demand Radar Scan — Không tự ý ép Điểm đến B mặc định):
 * - Chỉ kích hoạt khi nhận lệnh tìm kiếm từ Chat Bác sĩ AI ('chat_command') hoặc User chủ động bấm Quét ('user_direct_scan').
 * - Trả về NHIỀU địa điểm xung quanh để hiển thị đồng thời các biểu tượng đánh dấu vị trí (staggered pop-in).
 * - Trích xuất đầy đủ đánh giá của các user khác từ Google Maps (places.reviews) để hiển thị khi bấm vào Sao (★).
 */
export async function scanNearbyMedicalPlacesOnDemand(params: {
  userLat: number;
  userLng: number;
  radiusMeters: number;
  keyword?: string;
  category: 'all_nearby' | 'urgent_pharmacy' | 'emergency_hospital';
  triggerSource: 'chat_command' | 'user_direct_scan';
}) {
  const response = await fetch('/v1/geo/google-places-scan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      triggerSource: params.triggerSource,
      center: { latitude: params.userLat, longitude: params.userLng },
      radiusMeters: params.radiusMeters,
      keyword: params.keyword?.trim() || undefined,
      includedTypes:
        params.category === 'urgent_pharmacy'
          ? ['pharmacy']
          : params.category === 'emergency_hospital'
          ? ['hospital']
          : ['pharmacy', 'hospital'],
      fieldMask: [
        'places.id',
        'places.displayName',
        'places.formattedAddress',
        'places.location',
        'places.rating',
        'places.userRatingCount',
        'places.currentOpeningHours',
        'places.nationalPhoneNumber',
        'places.reviews'
      ].join(','),
      languageCode: 'vi',
      regionCode: 'VN',
      maxResultCount: 12
    })
  });

  if (!response.ok) {
    throw new Error(`Lỗi quét địa điểm xung quanh: HTTP ${response.status}`);
  }
  return response.json();
}

