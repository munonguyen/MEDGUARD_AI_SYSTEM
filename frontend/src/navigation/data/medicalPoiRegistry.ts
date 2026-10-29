/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * MedGuard AI - Central Medical POI, Emergency Infrastructure & Google Maps Healthcare Reviews Registry
 */

export interface MedicalCapability {
  code: string;
  name: string;
  isAvailable: boolean;
  highlight?: boolean;
}

export interface OperatingHours {
  is24_7: boolean;
  openTime?: string;
  closeTime?: string;
  description: string;
}

export interface MedicalPlaceReview {
  id: string;
  authorName: string;
  authorRole: string; // e.g., 'Local Guide Cấp 6 • Người nhà bệnh nhân', 'Bệnh nhân đã điều trị'
  avatarColor: string;
  rating: number;
  relativeTime: string;
  serviceTag: string; // e.g., 'Cấp cứu Đột quỵ DSA', 'Can thiệp Tim mạch', 'Mua thuốc kê đơn 24/7'
  comment: string;
  verifiedVisit: boolean;
  helpfulCount: number;
  facilityReply?: {
    responder: string;
    text: string;
    time: string;
  };
}

export interface ClinicalReviewBreakdown {
  emergencySpeedScore: number; // Thời gian tiếp nhận cấp cứu (Door-to-Doctor)
  doctorExpertiseScore: number; // Trình độ chuyên môn & thái độ y bác sĩ
  equipmentModernityScore: number; // Trang thiết bị máy móc / dự trữ thuốc
  insuranceTransparencyScore: number; // Chi phí & hỗ trợ BHYT
  starPercentages: [number, number, number, number, number]; // [5 sao, 4 sao, 3 sao, 2 sao, 1 sao]
}

export interface MedicalFacility {
  id: string;
  googlePlaceId: string;
  name: string;
  facilityType: 'hospital_emergency' | 'pharmacy';
  category: 'stroke' | 'cardiac' | 'trauma' | 'pediatrics' | 'obstetrics' | 'poisoning' | 'general' | 'pharmacy_24h';
  city: 'hcm' | 'hanoi' | 'danang';
  district: string;
  address: string;
  lat: number;
  lng: number;
  phone: string;
  emergencyHotline: string;
  emergencyLevel: 1 | 2 | 3; // 1 = Tuyến Trung Ương / Hạng Đặc Biệt
  operatingHours: OperatingHours;
  capabilities: MedicalCapability[];
  icuBedsAvailable: number;
  ambulanceBaysOpen: number;
  doctorOnDutyCount: number;
  specialtyTag: string;
  rating: number;
  reviewsCount: number;
  goldenHourWindowMinutes?: number;
  accreditationBadge: string;
  avgErWaitMinutes: number;
  patientSatisfactionPercent: number;
  reviewBreakdown: ClinicalReviewBreakdown;
  reviews: MedicalPlaceReview[];
}

export interface CityPreset {
  id: 'hcm' | 'hanoi' | 'danang';
  name: string;
  tag: string;
  centerLat: number;
  centerLng: number;
  defaultZoom: number;
  congestedArteries: string[];
  bypassArteries: string[];
}

export const CITY_PRESETS: Record<string, CityPreset> = {
  hcm: {
    id: 'hcm',
    name: 'TP. Hồ Chí Minh',
    tag: 'Đô thị đặc biệt phía Nam',
    centerLat: 10.7769,
    centerLng: 106.6953,
    defaultZoom: 15,
    congestedArteries: [
      'Đường Cách Mạng Tháng 8',
      'Đường Cộng Hòa',
      'Đường Xô Viết Nghệ Tĩnh',
      'Đường Nguyễn Trãi',
      'Đường Nam Kỳ Khởi Nghĩa',
      'Đường Lý Thường Kiệt',
    ],
    bypassArteries: [
      'Đại lộ Võ Văn Kiệt (Tuyến Vượt Cấp Cứu)',
      'Đại lộ Phạm Văn Đồng',
      'Tuyến Ven Kênh Hoàng Sa - Trường Sa',
      'Tuyến Cầu Thủ Thiêm & Mai Chí Thọ',
    ],
  },
  hanoi: {
    id: 'hanoi',
    name: 'Hà Nội',
    tag: 'Thủ đô & Tuyến Cấp cứu Trung ương',
    centerLat: 21.0285,
    centerLng: 105.8452,
    defaultZoom: 15,
    congestedArteries: [
      'Đường Giải Phóng',
      'Đường Nguyễn Trãi - Thanh Xuân',
      'Đường Đê La Thành',
      'Đường Kim Mã - Cầu Giấy',
      'Phố Huế - Hàng Bài',
    ],
    bypassArteries: [
      'Đường Vành đai 2 trên cao',
      'Đường Vành đai 3 trên cao',
      'Tuyến Yên Phụ - Trần Quang Khải - Trần Khánh Dư',
      'Đại lộ Thăng Long',
    ],
  },
  danang: {
    id: 'danang',
    name: 'Đà Nẵng',
    tag: 'Trung tâm Y tế Miền Trung',
    centerLat: 16.0688,
    centerLng: 108.2125,
    defaultZoom: 15,
    congestedArteries: ['Đường Hùng Vương', 'Đường Điện Biên Phủ', 'Đường Nguyễn Văn Linh'],
    bypassArteries: ['Đường Nguyễn Tất Thành ven biển', 'Đường Bạch Đằng ven sông Hàn'],
  },
};

