import React, { useState, useEffect } from 'react'
import { useStore } from '../store/useStore'
import {
  Cpu,
  Database,
  HardDrive,
  Thermometer,
  Clock,
  Video,
  VideoOff,
  Bell,
  Search,
  Menu,
} from 'lucide-react'

export const TopBar: React.FC = () => {
  const { health, mobileSidebarOpen, setMobileSidebarOpen } = useStore()
  const [timeStr, setTimeStr] = useState('')

  useEffect(() => {
    const updateTime = () => {
      const now = new Date()
      setTimeStr(now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }))
    }
    updateTime()
    const timer = setInterval(updateTime, 1000)
    return () => clearInterval(timer)
  }, [])

  const cameraState = health?.camera?.status || 'disconnected'
  const recordingState = health?.recording?.active || false
  const cpuPercent = health?.system?.cpu_percent || 0
  const memUsed = health?.system?.memory_used_mb || 0
  const temp = health?.system?.temperature_c || null
  const storageUsed = health?.recording?.storage_used_bytes || 0
  const storageFree = health?.recording?.storage_free_bytes || 0
  const storageTotal = storageUsed + storageFree
  const storagePct = storageTotal > 0 ? (storageUsed / storageTotal) * 100 : 0

  return (
    <header className="flex h-14 sm:h-16 w-full items-center justify-between border-b border-slate-900 bg-slate-950/80 px-3 sm:px-6 backdrop-blur-md">
      {/* Mobile Menu button & Search */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => setMobileSidebarOpen(!mobileSidebarOpen)}
          className="p-2 rounded-lg hover:bg-slate-900 text-slate-400 hover:text-slate-200 md:hidden border border-slate-900 bg-slate-950"
        >
          <Menu className="h-5 w-5" />
        </button>
        <div className="relative hidden md:block">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search recordings or press ⌘K..."
            readOnly
            className="h-9 w-64 rounded-xl bg-slate-900/50 border border-slate-900/80 pl-10 pr-4 text-xs text-slate-300 placeholder-slate-500 focus:outline-none focus:border-slate-800 cursor-pointer"
            onClick={() => window.dispatchEvent(new CustomEvent('open-command-palette'))}
          />
        </div>
      </div>

      {/* Subsystems and Resources Metrics */}
      <div className="flex items-center gap-2 sm:gap-4 lg:gap-6 text-xs text-slate-400">
        {/* Clock - hidden on very small screens */}
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/40 border border-slate-900">
          <Clock className="h-3.5 w-3.5 text-slate-500" />
          <span className="font-mono text-slate-200">{timeStr}</span>
        </div>

        {/* Camera Connection State */}
        <div className="flex items-center gap-2">
          {cameraState === 'active' ? (
            <span className="flex items-center gap-1.5 text-emerald-400 font-medium">
              <Video className="h-4 w-4" />
              <span className="hidden sm:inline">Camera Active</span>
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-rose-400 font-medium">
              <VideoOff className="h-4 w-4 animate-pulse" />
              <span className="hidden sm:inline">Offline</span>
            </span>
          )}
        </div>

        {/* Recording active state */}
        {recordingState && (
          <div className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-rose-500 animate-ping" />
            <span className="text-rose-400 font-medium tracking-wide">REC</span>
          </div>
        )}

        {/* Resources: CPU */}
        <div className="hidden lg:flex items-center gap-2" title="Host CPU Usage">
          <Cpu className="h-4 w-4 text-slate-500" />
          <span>CPU</span>
          <span className="font-semibold text-slate-200">{cpuPercent}%</span>
        </div>

        {/* Resources: RAM */}
        <div className="hidden lg:flex items-center gap-2" title="RAM Used">
          <Database className="h-4 w-4 text-slate-500" />
          <span>RAM</span>
          <span className="font-semibold text-slate-200">{Math.round(memUsed)} MB</span>
        </div>

        {/* Resources: Storage */}
        <div className="hidden xl:flex items-center gap-2" title="Storage Usage">
          <HardDrive className="h-4 w-4 text-slate-500" />
          <span>Disk</span>
          <span className="font-semibold text-slate-200">{storagePct.toFixed(0)}%</span>
        </div>

        {/* Resources: Temperature */}
        {temp !== null && (
          <div className="hidden xl:flex items-center gap-2" title="Host Temperature">
            <Thermometer className="h-4 w-4 text-slate-500" />
            <span>Temp</span>
            <span className="font-semibold text-slate-200">{temp}°C</span>
          </div>
        )}

        {/* Simple Notification Dot */}
        <button
          onClick={() => window.dispatchEvent(new CustomEvent('open-command-palette'))}
          className="relative p-2 rounded-xl hover:bg-slate-900 border border-transparent hover:border-slate-800 transition-all text-slate-400 hover:text-slate-200"
        >
          <Bell className="h-4 w-4" />
          <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-emerald-500" />
        </button>
      </div>
    </header>
  )
}
