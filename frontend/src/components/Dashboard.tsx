import { useEffect, useRef, useState } from 'react'
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { EventRow, Stats } from '../api'
import { fetchEvents, fetchStats, generateReport, queryEvents } from '../api'
import { MetricCard } from './MetricCard'

interface DashboardProps {
  videoId: number
  videoMeta: {
    filename: string
    path: string
    duration_seconds: number
    fps: number
    heatmap_path: string | null
  }
}

const EVENT_LABELS: Record<string, string> = {
  person_entering: 'Person Entering',
  person_leaving: 'Person Leaving',
  object_appeared: 'Object Appeared',
  object_disappeared: 'Object Disappeared',
  placed: 'Placed',
  picked_up: 'Picked Up',
  unattended: 'Unattended',
  zone_breach: 'Zone Breach',
  zone_entry: 'Zone Entry',
  loitering: 'Loitering',
}

const EVENT_COLORS: Record<string, string> = {
  person_entering: '#4F9CF9',
  person_leaving: '#A78BFA',
  object_appeared: '#34D399',
  object_disappeared: '#94A3B8',
  placed: '#FBBF24',
  picked_up: '#F97316',
  unattended: '#F43F5E',
  zone_breach: '#EF4444',
  zone_entry: '#EC4899',
  loitering: '#EAB308',
}

function formatTime(seconds: number): string {
  const t = Math.floor(seconds)
  return [Math.floor(t / 3600), Math.floor((t % 3600) / 60), t % 60]
    .map((v) => String(v).padStart(2, '0'))
    .join(':')
}

type Tab = 'timeline' | 'heatmap' | 'audit'

