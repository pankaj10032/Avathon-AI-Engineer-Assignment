import { useEffect, useMemo, useState } from 'react'
import MapView from './components/MapView'
import MetricsPanel from './components/MetricsPanel'

function haversineKm(loc1, loc2) {
  const toRad = (value) => (value * Math.PI) / 180
  const r = 6371
  const dLat = toRad((loc2?.lat ?? 0) - (loc1?.lat ?? 0))
  const dLng = toRad((loc2?.lng ?? 0) - (loc1?.lng ?? 0))
  const lat1 = toRad(loc1?.lat ?? 0)
  const lat2 = toRad(loc2?.lat ?? 0)
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) * Math.sin(dLng / 2)
  return 2 * r * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

function trafficMultiplier(currentTime) {
  const hour = currentTime.getHours()
  if ((hour >= 8 && hour < 10) || (hour >= 17 && hour < 20)) return 2.2
  if (hour >= 10 && hour < 17) return 1.4
  return 1.0
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

export default function App() {
  const [data, setData] = useState({ technicians: [], requests: [] })
  const [results, setResults] = useState(null)
  const [mode, setMode] = useState('greedy')
  const [pageLoading, setPageLoading] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [statusMessage, setStatusMessage] = useState('')
  const [flashChange, setFlashChange] = useState(null)
  const [animationMode, setAnimationMode] = useState(null)
  const [animationPhase, setAnimationPhase] = useState('idle')
  const [animationSteps, setAnimationSteps] = useState([])
  const [animationIndex, setAnimationIndex] = useState(-1)
  const [visibleAssignments, setVisibleAssignments] = useState([])
  const [courierBadgeCounts, setCourierBadgeCounts] = useState({})
  const [hungarianHeatmap, setHungarianHeatmap] = useState([])
  const [revealCount, setRevealCount] = useState(0)
  const [showMetricsPanel, setShowMetricsPanel] = useState(false)
  const [speedMs, setSpeedMs] = useState(600)

  async function loadData() {
    try {
      const response = await fetch(`${API_BASE}/api/data`)
      if (!response.ok) {
        throw new Error('Failed to fetch data')
      }
      const payload = await response.json()
      setData({
        technicians: payload.technicians ?? [],
        requests: payload.requests ?? [],
      })
    } catch {
      setError('The backend is unavailable right now. Please start FastAPI on port 8000 and try again.')
    }
  }

  useEffect(() => {
    ;(async () => {
      setPageLoading(true)
      await loadData()
      setPageLoading(false)
    })()
  }, [])

  const currentAssignments = useMemo(() => {
    if (!results) return []
    if (mode === 'both') return results.results?.hungarian?.assignments ?? []
    return results.assignments ?? []
  }, [results, mode])

  const currentMetrics = useMemo(() => {
    if (!results) return null
    if (mode === 'both') return null
    return results.metrics ?? null
  }, [results, mode])

  const comparison = useMemo(() => {
    if (mode !== 'both' || !results?.results) return null
    return results.results
  }, [results, mode])

  const animationAssignments = useMemo(() => {
    if (animationMode === 'greedy') return visibleAssignments
    if (animationMode === 'hungarian') return visibleAssignments.slice(0, revealCount)
    return currentAssignments
  }, [animationMode, visibleAssignments, revealCount, currentAssignments])

  const animationOverlay = useMemo(() => {
    if (animationMode === 'greedy' && animationIndex >= 0) {
      return animationSteps[animationIndex] ?? null
    }
    return null
  }, [animationMode, animationIndex, animationSteps])

  useEffect(() => {
    if (animationMode !== 'greedy' || !animationSteps.length) return undefined

    const interval = setInterval(() => {
      setAnimationIndex((prev) => {
        const next = prev + 1
        if (next >= animationSteps.length) {
          clearInterval(interval)
          return prev
        }
        setAnimationPhase('preview')
        return next
      })
    }, speedMs)

    return () => clearInterval(interval)
  }, [animationMode, animationSteps.length, speedMs])

  useEffect(() => {
    if (animationMode !== 'greedy' || animationIndex < 0 || animationIndex >= animationSteps.length) return undefined

    const step = animationSteps[animationIndex]
    setAnimationPhase('preview')

    const previewTimer = setTimeout(() => {
      setAnimationPhase('commit')
      if (step?.winning_courier) {
        setVisibleAssignments((prev) => {
          const next = prev.filter((assignment) => assignment.request_id !== step.request.id)
          next.push({
            technician_id: step.winning_courier.courier_id,
            request_id: step.request.id,
            algorithm_used: 'greedy',
            distance_km: step.winning_courier.distance_km,
            eta_minutes: step.winning_courier.eta_minutes,
            score: step.winning_courier.score,
            explanation: `Animated assignment to ${step.winning_courier.name}`,
            expiry_risk: false,
          })
          return next
        })
        setCourierBadgeCounts((prev) => ({
          ...prev,
          [step.winning_courier.courier_id]: (prev[step.winning_courier.courier_id] ?? 0) + 1,
        }))
      }
      if (animationIndex === animationSteps.length - 1) {
        setTimeout(() => {
          setAnimationMode(null)
          setAnimationPhase('idle')
          setShowMetricsPanel(true)
        }, 300)
      }
    }, 300)

    return () => clearTimeout(previewTimer)
  }, [animationMode, animationIndex, animationSteps])

  useEffect(() => {
    if (animationMode !== 'hungarian') return undefined
    const matrixTimer = setTimeout(() => {
      setAnimationPhase('reveal')
      setRevealCount(0)
      const stagger = setInterval(() => {
        setRevealCount((prev) => {
          const next = prev + 1
          if (next >= visibleAssignments.length) {
            clearInterval(stagger)
            setTimeout(() => {
              setAnimationMode(null)
              setAnimationPhase('idle')
              setShowMetricsPanel(true)
            }, 200)
          }
          return next
        })
      }, 100)
      return () => clearInterval(stagger)
    }, 2000)
    return () => clearTimeout(matrixTimer)
  }, [animationMode, visibleAssignments.length])

  async function runAllocation(algorithm) {
    setLoading(true)
    setError('')
    setStatusMessage('')

    try {
      const response = await fetch(`${API_BASE}/api/allocate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ algorithm }),
      })

      if (!response.ok) {
        throw new Error('Allocation request failed')
      }

      const payload = await response.json()
      setMode(algorithm)
      setResults(payload)
      setVisibleAssignments(payload.assignments ?? [])
      setCourierBadgeCounts({})
      setStatusMessage(`Finished ${algorithm} allocation.`)
      setShowMetricsPanel(true)
    } catch {
      setError('Could not run allocation. Make sure the FastAPI backend is running on port 8000.')
    } finally {
      setLoading(false)
    }
  }

  async function handleReset() {
    setLoading(true)
    setError('')
    setStatusMessage('')

    try {
      const response = await fetch(`${API_BASE}/api/reset`, {
        method: 'POST',
      })

      if (!response.ok) {
        throw new Error('Reset failed')
      }

      await loadData()
      setResults(null)
      setMode('greedy')
      setFlashChange(null)
      setAnimationMode(null)
      setAnimationPhase('idle')
      setAnimationSteps([])
      setAnimationIndex(-1)
      setVisibleAssignments([])
      setCourierBadgeCounts({})
      setHungarianHeatmap([])
      setRevealCount(0)
      setShowMetricsPanel(false)
      setStatusMessage('Sample data restored.')
    } catch {
      setError('Reset failed because the backend is unavailable. Please try again once FastAPI is running.')
    } finally {
      setLoading(false)
    }
  }

  async function handleUrgentArrival() {
    setLoading(true)
    setError('')
    setStatusMessage('')

    try {
      const urgentRequest = {
        id: `urgent-${Date.now()}`,
        hospital_name: 'Emergency Intake',
        location: {
          lat: data.technicians[0]?.location?.lat ?? 19.076,
          lng: data.technicians[0]?.location?.lng ?? 72.8777,
        },
        sample_type: 'blood',
        urgency: 'critical',
        expiry_minutes: 15,
        created_at: new Date().toISOString(),
        status: 'open',
      }

      const response = await fetch(`${API_BASE}/api/urgent-request`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          new_request: urgentRequest,
          current_assignments: currentAssignments,
        }),
      })

      if (!response.ok) {
        throw new Error('Urgent request failed')
      }

      const payload = await response.json()
      setResults((prev) => {
        if (!prev) return prev
        if (mode === 'both') {
          return prev
        }
        return {
          ...prev,
          assignments: payload.assignments,
          meta: payload.meta,
        }
      })

      const changed = payload.meta?.changed_assignment
      setFlashChange(changed || null)
      setStatusMessage(payload.meta?.reoptimized ? 'Urgent request triggered a re-optimization.' : 'Urgent request added without re-optimization.')
      if (payload.assignments) {
        setResults((prev) => {
          if (!prev) return prev
          if (mode === 'both') return prev
          return {
            ...prev,
            assignments: payload.assignments,
            metrics: {
              ...(prev.metrics ?? {}),
              urgent_meta: payload.meta,
            },
          }
        })
      }
    } catch {
      setError('Urgent re-optimization failed. Please make sure the backend is running.')
    } finally {
      setLoading(false)
    }
  }

  async function runGreedyAnimated() {
    setLoading(true)
    setError('')
    setStatusMessage('')
    setMode('greedy')
    setAnimationMode('greedy')
    setAnimationPhase('preview')
    setVisibleAssignments([])
    setCourierBadgeCounts({})
    setShowMetricsPanel(false)

    try {
      const [stepsResponse, resultsResponse] = await Promise.all([
        fetch(`${API_BASE}/api/allocate/steps?algorithm=greedy`),
        fetch(`${API_BASE}/api/allocate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ algorithm: 'greedy' }),
        }),
      ])

      if (!stepsResponse.ok || !resultsResponse.ok) {
        throw new Error('Animated greedy request failed')
      }

      const stepsPayload = await stepsResponse.json()
      const resultsPayload = await resultsResponse.json()
      setAnimationSteps(stepsPayload.steps ?? [])
      setResults(resultsPayload)
      setVisibleAssignments([])
      setAnimationIndex(-1)
      setStatusMessage('Playing greedy animation.')
    } catch {
      setError('Could not start the greedy animation. Make sure the FastAPI backend is running.')
      setAnimationMode(null)
    } finally {
      setLoading(false)
    }
  }

  function computeHeatmap() {
    const currentTime = new Date()
    const couriers = data.technicians
    const requests = data.requests
    return requests.map((request) =>
      couriers.map((courier) => {
        const dist = haversineKm(courier.location, request.location)
        const traffic = trafficMultiplier(currentTime)
        const eta = ((dist * traffic) / courier.speed_kmh) * 60
        return Number.isFinite(eta) ? eta : 0
      }),
    )
  }

  async function runHungarianAnimated() {
    setLoading(true)
    setError('')
    setStatusMessage('')
    setMode('hungarian')
    setAnimationMode('hungarian')
    setAnimationPhase('matrix')
    setVisibleAssignments([])
    setRevealCount(0)
    setShowMetricsPanel(false)

    try {
      const response = await fetch(`${API_BASE}/api/allocate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ algorithm: 'hungarian' }),
      })
      if (!response.ok) throw new Error('Hungarian animation failed')
      const payload = await response.json()
      setResults(payload)
      setVisibleAssignments(payload.assignments ?? [])
      setHungarianHeatmap(computeHeatmap())
      setStatusMessage('Showing Hungarian batch optimization.')
    } catch {
      setError('Could not start the Hungarian animation. Make sure the FastAPI backend is running.')
      setAnimationMode(null)
    } finally {
      setLoading(false)
    }
  }

  const mapKey = useMemo(() => {
    const assignmentIds = currentAssignments.map((assignment) => `${assignment.technician_id}-${assignment.request_id}`).join('|')
    return `${mode}-${assignmentIds}-${data.technicians.length}-${data.requests.length}`
  }, [currentAssignments, mode, data.technicians.length, data.requests.length])

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <h1>Resource Allocation Dashboard</h1>
          <p>Field service assignment engine for technicians and repair requests</p>
        </div>
        <div className="topbar-actions">
          <button onClick={() => runAllocation('greedy')} disabled={loading}>
            Run Greedy
          </button>
          <button onClick={runGreedyAnimated} disabled={loading || !data.technicians.length}>
            Run Greedy (Animated)
          </button>
          <button onClick={() => runAllocation('hungarian')} disabled={loading}>
            Run Hungarian
          </button>
          <button onClick={runHungarianAnimated} disabled={loading || !data.technicians.length}>
            Run Hungarian (Animated)
          </button>
          <button onClick={() => runAllocation('both')} disabled={loading}>
            Compare Both
          </button>
          <button className="secondary-btn" onClick={handleReset} disabled={loading}>
            Reset
          </button>
          <button className="urgent-btn" onClick={handleUrgentArrival} disabled={loading || !data.technicians.length}>
            Urgent Arrival
          </button>
          <label className="speed-control">
            <span>Speed</span>
            <input
              type="range"
              min="200"
              max="1000"
              step="200"
              value={speedMs}
              onChange={(e) => setSpeedMs(Number(e.target.value))}
            />
            <em>{speedMs === 1000 ? 'Slow' : speedMs === 600 ? 'Normal' : 'Fast'}</em>
          </label>
        </div>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}
      {statusMessage ? <div className="status-banner">{statusMessage}</div> : null}

      <main className="dashboard-grid">
        <section className="map-column">
          <div className="map-wrap">
          <MapView
              key={mapKey}
              technicians={data.technicians}
              requests={data.requests}
              assignments={animationAssignments}
              flashChange={flashChange}
              animationMode={animationMode}
              animationPhase={animationPhase}
              animationOverlay={animationOverlay}
              courierBadgeCounts={courierBadgeCounts}
              hungarianHeatmap={hungarianHeatmap}
            />
            {pageLoading || loading ? (
              <div className="loading-overlay" aria-live="polite" aria-busy="true">
                <div className="spinner" />
                <div className="loading-text">
                  {pageLoading ? 'Loading sample data...' : 'Running allocation...'}
                </div>
              </div>
            ) : null}
          </div>
        </section>

        <aside className="metrics-column">
          <MetricsPanel
            mode={mode}
            metrics={showMetricsPanel ? currentMetrics : null}
            comparison={comparison}
            assignments={animationAssignments}
            technicians={data.technicians}
            requests={data.requests}
            flashChange={flashChange}
            visible={showMetricsPanel}
          />
        </aside>
      </main>
    </div>
  )
}
