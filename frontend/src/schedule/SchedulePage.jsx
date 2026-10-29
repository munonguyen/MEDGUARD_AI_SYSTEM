import { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  Calendar,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Clock3,
  Edit3,
  Filter,
  HeartPulse,
  Info,
  LoaderCircle,
  MessageSquare,
  Pill,
  Plus,
  Printer,
  RefreshCw,
  Search,
  Sparkles,
  Stethoscope,
  Trash2,
  User,
  UserCheck,
  X,
} from 'lucide-react';

// Helper to calculate days of a week around a given date
function getWeekDates(baseDate = new Date()) {
  const current = new Date(baseDate);
  const day = current.getDay(); // 0 is Sunday, 1 is Monday...
  const diffToMonday = day === 0 ? -6 : 1 - day;
  const monday = new Date(current);
  monday.setDate(current.getDate() + diffToMonday);

  const days = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    days.push(d.toISOString().slice(0, 10));
  }
  return days;
}

function formatDateVietnamese(dateStr) {
  try {
    const d = new Date(dateStr + 'T00:00:00');
    return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`;
  } catch {
    return dateStr;
  }
}

const DAY_NAMES = [
  'Thứ 2',
  'Thứ 3',
  'Thứ 4',
  'Thứ 5',
  'Thứ 6',
  'Thứ 7',
  'Chủ Nhật',
];

const TODAY_STR = new Date().toISOString().slice(0, 10);
const CURRENT_WEEK_DAYS = getWeekDates(new Date());

const statusLabels = {
  in_progress: { label: 'Đang khám', className: 'status-pill in-progress' },
  confirmed: { label: 'Đã xác nhận', className: 'status-pill confirmed' },
  waiting: { label: 'Chờ tiếp nhận', className: 'status-pill waiting' },
  completed: { label: 'Đã hoàn tất', className: 'status-pill completed' },
  priority: { label: 'Cần ưu tiên', className: 'status-pill priority' },
};

const shiftFilterLabels = [
  { id: 'all', label: 'Tất cả các ca' },
  { id: 'morning', label: 'Ca Sáng (07:30 - 11:30)' },
  { id: 'afternoon', label: 'Ca Chiều (13:00 - 17:00)' },
  { id: 'evening', label: 'Ca Tối & Trực (17:30 - 21:30)' },
  { id: 'meds', label: 'Ca Uống Thuốc Trong Ngày' },
];

export function SchedulePage({ api, onBackToChat, onConsultPatient, onOpenMedicationPage }) {
  // Shifts state (synced with TiDB)
  const [shifts, setShifts] = useState(() => {
    try {
      const saved = localStorage.getItem('medguard.shifts.data');
      if (saved) {
        if (saved.includes('Nguyễn Văn An') || saved.includes('Trần Thị Mai')) {
          localStorage.removeItem('medguard.shifts.data');
          return [];
        }
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) return parsed;
      }
      return [];
    } catch {
      return [];
    }
  });

  // User medications state
  const [userMeds, setUserMeds] = useState(() => {
    try {
      const saved = localStorage.getItem('medguard.user_meds.data');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  // View switch: 'timetable' (weekly grid like user's image), 'cards' (card list), 'meds' (medication tracker)
  const [activeViewMode, setActiveViewMode] = useState('timetable');

  // Week navigation
  const [currentBaseDate, setCurrentBaseDate] = useState(new Date());
  const weekDates = useMemo(() => getWeekDates(currentBaseDate), [currentBaseDate]);

  // Filters
  const [selectedDate, setSelectedDate] = useState(TODAY_STR);
  const [selectedShiftFilter, setSelectedShiftFilter] = useState('all');
  const [selectedStatusFilter, setSelectedStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [medSchedules, setMedSchedules] = useState([]);
  const [loadingMeds, setLoadingMeds] = useState(false);
  const [loadingShifts, setLoadingShifts] = useState(false);
  const [dbConnected, setDbConnected] = useState(false);
  const [takenMeds, setTakenMeds] = useState({});

  // Hover Popover State
  const [hoveredShift, setHoveredShift] = useState(null);
  const [hoverPosition, setHoverPosition] = useState({ x: 0, y: 0, top: 0, bottom: 0, right: 0 });

  // CRUD Modals State
  const [shiftModal, setShiftModal] = useState({ open: false, mode: 'create', data: null });
  const [medModal, setMedModal] = useState({ open: false, mode: 'create', data: null });
  const [deleteDialog, setDeleteDialog] = useState({ open: false, type: 'shift', item: null });

  // Sync shifts to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('medguard.shifts.data', JSON.stringify(shifts));
    } catch {
      // ignore
    }
  }, [shifts]);

  // Sync user meds to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('medguard.user_meds.data', JSON.stringify(userMeds));
    } catch {
      // ignore
    }
  }, [userMeds]);

  // Load shifts from Database (TiDB Cloud)
  const loadShiftsFromDb = async () => {
    if (!api) return;
    setLoadingShifts(true);
    try {
      const res = await api.request('/v1/schedule/shifts');
      if (res && Array.isArray(res.shifts)) {
        setShifts(res.shifts);
        setDbConnected(true);
      }
    } catch (err) {
      console.warn('Could not load shifts from DB:', err);
    } finally {
      setLoadingShifts(false);
    }
  };

  const handleSeedSampleShifts = async () => {
    if (!api) return;
    setLoadingShifts(true);
    try {
      const res = await api.request('/v1/schedule/seed-sample', { method: 'POST' });
      if (res && Array.isArray(res.shifts)) {
        setShifts(res.shifts);
        setDbConnected(true);
      }
    } catch (err) {
      console.warn('Could not seed sample shifts:', err);
    } finally {
      setLoadingShifts(false);
    }
  };

  const handleClearShifts = async () => {
    if (!api) return;
    setLoadingShifts(true);
    try {
      await api.request('/v1/schedule/clear', { method: 'POST' });
      setShifts([]);
    } catch (err) {
      console.warn('Could not clear shifts:', err);
    } finally {
      setLoadingShifts(false);
    }
  };

  // Load medication schedules from API
  const loadMedicationSchedules = async () => {
    if (!api) return;
    setLoadingMeds(true);
    try {
      const res = await api.request('/v1/medication/regimen');
      if (res && Array.isArray(res.medications)) {
        setUserMeds(res.medications);
        const ocrItems = res.medications.filter((m) => m.scheduled_at && m.source === 'prescription_review');
        setMedSchedules(res.ocr_schedules || ocrItems);
      }
    } catch (err) {
      console.warn('Could not load med schedules:', err);
    } finally {
      setLoadingMeds(false);
    }
  };

  const handleRefreshAll = () => {
    loadShiftsFromDb();
    loadMedicationSchedules();
  };

  useEffect(() => {
    loadShiftsFromDb();
    loadMedicationSchedules();
  }, [api]);

  // Status transition handler - with instant DB persistence
  const handleUpdateStatus = async (shiftId, newStatus) => {
    setShifts((current) =>
      current.map((item) => (item.id === shiftId ? { ...item, status: newStatus } : item))
    );
    if (hoveredShift && hoveredShift.id === shiftId) {
      setHoveredShift((prev) => (prev ? { ...prev, status: newStatus } : null));
    }
    try {
      if (api) {
        await api.request(`/v1/schedule/shifts/${encodeURIComponent(shiftId)}/status`, {
          method: 'PATCH',
          body: { status: newStatus },
        });
      }
    } catch (err) {
      console.warn('Failed to update shift status in DB:', err);
    }
  };

  // Navigate Weeks
  const handlePrevWeek = () => {
    setCurrentBaseDate((prev) => {
      const d = new Date(prev);
      d.setDate(d.getDate() - 7);
      return d;
    });
  };

  const handleNextWeek = () => {
    setCurrentBaseDate((prev) => {
      const d = new Date(prev);
      d.setDate(d.getDate() + 7);
      return d;
    });
  };

  const handleCurrentWeek = () => {
    setCurrentBaseDate(new Date());
  };

  // Filtered shifts for Cards View
  const filteredShifts = useMemo(() => {
    return shifts.filter((item) => {
      if (selectedDate && item.date !== selectedDate) return false;
      if (selectedShiftFilter !== 'all' && selectedShiftFilter !== 'meds' && item.shiftType !== selectedShiftFilter) {
        return false;
      }
      if (selectedStatusFilter !== 'all' && item.status !== selectedStatusFilter) {
        return false;
      }
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const matchPatient = item.patientName.toLowerCase().includes(query) || item.patientRef.toLowerCase().includes(query);
        const matchDoctor = item.doctor.toLowerCase().includes(query) || item.department.toLowerCase().includes(query);
        const matchPurpose = item.purpose.toLowerCase().includes(query) || item.room.toLowerCase().includes(query);
        if (!matchPatient && !matchDoctor && !matchPurpose) return false;
      }
      return true;
    });
  }, [shifts, selectedDate, selectedShiftFilter, selectedStatusFilter, searchQuery]);

  // Summary Metrics
  const stats = useMemo(() => {
    const todayShifts = shifts.filter((s) => s.date === selectedDate);
    const morningCount = todayShifts.filter((s) => s.shiftType === 'morning').length;
    const afternoonCount = todayShifts.filter((s) => s.shiftType === 'afternoon').length;
    const eveningCount = todayShifts.filter((s) => s.shiftType === 'evening').length;
    const priorityCount = todayShifts.filter((s) => s.status === 'priority' || s.priority === 'urgent').length;
    return {
      total: todayShifts.length,
      morningCount,
      afternoonCount,
      eveningCount,
      priorityCount,
      medCount: userMeds.length + medSchedules.length,
    };
  }, [shifts, selectedDate, userMeds, medSchedules]);

  // Toggle med taken
  const toggleUserMedTaken = (id) => {
    setUserMeds((prev) =>
      prev.map((med) => (med.id === id ? { ...med, isTaken: !med.isTaken } : med))
    );
  };

  const toggleMedTaken = (id) => {
    setTakenMeds((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  // Hover popover trigger with coordinates
  const handleShiftMouseEnter = (shift, e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setHoverPosition({
      x: rect.left,
      y: rect.bottom + 8,
      top: rect.top,
      bottom: rect.bottom,
      right: rect.right,
      width: rect.width,
    });
    setHoveredShift(shift);
  };

  const handleShiftMouseLeave = () => {
    setHoveredShift(null);
  };

  // Save Shift (Create / Update)
  const handleSaveShift = (formData) => {
    if (shiftModal.mode === 'create') {
      const shiftType = formData.shiftType;
      const newShift = {
        id: `SHIFT-${Math.floor(100 + Math.random() * 900)}`,
        shiftType: shiftType,
        shiftName:
          shiftType === 'morning'
            ? 'Ca Sáng (07:30 - 11:30)'
            : shiftType === 'afternoon'
            ? 'Ca Chiều (13:00 - 17:00)'
            : 'Ca Tối & Trực Đêm (17:30 - 21:30)',
        timeSlot: formData.timeSlot || '09:00 - 09:30',
        date: formData.date || selectedDate,
        patientRef: (formData.patientRef || 'BN-NEW').toUpperCase(),
        patientName: formData.patientName || 'Bệnh nhân mới',
        age: Number(formData.age) || 35,
        sex: formData.sex || 'Nam',
        phone: formData.phone || '0900 000 000',
        doctor: formData.doctor || 'BS. CKII Khám Tổng quát',
        department: formData.department || 'Nội khoa',
        room: formData.room || 'Phòng Khám P.102',
        purpose: formData.purpose || 'Khám và tư vấn sức khỏe tổng quát',
        vitals: {
          bp: formData.bp || '--',
          hr: formData.hr || '--',
          spo2: formData.spo2 || '--',
          temp: formData.temp || '--',
        },
        prepNotes: formData.prepNotes || 'Mang theo hồ sơ khám cũ nếu có.',
        status: formData.status || 'confirmed',
        priority: formData.priority || 'normal',
        currentMeds: formData.currentMeds ? formData.currentMeds.split(',').map((m) => m.trim()).filter(Boolean) : [],
      };
      setShifts((prev) => [newShift, ...prev]);
      try {
        if (api) {
          api.request('/v1/schedule/shifts', { method: 'POST', body: newShift }).catch((e) => console.warn('DB create error:', e));
        }
      } catch (err) {
        console.warn('DB sync error:', err);
      }
    } else if (shiftModal.mode === 'edit' && shiftModal.data) {
      const updatedShift = {
        ...shiftModal.data,
        patientName: formData.patientName,
        patientRef: formData.patientRef,
        age: Number(formData.age) || shiftModal.data.age,
        sex: formData.sex,
        phone: formData.phone,
        date: formData.date,
        shiftType: formData.shiftType,
        shiftName:
          formData.shiftType === 'morning'
            ? 'Ca Sáng (07:30 - 11:30)'
            : formData.shiftType === 'afternoon'
            ? 'Ca Chiều (13:00 - 17:00)'
            : 'Ca Tối & Trực Đêm (17:30 - 21:30)',
        timeSlot: formData.timeSlot,
        doctor: formData.doctor,
        department: formData.department,
        room: formData.room,
        purpose: formData.purpose,
        vitals: {
          bp: formData.bp,
          hr: formData.hr,
          spo2: formData.spo2,
          temp: formData.temp || shiftModal.data.vitals?.temp || '36.8°C',
        },
        prepNotes: formData.prepNotes,
        status: formData.status,
        priority: formData.priority,
        currentMeds: formData.currentMeds ? formData.currentMeds.split(',').map((m) => m.trim()).filter(Boolean) : shiftModal.data.currentMeds,
      };
      setShifts((prev) =>
        prev.map((s) => (s.id !== shiftModal.data.id ? s : updatedShift))
      );
      try {
        if (api) {
          api.request(`/v1/schedule/shifts/${encodeURIComponent(shiftModal.data.id)}`, {
            method: 'PUT',
            body: updatedShift,
          }).catch((e) => console.warn('DB update error:', e));
        }
      } catch (err) {
        console.warn('DB update sync error:', err);
      }
    }
    setShiftModal({ open: false, mode: 'create', data: null });
  };

  // Delete Shift
  const handleConfirmDelete = () => {
    if (!deleteDialog.item) return;
    if (deleteDialog.type === 'shift') {
      const shiftId = deleteDialog.item.id;
      setShifts((prev) => prev.filter((s) => s.id !== shiftId));
      if (hoveredShift && hoveredShift.id === shiftId) setHoveredShift(null);
      try {
        if (api) {
          api.request(`/v1/schedule/shifts/${encodeURIComponent(shiftId)}`, {
            method: 'DELETE',
          }).catch((e) => console.warn('DB delete error:', e));
        }
      } catch (err) {
        console.warn('DB delete sync error:', err);
      }
    } else if (deleteDialog.type === 'med') {
      setUserMeds((prev) => prev.filter((m) => m.id !== deleteDialog.item.id));
    }
    setDeleteDialog({ open: false, type: 'shift', item: null });
  };

  // Save User Medication
  const handleSaveMed = (formData) => {
    if (medModal.mode === 'create') {
      const newMed = {
        id: `MED-${Math.floor(100 + Math.random() * 900)}`,
        name: formData.name,
        strength: formData.strength || '500mg',
        dosage: formData.dosage || '1 viên',
        timing: formData.timing || '08:00',
        slot: formData.slot || 'morning',
        slotLabel:
          formData.slot === 'morning'
            ? 'Cữ Sáng (06:00 - 09:00)'
            : formData.slot === 'noon'
            ? 'Cữ Trưa (11:30 - 13:00)'
            : formData.slot === 'evening'
            ? 'Cữ Tối (17:30 - 19:30)'
            : 'Cữ Khuya (20:30 - 22:00)',
        instruction: formData.instruction || 'Uống sau bữa ăn với nhiều nước',
        days: ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'],
        isTaken: false,
        note: formData.note || '',
      };
      setUserMeds((prev) => [...prev, newMed]);
    } else if (medModal.mode === 'edit' && medModal.data) {
      setUserMeds((prev) =>
        prev.map((m) => {
          if (m.id !== medModal.data.id) return m;
          return {
            ...m,
            name: formData.name,
            strength: formData.strength,
            dosage: formData.dosage,
            timing: formData.timing,
            slot: formData.slot,
            slotLabel:
              formData.slot === 'morning'
                ? 'Cữ Sáng (06:00 - 09:00)'
                : formData.slot === 'noon'
                ? 'Cữ Trưa (11:30 - 13:00)'
                : formData.slot === 'evening'
                ? 'Cữ Tối (17:30 - 19:30)'
                : 'Cữ Khuya (20:30 - 22:00)',
            instruction: formData.instruction,
            note: formData.note,
          };
        })
      );
    }
    setMedModal({ open: false, mode: 'create', data: null });
  };

  return (
    <div className="schedule-page-view">
      {/* Top Header */}
      <header className="schedule-top-nav">
        <div className="schedule-header-left">
          <button className="schedule-back-btn" type="button" onClick={onBackToChat} title="Quay lại cuộc trò chuyện">
            <ArrowLeft size={18} />
            <span>Về phòng Chat</span>
          </button>
          <div className="schedule-title-block">
            <div className="schedule-title-badge">
              <CalendarDays size={18} />
              <h1>Lịch Khám</h1>
            </div>
            <p>Thời khóa biểu tuần, quản lý ca khám bác sĩ, chuyên khoa lâm sàng và điều phối hồ sơ bệnh nhân</p>
          </div>
        </div>

        <div className="schedule-header-actions">
          {/* View Mode Toggle Buttons */}
          <div className="view-mode-toggle-group">
            <button
              type="button"
              className={`view-mode-btn ${activeViewMode === 'timetable' && selectedShiftFilter !== 'meds' ? 'active' : ''}`}
              onClick={() => { setActiveViewMode('timetable'); setSelectedShiftFilter('all'); }}
              title="Xem thời khóa biểu tuần"
            >
              <Calendar size={15} />
              <span>Thời khóa biểu tuần</span>
            </button>
            <button
              type="button"
              className={`view-mode-btn ${activeViewMode === 'cards' && selectedShiftFilter !== 'meds' ? 'active' : ''}`}
              onClick={() => { setActiveViewMode('cards'); setSelectedShiftFilter('all'); }}
              title="Xem danh sách thẻ"
            >
              <Filter size={15} />
              <span>Danh sách ca</span>
            </button>
          </div>

          <button
            type="button"
            className="btn-open-med-page"
            onClick={onOpenMedicationPage}
            title="Chuyển sang trang Lịch Uống Thuốc chuyên biệt"
          >
            <Pill size={15} />
            <span>Xem Lịch Uống Thuốc</span>
          </button>

          <div className="db-sync-badge" title="Đồng bộ hồ sơ lâm sàng bảo mật & thời gian thực">
            <span className={`pulse-dot ${dbConnected ? 'live' : ''}`} />
            <span>Đồng bộ Trực tuyến</span>
          </div>

          <button className="btn-refresh" type="button" onClick={handleRefreshAll} title="Làm mới dữ liệu từ Database">
            <RefreshCw size={16} className={loadingShifts || loadingMeds ? 'spin' : ''} />
            <span>Làm mới</span>
          </button>
          {shifts.length === 0 ? (
            <button
              className="btn-refresh"
              type="button"
              onClick={handleSeedSampleShifts}
              title="Nạp lịch ca khám mẫu để trải nghiệm"
              style={{ background: 'rgba(56, 189, 248, 0.1)', borderColor: '#38bdf8', color: '#0284c7' }}
            >
              <Sparkles size={16} />
              <span>Nạp mẫu Demo</span>
            </button>
          ) : (
            <button
              className="btn-refresh"
              type="button"
              onClick={handleClearShifts}
              title="Xóa toàn bộ lịch về trạng thái trống"
              style={{ background: 'rgba(239, 68, 68, 0.08)', borderColor: '#fca5a5', color: '#dc2626' }}
            >
              <Trash2 size={16} />
              <span>Xóa lịch</span>
            </button>
          )}
          <button className="btn-primary-add" type="button" onClick={() => setShiftModal({ open: true, mode: 'create', data: null })}>
            <Plus size={17} />
            <span>+ Đặt Lịch Khám Mới</span>
          </button>
        </div>
      </header>

      {/* Onboarding Empty Banner if No Shifts */}
      {shifts.length === 0 && (
        <div style={{
          margin: '0.75rem 1.25rem',
          padding: '1rem 1.25rem',
          background: 'linear-gradient(135deg, rgba(14, 165, 233, 0.06), rgba(99, 102, 241, 0.06))',
          border: '1px dashed #38bdf8',
          borderRadius: '12px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1rem',
          flexWrap: 'wrap'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '1.5rem' }}>📋</span>
            <div>
              <div style={{ fontWeight: '600', color: '#0f172a', fontSize: '0.95rem' }}>
                Chưa có lịch khám nào trong cơ sở dữ liệu cho tài khoản của bạn
              </div>
              <div style={{ fontSize: '0.82rem', color: '#64748b' }}>
                Hệ thống đã đồng bộ chuẩn xác với cơ sở dữ liệu TiDB Cloud. Bạn có thể tự đặt lịch khám hoặc nạp dữ liệu mẫu để trải nghiệm.
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              type="button"
              onClick={() => setShiftModal({ open: true, mode: 'create', data: null })}
              style={{
                padding: '0.45rem 0.9rem',
                borderRadius: '8px',
                background: '#0284c7',
                color: '#fff',
                border: 'none',
                fontWeight: '600',
                fontSize: '0.84rem',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.4rem'
              }}
            >
              <Plus size={15} /> + Đặt lịch khám
            </button>
            <button
              type="button"
              onClick={handleSeedSampleShifts}
              style={{
                padding: '0.45rem 0.9rem',
                borderRadius: '8px',
                background: '#fff',
                color: '#0284c7',
                border: '1px solid #38bdf8',
                fontWeight: '600',
                fontSize: '0.84rem',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.4rem'
              }}
            >
              <Sparkles size={15} /> Nạp lịch mẫu Demo
            </button>
          </div>
        </div>
      )}

      {/* Bento Stats Row */}
      <section className="schedule-bento-grid" aria-label="Thống kê ca khám">
        <div className="bento-card total-card" onClick={() => { setSelectedShiftFilter('all'); setActiveViewMode('timetable'); }}>
          <div className="bento-icon"><Calendar size={22} /></div>
          <div className="bento-data">
            <span className="bento-label">Lịch Khám Hôm Nay</span>
            <strong className="bento-val">{stats.total} <small>lịch hẹn</small></strong>
          </div>
        </div>

        <div className="bento-card morning-card" onClick={() => { setSelectedShiftFilter('morning'); setActiveViewMode('cards'); }}>
          <div className="bento-icon"><Clock3 size={22} /></div>
          <div className="bento-data">
            <span className="bento-label">
              <span>Ca Sáng</span>
              <small className="bento-shift-time">07:30 – 11:30</small>
            </span>
            <strong className="bento-val">{stats.morningCount} <small>lịch hẹn</small></strong>
          </div>
        </div>

        <div className="bento-card afternoon-card" onClick={() => { setSelectedShiftFilter('afternoon'); setActiveViewMode('cards'); }}>
          <div className="bento-icon"><Clock size={22} /></div>
          <div className="bento-data">
            <span className="bento-label">
              <span>Ca Chiều</span>
              <small className="bento-shift-time">13:00 – 17:00</small>
            </span>
            <strong className="bento-val">{stats.afternoonCount} <small>lịch hẹn</small></strong>
          </div>
        </div>

        <div className="bento-card evening-card" onClick={() => { setSelectedShiftFilter('evening'); setActiveViewMode('cards'); }}>
          <div className="bento-icon"><HeartPulse size={22} /></div>
          <div className="bento-data">
            <span className="bento-label">
              <span>Ca Tối</span>
              <small className="bento-shift-time">Khám ngoài giờ</small>
            </span>
            <strong className="bento-val">{stats.eveningCount} <small>lịch hẹn</small></strong>
          </div>
        </div>

        <div className="bento-card urgent-card" onClick={() => { setSelectedStatusFilter('priority'); setActiveViewMode('cards'); }}>
          <div className="bento-icon"><AlertTriangle size={22} /></div>
          <div className="bento-data">
            <span className="bento-label">Cần Khám Ưu Tiên</span>
            <strong className="bento-val">{stats.priorityCount} <small>lịch khẩn</small></strong>
          </div>
        </div>

        <div className="bento-card med-card" onClick={() => { if (onOpenMedicationPage) onOpenMedicationPage(); else { setSelectedShiftFilter('meds'); setActiveViewMode('meds'); } }} title="Mở trang Lịch Uống Thuốc riêng biệt">
          <div className="bento-icon"><Pill size={22} /></div>
          <div className="bento-data">
            <span className="bento-label">Lịch Uống Thuốc</span>
            <strong className="bento-val">{stats.medCount} <small>mở trang riêng →</small></strong>
          </div>
        </div>
      </section>

      {/* Control Bar: Date picker, Shift Tabs, Search & Status filter */}
      <section className="schedule-controls-panel">
        <div className="controls-row-top">
          {/* Date Selector */}
          <div className="date-nav-block">
            <span className="control-label">Chọn ngày:</span>
            <div className="date-chip-group">
              <button
                type="button"
                className={`date-chip ${selectedDate === TODAY_STR ? 'active' : ''}`}
                onClick={() => setSelectedDate(TODAY_STR)}
              >
                Hôm nay
              </button>
              <button
                type="button"
                className={`date-chip ${selectedDate === new Date(Date.now() + 86400000).toISOString().slice(0, 10) ? 'active' : ''}`}
                onClick={() => setSelectedDate(new Date(Date.now() + 86400000).toISOString().slice(0, 10))}
              >
                Ngày mai
              </button>
              <div className="date-input-wrapper">
                <input
                  type="date"
                  value={selectedDate}
                  onChange={(e) => setSelectedDate(e.target.value)}
                  className="native-date-input"
                />
              </div>
            </div>
          </div>

          {/* Search Box */}
          <div className="search-box-wrap">
            <Search size={16} />
            <input
              type="text"
              placeholder="Tìm theo tên BN, mã hồ sơ (BN-001), Bác sĩ, chuyên khoa..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="Tìm kiếm ca khám"
            />
            {searchQuery && (
              <button type="button" className="search-clear" onClick={() => setSearchQuery('')}>
                <X size={14} />
              </button>
            )}
          </div>
        </div>

        {/* Shift Filter Pills */}
        <div className="controls-row-bottom">
          <div className="shift-filter-tabs">
            {shiftFilterLabels.map((tab) => (
              <button
                key={tab.id}
                type="button"
                className={`shift-tab-pill ${selectedShiftFilter === tab.id ? 'active' : ''}`}
                onClick={() => {
                  setSelectedShiftFilter(tab.id);
                  if (tab.id === 'meds') setActiveViewMode('meds');
                  else if (activeViewMode === 'meds') setActiveViewMode('cards');
                }}
              >
                {tab.id === 'meds' && <Pill size={14} />}
                {tab.id === 'morning' && <Clock3 size={14} />}
                {tab.id === 'afternoon' && <Clock size={14} />}
                {tab.id === 'evening' && <HeartPulse size={14} />}
                <span>{tab.label}</span>
              </button>
            ))}
          </div>

          {/* Status Dropdown */}
          <div className="status-filter-wrapper">
            <Filter size={14} />
            <select
              value={selectedStatusFilter}
              onChange={(e) => setSelectedStatusFilter(e.target.value)}
              aria-label="Lọc theo trạng thái"
            >
              <option value="all">Tất cả trạng thái</option>
              <option value="in_progress">Đang khám</option>
              <option value="confirmed">Đã xác nhận</option>
              <option value="waiting">Chờ tiếp nhận</option>
              <option value="priority">Cần ưu tiên</option>
              <option value="completed">Đã hoàn tất</option>
            </select>
          </div>
        </div>
      </section>

      {/* Main Content Area */}
      <div className="schedule-content-layout">
        {/* VIEW 1: DEDICATED USER MEDICATION SCHEDULE */}
        {selectedShiftFilter === 'meds' || activeViewMode === 'meds' ? (
          <section className="med-schedules-section">
            <div className="section-header-row">
              <div>
                <h2><Pill size={18} /> Lịch Ca Uống Thuốc Trong Ngày</h2>
                <p>Lịch nhắc nhở và quản lý việc uống thuốc hàng ngày của người bệnh (kèm điểm danh đã uống)</p>
              </div>
              <button
                type="button"
                className="btn-primary-add"
                onClick={() => setMedModal({ open: true, mode: 'create', data: null })}
              >
                <Plus size={16} />
                <span>Thêm Thuốc Mới Vào Lịch</span>
              </button>
            </div>

            {/* Daily User Medication Timeline Cards */}
            <div className="user-meds-timeline">
              {['morning', 'noon', 'evening', 'night'].map((slotKey) => {
                const slotMeds = userMeds.filter((m) => {
                  const s = m.slot === 'afternoon' ? 'evening' : m.slot;
                  return s === slotKey;
                });
                const slotTitle =
                  slotKey === 'morning'
                    ? '🌅 Cữ Sáng (06:00 - 09:00)'
                    : slotKey === 'noon'
                    ? '☀️ Cữ Trưa (11:30 - 13:00)'
                    : slotKey === 'evening'
                    ? '🌇 Cữ Chiều / Tối (17:30 - 19:30)'
                    : '🌙 Cữ Khuya (Trước khi ngủ 20:30 - 22:00)';

                return (
                  <div key={slotKey} className="med-slot-block">
                    <div className="slot-heading">
                      <h3>{slotTitle}</h3>
                      <span className="slot-count">{slotMeds.length} loại thuốc</span>
                    </div>

                    {slotMeds.length === 0 ? (
                      <p className="slot-empty">Không có thuốc cần uống trong khung giờ này</p>
                    ) : (
                      <div className="med-items-grid">
                        {slotMeds.map((med) => (
                          <div
                            key={med.id}
                            className={`med-schedule-card ${med.isTaken ? 'is-taken' : ''}`}
                            onMouseEnter={(e) =>
                              handleShiftMouseEnter(
                                {
                                  id: med.id,
                                  patientName: 'Người dùng hiện tại',
                                  patientRef: 'BN-USER',
                                  purpose: `Uống thuốc: ${med.name} (${med.strength}) - ${med.instruction}`,
                                  timeSlot: med.timing,
                                  doctor: 'Dược sĩ / Bác sĩ chỉ định',
                                  department: 'Đơn thuốc cá nhân',
                                  room: 'Tại nhà',
                                  status: med.isTaken ? 'completed' : 'waiting',
                                  vitals: null,
                                  prepNotes: med.note || med.instruction,
                                  currentMeds: [med.name + ' ' + med.strength],
                                },
                                e
                              )
                            }
                            onMouseLeave={handleShiftMouseLeave}
                          >
                            <div className="med-card-time">
                              <Clock3 size={16} />
                              <strong>{med.timing}</strong>
                              <span className="med-recurrence">{med.dosage}</span>
                            </div>
                            <div className="med-card-body">
                              <div className="med-name-row">
                                <h3>{med.name}</h3>
                                <span className="med-strength-badge">{med.strength}</span>
                              </div>
                              <p className="med-instruction-text">{med.instruction}</p>
                              {med.note && <span className="med-purpose-note">📌 {med.note}</span>}
                            </div>
                            <div className="med-card-actions">
                              <button
                                type="button"
                                className={`btn-taken ${med.isTaken ? 'active' : ''}`}
                                onClick={() => toggleUserMedTaken(med.id)}
                                title={med.isTaken ? 'Bấm để hủy điểm danh' : 'Bấm để xác nhận đã uống'}
                              >
                                <Check size={16} />
                                <span>{med.isTaken ? 'Đã uống' : 'Điểm danh uống'}</span>
                              </button>
                              <div className="med-row-crud-btns">
                                <button
                                  type="button"
                                  className="mini-crud-btn edit"
                                  onClick={() => setMedModal({ open: true, mode: 'edit', data: med })}
                                  title="Chỉnh sửa liều lượng/giờ uống"
                                >
                                  <Edit3 size={14} />
                                </button>
                                <button
                                  type="button"
                                  className="mini-crud-btn delete"
                                  onClick={() => setDeleteDialog({ open: true, type: 'med', item: med })}
                                  title="Xóa thuốc khỏi lịch"
                                >
                                  <Trash2 size={14} />
                                </button>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* OCR / Prescription Sync Section */}
            {medSchedules.length > 0 && (
              <div className="ocr-synced-block">
                <h3 className="sub-section-title">
                  <Stethoscope size={16} /> Thuốc đồng bộ từ đơn thuốc bệnh viện
                </h3>
                <div className="med-items-grid">
                  {medSchedules.map((item) => {
                    const isTaken = takenMeds[item.schedule_id];
                    const dateObj = item.scheduled_at ? new Date(item.scheduled_at) : null;
                    const isValidDate = dateObj && !isNaN(dateObj.getTime());
                    const timeStr = isValidDate
                      ? dateObj.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
                      : (item.timing || '08:00');
                    return (
                      <div key={item.schedule_id} className={`med-schedule-card ${isTaken ? 'is-taken' : ''}`}>
                        <div className="med-card-time">
                          <Clock3 size={16} />
                          <strong>{timeStr}</strong>
                          <span className="med-recurrence">{item.recurrence === 'daily' ? 'Hàng ngày' : 'Một lần'}</span>
                        </div>
                        <div className="med-card-body">
                          <h3>{item.medication_name}</h3>
                          <div className="med-meta">
                            <span>Mã BN: <strong>{item.patient_ref}</strong></span>
                            <span>Nguồn: <em>{item.source === 'prescription_review' ? 'Đơn thuốc OCR' : 'Bệnh nhân tạo'}</em></span>
                          </div>
                        </div>
                        <div className="med-card-actions">
                          <button
                            type="button"
                            className={`btn-taken ${isTaken ? 'active' : ''}`}
                            onClick={() => toggleMedTaken(item.schedule_id)}
                          >
                            <Check size={16} />
                            <span>{isTaken ? 'Đã uống' : 'Điểm danh uống'}</span>
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </section>
        ) : activeViewMode === 'timetable' ? (
          /* VIEW 2: THỜI KHÓA BIỂU DẠNG TUẦN (WEEKLY TIMETABLE GRID) */
          <section className="weekly-timetable-section" aria-label="Thời khóa biểu dạng tuần">
            {/* Timetable Top Header Bar matching user's image */}
            <div className="timetable-control-header">
              <div className="timetable-title-line">
                <Calendar size={18} />
                <h2>THỜI KHÓA BIỂU DẠNG TUẦN</h2>
              </div>

              <div className="timetable-filter-row">
                <div className="timetable-select-group">
                  <select className="timetable-dropdown" defaultValue="sem1" aria-label="Kỳ điều trị">
                    <option value="sem1">Đợt điều trị: Tháng 09/2026 - Ngoại trú</option>
                    <option value="sem2">Đợt điều trị: Tháng 10/2026 - Tái khám</option>
                  </select>
                  <select className="timetable-dropdown" defaultValue="personal" aria-label="Đối tượng hiển thị">
                    <option value="personal">Thời khóa biểu ca khám & Lịch thuốc cá nhân</option>
                    <option value="all">Toàn bộ bác sĩ phụ trách chuyên khoa</option>
                  </select>
                </div>

                <div className="timetable-week-picker">
                  <button type="button" className="week-nav-btn" onClick={handlePrevWeek} title="Tuần trước">
                    <ChevronLeft size={16} />
                  </button>
                  <span className="week-range-text">
                    Tuần [từ {formatDateVietnamese(weekDates[0])} đến {formatDateVietnamese(weekDates[6])}]
                  </span>
                  <button type="button" className="week-nav-btn" onClick={handleNextWeek} title="Tuần sau">
                    <ChevronRight size={16} />
                  </button>
                  <button type="button" className="week-today-btn" onClick={handleCurrentWeek}>
                    Tuần này
                  </button>
                </div>

                <div className="timetable-legends">
                  <span className="legend-item blue"><i /> Ca khám lâm sàng</span>
                  <span className="legend-item purple"><i /> Ca uống thuốc</span>
                  <span className="legend-item red"><i /> Cần ưu tiên</span>
                  <span className="legend-item green"><i /> Đã hoàn tất</span>
                </div>
              </div>
            </div>

            {/* Timetable Grid Matrix */}
            <div className="timetable-grid-wrapper">
              <table className="timetable-grid">
                <thead>
                  <tr>
                    <th className="th-slot-col">Khung Giờ / Ca</th>
                    {weekDates.map((dateStr, idx) => {
                      const isToday = dateStr === TODAY_STR;
                      return (
                        <th key={dateStr} className={`th-day-col ${isToday ? 'is-today' : ''}`}>
                          <div className="day-name">{DAY_NAMES[idx]}</div>
                          <div className="day-date">({formatDateVietnamese(dateStr)})</div>
                          {isToday && <span className="today-indicator">Hôm nay</span>}
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {/* Row 1: Ca Sáng (07:30 - 11:30) */}
                  <tr>
                    <td className="time-slot-label morning-slot">
                      <div className="time-slot-inner">
                        <strong>Ca Sáng</strong>
                        <span>07:30 - 11:30</span>
                        <small>Khám & xét nghiệm</small>
                      </div>
                    </td>
                    {weekDates.map((dateStr) => {
                      const dayShifts = shifts.filter((s) => s.date === dateStr && s.shiftType === 'morning');

                      return (
                        <td key={dateStr} className="timetable-slot-cell">
                          <div className="timetable-cell-inner">
                            {dayShifts.map((shift) => {
                              const isUrgent = shift.status === 'priority' || shift.priority === 'urgent';
                              const isCompleted = shift.status === 'completed';
                              return (
                                <div
                                  key={shift.id}
                                  className={`timetable-event-card shift-card ${isUrgent ? 'urgent' : isCompleted ? 'completed' : 'clinical'}`}
                                  onMouseEnter={(e) => handleShiftMouseEnter(shift, e)}
                                  onMouseLeave={handleShiftMouseLeave}
                                >
                                  <div className="card-top-title">
                                    <strong>{shift.department}</strong>
                                    <span className="card-patient-code">{shift.patientRef}</span>
                                  </div>
                                  <div className="card-patient-name">{shift.patientName}</div>
                                  <div className="card-doctor-line">BS: {shift.doctor.replace('BS. CKII ', '').replace('ThS. BS ', '').replace('BS. CKI ', '')}</div>
                                  <div className="card-room-line">{shift.room}</div>
                                  <div className="card-time-line">
                                    <Clock size={11} />
                                    <span>{shift.timeSlot}</span>
                                  </div>
                                  <div className="card-hover-hint">
                                    <Info size={11} /> <span>Rê chuột xem chi tiết</span>
                                  </div>
                                </div>
                              );
                            })}
                            {dayShifts.length === 0 && (
                              <button
                                type="button"
                                className="timetable-empty-add-btn"
                                onClick={() => setShiftModal({ open: true, mode: 'create', data: { date: dateStr, shiftType: 'morning' } })}
                                title={`Thêm ca khám ngày ${formatDateVietnamese(dateStr)} (Ca Sáng)`}
                              >
                                <Plus size={13} />
                                <span>Thêm ca</span>
                              </button>
                            )}
                          </div>
                        </td>
                      );
                    })}
                  </tr>

                  {/* Row 2: Ca Chiều (13:00 - 17:00) */}
                  <tr>
                    <td className="time-slot-label afternoon-slot">
                      <div className="time-slot-inner">
                        <strong>Ca Chiều</strong>
                        <span>13:00 - 17:00</span>
                        <small>Khám & Chẩn đoán</small>
                      </div>
                    </td>
                    {weekDates.map((dateStr) => {
                      const dayShifts = shifts.filter((s) => s.date === dateStr && s.shiftType === 'afternoon');

                      return (
                        <td key={dateStr} className="timetable-slot-cell">
                          <div className="timetable-cell-inner">
                            {dayShifts.map((shift) => {
                              const isUrgent = shift.status === 'priority' || shift.priority === 'urgent';
                              const isCompleted = shift.status === 'completed';
                              return (
                                <div
                                  key={shift.id}
                                  className={`timetable-event-card shift-card ${isUrgent ? 'urgent' : isCompleted ? 'completed' : 'clinical'}`}
                                  onMouseEnter={(e) => handleShiftMouseEnter(shift, e)}
                                  onMouseLeave={handleShiftMouseLeave}
                                >
                                  <div className="card-top-title">
                                    <strong>{shift.department}</strong>
                                    <span className="card-patient-code">{shift.patientRef}</span>
                                  </div>
                                  <div className="card-patient-name">{shift.patientName}</div>
                                  <div className="card-doctor-line">BS: {shift.doctor.replace('BS. CKII ', '').replace('ThS. BS ', '').replace('BS. CKI ', '')}</div>
                                  <div className="card-room-line">{shift.room}</div>
                                  <div className="card-time-line">
                                    <Clock size={11} />
                                    <span>{shift.timeSlot}</span>
                                  </div>
                                  <div className="card-hover-hint">
                                    <Info size={11} /> <span>Rê chuột xem chi tiết</span>
                                  </div>
                                </div>
                              );
                            })}
                            {dayShifts.length === 0 && (
                              <button
                                type="button"
                                className="timetable-empty-add-btn"
                                onClick={() => setShiftModal({ open: true, mode: 'create', data: { date: dateStr, shiftType: 'afternoon' } })}
                                title={`Thêm ca khám ngày ${formatDateVietnamese(dateStr)} (Ca Chiều)`}
                              >
                                <Plus size={13} />
                                <span>Thêm ca</span>
                              </button>
                            )}
                          </div>
                        </td>
                      );
                    })}
                  </tr>

                  {/* Row 3: Ca Tối & Trực Đêm (17:30 - 21:30) */}
                  <tr>
                    <td className="time-slot-label evening-slot">
                      <div className="time-slot-inner">
                        <strong>Ca Tối & Trực</strong>
                        <span>17:30 - 21:30</span>
                        <small>Cấp cứu & Lưu bệnh</small>
                      </div>
                    </td>
                    {weekDates.map((dateStr) => {
                      const dayShifts = shifts.filter((s) => s.date === dateStr && s.shiftType === 'evening');

                      return (
                        <td key={dateStr} className="timetable-slot-cell">
                          <div className="timetable-cell-inner">
                            {dayShifts.map((shift) => {
                              const isUrgent = shift.status === 'priority' || shift.priority === 'urgent';
                              const isCompleted = shift.status === 'completed';
                              return (
                                <div
                                  key={shift.id}
                                  className={`timetable-event-card shift-card ${isUrgent ? 'urgent' : isCompleted ? 'completed' : 'clinical'}`}
                                  onMouseEnter={(e) => handleShiftMouseEnter(shift, e)}
                                  onMouseLeave={handleShiftMouseLeave}
                                >
                                  <div className="card-top-title">
                                    <strong>{shift.department}</strong>
                                    <span className="card-patient-code">{shift.patientRef}</span>
                                  </div>
                                  <div className="card-patient-name">{shift.patientName}</div>
                                  <div className="card-doctor-line">BS: {shift.doctor.replace('BS. CKII ', '').replace('ThS. BS ', '').replace('BS. CKI ', '')}</div>
                                  <div className="card-room-line">{shift.room}</div>
                                  <div className="card-time-line">
                                    <Clock size={11} />
                                    <span>{shift.timeSlot}</span>
                                  </div>
                                  <div className="card-hover-hint">
                                    <Info size={11} /> <span>Rê chuột xem chi tiết</span>
                                  </div>
                                </div>
                              );
                            })}
                            {dayShifts.length === 0 && (
                              <button
                                type="button"
                                className="timetable-empty-add-btn"
                                onClick={() => setShiftModal({ open: true, mode: 'create', data: { date: dateStr, shiftType: 'evening' } })}
                                title={`Thêm ca khám ngày ${formatDateVietnamese(dateStr)} (Ca Tối & Trực)`}
                              >
                                <Plus size={13} />
                                <span>Thêm ca</span>
                              </button>
                            )}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        ) : (
          /* VIEW 3: DETAILED CARDS VIEW */
          <section className="shifts-list-section" aria-label="Danh sách ca khám">
            {filteredShifts.length === 0 ? (
              <div className="empty-state-box">
                <CalendarDays size={36} />
                <strong>Không tìm thấy ca khám nào phù hợp</strong>
                <p>Thử đổi ngày khám, chọn ca làm việc khác hoặc xóa từ khóa tìm kiếm.</p>
                <button
                  type="button"
                  className="btn-primary-add"
                  style={{ marginTop: 12 }}
                  onClick={() => setShiftModal({ open: true, mode: 'create', data: null })}
                >
                  <Plus size={16} />
                  <span>Tạo ca khám mới cho ngày này</span>
                </button>
              </div>
            ) : (
              <div className="shifts-grid">
                {filteredShifts.map((shift) => {
                  const statusInfo = statusLabels[shift.status] || statusLabels.waiting;
                  return (
                    <article
                      key={shift.id}
                      className={`shift-detail-card ${shift.status === 'priority' ? 'has-priority' : ''}`}
                      onMouseEnter={(e) => handleShiftMouseEnter(shift, e)}
                      onMouseLeave={handleShiftMouseLeave}
                    >
                      {/* Card Header */}
                      <div className="shift-card-header">
                        <div className="shift-timing">
                          <span className="time-badge"><Clock size={14} /> {shift.timeSlot}</span>
                          <span className={`shift-type-tag ${shift.shiftType}`}>{shift.shiftName.split(' ')[1]}</span>
                          <span className="shift-room"><Stethoscope size={14} /> {shift.room}</span>
                        </div>
                        <div className="shift-header-right">
                          <span className={statusInfo.className}>
                            {shift.status === 'in_progress' && <span className="pulse-dot" />}
                            {statusInfo.label}
                          </span>
                          <span className="shift-id-tag">{shift.id}</span>
                          <button
                            type="button"
                            className="btn-mini-edit"
                            onClick={() => setShiftModal({ open: true, mode: 'edit', data: shift })}
                            title="Chỉnh sửa ca khám này"
                          >
                            <Edit3 size={13} /> Sửa
                          </button>
                          <button
                            type="button"
                            className="btn-mini-delete"
                            onClick={() => setDeleteDialog({ open: true, type: 'shift', item: shift })}
                            title="Xóa ca khám này"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </div>

                      {/* Card Patient & Reason */}
                      <div className="shift-card-main">
                        <div className="patient-info-row">
                          <div className="patient-avatar-circle">
                            {shift.patientName.split(' ').map((n) => n[0]).slice(-2).join('')}
                          </div>
                          <div className="patient-text-block">
                            <div className="patient-name-line">
                              <h3>{shift.patientName}</h3>
                              <span className="patient-ref-pill">{shift.patientRef}</span>
                              <span className="patient-demographics">{shift.age} tuổi · {shift.sex}</span>
                            </div>
                            <p className="patient-phone">SĐT liên hệ: {shift.phone}</p>
                          </div>
                        </div>

                        {/* Doctor info */}
                        <div className="doctor-badge-row">
                          <div className="doctor-pill">
                            <UserCheck size={14} />
                            <span>Bác sĩ: <strong>{shift.doctor}</strong> ({shift.department})</span>
                          </div>
                        </div>

                        {/* Purpose & Clinical Diagnosis */}
                        <div className="clinical-purpose-box">
                          <div className="purpose-title">
                            <Activity size={15} />
                            <span>Lý do & Chẩn đoán theo dõi:</span>
                          </div>
                          <p>{shift.purpose}</p>
                        </div>

                        {/* Vital Signs Row */}
                        {shift.vitals && (
                          <div className="vitals-summary-bar">
                            <span className="vitals-label"><HeartPulse size={14} /> Chỉ số gần nhất:</span>
                            <div className="vitals-chips">
                              <span className="vital-chip">Huyết áp: <strong>{shift.vitals.bp}</strong></span>
                              <span className="vital-chip">Nhịp tim: <strong>{shift.vitals.hr}</strong></span>
                              <span className="vital-chip">SpO2: <strong>{shift.vitals.spo2}</strong></span>
                              <span className="vital-chip">Thân nhiệt: <strong>{shift.vitals.temp}</strong></span>
                            </div>
                          </div>
                        )}

                        {/* Preparation & Instructions */}
                        {shift.prepNotes && (
                          <div className="prep-instructions-box">
                            <AlertCircle size={15} />
                            <div>
                              <strong>Hướng dẫn chuẩn bị ca khám:</strong>
                              <p>{shift.prepNotes}</p>
                            </div>
                          </div>
                        )}

                        {/* Current Medications */}
                        {shift.currentMeds?.length > 0 && (
                          <div className="current-meds-row">
                            <span className="meds-title"><Pill size={13} /> Thuốc đang dùng:</span>
                            <div className="meds-pill-list">
                              {shift.currentMeds.map((med, i) => (
                                <span key={i} className="single-med-pill">{med}</span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Card Footer Actions */}
                      <div className="shift-card-footer">
                        <div className="status-action-btns">
                          <span className="action-label">Đổi trạng thái:</span>
                          <button
                            type="button"
                            className={`mini-status-btn ${shift.status === 'in_progress' ? 'active' : ''}`}
                            onClick={() => handleUpdateStatus(shift.id, 'in_progress')}
                            title="Đang khám"
                          >
                            Đang khám
                          </button>
                          <button
                            type="button"
                            className={`mini-status-btn ${shift.status === 'confirmed' ? 'active' : ''}`}
                            onClick={() => handleUpdateStatus(shift.id, 'confirmed')}
                            title="Đã xác nhận"
                          >
                            Xác nhận
                          </button>
                          <button
                            type="button"
                            className={`mini-status-btn ${shift.status === 'completed' ? 'active' : ''}`}
                            onClick={() => handleUpdateStatus(shift.id, 'completed')}
                            title="Hoàn tất ca"
                          >
                            Hoàn tất
                          </button>
                        </div>

                        <div className="card-right-actions">
                          <button
                            type="button"
                            className="btn-consult-ai"
                            onClick={() => onConsultPatient(shift)}
                            title="Mở phòng chat để AI tư vấn hỗ trợ ca khám này"
                          >
                            <MessageSquare size={15} />
                            <span>Tư vấn AI ca này</span>
                          </button>
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </section>
        )}
      </div>

      {/* =========================================================================
          HOVER POPOVER CARD: HIỂN THỊ CHI TIẾT THÔNG TIN KHI RÊ CHUỘT
          ========================================================================= */}
      {hoveredShift && (
        <aside
          className="shift-hover-popover"
          style={{
            position: 'fixed',
            left: Math.min(Math.max(16, hoverPosition.x + (hoverPosition.width ? (hoverPosition.width / 2) - 175 : 0)), window.innerWidth - 380),
            top: hoverPosition.bottom + 320 > window.innerHeight
              ? Math.max(16, hoverPosition.top - 310)
              : hoverPosition.bottom + 8,
          }}
          onMouseEnter={() => setHoveredShift(hoveredShift)}
          onMouseLeave={handleShiftMouseLeave}
        >
          <div className="popover-header">
            <div className="popover-badge-group">
              <span className="popover-tag">{hoveredShift.department || 'Lâm sàng'}</span>
              <span className="popover-ref">{hoveredShift.patientRef}</span>
            </div>
            <span className={`popover-status-badge ${hoveredShift.status}`}>
              {statusLabels[hoveredShift.status]?.label || 'Đang theo dõi'}
            </span>
          </div>

          <div className="popover-main">
            <h4 className="popover-patient-name">{hoveredShift.patientName}</h4>
            {hoveredShift.age && (
              <p className="popover-demographics">
                {hoveredShift.age} tuổi · {hoveredShift.sex} {hoveredShift.phone ? `· SĐT: ${hoveredShift.phone}` : ''}
              </p>
            )}

            <div className="popover-info-line">
              <UserCheck size={14} />
              <span>Bác sĩ: <strong>{hoveredShift.doctor}</strong></span>
            </div>

            <div className="popover-info-line">
              <Clock size={14} />
              <span>Thời gian: <strong>{hoveredShift.timeSlot}</strong> ({hoveredShift.date})</span>
            </div>

            <div className="popover-info-line">
              <Stethoscope size={14} />
              <span>Phòng khám: <strong>{hoveredShift.room}</strong></span>
            </div>

            <div className="popover-purpose-box">
              <strong>Lý do khám / Chỉ dẫn:</strong>
              <p>{hoveredShift.purpose}</p>
            </div>

            {hoveredShift.vitals && (
              <div className="popover-vitals-mini">
                <span>HA: <strong>{hoveredShift.vitals.bp}</strong></span>
                <span>Tim: <strong>{hoveredShift.vitals.hr}</strong></span>
                <span>SpO2: <strong>{hoveredShift.vitals.spo2}</strong></span>
              </div>
            )}

            {hoveredShift.prepNotes && (
              <p className="popover-prep-note">
                <AlertCircle size={12} /> {hoveredShift.prepNotes}
              </p>
            )}
          </div>

          <div className="popover-footer-actions">
            <button
              type="button"
              className="popover-action-btn edit"
              onClick={() => {
                setHoveredShift(null);
                setShiftModal({ open: true, mode: 'edit', data: hoveredShift });
              }}
            >
              <Edit3 size={13} /> Sửa
            </button>
            <button
              type="button"
              className="popover-action-btn delete"
              onClick={() => {
                setHoveredShift(null);
                setDeleteDialog({ open: true, type: 'shift', item: hoveredShift });
              }}
            >
              <Trash2 size={13} /> Xóa
            </button>
            <button
              type="button"
              className="popover-action-btn consult"
              onClick={() => {
                setHoveredShift(null);
                onConsultPatient(hoveredShift);
              }}
            >
              <MessageSquare size={13} /> Tư vấn AI
            </button>
          </div>
        </aside>
      )}

      {/* =========================================================================
          MODAL 1: TẠO MỚI HOẶC CHỈNH SỬA CA KHÁM (SHIFT MODAL)
          ========================================================================= */}
      {shiftModal.open && (
        <div className="schedule-modal-layer">
          <div className="modal-scrim" onClick={() => setShiftModal({ open: false, mode: 'create', data: null })} />
          <div className="modal-window" role="dialog" aria-modal="true">
            <div className="modal-header">
              <div className="modal-title-wrap">
                {shiftModal.mode === 'create' ? <Plus size={18} /> : <Edit3 size={18} />}
                <h2>{shiftModal.mode === 'create' ? 'Thêm Ca Khám Lâm Sàng Mới' : `Chỉnh Sửa Ca Khám (${shiftModal.data?.id})`}</h2>
              </div>
              <button
                type="button"
                className="icon-button"
                onClick={() => setShiftModal({ open: false, mode: 'create', data: null })}
                title="Đóng"
              >
                <X size={18} />
              </button>
            </div>

            <form
              className="modal-form"
              onSubmit={(e) => {
                e.preventDefault();
                const fd = new FormData(e.currentTarget);
                handleSaveShift({
                  patientName: fd.get('patientName'),
                  patientRef: fd.get('patientRef'),
                  age: fd.get('age'),
                  sex: fd.get('sex'),
                  phone: fd.get('phone'),
                  date: fd.get('date'),
                  shiftType: fd.get('shiftType'),
                  timeSlot: fd.get('timeSlot'),
                  doctor: fd.get('doctor'),
                  department: fd.get('department'),
                  room: fd.get('room'),
                  purpose: fd.get('purpose'),
                  bp: fd.get('bp'),
                  hr: fd.get('hr'),
                  spo2: fd.get('spo2'),
                  temp: fd.get('temp'),
                  prepNotes: fd.get('prepNotes'),
                  status: fd.get('status'),
                  priority: fd.get('priority'),
                  currentMeds: fd.get('currentMeds'),
                });
              }}
            >
              <div className="form-section-divider">
                <span>Hành chính & Thông tin bệnh nhân</span>
              </div>

              <div className="form-grid-2">
                <label className="form-field">
                  <span>Họ tên bệnh nhân <span className="req">*</span></span>
                  <input
                    type="text"
                    name="patientName"
                    required
                    defaultValue={shiftModal.data?.patientName || ''}
                    placeholder="Ví dụ: Nguyễn Văn A"
                  />
                </label>
                <label className="form-field">
                  <span>Mã hồ sơ (Patient Ref) <span className="req">*</span></span>
                  <input
                    type="text"
                    name="patientRef"
                    required
                    defaultValue={shiftModal.data?.patientRef || ''}
                    placeholder="Ví dụ: BN-5501"
                  />
                </label>
              </div>

              <div className="form-grid-3">
                <label className="form-field">
                  <span>Tuổi:</span>
                  <input
                    type="number"
                    name="age"
                    min="0"
                    max="120"
                    defaultValue={shiftModal.data?.age ?? 40}
                  />
                </label>
                <label className="form-field">
                  <span>Giới tính:</span>
                  <select name="sex" defaultValue={shiftModal.data?.sex || 'Nam'}>
                    <option value="Nam">Nam</option>
                    <option value="Nữ">Nữ</option>
                    <option value="Khác">Khác</option>
                  </select>
                </label>
                <label className="form-field">
                  <span>Số điện thoại:</span>
                  <input
                    type="tel"
                    name="phone"
                    defaultValue={shiftModal.data?.phone || ''}
                    placeholder="0912..."
                  />
                </label>
              </div>

              <div className="form-section-divider">
                <span>Thời gian khám & Chuyên khoa</span>
              </div>

              <div className="form-grid-3">
                <label className="form-field">
                  <span>Ngày khám:</span>
                  <input
                    type="date"
                    name="date"
                    defaultValue={shiftModal.data?.date || selectedDate}
                  />
                </label>
                <label className="form-field">
                  <span>Chọn Ca:</span>
                  <select name="shiftType" defaultValue={shiftModal.data?.shiftType || 'morning'}>
                    <option value="morning">Ca Sáng (07:30 - 11:30)</option>
                    <option value="afternoon">Ca Chiều (13:00 - 17:00)</option>
                    <option value="evening">Ca Tối & Trực (17:30 - 21:30)</option>
                  </select>
                </label>
                <label className="form-field">
                  <span>Khung giờ:</span>
                  <input
                    type="text"
                    name="timeSlot"
                    defaultValue={shiftModal.data?.timeSlot || '08:30 - 09:00'}
                  />
                </label>
              </div>

              <div className="form-grid-3">
                <label className="form-field">
                  <span>Khoa phòng / Chuyên khoa:</span>
                  <input
                    type="text"
                    name="department"
                    defaultValue={shiftModal.data?.department || 'Nội Tim mạch'}
                  />
                </label>
                <label className="form-field">
                  <span>Bác sĩ phụ trách:</span>
                  <input
                    type="text"
                    name="doctor"
                    defaultValue={shiftModal.data?.doctor || 'BS. CKII Trần Quốc Huy'}
                  />
                </label>
                <label className="form-field">
                  <span>Phòng khám:</span>
                  <input
                    type="text"
                    name="room"
                    defaultValue={shiftModal.data?.room || 'Phòng 204 - Tầng 2'}
                  />
                </label>
              </div>

              <div className="form-section-divider">
                <span>Lý do khám & Chỉ số sinh tồn</span>
              </div>

              <label className="form-field">
                <span>Lý do khám / Chẩn đoán theo dõi <span className="req">*</span></span>
                <textarea
                  name="purpose"
                  rows="2"
                  required
                  defaultValue={shiftModal.data?.purpose || ''}
                  placeholder="Mô tả triệu chứng, lý do tái khám..."
                />
              </label>

              <div className="form-grid-4">
                <label className="form-field">
                  <span>Huyết áp:</span>
                  <input
                    type="text"
                    name="bp"
                    placeholder="Chưa đo (vd: 125/82 mmHg)"
                    defaultValue={shiftModal.data?.vitals?.bp || ''}
                  />
                </label>
                <label className="form-field">
                  <span>Nhịp tim:</span>
                  <input
                    type="text"
                    name="hr"
                    placeholder="Chưa đo (vd: 75 bpm)"
                    defaultValue={shiftModal.data?.vitals?.hr || ''}
                  />
                </label>
                <label className="form-field">
                  <span>SpO2:</span>
                  <input
                    type="text"
                    name="spo2"
                    placeholder="Chưa đo (vd: 98%)"
                    defaultValue={shiftModal.data?.vitals?.spo2 || ''}
                  />
                </label>
                <label className="form-field">
                  <span>Thân nhiệt:</span>
                  <input
                    type="text"
                    name="temp"
                    placeholder="Chưa đo (vd: 36.8°C)"
                    defaultValue={shiftModal.data?.vitals?.temp || ''}
                  />
                </label>
              </div>

              <div className="form-section-divider">
                <span>Phân luồng & Hướng dẫn</span>
              </div>

              <div className="form-grid-2">
                <label className="form-field">
                  <span>Trạng thái:</span>
                  <select name="status" defaultValue={shiftModal.data?.status || 'confirmed'}>
                    <option value="in_progress">Đang khám</option>
                    <option value="confirmed">Đã xác nhận</option>
                    <option value="waiting">Chờ tiếp nhận</option>
                    <option value="priority">Cần ưu tiên</option>
                    <option value="completed">Đã hoàn tất</option>
                  </select>
                </label>
                <label className="form-field">
                  <span>Mức độ ưu tiên:</span>
                  <select name="priority" defaultValue={shiftModal.data?.priority || 'normal'}>
                    <option value="normal">Bình thường</option>
                    <option value="high">Cao</option>
                    <option value="urgent">Khẩn cấp</option>
                  </select>
                </label>
              </div>

              <label className="form-field">
                <span>Thuốc đang dùng (ngăn cách bởi dấu phẩy):</span>
                <input
                  type="text"
                  name="currentMeds"
                  defaultValue={shiftModal.data?.currentMeds?.join(', ') || ''}
                  placeholder="Ví dụ: Amlodipine 5mg, Aspirin 81mg"
                />
              </label>

              <label className="form-field">
                <span>Hướng dẫn chuẩn bị:</span>
                <input
                  type="text"
                  name="prepNotes"
                  defaultValue={shiftModal.data?.prepNotes || 'Nhịn ăn sáng nếu cần lấy máu xét nghiệm.'}
                />
              </label>

              <div className="modal-actions-row">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setShiftModal({ open: false, mode: 'create', data: null })}
                >
                  Hủy
                </button>
                <button type="submit" className="btn-primary">
                  {shiftModal.mode === 'create' ? 'Tạo ca khám' : 'Lưu thay đổi'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* =========================================================================
          MODAL 2: TẠO MỚI HOẶC CHỈNH SỬA CA UỐNG THUỐC (USER MEDICATION MODAL)
          ========================================================================= */}
      {medModal.open && (
        <div className="schedule-modal-layer">
          <div className="modal-scrim" onClick={() => setMedModal({ open: false, mode: 'create', data: null })} />
          <div className="modal-window" role="dialog" aria-modal="true">
            <div className="modal-header">
              <div className="modal-title-wrap">
                <Pill size={18} />
                <h2>{medModal.mode === 'create' ? 'Thêm Lịch Uống Thuốc Cho Bệnh Nhân' : `Chỉnh Sửa Lịch Thuốc (${medModal.data?.name})`}</h2>
              </div>
              <button
                type="button"
                className="icon-button"
                onClick={() => setMedModal({ open: false, mode: 'create', data: null })}
                title="Đóng"
              >
                <X size={18} />
              </button>
            </div>

            <form
              className="modal-form"
              onSubmit={(e) => {
                e.preventDefault();
                const fd = new FormData(e.currentTarget);
                handleSaveMed({
                  name: fd.get('name'),
                  strength: fd.get('strength'),
                  dosage: fd.get('dosage'),
                  timing: fd.get('timing'),
                  slot: fd.get('slot'),
                  instruction: fd.get('instruction'),
                  note: fd.get('note'),
                });
              }}
            >
              <div className="form-grid-2">
                <label className="form-field">
                  <span>Tên thuốc:</span>
                  <input
                    type="text"
                    name="name"
                    required
                    defaultValue={medModal.data?.name || ''}
                    placeholder="Ví dụ: Amlodipine Besylate"
                  />
                </label>
                <label className="form-field">
                  <span>Hàm lượng / Dạng thuốc:</span>
                  <input
                    type="text"
                    name="strength"
                    required
                    defaultValue={medModal.data?.strength || '5mg'}
                    placeholder="Ví dụ: 5mg, 500mg, 1 gói"
                  />
                </label>
              </div>

              <div className="form-grid-3">
                <label className="form-field">
                  <span>Số lượng uống mỗi lần:</span>
                  <input
                    type="text"
                    name="dosage"
                    required
                    defaultValue={medModal.data?.dosage || '1 viên'}
                    placeholder="1 viên, 2 viên..."
                  />
                </label>
                <label className="form-field">
                  <span>Giờ uống:</span>
                  <input
                    type="time"
                    name="timing"
                    required
                    defaultValue={medModal.data?.timing || '08:00'}
                  />
                </label>
                <label className="form-field">
                  <span>Buổi uống trong ngày:</span>
                  <select name="slot" defaultValue={medModal.data?.slot === 'afternoon' ? 'evening' : (medModal.data?.slot || 'morning')}>
                    <option value="morning">🌅 Cữ Sáng (06:00 - 09:00)</option>
                    <option value="noon">☀️ Cữ Trưa (11:30 - 13:00)</option>
                    <option value="evening">🌇 Cữ Tối (17:30 - 19:30)</option>
                    <option value="night">🌙 Cữ Khuya (20:30 - 22:00)</option>
                  </select>
                </label>
              </div>

              <label className="form-field">
                <span>Hướng dẫn uống:</span>
                <input
                  type="text"
                  name="instruction"
                  required
                  defaultValue={medModal.data?.instruction || 'Uống sau bữa ăn 30 phút với nhiều nước'}
                  placeholder="Ví dụ: Uống sau ăn, uống trước ăn..."
                />
              </label>

              <label className="form-field">
                <span>Ghi chú công dụng / Bác sĩ chỉ định:</span>
                <input
                  type="text"
                  name="note"
                  defaultValue={medModal.data?.note || ''}
                  placeholder="Ví dụ: Thuốc huyết áp theo đơn của BS Huy"
                />
              </label>

              <div className="modal-actions-row">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setMedModal({ open: false, mode: 'create', data: null })}
                >
                  Hủy
                </button>
                <button type="submit" className="btn-primary">
                  {medModal.mode === 'create' ? 'Lưu lịch uống thuốc' : 'Cập nhật lịch thuốc'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* =========================================================================
          DIALOG 3: XÁC NHẬN XÓA CA (CONFIRM DELETE DIALOG)
          ========================================================================= */}
      {deleteDialog.open && (
        <div className="schedule-modal-layer">
          <div className="modal-scrim" onClick={() => setDeleteDialog({ open: false, type: 'shift', item: null })} />
          <div className="modal-window delete-window" role="dialog" aria-modal="true">
            <div className="modal-header">
              <div className="modal-title-wrap danger">
                <AlertTriangle size={18} />
                <h2>Xác nhận xóa</h2>
              </div>
              <button
                type="button"
                className="icon-button"
                onClick={() => setDeleteDialog({ open: false, type: 'shift', item: null })}
              >
                <X size={18} />
              </button>
            </div>
            <div className="delete-body">
              <div className="danger-icon-badge">
                <AlertTriangle size={26} />
              </div>
              <p>
                Bạn có chắc chắn muốn xóa{' '}
                <strong>
                  {deleteDialog.type === 'shift'
                    ? `ca khám của bệnh nhân "${deleteDialog.item?.patientName}" (${deleteDialog.item?.id})`
                    : `lịch uống thuốc "${deleteDialog.item?.name}"`}
                </strong>{' '}
                khỏi hệ thống không? Hành động này không thể hoàn tác.
              </p>
            </div>
            <div className="modal-actions-row delete-actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setDeleteDialog({ open: false, type: 'shift', item: null })}
              >
                Hủy bỏ
              </button>
              <button
                type="button"
                className="btn-danger"
                onClick={handleConfirmDelete}
              >
                Xác nhận xóa
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
