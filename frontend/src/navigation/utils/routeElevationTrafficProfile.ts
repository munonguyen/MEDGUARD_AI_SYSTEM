/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * Pure mathematical & geospatial profile generator for D3.js Elevation Profile
 * & Real-Time Traffic Density + Road Obstacle visualization along a selected route.
 */

import { calculateDistanceMeters } from './navigationMath.ts';
import type { TrafficLevel } from './navigationMath.ts';
import type { DualRoute } from '../services/routingService.ts';
import type {
  OperationalScenarioType,
  TransportVehicleType,
  WeatherConditionType,
} from '../services/bookingCareDispatchEngine.ts';

export type ObstacleCategory =
  | 'OVERPASS_BRIDGE'
  | 'TRAFFIC_BOTTLENECK'
  | 'LOW_LYING_FLOOD_DIP'
  | 'HOSPITAL_RAMP_GATE';

export interface RouteProfilePoint {
  index: number;
  lat: number;
  lng: number;
  distanceKm: number;
  progressFraction: number; // 0..1
  elevationMeters: number;
  slopePercent: number;
  trafficDensityPercent: number;
  trafficLevel: TrafficLevel;
  speedKmh: number;
  vibrationRms: number; // ISO 2631-1 m/s^2
  roadSegmentLabel: string;
}

export interface RouteObstacle {
  id: string;
  pointIndex: number;
  lat: number;
  lng: number;
  distanceKm: number;
  elevationMeters: number;
  trafficDensityPercent: number;
  category: ObstacleCategory;
  title: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH';
  medicalImpactNote: string;
  vehicleActionHint: string;
}

export interface RouteElevationTrafficAnalysis {
  points: RouteProfilePoint[];
  obstacles: RouteObstacle[];
  maxElevationMeters: number;
  minElevationMeters: number;
  avgElevationMeters: number;
  maxSlopePercent: number;
  avgTrafficDensityPercent: number;
  peakTrafficDensityPercent: number;
  totalElevationGainMeters: number;
}

export interface BuildProfileInput {
  route: DualRoute;
  scenarioType: OperationalScenarioType;
  vehicleType: TransportVehicleType;
  weather?: WeatherConditionType;
}

/**
 * Generates a deterministic, realistic elevation & real-time traffic density profile
 * along the exact coordinate geometry of the selected route.
 */
