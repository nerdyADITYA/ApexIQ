const BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'

async function request(path, options) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail)
  }
  return res.json()
}

const post = (path, body) => request(path, { method: 'POST', body: JSON.stringify(body) })

export const api = {
  seasons: () => request('/seasons'),
  events: (year) => request(`/events?season=${year}`),
  standings: (year) => request(`/seasons/${year}/standings`),
  driverForecast: (year) => request(`/championships/${year}/drivers`),
  constructorForecast: (year) => request(`/championships/${year}/constructors`),
  sessionDrivers: (id) => request(`/sessions/${id}/drivers`),
  laps: (id, driver) =>
    request(`/sessions/${id}/laps?limit=1000${driver ? `&driver=${driver}` : ''}`),
  compare: (id, drivers) => post(`/sessions/${id}/compare`, { drivers }),
  predictionsUpcoming: (year) => request(`/predictions/${year}`),
  raceForecast: (year, round) => request(`/predictions/${year}/rounds/${round}`),
  trackRecord: (year, source) => request(`/predictions/${year}/track-record?source=${source}`),
  progression: (year) => request(`/seasons/${year}/progression?top=6`),
  driverProfile: (code, year) => request(`/drivers/${code}/profile?season=${year}`),
  driverTracks: (code) => request(`/drivers/${code}/tracks`),
  constructorProfile: (team, year) =>
    request(`/constructors/${encodeURIComponent(team)}/profile?season=${year}`),
  telemetrySessions: () => request('/telemetry/sessions'),
  lapComparison: (sessionId, a, b) =>
    request(`/sessions/${sessionId}/lap-comparison?a=${a}${b ? `&b=${b}` : ''}`),
  simulateStrategy: (body) => post('/strategy/simulate', body),
}
