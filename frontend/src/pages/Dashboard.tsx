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
  ExternalLink,
  Copy,
  RefreshCw,
  Link,
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

  const formatTunnelUptime = (sec: number) => {
    if (!sec) return '0s'
    const hrs = Math.floor(sec / 3600)
    const mins = Math.floor((sec % 3600) / 60)
    const secs = sec % 60
    if (hrs > 0) return `${hrs}h ${mins}m ${secs}s`
    if (mins > 0) return `${mins}m ${secs}s`
    return `${secs}s`
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

        {/* Recent Activity Timeline & Cloudflare Tunnel Card */}
        <div className="space-y-6 flex flex-col">
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

          {/* Cloudflare Tunnel Card */}
          <div className="p-5 rounded-2xl border border-slate-900 bg-slate-950/40 flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-slate-900 pb-3">
              <div className="flex items-center gap-2">
                <Link className="h-4 w-4 text-sky-400" />
                <span className="text-sm font-semibold text-slate-200">Cloudflare Tunnel</span>
              </div>
              <div className="flex items-center gap-1.5">
                {/* State badge — color by state */}
                {(() => {
                  const state: string = health?.tunnel?.state || (health?.tunnel?.running ? 'CONNECTED' : 'STOPPED')
                  const colors: Record<string, string> = {
                    CONNECTED: 'bg-emerald-500 animate-pulse',
                    CONNECTING: 'bg-amber-400 animate-pulse',
                    STARTING: 'bg-blue-400 animate-pulse',
                    INSTALLING: 'bg-blue-400 animate-pulse',
                    DEGRADED: 'bg-amber-500 animate-pulse',
                    FAILED: 'bg-rose-500',
                    STOPPING: 'bg-slate-500',
                    STOPPED: 'bg-slate-600',
                  }
                  const textColors: Record<string, string> = {
                    CONNECTED: 'text-emerald-400',
                    CONNECTING: 'text-amber-400',
                    STARTING: 'text-blue-400',
                    INSTALLING: 'text-blue-400',
                    DEGRADED: 'text-amber-400',
                    FAILED: 'text-rose-400',
                    STOPPING: 'text-slate-400',
                    STOPPED: 'text-slate-400',
                  }
                  const dotClass = colors[state] || 'bg-slate-600'
                  const textClass = textColors[state] || 'text-slate-300'
                  return (
                    <>
                      <span className={`h-2 w-2 rounded-full ${dotClass}`} />
                      <span className={`text-xs font-semibold ${textClass}`}>{state}</span>
                    </>
                  )
                })()}
              </div>
            </div>

            {health?.tunnel?.state === 'CONNECTED' || health?.tunnel?.running ? (
              <div className="space-y-4">
                {/* Public URL Box */}
                <div className="flex flex-col gap-1.5">
                  <span className="text-[10px] text-slate-500 font-semibold tracking-wider uppercase">Public URL</span>
                  <div className="flex items-center gap-2 p-2.5 rounded-xl border border-slate-800 bg-slate-950">
                    <span className="text-xs text-sky-400 font-mono select-all truncate flex-1">{health?.tunnel?.url}</span>
                    <button
                      onClick={() => {
                        if (health?.tunnel?.url) {
                          navigator.clipboard.writeText(health.tunnel.url);
                          addNotification('Tunnel URL copied', 'success');
                        }
                      }}
                      className="p-1.5 rounded-lg hover:bg-slate-900 text-slate-400 hover:text-slate-200 transition-colors"
                      title="Copy URL"
                    >
                      <Copy className="h-3.5 w-3.5" />
                    </button>
                    <a
                      href={health?.tunnel?.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-1.5 rounded-lg hover:bg-slate-900 text-slate-400 hover:text-sky-400 transition-colors"
                      title="Open URL"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  </div>
                </div>

                {/* Tunnel Details & QR Code */}
                <div className="flex items-start gap-4">
                  {/* Info stats */}
                  <div className="flex-1 space-y-2">
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-slate-500">Uptime:</span>
                      <span className="font-mono text-slate-300">{formatTunnelUptime(health?.tunnel?.uptime_seconds || 0)}</span>
                    </div>
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-slate-500">Protocol:</span>
                      <span className="font-mono text-slate-300">{health?.tunnel?.protocol || 'quic'}</span>
                    </div>
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-slate-500">Latency:</span>
                      <span className="font-mono text-slate-300">
                        {health?.tunnel?.latency_ms ? `${health.tunnel.latency_ms} ms` : 'Measuring...'}
                      </span>
                    </div>
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-slate-500">Restarts:</span>
                      <span className="font-mono text-slate-300">{health?.tunnel?.restart_count ?? health?.tunnel?.crash_count ?? 0}</span>
                    </div>
                    {health?.tunnel?.arch && (
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-slate-500">Arch:</span>
                        <span className="font-mono text-slate-300">{health.tunnel.arch}</span>
                      </div>
                    )}
                  </div>

                  {/* QR code */}
                  {health?.tunnel?.url && (
                    <div className="relative group rounded-lg overflow-hidden border border-slate-800 bg-white p-1 h-20 w-20 flex items-center justify-center shadow-lg shadow-black/40">
                      <img
                        src={`https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${encodeURIComponent(health.tunnel.url)}`}
                        alt="Tunnel QR Code"
                        className="h-full w-full"
                      />
                    </div>
                  )}
                </div>

                {/* Restart button */}
                <button
                  onClick={async () => {
                    try {
                      const res = await fetch('/tunnel/restart', { method: 'POST' });
                      if (res.ok) {
                        addNotification('Tunnel restart triggered', 'success');
                      } else {
                        addNotification('Failed to restart tunnel', 'error');
                      }
                    } catch {
                      addNotification('Failed to restart tunnel', 'error');
                    }
                  }}
                  className="w-full flex items-center justify-center gap-2 rounded-xl bg-slate-900 hover:bg-slate-850 border border-slate-800 py-2 text-xs font-semibold text-slate-200 transition-colors"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  Restart Tunnel
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-6 text-center text-slate-500 gap-2">
                <Link className="h-8 w-8 text-slate-700" />
                <div className="text-xs">
                  <p className="font-medium text-slate-400">Tunnel {health?.tunnel?.state || 'Offline'}</p>
                  <p className="text-[10px] mt-0.5">
                    {health?.tunnel?.state === 'FAILED'
                      ? 'Tunnel failed after max retries. Use camz tunnel restart to try again.'
                      : health?.tunnel?.state === 'CONNECTING' || health?.tunnel?.state === 'STARTING'
                      ? 'Connecting to Cloudflare... validating endpoint.'
                      : 'Enable and start the tunnel using CLI or config.toml.'}
                  </p>
                </div>
                {health?.tunnel?.enabled && (
                  <button
                    onClick={async () => {
                      const endpoint = health?.tunnel?.state === 'FAILED' ? '/tunnel/restart' : '/tunnel/start';
                      try {
                        const res = await fetch(endpoint, { method: 'POST' });
                        if (res.ok) {
                          addNotification('Tunnel startup requested', 'success');
                        } else {
                          addNotification('Failed to start tunnel', 'error');
                        }
                      } catch {
                        addNotification('Failed to start tunnel', 'error');
                      }
                    }}
                    className="mt-3 flex items-center gap-2 rounded-xl bg-sky-500 hover:bg-sky-600 px-4 py-2 text-xs font-semibold text-slate-950 transition-colors shadow-lg shadow-sky-500/10"
                  >
                    <Play className="h-3.5 w-3.5" />
                    {health?.tunnel?.state === 'FAILED' ? 'Restart Tunnel' : 'Start Tunnel'}
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

