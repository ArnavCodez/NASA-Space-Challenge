import { useEffect } from 'react'

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

  return (
    <div className="player">
      <button onClick={() => step(-1)} aria-label="Previous frame" title="Previous (←)">‹</button>
      <button className="play" onClick={() => setPlaying(!playing)} title="Play / pause (space)">
        {playing ? 'Pause' : 'Play'}
      </button>
      <button onClick={() => step(1)} aria-label="Next frame" title="Next (→)">›</button>

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
    </div>
  )
}
