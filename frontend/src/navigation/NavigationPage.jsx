import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import MaplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
import * as turf from '@turf/turf';
import {
  AlertTriangle,
  Ambulance,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Bike,
  Building2,
  Car,
  Check,
  CheckCircle2,
  ChevronDown,
  Clock,
  Coffee,
  Compass,
  CornerUpLeft,
  CornerUpRight,
  ExternalLink,
  Footprints,
  Fuel,
  HeartPulse,
  Layers,
  LocateFixed,
  MapPin,
  Mic,
  MicOff,
  Navigation,
  Navigation2,
  Pause,
  PhoneCall,
  Pill,
  Play,
  RefreshCw,
  RotateCcw,
  Route,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  Utensils,
  Volume1,
  Volume2,
  VolumeX,
  X,
  Zap,
  BookOpen,
  Download,
  FileText,
  Plus,
  Minus,
  Maximize2,
  Minimize2,
  ChevronUp,
} from 'lucide-react';
import {
  getSavedUserLocation,
  saveUserLocation,
  requestBrowserGeolocation,
  autoDetectLiveLocation,
  watchLiveUserLocation,
  searchAddressGeocode,
  LOCATION_PRESETS,
  getLocationAuthorityLevel,
} from '../locationState';
import {
  computeMedicalTrustScore,
  isValidVerifiedMedicalPoiName,
  formatVietnameseManeuverStep,
} from './services/googlePlacesReputationAndRealtimeNav';
import GoogleReviewsPanel from './GoogleReviewsPanel';
import { useOnDemandMedicalMap } from './services/useOnDemandMedicalMap';
import {
  scanHyperLocalMedicalPois,
  formatDistanceLabel,
  buildMedicalCalloutNote,
  selectNonOverlappingMapPins,
} from '../utils/hyperLocalMedicalScanner';
import {
  orchestrateHyperLocalRoute,
  HANOI_UNIVERSITY_ITALIA_TEST_CASE,
} from '../utils/hyperLocalClinicalRouter';
import './NavigationPage.css';

// Configure MapLibre Web Worker URL for Vite bundled environments
if (typeof window !== 'undefined' && maplibregl?.setWorkerUrl) {
  try {
    maplibregl.setWorkerUrl(MaplibreWorkerUrl);
  } catch {}
}

const GEOAPIFY_API_KEY = '224447c8da3b4555a5380f31ddb56bf3';

// High-detail Google Maps HD (@2x Retina with Vietnamese labels) + 3D building extrusions
const STREETS_RASTER_STYLE = {
  version: 8,
  sources: {
    'google-roads-hd': {
      type: 'raster',
      tiles: [
        'https://mt0.google.com/vt/lyrs=m&hl=vi&x={x}&y={y}&z={z}&scale=2',
        'https://mt1.google.com/vt/lyrs=m&hl=vi&x={x}&y={y}&z={z}&scale=2',
        'https://mt2.google.com/vt/lyrs=m&hl=vi&x={x}&y={y}&z={z}&scale=2',
        'https://mt3.google.com/vt/lyrs=m&hl=vi&x={x}&y={y}&z={z}&scale=2',
      ],
      tileSize: 256,
      attribution: '© Google Maps, OpenStreetMap contributors',
      maxzoom: 21,
    },
    'geoapify-buildings': {
      type: 'vector',
      url: `https://maps.geoapify.com/v1/styles/osm-bright-smooth/data.json?apiKey=${GEOAPIFY_API_KEY}`,
    },
  },
  layers: [
    {
      id: 'google-streets-base',
      type: 'raster',
      source: 'google-roads-hd',
      minzoom: 0,
      maxzoom: 22,
    },
    {
      id: '3d-buildings',
      type: 'fill-extrusion',
      source: 'geoapify-buildings',
      'source-layer': 'building',
      minzoom: 15,
      paint: {
        'fill-extrusion-color': [
          'interpolate',
          ['linear'],
          ['coalesce', ['get', 'render_height'], 10],
          0,
          '#e2e8f0',
          20,
          '#cbd5e1',
          60,
          '#94a3b8',
        ],
        'fill-extrusion-height': [
          'interpolate',
          ['linear'],
          ['zoom'],
          15,
          0,
          15.6,
          ['coalesce', ['get', 'render_height'], 10],
        ],
        'fill-extrusion-base': [
          'interpolate',
          ['linear'],
          ['zoom'],
          15,
          0,
          15.6,
          ['coalesce', ['get', 'render_min_height'], 0],
        ],
        'fill-extrusion-opacity': 0.42,
      },
    },
  ],
};

const SATELLITE_RASTER_STYLE = {
  version: 8,
  sources: {
    'google-hybrid-hd': {
      type: 'raster',
      tiles: [
        'https://mt0.google.com/vt/lyrs=y&hl=vi&x={x}&y={y}&z={z}&scale=2',
        'https://mt1.google.com/vt/lyrs=y&hl=vi&x={x}&y={y}&z={z}&scale=2',
        'https://mt2.google.com/vt/lyrs=y&hl=vi&x={x}&y={y}&z={z}&scale=2',
        'https://mt3.google.com/vt/lyrs=y&hl=vi&x={x}&y={y}&z={z}&scale=2',
      ],
      tileSize: 256,
      attribution: '© Google Maps Satellite Hybrid',
      maxzoom: 21,
    },
  },
  layers: [
    {
      id: 'google-hybrid-base',
      type: 'raster',
      source: 'google-hybrid-hd',
      minzoom: 0,
      maxzoom: 22,
    },
  ],
};

const DARK_RASTER_STYLE = {
  version: 8,
  sources: {
    'dark-tiles': {
      type: 'raster',
      tiles: [
        `https://maps.geoapify.com/v1/tile/dark-matter-dark-grey/{z}/{x}/{y}@2x.png?apiKey=${GEOAPIFY_API_KEY}`,
      ],
      tileSize: 256,
      attribution: '© Geoapify, OpenStreetMap contributors',
      maxzoom: 20,
    },
    'geoapify-buildings': {
      type: 'vector',
      url: `https://maps.geoapify.com/v1/styles/dark-matter-dark-grey/data.json?apiKey=${GEOAPIFY_API_KEY}`,
    },
  },
  layers: [
    {
      id: 'dark-base',
      type: 'raster',
      source: 'dark-tiles',
      minzoom: 0,
      maxzoom: 22,
    },
    {
      id: '3d-buildings-dark',
      type: 'fill-extrusion',
      source: 'geoapify-buildings',
      'source-layer': 'building',
      minzoom: 14.5,
      paint: {
        'fill-extrusion-color': '#1e293b',
        'fill-extrusion-height': [
          'interpolate',
          ['linear'],
          ['zoom'],
          14.5,
          0,
          15,
          ['coalesce', ['get', 'render_height'], 12],
        ],
        'fill-extrusion-base': [
          'interpolate',
          ['linear'],
          ['zoom'],
          14.5,
          0,
          15,
          ['coalesce', ['get', 'render_min_height'], 0],
        ],
        'fill-extrusion-opacity': 0.75,
      },
    },
  ],
};

