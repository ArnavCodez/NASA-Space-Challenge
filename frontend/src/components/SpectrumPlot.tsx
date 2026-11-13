import { useMemo, useState, type MouseEvent } from 'react'
import type { Epoch, Spectrum, SpectrumPoint } from '../api'
import { day } from '../format'

const W = 640
const H = 300
const PAD = { l: 50, r: 12, t: 24, b: 36 }
const X0 = 0.7
const X1 = 5.05

const BANDS: [string, number, number][] = [
  ['D1', 0.75, 1.09],
  ['D2', 1.1, 1.62],
  ['D3', 1.63, 2.41],
  ['D4', 2.42, 3.82],
  ['D5', 3.83, 4.41],
  ['D6', 4.42, 5.0],
]

// three visits get distinct hues; more than that is a time series, so one hue dark (old) to light (new)
const FEW = ['#3987e5', '#d95926', '#199e70']
const RAMP = ['#184f95', '#1c5cab', '#256abf', '#2a78d6', '#3987e5', '#5598e7', '#6da7ec', '#86b6ef', '#9ec5f4', '#b7d3f6']

export function epochColors(epochs: Epoch[]) {
  if (epochs.length <= FEW.length) return new Map(epochs.map((e, i) => [e.id, FEW[i]]))
  const step = (RAMP.length - 1) / (epochs.length - 1)
  return new Map(epochs.map((e, i) => [e.id, RAMP[Math.round(i * step)]]))
}

function quantile(sorted: number[], q: number) {
  if (!sorted.length) return 0
  return sorted[Math.min(sorted.length - 1, Math.max(0, Math.round(q * (sorted.length - 1))))]
}

