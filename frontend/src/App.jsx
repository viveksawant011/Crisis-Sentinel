import { useState } from 'react'
import Header from './components/Header'
import SearchBar from './components/SearchBar'
import ScenarioChips from './components/ScenarioChips'
import MetricCard from './components/MetricCard'
import ActionCard from './components/ActionCard'
import NoExposure from './components/NoExposure'
import ErrorBanner from './components/ErrorBanner'
import { fetchScan } from './api'
import RouteGraph from './components/RouteGraph'
const euro = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 2,
})

function runwayTone(days) {
  if (days === null || days === undefined) return ''
  if (days < 3) return 'red'
  if (days < 7) return 'amber'
  return 'green'
}

function App() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  async function handleAnalyze() {
    setLoading(true)
    setResult(null)
    setError('')
    try {
      const data = await fetchScan(query)
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <Header />
      <SearchBar
        query={query}
        setQuery={setQuery}
        onAnalyze={handleAnalyze}
        loading={loading}
      />
      <ScenarioChips onPick={setQuery} disabled={loading} />
      {loading && <p className="status">Analyzing...</p>}
      {error && <ErrorBanner message={error} />}

      {result && !result.matched && (
        <NoExposure
          intelligence={result.intelligence}
          message={result.exposure.message}
        />
      )}

      {result && result.matched && (
        <>
          <div className="metrics">
            <MetricCard
              label="At risk"
              value={euro.format(result.exposure.total_exposure_eur)}
              tone="red"
            />
            <MetricCard label="Open POs" value={result.exposure.open_pos_count} />
            <MetricCard
              label="Runway (days)"
              value={result.exposure.critical_runway_days ?? 'n/a'}
              tone={runwayTone(result.exposure.critical_runway_days)}
            />
            <MetricCard
              label="Alternatives"
              value={result.exposure.mitigation_alternatives.length}
            />
          </div>
        <RouteGraph
  pos={result.exposure.affected_open_pos}
  alternatives={result.exposure.mitigation_alternatives}
/>
          <section className="brief">
            <h2 className="brief-headline">{result.brief.headline}</h2>
            <p className="brief-summary">{result.brief.criticality_summary}</p>
            {result.brief.recommended_actions.length === 0 && (
              <p className="muted">No automated actions were recommended.</p>
            )}
            {result.brief.recommended_actions.map((a) => (
              <ActionCard key={`${a.po_id}-${a.priority}`} action={a} />
            ))}
          </section>
        </>
      )}
    </div>
  )
}

export default App