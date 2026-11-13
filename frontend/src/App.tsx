import { useCallback, useEffect, useMemo, useState } from 'react'
import { getFrames, getTargets, search, type Manifest, type Stack, type Target, type View } from './api'
import Controls from './components/Controls'
import FrameInfo from './components/FrameInfo'
import Player from './components/Player'
import SearchBar from './components/SearchBar'
import TargetCard from './components/TargetCard'
import Viewer from './components/Viewer'
import { dms, hms } from './format'
import { limitsFor, type Cmap, type Curve } from './stretch'
import { readUrl, toQuery, writeUrl } from './url'

const start = readUrl()

// earliest visit with a decent number of exposures: longest baseline without a noisy reference
function defaultRef(m: Manifest, det: string) {
  const counts = m.epochs.map((e) => e.n[det] ?? 0)
  const enough = Math.max(...counts, 0) / 2
  return m.epochs.find((e) => (e.n[det] ?? 0) >= enough)?.id ?? 0
}

export default function App({ embed = false }: { embed?: boolean }) {
  const [presets, setPresets] = useState<Target[]>([])
  const [target, setTarget] = useState<Target | null>(
    start.ra !== undefined && start.dec !== undefined
      ? { name: start.name ?? `${hms(start.ra)} ${dms(start.dec)}`, ra: start.ra, dec: start.dec }
      : null,
  )
  const [det, setDet] = useState(start.det ?? 'D6')
  const [view, setView] = useState<View>(start.view ?? 'epoch')
  const [fov, setFov] = useState(start.fov ?? 3)
  const [refEpoch, setRefEpoch] = useState(start.ref ?? 0)

  const [manifest, setManifest] = useState<Manifest | null>(null)
  const [stack, setStack] = useState<Stack | null>(null)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')

  const [index, setIndex] = useState(0)
  const [playing, setPlaying] = useState(true)
  const [fps, setFps] = useState(start.fps ?? 2)
  const [curve, setCurve] = useState<Curve>(start.curve ?? 'asinh')
  const [cmap, setCmap] = useState<Cmap>(start.cmap ?? 'inverted')
  const [contrast, setContrast] = useState(1)
  const [steady, setSteady] = useState(true)
  const [showFlags, setShowFlags] = useState(false)
  const [smooth, setSmooth] = useState(false)
  const [copied, setCopied] = useState('')

  const pick = useCallback((t: Target) => {
    setTarget(t)
    if (t.det) setDet(t.det)
    if (t.fov) setFov(t.fov)
    setView('epoch')
    setRefEpoch(0)
    setIndex(0)
    setPlaying(true)
  }, [])

  useEffect(() => {
    getTargets()
      .then((list) => {
        setPresets(list)
        if (!target && list.length) pick(list[0])
        else if (target) {
          // came in from a link; pick up the preset's notes if it is one
          const hit = list.find((p) => Math.abs(p.ra - target.ra) < 1e-4 && Math.abs(p.dec - target.dec) < 1e-4)
          if (hit) setTarget((t) => ({ ...hit, ...t, note: hit.note, moved: hit.moved }))
        }
      })
      .catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (!target) return
    const ctl = new AbortController()
    setManifest(null)
    setStack(null)
    setError('')
    setStatus('Searching the SPHEREx archive. A spot nobody has asked for yet can take a minute.')
    search(target.ra, target.dec, ctl.signal)
      .then((m) => {
        setManifest(m)
        if (!m.frames.length) {
          setStatus('')
          setError('SPHEREx has not observed this position yet.')
        }
      })
      .catch((e) => {
        if (ctl.signal.aborted) return
        setStatus('')
        setError(e.message)
      })
    return () => ctl.abort()
  }, [target?.ra, target?.dec])

  const [refFromUrl, setRefFromUrl] = useState(start.ref !== undefined)
  useEffect(() => {
    if (!manifest) return
    if (refFromUrl) setRefFromUrl(false)
    else setRefEpoch(defaultRef(manifest, det))
  }, [manifest, det])

  useEffect(() => {
    if (!target || !manifest || !manifest.frames.length) return
    const n = manifest.counts[det] ?? 0
    if (!n) {
      const fallback = Object.keys(manifest.counts)[0]
      if (fallback) setDet(fallback)
      return
    }
    const ctl = new AbortController()
    setError('')
    setStatus(`Fetching ${det} exposures from IRSA (${n} cover this spot). First load of a view takes 10–60 s.`)
    getFrames({ ra: target.ra, dec: target.dec, det, view, fov, ref: refEpoch }, ctl.signal)
      .then((s) => {
        setStack(s)
        setIndex((i) => Math.min(i, Math.max(s.meta.n - 1, 0)))
        setStatus('')
        if (s.meta.failed) setError(`${s.meta.failed} exposures could not be read and were skipped.`)
      })
      .catch((e) => {
        if (ctl.signal.aborted) return
        setStatus('')
        setError(e.message)
      })
    return () => ctl.abort()
  }, [manifest, det, view, fov, refEpoch])

  useEffect(() => {
    setSteady(view !== 'raw')
    setFps((f) => (view === 'raw' || view === 'sub' ? Math.max(f, 6) : Math.min(f, 3)))
  }, [view])

  const query = useMemo(
    () => (target ? { name: target.name, ra: target.ra, dec: target.dec, det, view, fov, ref: view === 'diff' ? refEpoch : undefined } : {}),
    [target, det, view, fov, refEpoch],
  )

  useEffect(() => {
    if (target && !embed) writeUrl(query)
  }, [query, target, embed])

  const frame = stack?.meta.frames[index]
  const limits = useMemo(
    () => (stack && stack.meta.n ? limitsFor(stack, index, steady, contrast, view === 'diff') : { lo: 0, hi: 1 }),
    [stack, index, steady, contrast, view],
  )

  const ticks = useMemo(() => {
    const frames = stack?.meta.frames ?? []
    if (view !== 'raw' && view !== 'sub') return []
    return frames.flatMap((f, i) => (i > 0 && f.epoch !== frames[i - 1].epoch ? [i] : []))
  }, [stack, view])

  const frameLabel = frame ? (frame.label ?? frame.date) + (view === 'diff' ? ` − ${manifest?.epochs.find((e) => e.id === frame.ref)?.label ?? ''}` : '') : ''

  async function copy(kind: 'link' | 'embed') {
    const base = `${location.origin}${kind === 'embed' ? '/embed' : '/'}?${toQuery(query)}`
    const text = kind === 'embed' ? `<iframe src="${base}" width="480" height="560" style="border:0"></iframe>` : base
    await navigator.clipboard.writeText(text)
    setCopied(kind)
    setTimeout(() => setCopied(''), 1500)
  }

  const stage = (
    <section className="stage">
      <div className="frame-box">
        {stack && stack.meta.n > 0 ? (
          <Viewer
            stack={stack}
            index={index}
            limits={limits}
            curve={curve}
            cmap={view === 'diff' ? 'diverging' : cmap}
            showFlags={showFlags}
            smooth={smooth}
          />
        ) : (
          <div className="empty">{status || error || 'Pick a target to start.'}</div>
        )}
        {stack && status && <div className="busy">{status}</div>}
      </div>
      <Player
        count={stack?.meta.n ?? 0}
        index={index}
        setIndex={setIndex}
        playing={playing}
        setPlaying={setPlaying}
        fps={fps}
        setFps={setFps}
        ticks={ticks}
        label={frameLabel}
      />
    </section>
  )

  if (embed) {
    return (
      <div className="embed">
        {stage}
        <p className="embed-credit">
          {target?.name} · SPHEREx {det} ·{' '}
          <a href={`/?${toQuery(query)}`} target="_blank" rel="noreferrer">
            open in SPHEREx Blink
          </a>
        </p>
      </div>
    )
  }

  return (
    <div className="app">
      <header>
        <div className="brand">
          <h1>SPHEREx Blink</h1>
          <p>Flip through NASA SPHEREx infrared images of any spot on the sky and watch what moves.</p>
        </div>
        <SearchBar onTarget={pick} />
      </header>

      <nav className="presets" aria-label="Example targets">
        {presets.map((p) => (
          <button key={p.name} className={target?.name === p.name ? 'on' : ''} onClick={() => pick(p)}>
            {p.name}
          </button>
        ))}
      </nav>

      <main>
        {stage}

        <aside>
          {target && <TargetCard target={target} />}

          <Controls
            view={view}
            setView={(v) => {
              setView(v)
              setIndex(0)
            }}
            det={det}
            setDet={setDet}
            counts={manifest?.counts ?? {}}
            fov={fov}
            setFov={setFov}
            epochs={manifest?.epochs ?? []}
            refEpoch={refEpoch}
            setRefEpoch={setRefEpoch}
            curve={curve}
            setCurve={setCurve}
            cmap={cmap}
            setCmap={setCmap}
            contrast={contrast}
            setContrast={setContrast}
            steady={steady}
            setSteady={setSteady}
            showFlags={showFlags}
            setShowFlags={setShowFlags}
            smooth={smooth}
            setSmooth={setSmooth}
          />

          <FrameInfo frame={frame} manifest={manifest} />

          <div className="share">
            <button onClick={() => copy('link')}>{copied === 'link' ? 'Copied' : 'Copy link'}</button>
            <button onClick={() => copy('embed')}>{copied === 'embed' ? 'Copied' : 'Copy embed code'}</button>
          </div>
          {error && stack && <p className="error">{error}</p>}
        </aside>
      </main>

      <footer>
        Images: NASA SPHEREx Level 2 spectral images (DR1 + weekly quick releases) from NASA/IPAC IRSA. Names resolved with
        CDS Sesame. Built for NASA Space Apps 2026 by team Skill-Issue.
      </footer>
    </div>
  )
}
