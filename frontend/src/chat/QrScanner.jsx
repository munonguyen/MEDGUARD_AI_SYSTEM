import { useEffect, useRef, useState } from 'react';
import {
  Camera,
  CheckCircle2,
  Flashlight,
  FlashlightOff,
  ImagePlus,
  Keyboard,
  LoaderCircle,
  QrCode,
  Scan,
  ScanLine,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  X,
} from 'lucide-react';

async function createReader() {
  const { BrowserQRCodeReader } = await import('@zxing/browser');
  return new BrowserQRCodeReader();
}

const SAMPLE_CODES = [
  {
    id: 'amox-ok',
    label: 'Amoxicillin 500mg',
    badge: 'Chính hãng',
    tone: 'success',
    code: 'product=MG-AMOX-500|lot=AMX2409|serial=VN24A001',
  },
  {
    id: 'asp-ok',
    label: 'Aspirin 81mg',
    badge: 'Chính hãng',
    tone: 'success',
    code: 'product=MG-ASP-81|lot=ASP2410|serial=VN24B101',
  },
  {
    id: 'fake-alert',
    label: 'Nghi hàng giả',
    badge: 'Serial lạ',
    tone: 'danger',
    code: 'product=MG-AMOX-500|lot=AMX2409|serial=FAKE-VN999',
  },
  {
    id: 'recall-alert',
    label: 'Lô thu hồi',
    badge: 'Cảnh báo',
    tone: 'warning',
    code: 'product=MG-RECALL-001|lot=RCL2301|serial=VN23R001',
  },
];

