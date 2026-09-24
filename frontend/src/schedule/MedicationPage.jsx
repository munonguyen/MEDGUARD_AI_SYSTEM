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
  Edit3,
  Filter,
  HeartPulse,
  Info,
  LoaderCircle,
  MessageSquare,
  Pill,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  Trash2,
  X,
} from 'lucide-react';

function getWeekDates(baseDate = new Date()) {
  const current = new Date(baseDate);
  const day = current.getDay();
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

const DEFAULT_MEDS = [
  {
    id: 'MED-001',
    name: 'Amlodipine',
    activeSubstance: 'Amlodipine besylate',
    strength: '5mg',
    dosage: '1 viên',
    slot: 'morning',
    timing: '08:00',
    instruction: 'Uống sau bữa ăn sáng 30 phút, nuốt nguyên viên cùng nước lọc',
    purpose: 'Kiểm soát tăng huyết áp, bảo vệ thành mạch tim mạch',
    warnings: 'Không uống cùng nước bưởi chùm. Theo dõi nếu có phù mắt cá chân nhẹ.',
    doctor: 'BS. CKII Trần Quốc Huy (Tim mạch)',
    colorTheme: 'blue',
  },
  {
    id: 'MED-002',
    name: 'Amoxicillin',
    activeSubstance: 'Amoxicillin trihydrate',
    strength: '500mg',
    dosage: '1 viên',
    slot: 'morning',
    timing: '08:30',
    instruction: 'Uống sau ăn no, uống đủ liều đúng 7 ngày theo đơn chỉ định',
    purpose: 'Kháng sinh điều trị nhiễm khuẩn đường hô hấp trên',
    warnings: 'Tuyệt đối không tự ý ngưng thuốc khi thấy giảm triệu chứng.',
    doctor: 'BS. CKI Nguyễn Minh Tuấn (Tai Mũi Họng)',
    colorTheme: 'teal',
  },
  {
    id: 'MED-003',
    name: 'Metformin',
    activeSubstance: 'Metformin hydrochloride',
    strength: '500mg',
    dosage: '1 viên',
    slot: 'noon',
    timing: '12:30',
    instruction: 'Uống ngay trong hoặc sau bữa ăn trưa để tránh cồn cào dạ dày',
    purpose: 'Kiểm soát đường huyết, tăng nhạy cảm insulin (Đái tháo đường type 2)',
    warnings: 'Tránh uống rượu bia khi đang dùng thuốc.',
    doctor: 'ThS. BS Lê Hoàng Nam (Nội tiết)',
    colorTheme: 'purple',
  },
  {
    id: 'MED-004',
    name: 'Esomeprazole',
    activeSubstance: 'Esomeprazole magnesium',
    strength: '40mg',
    dosage: '1 viên',
    slot: 'evening',
    timing: '18:00',
    instruction: 'Uống trước bữa ăn tối 60 phút, nuốt nguyên viên không nhai nghiền',
    purpose: 'Ức chế tiết acid dạ dày, điều trị trào ngược dạ dày thực quản (GERD)',
    warnings: 'Không bẻ đôi hoặc nhai nát viên thuốc bao tan trong ruột.',
    doctor: 'BS. CKII Đặng Bích Thảo (Tiêu hóa)',
    colorTheme: 'amber',
  },
  {
    id: 'MED-005',
    name: 'Atorvastatin',
    activeSubstance: 'Atorvastatin calcium',
    strength: '20mg',
    dosage: '1 viên',
    slot: 'evening',
    timing: '20:00',
    instruction: 'Uống sau ăn tối, tốt nhất vào một giờ cố định mỗi ngày',
    purpose: 'Hạ cholesterol máu, ổn định mảng xơ vữa động mạch',
    warnings: 'Báo bác sĩ nếu có đau cơ hoặc mệt mỏi bất thường.',
    doctor: 'BS. CKII Trần Quốc Huy (Tim mạch)',
    colorTheme: 'indigo',
  },
  {
    id: 'MED-006',
    name: 'Magnesium B6',
    activeSubstance: 'Magnesi lactat + Pyridoxin HCl',
    strength: '470mg/5mg',
    dosage: '1 viên',
    slot: 'night',
    timing: '21:30',
    instruction: 'Uống trước khi đi ngủ 30 phút cùng nhiều nước',
    purpose: 'Bổ sung magie và vitamin B6, hỗ trợ giảm căng cơ, an thần nhẹ',
    warnings: 'Không uống cùng thời điểm với thuốc bổ sung canxi hoặc sắt.',
    doctor: 'BS. Đơn thuốc bổ trợ',
    colorTheme: 'emerald',
  },
];

const TIME_SLOTS = [
  { id: 'morning', label: 'Cữ Sáng', timeRange: '06:00 - 09:00', icon: '🌅', desc: 'Sau ăn sáng / Trước ăn sáng' },
  { id: 'noon', label: 'Cữ Trưa', timeRange: '11:30 - 13:00', icon: '☀️', desc: 'Sau ăn trưa / Cùng bữa ăn' },
  { id: 'evening', label: 'Cữ Tối', timeRange: '17:30 - 19:30', icon: '🌇', desc: 'Trước ăn tối / Sau ăn tối' },
  { id: 'night', label: 'Cữ Khuya', timeRange: '20:30 - 22:00', icon: '🌙', desc: 'Trước khi đi ngủ' },
];

export function MedicationPage({ api, onBackToChat, onOpenSchedulePage, onConsultMedicine, onNotify }) {
  const [currentBaseDate, setCurrentBaseDate] = useState(new Date());
  const weekDates = useMemo(() => getWeekDates(currentBaseDate), [currentBaseDate]);

  const [meds, setMeds] = useState(() => {
    try {
      const saved = localStorage.getItem('medguard.user_meds.data');
      return saved ? JSON.parse(saved) : DEFAULT_MEDS;
    } catch {
      return DEFAULT_MEDS;
    }
  });

  const [takenMap, setTakenMap] = useState(() => {
    try {
      const saved = localStorage.getItem('medguard.med_taken_records');
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });

  const [viewMode, setViewMode] = useState('timetable'); // 'timetable' | 'tracker'
  const [searchQuery, setSearchQuery] = useState('');
  const [slotFilter, setSlotFilter] = useState('all');

  // Hover Popover
  const [hoveredMed, setHoveredMed] = useState(null);
  const [hoverPosition, setHoverPosition] = useState({ x: 0, y: 0 });

  // Modals
  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState('create'); // 'create' | 'edit'
  const [editingMed, setEditingMed] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  // Form State
  const [form, setForm] = useState({
    name: '',
    activeSubstance: '',
    strength: '',
    dosage: '1 viên',
    slot: 'morning',
    timing: '08:00',
    instruction: '',
    purpose: '',
    warnings: '',
    doctor: '',
  });

  // Sync meds
  useEffect(() => {
    try {
      localStorage.setItem('medguard.user_meds.data', JSON.stringify(meds));
    } catch {
      // ignore
    }
  }, [meds]);

  // Sync taken map
  useEffect(() => {
    try {
      localStorage.setItem('medguard.med_taken_records', JSON.stringify(takenMap));
    } catch {
      // ignore
    }
  }, [takenMap]);

  // Week navigation
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

  // Toggle taken status for a specific date & med
  const toggleTaken = (dateStr, medId, e) => {
    e?.stopPropagation();
    const key = `${dateStr}_${medId}`;
    const nextState = !takenMap[key];
    setTakenMap((prev) => ({ ...prev, [key]: nextState }));
    onNotify?.(nextState ? '✓ Đã điểm danh uống thuốc thành công!' : 'Đã hoàn tác trạng thái uống thuốc.');
  };

  // Hover handlers
  const handleMouseEnter = (med, dateStr, e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const key = `${dateStr}_${med.id}`;
    setHoveredMed({ ...med, checkDate: dateStr, isTaken: !!takenMap[key] });
    setHoverPosition({
      x: rect.left + rect.width / 2,
      y: rect.top,
      bottom: rect.bottom,
    });
  };

  const handleMouseLeave = () => {
    setHoveredMed(null);
  };

  // Open Create Modal
  const openCreateModal = (defaultSlot = 'morning') => {
    setModalMode('create');
    setEditingMed(null);
    setForm({
      name: '',
      activeSubstance: '',
      strength: '500mg',
      dosage: '1 viên',
      slot: defaultSlot,
      timing: defaultSlot === 'morning' ? '08:00' : defaultSlot === 'noon' ? '12:30' : defaultSlot === 'evening' ? '18:00' : '21:00',
      instruction: 'Uống sau bữa ăn 30 phút cùng nước lọc',
      purpose: 'Điều trị theo chỉ định',
      warnings: '',
      doctor: 'BS. Điều trị',
    });
    setModalOpen(true);
  };

  // Open Edit Modal
  const openEditModal = (med) => {
    setModalMode('edit');
    setEditingMed(med);
    setForm({
      name: med.name || '',
      activeSubstance: med.activeSubstance || '',
      strength: med.strength || '',
      dosage: med.dosage || '1 viên',
      slot: med.slot || 'morning',
      timing: med.timing || '08:00',
      instruction: med.instruction || '',
      purpose: med.purpose || '',
      warnings: med.warnings || '',
      doctor: med.doctor || '',
    });
    setModalOpen(true);
    setHoveredMed(null);
  };

  // Save Modal
  const handleSaveModal = (e) => {
    e.preventDefault();
    if (!form.name.trim()) return;

    if (modalMode === 'create') {
      const newMed = {
        id: `MED-${Date.now().toString().slice(-4)}`,
        ...form,
        colorTheme: form.slot === 'morning' ? 'blue' : form.slot === 'noon' ? 'purple' : form.slot === 'evening' ? 'amber' : 'emerald',
      };
      setMeds((prev) => [...prev, newMed]);
      onNotify?.(`Đã thêm cữ thuốc: ${form.name}`);
    } else if (editingMed) {
      setMeds((prev) =>
        prev.map((item) => (item.id === editingMed.id ? { ...item, ...form } : item))
      );
      onNotify?.(`Đã cập nhật thông tin thuốc: ${form.name}`);
    }
    setModalOpen(false);
  };

  // Delete Medication
  const handleDeleteMed = (id) => {
    setMeds((prev) => prev.filter((m) => m.id !== id));
    setDeleteConfirm(null);
    setHoveredMed(null);
    onNotify?.('Đã xóa cữ thuốc khỏi phác đồ.');
  };

  // Load Sample Regimen
  const handleLoadSample = (regimenType) => {
    if (regimenType === 'cardio') {
      setMeds(DEFAULT_MEDS);
      onNotify?.('Đã nạp phác đồ mẫu: Tim mạch & Đái tháo đường');
    } else {
      const respiratory = [
        {
          id: `MED-${Date.now()}-1`,
          name: 'Amoxicillin + Clavulanic',
          activeSubstance: 'Amoxicillin 875mg / Clavulanate 125mg',
          strength: '1000mg',
          dosage: '1 viên',
          slot: 'morning',
          timing: '08:00',
          instruction: 'Uống ngay đầu bữa ăn sáng để tránh kích ứng dạ dày',
          purpose: 'Kháng sinh phổ rộng điều trị nhiễm khuẩn hô hấp',
          warnings: 'Uống đủ 7 ngày liên tục.',
          doctor: 'BS. Hô Hấp',
          colorTheme: 'teal',
        },
        {
          id: `MED-${Date.now()}-2`,
          name: 'Acetylcysteine',
          activeSubstance: 'Acetylcystein 200mg',
          strength: '200mg',
          dosage: '1 gói',
          slot: 'noon',
          timing: '12:30',
          instruction: 'Hòa tan vào 100ml nước đun sôi để nguội, uống sau bữa ăn',
          purpose: 'Long đờm, tiêu chất nhầy đường thở',
          warnings: 'Uống nhiều nước trong ngày.',
          doctor: 'BS. Hô Hấp',
          colorTheme: 'blue',
        },
        {
          id: `MED-${Date.now()}-3`,
          name: 'Cetirizine',
          activeSubstance: 'Cetirizine 10mg',
          strength: '10mg',
          dosage: '1 viên',
          slot: 'night',
          timing: '21:00',
          instruction: 'Uống trước khi đi ngủ 30 phút',
          purpose: 'Kháng histamin chống dị ứng đường hô hấp, giảm ngứa họng ho đêm',
          warnings: 'Có thể gây buồn ngủ nhẹ.',
          doctor: 'BS. Hô Hấp',
          colorTheme: 'purple',
        },
      ];
      setMeds((prev) => [...prev, ...respiratory]);
      onNotify?.('Đã thêm phác đồ mẫu: Nhiễm khuẩn hô hấp & Long đờm');
    }
  };

  // Stats calculation for the selected week
  const weekStats = useMemo(() => {
    let totalDoses = 0;
    let takenDoses = 0;

    weekDates.forEach((dateStr) => {
      meds.forEach((med) => {
        totalDoses += 1;
        if (takenMap[`${dateStr}_${med.id}`]) {
          takenDoses += 1;
        }
      });
    });

    const rate = totalDoses ? Math.round((takenDoses / totalDoses) * 100) : 100;
    return { totalDoses, takenDoses, rate };
  }, [weekDates, meds, takenMap]);

  // Today stats
  const todayStats = useMemo(() => {
    const totalToday = meds.length;
    let takenToday = 0;
    meds.forEach((m) => {
      if (takenMap[`${TODAY_STR}_${m.id}`]) takenToday += 1;
    });
    return {
      totalToday,
      takenToday,
      remainingToday: totalToday - takenToday,
      percent: totalToday ? Math.round((takenToday / totalToday) * 100) : 0,
    };
  }, [meds, takenMap]);

  // Filtered meds for list view
  const filteredMeds = useMemo(() => {
    return meds.filter((item) => {
      const matchSearch =
        item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.activeSubstance?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.purpose?.toLowerCase().includes(searchQuery.toLowerCase());
      const matchSlot = slotFilter === 'all' || item.slot === slotFilter;
      return matchSearch && matchSlot;
    });
  }, [meds, searchQuery, slotFilter]);

  return (
    <div className="medication-page-root">
      {/* Top Header */}
      <header className="med-page-header">
        <div className="med-header-left">
          <button
            type="button"
            className="btn-back-chat"
            onClick={onBackToChat}
            title="Quay lại khung chat"
          >
            <ArrowLeft size={16} />
            <span>Về phòng Chat</span>
          </button>
          <div className="med-title-block">
            <div className="med-badge">
              <Pill size={18} />
              <h1>Lịch Uống Thuốc</h1>
            </div>
            <p>Thời khóa biểu dùng thuốc hàng ngày & nhật ký tuân thủ điều trị</p>
          </div>
        </div>

        <div className="med-header-actions">
          <div className="view-mode-toggle-group">
            <button
              type="button"
              className={`view-mode-btn ${viewMode === 'timetable' ? 'active' : ''}`}
              onClick={() => setViewMode('timetable')}
              title="Xem thời khóa biểu tuần"
            >
              <Calendar size={15} />
              <span>Thời khóa biểu tuần</span>
            </button>
            <button
              type="button"
              className={`view-mode-btn ${viewMode === 'tracker' ? 'active' : ''}`}
              onClick={() => setViewMode('tracker')}
              title="Xem danh sách cữ thuốc"
            >
              <Filter size={15} />
              <span>Danh sách cữ thuốc</span>
            </button>
          </div>

          <button
            type="button"
            className="btn-link-appointments"
            onClick={onOpenSchedulePage}
            title="Chuyển sang Lịch khám"
          >
            <Stethoscope size={16} />
            <span>Xem Lịch khám</span>
          </button>

          <button
            type="button"
            className="btn-primary-add"
            onClick={() => openCreateModal('morning')}
          >
            <Plus size={16} />
            <span>Thêm Thuốc Mới</span>
          </button>
        </div>
      </header>

      {/* Progress & Adherence Bento Stats */}
      <section className="med-stats-bar">
        <div className="med-stat-card primary">
          <div className="stat-icon"><Activity size={20} /></div>
          <div className="stat-info">
            <span className="stat-label">Hôm nay ({formatDateVietnamese(TODAY_STR)})</span>
            <strong className="stat-value">{todayStats.takenToday} / {todayStats.totalToday} liều</strong>
          </div>
          <div className="stat-bar-wrap">
            <div className="stat-bar" style={{ width: `${todayStats.percent}%` }} />
          </div>
        </div>

        <div className="med-stat-card success">
          <div className="stat-icon"><CheckCircle2 size={20} /></div>
          <div className="stat-info">
            <span className="stat-label">Tuân thủ tuần này</span>
            <strong className="stat-value">{weekStats.rate}% <small>({weekStats.takenDoses}/{weekStats.totalDoses} liều)</small></strong>
          </div>
        </div>

        <div className="med-stat-card notice">
          <div className="stat-icon"><Clock size={20} /></div>
          <div className="stat-info">
            <span className="stat-label">Còn lại trong ngày</span>
            <strong className="stat-value">{todayStats.remainingToday} liều cần uống</strong>
          </div>
        </div>

        <div className="med-sample-actions">
          <button
            type="button"
            className="btn-sample-regimen"
            onClick={() => handleLoadSample('cardio')}
            title="Nạp mẫu thuốc Tim mạch & Tiểu đường"
          >
            <Sparkles size={14} />
            <span>Nạp phác đồ mẫu</span>
          </button>
        </div>
      </section>

      {/* MAIN VIEW 1: WEEKLY PILL TIMETABLE */}
      {viewMode === 'timetable' ? (
        <section className="med-timetable-section">
          {/* Week navigation control bar */}
          <div className="timetable-control-header">
            <div className="timetable-title-line">
              <CalendarDays size={18} />
              <h2>THỜI KHÓA BIỂU UỐNG THUỐC DẠNG TUẦN</h2>
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
              <span className="legend-item green"><i /> Đã uống</span>
              <span className="legend-item purple"><i /> Cần uống</span>
              <span className="legend-item blue"><i /> Cữ Sáng / Trưa</span>
              <span className="legend-item amber"><i /> Cữ Tối / Khuya</span>
            </div>
          </div>

          {/* Proper Table Layout */}
          <div className="timetable-grid-wrapper">
            <table className="timetable-grid">
              <thead>
                <tr>
                  <th className="th-slot-col">Cữ Uống / Giờ</th>
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
                {TIME_SLOTS.map((slot) => {
                  const slotMeds = meds.filter((m) => m.slot === slot.id);

                  return (
                    <tr key={slot.id}>
                      <td className="time-slot-cell">
                        <div className="time-slot-inner">
                          <strong>{slot.icon} {slot.label}</strong>
                          <span>{slot.timeRange}</span>
                          <small>{slot.desc}</small>
                          <button
                            type="button"
                            className="btn-quick-add-slot"
                            title={`Thêm thuốc vào ${slot.label}`}
                            onClick={() => openCreateModal(slot.id)}
                          >
                            <Plus size={12} /> Thêm
                          </button>
                        </div>
                      </td>

                      {weekDates.map((dateStr) => {
                        const isToday = dateStr === TODAY_STR;

                        return (
                          <td key={dateStr} className={`timetable-slot-cell ${isToday ? 'cell-today' : ''}`}>
                            <div className="timetable-cell-inner">
                              {slotMeds.length ? (
                                slotMeds.map((med) => {
                                  const key = `${dateStr}_${med.id}`;
                                  const isTaken = !!takenMap[key];

                                  return (
                                    <div
                                      key={med.id}
                                      className={`med-pill-card ${med.colorTheme || 'blue'} ${isTaken ? 'is-taken' : ''}`}
                                      onMouseEnter={(e) => handleMouseEnter(med, dateStr, e)}
                                      onMouseLeave={handleMouseLeave}
                                      onClick={(e) => toggleTaken(dateStr, med.id, e)}
                                      title="Nhấp để chuyển trạng thái Đã uống / Chưa uống"
                                    >
                                      <div className="card-top-title">
                                        <strong>
                                          <Pill size={12} /> {med.name}
                                        </strong>
                                        <span className="card-med-dose">{med.strength}</span>
                                      </div>

                                      <div className="card-time-line">
                                        <Clock size={11} />
                                        <span>{med.timing} ({med.dosage})</span>
                                      </div>

                                      <div className="card-med-instruction">
                                        {med.instruction}
                                      </div>

                                      <div className="card-check-action">
                                        <button
                                          type="button"
                                          className={`pill-check-btn ${isTaken ? 'checked' : ''}`}
                                          onClick={(e) => toggleTaken(dateStr, med.id, e)}
                                        >
                                          {isTaken ? <Check size={12} /> : null}
                                          <span>{isTaken ? 'Đã uống' : 'Uống thuốc'}</span>
                                        </button>
                                      </div>
                                    </div>
                                  );
                                })
                              ) : (
                                <div className="empty-cell-slot">
                                  <span>—</span>
                                </div>
                              )}
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ) : (
        /* MAIN VIEW 2: TRACKER CARD LIST */
        <section className="med-tracker-section">
          <div className="tracker-filter-bar">
            <div className="search-input-wrap">
              <Search size={16} />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Tìm thuốc theo tên, hoạt chất, mục đích..."
                aria-label="Tìm thuốc"
              />
            </div>

            <div className="slot-filter-buttons">
              <button
                type="button"
                className={`filter-slot-btn ${slotFilter === 'all' ? 'active' : ''}`}
                onClick={() => setSlotFilter('all')}
              >
                Tất cả ({meds.length})
              </button>
              {TIME_SLOTS.map((slot) => (
                <button
                  key={slot.id}
                  type="button"
                  className={`filter-slot-btn ${slotFilter === slot.id ? 'active' : ''}`}
                  onClick={() => setSlotFilter(slot.id)}
                >
                  {slot.icon} {slot.label} ({meds.filter((m) => m.slot === slot.id).length})
                </button>
              ))}
            </div>
          </div>

          <div className="med-cards-grid">
            {filteredMeds.map((med) => {
              const key = `${TODAY_STR}_${med.id}`;
              const isTaken = !!takenMap[key];

              return (
                <article key={med.id} className={`med-detail-card ${isTaken ? 'card-taken' : ''}`}>
                  <div className="detail-card-header">
                    <div className="med-main-info">
                      <div className="med-icon-wrap">
                        <Pill size={20} />
                      </div>
                      <div>
                        <h3>{med.name} <span className="strength-badge">{med.strength}</span></h3>
                        <small className="substance-line">{med.activeSubstance}</small>
                      </div>
                    </div>
                    <span className={`slot-tag ${med.slot}`}>
                      {TIME_SLOTS.find((s) => s.id === med.slot)?.label || med.slot}
                    </span>
                  </div>

                  <div className="detail-card-body">
                    <div className="detail-row">
                      <strong>Khung giờ:</strong>
                      <span><Clock size={13} /> {med.timing} ({med.dosage})</span>
                    </div>
                    <div className="detail-row">
                      <strong>Cách dùng:</strong>
                      <span>{med.instruction}</span>
                    </div>
                    {med.purpose && (
                      <div className="detail-row">
                        <strong>Mục đích:</strong>
                        <span>{med.purpose}</span>
                      </div>
                    )}
                    {med.warnings && (
                      <div className="detail-warning-box">
                        <AlertTriangle size={13} />
                        <span>{med.warnings}</span>
                      </div>
                    )}
                  </div>

                  <div className="detail-card-footer">
                    <button
                      type="button"
                      className={`btn-checkin-large ${isTaken ? 'completed' : ''}`}
                      onClick={(e) => toggleTaken(TODAY_STR, med.id, e)}
                    >
                      {isTaken ? <CheckCircle2 size={16} /> : <Check size={16} />}
                      <span>{isTaken ? '✓ Đã uống hôm nay' : 'Điểm danh uống thuốc'}</span>
                    </button>

                    <div className="card-utility-actions">
                      <button
                        type="button"
                        className="btn-icon-util"
                        title="Hỏi AI về thuốc này"
                        onClick={() => {
                          onConsultMedicine?.(med);
                        }}
                      >
                        <MessageSquare size={15} />
                      </button>
                      <button
                        type="button"
                        className="btn-icon-util"
                        title="Chỉnh sửa cữ thuốc"
                        onClick={() => openEditModal(med)}
                      >
                        <Edit3 size={15} />
                      </button>
                      <button
                        type="button"
                        className="btn-icon-util danger"
                        title="Xóa cữ thuốc"
                        onClick={() => setDeleteConfirm(med)}
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      )}

      {/* Floating Hover Popover */}
      {hoveredMed && (
        <div
          className="med-hover-popover"
          style={{
            left: `${hoverPosition.x}px`,
            top: `${hoverPosition.bottom + 8}px`,
          }}
        >
          <div className="popover-header">
            <div>
              <strong>{hoveredMed.name} {hoveredMed.strength}</strong>
              <small>{hoveredMed.activeSubstance}</small>
            </div>
            <span className={`popover-status-badge ${hoveredMed.isTaken ? 'taken' : 'pending'}`}>
              {hoveredMed.isTaken ? '✓ Đã uống' : 'Chưa uống'}
            </span>
          </div>

          <div className="popover-content">
            <p className="popover-instruction"><strong>Hướng dẫn:</strong> {hoveredMed.instruction}</p>
            {hoveredMed.purpose && (
              <p className="popover-purpose"><strong>Tác dụng:</strong> {hoveredMed.purpose}</p>
            )}
            {hoveredMed.warnings && (
              <div className="popover-warning">
                <AlertCircle size={13} />
                <span>{hoveredMed.warnings}</span>
              </div>
            )}
            <p className="popover-doctor"><strong>Bác sĩ:</strong> {hoveredMed.doctor}</p>
          </div>

          <div className="popover-actions">
            <button
              type="button"
              className="popover-btn edit"
              onClick={() => openEditModal(hoveredMed)}
            >
              <Edit3 size={12} /> Sửa
            </button>
            <button
              type="button"
              className="popover-btn ai"
              onClick={() => onConsultMedicine?.(hoveredMed)}
            >
              <MessageSquare size={12} /> Hỏi MedGuard AI
            </button>
          </div>
        </div>
      )}

      {/* Create / Edit Modal */}
      {modalOpen && (
        <div className="modal-backdrop">
          <div className="med-modal-dialog">
            <div className="modal-header">
              <h2>{modalMode === 'create' ? 'Thêm Cữ Thuốc Mới' : 'Chỉnh Sửa Cữ Thuốc'}</h2>
              <button type="button" className="btn-close-modal" onClick={() => setModalOpen(false)}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleSaveModal} className="med-form-body">
              <div className="form-row-2">
                <div className="form-field">
                  <label>Tên thuốc <span className="req">*</span></label>
                  <input
                    type="text"
                    required
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder="VD: Amlodipine, Panadol..."
                  />
                </div>
                <div className="form-field">
                  <label>Hàm lượng (mg/ml) <span className="req">*</span></label>
                  <input
                    type="text"
                    required
                    value={form.strength}
                    onChange={(e) => setForm({ ...form, strength: e.target.value })}
                    placeholder="VD: 5mg, 500mg..."
                  />
                </div>
              </div>

              <div className="form-row-2">
                <div className="form-field">
                  <label>Hoạt chất chính</label>
                  <input
                    type="text"
                    value={form.activeSubstance}
                    onChange={(e) => setForm({ ...form, activeSubstance: e.target.value })}
                    placeholder="VD: Paracetamol, Amlodipine besylate..."
                  />
                </div>
                <div className="form-field">
                  <label>Số lượng mỗi lần uống</label>
                  <input
                    type="text"
                    value={form.dosage}
                    onChange={(e) => setForm({ ...form, dosage: e.target.value })}
                    placeholder="VD: 1 viên, 2 viên, 1 gói..."
                  />
                </div>
              </div>

              <div className="form-row-2">
                <div className="form-field">
                  <label>Cữ uống trong ngày</label>
                  <select
                    value={form.slot}
                    onChange={(e) => {
                      const slot = e.target.value;
                      const timing = slot === 'morning' ? '08:00' : slot === 'noon' ? '12:30' : slot === 'evening' ? '18:00' : '21:00';
                      setForm({ ...form, slot, timing });
                    }}
                  >
                    <option value="morning">🌅 Cữ Sáng (06:00 - 09:00)</option>
                    <option value="noon">☀️ Cữ Trưa (11:30 - 13:00)</option>
                    <option value="evening">🌇 Cữ Tối (17:30 - 19:30)</option>
                    <option value="night">🌙 Cữ Khuya (20:30 - 22:00)</option>
                  </select>
                </div>
                <div className="form-field">
                  <label>Giờ uống cụ thể</label>
                  <input
                    type="time"
                    value={form.timing}
                    onChange={(e) => setForm({ ...form, timing: e.target.value })}
                  />
                </div>
              </div>

              <div className="form-field">
                <label>Cách dùng & Hướng dẫn</label>
                <input
                  type="text"
                  value={form.instruction}
                  onChange={(e) => setForm({ ...form, instruction: e.target.value })}
                  placeholder="VD: Uống sau bữa ăn 30 phút cùng nhiều nước"
                />
              </div>

              <div className="form-field">
                <label>Mục đích điều trị / Bệnh lý</label>
                <input
                  type="text"
                  value={form.purpose}
                  onChange={(e) => setForm({ ...form, purpose: e.target.value })}
                  placeholder="VD: Hạ huyết áp, giảm đau họng, đái tháo đường..."
                />
              </div>

              <div className="form-field">
                <label>Cảnh báo an toàn / Lưu ý</label>
                <input
                  type="text"
                  value={form.warnings}
                  onChange={(e) => setForm({ ...form, warnings: e.target.value })}
                  placeholder="VD: Không uống cùng sữa, tránh rượu bia, dễ buồn ngủ..."
                />
              </div>

              <div className="form-field">
                <label>Bác sĩ kê đơn</label>
                <input
                  type="text"
                  value={form.doctor}
                  onChange={(e) => setForm({ ...form, doctor: e.target.value })}
                  placeholder="VD: BS. CKII Trần Quốc Huy (Khoa Tim mạch)"
                />
              </div>

              <div className="modal-actions">
                <button type="button" className="btn-cancel" onClick={() => setModalOpen(false)}>
                  Hủy
                </button>
                <button type="submit" className="btn-save">
                  {modalMode === 'create' ? 'Tạo Cữ Thuốc' : 'Lưu Thay Đổi'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      {deleteConfirm && (
        <div className="modal-backdrop">
          <div className="delete-dialog-box">
            <AlertTriangle size={36} className="warn-icon" />
            <h3>Xóa cữ thuốc khỏi phác đồ?</h3>
            <p>
              Bạn có chắc chắn muốn xóa thuốc <strong>{deleteConfirm.name} ({deleteConfirm.strength})</strong>?
              Dữ liệu lịch uống sẽ không thể khôi phục.
            </p>
            <div className="delete-actions">
              <button type="button" className="btn-cancel" onClick={() => setDeleteConfirm(null)}>
                Hủy bỏ
              </button>
              <button
                type="button"
                className="btn-confirm-delete"
                onClick={() => handleDeleteMed(deleteConfirm.id)}
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
