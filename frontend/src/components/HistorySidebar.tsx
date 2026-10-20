import { useEffect, useState } from 'react'
import type { VideoMeta } from '../api'
import { deleteVideo, fetchVideos } from '../api'

interface HistorySidebarProps {
  onSelectVideo: (id: number) => void
  onDeleteVideo: (id: number) => void
  activeVideoId: number | null
  refreshKey: number
}

function formatTime(seconds: number): string {
  const t = Math.floor(seconds)
  return [Math.floor(t / 3600), Math.floor((t % 3600) / 60), t % 60]
    .map((v) => String(v).padStart(2, '0'))
    .join(':')
}

export function HistorySidebar({ onSelectVideo, onDeleteVideo, activeVideoId, refreshKey }: HistorySidebarProps) {
  const [videos, setVideos] = useState<VideoMeta[]>([])

  useEffect(() => {
    fetchVideos().then(setVideos)
  }, [activeVideoId, refreshKey]) // Refresh when a new analysis completes

  if (videos.length === 0) return null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <h4
        style={{
          margin: '0 0 8px',
          fontSize: 11,
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
          color: 'var(--text)',
          padding: '0 4px',
        }}
      >
        Previous Analyses
      </h4>
      {videos.map((v) => (
        <div
          key={v.id}
          style={{
            background: activeVideoId === v.id ? 'var(--accent-glow)' : 'transparent',
            border: `1px solid ${activeVideoId === v.id ? 'var(--accent)' : 'transparent'}`,
            borderRadius: 6,
            padding: '8px 10px',
            display: 'flex',
            gap: 8,
            alignItems: 'center',
            width: '100%',
          }}
        >
          <button
            onClick={() => onSelectVideo(v.id)}
            style={{
              background: 'transparent',
              border: 'none',
              padding: 0,
              textAlign: 'left',
              cursor: 'pointer',
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
              flex: 1,
              minWidth: 0,
            }}
            onMouseEnter={(e) => {
              if (activeVideoId !== v.id) {
                ;(e.currentTarget.parentElement as HTMLElement).style.background = 'var(--bg-panel)'
              }
            }}
            onMouseLeave={(e) => {
              if (activeVideoId !== v.id) {
                ;(e.currentTarget.parentElement as HTMLElement).style.background = 'transparent'
              }
            }}
          >
            <span
              style={{
                color: activeVideoId === v.id ? 'var(--accent)' : 'var(--text-h)',
                fontSize: 12,
                fontWeight: 500,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {v.filename}
            </span>
            <span style={{ color: 'var(--text)', fontSize: 10 }}>
              {formatTime(v.duration_seconds)} · {v.fps.toFixed(0)} fps
            </span>
          </button>

          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation()
              if (window.confirm(`Delete "${v.filename}" and all its analysis data? This cannot be undone.`)) {
                void deleteVideo(v.id).then(() => onDeleteVideo(v.id))
              }
            }}
            style={{
              background: 'rgba(244, 63, 94, 0.12)',
              border: '1px solid rgba(244, 63, 94, 0.35)',
              color: '#fca5a5',
              borderRadius: 6,
              padding: '4px 7px',
              fontSize: 10,
              fontWeight: 700,
              cursor: 'pointer',
            }}
            aria-label={`Delete ${v.filename}`}
          >
            Delete
          </button>
        </div>
      ))}
    </div>
  )
}
