import React, { useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { useStore } from './store/useStore'
import { Sidebar } from './components/Sidebar'
import { TopBar } from './components/TopBar'
import { NotificationToast } from './components/NotificationToast'
import { CommandPalette } from './components/CommandPalette'

import { Dashboard } from './pages/Dashboard'
import { LiveView } from './pages/LiveView'
import { Recordings } from './pages/Recordings'
import { Snapshots } from './pages/Snapshots'
import { Analytics } from './pages/Analytics'
import { Health } from './pages/Health'
import { Settings } from './pages/Settings'
import { Logs } from './pages/Logs'

const Layout: React.FC = () => {
  const { setActiveTab, fetchHealth } = useStore()
  const navigate = useNavigate()
  const location = useLocation()

  // Sync route → Zustand (one direction only; Sidebar reads activeTab for highlighting)
  useEffect(() => {
    const tab = location.pathname.substring(1) || 'dashboard'
    setActiveTab(tab)
  }, [location.pathname, setActiveTab])

  // Sync Zustand setActiveTab → navigate is handled inside Sidebar link clicks directly.
  // Do NOT add a reverse effect here — it creates a feedback loop.

  // Poll health metrics globally every 3s (increased from 2.5s to reduce churn)
  useEffect(() => {
    fetchHealth()
    const timer = setInterval(fetchHealth, 3000)
    return () => clearInterval(timer)
  }, [fetchHealth])

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-950 text-slate-100 antialiased font-sans">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <TopBar />
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 md:p-8 bg-[#0b0f19]">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/live" element={<LiveView />} />
            <Route path="/recordings" element={<Recordings />} />
            <Route path="/snapshots" element={<Snapshots />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/health" element={<Health />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
      <NotificationToast />
      <CommandPalette />
    </div>
  )
}

function App() {
  return (
    <Router>
      <Layout />
    </Router>
  )
}

export default App
