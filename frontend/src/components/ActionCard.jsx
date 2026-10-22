const euro = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
})

function ActionCard({ action }) {
  return (
    <div className="action">
      <div className="action-badge">{action.priority}</div>
      <div className="action-body">
        <h3 className="action-title">{action.title}</h3>
        <div className="action-meta">
          <span>{action.target_plant}</span>
          <span>{action.target_material}</span>
          <span>{action.action_type}</span>
        </div>
        <p className="action-rationale">{action.rationale}</p>
      </div>
      <div className="action-cost">
        <div className="action-cost-value">{euro.format(action.estimated_cost_eur)}</div>
        <div className="action-cost-label">Est. cost</div>
      </div>
    </div>
  )
}

export default ActionCard