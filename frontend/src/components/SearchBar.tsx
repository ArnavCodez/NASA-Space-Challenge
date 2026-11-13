import { useState } from 'react'
import { resolve, type Target } from '../api'

export default function SearchBar({ onTarget }: { onTarget: (t: Target) => void }) {
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!q.trim()) return
    setBusy(true)
    setError('')
    try {
      onTarget(await resolve(q.trim()))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="search" onSubmit={submit}>
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Star name or coordinates, e.g. TRAPPIST-1 or 08h55m10.8s -07d14m42s"
        aria-label="Target name or coordinates"
        spellCheck={false}
      />
      <button type="submit" disabled={busy}>
        {busy ? 'Looking up…' : 'Go'}
      </button>
      {error && <p className="error">{error}</p>}
    </form>
  )
}