export function buildRouteElevationAndTrafficProfile(
  input: BuildProfileInput
): RouteElevationTrafficAnalysis {
  const {
    route,
    scenarioType,
    vehicleType,
    weather = 'clear',
  } = input;

  const coords = route.coordinates || [];
  if (coords.length === 0) {
    return {
      points: [],
      obstacles: [],
      maxElevationMeters: 10,
      minElevationMeters: 0,
      avgElevationMeters: 5,
      maxSlopePercent: 0,
      avgTrafficDensityPercent: 0,
      peakTrafficDensityPercent: 0,
      totalElevationGainMeters: 0,
    };
  }

  const isBypass = route.type === 'OPTIMAL_BYPASS';
  const totalRouteKm = Math.max(0.4, route.distance_km || 3.5);

  // Calculate cumulative geodesic distances first
  const rawCumulativeMeters: number[] = [0];
  for (let i = 1; i < coords.length; i++) {
    const segM = calculateDistanceMeters(
      coords[i - 1][0],
      coords[i - 1][1],
      coords[i][0],
      coords[i][1]
    );
    rawCumulativeMeters.push(rawCumulativeMeters[i - 1] + segM);
  }
  const totalRawMeters = Math.max(1, rawCumulativeMeters[rawCumulativeMeters.length - 1]);

  // Base terrain elevation by latitude region (Hanoi ~11m, Danang ~9m, HCMC ~6.5m)
  const startLat = coords[0][0];
  const baseElevation =
    startLat >= 19.5 ? 11.2 : startLat >= 14.5 ? 8.8 : 6.4;

  const weatherTrafficBoost =
    weather === 'urban_flood_warning' ? 22 : weather === 'heavy_rain' ? 14 : 0;

  const points: RouteProfilePoint[] = [];
  let totalElevationGainMeters = 0;

  for (let i = 0; i < coords.length; i++) {
    const [lat, lng] = coords[i];
    const progress = coords.length === 1 ? 0 : rawCumulativeMeters[i] / totalRawMeters;
    const distanceKm = Number((progress * totalRouteKm).toFixed(2));

    // Deterministic topographic & urban infrastructure profile:
    // 1. Overpass / urban bridge around 28%-38% of the route
    const overpassBell = Math.exp(-Math.pow((progress - 0.33) / 0.085, 2)) * (isBypass ? 11.5 : 8.4);
    // 2. Low-lying canal / underpass basin around 62%-70% of the route
    const canalDip = -Math.exp(-Math.pow((progress - 0.66) / 0.075, 2)) * (isBypass ? 1.8 : 3.4);
    // 3. Hospital approach ramp at 90%-98%
    const hospitalRamp = Math.exp(-Math.pow((progress - 0.94) / 0.05, 2)) * 2.8;
    // 4. Micro-undulation from coordinate hash
    const coordWave = Math.sin(progress * Math.PI * 4 + (lat + lng) * 120) * 0.65;

    const elevationMeters = Number(
      Math.max(1.8, baseElevation + overpassBell + canalDip + hospitalRamp + coordWave).toFixed(1)
    );

    // Compute road gradient (slope %) relative to previous point
    let slopePercent = 0;
    if (i > 0) {
      const dElev = elevationMeters - points[i - 1].elevationMeters;
      const dHorizMeters = Math.max(25, (distanceKm - points[i - 1].distanceKm) * 1000);
      slopePercent = Number(((dElev / dHorizMeters) * 100).toFixed(1));
      if (dElev > 0) {
        totalElevationGainMeters += dElev;
      }
    }

    // Match traffic segment along progress
    const baseDensity = route.traffic_density_percent || (isBypass ? 28 : 64);
    // Intersection congestion wave peaks near 0.25, 0.52, and 0.78
    const intersectionPeak1 = Math.exp(-Math.pow((progress - 0.24) / 0.07, 2)) * (isBypass ? 10 : 22);
    const intersectionPeak2 = Math.exp(-Math.pow((progress - 0.54) / 0.09, 2)) * (isBypass ? 14 : 28);
    const gateApproachWave = Math.exp(-Math.pow((progress - 0.88) / 0.06, 2)) * 12;

    const rawDensity = Math.round(
      baseDensity * 0.72 +
        intersectionPeak1 +
        intersectionPeak2 +
        gateApproachWave +
        weatherTrafficBoost
    );
    const trafficDensityPercent = Math.max(12, Math.min(96, rawDensity));

    let trafficLevel: TrafficLevel = 'LOW';
    if (trafficDensityPercent >= 78) trafficLevel = 'SEVERELY_CONGESTED';
    else if (trafficDensityPercent >= 60) trafficLevel = 'HEAVY';
    else if (trafficDensityPercent >= 40) trafficLevel = 'MODERATE';

    // Effective speed in km/h factoring in BPR density + slope + vehicle priority
    const freeFlowSpeed =
      scenarioType === 'AMBULANCE_DISPATCH'
        ? 62
        : vehicleType === 'motorcycle'
        ? 45
        : 48;
    const congestionFactor =
      scenarioType === 'AMBULANCE_DISPATCH'
        ? 1 - (trafficDensityPercent / 100) * 0.35
        : vehicleType === 'motorcycle'
        ? 1 - (trafficDensityPercent / 100) * 0.45
        : 1 - (trafficDensityPercent / 100) * 0.62;
    const slopePenalty = Math.abs(slopePercent) > 3.5 ? 0.88 : 1.0;

    const speedKmh = Math.max(
      12,
      Math.round(freeFlowSpeed * congestionFactor * slopePenalty)
    );

    // ISO 2631-1 Whole-Body Vibration RMS (m/s^2)
    const vibrationRms = Number(
      (
        0.22 +
        Math.abs(slopePercent) * 0.045 +
        (trafficDensityPercent > 70 ? 0.12 : 0.04) -
        (scenarioType === 'AMBULANCE_DISPATCH' ? 0.08 : 0)
      ).toFixed(2)
    );

    // Map road segment name from route steps
    const stepIndex =
      route.steps && route.steps.length > 0
        ? Math.min(
            route.steps.length - 1,
            Math.floor(progress * route.steps.length)
          )
        : 0;
    const roadSegmentLabel =
      route.steps?.[stepIndex]?.road_name || 'Trục Đường Đô Thị';

    points.push({
      index: i,
      lat,
      lng,
      distanceKm,
      progressFraction: Number(progress.toFixed(3)),
      elevationMeters,
      slopePercent,
      trafficDensityPercent,
      trafficLevel,
      speedKmh,
      vibrationRms: Math.max(0.15, vibrationRms),
      roadSegmentLabel,
    });
  }

  // Extract 3-4 key obstacles along the route for visual callouts on the D3 chart & 3D map
  const obstacles: RouteObstacle[] = [];

  if (points.length >= 4) {
    // 1. Highest elevation point (Overpass / Bridge)
    let maxElevPt = points[0];
    for (const p of points) {
      if (p.elevationMeters > maxElevPt.elevationMeters) maxElevPt = p;
    }
    obstacles.push({
      id: 'obs-overpass-crest',
      pointIndex: maxElevPt.index,
      lat: maxElevPt.lat,
      lng: maxElevPt.lng,
      distanceKm: maxElevPt.distanceKm,
      elevationMeters: maxElevPt.elevationMeters,
      trafficDensityPercent: maxElevPt.trafficDensityPercent,
      category: 'OVERPASS_BRIDGE',
      title: `Đỉnh Cầu Vượt / Dốc Cầu (${maxElevPt.elevationMeters}m)`,
      severity: Math.abs(maxElevPt.slopePercent) >= 4 ? 'MEDIUM' : 'LOW',
      medicalImpactNote:
        scenarioType === 'AMBULANCE_DISPATCH'
          ? `Độ dốc mố cầu • Cáng thủy lực tự cân bằng (${maxElevPt.vibrationRms} m/s²)`
          : `Đoạn lên dốc cầu vượt trên ${maxElevPt.roadSegmentLabel}`,
      vehicleActionHint:
        scenarioType === 'AMBULANCE_DISPATCH'
          ? 'Giữ đều ga 45km/h qua khe co giãn mố cầu để tránh rung lắc dịch truyền'
          : vehicleType === 'motorcycle'
          ? 'Đi làn hỗn hợp bên phải, giữ khoảng cách an toàn khi lên dốc cầu'
          : 'Giữ làn giữa, ổn định tốc độ qua đỉnh cầu vượt',
    });

    // 2. Peak traffic congestion chokepoint (around middle of route)
    let peakTrafficPt = points[Math.floor(points.length * 0.5)];
    for (const p of points) {
      if (
        p.progressFraction > 0.15 &&
        p.progressFraction < 0.85 &&
        p.trafficDensityPercent > peakTrafficPt.trafficDensityPercent
      ) {
        peakTrafficPt = p;
      }
    }
    obstacles.push({
      id: 'obs-traffic-chokepoint',
      pointIndex: peakTrafficPt.index,
      lat: peakTrafficPt.lat,
      lng: peakTrafficPt.lng,
      distanceKm: peakTrafficPt.distanceKm,
      elevationMeters: peakTrafficPt.elevationMeters,
      trafficDensityPercent: peakTrafficPt.trafficDensityPercent,
      category: 'TRAFFIC_BOTTLENECK',
      title: `Điểm Nghẽn Giao Thông (${peakTrafficPt.trafficDensityPercent}%)`,
      severity:
        peakTrafficPt.trafficDensityPercent >= 75
          ? 'HIGH'
          : peakTrafficPt.trafficDensityPercent >= 55
          ? 'MEDIUM'
          : 'LOW',
      medicalImpactNote: `Mật độ BPR ${peakTrafficPt.trafficDensityPercent}% tại ${peakTrafficPt.roadSegmentLabel} • Tốc độ ~${peakTrafficPt.speedKmh} km/h`,
      vehicleActionHint:
        scenarioType === 'AMBULANCE_DISPATCH'
          ? 'Bật còi hụ & đèn ưu tiên 115 cách ngã tư 150m để xin nhường làn'
          : vehicleType === 'motorcycle'
          ? 'Tận dụng làn xe 2 bánh bên phải để thoát nhanh qua nút giao'
          : 'Chuyển sẵn sang làn rẽ trái/đi thẳng từ sớm, tránh bị kẹt đuôi xe buýt',
    });

    // 3. Lowest elevation dip (Canal basin / potential waterlogging dip around 60%-72%)
    let minElevPt = points[Math.floor(points.length * 0.65)];
    for (const p of points) {
      if (
        p.progressFraction >= 0.52 &&
        p.progressFraction <= 0.78 &&
        p.elevationMeters < minElevPt.elevationMeters
      ) {
        minElevPt = p;
      }
    }
    obstacles.push({
      id: 'obs-low-basin-dip',
      pointIndex: minElevPt.index,
      lat: minElevPt.lat,
      lng: minElevPt.lng,
      distanceKm: minElevPt.distanceKm,
      elevationMeters: minElevPt.elevationMeters,
      trafficDensityPercent: minElevPt.trafficDensityPercent,
      category: 'LOW_LYING_FLOOD_DIP',
      title:
        weather === 'urban_flood_warning'
          ? `Vùng Trũng Cảnh Báo Ngập (${minElevPt.elevationMeters}m)`
          : `Đoạn Nền Đường Thấp (${minElevPt.elevationMeters}m)`,
      severity:
        weather === 'urban_flood_warning'
          ? 'HIGH'
          : weather === 'heavy_rain'
          ? 'MEDIUM'
          : 'LOW',
      medicalImpactNote:
        weather === 'clear'
          ? `Cốt nền thấp ven kênh (${minElevPt.elevationMeters}m), mặt đường khô ráo an toàn`
          : `Cốt nền thấp (${minElevPt.elevationMeters}m) có nguy cơ đọng nước khi mưa lớn / triều cường`,
      vehicleActionHint:
        vehicleType === 'motorcycle' && weather !== 'clear'
          ? 'Cảnh báo Xe Máy: Đi sát tim đường cao ráo để tránh ngập bugi'
          : 'Giảm tốc qua đoạn trũng để tránh dằn xóc mặt đường',
    });

    // 4. Hospital Gate Ramp / Speed Bump at ~92%
    const gatePt = points[Math.max(0, Math.min(points.length - 1, Math.floor(points.length * 0.92)))];
    obstacles.push({
      id: 'obs-hospital-gate-ramp',
      pointIndex: gatePt.index,
      lat: gatePt.lat,
      lng: gatePt.lng,
      distanceKm: gatePt.distanceKm,
      elevationMeters: gatePt.elevationMeters,
      trafficDensityPercent: gatePt.trafficDensityPercent,
      category: 'HOSPITAL_RAMP_GATE',
      title: `Dốc & Gờ Giảm Tốc Cổng Viện (${gatePt.elevationMeters}m)`,
      severity: 'LOW',
      medicalImpactNote:
        scenarioType === 'AMBULANCE_DISPATCH'
          ? 'Gờ giảm tốc trước Sảnh Cấp Cứu • Giảm tốc xuống 15 km/h để bảo vệ cáng'
          : vehicleType === 'motorcycle'
          ? 'Lối rẽ vào Cổng Gửi Xe Máy • Chuẩn bị thẻ xe / QR BookingCare'
          : 'Lối lên Sảnh Drop-off có mái che • Chuẩn bị dừng trả bệnh nhân',
      vehicleActionHint:
        scenarioType === 'AMBULANCE_DISPATCH'
          ? 'Phối hợp điều dưỡng mở sẵn cửa hậu và khóa bánh băng ca'
          : 'Giảm tốc độ < 15 km/h khi qua gờ giảm tốc cổng bệnh viện',
    });
  }

  // Sort obstacles by distance along route
  obstacles.sort((a, b) => a.distanceKm - b.distanceKm);

  const elevations = points.map((p) => p.elevationMeters);
  const slopes = points.map((p) => Math.abs(p.slopePercent));
  const densities = points.map((p) => p.trafficDensityPercent);

  const maxElevationMeters = Number(Math.max(...elevations).toFixed(1));
  const minElevationMeters = Number(Math.min(...elevations).toFixed(1));
  const avgElevationMeters = Number(
    (elevations.reduce((s, v) => s + v, 0) / elevations.length).toFixed(1)
  );
  const maxSlopePercent = Number(Math.max(...slopes).toFixed(1));
  const avgTrafficDensityPercent = Math.round(
    densities.reduce((s, v) => s + v, 0) / densities.length
  );
  const peakTrafficDensityPercent = Math.max(...densities);

  return {
    points,
    obstacles,
    maxElevationMeters,
    minElevationMeters,
    avgElevationMeters,
    maxSlopePercent,
    avgTrafficDensityPercent,
    peakTrafficDensityPercent,
    totalElevationGainMeters: Number(totalElevationGainMeters.toFixed(1)),
  };
}
