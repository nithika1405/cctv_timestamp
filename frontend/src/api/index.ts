import axios from 'axios'

const http = axios.create({ baseURL: '/' })

export interface VideoMeta {
  id: number
  filename: string
  path: string
  fps: number
  frame_count: number
  duration_seconds: number
  heatmap_path: string | null
  roi_coords: string | null
  created_at: string
  video_hash: string | null
}

export interface EventRow {
  id: number
  video_id: number
  timestamp_seconds: number
  object_label: string
  tracking_id: number | null
  event_type: string
  confidence: number
  details: string
  created_at: string
}

export interface Stats {
  total: number
  people: number
  unattended: number
  objects_detected: number
  loitering: number
  breaches: number
}

export interface UploadResponse {
  filename: string
  video_hash: string
  path: string
  cached: boolean
}

export interface AnalysisRequest {
  video_path: string
  video_hash: string
  filename: string
  model_name?: string
  tracker?: string
  unattended_secs?: number
  proximity_ratio?: number
  loitering_secs?: number
  sample_every?: number
  confidence_threshold?: number
  scene_profile?: 'balanced' | 'crowded' | 'low_light' | 'outdoor'
  roi_polygon?: [number, number][] | null
}

export interface AnalysisStartResponse {
  status: 'started' | 'running' | 'cached'
  job_id?: string
  video_id?: number
}

export interface HealthStatus {
  status: 'ok' | 'degraded' | 'error'
  service: string
  timestamp: string
  database: {
    path: string
    exists: boolean
    videos: number
    events: number
  }
  uploads: {
    directory: string
    exists: boolean
    file_count: number
  }
  jobs: {
    active: number
    total: number
  }
}

// --- API calls ---

export const fetchVideos = () =>
  http.get<VideoMeta[]>('/api/videos').then((r) => r.data)

export const fetchVideo = (id: number) =>
  http.get<VideoMeta>(`/api/videos/${id}`).then((r) => r.data)

export const deleteVideo = (id: number) =>
  http.delete<{ deleted: boolean; video_id: number }>(`/api/videos/${id}`).then((r) => r.data)

export const fetchEvents = (videoId: number, search = '') =>
  http.get<EventRow[]>(`/api/events/${videoId}`, { params: { search } }).then((r) => r.data)

export const fetchStats = (videoId: number) =>
  http.get<Stats>(`/api/stats/${videoId}`).then((r) => r.data)

export const uploadVideo = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return http.post<UploadResponse>('/api/upload', form).then((r) => r.data)
}

export const startAnalysis = (req: AnalysisRequest) =>
  http.post<AnalysisStartResponse>('/api/analyze', req).then((r) => r.data)

export const fetchHealth = () =>
  http.get<HealthStatus>('/api/health').then((r) => r.data)

export const queryEvents = (videoId: number, question: string) =>
  http.post<{ answer: unknown }>('/api/query', { video_id: videoId, question }).then((r) => r.data)

export const generateReport = (videoId: number) =>
  http.post<{ report: string }>('/api/report', { video_id: videoId }).then(
    (r) => r.data,
  )
