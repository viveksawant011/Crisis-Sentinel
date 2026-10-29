import { timeAgo } from '../format.js'
import { Card } from './ui.jsx'

const short = (id) => (id ? id.split('/').pop() : null)

export default function RunDetails({ provenance, cached, recordedAt }) {
  const m = provenance.models || {}
  const degraded = provenance.degraded || []
  return (
    <Card title="How this was produced" bodyClass="card-body">
      <dl className="dl">
        <dt>Extraction</dt><dd>{short(m.extraction) || '–'}</dd>
        <dt>Strategy</dt><dd>{short(m.strategy) || 'SQL fallback (no model output used)'}</dd>
        <dt>Critic</dt><dd>{short(m.critic) || 'rule checks only'}</dd>
        <dt>Web searches</dt><dd>{provenance.search_count}</dd>
        <dt>Sources · claims</dt><dd>{provenance.source_count} · {provenance.claims_extracted}</dd>
        <dt>Conflicts resolved</dt><dd>{provenance.contradictions_resolved ?? 0} of {provenance.contradictions_identified}</dd>
        {provenance.total_s != null && <><dt>Run time</dt><dd>{provenance.total_s} s</dd></>}
        <dt>{cached ? 'Recorded' : 'Generated'}</dt><dd>{timeAgo(cached ? recordedAt : provenance.generated_at) || '–'}</dd>
      </dl>
      {degraded.length > 0 && (
        <p className="caption" style={{ marginTop: 12, color: 'var(--warning)' }}>
          Degraded stages: {degraded.join(', ')}. Figures from SQL are unaffected.
        </p>
      )}
    </Card>
  )
}
