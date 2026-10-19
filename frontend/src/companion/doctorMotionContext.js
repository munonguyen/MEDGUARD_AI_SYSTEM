// Motion metadata only: this classifier never makes clinical decisions or changes
// the answer. Explicit warning sentences take precedence over a friendly tone.
const normalize = text => String(text || '').toLocaleLowerCase('vi').replace(/\s+/g, ' ').trim();
export const splitMotionPhrases = text => String(text || '').match(/[^.!?\n]+[.!?]*/gu)?.map(s => s.trim()).filter(Boolean) || [];

export function motionContext(text, fallback = 'clinical') {
  const s = normalize(text);
  if (/cấp cứu|khẩn cấp|gọi\s*115|chống chỉ định|không (?:được |nên )?tự|không tự|ngừng (?:thuốc|dùng)|quá liều|cảnh báo|tránh|hạn chế|tuyệt đối không|nguy hiểm/.test(s)) return 'cautious';
  if (/lo lắng|sợ|hoang mang|buồn|đau|ê buốt|khó chịu|thấu hiểu|lắng nghe|đồng hành|ghi nhận|yên tâm|giảm đau|tạm thời/.test(s)) return 'empathetic';
  if (/tiến bộ|cải thiện|khích lệ|cố gắng|tốt hơn/.test(s)) return 'encouraging';
  return fallback;
}

export function phraseIntent(text, context = 'clinical') {
  const s = normalize(text);
  if (/xin chào|chào bạn|chào anh|chào chị/.test(s)) return 'greeting';
  if (/\?|cho biết|chia sẻ|bạn có (?!thể)|kể thêm|có bị|chảy mủ|chảy máu|há miệng|nổi mẩn|sốt/.test(s)) return 'invite';
  if (/đầu tiên|tiếp theo|bước|thứ nhất|thứ hai|cuối cùng|\b\d+[.)]/.test(s)) return 'enumerate';
  if (/súc miệng|nước muối|bàn chải|vệ sinh|chườm|hướng dẫn|theo dõi|ghi lại|ghi chép|thực hiện|kiểm tra|chăm sóc/.test(s)) return 'guide';
  if (/cấp cứu|khẩn cấp|chống chỉ định|tránh|không (?:được |nên )?tự|tuyệt đối không|ngừng|cảnh báo|hạn chế|ngọt gắt|quá nóng|quá lạnh/.test(s)) return 'caution';
  if (/so sánh|khác nhau|hai (?:loại|nhóm)|trong khi|hoặc là|ngược lại/.test(s)) return 'compare';
  if (/giải thích|cơ chế|thành phần|dược lý|tác dụng|nguyên nhân|do|tủy răng|men răng|xuất hiện do|kích thích|viêm|nhiễm trùng/.test(s)) return 'explain';
  if (motionContext(s, '') === 'empathetic' || /đau|ê buốt|khó chịu|yên tâm|giảm đau|tạm thời/.test(s)) return 'reassure';
  return context === 'empathetic' ? 'reassure' : 'explain';
}

