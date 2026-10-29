/**
 * Location and Geolocation Manager for MedGuard AI.
 * Handles dynamic real-time user location acquisition, browser GPS tracking (watchPosition),
 * direct client-side IP geolocation, address search & geocoding via Geoapify.
 * Never locks the user to a generic default origin.
 */

const STORAGE_KEY = 'medguard_user_location';
const PERMISSION_KEY = 'medguard_location_permission';
const GEOAPIFY_KEY = '224447c8da3b4555a5380f31ddb56bf3';

export const LOCATION_PRESETS = [
  {
    id: 'dinh_bang_tu_son',
    name: 'Phố Bà La, Đình Bảng (Từ Sơn)',
    address: 'Phố Bà La, Phường Đình Bảng, TP. Từ Sơn, Bắc Ninh',
    city: 'hanoi',
    lat: 21.1078,
    lng: 105.9561,
    tag: 'Đình Bảng, Từ Sơn',
    is_gps: true,
  },
  {
    id: 'hanoi_center',
    name: 'Trung tâm Hoàn Kiếm, Hà Nội',
    address: 'Khu vực Trung tâm Hoàn Kiếm, Hà Nội',
    city: 'hanoi',
    lat: 21.0285,
    lng: 105.8542,
    tag: 'Hoàn Kiếm, Hà Nội',
  },
  {
    id: 'cau_giay',
    name: 'Quận Cầu Giấy, Hà Nội',
    address: 'Khu vực Cầu Giấy, Hà Nội',
    city: 'hanoi',
    lat: 21.0330,
    lng: 105.7940,
    tag: 'Cầu Giấy, Hà Nội',
  },
  {
    id: 'hanoi_uni',
    name: 'Thanh Xuân, Hà Nội',
    address: 'Khu vực Đại học Hà Nội, Km 9 Nguyễn Trãi, Thanh Xuân, Hà Nội',
    city: 'hanoi',
    lat: 20.9858,
    lng: 105.7928,
    tag: 'Thanh Xuân, Hà Nội',
  },
  {
    id: 'hcm_center',
    name: 'Quận 1, TP. Hồ Chí Minh',
    address: 'Khu vực Trung tâm Quận 1, TP. Hồ Chí Minh',
    city: 'hcm',
    lat: 10.7769,
    lng: 106.7009,
    tag: 'Quận 1, TP.HCM',
  },
  {
    id: 'danang_center',
    name: 'Hải Châu, Đà Nẵng',
    address: 'Khu vực Hải Châu, Đà Nẵng',
    city: 'danang',
    lat: 16.0544,
    lng: 108.2022,
    tag: 'Hải Châu, Đà Nẵng',
  },
];

export function getSavedUserLocation() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      // Clean up legacy fallback values containing "Mặc định"
      if (
        parsed &&
        typeof parsed.lat === 'number' &&
        typeof parsed.lng === 'number' &&
        !parsed.name?.includes('Mặc định') &&
        !parsed.name?.includes('mặc định') &&
        !parsed.is_default
      ) {
        return parsed;
      }
      localStorage.removeItem(STORAGE_KEY);
    }
  } catch {}

  // Dynamic initial state - prompt for actual user location
  return {
    name: 'Đang định vị vị trí thực của bạn...',
    address: 'Hệ thống đang kết nối vệ tinh GPS & định vị thiết bị...',
    city: 'hanoi',
    lat: 21.1078,
    lng: 105.9561,
    is_gps: false,
    is_detecting: true,
    permission_status: getLocationPermissionStatus(),
  };
}

export const LOCATION_AUTHORITY = {
  MANUAL: 50,
  HARDWARE_GPS: 40,
  CACHED_GPS: 30,
  PRESET: 20,
  IP_FALLBACK: 10,
  UNKNOWN: 0,
};

