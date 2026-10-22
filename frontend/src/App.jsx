
import { useState } from 'react'
import Header from './components/Header'
import SearchBar from './components/SearchBar'
import ScenarioChips from './components/ScenarioChips'
import MetricCard from './components/MetricCard'
import ActionCard from './components/ActionCard'
import mockData from './mock/scan.json'

const euro = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 2,
})

function runwayTone(days) {
  if (days < 3) return 'red'
  if (days < 7) return 'amber'
  return 'green'
}

function App() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  function handleAnalyze() {
    if (loading || !query.trim()) return

    setLoading(true)
    setResult(null)
    setError('')

    setTimeout(() => {
      try {
        setResult(mockData)
      } catch (err) {
        setError('Analysis failed. Please try again.')
      } finally {
        setLoading(false)
      }
    }, 2000)
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

      <ScenarioChips
        onPick={setQuery}
        disabled={loading}
      />

      {loading && (
        <p className="status">Analyzing...</p>
      )}

      {error && (
        <p className="status" role="alert">
          {error}
        </p>
      )}

      {result?.matched && result.exposure && (
        <div className="metrics">
          <MetricCard
            label="At risk"
            value={euro.format(
              result.exposure.total_exposure_eur
            )}
            tone="red"
          />

          <MetricCard
            label="Open POs"
            value={result.exposure.open_pos_count}
          />

          <MetricCard
            label="Runway (days)"
            value={result.exposure.critical_runway_days}
            tone={runwayTone(
              result.exposure.critical_runway_days
            )}
          />

          <MetricCard
            label="Alternatives"
            value={
              result.exposure.mitigation_alternatives.length
            }
          />
        </div>
      )}

      {result?.brief && (
        <section className="brief">
          <h2 className="brief-headline">
            {result.brief.headline}
          </h2>

          <p className="brief-summary">
            {result.brief.criticality_summary}
          </p>

          {(result.brief.recommended_actions ?? []).map(
            (action) => (
              <ActionCard
                key={action.priority}
                action={action}
              />
            )
          )}
        </section>
      )}
    </div>
  )
}

export default App
