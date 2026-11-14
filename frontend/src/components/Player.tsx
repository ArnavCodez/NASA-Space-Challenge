import { useEffect, useState } from 'react'

type Props = {
  count: number
  index: number
  setIndex: (i: number) => void
  playing: boolean
  setPlaying: (p: boolean) => void
  fps: number
  setFps: (f: number) => void
  ticks: number[]
  label: string
}

export default function Player({ count, index, setIndex, playing, setPlaying, fps, setFps, ticks, label }: Props) {
  const [recording, setRecording] = useState(false)

  useEffect(() => {
    if (!playing || count < 2) return
    const id = window.setInterval(() => setIndex((index + 1) % count), 1000 / fps)
    return () => window.clearInterval(id)
  }, [playing, fps, count, index, setIndex])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).closest('input, select, textarea')) return
      if (e.key === ' ') {
        e.preventDefault()
        setPlaying(!playing)
      } else if (e.key === 'ArrowRight') {
        setPlaying(false)
        setIndex((index + 1) % count)
      } else if (e.key === 'ArrowLeft') {
        setPlaying(false)
        setIndex((index - 1 + count) % count)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [playing, index, count, setIndex, setPlaying])

  const step = (d: number) => {
    setPlaying(false)
    setIndex((index + d + count) % count)
  }

  function blinkAB() {
    setPlaying(false)
    setIndex(index === 0 ? Math.min(1, count - 1) : 0)
  }

  function exportClip() {
    const canvas = document.querySelector('canvas.viewer') as HTMLCanvasElement | null
    if (!canvas || count < 2 || recording) return
    try {
      setRecording(true)
      setPlaying(false)
      setIndex(0)

      const stream = canvas.captureStream(Math.max(fps, 8))
      const chunks: BlobPart[] = []
      const mimeType = typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported('video/webm;codecs=vp9')
        ? 'video/webm;codecs=vp9'
        : 'video/webm'

      const recorder = new MediaRecorder(stream, { mimeType })
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data)
      }

      recorder.onstop = () => {
        const blob = new Blob(chunks, { type: 'video/webm' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `spherex-blink-${Date.now()}.webm`
        a.click()
        URL.revokeObjectURL(url)
        setRecording(false)
        setPlaying(true)
      }

      recorder.start()

      // record 2 complete cycles through all frames
      const totalSteps = count * 2
      let stepIdx = 0
      const interval = Math.max(1000 / fps, 80)

      const timer = setInterval(() => {
        stepIdx++
        setIndex(stepIdx % count)
        if (stepIdx >= totalSteps) {
          clearInterval(timer)
          recorder.stop()
        }
      }, interval)
    } catch (err) {
      console.error('Recording failed:', err)
      setRecording(false)
    }
  }

  return (
    <div className="player">
      <button onClick={() => step(-1)} aria-label="Previous frame" title="Previous (←)">
        ‹
      </button>
      <button className="play" onClick={() => setPlaying(!playing)} title="Play / pause (space)">
        {playing ? 'Pause' : 'Play'}
      </button>
      <button onClick={() => step(1)} aria-label="Next frame" title="Next (→)">
        ›
      </button>

      {count > 1 && (
        <button
          className="blink-btn"
          onClick={blinkAB}
          title="Blink A/B: quickly toggle between 2 frames (Clyde Tombaugh mode)"
        >
          Blink A/B
        </button>
      )}

      <div className="scrub">
        <input
          type="range"
          min={0}
          max={Math.max(count - 1, 0)}
          value={index}
          onChange={(e) => {
            setPlaying(false)
            setIndex(Number(e.target.value))
          }}
          aria-label="Frame"
        />
        <div className="ticks">
          {count > 1 &&
            ticks.map((t) => <span key={t} style={{ left: `${(t / (count - 1)) * 100}%` }} />)}
        </div>
      </div>

      <span className="counter">
        {count ? index + 1 : 0}/{count}
        <small>{label}</small>
      </span>

      <label className="speed">
        <input type="range" min={1} max={20} value={fps} onChange={(e) => setFps(Number(e.target.value))} />
        <span>{fps} fps</span>
      </label>

      {count > 1 && typeof MediaRecorder !== 'undefined' && (
        <button
          className="export-btn"
          disabled={recording}
          onClick={exportClip}
          title="Export time-lapse clip as WebM video"
        >
          {recording ? '● Recording…' : 'Export Clip'}
        </button>
      )}
    </div>
  )
}
