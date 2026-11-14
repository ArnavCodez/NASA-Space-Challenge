export type Target = {
  name: string
  ra: number
  dec: number
  ra0?: number
  dec0?: number
  pmra?: number
  pmdec?: number
  moved?: number
  epoch?: number
  note?: string
  det?: string
  fov?: number
  source?: string
}

export type Epoch = {
  id: number
  label: string
  mjd_min: number
  mjd_max: number
  n: Record<string, number>
}

export type ManifestFrame = {
  id: string
  obs_id: string
  det: string
  mjd: number
  release: string
  epoch: number
  uri: string
}

export type Manifest = {
  ra: number
  dec: number
  queried_at: string
  cached: boolean
  frames: ManifestFrame[]
  epochs: Epoch[]
  counts: Record<string, number>
}

export type FrameMeta = {
  id: string
  det: string
  epoch: number
  mjd: number
  mjd_min?: number
  mjd_max?: number
  date: string
  wave: number
  bw?: number
  wave_min?: number
  wave_max?: number
  n_coadd: number
  noise?: number
  bkg?: number
  vmin: number
  vmax: number
  label?: string
  obs_id?: string
  release?: string
  ref?: number
  flags?: Record<string, number>
}

export type StackMeta = {
  ra: number
  dec: number
  fov: number
  scale: number
  det: string
  view: string
  failed: number
  total: number
  offset: number
  n: number
  nx: number
  ny: number
  frames: FrameMeta[]
}

export type Stack = {
  meta: StackMeta
  images: Float32Array
  masks: Uint8Array
}

export type View = 'epoch' | 'diff' | 'raw' | 'sub'

export type SpectrumPoint = {
  id: string
  det: string
  epoch: number
  mjd: number
  flux: number
  err: number
  wave: number
  bw: number
  flags: ('saturated' | 'artifact' | 'partial')[]
}

export type Spectrum = {
  ra: number
  dec: number
  unit: string
  aperture: number
  epochs: Epoch[]
  total: number
  failed: number
  points: SpectrumPoint[]
}

export type MotionEpoch = {
  epoch: number
  label: string
  mjd: number
  n_coadd: number
  wave: number
  expected: [number, number]
  east?: number
  north?: number
  err?: [number, number]
  method?: 'fit' | 'core'
}

export type MotionFit = {
  det: string
  fov: number
  scale: number
  catalog: { pmra: number; pmdec: number }
  epochs: MotionEpoch[]
  fit: { pmra: number; pmdec: number; pmra_err: number; pmdec_err: number; span: number } | null
}

export type FrameQuery = {
  ra: number
  dec: number
  det: string
  view: View
  fov: number
  ref: number
  sort?: 'time' | 'wave'
  offset?: number
}

export type GaiaStar = {
  id: string
  ra: number
  dec: number
  mag: number
  pmra: number
  pmdec: number
}

export type NeossatRecord = {
  obs_id: string
  target: string
  cadc_url: string
}

async function fail(r: Response): Promise<never> {
  const body = await r.json().catch(() => null)
  throw new Error(body?.detail ?? `${r.status} ${r.statusText}`)
}

async function json<T>(url: string, signal?: AbortSignal): Promise<T> {
  const r = await fetch(url, { signal })
  if (!r.ok) await fail(r)
  return r.json()
}

export const getTargets = () => json<Target[]>('/api/targets')

export const resolve = (q: string) => json<Target>(`/api/resolve?q=${encodeURIComponent(q)}`)

export const search = (ra: number, dec: number, signal?: AbortSignal) =>
  json<Manifest>(`/api/search?ra=${ra}&dec=${dec}`, signal)

export async function getFrames(q: FrameQuery, signal?: AbortSignal): Promise<Stack> {
  const params = new URLSearchParams(Object.entries(q).map(([k, v]) => [k, String(v)]))
  const r = await fetch(`/api/frames?${params}`, { signal })
  if (!r.ok) await fail(r)
  return decode(await r.arrayBuffer())
}

const pm = (t: Target) => `pmra=${t.pmra ?? 0}&pmdec=${t.pmdec ?? 0}`

// null means nobody has measured this spot yet (only asked when cachedOnly is set)
export async function getSpectrum(t: Target, cachedOnly: boolean, signal?: AbortSignal): Promise<Spectrum | null> {
  const r = await fetch(`/api/spectrum?ra=${t.ra}&dec=${t.dec}&${pm(t)}${cachedOnly ? '&cached=true' : ''}`, { signal })
  if (r.status === 204) return null
  if (!r.ok) await fail(r)
  return r.json()
}

export const getMotion = (t: Target, det: string, fov: number, signal?: AbortSignal) =>
  json<MotionFit>(`/api/motion?ra=${t.ra}&dec=${t.dec}&det=${det}&fov=${fov}&${pm(t)}`, signal)

export const getGaiaStars = (ra: number, dec: number, fov: number, signal?: AbortSignal) =>
  json<GaiaStar[]>(`/api/gaia?ra=${ra}&dec=${dec}&fov=${fov}`, signal)

export const getNeossat = (ra: number, dec: number, fov: number, signal?: AbortSignal) =>
  json<NeossatRecord[]>(`/api/neossat?ra=${ra}&dec=${dec}&fov=${fov}`, signal)

// see backend/app/wire.py for the layout
export function decode(buf: ArrayBuffer): Stack {
  const magic = new TextDecoder().decode(new Uint8Array(buf, 0, 4))
  if (magic !== 'SPXF') throw new Error('unexpected response from /api/frames')
  const size = new DataView(buf).getUint32(4, true)
  const meta: StackMeta = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 8, size)))
  const count = meta.n * meta.ny * meta.nx
  return {
    meta,
    images: new Float32Array(buf, 8 + size, count),
    masks: new Uint8Array(buf, 8 + size + count * 4, count),
  }
}

export const irsaUrl = (uri: string) => `https://irsa.ipac.caltech.edu/${uri}`
