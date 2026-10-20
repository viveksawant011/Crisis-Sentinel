import { useState } from 'react'
import { approveReroute } from '../api'

const euro = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
})

function ActionCard({ action }) {
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState('')

  const canApprove =
    action.action_type === 'reroute_supplier' &&
    action.po_id &&
    action.target_supplier_id

  async function handleApprove() {
    setStatus('loading')
    setError('')
    try {
      await approveReroute(action.po_id, action.target_supplier_id)
      setStatus('approved')
    } catch (err) {
      setError(err.message)
      setStatus('error')
    }
  }

  return (
    <div className="action">
      <div className="action-badge">{action.priority}</div>
      <div className="action-body">
        <h3 className="action-title">{action.title}</h3>
        <div className="action-meta">
          <span>{action.target_plant}</span>
          <span>{action.target_material}</span>
          <span>{action.action_type.replace('_', ' ')}</span>
        </div>
        <p className="action-rationale">{action.rationale}</p>
        {status === 'error' && <p className="action-error">{error}</p>}
      </div>
      <div className="action-cost">
        <div className="action-cost-value">{euro.format(action.estimated_cost_eur)}</div>
        <div className="action-cost-label">Est. cost</div>
        {canApprove && (
          <button
            className={`approve-button ${status === 'approved' ? 'done' : ''}`}
            onClick={handleApprove}
            disabled={status === 'loading' || status === 'approved'}
          >
            {status === 'loading' && 'Approving...'}
            {status === 'approved' && 'Approved ✓'}
            {(status === 'idle' || status === 'error') && 'Approve reroute'}
          </button>
        )}
      </div>
    </div>
  )
}

export default ActionCard