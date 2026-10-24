/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * MedGuard AI - Dual Corridor Comparison Bar
 */

import React from 'react';
import { Sparkles, AlertTriangle, ShieldCheck } from 'lucide-react';
import type { DualRoute } from '../services/routingService';

interface RouteComparisonBarProps {
  primaryRoute: DualRoute;
  alternativeRoute: DualRoute;
  selectedRouteId: string;
  onSelectRoute: (routeId: string) => void;
}

export const RouteComparisonBar: React.FC<RouteComparisonBarProps> = ({
  primaryRoute,
  alternativeRoute,
  selectedRouteId,
  onSelectRoute,
}) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {/* Bypass / Recommended Route */}
      <button
        type="button"
        onClick={() => onSelectRoute(alternativeRoute.id)}
        className={`w-full text-left p-4 rounded-2xl border transition-all relative overflow-hidden cursor-pointer ${
          selectedRouteId === alternativeRoute.id
            ? 'bg-sky-50/80 border-sky-500 shadow-sm ring-1 ring-sky-500/20'
            : 'bg-white border-slate-200/90 hover:border-slate-300 text-slate-700'
        }`}
      >
        {alternativeRoute.time_saved_minutes > 0 && (
          <span className="absolute top-3 right-3 inline-flex items-center gap-1 bg-sky-600 text-white font-extrabold text-[10px] px-2.5 py-0.5 rounded-full shadow-2xs">
            <Sparkles className="w-3 h-3" />
            TIẾT KIỆM {alternativeRoute.time_saved_minutes} PHÚT
          </span>
        )}

        <div className="flex items-center gap-2 flex-wrap pr-24 sm:pr-0">
          <span
            className={`w-3 h-3 rounded-full shrink-0 ${
              selectedRouteId === alternativeRoute.id ? 'bg-sky-600 ring-4 ring-sky-500/20' : 'bg-slate-300'
            }`}
          />
          <span className="text-xs font-extrabold text-sky-700 uppercase tracking-wider">
            {alternativeRoute.name}
          </span>
          <span className="hidden sm:inline-block text-[10px] bg-sky-100 text-sky-800 px-2 py-0.5 rounded-md font-bold">
            Tuyến Tránh Ưu Tiên
          </span>
        </div>

        <div className="mt-2 flex items-baseline gap-3 tabular-nums">
          <span className="text-xl font-black text-slate-900">
            {alternativeRoute.duration_minutes}{' '}
            <span className="text-xs font-semibold text-slate-500">phút</span>
          </span>
          <span className="text-xs text-slate-500 font-bold">
            {alternativeRoute.distance_km} km
          </span>
          <span className="text-[11px] font-bold text-emerald-700 inline-flex items-center gap-1">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            Thông thoáng (Mật độ {alternativeRoute.traffic_density_percent}%)
          </span>
        </div>

        <p className="mt-1.5 text-[11px] text-slate-500 line-clamp-1">
          {alternativeRoute.corridor_description}
        </p>
      </button>

      {/* Primary Direct Route */}
      <button
        type="button"
        onClick={() => onSelectRoute(primaryRoute.id)}
        className={`w-full text-left p-4 rounded-2xl border transition-all relative overflow-hidden cursor-pointer ${
          selectedRouteId === primaryRoute.id
            ? 'bg-amber-50/70 border-amber-500 shadow-sm ring-1 ring-amber-500/20'
            : 'bg-white border-slate-200/90 hover:border-slate-300 text-slate-700'
        }`}
      >
        <div className="flex items-center gap-2">
          <span
            className={`w-3 h-3 rounded-full ${
              selectedRouteId === primaryRoute.id ? 'bg-amber-500 ring-4 ring-amber-500/20' : 'bg-slate-300'
            }`}
          />
          <span className="text-xs font-extrabold text-amber-700 uppercase tracking-wider">
            {primaryRoute.name}
          </span>
          <span className="text-[10px] bg-slate-100 text-slate-700 px-2 py-0.5 rounded-md font-bold">
            Trục Chính Đô Thị
          </span>
        </div>

        <div className="mt-2 flex items-baseline gap-3 tabular-nums">
          <span className="text-xl font-black text-slate-900">
            {primaryRoute.duration_minutes}{' '}
            <span className="text-xs font-semibold text-slate-500">phút</span>
          </span>
          <span className="text-xs text-slate-500 font-bold">
            {primaryRoute.distance_km} km
          </span>
          <span
            className={`text-[11px] font-bold inline-flex items-center gap-1 ${
              primaryRoute.traffic_level === 'SEVERELY_CONGESTED'
                ? 'text-rose-600'
                : primaryRoute.traffic_level === 'HEAVY'
                ? 'text-amber-700'
                : 'text-slate-600'
            }`}
          >
            {primaryRoute.traffic_level === 'SEVERELY_CONGESTED' && (
              <AlertTriangle className="w-3.5 h-3.5" />
            )}
            Mật độ {primaryRoute.traffic_density_percent}%
          </span>
        </div>

        <p className="mt-1.5 text-[11px] text-slate-500 line-clamp-1">
          {primaryRoute.corridor_description}
        </p>
      </button>
    </div>
  );
};
