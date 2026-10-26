import { useState, useEffect, useMemo } from 'react';
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  BadgeCheck,
  Building2,
  Calendar,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock,
  CreditCard,
  Droplet,
  FileText,
  HeartPulse,
  Info,
  Mail,
  MapPin,
  Phone,
  Pill,
  Plus,
  RefreshCw,
  RotateCcw,
  Save,
  Scale,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Trash2,
  User,
  UserCheck,
  UserRound,
  X,
  Zap,
} from 'lucide-react';
import { calculateBmi } from './profileDisambiguation';
import './UserProfilePage.css';

const COMMON_HOSPITALS = [
  'Bệnh viện Chợ Rẫy (79-011)',
  'Bệnh viện Bạch Mai (01-001)',
  'Bệnh viện Đại học Y Dược TP.HCM (79-026)',
  'Bệnh viện Hữu nghị Việt Đức (01-002)',
  'Bệnh viện Đa khoa Đà Nẵng (48-001)',
  'Bệnh viện Quân Y 175 (79-012)',
  'Bệnh viện Thống Nhất (79-010)',
  'Bệnh viện K Trung ương (01-004)',
  'Bệnh viện Nhân dân Gia Định (79-015)',
  'Bệnh viện Hùng Vương (79-017)',
  'Bệnh viện Nhi Đồng 1 (79-019)',
];

const LIFE_INSURERS = [
  'Prudential Việt Nam',
  'Manulife Việt Nam',
  'Bảo Việt Nhân Thọ',
  'Dai-ichi Life Việt Nam',
  'AIA Việt Nam',
  'Generali Việt Nam',
  'MB Ageas Life',
  'PVI Care',
  'Chubb Life',
  'FWD Việt Nam',
  'Cathay Life',
];

const COMMON_CONDITIONS = [
  'Tăng huyết áp',
  'Đái tháo đường Type 2',
  'Viêm loét dạ dày - tá tràng',
  'Rối loạn lipid máu',
  'Trào ngược dạ dày thực quản (GERD)',
  'Gan nhiễm mỡ',
  'Hen phế quản',
  'Gout',
  'Bệnh mạch vành',
  'Viêm mũi dị ứng',
  'Thoái hóa cột sống',
];

const COMMON_ALLERGIES = [
  'Penicillin / Amoxicillin',
  'Aspirin / NSAIDs',
  'Cephalosporin',
  'Sulfa / Kháng sinh nhóm Sulfonamide',
  'Hải sản (Tôm, Cua, Mực)',
  'Đậu phộng / Lạc',
  'Trứng gà',
  'Sữa bò / Lactose',
  'Phấn hoa / Bụi nhà',
  'Thuốc cản quang Iod',
];

function parseList(val) {
  if (Array.isArray(val)) return val;
  if (!val || typeof val !== 'string') return [];
  return val
    .split(/[,;\n+]/)
    .map((s) => s.trim())
    .filter((s) => s && !['không', 'khong', 'none', 'chưa có'].includes(s.toLowerCase()));
}

