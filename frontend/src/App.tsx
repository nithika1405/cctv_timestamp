import { useCallback, useEffect, useState } from 'react'
import type { HealthStatus, VideoMeta } from './api'
import { fetchHealth, fetchVideo } from './api'
import { Dashboard } from './components/Dashboard'
import { HistorySidebar } from './components/HistorySidebar'
import { ProgressPanel } from './components/ProgressPanel'
import { UploadPanel } from './components/UploadPanel'

type View = 'upload' | 'analyzing' | 'dashboard'

function App() {
  const [view, setView] = useState<View>('upload')
  const [jobId, setJobId] = useState<string | null>(null)
  const [videoId, setVideoId] = useState<number | null>(null)
  const [videoMeta, setVideoMeta] = useState<VideoMeta | null>(null)
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0)

  useEffect(() => {
    const refreshHealth = async () => {
      try {
        const next = await fetchHealth()
        setHealth(next)
      } catch {
        setHealth(null)
      }
    }

    refreshHealth()
    const timer = window.setInterval(refreshHealth, 15000)
    return () => window.clearInterval(timer)
  }, [])

  const loadVideo = useCallback(async (id: number) => {
    const meta = await fetchVideo(id)
    setVideoMeta(meta)
    setVideoId(id)
    setView('dashboard')
  }, [])

  const handleAnalysisStarted = useCallback(
    (_jobId: string, _videoPath: string, _videoHash: string, _filename: string) => {
      setJobId(_jobId)
      setView('analyzing')
    },
    [],
  )

  const handleCacheHit = useCallback(
    (id: number) => {
      loadVideo(id)
    },
    [loadVideo],
  )

  const handleProgressComplete = useCallback(
    (id: number) => {
      loadVideo(id)
    },
    [loadVideo],
  )

  const handleNewAnalysis = useCallback(() => {
    setView('upload')
    setJobId(null)
    setVideoId(null)
    setVideoMeta(null)
  }, [])

  const handleDeleteVideo = useCallback((id: number) => {
    setHistoryRefreshKey((current) => current + 1)
    if (videoId === id) {
      setVideoId(null)
      setVideoMeta(null)
      setView('upload')
    }
  }, [videoId])

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="brand-block">
          <div className="brand-icon">🎯</div>
          <div>
            <h2>CCTV Monitor</h2>
            <span>Event Detection & Analysis</span>
          </div>
        </div>

        <button className="primary-button" onClick={handleNewAnalysis}>
          + New Analysis
        </button>

        <div
          style={{
            border: '1px solid var(--border)',
            background: health?.status === 'ok' ? 'rgba(16, 185, 129, 0.08)' : 'rgba(244, 63, 94, 0.08)',
            borderRadius: 12,
            padding: '10px 12px',
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <span style={{ fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-soft)' }}>
              System status
            </span>
            <span
              style={{
                width: 9,
                height: 9,
                borderRadius: '50%',
                background: health?.status === 'ok' ? 'var(--success)' : '#f59e0b',
                boxShadow: health?.status === 'ok' ? '0 0 0 4px rgba(16,185,129,0.15)' : '0 0 0 4px rgba(245,158,11,0.15)',
                display: 'inline-block',
              }}
            />
          </div>
          <strong style={{ color: 'var(--text-h)', fontSize: 14 }}>
            {health ? (health.status === 'ok' ? 'Online' : 'Degraded') : 'Checking...'}
          </strong>
          <span style={{ color: 'var(--text-soft)', fontSize: 11 }}>
            {health ? `${health.database.videos} videos • ${health.database.events} events` : 'Backend unreachable'}
          </span>
        </div>

        <div className="sidebar-panel">
          <HistorySidebar
            onSelectVideo={loadVideo}
            onDeleteVideo={handleDeleteVideo}
            activeVideoId={videoId}
            refreshKey={historyRefreshKey}
          />
        </div>

        <div className="sidebar-footer">
          <span>YOLO + OpenCV pipeline</span>
          <span>FastAPI • React • WebSocket</span>
        </div>
      </aside>

      <main className="app-main">
        {view === 'upload' && (
          <div className="page-shell">
            <div className="page-header">
              <div>
                <p className="eyebrow">Security Overview</p>
                <h1>Upload & Configure</h1>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div
                  className="header-badge"
                  style={{
                    background: health?.status === 'ok' ? 'rgba(16, 185, 129, 0.12)' : 'rgba(245, 158, 11, 0.12)',
                    borderColor: health?.status === 'ok' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(245, 158, 11, 0.3)',
                    color: health?.status === 'ok' ? '#a7f3d0' : '#fcd34d',
                  }}
                >
                  {health ? (health.status === 'ok' ? 'System online' : 'Monitoring degraded') : 'Checking backend'}
                </div>
                <div className="header-badge">Live Monitoring</div>
              </div>
            </div>
            <UploadPanel
              onAnalysisStarted={handleAnalysisStarted}
              onCacheHit={handleCacheHit}
            />
          </div>
        )}

        {view === 'analyzing' && jobId && (
          <div className="page-shell compact-shell">
            <ProgressPanel jobId={jobId} onComplete={handleProgressComplete} />
          </div>
        )}

        {view === 'dashboard' && videoMeta && videoId != null && (
          <div className="page-shell">
            <Dashboard videoId={videoId} videoMeta={videoMeta} />
          </div>
        )}
      </main>
    </div>
  )
}

export default App
