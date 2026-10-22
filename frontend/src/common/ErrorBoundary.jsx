import React from 'react';
import { AlertTriangle, RefreshCw, RotateCcw, Home } from 'lucide-react';

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('MedGuard ErrorBoundary caught error:', error, errorInfo);
    this.setState({ errorInfo });
  }

  handleReload = () => {
    window.location.reload();
  };

  handleHardReload = () => {
    if ('caches' in window) {
      caches.keys().then((names) => {
        for (const name of names) caches.delete(name);
      });
    }
    const url = new URL(window.location.href);
    url.searchParams.set('_ts', Date.now().toString());
    window.location.href = url.toString();
  };

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            minHeight: '70vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '24px',
            color: '#f8fafc',
            fontFamily: 'system-ui, -apple-system, sans-serif',
          }}
        >
          <div
            style={{
              maxWidth: '640px',
              width: '100%',
              background: 'rgba(15, 23, 42, 0.95)',
              border: '1px solid rgba(239, 68, 68, 0.4)',
              borderRadius: '16px',
              padding: '32px',
              boxShadow: '0 20px 40px rgba(0,0,0,0.6)',
              backdropFilter: 'blur(16px)',
              display: 'flex',
              flexDirection: 'column',
              gap: '20px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
              <div
                style={{
                  width: '44px',
                  height: '44px',
                  borderRadius: '12px',
                  background: 'rgba(239, 68, 68, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#ef4444',
                }}
              >
                <AlertTriangle size={24} />
              </div>
              <div>
                <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 600, color: '#f8fafc' }}>
                  Đã xảy ra sự cố hiển thị giao diện
                </h2>
                <p style={{ margin: '4px 0 0', fontSize: '13px', color: '#94a3b8' }}>
                  {this.props.title || 'Mô-đun đang gặp lỗi tạm thời. Vui lòng làm mới hoặc xóa bộ nhớ đệm.'}
                </p>
              </div>
            </div>

            {this.state.error && (
              <div
                style={{
                  background: 'rgba(0, 0, 0, 0.5)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: '8px',
                  padding: '12px 16px',
                  fontSize: '12px',
                  color: '#fca5a5',
                  fontFamily: 'monospace',
                  overflowX: 'auto',
                  maxHeight: '160px',
                }}
              >
                <strong>{this.state.error.name}:</strong> {this.state.error.message}
              </div>
            )}

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginTop: '8px' }}>
              <button
                type="button"
                onClick={this.handleReset}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '10px 18px',
                  background: 'linear-gradient(135deg, #0ea5e9, #0284c7)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '10px',
                  fontSize: '13px',
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                <RotateCcw size={15} />
                <span>Thử tải lại mô-đun</span>
              </button>

              <button
                type="button"
                onClick={this.handleHardReload}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '10px 18px',
                  background: 'rgba(255, 255, 255, 0.08)',
                  color: '#e2e8f0',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  borderRadius: '10px',
                  fontSize: '13px',
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                <RefreshCw size={15} />
                <span>Xoá Cache & Tải lại</span>
              </button>

              {this.props.onBackToChat && (
                <button
                  type="button"
                  onClick={this.props.onBackToChat}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '10px 18px',
                    background: 'transparent',
                    color: '#94a3b8',
                    border: '1px solid rgba(148, 163, 184, 0.2)',
                    borderRadius: '10px',
                    fontSize: '13px',
                    fontWeight: 500,
                    cursor: 'pointer',
                  }}
                >
                  <Home size={15} />
                  <span>Về phòng Chat</span>
                </button>
              )}
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
