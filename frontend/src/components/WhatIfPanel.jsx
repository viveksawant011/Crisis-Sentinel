import { useEffect, useRef, useState } from 'react'
import { runWhatIf } from '../api.js'
import { eurCompact, int } from '../format.js'
import { Card, Spinner } from './ui.jsx'

function Scenario({ title, t, better }) {
  return (
    <div className={`scenario-box ${better ? 'is-better' : ''}`}>
      <h4>{title}</h4>
      <div className="big">{eurCompact(t.value_at_risk_eur)}</div>
      <dl>
        <dt>Line stoppage</dt><dd>{t.max_stoppage_days} days</dd>
        <dt>Plants affected</dt><dd>{t.plants_at_risk}</dd>
        <dt>Units short</dt><dd>{int(t.units_short)}</dd>
      </dl>
    </div>
  )
}

export default function WhatIfPanel({ country, category, defaultDuration, refreshKey }) {
  const [duration, setDuration] = useState(Math.min(90, Math.max(1, defaultDuration || 28)))
  const [capacity, setCapacity] = useState(100)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const seq = useRef(0)

  useEffect(() => {
    const id = ++seq.current
    const timer = setTimeout(async () => {
      setLoading(true)
      try {
        const res = await runWhatIf({
          country, category, disruption_days: Number(duration),
          capacity_offline_pct: Number(capacity), apply_reroute: true,
        })
        if (id === seq.current) { setData(res); setError('') }
      } catch (e) {
        if (id === seq.current) setError(e.message)
      } finally {
        if (id === seq.current) setLoading(false)
      }
    }, 200)
    return () => clearTimeout(timer)
  }, [country, category, duration, capacity, refreshKey])

  const base = data?.totals.baseline
  const rer = data?.totals.with_reroute
  const delta = data?.totals.delta
  const helps = delta && delta.avoided_value_at_risk_eur > 0

  return (
    <Card
      title="What-if simulator"
      subtitle="Pure SQL and inventory arithmetic. No language model is involved."
      actions={loading ? <span className="row caption"><Spinner /> Updating</span> : null}
      footer={data ? `Assumptions: ${data.assumptions.join(' · ')}.` : null}
    >
      <div className="sliders">
        <div className="slider">
          <label htmlFor="whatif-days">Disruption length <output htmlFor="whatif-days">{duration} days</output></label>
          <input id="whatif-days" type="range" min="1" max="90" value={duration} onChange={(e) => setDuration(e.target.value)} />
        </div>
        <div className="slider">
          <label htmlFor="whatif-cap">Regional capacity offline <output htmlFor="whatif-cap">{capacity}%</output></label>
          <input id="whatif-cap" type="range" min="0" max="100" step="5" value={capacity} onChange={(e) => setCapacity(e.target.value)} />
        </div>
      </div>

      {error && <p className="caption" role="alert" style={{ color: 'var(--danger)', marginTop: 12 }}>{error}</p>}

      {data && (
        <>
          <div className="compare">
            <Scenario title="Without action" t={base} />
            <Scenario title="With approved reroutes" t={rer} better={helps} />
          </div>
          <p className={`headline-delta ${helps ? '' : 'is-flat'}`}>
            {helps
              ? `Rerouting cuts line stoppage from ${base.max_stoppage_days} to ${rer.max_stoppage_days} days and avoids ${eurCompact(delta.avoided_value_at_risk_eur)} at risk.`
              : base.value_at_risk_eur === 0
                ? 'At these settings current stock covers the disruption, so no line stoppage is expected.'
                : 'At these settings rerouting does not change the outcome.'}
          </p>
          {data.plants.length > 0 && (
            <table className="plant-table">
              <thead>
                <tr><th scope="col">Plant</th><th scope="col" className="num">Stoppage now</th><th scope="col" style={{ width: '26%' }}><span className="sr-only">Comparison</span></th><th scope="col" className="num">With reroute</th></tr>
              </thead>
              <tbody>
                {data.plants.map((p) => {
                  const max = Math.max(base.max_stoppage_days, 1)
                  return (
                    <tr key={p.plant_name}>
                      <td>{p.plant_name}</td>
                      <td className="num">{p.stoppage_days_baseline.toFixed(1)} d</td>
                      <td>
                        <div className="bar" aria-hidden="true"><span style={{ width: `${(p.stoppage_days_baseline / max) * 100}%` }} /></div>
                        <div className="bar good" style={{ marginTop: 3 }} aria-hidden="true"><span style={{ width: `${(p.stoppage_days_with_reroute / max) * 100}%` }} /></div>
                      </td>
                      <td className="num">{p.stoppage_days_with_reroute.toFixed(1)} d</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
          {data.pos_without_inventory_record.length > 0 && (
            <p className="caption" style={{ marginTop: 12 }}>
              {data.pos_without_inventory_record.length} PO(s) have no stock record at their plant and are excluded.
            </p>
          )}
        </>
      )}
    </Card>
  )
}