export const MEDICAL_FACILITIES: MedicalFacility[] = [
  // ==================== TP. HỒ CHÍ MINH ====================
  {
    id: 'fac-cr-hcm',
    googlePlaceId: 'ChIJ0-c9a2e9cudTER_ChoRayHospital',
    name: 'Bệnh viện Chợ Rẫy — Trung tâm Cấp cứu 115 & Đột quỵ Quốc gia',
    facilityType: 'hospital_emergency',
    category: 'stroke',
    city: 'hcm',
    district: 'Quận 5',
    address: '201B Nguyễn Chí Thanh, Phường 12, Quận 5, TP.HCM',
    lat: 10.7578,
    lng: 106.6596,
    phone: '028 3855 4137',
    emergencyHotline: '028 3855 4137',
    emergencyLevel: 1,
    operatingHours: { is24_7: true, description: 'Cấp cứu 24/7/365 liên tục không nghỉ' },
    capabilities: [
      { code: 'STROKE_CATH', name: 'Can thiệp Đột quỵ não DSA khẩn cấp', isAvailable: true, highlight: true },
      { code: 'ICU_TRAUMA', name: 'Hồi sức cấp cứu đa chấn thương hạng I', isAvailable: true, highlight: true },
      { code: 'BLOOD_BANK', name: 'Ngân hàng máu dự trữ khẩn', isAvailable: true },
      { code: 'CT_MRI_247', name: 'Chụp CT/MRI 256 lát cắt 24/7', isAvailable: true },
    ],
    icuBedsAvailable: 14,
    ambulanceBaysOpen: 6,
    doctorOnDutyCount: 22,
    specialtyTag: 'Đột quỵ não & Hồi sức Tối cấp',
    rating: 4.9,
    reviewsCount: 3840,
    goldenHourWindowMinutes: 270,
    accreditationBadge: 'Bệnh viện Hạng Đặc Biệt Tuyến Cuối Bộ Y Tế',
    avgErWaitMinutes: 4,
    patientSatisfactionPercent: 97,
    reviewBreakdown: {
      emergencySpeedScore: 4.9,
      doctorExpertiseScore: 5.0,
      equipmentModernityScore: 4.9,
      insuranceTransparencyScore: 4.7,
      starPercentages: [86, 10, 2, 1, 1],
    },
    reviews: [
      {
        id: 'rev-cr-1',
        authorName: 'Nguyễn Minh Tuấn',
        authorRole: 'Local Guide Cấp 7 • Người nhà bệnh nhân',
        avatarColor: 'bg-blue-600',
        rating: 5,
        relativeTime: '2 ngày trước',
        serviceTag: 'Cấp cứu Đột quỵ DSA',
        comment:
          'Ba tôi bị méo miệng và yếu nửa người lúc 2 giờ sáng. Nhờ chỉ đường vào thẳng cổng cấp cứu Nguyễn Chí Thanh, ekip trực nhận bệnh trong vòng chưa đầy 3 phút, chụp CT và can thiệp lấy huyết khối ngay trong giờ vàng. Ba tôi đã hồi phục hoàn toàn không di chứng.',
        verifiedVisit: true,
        helpfulCount: 142,
        facilityReply: {
          responder: 'Ban Giám đốc & Khoa Cấp cứu BV Chợ Rẫy',
          text: 'Cảm ơn gia đình anh Tuấn đã tin tưởng. Quy trình Báo động đỏ Đột quỵ (Code Stroke) luôn trực chiến 24/7 để bảo vệ từng phút giây não bộ cho người bệnh.',
          time: '1 ngày trước',
        },
      },
      {
        id: 'rev-cr-2',
        authorName: 'Trần Thị Thu Thảo',
        authorRole: 'Bệnh nhân nội trú • Đã xác thực BHYT',
        avatarColor: 'bg-emerald-600',
        rating: 5,
        relativeTime: '1 tuần trước',
        serviceTag: 'Hồi sức Đa chấn thương',
        comment:
          'Các bác sĩ chuyên môn cực kỳ vững, quyết đoán. Tuy lượng bệnh nhân đông nhưng phân luồng cấp cứu ca nặng rất khoa học, ưu tiên tuyệt đối cho xe cứu thương và ca nguy kịch.',
        verifiedVisit: true,
        helpfulCount: 68,
      },
      {
        id: 'rev-cr-3',
        authorName: 'Lê Hoàng Nam',
        authorRole: 'Local Guide Cấp 5',
        avatarColor: 'bg-amber-600',
        rating: 4,
        relativeTime: '2 tuần trước',
        serviceTag: 'Khám & Cấp cứu đêm',
        comment:
          'Bác sĩ đầu ngành giỏi nhất khu vực phía Nam. Lưu ý giờ cao điểm đường Thuận Kiều hơi đông nên đi hướng Nguyễn Chí Thanh hoặc Hồng Bàng sẽ vào cổng cấp cứu nhanh hơn.',
        verifiedVisit: true,
        helpfulCount: 39,
      },
    ],
  },
  {
    id: 'fac-115-hcm',
    googlePlaceId: 'ChIJ115PeopleHospital_StrokeCenter',
    name: 'Bệnh viện Nhân dân 115 — Trung tâm Đột quỵ & Tim mạch Can thiệp',
    facilityType: 'hospital_emergency',
    category: 'cardiac',
    city: 'hcm',
    district: 'Quận 10',
    address: '527 Sư Vạn Hạnh, Phường 12, Quận 10, TP.HCM',
    lat: 10.7756,
    lng: 106.6667,
    phone: '028 3865 2368',
    emergencyHotline: '028 3865 2368',
    emergencyLevel: 1,
    operatingHours: { is24_7: true, description: 'Cấp cứu 24/7 liên tục' },
    capabilities: [
      { code: 'CATHLAB', name: 'Phòng Can thiệp Tim mạch DSA 24/7', isAvailable: true, highlight: true },
      { code: 'STROKE_UNIT', name: 'Đơn vị Đột quỵ chuẩn Kim cương WSO', isAvailable: true, highlight: true },
      { code: 'ECMO', name: 'Kỹ thuật tim phổi nhân tạo ECMO', isAvailable: true },
      { code: 'RESUSCITATION', name: 'Phòng Hồi sức Tim mạch chuyên sâu', isAvailable: true },
    ],
    icuBedsAvailable: 8,
    ambulanceBaysOpen: 4,
    doctorOnDutyCount: 16,
    specialtyTag: 'Nhồi máu cơ tim & Đột quỵ',
    rating: 4.8,
    reviewsCount: 2910,
    goldenHourWindowMinutes: 90,
    accreditationBadge: 'Chứng nhận Chuẩn Kim Cương Hội Đột Quỵ Thế Giới (WSO)',
    avgErWaitMinutes: 3,
    patientSatisfactionPercent: 96,
    reviewBreakdown: {
      emergencySpeedScore: 4.9,
      doctorExpertiseScore: 4.9,
      equipmentModernityScore: 4.8,
      insuranceTransparencyScore: 4.7,
      starPercentages: [83, 12, 3, 1, 1],
    },
    reviews: [
      {
        id: 'rev-115-1',
        authorName: 'Phạm Quốc Bảo',
        authorRole: 'Local Guide Cấp 8 • Người nhà bệnh nhân',
        avatarColor: 'bg-cyan-600',
        rating: 5,
        relativeTime: '3 ngày trước',
        serviceTag: 'Can thiệp Mạch vành Cathlab',
        comment:
          'Trung tâm đột quỵ và tim mạch số 1! Chú mình bị nhồi máu cơ tim cấp đau ngực dữ dội, vào viện được đẩy thẳng lên phòng Cathlab đặt stent trong vòng 25 phút (Door-to-balloon cực nhanh). Đội ngũ y bác sĩ tận tâm.',
        verifiedVisit: true,
        helpfulCount: 115,
        facilityReply: {
          responder: 'Phòng Công tác Xã hội BV Nhân dân 115',
          text: 'Chân thành cảm ơn anh Bảo. Bệnh viện luôn duy trì 3 phòng DSA/Cathlab hoạt động 24/24 để cấp cứu kịp thời các ca nhồi máu cơ tim và đột quỵ.',
          time: '2 ngày trước',
        },
      },
      {
        id: 'rev-115-2',
        authorName: 'Đặng Ngọc Ánh',
        authorRole: 'Bệnh nhân điều trị',
        avatarColor: 'bg-purple-600',
        rating: 5,
        relativeTime: '5 ngày trước',
        serviceTag: 'Đơn vị Đột quỵ WSO',
        comment:
          'Quy trình tiếp nhận cấp cứu không cần đóng viện phí trước đối với ca nguy kịch. Điều dưỡng hướng dẫn nhẹ nhàng, máy chụp MRI thế hệ mới có kết quả ngay.',
        verifiedVisit: true,
        helpfulCount: 54,
      },
    ],
  },
  {
    id: 'fac-dhyd-hcm',
    googlePlaceId: 'ChIJ_UMC_HCMC_Hospital',
    name: 'Bệnh viện Đại học Y Dược TP.HCM — Khoa Cấp cứu Hồi sức',
    facilityType: 'hospital_emergency',
    category: 'general',
    city: 'hcm',
    district: 'Quận 5',
    address: '215 Hồng Bàng, Phường 11, Quận 5, TP.HCM',
    lat: 10.7554,
    lng: 106.6601,
    phone: '028 3855 4269',
    emergencyHotline: '028 3855 4269',
    emergencyLevel: 1,
    operatingHours: { is24_7: true, description: 'Cấp cứu 24/7' },
    capabilities: [
      { code: 'MULTI_SPEC', name: 'Hội chẩn liên chuyên khoa Giáo sư/Tiến sĩ', isAvailable: true, highlight: true },
      { code: 'CARDIAC_SURG', name: 'Phẫu thuật Tim mạch & Lồng ngực khẩn', isAvailable: true, highlight: true },
      { code: 'ENDO_247', name: 'Nội soi cầm máu tiêu hóa khẩn 24/7', isAvailable: true },
    ],
    icuBedsAvailable: 11,
    ambulanceBaysOpen: 5,
    doctorOnDutyCount: 19,
    specialtyTag: 'Đa khoa Chuyên sâu & Tim mạch',
    rating: 4.9,
    reviewsCount: 3420,
    goldenHourWindowMinutes: 120,
    accreditationBadge: 'Bệnh viện Đại học Chuẩn Quốc Tế JCI / ISO',
    avgErWaitMinutes: 3,
    patientSatisfactionPercent: 98,
    reviewBreakdown: {
      emergencySpeedScore: 4.9,
      doctorExpertiseScore: 5.0,
      equipmentModernityScore: 5.0,
      insuranceTransparencyScore: 4.8,
      starPercentages: [89, 8, 2, 1, 0],
    },
    reviews: [
      {
        id: 'rev-dhyd-1',
        authorName: 'Võ Hoàng Yến',
        authorRole: 'Local Guide Cấp 6',
        avatarColor: 'bg-indigo-600',
        rating: 5,
        relativeTime: '1 ngày trước',
        serviceTag: 'Cấp cứu Đa khoa & Tim mạch',
        comment:
          'Cơ sở vật chất sạch đẹp như khách sạn 5 sao, quy trình bệnh án điện tử hoàn toàn. Khoa cấp cứu tiếp nhận cực nhanh, bác sĩ giải thích cặn kẽ từng chỉ số xét nghiệm cho người nhà yên tâm.',
        verifiedVisit: true,
        helpfulCount: 93,
      },
      {
        id: 'rev-dhyd-2',
        authorName: 'Huỳnh Tấn Phát',
        authorRole: 'Người nhà bệnh nhân',
        avatarColor: 'bg-teal-600',
        rating: 5,
        relativeTime: '1 tuần trước',
        serviceTag: 'Phẫu thuật Cấp cứu',
        comment:
          'Khi Chợ Rẫy đông, chuyển qua ĐH Y Dược ngay gần đó (chỉ cách 400m trên đường Hồng Bàng) là lựa chọn tuyệt vời nhất. Phòng hồi sức vô trùng tuyệt đối.',
        verifiedVisit: true,
        helpfulCount: 61,
      },
    ],
  },
  {
    id: 'fac-nd1-hcm',
    googlePlaceId: 'ChIJ_ChildrenHospital1_HCMC',
    name: 'Bệnh viện Nhi Đồng 1 — Trung tâm Cấp cứu & Hồi sức Sơ sinh',
    facilityType: 'hospital_emergency',
    category: 'pediatrics',
    city: 'hcm',
    district: 'Quận 10',
    address: '341 Sư Vạn Hạnh, Phường 10, Quận 10, TP.HCM',
    lat: 10.7688,
    lng: 106.6708,
    phone: '028 3927 1119',
    emergencyHotline: '028 3927 1119',
    emergencyLevel: 1,
    operatingHours: { is24_7: true, description: 'Cấp cứu Nhi 24/7' },
    capabilities: [
      { code: 'PICU', name: 'Hồi sức tích cực Nhi khoa (PICU) & ECMO Nhi', isAvailable: true, highlight: true },
      { code: 'CONVULSION', name: 'Xử trí sốt cao co giật & Sốc sốt xuất huyết', isAvailable: true, highlight: true },
      { code: 'NEONATAL', name: 'Cấp cứu Sơ sinh chuyên sâu', isAvailable: true },
    ],
    icuBedsAvailable: 10,
    ambulanceBaysOpen: 4,
    doctorOnDutyCount: 15,
    specialtyTag: 'Cấp cứu Nhi khoa Tuyến cuối',
    rating: 4.8,
    reviewsCount: 2450,
    goldenHourWindowMinutes: 60,
    accreditationBadge: 'Trung tâm Hồi sức Nhi khoa Hàng đầu Phía Nam',
    avgErWaitMinutes: 2,
    patientSatisfactionPercent: 96,
    reviewBreakdown: {
      emergencySpeedScore: 5.0,
      doctorExpertiseScore: 4.9,
      equipmentModernityScore: 4.8,
      insuranceTransparencyScore: 4.7,
      starPercentages: [84, 11, 3, 1, 1],
    },
    reviews: [
      {
        id: 'rev-nd1-1',
        authorName: 'Chị Mai Phương',
        authorRole: 'Phụ huynh bệnh nhi',
        avatarColor: 'bg-rose-600',
        rating: 5,
        relativeTime: '4 ngày trước',
        serviceTag: 'Cấp cứu Sốt co giật Nhi',
        comment:
          'Bé nhà mình sốt cao 40 độ co giật tím tái lúc nửa đêm. Vào cổng cấp cứu Sư Vạn Hạnh là các cô điều dưỡng và bác sĩ bế thốc bé vào xử trí thở oxy và hạ sốt ngay lập tức trong 30 giây đầu tiên.',
        verifiedVisit: true,
        helpfulCount: 88,
      },
    ],
  },
  {
    id: 'fac-gd-hcm',
    googlePlaceId: 'ChIJ_GiaDinhPeopleHospital',
    name: 'Bệnh viện Nhân dân Gia Định — Cấp cứu Đa khoa & Chấn thương',
    facilityType: 'hospital_emergency',
    category: 'trauma',
    city: 'hcm',
    district: 'Bình Thạnh',
    address: '1 Nơ Trang Long, Phường 7, Bình Thạnh, TP.HCM',
    lat: 10.8035,
    lng: 106.6941,
    phone: '028 3841 2692',
    emergencyHotline: '028 3841 2692',
    emergencyLevel: 1,
    operatingHours: { is24_7: true, description: 'Cấp cứu 24/7' },
    capabilities: [
      { code: 'TRAUMA_SURG', name: 'Báo động đỏ Ngoại chấn thương & Phẫu thuật khẩn', isAvailable: true, highlight: true },
      { code: 'STROKE_FAST', name: 'Tiêu sợi huyết đột quỵ cửa sổ vàng', isAvailable: true },
    ],
    icuBedsAvailable: 9,
    ambulanceBaysOpen: 5,
    doctorOnDutyCount: 14,
    specialtyTag: 'Ngoại Chấn thương & Cấp cứu Đông Bắc',
    rating: 4.7,
    reviewsCount: 1980,
    goldenHourWindowMinutes: 60,
    accreditationBadge: 'Bệnh viện Đa khoa Hạng I Tuyến Thành Phố',
    avgErWaitMinutes: 4,
    patientSatisfactionPercent: 94,
    reviewBreakdown: {
      emergencySpeedScore: 4.8,
      doctorExpertiseScore: 4.8,
      equipmentModernityScore: 4.7,
      insuranceTransparencyScore: 4.7,
      starPercentages: [79, 14, 4, 2, 1],
    },
    reviews: [
      {
        id: 'rev-gd-1',
        authorName: 'Trương Trọng Nghĩa',
        authorRole: 'Local Guide Cấp 6',
        avatarColor: 'bg-sky-600',
        rating: 5,
        relativeTime: '6 ngày trước',
        serviceTag: 'Cấp cứu Chấn thương',
        comment:
          'Khu cấp cứu mới xây dựng rất rộng rãi, xe cấp cứu chạy thẳng vào sảnh. Bác sĩ ngoại khoa khâu vết thương và chụp X-quang rất nhanh.',
        verifiedVisit: true,
        helpfulCount: 42,
      },
    ],
  },
  {
    id: 'pharm-lc-hcm1',
    googlePlaceId: 'ChIJ_LongChau_HaiBaTrung_247',
    name: 'Nhà thuốc FPT Long Châu — 375 Hai Bà Trưng (Chuẩn GPP 24/7)',
    facilityType: 'pharmacy',
    category: 'pharmacy_24h',
    city: 'hcm',
    district: 'Quận 3',
    address: '375 Hai Bà Trưng, Phường Võ Thị Sáu, Quận 3, TP.HCM',
    lat: 10.7892,
    lng: 106.6881,
    phone: '1800 6928',
    emergencyHotline: '1800 6928',
    emergencyLevel: 2,
    operatingHours: { is24_7: true, description: 'Mở cửa 24/24 xuyên đêm kể cả Lễ Tết' },
    capabilities: [
      { code: 'RX_247', name: 'Đầy đủ thuốc kê đơn bệnh viện tuyến cuối', isAvailable: true, highlight: true },
      { code: 'COLD_CHAIN', name: 'Tủ lạnh chuẩn GSP bảo quản Insulin & Sinh phẩm', isAvailable: true, highlight: true },
      { code: 'PHARM_DEG', name: 'Dược sĩ Đại học trực tư vấn ca đêm', isAvailable: true },
    ],
    icuBedsAvailable: 0,
    ambulanceBaysOpen: 2,
    doctorOnDutyCount: 3,
    specialtyTag: 'Dược phẩm Kê đơn & Insulin 24/7',
    rating: 4.9,
    reviewsCount: 1240,
    accreditationBadge: 'Nhà Thuốc Đạt Chuẩn Thực Hành Tốt GPP Bộ Y Tế',
    avgErWaitMinutes: 1,
    patientSatisfactionPercent: 99,
    reviewBreakdown: {
      emergencySpeedScore: 5.0,
      doctorExpertiseScore: 4.9,
      equipmentModernityScore: 4.9,
      insuranceTransparencyScore: 5.0,
      starPercentages: [91, 7, 1, 1, 0],
    },
    reviews: [
      {
        id: 'rev-lc-1',
        authorName: 'Lê Thanh Hằng',
        authorRole: 'Khách hàng xác thực',
        avatarColor: 'bg-emerald-600',
        rating: 5,
        relativeTime: 'Hôm qua',
        serviceTag: 'Mua thuốc kê đơn đêm',
        comment:
          '1 giờ sáng đi tìm mua thuốc huyết áp và bút tiêm Insulin cho mẹ, may quá nhà thuốc mở sáng đèn 24/24. Dược sĩ kiểm tra đơn thuốc kỹ lưỡng, giá bán đúng niêm yết chính hãng.',
        verifiedVisit: true,
        helpfulCount: 51,
      },
    ],
  },
  {
    id: 'pharm-pc-hcm2',
    googlePlaceId: 'ChIJ_Pharmacity_CongQuynh_247',
    name: 'Nhà thuốc Pharmacity 24H — Cống Quỳnh (GPP Trực Đêm)',
    facilityType: 'pharmacy',
    category: 'pharmacy_24h',
    city: 'hcm',
    district: 'Quận 1',
    address: '189 Cống Quỳnh, Phường Nguyễn Cư Trinh, Quận 1, TP.HCM',
    lat: 10.7669,
    lng: 106.6882,
    phone: '1800 6821',
    emergencyHotline: '1800 6821',
    emergencyLevel: 2,
    operatingHours: { is24_7: true, description: 'Phục vụ 24/7 xuyên đêm' },
    capabilities: [
      { code: 'FIRST_AID', name: 'Bộ vật tư sơ cứu, băng gạc, đo SpO2 & Huyết áp', isAvailable: true, highlight: true },
      { code: 'FEVER_KIDS', name: 'Thuốc hạ sốt, bù điện giải & kháng sinh Nhi', isAvailable: true },
    ],
    icuBedsAvailable: 0,
    ambulanceBaysOpen: 2,
    doctorOnDutyCount: 2,
    specialtyTag: 'Thuốc Cấp thời & Vật tư Y tế 24/7',
    rating: 4.8,
    reviewsCount: 890,
    accreditationBadge: 'Chuỗi Nhà Thuốc GPP Hiện Đại 24/7',
    avgErWaitMinutes: 1,
    patientSatisfactionPercent: 96,
    reviewBreakdown: {
      emergencySpeedScore: 4.9,
      doctorExpertiseScore: 4.8,
      equipmentModernityScore: 4.8,
      insuranceTransparencyScore: 4.8,
      starPercentages: [85, 11, 2, 1, 1],
    },
    reviews: [
      {
        id: 'rev-pc-1',
        authorName: 'Đoàn Văn Hậu',
        authorRole: 'Local Guide Cấp 5',
        avatarColor: 'bg-blue-600',
        rating: 5,
        relativeTime: '4 ngày trước',
        serviceTag: 'Vật tư y tế & Thuốc đêm',
        comment:
          'Ngay gần khu bệnh viện Từ Dũ và Quận 1, rất tiện mua băng gạc y tế, thuốc hạ sốt ban đêm. Có chỗ đậu xe ô tô trước cửa.',
        verifiedVisit: true,
        helpfulCount: 28,
      },
    ],
  },

  // ==================== HÀ NỘI ====================
  {
    id: 'fac-bm-hn',
    googlePlaceId: 'ChIJ_BachMaiHospital_A9Center',
    name: 'Bệnh viện Bạch Mai — Trung tâm Cấp cứu A9 & Đột quỵ Toàn quốc',
    facilityType: 'hospital_emergency',
    category: 'stroke',
    city: 'hanoi',
    district: 'Đống Đa',
    address: '78 Đường Giải Phóng, Phương Mai, Đống Đa, Hà Nội',
    lat: 21.0031,
    lng: 105.8406,
    phone: '024 3869 3731',
    emergencyHotline: '024 3869 3731',
    emergencyLevel: 1,
    operatingHours: { is24_7: true, description: 'Cấp cứu A9 & Trung tâm Đột quỵ 24/7' },
    capabilities: [
      { code: 'A9_ER', name: 'Trung tâm Cấp cứu A9 & Chống độc Quốc gia', isAvailable: true, highlight: true },
      { code: 'STROKE_CENTER', name: 'Trung tâm Đột quỵ chuẩn Kim cương WSO', isAvailable: true, highlight: true },
      { code: 'CARDIO_INST', name: 'Viện Tim mạch Quốc gia Việt Nam', isAvailable: true, highlight: true },
    ],
    icuBedsAvailable: 18,
    ambulanceBaysOpen: 8,
    doctorOnDutyCount: 28,
    specialtyTag: 'Đột quỵ, Tim mạch & Chống độc Quốc gia',
    rating: 4.9,
    reviewsCount: 4520,
    goldenHourWindowMinutes: 270,
    accreditationBadge: 'Bệnh viện Đa khoa Hạng Đặc Biệt Đầu Ngành Miền Bắc',
    avgErWaitMinutes: 3,
    patientSatisfactionPercent: 98,
    reviewBreakdown: {
      emergencySpeedScore: 4.9,
      doctorExpertiseScore: 5.0,
      equipmentModernityScore: 4.9,
      insuranceTransparencyScore: 4.8,
      starPercentages: [88, 9, 2, 1, 0],
    },
    reviews: [
      {
        id: 'rev-bm-1',
        authorName: 'Vũ Quốc Khánh',
        authorRole: 'Local Guide Cấp 8 • Người nhà bệnh nhân',
        avatarColor: 'bg-blue-600',
        rating: 5,
        relativeTime: '2 ngày trước',
        serviceTag: 'Trung tâm Đột quỵ & A9',
        comment:
          'Trung tâm Cấp cứu A9 và Trung tâm Đột quỵ Bạch Mai làm việc với tốc độ đáng kinh ngạc. Bác tôi bị đột quỵ tắc mạch não lớn được tiêm tiêu sợi huyết và lấy huyết khối cơ học chỉ trong 40 phút đầu.',
        verifiedVisit: true,
        helpfulCount: 176,
      },
    ],
  },
  {
    id: 'fac-vd-hn',
    googlePlaceId: 'ChIJ_VietDucHospital_Trauma',
    name: 'Bệnh viện Hữu nghị Việt Đức — Trung tâm Cấp cứu Ngoại khoa & Chấn thương',
    facilityType: 'hospital_emergency',
    category: 'trauma',
    city: 'hanoi',
    district: 'Hoàn Kiếm',
    address: '40 Tràng Thi, Hàng Bông, Hoàn Kiếm, Hà Nội',
    lat: 21.0268,
    lng: 105.8468,
    phone: '024 3825 3531',
    emergencyHotline: '024 3825 3531',
    emergencyLevel: 1,
    operatingHours: { is24_7: true, description: 'Phẫu thuật Cấp cứu 24/7' },
    capabilities: [
      { code: 'NEURO_SURG', name: 'Phẫu thuật Thần kinh - Sọ não tối cấp', isAvailable: true, highlight: true },
      { code: 'ORTHO_TRAUMA', name: 'Cấp cứu Đa chấn thương, Cột sống & Mạch máu', isAvailable: true, highlight: true },
    ],
    icuBedsAvailable: 12,
    ambulanceBaysOpen: 6,
    doctorOnDutyCount: 24,
    specialtyTag: 'Ngoại khoa & Chấn thương Sọ não Số 1',
    rating: 4.9,
    reviewsCount: 3690,
    goldenHourWindowMinutes: 60,
    accreditationBadge: 'Trung tâm Phẫu thuật Ngoại khoa Hạng Đặc Biệt',
    avgErWaitMinutes: 3,
    patientSatisfactionPercent: 97,
    reviewBreakdown: {
      emergencySpeedScore: 4.9,
      doctorExpertiseScore: 5.0,
      equipmentModernityScore: 4.9,
      insuranceTransparencyScore: 4.7,
      starPercentages: [86, 10, 2, 1, 1],
    },
    reviews: [
      {
        id: 'rev-vd-1',
        authorName: 'Hoàng Minh Đức',
        authorRole: 'Bệnh nhân đã điều trị',
        avatarColor: 'bg-emerald-600',
        rating: 5,
        relativeTime: '5 ngày trước',
        serviceTag: 'Cấp cứu Ngoại chấn thương',
        comment:
          'Về chấn thương chỉnh hình, sọ não và ngoại khoa thì Việt Đức là đỉnh cao nhất cả nước. Cổng cấp cứu đường Phủ Doãn luôn có đội ngũ trực tiếp nhận ca tai nạn ngay lập tức.',
        verifiedVisit: true,
        helpfulCount: 120,
      },
    ],
  },
  {
    id: 'fac-108-hn',
    googlePlaceId: 'ChIJ_108MilitaryHospital_Hanoi',
    name: 'Bệnh viện Trung ương Quân đội 108 — Trung tâm Cấp cứu & Can thiệp Mạch',
    facilityType: 'hospital_emergency',
    category: 'cardiac',
    city: 'hanoi',
    district: 'Hai Bà Trưng',
    address: 'Số 1 Trần Hưng Đạo, Bạch Đằng, Hai Bà Trưng, Hà Nội',
    lat: 21.0185,
    lng: 105.8602,
    phone: '024 6278 4115',
    emergencyHotline: '024 6278 4115',
    emergencyLevel: 1,
    operatingHours: { is24_7: true, description: 'Cấp cứu 24/7' },
    capabilities: [
      { code: 'CATH_108', name: 'Can thiệp Tim mạch & Đột quỵ não công nghệ cao', isAvailable: true, highlight: true },
      { code: 'HYBRID_OR', name: 'Phòng mổ Hybrid đa năng hiện đại nhất Đông Nam Á', isAvailable: true, highlight: true },
    ],
    icuBedsAvailable: 15,
    ambulanceBaysOpen: 7,
    doctorOnDutyCount: 25,
    specialtyTag: 'Can thiệp Mạch & Tim mạch Hạng Đặc Biệt',
    rating: 4.9,
    reviewsCount: 3810,
    goldenHourWindowMinutes: 90,
    accreditationBadge: 'Bệnh viện Hạng Đặc Biệt Quốc Gia • Chuẩn Quốc Tế',
    avgErWaitMinutes: 2,
    patientSatisfactionPercent: 99,
    reviewBreakdown: {
      emergencySpeedScore: 5.0,
      doctorExpertiseScore: 5.0,
      equipmentModernityScore: 5.0,
      insuranceTransparencyScore: 4.9,
      starPercentages: [92, 6, 1, 1, 0],
    },
    reviews: [
      {
        id: 'rev-108-1',
        authorName: 'Nguyễn Trọng Đại',
        authorRole: 'Local Guide Cấp 7',
        avatarColor: 'bg-cyan-600',
        rating: 5,
        relativeTime: '3 ngày trước',
        serviceTag: 'Cấp cứu Tim mạch & Đột quỵ',
        comment:
          'Khuôn viên và tòa nhà trung tâm của BV 108 hiện đại bậc nhất châu Á. Kỷ luật quân đội cực kỳ nghiêm túc, sạch sẽ, tiếp nhận cấp cứu nhanh gọn không phải chờ đợi.',
        verifiedVisit: true,
        helpfulCount: 154,
      },
    ],
  },
  {
    id: 'pharm-lc-hn1',
    googlePlaceId: 'ChIJ_LongChau_XaDan_Hanoi',
    name: 'Nhà thuốc FPT Long Châu — 228 Xã Đàn (GPP Mở Cửa 24/7)',
    facilityType: 'pharmacy',
    category: 'pharmacy_24h',
    city: 'hanoi',
    district: 'Đống Đa',
    address: '228 Xã Đàn, Phương Liên, Đống Đa, Hà Nội',
    lat: 21.0118,
    lng: 105.8348,
    phone: '1800 6928',
    emergencyHotline: '1800 6928',
    emergencyLevel: 2,
    operatingHours: { is24_7: true, description: 'Mở cửa 24/7 xuyên đêm' },
    capabilities: [
      { code: 'RX_HANOI', name: 'Thuốc đặc trị theo đơn BV Bạch Mai, Việt Đức, 108', isAvailable: true, highlight: true },
      { code: 'INSULIN_COLD', name: 'Bảo quản lạnh thuốc sinh học & Insulin chuẩn GSP', isAvailable: true },
    ],
    icuBedsAvailable: 0,
    ambulanceBaysOpen: 2,
    doctorOnDutyCount: 2,
    specialtyTag: 'Thuốc Kê đơn Tuyến Trung Ương 24/7',
    rating: 4.9,
    reviewsCount: 950,
    accreditationBadge: 'Nhà Thuốc Chuẩn GPP Quốc Gia 24/7',
    avgErWaitMinutes: 1,
    patientSatisfactionPercent: 98,
    reviewBreakdown: {
      emergencySpeedScore: 5.0,
      doctorExpertiseScore: 4.9,
      equipmentModernityScore: 4.9,
      insuranceTransparencyScore: 4.9,
      starPercentages: [89, 8, 2, 1, 0],
    },
    reviews: [
      {
        id: 'rev-lchn-1',
        authorName: 'Phạm Hương Giang',
        authorRole: 'Khách hàng xác thực',
        avatarColor: 'bg-teal-600',
        rating: 5,
        relativeTime: '3 ngày trước',
        serviceTag: 'Thuốc kê đơn 24/7',
        comment:
          'Gần ngay trục Giải Phóng - Xã Đàn từ Bạch Mai ra. Đêm muộn vẫn có dược sĩ tư vấn liều dùng rất tận tình.',
        verifiedVisit: true,
        helpfulCount: 34,
      },
    ],
  },

  // ==================== ĐÀ NẴNG ====================
  {
    id: 'fac-dn-gen',
    googlePlaceId: 'ChIJ_DaNangHospital_Emergency',
    name: 'Bệnh viện Đà Nẵng — Trung tâm Tim mạch & Cấp cứu Đa khoa Miền Trung',
    facilityType: 'hospital_emergency',
    category: 'stroke',
    city: 'danang',
    district: 'Hải Châu',
    address: '124 Hải Phòng, Thạch Thang, Hải Châu, Đà Nẵng',
    lat: 16.0718,
    lng: 108.2154,
    phone: '0236 3821 118',
    emergencyHotline: '0236 3821 118',
    emergencyLevel: 1,
    operatingHours: { is24_7: true, description: 'Cấp cứu 24/7' },
    capabilities: [
      { code: 'STROKE_DN', name: 'Can thiệp Đột quỵ & Tim mạch khu vực Miền Trung', isAvailable: true, highlight: true },
      { code: 'ECMO_DN', name: 'Hồi sức tích cực & ECMO', isAvailable: true, highlight: true },
    ],
    icuBedsAvailable: 14,
    ambulanceBaysOpen: 6,
    doctorOnDutyCount: 20,
    specialtyTag: 'Đột quỵ & Hồi sức Tuyến cuối Miền Trung',
    rating: 4.8,
    reviewsCount: 2150,
    goldenHourWindowMinutes: 270,
    accreditationBadge: 'Bệnh viện Hạng I Tuyến Cuối Khu Vực Miền Trung',
    avgErWaitMinutes: 3,
    patientSatisfactionPercent: 96,
    reviewBreakdown: {
      emergencySpeedScore: 4.9,
      doctorExpertiseScore: 4.9,
      equipmentModernityScore: 4.8,
      insuranceTransparencyScore: 4.8,
      starPercentages: [85, 11, 2, 1, 1],
    },
    reviews: [
      {
        id: 'rev-dn-1',
        authorName: 'Nguyễn Văn Hùng',
        authorRole: 'Local Guide Cấp 6',
        avatarColor: 'bg-blue-600',
        rating: 5,
        relativeTime: '1 tuần trước',
        serviceTag: 'Cấp cứu Đột quỵ & Tim mạch',
        comment:
          'Trung tâm tim mạch và đột quỵ của Bệnh viện Đà Nẵng được đầu tư trang thiết bị rất hiện đại, bác sĩ cấp cứu nhiệt tình.',
        verifiedVisit: true,
        helpfulCount: 62,
      },
    ],
  },
  {
    id: 'fac-c-dn',
    googlePlaceId: 'ChIJ_CHospital_DaNang',
    name: 'Bệnh viện C Đà Nẵng — Trung tâm Cấp cứu & Tim mạch Bộ Y Tế',
    facilityType: 'hospital_emergency',
    category: 'cardiac',
    city: 'danang',
    district: 'Hải Châu',
    address: '122 Hải Phòng, Thạch Thang, Hải Châu, Đà Nẵng',
    lat: 16.0725,
    lng: 108.2168,
    phone: '0236 3821 480',
    emergencyHotline: '0236 3821 480',
    emergencyLevel: 1,
    operatingHours: { is24_7: true, description: 'Cấp cứu 24/7' },
    capabilities: [
      { code: 'CARDIO_C', name: 'Can thiệp Mạch vành & Cấp cứu Nội - Ngoại khoa', isAvailable: true, highlight: true },
      { code: 'STROKE_C', name: 'Đơn vị Đột quỵ chuẩn Vàng WSO', isAvailable: true },
    ],
    icuBedsAvailable: 11,
    ambulanceBaysOpen: 5,
    doctorOnDutyCount: 16,
    specialtyTag: 'Cấp cứu Tim mạch & Nội khoa Tuyến Trung Ương',
    rating: 4.8,
    reviewsCount: 1480,
    goldenHourWindowMinutes: 90,
    accreditationBadge: 'Bệnh viện Hạng I Trực Thuộc Bộ Y Tế',
    avgErWaitMinutes: 3,
    patientSatisfactionPercent: 97,
    reviewBreakdown: {
      emergencySpeedScore: 4.9,
      doctorExpertiseScore: 4.9,
      equipmentModernityScore: 4.8,
      insuranceTransparencyScore: 4.9,
      starPercentages: [86, 10, 2, 1, 1],
    },
    reviews: [
      {
        id: 'rev-cdn-1',
        authorName: 'Trần Quốc Tuấn',
        authorRole: 'Bệnh nhân điều trị',
        avatarColor: 'bg-emerald-600',
        rating: 5,
        relativeTime: '4 ngày trước',
        serviceTag: 'Cấp cứu Tim mạch',
        comment:
          'Ngay sát Bệnh viện Đà Nẵng, khu cấp cứu của Bệnh viện C rất thoáng, ít quá tải hơn và bác sĩ chăm sóc cực kỳ chu đáo.',
        verifiedVisit: true,
        helpfulCount: 47,
      },
    ],
  },
  {
    id: 'pharm-lc-dn1',
    googlePlaceId: 'ChIJ_LongChau_NguyenVanLinh_DN',
    name: 'Nhà thuốc FPT Long Châu — Nguyễn Văn Linh (GPP Mở Cửa 24/7)',
    facilityType: 'pharmacy',
    category: 'pharmacy_24h',
    city: 'danang',
    district: 'Hải Châu',
    address: '158 Nguyễn Văn Linh, Vĩnh Trung, Thanh Khê, Đà Nẵng',
    lat: 16.0605,
    lng: 108.2112,
    phone: '1800 6928',
    emergencyHotline: '1800 6928',
    emergencyLevel: 2,
    operatingHours: { is24_7: true, description: 'Mở cửa 24/7 xuyên đêm' },
    capabilities: [
      { code: 'RX_DN', name: 'Thuốc kê đơn & Vật tư y tế chính hãng 24/7', isAvailable: true, highlight: true },
    ],
    icuBedsAvailable: 0,
    ambulanceBaysOpen: 2,
    doctorOnDutyCount: 2,
    specialtyTag: 'Dược phẩm GPP 24/7 Đà Nẵng',
    rating: 4.9,
    reviewsCount: 640,
    accreditationBadge: 'Nhà Thuốc Đạt Chuẩn GPP 24/7',
    avgErWaitMinutes: 1,
    patientSatisfactionPercent: 98,
    reviewBreakdown: {
      emergencySpeedScore: 5.0,
      doctorExpertiseScore: 4.9,
      equipmentModernityScore: 4.9,
      insuranceTransparencyScore: 4.9,
      starPercentages: [90, 8, 1, 1, 0],
    },
    reviews: [
      {
        id: 'rev-lcdn-1',
        authorName: 'Lê Thị Mỹ Linh',
        authorRole: 'Khách hàng xác thực',
        avatarColor: 'bg-cyan-600',
        rating: 5,
        relativeTime: '2 ngày trước',
        serviceTag: 'Dược phẩm ban đêm',
        comment:
          'Nằm ngay trục đường lớn Nguyễn Văn Linh, đêm khuya mua thuốc cho con nhỏ rất an tâm.',
        verifiedVisit: true,
        helpfulCount: 29,
      },
    ],
  },
];
