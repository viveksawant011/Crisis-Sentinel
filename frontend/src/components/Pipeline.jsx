import { STAGES } from '../constants.js'
import { Spinner } from './ui.jsx'

export default function Pipeline({ stages, finished }) {
  return (
    <section className="card card-body" aria-label="Pipeline progress">
      <ol className="pipeline" aria-live="polite">
        {STAGES.map((s, i) => {
          const st = stages[s.key]
          const status = st?.status === 'done' ? 'done' : st?.status === 'running' ? 'active' : st?.status === 'error' ? 'error' : finished ? 'skipped' : 'pending'
          return (
            <li key={s.key} className={`step is-${status}`}>
              <div className="step-top">
                <span className="step-icon">
                  {status === 'done' ? '✓' : status === 'active' ? <Spinner /> : status === 'error' ? '!' : status === 'skipped' ? '–' : i + 1}
                </span>
                {s.label}
              </div>
              <p className="step-msg">{st?.message || (status === 'skipped' ? 'Not needed for this event' : 'Waiting')}</p>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
