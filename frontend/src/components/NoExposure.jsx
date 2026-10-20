function NoExposure({ intelligence, message }) {
  return (
    <div className="banner clean">
      <h2>No exposure found</h2>
      <p>{message}</p>
      <p className="muted">
        Detected: {intelligence.impacted_country} · {intelligence.impacted_category} ·
        severity {intelligence.severity}
      </p>
    </div>
  )
}

export default NoExposure