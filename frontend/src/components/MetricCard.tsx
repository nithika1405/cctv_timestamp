interface MetricCardProps {
  label: string
  value: number | string
  icon?: string
  variant?: 'default' | 'danger' | 'warning' | 'success'
}

const VARIANT_STYLES: Record<string, { color: string; bg: string; glow: string }> = {
  default: {
    color: 'var(--accent)',
    bg: 'var(--accent-glow)',
    glow: 'rgba(59, 130, 246, 0.2)',
  },
  danger: {
    color: 'var(--danger)',
    bg: 'var(--danger-glow)',
    glow: 'rgba(239, 68, 68, 0.2)',
  },
  warning: {
    color: 'var(--warning)',
    bg: 'var(--warning-glow)',
    glow: 'rgba(245, 158, 11, 0.2)',
  },
  success: {
    color: 'var(--success)',
    bg: 'var(--success-glow)',
    glow: 'rgba(16, 185, 129, 0.2)',
  },
}

export function MetricCard({ label, value, icon, variant = 'default' }: MetricCardProps) {
  const style = VARIANT_STYLES[variant]
  
  return (
    <div
      className="card animate-scale-in"
      style={{
        borderTop: `2px solid ${style.color}`,
        padding: '20px 24px',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        position: 'relative',
        overflow: 'hidden',
        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-4px) scale(1.02)'
        e.currentTarget.style.boxShadow = `0 20px 40px ${style.glow}`
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0) scale(1)'
        e.currentTarget.style.boxShadow = 'var(--shadow-md)'
      }}
    >
      {/* Gradient background accent */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          right: 0,
          width: '120px',
          height: '120px',
          background: `radial-gradient(circle, ${style.bg}, transparent 70%)`,
          opacity: 0.6,
          pointerEvents: 'none',
        }}
      />
      
      <div style={{ position: 'relative', zIndex: 1 }}>
        <span
          style={{
            fontSize: 11,
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
            color: 'var(--text-soft)',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          {icon && <span style={{ fontSize: 14 }}>{icon}</span>}
          {label}
        </span>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 8 }}>
          <span
            style={{
              fontSize: 32,
              fontWeight: 700,
              color: 'var(--text-h)',
              fontVariantNumeric: 'tabular-nums',
              lineHeight: 1,
              textShadow: `0 2px 12px ${style.glow}`,
            }}
          >
            {value}
          </span>
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: style.color,
              boxShadow: `0 0 12px ${style.color}`,
              animation: 'pulse 2s ease-in-out infinite',
            }}
          />
        </div>
      </div>
    </div>
  )
}
