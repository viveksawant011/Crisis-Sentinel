const SCENARIOS = [
  { label: 'Taiwan chips', query: 'Taiwan semiconductor supply chain disruption 2026' },
  { label: 'Poland battery', query: 'Poland battery component supplier strike' },
  { label: 'Japan sensors', query: 'Japan sensor logistics bottleneck' },
]

function ScenarioChips({ onPick, disabled }) {
  return (
    <div className="chips">
      <span className="chips-label">Try:</span>
      {SCENARIOS.map((s) => (
        <button
          key={s.label}
          className="chip"
          onClick={() => onPick(s.query)}
          disabled={disabled}
        >
          {s.label}
        </button>
      ))}
    </div>
  )
}

export default ScenarioChips