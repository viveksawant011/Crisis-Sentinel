function MetricCard({ label, value, tone = '' }) {
  return (
    <div className={`metric ${tone}`}>
      <div className="metric-value">{value}</div>
      <div className="metric-label">{label}</div>
    </div>
  )
}

export default MetricCard