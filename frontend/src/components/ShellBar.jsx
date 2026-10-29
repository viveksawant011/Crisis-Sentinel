import { Badge } from './ui.jsx'

export default function ShellBar({ mode, onMode, onReset, resetting, busy, health }) {
  const keysMissing = health && (!health.keys.nebius || !health.keys.tavily)
  return (
    <header className="shell">
      <div className="shell-inner">
        <div className="brand">
          <svg className="brand-mark" width="28" height="28" viewBox="0 0 32 32" aria-hidden="true">
            <rect width="32" height="32" rx="8" fill="#0a6ed1" />
            <circle cx="16" cy="16" r="8.5" fill="none" stroke="#fff" strokeWidth="2.4" />
            <circle cx="16" cy="16" r="3.2" fill="#fff" />
          </svg>
          <div className="brand-text">
            <span className="brand-name">CrisisSentinel</span>
            <span className="brand-sub">VoltAuto GmbH · Supply disruption command center</span>
          </div>
        </div>

        <div className="shell-actions">
          {health === null ? (
            <Badge tone="danger" dot>API offline</Badge>
          ) : keysMissing ? (
            <Badge tone="warning" dot title="NEBIUS_API_KEY or TAVILY_API_KEY is not set on the backend">Keys missing</Badge>
          ) : health ? (
            <Badge tone="dark" dot>API online</Badge>
          ) : null}

          <div className="segmented" role="group" aria-label="Data source">
            <button type="button" aria-pressed={mode === 'live'} onClick={() => onMode('live')} disabled={busy || keysMissing}
              title={keysMissing ? 'Live mode needs API keys on the backend' : 'Search the web and call Nemotron live'}>
              Live
            </button>
            <button type="button" aria-pressed={mode === 'recorded'} onClick={() => onMode('recorded')} disabled={busy}
              title="Load a recorded live run (works offline)">
              Recorded
            </button>
          </div>

          <button type="button" className="btn btn-on-dark" onClick={onReset} disabled={busy || resetting}
            title="Rebuild the demo database so approvals can be replayed">
            {resetting ? 'Resetting…' : 'Reset demo data'}
          </button>
        </div>
      </div>
    </header>
  )
}
