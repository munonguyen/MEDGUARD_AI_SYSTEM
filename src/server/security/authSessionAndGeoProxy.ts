// File: src/server/security/authSessionAndGeoProxy.ts
import crypto from 'node:crypto';
import type { Request, Response, NextFunction } from 'express';

const GUEST_MAX_TURNS = 3;
const guestQuotaStore = new Map<string, { usedTurns: number; expiresAt: number }>();

/**
 * Middleware cấp và xác thực Guest Session ID riêng biệt qua HttpOnly Cookie.
 * Đảm bảo khách A không bao giờ đọc được lịch sử khám bệnh của khách B.
 */
export function ensureIsolatedGuestSession(req: Request, res: Response, next: NextFunction) {
  // Nếu đã đăng nhập tài khoản thực thì bỏ qua
  if ((req as any).user?.id) {
    return next();
  }

  let guestSid = req.cookies?.['medguard_guest_sid'];
  if (!guestSid || !/^[a-f0-9]{32}$/.test(guestSid)) {
    guestSid = crypto.randomBytes(16).toString('hex');
    res.cookie('medguard_guest_sid', guestSid, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 2 * 60 * 60 * 1000 // Hết hạn sau 2 giờ
    });
  }

  (req as any).guestSessionId = guestSid;
  next();
}

/**
 * Middleware kiểm soát chặt 3 lượt dùng thử trên Server cho cả /v1/chat và /v1/companion (Bác sĩ 3D Live).
 */
export function enforceServerGuestQuota(req: Request, res: Response, next: NextFunction) {
  if ((req as any).user?.id) {
    return next();
  }

  const guestSid = (req as any).guestSessionId;
  if (!guestSid) {
    return res.status(401).json({ error: 'Vui lòng khởi tạo phiên dùng thử hợp lệ.' });
  }

  const now = Date.now();
  const record = guestQuotaStore.get(guestSid) || {
    usedTurns: 0,
    expiresAt: now + 24 * 60 * 60 * 1000
  };

  if (record.usedTurns >= GUEST_MAX_TURNS) {
    return res.status(403).json({
      code: 'GUEST_QUOTA_EXCEEDED',
      remainingTurns: 0,
      message: 'Bạn đã sử dụng hết 3/3 lượt dùng thử miễn phí. Vui lòng đăng nhập hoặc tạo tài khoản để tiếp tục tư vấn.'
    });
  }

  record.usedTurns += 1;
  guestQuotaStore.set(guestSid, record);
  res.setHeader('X-Guest-Remaining-Turns', String(GUEST_MAX_TURNS - record.usedTurns));
  next();
}

/**
 * Proxy ẩn Geoapify API Key phía Server & chuẩn hóa vị trí Việt Nam
 */
export async function handleIpLocationLookup(req: Request, res: Response) {
  try {
    const apiKey = process.env.GEOAPIFY_API_KEY;
    if (!apiKey) {
      return res.json({
        city: 'hanoi',
        name: 'Hà Nội (Mặc định)',
        lat: 21.0285,
        lng: 105.8542,
        isFallbackVn: true
      });
    }

    const clientIp = (req.headers['x-forwarded-for'] as string)?.split(',')[0]?.trim() || req.ip;
    const response = await fetch(
      `https://api.geoapify.com/v1/ipinfo?ip=${encodeURIComponent(clientIp || '')}&apiKey=${apiKey}`
    );
    const data = await response.json();

    // Nếu IP nằm ngoài lãnh thổ Việt Nam (ví dụ VPN/Cloud ở Shibuya, Tokyo), không trộn lẫn tọa độ Nhật Bản với tên "Hà Nội"!
    const countryCode = data?.country?.iso_code?.toUpperCase();
    if (countryCode !== 'VN') {
      return res.json({
        city: 'hanoi',
        name: 'Hà Nội (Cần cấp quyền GPS để lấy vị trí chính xác)',
        address: 'Trung tâm Điều phối Y tế Hà Nội',
        lat: 21.0285,
        lng: 105.8542,
        isForeignIpFallback: true
      });
    }

    return res.json({
      city: data.city?.name || 'Việt Nam',
      name: `Vị trí mạng (${data.city?.name || 'Việt Nam'})`,
      address: data.city?.name || 'Việt Nam',
      lat: data.location?.latitude ?? 21.0285,
      lng: data.location?.longitude ?? 105.8542,
      isForeignIpFallback: false
    });
  } catch {
    return res.json({
      city: 'hanoi',
      name: 'Hà Nội (Mặc định)',
      lat: 21.0285,
      lng: 105.8542,
      isFallbackVn: true
    });
  }
}
