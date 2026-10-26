import { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock,
  Droplet,
  Eye,
  FileBadge,
  FileText,
  Flame,
  Heart,
  HeartPulse,
  Info,
  Layers,
  MessageSquare,
  Mic,
  Navigation,
  Pill,
  Plus,
  RefreshCw,
  RotateCcw,
  Scan,
  Send,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  Syringe,
  CalendarCheck,
  Thermometer,
  TrendingDown,
  TrendingUp,
  User,
  Volume2,
  X,
  Zap,
  BarChart2,
  PieChart,
  Lock,
} from 'lucide-react';
import './HealthTwinPage.css';
import {
  QUICK_FEELING_CHIPS,
  normalizeOrgansArray,
  evaluateHolisticHealthInput,
  computeEpisodicHealthAnalytics,
  computePersonalizedHealthSolutions,
  computeHolisticVisualChartSuite,
} from './holisticHealthEngine';
import { DataManagementAuthGate } from '../common/DataManagementAuthGate';

const SCENARIOS = [
  {
    id: 'initial_flu',
    label: 'Khởi phát cúm (Sốt, đau đầu)',
    icon: Flame,
    color: '#f59e0b',
    desc: 'Bệnh nhân bắt đầu cảm cúm, đau đầu, sổ mũi, rát họng',
  },
  {
    id: 'recovered_headache',
    label: 'Hồi phục (Hết đau đầu, sổ mũi)',
    icon: CheckCircle2,
    color: '#10b981',
    desc: 'Triệu chứng thuyên giảm, hết sốt, khuyên ngừng Paracetamol',
  },
  {
    id: 'adr_stomach_nsaid',
    label: 'Tác dụng phụ: Đau dạ dày do thuốc',
    icon: ShieldAlert,
    color: '#ef4444',
    desc: 'Uống thuốc bị đau dạ dày dữ dội, AI ra lệnh dừng cách cũ!',
  },
  {
    id: 'severe_fever_progression',
    label: 'Tiến triển nặng: Sốt cao 39.5°C',
    icon: AlertTriangle,
    color: '#dc2626',
    desc: 'Sốt cao kịch phát, khó thở, báo động đến bệnh viện',
  },
  {
    id: 'healthy_baseline',
    label: 'Thể trạng bình thường (Khỏe mạnh)',
    icon: Sparkles,
    color: '#00e5ff',
    desc: 'Tất cả cơ quan hoạt động tối ưu, không có bệnh lý',
  },
];

const ORGAN_SYSTEMS = [
  { id: 'all', label: 'Tất cả cơ quan (9)', shortLabel: 'Tất cả', count: 9, icon: Activity },
  { id: 'digestive', label: 'Tiêu hóa & Gan mật (2)', shortLabel: 'Tiêu hóa', count: 2, icon: Flame, organIds: ['stomach', 'liver'] },
  { id: 'cardiopulmonary', label: 'Hô hấp & Tuần hoàn (3)', shortLabel: 'Hô hấp', count: 3, icon: HeartPulse, organIds: ['lungs', 'cardiovascular', 'ent'] },
  { id: 'neuromuscular', label: 'Thần kinh & Vận động (4)', shortLabel: 'Thần kinh', count: 4, icon: Zap, organIds: ['head', 'spine_joints', 'kidneys', 'skin'] },
];

