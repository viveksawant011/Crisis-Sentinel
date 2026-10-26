import { SEVERITY_TONE, timeAgo } from '../format.js'
import { Badge } from './ui.jsx'

export default function EventHeader({ intelligence, cached, recordedAt }) {
  const sev = (intelligence.severity || 'unknown').toLowerCase()
  return (
    <section className="card event" aria-label="Detected event">
      <div className="row">
        <Badge tone={SEVERITY_TONE[sev] || 'neutral'} dot>{sev === 'unknown' ? 'Severity unknown' : `${sev[0].toUpperCase()}${sev.slice(1)} severity`}</Badge>
        {intelligence.impacted_country && (
          <Badge>{intelligence.impacted_country}{intelligence.impacted_category ? ` · ${intelligence.impacted_category}` : ''}</Badge>
        )}
        {intelligence.estimated_duration_days != null && (
          <Badge tone="info" title="Duration estimated by the model from the sources">Est. duration {intelligence.estimated_duration_days} d</Badge>
        )}
        {cached && <Badge tone="warning">Recorded run{recordedAt ? ` · ${timeAgo(recordedAt)}` : ''}</Badge>}
      </div>
      <h2 className="event-title">{intelligence.event}</h2>
      <p className="caption">Evidence strength {intelligence.evidence_strength}</p>
    </section>
  )
}
