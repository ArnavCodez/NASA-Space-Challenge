import { irsaUrl, type FrameMeta, type Manifest } from '../api'
import { day, utc } from '../format'

export default function FrameInfo({ frame, manifest }: { frame?: FrameMeta; manifest: Manifest | null }) {
  if (!frame) return null
  const stacked = frame.mjd_min !== undefined
  const file = manifest?.frames.find((f) => f.id === frame.id)

  return (
    <dl className="info">
      {stacked ? (
        <>
          <dt>Visit</dt>
          <dd>{frame.label}</dd>
          <dt>Dates</dt>
          <dd>
            {day(frame.mjd_min!)} → {day(frame.mjd_max!)}
          </dd>
          <dt>Stacked</dt>
          <dd>{frame.n_coadd} exposures</dd>
          <dt>Wavelength</dt>
          <dd>
            {frame.wave_min?.toFixed(2)}–{frame.wave_max?.toFixed(2)} µm
          </dd>
        </>
      ) : (
        <>
          <dt>Taken</dt>
          <dd>{utc(frame.mjd)}</dd>
          <dt>MJD</dt>
          <dd>{frame.mjd.toFixed(4)}</dd>
          <dt>Wavelength</dt>
          <dd>
            {frame.wave.toFixed(3)} ± {((frame.bw ?? 0) / 2).toFixed(3)} µm
          </dd>
          <dt>Exposure</dt>
          <dd>
            {file ? (
              <a href={irsaUrl(file.uri)} target="_blank" rel="noreferrer">
                {frame.obs_id}
              </a>
            ) : (
              frame.obs_id
            )}{' '}
            <small>{frame.release}</small>
          </dd>
          {frame.flags && Object.keys(frame.flags).length > 0 && (
            <>
              <dt>Flags</dt>
              <dd className="flags">
                {Object.entries(frame.flags)
                  .sort((a, b) => b[1] - a[1])
                  .slice(0, 6)
                  .map(([k, v]) => (
                    <span key={k}>
                      {k.toLowerCase()} {v}
                    </span>
                  ))}
              </dd>
            </>
          )}
        </>
      )}
      <dt>Noise</dt>
      <dd>{frame.noise !== undefined ? `${(frame.noise * 1000).toFixed(1)} kJy/sr` : '–'}</dd>
      {frame.wave_warn && (
        <div
          style={{
            gridColumn: '1 / -1',
            background: 'rgba(255, 122, 107, 0.15)',
            border: '1px solid var(--bad)',
            borderRadius: '4px',
            padding: '6px 8px',
            fontSize: '0.8rem',
            color: 'var(--bad)',
            marginTop: '4px',
          }}
        >
          ⚠️ <strong>Color Warning:</strong> {frame.wave_warn}
        </div>
      )}
    </dl>
  )
}
