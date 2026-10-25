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
} from 'lucide-react';
import './HealthTwinPage.css';
import {
  QUICK_FEELING_CHIPS,
  normalizeOrgansArray,
  evaluateHolisticHealthInput,
  computeEpisodicHealthAnalytics,
  computePersonalizedHealthSolutions,
} from './holisticHealthEngine';

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
  { id: 'all', label: 'Tất cả cơ quan (9)', icon: Activity },
  { id: 'digestive', label: 'Tiêu hóa & Gan mật (2)', icon: Flame, organIds: ['stomach', 'liver'] },
  { id: 'cardiopulmonary', label: 'Hô hấp & Tuần hoàn (3)', icon: HeartPulse, organIds: ['lungs', 'cardiovascular', 'ent'] },
  { id: 'neuromuscular', label: 'Thần kinh & Vận động (4)', icon: Zap, organIds: ['head', 'spine_joints', 'kidneys', 'skin'] },
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

export function HealthTwinPage({ api, onBackToChat, onNavigate, onNotify }) {
  const [profile, setProfile] = useState(DEFAULT_HEALTH_PROFILE);
  const [loading, setLoading] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  // Default selected organ to 'liver' to directly highlight the Hepatitis B -> Liver cancer example
  const [selectedOrganId, setSelectedOrganId] = useState('liver');
  const [selectedSystem, setSelectedSystem] = useState('all');
  const [hoveredOrganId, setHoveredOrganId] = useState(null);
  const [inputMessage, setInputMessage] = useState('');
  // Default to future_risks tab so user immediately sees the predictive matrix and vaccination protocol
  const [activeTab, setActiveTab] = useState('future_risks');
  const [actionNotice, setActionNotice] = useState(null);
  const [modelViewMode, setModelViewMode] = useState('3d_hologram');
  const [isListening, setIsListening] = useState(false);
  const [showVaccineDrawer, setShowVaccineDrawer] = useState(false);
  const [episodicTimeframe, setEpisodicTimeframe] = useState('DAY');
  const [selectedBatchId, setSelectedBatchId] = useState('all');
  const [completedSolutions, setCompletedSolutions] = useState({});

  // Reset health profile back to clean baseline
  const handleResetProfile = async () => {
    try {
      setLoading(true);
      const res = await api.request('/v1/health-twin/reset', { method: 'POST' });
      if (res && res.organs) {
        setProfile(res);
        setActionNotice('Đã đặt lại thể trạng bình thường ban đầu thành công.');
        setTimeout(() => setActionNotice(null), 3500);
      }
    } catch (err) {
      console.error('Failed to reset health profile:', err);
      setProfile(DEFAULT_HEALTH_PROFILE);
      setActionNotice('Đã đặt lại thể trạng ban đầu.');
      setTimeout(() => setActionNotice(null), 3500);
    } finally {
      setLoading(false);
    }
  };

  // Voice speech-to-text handler for symptom description
  const handleVoiceInput = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      onNotify?.('Trình duyệt chưa hỗ trợ nhận diện giọng nói Web Speech.');
      return;
    }
    try {
      const recognition = new SpeechRecognition();
      recognition.lang = 'vi-VN';
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

  // Load initial health profile
  const fetchProfile = async () => {
    try {
      setLoading(true);
      const data = await api.request('/v1/health-twin/profile');
      if (data && data.organs) {
        const normalized = {
          ...DEFAULT_HEALTH_PROFILE,
          ...data,
          organs: normalizeOrgansArray(data.organs, DEFAULT_HEALTH_PROFILE.organs),
        };
        setProfile(normalized);
      }
    } catch (err) {
      console.error('Failed to load health profile:', err);
      try {
        const raw = localStorage.getItem('medguard_health_twin_profile');
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
      onNotify?.('Đang sử dụng hồ sơ sức khoẻ thông minh tại chỗ.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
    const handleSync = () => {
      fetchProfile();
    };
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
        if (detail.healthMutation?.adr_alert) {
          setActionNotice(`Cảnh báo lâm sàng ADR: ${detail.healthMutation.adr_alert.action_directive}`);
        } else {
          setActionNotice(`Đã tự động đồng bộ tình trạng bệnh & cảm giác vào Tổng Quan Sức Khoẻ!`);
        }
        setTimeout(() => setActionNotice(null), 5000);
      }
    };
    window.addEventListener('medguard:health-twin-updated', handleSync);
    window.addEventListener('medguard:unified-chat-sync', handleUnifiedChatSync);
    return () => {
      window.removeEventListener('medguard:health-twin-updated', handleSync);
      window.removeEventListener('medguard:unified-chat-sync', handleUnifiedChatSync);
    };
  }, []);

  // Quick scenario switcher
  const handleSwitchScenario = async (scenarioId) => {
    try {
      setLoading(true);
      const updated = await api.request('/v1/health-twin/scenario', {
        method: 'POST',
        body: { scenario_id: scenarioId },
      });
      setProfile(updated);
      const sc = SCENARIOS.find((s) => s.id === scenarioId);
      setActionNotice(`Đã chuyển kịch bản: ${sc?.label}`);
      setTimeout(() => setActionNotice(null), 4000);
    } catch (err) {
      console.error('Failed to switch scenario:', err);
      onNotify?.('Lỗi chuyển đổi kịch bản.');
    } finally {
      setLoading(false);
    }
  };

  // Submit patient progress message
  const handleEvaluateProgress = async (textToEvaluate) => {
    const text = textToEvaluate || inputMessage;
    if (!text || !text.trim()) return;

    try {
      setEvaluating(true);
      const res = await api.request('/v1/health-twin/evaluate-symptom-update', {
        method: 'POST',
        body: { message: text },
      });
      setProfile(res.profile);
      setInputMessage('');

      if (res.must_discontinue_previous) {
        onNotify?.('Cảnh báo lâm sàng: Phát hiện tác dụng phụ, đã kích hoạt hướng dẫn an toàn.');
      } else if (res.detected_event === 'recovery') {
        onNotify?.('Ghi nhận hồi phục tích cực: Đã cập nhật trạng thái cơ thể ổn định.');
      } else {
        onNotify?.('Đã cập nhật diễn tiến sức khoẻ vào hồ sơ.');
      }
    } catch (err) {
      console.error('Failed to evaluate symptom update:', err);
      onNotify?.('Không thể phân tích diễn tiến sức khoẻ.');
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
    () => computeEpisodicHealthAnalytics(profile, episodicTimeframe),
    [profile, episodicTimeframe]
  );

  const personalizedSolutions = useMemo(
    () => computePersonalizedHealthSolutions({ ...profile, organs: normalizedOrgans }),
    [profile, normalizedOrgans]
  );

  const getStatusColor = (status, score) => {
    if (status === 'adverse_reaction' || status === 'critical') return '#ef4444';
    if (status === 'inflamed') return '#f97316';
    if (status === 'monitoring') return '#eab308';
    if (score < 50) return '#ef4444';
    if (score < 80) return '#f59e0b';
    return '#10b981';
  };

  const getStatusBadgeText = (status) => {
    switch (status) {
      case 'adverse_reaction':
        return 'TÁC DỤNG PHỤ (ADR)';
      case 'critical':
        return 'BÁO ĐỘNG ĐỎ';
      case 'inflamed':
        return 'ĐANG VIÊM / TỔN THƯƠNG';
      case 'monitoring':
        return 'ĐANG THEO DÕI';
      default:
        return 'ỔN ĐỊNH / BÌNH THƯỜNG';
    }
  };

  return (
    <div className="health-twin-container" role="main" aria-label="Bản đồ Cơ thể & Sức khoẻ Thời gian thực">
      {/* Top Banner & Header */}
      <header className="health-twin-topbar">
        <div className="topbar-left">
          <button
            type="button"
            className="back-btn"
            onClick={onBackToChat}
            title="Quay lại phòng chat hội thoại"
          >
            <ArrowLeft size={16} />
            <span>Quay lại Chat</span>
          </button>
          <div className="twin-title-group">
            <div className="twin-brand-badge">
              <Activity size={18} className="twin-pulse-icon" />
              <h1>Anatomical Health Twin</h1>
              <span className="live-tag">CLINICAL PRECISION</span>
            </div>
            <p className="twin-subtitle">
              Định vị Giải phẫu Học Chính xác — Đánh giá Toàn diện Sinh hiệu & Dự báo Rủi ro Tương lai (AI Risk Prognosis)
            </p>
          </div>
        </div>

        <div className="topbar-right">
          <div className="patient-meta-pill">
            <User size={14} />
            <strong>{profile?.patient_name || 'Bệnh nhân'}</strong>
            <span className="meta-sep">•</span>
            <span>{profile?.age || 34} tuổi ({profile?.gender || 'Nam'})</span>
          </div>
          <button
            type="button"
            className="refresh-btn"
            onClick={fetchProfile}
            disabled={loading}
            title="Tải lại dữ liệu"
          >
            <RefreshCw size={14} className={loading ? 'spinning' : ''} />
          </button>
        </div>
      </header>

      {/* Action Notification Toast */}
      {actionNotice && (
        <div className="health-action-toast">
          <Sparkles size={16} />
          <span>{actionNotice}</span>
        </div>
      )}

      {/* Real-time Auto-Sync Clinical Header from Doctor Chat */}
      <section className="health-twin-sync-bar" aria-label="Đồng bộ tự động từ hội thoại khám bệnh lâm sàng">
        <div className="sync-bar-left">
          <div className="sync-status-indicator">
            <span className="sync-pulse-dot" />
            <Activity size={18} className="sync-pulse-icon" />
          </div>
          <div className="sync-meta-info">
            <div className="sync-badge-row">
              <span className="clinical-live-badge">ĐỒNG BỘ TỰ ĐỘNG TỪ HỘI THOẠI KHÁM BỆNH</span>
              <span className="patient-active-badge">
                Tình trạng: <strong>{profile?.active_diagnosis || 'Đang theo dõi sức khoẻ tổng quát'}</strong>
              </span>
            </div>
            <p className="sync-description">
              Hệ thống AI tự động phát hiện triệu chứng, đối chiếu phản ứng thuốc và cập nhật bản đồ giải phẫu dựa trên cuộc hội thoại khám bệnh của bạn.
            </p>
          </div>
        </div>

        <div className="sync-bar-right">
          <div className="sync-vitals-preview">
            <div className="preview-stat">
              <span className="stat-label">Điểm thể trạng</span>
              <span className="stat-value" style={{ color: getStatusColor('score', profile?.overall_health_score || 95) }}>
                {profile?.overall_health_score || 95}%
              </span>
            </div>
            <div className="preview-stat">
              <span className="stat-label">Diễn tiến</span>
              <span className="stat-value trend">
                {profile?.health_trend === 'improving' ? 'Đang hồi phục' : profile?.health_trend === 'deteriorating' ? 'Cần theo dõi sát' : 'Ổn định'}
              </span>
            </div>
          </div>

          <div className="sync-action-buttons">
            <button
              type="button"
              className="btn-open-chat-sync"
              onClick={() => onNavigate?.('chat')}
              title="Mở hội thoại để trao đổi triệu chứng với Bác sĩ AI"
            >
              <MessageSquare size={15} />
              <span>Trò chuyện với Bác sĩ AI</span>
            </button>
            <button
              type="button"
              className="btn-refresh-profile-sync"
              onClick={handleResetProfile}
              disabled={loading}
              title="Đặt lại thể trạng bình thường ban đầu"
            >
              <RotateCcw size={14} className={loading ? 'spinning' : ''} />
              <span>Đặt lại ban đầu</span>
            </button>
          </div>
        </div>
      </section>

      {/* AI Safe Guardrail Alert Banner (If Harmful Medication Detected) */}
      {profile?.safe_guardrail_alert && (
        <section className={`guardrail-alert-banner level-${profile.safe_guardrail_alert.alert_level}`}>
          <div className="alert-banner-header">
            <div className="alert-title-wrap">
              <ShieldAlert size={22} className="alert-beacon-icon" />
              <div>
                <h2>{profile.safe_guardrail_alert.title}</h2>
                <span className="alert-cause">Nguyên nhân: {profile.safe_guardrail_alert.cause_identified}</span>
              </div>
            </div>
            {profile.safe_guardrail_alert.seek_emergency && (
              <button
                type="button"
                className="alert-emergency-nav-btn"
                onClick={() => {
                  window.dispatchEvent(
                    new CustomEvent('medguard:navigate', {
                      detail: { view: 'navigation' },
                    })
                  );
                }}
              >
                <AlertTriangle size={15} />
                <span>CHỈ ĐƯỜNG ĐẾN CƠ SỞ CẤP CỨU GẦN NHẤT</span>
              </button>
            )}
          </div>

          <div className="guardrail-grid">
            <div className="guardrail-col stop-col">
              <div className="col-label">
                <X size={15} />
                <strong>CHỈ THỊ: DỪNG CÁCH CŨ GÂY HẠI</strong>
              </div>
              <p className="col-desc highlight-stop">{profile.safe_guardrail_alert.required_action}</p>
              <div className="contra-badge">
                <span>Chống chỉ định:</span>
                <strong>{profile.safe_guardrail_alert.contraindicated_item}</strong>
              </div>
            </div>

            <div className="guardrail-col alt-col">
              <div className="col-label">
                <ShieldCheck size={15} />
                <strong>PHƯƠNG ÁN AN TOÀN THAY THẾ</strong>
              </div>
              <p className="col-desc">{profile.safe_guardrail_alert.alternative_recommendation}</p>
            </div>
          </div>
        </section>
      )}

      {/* Holistic Symptom & Feeling Live Input Hub + Episodic Multi-Timeframe Dashboard & 4-Pillar Solutions */}
      <section className="holistic-health-command-center" aria-label="Trung tâm Đồng bộ Cảm giác, Biểu đồ Theo Đợt và Giải pháp Sức khoẻ">
        {/* 1. Holistic Natural-Language Symptom & Feeling Input Box */}
        <div className="holistic-live-input-card">
          <div className="holistic-input-header">
            <div className="holistic-title-wrap">
              <Sparkles size={18} className="holistic-sparkle-icon" />
              <div>
                <h3>Cập Nhật Tự Động Mọi Tình Trạng Bệnh, Triệu Chứng & Cảm Giác Cơ Thể</h3>
                <p>
                  Nhập hoặc nói bất kỳ biểu hiện bệnh, cơn đau hay cảm giác trong người (căng thẳng, mất ngủ, mỏi mắt, đau rát dạ dày, sốt, mệt lả, hoặc đã khỏe hơn...) — Hệ thống tự động đồng bộ toàn bộ 9 cơ quan, sinh hiệu, biểu đồ từng đợt và phác đồ giải pháp.
                </p>
              </div>
            </div>
            <span className="holistic-last-sync-pill">
              <Clock size={12} />
              <span>{profile?.last_updated || 'Đồng bộ thời gian thực'}</span>
            </span>
          </div>

          <div className="holistic-input-bar-row">
            <input
              type="text"
              className="holistic-symptom-input"
              placeholder="Ví dụ: Hôm nay tôi đau đầu căng thẳng, mất ngủ, mỏi mắt và hơi đau rát thượng vị dạ dày..."
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleEvaluateProgress();
              }}
            />
            <button
              type="button"
              className={`holistic-mic-btn ${isListening ? 'listening' : ''}`}
              onClick={handleVoiceInput}
              title="Nhập triệu chứng bằng giọng nói"
            >
              <Mic size={16} />
            </button>
            <button
              type="button"
              className="holistic-submit-btn"
              disabled={evaluating || !inputMessage.trim()}
              onClick={() => handleEvaluateProgress()}
            >
              <Send size={15} />
              <span>{evaluating ? 'Đang đồng bộ AI...' : 'Đồng bộ Toàn diện'}</span>
            </button>
          </div>

          {/* Quick Feeling & Symptom Chips */}
          <div className="holistic-quick-chips-row">
            <span className="chips-prefix-label">Khai báo nhanh cảm giác / bệnh lý:</span>
            {QUICK_FEELING_CHIPS.map((chip) => (
              <button
                key={chip.id}
                type="button"
                className="holistic-feeling-chip"
                onClick={() => handleEvaluateProgress(chip.text)}
              >
                <Zap size={12} />
                <span>{chip.label}</span>
              </button>
            ))}
          </div>

          {/* 4 Holistic Wellbeing & Subjective Feeling Strips */}
          <div className="holistic-wellbeing-strip">
            <div className="wellbeing-mini-card">
              <span className="wb-label">Chất lượng Giấc ngủ & Phục hồi</span>
              <strong className="wb-val">{profile?.wellbeing?.sleep_quality_score ?? 88}/100</strong>
            </div>
            <div className="wellbeing-mini-card">
              <span className="wb-label">Mức độ Căng thẳng Thần kinh</span>
              <strong className="wb-val">{profile?.wellbeing?.stress_level_label || 'Thấp (Ổn định)'}</strong>
            </div>
            <div className="wellbeing-mini-card">
              <span className="wb-label">Pin Năng lượng Cơ thể</span>
              <strong className="wb-val">{profile?.wellbeing?.energy_battery_percent ?? 90}%</strong>
            </div>
            <div className="wellbeing-mini-card">
              <span className="wb-label">Cân bằng Nước & Điện giải</span>
              <strong className="wb-val">{profile?.wellbeing?.hydration_balance_percent ?? 92}%</strong>
            </div>
          </div>
        </div>

        {/* 2. Episodic Multi-Timeframe Health Statistics Dashboard (Giờ / Ngày / Tuần / Tháng by Đợt 1, Đợt 2, Đợt 3) */}
        <div className="episodic-analytics-panel">
          <div className="episodic-panel-header">
            <div className="episodic-title-block">
              <div className="episodic-badge-row">
                <span className="episodic-tag">THỐNG KÊ SỨC KHOẺ THEO ĐỢT</span>
                <span className={`episodic-delta-pill ${episodicAnalytics.overallDelta >= 0 ? 'up' : 'down'}`}>
                  {episodicAnalytics.overallDelta >= 0 ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
                  <span>
                    {episodicAnalytics.overallDelta >= 0 ? `+${episodicAnalytics.overallDelta}%` : `${episodicAnalytics.overallDelta}%`} so với Đợt 1
                  </span>
                </span>
              </div>
              <h3>Biểu Đồ Thống Kê Diễn Tiến Sức Khoẻ Chia Theo Từng Đợt ({episodicAnalytics.timeframeLabel})</h3>
              <p>
                Phân tích đa khung thời gian (Giờ, Ngày, Tuần, Tháng) chia theo 3 đợt lâm sàng giúp đánh giá chính xác tốc độ đáp ứng điều trị và đề xuất giải pháp trúng đích.
              </p>
            </div>

            <div className="episodic-timeframe-switcher" role="tablist" aria-label="Chọn khung thời gian thống kê">
              {[
                { id: 'HOUR', label: 'Theo Giờ (24h)' },
                { id: 'DAY', label: 'Theo Ngày (7 ngày)' },
                { id: 'WEEK', label: 'Theo Tuần (4 tuần)' },
                { id: 'MONTH', label: 'Theo Tháng (6 tháng)' },
              ].map((tf) => (
                <button
                  key={tf.id}
                  type="button"
                  role="tab"
                  aria-selected={episodicTimeframe === tf.id}
                  className={`tf-switch-btn ${episodicTimeframe === tf.id ? 'active' : ''}`}
                  onClick={() => {
                    setEpisodicTimeframe(tf.id);
                    setSelectedBatchId('all');
                  }}
                >
                  {tf.label}
                </button>
              ))}
            </div>
          </div>

          {/* 3 Clinical Batch Filter Cards (Đợt 1, Đợt 2, Đợt 3 - Hiện tại) */}
          <div className="episodic-batches-grid">
            {episodicAnalytics.batches.map((batch) => {
              const isSelected = selectedBatchId === batch.id;
              return (
                <div
                  key={batch.id}
                  className={`episodic-batch-card ${batch.status} ${isSelected ? 'selected' : ''}`}
                  onClick={() => setSelectedBatchId(isSelected ? 'all' : batch.id)}
                  role="button"
                  tabIndex={0}
                >
                  <div className="batch-card-top">
                    <span className="batch-code-badge">{batch.code}</span>
                    <span className={`batch-delta-tag ${batch.delta >= 0 ? 'pos' : 'neg'}`}>
                      {batch.delta >= 0 ? `+${batch.delta}% điểm thể trạng` : `${batch.delta}% điểm thể trạng`}
                    </span>
                  </div>
                  <h4 className="batch-card-title">{batch.name}</h4>
                  <p className="batch-focus-text">{batch.focus}</p>
                  <div className="batch-metrics-row">
                    <div className="bm-item">
                      <span>Điểm TB</span>
                      <strong>{batch.avgScore}%</strong>
                    </div>
                    <div className="bm-item">
                      <span>Đau VAS</span>
                      <strong>{batch.avgPain}/10</strong>
                    </div>
                    <div className="bm-item">
                      <span>Thân nhiệt</span>
                      <strong>{batch.avgTemp}°C</strong>
                    </div>
                    <div className="bm-item">
                      <span>Nhịp tim</span>
                      <strong>{batch.avgHr} bpm</strong>
                    </div>
                  </div>
                  <div className="batch-solution-callout">
                    <CheckCircle2 size={13} />
                    <span><strong>Giải pháp trọng tâm đợt này:</strong> {batch.solutionSummary}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Visual Episodic Bar & Trend Chart */}
          <div className="episodic-chart-stage">
            <div className="chart-legend-bar">
              <span className="c-legend"><i className="dot score" /> Điểm Sức Khoẻ Tổng Thể (%)</span>
              <span className="c-legend"><i className="dot sleep" /> Chỉ Số Giấc Ngủ & Phục Hồi (%)</span>
              <span className="c-legend"><i className="dot pain" /> Thang Đau VAS (/10) & Nhiệt độ (°C)</span>
            </div>
            <div className="episodic-bars-columns">
              {episodicAnalytics.series.map((pt, idx) => {
                const isDimmed = selectedBatchId !== 'all' && pt.batchId !== selectedBatchId;
                return (
                  <div key={idx} className={`episodic-col-item ${isDimmed ? 'dimmed' : ''}`}>
                    <div className="col-batch-tag">{pt.batchCode}</div>
                    <div className="col-bars-track">
                      <div
                        className="col-bar health-bar"
                        style={{ height: `${Math.max(12, pt.healthScore)}%` }}
                        title={`Điểm sức khoẻ: ${pt.healthScore}%`}
                      >
                        <span className="bar-top-val">{pt.healthScore}%</span>
                      </div>
                      <div
                        className="col-bar sleep-bar"
                        style={{ height: `${Math.max(12, pt.sleepScore)}%` }}
                        title={`Giấc ngủ & phục hồi: ${pt.sleepScore}%`}
                      />
                    </div>
                    <div className="col-sub-metrics">
                      <span className="sub-pain">VAS {pt.painScore}/10</span>
                      <span className="sub-temp">{pt.temperature}°C</span>
                    </div>
                    <strong className="col-time-label">{pt.label}</strong>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* 3. 4-Pillar Personalized Health Solutions Center */}
        <div className="personalized-solutions-center">
          <div className="solutions-header-bar">
            <div>
              <span className="solutions-kicker">TRỌNG TÂM ĐÁNH GIÁ TỔNG QUAN & CAN THIỆP</span>
              <h3>Trung Tâm Giải Pháp Sức Khoẻ & Phác Đồ Hành Động Cá Nhân Hoá (4 Trụ Cột)</h3>
              <p>
                Tự động tổng hợp giải pháp từ tình trạng bệnh, cảm giác cơ thể và thống kê từng đợt của bạn để cải thiện sức khoẻ nhanh chóng, an toàn.
              </p>
            </div>
          </div>

          <div className="solutions-pillars-grid">
            {personalizedSolutions.map((sol) => {
              const isDone = Boolean(completedSolutions[sol.id]);
              return (
                <div key={sol.id} className={`solution-pillar-card priority-${sol.priorityLevel} ${isDone ? 'completed' : ''}`}>
                  <div className="sol-card-top">
                    <span className="sol-pillar-name">{sol.pillar}</span>
                    <span className={`sol-priority-badge ${sol.priorityLevel}`}>{sol.priority}</span>
                  </div>
                  <h4 className="sol-card-title">{sol.title}</h4>
                  <div className="sol-target-organ">
                    <HeartPulse size={13} />
                    <span>Đích tác động: <strong>{sol.targetOrgan}</strong></span>
                  </div>
                  <p className="sol-rationale">{sol.rationale}</p>
                  <ul className="sol-steps-list">
                    {sol.actionSteps.map((step, sIdx) => (
                      <li key={sIdx}>
                        <CheckCircle2 size={14} className="sol-step-icon" />
                        <span>{step}</span>
                      </li>
                    ))}
                  </ul>
                  <div className="sol-outcome-box">
                    <Sparkles size={13} />
                    <span><strong>Mục tiêu đạt được:</strong> {sol.expectedOutcome}</span>
                  </div>
                  <div className="sol-card-actions">
                    <button
                      type="button"
                      className={`sol-btn-check ${isDone ? 'done' : ''}`}
                      onClick={() =>
                        setCompletedSolutions((prev) => ({ ...prev, [sol.id]: !prev[sol.id] }))
                      }
                    >
                      <Check size={14} />
                      <span>{isDone ? 'Đã áp dụng giải pháp' : 'Đánh dấu thực hiện'}</span>
                    </button>
                    <button
                      type="button"
                      className="sol-btn-chat"
                      onClick={() => {
                        onNavigate?.('chat');
                        window.dispatchEvent(
                          new CustomEvent('medguard:navigate', {
                            detail: {
                              view: 'chat',
                              message: `Tư vấn chi tiết giải pháp: ${sol.title} cho ${sol.targetOrgan}`,
                            },
                          })
                        );
                      }}
                    >
                      <MessageSquare size={13} />
                      <span>Hỏi Bác sĩ AI</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Main Interactive Twin Workspace */}
      <div className="twin-main-grid">
        {/* Left Column: Interactive 3D Anatomical Digital Twin Model */}
        <section className="body-silhouette-card" aria-label="Sơ đồ Giải phẫu Cơ thể">
          <div className="silhouette-header">
            <div className="header-badge">
              <HeartPulse size={16} />
              <span>Sơ đồ Giải phẫu Cơ thể Người (Anatomical Landmarks)</span>
            </div>
            <div className="model-view-controls">
              <button
                type="button"
                className={`view-toggle-btn ${modelViewMode === '3d_hologram' ? 'active' : ''}`}
                onClick={() => setModelViewMode('3d_hologram')}
                title="Chế độ Giải phẫu Chuẩn 3D"
              >
                <Scan size={13} />
                <span>Giải phẫu 3D</span>
              </button>
              <button
                type="button"
                className={`view-toggle-btn ${modelViewMode === 'wireframe_heatmap' ? 'active' : ''}`}
                onClick={() => setModelViewMode('wireframe_heatmap')}
                title="Chế độ Bản đồ Nhiệt Lâm sàng"
              >
                <Layers size={13} />
                <span>Bản đồ Nhiệt</span>
              </button>
            </div>
          </div>

          {/* Organ Systems Filter Tabs */}
          <div className="system-filter-tabs-row" role="tablist" aria-label="Lọc theo hệ cơ quan">
            {ORGAN_SYSTEMS.map((sys) => {
              const Icon = sys.icon;
              const isActive = selectedSystem === sys.id;
              return (
                <button
                  key={sys.id}
                  type="button"
                  className={`system-tab-btn ${isActive ? 'active' : ''}`}
                  onClick={() => setSelectedSystem(sys.id)}
                >
                  <Icon size={12} />
                  <span>{sys.label}</span>
                </button>
              );
            })}
          </div>

          {/* Quick Organ Selector Chips */}
          <div className="organ-quick-chips-bar" role="tablist" aria-label="Chọn nhanh cơ quan">
            {normalizedOrgans.map((organ) => {
              const isSelected = selectedOrganId === organ.id;
              const statusColor = getStatusColor(organ.status, organ.health_score);
              const isSystemMember =
                selectedSystem === 'all' ||
                ORGAN_SYSTEMS.find((s) => s.id === selectedSystem)?.organIds?.includes(organ.id);

              if (!isSystemMember) return null;

              return (
                <button
                  key={organ.id}
                  type="button"
                  className={`organ-chip-btn ${isSelected ? 'active' : ''}`}
                  style={{ '--chip-color': statusColor }}
                  onClick={() => setSelectedOrganId(organ.id)}
                  title={`Xem chi tiết: ${organ.vietnamese_name}`}
                >
                  <span className="chip-status-dot" />
                  <span>{organ.vietnamese_name}</span>
                </button>
              );
            })}
          </div>

          <div className="human-canvas-wrapper">
            {/* Clinical studio background */}
            <div className="clinical-grid-backdrop" />

            {/* Inner Container keeping precise Aspect Ratio */}
            <div className={`human-canvas-inner-ratio ${modelViewMode}`}>
              {/* Detailed 3D Anatomical Human Model Image */}
              <img
                src="/static/assets/human_anatomical_twin.jpg"
                alt="3D Anatomical Digital Twin Model"
                className="human-3d-model-img"
                onError={(e) => {
                  if (!e.currentTarget.dataset.fallbackTried) {
                    e.currentTarget.dataset.fallbackTried = 'true';
                    e.currentTarget.src = '/assets/human_anatomical_twin.jpg';
                  }
                }}
              />

              {/* Active Organ Focus Halo (Clean subtle ring on the body, NO floating card) */}
              {activeOrgan?.coordinates && (
                <div
                  className="organ-focus-indicator"
                  style={{
                    left: `${activeOrgan.coordinates.x}%`,
                    top: `${activeOrgan.coordinates.y}%`,
                    '--indicator-color': getStatusColor(activeOrgan.status, activeOrgan.health_score),
                  }}
                >
                  <div className="focus-concentric-circle" />
                </div>
              )}

              {/* Hotspots: Precision Clinical Organ Pointer Dots */}
              {normalizedOrgans.map((organ) => {
                const isSelected = selectedOrganId === organ.id;
                const isHovered = hoveredOrganId === organ.id;
                const statusColor = getStatusColor(organ.status, organ.health_score);
                const isAlert = organ.status === 'adverse_reaction' || organ.status === 'critical';
                const isSystemMember =
                  selectedSystem === 'all' ||
                  ORGAN_SYSTEMS.find((s) => s.id === selectedSystem)?.organIds?.includes(organ.id);

                return (
                  <div
                    key={organ.id}
                    className={`clinical-organ-pin ${isSelected ? 'selected' : ''} ${isHovered ? 'hovered' : ''} ${isAlert ? 'is-alert' : ''} ${!isSystemMember ? 'dimmed' : ''}`}
                    style={{
                      left: `${organ.coordinates?.x ?? 50}%`,
                      top: `${organ.coordinates?.y ?? 50}%`,
                      '--organ-color': statusColor,
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
                    {/* Tooltip badge appears ONLY when hovered, keeping the human body completely clear of any cards */}
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

          {/* Quick Body Status Footer */}
          <div className="silhouette-footer-legend">
            <div className="legend-item"><span className="legend-dot normal" /> Ổn định (90-100%)</div>
            <div className="legend-item"><span className="legend-dot monitor" /> Cần theo dõi (70-89%)</div>
            <div className="legend-item"><span className="legend-dot inflamed" /> Đang viêm (50-69%)</div>
            <div className="legend-item"><span className="legend-dot alert" /> Báo động / ADR (&lt;50%)</div>
          </div>
        </section>

        {/* Right Column: Detailed Organ Inspector Card & Live Controls */}
        <div className="inspector-column">
          {/* Clinical ADR Safety Guardrail Emergency Banner */}
          {(profile.adr_alert?.active || profile.safe_guardrail_alert || activeOrgan?.status === 'adverse_reaction') && (
            <div className="clinical-adr-emergency-box">
              <div className="adr-box-header">
                <div className="adr-title-wrap">
                  <ShieldAlert size={20} className="adr-alert-icon" />
                  <div>
                    <h4>CẢNH BÁO AN TOÀN DƯỢC LÂM SÀNG (SAFETY GUARDRAIL / ADR)</h4>
                    <span className="adr-subtitle">Phát hiện phản ứng có hại của thuốc hoặc dấu hiệu cờ đỏ cấp tính</span>
                  </div>
                </div>
                <span className="adr-critical-badge">BÁO ĐỘNG ĐỎ</span>
              </div>
              <div className="adr-box-body">
                <div className="adr-instruction-row">
                  <div className="adr-action-badge stop">CHỈ THỊ: DỪNG THUỐC GÂY HẠI</div>
                  <p className="adr-text stop-text">
                    {profile.adr_alert?.action_directive || profile.safe_guardrail_alert?.required_action || 'DỪNG NGAY Ibuprofen / Thuốc kháng viêm NSAID'}
                  </p>
                </div>
                <div className="adr-instruction-row">
                  <div className="adr-action-badge safe">PHÁC ĐỒ THAY THẾ AN TOÀN</div>
                  <p className="adr-text safe-text">
                    {profile.adr_alert?.safe_alternative || profile.safe_guardrail_alert?.alternative_recommendation || 'Dùng Esomeprazole (Nexium 40mg) / Phosphalugel bảo vệ niêm mạc; thay bằng Paracetamol nếu cần hạ sốt.'}
                  </p>
                </div>
              </div>
              <div className="adr-box-footer">
                <button
                  type="button"
                  className="adr-emergency-115-btn"
                  onClick={() => {
                    onNavigate?.('navigation');
                    window.dispatchEvent(
                      new CustomEvent('medguard:navigate', {
                        detail: { view: 'navigation', emergency: true, reason: 'adr_stomach_ibuprofen' },
                      })
                    );
                  }}
                >
                  <Navigation size={16} />
                  <span>Chuyển sang Buồng lái Chỉ đường Cấp cứu 3D 115</span>
                  <ArrowRight size={16} />
                </button>
              </div>
            </div>
          )}

          {/* Ma trận 9 Hệ Cơ Quan Lâm Sàng (Không bị cắt chữ, 2 cột lớn) */}
          <div className="organ-matrix-section">
            <div className="matrix-section-header">
              <div className="matrix-title-group">
                <Activity size={16} style={{ color: '#00e5ff' }} />
                <h4>Ma Trận 9 Hệ Cơ Quan Sinh Học (100% Tiếng Việt)</h4>
              </div>
              <span className="matrix-hint">Nhấp vào thẻ để chọn tiêu điểm</span>
            </div>

            <div className="organ-matrix-9-grid">
              {[
                { id: 'head', name: '1. Não bộ & Thần kinh', icon: Zap },
                { id: 'eyes', name: '2. Mắt & Thị giác', icon: Eye },
                { id: 'ent', name: '3. Tai Mũi Họng', icon: Volume2 },
                { id: 'cardiovascular', name: '4. Tim mạch & Tuần hoàn', icon: Heart },
                { id: 'lungs', name: '5. Phổi & Hô hấp', icon: Droplet },
                { id: 'stomach', name: '6. Dạ Dày & Tiêu Hóa', icon: Flame },
                { id: 'liver', name: '7. Gan & Mật', icon: Activity },
                { id: 'kidneys', name: '8. Thận & Tiết Niệu', icon: Droplet },
                { id: 'spine_joints', name: '9. Cơ Xương Khớp', icon: Layers },
              ].map((sys) => {
                const organData = profile?.organs?.find((o) => o.id === sys.id || (sys.id === 'eyes' && o.id === 'skin')) || {
                  health_score: 95,
                  status: 'normal',
                  vas_pain_score: 0,
                  pain_level: 0,
                };
                const score = organData.health_score ?? 95;
                const vas = organData.vas_pain_score ?? organData.pain_level ?? 0;
                const statusColor = getStatusColor(organData.status, score);
                const isSelected = (selectedOrganId === sys.id) || (sys.id === 'eyes' && selectedOrganId === 'skin');
                const IconComponent = sys.icon;

                return (
                  <div
                    key={sys.id}
                    className={`matrix-organ-card ${isSelected ? 'selected' : ''}`}
                    onClick={() => setSelectedOrganId(sys.id === 'eyes' ? 'skin' : sys.id)}
                    style={{ '--organ-color': statusColor }}
                  >
                    <div className="matrix-card-top">
                      <div className="matrix-icon-badge" style={{ backgroundColor: `${statusColor}22`, color: statusColor }}>
                        <IconComponent size={16} />
                      </div>
                      <span className="matrix-organ-name">{sys.name}</span>
                    </div>

                    <div className="matrix-card-bars">
                      <div className="matrix-bar-row">
                        <span className="bar-label">Sức khoẻ:</span>
                        <div className="matrix-progress-track">
                          <div className="matrix-progress-fill" style={{ width: `${score}%`, backgroundColor: statusColor }} />
                        </div>
                        <strong className="bar-num" style={{ color: statusColor }}>{score}%</strong>
                      </div>

                      <div className="matrix-bar-row vas-row">
                        <span className="bar-label">Thang VAS:</span>
                        <div className="matrix-vas-track">
                          <div className="matrix-vas-fill" style={{ width: `${(vas / 10) * 100}%`, backgroundColor: vas >= 7 ? '#ef4444' : vas >= 4 ? '#f59e0b' : '#10b981' }} />
                        </div>
                        <strong className="bar-num vas-num">{vas}/10</strong>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {activeOrgan && (
            <div
              className={`organ-inspector-card ${activeOrgan.status === 'adverse_reaction' ? 'has-adr' : ''}`}
              style={{ '--organ-accent': getStatusColor(activeOrgan.status, activeOrgan.health_score) }}
            >
              <div className="inspector-header">
                <div className="inspector-organ-title">
                  <div className="organ-icon-circle">
                    {activeOrgan.id === 'head' && <Zap size={20} />}
                    {activeOrgan.id === 'ent' && <Eye size={20} />}
                    {activeOrgan.id === 'cardiovascular' && <Heart size={20} />}
                    {activeOrgan.id === 'lungs' && <Droplet size={20} />}
                    {activeOrgan.id === 'stomach' && <Flame size={20} />}
                    {activeOrgan.id === 'liver' && <Activity size={20} />}
                    {activeOrgan.id === 'kidneys' && <Droplet size={20} />}
                    {activeOrgan.id === 'spine_joints' && <Activity size={20} />}
                    {activeOrgan.id === 'skin' && <Shield size={20} />}
                  </div>
                  <div>
                    <h3>{activeOrgan.vietnamese_name}</h3>
                    <span className="organ-en-name">{activeOrgan.name}</span>
                  </div>
                </div>

                <div className="status-badge-wrap">
                  <span className={`status-pill ${activeOrgan.status}`}>
                    {getStatusBadgeText(activeOrgan.status)}
                  </span>
                </div>
              </div>

              {/* Quick Clinical Actions Bar */}
              <div className="organ-quick-actions-bar">
                <button
                  type="button"
                  className="organ-action-btn consult-btn"
                  onClick={() => {
                    onNavigate?.('chat');
                    window.dispatchEvent(
                      new CustomEvent('medguard:navigate', {
                        detail: {
                          view: 'chat',
                          message: `Tư vấn AI chuyên sâu về tình trạng cơ quan: ${activeOrgan.vietnamese_name} (${activeOrgan.status === 'adverse_reaction' ? 'đang có phản ứng bất lợi' : activeOrgan.status === 'inflamed' ? 'đang bị viêm' : 'cần đánh giá rủi ro tương lai'}).`,
                        },
                      })
                    );
                  }}
                  title="Chuyển sang Chat và hỏi AI về cơ quan này"
                >
                  <MessageSquare size={14} />
                  <span>Tư vấn AI</span>
                </button>

                <button
                  type="button"
                  className="organ-action-btn declare-btn"
                  onClick={() => {
                    setInputMessage(`Cập nhật triệu chứng tại ${activeOrgan.vietnamese_name}: `);
                    const el = document.querySelector('.console-text-input');
                    if (el) {
                      el.focus();
                      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                  }}
                  title={`Khai báo triệu chứng cho cơ quan ${activeOrgan.vietnamese_name}`}
                >
                  <Plus size={14} />
                  <span>Khai báo triệu chứng</span>
                </button>

                <button
                  type="button"
                  className="organ-action-btn recover-btn"
                  disabled={evaluating || activeOrgan.status === 'normal'}
                  onClick={() => {
                    handleEvaluateProgress(`Hôm nay triệu chứng tại ${activeOrgan.vietnamese_name} của tôi đã thuyên giảm hoàn toàn, không còn cảm giác đau hay khó chịu.`);
                  }}
                  title="Cập nhật báo cáo cơ quan này đã bình phục"
                >
                  <CheckCircle2 size={14} />
                  <span>Báo đã khỏi</span>
                </button>

                <button
                  type="button"
                  className="organ-action-btn nav-btn"
                  onClick={() => {
                    onNavigate?.('navigation');
                    window.dispatchEvent(
                      new CustomEvent('medguard:navigate', {
                        detail: { view: 'navigation', organ: activeOrgan.vietnamese_name },
                      })
                    );
                  }}
                  title="Chuyển sang bản đồ chỉ đường đến cơ sở y tế"
                >
                  <Navigation size={14} />
                  <span>Chỉ đường CSYT</span>
                </button>
              </div>

              {/* Organ Health Metrics Grid */}
              <div className="organ-metrics-row">
                <div className="metric-box">
                  <span className="metric-label">Điểm sức khoẻ</span>
                  <div className="metric-value-row">
                    <strong style={{ color: getStatusColor(activeOrgan.status, activeOrgan.health_score) }}>
                      {activeOrgan.health_score}
                    </strong>
                    <span className="metric-unit">/100</span>
                  </div>
                  <div className="score-mini-bar">
                    <div
                      className="score-mini-fill"
                      style={{
                        width: `${activeOrgan.health_score}%`,
                        backgroundColor: getStatusColor(activeOrgan.status, activeOrgan.health_score),
                      }}
                    />
                  </div>
                </div>

                <div className="metric-box">
                  <span className="metric-label">Mức độ đau (0-10)</span>
                  <div className="metric-value-row">
                    <strong className={activeOrgan.pain_level >= 5 ? 'pain-high' : ''}>
                      {activeOrgan.pain_level}
                    </strong>
                    <span className="metric-unit">
                      {activeOrgan.pain_level === 0 ? 'Không đau' : activeOrgan.pain_level <= 3 ? 'Nhẹ' : activeOrgan.pain_level <= 6 ? 'Vừa' : 'Dữ dội'}
                    </span>
                  </div>
                  <span className="metric-sub">Thang đo lâm sàng VAS</span>
                </div>

                <div className="metric-box">
                  <span className="metric-label">Mức độ viêm</span>
                  <div className="metric-value-row">
                    <strong className="text-capital">{activeOrgan.inflammation_level}</strong>
                  </div>
                  <span className="metric-sub">Đánh giá phản ứng mô</span>
                </div>
              </div>

              {/* Symptoms Recorded */}
              {activeOrgan.symptoms && activeOrgan.symptoms.length > 0 && (
                <div className="inspector-section">
                  <span className="section-title">Triệu chứng ghi nhận tại vị trí này:</span>
                  <div className="symptom-tag-list">
                    {activeOrgan.symptoms.map((s, idx) => (
                      <span key={idx} className="symptom-tag-item">
                        <AlertCircle size={12} />
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Warning or ADR callout */}
              {activeOrgan.warning && (
                <div className="inspector-warning-box">
                  <AlertTriangle size={16} />
                  <span>{activeOrgan.warning}</span>
                </div>
              )}

              {/* Contraindicated Actions */}
              {activeOrgan.contraindicated_actions && activeOrgan.contraindicated_actions.length > 0 && (
                <div className="contra-actions-box">
                  <div className="contra-title">
                    <X size={14} />
                    <span>HẠN CHẾ TIẾP TỤC / CHỐNG CHỈ ĐỊNH:</span>
                  </div>
                  <ul>
                    {activeOrgan.contraindicated_actions.map((act, idx) => (
                      <li key={idx}><strong>{act}</strong></li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Clinical Notes & Recommendations */}
              <div className="inspector-section notes-section">
                <span className="section-title">Ghi chú lâm sàng hiện tại:</span>
                <p className="clinical-notes-p">{activeOrgan.clinical_notes || 'Cơ quan ở trạng thái ổn định bình thường.'}</p>
              </div>

              {/* FUTURE RISK PROGNOSIS & PREVENTIVE VACCINATION CARD */}
              {activeOrgan.future_risk && (
                <div className="future-risk-prognosis-card">
                  <div className="risk-card-top">
                    <div className="risk-title-badge-group">
                      <ShieldAlert size={16} className={`risk-level-icon ${activeOrgan.future_risk.risk_level}`} />
                      <div>
                        <span className="risk-section-eyebrow">DỰ BÁO RỦI RO SỨC KHOẺ TƯƠNG LAI</span>
                        <h4 className="risk-prognosis-title">{activeOrgan.future_risk.risk_title}</h4>
                      </div>
                    </div>
                    <div className="risk-badges-cluster">
                      <span className={`risk-level-tag ${activeOrgan.future_risk.risk_level}`}>
                        {activeOrgan.future_risk.risk_level === 'high'
                          ? 'RỦI RO CAO'
                          : activeOrgan.future_risk.risk_level === 'moderate'
                          ? 'RỦI RO TRUNG BÌNH'
                          : 'RỦI RO THẤP'}
                      </span>
                      <span className="risk-timeframe-tag">
                        <Clock size={11} />
                        <span>{activeOrgan.future_risk.timeframe}</span>
                      </span>
                    </div>
                  </div>

                  {/* Vaccination & Preventive Shield Gap */}
                  {activeOrgan.future_risk.vaccination_status && (
                    <div className="vaccine-status-callout">
                      <Syringe size={16} className="syringe-accent-icon" />
                      <div>
                        <strong>Tình trạng Tiêm chủng & Miễn dịch:</strong>
                        <p>{activeOrgan.future_risk.vaccination_status}</p>
                      </div>
                    </div>
                  )}

                  {/* Latent Disease Mechanism */}
                  <div className="risk-body-block">
                    <span className="block-subtitle">Cơ chế rủi ro tiềm tàng:</span>
                    <p className="block-text">{activeOrgan.future_risk.latent_risk_description}</p>
                  </div>

                  {/* Visual Progression Chain */}
                  <div className="risk-progression-chain">
                    <span className="block-subtitle">Chuỗi tiến triển bệnh sinh nếu không phòng ngừa:</span>
                    <div className="progression-flow-items">
                      {activeOrgan.future_risk.potential_progression.split('->').map((step, sIdx, arr) => (
                        <div key={sIdx} className="prog-step-item">
                          <span className={`step-text ${sIdx === arr.length - 1 ? 'fatal-step' : ''}`}>{step.trim()}</span>
                          {sIdx < arr.length - 1 && <ChevronRight size={13} className="step-arrow" />}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Preventive Action Protocol */}
                  {activeOrgan.future_risk.preventive_recommendations?.length > 0 && (
                    <div className="risk-recs-block">
                      <span className="block-subtitle">Phác đồ can thiệp & Kế hoạch Tiêm chủng:</span>
                      <ul className="recs-list">
                        {activeOrgan.future_risk.preventive_recommendations.map((rec, rIdx) => (
                          <li key={rIdx}>
                            <CheckCircle2 size={14} className="rec-check-icon" />
                            <span>{rec}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Screening Tests */}
                  {activeOrgan.future_risk.screening_tests?.length > 0 && (
                    <div className="risk-screening-block">
                      <span className="block-subtitle">Xét nghiệm & Tầm soát định kỳ:</span>
                      <div className="screening-chips-flow">
                        {activeOrgan.future_risk.screening_tests.map((test, tIdx) => (
                          <span key={tIdx} className="screening-chip-badge">
                            <FileBadge size={12} />
                            <span>{test}</span>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Action buttons on Future Risk */}
                  <div className="risk-actions-footer">
                    <button
                      type="button"
                      className="risk-btn-primary"
                      onClick={() => {
                        onNavigate?.('chat');
                        window.dispatchEvent(
                          new CustomEvent('medguard:navigate', {
                            detail: {
                              view: 'chat',
                              message: `Tư vấn kế hoạch tiêm phòng vắc-xin và lộ trình tầm soát sớm rủi ro tương lai cho cơ quan: ${activeOrgan.vietnamese_name} (${activeOrgan.future_risk.risk_title}). Cụ thể: ${activeOrgan.future_risk.vaccination_status || ''}`,
                            },
                          })
                        );
                      }}
                    >
                      <Syringe size={14} />
                      <span>Tư vấn Tiêm chủng & Phòng ngừa</span>
                    </button>
                    <button
                      type="button"
                      className="risk-btn-secondary"
                      onClick={() => {
                        onNotify?.(`Đã thêm khuyến nghị tầm soát định kỳ cơ quan ${activeOrgan.vietnamese_name} vào lịch y bạ điện tử.`);
                      }}
                    >
                      <CalendarCheck size={14} />
                      <span>Lên lịch Tầm soát Y tế</span>
                    </button>
                  </div>
                </div>
              )}

              {/* Related Medications */}
              {activeOrgan.related_medications && activeOrgan.related_medications.length > 0 && (
                <div className="inspector-section meds-section">
                  <span className="section-title">Thuốc liên quan cơ quan này:</span>
                  <div className="meds-badge-row">
                    {activeOrgan.related_medications.map((m, idx) => (
                      <span key={idx} className="med-badge">
                        <Pill size={12} />
                        {m}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Conversational Clinical Care Guidance */}
          <div className="conversational-care-card">
            <div className="care-card-header">
              <MessageSquare size={16} className="care-icon" />
              <h4>Khai báo Triệu chứng qua Hội thoại</h4>
            </div>
            <p className="care-card-desc">
              Khi phát sinh triệu chứng mới, thuyên giảm hoặc gặp phản ứng phụ sau khi uống thuốc, bạn chỉ cần nhắn trực tiếp trong phần Chat. Bác sĩ AI sẽ tự động phân tích và cập nhật vào hồ sơ giải phẫu học này.
            </p>
            <button
              type="button"
              className="care-card-chat-btn"
              onClick={() => onNavigate?.('chat')}
            >
              <MessageSquare size={14} />
              <span>Nhắn tin với Bác sĩ AI ngay</span>
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* Bottom Section: Overall Health Dashboard, Risk Matrix & Recovery Timeline */}
      <section className="overall-health-dashboard">
        <div className="dashboard-tabs-bar" role="tablist">
          <button
            role="tab"
            aria-selected={activeTab === 'future_risks'}
            className={`dash-tab ${activeTab === 'future_risks' ? 'active' : ''}`}
            onClick={() => setActiveTab('future_risks')}
          >
            <ShieldAlert size={16} />
            <span>Ma trận Dự báo Rủi ro & Kế hoạch Tiêm chủng Phòng ngừa</span>
          </button>
          <button
            role="tab"
            aria-selected={activeTab === 'overview'}
            className={`dash-tab ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            <Activity size={16} />
            <span>Tổng quan Sinh hiệu & Điểm Sức khoẻ</span>
          </button>
          <button
            role="tab"
            aria-selected={activeTab === 'timeline'}
            className={`dash-tab ${activeTab === 'timeline' ? 'active' : ''}`}
            onClick={() => setActiveTab('timeline')}
          >
            <Clock size={16} />
            <span>Thời gian Thăm dò & Hồi phục ({profile?.timeline?.length || 0})</span>
          </button>
          <button
            role="tab"
            aria-selected={activeTab === 'meds'}
            className={`dash-tab ${activeTab === 'meds' ? 'active' : ''}`}
            onClick={() => setActiveTab('meds')}
          >
            <Pill size={16} />
            <span>Đơn thuốc & Phác đồ An toàn ({profile?.active_medications?.length || 0})</span>
          </button>
        </div>

        {/* Tab: Future Risk Matrix & Immunization Schedule */}
        {activeTab === 'future_risks' && (
          <div className="risk-matrix-tab-content">
            {/* Top Intelligence Alert Banner */}
            <div className="risk-intelligence-banner">
              <div className="banner-icon-side">
                <ShieldAlert size={28} className="shield-pulse-icon" />
              </div>
              <div className="banner-content-side">
                <h3>Bản Đồ Dự Báo Rủi Ro Sức Khoẻ Dài Hạn & Kế Hoạch Tiêm Chủng Chủ Động</h3>
                <p>
                  Hệ thống AI phân tích toàn diện dựa trên tiền sử tiêm chủng, tương tác thuốc đang dùng và tình trạng các cơ quan.
                  Việc chủ động tiêm phòng sớm (đặc biệt vắc-xin Viêm gan B) và tầm soát định kỳ giúp ngăn ngừa tới <strong>95%</strong> nguy cơ xơ gan và ung thư tế bào gan (HCC) trong 5-10 năm tới.
                </p>
              </div>
            </div>

            {/* Critical Priority Risk Cards */}
            <div className="future-risk-cards-grid">
              {/* Card 1: Liver & Hepatitis B -> Cancer */}
              <div className="risk-matrix-card priority-high">
                <div className="matrix-card-header">
                  <div className="organ-tag">
                    <Activity size={14} />
                    <span>Gan & Chuyển hoá</span>
                  </div>
                  <span className="risk-badge-pill high">RỦI RO CAO (3 - 10 NĂM)</span>
                </div>
                <h4 className="matrix-card-title">Nguy cơ HBV mạn tính → Xơ gan → Ung thư tế bào gan (HCC)</h4>
                <div className="matrix-vaccine-status">
                  <Syringe size={14} />
                  <span><strong>Thiếu hụt phòng hộ:</strong> Chưa tiêm vắc-xin Viêm gan B (Kháng thể Anti-HBs âm tính)</span>
                </div>
                <p className="matrix-desc">
                  Virus Viêm gan B lây âm thầm không có triệu chứng ban đầu. Sau 5-10 năm nhiễm mạn tính sẽ dẫn đến xơ gan và ung thư biểu mô gan HCC nguy cơ tử vong cao.
                </p>
                <div className="matrix-action-box">
                  <strong>Khuyến cáo can thiệp y tế:</strong>
                  <ul>
                    <li>Tiêm ngay vắc-xin Viêm gan B phác đồ 3 mũi (Tháng 0, 1, 6).</li>
                    <li>Định lượng kháng thể Anti-HBs sau mũi 3 bảo đảm đạt &gt; 10 mIU/mL.</li>
                    <li>Siêu âm Doppler gan & Xét nghiệm men gan, AFP mỗi 6 tháng/lần.</li>
                  </ul>
                </div>
                <div className="matrix-card-footer">
                  <button
                    type="button"
                    className="matrix-btn primary"
                    onClick={() => {
                      setSelectedOrganId('liver');
                      onNavigate?.('chat');
                      window.dispatchEvent(
                        new CustomEvent('medguard:navigate', {
                          detail: {
                            view: 'chat',
                            message: 'Tư vấn tiêm phòng vắc-xin Viêm gan B đủ 3 mũi và phác đồ tầm soát ung thư tế bào gan HCC.',
                          },
                        })
                      );
                    }}
                  >
                    <Syringe size={13} />
                    <span>Tư vấn Tiêm phòng HBV</span>
                  </button>
                  <button
                    type="button"
                    className="matrix-btn secondary"
                    onClick={() => setSelectedOrganId('liver')}
                  >
                    <span>Xem định vị Gan</span>
                  </button>
                </div>
              </div>

              {/* Card 2: Stomach & HP / NSAID abuse */}
              <div className="risk-matrix-card priority-high">
                <div className="matrix-card-header">
                  <div className="organ-tag">
                    <Flame size={14} />
                    <span>Dạ dày & Tiêu hoá</span>
                  </div>
                  <span className="risk-badge-pill high">RỦI RO CAO (1 - 3 NĂM)</span>
                </div>
                <h4 className="matrix-card-title">Viêm loét dạ dày tá tràng thủng → Dị sản ruột & Ung thư dạ dày</h4>
                <div className="matrix-vaccine-status">
                  <FileBadge size={14} />
                  <span><strong>Thiếu hụt phòng hộ:</strong> Chưa kiểm tra vi khuẩn HP, nguy cơ tổn thương do thuốc NSAID</span>
                </div>
                <p className="matrix-desc">
                  Lạm dụng thuốc giảm đau kháng viêm khi đói kết hợp nhiễm vi khuẩn Helicobacter pylori âm thầm làm mòn lớp chất nhầy bảo vệ niêm mạc, dẫn đến ổ loét sâu và dị sản ác tính.
                </p>
                <div className="matrix-action-box">
                  <strong>Khuyến cáo can thiệp y tế:</strong>
                  <ul>
                    <li>Làm xét nghiệm test hơi thở C13/C14 hoặc nội soi tầm soát vi khuẩn HP.</li>
                    <li>Tuyệt đối ngừng thuốc giảm đau chống viêm khi xuất hiện cồn cào đau thượng vị.</li>
                    <li>Dùng thuốc ức chế bơm proton (PPI) bảo vệ niêm mạc khi có chỉ định bác sĩ.</li>
                  </ul>
                </div>
                <div className="matrix-card-footer">
                  <button
                    type="button"
                    className="matrix-btn primary"
                    onClick={() => {
                      setSelectedOrganId('stomach');
                      onNavigate?.('chat');
                      window.dispatchEvent(
                        new CustomEvent('medguard:navigate', {
                          detail: {
                            view: 'chat',
                            message: 'Tư vấn tầm soát vi khuẩn Helicobacter pylori (HP) và phòng ngừa viêm loét dạ dày tá tràng do thuốc.',
                          },
                        })
                      );
                    }}
                  >
                    <FileBadge size={13} />
                    <span>Tư vấn Tầm soát HP</span>
                  </button>
                  <button
                    type="button"
                    className="matrix-btn secondary"
                    onClick={() => setSelectedOrganId('stomach')}
                  >
                    <span>Xem định vị Dạ dày</span>
                  </button>
                </div>
              </div>

              {/* Card 3: Cardiovascular */}
              <div className="risk-matrix-card priority-mod">
                <div className="matrix-card-header">
                  <div className="organ-tag">
                    <Heart size={14} />
                    <span>Tim mạch & Tuần hoàn</span>
                  </div>
                  <span className="risk-badge-pill mod">RỦI RO TRUNG BÌNH (5 - 10 NĂM)</span>
                </div>
                <h4 className="matrix-card-title">Xơ vữa động mạch vành → Cơn đau thắt ngực & Nhồi máu cơ tim (MACE)</h4>
                <div className="matrix-vaccine-status">
                  <HeartPulse size={14} />
                  <span><strong>Dấu hiệu cảnh báo:</strong> Huyết áp 122/80 mmHg ngưỡng tiền tăng huyết áp, chưa tiêm cúm</span>
                </div>
                <p className="matrix-desc">
                  Thói quen ít vận động, áp lực công việc và nhiễm cúm mùa lặp lại gây phản ứng viêm thành mạch, tích tụ mảng xơ vữa làm hẹp lòng mạch vành.
                </p>
                <div className="matrix-action-box">
                  <strong>Khuyến cáo can thiệp y tế:</strong>
                  <ul>
                    <li>Tiêm vắc-xin Cúm mùa hàng năm (giảm 20-30% nguy cơ nhồi máu cơ tim).</li>
                    <li>Tập thể dục aerobic tối thiểu 150 phút/tuần, giảm lượng muối ăn &lt; 5g/ngày.</li>
                    <li>Đo điện tâm đồ ECG và xét nghiệm mỡ máu Lipid panel định kỳ hàng năm.</li>
                  </ul>
                </div>
                <div className="matrix-card-footer">
                  <button
                    type="button"
                    className="matrix-btn primary"
                    onClick={() => setSelectedOrganId('cardiovascular')}
                  >
                    <span>Xem chi tiết Tim mạch</span>
                  </button>
                </div>
              </div>

              {/* Card 4: Lungs */}
              <div className="risk-matrix-card priority-mod">
                <div className="matrix-card-header">
                  <div className="organ-tag">
                    <Droplet size={14} />
                    <span>Phổi & Hô hấp</span>
                  </div>
                  <span className="risk-badge-pill mod">RỦI RO TRUNG BÌNH (2 - 5 NĂM)</span>
                </div>
                <h4 className="matrix-card-title">Viêm phế quản mạn & Bội nhiễm vi khuẩn Phế cầu (Streptococcus pneumoniae)</h4>
                <div className="matrix-vaccine-status">
                  <Syringe size={14} />
                  <span><strong>Thiếu hụt phòng hộ:</strong> Chưa tiêm vắc-xin Phế cầu (Prevenar 13 / Pneumovax 23)</span>
                </div>
                <p className="matrix-desc">
                  Đường thở đang tổn thương do virus cúm tạo điều kiện cho vi khuẩn phế cầu xâm lấn sâu vào phế nang, gây viêm phổi thùy và suy hô hấp cấp tính.
                </p>
                <div className="matrix-action-box">
                  <strong>Khuyến cáo can thiệp y tế:</strong>
                  <ul>
                    <li>Tiêm phòng 1 liều vắc-xin Phế cầu 13 chủng để tạo miễn dịch bảo vệ phế nang.</li>
                    <li>Đeo khẩu trang lọc bụi mịn chuẩn N95 khi di chuyển ngoài đường phố.</li>
                    <li>Đo chức năng hô hấp (Hô hấp ký Spirometry) và chụp X-quang phổi định kỳ.</li>
                  </ul>
                </div>
                <div className="matrix-card-footer">
                  <button
                    type="button"
                    className="matrix-btn primary"
                    onClick={() => setSelectedOrganId('lungs')}
                  >
                    <span>Xem chi tiết Phổi</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Comprehensive Preventive Immunization Schedule Table */}
            <div className="immunization-schedule-section">
              <div className="section-title-wrap">
                <Syringe size={18} />
                <div>
                  <h4>Bảng Kiểm Tiêm Chủng Phòng Ngừa Cho Người Lớn (Adult Immunization Schedule)</h4>
                  <span className="section-subtitle">Phác đồ phòng hộ chủ động theo khuyến cáo của Bộ Y tế & CDC</span>
                </div>
              </div>

              <div className="vaccine-table-responsive">
                <table className="vaccine-checklist-table">
                  <thead>
                    <tr>
                      <th>Vắc-xin & Chỉ định</th>
                      <th>Tình trạng cá nhân</th>
                      <th>Rủi ro phòng ngừa được</th>
                      <th>Phác đồ khuyến nghị</th>
                      <th>Hành động y tế</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="row-urgent">
                      <td>
                        <strong>Vắc-xin Viêm gan B (Engerix-B / Euvax-B)</strong>
                        <span className="table-subtext">20mcg/1ml tiêm bắp cơ delta</span>
                      </td>
                      <td>
                        <span className="table-status-pill urgent">CẦN TIÊM PHÒNG</span>
                        <span className="table-subtext">Anti-HBs &lt; 10 mIU/mL</span>
                      </td>
                      <td>
                        <strong>Ngừa 95% nguy cơ Xơ gan & Ung thư gan (HCC)</strong>
                        <p className="table-desc">Ngăn ngừa nhiễm virus HBV mạn tính và đột biến tế bào nhu mô gan.</p>
                      </td>
                      <td>
                        <strong>3 mũi chuẩn: Tháng 0, 1, 6</strong>
                        <span className="table-subtext">Định lượng kháng thể sau mũi 3</span>
                      </td>
                      <td>
                        <button
                          type="button"
                          className="table-action-btn primary"
                          onClick={() => {
                            onNavigate?.('chat');
                            window.dispatchEvent(
                              new CustomEvent('medguard:navigate', {
                                detail: {
                                  view: 'chat',
                                  message: 'Hướng dẫn đăng ký tiêm phòng vắc-xin Viêm gan B và xét nghiệm kháng thể Anti-HBs gần nhất.',
                                },
                              })
                            );
                          }}
                        >
                          Đăng ký tiêm phòng HBV
                        </button>
                      </td>
                    </tr>

                    <tr className="row-recommended">
                      <td>
                        <strong>Vắc-xin Phế cầu 13 chủng (Prevenar 13)</strong>
                        <span className="table-subtext">Vắc-xin cộng hợp phế cầu khuẩn</span>
                      </td>
                      <td>
                        <span className="table-status-pill warn">KHUYẾN NGHỊ</span>
                        <span className="table-subtext">Chưa từng tiêm</span>
                      </td>
                      <td>
                        <strong>Phòng viêm phổi thùy, viêm màng não do phế cầu</strong>
                        <p className="table-desc">Đặc biệt quan trọng khi đường thở đang có tổn thương do viêm cúm mùa.</p>
                      </td>
                      <td>
                        <strong>1 liều duy nhất</strong>
                        <span className="table-subtext">Hiệu lực bảo vệ dài hạn</span>
                      </td>
                      <td>
                        <button
                          type="button"
                          className="table-action-btn"
                          onClick={() => {
                            onNavigate?.('chat');
                            window.dispatchEvent(
                              new CustomEvent('medguard:navigate', {
                                detail: {
                                  view: 'chat',
                                  message: 'Tư vấn tiêm phòng vắc-xin Phế cầu Prevenar 13 bảo vệ phổi và đường hô hấp.',
                                },
                              })
                            );
                          }}
                        >
                          Tư vấn vắc-xin Phế cầu
                        </button>
                      </td>
                    </tr>

                    <tr className="row-routine">
                      <td>
                        <strong>Vắc-xin Cúm mùa Tứ giá (Vaxigrip Tetra)</strong>
                        <span className="table-subtext">Chống 4 chủng A/H1N1, A/H3N2, B/Yamagata, B/Victoria</span>
                      </td>
                      <td>
                        <span className="table-status-pill routine">TIÊM NHẮC ĐỊNH KỲ</span>
                        <span className="table-subtext">Mùa dịch cúm hiện tại</span>
                      </td>
                      <td>
                        <strong>Giảm 80% cúm nặng & 30% biến cố tim mạch</strong>
                        <p className="table-desc">Giảm nguy cơ bão cytokine và viêm cơ tim thứ phát do virus.</p>
                      </td>
                      <td>
                        <strong>1 mũi tiêm nhắc mỗi năm</strong>
                        <span className="table-subtext">Nên tiêm trước đỉnh dịch mùa đông</span>
                      </td>
                      <td>
                        <button
                          type="button"
                          className="table-action-btn"
                          onClick={() => {
                            onNotify?.('Đã lưu lịch nhắc tiêm vắc-xin Cúm mùa định kỳ vào hồ sơ.');
                          }}
                        >
                          Lưu lịch nhắc hàng năm
                        </button>
                      </td>
                    </tr>

                    <tr className="row-routine">
                      <td>
                        <strong>Vắc-xin Uốn ván - Bạch hầu - Ho gà (Tdap)</strong>
                        <span className="table-subtext">Boostrix / Adacel</span>
                      </td>
                      <td>
                        <span className="table-status-pill ok">ℹ️ THEO DÕI ĐỊNH KỲ</span>
                        <span className="table-subtext">Tiền sử đã tiêm cơ bản</span>
                      </td>
                      <td>
                        <strong>Phòng suy hô hấp do ho gà và co giật uốn ván</strong>
                        <p className="table-desc">Duy trì nồng độ kháng thể bảo vệ trước độc tố vi khuẩn Clostridium tetani.</p>
                      </td>
                      <td>
                        <strong>Tiêm nhắc mỗi 10 năm</strong>
                        <span className="table-subtext">Kiểm tra sau vết thương hở</span>
                      </td>
                      <td>
                        <button
                          type="button"
                          className="table-action-btn ghost"
                          onClick={() => {
                            onNotify?.('Hồ sơ tiêm chủng uốn ván đang ở trạng thái an toàn.');
                          }}
                        >
                          Kiểm tra sổ tiêm
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            {/* Periodic Diagnostic Screening Roadmap */}
            <div className="screening-roadmap-section">
              <div className="section-title-wrap">
                <FileBadge size={18} />
                <div>
                  <h4>Lộ Trình Tầm Soát Sớm Bệnh Lý Mạn Tính & Ung Thư (Early Screening Roadmap)</h4>
                  <span className="section-subtitle">Chủ động phát hiện mầm bệnh ở giai đoạn sớm có thể điều trị triệt căn</span>
                </div>
              </div>

              <div className="screening-roadmap-grid">
                <div className="roadmap-card">
                  <div className="roadmap-header">
                    <Activity size={16} />
                    <h5>Tầm soát Gan Mật & Chuyển hoá</h5>
                  </div>
                  <ul className="roadmap-list">
                    <li><strong>Siêu âm gan Doppler màu:</strong> Định kỳ 6 tháng/lần phát hiện u gan sớm &lt; 2cm.</li>
                    <li><strong>Xét nghiệm AFP & AFP-L3:</strong> Dấu ấn sinh học đặc hiệu ung thư tế bào gan.</li>
                    <li><strong>Cặp xét nghiệm HBsAg & Anti-HBs:</strong> Kiểm tra tải lượng kháng thể và virus.</li>
                  </ul>
                </div>

                <div className="roadmap-card">
                  <div className="roadmap-header">
                    <Flame size={16} />
                    <h5>Tầm soát Dạ Dày & Ống Tiêu Hoá</h5>
                  </div>
                  <ul className="roadmap-list">
                    <li><strong>Test hơi thở C13/C14 UBT:</strong> Độ nhạy 98% phát hiện vi khuẩn HP không xâm lấn.</li>
                    <li><strong>Nội soi thực quản - dạ dày (EGD):</strong> Tầm soát polyp, viêm teo niêm mạc và dị sản.</li>
                    <li><strong>Xét nghiệm Pepsinogen I/II:</strong> Đánh giá mức độ teo niêm mạc dạ dày sớm.</li>
                  </ul>
                </div>

                <div className="roadmap-card">
                  <div className="roadmap-header">
                    <Heart size={16} />
                    <h5>Tầm soát Tim Mạch & Huyết Áp</h5>
                  </div>
                  <ul className="roadmap-list">
                    <li><strong>Bilan Lipid máu toàn phần:</strong> Định lượng LDL-C, Triglyceride, ApoB hàng năm.</li>
                    <li><strong>Điện tâm đồ ECG 12 cần:</strong> Phát hiện thiếu máu cơ tim im lặng và rối loạn nhịp.</li>
                    <li><strong>Siêu âm tim Doppler:</strong> Đo phân suất tống máu EF và độ dày thành tâm thất.</li>
                  </ul>
                </div>

                <div className="roadmap-card">
                  <div className="roadmap-header">
                    <Droplet size={16} />
                    <h5>Tầm soát Hô Hấp & Phế Quản</h5>
                  </div>
                  <ul className="roadmap-list">
                    <li><strong>Đo Hô hấp ký Spirometry:</strong> Đánh giá dung tích sống FVC và chỉ số FEV1.</li>
                    <li><strong>Chụp X-quang phổi thẳng:</strong> Kiểm tra nhu mô phổi, rốn phổi và vòm hoành.</li>
                    <li><strong>Nồng độ FeNO thở ra:</strong> Đánh giá tình trạng viêm dị ứng đường thở phế quản.</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab: Overview & Vitals */}
        {activeTab === 'overview' && (
          <div className="overview-tab-content">
            {/* Health Score SVG Radial Ring & 5 Waveform Vitals Cards */}
            <div className="vitals-hud-grid">
              {/* Overall SVG Radial Ring Score Card */}
              {(() => {
                const currentScore = profile?.overall_health_score ?? 81;
                const ringColor = currentScore >= 80 ? '#10b981' : currentScore >= 50 ? '#06b6d4' : '#ef4444';
                const circumference = 2 * Math.PI * 46;
                const strokeDashoffset = circumference * (1 - currentScore / 100);

                return (
                  <div className="hud-card recovery-score-card">
                    <span className="card-subtitle">Điểm Sức khoẻ Toàn diện</span>
                    <div className="radial-ring-wrap">
                      <svg width="112" height="112" viewBox="0 0 112 112" className="svg-radial-ring">
                        <circle cx="56" cy="56" r="46" className="ring-bg" strokeWidth="8" />
                        <circle
                          cx="56"
                          cy="56"
                          r="46"
                          className="ring-progress"
                          strokeWidth="8"
                          stroke={ringColor}
                          strokeDasharray={circumference}
                          strokeDashoffset={strokeDashoffset}
                          strokeLinecap="round"
                          transform="rotate(-90 56 56)"
                        />
                      </svg>
                      <div className="radial-ring-content">
                        <strong className="ring-score-val" style={{ color: ringColor }}>{currentScore}</strong>
                        <span className="ring-score-max">/100</span>
                      </div>
                    </div>

                    <div className="trend-indicator-row">
                      {currentScore < 50 || profile?.health_trend === 'critical_alert' ? (
                        <span className="trend-badge alert">
                          <TrendingDown size={14} /> Báo động cần can thiệp
                        </span>
                      ) : currentScore < 80 ? (
                        <span className="trend-badge stable">
                          <Activity size={14} /> Cần theo dõi sinh lý
                        </span>
                      ) : (
                        <span className="trend-badge improving">
                          <TrendingUp size={14} /> Thể trạng tối ưu
                        </span>
                      )}
                    </div>
                    <p className="diagnosis-text">{profile?.active_diagnosis || 'Thể trạng sinh lý bình thường'}</p>
                  </div>
                );
              })()}

              {/* 1. Nhịp Tim BPM kèm Sóng Điện Tâm Đồ SVG (ECG Waveform) */}
              <div className="hud-card vital-card vital-waveform-card">
                <div className="vital-header">
                  <Heart size={16} className="vital-icon heart" />
                  <span>1. Nhịp tim (BPM)</span>
                </div>
                <div className="vital-val-row">
                  <strong className="vital-num">{profile?.vitals?.heart_rate_bpm || 78}</strong>
                  <span className="vital-unit">BPM</span>
                </div>
                {/* SVG ECG Waveform */}
                <div className="vital-svg-waveform-wrap">
                  <svg className="ecg-svg" viewBox="0 0 140 32" preserveAspectRatio="none">
                    <polyline
                      fill="none"
                      stroke="#ef4444"
                      strokeWidth="2.2"
                      points="0,16 25,16 32,16 38,8 44,26 50,2 56,20 62,14 68,16 95,16 102,8 108,26 114,2 120,20 126,14 140,16"
                    />
                  </svg>
                </div>
                <div className="vital-threshold-bar">
                  <span className="threshold-tag">Chuẩn: 60 - 100 bpm</span>
                  <span className="vital-status-text">
                    {(profile?.vitals?.heart_rate_bpm || 78) > 100 ? 'Nhịp nhanh' : (profile?.vitals?.heart_rate_bpm || 78) < 60 ? 'Nhịp chậm' : 'Nhịp đều chuẩn'}
                  </span>
                </div>
              </div>

              {/* 2. Huyết Áp mmHg */}
              <div className="hud-card vital-card">
                <div className="vital-header">
                  <Activity size={16} className="vital-icon bp" />
                  <span>2. Huyết áp (mmHg)</span>
                </div>
                <div className="vital-val-row">
                  <strong className="vital-num">
                    {profile?.vitals?.blood_pressure_systolic || 118}/{profile?.vitals?.blood_pressure_diastolic || 78}
                  </strong>
                  <span className="vital-unit">mmHg</span>
                </div>
                <div className="vital-progress-stack">
                  <div className="progress-stack-track">
                    <div
                      className="progress-stack-fill"
                      style={{
                        width: `${Math.min(100, ((profile?.vitals?.blood_pressure_systolic || 118) / 160) * 100)}%`,
                        backgroundColor: (profile?.vitals?.blood_pressure_systolic || 118) >= 140 ? '#ef4444' : (profile?.vitals?.blood_pressure_systolic || 118) >= 120 ? '#f59e0b' : '#10b981',
                      }}
                    />
                  </div>
                </div>
                <div className="vital-threshold-bar">
                  <span className="threshold-tag">Chuẩn: &lt;120/80</span>
                  <span className="vital-status-text">
                    {(profile?.vitals?.blood_pressure_systolic || 118) >= 130 ? 'Tăng HA độ 1' : (profile?.vitals?.blood_pressure_systolic || 118) >= 120 ? 'Tiền tăng HA' : 'Tối ưu'}
                  </span>
                </div>
              </div>

              {/* 3. Thân Nhiệt °C */}
              <div className="hud-card vital-card">
                <div className="vital-header">
                  <Thermometer size={16} className="vital-icon temp" />
                  <span>3. Thân nhiệt (°C)</span>
                </div>
                <div className="vital-val-row">
                  <strong className={`vital-num ${(profile?.vitals?.temperature_celsius || profile?.vitals?.body_temperature_c || 36.8) >= 38.5 ? 'vital-hot' : ''}`}>
                    {profile?.vitals?.temperature_celsius || profile?.vitals?.body_temperature_c || 36.8}°C
                  </strong>
                </div>
                <div className="vital-progress-stack">
                  <div className="progress-stack-track">
                    <div
                      className="progress-stack-fill"
                      style={{
                        width: `${Math.min(100, (((profile?.vitals?.temperature_celsius || profile?.vitals?.body_temperature_c || 36.8) - 35) / 5) * 100)}%`,
                        backgroundColor: (profile?.vitals?.temperature_celsius || profile?.vitals?.body_temperature_c || 36.8) >= 38.5 ? '#ef4444' : (profile?.vitals?.temperature_celsius || profile?.vitals?.body_temperature_c || 36.8) > 37.5 ? '#f59e0b' : '#10b981',
                      }}
                    />
                  </div>
                </div>
                <div className="vital-threshold-bar">
                  <span className="threshold-tag">Chuẩn: 36.5 - 37.5°C</span>
                  <span className="vital-status-text">
                    {(profile?.vitals?.temperature_celsius || profile?.vitals?.body_temperature_c || 36.8) >= 38.5 ? 'Sốt cao kịch phát' : (profile?.vitals?.temperature_celsius || profile?.vitals?.body_temperature_c || 36.8) > 37.5 ? 'Sốt nhẹ' : 'Bình thường'}
                  </span>
                </div>
              </div>

              {/* 4. SpO2 Máu % */}
              <div className="hud-card vital-card">
                <div className="vital-header">
                  <Droplet size={16} className="vital-icon spo2" />
                  <span>4. SpO2 Máu (%)</span>
                </div>
                <div className="vital-val-row">
                  <strong className="vital-num">{profile?.vitals?.spo2_percent || 98}%</strong>
                </div>
                <div className="vital-progress-stack">
                  <div className="progress-stack-track">
                    <div
                      className="progress-stack-fill"
                      style={{
                        width: `${profile?.vitals?.spo2_percent || 98}%`,
                        backgroundColor: (profile?.vitals?.spo2_percent || 98) < 95 ? '#ef4444' : '#00e5ff',
                      }}
                    />
                  </div>
                </div>
                <div className="vital-threshold-bar">
                  <span className="threshold-tag">Chuẩn: &ge; 95%</span>
                  <span className="vital-status-text">
                    {(profile?.vitals?.spo2_percent || 98) < 95 ? 'Báo động suy hô hấp' : 'Bão hòa oxy tối ưu'}
                  </span>
                </div>
              </div>

              {/* 5. Thang Đau VAS /10 */}
              <div className="hud-card vital-card">
                <div className="vital-header">
                  <Flame size={16} className="vital-icon pain" />
                  <span>5. Thang Đau VAS (/10)</span>
                </div>
                {(() => {
                  const vasScore = profile?.vitals?.vas_pain_score ?? profile?.vitals?.overall_pain_level ?? 2;
                  const vasColor = vasScore >= 7 ? '#ef4444' : vasScore >= 4 ? '#f59e0b' : '#10b981';
                  return (
                    <>
                      <div className="vital-val-row">
                        <strong className="vital-num" style={{ color: vasColor }}>{vasScore}/10</strong>
                        <span className="vital-unit">VAS</span>
                      </div>
                      <div className="vas-gradient-track-wrap">
                        <div className="vas-gradient-bar">
                          <div className="vas-pointer" style={{ left: `${Math.min(100, (vasScore / 10) * 100)}%` }} />
                        </div>
                      </div>
                      <div className="vital-threshold-bar">
                        <span className="threshold-tag">Chuẩn: 0 - 2 (Nhẹ)</span>
                        <span className="vital-status-text" style={{ color: vasColor }}>
                          {vasScore >= 7 ? 'Đau dữ dội cấp' : vasScore >= 4 ? 'Đau vừa có phản xạ' : vasScore === 0 ? 'Không đau' : 'Đau nhẹ kiểm soát'}
                        </span>
                      </div>
                    </>
                  );
                })()}
              </div>
            </div>

            {/* Directives & Action Recommendations */}
            <div className="directives-row">
              <div className="directives-box">
                <div className="box-title">
                  <Stethoscope size={16} />
                  <span>Chỉ thị Y tế & Lời khuyên Điều trị</span>
                </div>
                <ul className="directives-list">
                  {profile?.clinical_directives?.map((d, i) => (
                    <li key={i}>
                      <CheckCircle2 size={15} className="directive-check-icon" />
                      <span>{d}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Safety Discontinued Items Warning */}
              {profile?.discontinued_medications && profile.discontinued_medications.length > 0 && (
                <div className="discontinued-alert-box">
                  <div className="box-title danger">
                    <ShieldAlert size={16} />
                    <span>Thuốc & Cách cũ ĐÃ BỊ ĐÌNH CHỈ (Dừng Ngay)</span>
                  </div>
                  <p className="disc-sub">
                    Để bảo vệ bệnh nhân, AI đã gắn cờ cấm tiếp tục sử dụng các mục sau do phát hiện phản ứng bất lợi:
                  </p>
                  <ul className="disc-list">
                    {profile.discontinued_medications.map((item, idx) => (
                      <li key={idx}>
                        <X size={14} className="disc-cross" />
                        <strong>{item}</strong>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tab: Recovery Timeline */}
        {activeTab === 'timeline' && (
          <div className="timeline-tab-content">
            <div className="timeline-header-info">
              <Clock size={16} />
              <span>Tiến trình Diễn biến Lâm sàng & Các lần Tương tác Thăm dò</span>
            </div>

            <div className="timeline-vertical-flow">
              {profile?.timeline?.map((point, idx) => (
                <div key={point.id || idx} className={`timeline-entry-node ${point.phase}`}>
                  <div className="timeline-node-marker">
                    <span className="node-dot" />
                    {idx < profile.timeline.length - 1 && <span className="node-line" />}
                  </div>

                  <div className="timeline-entry-card">
                    <div className="entry-card-top">
                      <div className="entry-title-wrap">
                        <h4>{point.title}</h4>
                        <span className="entry-time">{point.timestamp}</span>
                      </div>
                      <span className={`phase-badge ${point.phase}`}>{point.status_label}</span>
                    </div>

                    <div className="trigger-quote-box">
                      <span className="quote-label">Tin nhắn bệnh nhân:</span>
                      <p>&ldquo;{point.trigger_message}&rdquo;</p>
                    </div>

                    <p className="clinical-summary-p">{point.clinical_summary}</p>

                    <div className="ai-directive-quote">
                      <Sparkles size={14} />
                      <div>
                        <strong>Chỉ dẫn AI Bác sĩ:</strong>
                        <p>{point.ai_directive}</p>
                      </div>
                    </div>

                    {point.medications_adjusted && point.medications_adjusted.length > 0 && (
                      <div className="med-adjust-row">
                        {point.medications_adjusted.map((m, i) => (
                          <span key={i} className="med-adjust-tag">
                            <Pill size={11} /> {m}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tab: Medications & Regimens */}
        {activeTab === 'meds' && (
          <div className="meds-tab-content">
            <div className="meds-columns-grid">
              <div className="meds-col active-meds">
                <div className="meds-col-header">
                  <CheckCircle2 size={16} />
                  <h3>Thuốc đang được sử dụng an toàn</h3>
                </div>
                {profile?.active_medications && profile.active_medications.length > 0 ? (
                  <ul className="meds-card-list">
                    {profile.active_medications.map((m, idx) => (
                      <li key={idx} className="med-item-card safe">
                        <Pill size={16} />
                        <div>
                          <strong>{m}</strong>
                          <span>Đang đáp ứng theo dõi tốt</span>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="empty-meds">Hiện không có thuốc kê thêm.</p>
                )}
              </div>

              <div className="meds-col stopped-meds">
                <div className="meds-col-header danger">
                  <ShieldAlert size={16} />
                  <h3>Thuốc đã bị dừng / Chống chỉ định</h3>
                </div>
                {profile?.discontinued_medications && profile.discontinued_medications.length > 0 ? (
                  <ul className="meds-card-list">
                    {profile.discontinued_medications.map((m, idx) => (
                      <li key={idx} className="med-item-card stopped">
                        <X size={16} />
                        <div>
                          <strong>{m}</strong>
                          <span className="stopped-warn">Ngừng khẩn cấp do gây phản ứng bất lợi</span>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="empty-meds">Chưa ghi nhận thuốc nào bị chống chỉ định.</p>
                )}
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
