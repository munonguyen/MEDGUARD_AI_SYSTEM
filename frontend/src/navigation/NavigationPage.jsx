import React, { useState, useEffect, useRef, useCallback } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import * as turf from '@turf/turf';
import {
  AlertTriangle,
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
} from 'lucide-react';
import {
  getSavedUserLocation,
  saveUserLocation,
  requestBrowserGeolocation,
  autoDetectLiveLocation,
  watchLiveUserLocation,
  LOCATION_PRESETS,
} from '../locationState';
import './NavigationPage.css';

const GEOAPIFY_API_KEY = '224447c8da3b4555a5380f31ddb56bf3';

// High-speed, guaranteed-uptime raster styles (Sub-50ms loading, never black, WebKit/Safari compatible)
const STREETS_RASTER_STYLE = {
  version: 8,
  sources: {
    'streets-tiles': {
      type: 'raster',
      tiles: [
        `https://maps.geoapify.com/v1/tile/osm-bright/{z}/{x}/{y}.png?apiKey=${GEOAPIFY_API_KEY}`,
      ],
      tileSize: 256,
      attribution: '© Geoapify, OpenStreetMap contributors',
      maxzoom: 20,
    },
  },
  layers: [
    {
      id: 'streets-base',
      type: 'raster',
      source: 'streets-tiles',
      minzoom: 0,
      maxzoom: 22,
    },
  ],
};

