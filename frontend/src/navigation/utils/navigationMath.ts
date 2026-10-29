/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * MedGuard AI - Navigation & Clinical Geolocation Pure Logic Engine
 */

export interface LatLng {
  lat: number;
  lng: number;
}

export type TrafficLevel = 'LOW' | 'MODERATE' | 'HEAVY' | 'SEVERELY_CONGESTED';

export interface RouteManeuver {
  step_number: number;
  instruction: string;
  road_name: string;
  distance_meters: number;
  modifier?: string; // left, right, straight, roundabout, uturn
  traffic_level?: TrafficLevel;
}

export interface GoldenHourAssessment {
  condition: string;
  maxWindowMinutes: number;
  elapsedMinutes: number;
  remainingMinutes: number;
  isWithinWindow: boolean;
  urgencyLevel: 'CRITICAL' | 'WARNING' | 'NORMAL';
  recommendation: string;
}

/**
 * Calculates great-circle distance between two geographic coordinates in meters.
 */
export function calculateDistanceMeters(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  const R = 6371000; // Earth radius in meters
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return Math.round(R * c);
}

/**
 * Calculates the forward azimuth / bearing in degrees (0 - 360) from point 1 to point 2.
 */
export function calculateBearing(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  const lat1Rad = (lat1 * Math.PI) / 180;
  const lat2Rad = (lat2 * Math.PI) / 180;
  const dLonRad = ((lon2 - lon1) * Math.PI) / 180;

  const y = Math.sin(dLonRad) * Math.cos(lat2Rad);
  const x =
    Math.cos(lat1Rad) * Math.sin(lat2Rad) -
    Math.sin(lat1Rad) * Math.cos(lat2Rad) * Math.cos(dLonRad);

  const brng = (Math.atan2(y, x) * 180) / Math.PI;
  return (brng + 360) % 360;
}

/**
 * Formats distance into clean human-readable Vietnamese representation.
 */
export function formatDistanceVi(meters: number): string {
  if (meters < 1000) {
    return `${Math.round(meters)} m`;
  }
  return `${(meters / 1000).toFixed(1)} km`;
}

/**
 * Formats estimated time into human-readable Vietnamese representation.
 */
export function formatDurationVi(totalMinutes: number): string {
  if (totalMinutes < 1) return 'Dưới 1 phút';
  if (totalMinutes < 60) return `${Math.round(totalMinutes)} phút`;
  const hours = Math.floor(totalMinutes / 60);
  const mins = Math.round(totalMinutes % 60);
  return mins > 0 ? `${hours} giờ ${mins} phút` : `${hours} giờ`;
}

/**
 * Snaps a user coordinate to the closest point along the route polyline.
 * Returns the snapped coordinate, index of the closest segment, distance to the line, and heading.
 */
