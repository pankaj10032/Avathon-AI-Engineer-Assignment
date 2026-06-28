export default function MetricsPanel({
  mode = 'greedy',
  metrics = null,
  comparison = null,
  assignments = [],
  technicians = [],
  requests = [],
  flashChange = null,
  visible = true,
}) {
  const panelClass = `metrics-panel ${visible ? 'metrics-panel-visible' : 'metrics-panel-hidden'}`

  if (mode === 'both' && comparison) {
    return (
      <div className={panelClass}>
        <div className="panel-card">
          <h2>Comparison</h2>
          <div className="comparison-table-wrap">
            <table className="comparison-table">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Greedy</th>
                  <th>Hungarian</th>
                </tr>
              </thead>
              <tbody>
                {[
                  'total_assigned',
                  'total_unassigned',
                  'avg_distance_km',
                  'max_distance_km',
                  'avg_technician_utilization',
                  'total_cost_score',
                  'runtime_ms',
                ].map((key) => (
                  <tr key={key}>
                    <td>{formatMetricLabel(key)}</td>
                    <td>{formatMetricValue(comparison.greedy.metrics[key])}</td>
                    <td>{formatMetricValue(comparison.hungarian.metrics[key])}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="comparison-grid">
          <div className="panel-card">
            <h2>Greedy Assignments</h2>
            <AssignmentList
              assignments={comparison.greedy.assignments}
              technicians={technicians}
              requests={requests}
              flashChange={flashChange}
            />
          </div>
          <div className="panel-card">
            <h2>Hungarian Assignments</h2>
            <AssignmentList
              assignments={comparison.hungarian.assignments}
              technicians={technicians}
              requests={requests}
              flashChange={flashChange}
            />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={panelClass}>
      <div className="metric-cards">
        <MetricCard label="Assigned" value={metrics?.total_assigned ?? 0} />
        <MetricCard label="Avg Distance" value={`${formatMetricValue(metrics?.avg_distance_km ?? 0)} km`} />
        <MetricCard
          label="Utilization"
          value={`${(Number(metrics?.avg_technician_utilization ?? 0) * 100).toFixed(1)}%`}
        />
      </div>

      <div className="panel-card">
        <h2>Assignments</h2>
        <AssignmentList
          assignments={assignments}
          technicians={technicians}
          requests={requests}
          flashChange={flashChange}
        />
      </div>
    </div>
  )
}

function MetricCard({ label, value }) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
    </div>
  )
}

function AssignmentList({ assignments, technicians, requests, flashChange }) {
  const technicianById = Object.fromEntries(technicians.map((tech) => [tech.id, tech]))
  const requestById = Object.fromEntries(requests.map((request) => [request.id, request]))

  if (!assignments.length) {
    return <div className="empty-state">No assignments yet.</div>
  }

  return (
    <div className="assignment-list">
      {assignments.map((assignment) => {
        const technician = technicianById[assignment.technician_id]
        const request = requestById[assignment.request_id]

        return (
          <div
            className={`assignment-row ${flashChange?.to_request_id === assignment.request_id ? 'assignment-row-flash' : ''}`}
            key={`${assignment.technician_id}-${assignment.request_id}`}
          >
            <div className="assignment-main">
              <strong>{technician?.name ?? assignment.technician_id}</strong>
              <span>→</span>
              <strong>{request?.id ?? assignment.request_id}</strong>
            </div>
            <div className="assignment-meta">
              <span>{assignment.distance_km.toFixed(1)} km</span>
              <span>{assignment.explanation}</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function formatMetricLabel(value) {
  return value
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function formatMetricValue(value) {
  if (typeof value === 'number') {
    return Number.isInteger(value) ? value.toString() : value.toFixed(2)
  }
  return value ?? '-'
}
