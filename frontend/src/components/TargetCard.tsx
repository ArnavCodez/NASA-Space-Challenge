import type { NeossatRecord, Target } from '../api'
import { dms, hms } from '../format'

export default function TargetCard({ target, neossat = [] }: { target: Target; neossat?: NeossatRecord[] }) {
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
      {neossat.length > 0 && (
        <p className="neossat-badge">
          🇨🇦 <b>NEOSSat (CSA):</b> {neossat.length} CADC observation{neossat.length > 1 ? 's' : ''} in field.{' '}
          <a href={neossat[0].cadc_url} target="_blank" rel="noreferrer">
            CADC Archive ↗
          </a>
        </p>
      )}
    </div>
  )
}
