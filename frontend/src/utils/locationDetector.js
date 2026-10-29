export async function reverseGeocode(lat, lng) {
  const fallbackCity = lat >= 19.5 ? "hanoi" : lat >= 14.5 ? "danang" : "hcm";
  // 1. Ưu tiên gọi trực tiếp Geoapify Reverse Geocoding để lấy chính xác tên đường/phố và không bao giờ gây lỗi 500 trên Console
  try {
    const geoKey = "224447c8da3b4555a5380f31ddb56bf3";
    const resp = await fetch(
      `https://api.geoapify.com/v1/geocode/reverse?lat=${lat}&lon=${lng}&lang=vi&limit=1&apiKey=${geoKey}`
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
          .join(", ");
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
    console.warn("Geoapify reverse geocode warning:", err);
  }

  return {
    address: `Tọa độ GPS (${lat.toFixed(4)}, ${lng.toFixed(4)})`,
    name: `Vị trí GPS (${lat.toFixed(4)}, ${lng.toFixed(4)})`,
    city: fallbackCity,
  };
}

export const reverseGeocodeCoords = reverseGeocode;
export default reverseGeocode;
