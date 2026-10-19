/**
 * Location and Geolocation Manager for MedGuard AI.
 * Handles dynamic real-time user location acquisition, browser GPS tracking (watchPosition),
 * reverse geocoding via Geoapify, and IP-based fallback.
 * Never locks the user to a fixed origin.
 */

const GEOAPIFY_API_KEY = '224447c8da3b4555a5380f31ddb56bf3';
const STORAGE_KEY = 'medguard_user_location';
const PERMISSION_KEY = 'medguard_location_permission';

export const LOCATION_PRESETS = [
  {
    id: 'live_detected',
    name: 'Vị trí hiện tại của bạn',
    address: 'Đang tự động định vị vị trí thực...',
    city: 'hanoi',
    lat: 21.0285,
    lng: 105.8542,
    tag: 'Tọa độ thực của thiết bị',
  },
  {
    id: 'hanoi_uni',
    name: 'Đại học Hà Nội',
    address: 'Trường Đại học Hà Nội, Km 9 Nguyễn Trãi, Thanh Xuân, Hà Nội',
    city: 'hanoi',
    lat: 20.9858,
    lng: 105.7928,
    tag: 'Thanh Xuân, Hà Nội',
  },
  {
    id: 'hanoi_center',
    name: 'Hoàn Kiếm, Hà Nội',
    address: 'Khu vực Trung tâm Hoàn Kiếm, Hà Nội',
    city: 'hanoi',
    lat: 21.0285,
    lng: 105.8542,
    tag: 'Trung tâm Hà Nội',
  },
  {
    id: 'cau_giay',
    name: 'Cầu Giấy, Hà Nội',
    address: 'Khu vực Cầu Giấy, Hà Nội',
    city: 'hanoi',
    lat: 21.0330,
    lng: 105.7940,
    tag: 'Cầu Giấy, Hà Nội',
  },
  {
    id: 'hcm_center',
    name: 'Quận 1, TP.HCM',
    address: 'Khu vực Trung tâm Quận 1, TP. Hồ Chí Minh',
    city: 'hcm',
    lat: 10.7769,
    lng: 106.7009,
    tag: 'Trung tâm TP.HCM',
  },
  {
    id: 'danang_center',
    name: 'Hải Châu, Đà Nẵng',
    address: 'Khu vực Hải Châu, Đà Nẵng',
    city: 'danang',
    lat: 16.0544,
    lng: 108.2022,
    tag: 'Trung tâm Đà Nẵng',
  },
];

export function getSavedUserLocation() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed.lat === 'number' && typeof parsed.lng === 'number') {
        return parsed;
      }
    }
  } catch {}

  // Dynamic initial state - prompt for actual user location
  return {
    name: 'Vị trí hiện tại của bạn',
    address: 'Đang định vị tọa độ GPS thực tế của bạn...',
    city: 'hanoi',
    lat: 21.0285,
    lng: 105.8542,
    is_gps: false,
    is_detecting: true,
    permission_status: getLocationPermissionStatus(),
  };
}

export function saveUserLocation(location) {
  try {
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
  try {
    const res = await fetch(
      `https://api.geoapify.com/v1/geocode/reverse?lat=${lat}&lon=${lng}&apiKey=${GEOAPIFY_API_KEY}`
    );
    if (res.ok) {
      const data = await res.json();
      const feat = data?.features?.[0];
      if (feat?.properties) {
        const p = feat.properties;
        const formatted = p.formatted || `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
        let city = 'hanoi';
        if (lat >= 19.5) city = 'hanoi';
        else if (lat >= 14.5 && lat <= 17.5) city = 'danang';
        else city = 'hcm';

        return {
          address: formatted,
          name: p.street ? `${p.housenumber ? p.housenumber + ' ' : ''}${p.street}` : (p.district || p.city || 'Vị trí hiện tại'),
          city: p.city?.toLowerCase().includes('ho chi minh') ? 'hcm' : p.city?.toLowerCase().includes('da nang') ? 'danang' : city,
        };
      }
    }
  } catch (e) {
    console.warn('Reverse geocode failed:', e);
  }
  return {
    address: `Tọa độ GPS (${lat.toFixed(4)}, ${lng.toFixed(4)})`,
    name: 'Vị trí hiện tại của bạn',
    city: lat >= 19.5 ? 'hanoi' : lat >= 14.5 ? 'danang' : 'hcm',
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
          name: geo.name || 'Vị trí GPS của bạn',
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
          message = 'Bạn chưa cấp quyền truy cập vị trí GPS.';
        } else if (error.code === error.POSITION_UNAVAILABLE) {
          message = 'Tín hiệu GPS hiện không khả dụng.';
        } else if (error.code === error.TIMEOUT) {
          message = 'Thời gian lấy GPS quá lâu.';
        }
        reject(new Error(message));
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 10000,
      }
    );
  });
}

/**
 * Auto-detect user location using available methods:
 * 1. Live browser Geolocation (if permission granted or prompt)
 * 2. Geoapify IP-based network geolocation fallback (detects actual user city & coords)
 */
export async function autoDetectLiveLocation() {
  // Step 1: Try browser geolocation
  if ('geolocation' in navigator) {
    try {
      const gpsLoc = await requestBrowserGeolocation();
      return gpsLoc;
    } catch {}
  }

  // Step 2: Fallback to Geoapify IPinfo (detects user's actual city and coordinates from connection)
  try {
    const res = await fetch(`https://api.geoapify.com/v1/ipinfo?apiKey=${GEOAPIFY_API_KEY}`);
    if (res.ok) {
      const data = await res.json();
      const lat = data.location?.latitude;
      const lng = data.location?.longitude;
      const cityName = data.city?.name || 'Việt Nam';
      const district = data.subdivisions?.[1]?.names?.en || data.subdivisions?.[0]?.names?.en || '';

      if (lat && lng) {
        let city = 'hanoi';
        if (lat >= 19.5) city = 'hanoi';
        else if (lat >= 14.5 && lat <= 17.5) city = 'danang';
        else city = 'hcm';

        const address = district ? `${district}, ${cityName}` : cityName;
        const loc = {
          name: `Vị trí mạng (${cityName})`,
          address: `Khu vực ${address}`,
          city,
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
  } catch {}

  return getSavedUserLocation();
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

      // Only re-geocode if moved more than ~30 meters or first time
      const moved = !lastLat || (Math.abs(lat - lastLat) > 0.0003 || Math.abs(lng - lastLng) > 0.0003);
      const coordChanged = !lastLat || (Math.abs(lat - lastLat) > 0.00005 || Math.abs(lng - lastLng) > 0.00005);

      if (!coordChanged && lastGeo) {
        return; // Coordinates haven't meaningfully changed, skip redundant render cycles
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
