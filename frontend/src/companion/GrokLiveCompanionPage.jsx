import { useEffect, useRef, useState } from 'react';
import {
  Activity,
  Camera,
  ChevronLeft,
  Mic,
  Send,
  Settings,
  Smile,
  Sparkles,
  Upload,
  User,
  Volume2,
  VolumeX,
  X,
} from 'lucide-react';
import { VRMAvatarEngine } from './VRMAvatarEngine';
import { splitSpeech, runSpeechQueue } from './speechQueue';
import './GrokLiveCompanionPage.css';

/**
 * Normalizes text for professional clinical text-to-speech:
 * - Strips all Markdown syntax (*, #, -, bullets, links, backticks)
 * - Expands Vietnamese medical abbreviations to clear spoken phrases
 */
const normalizeMedicalSpeech = (text) => {
  if (!text) return '';
  return text
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/\*(.*?)\*/g, '$1')
    .replace(/^#+\s+/gm, '')
    .replace(/^\s*[-*•]\s+/gm, '')
    .replace(/\[\d+\]/g, '')
    .replace(/[`>~_]/g, '')
    .replace(/\bBS\.\s*/gi, 'Bác sĩ ')
    .replace(/\bBs\.\s*/gi, 'Bác sĩ ')
    .replace(/\bThS\.BS\s*/gi, 'Thạc sĩ Bác sĩ ')
    .replace(/\bCKII\b/gi, 'Chuyên khoa hai ')
    .replace(/\bmg\b/gi, ' mi-li-gam ')
    .replace(/\bml\b/gi, ' mi-li-lít ')
    .replace(/\b°C\b/gi, ' độ C ')
    .replace(/\bBN\b/gi, ' bệnh nhân ')
    .replace(/\s+/g, ' ')
    .trim();
};

/**
 * GrokLiveCompanionPage (Bác Sĩ 3D Live Companion)
 * Interactive Anime Doctor Avatar powered by VRMAvatarEngine.
 */
export function GrokLiveCompanionPage({
  api = null,
  context = {},
  onBackToChat = null,
  onNotify = null,
}) {
  const canvasRef = useRef(null);
  const engineRef = useRef(null);
  const audioRef = useRef(null);
  const audioContextRef = useRef(null);
  const ttsAbortRef = useRef(null);
  const chatAbortRef = useRef(null);
  const queryStartedRef = useRef(null);
  const audioUrlRef = useRef(null);
  const fileInputRef = useRef(null);
  const recognitionRef = useRef(null);
  const conversationIdRef = useRef(crypto.randomUUID ? crypto.randomUUID() : `companion-${Date.now()}`);
  const messagesHistoryRef = useRef([]);
  const speechIdRef = useRef(0);
  const mutedRef = useRef(false);

  // Doctor Personas: 'dr_tuan' (Male) | 'dr_mai' (Female)
  const [doctorPersona, setDoctorPersona] = useState('dr_tuan');
  const [customModelName, setCustomModelName] = useState(null);
  const [cameraPreset, setCameraPreset] = useState('waist');
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isVoiceLoading, setIsVoiceLoading] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [isBusy, setIsBusy] = useState(false);
  const [inputText, setInputText] = useState('');
  const [dialogueText, setDialogueText] = useState(
    'Xin chào! Tôi là Bác sĩ Minh Tuấn từ MedGuard AI. Tôi luôn sẵn sàng lắng nghe và tư vấn sức khỏe cho bạn. Bạn đang có băn khoăn hay triệu chứng gì cần hỗ trợ hôm nay?'
  );
  // Consultation Emotional Tone: 'empathetic' | 'clinical' | 'encouraging' | 'cautious'
  const [consultationTone, setConsultationTone] = useState('empathetic');
  const [showEmotions, setShowEmotions] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [isCapturing, setIsCapturing] = useState(false);
  const [voiceConfig,setVoiceConfig] = useState(null);
  const [voiceConfigError,setVoiceConfigError] = useState('');
  const [voiceError,setVoiceError] = useState('');
  const [modelStatus,setModelStatus] = useState({phase:'loading',error:''});

  const currentDoctorName = customModelName
    ? customModelName
    : doctorPersona === 'dr_tuan'
    ? 'BS.CKII Vũ Minh Tuấn'
    : 'ThS.BS Lê Thanh Mai';

  const currentDoctorRole = customModelName
    ? 'Mô hình 3D tùy chỉnh'
    : doctorPersona === 'dr_tuan'
    ? 'Trưởng khoa Tư vấn Y tế'
    : 'Bác sĩ Dược & Lâm sàng';

  // Mount 3D Doctor Engine
  useEffect(() => {
    if (!canvasRef.current) return;

    const engine = new VRMAvatarEngine(canvasRef.current, {
      persona: doctorPersona,
      cameraPreset,
      onLoading: () => setModelStatus({phase:'loading',error:''}),
      onLoaded: (model) => {
        setModelStatus({phase:'ready',error:''});
        onNotify?.('Nhân vật bác sĩ đã sẵn sàng.');
      },
      onError: (err) => {
        setModelStatus({phase:'error',error:err?.message || 'Không khởi tạo được WebGL.'});
      },
    });
    engineRef.current = engine;
    if (typeof window !== 'undefined') {
      window.__companionEngine = engine;
    }

    const handleResize = () => {
      if (canvasRef.current) {
        const rect = canvasRef.current.getBoundingClientRect();
        engine.resize(rect.width, rect.height);
      }
    };
    const observer = new ResizeObserver(handleResize);
    observer.observe(canvasRef.current);
    handleResize();

    return () => {
      observer.disconnect();
      engine.destroy();
      engineRef.current = null;
      if (typeof window !== 'undefined' && window.__companionEngine === engine) {
        window.__companionEngine = null;
      }
    };
  }, []);

  useEffect(()=>{
    if(!showSettings)return;
    let active=true;const controller=new AbortController();
    setVoiceConfig(null);setVoiceConfigError('');
    const load=api?api.request('/v1/tts/profiles',{signal:controller.signal}):fetch('/v1/tts/profiles',{signal:controller.signal}).then(r=>{if(!r.ok)throw new Error();return r.json();});
    load.then(data=>{
      if(!data?.profiles?.dr_tuan?.voice||!data?.profiles?.dr_mai?.voice)throw new Error();
      if(active)setVoiceConfig(data);
    }).catch(()=>{if(active)setVoiceConfigError('Chưa nhận được cấu hình giọng bác sĩ. Hãy kiểm tra backend đã cập nhật và đang chạy.');});
    return ()=>{active=false;controller.abort();};
  },[showSettings,api]);

  // Clean up Web Speech Recognition & Audio on unmount
  useEffect(() => {
    return () => {
      speechIdRef.current++;
      disposePlayback();
      chatAbortRef.current?.abort();
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // ignore
        }
        recognitionRef.current = null;
      }
    };
  }, []);

  const disposePlayback = () => {
    ttsAbortRef.current?.abort();
    ttsAbortRef.current = null;
    if (audioRef.current) {
      const audio = audioRef.current;
      audio.onplaying = audio.onended = audio.onerror = audio.onpause = null;
      audio.pause();
      audio.removeAttribute('src');
      audio.load();
      audioRef.current = null;
    }
    if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
    audioUrlRef.current = null;
    audioContextRef.current?.close().catch(() => {});
    audioContextRef.current = null;
    engineRef.current?.stopSpeaking();
  };

  const speakDoctorVoice = async (text, persona = doctorPersona, reqSpeechId = null) => {
    if (mutedRef.current || typeof window === 'undefined') return;
    if (reqSpeechId !== null && reqSpeechId !== speechIdRef.current) return;
    disposePlayback();
    setIsSpeaking(false);
    const requestId = reqSpeechId ?? ++speechIdRef.current;
    const cleanSpeech = normalizeMedicalSpeech(text);
    if (!cleanSpeech) return;
    setIsVoiceLoading(true);
    setVoiceError('');
    const controller = new AbortController();
    ttsAbortRef.current = controller;
    const current = () => !mutedRef.current && !controller.signal.aborted && requestId === speechIdRef.current;
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    const audioContext = AudioContextClass ? new AudioContextClass() : null;
    audioContextRef.current = audioContext;
    // Resume within the interaction where possible (not after the synthesis request).
    audioContext?.resume().catch(() => {});
    const voiceStarted = performance.now();
    let firstSound = true;
    try {
      const synthesize = async sentence => {
        const body = { text: sentence, persona };
        if (api) return api.request('/v1/tts', {
          method: 'POST', body, responseType: 'blob', signal: controller.signal, timeoutMs: 30000,
        });
        const request = new AbortController();
        const cancel = () => request.abort();
        controller.signal.addEventListener('abort', cancel, { once: true });
        const timer = window.setTimeout(cancel, 30000);
        try {
          const response = await fetch('/v1/tts', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body), signal: request.signal,
          });
          if (!response.ok) throw new Error('Voice unavailable');
          return await response.blob();
        } finally {
          window.clearTimeout(timer);
          controller.signal.removeEventListener('abort', cancel);
        }
      };
      const play = (blob, sentence) => new Promise((resolve, reject) => {
        if (!current()) return reject(new DOMException('Cancelled', 'AbortError'));
        const url = URL.createObjectURL(blob);
        audioUrlRef.current = url;
        const audio = new Audio(url);
        audioRef.current = audio;
        let source = null;
        let analyser = null;
        let settled = false;
        const finish = error => {
          if (settled) return;
          settled = true;
          controller.signal.removeEventListener('abort', abort);
          audio.onplaying = audio.onended = audio.onerror = audio.onpause = null;
          audio.pause(); audio.removeAttribute('src'); audio.load();
          source?.disconnect(); analyser?.disconnect();
          URL.revokeObjectURL(url);
          if (audioRef.current === audio) audioRef.current = null;
          if (audioUrlRef.current === url) audioUrlRef.current = null;
          if (current()) {
            setIsSpeaking(false); setIsVoiceLoading(true);
            engineRef.current?.stopSpeaking();
          }
          error ? reject(error) : resolve();
        };
        const abort = () => finish(new DOMException('Cancelled', 'AbortError'));
        controller.signal.addEventListener('abort', abort, { once: true });
        if (audioContext) {
          analyser = audioContext.createAnalyser(); analyser.fftSize = 512;
          source = audioContext.createMediaElementSource(audio);
          source.connect(analyser); analyser.connect(audioContext.destination);
        }
        audio.onplaying = () => {
          if (!current()) return abort();
          setIsVoiceLoading(false); setIsSpeaking(true);
          engineRef.current?.setAudioAnalyser(analyser);
          engineRef.current?.startSpeaking(sentence);
          if (firstSound) {
            firstSound = false;
            const now = performance.now();
            window.dispatchEvent(new CustomEvent('medguard:companion-latency', { detail: {
              stage: 'first_audio', persona, ttsMs: Math.round(now - voiceStarted),
              totalMs: queryStartedRef.current === null ? null : Math.round(now - queryStartedRef.current),
            } }));
          }
        };
        audio.onended = () => finish();
        audio.onerror = () => finish(new Error('Audio playback failed'));
        (async () => {
          if (audioContext) {
            await Promise.race([audioContext.resume(), new Promise(r => window.setTimeout(r, 300))]);
            if (audioContext.state !== 'running') throw new DOMException('Audio needs a user gesture', 'NotAllowedError');
          }
          if (!current()) return abort();
          await audio.play();
        })().catch(finish);
      });
      await runSpeechQueue(splitSpeech(cleanSpeech), { synthesize, play, signal: controller.signal });
      if (current()) { setIsVoiceLoading(false); setIsSpeaking(false); disposePlayback(); }
    } catch (error) {
      if (!current()) return;
      setIsVoiceLoading(false); setIsSpeaking(false);
      disposePlayback();
      setVoiceError(error?.name === 'NotAllowedError'
        ? 'Trình duyệt đang chặn phát âm thanh. Hãy bấm Đọc lại để phát giọng bác sĩ.'
        : `Giọng bác sĩ chưa phát được${error?.status ? ` (HTTP ${error.status})` : ''}. Hãy kiểm tra backend và kết nối dịch vụ TTS, rồi bấm Đọc lại.`);
      onNotify?.('Giọng bác sĩ tạm thời chưa sẵn sàng. Bạn vẫn có thể đọc câu trả lời và thử lại.');
    }
  };

  // Alias for backward compatibility
  const speakText = (text, persona = doctorPersona, reqSpeechId = null) => {
    speakDoctorVoice(text, persona, reqSpeechId);
  };

  // Stop All Speech & Actions immediately
  const handleStop = () => {
    speechIdRef.current++;
    chatAbortRef.current?.abort();
    chatAbortRef.current = null;
    queryStartedRef.current = null;
    disposePlayback();
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    if (recognitionRef.current && isListening) {
      recognitionRef.current.stop();
    }
    setIsVoiceLoading(false);
    setIsSpeaking(false);
    setIsListening(false);
    setIsBusy(false);
    engineRef.current?.stopSpeaking();
    engineRef.current?.applyPose('pose_idle');
  };

  // Switch Doctor Persona without interrupting with unprompted voice greeting
  const handleSwitchDoctor = (persona) => {
    if (persona === doctorPersona && !customModelName) return;

    handleStop();
    setDoctorPersona(persona);
    setCustomModelName(null);
    engineRef.current?.setPersona(persona);

    const name = persona === 'dr_tuan' ? 'BS.CKII Vũ Minh Tuấn' : 'ThS.BS Lê Thanh Mai';
    const greeting =
      persona === 'dr_tuan'
        ? 'Xin chào! Tôi là Bác sĩ Minh Tuấn. Hãy cho tôi biết triệu chứng hoặc câu hỏi sức khỏe của bạn nhé!'
        : 'Xin chào! Tôi là Bác sĩ Thanh Mai. Tôi có thể hỗ trợ gì về thông tin thuốc hoặc chăm sóc sức khỏe cho bạn?';

    setDialogueText(greeting);
    onNotify?.(`Đã chuyển sang ${name}`);
  };

  // Select Consultation Tone & Style (Cảm xúc khi trả lời câu hỏi)
  const handleSelectTone = (tone) => {
    setConsultationTone(tone);
    engineRef.current?.setConsultationTone(tone);
    setShowEmotions(false);

    const toneLabels = {
      empathetic: 'Ân cần & Thấu cảm',
      clinical: 'Khoa học & Chuẩn xác',
      encouraging: 'Lạc quan & Động viên',
      cautious: 'Cẩn trọng & Cảnh báo',
    };
    onNotify?.(`Chế độ tư vấn: ${toneLabels[tone]}`);

    const greetings = {
      empathetic:
        doctorPersona === 'dr_tuan'
          ? 'Chào bạn, Bác sĩ Minh Tuấn luôn lắng nghe và thấu hiểu. Bạn hãy chia sẻ mọi băn khoăn sức khỏe nhé.'
          : 'Chào bạn, Bác sĩ Thanh Mai luôn ở đây đồng hành cùng bạn. Hãy yên tâm chia sẻ mọi khó chịu nhé!',
      clinical:
        doctorPersona === 'dr_tuan'
          ? 'Chào bạn, Bác sĩ Minh Tuấn sẽ phân tích cụ thể cơ chế triệu chứng và đưa ra phác đồ chuẩn mực y khoa.'
          : 'Chào bạn, Bác sĩ Thanh Mai sẵn sàng giải thích cơ chế dược lý và phân tích triệu chứng rõ ràng cho bạn.',
      encouraging:
        doctorPersona === 'dr_tuan'
          ? 'Chào bạn, hãy luôn giữ tinh thần lạc quan nhé! Chúng ta sẽ cùng nhau cải thiện sức khỏe thật tốt!'
          : 'Chào bạn, hãy mỉm cười và giữ tinh thần tích cực nhé! Sức khỏe của bạn sẽ sớm phục hồi thôi!',
      cautious:
        doctorPersona === 'dr_tuan'
          ? 'Chào bạn, Bác sĩ Tuấn sẽ chú ý đặc biệt các dấu hiệu cờ đỏ nguy cơ để đảm bảo an toàn tuyệt đối cho bạn.'
          : 'Chào bạn, Bác sĩ Mai sẽ rà soát kỹ các dấu hiệu cảnh báo nguy hiểm để hướng dẫn xử trí kịp thời.',
    };

    const textGreeting = greetings[tone] || greetings.empathetic;
    setDialogueText(textGreeting);
    speakDoctorVoice(textGreeting, doctorPersona);
  };

  // Process User Query (Voice or Text) via FastAPI /v1/chat
  const handleUserQuery = async (query) => {
    const text = (query || inputText).trim();
    if (!text) return;

    handleStop();
    const currentSpeechId = ++speechIdRef.current;
    const chatController = new AbortController();
    chatAbortRef.current = chatController;
    queryStartedRef.current = performance.now();

    setInputText('');
    setIsBusy(true);
    setIsSpeaking(false);
    setDialogueText(`"${text}" — Bác sĩ đang phân tích...`);
    engineRef.current?.applyPose('pose_thinking');

    try {
      let reply = '';
      if (api) {
        const toneInstruction = {
          empathetic: 'Phong cách tư vấn: Ân cần, thấu cảm, dịu dàng trấn an và quan tâm.',
          clinical: 'Phong cách tư vấn: Khoa học, chuẩn xác, giải thích cơ chế và phác đồ rõ ràng.',
          encouraging: 'Phong cách tư vấn: Lạc quan, khích lệ và truyền niềm tin phục hồi tích cực.',
          cautious: 'Phong cách tư vấn: Cẩn trọng, cảnh báo các dấu hiệu cờ đỏ và nguy cơ biến chứng.',
        }[consultationTone] || '';

        const payload = {
          conversation_id: conversationIdRef.current,
          messages: [
            ...messagesHistoryRef.current.slice(-6),
            { role: 'user', content: `${text} (${toneInstruction} Trả lời trực tiếp, súc tích; giữ đầy đủ dấu hiệu cảnh báo, hướng xử trí và câu hỏi cần làm rõ).` },
          ],
          context: {
            patient_ref: context?.patient_ref || 'BN-LIVE',
            display_name: context?.display_name || 'Bệnh nhân',
            conditions: context?.conditions || [],
          },
          intent_hint: 'auto',
          locale: 'vi-VN',
        };

        const data = await api.request('/v1/chat', {
          method: 'POST',
          body: payload,
          timeoutMs: 15000,
          signal: chatController.signal,
        });

        reply =
          data?.reply ||
          data?.answer?.summary ||
          data?.answer?.clinical_advice ||
          'Bác sĩ đã tiếp nhận thông tin của bạn.';

        if (currentSpeechId !== speechIdRef.current || chatController.signal.aborted) return;

        // Store chat history for natural follow-up reasoning
        messagesHistoryRef.current = [
          ...messagesHistoryRef.current.slice(-6),
          { role: 'user', content: text },
          { role: 'assistant', content: reply },
        ];
      } else {
        reply = 'Chưa kết nối được hệ thống tư vấn. Bạn vui lòng kiểm tra kết nối và gửi lại câu hỏi.';
      }

      // Check race condition
      if (currentSpeechId !== speechIdRef.current) return;

      // Preserve the final answer, especially warnings and follow-up questions.
      const conciseAdvice = normalizeMedicalSpeech(reply);
      window.dispatchEvent(new CustomEvent('medguard:companion-latency', { detail: {
        stage: 'safe_text', persona: doctorPersona,
        totalMs: Math.round(performance.now() - queryStartedRef.current),
      } }));

      // Cả chữ hiển thị trên màn hình và giọng đọc đều là nội dung này!
      setDialogueText(conciseAdvice);
      setIsBusy(false);
      engineRef.current?.applyPose('pose_idle');

      // Nhân vật nói trọn vẹn toàn bộ câu trả lời, không hẹn giờ ngắt
      engineRef.current?.reactToReply(conciseAdvice);
      speakDoctorVoice(conciseAdvice, doctorPersona, currentSpeechId);
    } catch (err) {
      console.error('Companion query failed:', err);
      if (currentSpeechId !== speechIdRef.current || chatController.signal.aborted) return;
      const errMsg =
        'Bác sĩ đã ghi nhận câu hỏi, nhưng kết nối máy chủ tạm thời gián đoạn. Bạn vui lòng thử gửi lại nhé!';
      setDialogueText(errMsg);
      setIsBusy(false);
      engineRef.current?.applyPose('pose_idle');
      speakDoctorVoice(errMsg, doctorPersona, currentSpeechId);
    } finally {
      if (chatAbortRef.current === chatController) chatAbortRef.current = null;
    }
  };

  // Toggle Microphone (Hỗ trợ toàn diện Chrome, Edge, Safari macOS/iOS với getUserMedia permission request)
  const toggleMic = async () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (isListening) {
      try {
        recognitionRef.current?.stop();
      } catch (e) {
        console.warn('Stop mic error:', e);
      }
      setIsListening(false);
      engineRef.current?.applyPose('pose_idle');
      return;
    }

    if (!SpeechRecognition) {
      onNotify?.('Trình duyệt chưa hỗ trợ Web Speech API nhận diện giọng nói. Vui lòng sử dụng Chrome, Edge hoặc Safari mới nhất.');
      return;
    }

    try {
      // 1. Dừng ngay giọng nói bác sĩ nếu đang nói
      if (isSpeaking) {
        handleStop();
      }

      // 2. Yêu cầu quyền Micro trực tiếp qua getUserMedia để bật popup cho phép trên Safari và Chrome
      if (navigator.mediaDevices?.getUserMedia) {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          // Dừng ngay các track stream kiểm tra để nhả mic phần cứng cho Web Speech API
          stream.getTracks().forEach((track) => track.stop());
        } catch (micErr) {
          console.warn('Microphone permission check:', micErr);
          if (micErr.name === 'NotAllowedError' || micErr.name === 'PermissionDeniedError') {
            onNotify?.('Microphone đang bị chặn. Vui lòng nhấn vào biểu tượng ổ khóa / mic trên thanh địa chỉ để Cho phép (Allow).');
            setDialogueText('Vui lòng cấp quyền Microphone trong cài đặt trình duyệt để nói chuyện trực tiếp với Bác sĩ.');
            return;
          }
        }
      }

      // 3. Khởi tạo phiên SpeechRecognition mới
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = 'vi-VN';
      recognition.maxAlternatives = 1;

      let recognizedFinal = '';

      recognition.onstart = () => {
        setIsListening(true);
        engineRef.current?.applyPose('pose_listening');
        setDialogueText('Bác sĩ đang lắng nghe... Mời bạn nói.');
        onNotify?.('Micro đã bật. Bác sĩ đang lắng nghe bạn nói...');
      };

      recognition.onresult = (event) => {
        let interim = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const chunk = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            recognizedFinal += chunk;
          } else {
            interim += chunk;
          }
        }
        const liveText = recognizedFinal || interim;
        if (liveText) {
          setDialogueText(`"${liveText}"`);
        }
      };

      recognition.onerror = (event) => {
        console.warn('Speech recognition error event:', event.error);
        setIsListening(false);
        engineRef.current?.applyPose('pose_idle');

        if (event.error === 'not-allowed') {
          onNotify?.('Quyền Micro bị từ chối. Vui lòng cho phép truy cập Micro trong cài đặt trình duyệt.');
          setDialogueText('Trình duyệt chưa cho phép truy cập Micro. Bạn vui lòng bật quyền Micro hoặc gõ vào ô chat nhé.');
        } else if (event.error === 'no-speech') {
          onNotify?.('Chưa nghe rõ âm thanh. Bạn hãy nói to hơn hoặc lại gần mic nhé.');
          setDialogueText('Bác sĩ chưa nghe rõ. Bạn có thể nhấn lại nút mic để nói hoặc nhập câu hỏi.');
        } else if (event.error === 'network') {
          onNotify?.('Lỗi kết nối mạng dịch vụ nhận diện giọng nói (Web Speech API).');
        } else if (event.error !== 'aborted') {
          onNotify?.(`Lỗi mic: ${event.error}`);
        }
      };

      recognition.onend = () => {
        setIsListening(false);
        const query = recognizedFinal.trim();
        if (query) {
          handleUserQuery(query);
        } else {
          engineRef.current?.applyPose('pose_idle');
        }
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err) {
      console.error('Cannot start speech recognition:', err);
      setIsListening(false);
      engineRef.current?.applyPose('pose_idle');
      onNotify?.('Không thể mở Microphone: ' + (err.message || 'Lỗi không xác định'));
    }
  };

  // Cycle Camera View (Portrait, Waist, Full)
  const handleCycleCamera = () => {
    const next = engineRef.current?.cycleCamera();
    if (next) {
      setCameraPreset(next);
      const labels = {
        portrait: 'Cận cảnh gương mặt (Portrait)',
        waist: 'Nửa người áo blouse (Waist)',
        full: 'Toàn cảnh (Full)',
      };
      onNotify?.(`Góc nhìn: ${labels[next] || next}`);
    }
  };

  // Capture Snapshot
  const handleCapture = () => {
    setIsCapturing(true);
    setTimeout(() => setIsCapturing(false), 260);

    const dataUrl = engineRef.current?.capturePhoto();
    if (dataUrl) {
      onNotify?.('Đã lưu ảnh bác sĩ 3D về thiết bị thành công!');
    }
  };

  // Apply Pose and Expression
  const handleSelectPose = (pose, expr, label) => {
    engineRef.current?.applyPose(pose);
    if (expr) engineRef.current?.setExpression(expr);
    setShowEmotions(false);
    onNotify?.(`Tư thế: ${label}`);
  };

  // Upload Custom 3D Model File (.glb, .gltf, .vrm)
  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    engineRef.current?.loadCustomModelFile(file);
    const cleanName = file.name.replace(/\.[^/.]+$/, '');
    setCustomModelName(cleanName);
    setShowSettings(false);
    onNotify?.(`Đã nạp mô hình 3D: ${file.name}`);
  };

  return (
    <div className="grok-companion-page">
      {/* Ambient Clinical Glow Backdrop */}
      <div className="grok-ambient-glow" />

      {/* Snapshot Shutter Flash */}
      <div className={`grok-capture-flash ${isCapturing ? 'active' : ''}`} />

      {/* Fullscreen 3D WebGL Canvas */}
      <canvas ref={canvasRef} className="grok-canvas-stage" />

      {modelStatus.phase==='error' && <div className="grok-model-error" role="alert">
        <strong>Chưa hiển thị được nhân vật 3D</strong>
        <p>{modelStatus.error}</p>
        <button type="button" onClick={()=>{const e=engineRef.current;if(e?.renderer&&!e.isDestroyed)e.loadModel(e.options.modelUrl);else window.location.reload();}}>Thử tải lại nhân vật</button>
      </div>}
      {/* TOP NAVIGATION BAR */}
      <header className="grok-topbar">
        {/* Left: Back to Chat Button */}
        <div className="grok-topbar-left">
          <button
            type="button"
            className="grok-back-chat-btn"
            onClick={onBackToChat}
            title="Quay lại phòng hội thoại văn bản"
          >
            <ChevronLeft size={18} />
            <span>Quay lại Chat</span>
          </button>

          {/* Quick Doctor Persona Switcher */}
          <div className="grok-doctor-switcher">
            <button
              type="button"
              className={`doctor-switch-pill ${doctorPersona === 'dr_tuan' && !customModelName ? 'active' : ''}`}
              onClick={() => handleSwitchDoctor('dr_tuan')}
              title="BS.CKII Vũ Minh Tuấn - Trưởng khoa Tư vấn"
            >
              <User size={13} />
              <span>BS. Minh Tuấn</span>
            </button>
            <button
              type="button"
              className={`doctor-switch-pill ${doctorPersona === 'dr_mai' && !customModelName ? 'active' : ''}`}
              onClick={() => handleSwitchDoctor('dr_mai')}
              title="ThS.BS Lê Thanh Mai - Bác sĩ Dược & Lâm sàng"
            >
              <User size={13} />
              <span>BS. Thanh Mai</span>
            </button>
          </div>
        </div>

        {/* Center: Live Status Indicator */}
        <div className="grok-model-badge">
          <span className={`grok-status-dot ${isBusy || isVoiceLoading ? 'busy' : isSpeaking ? 'speaking' : ''}`} />
          <span>{modelStatus.phase==='error' ? 'Lỗi tải nhân vật' : modelStatus.phase==='loading' ? 'Đang tải nhân vật…' : isBusy ? 'Đang suy nghĩ...' : isVoiceLoading ? 'Đang chuẩn bị giọng…' : isSpeaking ? 'Đang tư vấn...' : 'Sẵn sàng tư vấn'}</span>
        </div>

        {/* Right: Snapshot & Settings Buttons */}
        <div className="grok-topbar-right">
          <button
            type="button"
            className="grok-capture-btn"
            onClick={handleCapture}
            title="Chụp ảnh bác sĩ 3D (PNG)"
          >
            <Camera size={15} />
            <span>Chụp ảnh</span>
          </button>

          <button
            type="button"
            className="grok-settings-btn"
            onClick={() => setShowSettings(true)}
            title="Cài đặt bác sĩ & mô hình 3D"
          >
            <Settings size={18} />
          </button>
        </div>
      </header>

      {/* FLOATING DIALOGUE / CLINICAL SUBTITLE CARD (DOCKED ABOVE BOTTOM DOCK - NEVER COVERS FACE) */}
      {dialogueText && (
        <section className="grok-dialogue-overlay" aria-live="polite">
          <div className="grok-speech-bubble">
            <div className="grok-bubble-header">
              <div className="grok-doctor-title-tag">
                <span className="grok-tag-pulse" />
                <span className="grok-bubble-author">{currentDoctorName}</span>
                <span className="grok-bubble-role">• {currentDoctorRole}</span>
              </div>
              {isSpeaking && (
                <div className="grok-voice-waves" aria-label="Đang phát giọng nói">
                  <span />
                  <span />
                  <span />
                </div>
              )}
            </div>
            <p className="grok-bubble-text">{dialogueText}</p>
            {voiceError && <p role="alert">{voiceError}</p>}
            <button type="button" className="grok-back-chat-btn" disabled={isMuted||isVoiceLoading||isBusy||isSpeaking} onClick={()=>speakDoctorVoice(dialogueText,doctorPersona)}>Đọc lại</button>
          </div>
        </section>
      )}

      {/* BOTTOM FLOATING CONTROL DOCK */}
      <footer className="grok-bottom-dock">
        {/* UPPER PILL CONTROL BAR */}
        <div className="grok-controls-pill-row">
          {/* Camera Angle Toggle */}
          <button
            type="button"
            className="grok-dock-btn"
            onClick={handleCycleCamera}
            title="Đổi góc quay (Cận cảnh / Nửa người / Toàn thân)"
            aria-label="Góc quay camera"
          >
            <Camera size={20} />
          </button>

          {/* Voice Mute / Speaker Toggle */}
          <button
            type="button"
            className={`grok-dock-btn ${isMuted ? 'active' : ''}`}
            onClick={() => {
              mutedRef.current = !isMuted;
              setIsMuted(!isMuted);
              if (!isMuted && (isSpeaking || isVoiceLoading)) handleStop();
              onNotify?.(isMuted ? 'Đã bật giọng nói bác sĩ' : 'Đã tắt giọng nói bác sĩ');
            }}
            title={isMuted ? 'Bật giọng nói' : 'Tắt giọng nói'}
            aria-label="Âm thanh"
          >
            {isMuted ? <VolumeX size={20} /> : <Volume2 size={20} />}
          </button>

          {/* Center Voice Mic Call Button */}
          <button
            type="button"
            className={`grok-mic-primary-btn ${isListening ? 'listening' : ''}`}
            onClick={toggleMic}
            title={isListening ? 'Dừng lắng nghe' : 'Nói trực tiếp với bác sĩ'}
            aria-label="Micro trò chuyện"
          >
            <Mic size={24} />
          </button>

          {/* Consultation Emotional Tone & Style Toggle */}
          <button
            type="button"
            className={`grok-dock-btn ${showEmotions ? 'active' : ''}`}
            onClick={() => setShowEmotions(!showEmotions)}
            title="Cảm xúc & Phong cách tư vấn của Bác sĩ"
            aria-label="Cảm xúc tư vấn"
          >
            <span style={{ fontSize: '18px' }}>
              {consultationTone === 'empathetic' ? '💖' : consultationTone === 'clinical' ? '🩺' : consultationTone === 'encouraging' ? '🌟' : '⚠️'}
            </span>
          </button>

          {/* Doctor Switcher Quick Toggle */}
          <button
            type="button"
            className="grok-dock-btn"
            onClick={() => handleSwitchDoctor(doctorPersona === 'dr_tuan' ? 'dr_mai' : 'dr_tuan')}
            title={`Đổi sang ${doctorPersona === 'dr_tuan' ? 'BS. Thanh Mai (Nữ)' : 'BS. Minh Tuấn (Nam)'}`}
            aria-label="Đổi bác sĩ"
          >
            <User size={20} />
          </button>
        </div>

        {/* LOWER INPUT BAR ("Hỏi bác sĩ bất kỳ điều gì...") */}
        <form
          className="grok-input-pill-row"
          onSubmit={(e) => {
            e.preventDefault();
            handleUserQuery();
          }}
        >
          <input
            type="text"
            className="grok-text-input"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder={`Hỏi ${currentDoctorName} về triệu chứng, đơn thuốc, sức khỏe...`}
            aria-label="Nhập câu hỏi cho bác sĩ"
          />

          {isSpeaking || isListening || isBusy || isVoiceLoading ? (
            <button
              type="button"
              className="grok-stop-action-btn"
              onClick={handleStop}
              title="Dừng phản hồi"
            >
              <span className="stop-square" />
              <span>Dừng</span>
            </button>
          ) : (
            <button
              type="submit"
              className="grok-send-action-btn"
              disabled={!inputText.trim()}
              title="Gửi câu hỏi"
            >
              <Send size={18} />
            </button>
          )}
        </form>
      </footer>

      {/* CONSULTATION EMOTIONAL TONE & STYLE MENU */}
      {showEmotions && (
        <div className="grok-popover-menu" role="menu">
          <span className="grok-popover-title">Cảm Xúc & Phong Cách Tư Vấn</span>
          <button
            type="button"
            className={`grok-popover-item ${consultationTone === 'empathetic' ? 'active' : ''}`}
            onClick={() => handleSelectTone('empathetic')}
          >
            <span style={{ fontSize: '20px' }}>💖</span>
            <div className="grok-popover-text">
              <strong>Ân cần & Thấu cảm</strong>
              <small>Trấn an dịu dàng, lắng nghe, nét mặt ấm áp</small>
            </div>
          </button>
          <button
            type="button"
            className={`grok-popover-item ${consultationTone === 'clinical' ? 'active' : ''}`}
            onClick={() => handleSelectTone('clinical')}
          >
            <span style={{ fontSize: '20px' }}>🩺</span>
            <div className="grok-popover-text">
              <strong>Khoa học & Chuẩn xác</strong>
              <small>Phân tích cơ chế bệnh học, phác đồ rõ ràng</small>
            </div>
          </button>
          <button
            type="button"
            className={`grok-popover-item ${consultationTone === 'encouraging' ? 'active' : ''}`}
            onClick={() => handleSelectTone('encouraging')}
          >
            <span style={{ fontSize: '20px' }}>🌟</span>
            <div className="grok-popover-text">
              <strong>Lạc quan & Động viên</strong>
              <small>Truyền năng lượng tích cực, nụ cười rạng rỡ</small>
            </div>
          </button>
          <button
            type="button"
            className={`grok-popover-item ${consultationTone === 'cautious' ? 'active' : ''}`}
            onClick={() => handleSelectTone('cautious')}
          >
            <span style={{ fontSize: '20px' }}>⚠️</span>
            <div className="grok-popover-text">
              <strong>Cẩn trọng & Cảnh báo</strong>
              <small>Cảnh giác cờ đỏ (red flags), dặn dò an toàn</small>
            </div>
          </button>
        </div>
      )}

      {/* SETTINGS MODAL */}
      {showSettings && (
        <div className="grok-settings-backdrop" onClick={() => setShowSettings(false)}>
          <div className="grok-settings-card" onClick={(e) => e.stopPropagation()}>
            <h3>
              <span>Cài Đặt Bác Sĩ & Mô Hình 3D</span>
              <button
                type="button"
                className="icon-button"
                onClick={() => setShowSettings(false)}
                title="Đóng"
              >
                <X size={18} />
              </button>
            </h3>

            {/* Choose Doctor Persona */}
            <div className="grok-settings-group">
              <label>Chọn Bác sĩ tư vấn:</label>
              <p className="doctor-voice-description">Nam: giọng Nam Minh trầm, rõ ràng. Nữ: giọng Hoài My dịu, nhịp nói chậm vừa phải. Giọng đọc được tạo riêng cho từng nhân vật.</p>
              <p className="doctor-voice-description" role="status">{voiceConfigError || (voiceConfig ? `Giọng đang cấu hình trên máy chủ: ${voiceConfig.profiles[doctorPersona].voice} · tốc độ ${voiceConfig.profiles[doctorPersona].rate} · cao độ ${voiceConfig.profiles[doctorPersona].pitch} · bản ${voiceConfig.revision}` : 'Đang kiểm tra cấu hình giọng nói…')}</p>
              <button type="button" className="grok-back-chat-btn" disabled={!voiceConfig||isVoiceLoading||isMuted} onClick={()=>speakDoctorVoice('Xin chào bạn. Tôi sẽ lắng nghe và giải thích rõ ràng từng thông tin, để bạn dễ theo dõi.',doctorPersona)}>Nghe thử giọng bác sĩ</button>
              <button type="button" className="grok-back-chat-btn" disabled={modelStatus.phase!=='ready'||isSpeaking||isVoiceLoading} onClick={()=>{engineRef.current?.applyPose('pose_wave');setShowSettings(false);}}>Xem thử cử chỉ chào</button>
              <div className="doctor-preset-grid">
                <button
                  type="button"
                  className={`doctor-card-btn ${doctorPersona === 'dr_tuan' && !customModelName ? 'active' : ''}`}
                  onClick={() => {
                    handleSwitchDoctor('dr_tuan');
                    setShowSettings(false);
                  }}
                >
                  <div className="card-avatar">👨‍⚕️</div>
                  <div className="card-info">
                    <strong>BS.CKII Vũ Minh Tuấn</strong>
                    <span>Nam • Áo Blouse trắng & Ống nghe</span>
                  </div>
                </button>

                <button
                  type="button"
                  className={`doctor-card-btn ${doctorPersona === 'dr_mai' && !customModelName ? 'active' : ''}`}
                  onClick={() => {
                    handleSwitchDoctor('dr_mai');
                    setShowSettings(false);
                  }}
                >
                  <div className="card-avatar">👩‍⚕️</div>
                  <div className="card-info">
                    <strong>ThS.BS Lê Thanh Mai</strong>
                    <span>Nữ • Áo Blouse trắng & Ống nghe</span>
                  </div>
                </button>
              </div>
            </div>

            {/* Upload Custom 3D Model */}
            <div className="grok-settings-group">
              <label>Hoặc nạp mô hình 3D bác sĩ riêng (.glb, .gltf, .vrm):</label>
              <input
                ref={fileInputRef}
                type="file"
                accept=".glb,.gltf,.vrm"
                style={{ display: 'none' }}
                onChange={handleFileUpload}
              />
              <button
                type="button"
                className="grok-file-upload-btn"
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload size={18} />
                <span>Tải lên file .GLB / .VRM từ máy tính</span>
              </button>
            </div>

            <button
              type="button"
              className="grok-close-settings-btn"
              onClick={() => setShowSettings(false)}
            >
              Hoàn tất
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