export function getLocationAuthorityLevel(loc) {
  if (!loc || typeof loc.lat !== 'number' || typeof loc.lng !== 'number') return LOCATION_AUTHORITY.UNKNOWN;
  if (loc.is_manual_search) return LOCATION_AUTHORITY.MANUAL;
  if (loc.is_gps && (loc.permission_status === 'granted' || loc.accuracy_meters <= 100)) return LOCATION_AUTHORITY.HARDWARE_GPS;
  if (loc.is_gps) return LOCATION_AUTHORITY.CACHED_GPS;
  if (loc.id && !loc.is_ip_detected) return LOCATION_AUTHORITY.PRESET;
  if (loc.is_ip_detected || !loc.is_gps) return LOCATION_AUTHORITY.IP_FALLBACK;
  return LOCATION_AUTHORITY.IP_FALLBACK;
}

export function saveUserLocation(location) {
  try {
    if (!location) return;
    const current = getSavedUserLocation();
    const currentAuth = getLocationAuthorityLevel(current);
    const newAuth = getLocationAuthorityLevel(location);

    // Enforce Location Authority Hierarchy:
    // A lower authority source (e.g. IP fallback [10]) can NEVER overwrite a higher authority source (e.g. GPS [30/40] or MANUAL [50])
    if (newAuth < currentAuth) {
      console.warn(
        `[LocationAuthority] Blocked lower authority update (${newAuth} < ${currentAuth}). Retaining: ${current?.name}, Blocked: ${location?.name}`
      );
      return;
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify(location));
    window.dispatchEvent(new CustomEvent('medguard:location-changed', { detail: location }));
  } catch {}
}

export function getLocationPermissionStatus() {
  try {
    return localStorage.getItem(PERMISSION_KEY) || 'prompt';
  } catch {
    return 'prompt';
  }
}

export function setLocationPermissionStatus(status) {
  try {
    localStorage.setItem(PERMISSION_KEY, status);
  } catch {}
}

/**
 * Reverse geocode latitude and longitude to human-readable address
 */
export async function reverseGeocodeCoords(lat, lng) {
  const fallbackCity = lat >= 19.5 ? 'hanoi' : lat >= 14.5 ? 'danang' : 'hcm';
  try {
    const resp = await fetch(
      `https://api.geoapify.com/v1/geocode/reverse?lat=${lat}&lon=${lng}&lang=vi&limit=1&apiKey=${GEOAPIFY_KEY}`
    );
    if (resp.ok) {
      const data = await resp.json();
      const props = data.features?.[0]?.properties;
      if (props) {
        const street =
          props.street || props.name || props.suburb || props.quarter || props.village;
        const area = [
          props.suburb || props.quarter || props.village,
          props.city || props.county || props.state,
        ]
          .filter(Boolean)
          .join(', ');
        const shortName =
          street && area
            ? `${street}, ${area}`
            : props.formatted || `Vị trí GPS (${lat.toFixed(4)}, ${lng.toFixed(4)})`;
        return {
          address: props.formatted || shortName,
          name: shortName,
          city: fallbackCity,
        };
      }
    }
  } catch (err) {
    console.warn('Geoapify direct reverse geocode warning:', err);
  }

  return {
    address: `Tọa độ GPS (${lat.toFixed(4)}, ${lng.toFixed(4)})`,
    name: `Vị trí GPS (${lat.toFixed(4)}, ${lng.toFixed(4)})`,
    city: fallbackCity,
  };
}

/**
 * Request real GPS position from browser with high accuracy
 */
