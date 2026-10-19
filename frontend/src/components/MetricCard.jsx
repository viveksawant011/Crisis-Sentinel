function MetricCard({ label, value }) {
  return (
    <div style={{ border: '1px solid #ccc', padding: '16px', borderRadius: '8px', width: '180px' }}>
      <p>{label}</p>
      <h2>{value}</h2>
    </div>
  )
}

export default MetricCard;