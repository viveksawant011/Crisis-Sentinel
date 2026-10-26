import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App.jsx'

import recordedTaiwan from './fixtures/recorded_taiwan_semiconductor.json'
import recordedPoland from './fixtures/recorded_poland_battery.json'
import whatifTaiwan from './fixtures/whatif_taiwan.json'
import scanNoExposure from './fixtures/scan_no_exposure.json'
import scanDegraded from './fixtures/scan_degraded.json'

const HEALTH_OK = { ok: true, database: true, keys: { nebius: true, tavily: true }, recorded_scenarios: [] }
const json = (body, status = 200) => Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) })

let calls
function mockApi(overrides = {}) {
  calls = []
  globalThis.fetch = vi.fn((url, opts = {}) => {
    const path = String(url)
    calls.push({ path, body: opts.body ? JSON.parse(opts.body) : null })
    if (overrides[path]) return overrides[path](opts)
    if (path.endsWith('/api/health')) return json(HEALTH_OK)
    if (path.endsWith('/api/whatif')) return json(whatifTaiwan)
    if (path.includes('/api/cache/scenario/taiwan_semiconductor')) return json(recordedTaiwan)
    if (path.includes('/api/cache/scenario/poland_battery')) return json(recordedPoland)
    return json({ detail: 'not mocked: ' + path }, 404)
  })
}

class FakeEventSource {
  static last
  constructor(url) { this.url = url; FakeEventSource.last = this; this.closed = false }
  emit(obj) { this.onmessage?.({ data: JSON.stringify(obj) }) }
  close() { this.closed = true }
}

beforeEach(() => { globalThis.EventSource = FakeEventSource })
afterEach(() => { vi.restoreAllMocks() })

async function openRecorded(user, scenarioName = /Taiwan semiconductors/) {
  await user.click(screen.getByRole('button', { name: 'Recorded' }))
  await user.click(screen.getByRole('button', { name: scenarioName }))
  await user.click(screen.getByRole('button', { name: 'Load run' }))
}

