/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * MedGuard AI - Dedicated 3D Real-Time Medical & BookingCare Navigation Cockpit
 * Single unified 3D spatial perspective engine with OSRM road geometry, 3D building/gate markers,
 * and real-time vehicle physics (Ambulance Provider Fleet vs Motorcycle vs Car/Taxi).
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {
  Navigation,
  Volume2,
  VolumeX,
  Play,
  Pause,
  RotateCcw,
  GitFork,
  Star,
  CornerUpLeft,
  CornerUpRight,
  ArrowUp,
  CheckCircle2,
  Compass,
  Box,
} from 'lucide-react';
import type { DualRoute, RouteStep } from '../services/routingService';
import type { MedicalFacility } from '../data/medicalPoiRegistry';
import type {
  AmbulanceProvider,
  HospitalGateLogistics,
  OperationalScenarioType,
  TransportVehicleType,
  WeatherConditionType,
} from '../services/bookingCareDispatchEngine';
import {
  snapToRoute,
  calculateBearing,
  calculateDistanceMeters,
  calculateRemainingRouteDistance,
  formatDistanceVi,
} from '../utils/navigationMath';
import {
  buildRouteElevationAndTrafficProfile,
  type RouteObstacle,
  type RouteProfilePoint,
} from '../utils/routeElevationTrafficProfile';
import { RouteElevationTrafficChart } from './RouteElevationTrafficChart';

interface NavigationCockpitProps {
  userLocation: { lat: number; lng: number; name?: string; label?: string; isGps?: boolean };
  destination: MedicalFacility;
  activeRoute: DualRoute;
  allPois: MedicalFacility[];
  isNavigating: boolean;
  voiceEnabled: boolean;
  scenarioType: OperationalScenarioType;
  vehicleType: TransportVehicleType;
  weatherCondition?: WeatherConditionType;
  selectedAmbulanceProvider: AmbulanceProvider | null;
  gateLogistics: HospitalGateLogistics;
  overallRouteScore: number;
  onToggleVoice: () => void;
  onSelectFacility: (facility: MedicalFacility) => void;
  onCallHotline: (phone: string) => void;
  onProgressUpdate?: (stats: {
    remainingDistanceMeters: number;
    remainingDurationSeconds: number;
    currentStepIndex: number;
    distanceToNextTurnMeters: number;
    currentSpeedKmh: number;
    headingDegrees: number;
    isOffRoute: boolean;
  }) => void;
  onAutoRerouteRequest: (newStartLat: number, newStartLng: number) => void;
  onToggleAlternativeRoute?: () => void;
  onStopNavigation?: () => void;
  onStartNavigation?: () => void;
}

const STAR_SVG_INLINE = `<svg width="10" height="10" viewBox="0 0 24 24" fill="#f59e0b" stroke="#f59e0b" stroke-width="2" style="display:inline;vertical-align:-1px;"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>`;

