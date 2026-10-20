import { useEffect } from 'react'
import { useAnalysisProgress } from '../hooks/useAnalysisProgress'

interface ProgressPanelProps {
  jobId: string
  onComplete: (videoId: number) => void
}

function formatTime(seconds: number) {
  const t = Math.floor(seconds)
  return [Math.floor(t / 3600), Math.floor((t % 3600) / 60), t % 60]
    .map((v) => String(v).padStart(2, '0'))
    .join(':')
}

export function ProgressPanel({ jobId, onComplete }: ProgressPanelProps) {
  const msg = useAnalysisProgress(jobId)

  useEffect(() => {
    if (msg?.status === 'completed' && msg.video_id != null) {
      onComplete(msg.video_id)
    }
  }, [msg?.status, msg?.video_id, onComplete])

  const pct = msg ? Math.round(msg.progress * 100) : 0
  const status = msg?.status ?? 'pending'
  const metrics = msg?.metrics ?? {}

  return (
    <div
      className="card card-elevated animate-scale-in"
      style={{
        padding: 28,
        display: 'flex',
        flexDirection: 'column',
        gap: 20,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0, color: 'var(--text-h)', fontSize: 16, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 20 }}>🔍</span>
          Analyzing footage...
        </h3>
        <span
          className={`status-badge ${
            status === 'completed'
              ? 'status-success'
              : status === 'failed'
                ? 'status-danger'
                : 'status-info'
          }`}
        >
          {status === 'completed' && '✓ '}
          {status === 'failed' && '✕ '}
          {status === 'running' && '⟳ '}
          {status.toUpperCase()}
        </span>
      </div>

      {/* Progress bar */}
      <div style={{ 
        background: 'var(--bg-elevated)', 
        borderRadius: 12, 
        overflow: 'hidden', 
        height: 12,
        border: '1px solid var(--border)',
        boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.3)',
        position: 'relative',
      }}>
        <div
          style={{
            height: '100%',
            width: `${pct}%`,
            background: status === 'failed' 
              ? 'var(--gradient-danger)' 
              : status === 'completed'
                ? 'var(--gradient-success)'
                : 'var(--gradient-primary)',
            transition: 'width 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
            borderRadius: 12,
            boxShadow: status === 'running' ? '0 0 20px var(--accent-glow-strong)' : 'none',
            position: 'relative',
            overflow: 'hidden',
          }}
        >
          {status === 'running' && (
            <div
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                background: 'var(--gradient-shimmer)',
                animation: 'shimmer 1.5s ease-in-out infinite',
              }}
            />
          )}
        </div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 20, fontSize: 13 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ color: 'var(--accent)', fontVariantNumeric: 'tabular-nums', fontWeight: 700, fontSize: 18 }}>
            {pct}%
          </span>
        </div>
        {metrics.frame_index != null && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <span style={{ fontSize: 10, color: 'var(--text-soft)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Frame</span>
            <span style={{ color: 'var(--text-h)', fontWeight: 600 }}>{metrics.frame_index.toLocaleString()}</span>
          </div>
        )}
        {metrics.timestamp_seconds != null && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <span style={{ fontSize: 10, color: 'var(--text-soft)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Time</span>
            <span style={{ color: 'var(--text-h)', fontWeight: 600 }}>{formatTime(metrics.timestamp_seconds)}</span>
          </div>
        )}
        {metrics.fps != null && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <span style={{ fontSize: 10, color: 'var(--text-soft)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Speed</span>
            <span style={{ color: 'var(--success)', fontWeight: 600 }}>{metrics.fps.toFixed(1)} fps</span>
          </div>
        )}
      </div>

      {msg?.error && (
        <div style={{ 
          background: 'var(--danger-glow)', 
          border: '1px solid rgba(239, 68, 68, 0.3)',
          borderRadius: 10,
          padding: 12,
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}>
          <span style={{ fontSize: 16 }}>⚠️</span>
          <p style={{ color: 'var(--danger)', margin: 0, fontSize: 13, fontWeight: 500 }}>
            {msg.error}
          </p>
        </div>
      )}
    </div>
  )
}
