import type { Stack } from './api'

export type Curve = 'linear' | 'asinh' | 'log'
export type Cmap = 'gray' | 'inverted' | 'viridis' | 'diverging'
export type Limits = { lo: number; hi: number }

const STOPS: Record<Cmap, string[]> = {
  gray: ['#000000', '#ffffff'],
  inverted: ['#ffffff', '#000000'],
  viridis: ['#440154', '#482878', '#3e4a89', '#31688e', '#26828e', '#1f9e89', '#35b779', '#6ece58', '#b5de2b', '#fde725'],
  diverging: ['#2166ac', '#67a9cf', '#d1e5f0', '#f7f7f7', '#fddbc7', '#ef8a62', '#b2182b'],
}

const hex = (s: string) => [1, 3, 5].map((i) => parseInt(s.slice(i, i + 2), 16))

const luts = new Map<Cmap, Uint8ClampedArray>()

function lut(cmap: Cmap): Uint8ClampedArray {
  let out = luts.get(cmap)
  if (out) return out
  const stops = STOPS[cmap].map(hex)
  out = new Uint8ClampedArray(256 * 3)
  for (let i = 0; i < 256; i++) {
    const x = (i / 255) * (stops.length - 1)
    const k = Math.min(Math.floor(x), stops.length - 2)
    const f = x - k
    for (let c = 0; c < 3; c++) out[i * 3 + c] = stops[k][c] + (stops[k + 1][c] - stops[k][c]) * f
  }
  luts.set(cmap, out)
  return out
}

function shape(curve: Curve, t: number) {
  if (curve === 'asinh') return Math.asinh(t * 10) / Math.asinh(10)
  if (curve === 'log') return Math.log10(1 + 999 * t) / 3
  return t
}

// mask bits from backend/app/frames.py
export const MASK = { bad: 1, source: 2, artifact: 4, transient: 8, saturated: 16 }

const TINT: [number, number[]][] = [
  [MASK.saturated, [255, 64, 64]],
  [MASK.artifact, [255, 170, 0]],
  [MASK.transient, [80, 200, 255]],
]

export function paint(
  out: ImageData,
  stack: Stack,
  index: number,
  { lo, hi }: Limits,
  curve: Curve,
  cmap: Cmap,
  showFlags: boolean,
) {
  const { nx, ny } = stack.meta
  const size = nx * ny
  const base = index * size
  const colors = lut(cmap)
  const span = hi - lo || 1
  const centered = cmap === 'diverging'
  const px = out.data

  for (let i = 0; i < size; i++) {
    const v = stack.images[base + i]
    const o = i * 4
    px[o + 3] = 255
    if (Number.isNaN(v)) {
      px[o] = 40
      px[o + 1] = 32
      px[o + 2] = 48
      continue
    }
    let t = Math.min(1, Math.max(0, (v - lo) / span))
    if (centered) {
      // bend each side of zero on its own so zero stays white
      const u = 2 * t - 1
      t = 0.5 + 0.5 * Math.sign(u) * shape(curve, Math.abs(u))
    } else {
      t = shape(curve, t)
    }
    const k = Math.round(t * 255) * 3
    px[o] = colors[k]
    px[o + 1] = colors[k + 1]
    px[o + 2] = colors[k + 2]

    if (showFlags) {
      const m = stack.masks[base + i]
      for (const [bit, rgb] of TINT) {
        if (m & bit) {
          px[o] = (px[o] + rgb[0]) / 2
          px[o + 1] = (px[o + 1] + rgb[1]) / 2
          px[o + 2] = (px[o + 2] + rgb[2]) / 2
          break
        }
      }
    }
  }
}

function median(xs: number[]) {
  const s = [...xs].sort((a, b) => a - b)
  return s.length ? s[Math.floor(s.length / 2)] : 0
}

// zscale limits come from the server per frame; "steady" uses one set for the whole stack
// so brightness changes between frames stay visible
export function limitsFor(stack: Stack, index: number, steady: boolean, contrast: number, symmetric: boolean): Limits {
  const frames = stack.meta.frames
  let lo: number, hi: number
  if (steady) {
    lo = median(frames.map((f) => f.vmin))
    hi = median(frames.map((f) => f.vmax))
  } else {
    lo = frames[index]?.vmin ?? 0
    hi = frames[index]?.vmax ?? 1
  }
  const mid = (lo + hi) / 2
  const half = ((hi - lo) / 2) * contrast
  if (symmetric) {
    const m = Math.max(Math.abs(lo), Math.abs(hi)) * contrast
    return { lo: -m, hi: m }
  }
  return { lo: mid - half, hi: mid + half }
}
