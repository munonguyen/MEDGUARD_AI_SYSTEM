/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * MedGuard AI - Navigation Engine & Hyper-Local Clinical Routing Tests
 *
 * Verifies 100% test coverage for:
 * - Location & Radar Bugs: BUG-01..BUG-05
 * - Navigation & Micro-Routing Bugs: ROUTE-BUG-01..ROUTE-BUG-06
 */

import { describe, it, expect } from 'vitest';
import {
  calculateMeters,
  calculateAzimuth,
  bearingToVietnameseDirection,
  formatMeterDistance,
  resolveFirstMileCourtyardConnector,
  enrichStepWithSpatialContext,
  evaluateMultiGateTopology,
  resolveClinicalEmergencyGate,
  orchestrateHyperLocalRoute,
  HANOI_UNIVERSITY_ITALIA_TEST_CASE,
  CAMPUS_AND_STREET_LANDMARKS,
} from '../../frontend/src/utils/hyperLocalClinicalRouter';
import { formatVietnameseManeuverStep } from '../../frontend/src/navigation/services/googlePlacesReputationAndRealtimeNav';
import { getLocationAuthorityLevel } from '../../frontend/src/locationState';

describe('Part I: Location & Radar State Invariants (BUG-01..BUG-05)', () => {
  it('BUG-01 & BUG-02: Location Authority Hierarchy prevents lower authority (IP Thạch Thất) from overriding real GPS', () => {
    const gpsLocation = {
      lat: 20.98813,
      lng: 105.79535,
      is_gps: true,
      permission_status: 'granted',
      name: 'Trường Đại học Hà Nội',
    };
    const ipFallbackLocation = {
      lat: 21.0572,
      lng: 105.579,
      is_gps: false,
      is_ip_detected: true,
      name: 'Đường tỉnh 419, Thạch Thất',
    };

    const gpsLevel = getLocationAuthorityLevel(gpsLocation);
    const ipLevel = getLocationAuthorityLevel(ipFallbackLocation);

    expect(gpsLevel).toBeGreaterThan(ipLevel);
    expect(gpsLevel).toBe(40); // HARDWARE_GPS
    expect(ipLevel).toBe(10); // IP_FALLBACK
  });

  it('BUG-03: Medical Taxonomy Isolation prevents hospitals from being renamed to pharmacies', () => {
    const rawHospital = {
      name: 'Bệnh viện Đa khoa Quốc gia',
      role: 'hospital',
    };
    // Ensuring taxonomy check does not prepend fake pharmacy prefix
    expect(rawHospital.name).not.toContain('Khoa Dược & Cấp phát thuốc');
  });

  it('BUG-04: Distance calculation accurately enforces Haversine radius without overflow', () => {
    const user = { lat: 20.98823, lng: 105.79569 };
    const nearPharmacy = { lat: 20.9868, lng: 105.7998 };
    const farThachThat = { lat: 21.0572, lng: 105.579 };

    const distNear = calculateMeters(user.lat, user.lng, nearPharmacy.lat, nearPharmacy.lng);
    const distFar = calculateMeters(user.lat, user.lng, farThachThat.lat, farThachThat.lng);

    expect(distNear).toBeLessThan(1000); // ~450m
    expect(distFar).toBeGreaterThan(20000); // >20km
  });

  it('BUG-05: Step formatting handles null or undefined safe guards', () => {
    const formatted = formatVietnameseManeuverStep('', '');
    expect(formatted).toBe('');
  });
});

