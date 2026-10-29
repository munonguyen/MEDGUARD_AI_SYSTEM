import { useState, useCallback, useRef } from "react";

export const MAP_INTERACTION_STATES = {
  IDLE_STANDBY: "idle_standby",
  SCANNING_RADAR: "scanning_radar",
  REVIEW_INSPECTED: "review_inspected",
  ACTIVE_NAVIGATION: "active_navigation",
};

export function useOnDemandMedicalMap() {
  const [mapState, setMapState] = useState(MAP_INTERACTION_STATES.IDLE_STANDBY);
  const [isRadarScanning, setIsRadarScanning] = useState(false);
  const [revealedCount, setRevealedCount] = useState(99);
  const [scanGeneration, setScanGeneration] = useState(1);
  const [activeReviewPoi, setActiveReviewPoi] = useState(null);
  const timerRef = useRef(null);

  const triggerOnDemandScan = useCallback(async (options = {}) => {
    const total = Math.max(1, options.totalPoisCount || 8);
    setIsRadarScanning(true);
    setMapState(MAP_INTERACTION_STATES.SCANNING_RADAR);
    // Đặt toàn bộ số lượng ngay lập tức để Leaflet/MapLibre không xóa/tạo lại DOM nhiều lần,
    // hiệu ứng xuất hiện tuần tự sẽ do CSS animation-delay đảm nhiệm mượt mà
    setRevealedCount(total);
    setScanGeneration((g) => g + 1);

    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setIsRadarScanning(false);
    }, 950);
  }, []);

  const openGoogleReviewsPanel = useCallback((poi) => {
    setActiveReviewPoi(poi);
    setMapState(MAP_INTERACTION_STATES.REVIEW_INSPECTED);
  }, []);

  const closeGoogleReviewsPanel = useCallback(() => {
    setActiveReviewPoi(null);
    setMapState((prev) =>
      prev === MAP_INTERACTION_STATES.REVIEW_INSPECTED
        ? MAP_INTERACTION_STATES.SCANNING_RADAR
        : prev
    );
  }, []);

  const startDestinationNavigation = useCallback(() => {
    setActiveReviewPoi(null);
    setMapState(MAP_INTERACTION_STATES.ACTIVE_NAVIGATION);
  }, []);

  const resetToOverview = useCallback(() => {
    setMapState(MAP_INTERACTION_STATES.IDLE_STANDBY);
    setActiveReviewPoi(null);
    setRevealedCount(99);
  }, []);

  return {
    mapState,
    setMapState,
    isRadarScanning,
    revealedCount,
    scanGeneration,
    activeReviewPoi,
    triggerOnDemandScan,
    openGoogleReviewsPanel,
    closeGoogleReviewsPanel,
    startDestinationNavigation,
    resetToOverview,
  };
}