const OSM_RASTER_STYLE = {
  version: 8,
  sources: {
    'osm-tiles': {
      type: 'raster',
      tiles: [
        'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      ],
      tileSize: 256,
      attribution: '© OpenStreetMap contributors',
      maxzoom: 19,
    },
  },
  layers: [
    {
      id: 'osm-base',
      type: 'raster',
      source: 'osm-tiles',
      minzoom: 0,
      maxzoom: 22,
    },
  ],
};

export function getMapLibreStyleForTheme(theme) {
  if (theme === 'satellite') return SATELLITE_RASTER_STYLE;
  if (theme === 'dark') return DARK_RASTER_STYLE;
  if (theme === 'osm') return OSM_RASTER_STYLE;
  return STREETS_RASTER_STYLE;
}

/**
 * Generate instantaneous smooth client-side route with steps
 * Ensures map line and turn-by-turn guidance are visible with ZERO delay
 */
export function generateClientFallbackRoute(
  startLat,
  startLng,
  destLat,
  destLng,
  destName = 'Điểm đến',
  mode = 'motorcycle'
) {
  const orchestrated = orchestrateHyperLocalRoute({
    origin: { lat: startLat, lng: startLng },
    destination: { lat: destLat, lng: destLng, name: destName },
    travelMode: mode,
  });
  if (orchestrated) {
    return orchestrated;
  }

  const dLat = (destLat - startLat) * (Math.PI / 180);
  const dLng = (destLng - startLng) * (Math.PI / 180);
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(startLat * (Math.PI / 180)) *
      Math.cos(destLat * (Math.PI / 180)) *
      Math.sin(dLng / 2) *
      Math.sin(dLng / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  const rawDistKm = 6371 * c;
  const distKm = Math.max(0.1, Number((rawDistKm * 1.25).toFixed(3)));
  const speedKmh = mode === 'walk' ? 4.5 : mode === 'drive' ? 35 : 28;
  const etaMinutes = Math.max(1, Math.round((distKm / speedKmh) * 60));

  const midLat = (startLat + destLat) / 2;
  const midLng = (startLng + destLng) / 2;
  const coordinates = [
    [Number(startLat.toFixed(6)), Number(startLng.toFixed(6))],
    [Number(startLat.toFixed(6)), Number(midLng.toFixed(6))],
    [Number(midLat.toFixed(6)), Number(midLng.toFixed(6))],
    [Number(destLat.toFixed(6)), Number(midLng.toFixed(6))],
    [Number(destLat.toFixed(6)), Number(destLng.toFixed(6))],
  ];

  const steps = [
    {
      step_number: 1,
      instruction: `Xuất phát theo trục giao thông hướng về phía ${destName}.`,
      distance_km: Number((distKm * 0.3).toFixed(3)),
      distance_meters: Math.round(distKm * 300),
      time_seconds: Math.round(etaMinutes * 60 * 0.3),
      road_name: 'Trục đường xuất phát',
    },
    {
      step_number: 2,
      instruction: `Đi thẳng theo trục đường đô thị hướng tới ${destName}.`,
      distance_km: Number((distKm * 0.5).toFixed(3)),
      distance_meters: Math.round(distKm * 500),
      time_seconds: Math.round(etaMinutes * 60 * 0.5),
      road_name: 'Trục đường liên thông',
    },
    {
      step_number: 3,
      instruction: `Điểm đến (${destName}) nằm ở bên tay phải.`,
      distance_km: Number((distKm * 0.2).toFixed(3)),
      distance_meters: Math.round(distKm * 200),
      time_seconds: Math.round(etaMinutes * 60 * 0.2),
      road_name: destName,
    },
  ];

  return {
    distance_km: distKm,
    distance_meters: Math.round(distKm * 1000),
    eta_minutes: etaMinutes,
    mode,
    coordinates,
    steps,
  };
}

/**
 * Safely update or initialize 3D route line in MapLibre WebGL
 * Supports:
 * - Primary high-contrast route polyline
 * - Layer 1: First-mile courtyard connector (cyan dashed line)
 * - Layer 3: Google Maps comparison route (amber dashed line)
 */
export function update3dRouteLine(
  map3d,
  coordinates,
  firstMileCoordinates = [],
  gmapsCoordinates = []
) {
  if (!map3d) return;
  const coords = (coordinates || []).filter(
    (c) => Array.isArray(c) && typeof c[0] === 'number' && typeof c[1] === 'number'
  );
  if (coords.length < 2) return;

  const geojson = {
    type: 'Feature',
    properties: {},
    geometry: {
      type: 'LineString',
      coordinates: coords.map(([lat, lng]) => [lng, lat]),
    },
  };

  const applyData = () => {
    try {
      const src = map3d.getSource('route-source');
      if (src) {
        src.setData(geojson);
      } else {
        map3d.addSource('route-source', {
          type: 'geojson',
          data: geojson,
        });
      }

      // 1. Deep Contrast Casing: dark outline for maximum edge contrast
      if (!map3d.getLayer('route-casing')) {
        map3d.addLayer({
          id: 'route-casing',
          type: 'line',
          source: 'route-source',
          layout: { 'line-join': 'round', 'line-cap': 'round' },
          paint: {
            'line-color': '#0a192f',
            'line-width': 13,
            'line-opacity': 0.92,
          },
        });
      }

      // 2. Ambient High-Tech Glow: neon cyan
      if (!map3d.getLayer('route-glow')) {
        map3d.addLayer({
          id: 'route-glow',
          type: 'line',
          source: 'route-source',
          layout: { 'line-join': 'round', 'line-cap': 'round' },
          paint: {
            'line-color': '#00e5ff',
            'line-width': 9,
            'line-opacity': 0.65,
          },
        });
      }

      // 3. Primary Route Line: vivid cobalt blue
      if (!map3d.getLayer('route-line')) {
        map3d.addLayer({
          id: 'route-line',
          type: 'line',
          source: 'route-source',
          layout: { 'line-join': 'round', 'line-cap': 'round' },
          paint: {
            'line-color': '#2563eb',
            'line-width': 5.5,
            'line-opacity': 1.0,
          },
        });
      }

      // 4. Center Precision Stripe: bright white directional core
      if (!map3d.getLayer('route-inner-core')) {
        map3d.addLayer({
          id: 'route-inner-core',
          type: 'line',
          source: 'route-source',
          layout: { 'line-join': 'round', 'line-cap': 'round' },
          paint: {
            'line-color': '#ffffff',
            'line-width': 1.8,
            'line-opacity': 0.95,
          },
        });
      }

      // 5. Layer 1: First-Mile Courtyard Connector (Cyan Dashed Line)
      if (firstMileCoordinates && firstMileCoordinates.length >= 2) {
        const fmGeojson = {
          type: 'Feature',
          properties: {},
          geometry: {
            type: 'LineString',
            coordinates: firstMileCoordinates.map(([lat, lng]) => [lng, lat]),
          },
        };
        const fmSrc = map3d.getSource('first-mile-source');
        if (fmSrc) {
          fmSrc.setData(fmGeojson);
        } else {
          map3d.addSource('first-mile-source', {
            type: 'geojson',
            data: fmGeojson,
          });
        }
        if (!map3d.getLayer('first-mile-line')) {
          map3d.addLayer({
            id: 'first-mile-line',
            type: 'line',
            source: 'first-mile-source',
            layout: { 'line-join': 'round', 'line-cap': 'round' },
            paint: {
              'line-color': '#00e5ff',
              'line-width': 4.5,
              'line-dasharray': [2, 2],
              'line-opacity': 0.95,
            },
          });
        }
      }

      // 6. Layer 3: Google Maps Baseline Comparison Line (Amber Dashed Line)
      if (gmapsCoordinates && gmapsCoordinates.length >= 2) {
        const gmGeojson = {
          type: 'Feature',
          properties: {},
          geometry: {
            type: 'LineString',
            coordinates: gmapsCoordinates.map(([lat, lng]) => [lng, lat]),
          },
        };
        const gmSrc = map3d.getSource('gmaps-detour-source');
        if (gmSrc) {
          gmSrc.setData(gmGeojson);
        } else {
          map3d.addSource('gmaps-detour-source', {
            type: 'geojson',
            data: gmGeojson,
          });
        }
        if (!map3d.getLayer('gmaps-detour-line')) {
          map3d.addLayer({
            id: 'gmaps-detour-line',
            type: 'line',
            source: 'gmaps-detour-source',
            layout: { 'line-join': 'round', 'line-cap': 'round' },
            paint: {
              'line-color': '#f59e0b',
              'line-width': 3,
              'line-dasharray': [3, 2],
              'line-opacity': 0.75,
            },
          });
        }
      }
    } catch (err) {
      console.warn('update3dRouteLine error:', err);
    }
  };

  if (map3d.isStyleLoaded()) {
    applyData();
  } else {
    map3d.once('load', applyData);
    map3d.once('style.load', applyData);
  }
}

export function getTurnDirectionIcon(instruction = '') {
  const norm = instruction.toLowerCase();
  if (norm.includes('trái') || norm.includes('left')) {
    return <CornerUpLeft size={22} className="turn-icon turn-left" />;
  }
  if (norm.includes('phải') || norm.includes('right')) {
    return <CornerUpRight size={22} className="turn-icon turn-right" />;
  }
  if (norm.includes('vòng') || norm.includes('roundabout')) {
    return <RotateCcw size={22} className="turn-icon turn-roundabout" />;
  }
  return <ArrowUp size={22} className="turn-icon turn-straight" />;
}

export function translateStepInstruction(instruction = '', roadName = '', landmark = '') {
  if (!instruction) return 'Đi thẳng theo hướng dẫn';
  return formatVietnameseManeuverStep(instruction, roadName, landmark);
}

function speakVietnameseInstruction(text, audioMode = 'full', isAlertOnly = false) {
  if (audioMode === false || audioMode === 'muted') {
    return;
  }
  if (audioMode === 'alerts_only' && !isAlertOnly) {
    return;
  }
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
    return;
  }
  try {
    window.speechSynthesis.cancel();
    const cleanText = text.replace(/[•\n]/g, ' ').replace(/\s+/g, ' ').trim();
    if (!cleanText) return;
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = 'vi-VN';
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    const voices = window.speechSynthesis.getVoices();
    const viVoice = voices.find(
      (v) =>
        v.lang.startsWith('vi') ||
        v.lang.includes('VIE') ||
        v.lang.includes('Vietnamese')
    );
    if (viVoice) utterance.voice = viVoice;
    window.speechSynthesis.speak(utterance);
  } catch (e) {
    console.warn('Speech synthesis error:', e);
  }
}

function formatDistanceToTurn(distanceKm, distanceMeters) {
  if (typeof distanceMeters === 'number' && !isNaN(distanceMeters) && distanceMeters > 0) {
    if (distanceMeters < 1000) {
      return `Sau ${Math.round(distanceMeters)} m`;
    }
    return `Sau ${(distanceMeters / 1000).toFixed(1)} km`;
  }
  if (typeof distanceKm !== 'number' || isNaN(distanceKm)) return 'Sau 50 m';
  if (distanceKm < 1) {
    const meters = Math.round(distanceKm * 1000);
    return `Sau ${meters} m`;
  }
  return `Sau ${distanceKm.toFixed(1)} km`;
}

function getEstimatedArrivalTime(etaMinutes = 0) {
  const now = new Date();
  now.setMinutes(now.getMinutes() + Math.max(1, Math.round(etaMinutes || 2)));
  return now.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
}

// Core Turf.js Pipeline: Snapping to Route, Off-Route Detection, Bearing, and Exact Countdown
function processNavigationPosition(rawLat, rawLng, routeCoordinates, onOffRoute) {
  if (!routeCoordinates || routeCoordinates.length < 2) {
    return {
      snappedLat: rawLat,
      snappedLng: rawLng,
      heading: 0,
      remainingKm: 0,
      offRouteDistanceMeters: 0,
      segmentIndex: 0,
    };
  }

  try {
    const turfCoords = routeCoordinates.map(([lat, lng]) => [lng, lat]);
    const routeLine = turf.lineString(turfCoords);
    const userPt = turf.point([rawLng, rawLat]);

    // 1. Off-Route Detection
    const offDistKm = turf.pointToLineDistance(userPt, routeLine, { units: 'kilometers' });
    const offMeters = Math.round(offDistKm * 1000);

    if (offDistKm > 0.035 && onOffRoute) {
      onOffRoute(rawLat, rawLng, offMeters);
    }

    // 2. Snap to nearest point on road
    const snapped = turf.nearestPointOnLine(routeLine, userPt);
    const snappedLng = snapped.geometry.coordinates[0];
    const snappedLat = snapped.geometry.coordinates[1];
    const segmentIndex = snapped.properties.index || 0;

    // 3. Dynamic bearing based on current segment
    const nextPtCoord = turfCoords[Math.min(segmentIndex + 1, turfCoords.length - 1)];
    const segmentBearing = (turf.bearing(snapped, turf.point(nextPtCoord)) + 360) % 360;

    // 4. Exact remaining distance countdown
    const destPt = turf.point(turfCoords[turfCoords.length - 1]);
    let remainingKm = 0;
    try {
      const sliced = turf.lineSlice(snapped, destPt, routeLine);
      remainingKm = turf.length(sliced, { units: 'kilometers' });
    } catch {
      remainingKm = 0;
    }

    return {
      snappedLat,
      snappedLng,
      heading: segmentBearing,
      remainingKm: Math.round(remainingKm * 100) / 100,
      offRouteDistanceMeters: offMeters,
      segmentIndex,
    };
  } catch (err) {
    console.warn('Turf processing error:', err);
    return {
      snappedLat: rawLat,
      snappedLng: rawLng,
      heading: 0,
      remainingKm: 0,
      offRouteDistanceMeters: 0,
      segmentIndex: 0,
    };
  }
}

export function NavigationPage({
  api,
  userLocation: propUserLocation,
  onUpdateLocation,
  navigationContext,
  onBackToChat,
  onNotify,
}) {
  const [userLocation, setUserLocation] = useState(
    () => navigationContext?.userLocation || propUserLocation || getSavedUserLocation()
  );
  const [poiType, setPoiType] = useState(
    () => navigationContext?.poiType || 'pharmacy'
  );
  const [pois, setPois] = useState(
    () => (navigationContext?.selectedPoi ? [navigationContext.selectedPoi] : [])
  );
  const [selectedPoi, setSelectedPoi] = useState(
    () => navigationContext?.selectedPoi || null
  );
  const [activeRoute, setActiveRoute] = useState(
    () => navigationContext?.activeRoute || null
  );
  const [loadingPois, setLoadingPois] = useState(false);
  const [loadingRoute, setLoadingRoute] = useState(false);
  const [requestingGps, setRequestingGps] = useState(false);
  const [permissionPromptOpen, setPermissionPromptOpen] = useState(false);
  const [mapTheme, setMapTheme] = useState('streets'); // 'streets', 'satellite', 'dark', 'osm'
  const [activeStepIndex, setActiveStepIndex] = useState(0);
  const steps = activeRoute?.steps || [];
  const currentStep = steps[activeStepIndex] || steps[0] || {};
  const nextStep = steps[activeStepIndex + 1] || null;
  const [liveTracking, setLiveTracking] = useState(true);

  // Google Maps Travel Modes (Video instruction: motorcycle, driving, walking)
  const [travelMode, setTravelMode] = useState('motorcycle'); // 'motorcycle' (default in VN), 'drive', 'walk'
  const [avoidHighways, setAvoidHighways] = useState(false);
  const [avoidTolls, setAvoidTolls] = useState(false);

  // 3-State Audio Control (Video instruction: Unmuted Full, Alerts Only, Muted)
  const [audioGuidanceMode, setAudioGuidanceMode] = useState('full'); // 'full', 'alerts_only', 'muted'
  const voiceGuidanceEnabled = audioGuidanceMode !== 'muted';

  // Smart Search & Voice Search via Web Speech API (Video: Voice mic button)
  const [searchQuery, setSearchQuery] = useState('');
  const [isListeningVoice, setIsListeningVoice] = useState(false);
  const speechRecognitionRef = useRef(null);

  // Quick Amenities Along Route
  const [quickAmenity, setQuickAmenity] = useState(null);

  // Hybrid Mode: '2d_overview' (Stage 1: Clean 2D Overview) | '3d_cockpit' (Stage 2: Active 3D HUD) | 'gmaps_embed'
  const [mapViewMode, setMapViewMode] = useState('2d_overview');
  const [isNavigatingLive, setIsNavigatingLive] = useState(false);
  const [isSimulatingDrive, setIsSimulatingDrive] = useState(false);
  const [vehiclePosition, setVehiclePosition] = useState(null);
  const [vehicleHeading, setVehicleHeading] = useState(0);
  const [rerouteAlert, setRerouteAlert] = useState(false);
  const [isMapFullscreen, setIsMapFullscreen] = useState(false);
  const [isToolbarsCollapsed, setIsToolbarsCollapsed] = useState(false);

  // Business Category Selection & Professional Radar Loading States
  const [selectedCategory, setSelectedCategory] = useState(
    () => navigationContext?.poiType || 'pharmacy'
  ); // 'pharmacy' | 'clinic' | 'emergency' | 'all'
  const [isScanningActive, setIsScanningActive] = useState(false);
  const [scanProgress, setScanProgress] = useState(0);
  const [showPoiDrawer, setShowPoiDrawer] = useState(false);
  const [isFloatingPanelCollapsed, setIsFloatingPanelCollapsed] = useState(false);

  // Dynamic Real User Location & Address Search
  const [addressSearchQuery, setAddressSearchQuery] = useState('');
  const [addressSearchResults, setAddressSearchResults] = useState([]);
  const [isSearchingAddress, setIsSearchingAddress] = useState(false);

  // Module 10: 4 Progressive Disclosure States & On-Demand Radar
  const {
    mapState,
    setMapState,
    isRadarScanning,
    revealedCount,
    activeReviewPoi,
    triggerOnDemandScan,
    openGoogleReviewsPanel,
    closeGoogleReviewsPanel,
    startDestinationNavigation,
    resetToOverview,
  } = useOnDemandMedicalMap();

  const handleResetDestination = () => {
    setSelectedPoi(null);
    setActiveRoute(null);
    resetToOverview();
  };

  const isScanningRef = useRef(false);
  const scanIntervalRef = useRef(null);

  /**
   * Nghiệp vụ quét vị trí y tế theo phân loại:
   * Điểm bán thuốc (GPP), Điểm y tế (Phòng khám / Trạm y tế), Cấp cứu 24/7 (Bệnh viện)
   * Hiển thị trạng thái Loading Radar chuyên nghiệp kèm tiến trình % trước khi bung point
   */
  const executeRadarScan = useCallback(
    async (categoryToScan) => {
      if (isScanningRef.current) return;
      isScanningRef.current = true;

      const cat = categoryToScan || selectedCategory || poiType || 'pharmacy';
      setSelectedCategory(cat);
      setPoiType(cat);
      setIsScanningActive(true);
      setScanProgress(20);
      setSelectedPoi(null);
      setActiveRoute(null);
      setActiveStepIndex(0);
      setIsNavigatingLive(false);

      if (scanIntervalRef.current) clearInterval(scanIntervalRef.current);
      let currentProg = 20;
      scanIntervalRef.current = setInterval(() => {
        currentProg += Math.floor(Math.random() * 20) + 15;
        if (currentProg >= 95) {
          currentProg = 95;
          clearInterval(scanIntervalRef.current);
        }
        setScanProgress(currentProg);
      }, 100);

      try {
        let backendPois = [];
        try {
          const timeoutPromise = new Promise((resolve) => setTimeout(() => resolve(null), 3000));
          const reqPromise = api.request(
            `/v1/geo/pois?poi_type=${cat}&city=${userLocation.city || 'hanoi'}&lat=${userLocation.lat}&lng=${userLocation.lng}`
          );
          const res = await Promise.race([reqPromise, timeoutPromise]);
          if (res?.pois && res.pois.length > 0) {
            backendPois = res.pois;
          }
        } catch (e) {}

        const hyperLocalList = await scanHyperLocalMedicalPois({
          lat: userLocation.lat,
          lng: userLocation.lng,
          poiType: cat,
          radiusKm: 2.0,
          backendPois,
          searchQuery,
        });
        const finalList = Array.isArray(hyperLocalList) && hyperLocalList.length > 0 ? hyperLocalList : (pois && pois.length > 0 ? pois : []);

        // Trải nghiệm hiệu ứng radar mượt mà
        await new Promise((r) => setTimeout(r, 400));

        if (scanIntervalRef.current) clearInterval(scanIntervalRef.current);
        setScanProgress(100);
        await new Promise((r) => setTimeout(r, 200));

        setPois(finalList);
        setIsScanningActive(false);
        isScanningRef.current = false;

        const categoryNames = {
          pharmacy: 'Điểm bán thuốc GPP',
          clinic: 'Điểm Y tế & Phòng khám',
          emergency: 'Điểm Cấp cứu 24/7',
          all: 'Cơ sở Y tế & Quầy thuốc',
        };
        const catLabel = categoryNames[cat] || 'cơ sở y tế';
        onNotify?.(`✅ Đã quét xong: Tìm thấy ${finalList.length} ${catLabel} uy tín quanh bạn!`);

        triggerOnDemandScan({ totalPoisCount: finalList.length });

        // Tự động căn chỉnh khung hình bao quát toàn bộ các điểm vừa quét
        setTimeout(() => {
          if (mapViewMode === '3d_cockpit' && map3dInstanceRef.current && finalList.length > 0) {
            const map3d = map3dInstanceRef.current;
            const bounds = new maplibregl.LngLatBounds(
              [userLocation.lng, userLocation.lat],
              [userLocation.lng, userLocation.lat]
            );
            finalList.forEach((p) => {
              if (typeof p.lng === 'number' && typeof p.lat === 'number') {
                bounds.extend([p.lng, p.lat]);
              }
            });
            map3d.fitBounds(bounds, {
              padding: { top: 60, bottom: 60, left: 60, right: 60 },
              maxZoom: 15.6,
              duration: 800,
            });
          } else if (mapViewMode === '2d_overview' && map2dInstanceRef.current && finalList.length > 0) {
            const map2d = map2dInstanceRef.current;
            const points = [
              [userLocation.lat, userLocation.lng],
              ...finalList.map((p) => [p.lat, p.lng]),
            ];
            map2d.fitBounds(points, {
              padding: [60, 60],
              maxZoom: 15.6,
            });
          }
        }, 180);
      } catch (err) {
        console.error('Radar scan error:', err);
        if (scanIntervalRef.current) clearInterval(scanIntervalRef.current);
        setScanProgress(100);
        setIsScanningActive(false);
        isScanningRef.current = false;
      }
    },
    [selectedCategory, poiType, userLocation, searchQuery, api, triggerOnDemandScan, onNotify, mapViewMode, pois]
  );

  const handleZoomIn = useCallback(() => {
    if (mapViewMode === '3d_cockpit' && map3dInstanceRef.current) {
      map3dInstanceRef.current.zoomIn({ duration: 300 });
    } else if (mapViewMode === '2d_overview' && map2dInstanceRef.current) {
      map2dInstanceRef.current.zoomIn();
    }
  }, [mapViewMode]);

  const handleZoomOut = useCallback(() => {
    if (mapViewMode === '3d_cockpit' && map3dInstanceRef.current) {
      map3dInstanceRef.current.zoomOut({ duration: 300 });
    } else if (mapViewMode === '2d_overview' && map2dInstanceRef.current) {
      map2dInstanceRef.current.zoomOut();
    }
  }, [mapViewMode]);

  const handleFitAllPois = useCallback(() => {
    if (pois.length === 0) return;
    if (mapViewMode === '3d_cockpit' && map3dInstanceRef.current) {
      const map3d = map3dInstanceRef.current;
      const bounds = new maplibregl.LngLatBounds(
        [userLocation.lng, userLocation.lat],
        [userLocation.lng, userLocation.lat]
      );
      pois.forEach((p) => {
        if (typeof p.lng === 'number' && typeof p.lat === 'number') {
          bounds.extend([p.lng, p.lat]);
        }
      });
      map3d.fitBounds(bounds, {
        padding: { top: 70, bottom: 70, left: 70, right: 70 },
        maxZoom: 15.6,
        pitch: 0,
        bearing: 0,
        duration: 850,
      });
      onNotify?.(`Đã thu phóng toàn cảnh để xem toàn bộ ${pois.length} cơ sở y tế xung quanh`);
    } else if (mapViewMode === '2d_overview' && map2dInstanceRef.current) {
      const map2d = map2dInstanceRef.current;
      const points = [
        [userLocation.lat, userLocation.lng],
        ...pois.map((p) => [p.lat, p.lng]),
      ];
      map2d.fitBounds(points, { padding: [50, 50], maxZoom: 15.6 });
      onNotify?.(`Đã thu phóng toàn cảnh để xem toàn bộ ${pois.length} cơ sở y tế xung quanh`);
    }
  }, [pois, userLocation, mapViewMode, onNotify]);

  const handleToggleFullscreen = useCallback(() => {
    setIsMapFullscreen((prev) => {
      const next = !prev;
      setTimeout(() => {
        if (mapViewMode === '3d_cockpit' && map3dInstanceRef.current) {
          map3dInstanceRef.current.resize();
        } else if (mapViewMode === '2d_overview' && map2dInstanceRef.current) {
          map2dInstanceRef.current.invalidateSize();
        }
      }, 150);
      return next;
    });
  }, [mapViewMode]);

  // 1. Tạo danh sách POI hiển thị ổn định, không bị chớp giật hay biến mất khi quét
  const scannedPois = useMemo(() => {
    if (!pois || pois.length === 0) return [];
    return pois;
  }, [pois]);

  // Lọc thông minh chống đè nhãn trên bản đồ (Spatial Collision Culling):
  // Giữ lại tối đa 14 ghim cách nhau tối thiểu 70m, luôn ưu tiên điểm được chọn (selectedPoi)
  const displayedPois = useMemo(() => {
    return selectNonOverlappingMapPins(scannedPois, selectedPoi?.id, 14, 70);
  }, [scannedPois, selectedPoi?.id]);

  // Khai báo window.__medguardSelectPoi và window.__medguardOpenReviews cho Callout Notes & Popup Leaflet
  useEffect(() => {
    window.__medguardPois = pois;
    window.__medguardSelectPoi = (poiId) => {
      const found = pois.find((p) => String(p.id) === String(poiId));
      if (found) {
        setSelectedPoi(found);
        setIsFloatingPanelCollapsed(true);
        onNotify?.(`Đã chọn cơ sở: ${found.name}`);
      }
    };
    window.__medguardOpenReviews = (poiId) => {
      const found = pois.find((p) => String(p.id) === String(poiId));
      if (found) {
        openGoogleReviewsPanel(found);
      }
    };
    return () => {
      delete window.__medguardPois;
      delete window.__medguardSelectPoi;
      delete window.__medguardOpenReviews;
    };
  }, [pois, openGoogleReviewsPanel, onNotify]);

  // Hàm tạo HTML cho Note chỉ địa điểm bán thuốc / khám bệnh tinh gọn, đẹp mắt, không đè lên nhau
  const buildPoiCalloutNoteHtml = useCallback(
    (poi, index = 0, isSelected = false) => {
      const isEmergency =
        poi.type === 'hospital_emergency' &&
        !/phòng khám|trạm y tế/i.test(poi.name || '');
      const isClinic =
        poi.category_badge === 'PHÒNG KHÁM / KHÁM BỆNH' ||
        poi.category_badge === 'PHÒNG KHÁM / TRẠM Y TẾ' ||
        poi.category_badge === 'TRẠM Y TẾ & TIÊM CHỦNG' ||
        poi.category_badge === 'PHÒNG KHÁM CHUYÊN KHOA' ||
        /phòng khám|trạm y tế|chuyên khoa/i.test(poi.name || '');
      const wrapperTypeClass = isEmergency
        ? 'type-emergency'
        : isClinic
        ? 'type-clinic'
        : 'type-pharmacy';

      const typeIconSvg = isEmergency
        ? `<span class="pin-svg-wrap emergency" aria-label="Cấp cứu"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10 17h4V5H2v12h3"/><path d="M20 17h2v-3.34a4 4 0 0 0-1.17-2.83L19 9h-5v8h2"/><circle cx="7.5" cy="17.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/></svg></span>`
        : isClinic
        ? `<span class="pin-svg-wrap clinic" aria-label="Phòng khám"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4.8 2.3A.3.3 0 1 0 5 2H4a2 2 0 0 0-2 2v5a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6V4a2 2 0 0 0-2-2h-1a.2.2 0 1 0 .3.3"/><path d="M8 15v1a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6v-4"/><circle cx="20" cy="10" r="2"/></svg></span>`
        : `<span class="pin-svg-wrap pharmacy" aria-label="Nhà thuốc"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7Z"/><path d="m8.5 8.5 7 7"/></svg></span>`;

      const distText = poi.distance_label || formatDistanceLabel(poi.distance_km);
      const rating = poi.rating || (isEmergency ? 4.8 : 4.7);
      const delayMs = Math.min(index * 90, 800);

      // Rút gọn tên cơ sở để ghim hiển thị cực kỳ tinh tế, không choán diện tích
      let cleanName = (poi.name || 'Cơ sở Y tế')
        .split('—')[0]
        .replace(/Nhà thuốc GPP|Nhà thuốc Chuẩn GPP|Nhà thuốc/gi, 'NT')
        .replace(/Phòng khám Đa khoa & Nội Nhi|Phòng khám/gi, 'PK')
        .replace(/Bệnh viện Đa khoa Cấp cứu 115|Bệnh viện/gi, 'BV Cấp cứu')
        .trim();
      if (cleanName.length > 22) {
        cleanName = cleanName.slice(0, 20) + '…';
      }

      const fanClass = poi.fan_direction || '';

      return `
        <div class="med-compact-poi-pin ${wrapperTypeClass} ${fanClass} ${
        isSelected ? 'is-selected' : ''
      }" style="animation-delay: ${delayMs}ms;" onclick="window.__medguardSelectPoi && window.__medguardSelectPoi('${poi.id}')" title="${(poi.name || '').replace(/"/g, '&quot;')} - Bấm để xem chi tiết & chỉ đường">
          <div class="pin-pill-body">
            <span class="pin-icon">${typeIconSvg}</span>
            <span class="pin-title">${isSelected ? '<span class="pin-target-dot"></span>' : ''}${cleanName}</span>
            <span class="pin-sep">•</span>
            <span class="pin-dist">${distText}</span>
            <span class="pin-star">★ ${rating}</span>
          </div>
          <div class="pin-stem"></div>
          <div class="pin-ground-pulse"></div>
        </div>
      `;
    },
    []
  );


  const handleDownloadDesignDoc = (format = 'md') => {
    const filename = `KE_HOACH_THIET_KE_BAN_DO_CAP_CUU_GOOGLE_PLACES_MODULE_10.${format === 'doc' ? 'docx' : 'md'}`;
    const url = `/static/docs/${filename}`;
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    onNotify?.(`Đang tải xuống tài liệu thiết kế hệ thống (${format.toUpperCase()})...`);
  };

  // MapLibre 3D Refs
  const map3dContainerRef = useRef(null);
  const map3dInstanceRef = useRef(null);
  const vehicleMarker3dRef = useRef(null);
  const pinMarkers3dRef = useRef([]);

  // Leaflet 2D Refs
  const map2dContainerRef = useRef(null);
  const map2dInstanceRef = useRef(null);
  const markersGroup2dRef = useRef(null);
  const polylineGroup2dRef = useRef(null);
  const vehicleMarker2dRef = useRef(null);

  // Simulation & Reroute Refs
  const simIntervalRef = useRef(null);
  const simIndexRef = useRef(0);
  const isReroutingRef = useRef(false);

  // Position & Map Fitting Refs
  const hasFitInitialBoundsRef = useRef(false);
  const hasFit2dInitialBoundsRef = useRef(false);
  const lastPoiFetchCoordsRef = useRef(null);
  const lastPoiTypeRef = useRef(poiType);

  // Real GPS Position Handler (reads dynamic browser coords, flies camera, and re-scans)
  const handleRequestGps = useCallback(
    async (silent = false) => {
      setRequestingGps(true);
      try {
        const loc = await requestBrowserGeolocation();
        if (loc && typeof loc.lat === 'number' && typeof loc.lng === 'number') {
          setUserLocation(loc);
          onUpdateLocation?.(loc);
          setPermissionPromptOpen(false);

          // Reset fit bounds refs so the map re-centers on the newly acquired GPS position!
          hasFitInitialBoundsRef.current = false;
          hasFit2dInitialBoundsRef.current = false;
          lastPoiFetchCoordsRef.current = null;

          // Fly camera smoothly to the exact real GPS position
          if (mapViewMode === '3d_cockpit' && map3dInstanceRef.current) {
            map3dInstanceRef.current.flyTo({
              center: [loc.lng, loc.lat],
              zoom: 16.8,
              pitch: 52,
              duration: 900,
            });
          } else if (map2dInstanceRef.current) {
            map2dInstanceRef.current.flyTo([loc.lat, loc.lng], 16.5, {
              animate: true,
              duration: 0.9,
            });
          }

          const accInfo = loc.accuracy_meters ? ` (Sai số ±${loc.accuracy_meters}m)` : '';
          onNotify?.(`🎯 Đã định vị GPS chính xác: ${loc.name}${accInfo}`);
          if (!silent) {
            executeRadarScan(selectedCategory);
          }
        }
      } catch (err) {
        if (!silent) {
          onNotify?.(err.message || 'Không thể lấy GPS. Vui lòng bấm Cho phép trên thanh địa chỉ trình duyệt.');
        }
      } finally {
        setRequestingGps(false);
      }
    },
    [mapViewMode, onNotify, executeRadarScan, selectedCategory, onUpdateLocation]
  );

  // Address search debounce handler
  useEffect(() => {
    if (!addressSearchQuery || addressSearchQuery.trim().length < 2) {
      setAddressSearchResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setIsSearchingAddress(true);
      try {
        const results = await searchAddressGeocode(addressSearchQuery);
        setAddressSearchResults(results);
      } catch {
        setAddressSearchResults([]);
      } finally {
        setIsSearchingAddress(false);
      }
    }, 320);
    return () => clearTimeout(timer);
  }, [addressSearchQuery]);

  // Set user location from searched address or preset
  const handleSelectSearchedLocation = useCallback(
    (item) => {
      if (!item || typeof item.lat !== 'number' || typeof item.lng !== 'number') return;
      const loc = {
        name: item.name,
        address: item.address || item.name,
        city: item.city || (item.lat >= 19.5 ? 'hanoi' : item.lat >= 14.5 ? 'danang' : 'hcm'),
        lat: item.lat,
        lng: item.lng,
        is_gps: true,
        is_manual_search: true,
        accuracy_meters: 5,
        last_updated: Date.now(),
      };
      saveUserLocation(loc);
      setUserLocation(loc);
      onUpdateLocation?.(loc);
      setPermissionPromptOpen(false);
      setAddressSearchQuery('');
      setAddressSearchResults([]);

      hasFitInitialBoundsRef.current = false;
      hasFit2dInitialBoundsRef.current = false;
      lastPoiFetchCoordsRef.current = null;

      if (mapViewMode === '3d_cockpit' && map3dInstanceRef.current) {
        map3dInstanceRef.current.flyTo({
          center: [loc.lng, loc.lat],
          zoom: 16.8,
          pitch: 52,
          duration: 900,
        });
      } else if (map2dInstanceRef.current) {
        map2dInstanceRef.current.flyTo([loc.lat, loc.lng], 16.5, {
          animate: true,
          duration: 0.9,
        });
      }

      onNotify?.(`📍 Đã đặt vị trí của bạn: ${loc.name}`);
      executeRadarScan(selectedCategory);
    },
    [mapViewMode, onNotify, executeRadarScan, selectedCategory]
  );

  // Voice Search Handler (Web Speech API)
  const handleVoiceSearchToggle = () => {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
      onNotify?.(
        '⚠️ Trình duyệt của bạn chưa bật Web Speech API. Bạn có thể gõ trực tiếp tên địa điểm vào ô tìm kiếm.'
      );
      return;
    }

    if (isListeningVoice) {
      try {
        speechRecognitionRef.current?.stop();
      } catch {}
      setIsListeningVoice(false);
      return;
    }

    try {
      const recognition = new SpeechRec();
      recognition.lang = 'vi-VN';
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        setIsListeningVoice(true);
        onNotify?.(
          'Đang lắng nghe giọng nói tiếng Việt... Hãy nói: "Bệnh viện cấp cứu gần nhất", "Nhà thuốc GPP", "Bạch Mai", hoặc địa chỉ của bạn.'
        );

      };

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        setIsListeningVoice(false);
        setSearchQuery(transcript);
        onNotify?.(`Đã nhận diện giọng nói: "${transcript}"`);
        handleExecuteSearch(transcript);
      };

      recognition.onerror = (event) => {
        console.warn('Speech recognition error:', event.error);
        setIsListeningVoice(false);
        if (event.error !== 'no-speech') {
          onNotify?.('Không thể nhận diện giọng nói. Bạn hãy thử lại hoặc nhập từ khóa.');
        }
      };

      recognition.onend = () => {
        setIsListeningVoice(false);
      };

      speechRecognitionRef.current = recognition;
      recognition.start();
    } catch (err) {
      console.warn('Cannot start speech recognition:', err);
      setIsListeningVoice(false);
    }
  };

  const handleExecuteSearch = (queryText) => {
    const q = (queryText || searchQuery).trim().toLowerCase();
    if (!q) return;

    if (q.includes('xăng') || q.includes('fuel') || q.includes('gas')) {
      setPoiType('gas_station');
      setQuickAmenity('gas_station');
      onNotify?.('Đang tìm trạm xăng gần nhất...');
      return;
    }
    if (q.includes('cà phê') || q.includes('cafe') || q.includes('uống')) {
      setPoiType('cafe');
      setQuickAmenity('cafe');
      onNotify?.('Đang tìm quán cà phê / trạm nghỉ gần nhất...');
      return;
    }
    if (q.includes('cơm') || q.includes('ăn') || q.includes('quán ăn') || q.includes('gà')) {
      setPoiType('restaurant');
      setQuickAmenity('restaurant');
      onNotify?.('Đang tìm quán ăn / quán cơm gần nhất...');
      return;
    }
    if (q.includes('cấp cứu') || q.includes('bệnh viện') || q.includes('115')) {
      setPoiType('emergency');
      setQuickAmenity('emergency');
      onNotify?.('Đang tìm trung tâm cấp cứu 115 & bệnh viện...');
      return;
    }
    if (q.includes('thuốc') || q.includes('nhà thuốc') || q.includes('gpp')) {
      setPoiType('pharmacy');
      setQuickAmenity('pharmacy');
      onNotify?.('Đang tìm quầy thuốc GPP chuẩn gần nhất...');
      return;
    }

    const matched = pois.find(
      (p) =>
        p.name?.toLowerCase().includes(q) ||
        p.address?.toLowerCase().includes(q) ||
        (p.city && p.city.toLowerCase().includes(q))
    );
    if (matched) {
      setSelectedPoi(matched);
      onNotify?.(`Đã chọn điểm đến: ${matched.name}`);
    } else {
      onNotify?.(`Đang lọc theo từ khóa "${q}"...`);
    }
  };

  const handleCycleAudioGuidance = () => {
    setAudioGuidanceMode((curr) => {
      if (curr === 'full') {
        onNotify?.('Chế độ giọng nói: Chỉ phát cảnh báo quan trọng');
        return 'alerts_only';
      }
      if (curr === 'alerts_only') {
        onNotify?.('Chế độ giọng nói: Đã tắt tiếng hoàn toàn');
        return 'muted';
      }
      onNotify?.('Chế độ giọng nói: Bật âm thanh hướng dẫn đầy đủ');
      return 'full';
    });
  };

  const handleRecenterGps = () => {
    if (mapViewMode === '3d_cockpit' && map3dInstanceRef.current) {
      map3dInstanceRef.current.flyTo({
        center: [userLocation.lng, userLocation.lat],
        zoom: 17.2,
        pitch: 60,
        bearing: vehicleHeading || 0,
        speed: 1.4,
      });
      onNotify?.('Đã căn chỉnh camera về vị trí GPS của bạn');
    } else if (mapViewMode === '2d_overview' && map2dInstanceRef.current) {
      map2dInstanceRef.current.flyTo([userLocation.lat, userLocation.lng], 16, {
        animate: true,
        duration: 1.0,
      });
      onNotify?.('Đã căn chỉnh camera về vị trí GPS của bạn');
    }
  };

  const handleResetCompass = () => {
    if (mapViewMode === '3d_cockpit' && map3dInstanceRef.current) {
      map3dInstanceRef.current.rotateTo(0, { duration: 600 });
      setVehicleHeading(0);
      onNotify?.('Đã căn chỉnh la bàn về hướng Bắc (0°)');
    }
  };

  // Sync userLocation only if prop explicitly changes and has different coordinates
  const lastSyncedPropLocRef = useRef(propUserLocation);
  useEffect(() => {
    if (
      propUserLocation &&
      (!lastSyncedPropLocRef.current ||
        Math.abs(propUserLocation.lat - (lastSyncedPropLocRef.current?.lat || 0)) > 0.0001 ||
        Math.abs(propUserLocation.lng - (lastSyncedPropLocRef.current?.lng || 0)) > 0.0001)
    ) {
      lastSyncedPropLocRef.current = propUserLocation;
      setUserLocation((prev) => {
        const prevAuth = getLocationAuthorityLevel(prev);
        const newAuth = getLocationAuthorityLevel(propUserLocation);
        if (newAuth < prevAuth) {
          return prev; // Giữ nguyên GPS Đại học Hà Nội, chặn IP Thạch Thất ghi đè!
        }
        return propUserLocation;
      });
    }
  }, [propUserLocation]);

  // When navigationContext arrives from chat, immediately activate that exact guidance
  useEffect(() => {
    if (navigationContext?.selectedPoi) {
      const chatPoi = {
        ...navigationContext.selectedPoi,
        isRecommendedFromChat: true,
      };
      setSelectedPoi(chatPoi);
      setPois((prev) => {
        const filtered = prev.filter(
          (p) =>
            p.id !== chatPoi.id &&
            (!chatPoi.name || p.name?.toLowerCase() !== chatPoi.name?.toLowerCase())
        );
        return [chatPoi, ...filtered];
      });
      if (navigationContext.activeRoute) {
        setActiveRoute(navigationContext.activeRoute);
        setActiveStepIndex(0);
      }
      if (navigationContext.userLocation) {
        setUserLocation(navigationContext.userLocation);
      }
      if (navigationContext.poiType) {
        setPoiType(navigationContext.poiType);
      }
      setPermissionPromptOpen(false);
      onNotify?.(`Đã tải chính xác chỉ dẫn từ ca tư vấn: ${chatPoi.name}`);
    }
  }, [navigationContext]);

  // Coordinates array for route (Memoized to prevent infinite re-render cycles)
  const routeCoords = useMemo(() => {
    if (activeRoute?.coordinates?.length > 0) return activeRoute.coordinates;
    if (activeRoute?.canvas_polyline?.length > 0) return activeRoute.canvas_polyline;
    if (userLocation?.lat && selectedPoi?.lat) {
      return [
        [userLocation.lat, userLocation.lng],
        [selectedPoi.lat, selectedPoi.lng],
      ];
    }
    return [];
  }, [
    activeRoute?.coordinates,
    activeRoute?.canvas_polyline,
    userLocation?.lat,
    userLocation?.lng,
    selectedPoi?.lat,
    selectedPoi?.lng,
  ]);

  const routeCoordsRef = useRef(routeCoords);
  routeCoordsRef.current = routeCoords;

  const handleAutoRerouteRef = useRef(null);

  // Auto-Reroute Handler when Turf.js detects off-route
  const handleAutoReroute = useCallback(
    async (currentLat, currentLng, offMeters) => {
      if (isReroutingRef.current || !selectedPoi) return;
      isReroutingRef.current = true;
      setRerouteAlert(true);
      speakVietnameseInstruction(
        'Bạn đang đi chệch lộ trình. Hệ thống đang tự động tính toán lại đường đi...',
        audioGuidanceMode,
        true
      );
      try {
        const res = await api.request('/v1/geo/route', {
          method: 'POST',
          body: {
            start_lat: currentLat,
            start_lng: currentLng,
            dest_lat: selectedPoi.lat,
            dest_lng: selectedPoi.lng,
            dest_name: selectedPoi.name,
            dest_address: selectedPoi.address,
            mode: travelMode,
            avoid_highways: avoidHighways,
            avoid_tolls: avoidTolls,
          },
        });
        if (res && res.coordinates) {
          const enhanced = orchestrateHyperLocalRoute({
            origin: { lat: currentLat, lng: currentLng },
            destination: selectedPoi,
            travelMode,
            baseRoute: res,
          });
          setActiveRoute(enhanced || res);
          setActiveStepIndex(0);
          onNotify?.(`Đã tự động tính lại tuyến đường (lệch ${offMeters}m)`);
        }
      } catch (err) {
        console.warn('Auto reroute error:', err);
      } finally {
        setTimeout(() => {
          setRerouteAlert(false);
          isReroutingRef.current = false;
        }, 4000);
      }
    },
    [api, selectedPoi, travelMode, avoidHighways, avoidTolls, audioGuidanceMode, onNotify]
  );
  handleAutoRerouteRef.current = handleAutoReroute;

  // Auto-detect real user location on mount (GPS first, never fixed)
  useEffect(() => {
    if (navigationContext?.userLocation) return;
    let isMounted = true;

    // Check if permission already granted or listen for changes
    if ('geolocation' in navigator) {
      if ('permissions' in navigator) {
        navigator.permissions
          .query({ name: 'geolocation' })
          .then((perm) => {
            if (perm.state === 'granted') {
              handleRequestGps(true);
            }
            perm.onchange = () => {
              if (perm.state === 'granted') {
                handleRequestGps(true);
              }
            };
          })
          .catch(() => {});
      }
      // Proactively trigger live browser GPS detection
      handleRequestGps(true);
    }

    autoDetectLiveLocation()
      .then((loc) => {
        if (isMounted && loc && typeof loc.lat === 'number') {
          setUserLocation((prev) => {
            const prevAuth = getLocationAuthorityLevel(prev);
            const newAuth = getLocationAuthorityLevel(loc);
            if (newAuth < prevAuth) return prev;
            return loc;
          });
          if (loc.is_gps) {
            setPermissionPromptOpen(false);
          }
        }
      })
      .catch((e) => console.log('Auto location detection:', e));

    return () => {
      isMounted = false;
    };
  }, [navigationContext, handleRequestGps]);

  // Continuous live GPS tracking with Turf.js Snapping
  useEffect(() => {
    if (!liveTracking) return;
    const unwatch = watchLiveUserLocation(
      (liveLoc) => {
        if (liveLoc && typeof liveLoc.lat === 'number') {
          setUserLocation((prev) => {
            if (
              prev &&
              prev.name === liveLoc.name &&
              Math.abs(prev.lat - liveLoc.lat) < 0.00008 &&
              Math.abs(prev.lng - liveLoc.lng) < 0.00008
            ) {
              return prev;
            }
            return liveLoc;
          });
          setPermissionPromptOpen(false);

          if (isNavigatingLive && !isSimulatingDrive) {
            const currentCoords = routeCoordsRef.current;
            const processed = processNavigationPosition(
              liveLoc.lat,
              liveLoc.lng,
              currentCoords,
              (offLat, offLng, offM) => handleAutoRerouteRef.current?.(offLat, offLng, offM)
            );

            setVehiclePosition([processed.snappedLat, processed.snappedLng]);
            setVehicleHeading(processed.heading);

            // Follow vehicle in 3D MapLibre
            if (map3dInstanceRef.current && mapViewMode === '3d_cockpit') {
              map3dInstanceRef.current.easeTo({
                center: [processed.snappedLng, processed.snappedLat],
                bearing: processed.heading,
                pitch: 60,
                zoom: 17.5,
                duration: 600,
              });
            }

            // Follow vehicle in 2D Leaflet
            if (map2dInstanceRef.current && mapViewMode === '2d_overview') {
              map2dInstanceRef.current.panTo(
                [processed.snappedLat, processed.snappedLng],
                { animate: true }
              );
            }
          }
        }
      },
      (err) => console.log('Watch live position error:', err)
    );
    return () => unwatch();
  }, [liveTracking, isNavigatingLive, isSimulatingDrive, mapViewMode]);

  // Load POIs when user location or POI type changes
  useEffect(() => {
    let isCancelled = false;
    const shouldFetch =
      !lastPoiFetchCoordsRef.current ||
      lastPoiTypeRef.current !== poiType ||
      Math.abs(lastPoiFetchCoordsRef.current.lat - userLocation.lat) > 0.002 ||
      Math.abs(lastPoiFetchCoordsRef.current.lng - userLocation.lng) > 0.002;

    if (!shouldFetch && pois.length > 0) return;

    // Chặn tự động quét khi người dùng đang ở trạng thái chờ (idle_standby) và không điều hướng từ Chat
    if (mapState === 'idle_standby' && !navigationContext?.fromChat && !navigationContext?.selectedPoi) {
      return; // Chờ user bấm nút "Quét Điểm Bán Thuốc Quanh Bạn"
    }

    lastPoiFetchCoordsRef.current = { lat: userLocation.lat, lng: userLocation.lng };
    lastPoiTypeRef.current = poiType;

    const fetchPois = async () => {
      setLoadingPois(true);
      try {
        const backendPromise = api
          .request(
            `/v1/geo/pois?poi_type=${poiType}&city=${userLocation.city || 'hanoi'}&lat=${userLocation.lat}&lng=${userLocation.lng}`
          )
          .then((res) => res?.pois || [])
          .catch(() => []);

        const timeoutPromise = new Promise((resolve) => setTimeout(() => resolve([]), 4500));
        const backendPois = await Promise.race([backendPromise, timeoutPromise]);

        // Gộp kết quả quét thực địa đa tầng (Photon Komoot OSM + Geoapify v2 + Verified Registry + Backend)
        const hyperLocalList = await scanHyperLocalMedicalPois({
          lat: userLocation.lat,
          lng: userLocation.lng,
          poiType,
          radiusKm: 2.0,
          backendPois,
          searchQuery,
        });

        if (isCancelled) return;

        const currentTargetPoi = navigationContext?.selectedPoi || selectedPoi;
        if (currentTargetPoi && navigationContext?.fromChat) {
          const pinnedPoi = {
            ...currentTargetPoi,
            isRecommendedFromChat: true,
          };
          const isSame = (p) =>
            String(p.id) === String(currentTargetPoi.id) ||
            (p.name &&
              currentTargetPoi.name &&
              p.name.toLowerCase() === currentTargetPoi.name.toLowerCase());
          const others = hyperLocalList.filter((p) => !isSame(p));
          const merged = [pinnedPoi, ...others];
          setPois(merged);
          setSelectedPoi(pinnedPoi);
          triggerOnDemandScan({ totalPoisCount: merged.length });
        } else {
          setPois(hyperLocalList);
          triggerOnDemandScan({ totalPoisCount: hyperLocalList.length });
        }
      } catch (err) {
        console.warn('Failed to load hyper-local POIs:', err);
      } finally {
        if (!isCancelled) setLoadingPois(false);
      }
    };
    fetchPois();
    return () => {
      isCancelled = true;
    };
  }, [
    api,
    poiType,
    userLocation.lat,
    userLocation.lng,
    userLocation.city,
    navigationContext,
    triggerOnDemandScan,
    searchQuery,
  ]);

  // Load Route whenever selectedPoi or userLocation changes
  const lastRouteReqKeyRef = useRef('');

  useEffect(() => {
    if (!selectedPoi || typeof selectedPoi.lat !== 'number' || typeof selectedPoi.lng !== 'number') return;

    const reqKey = `${userLocation.lat.toFixed(4)}_${userLocation.lng.toFixed(4)}_${selectedPoi.lat.toFixed(4)}_${selectedPoi.lng.toFixed(4)}_${travelMode}_${avoidHighways}_${avoidTolls}`;
    if (lastRouteReqKeyRef.current === reqKey && activeRoute?.steps?.length > 0) {
      return;
    }

    // Immediately generate smooth client-side fallback route so map & instructions NEVER hang
    if (!activeRoute || activeRoute.steps?.length === 0) {
      const immediateRoute = generateClientFallbackRoute(
        userLocation.lat,
        userLocation.lng,
        selectedPoi.lat,
        selectedPoi.lng,
        selectedPoi.name || 'Điểm đến',
        travelMode
      );
      setActiveRoute(immediateRoute);
    }

    let isCancelled = false;
    const fetchRoute = async () => {
      setLoadingRoute(true);
      try {
        const res = await api.request('/v1/geo/route', {
          method: 'POST',
          body: {
            start_lat: userLocation.lat,
            start_lng: userLocation.lng,
            dest_lat: selectedPoi.lat,
            dest_lng: selectedPoi.lng,
            dest_name: selectedPoi.name,
            dest_address: selectedPoi.address,
            mode: travelMode,
            avoid_highways: avoidHighways,
            avoid_tolls: avoidTolls,
          },
        });
        if (!isCancelled && res && res.coordinates) {
          lastRouteReqKeyRef.current = reqKey;
          const enhanced = orchestrateHyperLocalRoute({
            origin: userLocation,
            destination: selectedPoi,
            travelMode,
            baseRoute: res,
          });
          setActiveRoute(enhanced || res);
          setActiveStepIndex(0);
        }
      } catch (err) {
        console.warn('Backend route calc failed, client fallback active:', err);
      } finally {
        if (!isCancelled) setLoadingRoute(false);
      }
    };
    fetchRoute();
    return () => {
      isCancelled = true;
    };
  }, [
    api,
    selectedPoi?.lat,
    selectedPoi?.lng,
    selectedPoi?.name,
    selectedPoi?.address,
    userLocation.lat,
    userLocation.lng,
    travelMode,
    avoidHighways,
    avoidTolls,
  ]);

  // =========================================================================
  // 1. ENGINE 1: MAPLIBRE GL JS (3D COCKPIT VIEW)
  // =========================================================================
  const map3dInitializedRef = useRef(false);
  const currentMapThemeRef = useRef('streets');

  useEffect(() => {
    if (!map3dContainerRef.current) return;

    if (!map3dInstanceRef.current) {
      const initialStyle = getMapLibreStyleForTheme('streets');
      currentMapThemeRef.current = 'streets';

      const map3d = new maplibregl.Map({
        container: map3dContainerRef.current,
        style: initialStyle,
        center: [userLocation.lng, userLocation.lat],
        zoom: 16.8,
        pitch: 52, // 3D Camera tilt thoáng mắt
        bearing: vehicleHeading || 0,
        attributionControl: false,
        dragPan: true,
        scrollZoom: true,
        boxZoom: true,
        dragRotate: true,
        touchPitch: true,
        touchZoomRotate: true,
        doubleClickZoom: true,
        cooperativeGestures: false,
      });

      map3d.on('load', () => {
        map3dInitializedRef.current = true;
        map3d.resize();
        map3d.dragPan.enable();
        map3d.scrollZoom.enable();
        map3d.doubleClickZoom.enable();
        map3d.touchZoomRotate.enable();
        update3dRouteLine(
          map3d,
          routeCoords,
          activeRoute?.first_mile_coordinates,
          activeRoute?.comparison?.gmapsDetourCoordinates
        );
      });

      map3d.on('error', (e) => {
        console.warn('MapLibre GL warning:', e);
      });

      map3dInstanceRef.current = map3d;
    }
  }, []);

  // Update 3D route line whenever routeCoords or activeRoute changes
  useEffect(() => {
    const map3d = map3dInstanceRef.current;
    if (map3d && routeCoords.length >= 2) {
      update3dRouteLine(
        map3d,
        routeCoords,
        activeRoute?.first_mile_coordinates,
        activeRoute?.comparison?.gmapsDetourCoordinates
      );
      if (!isNavigatingLive) {
        try {
          const bounds = routeCoords.reduce(
            (b, [lat, lng]) => b.extend([lng, lat]),
            new maplibregl.LngLatBounds(
              [routeCoords[0][1], routeCoords[0][0]],
              [routeCoords[0][1], routeCoords[0][0]]
            )
          );
          map3d.fitBounds(bounds, { padding: 80, maxZoom: 17, pitch: 50, duration: 600 });
        } catch {}
      }
    }
  }, [
    routeCoords,
    activeRoute?.first_mile_coordinates,
    activeRoute?.comparison?.gmapsDetourCoordinates,
    isNavigatingLive,
  ]);

  // Switch 3D Map style ONLY when mapTheme actually changes
  useEffect(() => {
    const map3d = map3dInstanceRef.current;
    if (!map3d) return;
    if (currentMapThemeRef.current === mapTheme) return;
    currentMapThemeRef.current = mapTheme;

    const targetStyle = getMapLibreStyleForTheme(mapTheme);
    try {
      map3d.setStyle(targetStyle);
      const onReload = () => {
        update3dRouteLine(
          map3d,
          routeCoords,
          activeRoute?.first_mile_coordinates,
          activeRoute?.comparison?.gmapsDetourCoordinates
        );
      };
      map3d.once('style.load', onReload);
    } catch (e) {
      console.warn('Map3d setStyle error:', e);
    }
  }, [
    mapTheme,
    routeCoords,
    activeRoute?.first_mile_coordinates,
    activeRoute?.comparison?.gmapsDetourCoordinates,
  ]);

  // MapLibre 3D Markers (A, B and Multi-POI Medical Callout Notes)
  useEffect(() => {
    const map3d = map3dInstanceRef.current;
    if (!map3d) return;

    // Clear old pin markers
    pinMarkers3dRef.current.forEach((m) => m.remove());
    pinMarkers3dRef.current = [];

    // Marker A (Origin) kèm sóng Radar lan tỏa & Beacon định vị trực quan
    const elA = document.createElement('div');
    elA.className = 'nav-map-pin-wrap user-gps-pin-container';
    elA.innerHTML = `
      <div class="user-live-gps-beacon">
        <div class="user-radar-wave-ring"></div>
        <div class="user-radar-wave-ring wave-delay-2"></div>
        <div class="beacon-core-dot"></div>
        <div class="nav-marker-pin pin-a user-active-pin">
          <span class="pin-letter">A</span>
          <span class="pin-tag">📍 Vị trí hiện tại của bạn</span>
        </div>
      </div>
    `;
    const markerA = new maplibregl.Marker({ element: elA, anchor: 'bottom' })
      .setLngLat([userLocation.lng, userLocation.lat])
      .addTo(map3d);
    pinMarkers3dRef.current.push(markerA);

    // Render Multi-POI Medical Callout Notes (theo tiến trình Radar xuất hiện)
    displayedPois.forEach((poi, idx) => {
      const isSelected = Boolean(selectedPoi && poi.id === selectedPoi.id);

      const el = document.createElement('div');
      el.className = 'nav-map-pin-wrap';
      el.innerHTML = buildPoiCalloutNoteHtml(poi, idx, isSelected);
      el.addEventListener('click', () => {
        setSelectedPoi(poi);
      });

      const m = new maplibregl.Marker({ element: el, anchor: 'bottom' })
        .setLngLat([poi.lng, poi.lat])
        .addTo(map3d);
      pinMarkers3dRef.current.push(m);
    });
  }, [
    userLocation.lat,
    userLocation.lng,
    userLocation.name,
    selectedPoi,
    displayedPois,
    isRadarScanning,
    buildPoiCalloutNoteHtml,
    openGoogleReviewsPanel,
  ]);

  // Chỉ tự động căn khung 1 lần duy nhất khi danh sách cơ sở y tế được nạp, không cản trở thao tác cuộn/kéo chuột tự do
  // Tự động căn khung MapLibre 3D bao quát Vị trí của bạn và các điểm y tế lân cận
  useEffect(() => {
    const map3d = map3dInstanceRef.current;
    if (!map3d || selectedPoi || isSimulatingDrive || mapViewMode !== '3d_cockpit') return;
    if (typeof userLocation.lat !== 'number' || typeof userLocation.lng !== 'number') return;

    try {
      if (displayedPois.length > 0) {
        const boundsPois = displayedPois.slice(0, 6);
        const bounds = new maplibregl.LngLatBounds(
          [userLocation.lng, userLocation.lat],
          [userLocation.lng, userLocation.lat]
        );
        boundsPois.forEach((p) => {
          if (typeof p.lng === 'number' && typeof p.lat === 'number') {
            bounds.extend([p.lng, p.lat]);
          }
        });
        map3d.fitBounds(bounds, {
          padding: { top: 90, bottom: 80, left: 180, right: 80 },
          maxZoom: 16.5,
          pitch: 48,
          duration: 750,
        });
      } else {
        map3d.flyTo({ center: [userLocation.lng, userLocation.lat], zoom: 16.2, pitch: 48, duration: 800 });
      }
    } catch (e) {}
  }, [userLocation.lat, userLocation.lng, displayedPois.length, selectedPoi, isSimulatingDrive, mapViewMode]);

  // MapLibre 3D Vehicle Marker & Chase Camera
  useEffect(() => {
    const map3d = map3dInstanceRef.current;
    if (!map3d) return;

    if (!vehiclePosition) {
      if (vehicleMarker3dRef.current) {
        vehicleMarker3dRef.current.remove();
        vehicleMarker3dRef.current = null;
      }
      return;
    }

    const [vLat, vLng] = vehiclePosition;

    if (!vehicleMarker3dRef.current) {
      const elV = document.createElement('div');
      elV.className = 'nav-vehicle-marker-wrap';
      elV.innerHTML = `
        <div class="nav-vehicle-puck" id="maplibre-vehicle-puck" style="transform: rotate(${Math.round(vehicleHeading || 0)}deg);">
          <div class="puck-radar-ring"></div>
          <div class="puck-arrow-icon">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L4 21L12 17L20 21L12 2Z" fill="#00e5ff" stroke="#ffffff" stroke-width="1.8" stroke-linejoin="round"/>
            </svg>
          </div>
        </div>
      `;
      vehicleMarker3dRef.current = new maplibregl.Marker({ element: elV, anchor: 'center' })
        .setLngLat([vLng, vLat])
        .addTo(map3d);
    } else {
      vehicleMarker3dRef.current.setLngLat([vLng, vLat]);
      const puckEl = document.getElementById('maplibre-vehicle-puck');
      if (puckEl) {
        puckEl.style.transform = `rotate(${Math.round(vehicleHeading || 0)}deg)`;
      }
    }

    // Camera chase in 3D Cockpit mode with speed/turn adaptive zoom & pitch
    if (mapViewMode === '3d_cockpit' && isNavigatingLive) {
      let dynamicZoom = 17.5;
      let dynamicPitch = 60;

      const currentStepObj = steps[activeStepIndex] || null;
      const distToTurn = currentStepObj?.distance_km ?? 0.5;

      if (distToTurn < 0.08) {
        // Approaching intersection (< 80m): close-in zoom, reduced pitch for maximum junction clarity
        dynamicZoom = 18.2;
        dynamicPitch = 52;
      } else if (distToTurn < 0.25) {
        // Preparation zone (< 250m)
        dynamicZoom = 17.8;
        dynamicPitch = 56;
      } else {
        // Open route cruise: broad horizon
        dynamicZoom = 16.9;
        dynamicPitch = 62;
      }

      map3d.easeTo({
        center: [vLng, vLat],
        bearing: vehicleHeading || 0,
        pitch: dynamicPitch,
        zoom: dynamicZoom,
        duration: 700,
        easing: (t) => t,
      });
    }
  }, [vehiclePosition, vehicleHeading, mapViewMode, isNavigatingLive, steps, activeStepIndex]);

  // Resize handler on perspective mode toggle
  useEffect(() => {
    if (mapViewMode === '3d_cockpit' && map3dInstanceRef.current) {
      requestAnimationFrame(() => {
        map3dInstanceRef.current?.resize();
      });
      setTimeout(() => map3dInstanceRef.current?.resize(), 120);
    } else if (mapViewMode === '2d_overview' && map2dInstanceRef.current) {
      requestAnimationFrame(() => {
        map2dInstanceRef.current?.invalidateSize();
      });
      setTimeout(() => map2dInstanceRef.current?.invalidateSize(), 120);
    }
  }, [mapViewMode]);

  // =========================================================================
  // 2. ENGINE 2: LEAFLET 2D (OVERVIEW & LIGHTWEIGHT VIEW)
  // =========================================================================
  useEffect(() => {
    if (!map2dContainerRef.current) return;

    if (!map2dInstanceRef.current) {
      const map = L.map(map2dContainerRef.current, {
        center: [userLocation.lat, userLocation.lng],
        zoom: 15,
        zoomControl: true,
        attributionControl: false,
      });

      markersGroup2dRef.current = L.featureGroup().addTo(map);
      polylineGroup2dRef.current = L.featureGroup().addTo(map);
      map2dInstanceRef.current = map;
    }

    const map = map2dInstanceRef.current;
    map.eachLayer((layer) => {
      if (layer instanceof L.TileLayer) {
        map.removeLayer(layer);
      }
    });

    const googleStreetsHdTileUrl =
      'https://mt1.google.com/vt/lyrs=m&hl=vi&x={x}&y={y}&z={z}&scale=2';
    const googleHybridHdTileUrl =
      'https://mt1.google.com/vt/lyrs=y&hl=vi&x={x}&y={y}&z={z}&scale=2';
    const darkTileUrl = `https://maps.geoapify.com/v1/tile/dark-matter-dark-grey/{z}/{x}/{y}{r}.png?apiKey=${GEOAPIFY_API_KEY}`;
    const osmTileUrl = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

    if (mapTheme === 'satellite') {
      L.tileLayer(googleHybridHdTileUrl, {
        maxZoom: 21,
        detectRetina: true,
        attribution: '© Google Maps Satellite Hybrid',
      }).addTo(map);
    } else {
      const tileUrl =
        mapTheme === 'dark'
          ? darkTileUrl
          : mapTheme === 'osm'
          ? osmTileUrl
          : googleStreetsHdTileUrl;

      L.tileLayer(tileUrl, {
        maxZoom: 21,
        detectRetina: true,
        attribution: '© Google Maps, OpenStreetMap',
      }).addTo(map);
    }
  }, [mapTheme]);

  // Leaflet 2D Markers and Polyline
  useEffect(() => {
    const map = map2dInstanceRef.current;
    if (!map || !markersGroup2dRef.current || !polylineGroup2dRef.current) return;

    markersGroup2dRef.current.clearLayers();
    polylineGroup2dRef.current.clearLayers();

    const startCoords = [userLocation.lat, userLocation.lng];

    // Vòng bán kính chính xác GPS (Accuracy Circle)
    L.circle(startCoords, {
      radius: Math.max(30, userLocation.accuracy_meters || 45),
      color: '#00d2ff',
      weight: 1.5,
      opacity: 0.85,
      fillColor: '#00d2ff',
      fillOpacity: 0.12,
    }).addTo(markersGroup2dRef.current);

    // Ghim Vị trí hiện tại của bạn với sóng radar trực quan
    const startIcon = L.divIcon({
      className: 'nav-map-pin-wrap user-gps-pin-container',
      html: `
        <div class="user-live-gps-beacon">
          <div class="user-radar-wave-ring"></div>
          <div class="user-radar-wave-ring wave-delay-2"></div>
          <div class="beacon-core-dot"></div>
          <div class="nav-marker-pin pin-a user-active-pin">
            <span class="pin-letter">A</span>
            <span class="pin-tag">📍 Vị trí hiện tại của bạn</span>
          </div>
        </div>
      `,
      iconSize: [44, 52],
      iconAnchor: [22, 46],
    });
    const startMarker = L.marker(startCoords, { icon: startIcon, zIndexOffset: 1000 }).addTo(markersGroup2dRef.current);
    startMarker.bindPopup(`<b>📍 Vị trí hiện tại của bạn:</b><br/>${userLocation.name}<br/><small>${userLocation.address || ''}</small>`);

    // Multi-POI Medical Callout Notes on 2D Map (theo tiến trình Radar)
    displayedPois.forEach((poi, idx) => {
      const isSelected = Boolean(selectedPoi && poi.id === selectedPoi.id);
      const poiIcon = L.divIcon({
        className: 'nav-map-pin-wrap',
        html: buildPoiCalloutNoteHtml(poi, idx, isSelected),
        iconSize: [180, 42],
        iconAnchor: [90, 42],
      });
      const poiMarker = L.marker([poi.lat, poi.lng], { icon: poiIcon }).addTo(markersGroup2dRef.current);
      poiMarker.on('click', () => {
        setSelectedPoi(poi);
      });
    });

    if (selectedPoi) {
      if (routeCoords.length > 0) {
        // Layer 1: Contrast casing (Dark border)
        L.polyline(routeCoords, {
          color: '#0a192f',
          weight: 10,
          opacity: 0.9,
          lineCap: 'round',
          lineJoin: 'round',
        }).addTo(polylineGroup2dRef.current);

        // Layer 2: Main vibrant route path
        L.polyline(routeCoords, {
          color: mapTheme === 'dark' ? '#00e5ff' : '#2563eb',
          weight: 6,
          opacity: 0.95,
          lineCap: 'round',
          lineJoin: 'round',
        }).addTo(polylineGroup2dRef.current);

        // Layer 3: Inner white directional stripe
        const mainLine = L.polyline(routeCoords, {
          color: '#ffffff',
          weight: 2,
          opacity: 0.9,
          lineCap: 'round',
          lineJoin: 'round',
        }).addTo(polylineGroup2dRef.current);

        // Tầng 1: First-Mile Courtyard Connector (Cyan Dashed Line)
        if (activeRoute?.first_mile_coordinates?.length >= 2) {
          L.polyline(activeRoute.first_mile_coordinates, {
            color: '#00e5ff',
            weight: 5,
            dashArray: '6, 8',
            opacity: 0.95,
            lineCap: 'round',
          }).addTo(polylineGroup2dRef.current);

          const fmStart = activeRoute.first_mile_coordinates[0];
          L.circleMarker(fmStart, {
            radius: 6,
            color: '#00e5ff',
            fillColor: '#ffffff',
            fillOpacity: 1,
            weight: 2.5,
          })
            .bindTooltip(`⚡ Đã nối liền ${activeRoute.first_mile_meters || 38}m sân nội bộ`, {
              permanent: true,
              direction: 'top',
              className: 'leaflet-tooltip-first-mile',
            })
            .addTo(polylineGroup2dRef.current);
        }

        // Tầng 3: Google Maps Baseline Comparison Line (Amber Dashed Line)
        if (activeRoute?.comparison?.gmapsDetourCoordinates?.length >= 2) {
          L.polyline(activeRoute.comparison.gmapsDetourCoordinates, {
            color: '#f59e0b',
            weight: 3.5,
            dashArray: '5, 8',
            opacity: 0.75,
            lineCap: 'round',
          })
            .bindTooltip('Google Maps (Tuyến đi vòng)', {
              permanent: false,
              direction: 'right',
            })
            .addTo(polylineGroup2dRef.current);
        }

        if (!isNavigatingLive && mapViewMode === '2d_overview') {
          try {
            const destMarker = L.marker([selectedPoi.lat, selectedPoi.lng]);
            const group = L.featureGroup([startMarker, destMarker, mainLine]);
            map.fitBounds(group.getBounds(), { padding: [45, 45] });
          } catch {}
        }
      }
    }
  }, [
    userLocation,
    selectedPoi,
    displayedPois,
    isRadarScanning,
    activeRoute,
    mapTheme,
    isNavigatingLive,
    mapViewMode,
    routeCoords,
    buildPoiCalloutNoteHtml,
    openGoogleReviewsPanel,
  ]);

  // Tự động căn khung Leaflet 2D bao quát cả Vị trí của bạn và các điểm y tế lân cận
  useEffect(() => {
    const map = map2dInstanceRef.current;
    if (!map || selectedPoi || isNavigatingLive || mapViewMode !== '2d_overview') return;
    if (typeof userLocation.lat !== 'number' || typeof userLocation.lng !== 'number') return;

    try {
      if (displayedPois.length > 0) {
        const boundsPois = displayedPois.slice(0, 6);
        const pts = [
          [userLocation.lat, userLocation.lng],
          ...boundsPois.map((p) => [p.lat, p.lng]),
        ];
        map.fitBounds(pts, { padding: [60, 60], maxZoom: 16.5 });
      } else {
        map.setView([userLocation.lat, userLocation.lng], 15.5, { animate: true });
      }
    } catch {
      map.setView([userLocation.lat, userLocation.lng], 15);
    }
  }, [userLocation.lat, userLocation.lng, displayedPois.length, selectedPoi, isNavigatingLive, mapViewMode]);

  // Leaflet 2D Vehicle Marker
  useEffect(() => {
    const map = map2dInstanceRef.current;
    if (!map) return;

    if (!vehiclePosition) {
      if (vehicleMarker2dRef.current) {
        map.removeLayer(vehicleMarker2dRef.current);
        vehicleMarker2dRef.current = null;
      }
      return;
    }

    const vehicleIcon = L.divIcon({
      className: 'nav-vehicle-marker-wrap',
      html: `
        <div class="nav-vehicle-puck" style="transform: rotate(${Math.round(vehicleHeading || 0)}deg);">
          <div class="puck-radar-ring"></div>
          <div class="puck-arrow-icon">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L4 21L12 17L20 21L12 2Z" fill="#00e5ff" stroke="#ffffff" stroke-width="1.8" stroke-linejoin="round"/>
            </svg>
          </div>
        </div>
      `,
      iconSize: [44, 44],
      iconAnchor: [22, 22],
    });

    if (!vehicleMarker2dRef.current) {
      vehicleMarker2dRef.current = L.marker(vehiclePosition, {
        icon: vehicleIcon,
        zIndexOffset: 1200,
      }).addTo(map);
    } else {
      vehicleMarker2dRef.current.setLatLng(vehiclePosition);
      vehicleMarker2dRef.current.setIcon(vehicleIcon);
    }
  }, [vehiclePosition, vehicleHeading]);

  // Resize when switching views
  useEffect(() => {
    if (mapViewMode === '3d_cockpit' && map3dInstanceRef.current) {
      setTimeout(() => map3dInstanceRef.current?.resize(), 100);
    } else if (mapViewMode === '2d_overview' && map2dInstanceRef.current) {
      setTimeout(() => map2dInstanceRef.current?.invalidateSize(), 100);
    }
  }, [mapViewMode]);



  // Unified Simulation Driving Loop using Turf.js Pipeline
  useEffect(() => {
    if (!isSimulatingDrive || !routeCoords || routeCoords.length < 2) {
      if (simIntervalRef.current) {
        clearInterval(simIntervalRef.current);
        simIntervalRef.current = null;
      }
      return;
    }

    simIndexRef.current = 0;
    const totalPoints = routeCoords.length;

    simIntervalRef.current = setInterval(() => {
      simIndexRef.current += 1;
      if (simIndexRef.current >= totalPoints) {
        clearInterval(simIntervalRef.current);
        simIntervalRef.current = null;
        setIsSimulatingDrive(false);
        speakVietnameseInstruction(
          `Bạn đã đến điểm đích: ${selectedPoi?.name || 'điểm đến'}. Chúc bạn dồi dào sức khỏe!`,
          voiceGuidanceEnabled
        );
        onNotify?.(`Đã hoàn thành lộ trình đến ${selectedPoi?.name || 'điểm đến'}`);
        return;
      }

      const curRaw = routeCoords[simIndexRef.current];
      // Run through Turf.js map matching and bearing
      const processed = processNavigationPosition(curRaw[0], curRaw[1], routeCoords);

      setVehiclePosition([processed.snappedLat, processed.snappedLng]);
      setVehicleHeading(processed.heading);

      // Advance turn step based on progress
      if (steps.length > 0) {
        const stepProgress = Math.min(
          steps.length - 1,
          Math.floor((simIndexRef.current / totalPoints) * steps.length)
        );
        setActiveStepIndex((prevIdx) => {
          if (stepProgress !== prevIdx) {
            const nextStepObj = steps[stepProgress];
            if (nextStepObj) {
              speakVietnameseInstruction(
                `${formatDistanceToTurn(nextStepObj.distance_km, nextStepObj.distance_meters)}, ${translateStepInstruction(nextStepObj.instruction, nextStepObj.road_name, nextStepObj.landmark)}`,
                voiceGuidanceEnabled
              );
            }
            return stepProgress;
          }
          return prevIdx;
        });
      }
    }, 1400);

    return () => {
      if (simIntervalRef.current) {
        clearInterval(simIntervalRef.current);
        simIntervalRef.current = null;
      }
    };
  }, [isSimulatingDrive, routeCoords, steps, voiceGuidanceEnabled, selectedPoi, onNotify]);

  // Start Live Turn-by-Turn Navigation (Stage 2: Active 3D Cockpit HUD)
  const startLiveNavigation = (simulate = false) => {
    setIsNavigatingLive(true);
    setMapViewMode('3d_cockpit');
    setActiveStepIndex(0);
    const startPoint = routeCoords[0] || [userLocation.lat, userLocation.lng];
    const initialProcessed = processNavigationPosition(startPoint[0], startPoint[1], routeCoords);

    setVehiclePosition([initialProcessed.snappedLat, initialProcessed.snappedLng]);
    setVehicleHeading(initialProcessed.heading);

    if (map3dInstanceRef.current) {
      map3dInstanceRef.current.easeTo({
        center: [initialProcessed.snappedLng, initialProcessed.snappedLat],
        bearing: initialProcessed.heading,
        pitch: 60,
        zoom: 17.5,
        duration: 800,
      });
    }

    const initialInstruction = steps[0]
      ? `${formatDistanceToTurn(steps[0].distance_km, steps[0].distance_meters)}, ${translateStepInstruction(steps[0].instruction, steps[0].road_name, steps[0].landmark)}`
      : `Bắt đầu dẫn đường đến ${selectedPoi?.name || 'điểm đến'}`;
    speakVietnameseInstruction(
      `Bắt đầu điều hướng đến ${selectedPoi?.name || 'điểm đến'}. ${initialInstruction}`,
      voiceGuidanceEnabled
    );

    if (simulate) {
      setIsSimulatingDrive(true);
    }
    onNotify?.('Đã kích hoạt chế độ dẫn đường Turn-by-Turn');
  };

  // Stop Live Navigation (Return to Stage 1: 2D Overview)
  const stopLiveNavigation = () => {
    setIsNavigatingLive(false);
    setIsSimulatingDrive(false);
    setMapViewMode('2d_overview');
    if (simIntervalRef.current) {
      clearInterval(simIntervalRef.current);
      simIntervalRef.current = null;
    }
    setVehiclePosition(null);
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    if (map3dInstanceRef.current) {
      map3dInstanceRef.current.easeTo({ pitch: 0, bearing: 0, zoom: 15, duration: 600 });
    }
    if (map2dInstanceRef.current && selectedPoi) {
      map2dInstanceRef.current.setView([userLocation.lat, userLocation.lng], 15);
    }
  };

  const toggleSimulateDriving = () => {
    if (!isNavigatingLive) {
      startLiveNavigation(true);
      return;
    }
    setIsSimulatingDrive((prev) => !prev);
  };

  const handleStepClick = (idx) => {
    setActiveStepIndex(idx);
    const step = steps[idx];
    if (step && voiceGuidanceEnabled) {
      speakVietnameseInstruction(
        `${formatDistanceToTurn(step.distance_km, step.distance_meters)}, ${translateStepInstruction(step.instruction, step.road_name, step.landmark)}`,
        true
      );
    }
  };

  // Test Hyper-Local Routing Handler (Scenario Hình 3 @ 20.98823, 105.79569)
  const handleTestHyperLocalRouting = useCallback(() => {
    const testCase = HANOI_UNIVERSITY_ITALIA_TEST_CASE;
    // 1. Update user location to courtyard pin in Hanoi University
    setUserLocation(testCase.origin);
    saveUserLocation(testCase.origin);

    // 2. Select target pharmacy: Long Châu 421 Nguyễn Trãi
    const dest = testCase.destinationLongChau421;
    setSelectedPoi(dest);

    // 3. Orchestrate 5-tier hyper-local clinical route
    const orchestrated = orchestrateHyperLocalRoute({
      origin: testCase.origin,
      destination: dest,
      travelMode: 'motorcycle',
    });

    setActiveRoute(orchestrated);
    setActiveStepIndex(0);

    // 4. Center camera smoothly
    if (mapViewMode === '3d_cockpit' && map3dInstanceRef.current) {
      map3dInstanceRef.current.easeTo({
        center: [testCase.origin.lng, testCase.origin.lat],
        pitch: 60,
        bearing: 42,
        zoom: 17.5,
        duration: 800,
      });
    } else if (map2dInstanceRef.current) {
      map2dInstanceRef.current.flyTo([testCase.origin.lat, testCase.origin.lng], 17, {
        duration: 0.8,
      });
    }

    onNotify?.(
      '⚡ Đã kích hoạt Lộ trình Hyper-Local (Fix Hình 3): Nối liền 38m sân Ngõ 2 ĐH Hà Nội ra Trục chính & KM9 Nguyễn Trãi.'
    );
  }, [mapViewMode, onNotify]);

  // Google Maps Deep Links with Vehicle Modes & Avoidances (Synchronized from Video!)
  const gmapsTravelMode =
    travelMode === 'motorcycle'
      ? 'two_wheeler'
      : travelMode === 'walk'
      ? 'walking'
      : 'driving';
  const avoidList = [];
  if (avoidTolls) avoidList.push('t');
  if (avoidHighways || travelMode === 'motorcycle') avoidList.push('h');
  const avoidParam = avoidList.length > 0 ? `&avoid=${avoidList.join(',')}` : '';

  const googleMapsUrl = selectedPoi
    ? `https://www.google.com/maps/dir/?api=1&origin=${userLocation.lat},${userLocation.lng}&destination=${selectedPoi.lat},${selectedPoi.lng}&travelmode=${gmapsTravelMode}${avoidParam}`
    : `https://www.google.com/maps/dir/?api=1&origin=${userLocation.lat},${userLocation.lng}&destination=nha+thuoc+gan+nhat&travelmode=${gmapsTravelMode}${avoidParam}`;

  const googleMapsNavUrl = selectedPoi
    ? `https://www.google.com/maps/dir/?api=1&origin=${userLocation.lat},${userLocation.lng}&destination=${selectedPoi.lat},${selectedPoi.lng}&travelmode=${gmapsTravelMode}&dir_action=navigate${avoidParam}`
    : `https://www.google.com/maps/dir/?api=1&origin=${userLocation.lat},${userLocation.lng}&destination=nha+thuoc+gan+nhat&travelmode=${gmapsTravelMode}&dir_action=navigate${avoidParam}`;

  const googleMapsEmbedUrl = selectedPoi
    ? `https://maps.google.com/maps?saddr=${userLocation.lat},${userLocation.lng}&daddr=${selectedPoi.lat},${selectedPoi.lng}&output=embed`
    : `https://maps.google.com/maps?saddr=${userLocation.lat},${userLocation.lng}&daddr=nha+thuoc+gan+nhat&output=embed`;

  return (
    <div
      className={`navigation-workspace-page ${
        isMapFullscreen ? 'fullscreen-active' : ''
      } ${isToolbarsCollapsed ? 'toolbars-collapsed' : ''}`}
    >
      {/* Geolocation & Custom Address Picker Modal */}
      {permissionPromptOpen && (
        <div
          className="nav-permission-overlay"
          role="dialog"
          aria-modal="true"
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setPermissionPromptOpen(false);
            }
          }}
        >
          <div className="nav-permission-modal" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              className="modal-close-btn"
              onClick={() => setPermissionPromptOpen(false)}
              aria-label="Đóng và tiếp tục với bản đồ"
              title="Đóng"
            >
              <X size={20} />
            </button>
            <div className="modal-icon-badge">
              <LocateFixed size={28} />
            </div>
            <h3>Xác Định Vị Trí Của Bạn (GPS Thiết Bị)</h3>
            <p>
              MedGuard AI đọc <strong>tọa độ GPS thực tế từ thiết bị của bạn</strong> để đo khoảng cách và tìm nhà thuốc GPP & điểm cấp cứu chính xác nhất xung quanh bạn, không cố định bất kỳ vị trí nào.
            </p>

            {/* Current Detected Coordinates Box */}
            <div className={`modal-current-fallback ${userLocation.is_gps ? 'gps-confirmed' : ''}`}>
              <div className="status-badge-row">
                <span className={`status-dot ${userLocation.is_gps ? 'live' : 'detecting'}`} />
                <span className="fallback-label">
                  {userLocation.is_gps ? 'Vị trí GPS thực tế đã xác nhận:' : 'Trạng thái vị trí hiện tại:'}
                </span>
                {userLocation.accuracy_meters && (
                  <span className="accuracy-tag">Sai số ±{userLocation.accuracy_meters}m</span>
                )}
              </div>
              <strong className="fallback-name">{userLocation.name}</strong>
              <small className="fallback-addr">{userLocation.address}</small>
              <small className="fallback-coords">
                Tọa độ thực tế: {userLocation.lat?.toFixed(5)}, {userLocation.lng?.toFixed(5)}
              </small>
            </div>

            {/* Primary GPS Action Button */}
            <div className="modal-actions-row">
              <button
                type="button"
                className="btn-grant-gps"
                disabled={requestingGps}
                onClick={() => handleRequestGps(false)}
              >
                {requestingGps ? (
                  <>
                    <RefreshCw size={18} className="spin" />
                    <span>Đang kết nối vệ tinh GPS & xác thực tọa độ...</span>
                  </>
                ) : (
                  <>
                    <LocateFixed size={18} />
                    <span>Lấy Chính Xác Vị Trí GPS Của Tôi (Khuyến Nghị)</span>
                  </>
                )}
              </button>

              {/* Address Search Option */}
              <div className="modal-address-search-container">
                <div className="address-search-input-wrap">
                  <Search size={16} className="search-icon" />
                  <input
                    type="text"
                    className="modal-address-input"
                    placeholder="Hoặc gõ địa chỉ của bạn (VD: số nhà, tên đường, phường xã)..."
                    value={addressSearchQuery}
                    onChange={(e) => setAddressSearchQuery(e.target.value)}
                  />
                  {isSearchingAddress && <RefreshCw size={14} className="spin search-spinner" />}
                </div>

                {addressSearchResults.length > 0 && (
                  <div className="modal-address-dropdown">
                    {addressSearchResults.map((item, idx) => (
                      <button
                        key={idx}
                        type="button"
                        className="dropdown-item-btn"
                        onClick={() => handleSelectSearchedLocation(item)}
                      >
                        <MapPin size={14} className="item-icon" />
                        <div className="item-text">
                          <strong className="item-title">{item.name}</strong>
                          <span className="item-desc">{item.address}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Quick Preset Locations */}
              <div className="modal-quick-presets">
                <span className="presets-title">HOẶC CHỌN NHANH KHU VỰC:</span>
                <div className="presets-chips">
                  {LOCATION_PRESETS.map((preset) => (
                    <button
                      key={preset.id}
                      type="button"
                      className="preset-chip-btn"
                      onClick={() => handleSelectSearchedLocation(preset)}
                    >
                      <MapPin size={12} />
                      <span>{preset.tag || preset.name}</span>
                    </button>
                  ))}
                </div>
              </div>

              <button
                type="button"
                className="btn-use-preset"
                onClick={() => setPermissionPromptOpen(false)}
              >
                Đóng và tiếp tục xem bản đồ
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 1. Streamlined Single-Row Control Bar (Clean 46px height, no double headers) */}
      <header className="nav-page-topbar">
        <div className="nav-topbar-left">
          <div className="nav-status-badge">
            <span className="nav-status-pulse" />
            <span className="nav-status-title">RETINA HD • BẢN ĐỒ Y TẾ REAL-TIME</span>
          </div>
        </div>

        <div className="nav-topbar-controls">
          {/* Origin Pill with GPS button & Clickable Location Modal Trigger */}
          <div
            className={`nav-origin-pill ${userLocation.is_gps ? 'gps-active' : 'need-gps'}`}
            title="Bấm để đổi vị trí hoặc lấy GPS chính xác"
            onClick={() => setPermissionPromptOpen(true)}
          >
            <span className={`loc-dot ${userLocation.is_gps ? 'gps pulse' : 'detecting'}`} />
            <MapPin size={14} className="pin-icon" />
            <div className="origin-text">
              <div className="origin-badge-row">
                <span className="origin-title">{userLocation.name}</span>
                <span className={`origin-type-badge ${userLocation.is_gps ? 'verified' : 'pending'}`}>
                  {userLocation.is_gps ? `GPS ±${userLocation.accuracy_meters || 5}m` : 'Bấm để bật GPS'}
                </span>
              </div>
              <small className="origin-coords">
                {userLocation.lat ? `${userLocation.lat.toFixed(5)}, ${userLocation.lng.toFixed(5)}` : 'Đang lấy tọa độ...'}
              </small>
            </div>
            <button
              type="button"
              className="gps-refresh-btn"
              onClick={(e) => {
                e.stopPropagation();
                handleRequestGps(false);
              }}
              disabled={requestingGps}
              title="Lấy lại vị trí GPS thực tế từ thiết bị"
            >
              <LocateFixed size={13} className={requestingGps ? 'spin' : ''} />
              <span>{userLocation.is_gps ? 'Cập nhật GPS' : 'Lấy GPS'}</span>
            </button>
          </div>

          {/* 3-State Audio Guidance Control */}
          <button
            type="button"
            className={`nav-audio-mode-btn audio-${audioGuidanceMode}`}
            onClick={handleCycleAudioGuidance}
            title="Chế độ âm thanh dẫn đường: Bật đầy đủ / Chỉ phát cảnh báo / Tắt tiếng"
          >
            {audioGuidanceMode === 'full' ? (
              <>
                <Volume2 size={14} />
                <span>Loa: Đầy đủ</span>
              </>
            ) : audioGuidanceMode === 'alerts_only' ? (
              <>
                <Volume1 size={14} />
                <span>Loa: Chỉ cảnh báo</span>
              </>
            ) : (
              <>
                <VolumeX size={14} />
                <span>Loa: Tắt tiếng</span>
              </>
            )}
          </button>

          {/* Toggle POI Cards Drawer */}
          <button
            type="button"
            className={`nav-drawer-toggle-btn ${showPoiDrawer ? 'active' : ''}`}
            onClick={() => setShowPoiDrawer((prev) => !prev)}
            title="Mở / đóng danh sách cơ sở y tế chi tiết"
          >
            <Layers size={14} />
            <span>Danh sách ({pois.length})</span>
          </button>

          {/* Download System Design Docs */}
          <div className="nav-doc-download-pill" title="Tải xuống Kế hoạch Thiết kế Hệ thống & Module 10">
            <button
              type="button"
              className="nav-doc-download-btn doc-md"
              onClick={() => handleDownloadDesignDoc('md')}
              title="Tải tệp thiết kế định dạng Markdown (.MD)"
            >
              <FileText size={13} />
              <span>Tải .MD</span>
            </button>
            <button
              type="button"
              className="nav-doc-download-btn doc-word"
              onClick={() => handleDownloadDesignDoc('doc')}
              title="Tải tệp thiết kế định dạng Microsoft Word (.DOCX)"
            >
              <Download size={13} />
              <span>Tải .DOC</span>
            </button>
          </div>
        </div>
      </header>

      {/* Consultation Guidance Context Banner when arriving from chat */}
      {navigationContext?.fromChat && (
        <div
          className="nav-consultation-guidance-banner"
          role="region"
          aria-label="Chỉ dẫn từ ca tư vấn y tế"
        >
          <div className="consultation-banner-info">
            <div className="consultation-badge-row">
              <span className="consultation-pulse-dot" />
              <Sparkles size={14} className="consultation-sparkle" />
              <strong className="consultation-kicker">
                {navigationContext.chatKicker || 'CHỈ DẪN TRỰC TIẾP TỪ CA TƯ VẤN Y TẾ'}
              </strong>
              <span className="consultation-status-pill">Đồng bộ chính xác từ Chat</span>
            </div>
            <div className="consultation-dest-heading">
              <h2 className="consultation-poi-name">
                {selectedPoi?.name || navigationContext.selectedPoi?.name}
              </h2>
              <span className="consultation-poi-address">
                <MapPin size={13} />
                {selectedPoi?.address || navigationContext.selectedPoi?.address}
              </span>
            </div>
            {activeRoute && (
              <div className="consultation-route-pills">
                <span className="route-pill pill-dist">
                  <Route size={12} />
                  Khoảng cách: <strong>{activeRoute.distance_km} km</strong>
                </span>
                <span className="route-pill pill-eta">
                  <Clock size={12} />
                  Thời gian: ~<strong>{activeRoute.eta_minutes} phút</strong>
                </span>
                {activeRoute.corridor_description && (
                  <span
                    className="route-pill pill-corridor"
                    title={activeRoute.corridor_description}
                  >
                    <Navigation size={12} />
                    {activeRoute.corridor_description}
                  </span>
                )}
              </div>
            )}
          </div>

          <div className="consultation-banner-actions">
            <button
              type="button"
              className="banner-cockpit-start-btn"
              onClick={() => startLiveNavigation(false)}
              title="Bật chế độ chỉ đường trực tiếp HUD"
            >
              <Navigation size={15} />
              <span>Chỉ Đường Trực Tiếp</span>
            </button>
            <a
              href={googleMapsNavUrl}
              target="_blank"
              rel="noreferrer"
              className="banner-gmaps-btn"
              title="Mở Google Maps App với chế độ dẫn đường Turn-by-Turn GPS"
            >
              <Navigation size={15} />
              <span>Google Maps GPS</span>
              <ExternalLink size={12} />
            </a>
          </div>
        </div>
      )}

      {/* 2. Hero Full-Canvas Workspace Layout */}
      <div className={`nav-workspace-layout ${showPoiDrawer ? 'has-drawer' : 'full-canvas'}`}>
        {/* Map View Canvas (Occupies full space) */}
        <section className="nav-map-view-section">
          <div className="nav-leaflet-container">
            {/* MapLibre 3D WebGL Root */}
            <div
              ref={map3dContainerRef}
              className="nav-maplibre-3d-root"
              style={{ display: mapViewMode === '3d_cockpit' ? 'block' : 'none' }}
            />

            {/* Leaflet 2D Map Root */}
            <div
              ref={map2dContainerRef}
              className="nav-leaflet-map-root"
              style={{ display: mapViewMode === '2d_overview' ? 'block' : 'none' }}
            />

            {/* FLOATING COMPONENT 1: Unified Floating Medical Search & Category Radar Card */}
            <div className={`floating-medical-radar-card ${isFloatingPanelCollapsed ? 'is-collapsed' : ''}`}>
              <div className="card-top-search-row">
                <div className="smart-search-box">
                  <Search size={15} className="search-icon" />
                  <input
                    type="text"
                    className="smart-search-input"
                    placeholder="Tìm nhà thuốc GPP, phòng khám, cấp cứu..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        handleExecuteSearch(searchQuery);
                      }
                    }}
                  />
                  {searchQuery && (
                    <button
                      type="button"
                      className="btn-clear-search"
                      onClick={() => {
                        setSearchQuery('');
                        setPoiType('pharmacy');
                      }}
                      title="Xóa tìm kiếm"
                    >
                      <X size={13} />
                    </button>
                  )}
                  <button
                    type="button"
                    className={`btn-voice-search ${isListeningVoice ? 'listening' : ''}`}
                    onClick={handleVoiceSearchToggle}
                    title="Tìm kiếm bằng giọng nói tiếng Việt"
                  >
                    {isListeningVoice ? <MicOff size={14} /> : <Mic size={14} />}
                  </button>
                </div>
                <button
                  type="button"
                  className="btn-collapse-panel"
                  onClick={() => setIsFloatingPanelCollapsed((prev) => !prev)}
                  title={isFloatingPanelCollapsed ? 'Mở rộng bảng điều khiển' : 'Thu gọn bảng điều khiển'}
                >
                  {isFloatingPanelCollapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
                </button>
              </div>

              {!isFloatingPanelCollapsed && (
                <div className="card-body-content">
                  <div className="medical-category-selector-section">
                    <div className="selector-title-row">
                      <Sparkles size={12} className="selector-sparkle-icon" />
                      <span className="selector-title">DANH MỤC CƠ SỞ Y TẾ CẦN TÌM</span>
                    </div>
                    <div className="category-chips-grid">
                      <button
                        type="button"
                        className={`category-chip ${selectedCategory === 'pharmacy' ? 'active' : ''}`}
                        onClick={() => {
                          setSelectedCategory('pharmacy');
                          setPoiType('pharmacy');
                        }}
                      >
                        <div className="chip-icon-box pharmacy">
                          <Pill size={16} strokeWidth={2.4} />
                        </div>
                        <div className="chip-text">
                          <strong className="chip-name">Điểm Bán Thuốc</strong>
                          <small className="chip-sub">Nhà thuốc GPP • 24/7</small>
                        </div>
                      </button>

                      <button
                        type="button"
                        className={`category-chip ${selectedCategory === 'clinic' ? 'active' : ''}`}
                        onClick={() => {
                          setSelectedCategory('clinic');
                          setPoiType('clinic');
                        }}
                      >
                        <div className="chip-icon-box clinic">
                          <Stethoscope size={16} strokeWidth={2.4} />
                        </div>
                        <div className="chip-text">
                          <strong className="chip-name">Điểm Y Tế</strong>
                          <small className="chip-sub">Phòng khám • Trạm y tế</small>
                        </div>
                      </button>

                      <button
                        type="button"
                        className={`category-chip ${selectedCategory === 'emergency' ? 'active' : ''}`}
                        onClick={() => {
                          setSelectedCategory('emergency');
                          setPoiType('emergency');
                        }}
                      >
                        <div className="chip-icon-box emergency">
                          <Ambulance size={16} strokeWidth={2.4} />
                        </div>
                        <div className="chip-text">
                          <strong className="chip-name">Cấp Cứu 24/7</strong>
                          <small className="chip-sub">Bệnh viện • Đội xe 115</small>
                        </div>
                      </button>

                      <button
                        type="button"
                        className={`category-chip ${selectedCategory === 'all' ? 'active' : ''}`}
                        onClick={() => {
                          setSelectedCategory('all');
                          setPoiType('all');
                        }}
                      >
                        <div className="chip-icon-box all">
                          <Building2 size={16} strokeWidth={2.4} />
                        </div>
                        <div className="chip-text">
                          <strong className="chip-name">Tất Cả Cơ Sở</strong>
                          <small className="chip-sub">Tổng hợp quanh bạn</small>
                        </div>
                      </button>
                    </div>
                  </div>

                  {/* Prominent Scan Action Button */}
                  <button
                    type="button"
                    className="btn-trigger-radar-primary"
                    onClick={() => executeRadarScan(selectedCategory)}
                    disabled={isScanningActive}
                  >
                    <div className="btn-radar-icon-box">
                      <Compass size={18} className={isScanningActive ? 'spin' : 'pulse-subtle'} />
                    </div>
                    <div className="btn-text-col">
                      <span className="btn-lead">
                        Quét {selectedCategory === 'pharmacy' ? 'Điểm Bán Thuốc' : selectedCategory === 'clinic' ? 'Điểm Y Tế' : selectedCategory === 'emergency' ? 'Bệnh Viện Cấp Cứu' : 'Tất Cả Cơ Sở'} Quanh Bạn
                      </span>
                      <small className="btn-subtext">Bán kính ~2.0 km • Đầy đủ địa chỉ & đánh giá</small>
                    </div>
                  </button>

                  {/* Vehicle Mode & Avoidances */}
                  <div className="vehicle-travel-row">
                    <div className="travel-mode-pills">
                      <button
                        type="button"
                        className={`mode-pill ${travelMode === 'motorcycle' ? 'active' : ''}`}
                        onClick={() => setTravelMode('motorcycle')}
                        title="Xe máy: Tối ưu ngõ hẻm an toàn"
                      >
                        <Bike size={13} />
                        <span>Xe máy</span>
                      </button>
                      <button
                        type="button"
                        className={`mode-pill ${travelMode === 'drive' ? 'active' : ''}`}
                        onClick={() => setTravelMode('drive')}
                        title="Ô tô: Lộ trình đường lớn"
                      >
                        <Car size={13} />
                        <span>Ô tô</span>
                      </button>
                      <button
                        type="button"
                        className={`mode-pill ${travelMode === 'walk' ? 'active' : ''}`}
                        onClick={() => setTravelMode('walk')}
                        title="Đi bộ"
                      >
                        <Footprints size={13} />
                        <span>Đi bộ</span>
                      </button>
                    </div>
                    <div className="avoidances-compact">
                      <label className="compact-avoid-label" title="Tránh trạm thu phí BOT">
                        <input
                          type="checkbox"
                          checked={avoidTolls}
                          onChange={(e) => setAvoidTolls(e.target.checked)}
                        />
                        <span>Tránh thu phí</span>
                      </label>
                      <label className="compact-avoid-label" title="Tránh đường cao tốc">
                        <input
                          type="checkbox"
                          checked={avoidHighways}
                          onChange={(e) => setAvoidHighways(e.target.checked)}
                        />
                        <span>Tránh cao tốc</span>
                      </label>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* FLOATING COMPONENT 2: Professional Medical Radar Scanning Modal / HUD */}
            {isScanningActive && (
              <div className="medical-radar-scanning-modal" role="status" aria-live="assertive">
                <div className="radar-scanning-card">
                  <div className="radar-holo-animation">
                    <div className="radar-sweep-beam" />
                    <div className="radar-ring r1" />
                    <div className="radar-ring r2" />
                    <div className="radar-ring r3" />
                    <div className="radar-center-icon">
                      {selectedCategory === 'pharmacy' && <Pill size={36} className="radar-svg-center pharmacy" strokeWidth={2.4} />}
                      {selectedCategory === 'clinic' && <Stethoscope size={36} className="radar-svg-center clinic" strokeWidth={2.4} />}
                      {selectedCategory === 'emergency' && <Ambulance size={36} className="radar-svg-center emergency" strokeWidth={2.4} />}
                      {selectedCategory === 'all' && <Building2 size={36} className="radar-svg-center all" strokeWidth={2.4} />}
                    </div>
                  </div>

                  <div className="radar-scan-info">
                    <div className="radar-status-badge">
                      <span className="live-dot-pulse" />
                      <span>MEDGUARD RADAR SCANNER AI</span>
                    </div>
                    <h3 className="radar-title">
                      Đang quét {selectedCategory === 'pharmacy' ? 'Điểm bán thuốc GPP' : selectedCategory === 'clinic' ? 'Điểm Y tế & Phòng khám' : selectedCategory === 'emergency' ? 'Cơ sở Cấp cứu 24/7' : 'Tất cả cơ sở y tế'}...
                    </h3>
                    <p className="radar-desc">
                      {selectedCategory === 'pharmacy'
                        ? 'Đang kết nối danh bạ Nhà thuốc GPP, đối soát giấy phép Bộ Y Tế & kiểm tra tình trạng mở cửa trong bán kính 2km...'
                        : selectedCategory === 'clinic'
                        ? 'Đang tìm kiếm Phòng khám đa khoa, Trạm y tế & Bác sĩ chuyên khoa trực ban gần bạn nhất...'
                        : selectedCategory === 'emergency'
                        ? 'Đang quét Bệnh viện cấp cứu 24/7, Cổng cấp cứu A9, Khoa hồi sức cấp cứu (ICU) & Đội xe 115...'
                        : 'Đang tổng hợp dữ liệu toàn bộ cơ sở y tế, dược phẩm & trạm cấp cứu quanh vị trí của bạn...'}
                    </p>

                    <div className="radar-progress-bar-wrap">
                      <div className="radar-progress-bar-fill" style={{ width: `${scanProgress}%` }} />
                    </div>
                    <div className="radar-progress-labels">
                      <span className="prog-percent">Tiến độ phân tích: {scanProgress}%</span>
                      <span className="prog-radius">Bán kính: ~2.0 km</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* FLOATING COMPONENT 3: 3D/2D View Mode & Theme Switcher (Top-Right) */}
            <div className="floating-view-mode-pill">
              <div className="mode-toggle-group">
                <button
                  type="button"
                  className={`mode-pill-btn ${mapViewMode === '3d_cockpit' ? 'active' : ''}`}
                  onClick={() => setMapViewMode('3d_cockpit')}
                  title="Bản đồ 3D Buồng lái nghiêng 60° (MapLibre GL JS & Nhà 3D)"
                >
                  <Car size={13} />
                  <span>3D Buồng Lái</span>
                </button>
                <button
                  type="button"
                  className={`mode-pill-btn ${mapViewMode === '2d_overview' ? 'active' : ''}`}
                  onClick={() => setMapViewMode('2d_overview')}
                  title="Bản đồ 2D Toàn cảnh (Leaflet HD)"
                >
                  <Compass size={13} />
                  <span>2D Toàn Cảnh</span>
                </button>
              </div>

              <div className="theme-toggle-group">
                <button
                  type="button"
                  className={`theme-pill-btn ${mapTheme === 'streets' ? 'active' : ''}`}
                  onClick={() => setMapTheme('streets')}
                  title="Bản đồ Phố HD"
                >
                  Phố HD
                </button>
                <button
                  type="button"
                  className={`theme-pill-btn ${mapTheme === 'satellite' ? 'active' : ''}`}
                  onClick={() => setMapTheme('satellite')}
                  title="Bản đồ Vệ tinh"
                >
                  Vệ Tinh
                </button>
                <button
                  type="button"
                  className={`theme-pill-btn ${mapTheme === 'dark' ? 'active' : ''}`}
                  onClick={() => setMapTheme('dark')}
                  title="Bản đồ Nền tối"
                >
                  Tối
                </button>
              </div>

              <button
                type="button"
                className="btn-test-hyperlocal"
                onClick={handleTestHyperLocalRouting}
                title="Kiểm tra Lộ trình Hyper-Local chính xác hơn Google Maps tại Ngõ 2 ĐH Hà Nội (Fix Hình 3)"
              >
                <Zap size={14} />
                <span>Test Chỉ Đường Hyper-Local (Fix Hình 3)</span>
              </button>
            </div>

            {/* FLOATING COMPONENT 4: Selected Place Detail Card (When Point is Clicked) */}
            {selectedPoi && !isNavigatingLive && mapViewMode !== 'gmaps_embed' && (() => {
              const isEmergencyPoi = selectedPoi.type === 'hospital_emergency' || /cấp cứu|bệnh viện/i.test(selectedPoi.name || '');
              const isClinicPoi = selectedPoi.category_badge?.includes('PHÒNG KHÁM') || /phòng khám|trạm y tế|chuyên khoa/i.test(selectedPoi.name || '');
              const fallbackHeroImageSrc = isEmergencyPoi ? '/assets/emergency_hero.jpg' : isClinicPoi ? '/assets/clinic_hero.jpg' : '/assets/pharmacy_hero.jpg';

              // Dynamic Google Maps Places Photo API URL
              const photoQuery = `${selectedPoi.name || ''} ${selectedPoi.address || ''}`.trim();
              const photoRole = selectedPoi.role || (isEmergencyPoi ? 'emergency' : isClinicPoi ? 'clinic' : 'pharmacy');
              const gmapsPhotoApiUrl = selectedPoi.photo_url || `/v1/geo/places-photo?query=${encodeURIComponent(photoQuery)}&lat=${selectedPoi.lat || ''}&lng=${selectedPoi.lng || ''}&place_id=${selectedPoi.id || ''}&facility_type=${photoRole}&redirect=true`;

              return (
                <div className="med-place-detail-card" role="region" aria-label="Chi tiết địa điểm y tế">
                  {/* Hero Media Banner with Category Badge & Status Overlay */}
                  <div className="detail-card-hero-banner">
                    <img
                      src={gmapsPhotoApiUrl}
                      alt={selectedPoi.name}
                      className="hero-banner-image"
                      loading="lazy"
                      onError={(e) => {
                        if (e.currentTarget.src !== fallbackHeroImageSrc) {
                          e.currentTarget.src = fallbackHeroImageSrc;
                        }
                      }}
                    />
                    <div className="hero-banner-gradient-overlay" />
                    <div className="hero-top-bar">
                      <div className="hero-category-badge-group">
                        <span className={`detail-category-badge ${isEmergencyPoi ? 'emergency' : isClinicPoi ? 'clinic' : 'pharmacy'}`}>
                          {isEmergencyPoi ? (
                            <><Ambulance size={12} strokeWidth={2.4} /> CẤP CỨU 24/7</>
                          ) : isClinicPoi ? (
                            <><Stethoscope size={12} strokeWidth={2.4} /> PHÒNG KHÁM / Y TẾ</>
                          ) : (
                            <><Pill size={12} strokeWidth={2.4} /> NHÀ THUỐC GPP</>
                          )}
                        </span>
                        <span className="detail-status-pill open">
                          <span className="live-status-dot" />
                          {selectedPoi.operating_status?.label || 'Đang mở cửa'}
                        </span>
                      </div>
                      <button
                        type="button"
                        className="btn-close-detail-glass"
                        onClick={() => {
                          setSelectedPoi(null);
                          setActiveRoute(null);
                          setActiveStepIndex(0);
                          setIsNavigatingLive(false);
                          setIsFloatingPanelCollapsed(false);
                        }}
                        title="Đóng chi tiết"
                      >
                        <X size={15} />
                      </button>
                    </div>
                    <div className="hero-bottom-bar">
                      <span className="hero-dist-pill">
                        <Route size={12} />
                        {selectedPoi.distance_label || formatDistanceLabel(selectedPoi.distance_km)}
                      </span>
                      <span className="hero-gmaps-photo-tag" title="Hình ảnh từ Google Maps Places API">
                        <span className="gmaps-g-symbol">G</span>
                        <span>Google Maps Photos API</span>
                      </span>
                    </div>
                  </div>

                  {/* Body Content */}
                  <div className="detail-card-body-section">
                    <h3 className="detail-place-name">{selectedPoi.name}</h3>
                    <p className="detail-place-address">
                      <MapPin size={13} className="pin-addr-icon" />
                      <span>{selectedPoi.address}</span>
                    </p>

                    <div className="detail-rating-trust-row">
                      <button
                        type="button"
                        className="detail-google-stars-btn"
                        onClick={() => openGoogleReviewsPanel(selectedPoi)}
                        title="Xem đánh giá Google Maps thực tế"
                      >
                        ★ {selectedPoi.rating || 4.8} ({selectedPoi.user_rating_count || 186} đánh giá Google • Xem chi tiết →)
                      </button>
                      <span className="detail-trust-pill">
                        <ShieldCheck size={13} /> Tin cậy: <strong>{selectedPoi.trust_score || 94}/100</strong>
                      </span>
                    </div>

                    <div className="detail-specialty-box">
                      <div className="specialty-header">
                        <Sparkles size={11} className="specialty-sparkle" />
                        <span className="specialty-label">Chuyên môn & Dịch vụ:</span>
                      </div>
                      <p className="specialty-text">{selectedPoi.medical_note || buildMedicalCalloutNote(selectedPoi)}</p>
                    </div>

                    {/* 2-Tier Stacked Action Buttons */}
                    <div className="detail-actions-stacked">
                      <button
                        type="button"
                        className="btn-start-nav-hero"
                        onClick={() => startLiveNavigation(false)}
                      >
                        <Navigation size={15} />
                        <span>BẮT ĐẦU CHỈ ĐƯỜNG NGAY</span>
                      </button>
                      <div className="detail-secondary-actions-row">
                        {selectedPoi.phone ? (
                          <a href={`tel:${selectedPoi.phone}`} className="btn-secondary-action call">
                            <PhoneCall size={13} />
                            <span>Gọi ({selectedPoi.phone})</span>
                          </a>
                        ) : (
                          <a href="tel:115" className="btn-secondary-action call">
                            <PhoneCall size={13} />
                            <span>Gọi Cấp cứu 115</span>
                          </a>
                        )}
                        <a
                          href={googleMapsNavUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="btn-secondary-action gmaps"
                          title="Mở Google Maps App"
                        >
                          <ExternalLink size={13} />
                          <span>Google Maps App</span>
                        </a>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })()}

            {/* FLOATING COMPONENT 5: Google Maps Unified Control Dock (Bottom-Right) */}
            {mapViewMode !== 'gmaps_embed' && (
              <div className="google-nav-floating-dock" role="toolbar" aria-label="Điều khiển bản đồ">
                <button
                  type="button"
                  className="gnav-dock-btn"
                  onClick={handleZoomIn}
                  title="Phóng to bản đồ (+)"
                  aria-label="Phóng to"
                >
                  <Plus size={16} />
                </button>
                <button
                  type="button"
                  className="gnav-dock-btn"
                  onClick={handleZoomOut}
                  title="Thu nhỏ bản đồ (-)"
                  aria-label="Thu nhỏ"
                >
                  <Minus size={16} />
                </button>
                <div className="gnav-dock-divider" />
                <button
                  type="button"
                  className="gnav-dock-btn"
                  onClick={handleFitAllPois}
                  title="Xem toàn bộ bản đồ & tất cả các cơ sở xung quanh"
                  aria-label="Xem toàn bộ bản đồ"
                >
                  <Compass size={16} />
                </button>
                <button
                  type="button"
                  className="gnav-dock-btn"
                  onClick={handleRecenterGps}
                  title="Về vị trí hiện tại của bạn"
                  aria-label="Về vị trí hiện tại"
                >
                  <LocateFixed size={16} />
                </button>
                <div className="gnav-dock-divider" />
                <button
                  type="button"
                  className={`gnav-dock-btn ${isMapFullscreen ? 'active' : ''}`}
                  onClick={handleToggleFullscreen}
                  title={isMapFullscreen ? 'Thu nhỏ giao diện bản đồ' : 'Mở rộng bản đồ toàn màn hình'}
                  aria-label="Mở rộng toàn màn hình"
                >
                  {isMapFullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
                </button>
              </div>
            )}

            {/* Embedded Google Maps View */}
            {mapViewMode === 'gmaps_embed' && (
              <div className="gmaps-embed-stage">
                <iframe
                  title="Bản đồ chỉ đường Google Maps trực tiếp"
                  src={googleMapsEmbedUrl}
                  className="gmaps-iframe-el"
                  loading="lazy"
                  allowFullScreen
                />
                <div className="gmaps-embed-bar">
                  <div className="embed-bar-info">
                    <Navigation size={14} className="spin-subtle" />
                    <span>
                      Đang hiển thị chỉ đường Google Maps trực tiếp từ tọa độ GPS của bạn đến {selectedPoi?.name || 'điểm đến'}
                    </span>
                  </div>
                  <a
                    href={googleMapsNavUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="btn-launch-gmaps-gps"
                  >
                    <Navigation size={14} />
                    <span>Mở Dẫn Đường Google Maps App</span>
                    <ExternalLink size={12} />
                  </a>
                </div>
              </div>
            )}

            {/* Top HUD Card (Turn-by-Turn Banner) - Shown only when an active POI destination & route are present */}
            {selectedPoi && activeRoute && steps.length > 0 && mapViewMode !== 'gmaps_embed' && (
              <div className="nav-hud-top-card">
                <div className="hud-main-bar">
                  <div className="hud-maneuver-icon-box">
                    {getTurnDirectionIcon(currentStep.instruction)}
                  </div>
                  <div className="hud-instruction-box">
                    <div className="hud-dist-lead">
                      {formatDistanceToTurn(currentStep.distance_km, currentStep.distance_meters)}
                    </div>
                    <div className="hud-action-lead">
                      {currentStep.landmark && (
                        <span className="hud-landmark-pill">
                          📍 Mốc: {currentStep.landmark}
                        </span>
                      )}
                      {currentStep.is_first_mile && (
                        <span className="hud-first-mile-pill">
                          ⚡ Lối nội bộ {currentStep.distance_meters || 38}m
                        </span>
                      )}
                      {translateStepInstruction(
                        currentStep.instruction,
                        currentStep.road_name,
                        currentStep.landmark
                      )}
                    </div>
                    {currentStep.lane_guidance && (
                      <div className="hud-lane-pill">
                        🛣️ {currentStep.lane_guidance}
                      </div>
                    )}
                  </div>
                  <div className="hud-quick-actions">
                    {!isNavigatingLive ? (
                      <>
                        <button
                          type="button"
                          className="btn-hud-start-quick"
                          onClick={() => startLiveNavigation(false)}
                          title="Bắt đầu dẫn đường Turn-by-Turn"
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            background: 'linear-gradient(135deg, #059669 0%, #10b981 100%)',
                            border: 'none',
                            color: '#ffffff',
                            fontWeight: 700,
                            fontSize: '0.8rem',
                            padding: '6px 12px',
                            borderRadius: '8px',
                            cursor: 'pointer',
                            boxShadow: '0 2px 10px rgba(16, 185, 129, 0.4)',
                          }}
                        >
                          <Navigation size={13} />
                          <span>Bắt đầu</span>
                        </button>
                        <button
                          type="button"
                          className="btn-change-destination"
                          onClick={handleResetDestination}
                          title="Quay lại danh sách các cơ sở y tế khác"
                        >
                          <RotateCcw size={12} />
                          <span>Đổi địa điểm khác</span>
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          type="button"
                          className={`hud-icon-btn audio-${audioGuidanceMode}`}
                          onClick={handleCycleAudioGuidance}
                          title={
                            audioGuidanceMode === 'full'
                              ? 'Âm thanh đầy đủ'
                              : audioGuidanceMode === 'alerts_only'
                              ? 'Chỉ cảnh báo'
                              : 'Đã tắt tiếng'
                          }
                        >
                          {audioGuidanceMode === 'full' ? (
                            <Volume2 size={20} />
                          ) : audioGuidanceMode === 'alerts_only' ? (
                            <Volume1 size={20} />
                          ) : (
                            <VolumeX size={20} />
                          )}
                        </button>
                        <button
                          type="button"
                          className="hud-icon-btn"
                          onClick={() =>
                            speakVietnameseInstruction(
                              `${formatDistanceToTurn(currentStep.distance_km, currentStep.distance_meters)}, ${translateStepInstruction(currentStep.instruction, currentStep.road_name, currentStep.landmark)}`,
                              audioGuidanceMode,
                              false
                            )
                          }
                          title="Nghe lại chỉ dẫn"
                        >
                          <RotateCcw size={18} />
                        </button>
                      </>
                    )}
                  </div>
                </div>

                {nextStep && (
                  <div className="hud-next-step-strip">
                    <span className="next-kicker">Sau đó:</span>
                    <span className="next-text">
                      {nextStep.landmark && (
                        <span className="hud-landmark-pill" style={{ fontSize: '0.68rem', padding: '1px 5px' }}>
                          Mốc: {nextStep.landmark}
                        </span>
                      )}
                      {translateStepInstruction(
                        nextStep.instruction,
                        nextStep.road_name,
                        nextStep.landmark
                      )}
                    </span>
                  </div>
                )}

                {activeRoute?.comparison?.advantageMessage && (
                  <div className="hud-gmaps-comparison-strip">
                    <span className="gmaps-label">
                      <Zap size={13} /> So sánh Google Maps
                    </span>
                    <span className="gmaps-savings">
                      {activeRoute.comparison.advantageMessage}
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Live Cockpit Bottom Bar (ETA & Navigation Controls) */}
            {isNavigatingLive && mapViewMode !== 'gmaps_embed' && (
              <div className="nav-hud-bottom-bar">
                <div className="cockpit-eta-cell">
                  <span className="eta-time-val">
                    {getEstimatedArrivalTime(activeRoute?.eta_minutes)}
                  </span>
                  <span className="eta-label">Giờ đến dự kiến</span>
                </div>
                <div className="cockpit-summary-cell">
                  <span className="cockpit-duration-val">
                    ~{activeRoute?.eta_minutes || 2} phút
                  </span>
                  <span className="cockpit-dist-val">
                    {activeRoute?.distance_km || 0.98} km •{' '}
                    {mapViewMode === '3d_cockpit' ? 'Góc nhìn 3D Buồng Lái' : 'Góc nhìn 2D Toàn Cảnh'}
                  </span>
                </div>
                <div className="cockpit-buttons-cell">
                  <button
                    type="button"
                    className="btn-cockpit-next"
                    onClick={() => {
                      if (activeStepIndex < steps.length - 1) {
                        const nextIdx = activeStepIndex + 1;
                        setActiveStepIndex(nextIdx);
                        const s = steps[nextIdx];
                        if (s && voiceGuidanceEnabled) {
                          speakVietnameseInstruction(
                            `${formatDistanceToTurn(s.distance_km, s.distance_meters)}, ${translateStepInstruction(s.instruction, s.road_name, s.landmark)}`,
                            audioGuidanceMode,
                            false
                          );
                        }
                      }
                    }}
                    title="Chuyển sang bước dẫn đường tiếp theo"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '5px',
                      background: 'rgba(255, 255, 255, 0.12)',
                      border: '1px solid rgba(255, 255, 255, 0.3)',
                      color: '#ffffff',
                      padding: '8px 12px',
                      borderRadius: '8px',
                      fontSize: '0.82rem',
                      fontWeight: 700,
                      cursor: 'pointer',
                    }}
                  >
                    <ArrowRight size={14} />
                    <span>Bước tiếp</span>
                  </button>
                  <button
                    type="button"
                    className={`btn-cockpit-sim ${isSimulatingDrive ? 'simulating' : ''}`}
                    onClick={toggleSimulateDriving}
                    title="Mô phỏng xe chạy theo từng khúc rẽ"
                  >
                    {isSimulatingDrive ? <Pause size={15} /> : <Play size={15} />}
                    <span>{isSimulatingDrive ? 'Tạm dừng xe' : 'Mô phỏng xe chạy'}</span>
                  </button>
                  <button
                    type="button"
                    className="btn-cockpit-stop"
                    onClick={stopLiveNavigation}
                    title="Dừng dẫn đường"
                  >
                    <X size={17} />
                    <span>Dừng</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Sliding POI Cards Drawer (Visible only when toggled) */}
        {showPoiDrawer && (
          <aside className="nav-sidebar-console slide-drawer">
            <div className="drawer-header-row">
              <div className="drawer-title-group">
                <Layers size={16} className="text-cyan" />
                <strong>Danh sách {pois.length} cơ sở y tế quanh bạn</strong>
              </div>
              <button
                type="button"
                className="btn-close-drawer"
                onClick={() => setShowPoiDrawer(false)}
                title="Đóng bảng danh sách"
              >
                <X size={16} />
              </button>
            </div>

            {/* Turn-by-Turn Navigation Stepper (When route is active) */}
            {steps.length > 0 && (
              <div className="nav-turn-stepper-box">
                <div className="stepper-header">
                  <div className="stepper-title-row">
                    <Compass size={16} className="compass-icon pulse-subtle" />
                    <strong>CHỈ DẪN TỪNG CHẶNG RẼ</strong>
                  </div>
                  <div className="stepper-actions-header">
                    <button
                      type="button"
                      className="btn-stepper-tts-speak"
                      onClick={() =>
                        speakVietnameseInstruction(
                          `${formatDistanceToTurn(currentStep.distance_km, currentStep.distance_meters)}, ${translateStepInstruction(currentStep.instruction, currentStep.road_name, currentStep.landmark)}`,
                          true
                        )
                      }
                      title="Phát giọng nói chặng hiện tại"
                    >
                      <Volume2 size={13} />
                      <span>Đọc</span>
                    </button>
                    <span className="step-count-pill">
                      Chặng {activeStepIndex + 1}/{steps.length}
                    </span>
                  </div>
                </div>

                <div className="active-turn-banner">
                  <div className="turn-direction-icon-box">
                    {getTurnDirectionIcon(currentStep.instruction)}
                  </div>
                  <div className="turn-instruction-info">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap', marginBottom: '4px' }}>
                      <span className="road-highlight">
                        {currentStep.road_name || 'Đoạn đường di chuyển'}
                      </span>
                      {currentStep.landmark && (
                        <span className="hud-landmark-pill" style={{ fontSize: '0.7rem' }}>
                          📍 Mốc: {currentStep.landmark}
                        </span>
                      )}
                      {currentStep.is_first_mile && (
                        <span className="hud-first-mile-pill" style={{ fontSize: '0.7rem' }}>
                          ⚡ Lối nội bộ
                        </span>
                      )}
                    </div>
                    <h4 className="instruction-heading">
                      {translateStepInstruction(
                        currentStep.instruction,
                        currentStep.road_name,
                        currentStep.landmark
                      )}
                    </h4>
                    {currentStep.lane_guidance && (
                      <div className="hud-lane-pill" style={{ marginBottom: '6px' }}>
                        🛣️ {currentStep.lane_guidance}
                      </div>
                    )}
                    <div className="turn-metrics">
                      <span className="metric-tag">
                        <Route size={12} /> {formatDistanceToTurn(currentStep.distance_km, currentStep.distance_meters)}
                      </span>
                      <span className="metric-tag">
                        <Clock size={12} /> ~
                        {Math.max(1, Math.round((currentStep.distance_meters ? currentStep.distance_meters / 400 : currentStep.distance_km * 2.5)))} phút
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* List of Nearby POIs */}
            <div className="nav-poi-list-section">
              <div className="poi-cards-scroll">
                {loadingPois ? (
                  <div className="poi-loading-skeleton">
                    <RefreshCw size={20} className="spin" />
                    <span>Đang quét các trạm y tế quanh bạn...</span>
                  </div>
                ) : pois.length === 0 ? (
                  <div className="poi-empty">
                    <span>Không tìm thấy địa điểm phù hợp tại khu vực này.</span>
                  </div>
                ) : (
                  pois.map((poi) => {
                    const isSelected = selectedPoi?.id === poi.id;
                    const isEmerg = poi.type === 'hospital_emergency';
                    const isClinic = poi.category_badge?.includes('PHÒNG KHÁM');
                    const candidate = {
                      id: poi.id,
                      name: poi.name,
                      facilityType: isEmerg ? 'emergency_hospital' : 'pharmacy',
                      distanceKm: poi.distance_km || 0.5,
                      etaMinutes: Math.round((poi.distance_km || 0.5) * 3),
                      lat: poi.lat,
                      lng: poi.lng,
                      emergencyGateName: poi.emergency_gate_name,
                      hospitalTier: poi.hospital_tier || (isEmerg ? 'TIER_1' : 'GPP_CHAIN'),
                      capabilities: poi.capabilities_or_services || [],
                      gppVerified: !isEmerg,
                      reputation: {
                        placeId: poi.id,
                        rating: poi.rating || (isEmerg ? 4.8 : 4.7),
                        userRatingCount: poi.user_rating_count || 1420,
                        openNow: Boolean(poi.operating_status?.is_open),
                        is24Hours: poi.operating_status?.status_badge === 'OPEN_24_7',
                        verifiedPhone: poi.phone,
                        googleMapsUri: poi.google_maps_turn_by_turn_url || '',
                        topReviews: poi.reviews || [],
                      },
                    };
                    const trustInfo = computeMedicalTrustScore(candidate);

                    return (
                      <div
                        key={poi.id}
                        className={`poi-card-item ${isSelected ? 'selected' : ''}`}
                        onClick={() => setSelectedPoi(poi)}
                      >
                        <div className="poi-card-top">
                          <div className="poi-name-col">
                            <strong>{poi.name}</strong>
                            <p className="poi-address-text">{poi.address}</p>
                            <div className="poi-reputation-row">
                              <button
                                type="button"
                                className="poi-google-rating"
                                onClick={(ev) => {
                                  ev.stopPropagation();
                                  openGoogleReviewsPanel(poi);
                                }}
                                title="Bấm để xem toàn bộ đánh giá Google Maps"
                              >
                                ★ {poi.rating || (isEmerg ? 4.8 : 4.7)} ({poi.user_rating_count || 186} đánh giá Google · Xem)
                              </button>
                              <span className="poi-trust-score-badge">
                                Tin cậy: {trustInfo.trustScore100}/100
                              </span>
                            </div>
                          </div>
                          <div className="poi-dist-badge">
                            <span className="dist-num">{poi.distance_km}</span>
                            <span className="dist-unit">km</span>
                          </div>
                        </div>

                        {poi.reviews && poi.reviews.length > 0 && (
                          <div
                            className="poi-reviews-preview"
                            onClick={(ev) => {
                              ev.stopPropagation();
                              openGoogleReviewsPanel(poi);
                            }}
                          >
                            <p className="review-quote">
                              &ldquo;{poi.reviews[0].text}&rdquo; <span style={{ color: '#38bdf8', fontWeight: 600 }}>Xem thêm →</span>
                            </p>
                          </div>
                        )}

                        <div className="poi-card-bottom">
                          <span className="poi-status-tag open">
                            {poi.operating_status?.label || 'Đang mở cửa'}
                          </span>
                          {poi.phone && (
                            <a
                              href={`tel:${poi.phone}`}
                              className="poi-phone-link"
                              onClick={(e) => e.stopPropagation()}
                              title={`Gọi điện thoại đến ${poi.name}`}
                            >
                              <PhoneCall size={12} />
                              <span>{poi.phone}</span>
                            </a>
                          )}
                          <span className="select-hint">
                            {isSelected ? 'Đang chọn' : 'Bấm để xem'}
                          </span>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </aside>
        )}
      </div>

      {/* State 3: Google Reviews Redesigned Panel */}
      {activeReviewPoi && (
        <GoogleReviewsPanel
          poi={activeReviewPoi}
          onClose={closeGoogleReviewsPanel}
          onSelectAndNavigate={(poi) => {
            setSelectedPoi(poi);
            startDestinationNavigation(poi);
          }}
        />
      )}
    </div>
  );
}


