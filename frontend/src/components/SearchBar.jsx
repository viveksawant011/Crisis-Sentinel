function SearchBar({ query, setQuery, onAnalyze, loading }) {
  return (
    <div className="searchbar">
      <input
        className="search-input"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Describe a crisis, e.g. Taiwan semiconductor disruption"
      />
      <button
        className="search-button"
        onClick={onAnalyze}
        disabled={loading || query.trim() === ''}
      >
        {loading ? 'Analyzing...' : 'Analyze'}
      </button>
    </div>
  )
}

export default SearchBar