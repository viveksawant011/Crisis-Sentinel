import { eurFull } from '../format.js'
import { Badge, Card, Spinner } from './ui.jsx'

const TYPE_LABEL = {
  reroute_supplier: 'Reroute',
  expedite: 'Expedite',
  buffer_stock: 'Buffer stock',
  verify_capacity: 'Verify capacity',
}

export default function ResponsePlan({ brief, onApprove, approving, approval, reroutable }) {
  const approved = new Set((approval?.results || []).filter((r) => r.success).map((r) => r.po_id))
  const nothingLeft = reroutable.length > 0 && reroutable.every((a) => approved.has(a.po_id))
  const fromModel = brief.brief_source === 'nemotron'

  return (
    <Card
      title="Recommended response"
      subtitle="Prepared for human approval. Nothing is executed until you approve."
      actions={
        fromModel ? <Badge tone="info" title={brief.model_used}>Nemotron Super</Badge>
          : <Badge tone="warning" title="The model did not return a valid plan, so this list was built from SQL only">SQL fallback</Badge>
      }
      footer="Plant, material and order values come from the ERP record of each PO. Reroutes are limited to suppliers the ERP lists as approved alternatives for that PO."
    >
      <h3>{brief.headline}</h3>
      {brief.criticality_summary && <p className="plan-summary" style={{ marginTop: 6 }}>{brief.criticality_summary}</p>}

      {brief.recommended_actions.length === 0 ? (
        <div className="empty"><h3>No valid actions</h3><p>The proposed actions did not match approved ERP data.</p></div>
      ) : (
        <ol className="actions">
          {brief.recommended_actions.map((a) => (
            <li key={a.po_id} className={`action ${approved.has(a.po_id) ? 'is-done' : ''}`}>
              <span className="action-num">{a.priority}</span>
              <div>
                <div className="action-title">{a.title}</div>
                {a.rationale && <p className="action-rationale">{a.rationale}</p>}
                <div className="action-meta">
                  <span className="chip">{TYPE_LABEL[a.action_type] || a.action_type}</span>
                  <span className="chip">{a.target_plant}</span>
                  <span className="chip">{a.target_material}</span>
                  <span className="chip chip-mono">{a.po_id}</span>
                  {a.target_supplier_id && <span className="chip chip-mono">→ {a.target_supplier_id}</span>}
                </div>
              </div>
              <div className="action-value">
                <strong>{eurFull(a.value_rerouted_eur)}</strong>
                <span className="caption">{approved.has(a.po_id) ? 'rerouted' : 'order value'}</span>
              </div>
            </li>
          ))}
        </ol>
      )}

      {reroutable.length > 0 && (
        <div className="approve-bar">
          <span className="caption">
            {nothingLeft ? `${approved.size} purchase order${approved.size === 1 ? '' : 's'} rerouted in the ERP database.`
              : `Approving updates ${reroutable.length} purchase order${reroutable.length === 1 ? '' : 's'} in the ERP database.`}
          </span>
          <button type="button" className={`btn ${nothingLeft ? 'btn-success' : 'btn-primary'}`} onClick={onApprove}
            disabled={approving || nothingLeft}>
            {approving ? <><Spinner /> Executing…</> : nothingLeft ? '✓ Approved' : `Approve ${reroutable.length} reroute${reroutable.length === 1 ? '' : 's'}`}
          </button>
        </div>
      )}
    </Card>
  )
}
