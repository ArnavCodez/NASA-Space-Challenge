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
}

const NUMBERS = ['ra', 'dec', 'fov', 'ref', 'fps'] as const
const STRINGS = ['name', 'det', 'view', 'curve', 'cmap'] as const

export function readUrl(): UrlState {
  const q = new URLSearchParams(location.search)
  const out: Record<string, string | number> = {}
  for (const k of NUMBERS) {
    const v = q.get(k)
    if (v !== null && v !== '' && !Number.isNaN(Number(v))) out[k] = Number(v)
  }
  for (const k of STRINGS) {
    const v = q.get(k)
    if (v) out[k] = v
  }
  return out as UrlState
}

export function toQuery(s: UrlState) {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(s)) {
    if (v === undefined || v === '') continue
    q.set(k, k === 'ra' || k === 'dec' ? Number(v).toFixed(5) : String(v))
  }
  return q.toString()
}

export function writeUrl(s: UrlState) {
  history.replaceState(null, '', `${location.pathname}?${toQuery(s)}`)
}