// Each intent has authored alternatives, rather than arbitrary unrelated actions.
// lift/bend/yaw/turn are radians in the normalized VRM T-pose; fingers are semantic.
export const GESTURE_POOL = {
  greeting: [
    {id:'shoulder-wave',lift:.22,bend:1.85,yaw:.08,turn:.12,lean:-.012,wave:.065,fingers:'open'},
    {id:'small-wave',lift:.18,bend:1.78,yaw:.10,turn:.14,lean:-.018,wave:.05,fingers:'open'},
    {id:'warm-wave',lift:.20,bend:1.82,yaw:.09,turn:.12,lean:-.025,wave:.06,fingers:'open'},
  ],
  explain: [
    {id:'palm-arc',lift:.24,bend:1.50,yaw:.16,turn:.28,lean:-.008,arc:.07,fingers:'open'},
    {id:'measured-beat',lift:.15,bend:1.64,yaw:.10,turn:.16,lean:0,arc:.03,fingers:'soft'},
    {id:'spatial-explain',lift:.30,bend:1.42,yaw:.22,turn:.33,lean:-.012,arc:.055,secondary:.65,fingers:'open'},
  ],
  invite: [
    {id:'one-palm-invite',lift:.23,bend:1.65,yaw:.18,turn:.36,lean:-.028,arc:.048,fingers:'open'},
    {id:'two-palm-invite',lift:.27,bend:1.54,yaw:.22,turn:.30,lean:-.021,secondary:.78,fingers:'open'},
    {id:'gentle-invite',lift:.14,bend:1.76,yaw:.12,turn:.23,lean:-.032,arc:.025,fingers:'soft'},
  ],
  reassure: [
    {id:'low-open-palms',lift:.16,bend:1.52,yaw:.16,turn:.35,lean:-.045,secondary:.60,fingers:'open'},
    {id:'hand-near-heart',lift:.10,bend:1.90,yaw:.27,turn:.10,lean:-.038,arc:.012,fingers:'soft'},
    {id:'gentle-offer',lift:.21,bend:1.60,yaw:.14,turn:.30,lean:-.031,arc:.04,fingers:'open'},
  ],
  caution: [
    {id:'compact-stop',lift:.22,bend:1.78,yaw:.10,turn:.08,lean:-.01,fingers:'open'},
    {id:'precise-warning',lift:.15,bend:1.68,yaw:.13,turn:.15,lean:-.008,arc:.02,fingers:'point'},
    {id:'controlled-beat',lift:.12,bend:1.60,yaw:.08,turn:.12,lean:0,arc:.015,fingers:'soft'},
  ],
  enumerate: [
    {id:'count-one',lift:.16,bend:1.76,yaw:.11,turn:.16,lean:-.006,fingers:'point'},
    {id:'count-two',lift:.19,bend:1.70,yaw:.17,turn:.24,lean:-.009,fingers:'two'},
    {id:'sequence-beat',lift:.14,bend:1.60,yaw:.12,turn:.18,lean:0,arc:.035,fingers:'soft'},
  ],
  compare: [
    {id:'two-sides',lift:.28,bend:1.45,yaw:.24,turn:.30,lean:-.006,secondary:.86,fingers:'open'},
    {id:'alternate-palm',lift:.22,bend:1.60,yaw:.18,turn:.25,lean:0,secondary:.58,arc:.06,fingers:'open'},
    {id:'small-range',lift:.15,bend:1.70,yaw:.12,turn:.18,lean:-.015,secondary:.70,fingers:'soft'},
  ],
  guide: [
    {id:'offer-step',lift:.25,bend:1.52,yaw:.20,turn:.30,lean:-.02,arc:.04,fingers:'open'},
    {id:'precise-step',lift:.16,bend:1.68,yaw:.11,turn:.16,lean:-.009,fingers:'point'},
    {id:'support-step',lift:.20,bend:1.60,yaw:.18,turn:.24,lean:-.016,secondary:.58,fingers:'soft'},
  ],
};

export class GesturePlanner {
  constructor(random = Math.random) { this.random = random; this.recent = []; this.lastSide = 'left'; }
  select(intent, context = 'clinical') {
    const pool = GESTURE_POOL[intent] || GESTURE_POOL.explain;
    // Exclude the immediately preceding variant; penalize the last six choices.
    const last = this.recent.at(-1);
    const weights = pool.map(p => p.id === last ? 0 : this.recent.includes(p.id) ? .18 : 1);
    let roll = this.random() * weights.reduce((a,b) => a+b,0);
    let variant = pool.at(-1);
    for (let i=0;i<pool.length;i++) { roll-=weights[i]; if (roll<=0 && weights[i]>0) {variant=pool[i];break;} }
    this.recent.push(variant.id); this.recent = this.recent.slice(-6);
    const side = intent === 'greeting' ? 'right' : this.random()<.78 ? (this.lastSide==='left'?'right':'left') : this.lastSide;
    this.lastSide = side;
    const emotion = context==='cautious'||intent==='caution' ? 'cautious' : intent==='reassure' ? 'empathetic' : context;
    return {intent, variant, side, emotion, energy:emotion==='empathetic'?.80:emotion==='cautious'?.92:1,
      energyLevel:emotion==='empathetic'?'low':emotion==='cautious'?'high':'medium',
      duration:3.8+this.random()*1.5};
  }
  plan(text, context) {
    return (splitMotionPhrases(text).length ? splitMotionPhrases(text) : [text]).map(sentence => {
      const localContext = context==='cautious' ? context : motionContext(sentence, context);
      return {text:sentence,...this.select(phraseIntent(sentence,context),localContext)};
    });
  }
}
