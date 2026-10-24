/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * D3.js Interactive Elevation Profile & Real-Time Traffic Density Telemetry Chart
 * Visualizes topographic elevation (m), road slope (%), BPR traffic density (%),
 * and physical road obstacles along the selected route inside NavigationCockpit.
 */

import React, { useMemo, useState, useRef, useEffect } from 'react';
import * as d3 from 'd3';
import {
  Mountain,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Gauge,
  Compass,
} from 'lucide-react';
import type {
  RouteElevationTrafficAnalysis,
  RouteObstacle,
  RouteProfilePoint,
} from '../utils/routeElevationTrafficProfile';
import type {
  OperationalScenarioType,
  TransportVehicleType,
} from '../services/bookingCareDispatchEngine';

interface RouteElevationTrafficChartProps {
  analysis: RouteElevationTrafficAnalysis;
  currentPointIndex: number;
  scenarioType: OperationalScenarioType;
  vehicleType: TransportVehicleType;
  onHoverPoint?: (point: RouteProfilePoint | null) => void;
  onSelectObstacle?: (obstacle: RouteObstacle) => void;
}

type ChartDisplayMode = 'DUAL_COMPARISON' | 'ELEVATION_ONLY' | 'TRAFFIC_ONLY';

export const RouteElevationTrafficChart: React.FC<RouteElevationTrafficChartProps> = ({
  analysis,
  currentPointIndex,
  scenarioType,
  vehicleType,
  onHoverPoint,
  onSelectObstacle,
}) => {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [isExpanded, setIsExpanded] = useState<boolean>(true);
  const [displayMode, setDisplayMode] = useState<ChartDisplayMode>('DUAL_COMPARISON');
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [selectedObstacleId, setSelectedObstacleId] = useState<string | null>(
    analysis.obstacles[0]?.id || null
  );

  const { points, obstacles } = analysis;

  // Dimensions for responsive SVG viewBox matching the 7-col container aspect ratio (~2.45:1)
  const width = 520;
  const height = 210;
  const margin = { top: 26, right: 38, bottom: 26, left: 36 };
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;

  // Compute D3 scales and SVG path generators
  const d3Geometry = useMemo(() => {
    if (points.length < 2) return null;

    const maxDist = Math.max(0.5, points[points.length - 1].distanceKm);
    const xScale = d3
      .scaleLinear()
      .domain([0, maxDist])
      .range([0, innerWidth]);

    const elevMin = Math.max(0, Math.floor(analysis.minElevationMeters - 1.5));
    const elevMax = Math.ceil(analysis.maxElevationMeters + 2.5);
    const yElevScale = d3
      .scaleLinear()
      .domain([elevMin, elevMax])
      .range([innerHeight, 0]);

    const yTrafficScale = d3
      .scaleLinear()
      .domain([0, 100])
      .range([innerHeight, 0]);

    const elevationAreaGen = d3
      .area<RouteProfilePoint>()
      .x((d) => xScale(d.distanceKm))
      .y0(innerHeight)
      .y1((d) => yElevScale(d.elevationMeters))
      .curve(d3.curveMonotoneX);

    const elevationLineGen = d3
      .line<RouteProfilePoint>()
      .x((d) => xScale(d.distanceKm))
      .y((d) => yElevScale(d.elevationMeters))
      .curve(d3.curveMonotoneX);

    const trafficAreaGen = d3
      .area<RouteProfilePoint>()
      .x((d) => xScale(d.distanceKm))
      .y0(innerHeight)
      .y1((d) => yTrafficScale(d.trafficDensityPercent))
      .curve(d3.curveMonotoneX);

    const trafficLineGen = d3
      .line<RouteProfilePoint>()
      .x((d) => xScale(d.distanceKm))
      .y((d) => yTrafficScale(d.trafficDensityPercent))
      .curve(d3.curveMonotoneX);

    const xTicks = xScale.ticks(6);
    const yElevTicks = yElevScale.ticks(4);
    const yTrafficTicks = [25, 50, 75, 100];

    return {
      xScale,
      yElevScale,
      yTrafficScale,
      elevationAreaPath: elevationAreaGen(points) || '',
      elevationLinePath: elevationLineGen(points) || '',
      trafficAreaPath: trafficAreaGen(points) || '',
      trafficLinePath: trafficLineGen(points) || '',
      xTicks,
      yElevTicks,
      yTrafficTicks,
      maxDist,
    };
  }, [points, analysis.minElevationMeters, analysis.maxElevationMeters, innerWidth, innerHeight]);

  // Render D3 Gridlines & Axis Enhancements via d3.select
  useEffect(() => {
    if (!svgRef.current || !d3Geometry || !isExpanded) return;

    const svg = d3.select(svgRef.current);
    const gridGroup = svg.select<SVGGElement>('.d3-grid-group');
    gridGroup.selectAll('*').remove();

    d3Geometry.yElevTicks.forEach((tickVal) => {
      const yPos = d3Geometry.yElevScale(tickVal);
      gridGroup
        .append('line')
        .attr('x1', 0)
        .attr('x2', innerWidth)
        .attr('y1', yPos)
        .attr('y2', yPos)
        .attr('stroke', 'rgba(148, 163, 184, 0.35)')
        .attr('stroke-dasharray', '3,3');
    });
  }, [d3Geometry, innerWidth, isExpanded]);

  if (!d3Geometry || points.length < 2) {
    return null;
  }

  const activePointIndex =
    hoveredIndex !== null
      ? hoveredIndex
      : Math.min(points.length - 1, Math.max(0, currentPointIndex));
  const inspectedPoint = points[activePointIndex] || points[0];

  const vehicleProgressPt =
    points[Math.min(points.length - 1, Math.max(0, currentPointIndex))] || points[0];

  const selectedObstacle =
    obstacles.find((o) => o.id === selectedObstacleId) || obstacles[0] || null;

  const handlePointerMove = (e: React.MouseEvent<SVGRectElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const relX = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const targetDist = relX * d3Geometry.maxDist;

    const bisect = d3.bisector((d: RouteProfilePoint) => d.distanceKm).center;
    const idx = bisect(points, targetDist);
    setHoveredIndex(idx);
    if (onHoverPoint && points[idx]) {
      onHoverPoint(points[idx]);
    }
  };

  const handlePointerLeave = () => {
    setHoveredIndex(null);
    if (onHoverPoint) {
      onHoverPoint(null);
    }
  };

  const getObstacleBadgeStyle = (severity: RouteObstacle['severity']) => {
    if (severity === 'HIGH') {
      return {
        stroke: '#e11d48',
        fill: '#be123c',
        badgeClass: 'bg-rose-50 text-rose-800 border-rose-300 ring-1 ring-rose-500/20',
      };
    }
    if (severity === 'MEDIUM') {
      return {
        stroke: '#d97706',
        fill: '#b45309',
        badgeClass: 'bg-amber-50 text-amber-800 border-amber-300 ring-1 ring-amber-500/20',
      };
    }
    return {
      stroke: '#0284c7',
      fill: '#0369a1',
      badgeClass: 'bg-sky-50 text-sky-800 border-sky-300 ring-1 ring-sky-500/20',
    };
  };

  const getShortObstacleLabel = (category: RouteObstacle['category']) => {
    switch (category) {
      case 'OVERPASS_BRIDGE':
        return 'Cầu Vượt';
      case 'TRAFFIC_BOTTLENECK':
        return 'Nghẽn BPR';
      case 'LOW_LYING_FLOOD_DIP':
        return 'Vùng Trũng';
      case 'HOSPITAL_RAMP_GATE':
        return 'Cổng Viện';
    }
  };

  const vehicleX = d3Geometry.xScale(vehicleProgressPt.distanceKm);
  const clampedBadgeOffsetX =
    vehicleX < 30 ? 30 - vehicleX : vehicleX > innerWidth - 30 ? innerWidth - 30 - vehicleX : 0;

  return (
    <div
      data-testid="d3-elevation-traffic-panel"
      className="bg-white border-t border-slate-200/90 text-slate-900 transition-all duration-300 select-none"
    >
      {/* Top Bar: Summary Metrics, Mode Switcher & Collapse Toggle */}
      <div className="px-4 py-2.5 flex flex-wrap items-center justify-between gap-2 border-b border-slate-200/80 bg-slate-50/70">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="w-7 h-7 rounded-lg bg-sky-100 border border-sky-200 flex items-center justify-center text-sky-700">
              <Mountain className="w-4 h-4" />
            </span>
            <div>
              <h3 className="text-xs font-extrabold tracking-tight text-slate-900">
                Biểu Đồ D3.js: Độ Cao Địa Hình &amp; Mật Độ Giao Thông Real-Time
              </h3>
              <div className="text-[11px] text-slate-500 font-medium tabular-nums">
                Độ cao: <strong className="text-sky-700">{analysis.minElevationMeters}m – {analysis.maxElevationMeters}m</strong> (Dốc {analysis.maxSlopePercent}%) • Mật độ BPR: <strong className="text-amber-700">TB {analysis.avgTrafficDensityPercent}%</strong> (Đỉnh {analysis.peakTrafficDensityPercent}%)
              </div>
            </div>
          </div>
        </div>

        {/* Display Layer Filters & Expand/Collapse */}
        <div className="flex items-center gap-2">
          <div className="bg-slate-200/70 p-0.5 rounded-xl flex items-center gap-0.5">
            {[
              { id: 'DUAL_COMPARISON', label: 'So Sánh Kép' },
              { id: 'ELEVATION_ONLY', label: 'Độ Cao (m)' },
              { id: 'TRAFFIC_ONLY', label: 'Mật Độ (%)' },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                data-testid={`d3-mode-${tab.id.toLowerCase()}`}
                onClick={() => setDisplayMode(tab.id as ChartDisplayMode)}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all cursor-pointer ${
                  displayMode === tab.id
                    ? 'bg-white text-sky-700 shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <button
            type="button"
            data-testid="toggle-d3-chart-btn"
            onClick={() => setIsExpanded(!isExpanded)}
            className="px-2.5 py-1 rounded-xl bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 text-[11px] font-bold flex items-center gap-1 cursor-pointer transition-colors"
          >
            <span>{isExpanded ? 'Thu gọn' : 'Mở biểu đồ D3'}</span>
            {isExpanded ? (
              <ChevronDown className="w-3.5 h-3.5" />
            ) : (
              <ChevronUp className="w-3.5 h-3.5" />
            )}
          </button>
        </div>
      </div>

      {isExpanded && (
        <div className="p-3.5 sm:px-4 sm:py-3.5 grid grid-cols-1 xl:grid-cols-12 gap-3.5 items-stretch bg-white">
          {/* Left 7 Columns: Interactive D3.js Dual-Axis SVG Chart */}
          <div className="xl:col-span-7 bg-slate-50/70 rounded-2xl border border-slate-200/90 p-3 flex flex-col gap-2 relative overflow-hidden">
            {/* Live Scrubbed Point Telemetry Strip */}
            <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-slate-200/70 text-[11px]">
              <div className="flex flex-wrap items-center gap-1.5 tabular-nums">
                <span className="px-2 py-0.5 rounded-md bg-sky-100 text-sky-800 font-extrabold">
                  Km {inspectedPoint.distanceKm.toFixed(2)} / {d3Geometry.maxDist.toFixed(2)} km
                </span>
                <span className="font-bold text-slate-800 truncate max-w-[165px]">
                  {inspectedPoint.roadSegmentLabel}
                </span>
                <span className="text-sky-700 font-bold">
                  • Cao độ: {inspectedPoint.elevationMeters}m ({inspectedPoint.slopePercent >= 0 ? `+${inspectedPoint.slopePercent}%` : `${inspectedPoint.slopePercent}%`})
                </span>
                <span
                  className={`font-bold ${
                    inspectedPoint.trafficDensityPercent >= 70
                      ? 'text-rose-600'
                      : inspectedPoint.trafficDensityPercent >= 50
                      ? 'text-amber-700'
                      : 'text-emerald-700'
                  }`}
                >
                  • Mật độ: {inspectedPoint.trafficDensityPercent}% (~{inspectedPoint.speedKmh} km/h)
                </span>
              </div>

              <div className="flex items-center gap-3 text-[10px] font-bold">
                {(displayMode === 'DUAL_COMPARISON' || displayMode === 'ELEVATION_ONLY') && (
                  <span className="flex items-center gap-1 text-sky-700">
                    <span className="w-2.5 h-2.5 rounded-xs bg-sky-600 inline-block" />
                    Độ cao (m)
                  </span>
                )}
                {(displayMode === 'DUAL_COMPARISON' || displayMode === 'TRAFFIC_ONLY') && (
                  <span className="flex items-center gap-1 text-amber-700">
                    <span className="w-2.5 h-2.5 rounded-xs bg-amber-500 inline-block" />
                    Mật độ BPR (%)
                  </span>
                )}
              </div>
            </div>

            {/* D3 SVG Canvas filling container cleanly */}
            <div className="w-full flex-1 flex items-center">
              <svg
                ref={svgRef}
                data-testid="d3-elevation-traffic-svg"
                viewBox={`0 0 ${width} ${height}`}
                className="w-full h-[195px] sm:h-[210px] overflow-visible font-sans"
              >
                <defs>
                  <linearGradient id="d3ElevationFillLight" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#0284c7" stopOpacity="0.32" />
                    <stop offset="70%" stopColor="#38bdf8" stopOpacity="0.12" />
                    <stop offset="100%" stopColor="#f8fafc" stopOpacity="0.02" />
                  </linearGradient>

                  <linearGradient id="d3TrafficFillLight" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#e11d48" stopOpacity="0.28" />
                    <stop offset="50%" stopColor="#f59e0b" stopOpacity="0.15" />
                    <stop offset="100%" stopColor="#10b981" stopOpacity="0.03" />
                  </linearGradient>

                  <linearGradient id="d3TrafficStrokeLight" x1="0" y1="1" x2="0" y2="0">
                    <stop offset="0%" stopColor="#059669" />
                    <stop offset="55%" stopColor="#d97706" />
                    <stop offset="100%" stopColor="#e11d48" />
                  </linearGradient>
                </defs>

                <g transform={`translate(${margin.left}, ${margin.top})`}>
                  {/* D3 Populated Grid Group */}
                  <g className="d3-grid-group" />

                  {/* Layer 1: Elevation Profile Area & Line */}
                  {(displayMode === 'DUAL_COMPARISON' || displayMode === 'ELEVATION_ONLY') && (
                    <g className="d3-elevation-layer">
                      <path
                        d={d3Geometry.elevationAreaPath}
                        fill="url(#d3ElevationFillLight)"
                      />
                      <path
                        d={d3Geometry.elevationLinePath}
                        fill="none"
                        stroke="#0284c7"
                        strokeWidth={2.75}
                        strokeLinecap="round"
                      />
                    </g>
                  )}

                  {/* Layer 2: Real-Time Traffic Density Area & Line */}
                  {(displayMode === 'DUAL_COMPARISON' || displayMode === 'TRAFFIC_ONLY') && (
                    <g className="d3-traffic-layer">
                      {displayMode === 'TRAFFIC_ONLY' && (
                        <path
                          d={d3Geometry.trafficAreaPath}
                          fill="url(#d3TrafficFillLight)"
                        />
                      )}
                      <path
                        d={d3Geometry.trafficLinePath}
                        fill="none"
                        stroke="url(#d3TrafficStrokeLight)"
                        strokeWidth={2.5}
                        strokeDasharray={displayMode === 'DUAL_COMPARISON' ? '6,3' : undefined}
                        strokeLinecap="round"
                      />
                    </g>
                  )}

                  {/* Left Y-Axis: Elevation (m) */}
                  {d3Geometry.yElevTicks.map((tick) => {
                    const y = d3Geometry.yElevScale(tick);
                    return (
                      <g key={`elev-tick-${tick}`} transform={`translate(0, ${y})`}>
                        <text
                          x={-8}
                          y={3}
                          textAnchor="end"
                          className="fill-sky-700 text-[10px] font-bold tabular-nums"
                        >
                          {tick}m
                        </text>
                      </g>
                    );
                  })}

                  {/* Right Y-Axis: Traffic Density (%) */}
                  {d3Geometry.yTrafficTicks.map((tick) => {
                    const y = d3Geometry.yTrafficScale(tick);
                    return (
                      <g key={`traffic-tick-${tick}`} transform={`translate(${innerWidth}, ${y})`}>
                        <text
                          x={8}
                          y={3}
                          textAnchor="start"
                          className="fill-amber-700 text-[10px] font-bold tabular-nums"
                        >
                          {tick}%
                        </text>
                      </g>
                    );
                  })}

                  {/* Bottom X-Axis: Route Distance (km) */}
                  <line
                    x1={0}
                    x2={innerWidth}
                    y1={innerHeight}
                    y2={innerHeight}
                    stroke="#cbd5e1"
                    strokeWidth={1}
                  />
                  {d3Geometry.xTicks.map((tick) => {
                    const x = d3Geometry.xScale(tick);
                    return (
                      <g key={`x-tick-${tick}`} transform={`translate(${x}, ${innerHeight})`}>
                        <line y1={0} y2={4} stroke="#94a3b8" />
                        <text
                          y={16}
                          textAnchor="middle"
                          className="fill-slate-600 text-[10px] font-bold tabular-nums"
                        >
                          {tick.toFixed(1)} km
                        </text>
                      </g>
                    );
                  })}

                  {/* Real-Time Vehicle Progress Tracker Line */}
                  <g transform={`translate(${vehicleX}, 0)`}>
                    <line
                      y1={-4}
                      y2={innerHeight}
                      stroke="#059669"
                      strokeWidth={2}
                      strokeDasharray="2,2"
                    />
                    <circle
                      cy={d3Geometry.yElevScale(vehicleProgressPt.elevationMeters)}
                      r={5}
                      fill="#10b981"
                      stroke="#ffffff"
                      strokeWidth={2}
                    />
                    <g transform={`translate(${clampedBadgeOffsetX}, 0)`}>
                      <rect
                        x={-29}
                        y={-20}
                        width={58}
                        height={15}
                        rx={4}
                        fill="#059669"
                      />
                      <text
                        x={0}
                        y={-10}
                        textAnchor="middle"
                        className="fill-white text-[9px] font-black"
                      >
                        XE HIỆN TẠI
                      </text>
                    </g>
                  </g>

                  {/* Interactive Scrubbing Cursor Line */}
                  {hoveredIndex !== null && (
                    <g
                      transform={`translate(${d3Geometry.xScale(inspectedPoint.distanceKm)}, 0)`}
                    >
                      <line
                        y1={0}
                        y2={innerHeight}
                        stroke="#334155"
                        strokeWidth={1.5}
                      />
                      {(displayMode === 'DUAL_COMPARISON' || displayMode === 'ELEVATION_ONLY') && (
                        <circle
                          cy={d3Geometry.yElevScale(inspectedPoint.elevationMeters)}
                          r={5}
                          fill="#0284c7"
                          stroke="#ffffff"
                          strokeWidth={2}
                        />
                      )}
                      {(displayMode === 'DUAL_COMPARISON' || displayMode === 'TRAFFIC_ONLY') && (
                        <circle
                          cy={d3Geometry.yTrafficScale(inspectedPoint.trafficDensityPercent)}
                          r={5}
                          fill="#d97706"
                          stroke="#ffffff"
                          strokeWidth={2}
                        />
                      )}
                    </g>
                  )}

                  {/* Obstacle Markers Along the Route */}
                  {obstacles.map((obs, idx) => {
                    const cx = d3Geometry.xScale(obs.distanceKm);
                    const cy =
                      displayMode === 'TRAFFIC_ONLY'
                        ? d3Geometry.yTrafficScale(obs.trafficDensityPercent)
                        : d3Geometry.yElevScale(obs.elevationMeters);
                    const style = getObstacleBadgeStyle(obs.severity);
                    const isSelected = selectedObstacle?.id === obs.id;

                    return (
                      <g
                        key={obs.id}
                        transform={`translate(${cx}, ${cy})`}
                        className="cursor-pointer"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedObstacleId(obs.id);
                          if (onSelectObstacle) onSelectObstacle(obs);
                        }}
                      >
                        <line
                          y1={0}
                          y2={innerHeight - cy}
                          stroke={style.stroke}
                          strokeWidth={1}
                          strokeDasharray="2,2"
                          opacity={0.7}
                        />
                        <circle
                          r={isSelected ? 8.5 : 6.5}
                          fill={style.fill}
                          stroke="#ffffff"
                          strokeWidth={2}
                        />
                        <text
                          y={3}
                          textAnchor="middle"
                          className="fill-white text-[9px] font-black pointer-events-none"
                        >
                          {idx + 1}
                        </text>
                      </g>
                    );
                  })}

                  {/* Transparent Pointer Overlay for Smooth Scrubbing */}
                  <rect
                    x={0}
                    y={0}
                    width={innerWidth}
                    height={innerHeight}
                    fill="transparent"
                    className="cursor-crosshair"
                    onMouseMove={handlePointerMove}
                    onMouseLeave={handlePointerLeave}
                  />
                </g>
              </svg>
            </div>
          </div>

          {/* Right 5 Columns: Interactive Obstacle Inspector & Actionable Vehicle Guidance */}
          <div className="xl:col-span-5 bg-slate-50/70 rounded-2xl border border-slate-200/90 p-3.5 flex flex-col justify-between gap-2.5">
            <div>
              <div className="flex items-center justify-between gap-2 mb-2.5">
                <span className="text-[11px] font-extrabold uppercase tracking-wide text-slate-700 flex items-center gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                  Chướng Ngại Vật Trên Tuyến ({obstacles.length})
                </span>
                <span className="text-[10px] font-semibold text-slate-500">
                  Chạm để định vị 3D
                </span>
              </div>

              {/* Obstacle Selector Pills with Clean Un-truncated Labels */}
              <div className="grid grid-cols-2 gap-1.5 mb-2.5">
                {obstacles.map((obs, idx) => {
                  const isSel = selectedObstacle?.id === obs.id;
                  const style = getObstacleBadgeStyle(obs.severity);
                  return (
                    <button
                      key={obs.id}
                      type="button"
                      data-testid={`obstacle-pill-${idx + 1}`}
                      onClick={() => {
                        setSelectedObstacleId(obs.id);
                        if (onSelectObstacle) onSelectObstacle(obs);
                      }}
                      className={`px-2.5 py-1.5 rounded-xl border text-left transition-all cursor-pointer flex items-center justify-between gap-1.5 ${
                        isSel
                          ? style.badgeClass
                          : 'bg-white border-slate-200 text-slate-700 hover:border-slate-300'
                      }`}
                    >
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span
                          className={`w-4 h-4 rounded-full text-[10px] font-black flex items-center justify-center shrink-0 tabular-nums ${
                            isSel
                              ? 'bg-slate-900 text-white'
                              : 'bg-slate-100 text-slate-700'
                          }`}
                        >
                          {idx + 1}
                        </span>
                        <span className="text-[11px] font-bold whitespace-nowrap">
                          {getShortObstacleLabel(obs.category)}
                        </span>
                      </div>
                      <span className="text-[10px] font-bold text-slate-500 shrink-0 tabular-nums">
                        {obs.distanceKm}km
                      </span>
                    </button>
                  );
                })}
              </div>

              {/* Selected Obstacle Telemetry Detail Card */}
              {selectedObstacle && (
                <div className="p-3 rounded-xl bg-white border border-slate-200/90 space-y-1.5 shadow-2xs">
                  <div className="flex flex-wrap items-center justify-between gap-1">
                    <span className="text-xs font-extrabold text-slate-900 leading-snug">
                      {selectedObstacle.title}
                    </span>
                    <span className="px-1.5 py-0.5 rounded bg-sky-50 border border-sky-200 text-[10px] font-bold text-sky-800 shrink-0 tabular-nums">
                      Km {selectedObstacle.distanceKm} • Mật độ {selectedObstacle.trafficDensityPercent}%
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-600 leading-relaxed">
                    {selectedObstacle.medicalImpactNote}
                  </p>
                  <div className="pt-1.5 border-t border-slate-100 flex items-start gap-1.5 text-[11px] text-emerald-700 font-semibold leading-snug">
                    <Compass className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                    <span>{selectedObstacle.vehicleActionHint}</span>
                  </div>
                </div>
              )}
            </div>

            {/* Bottom Biomechanical & Vehicle Summary Footer */}
            <div className="pt-2 border-t border-slate-200/80 flex items-center justify-between text-[10px] text-slate-500 tabular-nums">
              <span className="flex items-center gap-1 font-semibold">
                <Gauge className="w-3.5 h-3.5 text-sky-600" />
                Rung chấn ISO 2631-1: <strong className="text-slate-800">{inspectedPoint.vibrationRms} m/s²</strong>
              </span>
              <span className="font-bold text-sky-700">
                {scenarioType === 'AMBULANCE_DISPATCH'
                  ? 'Cáng Thủy Lực 115'
                  : vehicleType === 'motorcycle'
                  ? 'Tối ưu Xe Máy (Né ngập)'
                  : 'Tối ưu Ô Tô / Taxi'}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
