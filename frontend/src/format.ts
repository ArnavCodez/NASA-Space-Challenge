const pad = (n: number, w = 2) => String(n).padStart(w, '0')

export function hms(ra: number) {
  const h = (((ra % 360) + 360) % 360) / 15
  const hh = Math.floor(h)
  const m = (h - hh) * 60
  const mm = Math.floor(m)
  const ss = (m - mm) * 60
  return `${pad(hh)}h${pad(mm)}m${ss.toFixed(2).padStart(5, '0')}s`
}

export function dms(dec: number) {
  const sign = dec < 0 ? '-' : '+'
  const d = Math.abs(dec)
  const dd = Math.floor(d)
  const m = (d - dd) * 60
  const mm = Math.floor(m)
  const ss = (m - mm) * 60
  return `${sign}${pad(dd)}°${pad(mm)}'${ss.toFixed(1).padStart(4, '0')}"`
}

export function mjdToDate(mjd: number) {
  return new Date((mjd - 40587) * 86400000)
}

export function utc(mjd: number) {
  return mjdToDate(mjd).toISOString().slice(0, 16).replace('T', ' ') + ' UTC'
}

export function day(mjd: number) {
  return mjdToDate(mjd).toISOString().slice(0, 10)
}
