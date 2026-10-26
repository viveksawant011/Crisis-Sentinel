import { eurCompact, int, runwayTone } from '../format.js'

function Kpi({ label, value, sub, tone = 'neutral' }) {
  return (
    <div className={`card kpi tone-${tone}`}>
      <div className="kpi-label">
        <span>{label}</span>
        <span className="src-tag" title="Computed by SQL, not by a language model">SQL</span>
      </div>
      <div className="kpi-value">{value}</div>
      <div className="kpi-sub">{sub}</div>
    </div>
  )
}

export default function Kpis({ exposure, baselineTotal }) {
  const pos = exposure.affected_open_pos || []
  const altIds = new Set((exposure.mitigation_alternatives || []).map((a) => a.alt_supplier_id))
  const covered = pos.filter((p) => p.has_alternative).length
  const detail = exposure.critical_runway_detail
  const total = exposure.total_exposure_eur || 0
  const reduced = baselineTotal != null && baselineTotal > total

  return (
    <div className="kpis">
      <Kpi label="Value at risk" value={eurCompact(total)} tone={total > 0 ? 'danger' : 'success'}
        sub={reduced ? `was ${eurCompact(baselineTotal)} before approval` : 'open purchase orders exposed'} />
      <Kpi label="Exposed POs" value={int(exposure.open_pos_count)}
        sub={`${(exposure.affected_plants || []).length} plants · ${(exposure.affected_suppliers || []).length} suppliers`} />
      <Kpi label="Shortest runway" value={exposure.critical_runway_days != null ? `${exposure.critical_runway_days} d` : '–'}
        tone={runwayTone(exposure.critical_runway_days)}
        sub={detail ? `${detail.material_name} · ${detail.plant_name}` : 'no stock records for exposed POs'} />
      <Kpi label="Approved alternatives" value={int(altIds.size)} tone="info"
        sub={`${covered} of ${pos.length} POs can be rerouted`} />
    </div>
  )
}
