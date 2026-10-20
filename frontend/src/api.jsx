export async function approveReroute(poId, altSupplierId) {
  await new Promise((resolve) => setTimeout(resolve, 1000))
  return { success: true, po_id: poId, new_supplier: altSupplierId, status: 'rerouted' }
}