import { useEffect, useRef, useState } from 'react';
import { Pause, Play, Volume2, VolumeX } from 'lucide-react';

export default function InteractiveBackground({ mouseX = 0, mouseY = 0 }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(true);
  const [videoLoaded, setVideoLoaded] = useState(false);
  const [videoError, setVideoError] = useState(false);

  // Check prefers-reduced-motion
  useEffect(() => {
    try {
      const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
      if (mediaQuery.matches) {
        setIsPlaying(false);
        if (videoRef.current) videoRef.current.pause();
      }
    } catch {}
  }, []);

  // Control video play/pause
  const togglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
      setIsPlaying(false);
    } else {
      videoRef.current.play().catch(() => {});
      setIsPlaying(true);
    }
  };

  // Particle Canvas Animation
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    window.addEventListener('resize', handleResize);

    // Create subtle particles
    const PARTICLE_COUNT = Math.min(50, Math.floor(window.innerWidth / 32));
    const particles = [];
    const colors = [
      'rgba(45, 212, 191, ',  // teal
      'rgba(56, 189, 248, ',  // sky blue
      'rgba(167, 139, 250, ', // purple accent
    ];

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      particles.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.45,
        vy: (Math.random() - 0.5) * 0.45,
        radius: Math.random() * 2 + 1,
        colorPrefix: colors[Math.floor(Math.random() * colors.length)],
        baseAlpha: Math.random() * 0.5 + 0.25,
        pulseSpeed: Math.random() * 0.02 + 0.01,
        pulseOffset: Math.random() * Math.PI * 2,
      });
    }

    let frame = 0;
    const render = () => {
      frame++;
      ctx.clearRect(0, 0, width, height);

      // Draw connections
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 110) {
            const alpha = (1 - dist / 110) * 0.18;
            ctx.strokeStyle = `rgba(45, 212, 191, ${alpha})`;
            ctx.lineWidth = 0.8;
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.stroke();
          }
        }
      }

      // Update and draw particles
      for (const p of particles) {
        if (isPlaying) {
          p.x += p.vx;
          p.y += p.vy;

          if (p.x < 0) p.x = width;
          if (p.x > width) p.x = 0;
          if (p.y < 0) p.y = height;
          if (p.y > height) p.y = 0;
        }

        const pulse = Math.sin(frame * p.pulseSpeed + p.pulseOffset) * 0.2;
        const currentAlpha = Math.max(0.1, Math.min(0.9, p.baseAlpha + pulse));

        ctx.fillStyle = `${p.colorPrefix}${currentAlpha})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fill();

        // Subtle glow halo for larger particles
        if (p.radius > 2.2) {
          ctx.fillStyle = `${p.colorPrefix}${currentAlpha * 0.3})`;
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.radius * 2.4, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      animId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animId);
    };
  }, [isPlaying]);

  return (
    <div className="auth-bg-viewport" aria-hidden="true">
      {/* High-res Static Poster as base / fallback */}
      <div
        className="auth-bg-poster"
        style={{ backgroundImage: 'url(/static/assets/medical_bg_poster.jpg)' }}
      />

      {/* Looping Ambient Video */}
      {!videoError && (
        <video
          ref={videoRef}
          className={`auth-bg-video ${videoLoaded ? 'loaded' : ''}`}
          autoPlay
          loop
          muted
          playsInline
          poster="/static/assets/medical_bg_poster.jpg"
          onLoadedData={() => setVideoLoaded(true)}
          onError={() => setVideoError(true)}
        >
          <source src="/static/assets/medguard_login_bg.mp4" type="video/mp4" />
        </video>
      )}

      {/* Interactive Neural Synapse Canvas */}
      <canvas ref={canvasRef} className="auth-bg-canvas" />

      {/* Dynamic Cursor Spotlight Tracking */}
      <div
        className="auth-ambient-spotlight"
        style={{
          background: `radial-gradient(650px circle at ${mouseX}px ${mouseY}px, rgba(20, 184, 166, 0.16), transparent 75%)`,
        }}
      />

      {/* Futuristic Cyber Overlays & Vignettes */}
      <div className="auth-bg-cyber-grid" />
      <div className="auth-bg-vignette" />

      {/* Subtle Bottom Video Play/Pause Control Button */}
      <div className="auth-bg-controls" aria-hidden="false">
        <button
          type="button"
          className="auth-bg-toggle-btn"
          onClick={togglePlay}
          title={isPlaying ? 'Tạm dừng chuyển động video' : 'Phát chuyển động video'}
          aria-label={isPlaying ? 'Tạm dừng chuyển động video' : 'Phát chuyển động video'}
        >
          {isPlaying ? <Pause size={13} /> : <Play size={13} />}
          <span>{isPlaying ? 'Hiệu ứng: Bật' : 'Hiệu ứng: Tạm dừng'}</span>
        </button>
      </div>
    </div>
  );
}