const SATELLITE_RASTER_STYLE = {
  version: 8,
  sources: {
    'esri-satellite': {
      type: 'raster',
      tiles: [
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      ],
      tileSize: 256,
      attribution: 'Esri World Imagery',
      maxzoom: 19,
    },
  },
  layers: [
    {
      id: 'satellite-base',
      type: 'raster',
      source: 'esri-satellite',
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
        `https://maps.geoapify.com/v1/tile/dark-matter-dark-grey/{z}/{x}/{y}.png?apiKey=${GEOAPIFY_API_KEY}`,
      ],
      tileSize: 256,
      attribution: '© Geoapify, OpenStreetMap contributors',
      maxzoom: 20,
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
  const distKm = Math.max(0.1, Number((rawDistKm * 1.25).toFixed(2)));
  const speedKmh = mode === 'walk' ? 4.5 : mode === 'drive' ? 35 : 28;
  const etaMinutes = Math.max(1, Math.round((distKm / speedKmh) * 60));

  const coordinates = [];
  const count = 8;
  for (let i = 0; i <= count; i++) {
    const fraction = i / count;
    const lat = startLat + (destLat - startLat) * fraction;
    const lng = startLng + (destLng - startLng) * fraction;
    coordinates.push([Number(lat.toFixed(6)), Number(lng.toFixed(6))]);
  }

  const steps = [
    {
      step_number: 1,
      instruction: `Bắt đầu xuất phát từ vị trí hiện tại của bạn hướng về phía ${destName}.`,
      distance_km: Number((distKm * 0.25).toFixed(2)),
      time_seconds: Math.round(etaMinutes * 60 * 0.25),
      road_name: 'Tuyến đường xuất phát',
    },
    {
      step_number: 2,
      instruction: `Đi thẳng theo trục đường chính hướng về ${destName}.`,
      distance_km: Number((distKm * 0.55).toFixed(2)),
      time_seconds: Math.round(etaMinutes * 60 * 0.55),
      road_name: 'Trục đường liên thông',
    },
    {
      step_number: 3,
      instruction: `Điểm đến (${destName}) nằm ở ngay phía trước mặt bạn.`,
      distance_km: Number((distKm * 0.2).toFixed(2)),
      time_seconds: Math.round(etaMinutes * 60 * 0.2),
      road_name: destName,
    },
  ];

  return {
    distance_km: distKm,
    eta_minutes: etaMinutes,
    mode,
    coordinates,
    steps,
  };
}

/**
 * Safely update or initialize 3D route line in MapLibre WebGL
 */
export function update3dRouteLine(map3d, coordinates) {
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
        if (!map3d.getLayer('route-glow')) {
          map3d.addLayer({
            id: 'route-glow',
            type: 'line',
            source: 'route-source',
            layout: { 'line-join': 'round', 'line-cap': 'round' },
            paint: {
              'line-color': '#00e5ff',
              'line-width': 12,
              'line-opacity': 0.55,
            },
          });
        }
        if (!map3d.getLayer('route-line')) {
          map3d.addLayer({
            id: 'route-line',
            type: 'line',
            source: 'route-source',
            layout: { 'line-join': 'round', 'line-cap': 'round' },
            paint: {
              'line-color': '#2563eb',
              'line-width': 6,
              'line-opacity': 0.95,
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

export function translateStepInstruction(instruction = '', roadName = '') {
  if (!instruction) return 'Đi thẳng theo hướng dẫn';
  let text = instruction.trim();

  if (
    text.includes('Đi thẳng') ||
    text.includes('Rẽ phải') ||
    text.includes('Rẽ trái') ||
    text.includes('Đi chếch') ||
    text.includes('Đi theo') ||
    text.includes('vòng xuyến') ||
    text.includes('đích') ||
    text.includes('Quay đầu')
  ) {
    return text;
  }

  const dirMap = {
    northeast: 'Đông Bắc',
    northwest: 'Tây Bắc',
    southeast: 'Đông Nam',
    southwest: 'Tây Nam',
    north: 'Bắc',
    south: 'Nam',
    east: 'Đông',
    west: 'Tây',
  };

  if (/you have arrived|destination is on the/i.test(text)) {
    return 'Bạn đã đến điểm đích đến.';
  }

  const driveMatch = text.match(
    /^drive\s+(north|south|east|west|northeast|northwest|southeast|southwest)(?:\s+on\s+(.*))?/i
  );
  if (driveMatch) {
    const dir = dirMap[driveMatch[1].toLowerCase()] || driveMatch[1];
    const road = driveMatch[2] || roadName;
    if (road) {
      return `Đi thẳng về hướng ${dir} trên ${road}`;
    }
    return `Đi thẳng về hướng ${dir}`;
  }

  const turnMatch = text.match(/^turn\s+(left|right)(?:\s+onto\s+(.*))?/i);
  if (turnMatch) {
    const side = turnMatch[1].toLowerCase() === 'left' ? 'trái' : 'phải';
    const road = turnMatch[2] || roadName;
    if (road) {
      return `Rẽ ${side} vào ${road}`;
    }
    return `Rẽ ${side}`;
  }

  const keepMatch = text.match(/^(?:keep|slight)\s+(left|right)(?:\s+onto\s+(.*))?/i);
  if (keepMatch) {
    const side = keepMatch[1].toLowerCase() === 'left' ? 'bên trái' : 'bên phải';
    const road = keepMatch[2] || roadName;
    if (road) {
      return `Đi chếch ${side} vào ${road}`;
    }
    return `Đi chếch ${side}`;
  }

  const roundMatch = text.match(/roundabout.*?take the (\d+)[a-z]* exit(?:\s+onto\s+(.*))?/i);
  if (roundMatch) {
    const exitNum = roundMatch[1];
    const road = roundMatch[2] || roadName;
    if (road) {
      return `Tại vòng xuyến, đi theo lối ra thứ ${exitNum} vào ${road}`;
    }
    return `Tại vòng xuyến, đi theo lối ra thứ ${exitNum}`;
  }

  if (/make a u-turn/i.test(text)) {
    return 'Quay đầu xe hình chữ U';
  }

  const contMatch = text.match(/^continue(?:\s+onto\s+(.*))?/i);
  if (contMatch) {
    const road = contMatch[1] || roadName;
    if (road) {
      return `Tiếp tục đi thẳng trên ${road}`;
    }
    return 'Tiếp tục đi thẳng';
  }

  return roadName ? `Đi trên ${roadName}` : text;
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

function formatDistanceToTurn(distanceKm) {
  if (typeof distanceKm !== 'number' || isNaN(distanceKm)) return 'Sau 100 m';
  if (distanceKm < 1) {
    const meters = Math.max(20, Math.round(distanceKm * 1000));
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
  const [permissionPromptOpen, setPermissionPromptOpen] = useState(
    () => !getSavedUserLocation().is_gps && !navigationContext?.userLocation
  );
  const [mapTheme, setMapTheme] = useState('streets'); // 'streets', 'satellite', 'dark', 'osm'
  const [activeStepIndex, setActiveStepIndex] = useState(0);
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

  // Hybrid Mode: '3d_cockpit' (MapLibre GL JS) | '2d_overview' (Leaflet HD) | 'gmaps_embed'
  const [mapViewMode, setMapViewMode] = useState('3d_cockpit');
  const [isNavigatingLive, setIsNavigatingLive] = useState(false);
  const [isSimulatingDrive, setIsSimulatingDrive] = useState(false);
  const [vehiclePosition, setVehiclePosition] = useState(null);
  const [vehicleHeading, setVehicleHeading] = useState(0);
  const [rerouteAlert, setRerouteAlert] = useState(false);

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
          '🎙️ Đang lắng nghe giọng nói tiếng Việt... Hãy nói: "Cây xăng gần đây", "Quán cơm", "Quận 12", hoặc tên bệnh viện.'
        );
      };

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        setIsListeningVoice(false);
        setSearchQuery(transcript);
        onNotify?.(`🗣️ Đã nhận diện giọng nói: "${transcript}"`);
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
      onNotify?.('⛽ Đang tìm trạm xăng / cây xăng gần nhất...');
      return;
    }
    if (q.includes('cà phê') || q.includes('cafe') || q.includes('uống')) {
      setPoiType('cafe');
      setQuickAmenity('cafe');
      onNotify?.('☕ Đang tìm quán cà phê / trạm nghỉ gần nhất...');
      return;
    }
    if (q.includes('cơm') || q.includes('ăn') || q.includes('quán ăn') || q.includes('gà')) {
      setPoiType('restaurant');
      setQuickAmenity('restaurant');
      onNotify?.('🍱 Đang tìm quán ăn / quán cơm gần nhất...');
      return;
    }
    if (q.includes('cấp cứu') || q.includes('bệnh viện') || q.includes('115')) {
      setPoiType('emergency');
      setQuickAmenity('emergency');
      onNotify?.('🏥 Đang tìm trung tâm cấp cứu 115 & bệnh viện...');
      return;
    }
    if (q.includes('thuốc') || q.includes('nhà thuốc') || q.includes('gpp')) {
      setPoiType('pharmacy');
      setQuickAmenity('pharmacy');
      onNotify?.('💊 Đang tìm quầy thuốc GPP chuẩn gần nhất...');
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
      onNotify?.(`📍 Đã chọn điểm đến: ${matched.name}`);
    } else {
      onNotify?.(`🔍 Đang lọc theo từ khóa "${q}"...`);
    }
  };

  const handleCycleAudioGuidance = () => {
    setAudioGuidanceMode((curr) => {
      if (curr === 'full') {
        onNotify?.('⚠️ Chế độ giọng nói: Chỉ phát cảnh báo quan trọng');
        return 'alerts_only';
      }
      if (curr === 'alerts_only') {
        onNotify?.('🔇 Chế độ giọng nói: Đã tắt tiếng hoàn toàn');
        return 'muted';
      }
      onNotify?.('🔊 Chế độ giọng nói: Bật âm thanh hướng dẫn đầy đủ');
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
      onNotify?.('🎯 Đã đưa góc nhìn camera về vị trí GPS của bạn');
    } else if (mapViewMode === '2d_overview' && map2dInstanceRef.current) {
      map2dInstanceRef.current.flyTo([userLocation.lat, userLocation.lng], 16, {
        animate: true,
        duration: 1.0,
      });
      onNotify?.('🎯 Đã đưa góc nhìn camera về vị trí GPS của bạn');
    }
  };

  const handleResetCompass = () => {
    if (mapViewMode === '3d_cockpit' && map3dInstanceRef.current) {
      map3dInstanceRef.current.rotateTo(0, { duration: 600 });
      setVehicleHeading(0);
      onNotify?.('🧭 Đã căn chỉnh la bàn hướng thẳng về phía Bắc (0°)');
    }
  };

  // Sync userLocation if prop changes
  useEffect(() => {
    if (propUserLocation && !navigationContext?.userLocation) {
      setUserLocation(propUserLocation);
    }
  }, [propUserLocation, navigationContext]);

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
          setActiveRoute(res);
          setActiveStepIndex(0);
          onNotify?.(`🔄 Đã tự động định tuyến lại (lệch ${offMeters}m)`);
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

  // Auto-detect real user location on mount (GPS or IP network)
  useEffect(() => {
    if (navigationContext?.userLocation) return;
    let isMounted = true;
    autoDetectLiveLocation()
      .then((loc) => {
        if (isMounted && loc && typeof loc.lat === 'number') {
          setUserLocation(loc);
          if (loc.is_gps) {
            setPermissionPromptOpen(false);
          }
        }
      })
      .catch((e) => console.log('Auto location detection:', e));
    return () => {
      isMounted = false;
    };
  }, [navigationContext]);

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
  const lastPoiFetchCoordsRef = useRef(null);
  const lastPoiTypeRef = useRef(poiType);

  useEffect(() => {
    let isCancelled = false;
    const shouldFetch =
      !lastPoiFetchCoordsRef.current ||
      lastPoiTypeRef.current !== poiType ||
      Math.abs(lastPoiFetchCoordsRef.current.lat - userLocation.lat) > 0.005 ||
      Math.abs(lastPoiFetchCoordsRef.current.lng - userLocation.lng) > 0.005;

    if (!shouldFetch && pois.length > 0) return;

    lastPoiFetchCoordsRef.current = { lat: userLocation.lat, lng: userLocation.lng };
    lastPoiTypeRef.current = poiType;

    const fetchPois = async () => {
      setLoadingPois(true);
      try {
        const res = await api.request(
          `/v1/geo/pois?poi_type=${poiType}&city=${userLocation.city || 'hanoi'}&lat=${userLocation.lat}&lng=${userLocation.lng}`
        );
        if (!isCancelled && res?.pois && res.pois.length > 0) {
          const currentTargetPoi = navigationContext?.selectedPoi || selectedPoi;
          if (currentTargetPoi) {
            const isSame = (p) =>
              p.id === currentTargetPoi.id ||
              (p.name &&
                currentTargetPoi.name &&
                p.name.toLowerCase() === currentTargetPoi.name.toLowerCase());
            const others = res.pois.filter((p) => !isSame(p));
            const pinnedPoi = {
              ...currentTargetPoi,
              isRecommendedFromChat: Boolean(navigationContext?.fromChat),
            };
            setPois([pinnedPoi, ...others]);
            setSelectedPoi(pinnedPoi);
          } else {
            setPois(res.pois);
            setSelectedPoi(res.pois[0]);
          }
        } else if (!isCancelled) {
          const fallbackRes = await api.request(
            `/v1/geo/pois?poi_type=${poiType}&city=${userLocation.city || 'hanoi'}`
          );
          if (fallbackRes?.pois && fallbackRes.pois.length > 0) {
            const currentTargetPoi = navigationContext?.selectedPoi || selectedPoi;
            if (currentTargetPoi) {
              const isSame = (p) =>
                p.id === currentTargetPoi.id ||
                (p.name &&
                  currentTargetPoi.name &&
                  p.name.toLowerCase() === currentTargetPoi.name.toLowerCase());
              const others = fallbackRes.pois.filter((p) => !isSame(p));
              const pinnedPoi = {
                ...currentTargetPoi,
                isRecommendedFromChat: Boolean(navigationContext?.fromChat),
              };
              setPois([pinnedPoi, ...others]);
              setSelectedPoi(pinnedPoi);
            } else {
              setPois(fallbackRes.pois);
              setSelectedPoi(fallbackRes.pois[0]);
            }
          }
        }
      } catch (err) {
        console.warn('Failed to load POIs:', err);
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
          setActiveRoute(res);
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
        pitch: 60, // 3D Camera tilt
        bearing: vehicleHeading || 0,
        attributionControl: false,
      });

      map3d.on('load', () => {
        map3dInitializedRef.current = true;
        map3d.resize();
        update3dRouteLine(map3d, routeCoords);
      });

      map3d.on('error', (e) => {
        console.warn('MapLibre GL warning:', e);
      });

      map3dInstanceRef.current = map3d;
    }
  }, []);

  // Update 3D route line whenever routeCoords changes
  useEffect(() => {
    const map3d = map3dInstanceRef.current;
    if (map3d && routeCoords.length >= 2) {
      update3dRouteLine(map3d, routeCoords);
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
  }, [routeCoords, isNavigatingLive]);

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
        update3dRouteLine(map3d, routeCoords);
      };
      map3d.once('style.load', onReload);
    } catch (e) {
      console.warn('Map3d setStyle error:', e);
    }
  }, [mapTheme, routeCoords]);

  // MapLibre 3D Markers (A, B and Vehicle Marker)
  useEffect(() => {
    const map3d = map3dInstanceRef.current;
    if (!map3d) return;

    // Clear old pin markers
    pinMarkers3dRef.current.forEach((m) => m.remove());
    pinMarkers3dRef.current = [];

    // Marker A (Origin)
    const elA = document.createElement('div');
    elA.className = 'nav-map-pin-wrap';
    elA.innerHTML = `<div class="nav-marker-pin pin-a"><span class="pin-letter">A</span><span class="pin-tag">Vị trí của bạn</span></div>`;
    const markerA = new maplibregl.Marker({ element: elA, anchor: 'bottom' })
      .setLngLat([userLocation.lng, userLocation.lat])
      .addTo(map3d);
    pinMarkers3dRef.current.push(markerA);

    // Marker B (Destination)
    if (selectedPoi) {
      const isEmerg = selectedPoi.type === 'hospital_emergency';
      const elB = document.createElement('div');
      elB.className = 'nav-map-pin-wrap';
      elB.innerHTML = `<div class="nav-marker-pin ${isEmerg ? 'pin-emerg' : 'pin-b'}"><span class="pin-letter">B</span><span class="pin-tag">${isEmerg ? 'Cấp cứu' : 'Quầy thuốc'}</span></div>`;
      const markerB = new maplibregl.Marker({ element: elB, anchor: 'bottom' })
        .setLngLat([selectedPoi.lng, selectedPoi.lat])
        .addTo(map3d);
      pinMarkers3dRef.current.push(markerB);
    }
  }, [userLocation, selectedPoi]);

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

    // Camera chase in 3D Cockpit mode
    if (mapViewMode === '3d_cockpit' && isNavigatingLive) {
      map3d.easeTo({
        center: [vLng, vLat],
        bearing: vehicleHeading || 0,
        pitch: 60,
        zoom: 17.5,
        duration: 700,
        easing: (t) => t,
      });
    }
  }, [vehiclePosition, vehicleHeading, mapViewMode, isNavigatingLive]);

  // Resize handler on perspective mode toggle
  useEffect(() => {
    if (mapViewMode === '3d_cockpit' && map3dInstanceRef.current) {
      requestAnimationFrame(() => {
        map3dInstanceRef.current?.resize();
      });
    } else if (mapViewMode === '2d_overview' && map2dInstanceRef.current) {
      requestAnimationFrame(() => {
        map2dInstanceRef.current?.invalidateSize();
      });
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

    const brightTileUrl = `https://maps.geoapify.com/v1/tile/osm-bright/{z}/{x}/{y}.png?apiKey=${GEOAPIFY_API_KEY}`;
    const darkTileUrl = `https://maps.geoapify.com/v1/tile/dark-matter-dark-grey/{z}/{x}/{y}.png?apiKey=${GEOAPIFY_API_KEY}`;
    const osmTileUrl = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
    const satelliteTileUrl =
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';

    const tileUrl =
      mapTheme === 'satellite'
        ? satelliteTileUrl
        : mapTheme === 'dark'
        ? darkTileUrl
        : mapTheme === 'osm'
        ? osmTileUrl
        : brightTileUrl;

    L.tileLayer(tileUrl, {
      maxZoom: 20,
      attribution: '© OpenStreetMap, © Geoapify, Esri World Imagery',
    }).addTo(map);
  }, [mapTheme]);

  // Leaflet 2D Markers and Polyline
  useEffect(() => {
    const map = map2dInstanceRef.current;
    if (!map || !markersGroup2dRef.current || !polylineGroup2dRef.current) return;

    markersGroup2dRef.current.clearLayers();
    polylineGroup2dRef.current.clearLayers();

    const startCoords = [userLocation.lat, userLocation.lng];
    const startIcon = L.divIcon({
      className: 'nav-map-pin-wrap',
      html: `<div class="nav-marker-pin pin-a"><span class="pin-letter">A</span><span class="pin-tag">Vị trí của bạn</span></div>`,
      iconSize: [40, 48],
      iconAnchor: [20, 42],
    });
    const startMarker = L.marker(startCoords, { icon: startIcon }).addTo(markersGroup2dRef.current);
    startMarker.bindPopup(`<b>Điểm xuất phát:</b><br/>${userLocation.name}`);

    if (selectedPoi) {
      const destCoords = [selectedPoi.lat, selectedPoi.lng];
      const isEmerg = selectedPoi.type === 'hospital_emergency';
      const destIcon = L.divIcon({
        className: 'nav-map-pin-wrap',
        html: `<div class="nav-marker-pin ${isEmerg ? 'pin-emerg' : 'pin-b'}"><span class="pin-letter">B</span><span class="pin-tag">${isEmerg ? 'Cấp cứu' : 'Quầy thuốc'}</span></div>`,
        iconSize: [40, 48],
        iconAnchor: [20, 42],
      });
      const destMarker = L.marker(destCoords, { icon: destIcon }).addTo(markersGroup2dRef.current);
      destMarker.bindPopup(`<b>${selectedPoi.name}</b><br/>${selectedPoi.address}`);

      if (routeCoords.length > 0) {
        L.polyline(routeCoords, {
          color: mapTheme === 'dark' ? '#00e5ff' : '#60a5fa',
          weight: 10,
          opacity: 0.45,
          lineCap: 'round',
        }).addTo(polylineGroup2dRef.current);

        const mainLine = L.polyline(routeCoords, {
          color: mapTheme === 'dark' ? '#00e5ff' : '#2563eb',
          weight: 6,
          opacity: 0.95,
          lineCap: 'round',
          lineJoin: 'round',
        }).addTo(polylineGroup2dRef.current);

        if (!isNavigatingLive && mapViewMode === '2d_overview') {
          try {
            const group = L.featureGroup([startMarker, destMarker, mainLine]);
            map.fitBounds(group.getBounds(), { padding: [45, 45] });
          } catch {}
        }
      }
    } else {
      map.setView(startCoords, 15);
    }
  }, [userLocation, selectedPoi, activeRoute, mapTheme, isNavigatingLive, mapViewMode, routeCoords]);

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

  const steps = activeRoute?.steps || [];
  const currentStep = steps[activeStepIndex] || steps[0] || {};
  const nextStep = steps[activeStepIndex + 1] || null;

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
        onNotify?.(`🏁 Đã hoàn thành lộ trình đến ${selectedPoi?.name || 'điểm đến'}`);
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
                `${formatDistanceToTurn(nextStepObj.distance_km)}, ${translateStepInstruction(nextStepObj.instruction, nextStepObj.road_name)}`,
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

  // Start Live Turn-by-Turn Navigation
  const startLiveNavigation = (simulate = false) => {
    setIsNavigatingLive(true);
    setActiveStepIndex(0);
    const startPoint = routeCoords[0] || [userLocation.lat, userLocation.lng];
    const initialProcessed = processNavigationPosition(startPoint[0], startPoint[1], routeCoords);

    setVehiclePosition([initialProcessed.snappedLat, initialProcessed.snappedLng]);
    setVehicleHeading(initialProcessed.heading);

    if (mapViewMode === '3d_cockpit' && map3dInstanceRef.current) {
      map3dInstanceRef.current.easeTo({
        center: [initialProcessed.snappedLng, initialProcessed.snappedLat],
        bearing: initialProcessed.heading,
        pitch: 60,
        zoom: 17.5,
        duration: 800,
      });
    }

    const initialInstruction = steps[0]
      ? `${formatDistanceToTurn(steps[0].distance_km)}, ${translateStepInstruction(steps[0].instruction, steps[0].road_name)}`
      : `Bắt đầu dẫn đường đến ${selectedPoi?.name || 'điểm đến'}`;
    speakVietnameseInstruction(
      `Bắt đầu điều hướng đến ${selectedPoi?.name || 'điểm đến'}. ${initialInstruction}`,
      voiceGuidanceEnabled
    );

    if (simulate) {
      setIsSimulatingDrive(true);
    }
    onNotify?.(`🟢 Đã kích hoạt Chế độ Dẫn Đường 3D & 2D Kết Hợp (Turf.js GPS Engine)`);
  };

  // Stop Live Navigation
  const stopLiveNavigation = () => {
    setIsNavigatingLive(false);
    setIsSimulatingDrive(false);
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
        `${formatDistanceToTurn(step.distance_km)}, ${translateStepInstruction(step.instruction, step.road_name)}`,
        true
      );
    }
  };

  const handleRequestGps = async () => {
    setRequestingGps(true);
    try {
      const loc = await requestBrowserGeolocation();
      setUserLocation(loc);
      setPermissionPromptOpen(false);
      onNotify?.(`Đã xác định vị trí GPS thực tế: ${loc.address}`);
    } catch (err) {
      onNotify?.(err.message || 'Không thể lấy GPS. Vui lòng bật cấp quyền vị trí trên trình duyệt.');
    } finally {
      setRequestingGps(false);
    }
  };

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
    <div className="navigation-workspace-page">
      {/* Geolocation Permission Modal/Banner if not GPS verified */}
      {permissionPromptOpen && (
        <div className="nav-permission-overlay" role="dialog" aria-modal="true">
          <div className="nav-permission-modal">
            <div className="modal-icon-badge">
              <LocateFixed size={28} />
            </div>
            <h3>Xác định Vị trí Hiện tại để Điều hướng Google Maps</h3>
            <p>
              Để MedGuard AI và Google Maps có thể tự động điền{' '}
              <strong>Vị trí hiện tại của bạn (Origin)</strong> làm điểm xuất phát
              và quét các quầy thuốc GPP quanh bạn, vui lòng cho phép quyền truy cập GPS.
            </p>

            <div className="modal-current-fallback">
              <span className="fallback-label">Vị trí phát hiện hiện tại:</span>
              <strong className="fallback-name">{userLocation.name}</strong>
              <small className="fallback-addr">{userLocation.address}</small>
            </div>

            <div className="modal-actions-row">
              <button
                type="button"
                className="btn-grant-gps"
                disabled={requestingGps}
                onClick={handleRequestGps}
              >
                {requestingGps ? (
                  <>
                    <RefreshCw size={16} className="spin" />
                    <span>Đang xác thực tọa độ GPS của bạn...</span>
                  </>
                ) : (
                  <>
                    <LocateFixed size={16} />
                    <span>Lấy chính xác vị trí GPS của tôi (Khuyến nghị)</span>
                  </>
                )}
              </button>

              <button
                type="button"
                className="btn-use-preset"
                onClick={() => setPermissionPromptOpen(false)}
              >
                Tiếp tục với tọa độ phát hiện ({userLocation.name})
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main Top Header */}
      <header className="nav-page-topbar">
        <div className="nav-topbar-left">
          <button
            type="button"
            className="nav-back-chat-btn"
            onClick={onBackToChat}
            title="Quay lại cuộc trò chuyện"
          >
            <ArrowLeft size={16} />
            <span>Hội thoại</span>
          </button>
          <div className="nav-page-heading">
            <h1>Chỉ Đường Real-Time & Trạm Y Tế GPP</h1>
            <span className="heading-sub">
              Dẫn đường 3D Buồng Lái & 2D Toàn Cảnh kết hợp • Khử nhiễu GPS Turf.js & Auto-Reroute
            </span>
          </div>
        </div>

        <div className="nav-topbar-controls">
          {/* Origin Pill with GPS button */}
          <div className="nav-origin-pill" title={userLocation.address}>
            <span className={`loc-dot ${userLocation.is_gps ? 'gps' : 'preset'}`} />
            <MapPin size={14} className="pin-icon" />
            <div className="origin-text">
              <span className="origin-title">{userLocation.name}</span>
              <small className="origin-coords">
                {userLocation.lat.toFixed(4)}, {userLocation.lng.toFixed(4)}
              </small>
            </div>
            <button
              type="button"
              className="gps-refresh-btn"
              onClick={handleRequestGps}
              disabled={requestingGps}
              title="Lấy lại vị trí GPS thực tế"
            >
              <LocateFixed size={13} className={requestingGps ? 'spin' : ''} />
              <span>{userLocation.is_gps ? 'GPS Bật' : 'Lấy GPS'}</span>
            </button>
          </div>

          {/* Live GPS Tracking Toggle */}
          <button
            type="button"
            className={`nav-live-track-btn ${liveTracking ? 'active' : ''}`}
            onClick={() => setLiveTracking(!liveTracking)}
            title="Tự động cập nhật lộ trình khi bạn di chuyển trên đường"
          >
            <span className={`live-track-dot ${liveTracking ? 'tracking' : ''}`} />
            <span>{liveTracking ? 'Bám sát GPS' : 'Bật bám sát'}</span>
          </button>

          {/* Map theme toggle with Satellite Imagery support */}
          <button
            type="button"
            className="nav-theme-toggle-btn"
            onClick={() =>
              setMapTheme((curr) =>
                curr === 'streets'
                  ? 'satellite'
                  : curr === 'satellite'
                  ? 'dark'
                  : curr === 'dark'
                  ? 'osm'
                  : 'streets'
              )
            }
            title="Đổi loại bản đồ: Phố HD (Thành phố) / Vệ tinh (Địa hình nông thôn & ao hồ) / Nền tối / OpenStreetMap"
          >
            <Layers size={14} />
            <span>
              {mapTheme === 'streets'
                ? 'Bản đồ Phố HD'
                : mapTheme === 'satellite'
                ? 'Bản đồ Vệ tinh'
                : mapTheme === 'dark'
                ? 'Bản đồ Nền tối'
                : 'Bản đồ OpenStreetMap'}
            </span>
          </button>

          {/* 3-State Audio Guidance Control (Full / Alerts Only / Muted) */}
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
        </div>
      </header>

      {/* Smart Search, Vehicle Modes & Route Avoidances Control Strip (Google Maps standard) */}
      <div className="nav-smart-control-strip">
        {/* Left: Search & Voice Input */}
        <div className="smart-search-box">
          <Search size={15} className="search-icon" />
          <input
            type="text"
            className="smart-search-input"
            placeholder="Tìm địa điểm, cây xăng gần đây, quán cơm, hiệu thuốc..."
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
              <X size={14} />
            </button>
          )}
          <button
            type="button"
            className={`btn-voice-search ${isListeningVoice ? 'listening' : ''}`}
            onClick={handleVoiceSearchToggle}
            title={
              isListeningVoice
                ? 'Đang lắng nghe... Bấm để dừng'
                : 'Tìm kiếm bằng giọng nói tiếng Việt (Microphone)'
            }
          >
            {isListeningVoice ? <MicOff size={15} /> : <Mic size={15} />}
            <span>{isListeningVoice ? 'Đang nghe...' : 'Nói tìm kiếm'}</span>
          </button>
        </div>

        {/* Center: Vehicle Travel Mode Selector (Motorcycle / Car / Walking) */}
        <div className="vehicle-mode-selector" role="radiogroup" aria-label="Phương tiện di chuyển">
          <button
            type="button"
            className={`mode-btn ${travelMode === 'motorcycle' ? 'active' : ''}`}
            onClick={() => setTravelMode('motorcycle')}
            title="Lộ trình Xe máy: Tối ưu ngõ hẻm an toàn, tránh cao tốc cấm xe 2 bánh"
          >
            <Bike size={14} />
            <span>Xe máy</span>
            <span className="mode-subtag">Khuyên dùng</span>
          </button>
          <button
            type="button"
            className={`mode-btn ${travelMode === 'drive' ? 'active' : ''}`}
            onClick={() => setTravelMode('drive')}
            title="Lộ trình Ô tô: Đường lớn, tránh đường cấm hoặc ngõ hẹp"
          >
            <Car size={14} />
            <span>Ô tô</span>
          </button>
          <button
            type="button"
            className={`mode-btn ${travelMode === 'walk' ? 'active' : ''}`}
            onClick={() => setTravelMode('walk')}
            title="Lộ trình Đi bộ: Lối đi bộ ngắn nhất"
          >
            <Footprints size={14} />
            <span>Đi bộ</span>
          </button>
        </div>

        {/* Right: Route Avoidance Options */}
        <div className="route-avoidances-box">
          <label className="avoid-label" title="Tránh các trạm thu phí BOT dọc đường">
            <input
              type="checkbox"
              checked={avoidTolls}
              onChange={(e) => setAvoidTolls(e.target.checked)}
            />
            <span>Tránh trạm thu phí</span>
          </label>
          <label className="avoid-label" title="Tránh các tuyến đường cao tốc">
            <input
              type="checkbox"
              checked={avoidHighways}
              onChange={(e) => setAvoidHighways(e.target.checked)}
            />
            <span>Tránh cao tốc</span>
          </label>
        </div>
      </div>

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

      {/* Workspace Split Layout: Map on the left/center, Navigation Control on the right */}
      <div className="nav-workspace-layout">
        {/* Map View Canvas */}
        <section className="nav-map-view-section">
          <div className="map-canvas-header-bar">
            <div className="map-badge-group">
              <span className="live-radar-badge">
                <span className="live-pulse" /> LIVE TRAFFIC ROUTING
              </span>
              <span className="map-route-summary">
                {activeRoute ? (
                  <>
                    Lộ trình: <strong>{activeRoute.distance_km} km</strong> • ~
                    <strong>{activeRoute.eta_minutes} phút</strong> di chuyển
                  </>
                ) : (
                  'Đang tính toán lộ trình tối ưu...'
                )}
              </span>
            </div>

            {/* Tri-Mode Switcher: 3D Cockpit | 2D Overview | Google Maps Embed */}
            <div className="map-tab-switcher">
              <button
                type="button"
                className={`map-tab-btn ${mapViewMode === '3d_cockpit' ? 'active' : ''}`}
                onClick={() => setMapViewMode('3d_cockpit')}
                title="Bản đồ 3D Buồng lái nghiêng 60° (MapLibre GL JS & Nhà 3D)"
              >
                <Car size={13} />
                <span>3D Buồng Lái</span>
              </button>
              <button
                type="button"
                className={`map-tab-btn ${mapViewMode === '2d_overview' ? 'active' : ''}`}
                onClick={() => setMapViewMode('2d_overview')}
                title="Bản đồ 2D Toàn cảnh bao quát lộ trình (Leaflet HD)"
              >
                <Compass size={13} />
                <span>2D Toàn Cảnh</span>
              </button>
              <button
                type="button"
                className={`map-tab-btn ${mapViewMode === 'gmaps_embed' ? 'active' : ''}`}
                onClick={() => setMapViewMode('gmaps_embed')}
                title="Xem bản đồ chỉ đường nhúng trực tiếp từ Google Maps"
              >
                <ExternalLink size={13} />
                <span>Google Maps Trực tiếp</span>
              </button>
            </div>

            <div className="map-poi-type-toggle">
              <button
                type="button"
                className={`type-tab-btn ${poiType === 'pharmacy' ? 'active' : ''}`}
                onClick={() => setPoiType('pharmacy')}
              >
                <Pill size={14} />
                <span>Nhà thuốc GPP</span>
              </button>
              <button
                type="button"
                className={`type-tab-btn ${poiType === 'emergency' ? 'active' : ''}`}
                onClick={() => setPoiType('emergency')}
              >
                <Building2 size={14} />
                <span>Cấp cứu 115</span>
              </button>
            </div>
          </div>

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

            {/* Floating Compass Widget (Rotates dynamically with heading; click resets to North) */}
            {mapViewMode !== 'gmaps_embed' && (
              <button
                type="button"
                className="floating-compass-btn"
                onClick={handleResetCompass}
                title="Căn chỉnh la bàn hướng thẳng về chính Bắc (0°)"
              >
                <div
                  className="compass-dial"
                  style={{
                    transform: `rotate(${Math.round(vehicleHeading || 0)}deg)`,
                  }}
                >
                  <div className="compass-needle-n">▲ N</div>
                  <div className="compass-needle-s">S</div>
                </div>
              </button>
            )}

            {/* Floating Recenter GPS Button (Google Maps 'Về giữa' round button) */}
            {mapViewMode !== 'gmaps_embed' && (
              <button
                type="button"
                className="floating-recenter-btn"
                onClick={handleRecenterGps}
                title="Về giữa (Đưa camera quay lại vị trí GPS hiện tại của bạn)"
              >
                <LocateFixed size={18} />
                <span className="recenter-badge">Về giữa</span>
              </button>
            )}

            {/* Floating Along-Route Amenities Dock (Cây xăng, Quầy thuốc, Cấp cứu, Quán cơm, Cà phê) */}
            {mapViewMode !== 'gmaps_embed' && (
              <div className="floating-along-route-dock">
                <span className="dock-title">Dọc tuyến:</span>
                <button
                  type="button"
                  className={`dock-chip ${poiType === 'gas_station' ? 'active' : ''}`}
                  onClick={() => {
                    setPoiType('gas_station');
                    setQuickAmenity('gas_station');
                    onNotify?.('⛽ Đang quét các cây xăng / trạm xăng gần nhất dọc tuyến...');
                  }}
                  title="Tìm cây xăng / trạm xăng gần nhất"
                >
                  <Fuel size={13} />
                  <span>Cây xăng</span>
                </button>
                <button
                  type="button"
                  className={`dock-chip ${poiType === 'pharmacy' ? 'active' : ''}`}
                  onClick={() => {
                    setPoiType('pharmacy');
                    setQuickAmenity('pharmacy');
                    onNotify?.('💊 Đang hiển thị các quầy thuốc GPP gần nhất...');
                  }}
                  title="Tìm quầy thuốc GPP"
                >
                  <Pill size={13} />
                  <span>Quầy thuốc</span>
                </button>
                <button
                  type="button"
                  className={`dock-chip ${poiType === 'emergency' ? 'active' : ''}`}
                  onClick={() => {
                    setPoiType('emergency');
                    setQuickAmenity('emergency');
                    onNotify?.('🏥 Đang hiển thị các trung tâm cấp cứu 115 & bệnh viện...');
                  }}
                  title="Tìm trạm cấp cứu & bệnh viện"
                >
                  <Building2 size={13} />
                  <span>Cấp cứu 115</span>
                </button>
                <button
                  type="button"
                  className={`dock-chip ${poiType === 'cafe' ? 'active' : ''}`}
                  onClick={() => {
                    setPoiType('cafe');
                    setQuickAmenity('cafe');
                    onNotify?.('☕ Đang tìm quán cà phê / trạm dừng chân gần nhất...');
                  }}
                  title="Tìm quán cà phê / trạm nghỉ"
                >
                  <Coffee size={13} />
                  <span>Cà phê</span>
                </button>
                <button
                  type="button"
                  className={`dock-chip ${poiType === 'restaurant' ? 'active' : ''}`}
                  onClick={() => {
                    setPoiType('restaurant');
                    setQuickAmenity('restaurant');
                    onNotify?.('🍱 Đang tìm quán cơm / quán ăn gần nhất...');
                  }}
                  title="Tìm quán cơm / quán ăn"
                >
                  <Utensils size={13} />
                  <span>Quán cơm</span>
                </button>
              </div>
            )}

            {/* Off-Route Auto-Reroute Alert Badge */}
            {rerouteAlert && (
              <div className="offroute-reroute-alert" role="alert">
                <AlertTriangle size={16} className="spin-subtle" />
                <span>Phát hiện lệch đường • Đang tự động định tuyến lại lộ trình...</span>
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

            {/* Top HUD Card (Turn-by-Turn Banner) - Shown in both preview and live navigation */}
            {steps.length > 0 && mapViewMode !== 'gmaps_embed' && (
              <div className="nav-hud-top-card">
                <div className="hud-main-bar">
                  <div className="hud-maneuver-icon-box">
                    {getTurnDirectionIcon(currentStep.instruction)}
                  </div>
                  <div className="hud-instruction-box">
                    <div className="hud-dist-lead">
                      {formatDistanceToTurn(currentStep.distance_km)}
                    </div>
                    <div className="hud-action-lead">
                      {translateStepInstruction(
                        currentStep.instruction,
                        currentStep.road_name
                      )}
                    </div>
                  </div>
                  <div className="hud-quick-actions">
                    {!isNavigatingLive ? (
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
                              `${formatDistanceToTurn(currentStep.distance_km)}, ${translateStepInstruction(currentStep.instruction, currentStep.road_name)}`,
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
                      {translateStepInstruction(
                        nextStep.instruction,
                        nextStep.road_name
                      )}
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

            {/* Float Overlay on Map: Selected Destination Info (Preview Mode) */}
            {!isNavigatingLive && selectedPoi && mapViewMode !== 'gmaps_embed' && (
              <div className="map-float-poi-card">
                <div className="float-poi-content">
                  <div className="float-badge-row">
                    <span className="float-badge-dest">ĐIỂM ĐẾN (B)</span>
                    {navigationContext?.fromChat &&
                      (selectedPoi.id === navigationContext.selectedPoi?.id ||
                        selectedPoi.name === navigationContext.selectedPoi?.name) && (
                        <span className="float-chat-tag">
                          <Sparkles size={11} /> ĐỀ XUẤT TỪ CHAT
                        </span>
                      )}
                    <span
                      className={`float-op-badge ${selectedPoi.operating_status?.is_open ? 'open' : 'closed'}`}
                    >
                      {selectedPoi.operating_status?.status_label}
                    </span>
                    {(selectedPoi.operating_status?.status_badge === 'CLOSING_SOON' ||
                      (selectedPoi.operating_status?.minutes_until_close &&
                        selectedPoi.operating_status.minutes_until_close <= 30)) && (
                      <span className="closing-soon-warning">
                        <AlertTriangle size={12} />
                        Có thể đóng cửa trước lúc bạn đến
                      </span>
                    )}
                  </div>
                  <strong className="float-poi-title">{selectedPoi.name}</strong>
                  <p className="float-poi-addr">{selectedPoi.address}</p>
                </div>

                <div className="float-cta-group">
                  <button
                    type="button"
                    className="btn-start-cockpit-nav"
                    onClick={() => startLiveNavigation(false)}
                    title="Kích hoạt chế độ dẫn đường trực tiếp Google Maps"
                  >
                    <Navigation size={16} />
                    <span>🟢 BẮT ĐẦU CHỈ ĐƯỜNG</span>
                  </button>

                  <button
                    type="button"
                    className="btn-simulate-cockpit-nav"
                    onClick={() => startLiveNavigation(true)}
                    title="Mô phỏng xe di chuyển từng khúc rẽ và phát giọng nói tiếng Việt"
                  >
                    <Play size={14} />
                    <span>Mô phỏng xe chạy</span>
                  </button>

                  {selectedPoi.phone && (
                    <a
                      href={`tel:${selectedPoi.phone}`}
                      className="btn-poi-call-direct"
                      title={`Gọi trực tiếp đến ${selectedPoi.name}`}
                    >
                      <PhoneCall size={14} />
                      <span>Gọi ({selectedPoi.phone})</span>
                    </a>
                  )}

                  <a
                    href={googleMapsNavUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="float-gmaps-link-btn"
                    title="Mở Google Maps App với chế độ dẫn đường Turn-by-Turn GPS"
                  >
                    <Navigation size={14} />
                    <span>Mở Google Maps GPS</span>
                    <ExternalLink size={12} />
                  </a>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Navigation Sidebar & Console */}
        <aside className="nav-sidebar-console">
          {/* Turn-by-Turn Navigation Stepper (Positioned at TOP for immediate visibility) */}
          {steps.length > 0 && (
            <div className="nav-turn-stepper-box">
              <div className="stepper-header">
                <div className="stepper-title-row">
                  <Compass size={16} className="compass-icon pulse-subtle" />
                  <strong>CHỈ DẪN TỪNG CHẶNG RẼ (TURN-BY-TURN)</strong>
                </div>
                <div className="stepper-actions-header">
                  <button
                    type="button"
                    className="btn-stepper-tts-speak"
                    onClick={() =>
                      speakVietnameseInstruction(
                        `${formatDistanceToTurn(currentStep.distance_km)}, ${translateStepInstruction(currentStep.instruction, currentStep.road_name)}`,
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
                  <span className="road-highlight">
                    {currentStep.road_name || 'Đoạn đường di chuyển'}
                  </span>
                  <h4 className="instruction-heading">
                    {translateStepInstruction(
                      currentStep.instruction,
                      currentStep.road_name
                    )}
                  </h4>
                  <div className="turn-metrics">
                    <span className="metric-tag">
                      <Route size={12} /> {formatDistanceToTurn(currentStep.distance_km)}
                    </span>
                    <span className="metric-tag">
                      <Clock size={12} /> ~
                      {Math.max(1, Math.round(currentStep.distance_km * 2.5))}{' '}
                      phút
                    </span>
                  </div>
                </div>
              </div>

              {/* Start Navigation Action within Stepper */}
              <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
                <button
                  type="button"
                  onClick={() => {
                    if (!isNavigatingLive) startLiveNavigation(false);
                    else stopLiveNavigation();
                  }}
                  style={{
                    flex: 1,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    padding: '10px 14px',
                    background: isNavigatingLive
                      ? 'rgba(239, 68, 68, 0.2)'
                      : 'linear-gradient(135deg, #059669 0%, #10b981 100%)',
                    border: isNavigatingLive ? '1px solid #ef4444' : 'none',
                    borderRadius: '8px',
                    color: '#ffffff',
                    fontWeight: 700,
                    fontSize: '0.85rem',
                    cursor: 'pointer',
                    boxShadow: isNavigatingLive
                      ? 'none'
                      : '0 4px 14px rgba(16, 185, 129, 0.35)',
                  }}
                >
                  <Navigation size={15} />
                  <span>
                    {isNavigatingLive ? 'DỪNG DẪN ĐƯỜNG' : '🟢 BẮT ĐẦU CHỈ ĐƯỜNG'}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => startLiveNavigation(true)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    padding: '10px 14px',
                    background: 'rgba(255, 255, 255, 0.08)',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    borderRadius: '8px',
                    color: '#cbd5e1',
                    fontWeight: 600,
                    fontSize: '0.82rem',
                    cursor: 'pointer',
                  }}
                  title="Mô phỏng xe chạy"
                >
                  <Play size={14} />
                  <span>Mô phỏng</span>
                </button>
              </div>

              {/* Step Navigation Controls */}
              <div className="stepper-controls-bar">
                <button
                  type="button"
                  className="step-nav-btn"
                  disabled={activeStepIndex === 0}
                  onClick={() => handleStepClick(Math.max(0, activeStepIndex - 1))}
                >
                  <ArrowLeft size={13} /> Chặng trước
                </button>
                <div className="step-dots-group">
                  {steps.map((s, idx) => (
                    <button
                      key={idx}
                      type="button"
                      className={`step-dot ${idx === activeStepIndex ? 'active' : idx < activeStepIndex ? 'passed' : ''}`}
                      onClick={() => handleStepClick(idx)}
                      title={`Chặng ${idx + 1}: ${translateStepInstruction(s.instruction, s.road_name)}`}
                    >
                      {idx + 1}
                    </button>
                  ))}
                </div>
                <button
                  type="button"
                  className="step-nav-btn btn-next"
                  disabled={activeStepIndex === steps.length - 1}
                  onClick={() =>
                    handleStepClick(Math.min(steps.length - 1, activeStepIndex + 1))
                  }
                >
                  Chặng tiếp <ArrowRight size={13} />
                </button>
              </div>
            </div>
          )}

          {/* Dual Navigation Choice Hero Banner */}
          <div className="nav-dual-choice-hero">
            <div className="hero-header">
              <Navigation size={18} className="hero-icon" />
              <div>
                <strong>CƠ CHẾ ĐIỀU HƯỚNG KẾT HỢP 3D & 2D</strong>
                <p>
                  Động cơ <strong>Turf.js GPS Engine</strong> tự động khử nhiễu bắt dính tim đường, kết hợp{' '}
                  <strong>3D Buồng lái (MapLibre WebGL)</strong> và <strong>2D Toàn cảnh (Leaflet HD)</strong>.
                </p>
              </div>
            </div>

            <div className="hero-choices-grid">
              {/* Lựa chọn 1: Deep Link sang Google Maps App với tham số dẫn đường trực tiếp */}
              <a
                href={googleMapsNavUrl}
                target="_blank"
                rel="noreferrer"
                className="hero-choice-card choice-gmaps-primary"
              >
                <div className="choice-badge-top">
                  <span className="badge-tag">LỰA CHỌN 1</span>
                  <span className="badge-type">Google Maps App GPS</span>
                </div>
                <h4>Mở Ứng dụng Google Maps</h4>
                <p>
                  Khởi động chế độ Dẫn Đường Trực Tiếp (Turn-by-Turn Voice Navigation)
                  trên Google Maps với điểm A và B tự động nạp sẵn.
                </p>
                <div className="choice-btn-row">
                  <span>Bật Dẫn Đường Google Maps</span>
                  <ArrowRight size={14} />
                </div>
              </a>

              {/* Lựa chọn 2: Turn-by-Turn In-App Cockpit */}
              <div
                className={`hero-choice-card choice-inapp-primary ${isNavigatingLive ? 'navigating-active' : 'active'}`}
                onClick={() => {
                  if (!isNavigatingLive) {
                    startLiveNavigation(false);
                  }
                }}
              >
                <div className="choice-badge-top">
                  <span className="badge-tag tag-active">
                    {isNavigatingLive ? 'ĐANG DẪN ĐƯỜNG' : 'LỰA CHỌN 2 (MẶC ĐỊNH)'}
                  </span>
                  <span className="badge-type">3D WebGL & 2D Hybrid</span>
                </div>
                <h4>Chỉ Đường Real-time MedGuard</h4>
                <p>
                  Giao diện HUD buồng lái Google Maps với giọng nói hướng dẫn tiếng Việt,
                  theo dõi xe chạy và chỉ dẫn từng chặng rẽ.
                </p>
                <div className="choice-btn-row active-text">
                  <span className="btn-launch-inline">
                    {isNavigatingLive ? '🟢 Đang dẫn đường HUD' : '🟢 Bắt đầu chỉ đường ngay'}
                  </span>
                  <ChevronDown size={14} />
                </div>
              </div>
            </div>
          </div>

          {/* List of Nearby POIs */}
          <div className="nav-poi-list-section">
            <div className="poi-list-header">
              <span className="poi-list-title">
                {poiType === 'pharmacy'
                  ? 'Quầy thuốc GPP gần bạn nhất'
                  : poiType === 'emergency'
                  ? 'Bệnh viện & Trung tâm Cấp cứu 115'
                  : poiType === 'gas_station'
                  ? 'Trạm xăng & Cây xăng gần nhất'
                  : poiType === 'cafe'
                  ? 'Quán cà phê & Trạm dừng chân gần nhất'
                  : poiType === 'restaurant'
                  ? 'Quán cơm & Điểm ăn uống gần nhất'
                  : 'Địa điểm lân cận'}
              </span>
              <span className="poi-count-badge">{pois.length} địa điểm</span>
            </div>

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
                  const isFromChat =
                    poi.isRecommendedFromChat ||
                    (navigationContext?.selectedPoi &&
                      (poi.id === navigationContext.selectedPoi.id ||
                        (poi.name &&
                          navigationContext.selectedPoi.name &&
                          poi.name.toLowerCase() ===
                            navigationContext.selectedPoi.name.toLowerCase())));
                  return (
                    <div
                      key={poi.id}
                      className={`poi-card-item ${isSelected ? 'selected' : ''} ${isFromChat ? 'chat-recommended' : ''}`}
                      onClick={() => setSelectedPoi(poi)}
                    >
                      {isFromChat && (
                        <div className="poi-chat-recommended-badge">
                          <Sparkles size={11} />
                          <span>ĐỀ XUẤT TỪ CA TƯ VẤN</span>
                        </div>
                      )}
                      <div className="poi-card-top">
                        <div className="poi-name-col">
                          <strong>{poi.name}</strong>
                          <p className="poi-address-text">{poi.address}</p>
                        </div>
                        <div className="poi-dist-badge">
                          <span className="dist-num">{poi.distance_km}</span>
                          <span className="dist-unit">km</span>
                        </div>
                      </div>

                      <div className="poi-card-bottom">
                        <span
                          className={`poi-status-tag ${poi.operating_status?.is_open ? 'open' : 'closed'}`}
                        >
                          {poi.operating_status?.status_label}
                        </span>
                        {(poi.operating_status?.status_badge === 'CLOSING_SOON' ||
                          (poi.operating_status?.minutes_until_close &&
                            poi.operating_status.minutes_until_close <= 30)) && (
                          <span className="closing-soon-warning sidebar-warning">
                            <AlertTriangle size={11} />
                            Sắp đóng
                          </span>
                        )}
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
                          {isSelected ? 'Đang chọn' : 'Chọn để chỉ đường'}
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
