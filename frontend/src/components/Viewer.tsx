import { useEffect, useMemo, useRef, useState } from 'react'
import type { GaiaStar, Stack } from '../api'
import { paint, type Cmap, type Curve, type Limits } from '../stretch'

export type Motion = { pmra: number; pmdec: number; epoch: number }

type Props = {
  stack: Stack
  index: number
  limits: Limits
  curve: Curve
  cmap: Cmap
  showFlags: boolean
  smooth: boolean
  motion?: Motion
  gaiaStars?: GaiaStar[]
  showGaia?: boolean
}

const SIZE = 720

// arcsec offset (east, north) from the grid centre predicted for a given date
function offsetAt(m: Motion, mjd: number) {
  const years = (mjd - 51544.5) / 365.25 + 2000 - m.epoch
  return [(m.pmra / 1000) * years, (m.pmdec / 1000) * years]
}

export default function Viewer({
  stack,
  index,
  limits,
  curve,
  cmap,
  showFlags,
  smooth,
  motion,
  gaiaStars = [],
  showGaia = false,
}: Props) {
  const ref = useRef<HTMLCanvasElement>(null)
  const scratch = useMemo(() => document.createElement('canvas'), [])
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const dragStart = useRef({ x: 0, y: 0 })

  // reset pan/zoom when target or fov changes
  useEffect(() => {
    setZoom(1)
    setPan({ x: 0, y: 0 })
  }, [stack.meta.ra, stack.meta.dec, stack.meta.fov])

  useEffect(() => {
    const canvas = ref.current
    if (!canvas || !stack.meta.n) return
    const { nx, ny, scale } = stack.meta

    scratch.width = nx
    scratch.height = ny
    const sctx = scratch.getContext('2d')!
    const img = sctx.createImageData(nx, ny)
    paint(img, stack, Math.min(index, stack.meta.n - 1), limits, curve, cmap, showFlags)
    sctx.putImageData(img, 0, 0)

    const ctx = canvas.getContext('2d')!
    ctx.imageSmoothingEnabled = smooth
    ctx.clearRect(0, 0, SIZE, SIZE)

    // apply pan and zoom transformation
    ctx.save()
    ctx.translate(SIZE / 2 + pan.x, SIZE / 2 + pan.y)
    ctx.scale(zoom, zoom)
    ctx.translate(-SIZE / 2, -SIZE / 2)

    ctx.drawImage(scratch, 0, 0, SIZE, SIZE)

    const frames = stack.meta.frames
    if (motion && Math.hypot(motion.pmra, motion.pmdec) > 100 && frames.length) {
      track(ctx, nx, scale, motion, frames[0].mjd, frames[frames.length - 1].mjd, frames[Math.min(index, frames.length - 1)].mjd)
    }

    if (showGaia && gaiaStars.length > 0) {
      drawGaia(ctx, nx, scale, stack.meta.ra, stack.meta.dec, gaiaStars)
    }

    ctx.restore()

    // fixed UI overlays (crosshair, scale bar, compass)
    overlay(ctx, nx, scale, cmap === 'inverted', zoom)
  }, [stack, index, limits, curve, cmap, showFlags, smooth, scratch, motion, showGaia, gaiaStars, zoom, pan])

  function handleWheel(e: React.WheelEvent) {
    e.preventDefault()
    const factor = e.deltaY < 0 ? 1.25 : 0.8
    setZoom((z) => {
      const next = Math.max(1, Math.min(10, z * factor))
      if (next === 1) setPan({ x: 0, y: 0 })
      return next
    })
  }

  function handleMouseDown(e: React.MouseEvent) {
    if (zoom <= 1) return
    setIsDragging(true)
    dragStart.current = { x: e.clientX - pan.x, y: e.clientY - pan.y }
  }

  function handleMouseMove(e: React.MouseEvent) {
    if (!isDragging) return
    setPan({
      x: e.clientX - dragStart.current.x,
      y: e.clientY - dragStart.current.y,
    })
  }

  function handleMouseUp() {
    setIsDragging(false)
  }

  return (
    <div className="viewer-container" style={{ position: 'relative', width: '100%', maxWidth: `${SIZE}px` }}>
      <canvas
        ref={ref}
        width={SIZE}
        height={SIZE}
        className="viewer"
        style={{ cursor: zoom > 1 ? (isDragging ? 'grabbing' : 'grab') : 'crosshair', display: 'block', width: '100%', height: 'auto' }}
        aria-label="SPHEREx image"
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      />
      <div className="zoom-controls">
        <button
          type="button"
          title="Zoom in (or use mousewheel)"
          onClick={() => setZoom((z) => Math.min(10, z * 1.3))}
        >
          +
        </button>
        <button
          type="button"
          title="Zoom out"
          onClick={() =>
            setZoom((z) => {
              const next = Math.max(1, z / 1.3)
              if (next <= 1.05) {
                setPan({ x: 0, y: 0 })
                return 1
              }
              return next
            })
          }
        >
          −
        </button>
        {zoom > 1 && (
          <button
            type="button"
            className="zoom-reset"
            title="Reset view"
            onClick={() => {
              setZoom(1)
              setPan({ x: 0, y: 0 })
            }}
          >
            {zoom.toFixed(1)}x Reset
          </button>
        )}
      </div>
    </div>
  )
}