export function UserProfilePage({
  context = {},
  account = null,
  onSave,
  onClear,
  onBackToChat,
  onNotify,
}) {
  const [activeTab, setActiveTab] = useState('general'); // 'general' | 'insurance' | 'medical'
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [newConditionInput, setNewConditionInput] = useState('');
  const [newAllergyInput, setNewAllergyInput] = useState('');

  // Initial State from Context
  const initialValues = useMemo(() => ({
    display_name: context.display_name || account?.name || '',
    patient_ref: context.patient_ref || '',
    dob: context.dob || '',
    age: context.age ?? '',
    sex: context.sex || '',
    phone: context.phone || '',
    email: context.email || account?.email || '',
    address: context.address || '',
    citizen_id: context.citizen_id || '',
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
    current_medications: parseList(context.current_medications),
    allergies: parseList(context.allergies),
    conditions: parseList(context.conditions),
    emergency_contact_name: context.emergency_contact_name || '',
    emergency_contact_phone: context.emergency_contact_phone || '',
    emergency_contact_relation: context.emergency_contact_relation || '',
  }), [context, account]);

  const [draft, setDraft] = useState(initialValues);

  // Sync draft when context prop updates
  useEffect(() => {
    setDraft(initialValues);
  }, [initialValues]);

  // Dirty state checking
  const isDirty = useMemo(() => {
    return JSON.stringify(draft) !== JSON.stringify(initialValues);
  }, [draft, initialValues]);

  const updateField = (key, val) => {
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

  // BMI calculation
  const bmiData = calculateBmi(
    draft.height_cm ? Number(draft.height_cm) : null,
    draft.weight_kg ? Number(draft.weight_kg) : null
  );

  // Tag list helpers
  const addCondition = (item) => {
    const val = item.trim();
    if (!val) return;
    if (!draft.conditions.includes(val)) {
      setDraft((prev) => ({ ...prev, conditions: [...prev.conditions, val] }));
    }
    setNewConditionInput('');
  };

  const removeCondition = (val) => {
    setDraft((prev) => ({ ...prev, conditions: prev.conditions.filter((c) => c !== val) }));
  };

  const addAllergy = (item) => {
    const val = item.trim();
    if (!val) return;
    if (!draft.allergies.includes(val)) {
      setDraft((prev) => ({ ...prev, allergies: [...prev.allergies, val] }));
    }
    setNewAllergyInput('');
  };

  const removeAllergy = (val) => {
    setDraft((prev) => ({ ...prev, allergies: prev.allergies.filter((a) => a !== val) }));
  };

  const handleReset = () => {
    setDraft(initialValues);
    onNotify?.('info', 'Đã hủy các thay đổi chưa lưu');
  };

  const handleSave = async (e) => {
    e?.preventDefault();
    setSaving(true);

    const patientRef =
      draft.patient_ref.trim().toUpperCase() ||
      (draft.display_name
        ? `BN-${draft.display_name.trim().slice(0, 3).toUpperCase()}-26`
        : `BN-MG-${Math.floor(1000 + Math.random() * 9000)}`);

    const finalProfile = {
      display_name: draft.display_name.trim(),
      patient_ref: patientRef,
      dob: draft.dob || null,
      age: draft.age === '' ? null : Number(draft.age),
      sex: draft.sex || null,
      phone: draft.phone.trim(),
      email: draft.email.trim(),
      address: draft.address.trim(),
      citizen_id: draft.citizen_id.trim(),
      blood_type: draft.blood_type || null,
      height_cm: draft.height_cm === '' ? null : Number(draft.height_cm),
      weight_kg: draft.weight_kg === '' ? null : Number(draft.weight_kg),
      bhyt_number: draft.bhyt_number.trim().toUpperCase(),
      bhyt_hospital: draft.bhyt_hospital.trim(),
      bhyt_rate: draft.bhyt_rate === '' ? 80 : Number(draft.bhyt_rate),
      bhxh_number: draft.bhxh_number.trim(),
      vssid_status: draft.bhxh_number ? 'verified' : 'unlinked',
      life_insurance_provider: draft.life_insurance_provider.trim(),
      life_insurance_policy_no: draft.life_insurance_policy_no.trim(),
      coverage_limit_vnd: draft.coverage_limit_vnd === '' ? null : Number(draft.coverage_limit_vnd),
      is_verified: Boolean(draft.bhyt_number.trim() || draft.citizen_id.trim()),
      current_medications: draft.current_medications,
      allergies: draft.allergies,
      conditions: draft.conditions,
      emergency_contact_name: draft.emergency_contact_name.trim(),
      emergency_contact_phone: draft.emergency_contact_phone.trim(),
      emergency_contact_relation: draft.emergency_contact_relation.trim(),
    };

    try {
      await onSave?.(finalProfile);
      setSaving(false);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
      onNotify?.('success', 'Đã lưu Hồ sơ y tế & Xác thực bảo hiểm thành công!');
    } catch (err) {
      setSaving(false);
      onNotify?.('error', 'Lỗi khi lưu hồ sơ: ' + (err.message || 'Thử lại sau'));
    }
  };

  const userInitials = (draft.display_name || account?.name || 'BN')
    .trim()
    .split(/\s+/)
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  const isVerified = Boolean(draft.bhyt_number || draft.citizen_id || draft.is_verified);

  return (
    <div className="user-profile-page-workspace" role="main" aria-label="Trang quản lý hồ sơ bệnh nhân">
      {/* 1. TOP NAV & BREADCRUMB BAR */}
      <div className="profile-top-breadcrumb-bar">
        <div className="breadcrumb-left">
          <button
            type="button"
            className="btn-back-to-chat"
            onClick={onBackToChat}
            title="Quay lại Phòng trò chuyện"
          >
            <ArrowLeft size={16} />
            <span>Quay lại Hội thoại</span>
          </button>
          <div className="breadcrumb-divider">/</div>
          <span className="breadcrumb-current">Hồ Sơ Y Tế & Xác Thực Bảo Hiểm</span>
        </div>

        <div className="profile-header-actions">
          {isDirty && (
            <button
              type="button"
              className="btn-discard-changes"
              onClick={handleReset}
              disabled={saving}
            >
              <RotateCcw size={14} />
              <span>Hủy thay đổi</span>
            </button>
          )}

          <button
            type="button"
            className={`btn-save-master ${saveSuccess ? 'success' : ''}`}
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? (
              <>
                <RefreshCw size={15} className="spin-icon" />
                <span>Đang lưu...</span>
              </>
            ) : saveSuccess ? (
              <>
                <Check size={16} />
                <span>Đã lưu thành công!</span>
              </>
            ) : (
              <>
                <Save size={15} />
                <span>Lưu Hồ Sơ Y Tế</span>
              </>
            )}
          </button>
        </div>
      </div>

      <div className="profile-page-content-wrapper">
        {/* 2. EXECUTIVE HERO DOSSIER CARD */}
        <section className="profile-hero-dossier-card" aria-label="Thẻ tổng quan hồ sơ">
          <div className="dossier-main-row">
            <div className="dossier-avatar-wrap">
              <div className="dossier-avatar-circle">
                <span>{userInitials}</span>
              </div>
              {isVerified && (
                <div className="dossier-verified-badge" title="Đã liên kết BHYT & CCCD xác thực">
                  <BadgeCheck size={18} />
                </div>
              )}
            </div>

            <div className="dossier-identity-info">
              <div className="dossier-title-line">
                <h2>{draft.display_name || 'Bệnh nhân chưa đặt tên'}</h2>
                <div className="dossier-badges-cluster">
                  <span className="patient-id-tag">
                    MÃ BN: {draft.patient_ref || 'CHƯA CẤP MÃ'}
                  </span>
                  {isVerified ? (
                    <span className="verified-status-tag verified">
                      <ShieldCheck size={13} />
                      <span>ĐÃ XÁC THỰC BHYT</span>
                    </span>
                  ) : (
                    <span className="verified-status-tag unverified">
                      <AlertCircle size={13} />
                      <span>CHƯA LIÊN KẾT BHYT</span>
                    </span>
                  )}
                  {draft.vssid_status === 'verified' && (
                    <span className="verified-status-tag vssid">
                      <CheckCircle2 size={13} />
                      <span>VssID KÍCH HOẠT</span>
                    </span>
                  )}
                </div>
              </div>

              <div className="dossier-quick-meta-row">
                <span className="meta-pill">
                  <User size={13} />
                  <span>{draft.age ? `${draft.age} tuổi` : 'Chưa rõ tuổi'}</span>
                  <span className="dot">•</span>
                  <span>{draft.sex === 'male' || draft.sex === 'Nam' ? 'Nam' : draft.sex === 'female' || draft.sex === 'Nữ' ? 'Nữ' : 'Khác'}</span>
                </span>
                <span className="meta-pill">
                  <Droplet size={13} className="text-rose" />
                  <span>Nhóm máu: <strong>{draft.blood_type || 'Chưa cập nhật'}</strong></span>
                </span>
                <span className="meta-pill">
                  <Building2 size={13} className="text-teal" />
                  <span>{draft.bhyt_hospital ? draft.bhyt_hospital.split('(')[0].trim() : 'Chưa đăng ký KCB ban đầu'}</span>
                </span>
                <span className="meta-pill">
                  <Phone size={13} />
                  <span>{draft.phone || 'Chưa có SĐT'}</span>
                </span>
              </div>
            </div>
          </div>

          {/* 4 Quick Stat Summary Cards */}
          <div className="dossier-metrics-four-grid">
            {/* Metric 1: BMI & Thể chất */}
            <div className="dossier-stat-card">
              <div className="stat-card-top">
                <span className="stat-card-label">Thể chất & BMI Châu Á</span>
                <Scale size={16} className="text-teal" />
              </div>
              <div className="stat-card-main">
                {bmiData ? (
                  <>
                    <div className="stat-value-row">
                      <strong className="stat-big-number" style={{ color: bmiData.badgeColor }}>
                        {bmiData.bmi}
                      </strong>
                      <span className="stat-unit">kg/m²</span>
                    </div>
                    <span
                      className="bmi-category-badge"
                      style={{ background: `${bmiData.badgeColor}18`, color: bmiData.badgeColor, borderColor: `${bmiData.badgeColor}40` }}
                    >
                      {bmiData.category}
                    </span>
                    <div className="bmi-mini-scale-bar">
                      <div
                        className="bmi-needle-indicator"
                        style={{
                          left: `${Math.min(100, Math.max(0, ((bmiData.bmi - 15) / (32 - 15)) * 100))}%`,
                          backgroundColor: bmiData.badgeColor,
                        }}
                      />
                    </div>
                  </>
                ) : (
                  <div className="stat-empty-note">
                    <span>Nhập chiều cao & cân nặng để tính BMI</span>
                  </div>
                )}
              </div>
              <div className="stat-card-sub">
                <span>{draft.height_cm ? `${draft.height_cm} cm` : '-- cm'} • {draft.weight_kg ? `${draft.weight_kg} kg` : '-- kg'}</span>
              </div>
            </div>

            {/* Metric 2: Thẻ BHYT */}
            <div className="dossier-stat-card">
              <div className="stat-card-top">
                <span className="stat-card-label">Bảo Hiểm Y Tế (BHYT)</span>
                <CreditCard size={16} className="text-blue" />
              </div>
              <div className="stat-card-main">
                <div className="stat-value-row">
                  <strong className="stat-big-number text-blue">
                    {draft.bhyt_rate || 80}%
                  </strong>
                  <span className="stat-unit">mức hưởng</span>
                </div>
                <div className="bhyt-number-preview">
                  <span>{draft.bhyt_number || 'Chưa nhập số thẻ BHYT'}</span>
                </div>
              </div>
              <div className="stat-card-sub">
                <span>{draft.bhyt_hospital ? `KCB: ${draft.bhyt_hospital.slice(0, 24)}...` : 'Chưa gán cơ sở KCB'}</span>
              </div>
            </div>

            {/* Metric 3: Bảo hiểm Nhân thọ & VssID */}
            <div className="dossier-stat-card">
              <div className="stat-card-top">
                <span className="stat-card-label">Bảo Hiểm Thương Mại</span>
                <ShieldCheck size={16} className="text-indigo" />
              </div>
              <div className="stat-card-main">
                <strong className="stat-medium-title text-indigo">
                  {draft.life_insurance_provider || 'Chưa liên kết'}
                </strong>
                <span className="insurance-policy-sub">
                  {draft.life_insurance_policy_no ? `Số HĐ: ${draft.life_insurance_policy_no}` : 'Chưa có hợp đồng bảo hiểm'}
                </span>
              </div>
              <div className="stat-card-sub">
                <span>BHXH: {draft.bhxh_number || 'Chưa liên kết VssID'}</span>
              </div>
            </div>

            {/* Metric 4: SOS Liên hệ khẩn cấp */}
            <div className="dossier-stat-card">
              <div className="stat-card-top">
                <span className="stat-card-label">Liên Hệ Khẩn Cấp (24/7)</span>
                <AlertTriangle size={16} className="text-amber" />
              </div>
              <div className="stat-card-main">
                <strong className="stat-medium-title">
                  {draft.emergency_contact_name || 'Chưa thiết lập'}
                </strong>
                <span className="emergency-relation-sub">
                  {draft.emergency_contact_relation ? `Quan hệ: ${draft.emergency_contact_relation}` : 'Người thân / Giám hộ'}
                </span>
              </div>
              <div className="stat-card-sub">
                <span className="emergency-phone-hl">{draft.emergency_contact_phone || 'Chưa có SĐT khẩn cấp'}</span>
              </div>
            </div>
          </div>
        </section>

        {/* 3. MASTER STICKY NAVIGATION TABS */}
        <div className="profile-tabs-header-bar" role="tablist" aria-label="Phân loại thông tin hồ sơ">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'general'}
            className={`profile-master-tab ${activeTab === 'general' ? 'active' : ''}`}
            onClick={() => setActiveTab('general')}
          >
            <UserRound size={16} />
            <span>1. Thông Tin Cá Nhân & Thể Chất</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'insurance'}
            className={`profile-master-tab ${activeTab === 'insurance' ? 'active' : ''}`}
            onClick={() => setActiveTab('insurance')}
          >
            <ShieldCheck size={16} />
            <span>2. Bảo Hiểm Y Tế, BHXH & Nhân Thọ</span>
            {draft.bhyt_number && <span className="tab-pill-dot" />}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'medical'}
            className={`profile-master-tab ${activeTab === 'medical' ? 'active' : ''}`}
            onClick={() => setActiveTab('medical')}
          >
            <HeartPulse size={16} />
            <span>3. Tiền Sử Bệnh Lý, Dị Ứng & Khẩn Cấp</span>
            {draft.allergies.length > 0 && <span className="tab-pill-alert" />}
          </button>
        </div>

        {/* 4. TAB CONTENTS */}
        <form onSubmit={handleSave} className="profile-form-container">
          {/* ================= TAB 1: GENERAL & PHYSICAL ================= */}
          {activeTab === 'general' && (
            <div className="profile-tab-pane fade-in">
              {/* Group 1: Định danh */}
              <div className="form-section-card">
                <div className="form-section-header">
                  <div className="sec-icon-box teal">
                    <UserCheck size={18} />
                  </div>
                  <div>
                    <h3>Thông Tin Định Danh Cơ Bản</h3>
                    <p>Thông tin dùng để xưng hô, chỉ định điều trị và đồng bộ kết quả xét nghiệm</p>
                  </div>
                </div>

                <div className="form-fields-grid three-col">
                  <div className="field-group">
                    <label htmlFor="pf-display-name">
                      Họ và tên bệnh nhân <span className="req">*</span>
                    </label>
                    <input
                      id="pf-display-name"
                      type="text"
                      className="form-input"
                      placeholder="VD: Nguyễn Văn An"
                      value={draft.display_name}
                      onChange={(e) => updateField('display_name', e.target.value)}
                      required
                    />
                  </div>

                  <div className="field-group">
                    <label htmlFor="pf-patient-ref">
                      Mã định danh bệnh nhân (Patient Ref)
                    </label>
                    <input
                      id="pf-patient-ref"
                      type="text"
                      className="form-input mono"
                      placeholder="VD: BN-NGUYEN-01"
                      value={draft.patient_ref}
                      onChange={(e) => updateField('patient_ref', e.target.value)}
                    />
                    <span className="field-hint">Để trống hệ thống sẽ tự động cấp mã chuẩn lâm sàng</span>
                  </div>

                  <div className="field-group">
                    <label htmlFor="pf-citizen-id">Số CCCD / Mã định danh cá nhân</label>
                    <input
                      id="pf-citizen-id"
                      type="text"
                      className="form-input"
                      placeholder="VD: 079098001234 (12 số)"
                      value={draft.citizen_id}
                      onChange={(e) => updateField('citizen_id', e.target.value)}
                    />
                  </div>

                  <div className="field-group">
                    <label htmlFor="pf-dob">Ngày tháng năm sinh</label>
                    <input
                      id="pf-dob"
                      type="date"
                      className="form-input"
                      value={draft.dob}
                      onChange={(e) => updateField('dob', e.target.value)}
                    />
                  </div>

                  <div className="field-group">
                    <label htmlFor="pf-age">Tuổi hiện tại</label>
                    <input
                      id="pf-age"
                      type="number"
                      min="0"
                      max="130"
                      className="form-input"
                      placeholder="VD: 34"
                      value={draft.age}
                      onChange={(e) => updateField('age', e.target.value)}
                    />
                  </div>

                  <div className="field-group">
                    <label htmlFor="pf-sex">Giới tính sinh học</label>
                    <select
                      id="pf-sex"
                      className="form-select"
                      value={draft.sex}
                      onChange={(e) => updateField('sex', e.target.value)}
                    >
                      <option value="">-- Chọn giới tính --</option>
                      <option value="male">Nam</option>
                      <option value="female">Nữ</option>
                      <option value="other">Khác</option>
                    </select>
                  </div>

                  <div className="field-group">
                    <label htmlFor="pf-blood-type">Nhóm máu hệ ABO & Rhesus</label>
                    <select
                      id="pf-blood-type"
                      className="form-select"
                      value={draft.blood_type}
                      onChange={(e) => updateField('blood_type', e.target.value)}
                    >
                      <option value="">-- Chọn nhóm máu --</option>
                      <option value="O+">O+ (Rh dương)</option>
                      <option value="A+">A+ (Rh dương)</option>
                      <option value="B+">B+ (Rh dương)</option>
                      <option value="AB+">AB+ (Rh dương)</option>
                      <option value="O-">O- (Rh âm - hiếm)</option>
                      <option value="A-">A- (Rh âm - hiếm)</option>
                      <option value="B-">B- (Rh âm - hiếm)</option>
                      <option value="AB-">AB- (Rh âm - hiếm)</option>
                    </select>
                  </div>

                  <div className="field-group">
                    <label htmlFor="pf-phone">Số điện thoại liên lạc</label>
                    <input
                      id="pf-phone"
                      type="tel"
                      className="form-input"
                      placeholder="VD: 0912345678"
                      value={draft.phone}
                      onChange={(e) => updateField('phone', e.target.value)}
                    />
                  </div>

                  <div className="field-group">
                    <label htmlFor="pf-email">Địa chỉ Email</label>
                    <input
                      id="pf-email"
                      type="email"
                      className="form-input"
                      placeholder="VD: an.nguyen@example.com"
                      value={draft.email}
                      onChange={(e) => updateField('email', e.target.value)}
                    />
                  </div>
                </div>

                <div className="field-group full-width" style={{ marginTop: '12px' }}>
                  <label htmlFor="pf-address">Địa chỉ thường trú / Nơi ở hiện tại</label>
                  <input
                    id="pf-address"
                    type="text"
                    className="form-input"
                    placeholder="VD: 123 Nguyễn Thị Minh Khai, Phường 6, Quận 3, TP. Hồ Chí Minh"
                    value={draft.address}
                    onChange={(e) => updateField('address', e.target.value)}
                  />
                </div>
              </div>

              {/* Group 2: Chỉ số Nhân trắc & Thể chất */}
              <div className="form-section-card">
                <div className="form-section-header">
                  <div className="sec-icon-box emerald">
                    <Scale size={18} />
                  </div>
                  <div>
                    <h3>Chỉ Số Nhân Trắc Học & Đánh Giá Thể Trạng (WHO Châu Á)</h3>
                    <p>Cơ sở tính liều dược học chính xác theo diện tích da và phân loại chuyển hóa</p>
                  </div>
                </div>

                <div className="physical-bmi-interactive-layout">
                  <div className="inputs-col">
                    <div className="form-fields-grid two-col">
                      <div className="field-group">
                        <label htmlFor="pf-height">Chiều cao cơ thể (cm)</label>
                        <div className="input-with-suffix">
                          <input
                            id="pf-height"
                            type="number"
                            step="0.5"
                            min="50"
                            max="250"
                            className="form-input"
                            placeholder="VD: 172"
                            value={draft.height_cm}
                            onChange={(e) => updateField('height_cm', e.target.value)}
                          />
                          <span className="input-suffix">cm</span>
                        </div>
                      </div>

                      <div className="field-group">
                        <label htmlFor="pf-weight">Cân nặng cơ thể (kg)</label>
                        <div className="input-with-suffix">
                          <input
                            id="pf-weight"
                            type="number"
                            step="0.1"
                            min="20"
                            max="300"
                            className="form-input"
                            placeholder="VD: 68"
                            value={draft.weight_kg}
                            onChange={(e) => updateField('weight_kg', e.target.value)}
                          />
                          <span className="input-suffix">kg</span>
                        </div>
                      </div>
                    </div>

                    <div className="who-standard-note">
                      <Info size={14} className="text-teal" />
                      <span>
                        Hệ thống áp dụng chuẩn <strong>WHO Châu Á (WPRO)</strong>: BMI lý tưởng từ <strong>18.5 – 22.9 kg/m²</strong> (khác với chuẩn Châu Âu 18.5 – 24.9 kg/m² do tỷ lệ mỡ nội tạng người Châu Á cao hơn).
                      </span>
                    </div>
                  </div>

                  {/* Visual BMI Card */}
                  <div className="bmi-live-card">
                    <div className="bmi-live-header">
                      <span className="bmi-live-label">CHỈ SỐ KHỐI CƠ THỂ (BMI)</span>
                      {bmiData && (
                        <span
                          className="bmi-live-tag"
                          style={{ background: `${bmiData.badgeColor}18`, color: bmiData.badgeColor, borderColor: `${bmiData.badgeColor}40` }}
                        >
                          {bmiData.category}
                        </span>
                      )}
                    </div>

                    <div className="bmi-live-display">
                      <strong className="bmi-big-val" style={{ color: bmiData ? bmiData.badgeColor : '#94a3b8' }}>
                        {bmiData ? bmiData.bmi : '--.-'}
                      </strong>
                      <span className="bmi-unit-val">kg/m²</span>
                    </div>

                    <div className="bmi-spectrum-bar">
                      <div className="seg seg-under" title="Thiếu cân (<18.5)" />
                      <div className="seg seg-normal" title="Bình thường (18.5 - 22.9)" />
                      <div className="seg seg-pre" title="Tiền béo phì (23.0 - 24.9)" />
                      <div className="seg seg-obese" title="Béo phì (≥25.0)" />
                      {bmiData && (
                        <div
                          className="bmi-marker-pin"
                          style={{
                            left: `${Math.min(98, Math.max(2, ((bmiData.bmi - 15) / (32 - 15)) * 100))}%`,
                            backgroundColor: bmiData.badgeColor,
                          }}
                        />
                      )}
                    </div>

                    <div className="bmi-scale-labels">
                      <span>15.0</span>
                      <span>18.5</span>
                      <span>23.0</span>
                      <span>25.0</span>
                      <span>32.0</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ================= TAB 2: INSURANCE & POLICIES ================= */}
          {activeTab === 'insurance' && (
            <div className="profile-tab-pane fade-in">
              {/* Card 1: BHYT */}
              <div className="form-section-card">
                <div className="form-section-header">
                  <div className="sec-icon-box blue">
                    <CreditCard size={18} />
                  </div>
                  <div>
                    <h3>Thẻ Bảo Hiểm Y Tế (BHYT) Quốc Gia</h3>
                    <p>Đồng bộ cổng Giám định BHYT Việt Nam để áp dụng quyền lợi thông tuyến và giảm trừ chi phí</p>
                  </div>
                </div>

                <div className="form-fields-grid three-col">
                  <div className="field-group">
                    <label htmlFor="pf-bhyt-number">
                      Số thẻ BHYT (15 ký tự chuẩn BHXH)
                    </label>
                    <input
                      id="pf-bhyt-number"
                      type="text"
                      maxLength={15}
                      className="form-input mono uppercase"
                      placeholder="VD: GD4797931890123"
                      value={draft.bhyt_number}
                      onChange={(e) => updateField('bhyt_number', e.target.value.toUpperCase())}
                    />
                    <span className="field-hint">Mã gồm 15 ký tự (VD: GD4, DN4, CC1, TE1...)</span>
                  </div>

                  <div className="field-group">
                    <label htmlFor="pf-bhyt-rate">Mức hưởng BHYT đúng tuyến</label>
                    <select
                      id="pf-bhyt-rate"
                      className="form-select"
                      value={draft.bhyt_rate}
                      onChange={(e) => updateField('bhyt_rate', e.target.value)}
                    >
                      <option value="80">80% (Người lao động, Hộ gia đình...)</option>
                      <option value="95">95% (Hưu trí, Cận nghèo...)</option>
                      <option value="100">100% (Sĩ quan, Trẻ em &lt;6t, Người có công...)</option>
                    </select>
                  </div>

                  <div className="field-group">
                    <label htmlFor="pf-bhyt-hospital">Nơi đăng ký KCB ban đầu</label>
                    <input
                      id="pf-bhyt-hospital"
                      type="text"
                      list="hospitals-list"
                      className="form-input"
                      placeholder="VD: Bệnh viện Chợ Rẫy (79-011)"
                      value={draft.bhyt_hospital}
                      onChange={(e) => updateField('bhyt_hospital', e.target.value)}
                    />
                    <datalist id="hospitals-list">
                      {COMMON_HOSPITALS.map((h) => (
                        <option key={h} value={h} />
                      ))}
                    </datalist>
                  </div>
                </div>

                {draft.bhyt_number && (
                  <div className="bhyt-verified-callout">
                    <ShieldCheck size={18} className="text-emerald" />
                    <div>
                      <strong>Đã liên kết dữ liệu BHYT thành công</strong>
                      <p>
                        Khi đặt lịch khám hoặc tìm nhà thuốc, hệ thống sẽ tự động ưu tiên danh mục thuốc nằm trong phạm vi thanh toán của BHYT để tối ưu hóa chi phí.
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* Card 2: BHXH & VssID */}
              <div className="form-section-card">
                <div className="form-section-header">
                  <div className="sec-icon-box cyan">
                    <Building2 size={18} />
                  </div>
                  <div>
                    <h3>Bảo Hiểm Xã Hội (BHXH) & Ứng Dụng VssID</h3>
                    <p>Tra cứu lịch sử KCB và hưởng chế độ ốm đau, thai sản, bệnh nghề nghiệp</p>
                  </div>
                </div>

                <div className="form-fields-grid two-col">
                  <div className="field-group">
                    <label htmlFor="pf-bhxh-number">Mã số Bảo hiểm xã hội (10 số)</label>
                    <input
                      id="pf-bhxh-number"
                      type="text"
                      maxLength={10}
                      className="form-input mono"
                      placeholder="VD: 7912345678"
                      value={draft.bhxh_number}
                      onChange={(e) => updateField('bhxh_number', e.target.value)}
                    />
                  </div>

                  <div className="field-group">
                    <label htmlFor="pf-vssid-status">Trạng thái đồng bộ VssID</label>
                    <select
                      id="pf-vssid-status"
                      className="form-select"
                      value={draft.vssid_status}
                      onChange={(e) => updateField('vssid_status', e.target.value)}
                    >
                      <option value="verified">Đã kích hoạt & Liên kết tài khoản</option>
                      <option value="pending">Đang chờ xác minh hồ sơ</option>
                      <option value="unlinked">Chưa liên kết VssID</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Card 3: Bảo hiểm Nhân thọ & Sức khỏe Thương mại */}
              <div className="form-section-card">
                <div className="form-section-header">
                  <div className="sec-icon-box purple">
                    <Shield size={18} />
                  </div>
                  <div>
                    <h3>Bảo Hiểm Sức Khỏe Thương Mại & Nhân Thọ</h3>
                    <p>Bảo lãnh viện phí nội trú, ngoại trú, phẫu thuật và quyền lợi y tế bổ sung</p>
                  </div>
                </div>

                <div className="form-fields-grid three-col">
                  <div className="field-group">
                    <label htmlFor="pf-life-provider">Công ty bảo hiểm cung cấp</label>
                    <input
                      id="pf-life-provider"
                      type="text"
                      list="insurers-list"
                      className="form-input"
                      placeholder="VD: Prudential / Manulife..."
                      value={draft.life_insurance_provider}
                      onChange={(e) => updateField('life_insurance_provider', e.target.value)}
                    />
                    <datalist id="insurers-list">
                      {LIFE_INSURERS.map((ins) => (
                        <option key={ins} value={ins} />
                      ))}
                    </datalist>
                  </div>

                  <div className="field-group">
                    <label htmlFor="pf-life-policy">Số hợp đồng bảo hiểm / Thẻ bảo lãnh</label>
                    <input
                      id="pf-life-policy"
                      type="text"
                      className="form-input mono"
                      placeholder="VD: PRU-88992211"
                      value={draft.life_insurance_policy_no}
                      onChange={(e) => updateField('life_insurance_policy_no', e.target.value)}
                    />
                  </div>

                  <div className="field-group">
                    <label htmlFor="pf-coverage-limit">Hạn mức chi trả bảo hiểm tối đa (VNĐ)</label>
                    <input
                      id="pf-coverage-limit"
                      type="number"
                      step="5000000"
                      className="form-input"
                      placeholder="VD: 500000000 (500 triệu)"
                      value={draft.coverage_limit_vnd}
                      onChange={(e) => updateField('coverage_limit_vnd', e.target.value)}
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ================= TAB 3: CLINICAL & EMERGENCY ================= */}
          {activeTab === 'medical' && (
            <div className="profile-tab-pane fade-in">
              {/* Group 1: Bệnh lý nền */}
              <div className="form-section-card">
                <div className="form-section-header">
                  <div className="sec-icon-box rose">
                    <HeartPulse size={18} />
                  </div>
                  <div>
                    <h3>Bệnh Lý Nền Mạn Tính (Chronic Conditions)</h3>
                    <p>Hệ thống AI đối chiếu để phòng tránh chống chỉ định thuốc và cá nhân hóa chế độ dinh dưỡng</p>
                  </div>
                </div>

                <div className="tags-management-container">
                  <div className="active-tags-row">
                    {draft.conditions.length > 0 ? (
                      draft.conditions.map((c) => (
                        <span key={c} className="clinical-tag condition-tag">
                          <span>{c}</span>
                          <button
                            type="button"
                            className="tag-remove-btn"
                            onClick={() => removeCondition(c)}
                            title="Xóa bệnh lý này"
                          >
                            <X size={12} />
                          </button>
                        </span>
                      ))
                    ) : (
                      <span className="no-tags-placeholder">Chưa ghi nhận bệnh lý nền mạn tính nào.</span>
                    )}
                  </div>

                  <div className="add-tag-input-row">
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Nhập tên bệnh lý cần thêm (VD: Gan nhiễm mỡ độ 1...)"
                      value={newConditionInput}
                      onChange={(e) => setNewConditionInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          addCondition(newConditionInput);
                        }
                      }}
                    />
                    <button
                      type="button"
                      className="btn-add-tag"
                      onClick={() => addCondition(newConditionInput)}
                      disabled={!newConditionInput.trim()}
                    >
                      <Plus size={14} />
                      <span>Thêm bệnh</span>
                    </button>
                  </div>

                  <div className="quick-pick-tags-section">
                    <span className="quick-pick-label">Gợi ý chọn nhanh:</span>
                    <div className="quick-tags-wrap">
                      {COMMON_CONDITIONS.map((c) => {
                        const isAdded = draft.conditions.includes(c);
                        return (
                          <button
                            key={c}
                            type="button"
                            className={`quick-tag-btn ${isAdded ? 'added' : ''}`}
                            onClick={() => (isAdded ? removeCondition(c) : addCondition(c))}
                          >
                            {isAdded ? <Check size={11} /> : <Plus size={11} />}
                            <span>{c}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </div>

              {/* Group 2: Dị ứng */}
              <div className="form-section-card alert-border">
                <div className="form-section-header">
                  <div className="sec-icon-box alert-red">
                    <ShieldAlert size={18} />
                  </div>
                  <div>
                    <h3>Tiền Sử Dị Ứng Thuốc & Thực Phẩm (Allergies)</h3>
                    <p className="text-danger">Cảnh báo tối khẩn cấp: AI sẽ chặn tự động các đơn thuốc chứa hoạt chất dị ứng</p>
                  </div>
                </div>

                <div className="tags-management-container">
                  <div className="active-tags-row">
                    {draft.allergies.length > 0 ? (
                      draft.allergies.map((a) => (
                        <span key={a} className="clinical-tag allergy-tag">
                          <AlertTriangle size={12} />
                          <span>{a}</span>
                          <button
                            type="button"
                            className="tag-remove-btn"
                            onClick={() => removeAllergy(a)}
                            title="Xóa dị ứng này"
                          >
                            <X size={12} />
                          </button>
                        </span>
                      ))
                    ) : (
                      <span className="no-tags-placeholder safe">Không ghi nhận dị ứng thuốc hoặc thực phẩm.</span>
                    )}
                  </div>

                  <div className="add-tag-input-row">
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Nhập chất gây dị ứng (VD: Penicillin, Tôm cua...)"
                      value={newAllergyInput}
                      onChange={(e) => setNewAllergyInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          addAllergy(newAllergyInput);
                        }
                      }}
                    />
                    <button
                      type="button"
                      className="btn-add-tag danger"
                      onClick={() => addAllergy(newAllergyInput)}
                      disabled={!newAllergyInput.trim()}
                    >
                      <Plus size={14} />
                      <span>Thêm dị ứng</span>
                    </button>
                  </div>

                  <div className="quick-pick-tags-section">
                    <span className="quick-pick-label">Chất dị ứng phổ biến:</span>
                    <div className="quick-tags-wrap">
                      {COMMON_ALLERGIES.map((a) => {
                        const isAdded = draft.allergies.includes(a);
                        return (
                          <button
                            key={a}
                            type="button"
                            className={`quick-tag-btn danger ${isAdded ? 'added' : ''}`}
                            onClick={() => (isAdded ? removeAllergy(a) : addAllergy(a))}
                          >
                            {isAdded ? <Check size={11} /> : <Plus size={11} />}
                            <span>{a}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </div>

              {/* Group 3: Thuốc đang dùng & Liên hệ khẩn cấp */}
              <div className="form-section-card">
                <div className="form-section-header">
                  <div className="sec-icon-box amber">
                    <AlertTriangle size={18} />
                  </div>
                  <div>
                    <h3>Người Thân Liên Hệ Khẩn Cấp (24/7 SOS Contact)</h3>
                    <p>Người được thông báo và ủy quyền quyết định y khoa trong trường hợp khẩn cấp</p>
                  </div>
                </div>

                <div className="form-fields-grid three-col">
                  <div className="field-group">
                    <label htmlFor="pf-sos-name">Họ và tên người liên hệ</label>
                    <input
                      id="pf-sos-name"
                      type="text"
                      className="form-input"
                      placeholder="VD: Trần Thị Mai"
                      value={draft.emergency_contact_name}
                      onChange={(e) => updateField('emergency_contact_name', e.target.value)}
                    />
                  </div>

                  <div className="field-group">
                    <label htmlFor="pf-sos-rel">Mối quan hệ với bệnh nhân</label>
                    <select
                      id="pf-sos-rel"
                      className="form-select"
                      value={draft.emergency_contact_relation}
                      onChange={(e) => updateField('emergency_contact_relation', e.target.value)}
                    >
                      <option value="">-- Chọn mối quan hệ --</option>
                      <option value="Vợ/Chồng">Vợ / Chồng</option>
                      <option value="Bố/Mẹ">Bố / Mẹ</option>
                      <option value="Con">Con ruột</option>
                      <option value="Anh/Chị/Em">Anh / Chị / Em</option>
                      <option value="Người giám hộ">Người giám hộ hợp pháp</option>
                      <option value="Bạn thân / Đồng nghiệp">Bạn bè / Đồng nghiệp</option>
                    </select>
                  </div>

                  <div className="field-group">
                    <label htmlFor="pf-sos-phone">Số điện thoại khẩn cấp 24/7</label>
                    <input
                      id="pf-sos-phone"
                      type="tel"
                      className="form-input"
                      placeholder="VD: 0988776655"
                      value={draft.emergency_contact_phone}
                      onChange={(e) => updateField('emergency_contact_phone', e.target.value)}
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* 5. BOTTOM SUBMIT & DISCARD FOOTER */}
          <div className="profile-form-footer-bar">
            <div className="footer-left-info">
              <span className="security-notice">
                <ShieldCheck size={14} className="text-emerald" />
                <span>Dữ liệu được mã hóa đầu cuối và tuân thủ chuẩn bảo mật y tế HIPAA / HL7 FHIR</span>
              </span>
            </div>

            <div className="footer-right-buttons">
              <button
                type="button"
                className="btn-clear-profile"
                onClick={() => {
                  if (window.confirm('Bạn có chắc chắn muốn xóa toàn bộ thông tin hồ sơ phiên này?')) {
                    onClear?.();
                  }
                }}
              >
                <Trash2 size={14} />
                <span>Xóa hồ sơ</span>
              </button>

              <button
                type="submit"
                className={`btn-save-master ${saveSuccess ? 'success' : ''}`}
                disabled={saving}
              >
                {saving ? (
                  <>
                    <RefreshCw size={15} className="spin-icon" />
                    <span>Đang lưu hồ sơ...</span>
                  </>
                ) : saveSuccess ? (
                  <>
                    <Check size={16} />
                    <span>Lưu thành công!</span>
                  </>
                ) : (
                  <>
                    <Save size={15} />
                    <span>Lưu Thay Đổi Hồ Sơ</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </form>
      </div>

      {/* 6. FLOATING DOCK WHEN FORM IS DIRTY */}
      {isDirty && (
        <div className="profile-floating-dock-banner">
          <div className="dock-left">
            <span className="dock-dirty-dot" />
            <span>Bạn có thay đổi chưa được lưu trên hồ sơ</span>
          </div>
          <div className="dock-actions">
            <button
              type="button"
              className="dock-btn-discard"
              onClick={handleReset}
              disabled={saving}
            >
              Hủy
            </button>
            <button
              type="button"
              className="dock-btn-save"
              onClick={handleSave}
              disabled={saving}
            >
              <Save size={14} />
              <span>{saving ? 'Đang lưu...' : 'Lưu hồ sơ ngay'}</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
