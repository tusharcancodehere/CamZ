import React from 'react'
import { useStore } from '../store/useStore'
import {
  Video,
  Play,
  Square,
  Camera,
  Activity,
  Heart,
  Cpu,
  Clock,
  Shield,
} from 'lucide-react'

export const Dashboard: React.FC = () => {
  const { health, addNotification, setActiveTab } = useStore()

  // Calculate Health Score dynamically
  const getHealthScore = () => {
    if (!health) return 0
    let score = 0
    if (health.camera?.status === 'active') score += 50
    const cpu = health.system?.cpu_percent || 0
    if (cpu < 30) score += 25
    else if (cpu < 60) score += 15
    const memPct = health.system?.memory_percent || 0
    if (memPct < 60) score += 15
    else if (memPct < 85) score += 8
    const temp = health.system?.temperature_c || 40
    if (temp < 60) score += 10
    else if (temp < 80) score += 5
    return score
  }

  const score = getHealthScore()
  const uptimeSeconds = health?.system?.uptime_seconds || 0
  const formatUptime = (sec: number) => {
    const hrs = Math.floor(sec / 3600)
    const mins = Math.floor((sec % 3600) / 60)
    return `${hrs}h ${mins}m`
  }

  const handleAction = async (endpoint: string, successMsg: string, errorMsg: string, method = 'POST') => {
    try {
      const res = await fetch(endpoint, { method })
      if (res.ok) {
        addNotification(successMsg, 'success')
      } else {
        addNotification(errorMsg, 'error')
      }
    } catch {
      addNotification(errorMsg, 'error')
    }
  }

  return (
    <div className="space-y-6">
      {/* Hero Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-100">System Dashboard</h1>
          <p className="text-sm text-slate-500">Real-time status overview and surveillance operations control.</p>
        </div>
        
        {/* Quick Actions Panel */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => handleAction('/snapshot', 'Snapshot captured', 'Failed to capture snapshot')}
            className="flex items-center gap-2 rounded-xl bg-slate-900 border border-slate-800 hover:bg-slate-850 px-4 py-2.5 text-xs font-semibold text-slate-200 transition-all"
          >
            <Camera className="h-4 w-4" />
            Take Snapshot
          </button>
          <button
            onClick={() => handleAction('/recording/start', 'Manual recording started', 'Failed to start recording')}
            className="flex items-center gap-2 rounded-xl bg-emerald-500 hover:bg-emerald-600 px-4 py-2.5 text-xs font-semibold text-slate-950 transition-all shadow-lg shadow-emerald-500/10"
          >
            <Play className="h-4 w-4" />
            Start Recording
          </button>
          <button
            onClick={() => handleAction('/recording/stop', 'Recording stopped & saved', 'Failed to stop recording')}
            className="flex items-center gap-2 rounded-xl bg-rose-500 hover:bg-rose-600 px-4 py-2.5 text-xs font-semibold text-slate-950 transition-all shadow-lg shadow-rose-500/10"
          >
            <Square className="h-4 w-4" />
            Stop Recording
          </button>
          <button
            onClick={() => handleAction('/camera/restart', 'Camera restarted', 'Failed to restart camera')}
            className="flex items-center gap-2 rounded-xl bg-slate-900 border border-slate-800 hover:bg-slate-850 px-4 py-2.5 text-xs font-semibold text-slate-200 transition-all"
          >
            <Shield className="h-4 w-4" />
            Restart Camera
          </button>
        </div>
      </div>

      {/* Primary Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Health Score */}
        <div className="p-5 rounded-2xl border border-slate-900 bg-slate-950/50 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span>Health Score</span>
            <Heart className="h-4 w-4 text-rose-500 fill-rose-500/10" />
          </div>
          <div className="mt-4">
            <span className="text-3xl font-extrabold text-slate-100 font-mono">{score}%</span>
            <div className="mt-2 h-1.5 w-full rounded-full bg-slate-900 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  score > 80 ? 'bg-emerald-500' : score > 50 ? 'bg-amber-500' : 'bg-rose-500'
                }`}
                style={{ width: `${score}%` }}
              />
            </div>
          </div>
        </div>

        {/* Streaming FPS */}
        <div className="p-5 rounded-2xl border border-slate-900 bg-slate-950/50 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span>Streaming Frame Rate</span>
            <Activity className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-4">
            <span className="text-3xl font-extrabold text-slate-100 font-mono">
              {health?.pipeline?.streaming_fps?.toFixed(1) || '0.0'}
            </span>
            <span className="text-xs text-slate-500 ml-1.5">FPS</span>
          </div>
        </div>

        {/* CPU Load */}
        <div className="p-5 rounded-2xl border border-slate-900 bg-slate-950/50 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span>CPU Usage</span>
            <Cpu className="h-4 w-4 text-slate-500" />
          </div>
          <div className="mt-4 col-span-2">
            <span className="text-3xl font-extrabold text-slate-100 font-mono">
              {health?.system?.cpu_percent || 0}%
            </span>
            <span className="text-xs text-slate-500 ml-1.5">of Host</span>
          </div>
        </div>

        {/* System Uptime */}
        <div className="p-5 rounded-2xl border border-slate-900 bg-slate-950/50 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span>System Uptime</span>
            <Clock className="h-4 w-4 text-slate-500" />
          </div>
          <div className="mt-4">
            <span className="text-2xl font-bold text-slate-100 font-mono">
              {formatUptime(uptimeSeconds)}
            </span>
          </div>
        </div>
      </div>

      {/* Main Workspace: Large Preview & Quick Timeline */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Large Preview */}
        <div className="xl:col-span-2 p-5 rounded-2xl border border-slate-900 bg-slate-950/40 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Video className="h-4 w-4 text-emerald-400" />
              <span className="text-sm font-semibold text-slate-200">Live Camera Stream</span>
            </div>
            <button
              onClick={() => setActiveTab('live')}
              className="text-xs text-emerald-400 hover:text-emerald-300 font-medium transition-colors"
            >
              Expand Stream View &rarr;
            </button>
          </div>

          <div
            className="relative aspect-video rounded-xl border border-slate-900 bg-slate-950 overflow-hidden cursor-pointer shadow-2xl"
            onClick={() => setActiveTab('live')}
          >
            <img
              src="/stream.mjpeg"
              alt="Live camera feed"
              className="h-full w-full object-cover"
              onError={(e) => {
                e.currentTarget.style.display = 'none'
                const parent = e.currentTarget.parentElement
                if (parent) {
                  const placeholder = parent.querySelector('.stream-offline-placeholder') as HTMLElement
                  if (placeholder) placeholder.style.display = 'flex'
                }
              }}
            />
            <div className="stream-offline-placeholder absolute inset-0 hidden flex-col items-center justify-center gap-2 bg-slate-950 text-slate-600">
              <Video className="h-8 w-8" />
              <span className="text-xs">Stream offline</span>
            </div>
            <div className="absolute top-4 left-4 flex items-center gap-2 px-2.5 py-1 rounded-full bg-slate-950/80 border border-slate-900 backdrop-blur-sm text-[10px] text-slate-300 font-semibold tracking-wide">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
              LIVE
            </div>
          </div>
        </div>

        {/* Recent Activity Timeline */}
        <div className="p-5 rounded-2xl border border-slate-900 bg-slate-950/40 flex flex-col gap-4">
          <div className="flex items-center justify-between border-b border-slate-900 pb-3">
            <span className="text-sm font-semibold text-slate-200">System Diagnostics</span>
            <button
              onClick={() => setActiveTab('health')}
              className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
            >
              Details
            </button>
          </div>

          <div className="flex-1 space-y-4">
            {/* Camera Diagnostic */}
            <div className="flex items-start gap-3">
              <div className={`h-2 w-2 rounded-full mt-1.5 ${health?.camera?.status === 'active' ? 'bg-emerald-400' : 'bg-rose-500 animate-pulse'}`} />
              <div className="flex-1 flex flex-col gap-0.5">
                <span className="text-xs font-semibold text-slate-200">Camera Connection</span>
                <span className="text-[10px] text-slate-500">
                  {health?.camera?.status === 'active' ? 'Connected & capturing frames' : 'Camera offline/disconnected'}
                </span>
              </div>
            </div>

            {/* Storage Diagnostic */}
            <div className="flex items-start gap-3">
              <div className="h-2 w-2 rounded-full bg-emerald-400 mt-1.5" />
              <div className="flex-1 flex flex-col gap-0.5">
                <span className="text-xs font-semibold text-slate-200">Storage Controller</span>
                <span className="text-[10px] text-slate-500">
                  Storage quota and automatic cleanups active
                </span>
              </div>
            </div>

            {/* Log Diagnostic */}
            <div className="flex items-start gap-3">
              <div className="h-2 w-2 rounded-full bg-emerald-400 mt-1.5" />
              <div className="flex-1 flex flex-col gap-0.5">
                <span className="text-xs font-semibold text-slate-200">Log Handler</span>
                <span className="text-[10px] text-slate-500">
                  Monitoring camera log stream for errors
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
