import { useState } from 'react'
import Header from './components/Header'
import SearchBar from './components/SearchBar'

function App() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)

  function handleAnalyze() {
    setLoading(true)
    setTimeout(() => {
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
      {loading && <p className="status">Analyzing...</p>}
    </div>
  )
}

export default App