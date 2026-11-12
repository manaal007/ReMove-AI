import { useCallback, useEffect, useRef, useState } from 'react'

// Opens the webcam and attaches it to a <video> element.
// status: 'idle' | 'on' | 'denied' | 'error'
export default function useCamera(autoStart = true) {
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const [status, setStatus] = useState('idle')

  const start = useCallback(async () => {
    if (streamRef.current) return
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' },
        audio: false,
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play().catch(() => {})
      }
      setStatus('on')
    } catch (err) {
      setStatus(err?.name === 'NotAllowedError' ? 'denied' : 'error')
    }
  }, [])

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    setStatus('idle')
  }, [])

  useEffect(() => {
    if (autoStart) start()
    return () => stop()
  }, [autoStart, start, stop])

  return { videoRef, status, start, stop }
}
