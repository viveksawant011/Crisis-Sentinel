import scanMock from './mock/scan.json'
import scanCleanMock from './mock/scan_clean.json'

export async function fetchScan(query) {
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

export async function approveReroute(poId, altSupplierId) {
  await new Promise((resolve) => setTimeout(resolve, 1000))
  return { success: true, po_id: poId, new_supplier: altSupplierId, status: 'rerouted' }
}


import scanMock from './mock/scan.json'
import scanCleanMock from './mock/scan_clean.json'

const API_BASE = 'http://localhost:8000'
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

export async function fetchScan(query) {
  if (USE_MOCK) return fetchScanMock(query)

  let res
  try {
    res = await fetch(`${API_BASE}/api/disruption/scan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    })
  } catch {
    throw new Error('Could not reach the backend. Is the server running on port 8000?')
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Server error (${res.status})`)
  }
  return res.json()
}

export async function approveReroute(poId, altSupplierId) {
  await new Promise((resolve) => setTimeout(resolve, 1000))
  return { success: true, po_id: poId, new_supplier: altSupplierId, status: 'rerouted' }
}