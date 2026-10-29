import {
  ArrowRight,
  HeartPulse,
  Route,
  Sparkles,
  UserRound,
  WalletCards,
  CalendarClock,
  CalendarDays,
  Settings,
} from 'lucide-react';

const ICONS = {
  health: HeartPulse,
  spending: WalletCards,
  schedule: CalendarClock,
  medication: CalendarDays,
  companion: Sparkles,
  navigation: Route,
  profile: UserRound,
  settings: Settings,
};

export function QuickNavActionCard({
  navCommand,
  onNavigate,
}) {
  if (!navCommand || !navCommand.isNavCommand) return null;

  const Icon = ICONS[navCommand.targetView] || ArrowRight;

  return (
    <div className="chat-action-card quick-nav-card" role="region" aria-label="Điều hướng màn hình nhanh">
      <div className="quick-nav-left">
        <div className="quick-nav-icon">
          <Icon size={16} />
        </div>
        <div className="quick-nav-info">
          <span className="quick-nav-kicker">ĐIỀU HƯỚNG THEO YÊU CẦU</span>
          <strong className="quick-nav-title">{navCommand.label}</strong>
        </div>
      </div>
      <button
        type="button"
        className="quick-nav-btn"
        onClick={() => onNavigate?.(navCommand.targetView)}
      >
        <span>Mở ngay</span>
        <ArrowRight size={14} />
      </button>
    </div>
  );
}
