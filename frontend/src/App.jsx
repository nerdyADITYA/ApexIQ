import { Suspense, lazy } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { Box, Building2, Flag, Target, Trophy, TrendingUp, Users } from 'lucide-react'
import Dashboard from './pages/Dashboard.jsx'
import RaceExplorer from './pages/RaceExplorer.jsx'
import StrategyLab from './pages/StrategyLab.jsx'
import Predictions from './pages/Predictions.jsx'
import Drivers from './pages/Drivers.jsx'
import DriverDetail from './pages/DriverDetail.jsx'
import Constructors from './pages/Constructors.jsx'
import ConstructorDetail from './pages/ConstructorDetail.jsx'
import { SeasonProvider } from './hooks/useSeason.jsx'

// three.js is large: load the Circuit Lab only when it is visited
const CircuitLab = lazy(() => import('./pages/CircuitLab.jsx'))

const NAV = [
  { to: '/', label: 'Season', Icon: Trophy, end: true },
  { to: '/drivers', label: 'Drivers', Icon: Users },
  { to: '/constructors', label: 'Teams', Icon: Building2 },
  { to: '/race', label: 'Races', Icon: Flag },
  { to: '/predictions', label: 'Predict', Icon: Target },
  { to: '/strategy', label: 'Strategy', Icon: TrendingUp },
  { to: '/circuit', label: 'Circuit', Icon: Box },
]

function Shell() {
  return (
    <div className="app">
      <nav className="sidebar" aria-label="Primary">
        <div className="logo" aria-hidden="true">F1</div>
        {NAV.map(({ to, label, Icon, end }) => (
          <NavLink key={to} to={to} end={end} className="side-link" title={label}>
            <Icon size={20} aria-hidden="true" />
            <span className="side-label">{label}</span>
          </NavLink>
        ))}
      </nav>
      <main className="page">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/drivers" element={<Drivers />} />
          <Route path="/drivers/:code" element={<DriverDetail />} />
          <Route path="/constructors" element={<Constructors />} />
          <Route path="/constructors/:team" element={<ConstructorDetail />} />
          <Route path="/race" element={<RaceExplorer />} />
          <Route path="/predictions" element={<Predictions />} />
          <Route path="/strategy" element={<StrategyLab />} />
          <Route
            path="/circuit"
            element={
              <Suspense fallback={<p role="status" className="muted">Loading 3D view…</p>}>
                <CircuitLab />
              </Suspense>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <SeasonProvider>
      <Shell />
    </SeasonProvider>
  )
}