function niceStep(span: number, target = 6) {
  const raw = span / target
  const mag = 10 ** Math.floor(Math.log10(raw))
  return [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw
}

function toCsv(s: Spectrum) {
  const head = 'wavelength_um,bandwidth_um,flux_mjy,err_mjy,detector,mjd,visit,flags,frame'
  const label = new Map(s.epochs.map((e) => [e.id, e.label]))
  const rows = s.points.map((p) =>
    [p.wave, p.bw, p.flux, p.err, p.det, p.mjd, `"${label.get(p.epoch) ?? p.epoch}"`, p.flags.join('|'), p.id].join(','),
  )
  return [head, ...rows].join('\n')
}

// a bad pixel or two in the aperture is already scaled out; saturation and ghosts are not
const suspect = (p: SpectrumPoint) => p.flags.some((f) => f !== 'partial')

type Props = { spectrum: Spectrum; name: string }

export default function SpectrumPlot({ spectrum, name }: Props) {
  const [showFlagged, setShowFlagged] = useState(false)
  const [only, setOnly] = useState<number | null>(null)
  const [hover, setHover] = useState<SpectrumPoint | null>(null)

  const epochs = useMemo(() => {
    const seen = new Set(spectrum.points.map((p) => p.epoch))
    return spectrum.epochs.filter((e) => seen.has(e.id))
  }, [spectrum])
  const colors = useMemo(() => epochColors(epochs), [epochs])

  const shown = spectrum.points.filter((p) => showFlagged || !suspect(p))
  const hidden = spectrum.points.length - shown.length
  const skipped = spectrum.total - spectrum.failed - spectrum.points.length

  const [lo, hi] = useMemo(() => {
    const vals = shown.flatMap((p) => [p.flux - p.err, p.flux + p.err]).sort((a, b) => a - b)
    const a = Math.min(0, quantile(vals, 0.01))
    const b = Math.max(quantile(vals, 0.99), a + 1e-3)
    const pad = (b - a) * 0.08
    return [a - pad, b + pad]
  }, [shown])

  const x = (w: number) => PAD.l + ((w - X0) / (X1 - X0)) * (W - PAD.l - PAD.r)
  const y = (f: number) => H - PAD.b - ((f - lo) / (hi - lo)) * (H - PAD.t - PAD.b)
  const step = niceStep(hi - lo)
  const yTicks: number[] = []
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) yTicks.push(+v.toFixed(6))
  const offScale = shown.filter((p) => p.flux < lo || p.flux > hi).length

  // draw the highlighted visit last so it sits on top
  const order = only === null ? shown : [...shown.filter((p) => p.epoch !== only), ...shown.filter((p) => p.epoch === only)]

  function onMove(e: MouseEvent<SVGSVGElement>) {
    const box = e.currentTarget.getBoundingClientRect()
    const mx = ((e.clientX - box.left) / box.width) * W
    const my = ((e.clientY - box.top) / box.height) * H
    let best: SpectrumPoint | null = null
    let dist = 14
    for (const p of shown) {
      if (only !== null && p.epoch !== only) continue
      const d = Math.hypot(x(p.wave) - mx, y(p.flux) - my)
      if (d < dist) {
        dist = d
        best = p
      }
    }
    setHover(best)
  }

  const download = () => {
    const url = URL.createObjectURL(new Blob([toCsv(spectrum)], { type: 'text/csv' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `${name.replace(/\W+/g, '_')}_spherex_spectrum.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="plot">
      <div className="plot-head">
        <h3>Spectrum from every exposure</h3>
        <div className="legend">
          {epochs.map((e) => (
            <button
              key={e.id}
              className={only === e.id ? 'on' : only !== null ? 'off' : ''}
              onClick={() => setOnly(only === e.id ? null : e.id)}
              title="Show only this visit"
            >
              <i style={{ background: colors.get(e.id) }} />
              {e.label}
            </button>
          ))}
        </div>
      </div>

      <div className="plot-box">
        <svg viewBox={`0 0 ${W} ${H}`} onMouseMove={onMove} onMouseLeave={() => setHover(null)} role="img"
          aria-label={`Flux against wavelength for ${name}, ${shown.length} measurements`}>
          <defs>
            <clipPath id="spec-clip">
              <rect x={PAD.l} y={PAD.t} width={W - PAD.l - PAD.r} height={H - PAD.t - PAD.b} />
            </clipPath>
          </defs>

          {BANDS.map(([d, a, b], i) => (
            <g key={d}>
              {i % 2 === 0 && <rect className="band" x={x(a)} y={PAD.t} width={x(b) - x(a)} height={H - PAD.t - PAD.b} />}
              <text className="band-label" x={(x(a) + x(b)) / 2} y={PAD.t - 8}>
                {d}
              </text>
            </g>
          ))}

          {yTicks.map((v) => (
            <g key={v}>
              <line className={v === 0 ? 'zero' : 'grid'} x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)} />
              <text className="tick" x={PAD.l - 6} y={y(v) + 4} textAnchor="end">
                {+v.toPrecision(3)}
              </text>
            </g>
          ))}
          {[1, 2, 3, 4, 5].map((w) => (
            <text key={w} className="tick" x={x(w)} y={H - PAD.b + 16} textAnchor="middle">
              {w}
            </text>
          ))}
          <text className="axis" x={(PAD.l + W - PAD.r) / 2} y={H - 4} textAnchor="middle">
            wavelength (µm)
          </text>
          <text className="axis" transform={`translate(12 ${(PAD.t + H - PAD.b) / 2}) rotate(-90)`} textAnchor="middle">
            flux ({spectrum.unit})
          </text>

          <g clipPath="url(#spec-clip)">
            {order.map((p) => {
              const faded = only !== null && p.epoch !== only
              const color = faded ? 'var(--line)' : colors.get(p.epoch)
              const flagged = suspect(p)
              return (
                <g key={p.id} opacity={faded ? 0.6 : 1}>
                  <line stroke={color} strokeWidth={1} x1={x(p.wave)} x2={x(p.wave)} y1={y(p.flux - p.err)} y2={y(p.flux + p.err)} />
                  <circle
                    cx={x(p.wave)}
                    cy={y(p.flux)}
                    r={4}
                    fill={flagged ? 'var(--panel)' : color}
                    stroke={flagged ? color : 'var(--panel)'}
                    strokeWidth={flagged ? 1.5 : 2}
                  />
                </g>
              )
            })}
            {hover && <circle className="hover-ring" cx={x(hover.wave)} cy={y(hover.flux)} r={8} />}
          </g>
        </svg>

        {hover && (
          <div
            className="tip"
            style={{
              left: `${(x(hover.wave) / W) * 100}%`,
              top: `${(y(hover.flux) / H) * 100}%`,
              transform: `translate(${x(hover.wave) > W * 0.65 ? 'calc(-100% - 12px)' : '12px'}, -50%)`,
            }}
          >
            <b>
              {hover.flux.toFixed(3)} ± {hover.err.toFixed(3)} mJy
            </b>
            <span>
              {hover.wave.toFixed(3)} µm · {hover.det}
            </span>
            <span>{day(hover.mjd)}</span>
            {hover.flags.length > 0 && <span className="warn">{hover.flags.join(', ')}</span>}
          </div>
        )}
      </div>

      <div className="plot-foot">
        <label className="check">
          <input type="checkbox" checked={showFlagged} onChange={(e) => setShowFlagged(e.target.checked)} />
          Show flagged points{hidden > 0 && !showFlagged ? ` (${hidden} hidden)` : ''}
        </label>
        {offScale > 0 && <span>{offScale} off scale</span>}
        {skipped > 0 && (
          <span title="saturated or blanked at the target, or too close to the detector edge">
            {skipped} of {spectrum.total} exposures unusable
          </span>
        )}
        <button className="link" onClick={download}>
          Download CSV
        </button>
      </div>
      <p className="hint">
        SPHEREx sees each spot through a different part of its filter on every exposure, so one visit adds up to a full
        0.75–5 µm spectrum. Fluxes are summed in a {spectrum.aperture}″ radius around the target (no aperture correction),
        so a neighbouring star adds its light too. Visits that disagree at the same wavelength mean the source changed.
      </p>
    </div>
  )
}
