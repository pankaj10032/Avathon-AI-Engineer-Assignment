import { Fragment, useMemo } from 'react'
import { MapContainer, Marker, Popup, Polyline, TileLayer } from 'react-leaflet'
import L from 'leaflet'

const technicianIcon = L.divIcon({
  className: 'custom-marker technician-marker',
  html: '<div class="marker-dot marker-dot-blue"></div>',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
  popupAnchor: [0, -8],
})

const unassignedIcon = L.divIcon({
  className: 'custom-marker request-marker',
  html: '<div class="marker-dot marker-dot-red"></div>',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
  popupAnchor: [0, -8],
})

const currentRequestIcon = L.divIcon({
  className: 'custom-marker request-marker request-marker-current',
  html: '<div class="marker-dot marker-dot-yellow"></div>',
  iconSize: [20, 20],
  iconAnchor: [10, 10],
  popupAnchor: [0, -10],
})

const assignedIcon = L.divIcon({
  className: 'custom-marker assigned-marker',
  html: '<div class="marker-dot marker-dot-green"></div>',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
  popupAnchor: [0, -8],
})

const lineColors = {
  greedy: '#2563eb',
  hungarian: '#16a34a',
}

function courierSkills(courier) {
  if (Array.isArray(courier.skills)) return courier.skills
  if (courier.vehicle_type === 'van') return ['blood', 'organ', 'biopsy']
  if (courier.vehicle_type === 'motorcycle') return ['blood', 'biopsy']
  return []
}

function formatCoordinate(value) {
  return Number.isFinite(Number(value)) ? Number(value).toFixed(4) : '-'
}

function Legend() {
  return (
    <div className="legend">
      <div className="legend-title">Map Legend</div>
      <div className="legend-row">
        <span className="legend-dot blue" /> Technicians
      </div>
      <div className="legend-row">
        <span className="legend-dot red" /> Unassigned Requests
      </div>
      <div className="legend-row">
        <span className="legend-dot green" /> Assigned Requests
      </div>
      <div className="legend-row">
        <span className="legend-line greedy" /> Greedy line
      </div>
      <div className="legend-row">
        <span className="legend-line hungarian" /> Hungarian line
      </div>
    </div>
  )
}

function heatmapColor(value, maxValue) {
  if (!maxValue) return '#dbeafe'
  const ratio = Math.min(1, value / maxValue)
  const red = Math.round(219 - ratio * 139)
  const green = Math.round(234 - ratio * 128)
  const blue = Math.round(254 - ratio * 132)
  return `rgb(${red}, ${green}, ${blue})`
}