const DEFAULT_HEALTH_PROFILE = {
  patient_id: 'demo-patient-001',
  patient_name: 'Bệnh nhân MedGuard',
  age: 34,
  gender: 'Nam',
  active_diagnosis: 'Chưa ghi nhận bệnh lý cấp tính — Thể trạng bình thường',
  overall_health_score: 98,
  health_trend: 'stable',
  vitals: {
    heart_rate_bpm: 72,
    blood_pressure_systolic: 120,
    blood_pressure_diastolic: 80,
    temperature_celsius: 36.8,
    spo2_percent: 99,
    overall_pain_level: 0,
  },
  organs: [
    {
      id: 'head',
      name: 'Head & Brain',
      vietnamese_name: 'Đầu & Thần kinh',
      status: 'normal',
      health_score: 98,
      pain_level: 0,
      inflammation_level: 'none',
      symptoms: [],
      clinical_notes: 'Chức năng bình thường. Chưa ghi nhận triệu chứng bất thường từ người dùng.',
      related_medications: [],
      warning: null,
      is_adverse_reaction: false,
      contraindicated_actions: [],
      coordinates: { x: 50.0, y: 11.0 },
      future_risk: {
        risk_level: 'low',
        risk_title: 'Rủi ro Đau đầu mạn tính do lạm dụng thuốc giảm đau (MOH)',
        timeframe: '1 - 2 năm',
        vaccination_status: 'THẦN KINH: Chưa ghi nhận tổn thương thực thể',
        latent_risk_description: 'Đau đầu hiện tại do đáp ứng sốt virus. Nguy cơ hình thành thói quen phụ thuộc thuốc giảm đau cấp nếu dùng Paracetamol liên tục trên 15 ngày/tháng.',
        potential_progression: 'Đau đầu cấp tính -> Lạm dụng thuốc giảm đau -> Đau đầu dội ngược kháng trị (MOH)',
        preventive_recommendations: [
          'Không uống thuốc giảm đau quá 3-4 ngày liên tục mà không có chỉ định bác sĩ.',
          'Đảm bảo ngủ đủ 7-8 tiếng, hạn chế nhìn màn hình xanh quá 2 giờ liên tục khi đang sốt.',
          'Bổ sung Magie và Vitamin B2 để hỗ trợ ổn định dẫn truyền thần kinh.',
        ],
        screening_tests: [
          'Ghi chép nhật ký cơn đau đầu (Headache Diary)',
          'Khám chuyên khoa thần kinh nếu xuất hiện dấu hiệu cờ đỏ (nôn vọt, cứng gáy)',
        ],
      },
    },
    {
      id: 'ent',
      name: 'Ear, Nose & Throat',
      vietnamese_name: 'Tai Mũi Họng',
      status: 'normal',
      health_score: 98,
      pain_level: 0,
      inflammation_level: 'none',
      symptoms: [],
      clinical_notes: 'Đường thở trên thông thoáng, niêm mạc bình thường.',
      related_medications: [],
      warning: null,
      is_adverse_reaction: false,
      contraindicated_actions: [],
      coordinates: { x: 50.0, y: 18.0 },
      future_risk: {
        risk_level: 'low',
        risk_title: 'Rủi ro Viêm xoang mạn tính & Viêm họng hạt tái diễn',
        timeframe: '1 - 2 năm',
        vaccination_status: 'ĐƯỜNG THỞ TRÊN: Thông thoáng, không phù nề',
        latent_risk_description: 'Niêm mạc cuốn mũi đang xung huyết phù nề. Nếu ứ đọng dịch nhầy kéo dài dễ dẫn đến bội nhiễm vi khuẩn cơ hội tại các xoang cạnh mũi.',
        potential_progression: 'Viêm mũi họng cấp tính -> Tắc lỗ thông xoang -> Viêm xoang sàng/hàm mạn tính hoặc Viêm amiđan hốc mủ',
        preventive_recommendations: [
          'Rửa mũi bằng dung dịch nước muối sinh lý đẳng trương ấm 2-3 lần/ngày.',
          'Súc họng sâu với nước muối hoặc dung dịch Povidone Iodine 1% khi ra ngoài về.',
          'Giữ ấm vùng cổ ngực, uống nhiều nước ấm để làm loãng dịch đờm.',
        ],
        screening_tests: [
          'Nội soi Tai Mũi Họng ống mềm định kỳ nếu triệu chứng kéo dài > 10 ngày',
          'Chụp CT xoang liều thấp khi nghi ngờ viêm xoang tắc nghẽn',
        ],
      },
    },
    {
      id: 'cardiovascular',
      name: 'Cardiovascular',
      vietnamese_name: 'Tim mạch & Tuần hoàn',
      status: 'normal',
      health_score: 95,
      pain_level: 0,
      inflammation_level: 'none',
      symptoms: [],
      clinical_notes: 'Huyết áp 120/80 mmHg, nhịp tim đều 78 bpm, không đau ngực.',
      related_medications: [],
      warning: null,
      is_adverse_reaction: false,
      contraindicated_actions: [],
      coordinates: { x: 52.0, y: 28.5 },
      future_risk: {
        risk_level: 'moderate',
        risk_title: 'Rủi ro Xơ vữa mạch vành & Biến cố Tim mạch (Thang SCORE/Framingham)',
        timeframe: '5 - 10 năm',
        vaccination_status: 'TIÊM PHÒNG CÚM HÀNG NĂM: Cần tiêm nhắc để ngừa biến cố tim mạch',
        latent_risk_description: 'Huyết áp 120-122 mmHg ngưỡng tiền tăng huyết áp. Thói quen ngồi nhiều kết hợp áp lực công việc làm tăng stress oxy hóa thành mạch.',
        potential_progression: 'Rối loạn nội mạc mạch máu -> Lắng đọng mảng xơ vữa thành mạch vành -> Cơn đau thắt ngực & Nhồi máu cơ tim (MACE)',
        preventive_recommendations: [
          'Duy trì huyết áp mục tiêu < 120/80 mmHg, kiểm soát lượng muối ăn < 5g/ngày.',
          'Vận động thể thao nhịp điệu (đi bộ nhanh, bơi lội, đạp xe) tối thiểu 150 phút/tuần.',
          'Tiêm phòng vắc-xin Cúm mùa định kỳ hàng năm (giúp giảm 20-30% nguy cơ biến cố tim mạch).',
        ],
        screening_tests: [
          'Điện tâm đồ (ECG 12 chuyển đạo) & Siêu âm tim Doppler định kỳ hàng năm',
          'Xét nghiệm bộ mỡ máu Lipid panel (Cholesterol toàn phần, LDL-C, HDL-C, Triglyceride)',
        ],
      },
    },
    {
      id: 'lungs',
      name: 'Respiratory & Lungs',
      vietnamese_name: 'Phổi & Hô hấp',
      status: 'normal',
      health_score: 98,
      pain_level: 0,
      inflammation_level: 'none',
      symptoms: [],
      clinical_notes: 'SpO2 99%, phế bào êm, không ran, đường thở dưới thông thoáng.',
      related_medications: [],
      warning: null,
      is_adverse_reaction: false,
      contraindicated_actions: [],
      coordinates: { x: 43.5, y: 28.0 },
      future_risk: {
        risk_level: 'low',
        risk_title: 'Rủi ro Viêm phế quản mạn & Tăng phản ứng phế quản',
        timeframe: '2 - 5 năm',
        vaccination_status: 'VẮC-XIN PHẾ CẦU: Vui lòng khai báo tiền sử tiêm phòng phế cầu',
        latent_risk_description: 'Đường thở trên đang viêm virus. Nếu thường xuyên tiếp xúc khói bụi hoặc thời tiết lạnh mà chưa có kháng thể phế cầu khuẩn sẽ dễ bị viêm phổi thứ phát.',
        potential_progression: 'Nhiễm virus hô hấp tái diễn -> Tổn thương biểu mô lông chuyển -> Viêm phế quản mạn tính & Giảm dung tích sống FEV1',
        preventive_recommendations: [
          'Tiêm phòng vắc-xin ngừa phế cầu khuẩn (Streptococcus pneumoniae) để bảo vệ phế nang.',
          'Đeo khẩu trang chuẩn lọc bụi mịn N95 khi di chuyển ngoài đường phố đô thị.',
          'Tránh hoàn toàn khói thuốc lá thụ động và các chất khí độc hại.',
        ],
        screening_tests: [
          'Đo chức năng hô hấp (Hô hấp ký Spirometry)',
          'Chụp X-quang phổi thẳng định kỳ 1-2 năm/lần',
        ],
      },
    },
    {
      id: 'stomach',
      name: 'Gastrointestinal & Stomach',
      vietnamese_name: 'Dạ dày & Tiêu hoá',
      status: 'normal',
      health_score: 92,
      pain_level: 0,
      inflammation_level: 'none',
      symptoms: [],
      clinical_notes: 'Bụng mềm, không chướng, tiêu hóa bình thường. Cần lưu ý uống thuốc sau ăn.',
      related_medications: [],
      warning: null,
      is_adverse_reaction: false,
      contraindicated_actions: [],
      coordinates: { x: 53.5, y: 36.5 },
      future_risk: {
        risk_level: 'high',
        risk_title: 'Rủi ro Viêm loét dạ dày tá tràng thủng & Biến chứng Ung thư dạ dày',
        timeframe: '1 - 3 năm',
        vaccination_status: 'TẦM SOÁT KHUẨN HP: Chưa kiểm tra vi khuẩn Helicobacter pylori',
        latent_risk_description: 'Dạ dày rất dễ bị tổn thương nếu lạm dụng thuốc kháng viêm giảm đau (NSAID) hoặc nhiễm vi khuẩn HP âm thầm mà không phát hiện sớm.',
        potential_progression: 'Kích ứng niêm mạc cấp -> Ổ loét sâu thành dạ dày xuất huyết/thủng -> Viêm teo & Dị sản ruột -> Nguy cơ Ung thư dạ dày',
        preventive_recommendations: [
          'Tuyệt đối không uống thuốc giảm đau chống viêm khi đói; dừng ngay nếu thấy cồn cào đau thượng vị.',
          'Xét nghiệm test thở hoặc nội soi tầm soát vi khuẩn Helicobacter pylori (HP).',
          'Ăn uống đúng giờ, tránh thói quen ăn đồ quá cay nóng, nhiều muối hoặc thực phẩm muối chua.',
        ],
        screening_tests: [
          'Nội soi thực quản - dạ dày - tá tràng (EGD) có tiền mê',
          'Test hơi thở C13/C14 Urea Breath Test tìm vi khuẩn HP',
        ],
      },
    },
    {
      id: 'liver',
      name: 'Liver & Metabolism',
      vietnamese_name: 'Gan & Chuyển hoá',
      status: 'normal',
      health_score: 96,
      pain_level: 0,
      inflammation_level: 'none',
      symptoms: [],
      clinical_notes: 'Chức năng chuyển hóa ổn định. Chú ý không dùng Paracetamol quá 3000mg/24h.',
      related_medications: [],
      warning: null,
      is_adverse_reaction: false,
      contraindicated_actions: [],
      coordinates: { x: 43.5, y: 35.0 },
      future_risk: {
        risk_level: 'high',
        risk_title: 'Nguy cơ Nhiễm HBV mạn tính, Xơ gan tiến triển & Ung thư gan (HCC)',
        timeframe: '3 - 10 năm',
        vaccination_status: 'CHƯA TIÊM PHÒNG: Chưa tiêm vắc-xin Viêm gan B (Kháng thể Anti-HBs âm tính)',
        latent_risk_description: 'Cơ thể chưa có kháng thể bảo vệ trước virus Viêm gan B (HBV). Nếu phơi nhiễm nguồn lây qua máu, dịch tiết, thủ thuật y tế hoặc tiếp xúc cộng đồng, nguy cơ chuyển thành thể mạn tính chiếm tới 10-15%.',
        potential_progression: 'Nhiễm HBV mạn tính âm thầm -> Viêm hoại tử tế bào gan -> Xơ gan tiến triển (Cirrhosis) -> Ung thư biểu mô tế bào gan (HCC)',
        preventive_recommendations: [
          'Thực hiện tiêm phòng vắc-xin Viêm gan B đủ phác đồ chuẩn 3 mũi (Tháng 0, 1, 6) càng sớm càng tốt.',
          'Xét nghiệm kiểm tra lại hiệu giá kháng thể Anti-HBs sau mũi 3 đạt > 10 mIU/mL để đảm bảo miễn dịch.',
          'Hạn chế tối đa rượu bia, không dùng Paracetamol quá liều (> 3000mg/ngày) để giảm tải giải độc cho tế bào gan.',
        ],
        screening_tests: [
          'Xét nghiệm cặp HBsAg & Anti-HBs kiểm tra tình trạng nhiễm và kháng thể',
          'Định lượng men gan (AST, ALT, GGT) và chức năng gan tổng quát',
          'Siêu âm Doppler gan & Xét nghiệm chỉ dấu ung thư gan Alpha-fetoprotein (AFP) mỗi 6 tháng',
        ],
      },
    },
    {
      id: 'kidneys',
      name: 'Kidneys & Urinary',
      vietnamese_name: 'Thận & Tiết niệu',
      status: 'normal',
      health_score: 98,
      pain_level: 0,
      inflammation_level: 'none',
      symptoms: [],
      clinical_notes: 'Đào thải bình thường, duy trì uống đủ 2 lít nước ấm mỗi ngày.',
      related_medications: [],
      warning: null,
      is_adverse_reaction: false,
      contraindicated_actions: [],
      coordinates: { x: 44.5, y: 40.5 },
      future_risk: {
        risk_level: 'low',
        risk_title: 'Rủi ro Suy giảm mức lọc cầu thận & Bệnh thận do thuốc',
        timeframe: '3 - 5 năm',
        vaccination_status: 'CHỨC NĂNG THẬN: Ổn định, không protein niệu',
        latent_risk_description: 'Thận đóng vai trò đào thải chất chuyển hóa của thuốc. Nguy cơ tổn thương mô kẽ thận nếu dùng thuốc giảm đau liều cao kéo dài hoặc cơ thể thiếu nước.',
        potential_progression: 'Tổn thương tế bào ống thận âm thầm nếu lạm dụng thuốc kéo dài -> Giảm mức lọc cầu thận (eGFR) -> Bệnh thận mạn giai đoạn sớm',
        preventive_recommendations: [
          'Duy trì thói quen uống đủ 2 - 2.5 lít nước ấm mỗi ngày để bảo vệ chức năng bài tiết cầu thận.',
          'Tuyệt đối không tự ý phối hợp nhiều loại thuốc hạ sốt giảm đau cùng lúc mà không có ý kiến bác sĩ.',
        ],
        screening_tests: [
          'Xét nghiệm Creatinine huyết thanh & Ước tính mức lọc cầu thận eGFR',
          'Tổng phân tích nước tiểu 10 thông số định kỳ hàng năm',
        ],
      },
    },
    {
      id: 'spine_joints',
      name: 'Spine & Musculoskeletal',
      vietnamese_name: 'Cơ xương khớp & Cột sống',
      status: 'normal',
      health_score: 98,
      pain_level: 0,
      inflammation_level: 'none',
      symptoms: [],
      clinical_notes: 'Vận động bình thường, không co cứng cơ, không đau mỏi.',
      related_medications: [],
      warning: null,
      is_adverse_reaction: false,
      contraindicated_actions: [],
      coordinates: { x: 50.0, y: 43.5 },
      future_risk: {
        risk_level: 'low',
        risk_title: 'Rủi ro Thoái hóa cột sống cổ - thắt lưng & Co cứng cơ mạn tính',
        timeframe: '3 - 5 năm',
        vaccination_status: 'VẬN ĐỘNG HỌC: Cần cải thiện tư thế công thái học',
        latent_risk_description: 'Triệu chứng mỏi cơ hiện tại do phản ứng viêm với sốt, kết hợp thói quen làm việc văn phòng ngồi nhiều giờ liên tục ít thay đổi tư thế.',
        potential_progression: 'Căng cơ cổ vai gáy và thắt lưng mạn tính -> Giảm chiều cao đĩa đệm -> Thoái hóa cột sống & Thoát vị đĩa đệm sớm',
        preventive_recommendations: [
          'Thực hiện bài tập giãn cơ 5 phút sau mỗi 45-60 phút ngồi làm việc máy tính.',
          'Điều chỉnh ghế và màn hình máy tính theo chuẩn công thái học (Ergonomics).',
          'Bổ sung Canxi và Vitamin D3 qua thực phẩm hoặc tắm nắng buổi sớm.',
        ],
        screening_tests: [
          'Khám chuyên khoa Cơ Xương Khớp & Đánh giá biên độ vận động cột sống',
        ],
      },
    },
    {
      id: 'skin',
      name: 'Skin & Immune System',
      vietnamese_name: 'Da liễu & Hệ miễn dịch',
      status: 'normal',
      health_score: 95,
      pain_level: 0,
      inflammation_level: 'none',
      symptoms: [],
      clinical_notes: 'Da ấm, không phát ban, không nổi mề đay dị ứng thuốc.',
      related_medications: [],
      warning: null,
      is_adverse_reaction: false,
      contraindicated_actions: [],
      coordinates: { x: 32.5, y: 33.5 },
      future_risk: {
        risk_level: 'low',
        risk_title: 'Rủi ro Dị ứng thuốc phản vệ & Lão hóa quang hóa do tia UV',
        timeframe: '2 - 5 năm',
        vaccination_status: 'MIỄN DỊCH HỌC: Đang đáp ứng bảo vệ bình thường',
        latent_risk_description: 'Hệ miễn dịch đang tập trung sản xuất kháng thể chống virus cảm cúm. Cần lưu ý theo dõi các biểu hiện dị ứng nổi mề đay nếu đổi thuốc mới.',
        potential_progression: 'Dị ứng thuốc nhẹ không nhận biết -> Tái sử dụng dẫn đến phản ứng quá mẫn typ I hoặc hội chứng Stevens-Johnson',
        preventive_recommendations: [
          'Thông báo ngay cho bác sĩ nếu từng có tiền sử dị ứng với bất kỳ loại kháng sinh hoặc thuốc giảm đau nào.',
          'Sử dụng kem chống nắng SPF 50+ phổ rộng khi hoạt động ngoài trời để bảo vệ màng tế bào biểu bì.',
        ],
        screening_tests: [
          'Test áp bì hoặc định lượng IgE đặc hiệu nếu có tiền sử dị ứng thuốc nghi ngờ',
        ],
      },
    },
  ],
  active_medications: [],
  discontinued_medications: [],
  contraindicated_regimens: [],
  clinical_directives: [
    'Cung cấp triệu chứng hoặc tiền sử tiêm chủng để AI đánh giá chuyên sâu',
    'Duy trì uống đủ 2-2.5 lít nước ấm mỗi ngày',
    'Chế độ ăn cân đối dinh dưỡng và nghỉ ngơi hợp lý',
  ],
  safe_guardrail_alert: null,
  timeline: [
    {
      id: 't1',
      timestamp: 'Hiện tại',
      phase: 'baseline',
      title: 'Khởi tạo Hồ sơ Sức khoẻ Thực tế',
      trigger_message: 'Hệ thống sẵn sàng tiếp nhận thông tin từ người dùng.',
      health_score: 98,
      status_label: 'Thể trạng bình thường',
      clinical_summary: 'Chưa có thông tin bệnh lý. Bản đồ cơ thể và dự báo rủi ro sẽ chỉ cập nhật dựa trên thông tin thực tế do bạn cung cấp.',
      ai_directive: 'Vui lòng chia sẻ cảm nhận cơ thể, triệu chứng hoặc tiền sử tiêm chủng nếu có bất thường.',
      medications_adjusted: [],
    },
  ],
  last_updated: 'Hiện tại',
};

