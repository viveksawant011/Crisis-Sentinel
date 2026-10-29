import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'
import {
  executeMitigation, getHealth, getRecordedScenario, resetDemo, reviseMitigation, streamScan,
} from './api.js'
import CommandBar from './components/CommandBar.jsx'
import CriticPanel from './components/CriticPanel.jsx'
import EventHeader from './components/EventHeader.jsx'
import EvidencePanel from './components/EvidencePanel.jsx'
import Kpis from './components/Kpis.jsx'
import Pipeline from './components/Pipeline.jsx'
import ResponsePlan from './components/ResponsePlan.jsx'
import RunDetails from './components/RunDetails.jsx'
import ShellBar from './components/ShellBar.jsx'
import WhatIfPanel from './components/WhatIfPanel.jsx'
import { Alert, Card } from './components/ui.jsx'

const DEGRADED_TEXT = {
  extraction: 'The event could not be interpreted by the model.',
  strategy: 'The model did not return a valid plan, so the actions below were built from SQL only.',
  critic: 'The critic model was unavailable, so only rule checks ran.',
}

export default function App() {
  const [mode, setMode] = useState('live')
  const [health, setHealth] = useState(undefined) // undefined = loading, null = offline
  const [query, setQuery] = useState('')
  const [scenario, setScenario] = useState(null)
  const [loading, setLoading] = useState(false)
  const [stages, setStages] = useState({})
  const [finished, setFinished] = useState(false)
  const [result, setResult] = useState(null)
  const [baselineTotal, setBaselineTotal] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState(null)

  const [approving, setApproving] = useState(false)
  const [approval, setApproval] = useState(null)
  const [revising, setRevising] = useState(false)
  const [reviseError, setReviseError] = useState('')
  const [previousVerdict, setPreviousVerdict] = useState('')
  const [resetting, setResetting] = useState(false)
  const [whatIfKey, setWhatIfKey] = useState(0)
  const cancelRef = useRef(null)

  useEffect(() => {
    getHealth()
      .then((h) => {
        setHealth(h)
        if (!h.keys.nebius || !h.keys.tavily) setMode('recorded')
      })
      .catch(() => setHealth(null))
  }, [])

  const showNotice = useCallback((tone, text) => {
    setNotice({ tone, text })
    setTimeout(() => setNotice((n) => (n && n.text === text ? null : n)), 7000)
  }, [])

  const clearRun = () => {
    setResult(null); setError(''); setApproval(null); setPreviousVerdict(''); setReviseError('')
    setStages({}); setFinished(false); setBaselineTotal(null)
  }

  const acceptResult = (data) => {
    setResult(data)
    setBaselineTotal(data.exposure?.total_exposure_eur ?? null)
    setFinished(true)
    setLoading(false)
    cancelRef.current = null
  }

  const failRun = (err) => {
    setError(err.message)
    setFinished(true)
    setLoading(false)
    cancelRef.current = null
  }

  function handleAnalyze() {
    if (loading) return
    clearRun()
    setLoading(true)

    if (mode === 'recorded') {
      getRecordedScenario(scenario).then(acceptResult).catch(failRun)
      return
    }
    cancelRef.current = streamScan(query.trim(), {
      onEvent: (ev) => setStages((prev) => ({ ...prev, [ev.stage]: { status: ev.status, message: ev.message } })),
      onResult: acceptResult,
      onError: failRun,
    })
  }

  function handleCancel() {
    cancelRef.current?.()
    cancelRef.current = null
    setLoading(false)
    setFinished(true)
    showNotice('info', 'Cancelled. The server may still finish the run in the background.')
  }

  function handlePick(s) {
    setScenario(s.id)
    setQuery(s.query)
  }

  function handleQuery(text) {
    setQuery(text)
    setScenario(null)
  }

  function handleMode(next) {
    setMode(next)
    clearRun()
    if (next === 'recorded' && !scenario) {
      setQuery('')
    }
  }

  const reroutable = (result?.brief?.recommended_actions || []).filter(
    (a) => a.action_type === 'reroute_supplier' && a.po_id && a.target_supplier_id,
  )

  async function handleApprove() {
    if (!reroutable.length) return
    setApproving(true)
    try {
      const data = await executeMitigation({
        actions: reroutable.map((a) => ({ po_id: a.po_id, alt_supplier_id: a.target_supplier_id })),
        target_country: result.intelligence.impacted_country,
        target_category: result.intelligence.impacted_category,
      })
      setApproval(data.execution)
      if (data.updated_exposure) setResult((prev) => ({ ...prev, exposure: data.updated_exposure }))
      setWhatIfKey((k) => k + 1)
      const failed = data.execution.failed_pos_count
      showNotice(failed ? 'warning' : 'success',
        failed ? `${data.execution.rerouted_pos_count} rerouted, ${failed} refused by the ERP rules.`
          : `${data.execution.rerouted_pos_count} purchase order(s) rerouted in the ERP database.`)
    } catch (e) {
      showNotice('danger', `Approval failed: ${e.message}`)
    } finally {
      setApproving(false)
    }
  }

  async function handleRevise() {
    setRevising(true)
    setReviseError('')
    try {
      const data = await reviseMitigation({
        brief: result.brief, critique: result.critique,
        intelligence: result.intelligence, claims: result.intelligence.claims,
      })
      setPreviousVerdict(result.critique.verdict)
      setResult((prev) => ({ ...prev, brief: data.brief, critique: data.critique, exposure: data.exposure || prev.exposure }))
      setApproval(null)
    } catch (e) {
      setReviseError(e.message)
    } finally {
      setRevising(false)
    }
  }

  async function handleReset() {
    setResetting(true)
    try {
      await resetDemo()
      clearRun()
      showNotice('success', 'Demo database restored to its starting state.')
    } catch (e) {
      showNotice('danger', `Reset failed: ${e.message}`)
    } finally {
      setResetting(false)
    }
  }

  const exposure = result?.exposure
  const intel = result?.intelligence
  const degraded = (result?.provenance?.degraded || []).filter((d) => DEGRADED_TEXT[d])
  const showPipeline = loading || (mode === 'live' && Object.keys(stages).length > 0 && !result)

  return (
    <>
      <ShellBar mode={mode} onMode={handleMode} onReset={handleReset} resetting={resetting} busy={loading} health={health} />
      <main className="page">
        {notice && <Alert tone={notice.tone} onClose={() => setNotice(null)}>{notice.text}</Alert>}

        <CommandBar query={query} onQuery={handleQuery} scenario={scenario} onPick={handlePick}
          onAnalyze={handleAnalyze} onCancel={handleCancel} loading={loading} mode={mode} />

        {health === null && (
          <Alert tone="danger" title="API offline.">Start the backend (<code>uvicorn api:app --port 8000</code> inside <code>backend/</code>) and reload.</Alert>
        )}
        {error && <Alert tone="danger" title="Analysis failed.">{error}</Alert>}
        {showPipeline && <Pipeline stages={stages} finished={finished} />}

        {result && intel && (
          <>
            {result.cache_notice && <Alert tone="warning">{result.cache_notice}</Alert>}
            {degraded.map((d) => <Alert key={d} tone="warning" title={`Degraded: ${d}.`}>{DEGRADED_TEXT[d]}</Alert>)}

            <EventHeader intelligence={intel} cached={result.cached} recordedAt={result.recorded_at} />

            {!result.matched ? (
              <Card className="empty-card" bodyClass="">
                <div className="empty">
                  <h3>No exposure identified</h3>
                  <p>{exposure?.message || 'This event does not map to any open purchase orders.'}</p>
                  <p className="caption" style={{ marginTop: 8 }}>
                    A clean result is only reported when the event was understood and the SQL join found nothing.
                  </p>
                </div>
              </Card>
            ) : (
              <>
                <Kpis exposure={exposure} baselineTotal={baselineTotal} />
                <div className="grid">
                  <div className="stack">
                    {result.brief && (
                      <ResponsePlan brief={result.brief} onApprove={handleApprove} approving={approving}
                        approval={approval} reroutable={reroutable} />
                    )}
                    <WhatIfPanel country={intel.impacted_country} category={intel.impacted_category}
                      defaultDuration={intel.estimated_duration_days || 28} refreshKey={whatIfKey} />
                  </div>
                  <div className="stack">
                    {result.critique && (
                      <CriticPanel critique={result.critique} onRevise={handleRevise} revising={revising}
                        error={reviseError} previousVerdict={previousVerdict} />
                    )}
                    <EvidencePanel intelligence={intel} />
                    <RunDetails provenance={result.provenance} cached={result.cached} recordedAt={result.recorded_at} />
                  </div>
                </div>
              </>
            )}
          </>
        )}

        {!result && !loading && !error && (
          <Card bodyClass="">
            <div className="empty">
              <h3>Investigate a disruption</h3>
              <p>Choose a scenario or describe an event. CrisisSentinel researches it on the web, measures your exposure with SQL, and prepares an audited response for approval.</p>
            </div>
          </Card>
        )}
      </main>
    </>
  )
}