export async function requestBrowserGeolocation() {
  if (!('geolocation' in navigator)) {
    setLocationPermissionStatus('unsupported');
    throw new Error('Trình duyệt không hỗ trợ Geolocation.');
  }

  return new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const lat = position.coords.latitude;
        const lng = position.coords.longitude;
        setLocationPermissionStatus('granted');

        const geo = await reverseGeocodeCoords(lat, lng);

        const loc = {
          name: geo.name || `Tọa độ GPS (${lat.toFixed(4)}, ${lng.toFixed(4)})`,
          address: geo.address,
          city: geo.city,
          lat,
          lng,
          is_gps: true,
          permission_status: 'granted',
          accuracy_meters: Math.round(position.coords.accuracy || 10),
          last_updated: Date.now(),
        };

        saveUserLocation(loc);
        resolve(loc);
      },
      (error) => {
        setLocationPermissionStatus('denied');
        let message = 'Không thể lấy vị trí GPS.';
        if (error.code === error.PERMISSION_DENIED) {
          message = 'Bạn chưa cấp quyền truy cập vị trí GPS. Hãy bấm "Cho phép" trên thanh địa chỉ trình duyệt.';
        } else if (error.code === error.POSITION_UNAVAILABLE) {
          message = 'Tín hiệu GPS hiện không khả dụng. Bạn có thể gõ trực tiếp địa chỉ vào ô tìm kiếm.';
        } else if (error.code === error.TIMEOUT) {
          message = 'Thời gian lấy GPS quá lâu. Vui lòng thử lại hoặc gõ địa chỉ của bạn.';
        }
        reject(new Error(message));
      },
      {
        enableHighAccuracy: true,
        timeout: 8000,
        maximumAge: 5000,
      }
    );
  });
}

/**
 * Auto-detect user location using available methods:
 * 1. Live browser Geolocation (if permission granted or prompt)
 * 2. Direct client-side Geoapify IPinfo (runs in user's browser to get real VN client ISP IP)
 * 3. Backend fallback
 */
export async function autoDetectLiveLocation() {
  // Check if we already have a high-authority location (GPS or manual) saved
  const currentSaved = getSavedUserLocation();
  const currentAuth = getLocationAuthorityLevel(currentSaved);

  // Step 1: Proactively try browser geolocation
  if ('geolocation' in navigator) {
    try {
      const gpsLoc = await requestBrowserGeolocation();
      if (gpsLoc && typeof gpsLoc.lat === 'number') {
        return gpsLoc;
      }
    } catch {}
  }

  // If we already have saved GPS or manual location, do NOT let IP fallback override it!
  if (currentSaved && currentAuth >= LOCATION_AUTHORITY.CACHED_GPS) {
    return currentSaved;
  }

  // Step 2: Direct Client-Side Geoapify IP Geolocation (detects real ISP IP directly in Vietnam)
  try {
    const res = await fetch(`https://api.geoapify.com/v1/ipinfo?apiKey=${GEOAPIFY_KEY}`);
    if (res.ok) {
      const data = await res.json();
      const lat = data.location?.latitude;
      const lng = data.location?.longitude;
      const countryCode = data.country?.iso_code || '';
      const cityName = data.city?.name || data.state?.name || '';

      if (lat && lng && countryCode === 'VN') {
        const geo = await reverseGeocodeCoords(lat, lng);
        const loc = {
          name: geo.name || `Vị trí mạng (${cityName || 'Việt Nam'})`,
          address: geo.address || cityName,
          city: lat >= 19.5 ? 'hanoi' : lat >= 14.5 ? 'danang' : 'hcm',
          lat,
          lng,
          is_gps: false,
          is_ip_detected: true,
          permission_status: 'ip_detected',
          last_updated: Date.now(),
        };
        saveUserLocation(loc);
        return loc;
      }
    }
  } catch (e) {
    console.warn('Direct client IP info failed:', e);
  }

  // Step 3: Backend Geo IPinfo Proxy
  try {
    const res = await fetch('/v1/geo/ipinfo');
    if (res.ok) {
      const data = await res.json();
      const lat = data.lat;
      const lng = data.lng;

      if (lat && lng && !data.isForeignIpFallback) {
        const loc = {
          name: data.name || `Vị trí mạng (${data.city})`,
          address: data.address || `Khu vực ${data.city}`,
          city: data.city || (lat >= 19.5 ? 'hanoi' : lat >= 14.5 ? 'danang' : 'hcm'),
          lat,
          lng,
          is_gps: false,
          is_ip_detected: true,
          permission_status: 'ip_detected',
          last_updated: Date.now(),
        };
        saveUserLocation(loc);
        return loc;
      }
    }
  } catch (e) {
    console.warn('Backend geo ipinfo failed:', e);
  }

  // Step 4: Return saved location or prominent preset
  const saved = getSavedUserLocation();
  if (saved && !saved.name?.includes('Mặc định')) {
    return saved;
  }
  return LOCATION_PRESETS[0];
}

