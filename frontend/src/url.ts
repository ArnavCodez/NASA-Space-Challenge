import type { View } from './api'
import type { Cmap, Curve } from './stretch'

export type UrlState = {
  name?: string
  ra?: number
  dec?: number
  det?: string
  view?: View
  fov?: number
  ref?: number
  fps?: number
  curve?: Curve
  cmap?: Cmap
  sort?: 'time' | 'wave'
  gaia?: boolean
}

const NUMBERS = ['ra', 'dec', 'fov', 'ref', 'fps'] as const
const STRINGS = ['name', 'det', 'view', 'curve', 'cmap', 'sort'] as const
const BOOLEANS = ['gaia'] as const

export function readUrl(): UrlState {
  const q = new URLSearchParams(location.search)
  const out: Record<string, string | number | boolean> = {}
  for (const k of NUMBERS) {
    const v = q.get(k)
    if (v !== null && v !== '' && !Number.isNaN(Number(v))) out[k] = Number(v)
  }
  for (const k of STRINGS) {
    const v = q.get(k)
    if (v) out[k] = v
  }
  for (const k of BOOLEANS) {
    const v = q.get(k)
    if (v === 'true' || v === '1') out[k] = true
  }
  return out as UrlState
}

export function toQuery(s: UrlState) {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(s)) {
    if (v === undefined || v === '' || v === false) continue
    if (k === 'ra' || k === 'dec') {
      q.set(k, Number(v).toFixed(5))
    } else if (typeof v === 'boolean') {
      if (v) q.set(k, '1')
    } else {
      q.set(k, String(v))
    }
  }
  return q.toString()
}

export function writeUrl(s: UrlState) {
  history.replaceState(null, '', `${location.pathname}?${toQuery(s)}`)
}
