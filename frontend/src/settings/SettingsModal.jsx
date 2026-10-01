import { useEffect, useState } from 'react';
import {
  Activity,
  Bell,
  Check,
  Cpu,
  Database,
  Download,
  Eye,
  FileText,
  HeartPulse,
  Lock,
  Moon,
  Pill,
  Save,
  Server,
  Settings,
  Shield,
  Sun,
  Trash2,
  User,
  Volume2,
  VolumeX,
  Workflow,
  X,
} from 'lucide-react';
import { Field, SelectInput, TextInput } from '../components';
import { SystemModule } from '../modules/SystemModule';

const DEFAULT_SETTINGS = {
  theme: 'system', // 'system', 'light', 'dark'
  fontSize: 'standard', // 'standard', 'large'
  locale: 'vi-VN',
  soundEnabled: true,
  reminderMorning: '08:00',
  reminderNoon: '12:30',
  reminderEvening: '18:30',
  reminderNight: '21:00',
  enablePushReminders: true,
  urgentReminder: true,
};

function loadStoredSettings() {
  try {
    const raw = localStorage.getItem('medguard.settings.preferences');
    return raw ? { ...DEFAULT_SETTINGS, ...JSON.parse(raw) } : DEFAULT_SETTINGS;
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function SettingsModal({
  open,
  onClose,
  initialTab = 'general',
  context,
  onSaveProfile,
  onClearProfile,
  api,
  tenantId,
  onClearAllChat,
  onExportData,
  onNotify,
}) {
  const [activeTab, setActiveTab] = useState(initialTab);
  const [preferences, setPreferences] = useState(loadStoredSettings);
  const [profileDraft, setProfileDraft] = useState(() => ({
    display_name: context?.display_name || '',
    patient_ref: context?.patient_ref || '',
    age: context?.age ?? '',
    sex: context?.sex || '',
    current_medications: Array.isArray(context?.current_medications)
      ? context.current_medications.join(', ')
      : context?.current_medications || '',
    allergies: Array.isArray(context?.allergies)
      ? context.allergies.join(', ')
      : context?.allergies || '',
    conditions: Array.isArray(context?.conditions)
      ? context.conditions.join(', ')
      : context?.conditions || '',
  }));
  const [saveToast, setSaveToast] = useState(false);

  useEffect(() => {
    if (open) {
      setActiveTab(initialTab);
      setProfileDraft({
        display_name: context?.display_name || '',
        patient_ref: context?.patient_ref || '',
        age: context?.age ?? '',
        sex: context?.sex || '',
        current_medications: Array.isArray(context?.current_medications)
          ? context.current_medications.join(', ')
          : context?.current_medications || '',
        allergies: Array.isArray(context?.allergies)
          ? context.allergies.join(', ')
          : context?.allergies || '',
        conditions: Array.isArray(context?.conditions)
          ? context.conditions.join(', ')
          : context?.conditions || '',
      });
    }
  }, [open, initialTab, context]);

  const updatePref = (key, value) => {
    setPreferences((prev) => {
      const next = { ...prev, [key]: value };
      try {
        localStorage.setItem('medguard.settings.preferences', JSON.stringify(next));
      } catch {
        // Fallback for storage restricted environments
      }
      return next;
    });
  };

  const handleSaveProfile = async (e) => {
    e.preventDefault();
    const parseList = (str) =>
      str
        .split(',')
        .map((s) => s.trim())
        .filter((s) => s && !['không', 'khong', 'none'].includes(s.toLowerCase()));

    const saved = await onSaveProfile?.({
      display_name: profileDraft.display_name.trim(),
      patient_ref: profileDraft.patient_ref.trim().toUpperCase(),
      age: profileDraft.age === '' ? null : Number(profileDraft.age),
      sex: profileDraft.sex || null,
      current_medications: parseList(profileDraft.current_medications),
      allergies: parseList(profileDraft.allergies),
      conditions: parseList(profileDraft.conditions),
    });
    if (saved === false) return;
    setSaveToast(true);
    onNotify?.('Đã lưu thông tin hồ sơ sức khỏe');
    setTimeout(() => setSaveToast(false), 2000);
  };

  if (!open) return null;

  return (
    <div className="settings-dialog-overlay" role="dialog" aria-modal="true" aria-label="Cài đặt hệ thống">
      <div className="settings-dialog-scrim" onClick={onClose} />
      <div className="settings-dialog-window">
        {/* Header */}
        <header className="settings-header">
          <div className="settings-header-title">
            <span className="settings-icon-badge">
              <Settings size={20} />
            </span>
            <div>
              <h2>Cài đặt</h2>
              <p>Tùy chỉnh giao diện, hồ sơ sức khỏe và cấu hình MedGuard AI</p>
            </div>
          </div>
          <button
            type="button"
            className="icon-button settings-close-btn"
            onClick={onClose}
            aria-label="Đóng cài đặt"
            title="Đóng (Esc)"
          >
            <X size={20} />
          </button>
        </header>

        {/* Layout: Sidebar Tabs + Content Area */}
        <div className="settings-body">
          <nav className="settings-sidebar" aria-label="Các mục cài đặt">
            <button
              type="button"
              className={`settings-nav-item ${activeTab === 'general' ? 'active' : ''}`}
              onClick={() => setActiveTab('general')}
            >
              <Sun size={17} />
              <span>Chung & Giao diện</span>
            </button>
            <button
              type="button"
              className={`settings-nav-item ${activeTab === 'profile' ? 'active' : ''}`}
              onClick={() => setActiveTab('profile')}
            >
              <HeartPulse size={17} />
              <span>Hồ sơ sức khỏe</span>
            </button>
            <button
              type="button"
              className={`settings-nav-item ${activeTab === 'reminders' ? 'active' : ''}`}
              onClick={() => setActiveTab('reminders')}
            >
              <Bell size={17} />
              <span>Nhắc nhở uống thuốc</span>
            </button>
            <button
              type="button"
              className={`settings-nav-item ${activeTab === 'privacy' ? 'active' : ''}`}
              onClick={() => setActiveTab('privacy')}
            >
              <Shield size={17} />
              <span>Dữ liệu & Quyền riêng tư</span>
            </button>
          </nav>

          {/* Tab Content Panels */}
          <section className="settings-content-panel">
            {activeTab === 'general' && (
              <div className="settings-pane animate-fade-in">
                <div className="pane-section">
                  <h3>Chủ đề giao diện (Theme)</h3>
                  <p className="pane-desc">Chọn phong cách hiển thị màu sắc phù hợp với môi trường làm việc.</p>
                  <div className="theme-toggle-group">
                    <button
                      type="button"
                      className={`theme-option ${preferences.theme === 'light' ? 'selected' : ''}`}
                      onClick={() => updatePref('theme', 'light')}
                    >
                      <Sun size={18} />
                      <strong>Sáng</strong>
                      <span>Giao diện chuẩn y tế</span>
                    </button>
                    <button
                      type="button"
                      className={`theme-option ${preferences.theme === 'dark' ? 'selected' : ''}`}
                      onClick={() => updatePref('theme', 'dark')}
                    >
                      <Moon size={18} />
                      <strong>Tối</strong>
                      <span>Dịu mắt khi trực đêm</span>
                    </button>
                    <button
                      type="button"
                      className={`theme-option ${preferences.theme === 'system' ? 'selected' : ''}`}
                      onClick={() => updatePref('theme', 'system')}
                    >
                      <Cpu size={18} />
                      <strong>Tự động</strong>
                      <span>Theo hệ điều hành</span>
                    </button>
                  </div>
                </div>

                <div className="pane-divider" />

                <div className="pane-section">
                  <h3>Cỡ chữ nội dung lâm sàng</h3>
                  <p className="pane-desc">Tăng kích thước chữ giúp người lớn tuổi hoặc bác sĩ đọc nhanh triệu chứng dễ dàng hơn.</p>
                  <div className="font-size-row">
                    <button
                      type="button"
                      className={`pill-option ${preferences.fontSize === 'standard' ? 'active' : ''}`}
                      onClick={() => updatePref('fontSize', 'standard')}
                    >
                      Tiêu chuẩn (15px)
                    </button>
                    <button
                      type="button"
                      className={`pill-option ${preferences.fontSize === 'large' ? 'active' : ''}`}
                      onClick={() => updatePref('fontSize', 'large')}
                    >
                      Cỡ chữ lớn (17px - Dễ đọc)
                    </button>
                  </div>
                </div>

                <div className="pane-divider" />

                <div className="pane-section">
                  <h3>Phản hồi âm thanh & Giọng đọc</h3>
                  <div className="toggle-row">
                    <div>
                      <strong>Âm thanh thông báo khi có trả lời</strong>
                      <p>Phát âm thanh nhẹ khi MedGuard AI hoàn thành phân tích lâm sàng.</p>
                    </div>
                    <button
                      type="button"
                      className={`switch-toggle ${preferences.soundEnabled ? 'checked' : ''}`}
                      onClick={() => updatePref('soundEnabled', !preferences.soundEnabled)}
                      aria-label="Bật tắt âm thanh"
                    >
                      <span className="switch-knob" />
                    </button>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'profile' && (
              <form className="settings-pane animate-fade-in" onSubmit={handleSaveProfile}>
                <div className="pane-section">
                  <div className="section-head-with-badge">
                    <h3>Hồ sơ sức khỏe cá nhân</h3>
                    <span className="secure-badge">
                      <Lock size={13} /> Lưu cục bộ an toàn
                    </span>
                  </div>
                  <p className="pane-desc">
                    Thông tin này giúp MedGuard AI đưa ra cảnh báo tương tác thuốc và liều dùng chính xác hơn cho riêng bạn.
                  </p>

                  <div className="profile-form-grid">
                    <Field label="Tên người dùng / Tên hiển thị">
                      <TextInput
                        value={profileDraft.display_name}
                        onChange={(e) => setProfileDraft((p) => ({ ...p, display_name: e.target.value }))}
                        placeholder="Ví dụ: Nguyễn Văn An"
                      />
                    </Field>

                    <div className="grid-2-cols">
                      <Field label="Tuổi">
                        <TextInput
                          type="number"
                          min="0"
                          max="120"
                          value={profileDraft.age}
                          onChange={(e) => setProfileDraft((p) => ({ ...p, age: e.target.value }))}
                          placeholder="45"
                        />
                      </Field>
                      <Field label="Giới tính">
                        <SelectInput
                          value={profileDraft.sex}
                          onChange={(e) => setProfileDraft((p) => ({ ...p, sex: e.target.value }))}
                        >
                          <option value="">Chưa cung cấp</option>
                          <option value="male">Nam</option>
                          <option value="female">Nữ</option>
                          <option value="other">Khác</option>
                        </SelectInput>
                      </Field>
                    </div>

                    <Field label="Mã hồ sơ bệnh án (tùy chọn)">
                      <TextInput
                        value={profileDraft.patient_ref}
                        onChange={(e) => setProfileDraft((p) => ({ ...p, patient_ref: e.target.value }))}
                        placeholder="BN-1082"
                      />
                    </Field>

                    <Field label="Tiền sử bệnh nền">
                      <TextInput
                        value={profileDraft.conditions}
                        onChange={(e) => setProfileDraft((p) => ({ ...p, conditions: e.target.value }))}
                        placeholder="Tăng huyết áp, Đái tháo đường type 2, Viêm loét dạ dày..."
                      />
                    </Field>

                    <Field label="Dị ứng đã biết (Thuốc, Thức ăn)">
                      <TextInput
                        value={profileDraft.allergies}
                        onChange={(e) => setProfileDraft((p) => ({ ...p, allergies: e.target.value }))}
                        placeholder="Penicillin, Aspirin, Hải sản..."
                      />
                    </Field>

                    <Field label="Thuốc đang dùng hàng ngày">
                      <TextInput
                        value={profileDraft.current_medications}
                        onChange={(e) => setProfileDraft((p) => ({ ...p, current_medications: e.target.value }))}
                        placeholder="Amlodipine 5mg, Metformin 500mg, Panadol..."
                      />
                    </Field>
                  </div>

                  <div className="pane-actions-row">
                    <button
                      type="button"
                      className="secondary-button danger-action"
                      onClick={() => {
                        onClearProfile?.();
                        setProfileDraft({
                          display_name: '',
                          patient_ref: '',
                          age: '',
                          sex: '',
                          current_medications: '',
                          allergies: '',
                          conditions: '',
                        });
                        onNotify?.('Đã xóa thông tin hồ sơ sức khỏe');
                      }}
                    >
                      <Trash2 size={15} /> Xóa hồ sơ
                    </button>
                    <button type="submit" className="primary-button save-profile-btn">
                      {saveToast ? <Check size={16} /> : <Save size={16} />}
                      <span>{saveToast ? 'Đã lưu thành công!' : 'Lưu hồ sơ sức khỏe'}</span>
                    </button>
                  </div>
                </div>
              </form>
            )}

            {activeTab === 'reminders' && (
              <div className="settings-pane animate-fade-in">
                <div className="pane-section">
                  <h3>Cấu hình giờ nhắc uống thuốc</h3>
                  <p className="pane-desc">
                    Hệ thống sẽ gửi thông báo và chuông nhắc khi đến các cữ thuốc trong ngày của bạn.
                  </p>

                  <div className="toggle-row">
                    <div>
                      <strong>Bật thông báo đẩy lịch uống thuốc</strong>
                      <p>Nhận thông báo nổi trên trình duyệt khi tới giờ uống thuốc.</p>
                    </div>
                    <button
                      type="button"
                      className={`switch-toggle ${preferences.enablePushReminders ? 'checked' : ''}`}
                      onClick={() => updatePref('enablePushReminders', !preferences.enablePushReminders)}
                      aria-label="Bật tắt thông báo đẩy"
                    >
                      <span className="switch-knob" />
                    </button>
                  </div>

                  <div className="pane-divider" />

                  <h4>Khung giờ nhắc mặc định</h4>
                  <div className="reminder-time-grid">
                    <div className="time-card">
                      <span className="time-icon morning">☀️</span>
                      <div>
                        <strong>Cữ Sáng</strong>
                        <span>Sau bữa sáng</span>
                      </div>
                      <input
                        type="time"
                        value={preferences.reminderMorning}
                        onChange={(e) => updatePref('reminderMorning', e.target.value)}
                        className="time-input-styled"
                      />
                    </div>

                    <div className="time-card">
                      <span className="time-icon noon">🌤️</span>
                      <div>
                        <strong>Cữ Trưa</strong>
                        <span>Cùng bữa trưa</span>
                      </div>
                      <input
                        type="time"
                        value={preferences.reminderNoon}
                        onChange={(e) => updatePref('reminderNoon', e.target.value)}
                        className="time-input-styled"
                      />
                    </div>

                    <div className="time-card">
                      <span className="time-icon evening">🌇</span>
                      <div>
                        <strong>Cữ Chiều / Tối</strong>
                        <span>Trước bữa tối</span>
                      </div>
                      <input
                        type="time"
                        value={preferences.reminderEvening}
                        onChange={(e) => updatePref('reminderEvening', e.target.value)}
                        className="time-input-styled"
                      />
                    </div>

                    <div className="time-card">
                      <span className="time-icon night">🌙</span>
                      <div>
                        <strong>Cữ Khuya</strong>
                        <span>Trước khi ngủ</span>
                      </div>
                      <input
                        type="time"
                        value={preferences.reminderNight}
                        onChange={(e) => updatePref('reminderNight', e.target.value)}
                        className="time-input-styled"
                      />
                    </div>
                  </div>

                  <div className="pane-divider" />

                  <div className="toggle-row">
                    <div>
                      <strong>Cảnh báo nhắc lại khi quên liều</strong>
                      <p>Tự động nhắc lại sau 15 phút nếu người dùng chưa bấm nút "Đã uống".</p>
                    </div>
                    <button
                      type="button"
                      className={`switch-toggle ${preferences.urgentReminder ? 'checked' : ''}`}
                      onClick={() => updatePref('urgentReminder', !preferences.urgentReminder)}
                      aria-label="Bật tắt nhắc lại quên liều"
                    >
                      <span className="switch-knob" />
                    </button>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'privacy' && (
              <div className="settings-pane animate-fade-in">
                <div className="pane-section">
                  <h3>Bảo mật & Quyền riêng tư y tế</h3>
                  <p className="pane-desc">
                    Dữ liệu trao đổi y tế của bạn được xử lý bảo mật theo tiêu chuẩn đạo đức AI và bảo mật thông tin sức khỏe.
                  </p>

                  <div className="security-card">
                    <div className="security-icon-wrap">
                      <Shield size={24} />
                    </div>
                    <div>
                      <strong>Mã hóa đầu cuối & Không chia sẻ dữ liệu</strong>
                      <p>
                        Thông tin lâm sàng, triệu chứng và lịch uống thuốc được lưu cục bộ an toàn trên thiết bị của bạn.
                        MedGuard AI không chia sẻ dữ liệu y bạ với bên thứ ba vì mục đích thương mại.
                      </p>
                    </div>
                  </div>

                  <div className="pane-divider" />

                  <h3>Quản lý dữ liệu hội thoại</h3>
                  <div className="action-tile-row">
                    <div>
                      <strong>Tải về dữ liệu sức khỏe & hội thoại (Export JSON)</strong>
                      <p>Xuất file dữ liệu cá nhân bao gồm lịch sử tư vấn và danh sách đơn thuốc.</p>
                    </div>
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => {
                        onExportData?.();
                        onNotify?.('Đã xuất dữ liệu y bạ cá nhân');
                      }}
                    >
                      <Download size={15} /> Tải dữ liệu
                    </button>
                  </div>

                  <div className="pane-divider" />

                  <div className="action-tile-row danger-zone">
                    <div>
                      <strong className="danger-text">Xóa toàn bộ lịch sử trò chuyện</strong>
                      <p>Hành động này sẽ xóa vĩnh viễn tất cả cuộc hội thoại trước đây và không thể khôi phục.</p>
                    </div>
                    <button
                      type="button"
                      className="secondary-button danger-action"
                      onClick={() => {
                        if (window.confirm('Bạn có chắc chắn muốn xóa toàn bộ lịch sử trò chuyện không?')) {
                          onClearAllChat?.();
                          onNotify?.('Đã xóa toàn bộ lịch sử trò chuyện');
                        }
                      }}
                    >
                      <Trash2 size={15} /> Xóa tất cả
                    </button>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'system' && (
              <div className="settings-pane system-tab-pane animate-fade-in">
                <div className="pane-section">
                  <div className="section-head-with-badge">
                    <h3>Kiểm định & Trạng thái hệ thống</h3>
                    <span className="dev-tag">System Diagnostic</span>
                  </div>
                  <p className="pane-desc">
                    Trạng thái kết nối cơ sở dữ liệu nội bộ, kiểm thử an toàn lâm sàng và nhật ký audit event.
                  </p>

                  <div className="system-wrapper-box">
                    <SystemModule api={api} tenantId={tenantId} />
                  </div>
                </div>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
