/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * MedGuard AI - Emergency Clinical Triage & Symptom Router
 */

import React, { useState } from 'react';
import {
  Stethoscope,
  Heart,
  Brain,
  Activity,
  Baby,
  Pill,
  Navigation,
  Sparkles,
} from 'lucide-react';
import type { MedicalFacility } from '../data/medicalPoiRegistry';
import { MEDICAL_FACILITIES } from '../data/medicalPoiRegistry';

interface ClinicalTriageDrawerProps {
  currentCity: 'hcm' | 'hanoi' | 'danang';
  onTriageSelectFacility: (
    facility: MedicalFacility,
    emergencyCategory: 'stroke' | 'cardiac' | 'trauma' | 'pediatrics' | 'general'
  ) => void;
}

interface SymptomPreset {
  id: string;
  title: string;
  icon: React.ElementType;
  description: string;
  category: 'stroke' | 'cardiac' | 'trauma' | 'pediatrics' | 'general' | 'pharmacy_24h';
  facilityCategory: 'stroke' | 'cardiac' | 'trauma' | 'pediatrics' | 'general';
  urgency: 'CRITICAL' | 'HIGH' | 'MODERATE';
}

const SYMPTOM_PRESETS: SymptomPreset[] = [
  {
    id: 'stroke-fast',
    title: 'Nghi ngờ Đột quỵ Não (FAST)',
    icon: Brain,
    description: 'Méo miệng, nói đớ, yếu liệt một bên tay chân đột ngột. Cần DSA & tiêu sợi huyết.',
    category: 'stroke',
    facilityCategory: 'stroke',
    urgency: 'CRITICAL',
  },
  {
    id: 'cardiac-infarction',
    title: 'Đau thắt ngực dữ dội / Nghi nhồi máu',
    icon: Heart,
    description: 'Đau ngực như bị đè ép, lan ra vai/hàm, vã mồ hôi lạnh, khó thở. Cần Cathlab khẩn.',
    category: 'cardiac',
    facilityCategory: 'cardiac',
    urgency: 'CRITICAL',
  },
  {
    id: 'pediatric-emergency',
    title: 'Cấp cứu Nhi khoa / Sốt co giật',
    icon: Baby,
    description: 'Trẻ sốt cao li bì, co giật, khó thở, tím tái môi đầu chi. Cần hồi sức sơ sinh.',
    category: 'pediatrics',
    facilityCategory: 'pediatrics',
    urgency: 'CRITICAL',
  },
  {
    id: 'severe-trauma',
    title: 'Đa chấn thương / Ngoại khoa',
    icon: Activity,
    description: 'Tai nạn ngã cao/giao thông, nghi gãy xương lớn, chấn thương đầu ngực hở.',
    category: 'trauma',
    facilityCategory: 'trauma',
    urgency: 'HIGH',
  },
  {
    id: 'night-pharmacy',
    title: 'Cần tìm Quầy thuốc 24/7 GPP',
    icon: Pill,
    description: 'Mua thuốc hạ sốt, đau bụng đêm, dị ứng, dung dịch bù điện giải, insulin lạnh.',
    category: 'pharmacy_24h',
    facilityCategory: 'general',
    urgency: 'MODERATE',
  },
];