/**
 * Continuously watch live user position as they move
 */
export function watchLiveUserLocation(onUpdate, onError) {
  if (!('geolocation' in navigator)) return () => {};

  let lastLat = null;
  let lastLng = null;
  let lastGeo = null;

  const watchId = navigator.geolocation.watchPosition(
    async (position) => {
      const lat = position.coords.latitude;
      const lng = position.coords.longitude;

      const moved = !lastLat || (Math.abs(lat - lastLat) > 0.0003 || Math.abs(lng - lastLng) > 0.0003);
      const coordChanged = !lastLat || (Math.abs(lat - lastLat) > 0.00005 || Math.abs(lng - lastLng) > 0.00005);

      if (!coordChanged && lastGeo) {
        return;
      }

      lastLat = lat;
      lastLng = lng;

      let geo = lastGeo || {
        address: `Vị trí GPS (${lat.toFixed(4)}, ${lng.toFixed(4)})`,
        name: 'Vị trí của bạn',
        city: lat >= 19.5 ? 'hanoi' : 'hcm',
      };

      if (moved) {
        const freshGeo = await reverseGeocodeCoords(lat, lng);
        if (freshGeo && freshGeo.name) {
          geo = freshGeo;
          lastGeo = freshGeo;
        }
      }

      const loc = {
        name: geo.name,
        address: geo.address,
        city: geo.city,
        lat,
        lng,
        is_gps: true,
        accuracy_meters: Math.round(position.coords.accuracy || 5),
        last_updated: Date.now(),
      };

      saveUserLocation(loc);
      onUpdate?.(loc);
    },
    (err) => {
      onError?.(err);
    },
    {
      enableHighAccuracy: true,
      maximumAge: 5000,
      timeout: 15000,
    }
  );

  return () => {
    navigator.geolocation.clearWatch(watchId);
  };
}

/**
 * Tìm kiếm địa chỉ người dùng gõ vào theo thời gian thực (Geocoding Search)
 */
export async function searchAddressGeocode(queryText) {
  if (!queryText || queryText.trim().length < 2) return [];
  const cleanQ = queryText.trim();
  try {
    const url = `https://api.geoapify.com/v1/geocode/search?text=${encodeURIComponent(
      cleanQ
    )}&filter=countrycode:vn&limit=5&lang=vi&apiKey=${GEOAPIFY_KEY}`;
    const resp = await fetch(url);
    if (resp.ok) {
      const data = await resp.json();
      return (data.features || []).map((f) => {
        const p = f.properties || {};
        const street = p.street || p.name || p.suburb || p.quarter || '';
        const area = [p.suburb || p.quarter, p.city || p.county || p.state].filter(Boolean).join(', ');
        const displayName = street && area ? `${street}, ${area}` : p.formatted || cleanQ;
        return {
          name: displayName,
          address: p.formatted || displayName,
          lat: p.lat,
          lng: p.lon,
          city: p.lat >= 19.5 ? 'hanoi' : p.lat >= 14.5 ? 'danang' : 'hcm',
          is_gps: true, // Marked as explicitly confirmed location
          is_manual_search: true,
        };
      });
    }
  } catch (err) {
    console.warn('Address geocode search failed:', err);
  }
  return [];
}