export function QrScanner({ open, onClose, onDetected }) {
  const videoRef = useRef(null);
  const controlsRef = useRef(null);
  const trackRef = useRef(null);
  const [tab, setTab] = useState('camera');
  const [manual, setManual] = useState('');
  const [busy, setBusy] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [torchOn, setTorchOn] = useState(false);
  const [hasTorch, setHasTorch] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState('');

  const stopCamera = () => {
    if (controlsRef.current) {
      try {
        controlsRef.current.stop();
      } catch {}
      controlsRef.current = null;
    }
    if (trackRef.current) {
      try {
        trackRef.current.stop();
      } catch {}
      trackRef.current = null;
    }
    setCameraActive(false);
    setTorchOn(false);
    setHasTorch(false);
  };

  useEffect(() => () => stopCamera(), []);
  useEffect(() => {
    if (!open) stopCamera();
  }, [open]);

  // Handle ESC key to close modal
  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const finish = (value) => {
    const normalized = value?.trim();
    if (!normalized) return;
    stopCamera();
    onDetected(normalized);
  };

  const startCamera = async () => {
    setBusy(true);
    setError('');
    try {
      const reader = await createReader();
      controlsRef.current = await reader.decodeFromVideoDevice(undefined, videoRef.current, (result) => {
        if (result) finish(result.getText());
      });
      setCameraActive(true);

      // Check for torch capability
      if (videoRef.current?.srcObject) {
        const stream = videoRef.current.srcObject;
        const videoTrack = stream.getVideoTracks()?.[0];
        if (videoTrack) {
          trackRef.current = videoTrack;
          const capabilities = videoTrack.getCapabilities ? videoTrack.getCapabilities() : {};
          if (capabilities.torch) setHasTorch(true);
        }
      }
    } catch (cause) {
      setError(cause?.message || 'Không thể truy cập camera. Bạn hãy cấp quyền camera hoặc chọn tải ảnh / nhập mã thủ công.');
    } finally {
      setBusy(false);
    }
  };

  const toggleTorch = async () => {
    if (!trackRef.current || !hasTorch) return;
    try {
      const nextTorch = !torchOn;
      await trackRef.current.applyConstraints({
        advanced: [{ torch: nextTorch }],
      });
      setTorchOn(nextTorch);
    } catch (err) {
      console.warn('Torch toggle failed:', err);
    }
  };

  const decodeImageFile = async (file) => {
    if (!file) return;
    setBusy(true);
    setError('');
    const url = URL.createObjectURL(file);
    try {
      const reader = await createReader();
      const result = await reader.decodeFromImageUrl(url);
      finish(result.getText());
    } catch {
      setError('Không tìm thấy mã QR hợp lệ trong ảnh này. Hãy thử ảnh chụp cận cảnh và đủ sáng hơn.');
    } finally {
      URL.revokeObjectURL(url);
      setBusy(false);
    }
  };

  const handleFileInput = (event) => {
    const file = event.target.files?.[0];
    if (file) decodeImageFile(file);
    event.target.value = '';
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file && file.type.startsWith('image/')) {
      decodeImageFile(file);
    } else {
      setError('Vui lòng kéo thả file hình ảnh (PNG, JPG, WebP).');
    }
  };

  return (
    <div className="modal-layer qr-modal-layer" role="dialog" aria-modal="true" aria-labelledby="qr-title">
      <button className="modal-scrim" type="button" aria-label="Đóng trình quét QR" onClick={onClose} />
      <section className="qr-dialog modern-qr-panel">
        <header className="dialog-header modern-dialog-header">
          <div className="dialog-title-block">
            <span className="dialog-icon qr-gradient-icon" aria-hidden="true">
              <QrCode size={20} />
            </span>
            <div>
              <h2 id="qr-title">Xác thực QR Chống Hàng Giả</h2>
              <p>Đối chiếu tức thì với Registry Dược phẩm Chính hãng</p>
            </div>
          </div>
          <button className="icon-button dialog-close-btn" type="button" title="Đóng" aria-label="Đóng" onClick={onClose}>
            <X size={18} />
          </button>
        </header>

        {/* Quick sample chips */}
        <div className="qr-sample-bar">
          <span className="qr-sample-label">
            <Sparkles size={13} /> Thử mẫu nhanh:
          </span>
          <div className="qr-sample-chips">
            {SAMPLE_CODES.map((s) => (
              <button
                key={s.id}
                type="button"
                className={`qr-sample-chip chip-${s.tone}`}
                title={`Thử đối chiếu mã ${s.label}`}
                onClick={() => finish(s.code)}
              >
                <span className="chip-bullet" />
                <span className="chip-name">{s.label}</span>
                <span className="chip-badge">{s.badge}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="segmented qr-tabs modern-qr-tabs" role="tablist" aria-label="Phương thức quét mã">
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'camera'}
            className={tab === 'camera' ? 'active' : ''}
            onClick={() => {
              setError('');
              setTab('camera');
            }}
          >
            <Camera size={15} /> Quét Camera
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'image'}
            className={tab === 'image' ? 'active' : ''}
            onClick={() => {
              stopCamera();
              setError('');
              setTab('image');
            }}
          >
            <ImagePlus size={15} /> Tải Ảnh QR
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'manual'}
            className={tab === 'manual' ? 'active' : ''}
            onClick={() => {
              stopCamera();
              setError('');
              setTab('manual');
            }}
          >
            <Keyboard size={15} /> Nhập Mã Chuỗi
          </button>
        </div>

        {/* Tab 1: Live Camera Scan */}
        {tab === 'camera' && (
          <div className="scanner-view modern-scanner-view">
            <video ref={videoRef} muted playsInline autoPlay />
            <div className="scanner-hud-overlay" aria-hidden="true">
              <span className="hud-corner top-left" />
              <span className="hud-corner top-right" />
              <span className="hud-corner bottom-left" />
              <span className="hud-corner bottom-right" />
              <div className="scanner-laser-bar" />
              <span className="scanner-hud-hint">Đặt mã QR hoặc DataMatrix vào giữa khung hình</span>
            </div>

            {hasTorch && cameraActive && (
              <button
                type="button"
                className={`scanner-torch-btn ${torchOn ? 'active' : ''}`}
                onClick={toggleTorch}
                title={torchOn ? 'Tắt đèn pin' : 'Bật đèn pin'}
                aria-label="Đèn pin soi mã"
              >
                {torchOn ? <FlashlightOff size={16} /> : <Flashlight size={16} />}
              </button>
            )}

            {!cameraActive && (
              <div className="scanner-start-overlay">
                <div className="scanner-camera-icon-glow">
                  <Camera size={32} />
                </div>
                <strong>Quét mã QR trên bao bì thuốc</strong>
                <p>Hỗ trợ camera điện thoại, webcam máy tính và mã DataMatrix GS1</p>
                <button
                  className="camera-start modern-camera-start"
                  type="button"
                  disabled={busy}
                  onClick={startCamera}
                >
                  {busy ? <LoaderCircle className="spin" size={17} /> : <Camera size={17} />}
                  <span>{busy ? 'Đang kích hoạt camera…' : 'Bật Camera Quét Mã'}</span>
                </button>
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Image Upload */}
        {tab === 'image' && (
          <div
            className={`qr-upload-wrap ${isDragging ? 'dragging' : ''}`}
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
          >
            <label className="qr-upload modern-qr-upload">
              <div className="qr-upload-icon-ring">
                {busy ? <LoaderCircle className="spin" size={32} /> : <UploadCloud size={32} />}
              </div>
              <div className="qr-upload-text">
                <strong>{busy ? 'Đang giải mã QR từ ảnh…' : 'Bấm để chọn ảnh hoặc kéo thả vào đây'}</strong>
                <p>Hỗ trợ ảnh chụp nhãn hộp thuốc, vỉ thuốc hoặc hóa đơn (PNG, JPG, WebP)</p>
              </div>
              <span className="qr-upload-browse-btn">Chọn tệp từ thiết bị</span>
              <input
                className="visually-hidden"
                type="file"
                accept="image/png,image/jpeg,image/webp"
                disabled={busy}
                onChange={handleFileInput}
              />
            </label>
          </div>
        )}

        {/* Tab 3: Manual Code Entry */}
        {tab === 'manual' && (
          <form
            className="manual-code modern-manual-form"
            onSubmit={(event) => {
              event.preventDefault();
              finish(manual);
            }}
          >
            <label htmlFor="manual-qr-input" className="manual-code-label">
              Nội dung mã vạch hoặc chuỗi định danh:
            </label>
            <textarea
              id="manual-qr-input"
              value={manual}
              onChange={(event) => setManual(event.target.value)}
              placeholder="Ví dụ: product=MG-AMOX-500|lot=AMX2409|serial=VN24A001&#10;hoặc link: https://medguard.vn/verify?code=..."
              rows={4}
            />
            <div className="manual-actions">
              <button
                className="primary-button modern-verify-btn"
                type="submit"
                disabled={!manual.trim()}
              >
                <ShieldCheck size={16} /> Đối Chiếu Registry Ngay
              </button>
            </div>
          </form>
        )}

        {error && (
          <div className="dialog-error modern-dialog-error" role="alert" aria-live="assertive">
            <ShieldAlert size={16} className="error-icon" />
            <span>{error}</span>
          </div>
        )}
      </section>
    </div>
  );
}
