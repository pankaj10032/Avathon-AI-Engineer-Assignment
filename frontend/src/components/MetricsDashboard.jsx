import { useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const BAR_COLORS = ['#2563eb', '#0f766e', '#dc2626', '#7c3aed']

function formatMs(value) {
  if (typeof value !== 'number') return '-'
  return Number.isInteger(value) ? `${value} ms` : `${value.toFixed(0)} ms`
}

function formatMinutes(value) {
  if (typeof value !== 'number') return '-'
  return `${value.toFixed(1)} min`
}

function normalizeSeries(rows, keys) {
  const maxima = keys.reduce((acc, key) => {
    acc[key] = Math.max(...rows.map((row) => Number(row[key]) || 0), 1)
    return acc
  }, {})

  return rows.map((row) => {
    const normalized = { ...row }
    keys.forEach((key) => {
      normalized[key] = ((Number(row[key]) || 0) / maxima[key]) * 100
    })
    return normalized
  })
}

export default function MetricsDashboard({
  summary = {
    totalAssigned: 0,
    totalRequests: 0,
    avgTravelTime: 0,
    expiryRiskCount: 0,
    runtimeMs: 0,
  },
  algorithmStats = [],
  saConvergence = [],
  greedyBaselineCost = null,
}) {
  const [normalizeMetrics, setNormalizeMetrics] = useState(false)

  const barData = useMemo(() => {
    const rows = algorithmStats.map((entry) => ({
      name: entry.algorithm,
      totalAssigned: Number(entry.totalAssigned) || 0,
      avgTravelTime: Number(entry.avgTravelTime) || 0,
      expiryRisks: Number(entry.expiryRisks) || 0,
      runtimeMs: Number(entry.runtimeMs) || 0,
    }))

    if (!normalizeMetrics) return rows

    return normalizeSeries(rows, ['totalAssigned', 'avgTravelTime', 'expiryRisks', 'runtimeMs'])
  }, [algorithmStats, normalizeMetrics])

  const convergenceData = useMemo(
    () =>
      saConvergence.map((point, index) => ({
        iteration: point.iteration ?? index + 1,
        total_cost: Number(point.total_cost) || 0,
      })),
    [saConvergence],
  )

  const improvedPoints = useMemo(() => {
    if (greedyBaselineCost == null) return []
    return convergenceData.filter((point) => point.total_cost <= greedyBaselineCost)
  }, [convergenceData, greedyBaselineCost])

  const normalizeLabel = normalizeMetrics ? 'Normalized to 0-100%' : 'Raw values'

  return (
    <section className="metrics-dashboard">
      <div className="metrics-dashboard-header">
        <div>
          <h2>Live Metrics</h2>
          <p>{normalizeLabel}</p>
        </div>
        <label className="normalize-toggle">
          <input
            type="checkbox"
            checked={normalizeMetrics}
            onChange={(e) => setNormalizeMetrics(e.target.checked)}
          />
          <span>Normalize metrics</span>
        </label>
      </div>

      <div className="metrics-card-grid">
        <MetricCard label="Assigned / Requests" value={`${summary.totalAssigned}/${summary.totalRequests}`} />
        <MetricCard label="Avg Travel Time" value={formatMinutes(summary.avgTravelTime)} />
        <MetricCard label="Expiry Risk Count" value={summary.expiryRiskCount} highlight={summary.expiryRiskCount > 0} />
        <MetricCard label="Algorithm Runtime" value={formatMs(summary.runtimeMs)} />
      </div>

      <div className="charts-grid">
        <div className="chart-card">
          <div className="chart-card-header">
            <h3>Algorithm Comparison</h3>
            <p>Greedy vs Hungarian vs SA vs Hybrid</p>
          </div>
          <ResponsiveContainer width="100%" height={340}>
            <BarChart data={barData} margin={{ top: 12, right: 24, left: 8, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="name" tick={{ fill: '#475569' }} />
              <YAxis
                tick={{ fill: '#475569' }}
                domain={normalizeMetrics ? [0, 100] : ['auto', 'auto']}
                label={
                  normalizeMetrics
                    ? { value: 'Normalized score', angle: -90, position: 'insideLeft', fill: '#475569' }
                    : null
                }
              />
              <Tooltip />
              <Legend />
              <Bar dataKey="totalAssigned" name="Total Assigned" fill={BAR_COLORS[0]}>
                {barData.map((entry, index) => (
                  <Cell key={`assigned-${entry.name}`} fill={BAR_COLORS[0]} />
                ))}
              </Bar>
              <Bar dataKey="avgTravelTime" name="Avg Travel Time" fill={BAR_COLORS[1]}>
                {barData.map((entry) => (
                  <Cell key={`travel-${entry.name}`} fill={BAR_COLORS[1]} />
                ))}
              </Bar>
              <Bar dataKey="expiryRisks" name="Expiry Risks" fill={BAR_COLORS[2]}>
                {barData.map((entry) => (
                  <Cell key={`risk-${entry.name}`} fill={BAR_COLORS[2]} />
                ))}
              </Bar>
              <Bar dataKey="runtimeMs" name="Runtime" fill={BAR_COLORS[3]}>
                {barData.map((entry) => (
                  <Cell key={`runtime-${entry.name}`} fill={BAR_COLORS[3]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <div className="chart-card-header">
            <h3>Simulated Annealing Convergence</h3>
            <p>Improvement vs greedy baseline</p>
          </div>
          <ResponsiveContainer width="100%" height={340}>
            <LineChart data={convergenceData} margin={{ top: 12, right: 24, left: 8, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="iteration" tick={{ fill: '#475569' }} />
              <YAxis tick={{ fill: '#475569' }} />
              <Tooltip />
              <Legend />
              {greedyBaselineCost != null ? (
                <ReferenceLine y={greedyBaselineCost} stroke="#dc2626" strokeDasharray="6 6" label="Greedy baseline" />
              ) : null}
              <Line
                type="monotone"
                dataKey="total_cost"
                stroke="#2563eb"
                strokeWidth={3}
                dot={false}
                name="SA total cost"
              />
              {improvedPoints.length ? (
                <Line
                  type="monotone"
                  data={improvedPoints}
                  dataKey="total_cost"
                  stroke="#16a34a"
                  strokeWidth={3}
                  dot={{ r: 3 }}
                  name="Improved region"
                />
              ) : null}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </section>
  )
}

function MetricCard({ label, value, highlight = false }) {
  return (
    <div className={`dashboard-metric-card ${highlight ? 'dashboard-metric-card-alert' : ''}`}>
      <div className="dashboard-metric-label">{label}</div>
      <div className="dashboard-metric-value">{value}</div>
    </div>
  )
}
