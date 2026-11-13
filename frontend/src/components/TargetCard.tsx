import type { Target } from '../api'
import { dms, hms } from '../format'

export default function TargetCard({ target }: { target: Target }) {
  const pm = Math.hypot(target.pmra ?? 0, target.pmdec ?? 0)
  const rate = pm >= 1000 ? `${(pm / 1000).toFixed(1)}″` : `${pm.toFixed(0)} mas`

  return (
    <div className="target">
      <h2>{target.name}</h2>
      <p className="coords">
        {hms(target.ra)} {dms(target.dec)}
      </p>
      {(target.moved ?? 0) > 1 && (
        <p className="moved">
          Moves {rate} a year. Centred on its {target.epoch ?? 2026} position, {target.moved!.toFixed(0)}″ from where
          catalogues list it for 2000.
        </p>
      )}
      {target.note && <p className="note">{target.note}</p>}
    </div>
  )
}
