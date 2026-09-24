import { useEffect, useRef, useState } from 'react';
import { Camera, ImagePlus, Keyboard, LoaderCircle, ScanLine, X } from 'lucide-react';

async function createReader() {
  const { BrowserQRCodeReader } = await import('@zxing/browser');
  return new BrowserQRCodeReader();
}

export function QrScanner({ open, onClose, onDetected }) {
  const videoRef = useRef(null);
  const controlsRef = useRef(null);
  const [tab, setTab] = useState('camera');
  const [manual, setManual] = useState('');
  const [busy, setBusy] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [error, setError] = useState('');

  const stopCamera = () => {
    controlsRef.current?.stop();
    controlsRef.current = null;
    setCameraActive(false);
  };

  useEffect(() => () => controlsRef.current?.stop(), []);
  useEffect(() => {
    if (!open) stopCamera();
  }, [open]);

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
    } catch (cause) {
      setError(cause?.message || 'Không thể truy cập camera.');
    } finally {
      setBusy(false);
    }
  };

  const decodeImage = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError('');
    const url = URL.createObjectURL(file);
    try {
      const reader = await createReader();
      const result = await reader.decodeFromImageUrl(url);
      finish(result.getText());
    } catch {
      setError('Không tìm thấy QR hợp lệ trong ảnh này.');
    } finally {
      URL.revokeObjectURL(url);
      setBusy(false);
      event.target.value = '';
    }
  };

  return (
    <div className="modal-layer" role="dialog" aria-modal="true" aria-labelledby="qr-title">
      <button className="modal-scrim" type="button" aria-label="Đóng trình quét QR" onClick={onClose} />
      <section className="qr-dialog">
        <header className="dialog-header">
          <div><span className="dialog-icon"><ScanLine size={19} /></span><div><h2 id="qr-title">Xác thực sản phẩm</h2><p>Đối chiếu QR với registry</p></div></div>
          <button className="icon-button" type="button" title="Đóng" aria-label="Đóng" onClick={onClose}><X size={19} /></button>
        </header>
        <div className="segmented qr-tabs" role="tablist">
          <button type="button" className={tab === 'camera' ? 'active' : ''} onClick={() => setTab('camera')}><Camera size={15} /> Camera</button>
          <button type="button" className={tab === 'image' ? 'active' : ''} onClick={() => { stopCamera(); setTab('image'); }}><ImagePlus size={15} /> Ảnh QR</button>
          <button type="button" className={tab === 'manual' ? 'active' : ''} onClick={() => { stopCamera(); setTab('manual'); }}><Keyboard size={15} /> Nhập mã</button>
        </div>
        {tab === 'camera' && <div className="scanner-view">
          <video ref={videoRef} muted playsInline />
          <span className="scan-frame" aria-hidden="true" />
          {!cameraActive && <button className="camera-start" type="button" disabled={busy} onClick={startCamera}>{busy ? <LoaderCircle className="spin" size={18} /> : <Camera size={18} />} Mở camera</button>}
        </div>}
        {tab === 'image' && <label className="qr-upload"><ImagePlus size={26} /><strong>Chọn ảnh chứa QR</strong><input className="visually-hidden" type="file" accept="image/png,image/jpeg,image/webp" onChange={decodeImage} /></label>}
        {tab === 'manual' && <form className="manual-code" onSubmit={(event) => { event.preventDefault(); finish(manual); }}><textarea value={manual} onChange={(event) => setManual(event.target.value)} placeholder="MEDGUARD|product=...|serial=...|lot=..." /><button className="primary-button" type="submit" disabled={!manual.trim()}>Kiểm tra mã</button></form>}
        {error && <p className="dialog-error">{error}</p>}
      </section>
    </div>
  );
}
