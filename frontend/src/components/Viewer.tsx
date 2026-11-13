import { useEffect, useMemo, useRef } from 'react'
import type { Stack } from '../api'
import { paint, type Cmap, type Curve, type Limits } from '../stretch'

type Props = {
  stack: Stack
  index: number
  limits: Limits
  curve: Curve
  cmap: Cmap
  showFlags: boolean
  smooth: boolean
}

const SIZE = 720

export default function Viewer({ stack, index, limits, curve, cmap, showFlags, smooth }: Props) {
  const ref = useRef<HTMLCanvasElement>(null)
  const scratch = useMemo(() => document.createElement('canvas'), [])

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
    ctx.drawImage(scratch, 0, 0, SIZE, SIZE)
    overlay(ctx, nx, scale, cmap === 'inverted')
  }, [stack, index, limits, curve, cmap, showFlags, smooth, scratch])

  return <canvas ref={ref} width={SIZE} height={SIZE} className="viewer" aria-label="SPHEREx image" />
}

function overlay(ctx: CanvasRenderingContext2D, nx: number, scale: number, light: boolean) {
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
  const bar = (60 / scale) * px
  const by = SIZE - 20
  ctx.beginPath()
  ctx.moveTo(16, by)
  ctx.lineTo(16 + bar, by)
  ctx.stroke()
  ctx.fillText("1'", 16 + bar / 2 - 5, by - 8)
}
