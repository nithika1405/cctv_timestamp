import { useEffect, useRef, useState } from 'react'

export interface ProgressMessage {
  type: 'progress' | 'not_found'
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  metrics: {
    timestamp_seconds?: number
    frame_index?: number
    fps?: number
  }
  error: string | null
  video_id: number | null
}

const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_DELAY_MS = 2000

export function useAnalysisProgress(jobId: string | null) {
  const [message, setMessage] = useState<ProgressMessage | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectAttempts = useRef(0)

  useEffect(() => {
    if (!jobId) return

    let cancelled = false

    function connect() {
      if (cancelled) return

      // Auto-detect ws:// or wss:// based on page protocol
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${protocol}//${window.location.host}/ws/progress/${jobId}`)
      wsRef.current = ws

      ws.onopen = () => {
        reconnectAttempts.current = 0
      }

      ws.onmessage = (e) => {
        const data = JSON.parse(e.data) as ProgressMessage
        setMessage(data)
        // Auto-close when done
        if (data.status === 'completed' || data.status === 'failed') {
          ws.close()
        }
      }

      ws.onerror = () => {
        // Error will trigger onclose, reconnection handled there
      }

      ws.onclose = (e) => {
        if (cancelled) return

        // Don't reconnect if the job completed/failed normally
        const lastStatus = message?.status
        if (lastStatus === 'completed' || lastStatus === 'failed') return

        // Reconnect with backoff if connection dropped unexpectedly
        if (reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS && e.code !== 1000) {
          reconnectAttempts.current++
          setTimeout(connect, RECONNECT_DELAY_MS * reconnectAttempts.current)
        } else if (reconnectAttempts.current >= MAX_RECONNECT_ATTEMPTS) {
          setMessage((prev) =>
            prev
              ? { ...prev, status: 'failed', error: 'Lost connection to server. Please retry.' }
              : null,
          )
        }
      }
    }

    connect()

    return () => {
      cancelled = true
      wsRef.current?.close()
    }
  }, [jobId])

  return message
}
