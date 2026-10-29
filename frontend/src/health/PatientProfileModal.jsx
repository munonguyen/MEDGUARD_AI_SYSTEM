import { useState, useId } from 'react';
import {
  Activity,
  AlertTriangle,
  BadgeCheck,
  Building2,
  CalendarDays,
  Check,
  CreditCard,
  Droplet,
  HeartPulse,
  Mail,
  MapPin,
  Phone,
  Pill,
  Save,
  Scale,
  Shield,
  ShieldCheck,
  Sparkles,
  Trash2,
  UserCheck,
  UserRound,
  X,
} from 'lucide-react';
import { calculateBmi } from './profileDisambiguation';

function parseList(value) {
  if (Array.isArray(value)) return value;
  if (!value || typeof value !== 'string') return [];
  return value
    .split(',')
    .map((item) => item.trim())
    .filter((item) => item && !['không', 'khong', 'none'].includes(item.toLowerCase()));
}

const COMMON_HOSPITALS = [
  'Bệnh viện Chợ Rẫy (79-011)',
  'Bệnh viện Bạch Mai (01-001)',
  'Bệnh viện Đại học Y Dược TP.HCM (79-026)',
  'Bệnh viện Hữu nghị Việt Đức (01-002)',
  'Bệnh viện Đa khoa Đà Nẵng (48-001)',
  'Bệnh viện Quân Y 175 (79-012)',
  'Bệnh viện Thống Nhất (79-010)',
  'Bệnh viện K Trung ương (01-004)'
];

const LIFE_INSURERS = [
  'Prudential',
  'Manulife',
  'Bảo Việt Nhân Thọ',
  'Dai-ichi Life',
  'AIA',
  'Generali',
  'MB Ageas Life',
  'PVI Care',
  'Chubb Life'
];

