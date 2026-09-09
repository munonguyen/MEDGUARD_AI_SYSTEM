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
  Clock,
  Clock3,
  Filter,
  HeartPulse,
  LoaderCircle,
  MessageSquare,
  Pill,
  Plus,
  RefreshCw,
  Search,
  Stethoscope,
  Trash2,
  User,
  UserCheck,
  X,
} from 'lucide-react';

const INITIAL_SHIFTS = [
  {
    id: 'SHIFT-001',
    shiftType: 'morning',
    shiftName: 'Ca Sáng (07:30 - 11:30)',
    timeSlot: '08:00 - 08:30',
    date: new Date().toISOString().slice(0, 10),
    patientRef: 'BN-1082',
    patientName: 'Nguyễn Văn An',
    age: 58,
    sex: 'Nam',
    phone: '0912 345 678',
    doctor: 'BS. CKII Trần Quốc Huy',
    department: 'Nội Tim mạch',
    room: 'Phòng 204 - Tầng 2',
    purpose: 'Tái khám tăng huyết áp & đau thắt ngực gắng sức, theo dõi sau can thiệp stent mạch vành 3 tháng.',
    vitals: { bp: '135/85 mmHg', hr: '76 bpm', spo2: '98%', temp: '36.8°C' },
    prepNotes: 'Yêu cầu nhịn ăn sáng từ 22h tối hôm trước để lấy máu xét nghiệm sinh hóa lúc 07:45. Mang theo sổ đo huyết áp tại nhà.',
    status: 'in_progress',
    priority: 'high',
    currentMeds: ['Amlodipine 5mg', 'Aspirin 81mg', 'Atorvastatin 20mg'],
  },
  {
    id: 'SHIFT-002',
    shiftType: 'morning',
    shiftName: 'Ca Sáng (07:30 - 11:30)',
    timeSlot: '08:45 - 09:15',
    date: new Date().toISOString().slice(0, 10),
    patientRef: 'BN-2041',
    patientName: 'Trần Thị Mai',
    age: 46,
    sex: 'Nữ',
    phone: '0988 765 432',
    doctor: 'ThS. BS Lê Hoàng Mai',
    department: 'Nội tiết - Đái tháo đường',
    room: 'Phòng 108 - Tầng 1',
    purpose: 'Kiểm tra đường huyết định kỳ HbA1c, điều chỉnh liều insulin và metformin, khám biến chứng bàn chân.',
    vitals: { bp: '125/80 mmHg', hr: '82 bpm', spo2: '99%', temp: '36.6°C' },
    prepNotes: 'Không uống thuốc hạ đường huyết vào buổi sáng trước khi lấy máu làm nghiệm pháp. Mang phiếu theo dõi đường huyết 14 ngày.',
    status: 'confirmed',
    priority: 'normal',
    currentMeds: ['Metformin 500mg', 'Gliclazide 30mg'],
  },
  {
    id: 'SHIFT-003',
    shiftType: 'morning',
    shiftName: 'Ca Sáng (07:30 - 11:30)',
    timeSlot: '09:30 - 10:00',
    date: new Date().toISOString().slice(0, 10),
    patientRef: 'BN-3095',
    patientName: 'Vũ Minh Tuấn',
    age: 32,
    sex: 'Nam',
    phone: '0903 112 233',
    doctor: 'BS. CKI Phạm Thanh Tùng',
    department: 'Hô hấp & Dị ứng',
    room: 'Phòng 302 - Tầng 3',
    purpose: 'Cơn hen phế quản tái phát về đêm, ho có đờm trắng dính, đánh giá chức năng thông khí phổi (Hô hấp ký).',
    vitals: { bp: '118/75 mmHg', hr: '94 bpm', spo2: '94%', temp: '37.1°C' },
    prepNotes: 'Ngưng xịt thuốc giãn phế quản tác dụng ngắn trước khi đo hô hấp ký tối thiểu 6 giờ (trừ khi khó thở cấp).',
    status: 'priority',
    priority: 'urgent',
    currentMeds: ['Salbutamol xịt', 'Seretide 25/125'],
  },
  {
    id: 'SHIFT-004',
    shiftType: 'morning',
    shiftName: 'Ca Sáng (07:30 - 11:30)',
    timeSlot: '10:15 - 10:45',
    date: new Date().toISOString().slice(0, 10),
    patientRef: 'BN-4112',
    patientName: 'Đặng Ngọc Lan',
    age: 64,
    sex: 'Nữ',
    phone: '0934 556 778',
    doctor: 'BS. CKII Trần Quốc Huy',
    department: 'Nội Tim mạch',
    room: 'Phòng 204 - Tầng 2',
    purpose: 'Theo dõi rung nhĩ kịch phát và dùng thuốc chống đông kháng vitamin K (Warfarin), kiểm tra chỉ số INR.',
    vitals: { bp: '130/82 mmHg', hr: '88 bpm (loạn nhịp)', spo2: '97%', temp: '36.7°C' },
    prepNotes: 'Mang theo kết quả xét nghiệm INR gần nhất và danh sách thực phẩm, thảo dược đã dùng trong tuần.',
    status: 'waiting',
    priority: 'high',
    currentMeds: ['Warfarin 2mg', 'Bisoprolol 2.5mg'],
  },
  {
    id: 'SHIFT-005',
    shiftType: 'afternoon',
    shiftName: 'Ca Chiều (13:00 - 17:00)',
    timeSlot: '13:30 - 14:00',
    date: new Date().toISOString().slice(0, 10),
    patientRef: 'BN-5231',
    patientName: 'Hoàng Quốc Bảo',
    age: 51,
    sex: 'Nam',
    phone: '0918 889 900',
    doctor: 'ThS. BS Đỗ Thu Hằng',
    department: 'Tiêu hóa - Gan mật',
    room: 'Phòng 215 - Tầng 2',
    purpose: 'Tái khám viêm loét dạ dày tá tràng Hp (+), theo dõi sau phác đồ điều trị 14 ngày, nội soi kiểm tra.',
    vitals: { bp: '122/78 mmHg', hr: '74 bpm', spo2: '99%', temp: '36.5°C' },
    prepNotes: 'Nhịn ăn uống hoàn toàn từ 07h00 sáng để thực hiện nội soi gây mê đường tiêu hóa lúc 13h45.',
    status: 'confirmed',
    priority: 'normal',
    currentMeds: ['Esomeprazole 40mg', 'Amoxicillin 1g', 'Clarithromycin 500mg'],
  },
  {
    id: 'SHIFT-006',
    shiftType: 'afternoon',
    shiftName: 'Ca Chiều (13:00 - 17:00)',
    timeSlot: '14:30 - 15:00',
    date: new Date().toISOString().slice(0, 10),
    patientRef: 'BN-6120',
    patientName: 'Lê Thùy Dương',
    age: 29,
    sex: 'Nữ',
    phone: '0977 445 566',
    doctor: 'BS. CKI Phạm Thanh Tùng',
    department: 'Hô hấp & Dị ứng',
    room: 'Phòng 302 - Tầng 3',
    purpose: 'Dị ứng thức ăn nghi ngờ hải sản, phát ban mề đay diện rộng, tư vấn test lẩy da (Skin prick test).',
    vitals: { bp: '115/70 mmHg', hr: '80 bpm', spo2: '99%', temp: '36.9°C' },
    prepNotes: 'Ngưng dùng thuốc kháng histamin (Cetirizine/Loratadine) ít nhất 5 ngày trước khi thực hiện test da.',
    status: 'waiting',
    priority: 'normal',
    currentMeds: ['Fexofenadine 180mg'],
  },
  {
    id: 'SHIFT-007',
    shiftType: 'afternoon',
    shiftName: 'Ca Chiều (13:00 - 17:00)',
    timeSlot: '15:30 - 16:00',
    date: new Date().toISOString().slice(0, 10),
    patientRef: 'BN-7004',
    patientName: 'Phạm Đức Long',
    age: 70,
    sex: 'Nam',
    phone: '0922 667 788',
    doctor: 'BS. CKII Trần Quốc Huy',
    department: 'Nội Tim mạch',
    room: 'Phòng 204 - Tầng 2',
    purpose: 'Suy tim mạn NYHA II, siêu âm tim Doppler màu kiểm tra phân suất tống máu EF và chức năng van tim.',
    vitals: { bp: '110/68 mmHg', hr: '70 bpm', spo2: '96%', temp: '36.6°C' },
    prepNotes: 'Đo và ghi lại lượng nước uống cùng thể tích nước tiểu trong 24 giờ trước ngày khám.',
    status: 'confirmed',
    priority: 'high',
    currentMeds: ['Furosemide 40mg', 'Enalapril 5mg', 'Spironolactone 25mg'],
  },
  {
    id: 'SHIFT-008',
    shiftType: 'evening',
    shiftName: 'Ca Tối & Trực Đêm (17:30 - 21:30)',
    timeSlot: '18:00 - 18:30',
    date: new Date().toISOString().slice(0, 10),
    patientRef: 'BN-8109',
    patientName: 'Ngô Thanh Hằng',
    age: 38,
    sex: 'Nữ',
    phone: '0908 990 011',
    doctor: 'BS. Trực Cấp cứu & Nội tổng hợp',
    department: 'Khám ngoài giờ & Cấp cứu',
    room: 'Phòng Khám Đa khoa P.101',
    purpose: 'Sốt cao 39.2°C kéo dài ngày thứ 3, đau đầu dữ dội sau hốc mắt, đau nhức cơ khớp, nghi sốt xuất huyết Dengue.',
    vitals: { bp: '105/70 mmHg', hr: '102 bpm', spo2: '98%', temp: '39.2°C' },
    prepNotes: 'Ưu tiên lấy máu test nhanh NS1 Ag Dengue và tổng phân tích tế bào máu ngoại vi khẩn cấp.',
    status: 'priority',
    priority: 'urgent',
    currentMeds: ['Paracetamol 500mg (dùng hạ sốt)'],
  },
  {
    id: 'SHIFT-009',
    shiftType: 'evening',
    shiftName: 'Ca Tối & Trực Đêm (17:30 - 21:30)',
    timeSlot: '19:15 - 19:45',
    date: new Date().toISOString().slice(0, 10),
    patientRef: 'BN-9032',
    patientName: 'Bùi Quốc Hưng',
    age: 42,
    sex: 'Nam',
    phone: '0938 123 789',
    doctor: 'BS. Trực Cấp cứu & Nội tổng hợp',
    department: 'Khám ngoài giờ & Cấp cứu',
    room: 'Phòng Khám Đa khoa P.101',
    purpose: 'Tư vấn phơi nhiễm nghề nghiệp, kiểm tra huyết áp đột ngột tăng 165/100 tại nơi làm việc.',
    vitals: { bp: '165/100 mmHg', hr: '90 bpm', spo2: '98%', temp: '37.0°C' },
    prepNotes: 'Nghỉ ngơi tại chỗ 15 phút trước khi đo lại huyết áp 2 tay. Làm điện tâm đồ tại giường.',
    status: 'waiting',
    priority: 'high',
    currentMeds: [],
  },
];

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

