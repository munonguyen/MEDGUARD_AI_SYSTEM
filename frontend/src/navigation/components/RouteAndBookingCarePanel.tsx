/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * MedGuard AI - Multi-Condition Route Assessment, Ambulance Provider Fleet & BookingCare Dispatch Panel
 */

import React from 'react';
import {
  Bike,
  Car,
  CloudRain,
  Compass,
  Gauge,
  Hospital,
  PhoneCall,
  ShieldCheck,
  Siren,
  Star,
  Sun,
  Waves,
} from 'lucide-react';
import {
  AMBULANCE_PROVIDERS,
  DEFAULT_BOOKINGCARE_SLOTS,
  OperationalScenarioType,
  RouteConditionAssessment,
  TransportVehicleType,
  WeatherConditionType,
} from '../services/bookingCareDispatchEngine';
import type { DualRoute } from '../services/routingService';

interface RouteAndBookingCarePanelProps {
  assessment: RouteConditionAssessment;
  primaryRoute: DualRoute;
  alternativeRoute: DualRoute;
  selectedRouteId: string;
  onChangeScenario: (scenario: OperationalScenarioType) => void;
  onChangeVehicle: (vehicle: TransportVehicleType) => void;
  onChangeWeather: (weather: WeatherConditionType) => void;
  onChangeAmbulanceProvider: (providerId: string) => void;
  onChangeAppointmentSlot: (slotId: string) => void;
  onSelectRoute: (routeId: string) => void;
  onCallHotline: (phone: string) => void;
}