export function Dashboard({ videoId, videoMeta }: DashboardProps) {
  const [events, setEvents] = useState<EventRow[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [search, setSearch] = useState('')
  const [question, setQuestion] = useState('')
  const [queryAnswer, setQueryAnswer] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>('timeline')
  const [report, setReport] = useState<string | null>(null)
  const [reportLoading, setReportLoading] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const videoRef = useRef<HTMLVideoElement | null>(null)

  useEffect(() => {
    fetchEvents(videoId, search).then(setEvents)
    fetchStats(videoId).then(setStats)
  }, [videoId, search])

  const handleQuery = async () => {
    if (!question.trim()) return
    const resp = await queryEvents(videoId, question)

    if (!resp.answer) {
      setQueryAnswer('No matching events found.')
      return
    }

    if (Array.isArray(resp.answer)) {
      const first = resp.answer[0] as EventRow | undefined
      if (!first) {
        setQueryAnswer('No matching events found.')
        return
      }
      setQueryAnswer(
        `${first.object_label} at ${formatTime(first.timestamp_seconds)} — ${EVENT_LABELS[first.event_type] ?? first.event_type}`,
      )
      return
    }

    if (typeof resp.answer === 'object' && resp.answer !== null) {
      const answerObj = resp.answer as Record<string, unknown>
      if ('count' in answerObj) {
        setQueryAnswer(`Found ${Number(answerObj.count)} matching events.`)
        return
      }

      if ('object_label' in answerObj && 'timestamp_seconds' in answerObj) {
        const event = answerObj as Partial<EventRow>
        setQueryAnswer(
          `${event.object_label ?? 'Event'} at ${formatTime(Number(event.timestamp_seconds ?? 0))} — ${EVENT_LABELS[event.event_type ?? ''] ?? event.event_type ?? 'event'}`,
        )
        return
      }
    }

    setQueryAnswer(String(resp.answer))
  }

  const handleGenerateReport = async () => {
    setReportLoading(true)
    const resp = await generateReport(videoId)
    setReport(resp.report)
    setReportLoading(false)
  }

  const eventTypeOrder = Object.keys(EVENT_LABELS)
  const timelineTicks = [...new Set(events.map((e) => eventTypeOrder.indexOf(e.event_type) + 1))]
    .sort((a, b) => a - b)
  const timelineYLabels: Record<number, string> = Object.fromEntries(
    eventTypeOrder.map((eventType, index) => [index + 1, EVENT_LABELS[eventType] ?? eventType]),
  )

  const chartData = [...events]
    .sort((a, b) => a.timestamp_seconds - b.timestamp_seconds)
    .map((e) => ({
      x: e.timestamp_seconds,
      y: eventTypeOrder.indexOf(e.event_type) + 1,
      type: e.event_type,
      label: EVENT_LABELS[e.event_type] ?? e.event_type,
      color: EVENT_COLORS[e.event_type] ?? '#94A3B8',
      object: `${e.object_label} #${e.tracking_id ?? '?'}`,
    }))

  const tabs: { key: Tab; label: string }[] = [
    { key: 'timeline', label: '📊 Events & Timeline' },
    { key: 'heatmap', label: '🔥 Heatmap' },
    { key: 'audit', label: '🛡️ AI Audit Report' },
  ]

  const videoUrl = videoMeta?.path ? `/videos/${videoMeta.path.split(/[/\\]/).pop()}` : ''

  const handleVideoSeek = (time: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = time
      setCurrentTime(time)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Metadata bar */}
      <div
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border)',
          borderRadius: 8,
          padding: '10px 16px',
          display: 'flex',
          gap: 20,
          fontSize: 13,
          alignItems: 'center',
          flexWrap: 'wrap',
        }}
      >
        <strong style={{ color: 'var(--text-h)' }}>🎬 {videoMeta.filename}</strong>
        <span>{formatTime(videoMeta.duration_seconds)} duration</span>
        <span>{videoMeta.fps.toFixed(1)} fps</span>
        <span style={{ color: 'var(--accent)' }}>Video #{videoId}</span>
      </div>

      {/* Metric cards */}
      {stats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: 12 }}>
          <MetricCard label="Total Events" value={stats.total} icon="📋" />
          <MetricCard label="People" value={stats.people} icon="🧍" />
          <MetricCard label="Objects" value={stats.objects_detected} icon="📦" />
          <MetricCard label="Unattended" value={stats.unattended} icon="⚠️" variant="warning" />
          <MetricCard label="Zone Breaches" value={stats.breaches} icon="🚨" variant="danger" />
          <MetricCard label="Loitering" value={stats.loitering} icon="👀" variant="warning" />
        </div>
      )}

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--border)', paddingBottom: 0 }}>
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            style={{
              background: 'none',
              border: 'none',
              borderBottom: tab === t.key ? '2px solid var(--accent)' : '2px solid transparent',
              color: tab === t.key ? 'var(--text-h)' : 'var(--text)',
              padding: '10px 16px',
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: tab === t.key ? 600 : 400,
              transition: 'all 0.15s',
              marginBottom: -1,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ── TIMELINE TAB ── */}
      {tab === 'timeline' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div
            style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: 12,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <h4 style={{ margin: 0, color: 'var(--text-h)', fontSize: 13 }}>📹 Footage Review</h4>
            </div>
            {videoUrl ? (
              <>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 12,
                    marginBottom: 8,
                    color: 'var(--text-h)',
                    fontSize: 12,
                    fontWeight: 600,
                  }}
                >
                  <span>Current time: {formatTime(currentTime)}</span>
                  <span>{formatTime(videoMeta.duration_seconds)} total</span>
                </div>
                <video
                  ref={videoRef}
                  controls
                  preload="metadata"
                  src={videoUrl}
                  onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime || 0)}
                  onLoadedMetadata={(event) => setCurrentTime(event.currentTarget.currentTime || 0)}
                  style={{ width: '100%', maxHeight: 340, borderRadius: 6, background: '#000', display: 'block' }}
                />
              </>
            ) : (
              <div style={{ padding: 20, textAlign: 'center', color: 'var(--text)', background: 'var(--bg-panel)', borderRadius: 6 }}>
                No video available for this analysis.
              </div>
            )}
          </div>

          {/* NL Query */}
          <div style={{ display: 'flex', gap: 10 }}>
            <input
              placeholder="💬 Ask a question (e.g. Any loitering after 5 seconds?)"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleQuery()}
              style={{ ...inputStyle, flex: 1 }}
            />
            <button onClick={handleQuery} style={btnStyle}>
              Ask
            </button>
          </div>
          {queryAnswer && (
            <div
              style={{
                background: 'var(--accent-glow)',
                border: '1px solid var(--accent)',
                borderRadius: 6,
                padding: '10px 14px',
                color: 'var(--text-h)',
                fontSize: 13,
              }}
            >
              🎯 {queryAnswer}
            </div>
          )}

          {/* Chart */}
          {chartData.length > 0 && (
            <div
              style={{
                background: 'var(--bg-card)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: 16,
              }}
            >
              <h4 style={{ margin: '0 0 12px', color: 'var(--text-h)', fontSize: 13, fontWeight: 600 }}>
                Event Timeline
              </h4>
              <ResponsiveContainer width="100%" height={280}>
                <ScatterChart margin={{ top: 8, right: 20, bottom: 8, left: 4 }}>
                  <CartesianGrid stroke="rgba(255,255,255,0.05)" />
                  <XAxis
                    dataKey="x"
                    type="number"
                    name="Time (s)"
                    tick={{ fill: 'var(--text)', fontSize: 11 }}
                    label={{ value: 'Time (s)', position: 'insideBottom', offset: -4, fill: 'var(--text)', fontSize: 11 }}
                  />
                  <YAxis
                    type="number"
                    dataKey="y"
                    width={168}
                    domain={[1, Math.max(1, ...timelineTicks)]}
                    ticks={timelineTicks}
                    tick={{ fill: 'var(--text)', fontSize: 10 }}
                    tickFormatter={(value) => timelineYLabels[Number(value)] ?? ''}
                  />
                  <Tooltip
                    cursor={{ strokeDasharray: '3 3' }}
                    contentStyle={{
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border)',
                      borderRadius: 6,
                      fontSize: 12,
                    }}
                    formatter={(value, name, props) => {
                      const item = props?.payload as { object?: string; label?: string } | undefined
                      if (name === 'x') return [formatTime(Number(value)), 'Time']
                      return [item?.object ?? item?.label ?? value, 'Event']
                    }}
                    labelFormatter={(value) => `Time ${formatTime(Number(value))}`}
                  />
                  <Scatter
                    data={chartData}
                    shape={(props: { cx?: number; cy?: number; fill?: string; payload?: { color?: string } }) => {
                      const { cx = 0, cy = 0, payload } = props
                      return (
                        <circle
                          cx={cx}
                          cy={cy}
                          r={6}
                          fill={payload?.color ?? '#94A3B8'}
                          stroke="rgba(0,0,0,0.3)"
                          strokeWidth={1}
                        />
                      )
                    }}
                  />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Event table */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <input
                placeholder="Filter events..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ ...inputStyle, maxWidth: 280 }}
              />
              <button
                onClick={() => {
                  const rows = events.map((e) =>
                    [
                      formatTime(e.timestamp_seconds),
                      e.timestamp_seconds,
                      e.object_label,
                      e.tracking_id ?? '',
                      EVENT_LABELS[e.event_type] ?? e.event_type,
                      e.confidence.toFixed(3),
                      e.details,
                    ].join(','),
                  )
                  const csv = ['timestamp,seconds,object,tracking_id,event,confidence,details', ...rows].join('\n')
                  const blob = new Blob([csv], { type: 'text/csv' })
                  const url = URL.createObjectURL(blob)
                  const a = document.createElement('a')
                  a.href = url
                  a.download = `events_video_${videoId}.csv`
                  a.click()
                  URL.revokeObjectURL(url)
                }}
                style={{ ...btnStyle, background: 'var(--bg-panel)' }}
              >
                ⬇ Export CSV
              </button>
            </div>

            <div style={{ overflowX: 'auto', borderRadius: 8, border: '1px solid var(--border)' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ background: 'var(--bg-panel)' }}>
                    {['Time', 'Object', 'Track ID', 'Event', 'Confidence', 'Details'].map((h) => (
                      <th
                        key={h}
                        style={{
                          padding: '8px 12px',
                          textAlign: 'left',
                          color: 'var(--text)',
                          fontWeight: 600,
                          borderBottom: '1px solid var(--border)',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {events.map((e, i) => (
                    <tr
                      key={e.id}
                      onClick={() => handleVideoSeek(e.timestamp_seconds)}
                      style={{
                        background: i % 2 === 0 ? 'var(--bg-card)' : 'transparent',
                        borderLeft: `3px solid ${EVENT_COLORS[e.event_type] ?? '#94A3B8'}`,
                        cursor: 'pointer',
                      }}
                    >
                      <td style={tdStyle}>{formatTime(e.timestamp_seconds)}</td>
                      <td style={tdStyle}>{e.object_label}</td>
                      <td style={tdStyle}>{e.tracking_id ?? '—'}</td>
                      <td style={tdStyle}>
                        <span
                          style={{
                            background: `${EVENT_COLORS[e.event_type] ?? '#94A3B8'}22`,
                            color: EVENT_COLORS[e.event_type] ?? '#94A3B8',
                            padding: '2px 7px',
                            borderRadius: 4,
                            fontSize: 11,
                            fontWeight: 600,
                          }}
                        >
                          {EVENT_LABELS[e.event_type] ?? e.event_type}
                        </span>
                      </td>
                      <td style={tdStyle}>{e.confidence.toFixed(3)}</td>
                      <td style={{ ...tdStyle, color: 'var(--text)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {e.details || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {events.length === 0 && (
                <p style={{ textAlign: 'center', padding: 24, color: 'var(--text)' }}>No events found.</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── HEATMAP TAB ── */}
      {tab === 'heatmap' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <h4 style={{ margin: 0, color: 'var(--text-h)' }}>🔥 Spatial Activity Heatmap</h4>
          {videoMeta.heatmap_path ? (
            <div>
              <img
                src={`/heatmaps/${videoMeta.heatmap_path.split(/[/\\]/).pop()}`}
                alt="Activity Heatmap"
                style={{ width: '100%', borderRadius: 8, border: '1px solid var(--border)' }}
              />
              <p style={{ fontSize: 12, color: 'var(--text)', marginTop: 8 }}>
                Gaussian-blurred spatial density map — brighter areas indicate higher tracked activity.
              </p>
            </div>
          ) : (
            <div
              style={{
                background: 'var(--bg-panel)',
                borderRadius: 8,
                border: '1px solid var(--border)',
                padding: 40,
                textAlign: 'center',
                color: 'var(--text)',
              }}
            >
              <p style={{ fontSize: 32, margin: '0 0 8px' }}>🔥</p>
              <p>Heatmap not yet generated. Run a fresh analysis to generate one.</p>
            </div>
          )}
        </div>
      )}

      {/* ── AUDIT TAB ── */}
      {tab === 'audit' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <h4 style={{ margin: 0, color: 'var(--text-h)' }}>🛡️ AI Security Incident Audit</h4>

          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <p style={{ fontSize: 12, color: 'var(--text)', margin: 0, flex: 1 }}>
              Generate an AI-powered security audit report. Set the <code>ANTHROPIC_API_KEY</code> environment variable on the server for enhanced Claude reports, or leave unset for an offline report.
            </p>
            <button onClick={handleGenerateReport} disabled={reportLoading} style={btnStyle}>
              {reportLoading ? 'Generating...' : '📄 Generate Report'}
            </button>
          </div>

          {report && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <button
                onClick={() => {
                  const blob = new Blob([report], { type: 'text/markdown' })
                  const url = URL.createObjectURL(blob)
                  const a = document.createElement('a')
                  a.href = url
                  a.download = `security_report_video_${videoId}.md`
                  a.click()
                  URL.revokeObjectURL(url)
                }}
                style={{ ...btnStyle, alignSelf: 'flex-start', background: 'var(--bg-panel)' }}
              >
                ⬇ Download Report (.md)
              </button>
              <pre
                style={{
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  padding: 20,
                  whiteSpace: 'pre-wrap',
                  fontSize: 13,
                  lineHeight: 1.6,
                  color: 'var(--text-h)',
                  maxHeight: 600,
                  overflowY: 'auto',
                }}
              >
                {report}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  background: 'var(--bg)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  color: 'var(--text-h)',
  padding: '8px 10px',
  fontSize: 13,
  width: '100%',
}

const btnStyle: React.CSSProperties = {
  background: 'var(--accent)',
  color: '#fff',
  border: 'none',
  borderRadius: 6,
  padding: '8px 18px',
  fontSize: 13,
  fontWeight: 600,
  cursor: 'pointer',
  whiteSpace: 'nowrap',
}

const tdStyle: React.CSSProperties = {
  padding: '7px 12px',
  color: 'var(--text-h)',
  borderBottom: '1px solid var(--border)',
}
