import {
  Compass,
  CornerUpRight,
  ExternalLink,
  MapPin,
  Navigation,
  Route,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';

export function NavigationActionCard({
  action,
  onOpenNavigation,
}) {
  const nav = action?.navigation;
  if (!nav) return null;

  const isEmergency = nav.category === 'emergency';

  return (
    <div
      className={`chat-action-card nav-action-card ${isEmergency ? 'emergency' : ''}`}
      role="region"
      aria-label="Đề xuất chỉ đường đến cơ sở y tế"
    >
      <div className="card-header">
        <div className={`card-header-icon nav-icon ${isEmergency ? 'emergency' : ''}`}>
          {isEmergency ? <ShieldAlert size={18} /> : <Route size={18} />}
        </div>
        <div className="card-header-text">
          <div className="card-title-row">
            <strong>{isEmergency ? 'Cấp cứu & Chỉ đường Khẩn cấp' : 'Đề xuất Định tuyến & Chỉ đường'}</strong>
            <span className={`status-badge ${isEmergency ? 'emergency-tag' : 'nav-tag'}`}>
              {nav.categoryLabel}
            </span>
          </div>
          <span className="card-subtitle">
            Hệ thống tự động tìm kiếm cơ sở y tế phù hợp với yêu cầu của bạn
          </span>
        </div>
      </div>

      <div className="nav-details-box">
        <div className="nav-target-row">
          <div className="target-name-wrap">
            <MapPin size={16} className="pin-icon" />
            <strong className="poi-title">{nav.poiName}</strong>
          </div>
          <div className="nav-metrics-pill">
            <Compass size={12} />
            <span>{nav.distance}</span>
            <span className="dot">•</span>
            <span>{nav.duration}</span>
          </div>
        </div>

        <p className="nav-address-text">{nav.address}</p>
      </div>

      <div className="nav-action-row">
        <button
          type="button"
          className="nav-action-btn"
          onClick={() => onOpenNavigation?.(nav)}
        >
          <Navigation size={15} />
          <span>Mở Bản Đồ Chỉ Đường 3D Real-time</span>
          <CornerUpRight size={14} className="arrow-icon" />
        </button>
      </div>
    </div>
  );
}
