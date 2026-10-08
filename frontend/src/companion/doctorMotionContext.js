// Motion metadata only: this classifier never makes clinical decisions or changes
// the answer. Explicit warning sentences take precedence over a friendly tone.
const normalize = text => String(text || '').toLocaleLowerCase('vi').replace(/\s+/g, ' ').trim();
export const splitMotionPhrases = text => String(text || '').match(/[^.!?\n]+[.!?]*/gu)?.map(s => s.trim()).filter(Boolean) || [];

export function motionContext(text, fallback = 'clinical') {
  const s = normalize(text);
  if (/cấp cứu|khẩn cấp|gọi\s*115|chống chỉ định|không (?:được |nên )?tự|không tự|ngừng (?:thuốc|dùng)|quá liều|cảnh báo/.test(s)) return 'cautious';
  if (/lo lắng|sợ|hoang mang|buồn|đau đớn|khó chịu|thấu hiểu|lắng nghe|đồng hành|ghi nhận/.test(s)) return 'empathetic';
  if (/tiến bộ|cải thiện|khích lệ|cố gắng|tốt hơn/.test(s)) return 'encouraging';
  return fallback;
}

export function phraseIntent(text, context = 'clinical') {
  const s = normalize(text);
  if (motionContext(s, '') === 'cautious') return 'caution';
  if (/xin chào|chào bạn|chào anh|chào chị/.test(s)) return 'greeting';
  if (/\?|cho biết|chia sẻ|bạn có|kể thêm/.test(s)) return 'invite';
  if (/đầu tiên|tiếp theo|bước|thứ nhất|thứ hai|cuối cùng|\b\d+[.)]/.test(s)) return 'enumerate';
  if (motionContext(s, '') === 'empathetic') return 'reassure';
  if (/so sánh|khác nhau|hai (?:loại|nhóm)|trong khi/.test(s)) return 'compare';
  if (/hướng dẫn|theo dõi|ghi lại|ghi chép|thực hiện|kiểm tra/.test(s)) return 'guide';
  if (/giải thích|cơ chế|thành phần|dược lý|tác dụng|nguyên nhân/.test(s)) return 'explain';
  return context === 'empathetic' ? 'reassure' : 'explain';
}

// Each intent has authored alternatives, rather than arbitrary unrelated actions.
// lift/bend/yaw/turn are radians in the normalized VRM T-pose; fingers are semantic.
export const GESTURE_POOL = {
  greeting: [
    {id:'shoulder-wave',lift:.62,bend:2.60,yaw:.12,turn:.18,lean:-.012,wave:.12,fingers:'open'},
    {id:'small-wave',lift:.53,bend:2.48,yaw:.16,turn:.22,lean:-.018,wave:.09,fingers:'open'},
    {id:'warm-wave',lift:.58,bend:2.56,yaw:.20,turn:.16,lean:-.025,wave:.10,fingers:'open'},
  ],
  explain: [
    {id:'palm-arc',lift:.20,bend:1.55,yaw:.14,turn:.28,lean:-.008,arc:.065,fingers:'open'},
    {id:'measured-beat',lift:.12,bend:1.74,yaw:.07,turn:.14,lean:0,arc:.025,fingers:'soft'},
    {id:'spatial-explain',lift:.27,bend:1.48,yaw:.20,turn:.33,lean:-.012,arc:.05,secondary:.62,fingers:'open'},
  ],
  invite: [
    {id:'one-palm-invite',lift:.20,bend:1.74,yaw:.17,turn:.36,lean:-.028,arc:.045,fingers:'open'},
    {id:'two-palm-invite',lift:.25,bend:1.61,yaw:.21,turn:.30,lean:-.021,secondary:.76,fingers:'open'},
    {id:'gentle-invite',lift:.12,bend:1.85,yaw:.10,turn:.23,lean:-.032,arc:.025,fingers:'soft'},
  ],
  reassure: [
    {id:'low-open-palms',lift:.14,bend:1.58,yaw:.15,turn:.35,lean:-.045,secondary:.57,fingers:'open'},
    {id:'hand-near-heart',lift:.10,bend:1.93,yaw:.27,turn:.10,lean:-.038,arc:.012,fingers:'soft'},
    {id:'gentle-offer',lift:.19,bend:1.69,yaw:.12,turn:.30,lean:-.031,arc:.04,fingers:'open'},
  ],
  caution: [
    {id:'compact-stop',lift:.19,bend:1.88,yaw:.07,turn:.07,lean:-.01,fingers:'open'},
    {id:'precise-warning',lift:.12,bend:1.74,yaw:.11,turn:.14,lean:-.008,arc:.018,fingers:'point'},
    {id:'controlled-beat',lift:.09,bend:1.65,yaw:.06,turn:.12,lean:0,arc:.012,fingers:'soft'},
  ],
  enumerate: [
    {id:'count-one',lift:.15,bend:1.83,yaw:.09,turn:.16,lean:-.006,fingers:'point'},
    {id:'count-two',lift:.18,bend:1.78,yaw:.16,turn:.24,lean:-.009,fingers:'two'},
    {id:'sequence-beat',lift:.12,bend:1.66,yaw:.11,turn:.18,lean:0,arc:.035,fingers:'soft'},
  ],
  compare: [
    {id:'two-sides',lift:.25,bend:1.50,yaw:.22,turn:.30,lean:-.006,secondary:.84,fingers:'open'},
    {id:'alternate-palm',lift:.19,bend:1.69,yaw:.17,turn:.25,lean:0,secondary:.55,arc:.06,fingers:'open'},
    {id:'small-range',lift:.12,bend:1.79,yaw:.10,turn:.18,lean:-.015,secondary:.68,fingers:'soft'},
  ],
  guide: [
    {id:'offer-step',lift:.22,bend:1.58,yaw:.18,turn:.30,lean:-.02,arc:.035,fingers:'open'},
    {id:'precise-step',lift:.14,bend:1.76,yaw:.09,turn:.15,lean:-.009,fingers:'point'},
    {id:'support-step',lift:.18,bend:1.67,yaw:.17,turn:.23,lean:-.016,secondary:.54,fingers:'soft'},
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
