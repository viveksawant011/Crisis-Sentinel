function RouteRow({ tone, tag, fromName, fromSub, toName, toSub }) {
  return (
    <div className={`route-row ${tone}`}>
      <span className="route-tag">{tag}</span>
      <div className="route-node origin">
        <div className="route-node-name">{fromName}</div>
        <div className="route-node-sub">{fromSub}</div>
      </div>
      <div className="route-line"></div>
      <div className="route-node">
        <div className="route-node-name">{toName}</div>
        <div className="route-node-sub">{toSub}</div>
      </div>
    </div>
  )
}

function RouteGraph({ pos, alternatives }) {
  const top = pos[0]
  if (!top) return null

  const alt = alternatives.find((a) => a.po_id === top.po_id)

  return (
    <section className="route">
      <h3 className="route-title">Supply route · largest exposed order ({top.po_id})</h3>

      <RouteRow
        tone="red"
        tag="At risk"
        fromName={top.supplier_country}
        fromSub={top.supplier_name}
        toName={top.plant_name}
        toSub={top.material_id}
      />

      {alt ? (
        <RouteRow
          tone="green"
          tag="Fallback"
          fromName={alt.alt_supplier_country}
          fromSub={alt.alt_supplier_name}
          toName={top.plant_name}
          toSub={top.material_id}
        />
      ) : (
        <p className="muted">No registered alternative supplier for this order.</p>
      )}
    </section>
  )
}

export default RouteGraph