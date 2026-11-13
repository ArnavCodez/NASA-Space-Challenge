import type { MotionFit } from '../api'

const S = 300
const PAD = 34
const TRACK = '#5ae68c'
const MEASURED = '#f2b84b'

const arcsec = (mas: number) => (mas / 1000).toFixed(1)
const signed = (mas: number) => (mas >= 0 ? '+' : '−') + arcsec(Math.abs(mas))

function short(label: string) {
  const [m, y] = label.split(' ')
  return y ? `${m} ’${y.slice(2)}` : label
}

export default function MotionPlot({ data }: { data: MotionFit }) {
  const got = data.epochs.filter((e) => e.east !== undefined && e.north !== undefined)
  const cat = data.catalog
  const moving = Math.hypot(cat.pmra, cat.pmdec) > 100

  let reach = 3
  for (const e of data.epochs) {
    reach = Math.max(reach, Math.abs(e.expected[0]), Math.abs(e.expected[1]))
    if (e.east !== undefined && e.north !== undefined && e.err) {
      reach = Math.max(reach, Math.abs(e.east) + e.err[0], Math.abs(e.north) + e.err[1])
    }
  }
  reach = Math.ceil(reach * 1.15)
  const k = (S / 2 - PAD) / reach
  // east is to the left, same as the image
  const px = (east: number) => S / 2 - east * k
  const py = (north: number) => S / 2 - north * k
  const grid = reach > 12 ? 5 : reach > 5 ? 2 : 1
  const lines: number[] = []
  for (let v = -Math.floor(reach / grid) * grid; v <= reach; v += grid) lines.push(v)

  const first = data.epochs[0]
  const last = data.epochs[data.epochs.length - 1]
  const fit = data.fit

  return (
    <div className="plot">
      <div className="plot-head">
        <h3>Position at each visit</h3>
        <div className="legend static">
          <span>
            <i className="ring" style={{ borderColor: TRACK }} /> catalogue
          </span>
          <span>
            <i style={{ background: MEASURED }} /> measured
          </span>
        </div>
      </div>

      <svg viewBox={`0 0 ${S} ${S}`} className="motion" role="img" aria-label="Measured position of the target at each visit compared with the catalogue track">
        {lines.map((v) => (
          <g key={v}>
            <line className={v === 0 ? 'zero' : 'grid'} x1={PAD} x2={S - PAD} y1={py(v)} y2={py(v)} />
            <line className={v === 0 ? 'zero' : 'grid'} y1={PAD} y2={S - PAD} x1={px(v)} x2={px(v)} />
          </g>
        ))}
        {lines
          .filter((v) => v !== 0)
          .map((v) => (
            <text key={v} className="tick" x={px(v)} y={S - PAD + 14} textAnchor="middle">
              {v}″
            </text>
          ))}
        <text className="axis" x={PAD - 4} y={S / 2 + 4} textAnchor="end">
          E
        </text>
        <text className="axis" x={S / 2} y={PAD - 8} textAnchor="middle">
          N
        </text>
        <rect className="pixel" x={S - PAD - 6.15 * k} y={S - PAD - 6.15 * k} width={6.15 * k} height={6.15 * k} />

        {moving && first && last && (
          <line
            stroke={TRACK}
            strokeWidth={2}
            strokeDasharray="4 4"
            x1={px(first.expected[0])}
            y1={py(first.expected[1])}
            x2={px(last.expected[0])}
            y2={py(last.expected[1])}
          />
        )}
        {data.epochs.map((e) => (
          <circle key={e.epoch} cx={px(e.expected[0])} cy={py(e.expected[1])} r={6} fill="none" stroke={TRACK} strokeWidth={1.5} />
        ))}

        {got.map((e) => {
          const cx = px(e.east!)
          const cy = py(e.north!)
          const [ex, ey] = e.err ?? [0, 0]
          return (
            <g key={e.epoch}>
              <line stroke={MEASURED} strokeWidth={1} x1={cx - ex * k} x2={cx + ex * k} y1={cy} y2={cy} />
              <line stroke={MEASURED} strokeWidth={1} x1={cx} x2={cx} y1={cy - ey * k} y2={cy + ey * k} />
              <circle cx={cx} cy={cy} r={4.5} fill={MEASURED} stroke="var(--panel)" strokeWidth={2} />
              {got.length <= 4 && (
                <text className="point-label" x={cx + 8} y={cy - 7}>
                  {short(e.label)}
                </text>
              )}
            </g>
          )
        })}
      </svg>

      <div className="motion-text">
        {fit ? (
          <>
            <p>
              Measured over {fit.span.toFixed(1)} yr: <b>{signed(fit.pmra)}″/yr</b> east, <b>{signed(fit.pmdec)}″/yr</b> north
              <span className="dim"> (± {arcsec(Math.max(fit.pmra_err, fit.pmdec_err))})</span>
            </p>
            <p className="dim">
              Catalogue: {signed(cat.pmra)}″/yr east, {signed(cat.pmdec)}″/yr north
            </p>
          </>
        ) : (
          <p className="dim">Couldn't pin down the target in enough visits to measure a motion.</p>
        )}
        <p className="hint">
          Centroids from the {data.det} visit stacks. The small square is one SPHEREx pixel (6.15″), so this is sub-pixel
          astrometry: trust it for fast movers, not for anything under about 1″/yr.
          {got.some((e) => e.method === 'core') && ' Saturated core: position taken from the centre of the blanked-out pixels.'}
        </p>
      </div>
    </div>
  )
}