export function SchedulePage({ api, onBackToChat, onConsultPatient }) {
  const [shifts, setShifts] = useState(() => {
    try {
      const saved = localStorage.getItem('medguard.shifts.data');
      return saved ? JSON.parse(saved) : INITIAL_SHIFTS;
    } catch {
      return INITIAL_SHIFTS;
    }
  });

  const [selectedDate, setSelectedDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [selectedShiftFilter, setSelectedShiftFilter] = useState('all');
  const [selectedStatusFilter, setSelectedStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [medSchedules, setMedSchedules] = useState([]);
  const [loadingMeds, setLoadingMeds] = useState(false);
  const [newShiftModalOpen, setNewShiftModalOpen] = useState(false);
  const [takenMeds, setTakenMeds] = useState({});

  // Sync shifts to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('medguard.shifts.data', JSON.stringify(shifts));
    } catch {
      // ignore
    }
  }, [shifts]);

  // Load medication schedules from API
  const loadMedicationSchedules = async () => {
    setLoadingMeds(true);
    try {
      const res = await api.request('/v1/medication-schedules');
      setMedSchedules(res.schedules || []);
    } catch (err) {
      console.warn('Could not load med schedules:', err);
    } finally {
      setLoadingMeds(false);
    }
  };

  useEffect(() => {
    loadMedicationSchedules();
  }, [api]);

  // Status transition handler
  const handleUpdateStatus = (shiftId, newStatus) => {
    setShifts((current) =>
      current.map((item) => (item.id === shiftId ? { ...item, status: newStatus } : item))
    );
  };

  // Filtered shifts
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
      medCount: medSchedules.length,
    };
  }, [shifts, selectedDate, medSchedules]);

  const toggleMedTaken = (id) => {
    setTakenMeds((prev) => ({ ...prev, [id]: !prev[id] }));
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
              <h1>Lịch Khám & Ca Trực Lâm Sàng</h1>
            </div>
            <p>Hệ thống điều phối ca khám, phòng khám chuyên khoa, bác sĩ phụ trách và đồng bộ lịch điều trị</p>
          </div>
        </div>

        <div className="schedule-header-actions">
          <button className="btn-refresh" type="button" onClick={loadMedicationSchedules} title="Làm mới dữ liệu">
            <RefreshCw size={16} className={loadingMeds ? 'spin' : ''} />
            <span>Làm mới</span>
          </button>
          <button className="btn-primary-add" type="button" onClick={() => setNewShiftModalOpen(true)}>
            <Plus size={17} />
            <span>Thêm Ca Khám Mới</span>
          </button>
        </div>
      </header>

      {/* Bento Stats Row */}
      <section className="schedule-bento-grid" aria-label="Thống kê ca khám">
        <div className="bento-card total-card">
          <div className="bento-icon"><Calendar size={22} /></div>
          <div className="bento-data">
            <span className="bento-label">Tổng Ca Hôm Nay</span>
            <strong className="bento-val">{stats.total} <small>ca khám</small></strong>
          </div>
        </div>

        <div className="bento-card morning-card" onClick={() => setSelectedShiftFilter('morning')}>
          <div className="bento-icon"><Clock3 size={22} /></div>
          <div className="bento-data">
            <span className="bento-label">Ca Sáng (07:30 - 11:30)</span>
            <strong className="bento-val">{stats.morningCount} <small>bệnh nhân</small></strong>
          </div>
        </div>

        <div className="bento-card afternoon-card" onClick={() => setSelectedShiftFilter('afternoon')}>
          <div className="bento-icon"><Clock size={22} /></div>
          <div className="bento-data">
            <span className="bento-label">Ca Chiều (13:00 - 17:00)</span>
            <strong className="bento-val">{stats.afternoonCount} <small>bệnh nhân</small></strong>
          </div>
        </div>

        <div className="bento-card evening-card" onClick={() => setSelectedShiftFilter('evening')}>
          <div className="bento-icon"><HeartPulse size={22} /></div>
          <div className="bento-data">
            <span className="bento-label">Ca Tối & Trực Đêm</span>
            <strong className="bento-val">{stats.eveningCount} <small>ca trực</small></strong>
          </div>
        </div>

        <div className="bento-card urgent-card" onClick={() => setSelectedStatusFilter('priority')}>
          <div className="bento-icon"><AlertTriangle size={22} /></div>
          <div className="bento-data">
            <span className="bento-label">Ca Cần Ưu Tiên</span>
            <strong className="bento-val">{stats.priorityCount} <small>khẩn cấp</small></strong>
          </div>
        </div>

        <div className="bento-card med-card" onClick={() => setSelectedShiftFilter('meds')}>
          <div className="bento-icon"><Pill size={22} /></div>
          <div className="bento-data">
            <span className="bento-label">Ca Uống Thuốc</span>
            <strong className="bento-val">{stats.medCount} <small>lịch uống</small></strong>
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
                className={`date-chip ${selectedDate === new Date().toISOString().slice(0, 10) ? 'active' : ''}`}
                onClick={() => setSelectedDate(new Date().toISOString().slice(0, 10))}
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
                onClick={() => setSelectedShiftFilter(tab.id)}
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
        {/* If Medication filter is active */}
        {selectedShiftFilter === 'meds' ? (
          <section className="med-schedules-section">
            <div className="section-header-row">
              <div>
                <h2><Pill size={18} /> Lịch Ca Uống Thuốc Trong Ngày</h2>
                <p>Đồng bộ từ hồ sơ đơn thuốc đã được dược sĩ phê duyệt</p>
              </div>
            </div>

            {loadingMeds && (
              <div className="loading-state-box">
                <LoaderCircle size={24} className="spin" />
                <span>Đang đồng bộ dữ liệu lịch thuốc...</span>
              </div>
            )}

            {!loadingMeds && medSchedules.length === 0 && (
              <div className="empty-state-box">
                <Pill size={32} />
                <strong>Chưa có lịch uống thuốc nào được tạo</strong>
                <p>Bạn có thể chat với MedGuard AI: &quot;#lichthuoc uống amoxicillin 8h và 20h mỗi ngày&quot; hoặc quét đơn thuốc để tạo tự động.</p>
              </div>
            )}

            <div className="med-items-grid">
              {medSchedules.map((item) => {
                const isTaken = takenMeds[item.schedule_id];
                const dateObj = new Date(item.scheduled_at);
                const timeStr = dateObj.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
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
          </section>
        ) : (
          /* Normal Shifts List */
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
                  onClick={() => setNewShiftModalOpen(true)}
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
                    <article key={shift.id} className={`shift-detail-card ${shift.status === 'priority' ? 'has-priority' : ''}`}>
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

      {/* Modal: Thêm Ca Khám Mới */}
      {newShiftModalOpen && (
        <div className="schedule-modal-layer">
          <div className="modal-scrim" onClick={() => setNewShiftModalOpen(false)} />
          <div className="modal-window" role="dialog" aria-modal="true">
            <div className="modal-header">
              <div className="modal-title-wrap">
                <Plus size={18} />
                <h2>Thêm Ca Khám Lâm Sàng Mới</h2>
              </div>
              <button
                type="button"
                className="icon-button"
                onClick={() => setNewShiftModalOpen(false)}
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
                const shiftType = fd.get('shiftType');
                const newShift = {
                  id: `SHIFT-${Math.floor(100 + Math.random() * 900)}`,
                  shiftType: shiftType,
                  shiftName:
                    shiftType === 'morning'
                      ? 'Ca Sáng (07:30 - 11:30)'
                      : shiftType === 'afternoon'
                      ? 'Ca Chiều (13:00 - 17:00)'
                      : 'Ca Tối & Trực Đêm (17:30 - 21:30)',
                  timeSlot: fd.get('timeSlot') || '09:00 - 09:30',
                  date: fd.get('date') || selectedDate,
                  patientRef: (fd.get('patientRef') || 'BN-NEW').toUpperCase(),
                  patientName: fd.get('patientName') || 'Bệnh nhân mới',
                  age: Number(fd.get('age')) || 35,
                  sex: fd.get('sex') || 'Nam',
                  phone: fd.get('phone') || '0900 000 000',
                  doctor: fd.get('doctor') || 'BS. CKII Khám Tổng quát',
                  department: fd.get('department') || 'Nội khoa',
                  room: fd.get('room') || 'Phòng Khám P.102',
                  purpose: fd.get('purpose') || 'Khám và tư vấn sức khỏe tổng quát',
                  vitals: {
                    bp: fd.get('bp') || '120/80 mmHg',
                    hr: fd.get('hr') || '75 bpm',
                    spo2: fd.get('spo2') || '98%',
                    temp: '36.8°C',
                  },
                  prepNotes: fd.get('prepNotes') || 'Mang theo hồ sơ khám cũ nếu có.',
                  status: 'confirmed',
                  priority: 'normal',
                  currentMeds: [],
                };
                setShifts((prev) => [newShift, ...prev]);
                setNewShiftModalOpen(false);
              }}
            >
              <div className="form-grid-2">
                <label className="form-field">
                  <span>Họ tên bệnh nhân:</span>
                  <input type="text" name="patientName" required placeholder="Ví dụ: Nguyễn Văn A" />
                </label>
                <label className="form-field">
                  <span>Mã hồ sơ (Patient Ref):</span>
                  <input type="text" name="patientRef" required placeholder="Ví dụ: BN-5501" />
                </label>
              </div>

              <div className="form-grid-3">
                <label className="form-field">
                  <span>Tuổi:</span>
                  <input type="number" name="age" min="0" max="120" defaultValue="40" />
                </label>
                <label className="form-field">
                  <span>Giới tính:</span>
                  <select name="sex">
                    <option value="Nam">Nam</option>
                    <option value="Nữ">Nữ</option>
                    <option value="Khác">Khác</option>
                  </select>
                </label>
                <label className="form-field">
                  <span>Số điện thoại:</span>
                  <input type="tel" name="phone" placeholder="0912..." />
                </label>
              </div>

              <div className="form-grid-3">
                <label className="form-field">
                  <span>Ngày khám:</span>
                  <input type="date" name="date" defaultValue={selectedDate} />
                </label>
                <label className="form-field">
                  <span>Chọn Ca:</span>
                  <select name="shiftType" defaultValue="morning">
                    <option value="morning">Ca Sáng (07:30 - 11:30)</option>
                    <option value="afternoon">Ca Chiều (13:00 - 17:00)</option>
                    <option value="evening">Ca Tối & Trực (17:30 - 21:30)</option>
                  </select>
                </label>
                <label className="form-field">
                  <span>Khung giờ:</span>
                  <input type="text" name="timeSlot" defaultValue="08:30 - 09:00" />
                </label>
              </div>

              <div className="form-grid-2">
                <label className="form-field">
                  <span>Bác sĩ phụ trách:</span>
                  <input type="text" name="doctor" defaultValue="BS. CKII Trần Quốc Huy" />
                </label>
                <label className="form-field">
                  <span>Khoa phòng:</span>
                  <input type="text" name="room" defaultValue="Phòng 204 - Tầng 2" />
                </label>
              </div>

              <label className="form-field">
                <span>Lý do khám / Chẩn đoán theo dõi:</span>
                <textarea name="purpose" rows="2" required placeholder="Mô tả triệu chứng, lý do tái khám..." />
              </label>

              <div className="form-grid-3">
                <label className="form-field">
                  <span>Huyết áp:</span>
                  <input type="text" name="bp" defaultValue="120/80 mmHg" />
                </label>
                <label className="form-field">
                  <span>Nhịp tim:</span>
                  <input type="text" name="hr" defaultValue="75 bpm" />
                </label>
                <label className="form-field">
                  <span>SpO2:</span>
                  <input type="text" name="spo2" defaultValue="98%" />
                </label>
              </div>

              <label className="form-field">
                <span>Hướng dẫn chuẩn bị:</span>
                <input type="text" name="prepNotes" defaultValue="Nhịn ăn sáng nếu cần lấy máu xét nghiệm." />
              </label>

              <div className="modal-actions-row">
                <button type="button" className="btn-secondary" onClick={() => setNewShiftModalOpen(false)}>
                  Hủy
                </button>
                <button type="submit" className="btn-primary">
                  Tạo ca khám
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
