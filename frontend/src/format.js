const compact = new Intl.NumberFormat('en-IE', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 2,
})
const full = new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 })
const integer = new Intl.NumberFormat('en-IE')

export const eurCompact = (v) => (v == null ? '–' : compact.format(v))
export const eurFull = (v) => (v == null ? '–' : full.format(v))
export const int = (v) => (v == null ? '–' : integer.format(v))
export const days = (v) => (v == null ? '–' : `${Number(v).toFixed(1)} d`)

export function domain(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

export function timeAgo(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' })
}

export const SEVERITY_TONE = { critical: 'danger', high: 'danger', medium: 'warning', low: 'info', unknown: 'neutral' }

export function runwayTone(d) {
  if (d == null) return 'neutral'
  if (d < 3) return 'danger'
  if (d < 7) return 'warning'
  return 'success'
}
