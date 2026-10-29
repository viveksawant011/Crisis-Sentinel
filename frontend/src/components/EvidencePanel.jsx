import { useState } from 'react'
import { domain } from '../format.js'
import { Badge, Card } from './ui.jsx'

export default function EvidencePanel({ intelligence }) {
  const [tab, setTab] = useState('claims')
  const { claims = [], sources = [], contradictions = [], search_log: log = [] } = intelligence
  const byId = Object.fromEntries(sources.map((s) => [s.id, s]))
  const claimById = Object.fromEntries(claims.map((c) => [c.claim_id, c]))
  const tabs = [['claims', `Claims · ${claims.length}`], ['sources', `Sources · ${sources.length}`], ['conflicts', `Conflicts · ${contradictions.length}`]]

  const SourceChip = ({ id }) =>
    byId[id] ? <a className="chip chip-mono" href={byId[id].url} target="_blank" rel="noreferrer" title={byId[id].title}>{id}</a>
      : <span className="chip chip-mono">{id}</span>

  return (
    <Card title="Evidence" subtitle="Every claim links to the web page it came from." bodyClass="">
      <div className="tabs" role="tablist" aria-label="Evidence">
        {tabs.map(([key, label]) => (
          <button key={key} role="tab" type="button" className="tab" aria-selected={tab === key} onClick={() => setTab(key)}>{label}</button>
        ))}
      </div>
      <div className="card-body" role="tabpanel">
        {tab === 'claims' && (claims.length === 0 ? <p className="caption">No claims could be extracted from the sources.</p> : (
          <ul className="list">
            {claims.map((c) => (
              <li key={c.claim_id} className="claim">
                <div className="claim-text">{c.text}</div>
                <div className="claim-meta">
                  <span className="chip">{c.type}</span>
                  {c.value && <span className="chip">{c.value}</span>}
                  {c.source_ids.map((id) => <SourceChip key={id} id={id} />)}
                </div>
              </li>
            ))}
          </ul>
        ))}

        {tab === 'sources' && (sources.length === 0 ? <p className="caption">No sources were retrieved.</p> : (
          <ul className="list">
            {sources.map((s) => (
              <li key={s.id} className="source">
                <span className="chip chip-mono">{s.id}</span>
                <span><a href={s.url} target="_blank" rel="noreferrer">{s.title}</a><span className="caption" style={{ display: 'block' }}>{domain(s.url)}</span></span>
              </li>
            ))}
          </ul>
        ))}

        {tab === 'conflicts' && (contradictions.length === 0 ? <p className="caption">No directly conflicting claims were detected.</p> : (
          <ul className="list">
            {contradictions.map((c, i) => (
              <li key={i} className="conflict">
                <div className="row">
                  <strong>{c.topic}</strong>
                  <Badge tone={c.resolution_status === 'resolved' ? 'success' : 'warning'}>{c.resolution_status}</Badge>
                </div>
                <p style={{ marginTop: 6 }}>{c.explanation}</p>
                <p className="caption" style={{ marginTop: 6 }}>A: {claimById[c.claim_a_id]?.text}</p>
                <p className="caption">B: {claimById[c.claim_b_id]?.text}</p>
                {c.resolution_note && <p className="caption" style={{ marginTop: 6 }}>Follow-up: {c.resolution_note}</p>}
                {c.winning_claim_id && <p className="caption">Better supported: {c.winning_claim_id}</p>}
                {c.follow_up_source_ids?.length > 0 && (
                  <div className="claim-meta">{c.follow_up_source_ids.map((id) => <SourceChip key={id} id={id} />)}</div>
                )}
              </li>
            ))}
          </ul>
        ))}
      </div>
      {log.length > 0 && (
        <div className="card-foot">
          <details>
            <summary>{log.filter((l) => !l.error).length} searches run</summary>
            <ul style={{ marginTop: 8 }}>
              {log.map((l, i) => (
                <li key={i} className="mono" style={{ fontSize: 11.5, marginTop: 4 }}>
                  {l.query}{l.follow_up_for ? '  (follow-up)' : ''}{l.error ? '  (failed)' : ''}
                </li>
              ))}
            </ul>
          </details>
        </div>
      )}
    </Card>
  )
}
