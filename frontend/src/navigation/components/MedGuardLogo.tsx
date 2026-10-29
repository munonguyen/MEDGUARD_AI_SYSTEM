/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * MedGuard AI - Bespoke Symbolic Brand Emblem & Meaning Popover
 * Combines 4 clinical & spatial navigation pillars:
 * 1. Khiên Bảo Hộ Y Tế (Guardian Clinical Shield)
 * 2. Chữ Thập Cấp Cứu & Ngôi Sao Sự Sống (Emergency Cross)
 * 3. Mũi Tên La Bàn Không Gian 3D (3D Spatial Compass Vector)
 * 4. Sóng Nhịp Tim Giờ Vàng (Golden Hour ECG Lifeline)
 */

import React, { useState } from 'react';
import { ShieldCheck, Compass, Activity, HeartPulse, Sparkles, X } from 'lucide-react';

interface MedGuardLogoProps {
  isDarkTheme?: boolean;
}

export const MedGuardLogo: React.FC<MedGuardLogoProps> = ({ isDarkTheme = false }) => {
  const [showMeaningModal, setShowMeaningModal] = useState(false);

  return (
    <div className="relative flex items-center gap-3">
      {/* Interactive Emblem Button */}
      <button
        type="button"
        data-testid="medguard-brand-logo"
        onClick={() => setShowMeaningModal(!showMeaningModal)}
        title="Nhấn để xem ý nghĩa thiết kế biểu tượng MedGuard AI"
        className="group relative flex items-center gap-3 text-left focus:outline-none cursor-pointer"
      >
        {/* Custom Multi-Layered SVG Emblem */}
        <div className="relative w-11 h-11 sm:w-12 sm:h-12 rounded-2xl flex items-center justify-center transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:scale-105 shadow-[0_8px_22px_-4px_rgba(2,132,199,0.45)]">
          <svg
            viewBox="0 0 64 64"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className="w-full h-full overflow-visible"
            aria-label="Biểu tượng MedGuard AI: Khiên Bảo Hộ Y Tế, Nhịp Tim Sinh Tồn và La Bàn Dẫn Đường 3D"
          >
            <defs>
              {/* Outer Clinical Guardian Shield Gradient */}
              <linearGradient id="mgShieldBg" x1="6" y1="4" x2="58" y2="60" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stopColor="#0284C7" />
                <stop offset="52%" stopColor="#0369A1" />
                <stop offset="100%" stopColor="#0F172A" />
              </linearGradient>

              {/* Inner 3D Facet Rim Gradient */}
              <linearGradient id="mgShieldRim" x1="12" y1="8" x2="52" y2="56" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stopColor="#38BDF8" stopOpacity="0.9" />
                <stop offset="50%" stopColor="#2DD4BF" stopOpacity="0.5" />
                <stop offset="100%" stopColor="#0284C7" stopOpacity="0.2" />
              </linearGradient>

              {/* 3D Compass Navigation Vector Gradient */}
              <linearGradient id="mgNavArrow" x1="32" y1="12" x2="32" y2="46" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stopColor="#2DD4BF" />
                <stop offset="100%" stopColor="#0EA5E9" />
              </linearGradient>

              {/* Golden Hour Emergency Pulse Accent */}
              <linearGradient id="mgEcgPulse" x1="10" y1="36" x2="54" y2="36" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stopColor="#F43F5E" />
                <stop offset="50%" stopColor="#FBBF24" />
                <stop offset="100%" stopColor="#34D399" />
              </linearGradient>
            </defs>

            {/* Base Rounded Squircle-Shield Chassis */}
            <rect
              x="2"
              y="2"
              width="60"
              height="60"
              rx="16"
              fill="url(#mgShieldBg)"
            />

            {/* 3D Isometric Spatial Grid Ring */}
            <ellipse
              cx="32"
              cy="45"
              rx="19"
              ry="6.5"
              stroke="#38BDF8"
              strokeOpacity="0.32"
              strokeWidth="1.4"
              strokeDasharray="3 2.5"
            />

            {/* Layer 1: Guardian Clinical Shield Contour */}
            <path
              d="M32 8L50 15.2V30.8C50 43.2 42.1 52.6 32 56.5C21.9 52.6 14 43.2 14 30.8V15.2L32 8Z"
              fill="#0F172A"
              fillOpacity="0.55"
              stroke="url(#mgShieldRim)"
              strokeWidth="2"
              strokeLinejoin="round"
            />

            {/* Layer 2: Subtle Medical Cross of Life in Background */}
            <path
              d="M28.5 16H35.5V23H42.5V30H35.5V37H28.5V30H21.5V23H28.5V16Z"
              fill="#0EA5E9"
              fillOpacity="0.22"
            />

            {/* Layer 3: 3D Navigation Compass Vector Pin (Pointing Forward/North) */}
            <path
              d="M32 13L43 39L32 33.2L21 39L32 13Z"
              fill="url(#mgNavArrow)"
              stroke="#FFFFFF"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
            {/* 3D Left/Right Facet Shading on Navigation Arrow */}
            <path
              d="M32 13L43 39L32 33.2V13Z"
              fill="#0284C7"
              fillOpacity="0.38"
            />

            {/* Emergency Crimson Cross Emblem at the Heart of the Compass */}
            <path
              d="M30.4 21.5H33.6V24.4H36.5V27.6H33.6V30.5H30.4V27.6H27.5V24.4H30.4V21.5Z"
              fill="#FFFFFF"
            />

            {/* Layer 4: Golden Hour ECG Heartbeat Lifeline Wave */}
            <path
              d="M11 41H21.5L24.8 35.5L28.5 47.5L32.8 31.5L36.5 43.5L39.5 39H53"
              stroke="url(#mgEcgPulse)"
              strokeWidth="2.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            {/* Live GPS Satellite Beacon Dot */}
            <circle cx="49" cy="14" r="3.5" fill="#F43F5E" stroke="#FFFFFF" strokeWidth="1.5" />
          </svg>

          {/* Subtle Live Status Dot */}
          <span className="absolute -top-1 -right-1 flex h-3.5 w-3.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-rose-500 border-2 border-white" />
          </span>
        </div>

        {/* Brand Typography & Meaning Trigger */}
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-baseline gap-1">
              <span
                className={`text-lg sm:text-xl font-extrabold tracking-tight ${
                  isDarkTheme ? 'text-white' : 'text-slate-900'
                }`}
              >
                MedGuard
              </span>
              <span className="text-lg sm:text-xl font-extrabold tracking-tight bg-gradient-to-r from-sky-600 to-teal-600 bg-clip-text text-transparent">
                AI 3D
              </span>
            </div>

            <span
              className={`px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wide transition-colors flex items-center gap-1 ${
                isDarkTheme
                  ? 'bg-sky-500/15 text-sky-300 border border-sky-500/30 group-hover:bg-sky-500/25'
                  : 'bg-sky-50 text-sky-700 border border-sky-200 group-hover:bg-sky-100'
              }`}
            >
              <Sparkles className="w-2.5 h-2.5 text-sky-500" />
              <span>Ý nghĩa Logo</span>
            </span>
          </div>

          <p
            className={`text-[11px] font-medium hidden sm:block ${
              isDarkTheme ? 'text-slate-400' : 'text-slate-500'
            }`}
          >
            Chỉ đường Y tế 3D Real-Time • Điều phối Cấp Cứu 115 &amp; Đặt khám BookingCare
          </p>
        </div>
      </button>

      {/* Brand Symbolism Popover Card */}
      {showMeaningModal && (
        <div
          data-testid="logo-meaning-popover"
          className={`absolute top-14 left-0 z-50 w-[340px] sm:w-[410px] rounded-2xl p-4 shadow-2xl border animate-slide-down ${
            isDarkTheme
              ? 'bg-slate-900 border-slate-700 text-slate-100'
              : 'bg-white border-slate-200 text-slate-800'
          }`}
        >
          <div className="flex items-center justify-between border-b border-slate-200/70 dark:border-slate-800 pb-2.5 mb-3">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-sky-600" />
              <h3 className="text-xs font-extrabold uppercase tracking-wider text-sky-700 dark:text-sky-400">
                Ý Nghĩa Biểu Tượng MedGuard AI 3D
              </h3>
            </div>
            <button
              type="button"
              onClick={() => setShowMeaningModal(false)}
              className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer"
              aria-label="Đóng hộp thoại ý nghĩa logo"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="space-y-2.5 text-xs">
            <div className="flex items-start gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-sky-50 text-sky-600 border border-sky-200 flex items-center justify-center shrink-0 mt-0.5">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <div>
                <div className="font-bold text-slate-900 dark:text-white">
                  1. Khiên Bảo Hộ Lâm Sàng (Guardian Shield)
                </div>
                <p className="text-[11px] text-slate-600 dark:text-slate-300 leading-relaxed">
                  Khung khiên đa diện bảo vệ an toàn tính mạng bệnh nhân và xác thực độ uy tín của bệnh viện.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-teal-50 text-teal-600 border border-teal-200 flex items-center justify-center shrink-0 mt-0.5">
                <Compass className="w-4 h-4" />
              </div>
              <div>
                <div className="font-bold text-slate-900 dark:text-white">
                  2. Cánh La Bàn Không Gian 3D (3D Spatial Vector)
                </div>
                <p className="text-[11px] text-slate-600 dark:text-slate-300 leading-relaxed">
                  Mũi tên 3D hai mặt vát hướng thẳng về phía trước, biểu trưng cho thuật toán dẫn đường 3D chính xác tới tận cổng viện.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-rose-50 text-rose-600 border border-rose-200 flex items-center justify-center shrink-0 mt-0.5">
                <HeartPulse className="w-4 h-4" />
              </div>
              <div>
                <div className="font-bold text-slate-900 dark:text-white">
                  3. Sóng Điện Tim Giờ Vàng (Golden Hour ECG Line)
                </div>
                <p className="text-[11px] text-slate-600 dark:text-slate-300 leading-relaxed">
                  Dải sóng nhịp tim chuyển sắc Đỏ – Vàng – Ngọc lục bảo thể hiện hành trình chuyển trạng thái từ cấp cứu nguy kịch sang an toàn.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-amber-50 text-amber-600 border border-amber-200 flex items-center justify-center shrink-0 mt-0.5">
                <Activity className="w-4 h-4" />
              </div>
              <div>
                <div className="font-bold text-slate-900 dark:text-white">
                  4. Vòng Quỹ Đạo Địa Hình D3 (Topographic Orbit)
                </div>
                <p className="text-[11px] text-slate-600 dark:text-slate-300 leading-relaxed">
                  Vòng elip không gian dưới chân mũi tên tượng trưng cho việc phân tích độ cao địa hình, độ dốc và mật độ giao thông thời gian thực.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