export const RouteAndBookingCarePanel: React.FC<RouteAndBookingCarePanelProps> = ({
  assessment,
  primaryRoute,
  alternativeRoute,
  selectedRouteId,
  onChangeScenario,
  onChangeVehicle,
  onChangeWeather,
  onChangeAmbulanceProvider,
  onChangeAppointmentSlot,
  onSelectRoute,
  onCallHotline,
}) => {
  const {
    overallRouteScore,
    scenarioType,
    vehicleType,
    weatherCondition,
    selectedAmbulanceProvider,
    dispatchWaitMinutes,
    roadTravelMinutes,
    gateAndParkingMinutes,
    elevatorAndWalkMinutes,
    totalDoorToDoctorMinutes,
    appointmentSlot,
    slotBufferMinutes,
    slotStatus,
    slotRecommendation,
    gateLogistics,
    conditionFactors,
    algorithmSummary,
  } = assessment;

  const scoreColor =
    overallRouteScore >= 85
      ? 'text-emerald-700 border-emerald-200 bg-emerald-50'
      : overallRouteScore >= 68
      ? 'text-amber-700 border-amber-200 bg-amber-50'
      : 'text-rose-700 border-rose-200 bg-rose-50';

  return (
    <section
      aria-label="Phân Tích Nghiệp Vụ Phương Tiện, Thuật Toán Đường Đi & Điều Phối BookingCare"
      className="bg-white border border-slate-200/90 rounded-3xl p-4 sm:p-6 shadow-[0_8px_30px_rgb(15,23,42,0.06)] space-y-5 text-slate-900"
    >
      {/* 1. HEADER & 2 CORE HEALTHCARE SCENARIO SWITCHER (NGHIỆP VỤ CỐT LÕI) */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-slate-200/80 pb-4">
        <div className="flex items-start sm:items-center gap-3.5">
          <div
            className={`w-14 h-14 rounded-2xl border flex flex-col items-center justify-center shrink-0 tabular-nums shadow-2xs ${scoreColor}`}
          >
            <span className="text-xl font-black leading-none">{overallRouteScore}</span>
            <span className="text-[10px] font-bold opacity-80 mt-0.5">/100đ</span>
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-extrabold uppercase tracking-wider text-sky-700">
                Thuật Toán Đánh Giá Đa Điều Kiện Real-Time (OSRM • BPR • ISO 2631-1)
              </span>
              <span className="text-slate-300">•</span>
              <span className="text-xs font-semibold text-slate-500 tabular-nums">
                Chi phí tổng hợp: {algorithmSummary.compositeCostIndex}
              </span>
            </div>
            <h2 className="text-base sm:text-lg font-extrabold text-slate-900 mt-0.5">
              Phân Tích Nghiệp Vụ Phương Tiện, Điều Kiện Đường Đi &amp; Đồng Bộ Ca Khám BookingCare
            </h2>
          </div>
        </div>

        {/* 2 Core Operational Scenarios */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 bg-slate-100 p-1.5 rounded-2xl border border-slate-200/80 shrink-0">
          <button
            type="button"
            data-testid="scenario-ambulance-dispatch"
            onClick={() => onChangeScenario('AMBULANCE_DISPATCH')}
            className={`px-3.5 py-2 rounded-xl text-xs font-extrabold transition-all flex items-center gap-2.5 text-left cursor-pointer ${
              scenarioType === 'AMBULANCE_DISPATCH'
                ? 'bg-rose-600 text-white shadow-sm'
                : 'text-slate-600 hover:text-slate-900 hover:bg-white/60'
            }`}
          >
            <Siren className="w-4 h-4 shrink-0" />
            <div>
              <div>Nghiệp vụ 1: Điều Phối Xe Cấp Cứu</div>
              <div className="text-[10px] font-medium opacity-90">
                Hãng Xe Cứu Thương • Vào Cổng Cấp Cứu
              </div>
            </div>
          </button>

          <button
            type="button"
            data-testid="scenario-bookingcare-visit"
            onClick={() => onChangeScenario('BOOKINGCARE_HOSPITAL_VISIT')}
            className={`px-3.5 py-2 rounded-xl text-xs font-extrabold transition-all flex items-center gap-2.5 text-left cursor-pointer ${
              scenarioType === 'BOOKINGCARE_HOSPITAL_VISIT'
                ? 'bg-sky-600 text-white shadow-sm'
                : 'text-slate-600 hover:text-slate-900 hover:bg-white/60'
            }`}
          >
            <Hospital className="w-4 h-4 shrink-0" />
            <div>
              <div>Nghiệp vụ 2: Đi Khám (BookingCare)</div>
              <div className="text-[10px] font-medium opacity-90">
                Xe Máy / Ô Tô • Tính giờ gửi xe &amp; khám
              </div>
            </div>
          </button>
        </div>
      </div>

      {/* 2. SCENARIO-SPECIFIC VEHICLE / AMBULANCE FLEET & WEATHER CONTROLS */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left 7 Cols: Ambulance Fleet Selector OR Patient Vehicle + BookingCare Slot Selector */}
        <div className="lg:col-span-7 bg-slate-50/70 border border-slate-200/90 rounded-2xl p-4 space-y-3.5">
          {scenarioType === 'AMBULANCE_DISPATCH' ? (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <span className="text-[10px] font-extrabold uppercase tracking-wider text-rose-600">
                    ĐIỀU PHỐI ĐỘI XE CẤP CỨU CHUYÊN DỤNG (EMS PROVIDER FLEET)
                  </span>
                  <h3 className="text-sm sm:text-base font-extrabold text-slate-900">
                    Chọn Hãng Xe Cấp Cứu Uy Tín (Tự động bật Luồng Xanh &amp; Cổng Băng Ca)
                  </h3>
                </div>
                <span className="text-[11px] font-semibold text-slate-500">
                  Khổ đường ≥ 3.5m • Chống xóc ISO 2631-1
                </span>
              </div>

              <div className="grid grid-cols-1 gap-2.5">
                {AMBULANCE_PROVIDERS.map((prov) => {
                  const isSelected = selectedAmbulanceProvider?.id === prov.id;
                  return (
                    <div
                      key={prov.id}
                      data-testid={`ambulance-provider-${prov.id}`}
                      onClick={() => onChangeAmbulanceProvider(prov.id)}
                      className={`p-3.5 rounded-2xl border transition-all cursor-pointer flex flex-col gap-2 ${
                        isSelected
                          ? 'bg-rose-50/60 border-rose-500 shadow-xs ring-1 ring-rose-500/20'
                          : 'bg-white hover:border-slate-300 border-slate-200/90'
                      }`}
                    >
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-xs sm:text-sm font-extrabold text-slate-900">
                              {prov.name}
                            </span>
                            <span className="text-[11px] font-bold text-amber-600 flex items-center gap-0.5 tabular-nums">
                              <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />
                              {prov.rating.toFixed(1)} ({prov.reviewsCount.toLocaleString()} đánh giá)
                            </span>
                          </div>
                          <div className="text-[11px] text-sky-700 font-semibold mt-0.5">
                            {prov.vehicleSpec} • {prov.medicalCrew}
                          </div>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          <span className="px-2.5 py-1 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-extrabold tabular-nums">
                            Đón sau ~{prov.dispatchEtaMinutes} phút
                          </span>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              onCallHotline(prov.hotline);
                            }}
                            className="px-2.5 py-1 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold flex items-center gap-1 cursor-pointer transition-colors"
                          >
                            <PhoneCall className="w-3 h-3" />
                            <span>Gọi {prov.hotline}</span>
                          </button>
                        </div>
                      </div>

                      <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-600">
                        {prov.equipmentHighlights.map((eq, i) => (
                          <span
                            key={i}
                            className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 font-medium"
                          >
                            ✓ {eq}
                          </span>
                        ))}
                      </div>

                      {/* Verified Patient Review of this Ambulance Provider */}
                      <div className="bg-slate-50 border border-slate-200/80 rounded-xl p-2.5 text-[11px] text-slate-600 flex items-start gap-2">
                        <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                        <div>
                          <span className="font-bold text-slate-900">
                            {prov.featuredReview.author}
                          </span>{' '}
                          <span className="text-slate-500">
                            ({prov.featuredReview.role} • {prov.featuredReview.time}):
                          </span>{' '}
                          <span className="italic text-slate-700">
                            &ldquo;{prov.featuredReview.comment}&rdquo;
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          ) : (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <span className="text-[10px] font-extrabold uppercase tracking-wider text-sky-700">
                    PHƯƠNG TIỆN CÁ NHÂN &amp; ĐỒNG BỘ KHUNG GIỜ HẸN KHÁM BOOKINGCARE
                  </span>
                  <h3 className="text-sm sm:text-base font-extrabold text-slate-900">
                    Chọn Phương Tiện Đi Khám &amp; Ca Khám Đã Đặt Để Tính Chính Xác Cổng Vào
                  </h3>
                </div>
              </div>

              {/* Motorcycle vs Car/Taxi Selector */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                <button
                  type="button"
                  data-testid="vehicle-btn-motorcycle"
                  onClick={() => onChangeVehicle('motorcycle')}
                  className={`p-3.5 rounded-2xl border text-left transition-all cursor-pointer flex items-start gap-3 ${
                    vehicleType === 'motorcycle'
                      ? 'bg-sky-50/80 border-sky-500 shadow-xs ring-1 ring-sky-500/20'
                      : 'bg-white hover:border-slate-300 border-slate-200/90'
                  }`}
                >
                  <div className="w-10 h-10 rounded-xl bg-sky-100 text-sky-700 flex items-center justify-center shrink-0">
                    <Bike className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="text-xs sm:text-sm font-extrabold text-slate-900">
                      Xe Máy Cá Nhân (Phổ biến nhất)
                    </div>
                    <p className="text-[11px] text-slate-600 mt-0.5 leading-snug">
                      Linh hoạt né kẹt xe ngã tư, tự động tránh tuyến ngập nước &gt;15cm, dẫn vào{' '}
                      <strong className="text-sky-700">Cổng Số 2 (Bãi xe máy sát khu khám)</strong>.
                    </p>
                  </div>
                </button>

                <button
                  type="button"
                  data-testid="vehicle-btn-car_taxi"
                  onClick={() => onChangeVehicle('car_taxi')}
                  className={`p-3.5 rounded-2xl border text-left transition-all cursor-pointer flex items-start gap-3 ${
                    vehicleType === 'car_taxi'
                      ? 'bg-sky-50/80 border-sky-500 shadow-xs ring-1 ring-sky-500/20'
                      : 'bg-white hover:border-slate-300 border-slate-200/90'
                  }`}
                >
                  <div className="w-10 h-10 rounded-xl bg-teal-100 text-teal-700 flex items-center justify-center shrink-0">
                    <Car className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="text-xs sm:text-sm font-extrabold text-slate-900">
                      Ô Tô Cá Nhân / Taxi Đặt Khám
                    </div>
                    <p className="text-[11px] text-slate-600 mt-0.5 leading-snug">
                      Phù hợp đưa người già/trẻ nhỏ/thai phụ đi khám. Dẫn vào{' '}
                      <strong className="text-teal-700">Sảnh Drop-off có mái che &amp; xe lăn</strong>{' '}
                      trước khi xuống hầm B1.
                    </p>
                  </div>
                </button>
              </div>

              {/* BookingCare Appointment Slot Selector */}
              <div className="space-y-2 pt-1">
                <div className="text-xs font-bold text-slate-700">
                  Ca khám BookingCare đang đồng bộ thời gian thực:
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  {DEFAULT_BOOKINGCARE_SLOTS.map((slot) => {
                    const isSelected = appointmentSlot.id === slot.id;
                    return (
                      <button
                        key={slot.id}
                        type="button"
                        data-testid={`booking-slot-${slot.id}`}
                        onClick={() => onChangeAppointmentSlot(slot.id)}
                        className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                          isSelected
                            ? 'bg-sky-50 border-sky-500 ring-1 ring-sky-500/20'
                            : 'bg-white hover:border-slate-300 border-slate-200'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-1">
                          <span className="text-[10px] font-extrabold text-sky-700">
                            {slot.bookingCode}
                          </span>
                          <span className="text-[10px] font-bold text-amber-600 tabular-nums">
                            Còn {slot.MinutesFromNow}p
                          </span>
                        </div>
                        <div className="text-xs font-bold text-slate-900 truncate mt-0.5">
                          {slot.doctorName}
                        </div>
                        <div className="text-[10px] text-slate-500 truncate">
                          {slot.departmentName}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </>
          )}

          {/* Weather & Road Surface Condition Simulator */}
          <div className="pt-2.5 border-t border-slate-200/80 flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs font-bold text-slate-700">
              Điều kiện thời tiết &amp; mặt đường:
            </span>
            <div className="flex flex-wrap items-center gap-1.5">
              {[
                { id: 'clear' as const, label: 'Trời quang • Khô ráo', icon: Sun },
                { id: 'heavy_rain' as const, label: 'Mưa lớn • Trơn trượt', icon: CloudRain },
                {
                  id: 'urban_flood_warning' as const,
                  label: 'Triều cường • Ngập cục bộ',
                  icon: Waves,
                },
              ].map((w) => {
                const Icon = w.icon;
                const active = weatherCondition === w.id;
                return (
                  <button
                    key={w.id}
                    type="button"
                    data-testid={`weather-btn-${w.id}`}
                    onClick={() => onChangeWeather(w.id)}
                    className={`px-2.5 py-1.5 rounded-xl text-xs font-bold border flex items-center gap-1.5 transition-all cursor-pointer ${
                      active
                        ? 'bg-amber-50 border-amber-400 text-amber-800 shadow-2xs'
                        : 'bg-white border-slate-200 text-slate-600 hover:text-slate-900 hover:border-slate-300'
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    <span>{w.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right 5 Cols: BookingCare Door-to-Doctor Micro-Logistics & Gate Directive */}
        <div className="lg:col-span-5 bg-slate-50/70 border border-slate-200/90 rounded-2xl p-4 flex flex-col justify-between gap-3.5">
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[10px] font-extrabold uppercase tracking-wider text-teal-700">
                PHÂN TÍCH VI HẬU CẦN BỆNH VIỆN (DOOR-TO-DOCTOR ETA)
              </span>
              <span
                className={`px-2 py-0.5 rounded-md text-[10px] font-extrabold uppercase ${
                  slotStatus === 'ON_TIME_SAFE'
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    : slotStatus === 'TIGHT_BUFFER'
                    ? 'bg-amber-50 text-amber-700 border border-amber-200'
                    : 'bg-rose-50 text-rose-700 border border-rose-200'
                }`}
              >
                {slotStatus === 'ON_TIME_SAFE'
                  ? `Kịp giờ hẹn (+${slotBufferMinutes}p dự phòng)`
                  : slotStatus === 'TIGHT_BUFFER'
                  ? `Sát giờ hẹn (+${slotBufferMinutes}p)`
                  : `Nguy cơ trễ hẹn (${slotBufferMinutes}p)`}
              </span>
            </div>

            {/* Time Breakdown Bar */}
            <div className="grid grid-cols-4 gap-2 text-center">
              <div className="bg-white border border-slate-200/90 rounded-xl p-2">
                <div className="text-[10px] text-slate-500 font-medium">
                  {scenarioType === 'AMBULANCE_DISPATCH' ? 'Điều xe 115' : 'Trên đường'}
                </div>
                <div className="text-sm font-black text-sky-700 tabular-nums mt-0.5">
                  {scenarioType === 'AMBULANCE_DISPATCH'
                    ? `${dispatchWaitMinutes}p + ${roadTravelMinutes}p`
                    : `${roadTravelMinutes} phút`}
                </div>
              </div>

              <div className="bg-white border border-slate-200/90 rounded-xl p-2">
                <div className="text-[10px] text-slate-500 font-medium">Qua cổng/Gửi xe</div>
                <div className="text-sm font-black text-amber-600 tabular-nums mt-0.5">
                  +{gateAndParkingMinutes} phút
                </div>
              </div>

              <div className="bg-white border border-slate-200/90 rounded-xl p-2">
                <div className="text-[10px] text-slate-500 font-medium">Thang máy/Đi bộ</div>
                <div className="text-sm font-black text-slate-700 tabular-nums mt-0.5">
                  +{elevatorAndWalkMinutes} phút
                </div>
              </div>

              <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-2">
                <div className="text-[10px] text-emerald-800 font-bold">Tổng tới Bác sĩ</div>
                <div className="text-sm font-black text-emerald-700 tabular-nums mt-0.5">
                  {totalDoorToDoctorMinutes} phút
                </div>
              </div>
            </div>

            {/* Specific Hospital Gate & Parking Box */}
            <div className="bg-white border border-sky-200 rounded-xl p-3 space-y-1.5 shadow-2xs">
              <div className="text-[11px] font-extrabold text-sky-700 uppercase flex items-center gap-1.5">
                <Compass className="w-4 h-4 shrink-0" />
                <span>Chỉ Dẫn Cổng Vào &amp; Bãi Đỗ Chính Xác:</span>
              </div>
              <div className="text-xs sm:text-sm font-extrabold text-slate-900">
                {gateLogistics.recommendedGateName}
              </div>
              <div className="text-xs text-teal-700 font-bold">
                • {gateLogistics.parkingOrDropoffType}
              </div>
              <p className="text-[11px] text-slate-600 leading-relaxed">
                {gateLogistics.notes}
              </p>
            </div>

            {/* BookingCare Slot Recommendation */}
            <div
              className={`rounded-xl border p-3 text-xs leading-relaxed ${
                slotStatus === 'LATE_RISK'
                  ? 'bg-rose-50 border-rose-200 text-rose-900'
                  : 'bg-white border-slate-200 text-slate-700'
              }`}
            >
              <strong className="text-slate-900">Đánh giá khả thi lịch hẹn:</strong>{' '}
              {slotRecommendation}
            </div>
          </div>

          {/* Dual Corridor Selector Buttons */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
            <button
              type="button"
              onClick={() => onSelectRoute(alternativeRoute.id)}
              className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                selectedRouteId === alternativeRoute.id
                  ? 'bg-sky-50 border-sky-500 text-slate-900 ring-1 ring-sky-500/20'
                  : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
              }`}
            >
              <div className="flex items-center justify-between text-xs font-extrabold">
                <span className="text-sky-700">Tuyến Tránh Ưu Tiên</span>
                <span className="tabular-nums text-slate-900">{alternativeRoute.duration_minutes}p</span>
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5 tabular-nums">
                {alternativeRoute.distance_km} km • Mặt đường êm, né ngập
              </div>
            </button>

            <button
              type="button"
              onClick={() => onSelectRoute(primaryRoute.id)}
              className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                selectedRouteId === primaryRoute.id
                  ? 'bg-sky-50 border-sky-500 text-slate-900 ring-1 ring-sky-500/20'
                  : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
              }`}
            >
              <div className="flex items-center justify-between text-xs font-extrabold">
                <span className="text-slate-800">Tuyến Trục Chính Nội Đô</span>
                <span className="tabular-nums text-slate-900">{primaryRoute.duration_minutes}p</span>
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5 tabular-nums">
                {primaryRoute.distance_km} km • Nhiều giao cắt đèn đỏ
              </div>
            </button>
          </div>
        </div>
      </div>

      {/* 3. 5-FACTOR ALGORITHMIC ROAD CONDITION MATRIX */}
      <div className="space-y-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-xs font-extrabold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
            <Gauge className="w-4 h-4 text-sky-600" />
            <span>
              Ma Trận 5 Thuật Toán Đánh Giá Điều Kiện Trên Đường Đi (Theo Thời Gian Thực &amp; Phương Tiện)
            </span>
          </div>
          <span className="text-[11px] font-semibold text-slate-500 tabular-nums">
            BPR V/C = {algorithmSummary.bprCongestionRatio} • Rung chấn ISO ={' '}
            {algorithmSummary.isoVibrationRms} m/s² • Rủi ro ngập ={' '}
            {algorithmSummary.floodRiskPercent}%
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5">
          {conditionFactors.map((factor) => {
            const badgeStyle =
              factor.severity === 'optimal'
                ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                : factor.severity === 'caution'
                ? 'border-amber-200 bg-amber-50 text-amber-700'
                : 'border-rose-200 bg-rose-50 text-rose-700';

            return (
              <div
                key={factor.id}
                className="bg-slate-50/70 border border-slate-200/90 rounded-2xl p-3.5 flex flex-col justify-between gap-2"
              >
                <div className="space-y-1">
                  <div className="flex items-center justify-between gap-1">
                    <span className="text-[10px] font-bold text-sky-700 truncate">
                      {factor.algorithmSource}
                    </span>
                    <span className="text-xs font-black text-slate-900 tabular-nums">
                      {factor.score}/100
                    </span>
                  </div>
                  <h4 className="text-xs font-extrabold text-slate-900 leading-snug">
                    {factor.name}
                  </h4>
                  <div
                    className={`inline-block px-2 py-0.5 rounded-md border text-[10px] font-bold ${badgeStyle}`}
                  >
                    {factor.statusLabel}
                  </div>
                </div>

                <div className="space-y-1 pt-2 border-t border-slate-200/80">
                  <div className="text-[11px] font-bold text-slate-800 tabular-nums">
                    {factor.metricValue}
                  </div>
                  <p className="text-[10px] text-slate-500 leading-relaxed">
                    {factor.clinicalImpact}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};