export function HealthTwinPage({
  api,
  account = null,
  isGuest = false,
  onRequireAuth = null,
  onBackToChat,
  onNavigate,
  onNotify,
}) {
  const [profile, setProfile] = useState(DEFAULT_HEALTH_PROFILE);
  const [loading, setLoading] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [selectedOrganId, setSelectedOrganId] = useState("liver");
  const [selectedSystem, setSelectedSystem] = useState("all");
  const [hoveredOrganId, setHoveredOrganId] = useState(null);
  const [hoveredRadarAxis, setHoveredRadarAxis] = useState(null);
  const [hoveredGaugeId, setHoveredGaugeId] = useState(null);
  const [hoveredSplineIdx, setHoveredSplineIdx] = useState(null);
  const [hoveredBarIdx, setHoveredBarIdx] = useState(null);
  const [hoveredPillarId, setHoveredPillarId] = useState(null);
  const [inputMessage, setInputMessage] = useState("");
  const [activeTab, setActiveTab] = useState("vitals");
  const [sectionFilter, setSectionFilter] = useState("all");
  const [actionNotice, setActionNotice] = useState(null);
  const [modelViewMode, setModelViewMode] = useState("3d_hologram");
  const [isListening, setIsListening] = useState(false);
  const [episodicTimeframe, setEpisodicTimeframe] = useState("DAY");
  const [selectedBatchId, setSelectedBatchId] = useState("all");
  const [completedSolutions, setCompletedSolutions] = useState({});

  const handleResetProfile = async () => {
    try {
      setLoading(true);
      const res = await api.request("/v1/health-twin/reset", { method: "POST" });
      if (res && res.organs) {
        setProfile({
          ...DEFAULT_HEALTH_PROFILE,
          ...res,
          organs: normalizeOrgansArray(res.organs, DEFAULT_HEALTH_PROFILE.organs),
        });
      } else {
        setProfile(DEFAULT_HEALTH_PROFILE);
      }
      try {
        localStorage.removeItem("medguard_health_twin_profile");
      } catch {}
      setActionNotice("Đã đặt lại thể trạng bình thường ban đầu thành công.");
      setTimeout(() => setActionNotice(null), 3500);
    } catch {
      setProfile(DEFAULT_HEALTH_PROFILE);
      try {
        localStorage.removeItem("medguard_health_twin_profile");
      } catch {}
      setActionNotice("Đã đặt lại thể trạng ban đầu.");
      setTimeout(() => setActionNotice(null), 3500);
    } finally {
      setLoading(false);
    }
  };

  const handleVoiceInput = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      onNotify?.("Trình duyệt chưa hỗ trợ nhận diện giọng nói Web Speech.");
      return;
    }
    try {
      const recognition = new SpeechRecognition();
      recognition.lang = "vi-VN";
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.onstart = () => setIsListening(true);
      recognition.onend = () => setIsListening(false);
      recognition.onerror = () => setIsListening(false);
      recognition.onresult = (event) => {
        const text = event.results[0]?.[0]?.transcript;
        if (text) {
          setInputMessage((prev) => (prev ? `${prev} ${text}` : text));
          onNotify?.(`Đã nhận diện: "${text}"`);
        }
      };
      recognition.start();
    } catch {
      setIsListening(false);
    }
  };

  const fetchProfile = async () => {
    try {
      setLoading(true);
      const data = await api.request("/v1/health-twin/profile");
      if (data && data.organs) {
        const normalized = {
          ...DEFAULT_HEALTH_PROFILE,
          ...data,
          organs: normalizeOrgansArray(data.organs, DEFAULT_HEALTH_PROFILE.organs),
        };
        setProfile(normalized);
      }
    } catch {
      try {
        const raw = localStorage.getItem("medguard_health_twin_profile");
        if (raw) {
          const parsed = JSON.parse(raw);
          setProfile((prev) => {
            const base = {
              ...prev,
              ...parsed,
              organs: normalizeOrgansArray(parsed.organs, DEFAULT_HEALTH_PROFILE.organs),
            };
            return parsed.raw_message
              ? evaluateHolisticHealthInput(base, parsed.raw_message, DEFAULT_HEALTH_PROFILE)
              : base;
          });
          return;
        }
      } catch {}
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
    const handleSync = () => fetchProfile();
    const handleUnifiedChatSync = (event) => {
      const detail = event?.detail;
      if (detail?.healthMutation) {
        setProfile((prev) => {
          const base = {
            ...prev,
            ...detail.healthMutation,
            organs: normalizeOrgansArray(detail.healthMutation.organs, prev.organs || DEFAULT_HEALTH_PROFILE.organs),
          };
          return detail.healthMutation.raw_message
            ? evaluateHolisticHealthInput(base, detail.healthMutation.raw_message, DEFAULT_HEALTH_PROFILE)
            : base;
        });
        setActionNotice("Đã tự động đồng bộ tình trạng bệnh & cảm giác vào Đa Biểu Đồ Sức Khoẻ!");
        setTimeout(() => setActionNotice(null), 4500);
      }
    };
    window.addEventListener("medguard:health-twin-updated", handleSync);
    window.addEventListener("medguard:unified-chat-sync", handleUnifiedChatSync);
    return () => {
      window.removeEventListener("medguard:health-twin-updated", handleSync);
      window.removeEventListener("medguard:unified-chat-sync", handleUnifiedChatSync);
    };
  }, []);

  const handleEvaluateProgress = async (textToEvaluate) => {
    const text = (textToEvaluate ?? inputMessage ?? "").trim();
    if (!text) return;
    try {
      setEvaluating(true);
      let nextProfile = null;
      try {
        const res = await api.request("/v1/health-twin/evaluate-symptom-update", {
          method: "POST",
          body: { message: text },
        });
        if (res?.profile) {
          nextProfile = evaluateHolisticHealthInput(res.profile, text, DEFAULT_HEALTH_PROFILE);
        }
      } catch {
        // Fallback to client-side holistic engine
      }
      setProfile((prev) => {
        const computed = nextProfile || evaluateHolisticHealthInput(prev, text, DEFAULT_HEALTH_PROFILE);
        try {
          localStorage.setItem("medguard_health_twin_profile", JSON.stringify(computed));
        } catch {}
        return computed;
      });
      setInputMessage("");
      setActionNotice(`Đã cập nhật tự động: "${text.slice(0, 65)}..." vào toàn bộ Biểu đồ & Giải pháp!`);
      setTimeout(() => setActionNotice(null), 4500);
      onNotify?.("Đã đồng bộ triệu chứng & cảm giác vào hệ thống biểu đồ sức khoẻ.");
    } finally {
      setEvaluating(false);
    }
  };

  const normalizedOrgans = useMemo(
    () => normalizeOrgansArray(profile?.organs, DEFAULT_HEALTH_PROFILE.organs),
    [profile?.organs]
  );

  const activeOrgan = useMemo(() => {
    if (!normalizedOrgans.length) return null;
    const targetId = hoveredOrganId || selectedOrganId;
    return normalizedOrgans.find((o) => o.id === targetId) || normalizedOrgans[0];
  }, [normalizedOrgans, selectedOrganId, hoveredOrganId]);

  const episodicAnalytics = useMemo(
    () => computeEpisodicHealthAnalytics({ ...profile, organs: normalizedOrgans }, episodicTimeframe),
    [profile, normalizedOrgans, episodicTimeframe]
  );

  const personalizedSolutions = useMemo(
    () => computePersonalizedHealthSolutions({ ...profile, organs: normalizedOrgans }),
    [profile, normalizedOrgans]
  );

  const visualChartSuite = useMemo(
    () => computeHolisticVisualChartSuite({ ...profile, organs: normalizedOrgans }, completedSolutions),
    [profile, normalizedOrgans, completedSolutions]
  );

  const getStatusColor = (status, score) => {
    if (status === "adverse_reaction" || status === "critical") return "#e11d48";
    if (status === "inflamed") return "#d97706";
    if (status === "monitoring") return "#2563eb";
    if (score < 60) return "#e11d48";
    if (score < 85) return "#d97706";
    return "#0d9488";
  };

  const getStatusBadgeText = (status) => {
    switch (status) {
      case "adverse_reaction":
        return "PHẢN ỨNG THUỐC (ADR)";
      case "critical":
        return "CẢNH BÁO ĐỎ";
      case "inflamed":
        return "ĐANG VIÊM / ĐAU";
      case "monitoring":
        return "ĐANG THEO DÕI";
      default:
        return "ỔN ĐỊNH";
    }
  };

  // Strict RBAC guard if rendered directly in guest mode
  if (isGuest) {
    return (
      <DataManagementAuthGate
        moduleTitle="Hồ Sơ Cơ Thể & Thống Kê Sức Khoẻ Đa Biểu Đồ"
        moduleType="health"
        onRequireAuth={onRequireAuth}
        onBackToChat={onBackToChat}
      />
    );
  }

  // Compute SVG Dual-Spline coordinates for Section 2 Chart 2A
  const chartSeries = episodicAnalytics.series || [];
  const svgW = 520;
  const svgH = 170;
  const padX = 34;
  const padY = 22;
  const plotW = svgW - padX * 2;
  const plotH = svgH - padY * 2;

  const healthPoints = chartSeries.map((pt, i) => {
    const x = +(padX + (i / Math.max(1, chartSeries.length - 1)) * plotW).toFixed(1);
    const y = +(padY + ((100 - Math.max(20, Math.min(100, pt.healthScore))) / 80) * plotH).toFixed(1);
    return { x, y, val: pt.healthScore, label: pt.label, batchCode: pt.batchCode, batchId: pt.batchId };
  });

  const sleepPoints = chartSeries.map((pt, i) => {
    const x = +(padX + (i / Math.max(1, chartSeries.length - 1)) * plotW).toFixed(1);
    const y = +(padY + ((100 - Math.max(20, Math.min(100, pt.sleepScore))) / 80) * plotH).toFixed(1);
    return { x, y, val: pt.sleepScore };
  });

  const healthPolyline = healthPoints.map((p) => `${p.x},${p.y}`).join(" ");
  const healthAreaPath = healthPoints.length
    ? `M ${healthPoints[0].x},${padY + plotH} L ${healthPoints.map((p) => `${p.x},${p.y}`).join(" L ")} L ${healthPoints[healthPoints.length - 1].x},${padY + plotH} Z`
    : "";
  const sleepPolyline = sleepPoints.map((p) => `${p.x},${p.y}`).join(" ");

  // Temperature line coordinates for Chart 2B
  const tempPoints = chartSeries.map((pt, i) => {
    const x = +(padX + (i / Math.max(1, chartSeries.length - 1)) * plotW).toFixed(1);
    const clampedTemp = Math.max(36.0, Math.min(40.0, pt.temperature || 36.6));
    const y = +(padY + ((40.0 - clampedTemp) / 4.0) * plotH).toFixed(1);
    return { x, y, temp: pt.temperature, pain: pt.painScore, label: pt.label, batchId: pt.batchId };
  });
  const tempPolyline = tempPoints.map((p) => `${p.x},${p.y}`).join(" ");

  const overallScore = profile?.overall_health_score ?? 96;

  // ============================================================================
  // MODULAR RENDERERS FOR INTUITIVE CLINICAL LAYOUT
  // ============================================================================

  // 1. Executive Biometric Vitals Ribbon (5 Vital Signs)
  const renderVitalsRibbon = () => (
    <div className="vitals-sparkline-strip executive-vitals-bar" aria-label="5 Chỉ số Sinh hiệu Lâm sàng">
      <div className="vital-chart-card">
        <div className="vc-top">
          <span>1. Nhịp tim (ECG)</span>
          <strong className="text-rose">{profile?.vitals?.heart_rate_bpm || 78} bpm</strong>
        </div>
        <svg viewBox="0 0 120 32" className="vc-spark-svg" role="img" aria-label="Dải nhịp tim ECG">
          <polyline
            fill="none"
            stroke="#e11d48"
            strokeWidth="2"
            points="0,18 22,18 28,6 34,28 40,12 46,20 72,18 80,5 86,27 92,15 120,18"
          />
        </svg>
      </div>

      <div className="vital-chart-card">
        <div className="vc-top">
          <span>2. Huyết áp</span>
          <strong className="text-blue">{profile?.vitals?.blood_pressure || "120/80"} mmHg</strong>
        </div>
        <div className="vc-dual-bars">
          <div className="vc-bar-line"><span style={{ width: "75%", background: "#2563eb" }} /></div>
          <div className="vc-bar-line"><span style={{ width: "55%", background: "#0d9488" }} /></div>
        </div>
      </div>

      <div className="vital-chart-card">
        <div className="vc-top">
          <span>3. Thân nhiệt</span>
          <strong className="text-amber">
            {profile?.vitals?.temperature_celsius || profile?.vitals?.body_temperature_c || 36.6} °C
          </strong>
        </div>
        <div className="vc-thermometer-track">
          <div
            className="vc-thermometer-fill"
            style={{
              width: `${Math.min(100, Math.max(25, (((profile?.vitals?.temperature_celsius || 36.6) - 36) / 4) * 100))}%`,
            }}
          />
        </div>
      </div>

      <div className="vital-chart-card">
        <div className="vc-top">
          <span>4. Oxy máu SpO2</span>
          <strong className="text-teal">{profile?.vitals?.spo2_percent || 98}%</strong>
        </div>
        <div className="vc-thermometer-track">
          <div
            className="vc-thermometer-fill teal"
            style={{ width: `${profile?.vitals?.spo2_percent || 98}%` }}
          />
        </div>
      </div>

      <div className="vital-chart-card">
        <div className="vc-top">
          <span>5. Thang đau VAS</span>
          <strong className="text-amber">
            {profile?.vitals?.vas_pain_score ?? profile?.vitals?.overall_pain_level ?? 0}/10
          </strong>
        </div>
        <div className="vc-vas-segments">
          {Array.from({ length: 10 }).map((_, idx) => {
            const active = idx < (profile?.vitals?.vas_pain_score ?? 0);
            return (
              <span
                key={idx}
                className={`vas-seg ${active ? "active" : ""}`}
                style={{
                  backgroundColor: active
                    ? idx >= 6
                      ? "#e11d48"
                      : idx >= 3
                      ? "#f59e0b"
                      : "#10b981"
                    : "#e2e8f0",
                }}
              />
            );
          })}
        </div>
      </div>
    </div>
  );

  // 2. Universal Smart Natural Intake Console & Quick Chips
  const renderSmartIntakeConsole = () => (
    <section className="visual-section-card smart-intake-bar-card" aria-label="Khai báo Tự động Bệnh lý & Cảm giác">
      <div className="sec-head-compact">
        <div className="sec-title-inline">
          <Sparkles size={17} className="icon-teal" />
          <h3>Khai Báo Tự Động Bệnh Lý & Cảm Giác Cơ Thể</h3>
        </div>
        <span className="sec-sub-badge">Tự động cập nhật 100% Biểu đồ</span>
      </div>

      <div className="holistic-input-bar-row">
        <input
          type="text"
          className="holistic-symptom-input console-text-input"
          placeholder="Nhập triệu chứng hoặc cảm giác (VD: đau đầu căng thẳng, mất ngủ, đau rát dạ dày, sốt 38.5 độ...)"
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleEvaluateProgress();
          }}
        />
        <button
          type="button"
          className={`holistic-mic-btn ${isListening ? "listening" : ""}`}
          onClick={handleVoiceInput}
          title="Khai báo bằng giọng nói"
        >
          <Mic size={16} />
        </button>
        <button
          type="button"
          className="holistic-submit-btn console-submit-btn"
          disabled={evaluating || !inputMessage.trim()}
          onClick={() => handleEvaluateProgress()}
        >
          <Send size={14} />
          <span>{evaluating ? "Đang xử lý..." : "Đồng bộ ngay"}</span>
        </button>
      </div>

      <div className="holistic-quick-chips-row">
        {QUICK_FEELING_CHIPS.map((chip) => (
          <button
            key={chip.id}
            type="button"
            className="holistic-feeling-chip quick-chip-item"
            disabled={evaluating}
            onClick={() => handleEvaluateProgress(chip.message)}
          >
            <Zap size={12} />
            <span>{chip.label}</span>
          </button>
        ))}
        <button
          type="button"
          className="holistic-feeling-chip quick-chip-item"
          disabled={evaluating}
          onClick={() => handleEvaluateProgress("Tôi chưa tiêm phòng vắc-xin Viêm gan B, cần đánh giá rủi ro gan")}
        >
          <Syringe size={12} />
          <span>Chưa tiêm Viêm gan B</span>
        </button>
      </div>
    </section>
  );

  // 3. 3D Anatomical Body Silhouette Panel
  const render3DAnatomicalModel = () => (
    <section className="body-silhouette-panel" aria-label="Mô hình 3D Giải phẫu Cơ thể">
      <div className="panel-header-bar">
        <div className="header-bar-title">
          <div className="scan-icon-badge">
            <Scan size={15} />
          </div>
          <div className="header-bar-text">
            <h4>Giải Phẫu 3D (9 Cơ Quan)</h4>
          </div>
        </div>
        <div className="view-mode-pills" role="radiogroup" aria-label="Chế độ hiển thị 3D">
          <button
            type="button"
            role="radio"
            aria-checked={modelViewMode === "3d_hologram"}
            className={`mode-pill ${modelViewMode === "3d_hologram" ? "active" : ""}`}
            onClick={() => setModelViewMode("3d_hologram")}
          >
            <Layers size={13} />
            <span>3D Chuẩn</span>
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={modelViewMode === "xray_scan"}
            className={`mode-pill ${modelViewMode === "xray_scan" ? "active" : ""}`}
            onClick={() => setModelViewMode("xray_scan")}
          >
            <Eye size={13} />
            <span>Quét Mô</span>
          </button>
        </div>
      </div>

      {/* Organ System Filter Tabs */}
      <div className="system-filter-bar" role="tablist" aria-label="Lọc nhóm cơ quan giải phẫu">
        {ORGAN_SYSTEMS.map((sys) => {
          const IconComp = sys.icon || Activity;
          const isActive = selectedSystem === sys.id;
          return (
            <button
              key={sys.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              className={`system-tab-btn ${isActive ? "active" : ""}`}
              onClick={() => {
                setSelectedSystem(sys.id);
                if (sys.organIds && sys.organIds.length > 0 && !sys.organIds.includes(selectedOrganId)) {
                  setSelectedOrganId(sys.organIds[0]);
                }
              }}
            >
              <IconComp size={13} className="sys-tab-icon" />
              <span className="sys-tab-label">{sys.shortLabel || sys.label}</span>
              <span className="sys-tab-badge">{sys.count}</span>
            </button>
          );
        })}
      </div>

      <div className="human-canvas-wrapper">
        <div className="clinical-grid-backdrop" />
        <div className={`human-canvas-inner-ratio ${modelViewMode}`}>
          <img
            src="/static/assets/human_anatomical_twin.jpg"
            alt="3D Anatomical Digital Twin Model"
            className="human-3d-model-img"
            onError={(e) => {
              if (!e.currentTarget.dataset.fallbackTried) {
                e.currentTarget.dataset.fallbackTried = "true";
                e.currentTarget.src = "/assets/human_anatomical_twin.jpg";
              }
            }}
          />

          {activeOrgan?.coordinates && (
            <div
              className="organ-focus-indicator"
              style={{
                left: `${activeOrgan.coordinates.x}%`,
                top: `${activeOrgan.coordinates.y}%`,
                "--indicator-color": getStatusColor(activeOrgan.status, activeOrgan.health_score),
              }}
            >
              <div className="focus-concentric-circle" />
            </div>
          )}

          {normalizedOrgans.map((organ) => {
            const isSelected = selectedOrganId === organ.id;
            const isHovered = hoveredOrganId === organ.id;
            const statusColor = getStatusColor(organ.status, organ.health_score);
            const isAlert = organ.status === "adverse_reaction" || organ.status === "critical";
            const isSystemMember =
              selectedSystem === "all" ||
              ORGAN_SYSTEMS.find((s) => s.id === selectedSystem)?.organIds?.includes(organ.id);

            return (
              <div
                key={organ.id}
                className={`clinical-organ-pin ${isSelected ? "selected" : ""} ${isHovered ? "hovered" : ""} ${isAlert ? "is-alert" : ""} ${!isSystemMember ? "dimmed" : ""}`}
                style={{
                  left: `${organ.coordinates?.x ?? 50}%`,
                  top: `${organ.coordinates?.y ?? 50}%`,
                  "--organ-color": statusColor,
                }}
                onMouseEnter={() => setHoveredOrganId(organ.id)}
                onMouseLeave={() => setHoveredOrganId(null)}
                onClick={() => setSelectedOrganId(organ.id)}
                role="button"
                tabIndex={0}
                aria-label={`Cơ quan: ${organ.vietnamese_name}, Trạng thái: ${organ.status}`}
              >
                <span className="pin-pulse-wave" />
                <span className="pin-point-marker">
                  <span className="pin-dot-inner" />
                </span>
                {isHovered && (
                  <span className="pin-tooltip-badge">
                    <span className="tooltip-dot" />
                    <span className="tooltip-text">{organ.vietnamese_name}</span>
                    <span className="tooltip-score">{organ.health_score}%</span>
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="silhouette-footer-legend">
        <div className="legend-item"><span className="legend-dot normal" /> Ổn định (85-100%)</div>
        <div className="legend-item"><span className="legend-dot inflamed" /> Viêm / Theo dõi (60-84%)</div>
        <div className="legend-item"><span className="legend-dot alert" /> Báo động (&lt;60%)</div>
      </div>
    </section>
  );

  // 4. Selected Organ Inspector & Future Risk Gauge
  // 4. Selected Organ Inspector & Future Risk Gauge (Full-Width Executive Dossier)
  const renderOrganInspector = () => {
    if (!activeOrgan) return null;
    return (
      <section className={`organ-inspector-card fullwidth-dossier status-${activeOrgan.status}`} aria-label="Chi tiết cơ quan đang chọn">
        {/* Top Header Row */}
        <div className="inspector-header">
          <div className="organ-title-row">
            <div
              className="organ-icon-circle"
              style={{
                backgroundColor: `${getStatusColor(activeOrgan.status, activeOrgan.health_score)}18`,
                color: getStatusColor(activeOrgan.status, activeOrgan.health_score),
              }}
            >
              <HeartPulse size={20} />
            </div>
            <div>
              <div className="organ-name-badge-line">
                <h3>{activeOrgan.vietnamese_name}</h3>
                <span className={`status-pill ${activeOrgan.status}`}>
                  {getStatusBadgeText(activeOrgan.status)}
                </span>
                <span className="organ-score-badge">
                  Điểm sức khỏe: <strong>{activeOrgan.health_score}/100</strong>
                </span>
              </div>
              <span className="organ-en-name">{activeOrgan.clinical_notes || activeOrgan.name}</span>
            </div>
          </div>

          {/* Quick Clinical Actions Bar */}
          <div className="organ-quick-actions-bar">
            <button
              type="button"
              className="organ-action-btn consult-btn"
              onClick={() => {
                onNavigate?.("chat");
                window.dispatchEvent(
                  new CustomEvent("medguard:navigate", {
                    detail: {
                      view: "chat",
                      message: `Tư vấn AI chuyên sâu về tình trạng cơ quan: ${activeOrgan.vietnamese_name}`,
                    },
                  })
                );
              }}
            >
              <MessageSquare size={13} />
              <span>Tư vấn AI</span>
            </button>
            <button
              type="button"
              className="organ-action-btn declare-btn"
              onClick={() => {
                setInputMessage(`Cập nhật triệu chứng tại ${activeOrgan.vietnamese_name}: `);
                document.querySelector(".console-text-input")?.focus();
              }}
            >
              <Plus size={13} />
              <span>Khai báo thêm</span>
            </button>
            <button
              type="button"
              className="organ-action-btn recover-btn"
              disabled={evaluating || activeOrgan.status === "normal"}
              onClick={() =>
                handleEvaluateProgress(
                  `Triệu chứng tại ${activeOrgan.vietnamese_name} của tôi đã khỏi và ổn định hoàn toàn.`
                )
              }
            >
              <CheckCircle2 size={13} />
              <span>Báo đã khỏi</span>
            </button>
            <button
              type="button"
              className="organ-action-btn nav-btn"
              onClick={() => onNavigate?.("navigation")}
            >
              <Navigation size={13} />
              <span>Chỉ đường CSYT</span>
            </button>
          </div>
        </div>

        {/* 3-Column Diagnostic Dossier Grid */}
        <div className="organ-dossier-grid">
          {/* Col 1: Lâm sàng & Triệu chứng */}
          <div className="dossier-col clinical-status-col">
            <div className="dossier-col-head">
              <Activity size={15} className="text-teal" />
              <h5>Thực Trạng Sinh Lý & Lâm Sàng</h5>
            </div>
            <div className="dossier-content-box">
              <div className="dossier-field">
                <span className="field-lbl">Đánh giá cơ quan:</span>
                <p className="field-val">{activeOrgan.clinical_notes || "Chức năng bình thường, chưa ghi nhận tổn thương."}</p>
              </div>
              <div className="dossier-field">
                <span className="field-lbl">Mức độ đau / viêm:</span>
                <span className="field-val-badge">
                  Đau VAS: {activeOrgan.pain_level || 0}/10 • Viêm: {activeOrgan.inflammation_level === 'none' ? 'Không viêm' : activeOrgan.inflammation_level}
                </span>
              </div>
              {activeOrgan.warning && (
                <div className="dossier-alert-warning">
                  <AlertCircle size={14} />
                  <span>{activeOrgan.warning}</span>
                </div>
              )}
            </div>
          </div>

          {/* Col 2: Dự báo rủi ro 3 - 10 năm */}
          <div className="dossier-col future-risk-col">
            <div className="dossier-col-head">
              <ShieldAlert size={15} className="text-amber" />
              <h5>Tiên Lượng & Dự Báo Rủi Ro (3 - 10 Năm)</h5>
            </div>
            {activeOrgan.future_risk ? (
              <div className="organ-risk-gauge-panel">
                <div className="semi-gauge-col">
                  {(() => {
                    const rLevel = activeOrgan.future_risk.risk_level;
                    const rPct = rLevel === "high" ? 84 : rLevel === "moderate" ? 52 : 22;
                    const rColor = rLevel === "high" ? "#e11d48" : rLevel === "moderate" ? "#d97706" : "#0d9488";
                    const arcLen = Math.round((rPct / 100) * 125.6);
                    return (
                      <svg viewBox="0 0 100 62" className="semi-risk-svg">
                        <path
                          d="M 10 52 A 40 40 0 0 1 90 52"
                          fill="none"
                          stroke="#e2e8f0"
                          strokeWidth="9"
                          strokeLinecap="round"
                        />
                        <path
                          d="M 10 52 A 40 40 0 0 1 90 52"
                          fill="none"
                          stroke={rColor}
                          strokeWidth="9"
                          strokeDasharray={`${arcLen} 130`}
                          strokeLinecap="round"
                        />
                        <text x="50" y="42" textAnchor="middle" className="semi-gauge-pct" fill={rColor}>
                          {rPct}%
                        </text>
                        <text x="50" y="55" textAnchor="middle" className="semi-gauge-lbl">
                          Rủi ro ({activeOrgan.future_risk.timeframe})
                        </text>
                      </svg>
                    );
                  })()}
                </div>

                <div className="risk-concise-info">
                  <span className="risk-vaccine-pill">{activeOrgan.future_risk.vaccination_status}</span>
                  <h5 className="risk-prognosis-title">{activeOrgan.future_risk.risk_title}</h5>
                  <ul className="risk-concise-list">
                    {(activeOrgan.future_risk.preventive_recommendations || []).slice(0, 2).map((rec, i) => (
                      <li key={i}>
                        <CheckCircle2 size={13} className="text-emerald" />
                        <span>{rec}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            ) : (
              <p className="no-risk-txt">Chưa ghi nhận rủi ro tiềm ẩn cho cơ quan này.</p>
            )}
          </div>

          {/* Col 3: Dược lâm sàng & An toàn */}
          <div className="dossier-col pharma-safety-col">
            <div className="dossier-col-head">
              <Pill size={15} className="text-rose" />
              <h5>An Toàn Dược Lý & Trần Giá DAV</h5>
            </div>
            <div className="dossier-content-box">
              <div className="dossier-field">
                <span className="field-lbl">Thuốc liên quan / Chuyển hóa:</span>
                <p className="field-val">
                  {activeOrgan.related_medications?.length > 0
                    ? activeOrgan.related_medications.join(', ')
                    : 'Chưa dùng hoạt chất có gánh nặng chuyển hóa cao.'}
                </p>
              </div>
              <div className="dossier-field">
                <span className="field-lbl">Tương tác & Khuyến cáo:</span>
                <p className="field-val sub-advice">
                  {activeOrgan.id === 'liver'
                    ? 'Tránh lạm dụng Paracetamol > 3000mg/24h. Ưu tiên kiểm tra men gan định kỳ.'
                    : activeOrgan.id === 'stomach'
                    ? 'Không phối hợp đồng thời nhiều thuốc NSAID. Kê đơn PPI đạt chuẩn GPP.'
                    : 'Tuân thủ đúng phác đồ điều trị, đối chiếu giá trần niêm yết Cục Quản Lý Dược.'}
                </p>
              </div>
              <div className="dossier-pharma-badge">
                <ShieldCheck size={14} className="text-emerald" />
                <span>BHYT hỗ trợ 80% • Đạt chuẩn GPP</span>
              </div>
            </div>
          </div>
        </div>
      </section>
    );
  };

  // 5. Bio-Radar 6 Trục & 4 Vòng Sức Khoẻ Thể Trạng
  const renderBioRadarAndGauges = () => (
    <div className="bio-overview-combined-card" aria-label="Biểu đồ Radar và 4 Vòng Thể trạng">
      <div className="sec-head-compact">
        <div className="sec-title-inline">
          <Sparkles size={16} className="icon-teal" />
          <h4>Cân Bằng Sinh Học & Chỉ Số Thể Trạng</h4>
        </div>
        <span className="radar-avg-badge">TB: {visualChartSuite.radarAverage}/100</span>
      </div>

      <div className="bio-radar-and-gauges-row">
        {/* Radar SVG Stage with rich hover effects */}
        <div className="bio-right-radar-card inline-radar-box">
          <svg viewBox="0 0 220 220" className="bio-radar-svg" role="img" aria-label="Biểu đồ Radar 6 chiều sức khoẻ">
            {/* Concentric Hexagonal Rings */}
            {[0.35, 0.68, 1.0].map((scale, sIdx) => {
              const pts = visualChartSuite.radarAxes
                .map((a) => {
                  const rx = +(110 + 72 * scale * Math.cos(a.angle)).toFixed(1);
                  const ry = +(110 + 72 * scale * Math.sin(a.angle)).toFixed(1);
                  return `${rx},${ry}`;
                })
                .join(" ");
              return (
                <polygon
                  key={sIdx}
                  points={pts}
                  fill={sIdx === 2 ? "rgba(241,245,249,0.5)" : "none"}
                  stroke="#cbd5e1"
                  strokeWidth="1"
                  strokeDasharray={sIdx < 2 ? "2 2" : undefined}
                />
              );
            })}

            {/* Radial Spokes with Hover Glow */}
            {visualChartSuite.radarAxes.map((a) => {
              const isHovered = hoveredRadarAxis === a.id;
              return (
                <line
                  key={a.id}
                  x1="110"
                  y1="110"
                  x2={a.outerX}
                  y2={a.outerY}
                  stroke={isHovered ? a.color : "#cbd5e1"}
                  strokeWidth={isHovered ? 2.5 : 1}
                  strokeDasharray={isHovered ? undefined : "2 2"}
                  style={{ transition: "all 0.2s ease" }}
                />
              );
            })}

            {/* Active Polygon with Hover Expansion */}
            <polygon
              points={visualChartSuite.radarPolygonPoints}
              fill={hoveredRadarAxis ? "rgba(13, 148, 136, 0.35)" : "rgba(13, 148, 136, 0.22)"}
              stroke="#0d9488"
              strokeWidth={hoveredRadarAxis ? 3 : 2.5}
              className="bio-radar-polygon"
              style={{ transition: "all 0.25s ease", filter: hoveredRadarAxis ? "drop-shadow(0 0 8px rgba(13,148,136,0.5))" : "none" }}
            />

            {/* Data Vertex Nodes, Labels & Tooltips */}
            {visualChartSuite.radarAxes.map((a) => {
              const isHovered = hoveredRadarAxis === a.id;
              return (
                <g
                  key={a.id}
                  className={`radar-vertex-group ${isHovered ? "hovered" : ""}`}
                  onMouseEnter={() => setHoveredRadarAxis(a.id)}
                  onMouseLeave={() => setHoveredRadarAxis(null)}
                  style={{ cursor: "pointer" }}
                >
                  {/* Invisible enlarged hit target for easy hovering */}
                  <circle cx={a.x} cy={a.y} r="16" fill="transparent" />

                  {isHovered && (
                    <circle
                      cx={a.x}
                      cy={a.y}
                      r="12"
                      fill="none"
                      stroke={a.color}
                      strokeWidth="1.5"
                      className="radar-pulse-ring"
                    />
                  )}

                  <circle
                    cx={a.x}
                    cy={a.y}
                    r={isHovered ? 6.5 : 4}
                    fill={a.color}
                    stroke="#ffffff"
                    strokeWidth={isHovered ? 2.5 : 1.5}
                    style={{
                      filter: isHovered ? `drop-shadow(0 0 8px ${a.color})` : "none",
                      transition: "all 0.2s cubic-bezier(0.16, 1, 0.3, 1)",
                    }}
                  />
                  <text
                    x={a.labelX}
                    y={a.labelY}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    className={`radar-axis-label ${isHovered ? "active" : ""}`}
                    fill={isHovered ? a.color : "#334155"}
                    fontWeight={isHovered ? "800" : "700"}
                  >
                    {a.shortLabel} ({a.value})
                  </text>

                  {/* Interactive Floating Tooltip when hovered */}
                  {isHovered && (
                    <g className="radar-floating-tooltip" style={{ pointerEvents: "none" }}>
                      <rect
                        x={Math.max(6, Math.min(130, a.x - 42))}
                        y={Math.max(4, a.y - 28)}
                        width="84"
                        height="22"
                        rx="6"
                        fill="#0f172a"
                        fillOpacity="0.94"
                        filter="drop-shadow(0 4px 10px rgba(15,23,42,0.3))"
                      />
                      <text
                        x={Math.max(6, Math.min(130, a.x - 42)) + 42}
                        y={Math.max(4, a.y - 28) + 14}
                        textAnchor="middle"
                        fill="#2dd4bf"
                        fontSize="9.5"
                        fontWeight="800"
                      >
                        {a.label}: {a.value}/100
                      </text>
                    </g>
                  )}
                </g>
              );
            })}
          </svg>
        </div>

        {/* 4 Radial Gauges with Interactive Hover Lift and Ring Glow */}
        <div className="bio-radial-gauges-grid vertical-radial-grid">
          {[
            {
              id: "sleep",
              label: "Giấc ngủ & Phục hồi",
              val: profile?.wellbeing?.sleep_quality_score ?? 88,
              unit: "/100",
              color: "#0d9488",
              hint: "Chất lượng ngủ sâu REM đạt 7.5h",
            },
            {
              id: "neuro",
              label: "An thần & Tâm lý",
              val: String(profile?.wellbeing?.stress_level_label || "").includes("Cao") ? 52 : String(profile?.wellbeing?.stress_level_label || "").includes("Trung") ? 74 : 92,
              unit: "%",
              subText: profile?.wellbeing?.stress_level_label || "Thấp (Ổn định)",
              color: "#2563eb",
              hint: "Tâm lý thư thái, chỉ số căng thẳng thấp",
            },
            {
              id: "energy",
              label: "Pin Năng lượng",
              val: profile?.wellbeing?.energy_battery_percent ?? 90,
              unit: "%",
              color: "#d97706",
              hint: "Mức năng lượng tế bào đạt 90%",
            },
            {
              id: "hydration",
              label: "Nước & Điện giải",
              val: profile?.wellbeing?.hydration_balance_percent ?? 92,
              unit: "%",
              color: "#0284c7",
              hint: "Đã nạp 2.2L nước, điện giải cân bằng",
            },
          ].map((g) => {
            const isHovered = hoveredGaugeId === g.id;
            const dash = Math.round((Math.max(10, Math.min(100, g.val)) / 100) * 113);
            return (
              <div
                key={g.id}
                className={`radial-gauge-mini-card ${isHovered ? "hovered" : ""}`}
                onMouseEnter={() => setHoveredGaugeId(g.id)}
                onMouseLeave={() => setHoveredGaugeId(null)}
                title={g.hint}
              >
                <svg viewBox="0 0 44 44" className="radial-gauge-svg">
                  <circle cx="22" cy="22" r="18" fill="none" stroke="#e2e8f0" strokeWidth="4" />
                  <circle
                    cx="22"
                    cy="22"
                    r="18"
                    fill="none"
                    stroke={g.color}
                    strokeWidth={isHovered ? "5" : "4"}
                    strokeDasharray={`${dash} 114`}
                    strokeLinecap="round"
                    transform="rotate(-90 22 22)"
                    style={{
                      filter: isHovered ? `drop-shadow(0 0 6px ${g.color})` : "none",
                      transition: "all 0.25s ease",
                    }}
                  />
                  <text
                    x="22"
                    y="25"
                    textAnchor="middle"
                    className="radial-svg-num"
                    fill={g.color}
                    style={{
                      transform: isHovered ? "scale(1.12)" : "scale(1)",
                      transformOrigin: "22px 22px",
                      transition: "transform 0.2s ease",
                      fontWeight: isHovered ? "900" : "800",
                    }}
                  >
                    {g.val}
                  </text>
                </svg>
                <div className="radial-gauge-info">
                  <span>{g.label}</span>
                  <strong style={{ color: g.color }}>{g.subText || `${g.val}${g.unit}`}</strong>
                  {isHovered && <span className="gauge-hover-hint">{g.hint}</span>}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );

  // 6. Xếp Hạng 9 Hệ Cơ Quan & Tỷ Lệ An Toàn (Bi-directional Hover Synchronization)
  const renderOrganRankingDonutAndBars = () => (
    <div className="organ-ranking-chart-card" aria-label="Xếp hạng 9 cơ quan">
      <div className="sec-head-compact">
        <div className="sec-title-inline">
          <BarChart2 size={16} className="icon-teal" />
          <h4>Xếp Hạng Sức Khoẻ 9 Cơ Quan & Phân Bổ An Toàn</h4>
        </div>
        <span className="sec-sub-badge">Rê chuột để làm nổi bật cơ quan</span>
      </div>

      <div className="organ-ranking-layout">
        <div className="organ-donut-box">
          <svg viewBox="0 0 100 100" className="organ-donut-svg hoverable-donut">
            <circle cx="50" cy="50" r="36" fill="none" stroke="#e2e8f0" strokeWidth="12" />
            <circle
              cx="50"
              cy="50"
              r="36"
              fill="none"
              stroke="#0d9488"
              strokeWidth="12"
              strokeDasharray={`${Math.round((visualChartSuite.organDistribution.normal / 9) * 226)} 226`}
              transform="rotate(-90 50 50)"
              className="donut-active-circle"
            />
            <text x="50" y="48" textAnchor="middle" className="donut-big-num">
              {visualChartSuite.organDistribution.normal}/9
            </text>
            <text x="50" y="61" textAnchor="middle" className="donut-sub-txt">
              Ổn định
            </text>
          </svg>
        </div>

        <div className="organ-bars-list">
          {visualChartSuite.organRanking.map((item) => {
            const isSel = selectedOrganId === item.id;
            const isHovered = hoveredOrganId === item.id;
            return (
              <button
                key={item.id}
                type="button"
                className={`organ-bar-item-btn ${isSel ? "active" : ""} ${isHovered ? "hovered" : ""}`}
                onClick={() => setSelectedOrganId(item.id)}
                onMouseEnter={() => setHoveredOrganId(item.id)}
                onMouseLeave={() => setHoveredOrganId(null)}
              >
                <span className="ob-name">{item.name}</span>
                <div className="ob-track">
                  <div
                    className="ob-fill"
                    style={{
                      width: `${item.score}%`,
                      backgroundColor: item.color,
                      filter: isHovered ? `drop-shadow(0 0 6px ${item.color})` : "none",
                    }}
                  />
                </div>
                <strong className="ob-score" style={{ color: item.color }}>
                  {item.score}%
                </strong>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );

  // 7. Thống Kê Diễn Tiến Theo Đợt (Episodic Multi-Charts with Crosshair & Rich Tooltips)
  const renderEpisodicAnalyticsSuite = () => (
    <section className="visual-section-card episodic-analytics-panel" aria-label="Biểu đồ Thống kê Sức khoẻ Theo Đợt">
      <div className="episodic-panel-header">
        <div className="episodic-title-block">
          <div className="episodic-badge-row">
            <span className="episodic-tag">ĐA BIỂU ĐỒ THEO TỪNG ĐỢT</span>
            <span className={`episodic-delta-pill ${episodicAnalytics.overallDelta >= 0 ? "up" : "down"}`}>
              {episodicAnalytics.overallDelta >= 0 ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
              <span>
                {episodicAnalytics.overallDelta >= 0 ? `+${episodicAnalytics.overallDelta}%` : `${episodicAnalytics.overallDelta}%`} so với Đợt 1
              </span>
            </span>
          </div>
          <h3>Thống Kê Diễn Tiến Theo Đợt ({episodicAnalytics.timeframeLabel})</h3>
        </div>

        <div className="episodic-timeframe-switcher" role="tablist" aria-label="Chọn khung thời gian thống kê">
          {[
            { id: "HOUR", label: "Theo Giờ (24h)" },
            { id: "DAY", label: "Theo Ngày (7 ngày)" },
            { id: "WEEK", label: "Theo Tuần (4 tuần)" },
            { id: "MONTH", label: "Theo Tháng (6 tháng)" },
          ].map((tf) => (
            <button
              key={tf.id}
              type="button"
              role="tab"
              aria-selected={episodicTimeframe === tf.id}
              className={`tf-switch-btn ${episodicTimeframe === tf.id ? "active" : ""}`}
              onClick={() => {
                setEpisodicTimeframe(tf.id);
                setSelectedBatchId("all");
              }}
            >
              {tf.label}
            </button>
          ))}
        </div>
      </div>

      {/* 3 Compact Batch Filter Cards with Visual Progress Bars */}
      <div className="episodic-batches-grid">
        {episodicAnalytics.batches.map((batch) => {
          const isSelected = selectedBatchId === batch.id;
          return (
            <div
              key={batch.id}
              className={`episodic-batch-card ${batch.status} ${isSelected ? "selected" : ""}`}
              onClick={() => setSelectedBatchId(isSelected ? "all" : batch.id)}
              role="button"
              tabIndex={0}
            >
              <div className="batch-card-top">
                <span className="batch-code-badge">{batch.code}</span>
                <span className={`batch-delta-tag ${batch.delta >= 0 ? "pos" : "neg"}`}>
                  {batch.delta >= 0 ? `+${batch.delta}%` : `${batch.delta}%`}
                </span>
              </div>
              <h4 className="batch-card-title">{batch.name}</h4>
              <div className="batch-visual-bars">
                <div className="bv-bar-row">
                  <span>Thể trạng TB</span>
                  <div className="bv-track">
                    <div className="bv-fill teal" style={{ width: `${batch.avgScore}%` }} />
                  </div>
                  <strong>{batch.avgScore}%</strong>
                </div>
                <div className="bv-bar-row">
                  <span>Đau VAS & Nhiệt</span>
                  <div className="bv-track">
                    <div
                      className="bv-fill amber"
                      style={{ width: `${Math.max(8, batch.avgPain * 10)}%` }}
                    />
                  </div>
                  <strong>{batch.avgPain}/10 • {batch.avgTemp}°C</strong>
                </div>
              </div>
              <div className="batch-solution-callout">
                <CheckCircle2 size={13} />
                <span>{batch.solutionSummary}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Dual SVG Chart Grid */}
      <div className="episodic-dual-charts-grid">
        {/* Chart 2A: Biểu Đồ Đường Cong Miền Đôi (Thể trạng & Phục hồi) */}
        <div className="episodic-svg-chart-box">
          <div className="svg-chart-head">
            <div>
              <span className="chart-kicker">BIỂU ĐỒ MIỀN & ĐƯỜNG XU HƯỚNG</span>
              <h4>Diễn Tiến Điểm Sức Khoẻ & Phục Hồi Giấc Ngủ (%)</h4>
            </div>
            <div className="svg-legend-inline">
              <span className="leg-dot teal">● Thể trạng (%)</span>
              <span className="leg-dot blue">● Giấc ngủ (%)</span>
            </div>
          </div>

          <svg viewBox={`0 0 ${svgW} ${svgH}`} className="episodic-spline-svg">
            <defs>
              <linearGradient id="healthAreaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#0d9488" stopOpacity="0.28" />
                <stop offset="100%" stopColor="#0d9488" stopOpacity="0.02" />
              </linearGradient>
            </defs>

            {/* Reference Grid Lines */}
            {[40, 60, 80, 100].map((val) => {
              const y = +(padY + ((100 - val) / 80) * plotH).toFixed(1);
              return (
                <g key={val}>
                  <line x1={padX} y1={y} x2={svgW - padX} y2={y} stroke="#e2e8f0" strokeDasharray="3 3" />
                  <text x={padX - 6} y={y + 3} textAnchor="end" className="svg-axis-num">
                    {val}%
                  </text>
                </g>
              );
            })}

            {/* Vertical Crosshair Line when a point is hovered */}
            {hoveredSplineIdx !== null && healthPoints[hoveredSplineIdx] && (
              <line
                x1={healthPoints[hoveredSplineIdx].x}
                y1={padY}
                x2={healthPoints[hoveredSplineIdx].x}
                y2={svgH - 18}
                stroke="#0d9488"
                strokeWidth="1.5"
                strokeDasharray="3 3"
                opacity="0.8"
              />
            )}

            {/* Area Path */}
            {healthAreaPath && <path d={healthAreaPath} fill="url(#healthAreaGrad)" />}

            {/* Polylines with hover highlight */}
            <polyline
              fill="none"
              stroke="#2563eb"
              strokeWidth="2"
              strokeDasharray="4 3"
              points={sleepPolyline}
              className="spline-line-sleep"
            />
            <polyline
              fill="none"
              stroke="#0d9488"
              strokeWidth="3"
              strokeLinecap="round"
              strokeLinejoin="round"
              points={healthPolyline}
              className="spline-line-health"
            />

            {/* Data Points with interactive hover listeners & tooltips */}
            {healthPoints.map((p, idx) => {
              const isDimmed = selectedBatchId !== "all" && p.batchId !== selectedBatchId;
              const isHovered = hoveredSplineIdx === idx;
              return (
                <g
                  key={idx}
                  opacity={isDimmed ? 0.25 : 1}
                  onMouseEnter={() => setHoveredSplineIdx(idx)}
                  onMouseLeave={() => setHoveredSplineIdx(null)}
                  style={{ cursor: "pointer" }}
                >
                  {/* Invisible larger hit target */}
                  <circle cx={p.x} cy={p.y} r="16" fill="transparent" />

                  {isHovered && (
                    <circle cx={p.x} cy={p.y} r="11" fill="none" stroke="#0d9488" strokeWidth="1.5" className="spline-pulse-ring" />
                  )}

                  <circle
                    cx={p.x}
                    cy={p.y}
                    r={isHovered ? 7 : 4.5}
                    fill="#0d9488"
                    stroke="#ffffff"
                    strokeWidth={isHovered ? 2.5 : 1.5}
                    style={{
                      filter: isHovered ? "drop-shadow(0 0 8px rgba(13,148,136,0.8))" : "none",
                      transition: "all 0.18s ease",
                    }}
                  />

                  {isHovered && sleepPoints[idx] && (
                    <circle
                      cx={sleepPoints[idx].x}
                      cy={sleepPoints[idx].y}
                      r="6"
                      fill="#2563eb"
                      stroke="#ffffff"
                      strokeWidth="2"
                      style={{ filter: "drop-shadow(0 0 6px rgba(37,99,235,0.8))" }}
                    />
                  )}

                  <text x={p.x} y={p.y - (isHovered ? 12 : 8)} textAnchor="middle" className={`svg-node-val ${isHovered ? "active" : ""}`}>
                    {p.val}%
                  </text>
                  <text x={p.x} y={svgH - 4} textAnchor="middle" className={`svg-x-label ${isHovered ? "active" : ""}`}>
                    {p.label}
                  </text>

                  {/* Rich Floating Tooltip */}
                  {isHovered && (
                    <g className="spline-hover-tooltip" style={{ pointerEvents: "none" }}>
                      <rect
                        x={Math.max(6, Math.min(svgW - 142, p.x - 71))}
                        y={Math.max(4, p.y - 48)}
                        width="142"
                        height="38"
                        rx="7"
                        fill="#0f172a"
                        fillOpacity="0.94"
                        filter="drop-shadow(0 4px 12px rgba(15,23,42,0.3))"
                      />
                      <text
                        x={Math.max(6, Math.min(svgW - 142, p.x - 71)) + 71}
                        y={Math.max(4, p.y - 48) + 16}
                        textAnchor="middle"
                        fill="#94a3b8"
                        fontSize="9.5"
                        fontWeight="700"
                      >
                        {p.label} • {p.batchId === "b1" ? "Đợt 1" : p.batchId === "b2" ? "Đợt 2" : "Đợt 3"}
                      </text>
                      <text
                        x={Math.max(6, Math.min(svgW - 142, p.x - 71)) + 71}
                        y={Math.max(4, p.y - 48) + 30}
                        textAnchor="middle"
                        fontSize="10.5"
                        fontWeight="800"
                      >
                        <tspan fill="#2dd4bf">SK: {p.val}%</tspan>
                        <tspan fill="#64748b"> | </tspan>
                        <tspan fill="#60a5fa">Ngủ: {sleepPoints[idx]?.val ?? 88}%</tspan>
                      </text>
                    </g>
                  )}
                </g>
              );
            })}
          </svg>
        </div>

        {/* Chart 2B: Biểu Đồ Cột Ghép Đau VAS & Đường Thân Nhiệt (°C) with Crosshair & Tooltips */}
        <div className="episodic-svg-chart-box">
          <div className="svg-chart-head">
            <div>
              <span className="chart-kicker">BIỂU ĐỒ CỘT GHÉP & ĐƯỜNG NHIỆT ĐỘ</span>
              <h4>Tương Quan Mức Đau (VAS /10) & Thân Nhiệt (°C)</h4>
            </div>
            <div className="svg-legend-inline">
              <span className="leg-dot amber">■ Cột Đau VAS</span>
              <span className="leg-dot rose">● Thân nhiệt (°C)</span>
            </div>
          </div>

          <svg viewBox={`0 0 ${svgW} ${svgH}`} className="episodic-spline-svg">
            <line
              x1={padX}
              y1={+(padY + ((40.0 - 37.0) / 4.0) * plotH).toFixed(1)}
              x2={svgW - padX}
              y2={+(padY + ((40.0 - 37.0) / 4.0) * plotH).toFixed(1)}
              stroke="#94a3b8"
              strokeDasharray="3 3"
            />

            {/* Crosshair line when hovered */}
            {hoveredBarIdx !== null && tempPoints[hoveredBarIdx] && (
              <line
                x1={tempPoints[hoveredBarIdx].x}
                y1={padY}
                x2={tempPoints[hoveredBarIdx].x}
                y2={svgH - 18}
                stroke="#e11d48"
                strokeWidth="1.5"
                strokeDasharray="3 3"
                opacity="0.8"
              />
            )}

            {/* VAS Vertical Bars with Hover Expansion & Glow */}
            {tempPoints.map((pt, idx) => {
              const barH = Math.max(6, (pt.pain / 10) * plotH);
              const barY = padY + plotH - barH;
              const barColor = pt.pain >= 6 ? "#e11d48" : pt.pain >= 3 ? "#f59e0b" : "#10b981";
              const isDimmed = selectedBatchId !== "all" && pt.batchId !== selectedBatchId;
              const isHovered = hoveredBarIdx === idx;
              return (
                <g
                  key={idx}
                  opacity={isDimmed ? 0.25 : 1}
                  onMouseEnter={() => setHoveredBarIdx(idx)}
                  onMouseLeave={() => setHoveredBarIdx(null)}
                  style={{ cursor: "pointer" }}
                >
                  {/* Invisible hit target */}
                  <rect x={pt.x - 18} y={padY} width="36" height={plotH} fill="transparent" />

                  <rect
                    x={pt.x - (isHovered ? 16 : 14)}
                    y={barY - (isHovered ? 2 : 0)}
                    width={isHovered ? 32 : 28}
                    height={barH + (isHovered ? 2 : 0)}
                    rx="6"
                    fill={barColor}
                    fillOpacity={isHovered ? 0.55 : 0.25}
                    stroke={barColor}
                    strokeWidth={isHovered ? 2.5 : 1.5}
                    style={{
                      filter: isHovered ? `drop-shadow(0 0 10px ${barColor})` : "none",
                      transition: "all 0.18s ease",
                    }}
                  />
                  <text
                    x={pt.x}
                    y={padY + plotH - 4}
                    textAnchor="middle"
                    className={`svg-bar-vas ${isHovered ? "active" : ""}`}
                    fontWeight={isHovered ? "800" : "700"}
                  >
                    VAS {pt.pain}
                  </text>
                  <text x={pt.x} y={svgH - 4} textAnchor="middle" className={`svg-x-label ${isHovered ? "active" : ""}`}>
                    {pt.label}
                  </text>

                  {/* Floating VAS & Temp Tooltip */}
                  {isHovered && (
                    <g className="vas-hover-tooltip" style={{ pointerEvents: "none" }}>
                      <rect
                        x={Math.max(6, Math.min(svgW - 146, pt.x - 73))}
                        y={Math.max(4, barY - 44)}
                        width="146"
                        height="38"
                        rx="7"
                        fill="#0f172a"
                        fillOpacity="0.94"
                        filter="drop-shadow(0 4px 12px rgba(15,23,42,0.3))"
                      />
                      <text
                        x={Math.max(6, Math.min(svgW - 146, pt.x - 73)) + 73}
                        y={Math.max(4, barY - 44) + 16}
                        textAnchor="middle"
                        fill="#94a3b8"
                        fontSize="9.5"
                        fontWeight="700"
                      >
                        {pt.label} • {pt.pain >= 6 ? "Đau nhiều" : pt.pain >= 3 ? "Đau vừa" : "Ổn định"}
                      </text>
                      <text
                        x={Math.max(6, Math.min(svgW - 146, pt.x - 73)) + 73}
                        y={Math.max(4, barY - 44) + 30}
                        textAnchor="middle"
                        fontSize="10.5"
                        fontWeight="800"
                      >
                        <tspan fill={barColor}>Đau: VAS {pt.pain}/10</tspan>
                        <tspan fill="#64748b"> | </tspan>
                        <tspan fill="#fb7185">Nhiệt: {pt.temp}°C</tspan>
                      </text>
                    </g>
                  )}
                </g>
              );
            })}

            {/* Overlaid Temperature Line */}
            <polyline
              fill="none"
              stroke="#e11d48"
              strokeWidth="2.5"
              strokeLinecap="round"
              points={tempPolyline}
              className="spline-line-temp"
            />

            {/* Temperature Nodes with Hover Expansion */}
            {tempPoints.map((pt, idx) => {
              const isHovered = hoveredBarIdx === idx;
              return (
                <g key={`t-${idx}`}>
                  {isHovered && (
                    <circle cx={pt.x} cy={pt.y} r="11" fill="none" stroke="#e11d48" strokeWidth="1.5" className="spline-pulse-ring" />
                  )}
                  <circle
                    cx={pt.x}
                    cy={pt.y}
                    r={isHovered ? 6.5 : 4}
                    fill="#e11d48"
                    stroke="#ffffff"
                    strokeWidth={isHovered ? 2.5 : 1.5}
                    style={{
                      filter: isHovered ? "drop-shadow(0 0 8px #e11d48)" : "none",
                      transition: "all 0.18s ease",
                    }}
                  />
                  <text x={pt.x} y={pt.y - (isHovered ? 11 : 7)} textAnchor="middle" className={`svg-temp-val ${isHovered ? "active" : ""}`}>
                    {pt.temp}°C
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </div>
    </section>
  );

  // 8. Trung Tâm Giải Pháp 4 Trụ Cột (Synchronized Hover with Impact Bars)
  const renderSolutionsCenter = () => (
    <section className="visual-section-card solutions-and-vitals-wrapper" aria-label="Trung tâm Giải pháp 4 Trụ Cột">
      <div className="solutions-top-layout">
        <div className="solutions-impact-chart-card">
          <span className="chart-kicker">TIẾN ĐỘ & HIỆU QUẢ CAN THIỆP</span>
          <h4>Biểu Đồ Hoàn Thành Giải Pháp (4 Trụ Cột)</h4>
          <div className="sol-donut-and-bars">
            <svg viewBox="0 0 100 100" className="sol-donut-svg hoverable-donut">
              <circle cx="50" cy="50" r="36" fill="none" stroke="#e2e8f0" strokeWidth="11" />
              <circle
                cx="50"
                cy="50"
                r="36"
                fill="none"
                stroke="#0d9488"
                strokeWidth="11"
                strokeDasharray={`${Math.round((visualChartSuite.solutionsSummary.completionPct / 100) * 226)} 226`}
                strokeLinecap="round"
                transform="rotate(-90 50 50)"
                className="donut-active-circle"
              />
              <text x="50" y="47" textAnchor="middle" className="donut-big-num">
                {visualChartSuite.solutionsSummary.completedCount}/{visualChartSuite.solutionsSummary.total}
              </text>
              <text x="50" y="61" textAnchor="middle" className="donut-sub-txt">
                +{visualChartSuite.solutionsSummary.projectedGain}% Hồi phục
              </text>
            </svg>

            <div className="sol-impact-bars">
              {visualChartSuite.solutionsSummary.items.map((item, idx) => {
                const isHovered = hoveredPillarId === item.id;
                return (
                  <div
                    key={item.id}
                    className={`sol-impact-row ${isHovered ? "hovered" : ""}`}
                    onMouseEnter={() => setHoveredPillarId(item.id)}
                    onMouseLeave={() => setHoveredPillarId(null)}
                    style={{ cursor: "pointer", transition: "all 0.2s ease" }}
                  >
                    <span>Trụ cột {idx + 1}</span>
                    <div className="si-track">
                      <div
                        className="si-fill"
                        style={{
                          width: `${item.impactScore}%`,
                          backgroundColor: isHovered ? "#0d9488" : item.completed ? "#0d9488" : "#3b82f6",
                          filter: isHovered ? "drop-shadow(0 0 6px rgba(13,148,136,0.6))" : "none",
                        }}
                      />
                    </div>
                    <strong>{item.impactScore}%</strong>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="solutions-pillars-grid">
          {personalizedSolutions.map((sol) => {
            const isDone = Boolean(completedSolutions[sol.id]);
            const isHovered = hoveredPillarId === sol.id;
            return (
              <div
                key={sol.id}
                className={`solution-pillar-card priority-${sol.priorityLevel} ${isDone ? "completed" : ""} ${isHovered ? "hovered" : ""}`}
                onMouseEnter={() => setHoveredPillarId(sol.id)}
                onMouseLeave={() => setHoveredPillarId(null)}
              >
                <div className="sol-card-top">
                  <span className="sol-pillar-name">{sol.pillar}</span>
                  <span className={`sol-priority-badge ${sol.priorityLevel}`}>{sol.priority}</span>
                </div>
                <h4 className="sol-card-title">{sol.title}</h4>
                <ul className="sol-steps-list">
                  {sol.actionSteps.slice(0, 2).map((step, sIdx) => (
                    <li key={sIdx}>
                      <CheckCircle2 size={13} className="sol-step-icon" />
                      <span>{step}</span>
                    </li>
                  ))}
                </ul>
                <div className="sol-card-actions">
                  <button
                    type="button"
                    className={`sol-btn-check ${isDone ? "done" : ""}`}
                    onClick={() =>
                      setCompletedSolutions((prev) => ({ ...prev, [sol.id]: !prev[sol.id] }))
                    }
                  >
                    <Check size={13} />
                    <span>{isDone ? "Đã thực hiện" : "Đánh dấu hoàn thành"}</span>
                  </button>
                  <button
                    type="button"
                    className="sol-btn-chat"
                    onClick={() => onNavigate?.("chat")}
                  >
                    <MessageSquare size={13} />
                    <span>Hỏi AI</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );

  return (
    <div className="health-twin-container daylight-clinical-theme" role="main" aria-label="Bản đồ Cơ thể & Đa Biểu Đồ Sức khoẻ">
      {/* ====================================================================
          1. COMPACT EXECUTIVE TOPBAR & MEMBER AUTH BADGE
          ==================================================================== */}
      <header className="health-twin-topbar">
        <div className="topbar-left">
          <button
            type="button"
            className="back-btn"
            onClick={onBackToChat}
            title="Quay lại phòng chat hội thoại"
          >
            <ArrowLeft size={15} />
            <span>Hội thoại</span>
          </button>

          <div className="twin-title-group">
            <div className="twin-brand-badge">
              <HeartPulse size={18} className="twin-pulse-icon" />
              <h1>Quản Trị Sức Khoẻ & Giải Phẫu Đa Biểu Đồ</h1>
              <span className="live-tag">ĐỒNG BỘ TỰ ĐỘNG</span>
            </div>
            <p className="twin-subtitle">
              Tình trạng: <strong>{profile?.active_diagnosis || "Thể trạng Khỏe mạnh - Bình thường"}</strong> • Cập nhật lúc {profile?.last_updated || "Hiện tại"}
            </p>
          </div>
        </div>

        <div className="topbar-right">
          <div className="member-verified-pill" title="Phân quyền Hồ sơ Cá nhân đã xác thực">
            <ShieldCheck size={14} />
            <span>{account?.email || profile?.patient_name || "Thành viên Đã đăng nhập"}</span>
          </div>

          <div className="overall-score-mini-ring">
            <svg viewBox="0 0 36 36" className="mini-ring-svg">
              <circle cx="18" cy="18" r="15" fill="none" stroke="#e2e8f0" strokeWidth="3.5" />
              <circle
                cx="18"
                cy="18"
                r="15"
                fill="none"
                stroke={getStatusColor("normal", overallScore)}
                strokeWidth="3.5"
                strokeDasharray={`${Math.round((overallScore / 100) * 94.2)} 95`}
                strokeLinecap="round"
                transform="rotate(-90 18 18)"
              />
            </svg>
            <div className="mini-ring-text">
              <span>Thể trạng</span>
              <strong>{overallScore}%</strong>
            </div>
          </div>

          <button
            type="button"
            className="console-btn-subtle"
            onClick={handleResetProfile}
            disabled={loading}
            title="Đặt lại thể trạng ban đầu"
          >
            <RotateCcw size={14} className={loading ? "spinning" : ""} />
            <span>Đặt lại ban đầu</span>
          </button>
        </div>
      </header>

      {/* Action Notification Toast */}
      {actionNotice && (
        <div className="health-action-toast">
          <Sparkles size={15} />
          <span>{actionNotice}</span>
        </div>
      )}

      {/* ====================================================================
          2. BIOMETRIC VITALS EXECUTIVE RIBBON (5 VITAL SIGNS - PROMINENT AT TOP!)
          ==================================================================== */}
      {renderVitalsRibbon()}

      {/* ====================================================================
          3. UNIVERSAL NATURAL-LANGUAGE SYMPTOM/FEELING INPUT CONSOLE
          ==================================================================== */}
      {renderSmartIntakeConsole()}

      {/* ====================================================================
          4. SECTION FOCUS FILTER BAR (Segmented Navigation)
          ==================================================================== */}
      <nav className="health-section-switcher-bar" aria-label="Bộ lọc phân khu trực quan">
        <div className="section-tabs-group" role="tablist">
          {[
            { id: "all", label: "Tất cả Trực quan" },
            { id: "anatomy", label: "1. Giải phẫu 3D (9 Cơ quan)" },
            { id: "bio", label: "2. Radar Sinh học" },
            { id: "episodic", label: "3. Diễn tiến Đợt" },
            { id: "solutions", label: "4. Phác đồ 4 Trụ Cột" },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={sectionFilter === tab.id}
              className={`sec-filter-tab ${sectionFilter === tab.id ? "active" : ""}`}
              onClick={() => setSectionFilter(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <button
          type="button"
          className="btn-open-chat-sync"
          onClick={() => onNavigate?.("chat")}
        >
          <MessageSquare size={14} />
          <span>Chat với Bác sĩ AI</span>
        </button>
      </nav>

      {/* ====================================================================
          5. MAIN COMMAND CENTER DASHBOARD (BALANCED & EXECUTIVE MULTI-TIER)
          ==================================================================== */}
      {sectionFilter === "all" && (
        <div className="twin-executive-master-wrapper">
          {/* Upper Deck: 3D Anatomical Stage (Left) & Biometrics / Organ Ranking (Right) */}
          <div className="twin-executive-grid">
            {/* Left Wing: 3D Anatomical Twin */}
            <div className="twin-col-anatomy">
              {render3DAnatomicalModel()}
            </div>

            {/* Right Wing: Biometrics, 9-Organ Ranking */}
            <div className="twin-col-analytics">
              {renderBioRadarAndGauges()}
              {renderOrganRankingDonutAndBars()}
            </div>
          </div>

          {/* Dedicated Full-Width Organ Diagnostic Dossier */}
          {renderOrganInspector()}

          {/* Lower Clinical Deck: Full-Width Episodic Analytics & 4-Pillar Solutions */}
          <div className="twin-clinical-deck-full">
            {renderEpisodicAnalyticsSuite()}
            {renderSolutionsCenter()}
          </div>
        </div>
      )}

      {sectionFilter === "anatomy" && (
        <div className="twin-executive-master-wrapper">
          <div className="twin-focus-2col-grid">
            <div className="twin-col-anatomy">
              {render3DAnatomicalModel()}
            </div>
            <div className="twin-col-analytics">
              {renderOrganRankingDonutAndBars()}
            </div>
          </div>
          {renderOrganInspector()}
        </div>
      )}

      {sectionFilter === "bio" && (
        <div className="twin-focus-2col-grid">
          <div className="twin-col-left">
            {renderBioRadarAndGauges()}
          </div>
          <div className="twin-col-right">
            {renderOrganRankingDonutAndBars()}
          </div>
        </div>
      )}

      {sectionFilter === "episodic" && (
        <div className="twin-focus-full-width">
          {renderEpisodicAnalyticsSuite()}
        </div>
      )}

      {sectionFilter === "solutions" && (
        <div className="twin-focus-full-width">
          {renderSolutionsCenter()}
        </div>
      )}
    </div>
  );
}