function drawGaia(
  ctx: CanvasRenderingContext2D,
  nx: number,
  scale: number,
  centerRa: number,
  centerDec: number,
  stars: GaiaStar[],
) {
  const px = SIZE / nx / scale
  const cosDec = Math.cos((centerDec * Math.PI) / 180)

  ctx.strokeStyle = 'rgba(0, 235, 255, 0.85)'
  ctx.fillStyle = 'rgba(0, 235, 255, 0.95)'
  ctx.lineWidth = 1.5
  ctx.font = '500 11px ui-monospace, SFMono-Regular, monospace'

  for (const s of stars) {
    const e = (s.ra - centerRa) * 3600 * cosDec
    const n = (s.dec - centerDec) * 3600
    const x = SIZE / 2 - e * px
    const y = SIZE / 2 - n * px

    if (x < -20 || x > SIZE + 20 || y < -20 || y > SIZE + 20) continue

    const r = Math.max(4, Math.min(14, (20 - s.mag) * 1.6))
    ctx.beginPath()
    ctx.arc(x, y, r, 0, Math.PI * 2)
    ctx.stroke()

    if (s.mag < 16.5) {
      ctx.fillText(`${s.mag}m`, x + r + 3, y + 4)
    }
  }
}

// where the catalogue proper motion says the target should be on this frame's date
function track(ctx: CanvasRenderingContext2D, nx: number, scale: number, m: Motion, first: number, last: number, now: number) {
  const px = SIZE / nx / scale
  const toCanvas = (mjd: number) => {
    const [e, n] = offsetAt(m, mjd)
    return [SIZE / 2 - e * px, SIZE / 2 - n * px]
  }
  const [x0, y0] = toCanvas(first)
  const [x1, y1] = toCanvas(last)
  const [x, y] = toCanvas(now)

  ctx.strokeStyle = 'rgba(90, 230, 140, 0.6)'
  ctx.lineWidth = 2
  ctx.setLineDash([4, 4])
  ctx.beginPath()
  ctx.moveTo(x0, y0)
  ctx.lineTo(x1, y1)
  ctx.stroke()
  ctx.setLineDash([])

  ctx.strokeStyle = 'rgba(90, 230, 140, 0.95)'
  ctx.beginPath()
  ctx.arc(x, y, Math.max(8, 6.15 * 1.6 * (SIZE / nx / scale)), 0, Math.PI * 2)
  ctx.stroke()
}

function overlay(ctx: CanvasRenderingContext2D, nx: number, scale: number, light: boolean, zoom: number = 1) {
  const ink = light ? 'rgba(200, 40, 40, 0.9)' : 'rgba(242, 184, 75, 0.9)'
  const text = light ? '#222' : '#eee'
  const c = SIZE / 2
  const px = SIZE / nx

  // crosshair with a gap so it never covers the target itself
  const gap = Math.max(10, px * 2.5)
  ctx.strokeStyle = ink
  ctx.lineWidth = 2
  ctx.beginPath()
  for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
    ctx.moveTo(c + dx * gap, c + dy * gap)
    ctx.lineTo(c + dx * (gap + 14), c + dy * (gap + 14))
  }
  ctx.stroke()

  ctx.font = '600 13px ui-monospace, SFMono-Regular, Menlo, monospace'
  ctx.fillStyle = text
  ctx.strokeStyle = text
  ctx.lineWidth = 1.5

  // compass: north up, east left
  const ox = SIZE - 24
  const oy = 52
  ctx.beginPath()
  ctx.moveTo(ox, oy)
  ctx.lineTo(ox, oy - 30)
  ctx.moveTo(ox, oy)
  ctx.lineTo(ox - 30, oy)
  ctx.stroke()
  ctx.fillText('N', ox - 4, oy - 36)
  ctx.fillText('E', ox - 44, oy + 5)

  // 1 arcmin scale bar
  const bar = (60 / scale) * px * zoom
  const by = SIZE - 20
  ctx.beginPath()
  ctx.moveTo(16, by)
  ctx.lineTo(16 + bar, by)
  ctx.stroke()
  ctx.fillText("1'", 16 + bar / 2 - 5, by - 8)
}
