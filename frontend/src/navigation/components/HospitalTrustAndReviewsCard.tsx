/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * MedGuard AI - Upcoming Destination Reviews, Google Places Healthcare API Sync & Along-Route Checkpoints
 */

import React, { useState, useEffect, useMemo } from 'react';
import {
  Star,
  ShieldCheck,
  ThumbsUp,
  ArrowRightLeft,
  CheckCircle2,
  MessageSquarePlus,
  PhoneCall,
  Award,
  RefreshCw,
  MapPin,
  Code2,
} from 'lucide-react';
import type { MedicalFacility, MedicalPlaceReview } from '../data/medicalPoiRegistry';
import {
  getAlternativeFacilities,
  fetchHealthcarePlaceReviews,
  submitHealthcarePlaceReview,
  type AlternativeFacilityRecommendation,
} from '../services/googlePlacesReviewsService';
import { getUpcomingRouteMedicalCheckpoints } from '../services/bookingCareDispatchEngine';

interface HospitalTrustAndReviewsCardProps {
  facility: MedicalFacility;
  allFacilities: MedicalFacility[];
  userCoords: { lat: number; lng: number };
  onSwitchFacility: (newFacility: MedicalFacility) => void;
  onCallHotline: (phone: string) => void;
}

export const HospitalTrustAndReviewsCard: React.FC<HospitalTrustAndReviewsCardProps> = ({
  facility,
  allFacilities,
  userCoords,
  onSwitchFacility,
  onCallHotline,
}) => {
  const [reviews, setReviews] = useState<MedicalPlaceReview[]>(facility.reviews);
  const [totalReviewsCount, setTotalReviewsCount] = useState<number>(facility.reviewsCount);
  const [lastSynced, setLastSynced] = useState<string>('Vừa đồng bộ');
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [showWriteModal, setShowWriteModal] = useState<boolean>(false);
  const [showApiPayload, setShowApiPayload] = useState<boolean>(false);
  const [reviewFilter, setReviewFilter] = useState<'all' | 'emergency' | 'booking_gate'>('all');
  const [newAuthor, setNewAuthor] = useState<string>('');
  const [newRating, setNewRating] = useState<number>(5);
  const [newTag, setNewTag] = useState<string>('Đặt khám BookingCare & Cổng gửi xe');
  const [newComment, setNewComment] = useState<string>('');
  const [helpfulClickedIds, setHelpfulClickedIds] = useState<Record<string, boolean>>({});

  const alternatives: AlternativeFacilityRecommendation[] = useMemo(
    () => getAlternativeFacilities(facility, allFacilities, userCoords),
    [facility, allFacilities, userCoords]
  );

  const upcomingCheckpoints = useMemo(
    () => getUpcomingRouteMedicalCheckpoints(facility, allFacilities, userCoords).slice(0, 4),
    [facility, allFacilities, userCoords]
  );

  const syncPlaceReviews = () => {
    setIsSyncing(true);
    fetchHealthcarePlaceReviews(facility).then((payload) => {
      setReviews(payload.reviews);
      setTotalReviewsCount(payload.totalReviews);
      setLastSynced(payload.lastSyncedAt);
      setIsSyncing(false);
    });
  };

  useEffect(() => {
    syncPlaceReviews();
  }, [facility]);

  const filteredReviews = useMemo(() => {
    if (reviewFilter === 'emergency') {
      return reviews.filter(
        (r) =>
          r.serviceTag.toLowerCase().includes('cấp cứu') ||
          r.serviceTag.toLowerCase().includes('đột quỵ') ||
          r.serviceTag.toLowerCase().includes('hồi sức')
      );
    }
    if (reviewFilter === 'booking_gate') {
      return reviews.filter(
        (r) =>
          r.comment.toLowerCase().includes('cổng') ||
          r.comment.toLowerCase().includes('đường') ||
          r.comment.toLowerCase().includes('khám') ||
          r.serviceTag.toLowerCase().includes('khám')
      );
    }
    return reviews;
  }, [reviews, reviewFilter]);

  const handleSubmitReview = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newComment.trim()) return;
    const created = submitHealthcarePlaceReview(facility.id, {
      authorName: newAuthor,
      rating: newRating,
      serviceTag: newTag,
      comment: newComment,
    });
    setReviews((prev) => [created, ...prev]);
    setTotalReviewsCount((prev) => prev + 1);
    setNewAuthor('');
    setNewComment('');
    setShowWriteModal(false);
  };

  const breakdown = facility.reviewBreakdown;

  return (
    <section
      data-testid="upcoming-reviews-section"
      aria-label="Đánh giá uy tín cơ sở y tế sắp tới và dữ liệu Google Places API"
      className="bg-white border border-slate-200/90 rounded-3xl p-4 sm:p-6 shadow-[0_8px_30px_rgb(15,23,42,0.06)] text-slate-900 space-y-5"
    >
      {/* 1. UPCOMING MEDICAL CHECKPOINTS ALONG THE ROUTE CORRIDOR */}
      <div className="space-y-3 border-b border-slate-200/80 pb-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <span className="text-[10px] font-extrabold uppercase tracking-wider text-sky-700">
              ĐÁNH GIÁ ĐỊA ĐIỂM SẮP TỚI TRÊN LỘ TRÌNH (UPCOMING ROUTE DESTINATIONS)
            </span>
            <h3 className="text-sm sm:text-base font-extrabold text-slate-900">
              Các Điểm Y Tế Sắp Tới Theo Hướng Di Chuyển &amp; Độ Uy Tín Thực Tế Từ Người Dùng
            </h3>
          </div>
          <span className="text-xs text-slate-500 font-medium">
            Chạm vào địa điểm sắp tới bất kỳ để xem đánh giá &amp; chuyển hướng
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
          {upcomingCheckpoints.map((cp, idx) => (
            <button
              key={cp.facility.id}
              type="button"
              data-testid={`upcoming-checkpoint-${idx}`}
              onClick={() => {
                if (!cp.isPrimaryDestination) {
                  onSwitchFacility(cp.facility);
                }
              }}
              className={`p-3.5 rounded-2xl border text-left transition-all cursor-pointer flex flex-col justify-between gap-2 ${
                cp.isPrimaryDestination
                  ? 'bg-sky-50/80 border-sky-500 shadow-xs ring-1 ring-sky-500/20'
                  : 'bg-slate-50/70 hover:bg-white border-slate-200/90 hover:border-slate-300'
              }`}
            >
              <div className="space-y-1">
                <div className="flex items-center justify-between gap-1">
                  <span
                    className={`px-2 py-0.5 rounded-md text-[10px] font-extrabold uppercase ${
                      cp.isPrimaryDestination
                        ? 'bg-sky-600 text-white'
                        : 'bg-slate-200/80 text-slate-700'
                    }`}
                  >
                    {cp.isPrimaryDestination ? 'ĐÍCH ĐẾN CHÍNH' : `SẮP TỚI #${idx}`}
                  </span>
                  <span className="text-xs font-extrabold text-amber-600 flex items-center gap-0.5 tabular-nums">
                    <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />
                    {cp.facility.rating.toFixed(1)} ({cp.facility.reviewsCount.toLocaleString()})
                  </span>
                </div>
                <div className="text-xs font-extrabold text-slate-900 line-clamp-1 mt-0.5">
                  {cp.facility.name}
                </div>
              </div>

              <div className="flex items-center justify-between text-[11px] pt-1.5 border-t border-slate-200/80 tabular-nums">
                <span className="text-slate-600 font-medium flex items-center gap-1">
                  <MapPin className="w-3 h-3 text-sky-600" />
                  Cách {cp.distanceKm} km (~{cp.etaMinutes}p)
                </span>
                <span className="text-emerald-700 font-bold">
                  Tiếp nhận ~{cp.facility.avgErWaitMinutes}p
                </span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* 2. TOP HEADER: GOOGLE PLACES API REVIEWS & HIGH-TRUST VERIFICATION */}
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200/80 pb-4">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="font-extrabold text-emerald-700 flex items-center gap-1">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <span>Google Places &amp; BookingCare Verified</span>
            </span>
            <span className="text-slate-300">•</span>
            <span className="font-bold text-sky-700 flex items-center gap-1">
              <Award className="w-3.5 h-3.5 text-sky-600" />
              <span>{facility.accreditationBadge}</span>
            </span>
            <span className="text-slate-300">•</span>
            <span className="font-mono text-[11px] text-slate-500">
              Place ID: {facility.googlePlaceId}
            </span>
          </div>

          <h3 className="text-base sm:text-lg font-extrabold text-slate-900 mt-1">
            Đánh Giá Thực Tế Của Người Bệnh &amp; Chỉ Dẫn Cổng Vào: {facility.name}
          </h3>
          <p className="text-xs text-slate-500">
            Đồng bộ trực tiếp cấu trúc Google Places Reviews API kết hợp xác thực GPS người bệnh • Cập nhật lúc {lastSynced}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={syncPlaceReviews}
            className="px-3 py-2 rounded-xl bg-slate-50 hover:bg-slate-100 text-emerald-700 border border-emerald-200 text-xs font-bold flex items-center gap-1.5 transition-all cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin' : ''}`} />
            <span>Get API Đánh Giá Mới</span>
          </button>

          <button
            type="button"
            data-testid="toggle-api-json-btn"
            onClick={() => setShowApiPayload(!showApiPayload)}
            className="px-3 py-2 rounded-xl bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 text-xs font-bold flex items-center gap-1.5 transition-all cursor-pointer"
          >
            <Code2 className="w-3.5 h-3.5 text-sky-600" />
            <span>{showApiPayload ? 'Ẩn JSON API' : 'Xem Google Places API JSON'}</span>
          </button>

          <button
            type="button"
            onClick={() => setShowWriteModal(!showWriteModal)}
            className="px-3.5 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold flex items-center gap-1.5 shadow-xs transition-all active:scale-95 cursor-pointer"
          >
            <MessageSquarePlus className="w-4 h-4" />
            <span>Gửi Đánh Giá Thực Tế</span>
          </button>
        </div>
      </div>

      {/* Live Google Places API JSON Inspector if opened */}
      {showApiPayload && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-3.5 text-xs space-y-2 text-slate-100">
          <div className="flex items-center justify-between text-sky-400 font-mono text-[11px]">
            <span>
              GET https://places.googleapis.com/v1/places/{facility.googlePlaceId}?fields=id,displayName,rating,userRatingCount,reviews
            </span>
            <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-sans font-bold">
              HTTP 200 OK • Verified Schema
            </span>
          </div>
          <pre className="font-mono text-[11px] text-slate-200 overflow-x-auto max-h-44 p-2.5 rounded-xl bg-slate-950 border border-slate-800">
            {JSON.stringify(
              {
                place_id: facility.googlePlaceId,
                name: facility.name,
                rating: facility.rating,
                user_ratings_total: totalReviewsCount,
                avg_er_wait_minutes: facility.avgErWaitMinutes,
                reviews_sample: reviews.slice(0, 2).map((r) => ({
                  author_name: r.authorName,
                  rating: r.rating,
                  relative_time_description: r.relativeTime,
                  service_tag: r.serviceTag,
                  text: r.comment,
                  verified_gps_visit: r.verifiedVisit,
                })),
              },
              null,
              2
            )}
          </pre>
        </div>
      )}

      {/* Write Review Form if opened */}
      {showWriteModal && (
        <form
          onSubmit={handleSubmitReview}
          className="bg-sky-50/60 border border-sky-200 rounded-2xl p-4 space-y-3"
        >
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-extrabold text-sky-800 uppercase tracking-wider">
              Đóng góp đánh giá thực tế về đường đi, cổng gửi xe &amp; chất lượng tiếp nhận
            </h4>
            <button
              type="button"
              onClick={() => setShowWriteModal(false)}
              className="text-xs text-slate-500 hover:text-slate-800 cursor-pointer font-bold"
            >
              ✕ Đóng
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <input
              type="text"
              value={newAuthor}
              onChange={(e) => setNewAuthor(e.target.value)}
              placeholder="Họ tên của bạn (vd: Nguyễn Văn A)"
              aria-label="Họ tên người đánh giá"
              className="bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-900"
            />
            <select
              value={newTag}
              onChange={(e) => setNewTag(e.target.value)}
              aria-label="Chuyên mục đánh giá"
              className="bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-900"
            >
              <option value="Đặt khám BookingCare & Cổng gửi xe">
                Đặt khám BookingCare &amp; Cổng gửi xe
              </option>
              <option value="Cấp cứu Đột quỵ / Tim mạch">Cấp cứu Đột quỵ / Tim mạch</option>
              <option value="Hãng Xe Cấp Cứu 115 đưa đón">Hãng Xe Cấp Cứu 115 đưa đón</option>
              <option value="Trình độ Y Bác sĩ & Thái độ">Trình độ Y Bác sĩ &amp; Thái độ</option>
            </select>
            <div className="flex items-center gap-1 bg-white border border-slate-200 rounded-xl px-3 py-2">
              <span className="text-xs text-slate-500 mr-1">Số sao:</span>
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  type="button"
                  onClick={() => setNewRating(star)}
                  className="p-0.5 cursor-pointer"
                  aria-label={`Chọn ${star} sao`}
                >
                  <Star
                    className={`w-4 h-4 ${
                      star <= newRating ? 'text-amber-400 fill-amber-400' : 'text-slate-300'
                    }`}
                  />
                </button>
              ))}
            </div>
          </div>

          <textarea
            rows={2}
            value={newComment}
            onChange={(e) => setNewComment(e.target.value)}
            placeholder="Chia sẻ kinh nghiệm đi cổng nào nhanh nhất, gửi xe máy/ô tô ở đâu, thời gian bác sĩ khám..."
            aria-label="Nội dung đánh giá"
            className="w-full bg-white border border-slate-200 rounded-xl p-3 text-xs text-slate-900"
          />

          <div className="flex justify-end">
            <button
              type="submit"
              className="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-bold text-xs transition-all cursor-pointer"
            >
              Đăng Đánh Giá Xác Thực
            </button>
          </div>
        </form>
      )}

      {/* 3. MAIN GRID: LEFT = RATING SUMMARY + VERIFIED REVIEWS | RIGHT = INSTANT BACKUP FACILITY SWITCHER */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left 7 Cols: Google Maps Score & Verified Patient Reviews */}
        <div className="lg:col-span-7 space-y-4">
          <div className="bg-slate-50/80 border border-slate-200/90 rounded-2xl p-4 grid grid-cols-1 sm:grid-cols-12 gap-4 items-center">
            <div className="sm:col-span-4 flex flex-col items-center justify-center text-center border-b sm:border-b-0 sm:border-r border-slate-200 pb-3 sm:pb-0 sm:pr-3">
              <div className="text-4xl font-black text-slate-900 tracking-tight tabular-nums">
                {facility.rating.toFixed(1)}
              </div>
              <div className="flex items-center gap-0.5 my-1">
                {[1, 2, 3, 4, 5].map((s) => (
                  <Star key={s} className="w-4 h-4 text-amber-400 fill-amber-400" />
                ))}
              </div>
              <div className="text-xs text-slate-600 font-bold tabular-nums">
                {totalReviewsCount.toLocaleString()} đánh giá xác thực
              </div>
              <div className="mt-1.5 px-2.5 py-0.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-[10px] font-bold">
                {facility.patientSatisfactionPercent}% Bệnh nhân hài lòng
              </div>
            </div>

            <div className="sm:col-span-8 space-y-2.5">
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-white p-2.5 rounded-xl border border-slate-200/80">
                  <div className="text-[10px] text-slate-500">Tốc độ tiếp nhận Cấp cứu / Khám</div>
                  <div className="flex items-center justify-between mt-0.5 tabular-nums">
                    <span className="text-xs font-extrabold text-emerald-700">
                      ~{facility.avgErWaitMinutes} phút
                    </span>
                    <span className="text-xs font-bold text-amber-600 flex items-center gap-0.5">
                      <span>{breakdown.emergencySpeedScore}</span>
                      <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                    </span>
                  </div>
                </div>

                <div className="bg-white p-2.5 rounded-xl border border-slate-200/80">
                  <div className="text-[10px] text-slate-500">Chuyên môn Y Bác sĩ</div>
                  <div className="flex items-center justify-between mt-0.5 tabular-nums">
                    <span className="text-xs font-extrabold text-sky-700">Đầu ngành</span>
                    <span className="text-xs font-bold text-amber-600 flex items-center gap-0.5">
                      <span>{breakdown.doctorExpertiseScore}</span>
                      <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                    </span>
                  </div>
                </div>

                <div className="bg-white p-2.5 rounded-xl border border-slate-200/80">
                  <div className="text-[10px] text-slate-500">Hạ tầng Cổng vào &amp; Thiết bị</div>
                  <div className="flex items-center justify-between mt-0.5 tabular-nums">
                    <span className="text-xs font-extrabold text-slate-800">Hiện đại 24/7</span>
                    <span className="text-xs font-bold text-amber-600 flex items-center gap-0.5">
                      <span>{breakdown.equipmentModernityScore}</span>
                      <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                    </span>
                  </div>
                </div>

                <div className="bg-white p-2.5 rounded-xl border border-slate-200/80">
                  <div className="text-[10px] text-slate-500">Minh bạch BHYT &amp; Đặt khám</div>
                  <div className="flex items-center justify-between mt-0.5 tabular-nums">
                    <span className="text-xs font-extrabold text-emerald-700">Đúng niêm yết</span>
                    <span className="text-xs font-bold text-amber-600 flex items-center gap-0.5">
                      <span>{breakdown.insuranceTransparencyScore}</span>
                      <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Filter Pills for Reviews */}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-1.5">
              {[
                { id: 'all' as const, label: `Tất cả (${reviews.length})` },
                { id: 'emergency' as const, label: 'Cấp cứu & Hồi sức' },
                { id: 'booking_gate' as const, label: 'Đường đi & Cổng vào khám' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setReviewFilter(tab.id)}
                  className={`px-3 py-1 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                    reviewFilter === tab.id
                      ? 'bg-sky-600 text-white shadow-2xs'
                      : 'bg-slate-100 text-slate-600 hover:text-slate-900'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* Patient Reviews List */}
          <div className="space-y-3 max-h-[360px] overflow-y-auto pr-1">
            {filteredReviews.map((rev) => (
              <div
                key={rev.id}
                className="p-3.5 rounded-2xl bg-slate-50/60 border border-slate-200/90 space-y-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    <div
                      className={`w-8 h-8 rounded-full ${rev.avatarColor} text-white font-black text-xs flex items-center justify-center shrink-0`}
                    >
                      {rev.authorName.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="text-xs font-extrabold text-slate-900">{rev.authorName}</span>
                        {rev.verifiedVisit && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-0.5 font-semibold">
                            <CheckCircle2 className="w-2.5 h-2.5" /> Đã xác thực GPS / BHYT
                          </span>
                        )}
                      </div>
                      <div className="text-[10px] text-slate-500">{rev.authorRole}</div>
                    </div>
                  </div>

                  <div className="text-right">
                    <div className="flex items-center justify-end gap-0.5">
                      {Array.from({ length: rev.rating }).map((_, idx) => (
                        <Star key={idx} className="w-3 h-3 text-amber-400 fill-amber-400" />
                      ))}
                    </div>
                    <div className="text-[10px] text-slate-400 mt-0.5">{rev.relativeTime}</div>
                  </div>
                </div>

                <div className="inline-block px-2 py-0.5 rounded-md bg-sky-50 border border-sky-200/80 text-sky-800 text-[10px] font-bold">
                  {rev.serviceTag}
                </div>

                <p className="text-xs text-slate-700 leading-relaxed">{rev.comment}</p>

                {rev.facilityReply && (
                  <div className="bg-white border-l-2 border-sky-500 p-2.5 rounded-r-xl text-[11px] space-y-1">
                    <div className="font-bold text-sky-800">
                      Phản hồi từ {rev.facilityReply.responder} ({rev.facilityReply.time}):
                    </div>
                    <p className="text-slate-600">{rev.facilityReply.text}</p>
                  </div>
                )}

                <div className="flex items-center justify-between pt-1 text-[11px] text-slate-500">
                  <button
                    type="button"
                    onClick={() =>
                      setHelpfulClickedIds((prev) => ({ ...prev, [rev.id]: !prev[rev.id] }))
                    }
                    className={`flex items-center gap-1 font-semibold transition-colors cursor-pointer ${
                      helpfulClickedIds[rev.id]
                        ? 'text-sky-700'
                        : 'text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    <ThumbsUp className="w-3 h-3" />
                    <span>
                      Hữu ích ({rev.helpfulCount + (helpfulClickedIds[rev.id] ? 1 : 0)})
                    </span>
                  </button>
                  <span>Nguồn: Google Maps Places &amp; BookingCare</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right 5 Cols: Instant Alternative Hospital Switcher */}
        <div className="lg:col-span-5 flex flex-col justify-between bg-slate-50/70 border border-slate-200/90 rounded-2xl p-4 space-y-4">
          <div className="space-y-3">
            <div>
              <span className="text-[10px] font-extrabold uppercase tracking-wider text-teal-700">
                ĐỐI CHIẾU &amp; CHUYỂN HƯỚNG BỆNH VIỆN DỰ PHÒNG
              </span>
              <h4 className="text-sm sm:text-base font-extrabold text-slate-900 mt-0.5">
                Ngại Quá Tải Hoặc Muốn Đổi Sang Cơ Sở Uy Tín Khác Gần Bạn?
              </h4>
              <p className="text-xs text-slate-500 mt-0.5">
                Hệ thống tự động xếp hạng các bệnh viện cùng khu vực theo điểm đánh giá thực tế và thời gian chờ tiếp nhận
              </p>
            </div>

            <div className="space-y-2.5 max-h-[380px] overflow-y-auto pr-1">
              {alternatives.slice(0, 4).map((alt) => (
                <div
                  key={alt.facility.id}
                  className="p-3.5 rounded-2xl bg-white hover:border-slate-300 border border-slate-200/90 transition-all space-y-2 shadow-2xs"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="px-2 py-0.5 rounded bg-sky-50 text-sky-700 border border-sky-200/80 text-[10px] font-extrabold">
                          {alt.matchBadge}
                        </span>
                        <span className="text-[11px] text-slate-500 font-medium tabular-nums">
                          Cách {alt.distanceKm} km (~{alt.etaMinutes} phút)
                        </span>
                      </div>
                      <h5 className="text-xs sm:text-sm font-extrabold text-slate-900 mt-1 leading-snug">
                        {alt.facility.name}
                      </h5>
                    </div>

                    <div className="bg-amber-50 border border-amber-200 rounded-xl px-2.5 py-1 text-center shrink-0 tabular-nums">
                      <div className="text-sm font-black text-amber-600 flex items-center justify-center gap-0.5">
                        <span>{alt.facility.rating.toFixed(1)}</span>
                        <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />
                      </div>
                      <div className="text-[9px] text-amber-800/80 font-semibold">
                        {alt.facility.reviewsCount.toLocaleString()} lượt
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-1.5">
                    {alt.switchReasons.map((reason, idx) => (
                      <span
                        key={idx}
                        className="text-[10px] px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 font-medium"
                      >
                        • {reason}
                      </span>
                    ))}
                  </div>

                  <div className="flex items-center gap-2 pt-1">
                    <button
                      type="button"
                      onClick={() => onSwitchFacility(alt.facility)}
                      className="flex-1 px-3 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-bold text-xs flex items-center justify-center gap-1.5 transition-all active:scale-95 cursor-pointer"
                    >
                      <ArrowRightLeft className="w-3.5 h-3.5" />
                      <span>Chỉ Đường 3D Sang Cơ Sở Này</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => onCallHotline(alt.facility.emergencyHotline)}
                      className="px-3 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs flex items-center gap-1 transition-all cursor-pointer"
                    >
                      <PhoneCall className="w-3.5 h-3.5 text-emerald-600" />
                      <span>Gọi</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="pt-2 border-t border-slate-200/80 flex items-center justify-between text-[11px] text-slate-500">
            <span>Xác thực đa nguồn: Google Places + BHYT + BookingCare</span>
            <span className="text-emerald-600 font-bold">● Real-Time Sync</span>
          </div>
        </div>
      </div>
    </section>
  );
};