export function snapToRoute(
  userLat: number,
  userLng: number,
  polyline: [number, number][]
): {
  snappedLat: number;
  snappedLng: number;
  closestIndex: number;
  distanceFromRouteMeters: number;
  heading: number;
} {
  if (!polyline || polyline.length === 0) {
    return {
      snappedLat: userLat,
      snappedLng: userLng,
      closestIndex: 0,
      distanceFromRouteMeters: 0,
      heading: 0,
    };
  }

  if (polyline.length === 1) {
    const dist = calculateDistanceMeters(userLat, userLng, polyline[0][0], polyline[0][1]);
    return {
      snappedLat: polyline[0][0],
      snappedLng: polyline[0][1],
      closestIndex: 0,
      distanceFromRouteMeters: dist,
      heading: 0,
    };
  }

  let minDistance = Infinity;
  let closestIndex = 0;
  let snappedLat = polyline[0][0];
  let snappedLng = polyline[0][1];

  for (let i = 0; i < polyline.length - 1; i++) {
    const p1 = polyline[i];
    const p2 = polyline[i + 1];

    // Project point onto segment p1-p2
    const distP1 = calculateDistanceMeters(userLat, userLng, p1[0], p1[1]);
    const segLength = calculateDistanceMeters(p1[0], p1[1], p2[0], p2[1]);

    let candidateLat = p1[0];
    let candidateLng = p1[1];
    let dist = distP1;

    if (segLength > 0) {
      const u =
        ((userLat - p1[0]) * (p2[0] - p1[0]) + (userLng - p1[1]) * (p2[1] - p1[1])) /
        ((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2);
      const clampedU = Math.max(0, Math.min(1, u));
      candidateLat = p1[0] + clampedU * (p2[0] - p1[0]);
      candidateLng = p1[1] + clampedU * (p2[1] - p1[1]);
      dist = calculateDistanceMeters(userLat, userLng, candidateLat, candidateLng);
    }

    if (dist < minDistance) {
      minDistance = dist;
      closestIndex = i;
      snappedLat = candidateLat;
      snappedLng = candidateLng;
    }
  }

  const nextIndex = Math.min(closestIndex + 1, polyline.length - 1);
  const heading = calculateBearing(
    polyline[closestIndex][0],
    polyline[closestIndex][1],
    polyline[nextIndex][0],
    polyline[nextIndex][1]
  );

  return {
    snappedLat: Number(snappedLat.toFixed(6)),
    snappedLng: Number(snappedLng.toFixed(6)),
    closestIndex,
    distanceFromRouteMeters: Math.round(minDistance),
    heading: Math.round(heading),
  };
}

/**
 * Calculates remaining route distance in meters from current index to the end.
 */
export function calculateRemainingRouteDistance(
  currentIndex: number,
  polyline: [number, number][]
): number {
  if (!polyline || polyline.length <= 1 || currentIndex >= polyline.length - 1) {
    return 0;
  }
  let total = 0;
  for (let i = currentIndex; i < polyline.length - 1; i++) {
    total += calculateDistanceMeters(
      polyline[i][0],
      polyline[i][1],
      polyline[i + 1][0],
      polyline[i + 1][1]
    );
  }
  return Math.round(total);
}

/**
 * Evaluates the Emergency Clinical Golden Hour window for triage conditions.
 */
export function evaluateGoldenHour(
  conditionType: 'stroke' | 'cardiac' | 'myocardial_infarction' | 'anaphylaxis' | 'trauma' | 'pediatrics' | 'general',
  elapsedMinutes: number
): GoldenHourAssessment {
  switch (conditionType) {
    case 'stroke': {
      // Golden window for IV thrombolysis is 270 minutes (4.5 hours)
      const maxWindow = 270;
      const remaining = Math.max(0, maxWindow - elapsedMinutes);
      return {
        condition: 'Đột quỵ não cấp (Stroke)',
        maxWindowMinutes: maxWindow,
        elapsedMinutes,
        remainingMinutes: remaining,
        isWithinWindow: remaining > 0,
        urgencyLevel: remaining < 60 ? 'CRITICAL' : 'WARNING',
        recommendation:
          remaining > 0
            ? `CÒN ${remaining} PHÚT CỬA SỔ VÀNG tiêu sợi huyết / can thiệp lấy huyết khối! Cần tới ngay trung tâm đột quỵ.`
            : 'Đã quá cửa sổ tiêu sợi huyết thông thường. Cần khẩn cấp đánh giá can thiệp mạch mở rộng!',
      };
    }
    case 'cardiac':
    case 'myocardial_infarction': {
      // Golden door-to-balloon window is 90-120 minutes
      const maxWindow = 90;
      const remaining = Math.max(0, maxWindow - elapsedMinutes);
      return {
        condition: 'Nhồi máu cơ tim cấp (Cathlab)',
        maxWindowMinutes: maxWindow,
        elapsedMinutes,
        remainingMinutes: remaining,
        isWithinWindow: remaining > 0,
        urgencyLevel: remaining < 30 ? 'CRITICAL' : 'WARNING',
        recommendation:
          remaining > 0
            ? `Thời gian can thiệp mạch vành khẩn (Door-to-balloon) còn ${remaining} phút! Chọn cơ sở có phòng Cathlab 24/7.`
            : 'Cần tái tưới máu cơ tim khẩn cấp. Ưu tiên BV có Đơn vị Hồi sức Tim mạch can thiệp!',
      };
    }
    case 'pediatrics': {
      const maxWindow = 60;
      const remaining = Math.max(0, maxWindow - elapsedMinutes);
      return {
        condition: 'Cấp cứu Hồi sức Nhi khoa',
        maxWindowMinutes: maxWindow,
        elapsedMinutes,
        remainingMinutes: remaining,
        isWithinWindow: remaining > 0,
        urgencyLevel: remaining < 20 ? 'CRITICAL' : 'WARNING',
        recommendation:
          'Khẩn cấp hạ sốt, chống co giật và bảo vệ đường thở. Ưu tiên bệnh viện Nhi Đồng có máy thở sẵn sàng.',
      };
    }
    case 'anaphylaxis': {
      return {
        condition: 'Sốc phản vệ / Dị ứng tối cấp',
        maxWindowMinutes: 30,
        elapsedMinutes,
        remainingMinutes: Math.max(0, 30 - elapsedMinutes),
        isWithinWindow: elapsedMinutes <= 30,
        urgencyLevel: 'CRITICAL',
        recommendation:
          'CẤP CỨU TỐI KHẨN: Ưu tiên tới cơ sở y tế gần nhất có Adrenaline và oxy ngay lập tức!',
      };
    }
    case 'trauma': {
      return {
        condition: 'Đa chấn thương nặng',
        maxWindowMinutes: 60,
        elapsedMinutes,
        remainingMinutes: Math.max(0, 60 - elapsedMinutes),
        isWithinWindow: elapsedMinutes <= 60,
        urgencyLevel: elapsedMinutes > 40 ? 'CRITICAL' : 'WARNING',
        recommendation:
          'Giờ vàng chấn thương (Golden Hour 60p): Cần chuyển tuyến ngoại khoa & ngân hàng máu sẵn sàng.',
      };
    }
    default: {
      return {
        condition: 'Cấp cứu đa khoa',
        maxWindowMinutes: 180,
        elapsedMinutes,
        remainingMinutes: Math.max(0, 180 - elapsedMinutes),
        isWithinWindow: true,
        urgencyLevel: 'NORMAL',
        recommendation: 'Di chuyển an toàn đến khoa cấp cứu hoặc nhà thuốc gần nhất theo chỉ dẫn.',
      };
    }
  }
}

/**
 * Translates direction text into Vietnamese voice instruction.
 */
export function buildVoiceAnnouncementVi(
  instruction: string,
  roadName: string,
  distanceMeters: number
): string {
  const distText =
    distanceMeters < 100
      ? 'ngay phía trước'
      : `sau ${formatDistanceVi(distanceMeters)}`;

  const lower = instruction.toLowerCase();
  let action = 'Tiếp tục đi thẳng';

  if (lower.includes('trái') || lower.includes('left')) {
    action = 'Rẽ trái';
  } else if (lower.includes('phải') || lower.includes('right')) {
    action = 'Rẽ phải';
  } else if (lower.includes('quay đầu') || lower.includes('u-turn')) {
    action = 'Quay đầu xe';
  } else if (lower.includes('vòng xuyến') || lower.includes('roundabout')) {
    action = 'Đi vào vòng xuyến';
  } else if (lower.includes('nhập làn') || lower.includes('merge')) {
    action = 'Nhập làn';
  } else if (lower.includes('đến nơi') || lower.includes('arrive')) {
    return `Bạn sắp đến điểm đến: ${roadName || instruction}.`;
  }

  const targetRoad = roadName ? ` vào ${roadName}` : '';
  return `${distText}, ${action}${targetRoad}.`;
}
