/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * MedGuard AI - Emergency Golden Hour & Clinical Readiness Monitor
 */

import React from 'react';
import { AlertCircle, Clock, ShieldAlert, PhoneCall, Bed, Zap } from 'lucide-react';
import type { MedicalFacility } from '../data/medicalPoiRegistry';
import { evaluateGoldenHour } from '../utils/navigationMath';

interface GoldenHourMonitorProps {
  facility: MedicalFacility;
  emergencyCategory: 'stroke' | 'cardiac' | 'trauma' | 'pediatrics' | 'general';
  elapsedMinutes: number;
  onCallHotline: (phone: string) => void;
}

export const GoldenHourMonitor: React.FC<GoldenHourMonitorProps> = ({
  facility,
  emergencyCategory,
  elapsedMinutes,
  onCallHotline,
}) => {
  const assessment = evaluateGoldenHour(emergencyCategory, elapsedMinutes);

  const getUrgencyBadge = () => {
    if (assessment.urgencyLevel === 'CRITICAL') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-extrabold bg-rose-600 text-white shadow-xs">
          <ShieldAlert className="w-3.5 h-3.5" />
          BÁO ĐỘNG ĐỎ CẤP CỨU
        </span>
      );
    }
    if (assessment.urgencyLevel === 'WARNING') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-amber-500 text-white shadow-xs">
          <AlertCircle className="w-3.5 h-3.5" />
          CỬA SỔ VÀNG ĐANG ĐẾM NGƯỢC
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-600 text-white">
        <Zap className="w-3.5 h-3.5" />
        TIẾP NHẬN CẤP CỨU 24/7
      </span>
    );
  };

  return (
    <div className="bg-white border border-rose-200/90 rounded-3xl p-4 sm:p-5 text-slate-900 shadow-[0_8px_30px_rgb(15,23,42,0.05)] transition-all">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200/80 pb-3">
        <div className="flex flex-wrap items-center gap-2.5">
          {getUrgencyBadge()}
          <span className="text-xs font-bold text-slate-700">
            {assessment.condition}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => onCallHotline(facility.emergencyHotline)}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold transition-all shadow-xs active:scale-95 cursor-pointer"
            title={`Gọi ngay Khoa Cấp Cứu ${facility.emergencyHotline}`}
          >
            <PhoneCall className="w-3.5 h-3.5" />
            <span>Gọi Cấp Cứu: {facility.emergencyHotline}</span>
          </button>
        </div>
      </div>

      {/* Countdown and recommendation */}
      <div className="mt-3.5 grid grid-cols-1 md:grid-cols-12 gap-3.5 items-center">
        <div className="md:col-span-4 bg-rose-50/70 rounded-2xl p-3 border border-rose-200/80 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-rose-100 border border-rose-200 flex items-center justify-center text-rose-600 shrink-0">
            <Clock className="w-5 h-5 animate-spin-slow" />
          </div>
          <div className="tabular-nums">
            <div className="text-[10px] text-rose-700 font-bold uppercase tracking-wider">
              Thời gian Giờ Vàng còn lại
            </div>
            <div className="text-lg md:text-xl font-black text-rose-600 tracking-tight">
              {assessment.remainingMinutes}{' '}
              <span className="text-xs font-semibold text-slate-600">phút</span>
            </div>
            <div className="text-[10px] text-slate-500">
              Giới hạn chuẩn lâm sàng: {assessment.maxWindowMinutes}p
            </div>
          </div>
        </div>

        <div className="md:col-span-8 flex flex-col justify-between gap-2">
          <p className="text-xs leading-relaxed text-slate-700">
            {assessment.recommendation}
          </p>
          <div className="flex flex-wrap items-center gap-2 text-[11px] tabular-nums">
            <span className="inline-flex items-center gap-1 bg-sky-50 border border-sky-200/70 px-2.5 py-0.5 rounded-lg text-sky-800 font-bold">
              <Bed className="w-3.5 h-3.5 text-sky-600" />
              {facility.icuBedsAvailable} Giường ICU sẵn sàng
            </span>
            <span className="bg-emerald-50 border border-emerald-200/70 px-2.5 py-0.5 rounded-lg text-emerald-800 font-bold">
              {facility.ambulanceBaysOpen} Cổng cấp cứu thông thoáng
            </span>
            <span className="bg-amber-50 border border-amber-200/70 px-2.5 py-0.5 rounded-lg text-amber-800 font-bold">
              {facility.doctorOnDutyCount} Bác sĩ cấp cứu trực
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
