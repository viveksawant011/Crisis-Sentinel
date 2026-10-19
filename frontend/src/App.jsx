import { useState } from 'react'
import Header from './components/Header'
import SearchBar from './components/SearchBar'
import ScenarioChips from './components/ScenarioChips'
import MetricCard from './components/MetricCard'
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

  function handleAnalyze() {
    setLoading(true)
    setResult(null)
    setTimeout(() => {
      setResult(mockData)
      setLoading(false)
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
      <ScenarioChips onPick={setQuery} disabled={loading} />
      {loading && <p className="status">Analyzing...</p>}

      {result && result.matched && (
        <div className="metrics">
          <MetricCard
            label="At risk"
            value={euro.format(result.exposure.total_exposure_eur)}
            tone="red"
          />
          <MetricCard label="Open POs" value={result.exposure.open_pos_count} />
          <MetricCard
            label="Runway (days)"
            value={result.exposure.critical_runway_days}
            tone={runwayTone(result.exposure.critical_runway_days)}
          />
          <MetricCard
            label="Alternatives"
            value={result.exposure.mitigation_alternatives.length}
          />
        </div>
      )}
    </div>
  )
}

export default App