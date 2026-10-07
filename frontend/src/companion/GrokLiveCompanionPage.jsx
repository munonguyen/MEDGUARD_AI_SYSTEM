import { useEffect, useRef, useState } from 'react';
import {
  Camera,
  Maximize2,
  Menu,
  Mic,
  MicOff,
  Send,
  Settings,
  Smile,
  Square,
  Upload,
  Volume2,
  VolumeX,
  X,
} from 'lucide-react';
import { VRMAvatarEngine } from './VRMAvatarEngine';
import './GrokLiveCompanionPage.css';

/**
 * GrokLiveCompanionPage
 * Dedicated Fullscreen Interactive 3D Companion Page (Web & Mobile).
 * Direct 1-on-1 Realtime Voice & Text Communication.
 * Features:
 * - High-fidelity Anime Cel-Shading & Spring-Bone Hair/Cloth Physics
 * - Glassmorphic Bottom Dock matching Grok Companion
 * - Web Speech Recognition & Speech Synthesis with Real-Time Lip-Sync
 * - Camera Zoom Presets (Waist, Portrait, Full)
 * - Poses & Facial Expressions (Hand to cheek, Wave, Think, Cheer)
 * - High-Res Capture Snapshot
 */
export function GrokLiveCompanionPage({
  api = null,
  context = {},
  onBackToChat = null,
  onNotify = null,
}) {
  const canvasRef = useRef(null);
  const engineRef = useRef(null);
  const fileInputRef = useRef(null);
  const recognitionRef = useRef(null);

  // States
  const [modelUrl, setModelUrl] = useState('/models/AniGrok.vrm');
  const [modelName, setModelName] = useState('Ani (Grok Style)');
  const [cameraPreset, setCameraPreset] = useState('waist');
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [isBusy, setIsBusy] = useState(false);
  const [inputText, setInputText] = useState('');
  const [dialogueText, setDialogueText] = useState('Xin chào! Tôi là Ani, trợ lý ảo 3D đồng hành cùng bạn. Bạn cần tôi giúp gì hôm nay?');
  const [showEmotions, setShowEmotions] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [isCapturing, setIsCapturing] = useState(false);

  // Mount 3D Engine
  useEffect(() => {
    if (!canvasRef.current) return;

    const engine = new VRMAvatarEngine(canvasRef.current, {
      modelUrl,
      cameraPreset,
      onLoaded: (vrm) => {
        onNotify?.(`Đã tải nhân vật 3D: ${modelName}`);
      },
      onError: (err) => {
        onNotify?.('Không thể tải model VRM, đang dùng model mặc định');
      },
    });
    engineRef.current = engine;

    const handleResize = () => {
      if (canvasRef.current) {
        engine.resize(window.innerWidth, window.innerHeight);
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      engine.destroy();
      engineRef.current = null;
    };
  }, [modelUrl]);

  // Web Speech API Initialization
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
        if (transcript) {
          handleUserQuery(transcript);
        }
      };

      recognitionRef.current = recognition;
    }
  }, []);

  // Text-To-Speech Playback with 3D Lip-Sync
  const speakText = (text) => {
    if (isMuted || typeof window === 'undefined' || !window.speechSynthesis) return;

    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = 'vi-VN';
    utter.rate = 1.05;
    utter.pitch = 1.1; // anime slightly cheerful tone

    utter.onstart = () => {
      setIsSpeaking(true);
      engineRef.current?.startSpeaking(text);
    };

    utter.onend = () => {
      setIsSpeaking(false);
      engineRef.current?.stopSpeaking();
    };

    utter.onerror = () => {
      setIsSpeaking(false);
      engineRef.current?.stopSpeaking();
    };

    window.speechSynthesis.speak(utter);
  };

  // Stop All Speech & Actions
  const handleStop = () => {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    if (recognitionRef.current && isListening) {
      recognitionRef.current.stop();
    }
    setIsSpeaking(false);
    setIsListening(false);
    setIsBusy(false);
    engineRef.current?.stopSpeaking();
    engineRef.current?.applyPose('pose_idle');
  };

  // Process User Query (Voice or Text)
  const handleUserQuery = async (query) => {
    const text = (query || inputText).trim();
    if (!text || isBusy) return;

    setInputText('');
    setIsBusy(true);
    setDialogueText(`"${text}" — Đang suy nghĩ...`);
    engineRef.current?.applyPose('pose_thinking');

    try {
      let reply = '';
      if (api) {
        const payload = {
          message: text,
          context: {
            patient_ref: context.patient_ref,
            display_name: context.display_name,
            conditions: context.conditions,
          },
        };
        const data = await api.request('/v1/chat/message', {
          method: 'POST',
          body: payload,
          timeoutMs: 15000,
        });
        reply = data?.answer?.summary || data?.message || data?.text || 'Tôi đã tiếp nhận câu hỏi của bạn.';
      } else {
        reply = `Cảm ơn bạn đã hỏi về: "${text}". Tôi đang hỗ trợ bạn với các lời khuyên y khoa và chăm sóc sức khỏe.`;
      }

      setDialogueText(reply);
      setIsBusy(false);

      // Trigger companion reaction pose
      engineRef.current?.applyPose('pose_idle');
      speakText(reply);
    } catch (err) {
      const errMsg = 'Tôi đang lắng nghe nhưng chưa kết nối được máy chủ. Bạn có thể hỏi lại nhé!';
      setDialogueText(errMsg);
      setIsBusy(false);
      engineRef.current?.applyPose('pose_idle');
      speakText(errMsg);
    }
  };

  // Toggle Microphone
  const toggleMic = () => {
    if (!recognitionRef.current) {
      onNotify?.('Trình duyệt chưa hỗ trợ Web Speech API nhận diện giọng nói');
      return;
    }

    if (isListening) {
      recognitionRef.current.stop();
    } else {
      try {
        if (isSpeaking) handleStop();
        recognitionRef.current.start();
        onNotify?.('Đang lắng nghe bạn nói...');
      } catch {
        recognitionRef.current.stop();
      }
    }
  };

  // Cycle Camera View
  const handleCycleCamera = () => {
    const next = engineRef.current?.cycleCamera();
    if (next) {
      setCameraPreset(next);
      onNotify?.(`Góc quay: ${next === 'portrait' ? 'Cận cảnh (Portrait)' : next === 'waist' ? 'Nửa người (Waist)' : 'Toàn thân (Full)'}`);
    }
  };

  // Capture Snapshot
  const handleCapture = () => {
    setIsCapturing(true);
    setTimeout(() => setIsCapturing(false), 260);

    const dataUrl = engineRef.current?.capturePhoto();
    if (dataUrl) {
      onNotify?.('Đã chụp và lưu ảnh nhân vật 3D thành công!');
    }
  };

  // Apply Pose and Expression
  const handleSelectPose = (pose, expr, label) => {
    engineRef.current?.applyPose(pose);
    if (expr) engineRef.current?.setExpression(expr);
    setShowEmotions(false);
    onNotify?.(`Tư thế: ${label}`);
  };

  // Upload Custom VRM
  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    engineRef.current?.loadCustomVRMFile(file);
    setModelName(file.name.replace(/\.[^/.]+$/, ''));
    setShowSettings(false);
    onNotify?.(`Đã nạp file VRM: ${file.name}`);
  };

  return (
    <div className="grok-companion-page">
      {/* Ambient Radial Glow */}
      <div className="grok-ambient-glow" />

      {/* Snapshot Shutter Flash */}
      <div className={`grok-capture-flash ${isCapturing ? 'active' : ''}`} />

      {/* Fullscreen 3D WebGL Canvas */}
      <canvas ref={canvasRef} className="grok-canvas-stage" />

      {/* TOP NAVIGATION BAR */}
      <header className="grok-topbar">
        <button
          type="button"
          className="grok-menu-btn"
          onClick={onBackToChat}
          title="Quay lại giao diện trò chuyện MedGuard"
          aria-label="Menu MedGuard"
        >
          <Menu size={20} />
        </button>

        <div className="grok-model-badge">
          <span className="grok-status-dot" />
          <span>{modelName}</span>
        </div>

        <button
          type="button"
          className="grok-capture-btn"
          onClick={handleCapture}
          title="Chụp ảnh nhân vật 3D (Capture)"
        >
          <Camera size={16} />
          <span>Capture</span>
        </button>
      </header>

      {/* FLOATING DIALOGUE / SUBTITLE CARD */}
      {dialogueText && (
        <section className="grok-dialogue-overlay" aria-live="polite">
          <div className="grok-speech-bubble">
            <div className="grok-bubble-header">
              <span className="grok-bubble-author">ANI • 3D COMPANION</span>
              {isSpeaking && (
                <div className="grok-voice-waves" aria-label="Đang phát giọng nói">
                  <span />
                  <span />
                  <span />
                </div>
              )}
            </div>
            <p className="grok-bubble-text">{dialogueText}</p>
          </div>
        </section>
      )}

      {/* BOTTOM FLOATING CONTROL DOCK */}
      <footer className="grok-bottom-dock">
        {/* UPPER PILL CONTROL BAR */}
        <div className="grok-controls-pill-row">
          {/* Camera Zoom Toggle */}
          <button
            type="button"
            className="grok-dock-btn"
            onClick={handleCycleCamera}
            title="Đổi góc máy (Cận cảnh / Nửa người / Toàn thân)"
            aria-label="Góc quay camera"
          >
            <Camera size={20} />
          </button>

          {/* Voice Mute / Speaker Toggle */}
          <button
            type="button"
            className={`grok-dock-btn ${isMuted ? 'active' : ''}`}
            onClick={() => {
              setIsMuted(!isMuted);
              if (!isMuted && isSpeaking) handleStop();
              onNotify?.(isMuted ? 'Đã bật giọng nói' : 'Đã tắt giọng nói');
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
            title={isListening ? 'Dừng lắng nghe' : 'Nói trực tiếp với nhân vật'}
            aria-label="Micro trò chuyện"
          >
            <Mic size={24} />
          </button>

          {/* Settings Modal Toggle */}
          <button
            type="button"
            className="grok-dock-btn"
            onClick={() => setShowSettings(true)}
            title="Cài đặt mô hình & Giọng nói"
            aria-label="Cài đặt"
          >
            <Settings size={20} />
          </button>

          {/* Emotions & Poses Popover Toggle */}
          <button
            type="button"
            className={`grok-dock-btn ${showEmotions ? 'active' : ''}`}
            onClick={() => setShowEmotions(!showEmotions)}
            title="Biểu cảm & Tư thế tạo dáng"
            aria-label="Biểu cảm"
          >
            <Smile size={20} />
          </button>
        </div>

        {/* LOWER INPUT BAR ("Ask Anything") */}
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
            placeholder="Ask Anything..."
            aria-label="Nhập câu hỏi"
          />

          {isSpeaking || isListening || isBusy ? (
            <button
              type="button"
              className="grok-stop-action-btn"
              onClick={handleStop}
              title="Dừng phản hồi"
            >
              <span className="stop-square" />
              <span>Stop</span>
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

      {/* POSE & EMOTION POPUP MENU */}
      {showEmotions && (
        <div className="grok-popover-menu" role="menu">
          <span className="grok-popover-title">Tư thế & Biểu cảm</span>
          <button
            type="button"
            className="grok-popover-item"
            onClick={() => handleSelectPose('pose_hand_to_cheek', 'relaxed', 'Đưa tay áp má (Grok Pose)')}
          >
            <span>✨</span>
            <span>Đưa tay áp má (Grok Pose)</span>
          </button>
          <button
            type="button"
            className="grok-popover-item"
            onClick={() => handleSelectPose('pose_wave', 'happy', 'Vẫy tay chào')}
          >
            <span>👋</span>
            <span>Vẫy tay chào (Wave)</span>
          </button>
          <button
            type="button"
            className="grok-popover-item"
            onClick={() => handleSelectPose('pose_cheer', 'happy', 'Đáng yêu & Cười tươi')}
          >
            <span>🌸</span>
            <span>Đáng yêu & Cười tươi</span>
          </button>
          <button
            type="button"
            className="grok-popover-item"
            onClick={() => handleSelectPose('pose_thinking', 'surprised', 'Suy nghĩ thấu đáo')}
          >
            <span>🤔</span>
            <span>Suy nghĩ (Thinking)</span>
          </button>
          <button
            type="button"
            className="grok-popover-item"
            onClick={() => handleSelectPose('pose_idle', 'neutral', 'Tự nhiên')}
          >
            <span>😊</span>
            <span>Tự nhiên (Idle)</span>
          </button>
        </div>
      )}

      {/* SETTINGS MODAL */}
      {showSettings && (
        <div className="grok-settings-backdrop" onClick={() => setShowSettings(false)}>
          <div className="grok-settings-card" onClick={(e) => e.stopPropagation()}>
            <h3>
              <span>Cài Đặt Nhân Vật 3D</span>
              <button
                type="button"
                className="icon-button"
                onClick={() => setShowSettings(false)}
                title="Đóng"
              >
                <X size={18} />
              </button>
            </h3>

            {/* Choose Preset Model */}
            <div className="grok-settings-group">
              <label>Chọn nhân vật có sẵn:</label>
              <select
                className="grok-select-input"
                value={modelUrl}
                onChange={(e) => {
                  const url = e.target.value;
                  setModelUrl(url);
                  setModelName(e.target.options[e.target.selectedIndex].text);
                  setShowSettings(false);
                }}
              >
                <option value="/models/AniGrok.vrm">Ani (Grok 3D Companion Style)</option>
                <option value="/models/AliciaSolid.vrm">Alicia Solid (Classic Anime VRM)</option>
                <option value="/models/Godette.vrm">Godette (Godot Anime Style)</option>
                <option value="/models/VRM1_Sample.vrm">VRM 1.0 Sample</option>
              </select>
            </div>

            {/* Upload Custom VRM */}
            <div className="grok-settings-group">
              <label>Hoặc nạp file VRM / GLB từ máy tính:</label>
              <input
                ref={fileInputRef}
                type="file"
                accept=".vrm,.glb,.gltf"
                style={{ display: 'none' }}
                onChange={handleFileUpload}
              />
              <button
                type="button"
                className="grok-file-upload-btn"
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload size={18} />
                <span>Chọn file .VRM / .GLB để tải lên</span>
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
