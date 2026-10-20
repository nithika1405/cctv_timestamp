import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import type { AnalysisRequest, UploadResponse } from '../api'
import { startAnalysis, uploadVideo } from '../api'

interface UploadPanelProps {
  onAnalysisStarted: (jobId: string, videoPath: string, videoHash: string, filename: string) => void
  onCacheHit: (videoId: number) => void
}

const ROI_PRESETS: Record<string, [number, number][] | null> = {
  'None (Full Frame)': null,
  'Center Zone': [
    [0.25, 0.25],
    [0.75, 0.25],
    [0.75, 0.75],
    [0.25, 0.75],
  ],
  'Left Entrance': [
    [0.0, 0.0],
    [0.35, 0.0],
    [0.35, 1.0],
    [0.0, 1.0],
  ],
  'Right Boundary': [
    [0.65, 0.0],
    [1.0, 0.0],
    [1.0, 1.0],
    [0.65, 1.0],
  ],
}

export function UploadPanel({ onAnalysisStarted, onCacheHit }: UploadPanelProps) {
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null)
  const [uploading, setUploading] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sceneProfile, setSceneProfile] = useState<AnalysisRequest['scene_profile']>('balanced')

  // Config state
  const [modelName, setModelName] = useState('yolo11s.pt')
  const [tracker, setTracker] = useState('botsort.yaml')
  const [sampleEvery, setSampleEvery] = useState(1)
  const [loiteringSecs, setLoiteringSecs] = useState(15)
  const [unattendedSecs, setUnattendedSecs] = useState(8)
  const [proximityRatio, setProximityRatio] = useState(0.75)
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.45)
  const [roiPreset, setRoiPreset] = useState<string>('None (Full Frame)')

  const applySceneProfile = (profile: NonNullable<AnalysisRequest['scene_profile']>) => {
    setSceneProfile(profile)
    setTracker('botsort.yaml')
    setSampleEvery(1)
    if (profile === 'crowded') {
      setModelName('yolo11m.pt')
      setConfidenceThreshold(0.3)
      setUnattendedSecs(10)
      setProximityRatio(0.65)
      setLoiteringSecs(20)
    } else if (profile === 'low_light') {
      setModelName('yolo11s.pt')
      setConfidenceThreshold(0.3)
      setUnattendedSecs(12)
      setProximityRatio(0.8)
      setLoiteringSecs(20)
    } else if (profile === 'outdoor') {
      setModelName('yolo11s.pt')
      setConfidenceThreshold(0.5)
      setUnattendedSecs(8)
      setProximityRatio(0.75)
      setLoiteringSecs(15)
    } else {
      setModelName('yolo11s.pt')
      setConfidenceThreshold(0.45)
      setUnattendedSecs(8)
      setProximityRatio(0.75)
      setLoiteringSecs(15)
    }
  }

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0]
      if (!file) return
      setError(null)
      setUploading(true)
      try {
        const result = await uploadVideo(file)
        setUploadResult(result)
      } catch {
        setError('Upload failed. Make sure the backend is running.')
      } finally {
        setUploading(false)
      }
    },
    [],
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'video/*': ['.mp4', '.avi', '.mov', '.mkv'] },
    maxFiles: 1,
  })

  const handleAnalyze = async () => {
    if (!uploadResult) return
    setAnalyzing(true)
    setError(null)
    try {
      const req: AnalysisRequest = {
        video_path: uploadResult.path,
        video_hash: uploadResult.video_hash,
        filename: uploadResult.filename,
        model_name: modelName,
        tracker,
        unattended_secs: unattendedSecs,
        proximity_ratio: proximityRatio,
        loitering_secs: loiteringSecs,
        sample_every: sampleEvery,
        confidence_threshold: confidenceThreshold,
        scene_profile: sceneProfile,
        roi_polygon: ROI_PRESETS[roiPreset],
      }
      const resp = await startAnalysis(req)
      if (resp.status === 'cached' && resp.video_id != null) {
        onCacheHit(resp.video_id)
      } else if (resp.job_id) {
        onAnalysisStarted(resp.job_id, uploadResult.path, uploadResult.video_hash, uploadResult.filename)
      }
    } catch {
      setError('Failed to start analysis. Make sure the backend is running.')
    } finally {
      setAnalyzing(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Dropzone */}
      <div
        {...getRootProps()}
        style={{
          border: `2px dashed ${isDragActive ? 'var(--accent)' : 'var(--border)'}`,
          borderRadius: 10,
          padding: 40,
          textAlign: 'center',
          cursor: 'pointer',
          background: isDragActive ? 'var(--accent-glow)' : 'var(--bg-panel)',
          transition: 'all 0.2s',
        }}
      >
        <input {...getInputProps()} />
        <div style={{ fontSize: 36, marginBottom: 12 }}>🎥</div>
        {uploading ? (
          <p style={{ color: 'var(--accent)' }}>Uploading...</p>
        ) : uploadResult ? (
          <div>
            <p style={{ color: 'var(--success)', fontWeight: 600 }}>✓ {uploadResult.filename}</p>
            {uploadResult.cached && (
              <p style={{ color: 'var(--warning)', fontSize: 12, marginTop: 4 }}>
                ⚡ Already in cache — analysis will load instantly
              </p>
            )}
          </div>
        ) : (
          <p>
            {isDragActive
              ? 'Drop the footage here...'
              : 'Drag & drop CCTV footage, or click to browse'}
          </p>
        )}
      </div>

      {/* Config grid */}
      {uploadResult && (
        <>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
              gap: 16,
            }}
          >
            <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Scene profile
              </span>
              <select
                value={sceneProfile}
                onChange={(e) => applySceneProfile(e.target.value as NonNullable<AnalysisRequest['scene_profile']>)}
                style={inputStyle}
              >
                <option value="balanced">Balanced</option>
                <option value="crowded">Crowded</option>
                <option value="low_light">Low light</option>
                <option value="outdoor">Outdoor</option>
              </select>
            </label>

            <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                YOLO Model
              </span>
              <select
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                style={inputStyle}
              >
                <option value="yolo11n.pt">YOLO11 Nano</option>
                <option value="yolo11s.pt">YOLO11 Small</option>
                <option value="yolo11m.pt">YOLO11 Medium</option>
              </select>
            </label>

            <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Tracker
              </span>
              <select
                value={tracker}
                onChange={(e) => setTracker(e.target.value)}
                style={inputStyle}
              >
                <option value="bytetrack.yaml">ByteTrack</option>
                <option value="botsort.yaml">BoT-SORT</option>
              </select>
            </label>

            <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                ROI Zone Preset
              </span>
              <select
                value={roiPreset}
                onChange={(e) => setRoiPreset(e.target.value)}
                style={inputStyle}
              >
                {Object.keys(ROI_PRESETS).map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
              </select>
            </label>

            <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Detection confidence: {confidenceThreshold.toFixed(2)}
              </span>
              <input
                type="range"
                min={0.2}
                max={0.8}
                step={0.05}
                value={confidenceThreshold}
                onChange={(e) => setConfidenceThreshold(Number(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--accent)' }}
              />
            </label>

            <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Proximity ratio: {proximityRatio.toFixed(2)}
              </span>
              <input
                type="range"
                min={0.3}
                max={1.5}
                step={0.05}
                value={proximityRatio}
                onChange={(e) => setProximityRatio(Number(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--accent)' }}
              />
            </label>

            <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Sample every Nth frame: {sampleEvery}
              </span>
              <input
                type="range"
                min={1}
                max={5}
                value={sampleEvery}
                onChange={(e) => setSampleEvery(Number(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--accent)' }}
              />
            </label>

            <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Loitering threshold: {loiteringSecs}s
              </span>
              <input
                type="range"
                min={3}
                max={60}
                value={loiteringSecs}
                onChange={(e) => setLoiteringSecs(Number(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--accent)' }}
              />
            </label>

            <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Unattended after: {unattendedSecs}s
              </span>
              <input
                type="range"
                min={2}
                max={30}
                value={unattendedSecs}
                onChange={(e) => setUnattendedSecs(Number(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--accent)' }}
              />
            </label>
          </div>

          {error && (
            <p style={{ color: 'var(--danger)', background: 'rgba(244,63,94,0.1)', padding: '10px 14px', borderRadius: 6 }}>
              {error}
            </p>
          )}

          <button
            onClick={handleAnalyze}
            disabled={analyzing}
            style={{
              background: analyzing ? 'var(--border)' : 'var(--accent)',
              color: analyzing ? 'var(--text)' : '#fff',
              border: 'none',
              borderRadius: 8,
              padding: '12px 24px',
              fontSize: 14,
              fontWeight: 600,
              cursor: analyzing ? 'not-allowed' : 'pointer',
              transition: 'background 0.2s',
            }}
          >
            {analyzing ? 'Starting analysis...' : '🚀 Analyze Video'}
          </button>
        </>
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