export function PatientProfileModal({ open, context = {}, onSave, onClear, onClose }) {
  if (!open) return null;

  const [activeTab, setActiveTab] = useState('general');
  const [draft, setDraft] = useState({
    display_name: context.display_name || '',
    patient_ref: context.patient_ref || '',
    dob: context.dob || '',
    age: context.age ?? '',
    sex: context.sex || '',
    phone: context.phone || '',
    email: context.email || '',
    address: context.address || '',
    blood_type: context.blood_type || '',
    height_cm: context.height_cm ?? '',
    weight_kg: context.weight_kg ?? '',
    bhyt_number: context.bhyt_number || '',
    bhyt_hospital: context.bhyt_hospital || '',
    bhyt_rate: context.bhyt_rate ?? 80,
    bhxh_number: context.bhxh_number || '',
    vssid_status: context.vssid_status || (context.bhxh_number ? 'verified' : 'unlinked'),
    life_insurance_provider: context.life_insurance_provider || '',
    life_insurance_policy_no: context.life_insurance_policy_no || '',
    coverage_limit_vnd: context.coverage_limit_vnd ?? '',
    is_verified: context.is_verified || Boolean(context.bhyt_number),
    current_medications: Array.isArray(context.current_medications) ? context.current_medications.join(', ') : (context.current_medications || ''),
    allergies: Array.isArray(context.allergies) ? context.allergies.join(', ') : (context.allergies || ''),
    conditions: Array.isArray(context.conditions) ? context.conditions.join(', ') : (context.conditions || ''),
    emergency_contact_name: context.emergency_contact_name || '',
    emergency_contact_phone: context.emergency_contact_phone || '',
    emergency_contact_relation: context.emergency_contact_relation || '',
  });

  const update = (key, val) => {
    setDraft((prev) => {
      const next = { ...prev, [key]: val };
      if (key === 'dob' && val) {
        const year = parseInt(val.split('-')[0], 10);
        if (year > 1900 && year <= 2026) {
          next.age = 2026 - year;
        }
      }
      return next;
    });
  };

  const bmiData = calculateBmi(
    draft.height_cm ? Number(draft.height_cm) : null,
    draft.weight_kg ? Number(draft.weight_kg) : null
  );

  const handleSubmit = (e) => {
    e.preventDefault();
    const finalProfile = {
      display_name: draft.display_name.trim(),
      patient_ref: draft.patient_ref.trim().toUpperCase() || (draft.display_name ? `BN-${draft.display_name.trim().slice(0, 3).toUpperCase()}-01` : 'BN-001'),
      dob: draft.dob || null,
      age: draft.age === '' ? null : Number(draft.age),
      sex: draft.sex || null,
      phone: draft.phone.trim(),
      email: draft.email.trim(),
      address: draft.address.trim(),
      blood_type: draft.blood_type || null,
      height_cm: draft.height_cm === '' ? null : Number(draft.height_cm),
      weight_kg: draft.weight_kg === '' ? null : Number(draft.weight_kg),
      bmi: bmiData?.bmi || null,
      bhyt_number: draft.bhyt_number.replace(/\s+/g, '').toUpperCase(),
      bhyt_hospital: draft.bhyt_hospital.trim(),
      bhyt_rate: draft.bhyt_rate ? Number(draft.bhyt_rate) : 80,
      bhxh_number: draft.bhxh_number.trim(),
      vssid_status: draft.bhxh_number ? 'verified' : 'unlinked',
      life_insurance_provider: draft.life_insurance_provider.trim(),
      life_insurance_policy_no: draft.life_insurance_policy_no.trim(),
      coverage_limit_vnd: draft.coverage_limit_vnd === '' ? null : Number(draft.coverage_limit_vnd),
      is_verified: Boolean(draft.bhyt_number || draft.bhxh_number),
      current_medications: parseList(draft.current_medications),
      allergies: parseList(draft.allergies),
      conditions: parseList(draft.conditions),
      emergency_contact_name: draft.emergency_contact_name.trim(),
      emergency_contact_phone: draft.emergency_contact_phone.trim(),
      emergency_contact_relation: draft.emergency_contact_relation.trim(),
    };
    onSave(finalProfile);
  };

  const formattedBhyt = draft.bhyt_number
    ? draft.bhyt_number.replace(/\s+/g, '').replace(/(\w{2})(\w{1})(\w{2})(\w{2})(\w{8})/, '$1 $2 $3 $4 $5')
    : 'CHƯA LIÊN KẾT BHYT';

  return (
    <div className="profile-modal-backdrop" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="profile-modal-container" role="dialog" aria-modal="true" aria-labelledby="profile-modal-title">
        
        {/* Modal Header */}
        <div className="profile-modal-header">
          <div className="header-title-box">
            <div className="header-icon-aura">
              <ShieldCheck size={22} />
            </div>
            <div>
              <h2 id="profile-modal-title">Hồ Sơ Y Tế & Xác Thực Bảo Hiểm</h2>
              <p>Quản lý thông tin cá nhân, định danh thẻ BHYT, BHXH (VssID) và Bảo hiểm nhân thọ</p>
            </div>
          </div>
          <button type="button" className="icon-button modal-close-btn" onClick={onClose} aria-label="Đóng">
            <X size={18} />
          </button>
        </div>

        {/* Digital Medical Card Preview */}
        <div className="digital-health-card-preview">
          <div className="card-top-row">
            <div className="card-emblem">
              <span className="emblem-dot" />
              <strong>MEDGUARD DIGITAL HEALTH ID</strong>
            </div>
            <div className="card-vssid-badge">
              {draft.bhyt_number ? (
                <span className="vssid-tag active"><ShieldCheck size={12} /> BHYT ĐÃ XÁC THỰC</span>
              ) : (
                <span className="vssid-tag unlinked"><Shield size={12} /> CHƯA XÁC THỰC</span>
              )}
            </div>
          </div>

          <div className="card-body-row">
            <div className="card-patient-info">
              <span className="card-label">HỌ VÀ TÊN CHỦ THẺ</span>
              <h3 className="card-name">{draft.display_name || 'NGƯỜI DÙNG MEDGUARD'}</h3>
              <div className="card-meta-line">
                <span>{draft.dob ? `NS: ${draft.dob}` : draft.age ? `Tuổi: ${draft.age}` : 'Chưa có ngày sinh'}</span>
                <span>•</span>
                <span>{draft.sex === 'female' ? 'Nữ' : draft.sex === 'male' ? 'Nam' : 'Khác'}</span>
                <span>•</span>
                <span>Nhóm máu: <strong style={{ color: '#00e5ff' }}>{draft.blood_type || 'Chưa rõ'}</strong></span>
              </div>
            </div>
            <div className="card-chip-simulation">
              <div className="card-chip-rect" />
            </div>
          </div>

          <div className="card-insurance-row">
            <div className="card-bhyt-box">
              <span className="card-label">MÃ SỐ BHYT TOÀN QUỐC</span>
              <strong className="card-bhyt-code">{formattedBhyt}</strong>
              <small className="card-hosp-name">{draft.bhyt_hospital || 'Nơi KCB: Chưa cập nhật bệnh viện ban đầu'}</small>
            </div>
            <div className="card-badges-stack">
              <div className="rate-pill">
                <span>Mức hưởng:</span>
                <strong>{draft.bhyt_rate || 80}%</strong>
              </div>
              {bmiData && (
                <div className="bmi-pill" style={{ borderColor: bmiData.badgeColor, color: bmiData.badgeColor }}>
                  <Scale size={11} />
                  <span>BMI {bmiData.bmi} ({bmiData.category.split(' ')[0]})</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="profile-tabs-bar" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'general'}
            className={`profile-tab-btn ${activeTab === 'general' ? 'active' : ''}`}
            onClick={() => setActiveTab('general')}
          >
            <UserRound size={16} />
            <span>1. Cá nhân & Thể chất</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'insurance'}
            className={`profile-tab-btn ${activeTab === 'insurance' ? 'active' : ''}`}
            onClick={() => setActiveTab('insurance')}
          >
            <CreditCard size={16} />
            <span>2. BHYT, BHXH & Nhân thọ</span>
            {draft.bhyt_number && <span className="tab-indicator-dot" />}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'medical'}
            className={`profile-tab-btn ${activeTab === 'medical' ? 'active' : ''}`}
            onClick={() => setActiveTab('medical')}
          >
            <Activity size={16} />
            <span>3. Tiền sử Y tế & Khẩn cấp</span>
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="profile-form-body">
          {activeTab === 'general' && (
            <div className="tab-pane-content fade-in">
              <div className="pane-intro">
                <strong>Thông tin định danh cá nhân & Chỉ số thể trạng</strong>
                <p>Hệ thống tự động sử dụng thông tin này để cá nhân hóa chỉ số Digital Twin và cảnh báo liều dùng thuốc.</p>
              </div>

              <div className="form-grid-2">
                <div className="form-field">
                  <label htmlFor="pf-display-name">Họ và tên bệnh nhân <span className="req">*</span></label>
                  <input
                    id="pf-display-name"
                    type="text"
                    value={draft.display_name}
                    onChange={(e) => update('display_name', e.target.value)}
                    placeholder="VD: Nguyễn Văn An"
                    autoComplete="name"
                    required
                  />
                </div>
                <div className="form-field">
                  <label htmlFor="pf-patient-ref">Mã hồ sơ y bạ (Patient Ref)</label>
                  <input
                    id="pf-patient-ref"
                    type="text"
                    value={draft.patient_ref}
                    onChange={(e) => update('patient_ref', e.target.value)}
                    placeholder="VD: BN-HCM-001"
                    autoComplete="off"
                  />
                </div>
              </div>

              <div className="form-grid-3">
                <div className="form-field">
                  <label htmlFor="pf-dob">Ngày sinh</label>
                  <input
                    id="pf-dob"
                    type="date"
                    value={draft.dob}
                    onChange={(e) => update('dob', e.target.value)}
                  />
                </div>
                <div className="form-field">
                  <label htmlFor="pf-age">Tuổi</label>
                  <input
                    id="pf-age"
                    type="number"
                    min="0"
                    max="125"
                    value={draft.age}
                    onChange={(e) => update('age', e.target.value)}
                    placeholder="VD: 35"
                  />
                </div>
                <div className="form-field">
                  <label htmlFor="pf-sex">Giới tính sinh học</label>
                  <select
                    id="pf-sex"
                    value={draft.sex}
                    onChange={(e) => update('sex', e.target.value)}
                  >
                    <option value="">-- Chưa cung cấp --</option>
                    <option value="male">Nam (Male)</option>
                    <option value="female">Nữ (Female)</option>
                    <option value="other">Khác</option>
                  </select>
                </div>
              </div>

              <div className="form-grid-3">
                <div className="form-field">
                  <label htmlFor="pf-phone">Số điện thoại</label>
                  <input
                    id="pf-phone"
                    type="tel"
                    value={draft.phone}
                    onChange={(e) => update('phone', e.target.value)}
                    placeholder="0912345678"
                    autoComplete="tel"
                  />
                </div>
                <div className="form-field">
                  <label htmlFor="pf-email">Email liên hệ</label>
                  <input
                    id="pf-email"
                    type="email"
                    value={draft.email}
                    onChange={(e) => update('email', e.target.value)}
                    placeholder="nguyenan@example.com"
                    autoComplete="email"
                  />
                </div>
                <div className="form-field">
                  <label htmlFor="pf-blood">Nhóm máu ABO / Rh</label>
                  <select
                    id="pf-blood"
                    value={draft.blood_type}
                    onChange={(e) => update('blood_type', e.target.value)}
                  >
                    <option value="">-- Chọn nhóm máu --</option>
                    <option value="O+">O Rh+</option>
                    <option value="O-">O Rh- (Hiếm)</option>
                    <option value="A+">A Rh+</option>
                    <option value="A-">A Rh-</option>
                    <option value="B+">B Rh+</option>
                    <option value="B-">B Rh-</option>
                    <option value="AB+">AB Rh+</option>
                    <option value="AB-">AB Rh- (Rất hiếm)</option>
                  </select>
                </div>
              </div>

              <div className="form-field">
                <label htmlFor="pf-address">Địa chỉ thường trú / Tỉnh - Thành phố</label>
                <input
                  id="pf-address"
                  type="text"
                  value={draft.address}
                  onChange={(e) => update('address', e.target.value)}
                  placeholder="VD: Quận 1, TP. Hồ Chí Minh"
                  autoComplete="street-address"
                />
              </div>

              {/* Vitals & Live BMI Meter */}
              <div className="vitals-calculation-panel">
                <div className="panel-title-row">
                  <Scale size={16} />
                  <strong>Chỉ số Thể chất & Đo lường BMI Tự động</strong>
                </div>
                <div className="vitals-inputs-row">
                  <div className="form-field">
                    <label htmlFor="pf-height">Chiều cao (cm)</label>
                    <input
                      id="pf-height"
                      type="number"
                      min="40"
                      max="250"
                      value={draft.height_cm}
                      onChange={(e) => update('height_cm', e.target.value)}
                      placeholder="175"
                    />
                  </div>
                  <div className="form-field">
                    <label htmlFor="pf-weight">Cân nặng (kg)</label>
                    <input
                      id="pf-weight"
                      type="number"
                      step="0.5"
                      min="5"
                      max="300"
                      value={draft.weight_kg}
                      onChange={(e) => update('weight_kg', e.target.value)}
                      placeholder="68.5"
                    />
                  </div>
                  <div className="bmi-result-card">
                    <span className="bmi-calc-label">Chỉ số BMI chuẩn Châu Á:</span>
                    <div className="bmi-display-row">
                      <strong className="bmi-num" style={{ color: bmiData?.badgeColor || '#94a3b8' }}>
                        {bmiData ? bmiData.bmi : '--'}
                      </strong>
                      <span className="bmi-status" style={{ color: bmiData?.badgeColor || '#94a3b8' }}>
                        {bmiData ? bmiData.category : 'Nhập chiều cao & cân nặng'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'insurance' && (
            <div className="tab-pane-content fade-in">
              <div className="pane-intro">
                <strong>Định danh Thẻ Bảo hiểm Y tế (BHYT), BHXH & Bảo hiểm Nhân thọ</strong>
                <p>MedGuard đối soát quyền lợi bảo hiểm khi bạn tư vấn thuốc, đặt lịch khám và đánh giá chi tiêu y tế.</p>
              </div>

              {/* Section 1: BHYT */}
              <div className="insurance-sub-card">
                <div className="sub-card-header">
                  <div className="badge-icon emerald"><CreditCard size={17} /></div>
                  <div>
                    <strong>Bảo hiểm Y tế Quốc gia (BHYT)</strong>
                    <span>15 ký tự hoặc 10 số theo thẻ BHYT chuẩn Bộ Y Tế / BHXH Việt Nam</span>
                  </div>
                </div>

                <div className="form-grid-2">
                  <div className="form-field">
                    <label htmlFor="pf-bhyt-num">Số thẻ BHYT</label>
                    <input
                      id="pf-bhyt-num"
                      type="text"
                      value={draft.bhyt_number}
                      onChange={(e) => update('bhyt_number', e.target.value.toUpperCase())}
                      placeholder="VD: DN 4 79 79 12345678"
                      maxLength={20}
                      autoComplete="off"
                    />
                    <small>Mã 15 ký tự (VD: DN479...) hoặc mã 10 số in trên thẻ BHYT</small>
                  </div>
                  <div className="form-field">
                    <label htmlFor="pf-bhyt-rate">Tỷ lệ hưởng BHYT đúng tuyến</label>
                    <select
                      id="pf-bhyt-rate"
                      value={draft.bhyt_rate}
                      onChange={(e) => update('bhyt_rate', Number(e.target.value))}
                    >
                      <option value={80}>80% - Lao động thông thường / Hộ gia đình</option>
                      <option value={95}>95% - Hộ cận nghèo, bảo trợ xã hội, hưu trí</option>
                      <option value={100}>100% - Người có công, lực lượng vũ trang, trẻ em &lt; 6T</option>
                    </select>
                  </div>
                </div>

                <div className="form-field">
                  <label htmlFor="pf-bhyt-hosp">Nơi đăng ký Khám chữa bệnh (KCB) ban đầu</label>
                  <input
                    id="pf-bhyt-hosp"
                    type="text"
                    value={draft.bhyt_hospital}
                    onChange={(e) => update('bhyt_hospital', e.target.value)}
                    placeholder="VD: Bệnh viện Chợ Rẫy (Mã 79-011)"
                    list="hospital-presets"
                  />
                  <datalist id="hospital-presets">
                    {COMMON_HOSPITALS.map((h, i) => (
                      <option value={h} key={i} />
                    ))}
                  </datalist>
                </div>
              </div>

              {/* Section 2: BHXH / VssID */}
              <div className="insurance-sub-card">
                <div className="sub-card-header">
                  <div className="badge-icon cyan"><BadgeCheck size={17} /></div>
                  <div>
                    <strong>Bảo hiểm Xã hội (BHXH) & Ứng dụng VssID</strong>
                    <span>Mã định danh công dân 10 chữ số đồng bộ dữ liệu sổ BHXH</span>
                  </div>
                </div>

                <div className="form-grid-2">
                  <div className="form-field">
                    <label htmlFor="pf-bhxh-num">Mã số BHXH (10 số)</label>
                    <input
                      id="pf-bhxh-num"
                      type="text"
                      value={draft.bhxh_number}
                      onChange={(e) => update('bhxh_number', e.target.value)}
                      placeholder="VD: 0790901234"
                      maxLength={12}
                    />
                  </div>
                  <div className="form-field">
                    <label htmlFor="pf-vssid-status">Trạng thái VssID</label>
                    <select
                      id="pf-vssid-status"
                      value={draft.vssid_status}
                      onChange={(e) => update('vssid_status', e.target.value)}
                    >
                      <option value="verified">Đã xác thực định danh Mức 2 (VNeID/VssID)</option>
                      <option value="unlinked">Chưa liên kết tài khoản VssID</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Section 3: Commercial / Life Insurance */}
              <div className="insurance-sub-card">
                <div className="sub-card-header">
                  <div className="badge-icon purple"><ShieldCheck size={17} /></div>
                  <div>
                    <strong>Bảo hiểm Nhân thọ & Thẻ Sức khỏe Thương mại</strong>
                    <span>Bảo lãnh viện phí nội trú / ngoại trú tại bệnh viện quốc tế</span>
                  </div>
                </div>

                <div className="form-grid-3">
                  <div className="form-field">
                    <label htmlFor="pf-life-prov">Hãng bảo hiểm</label>
                    <input
                      id="pf-life-prov"
                      type="text"
                      value={draft.life_insurance_provider}
                      onChange={(e) => update('life_insurance_provider', e.target.value)}
                      placeholder="VD: Prudential, Manulife..."
                      list="life-ins-presets"
                    />
                    <datalist id="life-ins-presets">
                      {LIFE_INSURERS.map((ins, i) => (
                        <option value={ins} key={i} />
                      ))}
                    </datalist>
                  </div>
                  <div className="form-field">
                    <label htmlFor="pf-policy-num">Số hợp đồng bảo hiểm</label>
                    <input
                      id="pf-policy-num"
                      type="text"
                      value={draft.life_insurance_policy_no}
                      onChange={(e) => update('life_insurance_policy_no', e.target.value)}
                      placeholder="VD: POL-8829103"
                    />
                  </div>
                  <div className="form-field">
                    <label htmlFor="pf-coverage-limit">Hạn mức bảo lãnh (VND/năm)</label>
                    <input
                      id="pf-coverage-limit"
                      type="number"
                      step="1000000"
                      value={draft.coverage_limit_vnd}
                      onChange={(e) => update('coverage_limit_vnd', e.target.value)}
                      placeholder="VD: 300000000"
                    />
                    {draft.coverage_limit_vnd ? (
                      <small style={{ color: '#00e5ff' }}>
                        = {Number(draft.coverage_limit_vnd).toLocaleString('vi-VN')} đ/năm
                      </small>
                    ) : null}
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'medical' && (
            <div className="tab-pane-content fade-in">
              <div className="pane-intro">
                <strong>Hồ sơ Lâm sàng nền & Người liên hệ trong trường hợp khẩn cấp</strong>
                <p>Dữ liệu quan trọng giúp Bác sĩ AI sàng lọc tương tác thuốc nguy hiểm và phản ứng dị ứng.</p>
              </div>

              <div className="form-field">
                <label htmlFor="pf-allergies">
                  <span className="field-icon-label"><AlertTriangle size={15} style={{ color: '#f59e0b' }} /> Tiền sử Dị ứng thuốc & Dị nguyên</span>
                </label>
                <input
                  id="pf-allergies"
                  type="text"
                  value={draft.allergies}
                  onChange={(e) => update('allergies', e.target.value)}
                  placeholder="VD: Penicillin, Cephalosporin, Paracetamol, Aspirin, hải sản (ngăn cách bằng dấu phẩy)"
                />
                <small>Nhập tên thuốc hoặc chất gây sốc phản vệ, phát ban hoặc khó thở</small>
              </div>

              <div className="form-field">
                <label htmlFor="pf-conditions">
                  <span className="field-icon-label"><Activity size={15} style={{ color: '#00e5ff' }} /> Bệnh lý nền mãn tính</span>
                </label>
                <input
                  id="pf-conditions"
                  type="text"
                  value={draft.conditions}
                  onChange={(e) => update('conditions', e.target.value)}
                  placeholder="VD: Tăng huyết áp, Đái tháo đường Type 2, Loét dạ dày, Hen phế quản"
                />
                <small>Các bệnh mãn tính đang theo dõi điều trị định kỳ</small>
              </div>

              <div className="form-field">
                <label htmlFor="pf-medications">
                  <span className="field-icon-label"><Pill size={15} style={{ color: '#10b981' }} /> Thuốc đang dùng hàng ngày</span>
                </label>
                <input
                  id="pf-medications"
                  type="text"
                  value={draft.current_medications}
                  onChange={(e) => update('current_medications', e.target.value)}
                  placeholder="VD: Amlodipine 5mg, Metformin 500mg, Aspirin 81mg"
                />
                <small>Hệ thống tự động kiểm tra chống chỉ định khi bạn hỏi về thuốc mới</small>
              </div>

              <div className="insurance-sub-card" style={{ marginTop: '16px' }}>
                <div className="sub-card-header">
                  <div className="badge-icon emerald"><Phone size={17} /></div>
                  <div>
                    <strong>Người liên hệ trong trường hợp khẩn cấp (Emergency Contact)</strong>
                    <span>Liên lạc y tế khi có dấu hiệu cảnh báo đỏ (Red flag)</span>
                  </div>
                </div>

                <div className="form-grid-3">
                  <div className="form-field">
                    <label htmlFor="pf-em-name">Họ tên người thân</label>
                    <input
                      id="pf-em-name"
                      type="text"
                      value={draft.emergency_contact_name}
                      onChange={(e) => update('emergency_contact_name', e.target.value)}
                      placeholder="VD: Nguyễn Thị Lan"
                    />
                  </div>
                  <div className="form-field">
                    <label htmlFor="pf-em-phone">Số điện thoại khẩn cấp</label>
                    <input
                      id="pf-em-phone"
                      type="tel"
                      value={draft.emergency_contact_phone}
                      onChange={(e) => update('emergency_contact_phone', e.target.value)}
                      placeholder="0988776655"
                    />
                  </div>
                  <div className="form-field">
                    <label htmlFor="pf-em-rel">Mối quan hệ</label>
                    <input
                      id="pf-em-rel"
                      type="text"
                      value={draft.emergency_contact_relation}
                      onChange={(e) => update('emergency_contact_relation', e.target.value)}
                      placeholder="VD: Vợ / Chồng / Bố / Mẹ / Con"
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Modal Actions */}
          <div className="profile-modal-footer">
            <button
              type="button"
              className="secondary-button danger-action"
              onClick={onClear}
            >
              <Trash2 size={15} />
              <span>Xóa Profile</span>
            </button>
            <div className="footer-right-buttons">
              <button
                type="button"
                className="secondary-button"
                onClick={onClose}
              >
                Hủy bỏ
              </button>
              <button
                type="submit"
                className="primary-save-button"
              >
                <Save size={16} />
                <span>Lưu Hồ Sơ & Xác Thực</span>
              </button>
            </div>
          </div>
        </form>

      </div>
    </div>
  );
}
