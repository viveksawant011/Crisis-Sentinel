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