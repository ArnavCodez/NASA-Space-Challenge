import type { Epoch, View } from '../api'
import type { Cmap, Curve } from '../stretch'

const DETECTORS: [string, string][] = [
  ['D1', '0.75–1.09'],
  ['D2', '1.10–1.62'],
  ['D3', '1.63–2.41'],
  ['D4', '2.42–3.82'],
  ['D5', '3.83–4.41'],
  ['D6', '4.42–5.00'],
]

const VIEWS: [View, string, string][] = [
  ['epoch', 'Epochs', 'One stacked image per visit, months apart. Best for slow movers and brightness changes.'],
  ['diff', 'Difference', 'Each visit minus a reference visit. Movers show up as a dark/light pair.'],
  ['raw', 'Frames', 'Every single exposure in time order. Each one sees the sky at a slightly different wavelength.'],
  ['sub', 'Static removed', 'Single exposures minus the median sky, so anything that changes stands out.'],
]

type Props = {
  view: View
  setView: (v: View) => void
  det: string
  setDet: (d: string) => void
  counts: Record<string, number>
  fov: number
  setFov: (f: number) => void
  epochs: Epoch[]
  refEpoch: number
  setRefEpoch: (e: number) => void
  curve: Curve
  setCurve: (c: Curve) => void
  cmap: Cmap
  setCmap: (c: Cmap) => void
  contrast: number
  setContrast: (c: number) => void
  steady: boolean
  setSteady: (s: boolean) => void
  showFlags: boolean
  setShowFlags: (s: boolean) => void
  smooth: boolean
  setSmooth: (s: boolean) => void
}

export default function Controls(p: Props) {
  const help = VIEWS.find(([v]) => v === p.view)?.[2]

  return (
    <div className="controls">
      <div className="tabs" role="tablist">
        {VIEWS.map(([v, label]) => (
          <button key={v} role="tab" aria-selected={p.view === v} className={p.view === v ? 'on' : ''} onClick={() => p.setView(v)}>
            {label}
          </button>
        ))}
      </div>
      <p className="hint">{help}</p>

      {p.view === 'diff' && p.epochs.length > 1 && (
        <label className="row">
          <span>Reference</span>
          <select value={p.refEpoch} onChange={(e) => p.setRefEpoch(Number(e.target.value))}>
            {p.epochs.map((e) => (
              <option key={e.id} value={e.id}>
                {e.label}
              </option>
            ))}
          </select>
        </label>
      )}

      <fieldset>
        <legend>
          Detector <span className="unit">µm</span>
        </legend>
        <div className="chips">
          {DETECTORS.map(([d, range]) => {
            const n = p.counts[d] ?? 0
            return (
              <button key={d} className={p.det === d ? 'chip on' : 'chip'} disabled={!n} onClick={() => p.setDet(d)}>
                <b>{d}</b>
                <span>{range}</span>
                <small>{n} frames</small>
              </button>
            )
          })}
        </div>
      </fieldset>

      <label className="row">
        <span>Field of view</span>
        <select value={p.fov} onChange={(e) => p.setFov(Number(e.target.value))}>
          {[3, 6, 12, 20].map((f) => (
            <option key={f} value={f}>
              {f} arcmin
            </option>
          ))}
        </select>
      </label>

      <fieldset>
        <legend>Display</legend>
        <label className="row">
          <span>Stretch</span>
          <select value={p.curve} onChange={(e) => p.setCurve(e.target.value as Curve)}>
            <option value="linear">linear</option>
            <option value="asinh">asinh</option>
            <option value="log">log</option>
          </select>
        </label>
        <label className="row">
          <span>Colors</span>
          <select value={p.cmap} onChange={(e) => p.setCmap(e.target.value as Cmap)} disabled={p.view === 'diff'}>
            <option value="inverted">black on white</option>
            <option value="gray">white on black</option>
            <option value="viridis">viridis</option>
          </select>
        </label>
        <label className="row">
          <span>Contrast</span>
          <input
            type="range"
            min={-2}
            max={2}
            step={0.1}
            value={-Math.log2(p.contrast)}
            onChange={(e) => p.setContrast(2 ** -Number(e.target.value))}
          />
        </label>
        <label className="check">
          <input type="checkbox" checked={p.steady} onChange={(e) => p.setSteady(e.target.checked)} />
          Same stretch for every frame
        </label>
        <label className="check">
          <input type="checkbox" checked={p.showFlags} onChange={(e) => p.setShowFlags(e.target.checked)} />
          Tint flagged pixels <i className="key sat" /> saturated <i className="key art" /> artifact <i className="key tr" /> transient
        </label>
        <label className="check">
          <input type="checkbox" checked={p.smooth} onChange={(e) => p.setSmooth(e.target.checked)} />
          Smooth pixels
        </label>
      </fieldset>
    </div>
  )
}