export const NavigationCockpit: React.FC<NavigationCockpitProps> = ({
  userLocation,
  destination,
  activeRoute,
  allPois,
  isNavigating,
  voiceEnabled,
  scenarioType,
  vehicleType,
  weatherCondition = 'clear',
  selectedAmbulanceProvider,
  gateLogistics,
  overallRouteScore,
  onToggleVoice,
  onSelectFacility,
  onProgressUpdate,
  onToggleAlternativeRoute,
  onStopNavigation,
  onStartNavigation,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);

  // Map Layers Refs
  const vehicleMarkerRef = useRef<L.Marker | null>(null);
  const scrubberMarkerRef = useRef<L.Marker | null>(null);
  const routeShadowPolylineRef = useRef<L.Polyline | null>(null);
  const routeOutlinePolylineRef = useRef<L.Polyline | null>(null);
  const routeMainPolylineRef = useRef<L.Polyline | null>(null);
  const trafficPolylinesRef = useRef<L.Polyline[]>([]);
  const turnArrowsLayerGroupRef = useRef<L.LayerGroup | null>(null);
  const poiLayerGroupRef = useRef<L.LayerGroup | null>(null);

  // 3D Spatial Camera States (Focused 100% on 3D Navigation)
  const [pitchAngleDeg, setPitchAngleDeg] = useState<number>(32); // 32° Full-Bleed 3D Cockpit Pitch
  const [vehicleCoords, setVehicleCoords] = useState<[number, number]>([
    userLocation.lat,
    userLocation.lng,
  ]);
  const [currentSpeedKmh, setCurrentSpeedKmh] = useState<number>(isNavigating ? 45 : 0);
  const [simPlaying, setSimPlaying] = useState<boolean>(false);
  const [simSpeedMultiplier, setSimSpeedMultiplier] = useState<number>(1);
  const [simPointIndex, setSimPointIndex] = useState<number>(0);
  const [isFollowingVehicle, setIsFollowingVehicle] = useState<boolean>(true);
  const [showStepDrawer, setShowStepDrawer] = useState<boolean>(false);
  const [activeStepIdx, setActiveStepIdx] = useState<number>(0);
  const [distToNextTurn, setDistToNextTurn] = useState<number>(
    activeRoute.steps[0]?.distance_meters || 150
  );

  // Simulation Refs
  const simIndexRef = useRef<number>(0);
  const simTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Compute D3 Elevation & Real-Time Traffic Profile + Obstacles
  const elevationTrafficAnalysis = React.useMemo(
    () =>
      buildRouteElevationAndTrafficProfile({
        route: activeRoute,
        scenarioType,
        vehicleType,
        weather: weatherCondition,
      }),
    [activeRoute, scenarioType, vehicleType, weatherCondition]
  );

  // Compute Expected Arrival Time (HH:mm)
  const computeArrivalTimeStr = (durationMins: number): string => {
    const now = new Date();
    now.setMinutes(now.getMinutes() + durationMins);
    return now.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', hour12: false });
  };

  // 1. Initialize Unified 3D Spatial Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: [userLocation.lat, userLocation.lng],
      zoom: 15,
      zoomControl: false,
      attributionControl: true,
    });

    mapInstanceRef.current = map;
    poiLayerGroupRef.current = L.layerGroup().addTo(map);
    turnArrowsLayerGroupRef.current = L.layerGroup().addTo(map);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap • MedGuard 3D Spatial Routing Engine',
      maxZoom: 19,
      subdomains: 'abc',
      className: 'medguard-3d-map-tiles',
    }).addTo(map);

    map.on('dragstart', () => {
      setIsFollowingVehicle(false);
    });

    setTimeout(() => {
      map.invalidateSize();
    }, 200);

    return () => {
      if (simTimerRef.current) clearInterval(simTimerRef.current);
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // 2. Render 3D Extruded Route Corridor + BPR Traffic Segments + On-Road 3D Turn Callouts
  useEffect(() => {
    const map = mapInstanceRef.current;
    const turnGroup = turnArrowsLayerGroupRef.current;
    if (!map || !activeRoute || activeRoute.coordinates.length < 2) return;

    if (routeShadowPolylineRef.current) map.removeLayer(routeShadowPolylineRef.current);
    if (routeOutlinePolylineRef.current) map.removeLayer(routeOutlinePolylineRef.current);
    if (routeMainPolylineRef.current) map.removeLayer(routeMainPolylineRef.current);
    trafficPolylinesRef.current.forEach((p) => map.removeLayer(p));
    trafficPolylinesRef.current = [];
    if (turnGroup) turnGroup.clearLayers();

    const isBypass = activeRoute.type === 'OPTIMAL_BYPASS';

    // 3D Elevation Drop-Shadow Polyline
    const shadowPoly = L.polyline(activeRoute.coordinates, {
      color: '#020617',
      weight: 18,
      opacity: 0.45,
      lineCap: 'round',
      lineJoin: 'round',
    }).addTo(map);
    routeShadowPolylineRef.current = shadowPoly;

    // Deep Navy 3D Casing
    const outlinePoly = L.polyline(activeRoute.coordinates, {
      color: isBypass ? '#0f172a' : '#1e3a8a',
      weight: 13,
      opacity: 0.95,
      lineCap: 'round',
      lineJoin: 'round',
    }).addTo(map);
    routeOutlinePolylineRef.current = outlinePoly;

    // Primary 3D Glowing Corridor Polyline
    const mainPoly = L.polyline(activeRoute.coordinates, {
      color:
        scenarioType === 'AMBULANCE_DISPATCH'
          ? '#06b6d4'
          : isBypass
          ? '#2563eb'
          : '#3b82f6',
      weight: 8,
      opacity: 1,
      lineCap: 'round',
      lineJoin: 'round',
    }).addTo(map);
    routeMainPolylineRef.current = mainPoly;

    // Overlay Traffic Congestion Segments
    if (activeRoute.trafficSegments && activeRoute.trafficSegments.length > 0) {
      activeRoute.trafficSegments.forEach((seg) => {
        if (
          seg.level === 'MODERATE' ||
          seg.level === 'HEAVY' ||
          seg.level === 'SEVERELY_CONGESTED'
        ) {
          const segPoly = L.polyline(seg.coordinates, {
            color: seg.level === 'SEVERELY_CONGESTED' ? '#ef4444' : '#f59e0b',
            weight: 7,
            opacity: 0.95,
            lineCap: 'round',
            lineJoin: 'round',
          }).addTo(map);
          trafficPolylinesRef.current.push(segPoly);
        }
      });
    }

    // Render 3D Directional Flow Chevrons along the route
    if (turnGroup && activeRoute.coordinates.length > 2) {
      const stride = Math.max(1, Math.floor(activeRoute.coordinates.length / 7));
      for (let i = 1; i < activeRoute.coordinates.length - 1; i += stride) {
        const pt1 = activeRoute.coordinates[i - 1];
        const pt2 = activeRoute.coordinates[i];
        const segBearing = calculateBearing(pt1[0], pt1[1], pt2[0], pt2[1]);
        const chevronHtml = `
          <div class="pointer-events-none flex items-center justify-center" style="transform: rotate(${segBearing}deg);">
            <div class="w-4 h-4 rounded-full bg-white border border-blue-700 shadow flex items-center justify-center text-[9px] font-black text-blue-700 leading-none">
              ▲
            </div>
          </div>
        `;
        L.marker([pt2[0], pt2[1]], {
          icon: L.divIcon({
            html: chevronHtml,
            className: 'medguard-3d-chevron',
            iconSize: [16, 16],
            iconAnchor: [8, 8],
          }),
          zIndexOffset: 350,
        }).addTo(turnGroup);
      }
    }

    // Render Mid-Route Algorithmic Road Condition Badge on the 3D Corridor
    if (turnGroup && activeRoute.coordinates.length > 4) {
      const midIdx = Math.floor(activeRoute.coordinates.length * 0.45);
      const midPt = activeRoute.coordinates[midIdx];
      const condHtml = `
        <div class="pointer-events-none flex flex-col items-center">
          <div class="px-2.5 py-1 rounded-xl bg-slate-950/95 text-white border border-cyan-400/80 shadow-2xl text-[10px] font-bold whitespace-nowrap flex items-center gap-1.5">
            <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>Điểm lộ trình: ${overallRouteScore}/100</span>
            <span class="text-cyan-300">• ${
              scenarioType === 'AMBULANCE_DISPATCH'
                ? 'Luồng Xanh Cấp Cứu 115'
                : vehicleType === 'motorcycle'
                ? 'Tối ưu Xe Máy (Không ngập)'
                : 'Làn Ô Tô (Vào Sảnh Chính)'
            }</span>
          </div>
        </div>
      `;
      L.marker([midPt[0], midPt[1]], {
        icon: L.divIcon({
          html: condHtml,
          className: 'medguard-corridor-telemetry-badge',
          iconSize: [240, 32],
          iconAnchor: [120, -12],
        }),
        zIndexOffset: 480,
      }).addTo(turnGroup);
    }

    // Render Primary Turn Callouts (Max 2 to avoid clutter on 3D plane)
    if (turnGroup && activeRoute.steps.length > 1) {
      activeRoute.steps.slice(1, 3).forEach((step, idx) => {
        if (step.maneuver_type === 'arrive') return;
        const [lat, lng] = step.location;
        if (!lat || !lng) return;

        const turnSymbol =
          step.maneuver_type === 'turn-left'
            ? '↰'
            : step.maneuver_type === 'turn-right'
            ? '↱'
            : '↑';

        const arrowHtml = `
          <div class="relative flex flex-col items-center pointer-events-none">
            ${
              idx === 0
                ? `<div class="mb-1 px-2 py-0.5 rounded-lg bg-slate-900/95 text-white text-[10px] font-extrabold shadow-xl border border-white/30 whitespace-nowrap flex items-center gap-1">
                    <span class="text-cyan-300">${turnSymbol}</span>
                    <span>${step.road_name}</span>
                  </div>`
                : ''
            }
            <div class="w-6 h-6 rounded-full bg-white border-2 border-blue-700 shadow-lg flex items-center justify-center text-blue-700 font-black text-xs">
              ${turnSymbol}
            </div>
          </div>
        `;

        L.marker([lat, lng], {
          icon: L.divIcon({
            html: arrowHtml,
            className: 'medguard-3d-turn-arrow',
            iconSize: [140, 48],
            iconAnchor: [70, 24],
          }),
          zIndexOffset: 450,
        }).addTo(turnGroup);
      });
    }

    // Render Numbered Road Obstacle Badges (1..4) along the 3D Corridor synchronized with D3.js chart
    if (turnGroup && elevationTrafficAnalysis.obstacles.length > 0) {
      elevationTrafficAnalysis.obstacles.forEach((obs, idx) => {
        const bgClass =
          obs.severity === 'HIGH'
            ? 'bg-red-600 border-red-300'
            : obs.severity === 'MEDIUM'
            ? 'bg-amber-600 border-amber-300'
            : 'bg-cyan-700 border-cyan-300';
        const obsHtml = `
          <div class="pointer-events-none flex items-center justify-center">
            <div class="w-5 h-5 rounded-full ${bgClass} border-2 shadow-lg flex items-center justify-center text-white font-black text-[10px] leading-none">
              ${idx + 1}
            </div>
          </div>
        `;
        L.marker([obs.lat, obs.lng], {
          icon: L.divIcon({
            html: obsHtml,
            className: 'medguard-3d-obstacle-pin',
            iconSize: [20, 20],
            iconAnchor: [10, 10],
          }),
          zIndexOffset: 470,
        }).addTo(turnGroup);
      });
    }

    if (!isNavigating) {
      map.fitBounds(outlinePoly.getBounds(), { padding: [85, 85], maxZoom: 15 });
    }
  }, [
    activeRoute,
    isNavigating,
    scenarioType,
    vehicleType,
    overallRouteScore,
    elevationTrafficAnalysis.obstacles,
  ]);

  // 3. Render 3D Extruded Hospital Towers & Upcoming Medical Checkpoints with Verified Google Ratings
  useEffect(() => {
    const map = mapInstanceRef.current;
    const group = poiLayerGroupRef.current;
    if (!map || !group) return;

    group.clearLayers();

    allPois.forEach((poi) => {
      const isSelected = poi.id === destination.id;
      const isHospital = poi.facilityType === 'hospital_emergency';
      const gateLabel = gateLogistics.recommendedGateName.split('—')[0].trim();

      // Full callout for Selected Destination; compact 3D rating pill for backup checkpoints so there is zero label collision
      const iconHtml = isSelected
        ? `
        <div class="cursor-pointer group transition-transform hover:scale-105 flex flex-col items-center">
          <div class="mb-1.5 px-3 py-1.5 rounded-xl bg-slate-950 text-white border-2 border-cyan-400 shadow-[0_10px_25px_rgba(6,182,212,0.5)] text-[11px] font-bold whitespace-nowrap flex flex-col items-center gap-0.5">
            <div class="flex items-center gap-1.5">
              <span>${poi.name.split('—')[0].trim()}</span>
              <span class="px-1.5 py-0.5 rounded bg-amber-400/20 text-amber-300 font-black text-[10px] inline-flex items-center gap-1">
                ${STAR_SVG_INLINE} ${poi.rating.toFixed(1)} (${poi.reviewsCount.toLocaleString()})
              </span>
            </div>
            <div class="text-[10px] font-extrabold text-cyan-300">
              Vào: ${gateLabel}
            </div>
          </div>

          <div class="relative flex items-center justify-center">
            <div class="absolute -inset-3 rounded-full ${
              isHospital ? 'bg-red-500/45' : 'bg-emerald-500/45'
            } animate-ping"></div>
            <div class="w-10 h-10 rounded-2xl flex flex-col items-center justify-center font-black text-white shadow-[0_8px_0_rgba(15,23,42,0.9)] border-2 border-white bg-gradient-to-b from-red-500 to-rose-700">
              <span class="text-sm leading-none">${isHospital ? 'H+' : 'Rx'}</span>
              <span class="text-[8px] font-bold opacity-90">ĐÍCH</span>
            </div>
          </div>
        </div>
      `
        : `
        <div class="cursor-pointer group transition-transform hover:scale-110 flex flex-col items-center" title="${poi.name}">
          <div class="mb-1 px-2 py-0.5 rounded-lg bg-slate-900/90 text-white border border-slate-600 shadow-md text-[10px] font-bold whitespace-nowrap flex items-center gap-1">
            <span>${poi.name.split('—')[0].replace('Bệnh viện', 'BV').replace('Nhà thuốc', 'NT').trim()}</span>
            <span class="text-amber-300 font-black inline-flex items-center gap-0.5">
              ${STAR_SVG_INLINE} ${poi.rating.toFixed(1)}
            </span>
          </div>
          <div class="w-8 h-8 rounded-xl flex items-center justify-center font-black text-white text-xs shadow-[0_5px_0_rgba(15,23,42,0.85)] border border-white ${
            isHospital ? 'bg-rose-600' : 'bg-emerald-600'
          }">
            ${isHospital ? 'H+' : 'Rx'}
          </div>
        </div>
      `;

      const marker = L.marker([poi.lat, poi.lng], {
        icon: L.divIcon({
          html: iconHtml,
          className: 'medguard-3d-poi-tower',
          iconSize: isSelected ? [230, 86] : [140, 56],
          iconAnchor: isSelected ? [115, 72] : [70, 44],
        }),
        zIndexOffset: isSelected ? 950 : 500,
      }).addTo(group);

      marker.on('click', () => {
        onSelectFacility(poi);
      });
    });
  }, [allPois, destination, gateLogistics, onSelectFacility]);

  // 4. Update 3D Vehicle Navigator Puck
  const updateVehiclePuck = useCallback(
    (lat: number, lng: number, heading: number, speed: number) => {
      const map = mapInstanceRef.current;
      if (!map) return;

      setVehicleCoords([lat, lng]);
      setCurrentSpeedKmh(speed);

      const vehicleBadgeLabel =
        scenarioType === 'AMBULANCE_DISPATCH'
          ? selectedAmbulanceProvider?.shortName || 'Xe Cấp Cứu 115'
          : vehicleType === 'motorcycle'
          ? 'Xe Máy Đi Khám'
          : 'Ô Tô / Taxi Đặt Khám';

      const ringColor =
        scenarioType === 'AMBULANCE_DISPATCH'
          ? 'border-red-500 shadow-[0_6px_24px_rgba(239,68,68,0.65)]'
          : vehicleType === 'motorcycle'
          ? 'border-cyan-400 shadow-[0_6px_24px_rgba(6,182,212,0.55)]'
          : 'border-blue-500 shadow-[0_6px_24px_rgba(37,99,235,0.55)]';

      const arrowFill =
        scenarioType === 'AMBULANCE_DISPATCH'
          ? '#ef4444'
          : vehicleType === 'motorcycle'
          ? '#06b6d4'
          : '#2563eb';

      const puckHtml = `
        <div class="relative flex flex-col items-center justify-center">
          <div class="w-12 h-12 rounded-full bg-slate-950/95 border-2 ${ringColor} flex items-center justify-center" style="transform: rotate(${heading}deg); transition: transform 0.25s linear;">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L4.5 20.29L5.21 21L12 18L18.79 21L19.5 20.29L12 2Z" fill="${arrowFill}" stroke="#ffffff" stroke-width="1.5" stroke-linejoin="round"/>
            </svg>
          </div>
          <div class="mt-1 px-2.5 py-0.5 rounded-full bg-slate-950 text-white font-extrabold text-[10px] shadow-lg border border-cyan-400/60 whitespace-nowrap flex items-center gap-1">
            ${
              scenarioType === 'AMBULANCE_DISPATCH'
                ? '<span class="w-2 h-2 rounded-full bg-red-500 animate-ping"></span>'
                : ''
            }
            <span>${vehicleBadgeLabel}</span>
          </div>
        </div>
      `;

      if (!vehicleMarkerRef.current) {
        const marker = L.marker([lat, lng], {
          icon: L.divIcon({
            html: puckHtml,
            className: 'medguard-3d-vehicle-puck',
            iconSize: [140, 74],
            iconAnchor: [70, 28],
          }),
          zIndexOffset: 1000,
        }).addTo(map);
        vehicleMarkerRef.current = marker;
      } else {
        vehicleMarkerRef.current.setLatLng([lat, lng]);
        const el = vehicleMarkerRef.current.getElement();
        if (el) {
          el.innerHTML = puckHtml;
        }
      }

      if (isFollowingVehicle && isNavigating) {
        const rad = (heading * Math.PI) / 180;
        const leadLat = lat + Math.cos(rad) * 0.0005;
        const leadLng = lng + Math.sin(rad) * 0.0005;
        map.panTo([leadLat, leadLng], { animate: true, duration: 0.45 });
      }
    },
    [isFollowingVehicle, isNavigating, scenarioType, vehicleType, selectedAmbulanceProvider]
  );

  // Initialize Vehicle Puck at User Location
  useEffect(() => {
    const initialHeading =
      activeRoute.coordinates.length >= 2
        ? calculateBearing(
            activeRoute.coordinates[0][0],
            activeRoute.coordinates[0][1],
            activeRoute.coordinates[1][0],
            activeRoute.coordinates[1][1]
          )
        : 0;
    updateVehiclePuck(userLocation.lat, userLocation.lng, initialHeading, isNavigating ? 42 : 0);
  }, [userLocation.lat, userLocation.lng, activeRoute, updateVehiclePuck, isNavigating]);

  // 5. Real-Time 3D Simulation Loop
  useEffect(() => {
    if (!simPlaying || !activeRoute || activeRoute.coordinates.length < 2) {
      if (simTimerRef.current) clearInterval(simTimerRef.current);
      return;
    }

    const coords = activeRoute.coordinates;
    const intervalMs = Math.max(120, Math.round(460 / simSpeedMultiplier));

    simTimerRef.current = setInterval(() => {
      simIndexRef.current += 1;
      if (simIndexRef.current >= coords.length) {
        simIndexRef.current = 0;
      }
      setSimPointIndex(simIndexRef.current);

      const currentPoint = coords[simIndexRef.current];
      const nextPoint = coords[Math.min(simIndexRef.current + 1, coords.length - 1)];

      const heading = calculateBearing(
        currentPoint[0],
        currentPoint[1],
        nextPoint[0],
        nextPoint[1]
      );
      const baseSpeed =
        scenarioType === 'AMBULANCE_DISPATCH'
          ? 54
          : vehicleType === 'motorcycle'
          ? 38
          : 34;
      const simulatedSpeed = Math.min(80, Math.round(baseSpeed * simSpeedMultiplier));

      updateVehiclePuck(currentPoint[0], currentPoint[1], heading, simulatedSpeed);

      const snap = snapToRoute(currentPoint[0], currentPoint[1], coords);
      const stepCount = activeRoute.steps.length;
      const stepIdx = Math.min(
        stepCount - 1,
        Math.floor((simIndexRef.current / coords.length) * stepCount)
      );
      setActiveStepIdx(stepIdx);

      const targetStep = activeRoute.steps[Math.min(stepIdx + 1, stepCount - 1)];
      const distNext = targetStep
        ? calculateDistanceMeters(
            currentPoint[0],
            currentPoint[1],
            targetStep.location[0],
            targetStep.location[1]
          )
        : 50;
      setDistToNextTurn(distNext);

      if (onProgressUpdate) {
        const remMeters = calculateRemainingRouteDistance(snap.closestIndex, coords);
        onProgressUpdate({
          remainingDistanceMeters: remMeters,
          remainingDurationSeconds: Math.round(remMeters / 11),
          currentStepIndex: stepIdx,
          distanceToNextTurnMeters: distNext,
          currentSpeedKmh: simulatedSpeed,
          headingDegrees: heading,
          isOffRoute: false,
        });
      }
    }, intervalMs);

    return () => {
      if (simTimerRef.current) clearInterval(simTimerRef.current);
    };
  }, [
    simPlaying,
    simSpeedMultiplier,
    activeRoute,
    scenarioType,
    vehicleType,
    updateVehiclePuck,
    onProgressUpdate,
  ]);

  // Synchronize D3.js chart hover/obstacle selection with a 3D beacon on the map
  const handleHoverD3Point = useCallback((pt: RouteProfilePoint | null) => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (!pt) {
      if (scrubberMarkerRef.current) {
        map.removeLayer(scrubberMarkerRef.current);
        scrubberMarkerRef.current = null;
      }
      return;
    }

    const beaconHtml = `
      <div class="pointer-events-none flex flex-col items-center">
        <div class="mb-1 px-2 py-0.5 rounded-lg bg-slate-950/95 text-white border border-cyan-400 shadow-xl text-[10px] font-bold whitespace-nowrap">
          Km ${pt.distanceKm.toFixed(2)} • ${pt.elevationMeters}m • Mật độ ${pt.trafficDensityPercent}%
        </div>
        <div class="w-4 h-4 rounded-full bg-cyan-400 border-2 border-white shadow-[0_0_14px_rgba(34,211,238,0.9)]"></div>
      </div>
    `;

    if (!scrubberMarkerRef.current) {
      scrubberMarkerRef.current = L.marker([pt.lat, pt.lng], {
        icon: L.divIcon({
          html: beaconHtml,
          className: 'medguard-d3-scrubber-beacon',
          iconSize: [180, 44],
          iconAnchor: [90, 36],
        }),
        zIndexOffset: 980,
      }).addTo(map);
    } else {
      scrubberMarkerRef.current.setLatLng([pt.lat, pt.lng]);
      const el = scrubberMarkerRef.current.getElement();
      if (el) el.innerHTML = beaconHtml;
    }
  }, []);

  const handleSelectD3Obstacle = useCallback((obs: RouteObstacle) => {
    const map = mapInstanceRef.current;
    if (!map) return;
    setIsFollowingVehicle(false);
    map.flyTo([obs.lat, obs.lng], 16, { animate: true, duration: 0.65 });
  }, []);

  const handleRecenter = () => {
    setIsFollowingVehicle(true);
    const map = mapInstanceRef.current;
    if (map) {
      map.flyTo(vehicleCoords, 16, { animate: true, duration: 0.7 });
    }
  };

  const currentStep: RouteStep =
    activeRoute.steps[activeStepIdx] || activeRoute.steps[0];
  const nextStep: RouteStep | null =
    activeRoute.steps[activeStepIdx + 1] || null;

  const renderTurnIcon = (type?: string) => {
    switch (type) {
      case 'turn-left':
        return <CornerUpLeft className="w-8 h-8 sm:w-9 sm:h-9 text-white stroke-[2.5]" />;
      case 'turn-right':
        return <CornerUpRight className="w-8 h-8 sm:w-9 sm:h-9 text-white stroke-[2.5]" />;
      case 'arrive':
        return <CheckCircle2 className="w-8 h-8 sm:w-9 sm:h-9 text-emerald-300 stroke-[2.5]" />;
      default:
        return <ArrowUp className="w-8 h-8 sm:w-9 sm:h-9 text-white stroke-[2.5]" />;
    }
  };

  return (
    <div
      data-testid="3d-navigation-cockpit"
      className="w-full rounded-3xl overflow-hidden border border-slate-200/90 shadow-[0_8px_30px_rgb(15,23,42,0.08)] bg-white flex flex-col"
    >
      <style>{`
        .medguard-3d-map-tiles {
          filter: brightness(0.99) contrast(1.04) saturate(1.12);
        }
      `}</style>

      {/* Top 3D Spatial Viewport Stage */}
      <div className="relative w-full h-[460px] sm:h-[500px] overflow-hidden bg-slate-900">
        {/* Subtle Top Horizon Sky Vignette so HUD is ultra-legible */}
      {pitchAngleDeg > 0 && (
        <div
          className="absolute top-0 inset-x-0 h-24 z-10 pointer-events-none"
          style={{
            background:
              'linear-gradient(to bottom, rgba(2, 6, 23, 0.72) 0%, rgba(15, 23, 42, 0.25) 60%, rgba(15, 23, 42, 0) 100%)',
          }}
        />
      )}

      {/* Full-Bleed 3D Perspective Map Viewport (Oversized bounds prevent top/side clipping when tilted!) */}
      <div
        ref={mapContainerRef}
        style={{
          transform:
            pitchAngleDeg > 0
              ? `perspective(1100px) rotateX(${pitchAngleDeg}deg) scale(${
                  pitchAngleDeg >= 30 ? 1.24 : 1.14
                })`
              : 'none',
          transformOrigin: '50% 60%',
        }}
        className="w-full h-full absolute inset-0 z-0 bg-slate-900 transition-transform duration-500 ease-out"
      />

      {/* =====================================================================
          1. TOP-LEFT 3D TURN-BY-TURN & HOSPITAL GATE DIRECTIVE HUD
      ===================================================================== */}
      {currentStep && (
        <div className="absolute top-3 left-3 right-3 sm:right-auto z-20 sm:w-[390px] rounded-2xl bg-[#0b534b] text-white shadow-[0_12px_32px_rgba(0,0,0,0.45)] border border-emerald-400/40 overflow-hidden">
          <div className="p-3 sm:p-3.5 flex items-center gap-3">
            <div className="flex flex-col items-center justify-center shrink-0 pr-2.5 border-r border-emerald-400/25">
              {renderTurnIcon(currentStep.maneuver_type)}
              <span className="text-xs font-black text-emerald-200 mt-0.5 tabular-nums">
                {formatDistanceVi(distToNextTurn)}
              </span>
            </div>

            <div className="min-w-0 flex-1">
              <div className="text-[11px] font-bold text-emerald-200 flex items-center gap-1.5">
                <span className="px-1.5 py-0.5 rounded bg-emerald-950 text-cyan-300 text-[10px] font-black shrink-0">
                  3D REAL-TIME
                </span>
                <span className="truncate">
                  Đích: {gateLogistics.recommendedGateName.split('—')[0].trim()}
                </span>
              </div>
              <h2 className="text-base sm:text-lg font-black text-white tracking-tight truncate leading-tight mt-0.5">
                {currentStep.road_name}
              </h2>
              <p className="text-xs text-emerald-100/90 truncate mt-0.5">
                {currentStep.instruction}
              </p>
            </div>
          </div>

          <div className="bg-[#073b35] px-3.5 py-1.5 flex items-center justify-between gap-2 text-[11px] border-t border-emerald-400/20">
            <div className="truncate text-emerald-100">
              <span className="font-bold uppercase text-emerald-300 mr-1.5">Tiếp theo:</span>
              <span>
                {nextStep
                  ? nextStep.instruction
                  : `Vào thẳng ${gateLogistics.recommendedGateName}`}
              </span>
            </div>
            <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-200 font-bold shrink-0 tabular-nums">
              Điểm đường: {overallRouteScore}/100
            </span>
          </div>
        </div>
      )}

      {/* =====================================================================
          2. TOP-RIGHT 3D CAMERA PITCH CONTROLLER
      ===================================================================== */}
      <div className="absolute top-[134px] sm:top-3.5 right-3 z-20 flex flex-col items-end gap-2">
        <div className="bg-slate-950 p-1 rounded-2xl border border-cyan-500/40 shadow-xl text-white flex items-center gap-1">
          <span className="px-2 py-1 text-[10px] font-black uppercase text-cyan-300 flex items-center gap-1">
            <Box className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Góc 3D:</span>
          </span>
          {[
            { deg: 32, label: '3D 32°' },
            { deg: 18, label: '3D 18°' },
            { deg: 0, label: '2D 0°' },
          ].map((opt) => (
            <button
              key={opt.deg}
              type="button"
              data-testid={`pitch-btn-${opt.deg}`}
              onClick={() => setPitchAngleDeg(opt.deg)}
              className={`px-2.5 py-1 text-xs font-extrabold rounded-xl transition-all cursor-pointer tabular-nums ${
                pitchAngleDeg === opt.deg
                  ? 'bg-cyan-500 text-slate-950 shadow'
                  : 'text-slate-300 hover:text-white'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* =====================================================================
          3. RIGHT-SIDE FLOATING COCKPIT CONTROLS
      ===================================================================== */}
      <div className="absolute right-3 top-[184px] sm:top-1/2 sm:-translate-y-1/2 z-20 flex flex-col gap-2">
        <button
          type="button"
          onClick={handleRecenter}
          className="w-11 h-11 rounded-full bg-slate-950 hover:bg-slate-900 text-white shadow-xl border border-slate-700 flex flex-col items-center justify-center transition-all active:scale-90 cursor-pointer"
          title="Đưa tâm bản đồ 3D về phương tiện"
        >
          <span className="text-[9px] font-black text-red-400 leading-none">3D</span>
          <Compass className="w-5 h-5 text-cyan-400" />
        </button>

        <button
          type="button"
          onClick={onToggleVoice}
          className={`w-11 h-11 rounded-full shadow-xl border flex items-center justify-center transition-all active:scale-90 cursor-pointer ${
            voiceEnabled
              ? 'bg-slate-950 text-cyan-400 border-cyan-500/50'
              : 'bg-slate-900 text-slate-500 border-slate-700'
          }`}
          title={voiceEnabled ? 'Đang bật giọng nói dẫn đường' : 'Đang tắt giọng nói'}
        >
          {voiceEnabled ? <Volume2 className="w-5 h-5" /> : <VolumeX className="w-5 h-5" />}
        </button>

        <button
          type="button"
          onClick={() => {
            if (onToggleAlternativeRoute) onToggleAlternativeRoute();
            setShowStepDrawer(!showStepDrawer);
          }}
          className={`w-11 h-11 rounded-full shadow-xl border flex items-center justify-center transition-all active:scale-90 cursor-pointer ${
            showStepDrawer
              ? 'bg-cyan-500 text-slate-950 border-cyan-400'
              : 'bg-slate-950 text-white border-slate-700 hover:bg-slate-900'
          }`}
          title="Xem chi tiết các chặng rẽ & đổi lộ trình"
        >
          <GitFork className="w-5 h-5" />
        </button>
      </div>

      {/* =====================================================================
          4. BOTTOM COCKPIT TELEMETRY, SIMULATION & ETA RIBBON
      ===================================================================== */}
      <div className="absolute bottom-3.5 left-3.5 right-3.5 z-20 flex flex-wrap items-end justify-between gap-2.5 pointer-events-none">
        <div className="flex flex-wrap items-center gap-2.5 pointer-events-auto">
          <div className="bg-slate-950 text-white rounded-2xl px-4 py-3 shadow-2xl border border-slate-800 flex flex-wrap items-center gap-4 justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xl sm:text-2xl font-black text-cyan-400 tracking-tight tabular-nums">
                  {activeRoute.duration_minutes} phút
                </span>
                <span className="text-xs font-bold text-slate-300 tabular-nums">
                  ({activeRoute.distance_km} km)
                </span>
                <span className="px-2 py-0.5 rounded-full bg-amber-500/20 border border-amber-500/40 text-amber-300 text-xs font-black flex items-center gap-1 tabular-nums">
                  <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />
                  {destination.rating.toFixed(1)}
                </span>
              </div>
              <div className="text-[11px] font-semibold text-slate-300 mt-0.5 flex flex-wrap items-center gap-1.5">
                <span>Dự kiến tới: {computeArrivalTimeStr(activeRoute.duration_minutes)}</span>
                <span>•</span>
                <span className="text-emerald-300 font-bold">
                  {gateLogistics.parkingOrDropoffType.split('(')[0].trim()}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                data-testid="simulate-3d-drive-btn"
                onClick={() => setSimPlaying(!simPlaying)}
                className={`px-3.5 py-2 rounded-xl font-extrabold text-xs flex items-center gap-1.5 transition-all shadow-sm active:scale-95 cursor-pointer ${
                  simPlaying
                    ? 'bg-amber-500 text-slate-950'
                    : 'bg-slate-800 text-cyan-300 hover:bg-slate-700 border border-cyan-500/30'
                }`}
              >
                {simPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                <span>{simPlaying ? 'Tạm dừng 3D' : 'Mô phỏng chạy 3D'}</span>
              </button>

              {isNavigating ? (
                <button
                  type="button"
                  onClick={onStopNavigation}
                  className="px-4 py-2 rounded-xl bg-red-600 hover:bg-red-500 text-white font-black text-xs sm:text-sm shadow-md transition-all active:scale-95 cursor-pointer"
                >
                  Kết thúc
                </button>
              ) : (
                <button
                  type="button"
                  onClick={onStartNavigation}
                  className="px-4 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-black text-xs sm:text-sm shadow-md transition-all active:scale-95 cursor-pointer"
                >
                  Bắt đầu Dẫn đường 3D
                </button>
              )}
            </div>
          </div>

          {simPlaying && (
            <div className="bg-slate-950/95 text-white px-3 py-2 rounded-xl border border-slate-700 shadow-xl flex items-center gap-2 text-xs font-bold tabular-nums">
              <span>{currentSpeedKmh} km/h</span>
              <button
                type="button"
                onClick={() =>
                  setSimSpeedMultiplier(
                    simSpeedMultiplier === 1 ? 2 : simSpeedMultiplier === 2 ? 4 : 1
                  )
                }
                className="px-2 py-0.5 rounded-lg bg-cyan-500 text-slate-950 font-black cursor-pointer"
              >
                {simSpeedMultiplier}x
              </button>
              <button
                type="button"
                onClick={() => {
                  simIndexRef.current = 0;
                  setSimPointIndex(0);
                  if (activeRoute.coordinates[0]) {
                    updateVehiclePuck(
                      activeRoute.coordinates[0][0],
                      activeRoute.coordinates[0][1],
                      0,
                      0
                    );
                  }
                }}
                className="p-1 text-slate-300 hover:text-white cursor-pointer"
                title="Đưa phương tiện về lại điểm xuất phát"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Step-by-Step Turn Drawer if opened */}
      {showStepDrawer && (
        <div className="absolute inset-y-0 right-0 w-full sm:w-80 bg-slate-950/95 backdrop-blur-xl border-l border-slate-800 z-30 p-4 flex flex-col justify-between shadow-2xl">
          <div>
            <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3">
              <div className="flex items-center gap-2">
                <Navigation className="w-4 h-4 text-cyan-400" />
                <h3 className="text-sm font-bold text-white">Chi Tiết Từng Chặng Rẽ 3D</h3>
              </div>
              <button
                type="button"
                onClick={() => setShowStepDrawer(false)}
                className="text-xs text-slate-400 hover:text-white p-1 cursor-pointer"
              >
                ✕ Đóng
              </button>
            </div>

            <div className="space-y-2.5 overflow-y-auto max-h-[380px] pr-1">
              {activeRoute.steps.map((st) => (
                <div
                  key={st.step_number}
                  className="p-2.5 rounded-xl bg-slate-900/90 border border-slate-800 flex items-start gap-2.5 text-xs"
                >
                  <div className="w-6 h-6 rounded-lg bg-cyan-500 text-slate-950 font-black flex items-center justify-center shrink-0 mt-0.5 tabular-nums">
                    {st.step_number}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-1">
                      <span className="font-bold text-white truncate">{st.instruction}</span>
                      <span className="text-[10px] text-cyan-400 font-semibold shrink-0 tabular-nums">
                        {formatDistanceVi(st.distance_meters)}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-400 mt-0.5 truncate">
                      {st.road_name}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="pt-3 border-t border-slate-800 text-[11px] text-slate-400 text-center tabular-nums">
            Tổng lộ trình: {activeRoute.distance_km} km • {activeRoute.duration_minutes} phút
          </div>
        </div>
      )}
      </div>

      {/* =====================================================================
          5. D3.JS ROUTE ELEVATION PROFILE & REAL-TIME TRAFFIC DENSITY DOCK
      ===================================================================== */}
      <RouteElevationTrafficChart
        analysis={elevationTrafficAnalysis}
        currentPointIndex={simPointIndex}
        scenarioType={scenarioType}
        vehicleType={vehicleType}
        onHoverPoint={handleHoverD3Point}
        onSelectObstacle={handleSelectD3Obstacle}
      />
    </div>
  );
};
