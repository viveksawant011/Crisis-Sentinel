import scanMock from './mock/scan.json'
import scanCleanMock from './mock/scan_clean.json'

const API_BASE = 'http://localhost:8080'
const USE_MOCK = false

async function fetchScanMock(query) {
  await new Promise((resolve) => setTimeout(resolve, 2000))
  const q = query.toLowerCase()
  if (q.includes('error')) {
    throw new Error('Could not reach the backend. Is the server running?')
  }
  if (q.includes('poland')) {
    return scanCleanMock
  }
  return scanMock
}

async function post(path, body) {
  let res
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new Error(`Could not reach the backend at ${API_BASE}. Is the server running?`)
  }

  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Server error (${res.status})`)
  }
  return res.json()
}

export async function fetchScan(query) {
  if (USE_MOCK) return fetchScanMock(query)
  return post('/api/disruption/scan', { query })
}

export async function approveReroute(poId, altSupplierId) {
  if (USE_MOCK) {
    await new Promise((resolve) => setTimeout(resolve, 1000))
    return { success: true, po_id: poId, new_supplier: altSupplierId, status: 'rerouted' }
  }
  return post('/api/mitigation/execute', { po_id: poId, alt_supplier_id: altSupplierId })
}

export async function resetDemo() {
  if (USE_MOCK) return { success: true }
  return post('/api/demo/reset')
}