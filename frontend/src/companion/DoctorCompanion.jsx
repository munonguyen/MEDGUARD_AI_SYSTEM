import { useEffect, useRef, useState } from 'react';
import {
  Activity,
  Bot,
  ChevronDown,
  Maximize2,
  Minimize2,
  Sparkles,
  Upload,
  User,
  Volume2,
  VolumeX,
  X,
} from 'lucide-react';
import { DoctorAvatar3D } from './DoctorAvatar3D';
import './DoctorCompanion.css';

/**
 * MedGuard 3D Doctor Companion (Grok-inspired Web Assistant)
 */
export function DoctorCompanion({
  isOpen: controlledIsOpen = undefined,
  setIsOpen: controlledSetIsOpen = undefined,
  speakingText = null,
  isBusy = false,
  lastAnswer = null,
  autoSpeak = false,
  setAutoSpeak = null,
  onNotify = null,
}) {
  const [internalIsOpen, setInternalIsOpen] = useState(false);
  const isOpen = controlledIsOpen !== undefined ? controlledIsOpen : internalIsOpen;
  const setIsOpen = controlledSetIsOpen !== undefined ? controlledSetIsOpen : setInternalIsOpen;

  const [isExpanded, setIsExpanded] = useState(false);
  const [persona, setPersona] = useState('dr_tuan'); // 'dr_tuan' | 'dr_mai' | 'custom'
  const [customModelName, setCustomModelName] = useState(null);
  const [isMuted, setIsMuted] = useState(false);
  const [companionStatus, setCompanionStatus] = useState('Sẵn sàng tư vấn');

  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const avatarInstanceRef = useRef(null);
  const fileInputRef = useRef(null);

  // Initialize Three.js Engine
  useEffect(() => {
    if (!isOpen || !canvasRef.current) return;

    const avatar = new DoctorAvatar3D(canvasRef.current, { persona });
    avatarInstanceRef.current = avatar;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect) {
          const { width, height } = entry.contentRect;
          avatar.resize(width, height);
        }
      }
    });

    if (canvasRef.current) {
      resizeObserver.observe(canvasRef.current);
    }

    return () => {
      resizeObserver.disconnect();
      avatar.destroy();
      avatarInstanceRef.current = null;
    };
  }, [isOpen]);

  // Update Persona
  useEffect(() => {
    if (!avatarInstanceRef.current) return;
    if (persona === 'custom') return;
    avatarInstanceRef.current.setPersona(persona);
  }, [persona]);

  // Handle Busy / Thinking State
  useEffect(() => {
    if (!avatarInstanceRef.current) return;
    if (isBusy) {
      avatarInstanceRef.current.setEmotion('thinking');
      setCompanionStatus('Đang đối chiếu phác đồ…');
    } else if (!speakingText) {
      avatarInstanceRef.current.setEmotion('idle');
      setCompanionStatus('Sẵn sàng lắng nghe');
    }
  }, [isBusy, speakingText]);

  // Handle Speech & Lip-Sync
  useEffect(() => {
    if (!avatarInstanceRef.current) return;

    if (speakingText && speakingText.trim() && !isMuted) {
      avatarInstanceRef.current.startSpeaking(speakingText);
      setCompanionStatus('Đang giải thích lâm sàng…');
    } else {
      avatarInstanceRef.current.stopSpeaking();
      if (!isBusy) {
        avatarInstanceRef.current.setEmotion('idle');
        setCompanionStatus('Sẵn sàng lắng nghe');
      }
    }
  }, [speakingText, isMuted, isBusy]);

  // Handle Clinical Severity Reaction
  useEffect(() => {
    if (!avatarInstanceRef.current || !lastAnswer) return;
    const urgency = (lastAnswer.urgency || '').toUpperCase();
    if (urgency === 'EMERGENCY' || urgency === 'HIGH') {
      avatarInstanceRef.current.setEmotion('alert');
      setCompanionStatus('Cảnh báo: Dấu hiệu cần khám sớm');
    }
  }, [lastAnswer]);

  // Doctor Audio Greeting
  const handleGreeting = () => {
    if (typeof window === 'undefined' || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();

    const name = persona === 'dr_mai' ? 'Bác sĩ Thanh Mai' : 'Bác sĩ Minh Tuấn';
    const text = `Xin chào bạn, tôi là ${name}, bác sĩ trợ lý MedGuard AI. Hãy chia sẻ triệu chứng hoặc thắc mắc của bạn để tôi tư vấn phác đồ chuẩn y khoa nhé!`;

    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = 'vi-VN';
    utter.rate = 1.0;

    avatarInstanceRef.current?.startSpeaking(text);
    setCompanionStatus('Đang chào hỏi…');

    utter.onend = () => {
      avatarInstanceRef.current?.stopSpeaking();
      setCompanionStatus('Sẵn sàng lắng nghe');
    };
    utter.onerror = () => {
      avatarInstanceRef.current?.stopSpeaking();
      setCompanionStatus('Sẵn sàng lắng nghe');
    };

    window.speechSynthesis.speak(utter);
    onNotify?.(`Bác sĩ ảo đang giới thiệu`);
  };

  // Custom GLB Upload handler
  const handleCustomGlb = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const url = URL.createObjectURL(file);
    setCustomModelName(file.name);
    setPersona('custom');

    if (avatarInstanceRef.current) {
      avatarInstanceRef.current.setCustomGLB(url);
    }
    onNotify?.(`Đã tải model 3D: ${file.name}`);
    event.target.value = '';
  };

  const currentDoctorName =
    persona === 'dr_mai'
      ? 'BS. Thanh Mai'
      : persona === 'custom'
      ? (customModelName ? `3D: ${customModelName.slice(0, 14)}` : 'Model 3D riêng')
      : 'BS. Minh Tuấn';

  const currentSpecialty =
    persona === 'dr_mai' ? 'Dược lâm sàng & Nhi' : persona === 'custom' ? 'Custom 3D Avatar' : 'Nội khoa & Cấp cứu';

  return (
    <aside className="doctor-companion-container" aria-label="Bác sĩ 3D AI MedGuard" ref={containerRef}>
      {!isOpen ? (
        /* Minimized Pill Mode */
        <button
          className="doctor-companion-pill"
          type="button"
          onClick={() => setIsOpen(true)}
          title="Mở Bác sĩ 3D AI đồng hành"
          aria-label="Mở Bác sĩ 3D AI đồng hành"
        >
          <div className="pill-avatar-thumb">
            <Bot size={18} />
            <span className="pill-status-dot" />
          </div>
          <div className="pill-text">
            <strong>{currentDoctorName}</strong>
            <span>{isBusy ? 'Đang suy nghĩ…' : speakingText ? 'Đang nói…' : 'Đang trực tuyến'}</span>
          </div>
          <Sparkles size={14} style={{ color: '#2dd4bf', marginLeft: 4 }} />
        </button>
      ) : (
        /* Docked Card Mode */
        <div className={`doctor-companion-card ${isExpanded ? 'expanded' : ''}`}>
          {/* Header */}
          <div className="companion-card-header">
            <div className="companion-doctor-meta">
              <span className="doctor-live-badge">
                <span className="live-pulse" /> Live 3D
              </span>
              <div>
                <strong>{currentDoctorName}</strong>
              </div>
            </div>
            <div className="companion-header-actions">
              <button
                className="companion-icon-btn"
                type="button"
                onClick={() => setIsExpanded(!isExpanded)}
                title={isExpanded ? 'Thu nhỏ' : 'Mở rộng'}
                aria-label={isExpanded ? 'Thu nhỏ' : 'Mở rộng'}
              >
                {isExpanded ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
              </button>
              <button
                className="companion-icon-btn"
                type="button"
                onClick={() => setIsOpen(false)}
                title="Thu gọn thành thanh nhỏ"
                aria-label="Thu gọn"
              >
                <X size={15} />
              </button>
            </div>
          </div>

          {/* 3D Viewport Canvas */}
          <div className="companion-viewport-wrap">
            <canvas ref={canvasRef} className="companion-3d-canvas" />

            {/* Interactive Status Pill */}
            <div className="companion-state-pill">
              <span
                className={
                  speakingText
                    ? 'state-dot-speaking'
                    : isBusy
                    ? 'state-dot-thinking'
                    : 'state-dot-active'
                }
              />
              <span>{companionStatus}</span>
            </div>
          </div>

          {/* Footer & Controls */}
          <div className="companion-card-footer">
            {/* Persona Switcher */}
            <div className="companion-persona-tabs" role="tablist">
              <button
                type="button"
                role="tab"
                aria-selected={persona === 'dr_tuan'}
                className={`persona-tab-btn ${persona === 'dr_tuan' ? 'active' : ''}`}
                onClick={() => setPersona('dr_tuan')}
              >
                <User size={13} />
                <span>BS. Minh Tuấn</span>
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={persona === 'dr_mai'}
                className={`persona-tab-btn ${persona === 'dr_mai' ? 'active' : ''}`}
                onClick={() => setPersona('dr_mai')}
              >
                <User size={13} />
                <span>BS. Thanh Mai</span>
              </button>
            </div>

            {/* Quick Actions */}
            <div className="companion-quick-actions">
              <button
                type="button"
                className="companion-action-pill"
                onClick={handleGreeting}
                title="Bác sĩ chào hỏi và giới thiệu"
              >
                <Sparkles size={13} style={{ color: '#2dd4bf' }} />
                <span>Chào hỏi</span>
              </button>

              {setAutoSpeak && (
                <button
                  type="button"
                  className={`companion-action-pill ${autoSpeak ? 'active' : ''}`}
                  onClick={() => setAutoSpeak(!autoSpeak)}
                  title="Tự động đọc giọng nói khi MedGuard trả lời"
                >
                  <Volume2 size={13} />
                  <span>{autoSpeak ? 'Tự đọc: BẬT' : 'Tự đọc: TẮT'}</span>
                </button>
              )}

              <button
                type="button"
                className="companion-action-pill"
                onClick={() => fileInputRef.current?.click()}
                title="Tải lên model 3D cá nhân dạng .glb (Rodin / Meshy / RPM)"
              >
                <Upload size={13} />
                <span>Load GLB</span>
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".glb,.gltf"
                className="file-upload-hidden"
                onChange={handleCustomGlb}
              />
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
