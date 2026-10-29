/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * MedGuard AI - Navigation POI Sidebar & Healthcare-Only Search with Google Maps Ratings
 */

import React, { useState, useMemo } from 'react';
import {
  Search,
  PhoneCall,
  Bed,
  Star,
  Clock,
  MapPin,
  MessageSquare,
  ArrowRightLeft,
} from 'lucide-react';
import type { MedicalFacility } from '../data/medicalPoiRegistry';
import { CITY_PRESETS } from '../data/medicalPoiRegistry';
import { calculateDistanceMeters, formatDistanceVi } from '../utils/navigationMath';

interface NavigationSidebarProps {
  facilities: MedicalFacility[];
  selectedFacility: MedicalFacility;
  userCoords: { lat: number; lng: number };
  activeCity: 'hcm' | 'hanoi' | 'danang';
  onChangeCity: (city: 'hcm' | 'hanoi' | 'danang') => void;
  onSelectFacility: (facility: MedicalFacility) => void;
  onCallHotline: (phone: string) => void;
  onViewReviews?: (facility: MedicalFacility) => void;
}

export const NavigationSidebar: React.FC<NavigationSidebarProps> = ({
  facilities,
  selectedFacility,
  userCoords,
  activeCity,
  onChangeCity,
  onSelectFacility,
  onCallHotline,
  onViewReviews,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [sortBy, setSortBy] = useState<'distance' | 'rating' | 'wait_time'>('distance');

  const filteredFacilities = useMemo(() => {
    return facilities
      .filter((fac) => fac.city === activeCity)
      .filter((fac) => {
        if (categoryFilter === 'hospital') return fac.facilityType === 'hospital_emergency';
        if (categoryFilter === 'pharmacy') return fac.facilityType === 'pharmacy';
        if (categoryFilter === 'stroke') return fac.category === 'stroke';
        if (categoryFilter === 'cardiac') return fac.category === 'cardiac';
        if (categoryFilter === 'trauma') return fac.category === 'trauma';
        return true;
      })
      .filter((fac) => {
        if (!searchTerm.trim()) return true;
        const q = searchTerm.toLowerCase();
        return (
          fac.name.toLowerCase().includes(q) ||
          fac.address.toLowerCase().includes(q) ||
          fac.district.toLowerCase().includes(q) ||
          fac.specialtyTag.toLowerCase().includes(q)
        );
      })
      .map((fac) => ({
        ...fac,
        distanceMeters: calculateDistanceMeters(userCoords.lat, userCoords.lng, fac.lat, fac.lng),
      }))
      .sort((a, b) => {
        if (sortBy === 'rating') return b.rating - a.rating;
        if (sortBy === 'wait_time') return a.avgErWaitMinutes - b.avgErWaitMinutes;
        return a.distanceMeters - b.distanceMeters;
      });
  }, [facilities, activeCity, categoryFilter, searchTerm, userCoords, sortBy]);

  return (
    <aside
      aria-label="Danh sách cơ sở y tế và bộ lọc tìm kiếm"
      className="flex flex-col h-full bg-white border border-slate-200/90 rounded-3xl overflow-hidden shadow-[0_8px_30px_rgb(15,23,42,0.06)]"
    >
      {/* City Presets Bar */}
      <div className="px-4 py-3 bg-slate-50/90 border-b border-slate-200/80 flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <MapPin className="w-4 h-4 text-sky-600" />
          <span className="text-xs font-extrabold text-slate-800 tracking-tight">
            Khu Vực Y Tế
          </span>
        </div>
        <div className="flex items-center gap-1 bg-slate-200/70 p-0.5 rounded-xl">
          {(['hcm', 'hanoi', 'danang'] as const).map((cityKey) => {
            const city = CITY_PRESETS[cityKey];
            const isActive = activeCity === cityKey;
            return (
              <button
                key={cityKey}
                type="button"
                onClick={() => onChangeCity(cityKey)}
                className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                  isActive
                    ? 'bg-white text-sky-700 shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {city.name.replace('TP. ', '')}
              </button>
            );
          })}
        </div>
      </div>

      {/* Search Input & Healthcare Filter */}
      <div className="p-3.5 border-b border-slate-200/80 space-y-2.5 bg-white">
        <div className="relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Tìm bệnh viện cấp cứu, nhà thuốc GPP 24/7..."
            aria-label="Tìm bệnh viện cấp cứu hoặc nhà thuốc"
            className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-sky-500 focus:ring-2 focus:ring-sky-500/15 transition-all"
          />
        </div>

        {/* Category Filter Tabs */}
        <div className="flex flex-wrap items-center gap-1">
          {[
            { id: 'all', label: 'Tất cả' },
            { id: 'hospital', label: 'Bệnh viện' },
            { id: 'stroke', label: 'Đột quỵ' },
            { id: 'cardiac', label: 'Tim mạch' },
            { id: 'trauma', label: 'Chấn thương' },
            { id: 'pharmacy', label: 'Nhà thuốc 24/7' },
          ].map((cat) => (
            <button
              key={cat.id}
              type="button"
              onClick={() => setCategoryFilter(cat.id)}
              className={`whitespace-nowrap px-2 py-1 rounded-lg text-[11px] font-bold transition-all cursor-pointer ${
                categoryFilter === cat.id
                  ? 'bg-sky-600 text-white shadow-xs'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200/70 hover:text-slate-900'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* Sort By Bar: Distance vs Rating vs Fast Intake */}
        <div className="flex items-center justify-between text-[11px] pt-1.5 border-t border-slate-100">
          <span className="text-slate-500 font-semibold">Xếp theo:</span>
          <div className="flex items-center gap-1">
            {[
              { id: 'distance', label: 'Gần nhất' },
              { id: 'rating', label: 'Uy tín cao' },
              { id: 'wait_time', label: 'Tiếp nhận nhanh' },
            ].map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => setSortBy(s.id as 'distance' | 'rating' | 'wait_time')}
                className={`px-2 py-0.5 rounded-md font-bold transition-all cursor-pointer ${
                  sortBy === s.id
                    ? 'bg-sky-50 text-sky-700 border border-sky-200'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Facilities List with Google Maps Reviews & Instant Switch */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2.5 max-h-[675px] bg-slate-50/50">
        {filteredFacilities.length === 0 ? (
          <div className="text-center py-12 px-4">
            <p className="text-slate-500 text-xs font-medium">
              Không tìm thấy cơ sở y tế hoặc nhà thuốc nào phù hợp với từ khóa.
            </p>
            <button
              type="button"
              onClick={() => {
                setSearchTerm('');
                setCategoryFilter('all');
              }}
              className="mt-2.5 px-3 py-1.5 rounded-lg bg-sky-600 text-white text-xs font-bold cursor-pointer"
            >
              Xóa bộ lọc
            </button>
          </div>
        ) : (
          filteredFacilities.map((fac) => {
            const isSelected = selectedFacility.id === fac.id;
            const isHospital = fac.facilityType === 'hospital_emergency';

            return (
              <div
                key={fac.id}
                onClick={() => onSelectFacility(fac)}
                className={`p-3.5 rounded-2xl border transition-all duration-200 cursor-pointer relative ${
                  isSelected
                    ? 'bg-sky-50/70 border-sky-500 shadow-sm ring-1 ring-sky-500/20'
                    : 'bg-white border-slate-200/90 hover:border-slate-300 hover:shadow-xs'
                }`}
              >
                <div className="flex items-start justify-between gap-2.5">
                  <div className="flex items-start gap-2.5 min-w-0">
                    <div
                      className={`w-9 h-9 rounded-xl flex items-center justify-center font-black text-xs shrink-0 mt-0.5 ${
                        isHospital
                          ? 'bg-rose-600 text-white shadow-xs'
                          : 'bg-teal-600 text-white shadow-xs'
                      }`}
                    >
                      {isHospital ? 'H+' : 'Rx'}
                    </div>

                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap tabular-nums">
                        <span
                          className={`text-[10px] font-extrabold uppercase tracking-wide ${
                            isHospital ? 'text-rose-600' : 'text-teal-700'
                          }`}
                        >
                          {isHospital ? 'Cấp cứu 24/7' : 'Nhà thuốc GPP'}
                        </span>
                        <span className="text-slate-300">•</span>
                        <span className="text-[11px] text-sky-700 font-bold">
                          {formatDistanceVi(fac.distanceMeters)}
                        </span>
                        <span className="text-slate-300">•</span>
                        <span className="text-[11px] font-bold text-amber-600 flex items-center gap-0.5">
                          <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                          {fac.rating.toFixed(1)}{' '}
                          <span className="text-slate-400 font-medium">
                            ({fac.reviewsCount.toLocaleString()})
                          </span>
                        </span>
                      </div>

                      <h4 className="text-xs sm:text-sm font-extrabold text-slate-900 truncate mt-0.5">
                        {fac.name}
                      </h4>
                      <p className="text-[11px] text-slate-500 truncate mt-0.5">
                        {fac.address}
                      </p>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onCallHotline(fac.emergencyHotline);
                    }}
                    className="p-2 rounded-xl bg-rose-50 hover:bg-rose-600 text-rose-600 hover:text-white border border-rose-200 transition-colors shrink-0 cursor-pointer"
                    title={`Gọi ngay ${fac.emergencyHotline}`}
                    aria-label={`Gọi cấp cứu ${fac.name}`}
                  >
                    <PhoneCall className="w-3.5 h-3.5" />
                  </button>
                </div>

                {/* Clinical Trust Metrics & Quick Switch Row */}
                <div className="mt-2.5 pt-2 border-t border-slate-100 flex items-center justify-between gap-2 text-[11px] tabular-nums">
                  <div className="flex items-center gap-3 text-slate-600">
                    {isHospital ? (
                      <span className="flex items-center gap-1 text-slate-700 font-semibold">
                        <Bed className="w-3.5 h-3.5 text-sky-600" />
                        {fac.icuBedsAvailable} giường ICU
                      </span>
                    ) : (
                      <span className="text-teal-700 font-semibold">Đủ thuốc cấp cứu</span>
                    )}
                    <span className="flex items-center gap-1 text-emerald-700 font-semibold">
                      <Clock className="w-3.5 h-3.5 text-emerald-600" />
                      ~{fac.avgErWaitMinutes}p tiếp nhận
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5">
                    {onViewReviews && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectFacility(fac);
                          onViewReviews(fac);
                        }}
                        className="px-2 py-1 rounded-lg bg-slate-100 hover:bg-slate-200/80 text-slate-700 font-bold flex items-center gap-1 transition-colors cursor-pointer"
                      >
                        <MessageSquare className="w-3 h-3 text-amber-500" />
                        <span>Đánh giá</span>
                      </button>
                    )}
                    {!isSelected ? (
                      <span className="px-2 py-1 rounded-lg bg-sky-50 text-sky-700 font-bold flex items-center gap-1 border border-sky-200/70">
                        <ArrowRightLeft className="w-3 h-3" />
                        <span>Chọn đích</span>
                      </span>
                    ) : (
                      <span className="px-2 py-1 rounded-lg bg-sky-600 text-white font-bold text-[10px]">
                        Đang chọn
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
};
