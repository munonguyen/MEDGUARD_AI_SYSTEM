// File: src/client/companion/doctor3dLiveEngine.ts

export type VrmVisemeName = 'aa' | 'ih' | 'ou' | 'ee' | 'oh';

export interface VisemeFrame {
  viseme: VrmVisemeName;
  weight: number;
  durationMs: number;
}

/**
 * 1. Lọc bỏ hoàn toàn thông báo lỗi kỹ thuật & rút gọn văn bản sang văn phong hội thoại 2–3 câu
 * trước khi gửi tới endpoint POST /v1/tts của Bác sĩ 3D Live.
 */
export function sanitizeAndCondenseFor3DDoctorSpeech(rawChatText: string): string {
  const cleaned = rawChatText
    .replace(/AI chưa trả lời được;[^.\n]*[.\n]?/gi, '')
    .replace(/Kiểm tra kết nối AI trong Cài đặt\.?/gi, '')
    .replace(/CẢNH BÁO AN TOÀN LÂM SÀNG:\s*/gi, '')
    .replace(/\s+/g, ' ')
    .trim();

  // Khử các câu bị lặp lại nhiều lần (ví dụ câu "Gọi 115 hoặc đến khoa Cấp cứu; không tự lái xe" lặp 3 lần)
  const rawSentences = cleaned
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim())
    .filter(Boolean);

  const uniqueSentences: string[] = [];
  const seenNormalized = new Set<string>();

  for (const sentence of rawSentences) {
    const key = sentence.toLowerCase().replace(/[^a-zà-ỹ0-9]/g, '');
    if (!seenNormalized.has(key)) {
      seenNormalized.add(key);
      uniqueSentences.push(sentence);
    }
    if (uniqueSentences.length >= 3) break; // Giữ tối đa 3 câu súc tích cho hội thoại 3D trực tiếp
  }

  return uniqueSentences.join(' ');
}

/**
 * 2. Bộ ánh xạ Âm tiết Tiếng Việt sang VRM Viseme (Vietnamese Grapheme-to-Viseme)
 * Thay thế hoàn toàn model-en-mixed.bin của tiếng Anh!
 */
export function mapVietnameseTextToVrmVisemes(sentence: string): VisemeFrame[] {
  const words = sentence
    .toLowerCase()
    .replace(/[.,!?;:()"'«»—-]/g, ' ')
    .split(/\s+/)
    .filter(Boolean);

  const timeline: VisemeFrame[] = [];

  for (const word of words) {
    // Nguyên âm đôi "ươ / uô" (ví dụ: thuốc, được, người, luôn) -> chuyển mượt từ tròn môi (ou) sang mở vừa (ee/aa)
    if (/(ươ|uô|ưa|ua)/.test(word)) {
      timeline.push({ viseme: 'ou', weight: 0.75, durationMs: 85 });
      timeline.push({ viseme: 'aa', weight: 0.65, durationMs: 95 });
      continue;
    }
    // Nhóm nguyên âm mở rộng (a, ă, â, oai, oay)
    if (/[aăâáàảãạắằẳẵặấầẩẫậ]/.test(word)) {
      timeline.push({ viseme: 'aa', weight: 0.85, durationMs: 140 });
      continue;
    }
    // Nhóm nguyên âm tròn môi mở (o, ô)
    if (/[oôóòỏõọốồổỗộ]/.test(word)) {
      timeline.push({ viseme: 'oh', weight: 0.8, durationMs: 135 });
      continue;
    }
    // Nhóm nguyên âm tròn môi hẹp (u)
    if (/[uúùủũụ]/.test(word)) {
      timeline.push({ viseme: 'ou', weight: 0.8, durationMs: 130 });
      continue;
    }
    // Nhóm nguyên âm không tròn môi đặc trưng tiếng Việt (ư, ơ) -> kết hợp ih/ee tự nhiên, không chu môi kiểu tiếng Anh
    if (/[ươứừửữựớờởỡợ]/.test(word)) {
      timeline.push({ viseme: 'ih', weight: 0.65, durationMs: 130 });
      continue;
    }
    // Nhóm nguyên âm dẹt (e, ê, i, y)
    if (/[eêéèẻẽẹếềểễệiíìỉĩịyýỳỷỹỵ]/.test(word)) {
      timeline.push({ viseme: 'ee', weight: 0.75, durationMs: 125 });
      continue;
    }

    timeline.push({ viseme: 'ih', weight: 0.4, durationMs: 100 });
  }

  return timeline;
}

/**
 * 3. Quản lý Hàng đợi Âm thanh (TTS Session Manager) kèm AbortController & Bộ nhớ đệm VRMA Animation
 */
export class Doctor3DSessionController {
  private ttsAbortController: AbortController | null = null;
  private vrmaAnimationCache = new Map<string, ArrayBuffer>();
  private currentDoctorId: 'tuan' | 'mai' = 'tuan';

  public switchDoctor(newDoctorId: 'tuan' | 'mai') {
    // Hủy ngay lập tức mọi request POST /v1/tts của bác sĩ trước đó!
    this.stopCurrentSpeech();
    this.currentDoctorId = newDoctorId;
  }

  public stopCurrentSpeech() {
    if (this.ttsAbortController) {
      this.ttsAbortController.abort();
      this.ttsAbortController = null;
    }
  }

  public async loadCachedVrmaAnimation(url: string): Promise<ArrayBuffer> {
    const cached = this.vrmaAnimationCache.get(url);
    if (cached) return cached;

    const res = await fetch(url);
    const buffer = await res.arrayBuffer();
    this.vrmaAnimationCache.set(url, buffer);
    return buffer;
  }

  public async speakWithStreamingTts(rawResponseText: string, onVisemeTimeline: (frames: VisemeFrame[]) => void) {
    this.stopCurrentSpeech();
    this.ttsAbortController = new AbortController();
    const { signal } = this.ttsAbortController;

    const conciseSpeech = sanitizeAndCondenseFor3DDoctorSpeech(rawResponseText);
    const sentences = conciseSpeech.split(/(?<=[.!?])\s+/).filter(Boolean);

    for (const sentence of sentences) {
      if (signal.aborted) return;

      const visemeFrames = mapVietnameseTextToVrmVisemes(sentence);
      onVisemeTimeline(visemeFrames);

      await fetch('/v1/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: sentence,
          voiceId: this.currentDoctorId === 'tuan' ? 'vi-VN-NamMinhNeural' : 'vi-VN-HoaiMyNeural'
        }),
        signal
      });
    }
  }
}