describe('CrisisSentinel UI', () => {
  it('shows an offline banner when the API cannot be reached', async () => {
    mockApi({ '/api/health': () => Promise.reject(new Error('down')) })
    render(<App />)
    expect(await screen.findAllByText(/API offline/i)).not.toHaveLength(0)
  })

  it('defaults to recorded mode when the backend has no API keys', async () => {
    mockApi({ '/api/health': () => json({ ...HEALTH_OK, keys: { nebius: false, tavily: false } }) })
    render(<App />)
    expect(await screen.findByText('Keys missing')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Recorded' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Live' })).toBeDisabled()
  })

  it('renders the recorded Taiwan run with SQL-derived KPIs, plan, critic and evidence', async () => {
    mockApi()
    const user = userEvent.setup()
    render(<App />)
    await openRecorded(user)

    expect(await screen.findByText('Recommended response')).toBeInTheDocument()
    expect(screen.getByText('€4.72M')).toBeInTheDocument()        // value at risk from the SQL exposure
    expect(screen.getByText('Critic audit')).toBeInTheDocument()
    expect(screen.getByText('Evidence')).toBeInTheDocument()
    expect(screen.getByText(/Recorded run/)).toBeInTheDocument()
    expect(screen.getByText(/recorded action\(s\) were removed/)).toBeInTheDocument()   // cache notice is surfaced
    expect(await screen.findByText(/Rerouting cuts line stoppage/)).toBeInTheDocument() // what-if loaded
    expect(screen.queryByText(/92\s*\/\s*100|98\s*\/\s*100/)).not.toBeInTheDocument()  // no fabricated critic score
  })

  it('approves exactly the plan\'s reroute actions, each as a (po, supplier) pair', async () => {
    mockApi({
      '/api/mitigation/execute': () => json({
        execution: { status: 'SUCCESS', rerouted_pos_count: 2, failed_pos_count: 0, results: recordedTaiwan.brief.recommended_actions.map((a) => ({ success: true, po_id: a.po_id })) },
        updated_exposure: { ...recordedTaiwan.exposure, total_exposure_eur: 1000000, open_pos_count: 9 },
      }),
    })
    const user = userEvent.setup()
    render(<App />)
    await openRecorded(user)
    await user.click(await screen.findByRole('button', { name: /Approve 2 reroutes/ }))

    await waitFor(() => expect(screen.getByRole('button', { name: /Approved/ })).toBeDisabled())
    const exec = calls.find((c) => c.path.endsWith('/api/mitigation/execute'))
    expect(exec.body.actions).toEqual(recordedTaiwan.brief.recommended_actions.map((a) => ({ po_id: a.po_id, alt_supplier_id: a.target_supplier_id })))
    expect(exec.body.target_country).toBe('Taiwan')
    expect(await screen.findByText(/was €4.72M before approval/)).toBeInTheDocument()
  })

  it('refuses to load a recorded scenario when none is selected', async () => {
    mockApi()
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('button', { name: 'Recorded' }))
    expect(screen.getByRole('button', { name: 'Load run' })).toBeDisabled()
  })

  it('streams real pipeline stages in live mode, then shows the result', async () => {
    mockApi()
    const user = userEvent.setup()
    render(<App />)
    await user.type(await screen.findByLabelText(/Describe a real-world disruption/), 'Taiwan fab shutdown')
    await user.click(screen.getByRole('button', { name: 'Investigate' }))

    const es = FakeEventSource.last
    expect(es.url).toContain('/api/disruption/scan/stream?query=Taiwan%20fab%20shutdown')
    es.emit({ stage: 'research', status: 'running', message: 'Searching live sources (3 queries)' })
    expect(await screen.findByText('Searching live sources (3 queries)')).toBeInTheDocument()
    es.emit({ stage: 'research', status: 'done', message: 'Complete' })
    es.emit({ stage: 'extraction', status: 'running', message: 'Extracting claims from 6 sources' })
    expect(await screen.findByText('Extracting claims from 6 sources')).toBeInTheDocument()

    es.emit({ stage: 'result', status: 'done', data: { ...recordedTaiwan, cached: false, cache_notice: undefined } })
    expect(await screen.findByText('Recommended response')).toBeInTheDocument()
    expect(es.closed).toBe(true)
  })

  it('surfaces stream errors and rate limits instead of hanging', async () => {
    mockApi()
    const user = userEvent.setup()
    render(<App />)
    await user.type(await screen.findByLabelText(/Describe a real-world disruption/), 'anything')
    await user.click(screen.getByRole('button', { name: 'Investigate' }))
    FakeEventSource.last.emit({ stage: 'error', status: 'error', message: 'RuntimeError: boom' })
    expect(await screen.findByText(/RuntimeError: boom/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Investigate' })).toBeEnabled()
  })

  it('says so plainly when there is no exposure, without KPIs or a plan', async () => {
    mockApi()
    const user = userEvent.setup()
    render(<App />)
    await user.type(await screen.findByLabelText(/Describe a real-world disruption/), 'Volcanic ash')
    await user.click(screen.getByRole('button', { name: 'Investigate' }))
    FakeEventSource.last.emit({ stage: 'result', status: 'done', data: scanNoExposure })
    expect(await screen.findByText('No exposure identified')).toBeInTheDocument()
    expect(screen.queryByText('Value at risk')).not.toBeInTheDocument()
    expect(screen.queryByText('Recommended response')).not.toBeInTheDocument()
  })

  it('labels degraded stages and the SQL fallback honestly', async () => {
    mockApi()
    const user = userEvent.setup()
    render(<App />)
    await user.type(await screen.findByLabelText(/Describe a real-world disruption/), 'Taiwan chips')
    await user.click(screen.getByRole('button', { name: 'Investigate' }))
    FakeEventSource.last.emit({ stage: 'result', status: 'done', data: scanDegraded })
    expect(await screen.findByText('SQL fallback')).toBeInTheDocument()
    expect(screen.getByText(/Degraded: strategy/)).toBeInTheDocument()
    expect(screen.getByText('Not independently reviewed')).toBeInTheDocument()
    expect(screen.getByText('SQL fallback (no model output used)')).toBeInTheDocument()
  })

  it('offers one revision when the critic says revise, and shows the real new verdict', async () => {
    const revised = { ...recordedTaiwan.critique, verdict: 'accept', revised: true, challenges: [] }
    mockApi({
      '/api/mitigation/revise': () => json({ status: 'revised', previous_verdict: 'revise', brief: recordedTaiwan.brief, critique: revised, exposure: recordedTaiwan.exposure }),
    })
    const user = userEvent.setup()
    render(<App />)
    await openRecorded(user)
    await user.click(await screen.findByRole('button', { name: /Revise plan using this feedback/ }))
    expect(await screen.findByText('Plan accepted')).toBeInTheDocument()
    expect(screen.getByText(/previous verdict: revise/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Revise plan/ })).not.toBeInTheDocument()  // bounded to one revision
  })

  it('shows the API reason when a revision is unavailable', async () => {
    mockApi({ '/api/mitigation/revise': () => json({ detail: 'Revision unavailable: the model did not return a valid plan. The original plan is unchanged.' }, 502) })
    const user = userEvent.setup()
    render(<App />)
    await openRecorded(user)
    await user.click(await screen.findByRole('button', { name: /Revise plan using this feedback/ }))
    expect(await screen.findByText(/Revision unavailable/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Revise plan using this feedback/ })).toBeEnabled()
  })

  it('renders the Poland recording and lists evidence tabs with source links', async () => {
    mockApi()
    const user = userEvent.setup()
    render(<App />)
    await openRecorded(user, /Poland batteries/)
    await screen.findByText('Evidence')
    await user.click(screen.getByRole('tab', { name: /Sources/ }))
    const panel = screen.getByRole('tabpanel')
    const links = within(panel).getAllByRole('link')
    expect(links.length).toBeGreaterThan(0)
    expect(links[0]).toHaveAttribute('href', expect.stringMatching(/^https?:\/\//))
  })
})
