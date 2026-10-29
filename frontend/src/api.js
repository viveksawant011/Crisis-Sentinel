// Thin client for the CrisisSentinel API. Every request goes through here,
// so the base URL is configured in exactly one place.
const BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message, status, detail) {
    super(message)
    this.status = status
    this.detail = detail
  }
}

function describe(detail, fallback) {
  if (!detail) return fallback
  if (typeof detail === 'string') return detail
  if (detail.results?.length) {
    const first = detail.results.find((r) => r.error)
    return first ? first.error : detail.message || fallback
  }
  return detail.message || fallback
}

async function request(path, options = {}) {
  let res
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
  } catch {
    throw new ApiError('Cannot reach the CrisisSentinel API. Is the backend running?', 0)
  }
  if (!res.ok) {
    let detail
    try {
      detail = (await res.json()).detail
    } catch {
      detail = undefined
    }
    throw new ApiError(describe(detail, `Request failed (HTTP ${res.status})`), res.status, detail)
  }
  return res.json()
}

const post = (path, body) => request(path, { method: 'POST', body: JSON.stringify(body) })

export const getHealth = () => request('/api/health')
export const getRecordedScenario = (name) => request(`/api/cache/scenario/${name}`)
export const runWhatIf = (body) => post('/api/whatif', body)
export const executeMitigation = (body) => post('/api/mitigation/execute', body)
export const reviseMitigation = (body) => post('/api/mitigation/revise', body)
export const resetDemo = () => post('/api/demo/reset', {})

/**
 * Runs a live scan and reports real pipeline progress.
 * Returns a function that cancels the stream.
 */
export function streamScan(query, { onEvent, onResult, onError }) {
  const source = new EventSource(`${BASE}/api/disruption/scan/stream?query=${encodeURIComponent(query)}`)
  let finished = false
  const finish = () => {
    finished = true
    source.close()
  }
  source.onmessage = (msg) => {
    let event
    try {
      event = JSON.parse(msg.data)
    } catch {
      return
    }
    if (event.stage === 'result') {
      finish()
      onResult(event.data)
    } else if (event.stage === 'error') {
      finish()
      onError(new ApiError(event.message || 'The scan failed.', 500))
    } else {
      onEvent(event)
    }
  }
  source.onerror = () => {
    if (finished) return
    finish()
    onError(new ApiError('The connection to the API was lost or rate-limited. Try again, or use a recorded scenario.', 0))
  }
  return finish
}
