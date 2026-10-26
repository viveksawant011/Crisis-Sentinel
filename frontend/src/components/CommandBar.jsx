import { SCENARIOS } from '../constants.js'
import { Spinner } from './ui.jsx'

export default function CommandBar({ query, onQuery, scenario, onPick, onAnalyze, onCancel, loading, mode }) {
  const recorded = mode === 'recorded'
  const canRun = !loading && (recorded ? Boolean(scenario) : query.trim().length > 0)
  return (
    <section className="card command" aria-label="Investigate a disruption">
      <label className="command-label" htmlFor="query">
        {recorded ? 'Pick a recorded scenario' : 'Describe a real-world disruption to investigate'}
      </label>
      <form className="command-form" onSubmit={(e) => { e.preventDefault(); if (canRun) onAnalyze() }}>
        <input
          id="query"
          className="input"
          value={query}
          onChange={(e) => onQuery(e.target.value)}
          placeholder={recorded ? 'Choose one of the scenarios below' : 'e.g. Taiwan semiconductor supply chain disruption'}
          disabled={loading || recorded}
          autoComplete="off"
        />
        {loading ? (
          <button type="button" className="btn" onClick={onCancel}>Cancel</button>
        ) : (
          <button type="submit" className="btn btn-primary" disabled={!canRun}>
            {recorded ? 'Load run' : 'Investigate'}
          </button>
        )}
      </form>
      <div className="scenarios" role="group" aria-label="Scenarios">
        {SCENARIOS.map((s) => (
          <button key={s.id} type="button" className="scenario" aria-pressed={scenario === s.id}
            onClick={() => onPick(s)} disabled={loading}>
            <div className="scenario-title">{s.title}</div>
            <div className="scenario-sub">{s.sub}</div>
          </button>
        ))}
      </div>
      {loading && (
        <div className="row caption" aria-live="polite"><Spinner /> Working… live runs usually take 30–90 seconds.</div>
      )}
    </section>
  )
}
