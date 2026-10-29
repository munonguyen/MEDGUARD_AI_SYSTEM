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
  const { BrowserMultiFormatReader } = await import('@zxing/browser');
  return new BrowserMultiFormatReader();
}

const SAMPLE_CODES = [
  {
    id: 'entero-ok',
    label: 'EnteroBifina 2.5B',
    badge: 'Mã vạch EAN-13',
    tone: 'success',
    code: '8936151980798',
  },
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

      // 1. Direct full-image scan
      let detectedText = null;
      try {
        const result = await reader.decodeFromImageUrl(url);
        if (result?.getText()) {
          detectedText = result.getText();
        }
      } catch {
        // Fallback to multi-region canvas scanning
      }

      // 2. Multi-region & angle scan if direct full-image failed
      // Medicine packages often have barcodes tilted or positioned in specific quadrants
      if (!detectedText) {
        const img = new Image();
        img.src = url;
        await new Promise((resolve, reject) => {
          img.onload = resolve;
          img.onerror = () => reject(new Error('Không thể tải file hình ảnh.'));
        });

        const w = img.naturalWidth || img.width;
        const h = img.naturalHeight || img.height;
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');

        // Focused crops where barcodes / QR codes typically sit on medicine packaging:
        const candidateRegions = [
          // Bottom half (standard for box barcodes like EnteroBifina, blisters)
          { x: 0, y: Math.floor(h * 0.35), w: w, h: Math.floor(h * 0.65) },
          // Bottom-right quadrant (EAN-13 location on EnteroBifina)
          { x: Math.floor(w * 0.35), y: Math.floor(h * 0.45), w: Math.floor(w * 0.65), h: Math.floor(h * 0.55) },
          // Center 70%
          { x: Math.floor(w * 0.15), y: Math.floor(h * 0.15), w: Math.floor(w * 0.7), h: Math.floor(h * 0.7) },
          // Bottom-left quadrant
          { x: 0, y: Math.floor(h * 0.45), w: Math.floor(w * 0.65), h: Math.floor(h * 0.55) },
          // Top half (bottle caps and ampoule labels)
          { x: 0, y: 0, w: w, h: Math.floor(h * 0.6) },
        ];

        for (const reg of candidateRegions) {
          canvas.width = reg.w;
          canvas.height = reg.h;
          ctx.clearRect(0, 0, reg.w, reg.h);
          ctx.drawImage(img, reg.x, reg.y, reg.w, reg.h, 0, 0, reg.w, reg.h);
          try {
            const res = await reader.decodeFromCanvas(canvas);
            if (res?.getText()) {
              detectedText = res.getText();
              break;
            }
          } catch {}
        }

        // 3. Tilted package rotation scan (for hand-held or slanted packages)
        if (!detectedText) {
          const angles = [10, -10, 15, -15, 90, 270];
          for (const angle of angles) {
            const regW = Math.floor(w * 0.85);
            const regH = Math.floor(h * 0.65);
            canvas.width = regW;
            canvas.height = regH;
            ctx.save();
            ctx.translate(regW / 2, regH / 2);
            ctx.rotate((angle * Math.PI) / 180);
            ctx.drawImage(img, -w / 2, -h / 2);
            ctx.restore();
            try {
              const res = await reader.decodeFromCanvas(canvas);
              if (res?.getText()) {
                detectedText = res.getText();
                break;
              }
            } catch {}
          }
        }
      }

      if (detectedText) {
        finish(detectedText);
      } else {
        setError('Không nhận diện được mã QR hoặc mã vạch từ ảnh này. Đối với các hộp thuốc như EnteroBifina (mã vạch 8936151980798), bạn có thể chụp cận cảnh mã hơn hoặc dùng tab "Nhập Mã Chuỗi" để đối chiếu.');
      }
    } catch {
      setError('Lỗi khi xử lý ảnh. Hãy thử ảnh chụp cận cảnh và đủ sáng hơn hoặc nhập mã chuỗi trực tiếp.');
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
              <h2 id="qr-title">Xác thực QR & Mã Vạch Thuốc</h2>
              <p>Hỗ trợ QR Code 2D & Barcode 1D (EAN-13, UPC, GS1 DataMatrix)</p>
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
            <ImagePlus size={15} /> Tải Ảnh QR / Mã Vạch
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
              <span className="scanner-hud-hint">Đặt mã QR hoặc mã vạch 1D vào giữa khung hình</span>
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
                <strong>Quét mã QR hoặc mã vạch trên bao bì thuốc</strong>
                <p>Hỗ trợ camera điện thoại, webcam, mã vạch EAN-13 và mã QR DataMatrix GS1</p>
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
                <strong>{busy ? 'Đang giải mã QR / Mã vạch từ ảnh…' : 'Bấm để chọn ảnh hoặc kéo thả vào đây'}</strong>
                <p>Hỗ trợ mã QR, DataMatrix và mã vạch 1D EAN-13 (PNG, JPG, WebP)</p>
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