export default function MapView({
  technicians = [],
  requests = [],
  assignments = [],
  flashChange = null,
  animationMode = null,
  animationPhase = 'idle',
  animationOverlay = null,
  courierBadgeCounts = {},
  hungarianHeatmap = [],
}) {
  const technicianById = useMemo(
    () => Object.fromEntries(technicians.map((tech) => [tech.id, tech])),
    [technicians],
  )

  const requestById = useMemo(
    () => Object.fromEntries(requests.map((request) => [request.id, request])),
    [requests],
  )

  const assignedRequestIds = useMemo(
    () => new Set(assignments.map((assignment) => assignment.request_id)),
    [assignments],
  )

  const center = useMemo(() => {
    if (!technicians.length && !requests.length) return [41.8781, -87.6298]
    const points = [...technicians.map((t) => t.location), ...requests.map((r) => r.location)]
    const avgLat = points.reduce((sum, point) => sum + point.lat, 0) / points.length
    const avgLng = points.reduce((sum, point) => sum + point.lng, 0) / points.length
    return [avgLat, avgLng]
  }, [technicians, requests])

  const currentRequest = animationMode === 'greedy' ? animationOverlay?.request ?? null : null
  const eligibleCouriers =
    animationMode === 'greedy' ? animationOverlay?.eligible_couriers ?? [] : []

  const heatmapMax = useMemo(
    () =>
      hungarianHeatmap.reduce(
        (max, row) => Math.max(max, ...row.map((cell) => (Number.isFinite(cell) ? cell : 0))),
        0,
      ),
    [hungarianHeatmap],
  )

  const currentAssignment = useMemo(() => {
    if (animationMode !== 'greedy') return null
    return animationOverlay?.winning_courier ?? null
  }, [animationMode, animationOverlay])

  return (
    <div className="map-shell">
      <MapContainer center={center} zoom={11} className="map-container">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {technicians.map((tech) => (
          <Marker key={tech.id} position={[tech.location.lat, tech.location.lng]} icon={technicianIcon}>
            <Popup>
              <strong>{tech.name}</strong>
              <br />
              Skills: {courierSkills(tech).join(', ') || 'Unknown'}
              <br />
              Location: {formatCoordinate(tech.location?.lat)}, {formatCoordinate(tech.location?.lng)}
            </Popup>
          </Marker>
        ))}

        {requests.map((request) => {
          const assignment = requestById[request.id] ? assignments.find((item) => item.request_id === request.id) : null
          const isAssigned = assignedRequestIds.has(request.id)
          const isCurrent = currentRequest?.id === request.id
          const icon = isCurrent ? currentRequestIcon : isAssigned ? assignedIcon : unassignedIcon

          return (
            <Marker
              key={request.id}
              position={[request.location.lat, request.location.lng]}
              icon={icon}
            >
              <Popup>
                <strong>{request.id}</strong>
                <br />
                Hospital: {request.hospital_name ?? request.id}
                <br />
                Skill needed: {request.required_skill ?? request.sample_type ?? 'Unknown'}
                <br />
                Priority: {request.priority ?? request.urgency ?? 'Unknown'}
                {assignment ? (
                  <>
                    <br />
                    Assigned to: {technicianById[assignment.technician_id]?.name ?? assignment.technician_id}
                  </>
                ) : null}
              </Popup>
            </Marker>
          )
        })}

        {animationMode !== 'greedy'
          ? assignments.map((assignment) => {
              const technician = technicianById[assignment.technician_id]
              const request = requestById[assignment.request_id]
              if (!technician || !request) return null
              const isFlashing = flashChange?.to_request_id === assignment.request_id

              return (
                <Fragment key={`${assignment.technician_id}-${assignment.request_id}-group`}>
                  <Polyline
                    positions={[
                      [technician.location.lat, technician.location.lng],
                      [request.location.lat, request.location.lng],
                    ]}
                    pathOptions={{
                      color: lineColors[assignment.algorithm_used] ?? '#64748b',
                      weight: 3,
                      opacity: 0.9,
                    }}
                  />
                  {isFlashing ? (
                    <Polyline
                      positions={[
                        [technician.location.lat, technician.location.lng],
                        [request.location.lat, request.location.lng],
                      ]}
                      pathOptions={{
                        color: '#ef4444',
                        weight: 7,
                        opacity: 0.9,
                        dashArray: '10, 10',
                        className: 'reopt-flash-line',
                      }}
                    />
                  ) : null}
                </Fragment>
              )
            })
          : null}

        {animationMode === 'greedy' && currentRequest
          ? eligibleCouriers.map((courier) => {
              const technician = technicianById[courier.courier_id]
              if (!technician) return null
              return (
                <Polyline
                  key={`eligible-${courier.courier_id}-${currentRequest.id}`}
                  positions={[
                    [currentRequest.location.lat, currentRequest.location.lng],
                    [technician.location.lat, technician.location.lng],
                  ]}
                  pathOptions={{
                    color: '#94a3b8',
                    weight: 2,
                    opacity: 0.35,
                    dashArray: '6, 10',
                    className: 'eligible-line',
                  }}
                />
              )
            })
          : null}

        {animationMode === 'greedy' && currentRequest && currentAssignment
          ? (() => {
              const technician = technicianById[currentAssignment.courier_id]
              if (!technician) return null
              return (
                <Polyline
                  positions={[
                    [technician.location.lat, technician.location.lng],
                    [currentRequest.location.lat, currentRequest.location.lng],
                  ]}
                  pathOptions={{
                    color: '#22c55e',
                    weight: 5,
                    opacity: 0.95,
                    className: 'winning-line',
                  }}
                />
              )
            })()
          : null}
      </MapContainer>

      {animationMode === 'hungarian' && animationPhase === 'matrix' && hungarianHeatmap.length ? (
        <div className="heatmap-overlay">
          <div className="heatmap-title">Hungarian Cost Matrix</div>
          <table className="heatmap-table">
            <tbody>
              {hungarianHeatmap.map((row, rowIndex) => (
                <tr key={`heatmap-row-${rowIndex}`}>
                  {row.map((cell, cellIndex) => (
                    <td
                      key={`heatmap-cell-${rowIndex}-${cellIndex}`}
                      style={{ background: heatmapColor(Number(cell) || 0, heatmapMax) }}
                    >
                      {Number(cell).toFixed(1)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {animationMode === 'hungarian' && animationPhase === 'reveal' ? (
        <div className="hungarian-reveal-banner">Batch assignments appearing in parallel</div>
      ) : null}

      {Object.keys(courierBadgeCounts).length ? (
        <div className="courier-badges">
          {technicians.map((tech) => {
            const count = courierBadgeCounts[tech.id]
            if (!count) return null
            const left = `${Math.max(6, Math.min(94, 50 + (tech.location.lng - center[1]) * 35))}%`
            const top = `${Math.max(6, Math.min(94, 50 - (tech.location.lat - center[0]) * 35))}%`
            return (
              <div key={`badge-${tech.id}`} className="courier-badge" style={{ left, top }}>
                {count}
              </div>
            )
          })}
        </div>
      ) : null}

      <Legend />
    </div>
  )
}