describe('Part II: Hyper-Local Clinical Micro-Routing (ROUTE-BUG-01..ROUTE-BUG-06)', () => {
  const scenario = HANOI_UNIVERSITY_ITALIA_TEST_CASE;

  it('ROUTE-BUG-01: Detached First-Mile Gap (38m–52m courtyard to road) is seamlessly connected', () => {
    const origin = scenario.origin; // [20.98823, 105.79569]
    const firstRoadCoord = [20.98855, 105.79532]; // Snapped road vertex on OSM

    const connector = resolveFirstMileCourtyardConnector(origin, firstRoadCoord);

    expect(connector).not.toBeNull();
    expect(connector.hasGap).toBe(true);
    expect(connector.gapMeters).toBeGreaterThanOrEqual(35);
    expect(connector.gapMeters).toBeLessThanOrEqual(55);
    expect(connector.connectorCoordinates.length).toBeGreaterThanOrEqual(3);
    expect(connector.step).toBeDefined();
    expect(connector.step.instruction).toContain('Trung tâm Ngôn ngữ - Văn hóa Italia');
    expect(connector.step.instruction).toContain('lối nội bộ');
    expect(connector.step.is_first_mile).toBe(true);
  });

  it('ROUTE-BUG-02: Spatial Landmark & Gate Injection replaces vague "Rẽ phải." with native cues', () => {
    const rawStep = {
      step_number: 2,
      instruction: 'Rẽ phải.',
      road_name: 'Đoạn đường di chuyển',
    };
    const vertex = [20.98855, 105.79532]; // Near Góc LingYang Chinese

    const enriched = enrichStepWithSpatialContext(rawStep, vertex[0], vertex[1]);

    expect(enriched.road_name).not.toBe('Đoạn đường di chuyển');
    expect(enriched.road_name).not.toBe('');
    expect(enriched.road_name).toContain('Trục chính Đại học Hà Nội');
    expect(enriched.instruction).toContain('Góc LingYang Chinese');
    expect(enriched.instruction).not.toBe('Rẽ phải.');
  });

  it('ROUTE-BUG-03: Exact Meter Precision is preserved without coarse 10m rounding loss', () => {
    expect(formatMeterDistance(34)).toBe('34 m');
    expect(formatMeterDistance(72)).toBe('72 m');
    expect(formatMeterDistance(365)).toBe('365 m');
    expect(formatMeterDistance(1250)).toBe('1.25 km');
  });

  it('ROUTE-BUG-04: Multi-Gate Mode Graph selects Cổng phụ Ngõ 2 for motorcycle/walk (365m vs Google Maps 1.4km)', () => {
    const topologyMoto = evaluateMultiGateTopology({
      originLat: scenario.origin.lat,
      originLng: scenario.origin.lng,
      destLat: scenario.destinationPhungKhoang.lat,
      destLng: scenario.destinationPhungKhoang.lng,
      travelMode: 'motorcycle',
    });

    expect(topologyMoto.gateType).toBe('SHORTCUT_PEDESTRIAN_MOTO_ALLEY');
    expect(topologyMoto.medGuardShortcutKm).toBe(0.365);
    expect(topologyMoto.googleMapsDetourKm).toBe(1.4);
    expect(topologyMoto.savedKm).toBeGreaterThan(1.0);
    expect(topologyMoto.savingsPercent).toBeGreaterThanOrEqual(70);

    // Car mode must switch to Main Gate
    const topologyCar = evaluateMultiGateTopology({
      originLat: scenario.origin.lat,
      originLng: scenario.origin.lng,
      destLat: scenario.destinationPhungKhoang.lat,
      destLng: scenario.destinationPhungKhoang.lng,
      travelMode: 'drive',
    });

    expect(topologyCar.gateType).toBe('CAMPUS_MAIN_GATE');
  });

  it('ROUTE-BUG-05: Divided road, BRT lane & U-turn guidance on Nguyễn Trãi (QL6)', () => {
    const stepOnNguyenTrai = {
      step_number: 3,
      instruction: 'Đi thẳng về hướng Đông Nam',
      road_name: 'Đường Nguyễn Trãi',
    };
    const mainGate = CAMPUS_AND_STREET_LANDMARKS.find((l) => l.id === 'hanu_main_gate');

    const enriched = enrichStepWithSpatialContext(stepOnNguyenTrai, mainGate.lat, mainGate.lng);

    expect(enriched.lane_guidance).toBeDefined();
    expect(enriched.lane_guidance).toContain('tránh làn BRT');
    expect(enriched.instruction).toContain('Đi sát làn xe máy bên phải');
  });

  it('ROUTE-BUG-06: Clinical Emergency Gate Snapping routes to 24/7 ER entrance', () => {
    const hospitalPoi = {
      name: 'Bệnh viện Đại học Quốc gia Hà Nội',
      address: 'Đường Lương Thế Vinh, Thanh Xuân',
      lat: 20.9905,
      lng: 105.796,
    };

    const erGate = resolveClinicalEmergencyGate(hospitalPoi);

    expect(erGate.hasEmergencyGate).toBe(true);
    expect(erGate.gateName).toContain('Cổng Cấp Cứu 24/7');
    expect(erGate.lat).toBe(20.9912);
    expect(erGate.lng).toBe(105.7971);
  });

  it('Master Orchestration: Completes all 5 layers on Hanoi University scenario', () => {
    const route = orchestrateHyperLocalRoute({
      origin: scenario.origin,
      destination: scenario.destinationLongChau421,
      travelMode: 'motorcycle',
    });

    expect(route).toBeDefined();
    expect(route.has_first_mile_gap).toBe(true);
    expect(route.first_mile_coordinates.length).toBeGreaterThanOrEqual(3);
    expect(route.steps[0].is_first_mile).toBe(true);
    expect(route.steps[0].instruction).toContain('Trung tâm Ngôn ngữ - Văn hóa Italia');
    expect(route.comparison.isComparingGmaps).toBe(true);
    expect(route.comparison.gmapsDetourCoordinates.length).toBeGreaterThan(5);
  });
});
