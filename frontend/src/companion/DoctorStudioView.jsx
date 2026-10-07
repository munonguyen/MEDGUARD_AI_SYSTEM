import { useEffect, useRef, useState } from 'react';
import {
  ArrowUpRight,
  Heart,
  Mic,
  MicOff,
  Sparkles,
  Square,
  Upload,
  Volume2,
  VolumeX,
} from 'lucide-react';
import { DoctorAvatar3D } from './DoctorAvatar3D';
import './DoctorStudioView.css';

/**
 * MedGuard 3D Consultation Studio (Phòng Tư Vấn Trực Quan)
 * Inspired by Grok 3D Companion Studio layout.
 */
export function DoctorStudioView({
  persona = 'dr_mai',
  speakingText = null,
  isBusy = false,
  autoSpeak = false,
  setAutoSpeak = null,
  onSpeechInput = null,
  children, // The chat conversation pane
  onNotify = null,
}) {
  const canvasRef = useRef(null);
  const avatarRef = useRef(null);
  const fileInputRef = useRef(null);
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef(null);

  // Handle uploading custom GLB avatar (from Ready Player Me, VRoid, Rodin, Meshy)
  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    avatarRef.current?.setCustomGLB(url);
    onNotify?.(`Đã nạp model 3D: ${file.name}`);
  };

  // Initialize Speech Recognition
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = 'vi-VN';

      recognition.onstart = () => setIsListening(true);
      recognition.onend = () => setIsListening(false);
      recognition.onerror = () => setIsListening(false);
      recognition.onresult = (event) => {
        const transcript = event.results?.[0]?.[0]?.transcript;
        if (transcript && onSpeechInput) {
          onSpeechInput(transcript);
          onNotify?.(`Đã nhận diện: "${transcript}"`);
        }
      };

      recognitionRef.current = recognition;
    }
  }, [onSpeechInput, onNotify]);

  const toggleMic = () => {
    if (!recognitionRef.current) {
      onNotify?.('Trình duyệt chưa hỗ trợ nhận diện giọng nói Web Speech');
      return;
    }
    if (isListening) {
      recognitionRef.current.stop();
    } else {
      try {
        recognitionRef.current.start();
        onNotify?.('Đang lắng nghe triệu chứng của bạn…');
      } catch {
        recognitionRef.current.stop();
      }
    }
  };

  // Mount 3D Engine
  useEffect(() => {
    if (!canvasRef.current) return;

    const avatar = new DoctorAvatar3D(canvasRef.current, { persona });
    avatarRef.current = avatar;

    const handleResize = () => {
      if (canvasRef.current) {
        avatar.resize(canvasRef.current.clientWidth, canvasRef.current.clientHeight);
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      avatar.destroy();
      avatarRef.current = null;
    };
  }, []);

  // Update Persona
  useEffect(() => {
    if (!avatarRef.current) return;
    avatarRef.current.setPersona(persona);
  }, [persona]);

  // Speaking state & Lip-sync
  useEffect(() => {
    if (!avatarRef.current) return;
    if (speakingText && speakingText.trim()) {
      avatarRef.current.startSpeaking(speakingText);
    } else {
      avatarRef.current.stopSpeaking();
      if (!isBusy) {
        avatarRef.current.setEmotion('idle');
      }
    }
  }, [speakingText, isBusy]);

  // Thinking state
  useEffect(() => {
    if (!avatarRef.current) return;
    if (isBusy) {
      avatarRef.current.setEmotion('thinking');
    }
  }, [isBusy]);

  // Handle Play Sample Voice Greeting
  const handlePlayGreeting = () => {
    if (typeof window === 'undefined' || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();

    const name = persona === 'dr_mai' ? 'Bác sĩ Thanh Mai' : 'Bác sĩ Minh Tuấn';
    const text = `Xin chào bạn, tôi là ${name}. Hãy chia sẻ triệu chứng hoặc thắc mắc về sức khỏe của bạn để tôi tư vấn chuẩn y khoa nhé!`;

    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = 'vi-VN';
    utter.rate = 1.0;

    avatarRef.current?.startSpeaking(text);

    utter.onend = () => avatarRef.current?.stopSpeaking();
    utter.onerror = () => avatarRef.current?.stopSpeaking();

    window.speechSynthesis.speak(utter);
    onNotify?.(`Bác sĩ ảo đang giới thiệu`);
  };

  // Stop all audio
  const handleStopAudio = () => {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    avatarRef.current?.stopSpeaking();
    onNotify?.('Đã dừng phát âm thanh');
  };

  return (
    <div className="consultation-studio-workspace">
      {/* LEFT 3D STUDIO STAGE */}
      <section className="studio-stage-pane" aria-label="Phòng tư vấn 3D với Bác sĩ ảo">
        {/* Top Badges */}
        <div className="studio-stage-header">
          <div className="studio-status-indicator">
            <span className="status-dot" />
            <span>Sẵn sàng trò chuyện</span>
          </div>
          <div className="studio-stage-header-actions">
            <input
              ref={fileInputRef}
              type="file"
              accept=".glb,.gltf"
              style={{ display: 'none' }}
              onChange={handleFileUpload}
            />
            <button
              type="button"
              className="studio-upload-glb-btn"
              onClick={() => fileInputRef.current?.click()}
              title="Tải model .GLB tùy chỉnh (từ Ready Player Me / VRoid / Rodin / Meshy)"
            >
              <Upload size={12} />
              <span>Nạp GLB</span>
            </button>
            <div className="studio-ai-tag">NHÂN VẬT AI</div>
          </div>
        </div>

        {/* 3D WebGL Canvas */}
        <canvas ref={canvasRef} className="studio-canvas-stage" />

        {/* Stage Bottom Overlay */}
        <div className="studio-stage-overlay">
          <span className="studio-motto">CHĂM SÓC BẮT ĐẦU TỪ LẮNG NGHE</span>
          <h2>Luôn ở đây, cùng bạn.</h2>
          <p>
            Trợ lý sức khỏe AI - {persona === 'dr_mai' ? 'Nhân vật nữ' : 'Nhân vật nam'}
          </p>

          {/* Voice Controls */}
          <div className="studio-voice-controls">
            <button
              type="button"
              className={`studio-mic-btn ${isListening ? 'listening' : ''}`}
              onClick={toggleMic}
              title={isListening ? 'Dừng lắng nghe' : 'Bật micro để nhập giọng nói'}
              aria-label="Micro giọng nói"
            >
              <Mic size={24} />
            </button>
            <button
              type="button"
              className="studio-icon-btn"
              onClick={handlePlayGreeting}
              title="Nghe bác sĩ chào hỏi"
              aria-label="Nghe giới thiệu"
            >
              <Volume2 size={20} />
            </button>
            <button
              type="button"
              className="studio-icon-btn"
              onClick={handleStopAudio}
              title="Dừng âm thanh"
              aria-label="Dừng âm thanh"
            >
              <Square size={16} />
            </button>
          </div>

          {/* Auto Read Checkbox */}
          {setAutoSpeak && (
            <label className="studio-auto-label">
              <input
                type="checkbox"
                checked={autoSpeak}
                onChange={(e) => setAutoSpeak(e.target.checked)}
              />
              <span>Tự đọc phản hồi đã kiểm tra</span>
            </label>
          )}

          <small className="studio-subtext">
            Bật micro để nhập giọng nói. Trình duyệt có thể xử lý âm thanh qua dịch vụ bên ngoài.
          </small>
        </div>
      </section>

      {/* RIGHT CONVERSATION PANE */}
      <section className="studio-chat-pane" aria-label="Khu vực trò chuyện">
        <div className="studio-chat-header">
          <span>KHÔNG GIAN CỦA BẠN</span>
          <h3>Cuộc trò chuyện</h3>
        </div>
        <div className="studio-chat-body">{children}</div>
      </section>
    </div>
  );
}