export const ClinicalTriageDrawer: React.FC<ClinicalTriageDrawerProps> = ({
  currentCity,
  onTriageSelectFacility,
}) => {
  const [customSymptom, setCustomSymptom] = useState('');
  const [triageResult, setTriageResult] = useState<{
    facility: MedicalFacility;
    category: 'stroke' | 'cardiac' | 'trauma' | 'pediatrics' | 'general';
    analysis: string;
  } | null>(null);

  const handleSelectPreset = (preset: SymptomPreset) => {
    let best = MEDICAL_FACILITIES.find(
      (f) => f.city === currentCity && f.category === preset.category
    );
    if (!best) {
      best =
        MEDICAL_FACILITIES.find(
          (f) => f.city === currentCity && f.facilityType === 'hospital_emergency'
        ) || MEDICAL_FACILITIES[0];
    }

    setTriageResult({
      facility: best,
      category: preset.facilityCategory,
      analysis: `Hệ thống phân luồng MedGuard AI: Trường hợp "${preset.title}" được định tuyến tới ${best.name} — nơi có sẵn trang thiết bị chuyên khoa (${best.specialtyTag}) và đội ngũ cấp cứu trực chiến.`,
    });
  };

  const handleCustomSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!customSymptom.trim()) return;

    const query = customSymptom.toLowerCase();
    let targetCat: 'stroke' | 'cardiac' | 'trauma' | 'pediatrics' | 'general' = 'general';

    if (
      query.includes('đột quỵ') ||
      query.includes('tai biến') ||
      query.includes('méo') ||
      query.includes('liệt')
    ) {
      targetCat = 'stroke';
    } else if (
      query.includes('tim') ||
      query.includes('ngực') ||
      query.includes('nhồi máu') ||
      query.includes('khó thở')
    ) {
      targetCat = 'cardiac';
    } else if (
      query.includes('trẻ') ||
      query.includes('bé') ||
      query.includes('nhi') ||
      query.includes('co giật')
    ) {
      targetCat = 'pediatrics';
    } else if (
      query.includes('gãy') ||
      query.includes('ngã') ||
      query.includes('máu') ||
      query.includes('chấn thương')
    ) {
      targetCat = 'trauma';
    }

    let match = MEDICAL_FACILITIES.find(
      (f) => f.city === currentCity && f.category === targetCat
    );
    if (!match) {
      match = MEDICAL_FACILITIES.find((f) => f.city === currentCity) || MEDICAL_FACILITIES[0];
    }

    setTriageResult({
      facility: match,
      category: targetCat,
      analysis: `Phân tích lâm sàng: Triệu chứng được nhận diện phù hợp chuyên khoa ${targetCat.toUpperCase()}. Cơ sở tiếp nhận tối ưu nhất: ${match.name}.`,
    });
  };

  return (
    <div className="bg-white border border-slate-200/90 rounded-3xl p-4 sm:p-5 text-slate-900 shadow-[0_8px_30px_rgb(15,23,42,0.06)]">
      <div className="flex items-center gap-2.5 mb-3">
        <div className="w-9 h-9 rounded-xl bg-rose-50 border border-rose-200 text-rose-600 flex items-center justify-center">
          <Stethoscope className="w-4.5 h-4.5" />
        </div>
        <div>
          <h3 className="text-sm font-extrabold text-slate-900">
            Phân Luồng Triệu Chứng Cấp Cứu Lâm Sàng (Clinical Triage)
          </h3>
          <p className="text-[11px] text-slate-500">
            Chọn triệu chứng khẩn để hệ thống tự động chọn bệnh viện có đúng chuyên khoa và mở luồng dẫn đường 3D
          </p>
        </div>
      </div>

      {/* Preset Symptom Buttons */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5 my-3">
        {SYMPTOM_PRESETS.map((preset) => {
          const Icon = preset.icon;
          return (
            <button
              key={preset.id}
              type="button"
              onClick={() => handleSelectPreset(preset)}
              className="text-left p-3.5 rounded-2xl bg-slate-50/80 hover:bg-sky-50/60 border border-slate-200/90 hover:border-sky-400 transition-all group active:scale-[0.98] cursor-pointer"
            >
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  <Icon className="w-4 h-4 text-sky-600" />
                  <span className="text-xs font-extrabold text-slate-900 group-hover:text-sky-800">
                    {preset.title}
                  </span>
                </div>
                {preset.urgency === 'CRITICAL' && (
                  <span className="text-[9px] font-black bg-rose-600 text-white px-1.5 py-0.5 rounded">
                    TỐI KHẨN
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-600 line-clamp-2 leading-relaxed">
                {preset.description}
              </p>
            </button>
          );
        })}
      </div>

      {/* Custom Symptom Input */}
      <form onSubmit={handleCustomSubmit} className="flex gap-2 mt-2">
        <input
          type="text"
          value={customSymptom}
          onChange={(e) => setCustomSymptom(e.target.value)}
          placeholder="Hoặc nhập triệu chứng cụ thể (ví dụ: đau ngực dữ dội, ngất xỉu, sốt 40 độ...)"
          aria-label="Nhập triệu chứng cần phân luồng"
          className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-sky-500"
        />
        <button
          type="submit"
          className="px-4 py-2 bg-sky-600 hover:bg-sky-500 text-white rounded-xl font-bold text-xs flex items-center gap-1.5 transition-all cursor-pointer"
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>Phân tích</span>
        </button>
      </form>

      {/* Triage Decision Card */}
      {triageResult && (
        <div className="mt-4 p-4 rounded-2xl bg-sky-50 border border-sky-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-extrabold bg-sky-600 text-white px-2.5 py-0.5 rounded-full uppercase">
                Khuyến nghị MedGuard AI
              </span>
              <span className="text-xs font-extrabold text-slate-900">
                {triageResult.facility.name}
              </span>
            </div>
            <p className="text-xs text-slate-700 mt-1">{triageResult.analysis}</p>
          </div>
          <button
            type="button"
            onClick={() => onTriageSelectFacility(triageResult.facility, triageResult.category)}
            className="w-full sm:w-auto px-4 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-bold text-xs flex items-center justify-center gap-2 shrink-0 shadow-sm active:scale-95 transition-all cursor-pointer"
          >
            <Navigation className="w-4 h-4" />
            <span>Kích Hoạt Chỉ Đường 3D Ngay</span>
          </button>
        </div>
      )}
    </div>
  );
};
