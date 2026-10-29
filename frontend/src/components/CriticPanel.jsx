import { Badge, Card, Spinner } from './ui.jsx'

const VERDICT = {
  accept: { tone: 'success', label: 'Plan accepted' },
  revise: { tone: 'warning', label: 'Revision recommended' },
  escalate: { tone: 'danger', label: 'Escalate to a human' },
  unverified: { tone: 'neutral', label: 'Not independently reviewed' },
}

export default function CriticPanel({ critique, onRevise, revising, error, previousVerdict }) {
  const verdict = VERDICT[critique.verdict] || VERDICT.unverified
  const checks = critique.checks || []
  const challenges = critique.challenges || []
  const canRevise = critique.verdict === 'revise' && !critique.revised
  const passedCount = checks.filter((c) => c.passed).length

  return (
    <Card
      title="Critic audit"
      subtitle="Rules re-verify every number in the plan; a second model argues against it."
      actions={<Badge tone={verdict.tone} dot>{verdict.label}</Badge>}
    >
      {critique.revised && (
        <p className="caption" style={{ marginBottom: 12 }}>
          Revised once after critique{previousVerdict ? ` (previous verdict: ${previousVerdict})` : ''}. This audit covers the new plan.
        </p>
      )}
      {critique.status === 'degraded' && (
        <p className="caption" style={{ marginBottom: 12, color: 'var(--warning)' }}>
          The critic model was unavailable, so only the rule checks ran.
        </p>
      )}

      <div className="section-label">Rule checks · {passedCount}/{checks.length} passed</div>
      <ul className="checks">
        {checks.map((c) => (
          <li key={c.id} className={`check ${c.passed ? 'ok' : 'fail'}`}>
            <span className="check-icon" aria-label={c.passed ? 'Passed' : 'Failed'}>{c.passed ? '✓' : '✕'}</span>
            <span>{c.label}<span className="check-detail">{c.detail}</span></span>
          </li>
        ))}
      </ul>

      <div className="section-label">Challenges{challenges.length ? ` · ${challenges.length}` : ''}</div>
      {challenges.length === 0 ? (
        <p className="caption">The critic found no weaknesses it could substantiate.</p>
      ) : (
        <div>
          {challenges.map((c, i) => (
            <div key={i} className={`challenge sev-${c.severity}`}>
              <div className="challenge-head">
                <span>{c.target}</span>
                <Badge tone={c.severity === 'high' ? 'danger' : c.severity === 'medium' ? 'warning' : 'info'}>{c.severity}</Badge>
                <span className="chip">{c.origin === 'deterministic' ? 'Rule' : 'Model'}</span>
              </div>
              <p>{c.explanation}</p>
              {c.suggested_fix && <p className="fix">Suggested: {c.suggested_fix}</p>}
            </div>
          ))}
        </div>
      )}

      {error && <p role="alert" className="caption" style={{ marginTop: 12, color: 'var(--danger)' }}>{error}</p>}

      {canRevise && (
        <button type="button" className="btn btn-primary" style={{ marginTop: 16, width: '100%' }} onClick={onRevise} disabled={revising}>
          {revising ? <><Spinner /> Rewriting and re-auditing…</> : 'Revise plan using this feedback'}
        </button>
      )}
      {critique.revised && critique.verdict === 'revise' && (
        <p className="caption" style={{ marginTop: 12 }}>
          The critic still has objections after the one allowed revision. A human should decide.
        </p>
      )}
    </Card>
  )
}
